import atexit
import json
import os
import sys
import time

from abc import ABCMeta, abstractmethod
from signal import SIGTERM
from StringIO import StringIO

from IPython.config import Config
from IPython.nbconvert.exporters.html import HTMLExporter
from IPython.nbformat.current import read as nb_read, write

from flask import Flask, request, render_template, url_for
from werkzeug.exceptions import BadRequestKeyError

from runipy.notebook_runner import NotebookRunner, NotebookError

from ipyapp.config import PORT, PIDFILE, LOGFILE, ERRFILE

app = Flask(__name__, template_folder='templates')

@app.route("/custom.css")
@app.route("/ipyapp/custom.css")
def custom_css():
    return ""

## form
@app.route("/<nbname>.ipynb/form")
@app.route("/<nbname>/form")
def nb_form(nbname):
    params = {}
    nb = json.load(open(nbname + ".ipynb"))
    app_meta = json.loads("".join(nb['worksheets'][0]['cells'][-1]['source']))
    for var, t in app_meta['inputs'].iteritems():
        params[var] = None
    return render_template("form_submit.html", params = params, nbname = nbname)

## post
@app.route("/<nbname>.ipynb", methods=['GET','POST'])
@app.route("/<nbname>", methods=['GET','POST'])
def nb_post(nbname):

    print "You may submit new parameters using",url_for('nb_form', nbname=nbname)

    input_cell = json.loads("""
    { 
     "cell_type": "code",
     "collapsed": false,
     "input": [],
     "language": "python",
     "metadata": {},
     "outputs": [],
     "prompt_number": 3
    }
""")

    nb = json.load(open(nbname + ".ipynb"))
    app_meta = json.loads("".join(nb['worksheets'][0]['cells'][-1]['source']))

    for var, t in app_meta['inputs'].iteritems():
        try:
            if request.method == 'GET':
              value = eval("repr({cast}('{expr}'))".format(cast=t, expr=request.args[var]))
            else:
              value = eval("repr({cast}('{expr}'))".format(cast=t, expr=request.form[var]))
        except BadRequestKeyError as ex:
            value = eval("repr({cast}())".format(cast=t))
            print "BadReq for parameter key/type",var,t
        input_cell['input'].append('{var} = {value}\n'.format(var=var, value=value))
        
    nb['worksheets'][0]['cells'][0] = input_cell

    nb_obj      = nb_read(StringIO(json.dumps(nb)), 'json')
    nb_runner   = NotebookRunner(nb_obj)
    nb_runner.run_notebook(skip_exceptions=False)
    exporter    = CustomHTMLExporter(config=Config({'HTMLExporter':{'default_template': 'noinputs.tpl'}}))
    output, resources = exporter.from_notebook_node(nb_runner.nb)

    return output

from IPython.nbconvert.preprocessors.base import Preprocessor

class AppifyNotebook(Preprocessor):
    def preprocess_cell(self, cell, resources, cell_index):
        if cell.cell_type == 'raw':
            cell.source = ''
        if hasattr(cell, "prompt_number"):
            del cell.dict()['prompt_number']
        if hasattr(cell, "input"):
          del cell.dict()['input']
        return cell, resources

class CustomHTMLExporter(HTMLExporter):

    def __init__(self, **kw):
        super(CustomHTMLExporter, self).__init__(**kw)
        self.register_preprocessor(AppifyNotebook, enabled=True)

def start_local_server(port=PORT):
    " forks a separate process to run the server on localhost "

    daemon = AppServerDaemon(port=port, stdout=LOGFILE, stderr=ERRFILE)
    daemon.start()

def serve(port=PORT):
    app.run(debug=True, port=port)


class Daemon(object):
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method

    Adapted from work by Sander Marechal, which he has released into the public domain.
    """

    __meta__ = ABCMeta

    def __init__(self, pidfile, stdin='/dev/null', stdout='/dev/null', stderr='/dev/null'):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile

    def daemonize(self):
        """
        do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        with open('entry.log', 'a+') as debuglog:
            debuglog.write('daemonize %s\n' % os.getpid())

        try:
            pid = os.fork()
            if pid > 0:
                # exit first parent
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # decouple from parent environment
        os.setsid()
        os.umask(0)

        # do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # exit from second parent to daemonize
                sys.exit(0)
        except OSError, e:
            sys.stderr.write("fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            sys.exit(1)

        # redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = file(self.stdin, 'r')
        so = file(self.stdout, 'a+')
        se = file(self.stderr, 'a+', 0)
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid())
        file(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        with open('entry.log', 'a+') as debuglog:
            import glob
            debuglog.write('delpid %s\n' % os.getpid())
            debuglog.write("%s\n" % glob.glob(self.pidfile))

        os.remove(self.pidfile)

    def start(self):
        """
        Start the daemon
        """
        # Check for a pidfile to see if the daemon already runs
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError: # good, we don't want it to exist
            pid = None

        with open('entry.log', 'a+') as debuglog:
            import glob
            debuglog.write('start %s\n' % os.getpid())
            debuglog.write("%s\n" % glob.glob(self.pidfile))

        if pid:
            message = "pidfile %s already exist. Daemon already running?\n"
            sys.stderr.write(message % self.pidfile)
            sys.exit(1)

        # Start the daemon
        self.daemonize()
        self.run()

    def stop(self):
        """
        Stop the daemon
        """
        # Get the pid from the pidfile

        with open('entry.log', 'a+') as debuglog:
            import glob
            debuglog.write('stop %s\n' % os.getpid())
            debuglog.write("%s\n" % glob.glob(self.pidfile))

        try:
            pf = file(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)
            return  # not an error in a restart

        # Try killing the daemon process
        try:
            while 1:
                os.kill(pid, SIGTERM)
                time.sleep(0.1)
        except OSError, err:
            err = str(err)
            if err.find("No such process") > 0:
                if os.path.exists(self.pidfile):
                    os.remove(self.pidfile)
            else:
                print str(err)
                sys.exit(1)

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    @abstractmethod
    def run(self):
        """
        You should override this method when you subclass Daemon. It will be called after the process has been
        daemonized by start() or restart().
        """
        raise NotImplementedError("Need a concrete implementation of the daemon run method")

class AppServerDaemon(Daemon):

    def __init__(self, pidfile=None, port=PORT, *args, **kwargs):
        self.port = port
        if not pidfile:
            pidfile = PIDFILE
        super(AppServerDaemon, self).__init__(pidfile, *args, **kwargs)

    def run(self):
        serve(port=self.port)


if __name__ == "__main__":
    serve()
