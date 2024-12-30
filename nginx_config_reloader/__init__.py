#!/usr/bin/env python
from __future__ import absolute_import

import argparse
import fnmatch
import logging
import logging.handlers
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from typing import Optional

import pyinotify
from dasbus.loop import EventLoop
from dasbus.signal import Signal

from nginx_config_reloader.copy_files import safe_copy_files
from nginx_config_reloader.dbus.common import NGINX_CONFIG_RELOADER, SYSTEM_BUS
from nginx_config_reloader.dbus.server import NginxConfigReloaderInterface
from nginx_config_reloader.settings import (
    BACKUP_CONFIG_DIR,
    CUSTOM_CONFIG_DIR,
    MAIN_CONFIG_DIR,
    DIR_TO_WATCH,
    ERROR_FILE,
    FORBIDDEN_CONFIG_REGEX,
    MAGENTO1_CONF,
    MAGENTO2_CONF,
    MAGENTO_CONF,
    NGINX,
    NGINX_PID_FILE,
    UNPRIVILEGED_GID,
    UNPRIVILEGED_UID,
    WATCH_IGNORE_FILES,
)
from nginx_config_reloader.utils import directory_is_unmounted

logger = logging.getLogger(__name__)
dbus_loop: Optional[EventLoop] = None


class NginxConfigReloader(pyinotify.ProcessEvent):
    def my_init(
        self,
        logger=None,
        no_magento_config=False,
        no_custom_config=False,
        dir_to_watch=DIR_TO_WATCH,
        magento2_flag=None,
        notifier=None,
        use_systemd=False,
    ):
        """Constructor called by ProcessEvent

        :param logging.Logger logger: The logger object
        :param bool no_magento_config: True if we should not install Magento configuration
        :param bool no_custom_config: True if we should not copy custom configuration
        :param str dir_to_watch: The directory to watch
        :param str magento2_flag: Magento 2 flag location
        """
        if not logger:
            self.logger = logging
        else:
            self.logger = logger
        self.no_magento_config = no_magento_config
        self.no_custom_config = no_custom_config
        self.dir_to_watch = dir_to_watch
        if not magento2_flag:
            self.magento2_flag = dir_to_watch + "/magento2.flag"
        else:
            self.magento2_flag = magento2_flag
        self.logger.info(self.dir_to_watch)
        self.notifier = notifier
        self.use_systemd = use_systemd
        self.dirty = False
        self.applying = False
        self._on_config_reload = Signal()

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

    def process_IN_CREATE(self, event):
        """Triggered by inotify when a dir is created in the watch dir"""
        if event.dir:
            self.handle_event(event)

    def process_IN_CLOSE_WRITE(self, event):
        """Triggered by inotify when a file is written in the dir"""
        self.handle_event(event)

    def process_IN_MOVE_SELF(self, event):
        """Triggered by inotify when watched dir is moved"""
        raise ListenTargetTerminated

    def handle_event(self, event):
        if not any(fnmatch.fnmatch(event.name, pat) for pat in WATCH_IGNORE_FILES):
            self.logger.info("{} detected on {}.".format(event.maskname, event.name))
            self.dirty = True

    def install_magento_config(self):
        # Check if configs are present
        os.stat(MAGENTO1_CONF)
        os.stat(MAGENTO2_CONF)

        # Create new temporary filename for new config
        MAGENTO_CONF_NEW = MAGENTO_CONF + "_new"

        # Remove tmp link if it exists (leftover?)
        try:
            os.unlink(MAGENTO_CONF_NEW)
        except OSError:
            pass

        # Symlink new config to temporary filename
        if os.path.isfile(self.magento2_flag):
            os.symlink(MAGENTO2_CONF, MAGENTO_CONF_NEW)
        else:
            os.symlink(MAGENTO1_CONF, MAGENTO_CONF_NEW)

        # Move temporary symlink to actual location, overwriting existing link or file
        os.rename(MAGENTO_CONF_NEW, MAGENTO_CONF)

    def check_can_write_to_main_config_dir(self):
        return os.access(MAIN_CONFIG_DIR, os.W_OK)

    def check_no_forbidden_config_directives_are_present(self):
        """
        Loop over the :FORBIDDEN_CONFIG_REGEX: to check if nginx config directory contains forbidden configuration
         options
        :return bool:
                        True    if forbidden config directives are present
                        False   if check couldn't find any forbidden config flags
        """
        if os.path.isdir(self.dir_to_watch):
            for rules in FORBIDDEN_CONFIG_REGEX:
                try:
                    # error file may contain messages that match a forbidden config pattern
                    # then validation could fail while the actual config is correct.
                    # we'll exclude the error file from searching for patterns,
                    # NOTE: exclusion of error_file requires to ensure the
                    # file is removed before moving it to nginx conf dir
                    # @TODO: use Python to search for forbidden configs instead
                    # of spawning external procs. Will have better testing
                    # and even may consume less system resources
                    check_external_resources = (
                        "[ $(grep -r --exclude={} -P '{}' '{}' | wc -l) -lt 1 ]".format(
                            ERROR_FILE, rules[0], self.dir_to_watch
                        )
                    )
                    subprocess.check_output(check_external_resources, shell=True)
                except subprocess.CalledProcessError:
                    error = "Unable to load config: {}".format(rules[1])
                    self.logger.error(error)
                    self.write_error_file(error)
                    return True
            return False

    def remove_error_file(self):
        """Try removing the error file. Return True on success or False on errors
        :rtype: bool
        """
        removed = False
        try:
            os.unlink(os.path.join(self.dir_to_watch, ERROR_FILE))
            removed = True
        except OSError:
            pass
        return removed

    def apply_new_config(self):
        # Wrapper function to prevent multiple config applications
        if self.applying:
            logger.debug(f"A config is already being applied. Skipping this one.")
            return False

        self.applying = True
        try:
            res = self._apply()
        except Exception as e:
            logger.exception(e)
            res = False
        self.applying = False
        return res

    def _apply(self):
        logger.debug("Applying new config")
        if self.check_no_forbidden_config_directives_are_present():
            return False
        
        if not self.check_can_write_to_main_config_dir():
            self.logger.error("No write permissions to main nginx config directory, please check your permissions.")
            return False

        if not self.no_magento_config:
            try:
                self.install_magento_config()
            except OSError:
                self.logger.error("Installation of magento config failed")
                return False

        if not self.no_custom_config:
            try:
                self.fix_custom_config_dir_permissions()
                self.install_new_custom_config_dir()
            except (OSError, subprocess.CalledProcessError) as e:
                error_output = str(e)
                if hasattr(e, "output"):
                    extra_output = e.output
                    if isinstance(e.output, bytes):
                        extra_output = extra_output.decode()
                    error_output += "\n\n{}".format(extra_output)
                self.logger.error("Installation of custom config failed")
                self.restore_old_custom_config_dir()
                self.write_error_file(error_output)
                return False

        try:
            subprocess.check_output([NGINX, "-t"], stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            self.logger.info("Config check failed")
            if not self.no_custom_config:
                self.restore_old_custom_config_dir()

            if isinstance(e.output, bytes):
                self.write_error_file(e.output.decode())
            else:
                self.write_error_file(e.output)

            return False
        else:
            self.remove_error_file()

        self.reload_nginx()

        return True

    def fix_custom_config_dir_permissions(self):
        try:
            subprocess.check_output(
                ["chmod", "755", self.dir_to_watch],
                preexec_fn=as_unprivileged_user,
            )
            for root, dirs, _ in os.walk(self.dir_to_watch):
                for name in dirs:
                    path = os.path.join(root, name)
                    if os.path.islink(path):
                        continue
                    subprocess.check_output(
                        ["chmod", "755", path],
                        preexec_fn=as_unprivileged_user,
                    )
        except subprocess.CalledProcessError:
            self.logger.info("Failed fixing permissions on watched directory")

    def install_new_custom_config_dir(self):
        self.remove_error_file()
        shutil.rmtree(BACKUP_CONFIG_DIR, ignore_errors=True)
        if os.path.exists(CUSTOM_CONFIG_DIR):
            shutil.move(CUSTOM_CONFIG_DIR, BACKUP_CONFIG_DIR)
        os.mkdir(CUSTOM_CONFIG_DIR)
        safe_copy_files(self.dir_to_watch, CUSTOM_CONFIG_DIR)

    def restore_old_custom_config_dir(self):
        shutil.rmtree(CUSTOM_CONFIG_DIR)
        if os.path.exists(BACKUP_CONFIG_DIR):
            shutil.move(BACKUP_CONFIG_DIR, CUSTOM_CONFIG_DIR)

    def reload_nginx(self):
        if self.use_systemd:
            subprocess.check_call(["systemctl", "reload", "nginx"])
        else:
            pid = self.get_nginx_pid()
            if not pid:
                self.logger.warning("Not reloading, nginx not running")
            else:
                self.logger.info("Reloading nginx config")
                os.kill(pid, signal.SIGHUP)

    def get_nginx_pid(self):
        try:
            with open(NGINX_PID_FILE, "r") as f:
                return int(f.read())
        except (IOError, ValueError):
            return None

    def write_error_file(self, error):
        with open(os.path.join(self.dir_to_watch, ERROR_FILE), "w") as f:
            f.write(error)

    @property
    def reloaded(self):
        """Signal for the reload event."""
        return self._on_config_reload

    def reload(self, send_signal=True):
        if directory_is_unmounted(self.dir_to_watch):
            self.logger.warning(
                f"Directory {self.dir_to_watch} is unmounted, not reloading!"
            )
            return

        self.apply_new_config()
        if send_signal:
            self._on_config_reload.emit()


class ListenTargetTerminated(BaseException):
    pass


def after_loop(nginx_config_reloader: NginxConfigReloader) -> None:
    if nginx_config_reloader.dirty:
        try:
            nginx_config_reloader.reload()
        except:
            pass
        nginx_config_reloader.dirty = False
        nginx_config_reloader.applying = False


def dbus_event_loop():
    dbus_loop = EventLoop()
    dbus_loop.run()


def wait_loop(
    logger=None,
    no_magento_config=False,
    no_custom_config=False,
    dir_to_watch=DIR_TO_WATCH,
    recursive_watch=False,
    use_systemd=False,
    no_dbus=False,
):
    """Main event loop

    There is an outer loop that checks the availability of the directory to watch.
    As soon as it becomes available, it starts an inotify-monitor that monitors
    configuration changes in an inner event loop. When the monitored directory is
    renamed or removed, the inotify-handler raises an exception to break out of the
    inner loop and we're back here in the outer loop.

    :param logging.Logger logger: The logger object
    :param bool no_magento_config: True if we should not install Magento configuration
    :param bool no_custom_config: True if we should not copy custom configuration
    :param str dir_to_watch: The directory to watch
    :param bool recursive_watch: True if we should watch the dir recursively
    :param use_systemd: True if we should reload nginx using systemd instead of process signal
    :param bool no_dbus: True if we should not use DBus
    :return None:
    """
    dir_to_watch = os.path.abspath(dir_to_watch)

    wm = pyinotify.WatchManager()
    notifier = pyinotify.Notifier(wm)

    class SymlinkChangedHandler(pyinotify.ProcessEvent):
        def process_IN_DELETE(self, event):
            if event.pathname == dir_to_watch:
                raise ListenTargetTerminated("watched directory was deleted")

    nginx_config_changed_handler = NginxConfigReloader(
        logger=logger,
        no_magento_config=no_magento_config,
        no_custom_config=no_custom_config,
        dir_to_watch=dir_to_watch,
        notifier=notifier,
        use_systemd=use_systemd,
    )

    if not no_dbus:
        SYSTEM_BUS.publish_object(
            NGINX_CONFIG_RELOADER.object_path,
            NginxConfigReloaderInterface(nginx_config_changed_handler),
        )
        SYSTEM_BUS.register_service(NGINX_CONFIG_RELOADER.service_name)
        dbus_thread = threading.Thread(target=dbus_event_loop)
        dbus_thread.start()

    while True:
        while not os.path.exists(dir_to_watch):
            logger.warning(
                "Configuration dir {} not found, waiting...".format(dir_to_watch)
            )
            time.sleep(5)

        wm.add_watch(
            dir_to_watch,
            pyinotify.ALL_EVENTS,
            nginx_config_changed_handler,
            rec=recursive_watch,
            auto_add=True,
        )
        wm.watch_transient_file(
            dir_to_watch, pyinotify.ALL_EVENTS, SymlinkChangedHandler
        )

        # Install initial configuration
        nginx_config_changed_handler.reload(send_signal=False)

        try:
            logger.info("Listening for changes to {}".format(dir_to_watch))
            notifier.coalesce_events()
            notifier.loop(callback=lambda _: after_loop(nginx_config_changed_handler))
        except pyinotify.NotifierError as err:
            logger.critical(err)
        except ListenTargetTerminated:
            logger.warning("Configuration dir lost, waiting for it to reappear")


def as_unprivileged_user():
    os.setgid(UNPRIVILEGED_GID)
    os.setuid(UNPRIVILEGED_UID)


def parse_nginx_config_reloader_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--monitor",
        "-m",
        action="store_true",
        help="Monitor files on foreground with output",
    )
    parser.add_argument(
        "--nomagentoconfig",
        action="store_true",
        help="Disable Magento configuration",
        default=False,
    )
    parser.add_argument(
        "--nocustomconfig",
        action="store_true",
        help="Disable copying custom configuration",
        default=False,
    )
    parser.add_argument(
        "--watchdir", "-w", help="Set directory to watch", default=DIR_TO_WATCH
    )
    parser.add_argument(
        "--recursivewatch",
        action="store_true",
        help="Enable recursive watching of subdirectories",
        default=False,
    )
    parser.add_argument(
        "--use-systemd",
        action="store_true",
        help="Reload nginx using systemd instead of process signal",
        default=False,
    )
    parser.add_argument(
        "--no-dbus",
        action="store_true",
        help="Disable DBus interface",
        default=False,
    )
    return parser.parse_args()


def get_logger():
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(name)-12s %(levelname)-8s %(message)s")
    )
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    return logger


def main():
    args = parse_nginx_config_reloader_arguments()
    log = get_logger()

    if args.monitor:
        # Track changed files in the nginx config dir and reload on change
        wait_loop(
            logger=log,
            no_magento_config=args.nomagentoconfig,
            no_custom_config=args.nocustomconfig,
            dir_to_watch=args.watchdir,
            recursive_watch=args.recursivewatch,
            use_systemd=args.use_systemd,
            no_dbus=args.no_dbus,
        )
        # should never return
        return 1
    else:
        # Reload the config once
        NginxConfigReloader(
            logger=log,
            no_magento_config=args.nomagentoconfig,
            no_custom_config=args.nocustomconfig,
            dir_to_watch=args.watchdir,
            use_systemd=args.use_systemd,
        ).apply_new_config()
        return 0


if __name__ == "__main__":
    sys.exit(main())
