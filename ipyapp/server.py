#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import contextlib
import json
import os
import sys

from glob import glob
from Queue import Empty

# TODO: handle better py3 compat
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import multiprocessing as mp

from argparse import RawDescriptionHelpFormatter

from IPython.config import Config
from IPython.nbconvert.exporters.html import HTMLExporter
from IPython.nbconvert.preprocessors.base import Preprocessor
from IPython.nbformat.current import read as nb_read

from flask import Flask, request, redirect, render_template, abort, current_app
from werkzeug.exceptions import BadRequestKeyError


from runipy.notebook_runner import NotebookRunner, NotebookError

from ipyapp        import condaenv
from ipyapp.daemon import Daemon
from ipyapp.config import DEBUG, PORT, HOST, PREFIX, PIDFILE, LOGFILE, ERRFILE

app = Flask(__name__, template_folder='templates')

@app.route("/custom.css")
@app.route("/ipyapp/custom.css")
def custom_css():
    return ""

@app.route("/")
def applist():
    " generate list of all apps "
    # TODO: for now this just lists .ipynb files in the current directory
    #       (and eventually "registered app directories")
    apps = [nb.replace('.ipynb','') for nb in sorted(glob('*.ipynb'))]
    apps.extend([nb.replace('.ipynb','') for nb in sorted(glob('*/*.ipynb'))])

    basedir = os.path.abspath('.')
    return render_template("applist.html", apps=apps, basedir=basedir)

if HOST == '127.0.0.1': # localhost
    from flask import request
    @app.route('/shutdown')
    def shutdown_server():
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            return (render_template('status.html',
                                   message='ERROR: Cannot shutdown. Not running with the Werkzeug Server'),
                    404)
        else:
            func()
            return redirect("/" + PREFIX)
else:
    @app.route('/shutdown')
    def shutdown_server():
        return (render_template('status.html',
                               message='ERROR: Cannot shutdown. Not running from LOCALHOST. Contact system administrator'),
                404)


def input_form(function, nbapp, app_meta):
    params = {}
    return render_template("form.html", nbapp=nbapp,
                           params=app_meta.get('inputs', {}).items(),
                           desc=app_meta.get('desc', ''))

def fetch_nb(nbname):
    """Given the notebook name, do whatever it takes to fetch it locally
    and then pass the file path back"""
    # TODO: Support more than just local files
    nbpath = "%s.ipynb" % nbname # local notebook file
    nbpath2 = "%s/%s.ipynb" % (nbname, nbname) # directory with same-name notebook in it
    if os.path.exists(nbpath):
        return nbpath
    elif os.path.exists(nbpath2):
        return nbpath2
    else:
        raise LookupError('nbpath [%s] not found' % nbpath)

@app.route("/<path:nbname>", methods=['GET','POST'])
def execute(nbname):

    try:
        nbpath = fetch_nb(nbname)
    except LookupError as ex:
        return (render_template("status.html", message="Cannot locate notebook app: " + nbname),
                404)

    nbdir  = os.path.dirname(nbpath)
    nbfile = os.path.basename(nbpath)
    nbapp  = nbfile.replace(".ipynb",'')

    with cd(nbdir): # all execution now happens in the same directory as the notebook
        try:
            nb = json.load(open(nbfile))
        except ValueError:
            return (render_template("status.html", message="Invalid notebook file (not JSON): " + nbpath),
                    501)

        try:
            app_meta = fetch_meta(nb)
        except ValueError:
            return (render_template("status.html", message="Invalid notebook app (last cell must be JSON): " + nbpath),
                    501)
        except KeyError:
            app_meta = dict(inputs=[]) # a no-params notebook

        # a GET request with no arguments on a notebook with 1+ expected argument
        # results in an input form rendering
        if len(app_meta['inputs']) > 0 and request.method == 'GET' and len(request.args) == 0:
            return input_form('execute', nbapp, app_meta)

        input_cell = {
             "cell_type":       "code",
             "collapsed":       False,
             "input":           [],
             "language":        "python",
             "metadata":        {},
             "outputs":         [],
             "prompt_number":   3
        }

        if request.method == 'GET':
            vals = request.args
        else:  # POST, so get from form
            vals = request.form

        # TODO: check if there is an env specified or dependencies

        if 'view' in vals: # only want to view notebook app, not run it
            run = False
        else: # otherwise assume we will run the notebook app
            run = True

        if run:
            if app_meta.has_key('env'): # check for named environment first
                envname = app_meta['env']
            elif app_meta.has_key('deps'): # next see if there are dependencies
                envname = nbapp.replace(' ','-').lower()
                condaenv.create(name=envname, pkgs=app_meta['deps'])
            else:
                envname = None # just use this interpreter

            for var in app_meta['inputs']:
                type = app_meta['inputs'][var]
                try:
                    value = eval("repr({type}('{val}'))".format(type=type, val=vals[var]))
                except (BadRequestKeyError, ValueError) as ex:
                    return (render_template("status.html", message="Invalid input: [%s, %s, %s]" % (var, type, vals[var])),
                            400)

                input_cell['input'].append('{var} = {value}\n'.format(var=var, value=value))

            insert_inputs(nb, input_cell)

        nb_obj    = nb_read(StringIO(json.dumps(nb)), 'json')
        nb_runner = NotebookRunner(nb_obj)
        try:
            if run:
                nb_runner.run_notebook(skip_exceptions=False)
            exporter  = HTMLExporter(extra_loaders=[current_app.jinja_env.loader],
                                     template_file='output.html')
            output, resources = exporter.from_notebook_node(nb_runner.nb, resources=dict(nbapp=nbapp))
            return output
        except Empty as ex:
            return (render_template("status.html",
                        message="ERROR: %s: IPython Kernel timeout" % nbapp),
                    504)
        except (NotImplementedError, NotebookError) as ex:
            return (render_template("status.html",
                        message="ERROR: %s: Notebook contains unsupported feature: %s" % (nbapp, str(ex).split(':')[-1])),
                    504)
        except ImportError:
            return (render_template("status.html",
                        message="ERROR: %s: nodejs or pandoc must be installed" % (nbapp)),
                    504)
def fetch_meta(nb):
    " find app meta data for notebook "
    meta = {'inputs': {}}
    if 'conda.app' in nb['metadata']:
        meta = nb['metadata']['conda.app']
    else:
        # otherwise, look from the last cell backwards for the first "raw" cell,
        # and try to use its source as JSON meta
        for cell in reversed(nb['worksheets'][0]['cells']):
            if cell['cell_type'] == 'raw':
                try:
                    meta = json.loads("".join(cell['source']))
                except ValueError:
                    pass # just use the default
                break

    return meta

def insert_inputs(nb, input_cell):
    nb['worksheets'][0]['cells'][0] = input_cell
    return
    for i, cell in enumerate(nb['worksheets'][0]['cells']):
        if cell['cell_type'] == 'code':
            # replace the first code cell with the input_cell
            nb['worksheets'][0]['cells'][i] = input_cell

@contextlib.contextmanager
def cd(path):
    """A context manager which changes the working directory to the given
    path, and then changes it back to its previous value on exit.
    """
    prev_cwd = os.getcwd()
    if path:
        os.chdir(path)
    yield
    os.chdir(prev_cwd)

def delayed_open(url, delay=3):
    import time
    import webbrowser

    time.sleep(delay)
    webbrowser.open(url)

# TODO: Need something that will work on Windows
class AppServerDaemon(Daemon):

    def run(self, debug=False):
        #raise NotImplementedError("flask somehow defeats daemonization, so this doesn't work")
        import logging
        import time
        import traceback

        if isinstance(self.stdout, str):
            logging.basicConfig(filename=self.stdout,level=self.loglevel)
        else: # assume it is a file handle:
            logging.basicConfig(stream=self.stdout,level=self.loglevel)

        try:
            # daemonization doesn't work if relodader=True (default if debug=True)
            app.run(debug=debug, use_reloader=False, port=self.port)
        except Exception as ex:
            logging.critical(traceback.format_exc())
        logging.critical("looping to restart Flask app server after exception")


def server_parser():

    import argparse

    p = argparse.ArgumentParser(
        formatter_class=RawDescriptionHelpFormatter,
        description="Start a notebook app server",
        # help = descr, # only used in sub-parsers
        epilog="conda-appserver -p 5007"
    )

    p.add_argument(
        "-p", "--port",
        default=PORT,
        help="set the app server port",
    )

    p.add_argument(
        "--host",
        default=HOST,
        help="set the app server ip",
    )
    p.add_argument(
        "action",
        default="start",
        help="specify server action: daemon|start|stop|restart",
    )
    p.set_defaults(func=startserver)

    return p

def serve(host=HOST, port=PORT, action='start', open_web=True):
    " control the server process: start, daemonize, stop, restart, depending on action "

    # TODO: stdout/stderr redirection to files is not working properly
    server = AppServerDaemon(pidfile=PIDFILE, stdout=LOGFILE, stderr=ERRFILE)

    # TODO: this should be part of __init__, but pulled it for debugging
    server.host = host
    server.port = port

    server_url = "http://{host}:{port}".format(host=host, port=port)
    print("server: %s" % server_url)

    if open_web:
        proc = mp.Process(target=delayed_open, kwargs=dict(url=server_url))
        proc.start()

    if action == "daemon":
        if server.running:
            print("daemonized app server already running: %s:%s" % (server.host, server.port))
        else:
            print("starting daemonized app server in the background")
            server.start()
    elif action == "start":
        print("starting app server in the foreground -- press CTRL-C to stop")
        # set output to STDOUT and error to STDERR instead of log files, if starting locally
        server.stdout = sys.stdout
        server.stderr = sys.stderr
        server.run(debug=DEBUG)
    elif action == "stop":
        print("stopping background app server")
        server.stop()
    elif action == "restart":
        print("restarting background app server")
        server.restart()
    elif action == "status":
        if server.running:
            print("app server is running: PID [%s]" % server.pid)
        else:
            print("app server is not running")

def startserver():
    args = server_parser().parse_args()
    serve(port=args.port, action=args.action)

if __name__ == "__main__":
    startserver()
