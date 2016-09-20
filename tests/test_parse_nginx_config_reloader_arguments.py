from mock import call

from nginx_config_reloader import parse_nginx_config_reloader_arguments
from tests.testcase import TestCase


class TestParseNginxConfigReloaderArguments(TestCase):
    def setUp(self):
        self.parser = self.set_up_patch(
            'nginx_config_reloader.argparse.ArgumentParser'
        )

    def test_parse_nginx_config_reloader_arguments_instantiates_argparser(self):
        parse_nginx_config_reloader_arguments()

        self.parser.assert_called_once_with()

    def test_parse_nginx_config_reloader_arguments_adds_options(self):
        parse_nginx_config_reloader_arguments()

        expected_calls = [
            call("--daemon", '-d', action='store_true',
                 help='Fork to background and run as daemon'),
            call('--monitor', '-m', action='store_true',
                 help='Monitor files on foreground with output'),
            call('--allow-includes', action='store_true',
                 help='Allow the config to contain includes outside of'
                      ' the system nginx config directory (default False)')
        ]
        self.assertEqual(
            self.parser.return_value.add_argument.mock_calls, expected_calls
        )

    def test_parse_nginx_config_reloader_arguments_returns_parsed_arguments(self):
        ret = parse_nginx_config_reloader_arguments()

        self.assertEqual(ret, self.parser.return_value.parse_args.return_value)

