import os
import subprocess
from tempfile import mkdtemp, mkstemp, NamedTemporaryFile
import shutil
import signal
import mock
import nginx_config_reloader
from tests.testcase import TestCase


class TestConfigReloader(TestCase):

    def setUp(self):
        self.get_pid = self.set_up_patch('nginx_config_reloader.NginxConfigReloader.get_nginx_pid')
        self.get_pid.return_value = 42
        self.fix_custom_config_dir_permissions = self.set_up_patch(
            'nginx_config_reloader.NginxConfigReloader.fix_custom_config_dir_permissions'
        )

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

        self.test_config = self.set_up_patch('subprocess.check_output')
        self.kill = self.set_up_patch('os.kill')
        self.error_file = os.path.join(nginx_config_reloader.DIR_TO_WATCH, nginx_config_reloader.ERROR_FILE)

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

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._dest('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_config_moves_files_to_dest_dir_if_it_doesnt_yet_exist(self):
        self._write_file(self._source('myfile'), 'config contents')
        shutil.rmtree(self.dest, ignore_errors=True)

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._dest('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_new_config_defaults_to_magento1_config(self):
        self._write_file(self.mag1_conf, 'magento1 config')
        self._write_file(self.mag2_conf, 'magento2 config')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self.mag_conf)
        self.assertTrue(os.path.islink(self.mag_conf))
        self.assertEqual(contents, 'magento1 config')

    def test_that_apply_new_config_does_not_install_configs_if_magento1_config_doesnt_exist(self):
        mock_install_custom = self.set_up_patch(
            'nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        os.unlink(self.mag1_conf)

        tm = self._get_nginx_config_reloader_instance()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

    def test_that_apply_new_config_keeps_current_magento_config_if_symlinking_new_config_goes_wrong(self):
        self._write_file(self.mag_conf, 'magento1 config')

        mock_symlink = self.set_up_patch('os.symlink')
        mock_symlink.side_effect = OSError

        mock_install_custom = self.set_up_patch(
            'nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = self._get_nginx_config_reloader_instance()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

        self.assertTrue(os.path.exists(self.mag_conf))
        contents = self._read_file(self.mag_conf)
        self.assertEqual(contents, 'magento1 config')

    def test_that_apply_new_config_does_not_install_configs_if_magento2_config_doesnt_exist(self):
        mock_install_custom = self.set_up_patch(
            'nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        os.unlink(self.mag2_conf)

        tm = self._get_nginx_config_reloader_instance()
        ret = tm.apply_new_config()

        self.assertFalse(ret)
        self.assertFalse(mock_install_custom.called)

    def test_that_apply_new_config_enables_magento1_config_if_customer_sets_flag(self):
        self._write_file(self.mag1_conf, 'magento1 config')
        self._write_file(self.mag2_conf, 'magento2 config')

        with NamedTemporaryFile() as f:
            nginx_config_reloader.MAGENTO2_FLAG = f.name

            tm = self._get_nginx_config_reloader_instance(magento2_flag=f.name)
            tm.apply_new_config()

        contents = self._read_file(self.mag_conf)
        self.assertTrue(os.path.islink(self.mag_conf))
        self.assertEqual(contents, 'magento2 config')

    def test_that_apply_new_config_keeps_files_in_source_dir(self):
        self._write_file(self._source('myfile'), 'config contents')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._source('myfile'))
        self.assertEqual(contents, 'config contents')

    def test_that_apply_new_config_sends_hup_to_nginx(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_apply_new_config_removes_error_file_when_config_correct_and_ignores_all_oserrors(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_magento_config')

        # This test triggers an OSError because the tempdir we created does not
        # have any error files on disk. So this test tests: 1. the unlink call, 2. the OSErrors
        # OSErrors could be: missing file, no permission to remove
        with mock.patch('os.unlink') as mock_unlink:
            self.test_config.return_value = True

            tm = self._get_nginx_config_reloader_instance()
            tm.apply_new_config()

            error_file = os.path.join(nginx_config_reloader.DIR_TO_WATCH, nginx_config_reloader.ERROR_FILE)
            mock_unlink.assert_has_calls([mock.call(error_file), mock.call(error_file)])

    def test_that_apply_new_config_restores_files_if_config_check_fails(self):
        self._write_file(self._source('conffile'), 'failing config')
        self._write_file(self._dest('conffile'), 'working config')
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._dest('conffile'))
        self.assertEqual(contents, 'working config')

    def test_that_apply_new_config_restores_files_if_dest_didnt_exist_yet(self):
        self._write_file(self._source('conffile'), 'failing config')
        shutil.rmtree(self.dest, ignore_errors=True)
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self.dest))

    def test_that_apply_new_config_doesnt_hup_nginx_if_config_check_fails(self):
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_apply_new_config_writes_error_message_to_source_dir_if_body_temp_path_check_fails(self):
        self.test_config.side_effect = subprocess.CalledProcessError(1, 'nginx', 'oops!')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._source(nginx_config_reloader.ERROR_FILE))
        self.assertIn(nginx_config_reloader.FORBIDDEN_CONFIG_REGEX[0][1], contents)

    def test_that_apply_new_config_writes_error_message_to_source_dir_if_include_is_rejected(self):
        self.isdir = self.set_up_context_manager_patch(
            'nginx_config_reloader.os.path.isdir'
        )
        self.isdir.return_value = True
        self.test_config.side_effect = subprocess.CalledProcessError(1, '', '')  # grep with -q

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._source(nginx_config_reloader.ERROR_FILE))
        self.assertIn(nginx_config_reloader.FORBIDDEN_CONFIG_REGEX[0][1], contents)

    def test_that_apply_new_config_does_not_check_includes_if_dir_to_watch_does_not_exist(self):
        self.isdir = self.set_up_context_manager_patch(
            'nginx_config_reloader.os.path.isdir'
        )
        self.isdir.return_value = False

        self.test_config.side_effect = subprocess.CalledProcessError(1, '', '')  # grep with -q

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        contents = self._read_file(self._source(nginx_config_reloader.ERROR_FILE))
        self.assertEqual(contents, '')

    def test_that_apply_new_config_doesnt_kill_if_no_pidfile(self):
        self.get_pid.return_value = None

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_apply_new_config_doesnt_fail_on_failed_rsync(self):
        check_call = self.set_up_patch('subprocess.check_call')
        check_call.side_effect = OSError('Rsync error')

        tm = self._get_nginx_config_reloader_instance()
        result = tm.apply_new_config()

        self.assertEqual(len(self.test_config.mock_calls), len(nginx_config_reloader.FORBIDDEN_CONFIG_REGEX))
        self.assertEqual(len(self.kill.mock_calls), 0)
        self.assertFalse(result)

    def test_that_apply_new_config_does_install_magento_config_by_default(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_magento_config')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertTrue(tm.install_magento_config.called)

    def test_that_apply_new_config_does_install_custom_config_dir_by_default(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertTrue(tm.install_new_custom_config_dir.called)

    def test_that_apply_new_config_fixes_custom_config_dir_permissions_by_default(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.fix_custom_config_dir_permissions.assert_called_once_with()

    def test_that_apply_new_config_does_not_install_magento_config_if_specified(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_magento_config')

        tm = self._get_nginx_config_reloader_instance(no_magento_config=True)
        tm.apply_new_config()

        self.assertFalse(tm.install_magento_config.called)

    def test_that_apply_new_config_does_not_install_custom_config_dir_if_specified(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = self._get_nginx_config_reloader_instance(no_custom_config=True)
        tm.apply_new_config()

        self.assertFalse(tm.install_new_custom_config_dir.called)

    def test_that_apply_new_config_does_not_fix_custom_config_dir_permissions_if_specified(self):
        self.set_up_patch('nginx_config_reloader.NginxConfigReloader.install_new_custom_config_dir')

        tm = self._get_nginx_config_reloader_instance(no_custom_config=True)
        tm.apply_new_config()

        self.assertFalse(self.fix_custom_config_dir_permissions.called)

    def test_that_error_file_is_not_moved_to_dest_dir(self):
        self._write_file(self._source(nginx_config_reloader.ERROR_FILE), 'some error')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest(nginx_config_reloader.ERROR_FILE)))

    def test_that_files_starting_with_dot_are_not_moved_to_dest_dir(self):
        self._write_file(self._source('.config.swp'), 'asdf')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest('.config.swp')))

    def test_that_flags_are_not_moved_to_dest_dir(self):
        self._write_file(self._source('whatever.flag'), '')

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

        self.assertFalse(os.path.exists(self._dest('whatever.flag')))

    def test_that_handle_event_applies_config(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.handle_event(Event('some_file'))

        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_flags_trigger_config_reload(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.handle_event(Event('magento2.flag'))
        self.kill.assert_called_once_with(42, signal.SIGHUP)

    def test_that_handle_event_doesnt_apply_config_on_change_of_error_file(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.handle_event(Event(nginx_config_reloader.ERROR_FILE))

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_that_handle_event_doesnt_apply_config_on_change_of_invisible_file(self):
        tm = self._get_nginx_config_reloader_instance()
        tm.handle_event(Event('.config.swp'))

        self.assertEqual(len(self.kill.mock_calls), 0)

    def test_remove_error_file_unlinks_the_error_file(self):
        mock_os = self.set_up_patch('nginx_config_reloader.os')
        mock_os.path.join.return_value = self.error_file
        tm = self._get_nginx_config_reloader_instance()
        self.assertTrue(tm.remove_error_file())
        mock_os.unlink.assert_called_once_with(self.error_file)
        self.assertTrue(mock_os.path.join.called)

    def test_remove_error_file_returns_false_on_errors(self):
        mock_os = self.set_up_patch('nginx_config_reloader.os')
        mock_os.unlink.side_effect = OSError('mocked error')
        tm = self._get_nginx_config_reloader_instance()
        self.assertFalse(tm.remove_error_file())

    def test_that_install_new_custom_config_dir_always_removes_the_error_file_before_copying_configs(self):
        mock_remove_error_file = self.set_up_patch('nginx_config_reloader.NginxConfigReloader.remove_error_file')
        # ensure all IO operations would fail other than error_file removal
        mock_shutil = self.set_up_patch('nginx_config_reloader.shutil')
        mock_shutil.rmtree.side_effect = RuntimeError('mock error')
        mock_shutil.move.side_effect = RuntimeError('mock error')
        mock_shutil.copytree.side_effect = RuntimeError('mock error')

        tm = self._get_nginx_config_reloader_instance()
        with self.assertRaises(RuntimeError):
            tm.install_new_custom_config_dir()

        self.assertTrue(mock_remove_error_file.called)

    def test_recursive_symlink_is_not_copied(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.symlink(dst=os.path.join(self.source, 'new_dir/recursive_symlink'), src=self.source)
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertFalse(os.path.exists(self._dest('new_dir/recursive_symlink')))

    def test_backup_is_placed_if_custom_config_fails_to_be_placed(self):
        check_call = self.set_up_patch('subprocess.check_call')
        check_call.side_effect = OSError('Rsync error')
        os.mkdir(self._dest('old_dir'))

        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertTrue(os.path.exists(self._dest('old_dir')))

    def test_other_files_are_not_placed_on_rsync_error(self):
        check_call = self.set_up_patch('subprocess.check_call')
        check_call.side_effect = OSError('Rsync error')

        os.mkdir(self._source('new_dir'))
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertFalse(os.path.exists(self._dest('new_dir')))

    def test_rsync_error_is_placed_in_error_file(self):
        check_call = self.set_up_patch('subprocess.check_call')
        check_call.side_effect = OSError('Rsync error')

        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.symlink(dst=os.path.join(self.source, 'new_dir/recursive_symlink'), src=self.source)
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertTrue(os.path.exists(self.error_file))
        with open(self.error_file) as fp:
            self.assertIn("Rsync error", fp.read())

    def test_reloader_doesnt_crash_if_source_dir_is_empty(self):
        shutil.rmtree(self.source, ignore_errors=True)
        os.mkdir(self.source)

        # Doesn't crash
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()

    def test_files_are_copied(self):
        with open(os.path.join(self.source, 'server.test.cnf'), 'w') as fp:
            fp.write("test")
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertTrue(os.path.exists(os.path.join(self.dest, 'server.test.cnf')))
        with open(os.path.join(self.dest, 'server.test.cnf')) as fp:
            self.assertIn('test', fp.read())

    def test_new_dir_is_placed(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertTrue(os.path.exists(os.path.join(self.dest, 'new_dir')))

    def test_dotfiles_are_ignored(self):
        os.mkdir(os.path.join(self.source, '.git'))
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertFalse(os.path.exists(os.path.join(self.dest, '.git')))

    def test_symlink_to_file_is_copied_to_file(self):
        with open(os.path.join(self.source, 'server.test.cnf'), 'w') as fp:
            fp.write("test")
        os.symlink(
            dst=os.path.join(self.source, 'symlink'),
            src=os.path.join(self.source, 'server.test.cnf')
        )
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertFalse(os.path.islink(os.path.join(self.dest, 'symlink')))
        self.assertTrue(os.path.isfile(os.path.join(self.dest, 'symlink')))

    def test_symlink_to_dir_is_copied_to_dir(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.symlink(
            dst=os.path.join(self.source, 'symlink'),
            src=os.path.join(self.source, 'new_dir')
        )
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertFalse(os.path.islink(os.path.join(self.dest, 'symlink')))
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'symlink')))

    def test_permissions_are_masked_for_file(self):
        with open(os.path.join(self.source, 'server.test.cnf'), 'w') as fp:
            fp.write("test")
        os.chmod(os.path.join(self.source, 'server.test.cnf'), 0o777)
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertEqual(str(oct(os.stat(os.path.join(self.dest, 'server.test.cnf')).st_mode))[-4:], '0644')

    def test_permissions_are_masked_for_directory(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.chmod(os.path.join(self.source, 'new_dir'), 0o777)
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertEqual(str(oct(os.stat(os.path.join(self.dest, 'new_dir')).st_mode))[-4:], '0755')

    def test_permissions_are_masked_for_file_in_subdir(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        with open(os.path.join(self.source, 'new_dir/server.test.cnf'), 'w') as fp:
            fp.write("test")
        os.chmod(os.path.join(self.source, 'new_dir/server.test.cnf'), 0o777)
        tm = self._get_nginx_config_reloader_instance()
        tm.apply_new_config()
        self.assertEqual(str(oct(os.stat(os.path.join(self.dest, 'new_dir/server.test.cnf')).st_mode))[-4:], '0644')

    def _get_nginx_config_reloader_instance(self, no_magento_config=False, no_custom_config=False, magento2_flag=None):
        return nginx_config_reloader.NginxConfigReloader(
            no_magento_config=no_magento_config,
            no_custom_config=no_custom_config,
            dir_to_watch=self.source,
            magento2_flag=magento2_flag
        )

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

    def _backup(self, name):
        return os.path.join(self.backup, name)


class Event:
    def __init__(self, name):
        self.name = name
        self.maskname = 'IN_CLOSE_WRITE'
