import os

# TODO: could (should?) look for this info from a config file

# Defaults:

HOST    = "127.0.0.1"
PREFIX  = ""            # URL path prefix
SEARCH  = ""            # Location of apps
PORT    = 5007
DEBUG   = True          # will stop daemonizer from working if set to True

PIDFILE = os.path.expanduser("~/.appserver_pid")
LOGFILE = os.path.expanduser("~/.appserver_log")
ERRFILE = os.path.expanduser("~/.appserver_err")
