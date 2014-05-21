import os

HOST    = "127.0.0.1"
PORT    = 5007
DEBUG   = True
PIDFILE = os.path.expanduser("~/.appserver_pid")
LOGFILE = os.path.expanduser("~/.appserver_log")
ERRFILE = os.path.expanduser("~/.appserver_err")