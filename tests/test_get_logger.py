from logging import DEBUG

from nginx_config_reloader import get_logger
from tests.testcase import TestCase


class TestGetLogger(TestCase):
    def setUp(self):
        self.logging = self.set_up_patch(
            'nginx_config_reloader.logging'
        )
        self.handler = self.logging.StreamHandler.return_value
        self.logger = self.set_up_patch(
            'nginx_config_reloader.logger'
        )

    def test_get_logger_instantiates_streamhandler(self):
        get_logger()

        self.logging.StreamHandler.assert_called_once_with()

    def test_get_logger_sets_custom_formatter(self):
        get_logger()

        self.handler.setFormatter.assert_called_once_with(
            self.logging.Formatter.return_value
        )

    def test_get_logger_sets_default_logging_level_to_debug(self):
        get_logger()

        self.logger.setLevel.assert_called_once_with(
            self.logging.DEBUG
        )

    def test_get_logger_adds_custom_logging_handler(self):
        get_logger()

        self.logger.addHandler.assert_called_once_with(
            self.handler
        )

    def test_get_logger_returns_logger(self):
        ret = get_logger()

        self.assertEqual(self.logger, ret)
