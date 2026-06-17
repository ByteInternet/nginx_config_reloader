import sys

import pytest

requires_linux = pytest.mark.skipif(sys.platform != "linux", reason="Linux only")
