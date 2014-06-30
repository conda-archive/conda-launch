#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function

import argparse
import sys

from os.path import abspath, exists

try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode

import webbrowser

from argparse import RawDescriptionHelpFormatter

from ipyapp.config  import MODE, FORMAT, TIMEOUT
from ipyapp.fetch   import fetch_gist, fetch_url
from ipyapp.execute import NotebookApp, run

descr   = "Invoke an IPython Notebook as an app and display the results"
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

def apprun(notebook, mode="open", *args, **kwargs):
    """ Invoke the notebook as an app.  See ipyapp.execute.run for other parameters

        :param notebook: a notebook identifier (path, gist, name)
        :param mode: open [default],stream (to STDOUT), api (return result), quiet (write to disk)
    """

    parts   = notebook.split('/')
    last    = parts[-1].replace(".ipynb", '')
    if exists(notebook):
        notebook_fp = notebook # path to local file
    elif last.isdigit(): # just digits, assume gist
        notebook_fp = fetch_gist(last)
    elif notebook.startswith("http"):
        notebook_fp = fetch_url(notebook)
    else:
        raise NotImplementedError('launch only supports local files, URLs, and GitHub gists -- could not resolve %s' %
                                  notebook)

    result = run(notebook_fp, *args, **kwargs)

    out_fn = "%s.%s" % (notebook, format)
    with open(out_fn, 'w') as fh:
        fh.write(result)

    if mode == 'open':
        webbrowser.open(out_fn)
    elif mode == 'stream':
        print(result)
    elif mode == 'api':
        return result
    elif mode == 'quiet':
        pass # do nothing: output is written to disk
    else:
        pass # do nothing: output is written to disk

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
        "-t", "--timeout",
        default=TIMEOUT,
        help="set a processing timeout",
    )
    p.add_argument(
        "--stream",
        action="store_true",
        default=False,
        help="run notebook app from JSON on STDIN, return results on STDOUT",
    )
    p.add_argument(
        "-e", "--env",
        help="conda environment to use (by name or path)",
    )
    p.add_argument(
        "-m", "--mode",
        default=MODE,
        help="specify processing mode: [open|stream|quiet] default: open [TODO]",
    )
    p.add_argument(
        "-f", "--format",
        default=FORMAT,
        help="result format: [html|md|py|pdf] default:html [TODO]",
    )
    p.add_argument(
        "-c", "--channel",
        action="append",
        help="add a channel that will be used to look for the app [TODO]",
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
        if args.stream: # just execute the STDIN stream in the current python environment, return result on STDOUT
            result = run(sys.stdin, format=args.format)
            if args.mode in "open stream".split():
                print(result)
            else: # don't do anything else
                pass
        else: # create a notebook app object from the CLI args
            nba = NotebookApp(args.notebook, args.nbargs, timeout=args.timeout,
                              mode=args.mode, format=args.format, output=args.output, env=args.env)
            result = nba.startapp()
            if args.mode == "open":
                output_fn = "{name}-output.html"
                open(output_fn, 'w').write(result)
                webbrowser.open(abspath(output_fn))

    except ValueError as ex:
        print("invalid arguments: " + str(ex))


if __name__ == "__main__":
    launchcmd()
