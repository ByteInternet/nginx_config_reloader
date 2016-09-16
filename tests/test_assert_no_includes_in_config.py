import pipes
from subprocess import check_output, CalledProcessError

from nginx_config_reloader import NginxConfigReloader, ILLEGAL_INCLUDE_REGEX
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

    def test_include_prevention_legal_includes(self):
        no_matches = [
            "include /etc/nginx/fastcgi_params",
            "include \"/etc/nginx/php-handler.conf\";",
            "include '/etc/nginx/php-handler.conf';",
            "include /etc/nginx/fastcgi_params",
            "include handler.conf",
            "include relative_file.conf",
            "include /etc/nginx/app/server.*;",
            "include /etc/nginx//fastcgi_params",
            "include /etc//nginx/fastcgi_params",
        ]

        for line in no_matches:
            print line
            check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(pipes.quote(line), ILLEGAL_INCLUDE_REGEX),
                         shell=True)

    def test_include_prevention_illegal_includes(self):
        matches = [
            "include /data/web/nginx/someexample.allow;",
            "include /etc/nginx/../../data/web/banaan.config",
            'include "/etc/nginx/../../data/web/banaan.config"',
            "include '/etc/nginx/../data/web/banaan.config'",
            "include /data/web/banaan.config",
            "include somedir/../../../../danger",
            "include '/data/web/banaan.config'",
            'include "/data/web/banaan.config"',
            "include /etc/nginx/app_bak/server.*;",
            'include "/data//web/banaan.config"',
            'include "//data/web/banaan.config"',
            'include "/data/web//banaan.config"'
        ]

        for line in matches:
            with self.assertRaises(CalledProcessError):
                print line
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(pipes.quote(line), ILLEGAL_INCLUDE_REGEX), shell=True)
