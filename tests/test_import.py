import unittest
import builtins
from importlib import reload

import_orig = builtins.__import__


def mocked_import(name, *args):
    if name == "graypy":
        raise ImportError()
    return import_orig(name, *args)


builtins.__import__ = mocked_import


class TestWithoutGraypy(unittest.TestCase):
    def tearDown(self):
        builtins.__import__ = import_orig
        import loggo

        reload(loggo.loggo)

    def tests_using_graypy(self):
        import loggo

        reload(loggo.loggo)
        loggo.Loggo()
        self.assertEqual(loggo.loggo.graypy, None)


if __name__ == "__main__":
    unittest.main()
