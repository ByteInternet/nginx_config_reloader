import sys
import unittest
from unittest.mock import Mock, mock_open, patch


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

    def set_up_mock_open(self, read_value=""):
        py_version = sys.version_info
        python2 = py_version < (3, 0)
        if python2:
            return self.set_up_patch(
                "__builtin__.open", mock_open(read_data=read_value)
            )
        else:
            return self.set_up_patch("builtins.open", mock_open(read_data=read_value))
