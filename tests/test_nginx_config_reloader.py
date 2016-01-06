import os
import subprocess
from tempfile import mkdtemp, mkstemp, NamedTemporaryFile
import unittest
import shutil
import signal
import mock
import nginx_config_reloader


class TestConfigReloader(unittest.TestCase):

    def setUp(self):
        self.get_pid = self._patch('nginx_config_reloader.NginxConfigReloader.get_nginx_pid')
        self.get_pid.return_value = 42

        self.source = mkdtemp()
        self.dest = mkdtemp()
        self.backup = mkdtemp()
        _, self.mag_conf = mkstemp(text=True)
        _, self.mag1_conf = mkstemp(text=True)
        _, self.mag2_conf = mkstemp(text=True)

        nginx_config_reloader.DIR_TO_WATCH = self.source
        nginx_config_reloader.CUSTOM_CONFIG_DIR = self.dest
        nginx_config_reloader.BACKUP_CONFIG_DIR = self.backup

        nginx_config_reloader.MAGENTO_CONF = self.mag_conf
        nginx_config_reloader.MAGENTO1_CONF = self.mag1_conf
        nginx_config_reloader.MAGENTO2_CONF = self.mag2_conf

        self.test_config = self._patch('subprocess.check_output')
        self.kill = self._patch('os.kill')

    def tearDown(self):
        shutil.rmtree(self.source, ignore_errors=True)
        shutil.rmtree(self.dest, ignore_errors=True)
        shutil.rmtree(self.backup, ignore_errors=True)
        for f in [self.mag_conf, self.mag1_conf, self.mag2_conf]:
            try:
                os.unlink(f)
            except OSError:
                pass

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

    def test_that_apply_new_config_defaults_to_magento1_config(self):
        self._write_file(self.mag1_conf, 'magento1 config')
        self._write_file(self.mag2_conf, 'magento2 config')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        contents = self._read_file(self.mag_conf)
        self.assertTrue(os.path.islink(self.mag_conf))
        self.assertEqual(contents, 'magento1 config')

    def test_that_apply_new_config_does_not_install_configs_if_magento1_config_doesnt_exist(self):
        mock_install_custom = self._patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        os.unlink(self.mag1_conf)

        tm = nginx_config_reloader.NginxConfigReloader()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

    def test_that_apply_new_config_keeps_current_magento_config_if_symlinking_new_config_goes_wrong(self):
        self._write_file(self.mag_conf, 'magento1 config')

        mock_symlink = self._patch('os.symlink')
        mock_symlink.side_effect = OSError

        mock_install_custom = self._patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = nginx_config_reloader.NginxConfigReloader()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

        self.assertTrue(os.path.exists(self.mag_conf))
        contents = self._read_file(self.mag_conf)
        self.assertEqual(contents, 'magento1 config')

    def test_that_apply_new_config_does_not_install_configs_if_magento2_config_doesnt_exist(self):
        mock_install_custom = self._patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        os.unlink(self.mag2_conf)

        tm = nginx_config_reloader.NginxConfigReloader()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

    def test_that_apply_new_config_enables_magento1_config_if_customer_sets_flag(self):
        self._write_file(self.mag1_conf, 'magento1 config')
        self._write_file(self.mag2_conf, 'magento2 config')

        with NamedTemporaryFile() as f:
            nginx_config_reloader.MAGENTO2_FLAG = f.name

            tm = nginx_config_reloader.NginxConfigReloader()
            tm.apply_new_config()

        contents = self._read_file(self.mag_conf)
        self.assertTrue(os.path.islink(self.mag_conf))
        self.assertEqual(contents, 'magento2 config')

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

    def test_that_apply_new_config_removes_error_file_when_config_correct_and_ignores_all_oserrors(self):
        self._patch('nginx_config_reloader.NginxConfigReloader.install_magento_config')

        # This test triggers an OSError because the tempdir we created does not
        # have any error files on disk. So this test tests: 1. the unlink call, 2. the OSErrors
        # OSErrors could be: missing file, no permission to remove
        with mock.patch('os.unlink') as mock_unlink:
            self.test_config.return_value = True

            tm = nginx_config_reloader.NginxConfigReloader()
            tm.apply_new_config()

            error_file = os.path.join(nginx_config_reloader.DIR_TO_WATCH, nginx_config_reloader.ERROR_FILE)
            mock_unlink.assert_called_once_with(error_file)

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

    def test_that_flags_are_not_moved_to_dest_dir(self):
        self._write_file(self._source('whatever.flag'), '')

        tm = nginx_config_reloader.NginxConfigReloader()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest('whatever.flag')))

    def test_that_handle_event_applies_config(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.handle_event(Event('some_file'))

        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_flags_trigger_config_reload(self):
        tm = nginx_config_reloader.NginxConfigReloader()
        tm.handle_event(Event('magento2.flag'))
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


class Event:
    def __init__(self, name):
        self.name = name
        self.maskname = 'IN_CLOSE_WRITE'
