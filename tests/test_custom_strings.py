import unittest
from unittest.mock import patch
from typing import Mapping, Optional
from loggo import Loggo as LoggoType

# without the Mapping annotation this fails, apparently due to mypy problems
strings = dict(called='Log string {call_signature}',
               returned='Log string for return',
               errored='Log string on exception')  # type: Mapping[str, str]

CustomStrings = LoggoType(log_if_graylog_disabled=False, **strings)

nocalled = dict(called=None,
                returned='Log string for return',
                returned_none='Returned none!',
                errored='Log string on exception')  # type: Mapping[str, Optional[str]]

CustomNoneString = LoggoType(log_if_graylog_disabled=False, **nocalled)


# custom message test data
@CustomStrings
def custom_success():
    return 1


@CustomStrings
def custom_none_user_returned():
    return


@CustomStrings
def custom_fail():
    raise ValueError('Boom!')


@CustomNoneString
def custom_none_default():
    return


class TestCustomStrings(unittest.TestCase):

    def test_pass(self):
        with patch('logging.Logger.log') as logger:
            n = custom_success()
            self.assertEqual(n, 1)
            self.assertEqual(logger.call_count, 2)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'Log string custom_success()')
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string for return')

    def test_user_default_none(self):
        with patch('logging.Logger.log') as logger:
            n = custom_success()
            self.assertEqual(n, 1)
            self.assertEqual(logger.call_count, 2)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'Log string custom_success()')
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string for return')

    def custom_none_default(self):
        with patch('logging.Logger.log') as logger:
            n = custom_success()
            self.assertEqual(n, 1)
            self.assertEqual(logger.call_count, 1)
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string for return')

    def test_fail(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError):
                custom_fail()
            self.assertEqual(logger.call_count, 2)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'Log string custom_fail()')
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string on exception')
            self.assertEqual(alert, 20)


if __name__ == '__main__':
    unittest.main()
