from mock import Mock

import shutil
from tempfile import mkdtemp
from nginx_config_reloader import main
from tests.testcase import TestCase


class TestMain(TestCase):
    def setUp(self):
        self.source = mkdtemp()
        self.parse_nginx_config_reloader_arguments = self.set_up_patch(
            'nginx_config_reloader.parse_nginx_config_reloader_arguments'
        )
        self.parse_nginx_config_reloader_arguments.return_value = Mock(
            monitor=False, allow_includes=False,
            nomagentoconfig=False, nocustomconfig=False, watchdir=self.source,
            norecursivewatch=False
        )
        self.get_logger = self.set_up_context_manager_patch(
            'nginx_config_reloader.get_logger'
        )
        self.wait_loop = self.set_up_context_manager_patch(
            'nginx_config_reloader.wait_loop'
        )
        self.reloader = self.set_up_context_manager_patch(
            'nginx_config_reloader.NginxConfigReloader'
        )

    def tearDown(self):
        shutil.rmtree(self.source, ignore_errors=True)

    def test_main_gets_logger(self):
        main()

        self.get_logger.assert_called_once_with()

    def test_main_parses_nginx_config_reloader_arguments(self):
        main()

        self.parse_nginx_config_reloader_arguments.assert_called_once_with()

    def test_main_reloads_config_once_if_monitor_mode_not_specified(self):
        main()

        self.reloader.assert_called_once_with(
            logger=self.get_logger.return_value,
            no_magento_config=self.parse_nginx_config_reloader_arguments.return_value.nomagentoconfig,
            no_custom_config=self.parse_nginx_config_reloader_arguments.return_value.nocustomconfig,
            dir_to_watch=self.parse_nginx_config_reloader_arguments.return_value.watchdir,
            no_recursive_watch=self.parse_nginx_config_reloader_arguments.return_value.norecursivewatch
        )
        self.reloader.return_value.apply_new_config()

    def test_main_does_not_watch_the_config_dir_if_monitor_mode_not_specified(self):
        main()

        self.assertFalse(self.wait_loop.called)

    def test_main_returns_zero_if_no_errors_after_reloading_once(self):
        ret = main()

        self.assertEqual(0, ret)

    def test_main_watches_the_config_dir_if_monitor_specified(self):
        self.parse_nginx_config_reloader_arguments.return_value.monitor = True

        main()

        self.wait_loop.assert_called_once_with(
            logger=self.get_logger.return_value,
            no_magento_config=self.parse_nginx_config_reloader_arguments.return_value.nomagentoconfig,
            no_custom_config=self.parse_nginx_config_reloader_arguments.return_value.nocustomconfig,
            dir_to_watch=self.parse_nginx_config_reloader_arguments.return_value.watchdir,
            no_recursive_watch=self.parse_nginx_config_reloader_arguments.return_value.norecursivewatch
        )

    def test_main_watches_the_config_dir_if_monitor_mode_is_specified_and_includes_allowed(self):
        self.parse_nginx_config_reloader_arguments.return_value.allow_includes = True
        self.parse_nginx_config_reloader_arguments.return_value.monitor = True

        main()

        self.wait_loop.assert_called_once_with(
            logger=self.get_logger.return_value,
            no_magento_config=self.parse_nginx_config_reloader_arguments.return_value.nomagentoconfig,
            no_custom_config=self.parse_nginx_config_reloader_arguments.return_value.nocustomconfig,
            dir_to_watch=self.parse_nginx_config_reloader_arguments.return_value.watchdir,
            no_recursive_watch=self.parse_nginx_config_reloader_arguments.return_value.norecursivewatch
        )

    def test_main_does_not_reload_the_config_once_if_monitor_mode_is_specified(self):
        self.parse_nginx_config_reloader_arguments.return_value.monitor = True

        main()

        self.assertFalse(self.reloader.called)

    def test_main_returns_nonzero_if_monitor_mode_and_loop_returns(self):
        self.parse_nginx_config_reloader_arguments.return_value.monitor = True

        ret = main()

        self.assertEqual(1, ret)
