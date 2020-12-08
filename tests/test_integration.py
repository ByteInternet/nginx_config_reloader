import os
from os import makedirs
from shutil import rmtree
from tempfile import mkdtemp

from nginx_config_reloader import NginxConfigReloader
from tests.testcase import TestCase


class TestIntegration(TestCase):
    def setUp(self):
        module = 'nginx_config_reloader.'
        self.source = mkdtemp()
        self.root_nginx = mkdtemp()
        self.main_config = self.set_up_patch(module + 'MAIN_CONFIG_DIR', self.root_nginx)
        self.dest = self.set_up_patch(module + 'CUSTOM_CONFIG_DIR', os.path.join(self.main_config, 'app'))
        self.set_up_patch(module + 'BACKUP_CONFIG_DIR', os.path.join(self.main_config, 'app_bak'))
        self.set_up_patch(module + 'MAGENTO_CONF', os.path.join(self.dest, 'magento.conf'))
        self.mag1_conf = self.set_up_patch(module + 'MAGENTO1_CONF', os.path.join(self.dest, 'magento1.conf'))
        self.mag2_conf = self.set_up_patch(module + 'MAGENTO2_CONF', os.path.join(self.dest, 'magento2.conf'))
        makedirs(self.dest, exist_ok=True)
        with open(self.mag1_conf, 'w') as fp:
            fp.write('mag1')
        with open(self.mag2_conf, 'w') as fp:
            fp.write('mag2')
        self.set_up_patch('subprocess.check_output')  # Don't run nginx
        self.reload_nginx = self.set_up_patch(module + 'NginxConfigReloader.reload_nginx')  # Never reload nginx

    def tearDown(self):
        rmtree(self.source, ignore_errors=True)
        rmtree(self.root_nginx, ignore_errors=True)

    def test_reloader_doesnt_crash_if_source_dir_is_empty(self):
        rmtree(self.source, ignore_errors=True)
        os.mkdir(self.source)

        # Doesn't crash
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()

    def test_files_are_copied(self):
        with open(os.path.join(self.source, 'server.test.cnf'), 'w') as fp:
            fp.write("test")
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertTrue(os.path.exists(os.path.join(self.dest, 'server.test.cnf')))
        with open(os.path.join(self.dest, 'server.test.cnf')) as fp:
            self.assertIn('test', fp.read())

    def test_new_dir_is_placed(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertTrue(os.path.exists(os.path.join(self.dest, 'new_dir')))

    def test_dotfiles_are_ignored(self):
        os.mkdir(os.path.join(self.source, '.git'))
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertFalse(os.path.exists(os.path.join(self.dest, '.git')))

    def test_symlink_to_file_is_copied_to_file(self):
        with open(os.path.join(self.source, 'server.test.cnf'), 'w') as fp:
            fp.write("test")
        os.symlink(
            dst=os.path.join(self.source, 'symlink'),
            src=os.path.join(self.source, 'server.test.cnf')
        )
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertFalse(os.path.islink(os.path.join(self.dest, 'symlink')))
        self.assertTrue(os.path.isfile(os.path.join(self.dest, 'symlink')))

    def test_symlink_to_dir_is_copied_to_dir(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.symlink(
            dst=os.path.join(self.source, 'symlink'),
            src=os.path.join(self.source, 'new_dir')
        )
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertFalse(os.path.islink(os.path.join(self.dest, 'symlink')))
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'symlink')))

    def test_recursive_symlink_is_recursively_copied(self):
        os.mkdir(os.path.join(self.source, 'new_dir'))
        os.symlink(dst=os.path.join(self.source, 'new_dir/recursive_symlink'), src=self.source)
        NginxConfigReloader(dir_to_watch=self.source).apply_new_config()
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'new_dir/recursive_symlink')))
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'new_dir/recursive_symlink/new_dir')))
        self.assertTrue(os.path.isdir(os.path.join(self.dest, 'new_dir/recursive_symlink/new_dir/recursive_symlink')))
