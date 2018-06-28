import subprocess

from nginx_config_reloader import NginxConfigReloader, as_unprivileged_user
from tests.testcase import TestCase


class TestFixCustomConfigDirPermissions(TestCase):
    def setUp(self):
        self.check_output = self.set_up_patch(
            'nginx_config_reloader.subprocess.check_output'
        )
        self.tm = NginxConfigReloader(
            no_magento_config=False,
            no_custom_config=False,
            dir_to_watch='/data/web/nginx',
            magento2_flag=None
        )

    def test_fix_custom_config_dir_permissions_chmods_all_dirs_to_755(self):
        self.tm.fix_custom_config_dir_permissions()

        self.check_output.assert_called_once_with(
            ['find', self.tm.dir_to_watch, '-type', 'd', '-exec', 'chmod', '0755', '{}', ';'],
            preexec_fn=as_unprivileged_user,
            stderr=subprocess.STDOUT
        )

    def test_fix_custom_config_dir_permissions_does_not_raise_if_find_fails(self):
        self.check_output.side_effect = subprocess.CalledProcessError('', '', '')
        self.tm.fix_custom_config_dir_permissions()
