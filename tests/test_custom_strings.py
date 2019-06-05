import unittest
from unittest.mock import patch
from typing import Mapping, Optional
from loggo import Loggo

# without the Mapping annotation this fails, apparently due to mypy problems
strings = dict(called='Log string {call_signature}',
               returned='Log string for return',
               errored='Log string on exception')  # type: Mapping[str, str]

custom_strings = Loggo(log_if_graylog_disabled=False, **strings)

nocalled = dict(called=None,
                returned='Log string for return',
                returned_none='Returned none!',
                errored='Log string on exception')  # type: Mapping[str, Optional[str]]

no_return = dict(called='called fine',
                 returned=None,
                 returned_none=None)  # type: Mapping[str, Optional[str]]

custom_none_string = Loggo(log_if_graylog_disabled=False, **nocalled)

custom_no_return = Loggo(log_if_graylog_disabled=False, **no_return)


# custom message test data
@custom_strings
def custom_success():
    return 1


@custom_strings
def custom_none_user_returned():
    return


@custom_strings
def custom_fail():
    raise ValueError('Boom!')


@custom_none_string
def custom_none_default():
    return


@custom_no_return
def custom_without_return():
    return 1


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

    def test_no_return_string(self):
        with patch('logging.Logger.log') as logger:
            n = custom_without_return()
            self.assertEqual(n, 1)
            self.assertEqual(logger.call_count, 1)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'called fine')


if __name__ == '__main__':
    unittest.main()
