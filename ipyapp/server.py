#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import json
import os
import sys
import multiprocessing as mp

from os.path    import basename
from functools  import partial
from glob       import glob
from logging    import info, debug
from argparse   import RawDescriptionHelpFormatter

# TODO: handle better py3 compat (with six?)
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from jinja2     import Environment, PackageLoader
from flask      import Flask, request, redirect, render_template, abort, current_app
from werkzeug.exceptions import BadRequestKeyError

from IPython.nbformat.current             import reads_json as nb_read_json
from IPython.nbconvert.exporters.html     import HTMLExporter
from IPython.nbconvert.exporters.markdown import MarkdownExporter
from IPython.nbconvert.exporters.python   import PythonExporter

from ipyapp.execute import run, NotebookApp, NotebookAppFormatError, NotebookAppExecutionError, NotebookAppError
from ipyapp.daemon  import Daemon
from ipyapp.config  import DEBUG, PORT, HOST, PREFIX, PIDFILE, LOGFILE, ERRFILE, TIMEOUT, FORMAT, LOG_LEVEL, SECRET_KEY

app = Flask(__name__, template_folder='templates')
app.debug = DEBUG # NOTE: app.debug = True will stop daemonizer from working!

try:
    from flask_debugtoolbar import DebugToolbarExtension
    app.config['SECRET_KEY'] = SECRET_KEY
    toolbar = DebugToolbarExtension(app)
except Exception:
    # I guess flask-debugtoolbar isn't installed, so just ignore this
    pass

@app.route("/custom.css")
@app.route("/ipyapp/custom.css")
def custom_css():
    return ""

@app.route("/")
def applist():
    " generate list of all apps "
    # TODO: for now this just lists .ipynb files in the current directory and one directory down
    #       (and eventually "registered app directories")
    apps = [nb.replace('.ipynb','') for nb in sorted(glob('*.ipynb'))]
    apps.extend([nb.replace('.ipynb','') for nb in sorted(glob('*/*.ipynb'))])

    basedir = os.path.abspath('.')
    return render_template("applist.html", apps=apps, basedir=basedir)

if HOST == '127.0.0.1': # shutdown web option only available when running exclusively on localhost
    @app.route('/shutdown')
    def shutdown_server():
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            return (render_template('server_status.html',
                                   message='ERROR: Cannot shutdown. Not running with the Werkzeug Server'),
                    404)
        else:
            func()
            return redirect("/" + PREFIX)
else:
    @app.route('/shutdown')
    def shutdown_server():
        return (render_template('server_status.html',
                               message='ERROR: Cannot shutdown. Not running from LOCALHOST. Contact system administrator'),
                404)

@app.route('/favicon.ico')
def favicon():
    return app.send_static_file('favicon.ico')

def fetch_nb(nbname):
    """Given the notebook name, find it locally and return the full path"""
    nbpaths = [ nbname,
                "%s.ipynb" % nbname, # local notebook file
                "%s/%s.ipynb" % (nbname, nbname), # directory with same-name notebook in it
                ]
    for nbpath in nbpaths:
        if os.path.exists(nbpath):
            return nbpath

    # if we haven't returned nbpath yet, raise a not found exception
    raise LookupError('Notebook [%s] not found' % nbpath)

# FIXME: Currently `nbname` could probably have relative or `..` paths that will access unintended files
@app.route("/<path:nbname>", methods=['GET','POST'])
def runapp(nbname):

    err = "" # initialize error string returned by notebook app invocation -- required for exception messages
    try:
        nbpath = fetch_nb(nbname)
    except LookupError as ex:
        return (render_template("server_status.html", message="Cannot locate notebook app: " + nbname),
                404)

    jinja_env = Environment(loader=PackageLoader('ipyapp', 'templates'))
    status    = HTMLExporter(extra_loaders=[current_app.jinja_env.loader], template_file='server_status.html')

    try:

        options = dict(env=None, timeout=TIMEOUT, output=None, view=False, format=FORMAT)

        if request.method == 'GET':
            nbargs_dict = request.args.to_dict()
        else:  # POST, so get from form
            nbargs_dict = request.form.to_dict()

        debug('options (before): %s' % options)
        debug('nbargs_dict (before): %s' % nbargs_dict)

        update_options_nbargs(options,nbargs_dict)

        debug('options (before): %s' % options)
        debug('nbargs_dict (before): %s' % nbargs_dict)

        info("notebook arguments:" + str(nbargs_dict))

        if options['view']: # just view notebook, don't re-execute
            info("app view only")
            nbtxt      = open(nbpath).read()
            name       = basename(nbpath).replace('.ipynb', '')

        else:
            info("creating NotebookApp")
            nba = NotebookApp(nbpath, template="server_output.html", **options)
            name = nba.name
            info("nba.inputs: %s" % nba.inputs)
            info("nbargs_dict: %s" % nbargs_dict)
            if len(nba.inputs) > 0 and len(nba.inputs) > len(nbargs_dict) and request.method == "GET":
                info("generate app form, since not enough inputs were provided")
                singles = {k:v for k,v in nba.inputs.iteritems() if v != "para"}
                multis = [k for k,v in nba.inputs.iteritems() if v == "para"]
                return (render_template("form.html", nbapp=nba.name, desc=nba.desc,
                    params=sorted(singles.items()),
                    multiline=sorted(multis),
                    ),
                    200)
            else:
                nba.set_nbargs(**nbargs_dict)
                (nbtxt, err)  = nba.startapp()

        if options['format']=='html':
            Exporter = partial(HTMLExporter,
                               extra_loaders=[current_app.jinja_env.loader],
                               template_file="server_output.html")
        elif options['format']=='md' or options['format']=='markdown':
            Exporter = MarkdownExporter
        elif options['format']=='py' or options['format']=='python':
            Exporter = PythonExporter
        exporter = Exporter()

        nb_obj = nb_read_json(nbtxt)
        html, resources = exporter.from_notebook_node(nb_obj, resources=dict(nbapp=name))

        return (html, 200)

    except (IOError, ValueError, NotebookAppFormatError) as ex:
        return (render_template("server_status.html",
                                message="Notebook App [%s] invalid file" % nbpath,
                                exception=ex,
                                error=err),
                501)
    except (BadRequestKeyError, KeyError, ValueError, TypeError) as ex:
        # TODO: tighten this up so invalid inputs are caught in a way that nba.name can be used
        return (render_template("server_status.html",
                                message="Notebook App [%s] invalid inputs" % nbpath,
                                exception=ex,
                                error=err),
                400)
    except NotebookAppExecutionError as ex:
        return (render_template("server_status.html",
                                message='Notebook App [%s] failed to run' % nba.name,
                                exception=ex,
                                error=err),
                400)
    except Exception as ex:
        return (render_template("server_status.html",
                                message='Notebook App [%s] unknown error' % nbpath,
                                exception=ex,
                                error=err),
                400)


def update_options_nbargs(options, rest_dict):
    "Update notebook app options from REST arguments dict and remove server args from nbargs"
    if 'timeout' in rest_dict:
        options['timeout'] = int(rest_dict['timeout'])
    if 'view' in rest_dict:
        options['view'] = bool(rest_dict['view'])
    if 'format' in rest_dict:
        options['view'] = rest_dict['format']
    if 'output' in rest_dict:
        options['output'] = rest_dict['output']
    if 'env' in rest_dict:
        options['env'] = rest_dict['env']

    for key in "timeout view env output format".split():
        if key in rest_dict:
            del rest_dict[key]


def web_help(nba):
    params = []
    for input, type in nba.inputs.items():
        params.append("{input}=[{type}] ".format(input=input, type=type))
    return params


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
        proc = mp.Process(target=delayed_open, kwargs=dict(url=server_url, delay=0))
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
