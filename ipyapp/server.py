#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import json
import os
import sys

from glob import glob

# TODO: handle better py3 compat
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import multiprocessing as mp

from argparse import RawDescriptionHelpFormatter

from flask import Flask, request, redirect, render_template, abort, current_app
from werkzeug.exceptions import BadRequestKeyError

from ipyapp.execute import NotebookApp, NotebookAppFormatError
from ipyapp.daemon  import Daemon
from ipyapp.config  import DEBUG, PORT, HOST, PREFIX, PIDFILE, LOGFILE, ERRFILE

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
    nbpaths = [ nbname,
                "%s.ipynb" % nbname, # local notebook file
                "%s/%s.ipynb" % (nbname, nbname), # directory with same-name notebook in it
                ]
    for nbpath in nbpaths:
        if os.path.exists(nbpath):
            return nbpath

    # TODO: Support more than just local files

    # if we haven't returned nbpath yet, raise a not found exception
    raise LookupError('Notebook [%s] not found' % nbpath)

@app.route("/<path:nbname>", methods=['GET','POST'])
def runapp(nbname):

    try:
        nbpath = fetch_nb(nbname)
    except LookupError as ex:
        return (render_template("status.html", message="Cannot locate notebook app: " + nbname),
                404)

    try:
        nba = NotebookApp(nbpath)
        restvars2nbvars(nba, request)
    except NotebookAppFormatError as ex:
        return (render_template("status.html", message="Invalid app notebook file: " + nbpath),
                501)
    except (BadRequestKeyError, ValueError) as ex:
        return (render_template("status.html", message="Invalid inputs: " + ex),
                400)
    # a GET request with no arguments on a notebook with 1+ expected argument
    # results in an input form rendering
    if len(nba.meta['inputs']) > 0 and request.method == 'GET' and len(request.args) == 0:
        return input_form('execute', nba.name, nba.meta)


def restvars2nbvars(nba, request):

    if request.method == 'GET':
        vals = request.args
    else:  # POST, so get from form
        vals = request.form

    if vals['env']:
        nba.env = vals['env']
    # TODO: check if there is an env specified or dependencies

    if 'view' in vals: # only want to view notebook app, not run it
        run = False
    else: # otherwise assume we will run the notebook app
        run = True

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
