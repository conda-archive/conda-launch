# (c) 2012-2014 Continuum Analytics, Inc. / http://continuum.io
# All Rights Reserved
#
# conda is distributed under the terms of the BSD 3-clause license.
# Consult LICENSE.txt or http://opensource.org/licenses/BSD-3-Clause.

from __future__ import print_function, division, absolute_import

from argparse import RawDescriptionHelpFormatter
import argparse

descr = "Launch an IPython Notebook as an app"
example = """
examples:
    conda launch MyNotebookApp.ipynb

"""

def configure_launch_parser(p):
    # The following is from the previous life of cli as conda.cli.main_launch
    # p = sub_parsers.add_parser(
    #    'launch',
    #    formatter_class = RawDescriptionHelpFormatter,
    #    description = descr,
    #    help = descr,
    #    epilog = example,
    # )
    # common.add_parser_install(p)
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

def configure_server_parser(p):
    p.add_argument(
        "-p", "--port",
        default=5007,
        help="set the app server port",
    )
    p.add_argument(
        "-d", "--daemon",
        action="store_true",
        default=False,
        help="start server in daemon mode",
    )
    p.set_defaults(func=startserver)

def launchcmd():
    import argparse
    from ipyapp.client import launch

    parser = argparse.ArgumentParser(
        formatter_class = RawDescriptionHelpFormatter,
        description = descr,
        # help = descr, # only used in sub-parsers
        epilog = example,
    )

    configure_launch_parser(parser)
    args = parser.parse_args()
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

def startserver():
    import argparse
    from ipyapp.server import serve, start_local_server

    parser = argparse.ArgumentParser(
        formatter_class = RawDescriptionHelpFormatter,
        description = "Start a notebook app server",
        # help = descr, # only used in sub-parsers
        epilog = "conda-appserver -p 5007"
    )

    configure_server_parser(parser)
    args = parser.parse_args()
    if args.daemon:
        start_local_server(port=args.port)
    else:
        serve(port=args.port)

if __name__ == "__main__":
    launchcmd()
