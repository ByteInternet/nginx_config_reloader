from mock import Mock

from nginx_config_reloader import logger, main
from tests.testcase import TestCase


class TestMain(TestCase):
    def setUp(self):
        self.args = Mock(
            daemon=False,
            monitor=True,
        )
        self.parse_nginx_config_reloader_arguments = self.set_up_patch(
            'nginx_config_reloader.parse_nginx_config_reloader_arguments',
        )
        self.parse_nginx_config_reloader_arguments.return_value = self.args
        self.daemoncontext = self.set_up_context_manager_patch(
            'nginx_config_reloader.daemon.DaemonContext'
        )
        self.wait_loop = self.set_up_context_manager_patch(
            'nginx_config_reloader.wait_loop'
        )
        self.reloader = self.set_up_context_manager_patch(
            'nginx_config_reloader.NginxConfigReloader'
        )

    def test_main_parses_arguments(self):
        main()

        self.parse_nginx_config_reloader_arguments.assert_called_once_with()

    def test_main_runs_the_reloader_in_the_foreground_if_monitor_is_specified(self):
        main()

        self.assertFalse(self.daemoncontext.called)
        self.wait_loop.assert_called_once_with(logger=logger)

    def test_main_runs_the_reloader_in_the_background_if_daemon_is_specified(self):
        self.args.daemon = True
        self.args.monitor = False
        self.parse_nginx_config_reloader_arguments.return_value = self.args

        main()

        self.assertTrue(self.daemoncontext.called)
        self.wait_loop.assert_called_once_with(logger=logger)

    def test_main_runs_the_reloader_once_if_no_monitor_or_daemon_is_specified(self):
        self.args.daemon = False
        self.args.monitor = False
        self.parse_nginx_config_reloader_arguments.return_value = self.args

        main()

        self.reloader.assert_called_once_with(allow_includes=self.args.allow_includes)
        self.reloader.return_value.apply_new_config.assert_called_once_with()
