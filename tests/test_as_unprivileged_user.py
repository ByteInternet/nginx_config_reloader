from nginx_config_reloader import (
    UNPRIVILEGED_GID,
    UNPRIVILEGED_UID,
    as_unprivileged_user,
)
from tests.testcase import TestCase


class TestAsUnprivilegedUser(TestCase):
    def setUp(self):
        self.setgid = self.set_up_patch("nginx_config_reloader.os.setgid")
        self.setuid = self.set_up_patch("nginx_config_reloader.os.setuid")

    def test_as_unprivileged_user_sets_gid_to_unprivileged_gid(self):
        as_unprivileged_user()

        self.setgid.assert_called_once_with(UNPRIVILEGED_GID)

    def test_as_unprivileged_user_sets_uid_to_unprivileged_uid(self):
        as_unprivileged_user()

        self.setuid.assert_called_once_with(UNPRIVILEGED_UID)
