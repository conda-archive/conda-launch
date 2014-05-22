#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

import argparse
import atexit
import json
import os
import sys
import time

from abc import ABCMeta, abstractmethod
from signal import SIGTERM
from StringIO import StringIO
from argparse import RawDescriptionHelpFormatter

from IPython.config import Config
from IPython.nbconvert.exporters.html import HTMLExporter
from IPython.nbformat.current import read as nb_read, write

from flask import Flask, request, render_template, url_for
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

    print("You may submit new parameters using",url_for('nb_form', nbname=nbname))

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
            print("BadReq for parameter key/type",var,t)
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

# TODO: Need something that will work on Windows
class AppServerDaemon(Daemon):

    def run(self):
        #raise NotImplementedError("flask somehow defeats daemonization, so this doesn't work")
        import logging
        logging.basicConfig(filename=self.stdout,level=self.loglevel)
        app.run(debug=False, port=self.port)

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

def startserver():
    args = server_parser().parse_args()
    serve(port=args.port, action=args.action)

if __name__ == "__main__":
    startserver()