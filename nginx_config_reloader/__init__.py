#!/usr/bin/env python
import argparse
import fnmatch
import daemon
import daemon.pidlockfile
import pyinotify
import subprocess
import signal
import os
import logging
import logging.handlers
import shutil
import sys
import time


DIR_TO_WATCH = '/data/web/nginx'
CUSTOM_CONFIG_DIR = '/etc/nginx/app'

NGINX = '/usr/sbin/nginx'
NGINX_PID_FILE = '/var/run/nginx.pid'
ERROR_FILE = 'nginx_error_output'

BACKUP_CONFIG_DIR = CUSTOM_CONFIG_DIR + '_bak'
IGNORE_FILES = (
    # glob patterns
    '.*',
    '*~',
    ERROR_FILE,
)
SYSLOG_SOCKET = '/dev/log'

logger = logging.getLogger(__name__)


class NginxConfigReloader(pyinotify.ProcessEvent):

    def my_init(self, logger=None):
        """Constructor called by ProcessEvent"""
        if not logger:
            self.logger = logging
        else:
            self.logger = logger

    def process_IN_DELETE(self, event):
        """Triggered by inotify on removal of file or removal of dir

        If the dir itself is removed, inotify will stop watching and also
        trigger IN_IGNORED.
        """
        if not event.dir:  # Will also capture IN_DELETE_SELF
            self.handle_event(event)

    def process_IN_MOVED(self, event):
        """Triggered by inotify when a file is moved from or to the dir"""
        self.handle_event(event)

    def process_IN_CLOSE_WRITE(self, event):
        """Triggered by inotify when a file is written in the dir"""
        self.handle_event(event)

    def process_IN_IGNORED(self, event):
        """Triggered by inotify when it stops watching"""
        raise ListenTargetTerminated

    def process_IN_MOVE_SELF(self, event):
        """Triggered by inotify when watched dir is moved"""
        raise ListenTargetTerminated

    def handle_event(self, event):
        if not any(fnmatch.fnmatch(event.name, pat) for pat in IGNORE_FILES):
            self.logger.info("%s detected on %s" % (event.maskname, event.name))
            self.apply_new_config()

    def apply_new_config(self):
        try:
            self.install_new_custom_config_dir()
        except OSError:
            self.logger.error("Installation of custom config failed")
            return False

        try:
            subprocess.check_output([NGINX, '-t'], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.logger.info("Config check failed")
            self.restore_old_custom_config_dir()
            self.write_error_file(e.output)
            return False

        self.reload_nginx()
        return True

    def install_new_custom_config_dir(self):
        shutil.rmtree(BACKUP_CONFIG_DIR, ignore_errors=True)
        if os.path.exists(CUSTOM_CONFIG_DIR):
            shutil.move(CUSTOM_CONFIG_DIR, BACKUP_CONFIG_DIR)
        completed = False
        while not completed:
            try:
                shutil.copytree(DIR_TO_WATCH, CUSTOM_CONFIG_DIR, ignore=shutil.ignore_patterns(*IGNORE_FILES))
                completed = True
            except shutil.Error:
                pass  # retry

    def restore_old_custom_config_dir(self):
        shutil.rmtree(CUSTOM_CONFIG_DIR)
        if os.path.exists(BACKUP_CONFIG_DIR):
            shutil.move(BACKUP_CONFIG_DIR, CUSTOM_CONFIG_DIR)

    def reload_nginx(self):
        pid = self.get_nginx_pid()
        if not pid:
            self.logger.warning("Not reloading, nginx not running")
        else:
            self.logger.info("Reloading nginx config")
            os.kill(pid, signal.SIGHUP)

    def get_nginx_pid(self):
        try:
            with open(NGINX_PID_FILE, 'r') as f:
                return int(f.read())
        except (IOError, ValueError):
            return None

    def write_error_file(self, error):
        with open(os.path.join(DIR_TO_WATCH, ERROR_FILE), 'w') as f:
            f.write(error)


class ListenTargetTerminated(BaseException):
    pass


def wait_loop(logger=None):
    """Main event loop

    There is an outer loop that checks the availability of the directory to watch.
    As soon as it becomes available, it starts an inotify-monitor that monitors
    configuration changes in an inner event loop. When the monitored directory is
    renamed or removed, the inotify-handler raises an exception to break out of the
    inner loop and we're back here in the outer loop.
    """
    wm = pyinotify.WatchManager()
    handler = NginxConfigReloader(logger=logger)
    notifier = pyinotify.Notifier(wm, default_proc_fun=handler)

    while True:
        while not os.path.exists(DIR_TO_WATCH):
            logger.warning("Configuration dir %s not found, waiting..." % DIR_TO_WATCH)
            time.sleep(5)

        wm.add_watch(DIR_TO_WATCH, pyinotify.ALL_EVENTS)

        # Install initial configuration
        handler.apply_new_config()

        try:
            logger.info("Listening for changes to %s" % DIR_TO_WATCH)
            notifier.loop()
        except pyinotify.NotifierError as err:
            logger.critical(err)
        except ListenTargetTerminated:
            logger.warning("Configuration dir list, waiting for it to reappear")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', '-d', action='store_true', help='Fork to background and run as daemon')
    parser.add_argument('--test', '-t', action='store_true', help='Test mode: monitor files on foreground with output')
    args = parser.parse_args()

    if args.test:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        wait_loop(logger=logger)

    if args.daemon:
        handler = logging.handlers.SysLogHandler(address=SYSLOG_SOCKET)
        handler.setFormatter(logging.Formatter('%(name)-12s %(levelname)-8s %(message)s'))
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        pidfile = pidfile=daemon.pidlockfile.PIDLockFile('/var/run/%s.pid' % os.path.basename(sys.argv[0]))
        with daemon.DaemonContext(pidfile=pidfile, files_preserve=[handler.socket.fileno()]):
            wait_loop(logger=logger)

    else:
        tm = NginxConfigReloader()
        tm.apply_new_config()


if __name__ == '__main__':
    sys.exit(main())
