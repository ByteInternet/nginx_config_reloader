import os
import tempfile
from unittest.mock import call

from nginx_config_reloader import NginxConfigReloader, as_unprivileged_user
from tests.testcase import TestCase


class TestFixCustomConfigDirPermissions(TestCase):
    def setUp(self):
        self.check_call = self.set_up_patch("subprocess.check_call")
        self.temp_dir = tempfile.mkdtemp()
        self.tm = NginxConfigReloader(
            no_magento_config=False,
            no_custom_config=False,
            dir_to_watch=self.temp_dir,
            magento2_flag=None,
        )

    def test_fix_custom_config_dir_permissions_chmods_dirs_to_755(self):
        os.chmod(self.temp_dir, 0o700)
        os.mkdir(self.temp_dir + "/some_dir")
        os.chmod(self.temp_dir + "/some_dir", 0o700)

        self.tm.fix_custom_config_dir_permissions()

        self.check_call.assert_has_calls(
            [
                call(["chmod", "755", self.temp_dir], preexec_fn=as_unprivileged_user),
                call(
                    ["chmod", "755", self.temp_dir + "/some_dir"],
                    preexec_fn=as_unprivileged_user,
                ),
            ]
        )

    def test_fix_custom_config_dir_permissions_skips_dirs_that_are_already_755(self):
        os.chmod(self.temp_dir, 0o755)
        os.mkdir(self.temp_dir + "/some_dir")
        os.chmod(self.temp_dir + "/some_dir", 0o755)

        self.tm.fix_custom_config_dir_permissions()

        self.check_call.assert_not_called()

    def test_fix_custom_config_dir_permissions_ignores_symlinks(self):
        other_temp_dir = tempfile.mkdtemp()
        os.symlink(other_temp_dir, self.temp_dir + "/some_pointing_dir")
        os.chmod(self.temp_dir, 0o700)

        self.tm.fix_custom_config_dir_permissions()

        self.check_call.assert_called_once_with(
            ["chmod", "755", self.temp_dir], preexec_fn=as_unprivileged_user
        )
