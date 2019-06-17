import sys
import unittest


class TestWithoutGraypy(unittest.TestCase):
    def setUp(self):
        self._temp_graypy = None
        if sys.modules.get("graypy"):
            self._temp_graypy = sys.modules["graypy"]
        sys.modules["graypy"] = None

    def tearDown(self):
        if self._temp_graypy:
            sys.modules["graypy"] = self._temp_graypy
        else:
            del sys.modules["graypy"]

    def tests_using_graypy(self):
        flag = False
        try:
            import loggo
        except ImportError:
            flag = True
        self.assertTrue(flag)


class TestWithGraypy(unittest.TestCase):
    def tests_using_graypy(self):
        flag = False
        try:
            import loggo
        except ImportError:
            flag = True
        self.assertFalse(flag)
