import pipes
from subprocess import check_output, CalledProcessError

from nginx_config_reloader import NginxConfigReloader, ILLEGAL_INCLUDE_REGEX, FORBIDDEN_CONFIG_REGEX
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

        NginxConfigReloader.assert_regex_not_present(ILLEGAL_INCLUDE_REGEX)

        self.assertFalse(self.check_output.called)

    def test_assert_no_includes_in_config_checks_user_nginx_dir_for_forbidden_includes(self):
        NginxConfigReloader.assert_regex_not_present(ILLEGAL_INCLUDE_REGEX)

        expected_command = "[ $(grep -r -P '^(?!\\s*#)\\s*(include|load_module)" \
                           "\\s*(\\042|\\047)?\s*(?=.*\\.\\.|/+etc/+nginx/+app_bak|" \
                           "/+(?!etc/+nginx))(\\042|\\047)?\s*' " \
                           "'/data/web/nginx' | wc -l) -lt 1 ]"
        self.check_output.assert_called_once_with(expected_command, shell=True)

    def test_include_prevention_legal_includes(self):
        no_matches = [
            "include /etc/nginx/fastcgi_params",
            "include \"/etc/nginx/php-handler.conf\";",
            "include '/etc/nginx/php-handler.conf';",
            "include ' /etc/nginx/php-handler.conf';",
            "include /etc/nginx/fastcgi_params",
            "include handler.conf",
            "include relative_file.conf",
            "include /etc/nginx/app/server.*;",
            "include /etc/nginx//fastcgi_params",
            "include /etc//nginx/fastcgi_params",
        ]

        for line in no_matches:
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
            'include "/data/web//banaan.config"',
            'include " /data/web//banaan.config"'
        ]

        for line in matches:
            with self.assertRaises(CalledProcessError):
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                    pipes.quote(line), ILLEGAL_INCLUDE_REGEX), shell=True
                )

    def test_forbidden_config_client_body_temp_path_regex_unhappy_case(self):
        TEST_CASES = ["client_body_temp_path /tmp/path",
                      "     client_body_temp_path /tmp/path",
                      "client_body_temp_path  '/tmp/path'",
                      "client_body_temp_path \"/tmp/path\"",
                      "client_body_temp_path  ' /tmp/path'"
                      ]

        for test in TEST_CASES:
            with self.assertRaises(CalledProcessError):
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                    pipes.quote(test), FORBIDDEN_CONFIG_REGEX[0][0]), shell=True
                )

    def test_forbidden_access_or_error_log_configuration_options(self):
        TEST_CASES = [
            "access_log /var/log/nginx/acceptatie.log;",
            "     error_log /var/log/nginx/acceptatie.error.log info;",
            "  access_log   //var//log/nginx/staging.log hypernode;",
            "access_log   /var/log/../../staging.log hypernode;",
            "  access_log   /data/var/log/../../../access.log;",
            "access_log   /tmp/staging.log;",
            "access_log   output.log;",  # would be placed in /usr/share/nginx/output.log
            "access_log '/var/log/nginx/acceptatie.log;'",
            "     error_log \"/var/log/nginx/acceptatie.error.log info;\"",
            "access_log   '/tmp/staging.log ';",
            "access_log   \"output.log;\"",  # would be placed in /usr/share/nginx/output.log
            "access_log  \"/usr/output.log;\"",
            "access_log  '/tmp/staging.log ';",
            "access_log  ' /tmp/staging.log';",
        ]

        for test in TEST_CASES:
            with self.assertRaises(CalledProcessError):
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                    pipes.quote(test), FORBIDDEN_CONFIG_REGEX[1][0]), shell=True
                )

    def test_allowed_access_or_error_log_configuration_options(self):
        TEST_CASES = [
            "access_log /data/var/log/access.log;",
            "     error_log /data/var/log/access.log;",
            "  access_log   //data//var//log//access.log;",
            "access_log '/data/var/log/access.log';",
            "     error_log \"/data/var/log/access.log;\"",
            "  access_log   \"//data//var//log//access.log;\"",
            "#access_log /tmp/log.log;"
        ]

        for test in TEST_CASES:
            check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                pipes.quote(test), FORBIDDEN_CONFIG_REGEX[1][0]), shell=True
            )


