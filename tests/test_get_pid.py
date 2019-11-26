import mock
import nginx_config_reloader
from tests.testcase import TestCase


class TestGetPid(TestCase):

    def setUp(self):
        self.mock_open = self.set_up_mock_open(read_value='42')

    def test_that_get_pid_returns_pid_from_pidfile(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        self.assertEqual(tm.get_nginx_pid(), 42)

    def test_that_get_pid_returns_none_if_theres_no_pid_file(self):
        self.mock_open.side_effect = IOError('No such file or directory')
        tm = nginx_config_reloader.NginxConfigReloader()
        self.assertIsNone(tm.get_nginx_pid())

    def test_that_get_pid_returns_none_if_pidfile_doesnt_contain_pid(self):
        self.mock_open = self.set_up_mock_open(read_value='')
        tm = nginx_config_reloader.NginxConfigReloader()
        self.assertIsNone(tm.get_nginx_pid())
