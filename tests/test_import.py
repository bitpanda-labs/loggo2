import builtins
import unittest
from importlib import reload


class TestWithoutGraypy(unittest.TestCase):
    def setUp(self):
        self.import_orig = builtins.__import__

        def mocked_import(name, *args):
            if name == "graypy":
                raise ImportError()
            return self.import_orig(name, *args)

        builtins.__import__ = mocked_import

    def tearDown(self):
        builtins.__import__ = self.import_orig
        import loggo

        reload(loggo.loggo)

    def tests_using_graypy(self):
        import loggo

        reload(loggo.loggo)
        loggo.Loggo()
        self.assertEqual(loggo.loggo.graypy, None)


if __name__ == "__main__":
    unittest.main()
