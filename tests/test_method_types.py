from unittest.mock import patch

from loggo2 import Loggo

loggo = Loggo(log_if_graylog_disabled=False)


@loggo
class AllMethodTypes:
    def __secret__(self):
        """a method that should never be logged."""
        return True

    def public(self):
        """normal method."""
        return True

    @classmethod
    def cl(cls):
        """class method."""
        return True

    @staticmethod
    def st():
        """static method."""
        return True

    @loggo
    def doubled(self):
        """Loggo twice, bad but shouldn't kill."""
        return True


all_method_types = AllMethodTypes()


class TestMethods:
    def test_methods_secret_not_called(self):
        with patch("logging.Logger.log") as logger:
            result = all_method_types.__secret__()
            assert result
            logger.assert_not_called()

    def test_methods_public_instance(self):
        with patch("logging.Logger.log") as logger:
            result = all_method_types.public()
            assert result
            assert logger.call_count == 2

    def test_methods_classmethod_instance(self):
        with patch("logging.Logger.log") as logger:
            result = all_method_types.cl()
            assert result
            assert logger.call_count == 2

    def test_methods_classmethod_class(self):
        with patch("logging.Logger.log") as logger:
            result = AllMethodTypes.cl()
            assert result
            assert logger.call_count == 2

    def test_methods_staticmethod_instance(self):
        with patch("logging.Logger.log") as logger:
            result = all_method_types.st()
            assert result
            assert logger.call_count == 2

    def test_methods_staticmethod_class(self):
        with patch("logging.Logger.log") as logger:
            result = AllMethodTypes.st()
            assert result
            assert logger.call_count == 2

    def test_methods_double_logged_instance(self):
        with patch("logging.Logger.log") as logger:
            result = all_method_types.doubled()
            assert result
            assert logger.call_count == 4
