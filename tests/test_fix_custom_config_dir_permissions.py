import os
import tempfile
from unittest.mock import call

from nginx_config_reloader import NginxConfigReloader
from tests.testcase import TestCase


class TestFixCustomConfigDirPermissions(TestCase):
    def setUp(self):
        self.chmod = self.set_up_patch('os.chmod')
        self.temp_dir = tempfile.mkdtemp()
        self.tm = NginxConfigReloader(
            no_magento_config=False,
            no_custom_config=False,
            dir_to_watch=self.temp_dir,
            magento2_flag=None
        )

    def test_fix_custom_config_dir_permissions_chmods_all_dirs_to_755(self):
        os.mkdir(self.temp_dir + "/some_dir")

        self.tm.fix_custom_config_dir_permissions()

        self.chmod.assert_has_calls([
            call(self.temp_dir, 0o755),
            call(self.temp_dir + "/some_dir", 0o755),
        ])

    def test_fix_custom_config_dir_permissions_ignores_symlinks(self):
        other_temp_dir = tempfile.mkdtemp()
        os.symlink(other_temp_dir, self.temp_dir + "/some_pointing_dir")

        self.tm.fix_custom_config_dir_permissions()

        self.chmod.assert_called_once_with(self.temp_dir, 0o755)
