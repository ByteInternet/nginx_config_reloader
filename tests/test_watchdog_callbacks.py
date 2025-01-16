import os
import shutil
import unittest
from tempfile import NamedTemporaryFile, mkdtemp

import mock
from watchdog.events import DirCreatedEvent, FileDeletedEvent, FileMovedEvent

import nginx_config_reloader


class TestWatchdogCallbacks(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch("nginx_config_reloader.NginxConfigReloader.handle_event")
        self.addCleanup(patcher.stop)
        self.handle_event = patcher.start()

        self.dir = mkdtemp()
        with open(os.path.join(self.dir, "existing_file"), "w") as f:
            f.write("blablabla")

        self.observer = mock.Mock()
        self.handler = nginx_config_reloader.NginxConfigReloader(dir_to_watch=self.dir)
        self.handler.observer = self.observer

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_new_dir_is_created(self):
        event = DirCreatedEvent(os.path.join(self.dir, "testdir"))
        self.handler.on_created(event)

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_removed(self):
        event = FileDeletedEvent(os.path.join(self.dir, "existing_file"))
        self.handler.on_deleted(event)

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_moved_in(self):
        with NamedTemporaryFile(delete=False) as f:
            event = FileMovedEvent(f.name, os.path.join(self.dir, "newfile"))
            self.handler.on_moved(event)

            self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_moved_out(self):
        destdir = mkdtemp()
        event = FileMovedEvent(
            os.path.join(self.dir, "existing_file"),
            os.path.join(destdir, "existing_file"),
        )
        self.handler.on_moved(event)

        self.assertEqual(len(self.handle_event.mock_calls), 1)

        shutil.rmtree(destdir)

    def test_that_handle_event_is_called_when_a_file_is_renamed(self):
        event = FileMovedEvent(
            os.path.join(self.dir, "existing_file"),
            os.path.join(self.dir, "new_name"),
        )
        self.handler.on_moved(event)

        self.assertGreaterEqual(len(self.handle_event.mock_calls), 1)


class TestWatchdogRecursiveCallbacks(TestWatchdogCallbacks):
    # Run all callback tests on a subdir
    def setUp(self):
        patcher = mock.patch("nginx_config_reloader.NginxConfigReloader.handle_event")
        self.addCleanup(patcher.stop)
        self.handle_event = patcher.start()

        self.rootdir = mkdtemp()
        self.dir = mkdtemp(dir=self.rootdir)
        with open(os.path.join(self.dir, "existing_file"), "w") as f:
            f.write("blablabla")

        self.observer = mock.Mock()
        self.handler = nginx_config_reloader.NginxConfigReloader(dir_to_watch=self.dir)
        self.handler.observer = self.observer

    def tearDown(self):
        shutil.rmtree(self.rootdir, ignore_errors=True)
