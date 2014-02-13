#!/usr/bin/env python
import argparse
import fnmatch
import pyinotify
import subprocess
import signal
import os
import logging
import shutil
import sys


DIR_TO_WATCH = '/data/web/nginx'
CUSTOM_CONFIG_DIR = '/etc/nginx/app'

NGINX = '/usr/sbin/nginx'
NGINX_PID_FILE = '/var/run/nginx.pid'
ERROR_FILE = 'nginx_error_output'

BACKUP_CONFIG_DIR = CUSTOM_CONFIG_DIR + '_bak'
IGNORE_FILES = (
    '.*',
    ERROR_FILE,
)


logging.basicConfig(level=logging.INFO)


class TrackModifications(pyinotify.ProcessEvent):

    def process_IN_DELETE(self, event):
        self.handle_event(event)

    def process_IN_CLOSE_WRITE(self, event):
        self.handle_event(event)

    def handle_event(self, event):
        if not any(fnmatch.fnmatch(event.name, pat) for pat in IGNORE_FILES):
            logging.info("%s detected on %s" % (event.maskname, event.name))
            self.apply_new_config()

    def apply_new_config(self):
        self.install_new_custom_config_dir()
        try:
            subprocess.check_output([NGINX, '-t'], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.restore_old_custom_config_dir()
            self.write_error_file(e.output)
            return False

        self.reload_nginx()
        return True

    def get_pid(self):
        with open(NGINX_PID_FILE, 'r') as f:
            return int(f.read())

    def write_error_file(self, error):
        with open(os.path.join(DIR_TO_WATCH, ERROR_FILE), 'w') as f:
            f.write(error)

    def install_new_custom_config_dir(self):
        shutil.rmtree(BACKUP_CONFIG_DIR, ignore_errors=True)
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
        shutil.move(BACKUP_CONFIG_DIR, CUSTOM_CONFIG_DIR)

    def reload_nginx(self):
        pid = self.get_pid()
        if not pid:
            logging.info("Not reloading, nginx not running")
        else:
            os.kill(pid, signal.SIGHUP)


def wait_loop(daemonize=True):
    wm = pyinotify.WatchManager()
    handler = TrackModifications()
    notifier = pyinotify.Notifier(wm, default_proc_fun=handler)
    wm.add_watch(DIR_TO_WATCH, pyinotify.ALL_EVENTS)

    try:
        outfile = os.path.basename(sys.argv[0]) + '.log'
        notifier.loop(daemonize=daemonize, stdout=outfile, stderr=outfile)
    except pyinotify.NotifierError as err:
        print err


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--daemon', '-d', action='store_true', help='Fork to background and run as daemon')
    parser.add_argument('--test', '-t', action='store_true', help='Test mode: monitor files on foreground with output')
    args = parser.parse_args()

    if args.test:
        logging.basicConfig(level=logging.DEBUG,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        wait_loop(False)
    if args.daemon:
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s')
        wait_loop(True)
    else:
        tm = TrackModifications()
        tm.apply_new_config()


if __name__ == '__main__':
    sys.exit(main())
