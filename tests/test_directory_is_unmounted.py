import json

from nginx_config_reloader import directory_is_unmounted
from tests.testcase import TestCase


class TestDirectoryIsUnmounted(TestCase):
    def setUp(self):
        self.check_output = self.set_up_patch(
            "nginx_config_reloader.utils.subprocess.check_output",
            return_value=json.dumps(
                [
                    {
                        "unit": "-.mount",
                        "load": "loaded",
                        "active": "active",
                        "sub": "mounted",
                        "description": "Root Mount",
                    },
                    {
                        "unit": "data-web-nginx.mount",
                        "load": "loaded",
                        "active": "active",
                        "sub": "mounted",
                        "description": "/data/web/nginx",
                    },
                ]
            ),
        )

    def test_it_calls_systemctl_list_units(self):
        directory_is_unmounted("/data/web/nginx")

        self.check_output.assert_called_once_with(
            ["systemctl", "list-units", "-t", "mount", "--all", "-o", "json"],
            encoding="utf-8",
        )

    def test_it_returns_false_if_no_mount_found(self):
        self.check_output.return_value = json.dumps(
            [
                {
                    "unit": "-.mount",
                    "load": "loaded",
                    "active": "active",
                    "sub": "mounted",
                    "description": "Root Mount",
                },
            ]
        )

        self.assertFalse(directory_is_unmounted("/data/web/nginx"))

    def test_it_returns_false_if_mount_exists_active_mounted(self):
        self.assertFalse(directory_is_unmounted("/data/web/nginx"))

    def test_it_returns_true_if_mount_exists_not_active(self):
        self.check_output.return_value = json.dumps(
            [
                {
                    "unit": "-.mount",
                    "load": "loaded",
                    "active": "active",
                    "sub": "mounted",
                    "description": "Root Mount",
                },
                {
                    "unit": "data-web-nginx.mount",
                    "load": "loaded",
                    "active": "inactive",
                    "sub": "dead",
                    "description": "/data/web/nginx",
                },
            ]
        )

        self.assertTrue(directory_is_unmounted("/data/web/nginx"))

    def test_it_returns_true_if_mount_exists_active_not_mounted(self):
        self.check_output.return_value = json.dumps(
            [
                {
                    "unit": "-.mount",
                    "load": "loaded",
                    "active": "active",
                    "sub": "mounted",
                    "description": "Root Mount",
                },
                {
                    "unit": "data-web-nginx.mount",
                    "load": "loaded",
                    "active": "active",
                    "sub": "dead",
                    "description": "/data/web/nginx",
                },
            ]
        )

        self.assertTrue(directory_is_unmounted("/data/web/nginx"))
