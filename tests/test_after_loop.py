from tempfile import mkdtemp
from unittest.mock import Mock

import nginx_config_reloader
from tests.testcase import TestCase


class TestAfterLoop(TestCase):
    def setUp(self) -> None:
        self.source = mkdtemp()
        self.set_up_patch(
            "nginx_config_reloader.directory_is_unmounted", return_value=False
        )

    def test_it_returns_nothing(self):
        tm = self._get_nginx_config_reloader_instance()

        result = nginx_config_reloader.after_loop(tm)

        self.assertIsNone(result)

    def test_it_applies_config_if_tree_dirty(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config = Mock()
        tm.dirty = True

        nginx_config_reloader.after_loop(tm)

        tm.apply_new_config.assert_called_once_with()
        self.assertFalse(tm.dirty)

    def test_it_does_not_apply_config_if_tree_not_dirty(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config = Mock()
        tm.dirty = False

        nginx_config_reloader.after_loop(tm)

        tm.apply_new_config.assert_not_called()
        self.assertFalse(tm.dirty)

    def test_it_restarts_observer_and_reloads_when_symlink_targets_change(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.symlink_targets_changed = Mock(return_value=True)
        tm.restart_observer = Mock()
        tm.reload = Mock()

        nginx_config_reloader.after_loop(tm)

        tm.restart_observer.assert_called_once_with()
        tm.reload.assert_called_once_with()
        self.assertFalse(tm.dirty)

    def test_it_does_not_restart_observer_when_symlink_targets_are_stable(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.symlink_targets_changed = Mock(return_value=False)
        tm.restart_observer = Mock()
        tm.reload = Mock()

        nginx_config_reloader.after_loop(tm)

        tm.restart_observer.assert_not_called()
        tm.reload.assert_not_called()

    def test_it_swallows_errors_while_restarting_observer(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.symlink_targets_changed = Mock(return_value=True)
        tm.restart_observer = Mock(side_effect=OSError("inotify watch limit reached"))
        tm.reload = Mock()

        nginx_config_reloader.after_loop(tm)

        tm.restart_observer.assert_called_once_with()
        tm.reload.assert_called_once_with()

    def _get_nginx_config_reloader_instance(
        self,
        no_magento_config=False,
        no_custom_config=False,
        magento2_flag=None,
    ):
        return nginx_config_reloader.NginxConfigReloader(
            no_magento_config=no_magento_config,
            no_custom_config=no_custom_config,
            dir_to_watch=self.source,
            magento2_flag=magento2_flag,
        )
