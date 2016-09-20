import unittest
from mock import patch, Mock


class TestCase(unittest.TestCase):
    def set_up_patch(self, patch_target, mock_target=None, **kwargs):
        patcher = patch(patch_target, mock_target or Mock(**kwargs))
        self.addCleanup(patcher.stop)
        return patcher.start()

    def set_up_context_manager_patch(self, topatch, themock=None, **kwargs):
        patcher = self.set_up_patch(topatch, themock=themock, **kwargs)
        patcher.return_value.__exit__ = lambda a, b, c, d: None
        patcher.return_value.__enter__ = lambda x: None
        return patcher
