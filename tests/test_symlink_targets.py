import os
import shutil
from tempfile import mkdtemp
from unittest.mock import Mock

import nginx_config_reloader
from tests.testcase import TestCase


class TestSymlinkTargets(TestCase):
    def setUp(self):
        self.watch_dir = mkdtemp()
        self.target_a = mkdtemp()
        self.target_b = mkdtemp()

    def tearDown(self):
        for d in (self.watch_dir, self.target_a, self.target_b):
            shutil.rmtree(d, ignore_errors=True)

    def _handler(self):
        return nginx_config_reloader.NginxConfigReloader(dir_to_watch=self.watch_dir)

    def _symlink(self, name, target):
        path = os.path.join(self.watch_dir, name)
        os.symlink(target, path)
        return path

    def test_plain_directories_are_not_recorded(self):
        os.mkdir(os.path.join(self.watch_dir, "plain"))

        targets = self._handler().get_symlink_targets()

        self.assertEqual(targets, {})

    def test_symlinked_directory_is_recorded_with_target_identity(self):
        link = self._symlink("example.com", self.target_a)
        st = os.stat(self.target_a)

        targets = self._handler().get_symlink_targets()

        self.assertEqual(
            targets,
            {
                link: (
                    os.path.realpath(self.target_a),
                    st.st_dev,
                    st.st_ino,
                    st.st_ctime_ns,
                )
            },
        )

    def test_breaking_a_symlink_is_detected_as_a_change(self):
        target = os.path.join(self.target_a, "release")
        os.mkdir(target)
        self._symlink("example.com", target)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        shutil.rmtree(target)

        self.assertEqual(handler.get_symlink_targets(), {})
        self.assertTrue(handler.symlink_targets_changed())

    def test_nested_symlink_below_followed_symlink_is_recorded(self):
        self._symlink("example.com", self.target_a)
        os.symlink(self.target_b, os.path.join(self.target_a, "inner"))

        targets = self._handler().get_symlink_targets()

        self.assertIn(os.path.join(self.watch_dir, "example.com"), targets)
        self.assertIn(os.path.join(self.watch_dir, "example.com", "inner"), targets)

    def test_changed_is_false_when_targets_are_stable(self):
        self._symlink("example.com", self.target_a)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        self.assertFalse(handler.symlink_targets_changed())

    def test_changed_is_true_when_symlink_is_repointed(self):
        link = self._symlink("example.com", self.target_a)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        os.unlink(link)
        os.symlink(self.target_b, link)

        self.assertTrue(handler.symlink_targets_changed())

    def test_changed_is_true_when_target_inode_is_replaced(self):
        target = os.path.join(self.target_a, "release")
        os.mkdir(target)
        self._symlink("example.com", target)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        shutil.rmtree(target)
        os.mkdir(target)

        self.assertTrue(handler.symlink_targets_changed())

    def test_changed_is_true_when_target_metadata_changes(self):
        self._symlink("example.com", self.target_a)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        os.chmod(self.target_a, 0o700)

        self.assertTrue(handler.symlink_targets_changed())

    def test_changed_is_true_when_a_new_symlink_appears(self):
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()

        self._symlink("example.com", self.target_a)

        self.assertTrue(handler.symlink_targets_changed())

    def test_after_loop_restarts_and_reloads_when_symlink_is_repointed(self):
        link = self._symlink("example.com", self.target_a)
        handler = self._handler()
        handler.watched_symlink_targets = handler.get_symlink_targets()
        self.assertFalse(handler.symlink_targets_changed())

        os.unlink(link)
        os.symlink(self.target_b, link)
        self.assertFalse(handler.dirty)

        self.assertTrue(handler.symlink_targets_changed())

        handler.restart_observer = Mock()
        handler.reload = Mock()
        nginx_config_reloader.after_loop(handler)

        handler.restart_observer.assert_called_once_with()
        handler.reload.assert_called_once_with()
        self.assertFalse(handler.dirty)
