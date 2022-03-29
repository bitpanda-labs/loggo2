import builtins
from importlib import reload


class TestWithoutGraypy:
    def setup_method(self):
        self.import_orig = builtins.__import__

        def mocked_import(name, *args):
            if name == "graypy":
                raise ImportError()
            return self.import_orig(name, *args)

        builtins.__import__ = mocked_import

    def teardown_method(self):
        builtins.__import__ = self.import_orig
        import loggo2

        reload(loggo2._loggo2)

    def tests_using_graypy(self):
        import loggo2

        reload(loggo2._loggo2)
        loggo2.Loggo()
        assert loggo2._loggo2.graypy is None
