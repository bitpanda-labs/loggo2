import os
import unittest
from unittest.mock import mock_open, patch, ANY, Mock
import logging

from loggo import Loggo as LoggoType

test_setup = dict(facility='LOGGO_TEST',
                  ip=None,
                  port=None,
                  do_print=True,
                  do_write=True,
                  private_data=['mnemonic', 'priv'])
Loggo = LoggoType(test_setup)


@Loggo
def function_with_private_arg(priv, acceptable=True):
    return acceptable


@Loggo
def function_with_private_kwarg(number, a_float=0.0, mnemonic=None):
    return number * a_float


# we can also use loggo.__call__
@Loggo
def may_or_may_not_error_test(first, other, kwargs=None):
    """
    A function that may or may not error
    """
    if not kwargs:
        raise ValueError('no good')
    else:
        return (first + other, kwargs)


@Loggo
def aaa():
    return 'this'


@Loggo
class AllMethodTypes:

    def __secret__(self):
        """a method that should never be logged"""
        return True

    def public(self):
        """normal method"""
        return True

    @classmethod
    def cl(cls):
        """class method"""
        return True

    @staticmethod
    def st():
        """static method"""
        return True

    @Loggo
    def doubled(self):
        """Loggo twice, bad but shouldn't kill"""
        return True


all_method_types = AllMethodTypes()


@Loggo
class DummyClass:
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
        return number * number

    def optional_provided(self, kw=None, **kwargs):
        if kw:
            raise ValueError('Should not have provided!')

    @Loggo.ignore
    def hopefully_ignored(self, n):
        return n**n

    @Loggo.errors
    def hopefully_only_errors(self, n):
        raise ValueError('Bam!')


class DummyClass2:
    def add(self, a, b, c):
        return a + b + c


@Loggo.errors
def first_test_func(number):
    raise ValueError('Broken!')


@Loggo.errors
def second_test_func(number):
    raise ValueError('Broken!')


@Loggo
def test_func3(number):
    raise ValueError('Broken!')


@Loggo
def test_inner():
    try:
        test_func3(1)
    except Exception:
        pass
    return 1


within = dict(lst=list(), ok=dict(ok=dict(priv='secret')))
beyond = dict(lst=list(), ok=dict(ok=dict(ok=dict(ok=dict(ok=dict(ok=dict(priv='allowed')))))))


@Loggo
def test_func_with_recursive_data_beyond(data):
    pass


@Loggo
def test_func_with_recursive_data_within(data):
    pass


dummy = DummyClass()

# events test data
@Loggo.events(called='Log string for method call',
              returned='Log string for return')
def event_success():
    return 1


@Loggo.events(called='Log string for method call',
              errored='Log string on exception',
              error_level=50)
def event_fail():
    raise ValueError('Boom!')


class TestDecoration(unittest.TestCase):

    def test_inheritance_signature_change(self):
        d2 = DummyClass2()
        self.assertEqual(6, d2.add(1, 2, 3))

    def test_errors_on_func(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError):
                first_test_func(5)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertEqual(logged_msg, '*Errored during first_test_func(number=5) with ValueError "Broken!"')

    def test_log_errors(self):
        with patch('logging.Logger.log'):
            with self.assertRaises(ValueError):
                with Loggo.log_errors():
                    second_test_func(5)

    def test_one(self):
        """
        Check that an error is thrown for a func
        """
        with patch('logging.Logger.log') as logger:
            with self.assertRaisesRegex(ValueError, 'no good'):
                may_or_may_not_error_test('astadh', 1331)
            (alert, logged_msg), extras = logger.call_args
            self.assertEqual(alert, 20)
            expected_msg = ('*Errored during may_or_may_not_error_test(first=\'astadh\', other=1331) '
                            'with ValueError "no good"')
            self.assertEqual(logged_msg, expected_msg)

    def test_logme_0(self):
        """
        Test correct result
        """
        with patch('logging.Logger.log') as logger:
            res, kwa = may_or_may_not_error_test(2534, 2466, kwargs=True)
            self.assertEqual(res, 5000)
            self.assertTrue(kwa)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, '*Called may_or_may_not_error_test(first=2534, other=2466, kwargs=True)')
            (alert, logged_msg), extras = logger.call_args_list[-1]
            expected_msg = ('*Returned from may_or_may_not_error_test(first=2534, other=2466, '
                            'kwargs=True) with tuple ((5000, True))')
            self.assertEqual(logged_msg, expected_msg)

    def test_logme_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.add(1, 2)
            self.assertEqual(result, 3)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, '*Called DummyClass.add(a=1, b=2)')
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertEqual('*Returned from DummyClass.add(a=1, b=2) with int (3)', logged_msg)

    def test_everything_0(self):
        with patch('logging.Logger.log') as logger:
            dummy.add_and_maybe_subtract(15, 10, 5)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, '*Called DummyClass.add_and_maybe_subtract(a=15, b=10, c=5)')
            (alert, logged_msg), extras = logger.call_args_list[-1]
            expected_msg = '*Returned from DummyClass.add_and_maybe_subtract(a=15, b=10, c=5) with int (20)'
            self.assertEqual(expected_msg, logged_msg)

    def test_everything_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.static_method(10)
            self.assertEqual(result, 100)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertEqual('*Returned from DummyClass.static_method(number=10) with int (100)', logged_msg)

    def test_everything_3(self):
        with patch('logging.Logger.log') as logger:
            dummy.optional_provided()
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, '*Called DummyClass.optional_provided()')
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned None' in logged_msg)

    def test_everything_4(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaisesRegex(ValueError, 'Should not have provided!'):
                result = dummy.optional_provided(kw='Something')
                self.assertIsNone(result)
                (alert, logged_msg), extras = logger.call_args_list[0]
                self.assertTrue('0 args, 1 kwargs' in logged_msg)
                (alert, logged_msg), extras = logger.call_args_list[-1]
                self.assertTrue('Errored with ValueError' in logged_msg, logged_msg)

    def test_loggo_ignore(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.hopefully_ignored(5)
            self.assertEqual(result, 5**5)
            logger.assert_not_called()

    def test_loggo_errors(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError):
                dummy.hopefully_only_errors(5)
            (alert, logged_msg), extras = logger.call_args
            self.assertEqual('*Errored during DummyClass.hopefully_only_errors(n=5) with ValueError "Bam!"', logged_msg)

    def test_private_keyword_removal(self):
        with patch('logging.Logger.log') as logger:
            mnem = 'every good boy deserves fruit'
            res = function_with_private_kwarg(10, a_float=5.5, mnemonic=mnem)
            self.assertEqual(res, 10 * 5.5)
            (_alert, _logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(extras['extra']['mnemonic'], "'[PRIVATE_DATA]'")

    def test_private_positional_removal(self):
        with patch('logging.Logger.log') as logger:
            res = function_with_private_arg('should not log', False)
            self.assertFalse(res)
            (_alert, _logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(extras['extra']['priv'], "'[PRIVATE_DATA]'")

    def test_private_beyond(self):
        with patch('logging.Logger.log') as logger:
            test_func_with_recursive_data_beyond(beyond)
            (_alert, _logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('allowed' in extras['extra']['data'])

    def test_private_within(self):
        with patch('logging.Logger.log') as logger:
            test_func_with_recursive_data_within(within)
            (_alert, _logged_msg), extras = logger.call_args_list[0]
            self.assertFalse('secret' in extras['extra']['data'])


class NoRepr:
    """
    An object that really hates being repr'd
    """
    def __repr__(self):
        raise Exception('No.')


class TestLog(unittest.TestCase):

    def setUp(self):
        self.log_msg = 'This is a message that can be used when the content does not matter.'
        self.log_data = {'This is': 'log data', 'that can be': 'used when the content does not matter'}

        self.test_setup = dict(facility='LOG_TEST', ip=None, port=None, do_print=True, do_write=True)
        self.loggo = LoggoType(self.test_setup)
        self.log = self.loggo.log

    def test_protected_keys(self):
        """
        Check that a protected name "name" is converted to "protected_name",
        in order to stop error in logger later
        """
        with patch('logging.Logger.log') as mock_log:
            self.log(logging.INFO, 'fine', dict(name='bad', other='good'))
            (_alert, _msg), kwargs = mock_log.call_args
            self.assertEqual(kwargs['extra']['protected_name'], 'bad')
            self.assertEqual(kwargs['extra']['other'], 'good')

    def test_can_log(self):
        with patch('logging.Logger.log') as logger:
            level_num = 50
            msg = 'Test message here'
            result = self.log(level_num, msg, dict(extra='data'))
            self.assertIsNone(result)
            (alert, logged_msg), extras = logger.call_args
            self.assertEqual(alert, level_num)
            self.assertEqual(msg, logged_msg)
            self.assertEqual(extras['extra']['extra'], 'data')

    def test_write_to_file(self):
        """
        Check that we can write logs to file
        """
        mock = mock_open()
        with patch('builtins.open', mock):
            self.log(logging.INFO, 'An entry in our log')
            mock.assert_called_with(Loggo.logfile, 'a')
            self.assertTrue(os.path.isfile(Loggo.logfile))

    def test_int_truncation(self):
        """
        Log was failing to truncate big integers. Check that this is now fixed.
        """
        with patch('logging.Logger.log') as mock_log:
            msg = 'This is simply a test of the int truncation inside the log.'
            large_number = 10**300001
            log_data = dict(key=large_number)
            self.log(logging.INFO, msg, log_data)
            mock_log.assert_called_with(20, msg, extra=ANY)
            logger_was_passed = mock_log.call_args[1]['extra']['key']
            # 7500 here is the default self.truncation for loggo
            done_by_hand = str(large_number)[:7500] + '...'
            self.assertEqual(logger_was_passed, done_by_hand)

    def test_string_truncation_fail(self):
        """
        If something cannot be cast to string, we need to know about it
        """
        with patch('logging.Logger.log') as mock_log:
            no_string_rep = NoRepr()
            result = self.loggo._force_string_and_truncate(no_string_rep, 7500)
            self.assertEqual(result, '<<Unstringable input>>')
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual('Object could not be cast to string', msg)

    def test_fail_to_add_entry(self):
        with patch('logging.Logger.log') as mock_log:
            no_string_rep = NoRepr()
            sample = dict(fine=123, not_fine=no_string_rep)
            result = self.loggo.sanitise(sample)
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual('Object could not be cast to string', msg)
            self.assertEqual(result['not_fine'], '<<Unstringable input>>')
            self.assertEqual(result['fine'], '123')

    def test_log_fail(self):
        with patch('logging.Logger.log') as mock_log:
            mock_log.side_effect = Exception('Really dead.')
            self.loggo.raise_logging_errors = True
            with self.assertRaises(Exception):
                self.loggo.log(logging.INFO, 'Anything')

    def test_loggo_pause(self):
        with patch('logging.Logger.log') as mock_log:
            with Loggo.pause():
                Loggo.log(logging.INFO, 'test')
            mock_log.assert_not_called()
            Loggo.log(logging.INFO, 'test')
            mock_log.assert_called()

    def test_loggo_pause_error(self):
        with patch('logging.Logger.log') as logger:
            with Loggo.pause():
                with self.assertRaises(ValueError):
                    may_or_may_not_error_test('one', 'two')
            (alert, msg), kwargs = logger.call_args
            expected_msg = ('*Errored during may_or_may_not_error_test(first=\'one\', '
                            'other=\'two\') with ValueError "no good"')
            self.assertEqual(expected_msg, msg)
            logger.assert_called_once()
            logger.reset()
            with self.assertRaises(ValueError):
                may_or_may_not_error_test('one', 'two')
                self.assertEqual(len(logger.call_args_list), 2)

    def test_loggo_error_suppressed(self):
        with patch('logging.Logger.log') as logger:
            with Loggo.pause(allow_errors=False):
                with self.assertRaises(ValueError):
                    may_or_may_not_error_test('one', 'two')
            logger.assert_not_called()
            Loggo.log(logging.INFO, 'test')
            logger.assert_called_once()

    def test_see_below(self):
        msg = 'testing only'
        s = self.loggo._build_string(msg, 50)
        self.assertTrue('-- see below:' not in s)

    def test_compat(self):
        test = 'a string'
        with patch('loggo.Loggo.log') as logger:
            Loggo.log(logging.INFO, test, None)
        args = logger.call_args
        self.assertIsInstance(args[0][0], int)
        self.assertEqual(args[0][1], test)
        self.assertIsNone(args[0][2])
        with patch('logging.Logger.log') as logger:
            Loggo.log(logging.INFO, test)
        (alert, msg), kwargs = logger.call_args
        self.assertEqual(test, msg)

    def test_bad_args(self):

        @Loggo
        def dummy(needed):
            return needed
        with self.assertRaises(TypeError):
            dummy()

    def test_debug(self):
        with patch('loggo.Loggo.log') as logger:
            self.loggo.debug(self.log_msg, self.log_data)
            logger.assert_called_with(logging.DEBUG, self.log_msg, self.log_data)

    def test_info(self):
        with patch('loggo.Loggo.log') as logger:
            self.loggo.info(self.log_msg, self.log_data)
            logger.assert_called_with(logging.INFO, self.log_msg, self.log_data)

    def test_warning(self):
        with patch('loggo.Loggo.log') as logger:
            self.loggo.warning(self.log_msg, self.log_data)
            logger.assert_called_with(logging.WARNING, self.log_msg, self.log_data)

    def test_error(self):
        with patch('loggo.Loggo.log') as logger:
            self.loggo.error(self.log_msg, self.log_data)
            logger.assert_called_with(logging.ERROR, self.log_msg, self.log_data)

    def test_critical(self):
        with patch('loggo.Loggo.log') as logger:
            self.loggo.critical(self.log_msg, self.log_data)
            logger.assert_called_with(logging.CRITICAL, self.log_msg, self.log_data)

    def test_listen_to(self):
        sub_loggo_facility = 'a sub logger'
        sub_loggo = LoggoType({'facility': sub_loggo_facility})
        self.loggo.listen_to(sub_loggo_facility)

        self.loggo.log = Mock()
        log_args = logging.WARNING, 'The parent logger should log this message after sublogger logs it'
        sub_loggo.log(*log_args)

        self.loggo.log.assert_called_with(*log_args, ANY)


class TestMethods(unittest.TestCase):

    def test_methods_secret_not_called(self):
        with patch('logging.Logger.log') as logger:
            result = all_method_types.__secret__()
            self.assertTrue(result)
            logger.assert_not_called()

    def test_methods_public_instance(self):
        with patch('logging.Logger.log') as logger:
            result = all_method_types.public()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 2)

    def test_methods_classmethod_instance(self):
        with patch('logging.Logger.log') as logger:
            result = all_method_types.cl()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 2)

    def test_methods_classmethod_class(self):
        with patch('logging.Logger.log') as logger:
            result = AllMethodTypes.cl()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 2)

    def test_methods_staticmethod_instance(self):
        with patch('logging.Logger.log') as logger:
            result = all_method_types.st()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 2)

    def test_methods_staticmethod_class(self):
        with patch('logging.Logger.log') as logger:
            result = AllMethodTypes.st()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 2)

    def test_methods_double_logged_instance(self):
        with patch('logging.Logger.log') as logger:
            result = all_method_types.doubled()
            self.assertTrue(result)
            self.assertEqual(logger.call_count, 4)


class TestEvents(unittest.TestCase):

    def test_events_pass(self):
        with patch('logging.Logger.log') as logger:
            n = event_success()
            self.assertEqual(n, 1)
            self.assertEqual(logger.call_count, 2)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'Log string for method call')
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string for return')

    def test_events_fail(self):
        with patch('logging.Logger.log') as logger:
            n = event_fail()
            self.assertIsNone(n)
            self.assertEqual(logger.call_count, 2)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertEqual(logged_msg, 'Log string for method call')
            (alert, logged_msg), extras = logger.call_args_list[1]
            self.assertEqual(logged_msg, 'Log string on exception')
            self.assertEqual(alert, 50)


if __name__ == '__main__':
    unittest.main()
