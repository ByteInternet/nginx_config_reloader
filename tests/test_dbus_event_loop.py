from nginx_config_reloader import dbus_event_loop
from tests.testcase import TestCase


class TestDbusEventLoop(TestCase):
    def setUp(self):
        self.event_loop = self.set_up_patch("nginx_config_reloader.EventLoop")

    def test_it_runs_dbus_event_loop(self):
        dbus_event_loop()

        self.event_loop.assert_called_once_with()
        self.event_loop.return_value.run.assert_called_once_with()
