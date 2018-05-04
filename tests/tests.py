import unittest
from loggo import Loggo
test_setup = dict(facility='DKTEST', ip='192.168.1.11', port=12206, do_print=True, do_write=True)
Loggo = Loggo(test_setup)
from unittest.mock import patch

@Loggo.logme
def test(first, other, kwargs=None):
    """
    A function that may or may not error
    """
    if not kwargs:
        raise ValueError('no good')
    else:
        return (first+other, kwargs)

@Loggo.logme
def aaa():
    return 'this'

@Loggo.everything
class DummyClass(object):
    """
    A class with regular methods, static methods and errors
    """

    def add(self, a, b):
        return a + b

    def add_and_maybe_subtract(self, a, b, c=False):
        added = a + b
        if c:
            return added - c
        return added

    @staticmethod
    def static_method(number):
        return number*number

    def optional_provided(self, kw=None, **kwargs):
        if kw:
            raise ValueError('Should not have provided!')

dummy = DummyClass()

class TestLoggo(unittest.TestCase):

    def test_one(self):
        """
        Check that an error is thrown for a func
        """
        return
        with patch('logging.Logger.log') as logger:
            with self.assertRaisesRegex(ValueError, 'no good'):
                result = test('astadh', 1331)
                (alert, logged_msg), extras = logger.call_args

    def test_logme_0(self):
        """
        Test correct result
        """
        with patch('logging.Logger.log') as logger:
            res, kwa = test(2534, 2466, kwargs=True)
            self.assertEqual(res, 5000)
            self.assertTrue(kwa)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('2 args, 1 kwargs' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a tuple' in logged_msg)

    def test_logme_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.add(1, 2)
            self.assertEqual(result, 3)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('2 args' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg)

    def test_exhaustive_0(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.add_and_maybe_subtract(15, 10, 5)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('3 args' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg)

    def test_exhaustive_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.static_method(10)
            self.assertEqual(result, 100)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('1 args' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg)

    def test_exhaustive_3(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.optional_provided()
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('0 args, 0 kwargs' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a NoneType' in logged_msg)

    def test_exhaustive_4(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaisesRegex(ValueError, 'Should not have provided!'):
                result = dummy.optional_provided(kw='Something')
                self.assertIsNone(result)
                (alert, logged_msg), extras = logger.call_args_list[0]
                self.assertTrue('0 args, 1 kwargs' in logged_msg)
                (alert, logged_msg), extras = logger.call_args_list[-1]
                self.assertTrue('Errored with ValueError' in logged_msg)


if __name__ == '__main__':
    unittest.main()
