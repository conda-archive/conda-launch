import os

# TODO: could (should?) look for this info from a config file

# Defaults:

# run
FORMAT      = 'html' # output format defaults to HTML
MODE        = 'open' # processing mode defaults to "open results"
TIMEOUT     = 10     # seconds
FIXED_DEPS  = "ipython ipython-notebook runipy jinja2 six setuptools conda-api conda-launch".split()

# server
HOST    = "127.0.0.1"
PREFIX  = ""            # URL path prefix
SEARCH  = ""            # Location of apps
PORT    = 5007
DEBUG   = False          # will stop daemonizer from working if set to True

# process
PIDFILE = os.path.expanduser("~/.appserver_pid")
LOGFILE = os.path.expanduser("~/.appserver_log")
ERRFILE = os.path.expanduser("~/.appserver_err")
