import os
import tempfile
from unittest.mock import call

from nginx_config_reloader import NginxConfigReloader, as_unprivileged_user
from tests.testcase import TestCase


class TestFixCustomConfigDirPermissions(TestCase):
    def setUp(self):
        self.check_output = self.set_up_patch("subprocess.check_output")
        self.temp_dir = tempfile.mkdtemp()
        self.tm = NginxConfigReloader(
            no_magento_config=False,
            no_custom_config=False,
            dir_to_watch=self.temp_dir,
            magento2_flag=None,
        )

    def test_fix_custom_config_dir_permissions_chmods_all_dirs_to_755(self):
        os.mkdir(self.temp_dir + "/some_dir")

        self.tm.fix_custom_config_dir_permissions()

        self.check_output.assert_has_calls(
            [
                call(["chmod", "755", self.temp_dir], preexec_fn=as_unprivileged_user),
                call(
                    ["chmod", "755", self.temp_dir + "/some_dir"],
                    preexec_fn=as_unprivileged_user,
                ),
            ]
        )

    def test_fix_custom_config_dir_permissions_ignores_symlinks(self):
        other_temp_dir = tempfile.mkdtemp()
        os.symlink(other_temp_dir, self.temp_dir + "/some_pointing_dir")

        self.tm.fix_custom_config_dir_permissions()

        self.check_output.assert_called_once_with(
            ["chmod", "755", self.temp_dir], preexec_fn=as_unprivileged_user
        )
