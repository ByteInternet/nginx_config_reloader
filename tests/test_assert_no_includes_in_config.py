from nginx_config_reloader import NginxConfigReloader
from tests.testcase import TestCase


class TestAssertNoIncludesInConfig(TestCase):
    def setUp(self):
        self.isdir = self.set_up_patch(
            'nginx_config_reloader.os.path.isdir'
        )
        self.isdir.return_value = True
        self.check_output = self.set_up_patch(
            'nginx_config_reloader.subprocess.check_output'
        )

    def test_assert_no_includes_in_config_does_not_check_config_if_no_dir_to_watch(self):
        self.isdir.return_value = False

        NginxConfigReloader.assert_no_includes_in_config()

        self.assertFalse(self.check_output.called)

    def test_assert_no_includes_in_config_checks_user_nginx_dir_for_forbidden_includes(self):
        NginxConfigReloader.assert_no_includes_in_config()

        expected_command = "[ $(grep --no-filename -r 'include\|load_module' '/data/web/nginx' | " \
                           "grep -v '^\s*#\|include [^/\|^..]\|/etc/nginx' | wc -l) -lt 1 ]"
        self.check_output.assert_called_once_with(expected_command, shell=True)

