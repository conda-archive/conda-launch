#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function

import argparse
import multiprocessing as mp
import time

from os.path import abspath, exists

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

import webbrowser
import requests

from argparse import RawDescriptionHelpFormatter

from ipyapp.config import HOST, PORT


descr = "Launch an IPython Notebook as an app"
example = """
examples:
    conda launch MyNotebookApp.ipynb

"""

def url2path(notebook):
    " convert a url to a path. e.g. http://example.com/a/b.ipynb -> url/example.com/a/b.ipynb "
    from urlparse import urlparse

    url = urlparse(notebook)
    if url.scheme == "http":
        path = ['url']
    elif url.scheme == "https":
        path = ['urls']
    path.extend([url.netloc, url.path])

    return path

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

    if not server:
        import ipyapp.server
        server_proc = mp.Process(target=ipyapp.server.serve, kwargs=dict(host=HOST, port=PORT, action="start"))
        server_proc.daemon = False
        server_proc.start()
        server = "http://{host}:{port}".format(host=HOST, port=PORT)
    else:
        server_proc = None

    urlargs = []
    path    = []
    parts   = notebook.split('/')
    last    = parts[-1].replace(".ipynb", '')
    if exists(notebook): # path to local file
        path.extend(parts[:-1])
        path.append(last)
    elif last.isdigit(): # just digits, assume gist
        path.extend(['gist',last])
    elif notebook.startswith("http"):
        path.extend(url2path(notebook))
    else:
        raise NotImplementedError('launch only supports local files, URLs, and GitHub gists')

    if args:
        urlargs.extend(tuple(arg.split("=")) for arg in args)

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
    except (ValueError, TypeError):
        raise ValueError("launch arguments must be valid pairs, such as 'a=7'\n%s" % str(urlargs))

    if urlargs_str:
        urlargs_str = "?" + urlargs_str

    url = "{prefix}/{path}{urlargs_str}".format(prefix=server, path='/'.join(path), urlargs_str=urlargs_str)
    if mode == 'open':
        webbrowser.open(url, )
    elif mode == 'fetch':
        r = requests.get(url)
        if r.status_code == 200:
            return r.text
        else:
            r.raise_for_status()

    if server_proc: # if we started a server process, then we're going to wait for it to finish
        print("waiting for app server to be terminated.  Press CTRL-C to end now.")
        server_proc.join()

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


def launchcmd():

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


if __name__ == "__main__":
    launchcmd()
