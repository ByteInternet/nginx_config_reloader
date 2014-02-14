import os
import subprocess
from tempfile import mkdtemp
import unittest
import mock
import shutil
import signal
import nginx_config_reloader


class TestConfigReloader(unittest.TestCase):

    def setUp(self):
        self.get_pid = self._patch('nginx_config_reloader.NginxConfigReloader.get_nginx_pid')
        self.get_pid.return_value = 42

        self.source = mkdtemp()
        nginx_config_reloader.DIR_TO_WATCH = self.source
        self.dest = mkdtemp()
        nginx_config_reloader.CUSTOM_CONFIG_DIR = self.dest
        nginx_config_reloader.BACKUP_CONFIG_DIR = mkdtemp()

        self.test_config = self._patch('subprocess.check_output')
        self.kill = self._patch('os.kill')

    def tearDown(self):
        shutil.rmtree(self.source, ignore_errors=True)
        shutil.rmtree(self.dest, ignore_errors=True)
        shutil.rmtree(nginx_config_reloader.BACKUP_CONFIG_DIR, ignore_errors=True)

    def test_that_apply_new_config_moves_files_to_dest_dir(self):
        self._write_file(self._source('myfile'), 'config contents')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self._dest('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_config_moves_files_to_dest_dir_if_it_doesnt_yet_exist(self):
        self._write_file(self._source('myfile'), 'config contents')
        shutil.rmtree(self.dest, ignore_errors=True)

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self._dest('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_new_config_keeps_files_in_source_dir(self):
        self._write_file(self._source('myfile'), 'config contents')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self._source('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_new_config_sends_hup_to_nginx(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_apply_new_config_restores_files_if_config_check_fails(self):
        self._write_file(self._source('conffile'), 'failing config')
        self._write_file(self._dest('conffile'), 'working config')
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self._dest('conffile'))
        self.assertEqual(contents, 'working config')

    def test_that_apply_new_config_restores_files_if_dest_didnt_exist_yet(self):
        self._write_file(self._source('conffile'), 'failing config')
        shutil.rmtree(self.dest, ignore_errors=True)
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self.dest))

    def test_that_apply_new_config_doesnt_hup_nginx_if_config_check_fails(self):
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_apply_new_config_writes_error_message_to_source_dir(self):
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops!')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self._source(nginx_config_reloader.ERROR_FILE))
        self.assertEqual(contents, 'oops!')

    def test_that_apply_new_config_doesnt_kill_if_no_pidfile(self):
        self.get_pid.return_value = None

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_apply_new_config_doesnt_fail_on_failing_copy(self):
        copytree = self._patch('shutil.copytree')
        copytree.side_effect = OSError('Directory doesnt exist')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertEqual(len(self.test_config.mock_calls), 0)
        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_error_file_is_not_moved_to_dest_dir(self):
        self._write_file(self._source(nginx_config_reloader.ERROR_FILE), 'some error')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest(nginx_config_reloader.ERROR_FILE)))

    def test_that_files_starting_with_dot_are_not_moved_to_dest_dir(self):
        self._write_file(self._source('.config.swp'), 'asdf')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest('.config.swp')))

    def test_that_handle_event_applies_config(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.handle_event(Event('some_file'))

        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_handle_event_doesnt_apply_config_on_change_of_error_file(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.handle_event(Event(nginx_config_reloader.ERROR_FILE))

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_handle_event_doesnt_apply_config_on_change_of_invisible_file(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.handle_event(Event('.config.swp'))

        self.assertEqual(len(self.kill.mock_calls), 0)

    def _patch(self, name):
        themock = mock.Mock()

        patcher = mock.patch(name, themock)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def _write_file(self, name, contents):
        with open(name, 'w') as f:
            f.write(contents)

    def _read_file(self, name):
        with open(name) as f:
            return f.read()

    def _source(self, name):
        return os.path.join(self.source, name)

    def _dest(self, name):
        return os.path.join(self.dest, name)


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


class Event:
    def __init__(self, name):
        self.name = name
        self.maskname = 'IN_CLOSE_WRITE'