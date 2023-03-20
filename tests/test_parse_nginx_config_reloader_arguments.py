from mock import call

import nginx_config_reloader
from nginx_config_reloader import parse_nginx_config_reloader_arguments
from tests.testcase import TestCase


class TestParseNginxConfigReloaderArguments(TestCase):
    def setUp(self):
        self.parser = self.set_up_patch("nginx_config_reloader.argparse.ArgumentParser")

    def test_parse_nginx_config_reloader_arguments_instantiates_argparser(self):
        parse_nginx_config_reloader_arguments()

        self.parser.assert_called_once_with()

    def test_parse_nginx_config_reloader_arguments_adds_options(self):
        parse_nginx_config_reloader_arguments()

        expected_calls = [
            call(
                "--monitor",
                "-m",
                action="store_true",
                help="Monitor files on foreground with output",
            ),
            call(
                "--nomagentoconfig",
                action="store_true",
                help="Disable Magento configuration",
                default=False,
            ),
            call(
                "--nocustomconfig",
                action="store_true",
                help="Disable copying custom configuration",
                default=False,
            ),
            call(
                "--watchdir",
                "-w",
                help="Set directory to watch",
                default=nginx_config_reloader.DIR_TO_WATCH,
            ),
            call(
                "--recursivewatch",
                action="store_true",
                help="Enable recursive watching of subdirectories",
                default=False,
            ),
            call(
                "--use-systemd",
                action="store_true",
                help="Reload nginx using systemd instead of process signal",
                default=False,
            ),
            call(
                "-s",
                "--nats-server",
                help="NATS server to connect to. Will publish/subscribe to the topic 'nginx-config-reloader'. Will not use this if not set.",
            ),
        ]
        self.assertEqual(
            self.parser.return_value.add_argument.mock_calls, expected_calls
        )

    def test_parse_nginx_config_reloader_arguments_returns_parsed_arguments(self):
        ret = parse_nginx_config_reloader_arguments()

        self.assertEqual(ret, self.parser.return_value.parse_args.return_value)
