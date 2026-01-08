import logging
import shutil
from tempfile import mkdtemp
from unittest.mock import Mock, call

import nginx_config_reloader
from nginx_config_reloader import ListenTargetTerminated, wait_loop
from tests.testcase import TestCase


class TestWaitLoop(TestCase):
    def setUp(self):
        self.source = mkdtemp()
        self.mock_logger = Mock(spec_set=logging.Logger)
        self.nginx_config_reloader = self.set_up_patch(
            "nginx_config_reloader.NginxConfigReloader"
        )
        self.mock_handler = Mock()
        self.nginx_config_reloader.return_value = self.mock_handler
        self.set_up_patch("nginx_config_reloader.SYSTEM_BUS")
        self.set_up_patch("nginx_config_reloader.NginxConfigReloaderInterface")
        self.set_up_patch("nginx_config_reloader.threading.Thread")
        self.time_sleep = self.set_up_patch("nginx_config_reloader.time.sleep")
        self.after_loop = self.set_up_patch("nginx_config_reloader.after_loop")

    def tearDown(self):
        shutil.rmtree(self.source, ignore_errors=True)

    def test_wait_loop_creates_nginx_config_reloader_handler(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.nginx_config_reloader.assert_called_once_with(
            logger=self.mock_logger,
            no_magento_config=False,
            no_custom_config=False,
            dir_to_watch=self.source,
            use_systemd=False,
        )

    def test_wait_loop_creates_handler_with_custom_arguments(self):
        self._run_wait_loop_with_keyboard_interrupt(
            no_magento_config=True,
            no_custom_config=True,
            use_systemd=True,
        )

        self.nginx_config_reloader.assert_called_once_with(
            logger=self.mock_logger,
            no_magento_config=True,
            no_custom_config=True,
            dir_to_watch=self.source,
            use_systemd=True,
        )

    def test_wait_loop_sets_up_dbus_when_no_dbus_is_false(self):
        system_bus = self.set_up_patch("nginx_config_reloader.SYSTEM_BUS")
        interface_class = self.set_up_patch(
            "nginx_config_reloader.NginxConfigReloaderInterface"
        )
        thread_class = self.set_up_patch("nginx_config_reloader.threading.Thread")

        self._run_wait_loop_with_keyboard_interrupt(no_dbus=False)

        interface_class.assert_called_once_with(self.mock_handler)
        system_bus.publish_object.assert_called_once()
        system_bus.register_service.assert_called_once()
        thread_class.assert_called_once_with(
            target=nginx_config_reloader.dbus_event_loop
        )
        thread_class.return_value.start.assert_called_once()

    def test_wait_loop_skips_dbus_setup_when_no_dbus_is_true(self):
        system_bus = self.set_up_patch("nginx_config_reloader.SYSTEM_BUS")
        interface_class = self.set_up_patch(
            "nginx_config_reloader.NginxConfigReloaderInterface"
        )
        thread_class = self.set_up_patch("nginx_config_reloader.threading.Thread")

        self._run_wait_loop_with_keyboard_interrupt(no_dbus=True)

        interface_class.assert_not_called()
        system_bus.publish_object.assert_not_called()
        system_bus.register_service.assert_not_called()
        thread_class.assert_not_called()

    def test_wait_loop_waits_for_directory_to_appear(self):
        # Return False twice, then True on subsequent calls
        exists_mock = self.set_up_patch(
            "nginx_config_reloader.os.path.exists", side_effect=[False, False, True]
        )

        self._run_wait_loop_with_keyboard_interrupt()

        self.assertEqual(exists_mock.call_count, 3)
        # Should have called sleep(5) twice while waiting for directory
        sleep_calls = [c for c in self.time_sleep.call_args_list if c == call(5)]
        self.assertEqual(len(sleep_calls), 2)

    def test_wait_loop_logs_warning_when_directory_not_found(self):
        # Return False once, then True
        self.set_up_patch(
            "nginx_config_reloader.os.path.exists", side_effect=[False, True]
        )

        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_logger.warning.assert_any_call(
            f"Configuration dir {self.source} not found, waiting..."
        )

    def test_wait_loop_calls_reload_with_send_signal_false(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_handler.reload.assert_called_once_with(send_signal=False)

    def test_wait_loop_starts_observer(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_handler.start_observer.assert_called_once()

    def test_wait_loop_calls_after_loop_in_loop(self):
        loop_count = [0]

        def mock_after_loop(handler):
            loop_count[0] += 1
            if loop_count[0] >= 3:
                raise KeyboardInterrupt

        self.after_loop.side_effect = mock_after_loop

        wait_loop(
            logger=self.mock_logger,
            dir_to_watch=self.source,
            no_dbus=True,
        )

        self.assertEqual(self.after_loop.call_count, 3)
        self.after_loop.assert_called_with(self.mock_handler)

    def test_wait_loop_sleeps_one_second_between_after_loop_calls(self):
        loop_count = [0]

        def mock_sleep(seconds):
            if seconds == 1:
                loop_count[0] += 1
                if loop_count[0] >= 2:
                    raise KeyboardInterrupt

        self.time_sleep.side_effect = mock_sleep

        wait_loop(
            logger=self.mock_logger,
            dir_to_watch=self.source,
            no_dbus=True,
        )

        self.assertGreaterEqual(loop_count[0], 2)

    def test_wait_loop_handles_listen_target_terminated(self):
        call_count = [0]

        def mock_start_observer():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ListenTargetTerminated
            raise KeyboardInterrupt

        self.mock_handler.start_observer.side_effect = mock_start_observer

        wait_loop(
            logger=self.mock_logger,
            dir_to_watch=self.source,
            no_dbus=True,
        )

        # Should have tried to start observer twice
        self.assertEqual(self.mock_handler.start_observer.call_count, 2)
        # Should have stopped observer after ListenTargetTerminated
        self.mock_handler.stop_observer.assert_called()
        # Should have logged warning
        self.mock_logger.warning.assert_any_call(
            "Configuration dir lost, waiting for it to reappear"
        )

    def test_wait_loop_stops_observer_on_keyboard_interrupt(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_handler.stop_observer.assert_called_once()

    def test_wait_loop_logs_info_on_keyboard_interrupt(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_logger.info.assert_any_call("Shutting down observer.")

    def test_wait_loop_logs_info_when_starting_to_listen(self):
        self._run_wait_loop_with_keyboard_interrupt()

        self.mock_logger.info.assert_any_call(f"Listening for changes to {self.source}")

    def test_wait_loop_reloads_config_after_listen_target_terminated(self):
        call_count = [0]

        def mock_start_observer():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ListenTargetTerminated
            raise KeyboardInterrupt

        self.mock_handler.start_observer.side_effect = mock_start_observer

        wait_loop(
            logger=self.mock_logger,
            dir_to_watch=self.source,
            no_dbus=True,
        )

        # reload should be called twice - once initially and once after recovery
        self.assertEqual(self.mock_handler.reload.call_count, 2)

    def _run_wait_loop_with_keyboard_interrupt(self, **kwargs):
        """Helper to run wait_loop that exits on first after_loop call."""
        self.after_loop.side_effect = KeyboardInterrupt

        default_kwargs = {
            "dir_to_watch": self.source,
            "no_dbus": True,
        }
        default_kwargs.update(kwargs)

        wait_loop(logger=self.mock_logger, **default_kwargs)
