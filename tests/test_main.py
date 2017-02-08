from mock import Mock

from nginx_config_reloader import logger, main
from tests.testcase import TestCase


class TestMain(TestCase):
    def setUp(self):
        self.wait_loop = self.set_up_context_manager_patch(
            'nginx_config_reloader.wait_loop'
        )
        self.reloader = self.set_up_context_manager_patch(
            'nginx_config_reloader.NginxConfigReloader'
        )

    def test_main_runs_the_reloader_in_the_foreground_if_monitor_is_specified(self):
        main()
        self.wait_loop.assert_called_once_with(logger=logger)
