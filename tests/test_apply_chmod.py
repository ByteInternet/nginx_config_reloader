import os
import tempfile

from nginx_config_reloader import as_unprivileged_user
from nginx_config_reloader.utils import apply_chmod
from tests.testcase import TestCase


class TestApplyChmod(TestCase):
    def setUp(self):
        self.check_call = self.set_up_patch("subprocess.check_call")
        _, self.path = tempfile.mkstemp()

    def tearDown(self):
        try:
            os.unlink(self.path)
        except OSError:
            pass

    def test_apply_chmod_changes_mode(self):
        os.chmod(self.path, 0o600)

        apply_chmod(self.path, "644", preexec_fn=as_unprivileged_user)

        self.check_call.assert_called_once_with(
            ["chmod", "644", self.path], preexec_fn=as_unprivileged_user
        )

    def test_apply_chmod_skips_existing_mode(self):
        os.chmod(self.path, 0o644)

        apply_chmod(self.path, "644", preexec_fn=as_unprivileged_user)

        self.check_call.assert_not_called()

    def test_apply_chmod_accepts_int_mode(self):
        os.chmod(self.path, 0o600)

        apply_chmod(self.path, 0o644, preexec_fn=as_unprivileged_user)

        self.check_call.assert_called_once_with(
            ["chmod", "644", self.path], preexec_fn=as_unprivileged_user
        )
