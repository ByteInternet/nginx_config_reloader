import os
import shutil
import time
from tempfile import mkdtemp
from unittest.mock import Mock

import nginx_config_reloader
from tests.helpers import requires_linux
from tests.testcase import TestCase


class TestSymlinkRearmIntegration(TestCase):
    def setUp(self):
        self.handler = None
        self.watch_dir = mkdtemp()
        self.target_a = mkdtemp()
        self.target_b = mkdtemp()

    def tearDown(self):
        if self.handler is not None:
            try:
                self.handler.stop_observer()
            except Exception:
                pass
        for d in (self.watch_dir, self.target_a, self.target_b):
            shutil.rmtree(d, ignore_errors=True)

    def _write(self, path, contents):
        with open(path, "w") as f:
            f.write(contents)
            f.flush()
            os.fsync(f.fileno())

    def _repoint(self, link, new_target):
        tmp = link + ".tmp"
        os.symlink(new_target, tmp)
        os.replace(tmp, link)

    def _wait_for_dirty(self, handler, timeout=5.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if handler.dirty:
                return True
            time.sleep(0.02)
        return handler.dirty

    def _clear_pending_events(self, handler, quiet=0.3, timeout=3.0):
        deadline = time.monotonic() + timeout
        handler.dirty = False
        quiet_until = time.monotonic() + quiet
        while time.monotonic() < deadline:
            if handler.dirty:
                handler.dirty = False
                quiet_until = time.monotonic() + quiet
            elif time.monotonic() >= quiet_until:
                return
            time.sleep(0.02)

    @requires_linux
    def test_repointed_symlink_goes_stale_until_after_loop_restarts_observer(self):
        site = os.path.join(self.watch_dir, "site")
        os.symlink(self.target_a, site)

        handler = self.handler = nginx_config_reloader.NginxConfigReloader(
            dir_to_watch=self.watch_dir
        )
        handler.reload = Mock()
        handler.start_observer()

        self._write(os.path.join(site, "a.conf"), "one")
        self.assertTrue(
            self._wait_for_dirty(handler),
            "precondition failed: change under the original target was not detected",
        )

        self._repoint(site, self.target_b)
        self._clear_pending_events(handler)

        self._write(os.path.join(site, "b.conf"), "two")
        self.assertFalse(
            self._wait_for_dirty(handler, timeout=1.5),
            "expected the stale watch to miss changes under the repointed target",
        )

        self.assertTrue(handler.symlink_targets_changed())
        nginx_config_reloader.after_loop(handler)
        self._clear_pending_events(handler)

        self._write(os.path.join(site, "c.conf"), "three")
        self.assertTrue(
            self._wait_for_dirty(handler),
            "change under the repointed target was still missed after observer restart",
        )
