from unittest.mock import patch

from loggo import Loggo

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


class Base:
    def f(self):
        return 1

    def g(self):
        return 2


@loggo
class Derived(Base):
    def g(self):
        return 3

    def h(self):
        return 4


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

    def test_inheritance_decorating(self):
        with patch("logging.Logger.log") as logger:
            derived = Derived()
            assert derived.f() == 1
            assert logger.call_count == 0
            assert derived.g() == 3
            assert logger.call_count == 2
            assert derived.h() == 4
            assert logger.call_count == 4
