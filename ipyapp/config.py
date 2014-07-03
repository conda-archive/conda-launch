import logging
import os
import random
import string

# TODO: could (should?) look for this info from a config file

LOG_LEVEL   = logging.WARNING
DEBUG       = False         # will stop server daemonizer from working if set to True

# Defaults:

# run
FORMAT      = 'html' # output format defaults to HTML
MODE        = 'open' # processing mode defaults to "open results"
TIMEOUT     = 10     # seconds
FIXED_DEPS  = "ipython ipython-notebook runipy jinja2 six setuptools conda-api conda-launch".split()
TEMPLATE    = "output.html"

# server
HOST    = "127.0.0.1"
PREFIX  = ""            # URL path prefix
SEARCH  = ""            # Location of apps
PORT    = 5007

# process
PIDFILE = os.path.expanduser("~/.appserver_pid")
LOGFILE = os.path.expanduser("~/.appserver_log")
ERRFILE = os.path.expanduser("~/.appserver_err")

def key_generator(size=20, chars=string.ascii_letters + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

SECRET_KEY = key_generator()