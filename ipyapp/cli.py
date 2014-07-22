#!/usr/bin/env python

# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function

import argparse
import json
import logging
import re
import sys
import webbrowser

from argparse   import RawDescriptionHelpFormatter
from functools  import partial
from os.path    import abspath

# TODO: use six instead? added dependency...
try:
    from urllib         import urlencode
    from urllib         import pathname2url
except ImportError:
    from urllib.parse   import urlencode
    from urllib.request import pathname2url

from jinja2     import Environment, PackageLoader

from IPython.nbformat.current             import reads_json as nb_read_json
from IPython.nbconvert.exporters.html     import HTMLExporter
from IPython.nbconvert.exporters.markdown import MarkdownExporter
from IPython.nbconvert.exporters.python   import PythonExporter


from ipyapp.config  import MODE, FORMAT, TIMEOUT, TEMPLATE, LOG_LEVEL
from ipyapp.execute import NotebookApp, NotebookAppExecutionError, run

logging.basicConfig(level=LOG_LEVEL)
log = logging.getLogger(__name__)

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
        "--template",
        default=TEMPLATE,
        help="specify an alternative output template file",
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

    err = "" # initialize error string returned by invoking notebook app (used in exception messages)

    try:
        args = launch_parser().parse_args()

        if "-h" in args.nbargs or "--help" in args.nbargs: # print help for this notebook and exit

            log.debug('notebook app help')
            nba = NotebookApp(args.notebook)
            help(nba)
            return 0

        elif args.stream: # just execute the STDIN stream as JSON in the current python environment, return result on STDOUT

            log.debug('notebook app stream processing')
            nbtxt = sys.stdin.read()
            nbjson = run(nbtxt, args.output, args.view)
            print(json.dumps(nbjson))
            return 0

        elif args.view: # get a view of the current content, don't re-invoke

            log.debug('notebook app view only')
            nba = NotebookApp(args.notebook)
            nbtxt = run(json.dumps(nba.json), view=args.view)

        else: # regular notebook app processing

            log.debug('notebook app regular execution')
            nbargs_dict = dict(pair.split('=',1) for pair in args.nbargs) # convert args from list to dict
            nba = NotebookApp(args.notebook, timeout=args.timeout,
                              mode=args.mode, format=args.format, output=args.output, env=args.env,
                              override=args.override)
            nba.set_nbargs(**nbargs_dict)
            (nbtxt, err) = nba.startapp()

            log.debug('finished regular execution')


        jinja_env = Environment(loader=PackageLoader('ipyapp', 'templates'))
        template = jinja_env.get_template('status.html')

        format = args.format.lower()
        if format=='html':
            Exporter = partial(HTMLExporter,
                               extra_loaders=[jinja_env.loader],
                               template_file="output.html")
        elif format=='md' or format=='markdown':
            Exporter = MarkdownExporter
        elif format=='py' or format=='python':
            Exporter = PythonExporter
        exporter = Exporter()

        log.debug('create notebook object (JSON) from JSON text string')
        nb_obj = nb_read_json(nbtxt)
        log.debug('convert notebook to HTML via exporter')
        result, resources = exporter.from_notebook_node(nb_obj, resources=dict(nbapp=nba.name))

        if nba.mode == "open":
            output_fn = "{name}-output.html".format(name=nba.name)
            open(output_fn, 'w').write(result)
            webbrowser.open('file://' + pathname2url(abspath(output_fn)))
        elif nba.mode == "stream":
            print(result)
        elif nba.mode == "quiet":
            # do nothing
            pass

    except IOError as ex:
        sys.stderr.write('ERROR: Notebook App [%s] could not be opened\n' % args.notebook)
        return 1
    except ValueError as ex:
        sys.stderr.write('ERROR: Notebook App: could not decode JSON stream\n%s\n' % err)
        #sys.stderr.write(format_exception(ex))
        return 1
    except TypeError as ex:
        sys.stderr.write('ERROR: Notebook App parameter error\n%s\n' % str(ex))
        help(nba)
        return 2
    except NotebookAppExecutionError as ex:
        sys.stderr.write('ERROR: Notebook App [%s] failed to run:\n%s\n%s\n' % (args.notebook, err, ex))
        help(nba) # created OK, so can use nba
        return 3
    except Exception as ex:
        sys.stderr.write('ERROR: Notebook App unknown error: %s\n%s\n' % (err, ex))
        sys.stderr.write(format_exception(ex) + "\n")

        return 4

def help(nba):
    print("usage: conda launch {file} ".format(file=nba.nbfile), end='')
    for input, type in nba.inputs.items():
        print("{input}=[{type}] ".format(input=input, type=type), end='')
    print()
    return

import traceback

def format_exception(e):
    exception_list = traceback.format_stack()
    exception_list = exception_list[:-2]
    exception_list.extend(traceback.format_tb(sys.exc_info()[2]))
    exception_list.extend(traceback.format_exception_only(sys.exc_info()[0], sys.exc_info()[1]))

    exception_str = "Traceback (most recent call last):\n"
    exception_str += "".join(exception_list)
    # Removing the last \n
    exception_str = exception_str[:-1]

    return exception_str

if __name__ == "__main__":
    launchcmd()
