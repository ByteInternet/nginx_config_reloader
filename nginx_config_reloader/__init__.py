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
MAIN_CONFIG_DIR = '/etc/nginx'
CUSTOM_CONFIG_DIR = MAIN_CONFIG_DIR + '/app'
BACKUP_CONFIG_DIR = MAIN_CONFIG_DIR + '/app_bak'

MAGENTO_CONF = MAIN_CONFIG_DIR + '/magento.conf'
MAGENTO1_CONF = MAIN_CONFIG_DIR + '/magento1.conf'
MAGENTO2_CONF = MAIN_CONFIG_DIR + '/magento2.conf'
MAGENTO2_FLAG = DIR_TO_WATCH + '/magento2.flag'

NGINX = '/usr/sbin/nginx'
NGINX_PID_FILE = '/var/run/nginx.pid'
ERROR_FILE = 'nginx_error_output'

WATCH_IGNORE_FILES = (
    # glob patterns
    '.*',
    '*~',
    ERROR_FILE
)
SYNC_IGNORE_FILES = WATCH_IGNORE_FILES + ('*.flag',)
SYSLOG_SOCKET = '/dev/log'

# Using include or load_module is forbidden unless
# - it is in a comment
# - the include is a relative path but does not contain  ..
# - the include is absolute but in the MAIN_CONFIG_DIR
# - but not in the BACKUP_CONFIG_DIR
# - also takes into account double slashes
# Because of bash escaping problems we define quote's in octal format \042 == ' and \047 == "
ILLEGAL_INCLUDE_REGEX = "^(?!\s*#)\s*(include|load_module)\s*" \
                        "(\\042|\\047)?" \
                        "(?=.*\.\.|/+etc/+nginx/+app_bak|/+(?!etc/+nginx))" \
                        "(\\042|\\047)?"


logger = logging.getLogger(__name__)


class NginxConfigReloader(pyinotify.ProcessEvent):

    def my_init(self, logger=None, allow_includes=False):
        """Constructor called by ProcessEvent"""
        if not logger:
            self.logger = logging
        else:
            self.logger = logger
        self.allow_includes = allow_includes

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
        if not any(fnmatch.fnmatch(event.name, pat) for pat in WATCH_IGNORE_FILES):
            self.logger.info("%s detected on %s" % (event.maskname, event.name))
            self.apply_new_config()

    def install_magento_config(self):
        # Check if configs are present
        os.stat(MAGENTO1_CONF)
        os.stat(MAGENTO2_CONF)

        # Create new temporary filename for new config
        MAGENTO_CONF_NEW = MAGENTO_CONF + '_new'

        # Remove tmp link it it exists (leftover?)
        try:
            os.unlink(MAGENTO_CONF_NEW)
        except OSError:
            pass

        # Symlink new config to temporary filename
        if os.path.isfile(MAGENTO2_FLAG):
            os.symlink(MAGENTO2_CONF, MAGENTO_CONF_NEW)
        else:
            os.symlink(MAGENTO1_CONF, MAGENTO_CONF_NEW)

        # Move temporary symlink to actual location, overwriting existing link or file
        os.rename(MAGENTO_CONF_NEW, MAGENTO_CONF)

    @staticmethod
    def assert_no_includes_in_config():
        """
        Verify that there are no includes to files outside of the /etc/nginx/ directory in the user config
        Relative includes are OK
        :return None|CalledProcessError:
        """
        if os.path.isdir(DIR_TO_WATCH):
            # Using include or load_module is forbidden unless
            # - it is in a comment
            # - the include is a relative path but does not start with ..
            # - the include is absolute but to the MAIN_CONFIG_DIR
            check_external_resources = \
                "[ $(grep -r -P '{}' '{}' | wc -l) -lt 1 ]".format(
                    ILLEGAL_INCLUDE_REGEX, DIR_TO_WATCH
                )
            subprocess.check_output(check_external_resources, shell=True)

    def apply_new_config(self):
        if not self.allow_includes:
            try:
                self.assert_no_includes_in_config()
            except subprocess.CalledProcessError:
                self.logger.error("Config is not allowed to load external resources")
                self.write_error_file(
                    "You are not allowed to use include or load_module in the nginx config unless the path is relative "
                    "or in the main nginx config directory. "
                    "See the NGINX dos and don'ts in this article: "
                    "https://support.hypernode.com/knowledgebase/how-to-use-nginx/\n"
                )
                return False
        try:
            self.install_magento_config()
        except OSError:
            self.logger.error("Installation of magento config failed")
            return False

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
        else:
            try:
                os.unlink(os.path.join(DIR_TO_WATCH, ERROR_FILE))
            except OSError:
                pass

        self.reload_nginx()
        return True

    def install_new_custom_config_dir(self):
        shutil.rmtree(BACKUP_CONFIG_DIR, ignore_errors=True)
        if os.path.exists(CUSTOM_CONFIG_DIR):
            shutil.move(CUSTOM_CONFIG_DIR, BACKUP_CONFIG_DIR)
        completed = False
        while not completed:
            try:
                shutil.copytree(DIR_TO_WATCH, CUSTOM_CONFIG_DIR, ignore=shutil.ignore_patterns(*SYNC_IGNORE_FILES))
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


def wait_loop(logger=None, allow_includes=False):
    """Main event loop

    There is an outer loop that checks the availability of the directory to watch.
    As soon as it becomes available, it starts an inotify-monitor that monitors
    configuration changes in an inner event loop. When the monitored directory is
    renamed or removed, the inotify-handler raises an exception to break out of the
    inner loop and we're back here in the outer loop.
    """
    wm = pyinotify.WatchManager()
    handler = NginxConfigReloader(logger=logger, allow_includes=allow_includes)
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
            logger.warning("Configuration dir lost, waiting for it to reappear")


def parse_nginx_config_reloader_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', '-d', action='store_true', help='Fork to background and run as daemon')
    parser.add_argument('--monitor', '-m', action='store_true', help='Monitor files on foreground with output')
    parser.add_argument(
        '--allow-includes', action='store_true',
        help='Allow the config to contain includes outside of'
             ' the system nginx config directory (default False)'
    )
    return parser.parse_args()


def main():

    args = parse_nginx_config_reloader_arguments()

    if args.monitor:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter('%(asctime)s %(name)-12s %(levelname)-8s %(message)s'))
        logger.setLevel(logging.DEBUG)
        logger.addHandler(handler)

        wait_loop(logger=logger, allow_includes=args.allow_includes)

    if args.daemon:
        handler = logging.handlers.SysLogHandler(address=SYSLOG_SOCKET)
        handler.setFormatter(logging.Formatter('%(name)-12s %(levelname)-8s %(message)s'))
        logger.setLevel(logging.INFO)
        logger.addHandler(handler)

        pidfile = daemon.pidlockfile.PIDLockFile('/var/run/%s.pid' % os.path.basename(sys.argv[0]))
        with daemon.DaemonContext(pidfile=pidfile, files_preserve=[handler.socket.fileno()]):
            wait_loop(logger=logger, allow_includes=args.allow_includes)

    else:
        tm = NginxConfigReloader(allow_includes=args.allow_includes)
        tm.apply_new_config()


if __name__ == '__main__':
    sys.exit(main())
