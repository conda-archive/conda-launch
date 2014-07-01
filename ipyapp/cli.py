#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function

import argparse
import sys
import webbrowser

from argparse import RawDescriptionHelpFormatter
from os.path  import abspath

# TODO: could use six instead
try:
    from urllib import urlencode, pathname2url
except ImportError:
    from urllib.parse   import urlencode
    from urllib.request import pathname2url

from ipyapp.config  import MODE, FORMAT, TIMEOUT
from ipyapp.execute import NotebookApp, run

descr   = "Invoke an IPython Notebook as an app and display the results"
example = """
examples:
    conda launch MyNotebookApp.ipynb a=12 b="some string"
"""

def launch_parser():

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
        help="specify processing mode: [open|stream|quiet] (default: %(default)s) [TODO] ",
    )
    p.add_argument(
        "-f", "--format",
        default=FORMAT,
        help="result format: [html|md|py|pdf] (default: %(default)s) [TODO]",
    )
    p.add_argument(
        "-c", "--channel",
        action="append",
        help="add a channel that will be used to look for the app [TODO]",
    )
    p.add_argument(
        "-o", "--output",
        help="specify a single variable to return from processed notebook [TODO]",
    )
    p.add_argument(
        "--override",
        action="store_true",
        default=False,
        help="override values set in notebook app",
    )
    p.add_argument(
        "-t", "--timeout",
        default=TIMEOUT,
        help="set a processing timeout (default: %(default)s sec)",
    )
    p.add_argument(
        "notebook",
        nargs='?',
        help="notebook app name, URL, or path",
    )
    p.add_argument(
        'nbargs',
        nargs=argparse.REMAINDER,
        help="arguments to pass to notebook app",
    )

    p.set_defaults(func=launchcmd)

    return p


def launchcmd():

    args = launch_parser().parse_args()

    try:
        if args.stream: # just execute the STDIN stream as JSON in the current python environment, return result on STDOUT
            try:
                result = run(sys.stdin.read(), format=args.format)
                if args.mode in "open stream".split(): # in stream mode, open and tream are equivalent
                    print(result)
                else: # don't do anything else
                    pass
            except ValueError as ex:
                print('bad notebook format: could not decode JSON')
        else: # create a notebook app object from the CLI args

            if args.view: # get a view of the current content, don't re-invoke
                nba = NotebookApp(args.notebook)
                result = run(nba.json, view=args.view)
            else: # re-process notebook with new arguments

                if "-h" in args.nbargs or "--help" in args.nbargs:
                    nba = NotebookApp(args.notebook)
                    help(nba)
                    return

                try:
                    nbargs_dict = dict(pair.split('=',1) for pair in args.nbargs) # convert args from list to dict
                    nba = NotebookApp(args.notebook, nbargs_dict, timeout=args.timeout,
                                      mode=args.mode, format=args.format, output=args.output, env=args.env,
                                      override=args.override)
                    result = nba.startapp()
                except KeyError as ex:
                    print('ERROR: Notebook parameter [%s] not found' % str(ex))
                    nba = NotebookApp(args.notebook)
                    help(nba)
                    return

            if nba.mode == "open":
                output_fn = "{name}-output.html".format(name=nba.name)
                open(output_fn, 'w').write(result)
                webbrowser.open('file://' + pathname2url(abspath(output_fn)))
            elif nba.mode == "stream":
                print(result)
            elif nba.mode == "quiet":
                # do nothing
                pass

    except ValueError as ex:
        print("invalid arguments: " + str(ex))

def help(nba):
    print("usage: conda launch {file} ".format(file=nba.nbfile), end='')
    for input, type in nba.inputs.items():
        print("{input}=[{type}] ".format(input=input, type=type), end='')
    print()
    return

if __name__ == "__main__":
    launchcmd()
