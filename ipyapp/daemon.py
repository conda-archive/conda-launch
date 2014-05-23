"""
***
Modified generic daemon class
***

Author:         http://www.jejik.com/articles/2007/02/
                        a_simple_unix_linux_daemon_in_python/www.boxedice.com
                https://github.com/serverdensity/python-daemon

License:        http://creativecommons.org/licenses/by-sa/3.0/

Changes:        Various fixes where added in signal handling, pid file handling,
                return codes and exception handling

"""

# Core modules
import atexit
import os
import sys
import time
import signal
import logging
import traceback


class Daemon(object):
    """
    A generic daemon class.

    Usage: subclass the Daemon class and override the run() method
    """
    def __init__(self, pidfile, stdin=os.devnull,
                 stdout=os.devnull, stderr=os.devnull,
                 home_dir='.', umask=0o022, loglevel=logging.INFO):
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.pidfile = pidfile
        self.home_dir = home_dir
        self.loglevel = loglevel
        self.umask = umask

    def daemonize(self):
        """
        Do the UNIX double-fork magic, see Stevens' "Advanced
        Programming in the UNIX Environment" for details (ISBN 0201563177)
        http://www.erlenstar.demon.co.uk/unix/faq_2.html#SEC16
        """
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(
                "fork #1 failed: %d (%s)\n" % (e.errno, e.strerror))
            os._exit(1)

        # Decouple from parent environment
        os.chdir(self.home_dir)
        os.setsid()
        os.umask(self.umask)

        # Do second fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit from second parent
                sys.exit(0)
        except OSError as e:
            sys.stderr.write(
                "fork #2 failed: %d (%s)\n" % (e.errno, e.strerror))
            os._exit(1)

        #if sys.platform != 'darwin':  # This block breaks on OS X
        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()
        si = open(self.stdin, 'r')
        so = open(self.stdout, 'a+')
        if self.stderr:
            se = open(self.stderr, 'ab+', 0)
        else:
            se = so
        os.dup2(si.fileno(), sys.stdin.fileno())
        os.dup2(so.fileno(), sys.stdout.fileno())
        os.dup2(se.fileno(), sys.stderr.fileno())

        signal.signal(signal.SIGTERM, self._shutdown)
        signal.signal(signal.SIGINT, self._shutdown)
        # end of OS X block

        logging.info("Daemon started")

        # Write pidfile
        atexit.register(
            self.delpid)  # Make sure pid file is removed if we quit
        pid = str(os.getpid())
        open(self.pidfile, 'w+').write("%s\n" % pid)

    def delpid(self):
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)

    def start(self, return_on_exit=False, overwrite_pid=False, *args, **kwargs):
        """
        Start the daemon
        """

        logging.info('Start daemon')

        # Check for a pidfile to see if the daemon already runs
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None

        if pid:
            if overwrite_pid:
                self.delpid()
            else:
                message = "pidfile %s already exist. Daemon already running?\n"
                sys.stderr.write(message % self.pidfile)
                if return_on_exit:
                    return False
                sys.exit(1)

        # Start the daemon
        _exitcode = 0

        self.daemonize()

        try:
            logging.info('Running process')
            self.run(*args, **kwargs)
            logging.info('Process finished normally.')
        except Exception as e:
            logging.error('Daemonized process threw an exception [%s].' % e)
            tb = traceback.format_exc()
            logging.error(tb)
            _exitcode = 255
        finally:
            # Make sure the pid file gets deleted even in case of errors
            self.delpid()
            if return_on_exit:
                return _exitcode if _exitcode else False
            sys.exit(_exitcode)

    def _shutdown(self, signum=None, frame=None):
        self.shutdown(frame)

    def shutdown(self, frame=None):
        os.kill(self.pid, signal.SIGTERM)

    def stop(self):
        """
        Stop the daemon
        """


        logging.info("Stopping daemon...")

        # Get the pid from the pidfile
        pid = self.pid
        logging.debug("trying to stop app server with PID %s" % pid)

        if not pid:
            message = "pidfile %s does not exist. Daemon not running?\n"
            sys.stderr.write(message % self.pidfile)

            # Just to be sure. A ValueError might occur if the PID file is
            # empty but does actually exist
            if os.path.exists(self.pidfile):
                os.remove(self.pidfile)

            return  # Not an error in a restart

        # Try killing the daemon process
        try:
            os.kill(pid, signal.SIGTERM)
            os.getpgid(pid)              # this will raise an exception if the process isn't running
            time.sleep(1)                # process gets 1 second to clean itself up
            os.kill(pid, signal.SIGKILL) # and now try to kill it if its still around
            self.delpid()                # if we get this far without an exception, then remove the PID file
        except OSError as err:
            err = str(err)
            if err.find("No such process") > 0:
                logging.debug('process purged, deleting pid file')
                self.delpid()
            else:
                logging.debug('failed to stop process: ' + err)
                print(str(err))
                sys.exit(1)

        logging.info("Stopped daemon")

    def restart(self):
        """
        Restart the daemon
        """
        self.stop()
        self.start()

    @property
    def pid(self):
        try:
            pf = open(self.pidfile, 'r')
            pid = int(pf.read().strip())
            pf.close()
        except IOError:
            pid = None
        except SystemExit:
            pid = None
        return pid

    def is_running(self):
        return self.running

    @property
    def running(self):
        import psutil
        pid = self.pid
        return pid and pid in psutil.pids()

    def run(self):
        """
        You should override this method when you subclass Daemon.
        It will be called after the process has been
        daemonized by start() or restart().
        """
        raise NotImplemented('You should override this method when you subclass Daemon')
