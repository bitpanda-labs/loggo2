import unittest
import builtins


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

    def tests_using_graypy(self):
        from loggo.loggo import graypy

        self.assertEqual(graypy, None)


if __name__ == "__main__":
    unittest.main()
