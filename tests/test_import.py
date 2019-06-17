import unittest
import builtins
from typing import Mapping, Any
from importlib import reload

import_orig = builtins.__import__


def mocked_import(name, *args):
    if name == "graypy":
        raise ImportError()
    return import_orig(name, *args)


builtins.__import__ = mocked_import

test_setup = dict(
    do_write=True, log_if_graylog_disabled=False, private_data={"mnemonic", "priv"}
)  # type: Mapping[str, Any]


class TestWithoutGraypy(unittest.TestCase):
    def tearDown(self):
        builtins.__import__ = import_orig

    def tests_using_graypy(self):
        import loggo

        reload(loggo.loggo)
        l = loggo.Loggo(**test_setup)
        self.assertEqual(loggo.loggo.graypy, None)


if __name__ == "__main__":
    unittest.main()
