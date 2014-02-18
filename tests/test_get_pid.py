import unittest
import mock
import nginx_config_reloader


class TestGetPid(unittest.TestCase):

    def test_that_get_pid_returns_pid_from_pidfile(self):
        with mock.patch('__builtin__.open', mock.mock_open(read_data='42')):
            tm = nginx_config_reloader.NginxConfigReloader()
            self.assertEqual(tm.get_nginx_pid(), 42)

    def test_that_get_pid_returns_none_if_theres_no_pid_file(self):
        with mock.patch('__builtin__.open', mock.mock_open()) as m:
            m.side_effect = IOError('No such file or directory')

            tm = nginx_config_reloader.NginxConfigReloader()
            self.assertIsNone(tm.get_nginx_pid())

    def test_that_get_pid_returns_none_if_pidfile_doesnt_contain_pid(self):
        with mock.patch('__builtin__.open', mock.mock_open(read_data='')):

            tm = nginx_config_reloader.NginxConfigReloader()
            self.assertIsNone(tm.get_nginx_pid())