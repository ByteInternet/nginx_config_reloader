import signal

from nginx_config_reloader import NginxConfigReloader
from tests.testcase import TestCase


class TestReloadNginx(TestCase):
    def setUp(self) -> None:
        self.get_nginx_pid = self.set_up_patch(
            "nginx_config_reloader.NginxConfigReloader.get_nginx_pid",
            return_value=12345,
        )
        self.kill = self.set_up_patch("nginx_config_reloader.os.kill")
        self.check_call = self.set_up_patch(
            "nginx_config_reloader.subprocess.check_call"
        )
        self.reloader = NginxConfigReloader(use_systemd=False)

    def test_reload_nginx_uses_signal_process(self) -> None:
        self.reloader.reload_nginx()
        self.check_call.assert_not_called()
        self.get_nginx_pid.assert_called_once_with()
        self.kill.assert_called_once_with(12345, signal.SIGHUP)

    def test_reload_nginx_does_nothing_if_no_process_pid(self) -> None:
        self.get_nginx_pid.return_value = None
        self.reloader.reload_nginx()
        self.check_call.assert_not_called()
        self.get_nginx_pid.assert_called_once_with()
        self.kill.assert_not_called()

    def test_reload_nginx_uses_systemd(self) -> None:
        self.reloader.use_systemd = True
        self.reloader.reload_nginx()
        self.check_call.assert_called_once_with(["systemctl", "reload", "nginx"])
        self.get_nginx_pid.assert_not_called()
        self.kill.assert_not_called()
