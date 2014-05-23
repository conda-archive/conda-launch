#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import os
import json

from StringIO import StringIO
from argparse import RawDescriptionHelpFormatter

from IPython.config import Config
from IPython.nbconvert.exporters.html import HTMLExporter
from IPython.nbconvert.preprocessors.base import Preprocessor
from IPython.nbformat.current import read as nb_read, write

from flask import Flask, request, render_template, url_for, abort
from werkzeug.exceptions import BadRequestKeyError


from runipy.notebook_runner import NotebookRunner, NotebookError

from ipyapp.daemon import Daemon
from ipyapp.config import PORT, HOST, PIDFILE, LOGFILE, ERRFILE, DEBUG


app = Flask(__name__, template_folder='templates')

@app.route("/custom.css")
@app.route("/ipyapp/custom.css")
def custom_css():
    return ""

## form
def input_form(function, nbname, app_meta):
    params = {}
    return render_template("form_submit.html", nbname=nbname,
                           params=app_meta.get('inputs', {}).items(),
                           desc=app_meta.get('desc', ''))

def fetch_nb(nbname):
    "Given the notebook name, do whatever it takes to fetch it locally and then pass the file path back"
    # TODO: Support more than just local files
    nbpath = "%s.ipynb" % nbname
    if os.path.exists(nbpath):
        return nbpath
    else:
        raise LookupError('nbpath [%s] not found' % nbpath)

@app.route("/<path:nbname>.ipynb", methods=['GET','POST'])
@app.route("/<path:nbname>", methods=['GET','POST'])
def execute(nbname):

    try:
        nbpath = fetch_nb(nbname)
    except LookupError as ex:
        abort(404)

    nb = json.load(open(nbpath))
    app_meta = json.loads("".join(nb['worksheets'][0]['cells'][-1]['source']))

    # a GET request with no arguments on a notebook with 1+ expected argument results in an input form rendering
    if len(app_meta['inputs']) > 0 and request.method == 'GET' and len(request.args) == 0:
        return input_form('execute', nbname, app_meta)

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

    if request.method == 'GET':
      vals = request.args
    else: # POST, so get from form
      vals = request.form

    for var, type in app_meta['inputs'].iteritems():
        try:
            value = eval("repr({type}('{val}'))".format(type=type, val=vals[var]))
        except BadRequestKeyError as ex:
            print("BadReq for parameter (value, type): [%s, %s]" % (var,type))

        input_cell['input'].append('{var} = {value}\n'.format(var=var, value=value))
        
    nb['worksheets'][0]['cells'][0] = input_cell

    nb_obj      = nb_read(StringIO(json.dumps(nb)), 'json')
    nb_runner   = NotebookRunner(nb_obj)
    nb_runner.run_notebook(skip_exceptions=False)
    exporter    = CustomHTMLExporter(config=Config({'HTMLExporter':{'default_template': 'noinputs.tpl'}}))
    output, resources = exporter.from_notebook_node(nb_runner.nb)

    return output

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

# TODO: Need something that will work on Windows
class AppServerDaemon(Daemon):

    def run(self):
        #raise NotImplementedError("flask somehow defeats daemonization, so this doesn't work")
        import logging
        import time
        import traceback

        logging.basicConfig(filename=self.stdout,level=self.loglevel)
        try:
            app.run(debug=False, port=self.port)  # daemonization doesn't work if debug=True
        except Exception as ex:
            logging.critical(traceback.format_exc())
        logging.critical("looping to restart Flask app server after exception")

def server_parser():

    import argparse

    p = argparse.ArgumentParser(
        formatter_class = RawDescriptionHelpFormatter,
        description = "Start a notebook app server",
        # help = descr, # only used in sub-parsers
        epilog = "conda-appserver -p 5007"
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

def serve(host=HOST, port=PORT, action='start'):
    " control the server process: start, daemonize, stop, restart, depending on action "

    # TODO: stdout/stderr redirection to files is not working properly
    server = AppServerDaemon(pidfile=PIDFILE, stdout=LOGFILE, stderr=ERRFILE)

    # TODO: this should be part of __init__, but pulled it for debugging
    server.host = host
    server.port = port

    if action == "daemon":
        if server.running:
            print("daemonized app server already running: %s:%s" % (server.host, server.port))
        else:
            print("starting daemonized app server in the background")
            server.start()
    elif action == "start":
        print("starting app server in the foreground")
        server.run()
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