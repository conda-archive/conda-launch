#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function

import argparse
import json
import os
import subprocess
import sys

from argparse import RawDescriptionHelpFormatter

from ipyapp.config import HOST, PORT


descr = "Launch an IPython Notebook as an app"
example = """
examples:
    conda launch MyNotebookApp.ipynb

"""

def launch(notebook,
        args=None,
        server=None,
        env=None,
        channels=None,
        output=None,
        view=False,
        mode="open",
        format=None):
    """ Launch the app view of the specified notebook, using a server.
        If the server is not specified, assume localhsot and (try to)
        start it.

        :param notebook: a notebook identifier (path, gist, name)
        :param args: input arguments to pass to the notebook
        :param server: (protocol, host, port) string specifying server
        :param env: environment to use for notebook app invocation
        :param channels: list of channels for server to use to find apps and deps
        :param output: specify a particular artifact to return from executed app
        :param view: view mode only (don't execute notebook, just render and return)
        :param mode: open (default) opens browser, fetch returns result on STDOUT
        :param format: allows specification of result format: html (default), pdf
    """

    from os.path import abspath, exists
    from urllib import urlencode
    import webbrowser
    import requests



    if not server:
        # TODO: Once the daemonized server is fixed, change this
        import socket;
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1',PORT))
        if result: # we were able to make a connection, so nothing else is bound to PORT
            del result
            print("Start an app server first: conda-appserver")
            sys.exit(1)
        else: # we weren't able to make a connection, so assume the appserver is running
            server = "http://{host}:{port}".format(host=HOST, port=PORT)

        # This is what *should* work, but server daemonization is broken
        if False:
            import ipyapp.server
            pid = os.fork() # need to create an independent process to start the daemonized server
            if pid: # then we are in the client:
                server = "http://{host}:{port}".format(host=HOST, port=PORT)
            else: # then we are in the process where the daemonized server should start:
                ipyapp.server.serve(daemon=True, port=PORT)
                sys.exit(1) # shouldn't get here: daemonized zerver should self-exit


    urlargs = []
    path    = []
    if exists(notebook): # path to local file
        urlargs.append(('nbfile',abspath(notebook)))
    elif notebook.isdigit(): # just digits, assume gist 
        urlargs.append(('gist',notebook))
    else:
        path.append(notebook)

    if args:
        urlargs.extend(arg.split("=") for arg in args)

    if env:
        urlargs.append(('env',env))

    if channels:
        urlargs.append(('channels',",".join(channels)))

    if view:
        urlargs.append(('view','t'))

    if output:
        urlargs.append(('output', output))

    if format:
        urlargs.append(('format', format))

    try:
        urlargs_str = urlencode(urlargs).replace("%2F","/")
    except ValueError:
        raise ValueError("launch arguments must be valid pairs, such as 'a=7'")

    url = "{prefix}/{path}?{urlargs_str}".format(prefix=server, path='/'.join(path), urlargs_str=urlargs_str)
    if mode == 'open':
        webbrowser.open(url)
    elif mode == 'fetch':
        r = requests.get(url)
        if r.status_code == 200:
            return r.text
        else:
            r.raise_for_status()

def launchcmd():

    from ipyapp.client import launch

    args = launch_parser().parse_args()

    try:
        launch(
            notebook    = args.notebook,
            args        = args.nbargs,
            server      = args.server,
            env         = args.env,
            channels    = args.channel,
            view        = args.view
        )
    except ValueError as ex:
        print("invalid arguments: " + str(ex))


def launch_parser():
    # The following is from the previous life of cli as conda.cli.main_launch
    # p = sub_parsers.add_parser(
    #    'launch',
    #    formatter_class = RawDescriptionHelpFormatter,
    #    description = descr,
    #    help = descr,
    #    epilog = example,
    # )
    # common.add_parser_install(p)

    import argparse

    p = argparse.ArgumentParser(
        formatter_class = RawDescriptionHelpFormatter,
        description = descr,
        # help = descr, # only used in sub-parsers
        epilog = example,
    )

    p.add_argument(
        "-v", "--view",
        action="store_true",
        default=False,
        help="view notebook app (do not execute or prompt for input)",
    )
    p.add_argument(
        "-s", "--server",
        help="app server (protocol, hostname, port)",
    )
    p.add_argument(
        "-e", "--env",
        help="conda environment to use (by name or path, relative to app server)",
    )
    p.add_argument(
        "-c", "--channel",
        action="append",
        help="add a channel that will be used to look for the app or dependencies",
    )
    p.add_argument(
        "notebook",
        help="notebook app name, URL, or path",
    )
    p.add_argument(
        'nbargs',
        nargs=argparse.REMAINDER
    )

    p.set_defaults(func=launchcmd)

    return p

if __name__ == "__main__":
    launchcmd()
