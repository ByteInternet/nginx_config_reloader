import pipes
from subprocess import check_output, CalledProcessError, call

from nginx_config_reloader import NginxConfigReloader, FORBIDDEN_CONFIG_REGEX
from tests.testcase import TestCase


class TestAssertNoForbiddenStatementsInConfig(TestCase):
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

        NginxConfigReloader.check_no_forbidden_config_directives_are_present(NginxConfigReloader())

        self.assertFalse(self.check_output.called)

    def test_include_prevention_legal_includes(self):
        TEST_CASES = [
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

        for line in TEST_CASES:
            check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                pipes.quote(line), FORBIDDEN_CONFIG_REGEX[2][0]), shell=True)

    def test_include_prevention_illegal_includes(self):
        TEST_CASES = [
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

        for line in TEST_CASES:
            with self.assertRaises(CalledProcessError):
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                    pipes.quote(line), FORBIDDEN_CONFIG_REGEX[2][0]), shell=True
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
            "access_log   \"output.log\";",  # would be placed in /usr/share/nginx/output.log
            "access_log  \"/usr/output.log\";",
            "access_log  '/tmp/staging.log ';",
            "access_log  ' /tmp/staging.log';",
            "access_log  ../../../some.log;",
            "access_log  \"../some.log\";",
            "access_log   syslog:server=unix:/run/systemd/journal/stdout;",
            "error_log  syslog:server=unix:/run/systemd/journal/stdout;",
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
            "#access_log /tmp/log.log;",
            "access_log syslog:server=log.erikhyperdev.nl:2110 octologs_json;",
            "access_log syslog:server=[2001:db8::1]:12345,facility=local7,tag=nginx,severity=info combined;"
        ]

        for test in TEST_CASES:
            check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                pipes.quote(test), FORBIDDEN_CONFIG_REGEX[1][0]), shell=True
            )

    def test_forbidden_config_init_by_lua_regex_matches_target_directives(self):
        TEST_CASES = ['init_by_lua', 'init_by_lua_block', 'init_by_lua_file']

        for test in TEST_CASES:
            with self.assertRaises(CalledProcessError):
                check_output("[ $(echo {} | grep -P '{}' | wc -l) -lt 1 ]".format(
                    pipes.quote(test), FORBIDDEN_CONFIG_REGEX[3][0]), shell=True
                )

