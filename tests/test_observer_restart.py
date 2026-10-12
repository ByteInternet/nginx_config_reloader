import os
import shutil
from tempfile import mkdtemp
from unittest.mock import Mock, patch

from watchdog.observers import Observer
from watchdog.observers.api import EventEmitter

import nginx_config_reloader
from tests.testcase import TestCase


class TestObserverRestart(TestCase):
    def setUp(self):
        self.watch_dir = mkdtemp()
        self.target_a = mkdtemp()
        self.target_b = mkdtemp()
        self.site = os.path.join(self.watch_dir, "site")
        os.symlink(self.target_a, self.site)
        self.handler = nginx_config_reloader.NginxConfigReloader(
            dir_to_watch=self.watch_dir
        )
        self.handler.reload = Mock()

    def tearDown(self):
        try:
            self.handler.stop_observer()
        except Exception:
            pass
        for d in (self.watch_dir, self.target_a, self.target_b):
            shutil.rmtree(d, ignore_errors=True)

    def _repoint(self, link, new_target):
        tmp = link + ".tmp"
        os.symlink(new_target, tmp)
        os.replace(tmp, link)

    def _fail_first_emitter_start(self):
        original_start = EventEmitter.start
        calls = []

        def start(emitter):
            calls.append(emitter)
            if len(calls) == 1:
                raise OSError(28, "inotify watch limit reached")
            return original_start(emitter)

        return patch.object(EventEmitter, "start", start)

    def test_stop_observer_does_not_raise_when_observer_was_never_started(self):
        self.handler.observer = Observer()

        self.handler.stop_observer()

    def test_restart_observer_recovers_after_failed_start(self):
        self.handler.start_observer()
        self._repoint(self.site, self.target_b)

        with self._fail_first_emitter_start():
            with self.assertRaises(OSError):
                self.handler.restart_observer()
            self.handler.restart_observer()

        self.assertTrue(self.handler.observer.is_alive())
        self.assertFalse(self.handler.symlink_targets_changed())

    def test_after_loop_recovers_from_failed_observer_restart_without_reload_loop(
        self,
    ):
        # Ignore real filesystem events (e.g. the symlink repoint itself), so
        # only reloads caused by the observer restart logic are counted
        self.handler.dispatch = Mock()
        self.handler.start_observer()
        self._repoint(self.site, self.target_b)

        with self._fail_first_emitter_start():
            for _ in range(4):
                nginx_config_reloader.after_loop(self.handler)

        self.assertTrue(self.handler.observer.is_alive())
        self.assertFalse(self.handler.symlink_targets_changed())
        self.handler.reload.assert_called_once_with()
