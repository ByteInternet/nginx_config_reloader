import os
import shutil
from tempfile import mkdtemp, NamedTemporaryFile
import unittest
import mock
import pyinotify
import nginx_config_reloader


class TestInotifyCallbacks(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch('nginx_config_reloader.NginxConfigReloader.handle_event')
        self.addCleanup(patcher.stop)
        self.handle_event = patcher.start()

        self.dir = mkdtemp()
        with open(os.path.join(self.dir, 'existing_file'), 'w') as f:
            f.write('blablabla')

        wm = pyinotify.WatchManager()
        handler = nginx_config_reloader.NginxConfigReloader()
        self.notifier = pyinotify.Notifier(wm, default_proc_fun=handler)
        wm.add_watch(self.dir, pyinotify.ALL_EVENTS)

    def tearDown(self):
        self.notifier.stop()
        shutil.rmtree(self.dir, ignore_errors=True)

    def _process_events(self):
        while self.notifier.check_events(0):
            self.notifier.read_events()
            self.notifier.process_events()

    def test_that_handle_event_is_called_when_new_file_is_created(self):
        with open(os.path.join(self.dir, 'testfile'), 'w') as f:
            f.write('blablabla')

        self._process_events()

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_new_dir_is_created(self):
        mkdtemp(dir=self.dir)
        self._process_events()

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_removed(self):
        os.remove(os.path.join(self.dir, 'existing_file'))

        self._process_events()

        self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_moved_in(self):
        with NamedTemporaryFile(delete=False) as f:
            os.rename(f.name, os.path.join(self.dir, 'newfile'))

            self._process_events()

            self.assertEqual(len(self.handle_event.mock_calls), 1)

    def test_that_handle_event_is_called_when_a_file_is_moved_out(self):
        destdir = mkdtemp()
        os.rename(os.path.join(self.dir, 'existing_file'), os.path.join(destdir, 'existing_file'))

        self._process_events()

        self.assertEqual(len(self.handle_event.mock_calls), 1)

        shutil.rmtree(destdir)

    def test_that_handle_event_is_called_when_a_file_is_renamed(self):
        os.rename(os.path.join(self.dir, 'existing_file'), os.path.join(self.dir, 'new_name'))

        self._process_events()

        self.assertGreaterEqual(len(self.handle_event.mock_calls), 1)

    def test_that_listen_target_terminated_is_raised_if_dir_is_renamed(self):
        destdir = mkdtemp()
        os.rename(self.dir, destdir)

        with self.assertRaises(nginx_config_reloader.ListenTargetTerminated):
            self._process_events()

        shutil.rmtree(destdir)

    def test_that_listen_target_terminated_is_raised_if_dir_is_removed(self):
        shutil.rmtree(self.dir)

        with self.assertRaises(nginx_config_reloader.ListenTargetTerminated):
            self._process_events()


class TestInotifyRecursiveCallbacks(TestInotifyCallbacks):
    # Run all callback tests on a subdir
    def setUp(self):
        patcher = mock.patch('nginx_config_reloader.NginxConfigReloader.handle_event')
        self.addCleanup(patcher.stop)
        self.handle_event = patcher.start()

        self.rootdir = mkdtemp()
        self.dir = mkdtemp(dir=self.rootdir)
        with open(os.path.join(self.dir, 'existing_file'), 'w') as f:
            f.write('blablabla')

        wm = pyinotify.WatchManager()
        handler = nginx_config_reloader.NginxConfigReloader()
        self.notifier = pyinotify.Notifier(wm, default_proc_fun=handler)
        wm.add_watch(self.rootdir, pyinotify.ALL_EVENTS, rec=True)

    def tearDown(self):
        self.notifier.stop()
        shutil.rmtree(self.rootdir, ignore_errors=True)
