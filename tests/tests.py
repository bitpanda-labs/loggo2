import os
import unittest
from unittest.mock import mock_open, patch, ANY, Mock

from loggo import Loggo as a_loggo

test_setup = dict(facility='LOGGO_TEST', ip=None, port=None, do_print=True, do_write=True)
Loggo = a_loggo(test_setup)

@Loggo.logme
def function_with_private_arg(priv, acceptable=True):
    return acceptable

@Loggo.logme
def function_with_private_kwarg(number, a_float=0.0, mnemonic=None):
    return number * a_float

# we can also use loggo.__call__
@Loggo
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

    @Loggo.ignore
    def hopefully_ignored(self, n):
        return n**n

    @Loggo.errors
    def hopefully_only_errors(self, n):
        raise ValueError('Bam!')

class DummyClass2(object):
    def add(self, a, b, c):
        return a + b + c

@Loggo.errors
def test_func(number):
    raise ValueError('Broken!')

def test_func2(number):
    raise ValueError('Broken!')

@Loggo.logme
def test_func3(number):
    raise ValueError('Broken!')

@Loggo.logme
def test_inner():
    try:
        test_func3(1)
    except Exception as error:
        pass
    return 1

dummy = DummyClass()

class TestDecoration(unittest.TestCase):

    def test_inheritance_signature_change(self):
        d2 = DummyClass2()
        self.assertEqual(6, d2.add(1,2,3))

    def test_errors_on_func(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError):
                test_func(5)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('*Errored with ValueError' in logged_msg)

    def test_log_errors(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError) as error:
                with Loggo.log_errors() as loggin:
                    test_func2(5)
            #(alert, logged_msg), extras = logger.call_args_list[-1]
            #self.assertTrue('*Errored with ValueError' in logged_msg)

    def test_one(self):
        """
        Check that an error is thrown for a func
        """
        with patch('logging.Logger.log') as logger:
            with self.assertRaisesRegex(ValueError, 'no good'):
                result = test('astadh', 1331)
            (alert, logged_msg), extras = logger.call_args
            self.assertEqual(alert, 40)
            self.assertTrue('Errored with ValueError "no good"' in logged_msg, logged_msg)

    def test_logme_0(self):
        """
        Test correct result
        """
        with patch('logging.Logger.log') as logger:
            res, kwa = test(2534, 2466, kwargs=True)
            self.assertEqual(res, 5000)
            self.assertTrue(kwa)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('2 args, 1 kwargs' in logged_msg, logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a tuple' in logged_msg, logged_msg)

    def test_logme_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.add(1, 2)
            self.assertEqual(result, 3)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('2 args' in logged_msg, logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg, logged_msg)

    def test_everything_0(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.add_and_maybe_subtract(15, 10, 5)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('2 args' in logged_msg, logged_msg)
            self.assertTrue('1 kwargs' in logged_msg, logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg, logged_msg)

    def test_everything_1(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.static_method(10)
            self.assertEqual(result, 100)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('1 args' in logged_msg)
            (alert, logged_msg), extras = logger.call_args_list[-1]
            self.assertTrue('Returned a int' in logged_msg)

    def test_everything_3(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.optional_provided()
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('0 args, 0 kwargs' in logged_msg, logged_msg)
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
                self.assertTrue('Errored with ValueError' in logged_msg)

    def test_loggo_ignore(self):
        with patch('logging.Logger.log') as logger:
            result = dummy.hopefully_ignored(5)
            self.assertEqual(result, 5**5)
            logger.assert_not_called()

    def test_loggo_errors(self):
        with patch('logging.Logger.log') as logger:
            with self.assertRaises(ValueError):
                result = dummy.hopefully_only_errors(5)
            (alert, logged_msg), extras = logger.call_args
            self.assertTrue('Errored with ValueError' in logged_msg)

    def test_private_keyword_removal(self):
        with patch('logging.Logger.log') as logger:
            mnem = 'every good boy deserves fruit'
            res = function_with_private_kwarg(10, a_float=5.5, mnemonic=mnem)
            self.assertEqual(res, 10*5.5)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('1 private arguments (mnemonic) not displayed' in logged_msg)

    def test_private_positional_removal(self):
        with patch('logging.Logger.log') as logger:
            mnem = 'every good boy deserves fruit'
            res = function_with_private_arg('should not log', False)
            self.assertFalse(res)
            (alert, logged_msg), extras = logger.call_args_list[0]
            self.assertTrue('1 private arguments (priv) not displayed' in logged_msg)

class NoString(object):
    """
    An object that really hates being cast to string
    """
    def __str__(self):
        raise Exception('No.')

class TestLog(unittest.TestCase):

    def setUp(self):
        self.test_setup = dict(facility='LOG_TEST', ip=None, port=None, do_print=True, do_write=True)
        self.loggo = a_loggo(self.test_setup)
        self.log = self.loggo.log

    def test_protected_keys(self):
        """
        Check that a protected name "name" is converted to "protected_name",
        in order to stop error in logger later
        """
        with patch('logging.Logger.log') as mock_log:
            self.log('fine', None, dict(name='bad', other='good'))
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual(kwargs['extra']['protected_name'], 'bad')
            self.assertEqual(kwargs['extra']['other'], 'good')

    def test_can_log(self):
        with patch('logging.Logger.log') as logger:
            nums = [(None, 20), ('dev', 40), ('critical', 50)]
            msg = 'Test message here'
            for level, num in nums:
                result = self.log(msg, level, dict(extra='data'))
                self.assertIsNone(result)
                (alert, logged_msg), extras = logger.call_args
                self.assertEqual(alert, num)
                self.assertEqual(msg, logged_msg)
                self.assertEqual(extras['extra']['extra'], 'data')

    def test_write_to_file(self):
        """
        Check that we can write logs to file
        """
        mock = mock_open()
        with patch('builtins.open', mock):
            self.log('An entry in our log')
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
            self.log(msg, None, log_data)
            mock_log.assert_called_with(20, msg, extra=ANY)
            logger_was_passed = mock_log.call_args[1]['extra']['key']
            done_by_hand = str(large_number)[:30000] + '...'
            self.assertEqual(logger_was_passed, done_by_hand)

    def test_string_truncation_fail(self):
        """
        If something cannot be cast to string, we need to know about it
        """
        with patch('logging.Logger.log') as mock_log:
            no_string_rep = NoString()
            result = self.loggo._force_string_and_truncate(no_string_rep)
            self.assertEqual(result, '<<Unstringable input>>')
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual('Object could not be cast to string', msg)

    def test_stringify_non_dict(self):
        example = 123
        result = self.loggo._stringify_dict(example)
        self.assertEqual(result['data'], str(example))

    def test_fail_to_add_entry(self):
        with patch('logging.Logger.log') as mock_log:
            no_string_rep = NoString()
            sample = dict(fine=123, not_fine=no_string_rep)
            result = self.loggo._stringify_dict(sample)
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual('Object could not be cast to string', msg)
            self.assertEqual(result['not_fine'], '<<Unstringable input>>')
            self.assertEqual(result['fine'], '123')

    def test_emergency_log_finite(self):
        with patch('logging.Logger.log') as mock_log:
            self.loggo._emergency_log('an error', 'different error', ValueError)
            (alert, msg), kwargs = mock_log.call_args
            self.assertEqual(msg, 'Unknown error in emergency log')

    def test_emergency_log_infinite(self):
        with patch('logging.Logger.log') as mock_log, \
                patch('loggo.Loggo._stringify_dict') as stringer, \
                patch('builtins.print') as printer:
            stringer.side_effect = Exception('Bam!')
            with self.assertRaises(Exception):
                self.log('Otherwise', None, dict(reasonable='message'))
                print_args = printer.call_args
                self.assertEqual(print_args, 'General log failure: Bam!')
                self.assertEqual(kwargs, dict())

    def test_emergency_megafail(self):
        with patch('logging.Logger.log') as mock_log:#, \
                #patch('builtins.print') as printer:
            msg = 'General log failure: Really dead.'
            mock_log.side_effect = Exception('Really dead.')
            with self.assertRaises(SystemExit):
                self.loggo._emergency_log('an error', 'different error', ValueError)
                print_args = printer.call_args
                self.assertTrue(msg in print_args)

    def test_loggo_pause(self):
        with patch('logging.Logger.log') as mock_log:
            with Loggo.pause():
                Loggo.log('test')
            mock_log.assert_not_called()
            Loggo.log('test')
            mock_log.assert_called()

    def test_loggo_pause_error(self):
        with patch('logging.Logger.log') as logger:
            with Loggo.pause():
                with self.assertRaises(ValueError):
                    test('one', 'two')
            (alert, msg), kwargs = logger.call_args
            self.assertTrue('Errored with ValueError' in msg)
            logger.assert_called_once()
            logger.reset()
            with self.assertRaises(ValueError):
                test('one', 'two')
                self.assertEqual(len(logger.call_args_list), 2)

    def test_loggo_error_suppressed(self):
        with patch('logging.Logger.log') as logger:
            with Loggo.pause(allow_errors=False):
                with self.assertRaises(ValueError):
                    test('one', 'two')
            logger.assert_not_called()
            Loggo.log('test')
            logger.assert_called_once()

    def test_see_below(self):
        with patch('logging.Logger.log') as logger:
            msg = 'testing only'
            log_data = {'traceback': False, 'other': 123}
            msg, log_data = self.loggo.sanitise(msg, log_data)
            s = self.loggo._build_string(msg, 'dev', log_data, truncate=200, include_data=False)
            self.assertTrue('-- see below:' not in s)

    def test_compat(self):
        test = 'a string'
        with patch('loggo.Loggo.log') as logger:
            Loggo.log(test, None, None)
        args = logger.call_args
        self.assertEqual(args[0][0], test)
        self.assertIsNone(args[0][1])
        self.assertIsNone(args[0][2])
        with patch('logging.Logger.log') as logger:
            Loggo.log(test)
        (alert, msg), kwargs = logger.call_args
        self.assertEqual(test, msg)

    def test_bad_args(self):

        @Loggo.logme
        def dummy(needed):
            return needed
        with self.assertRaises(TypeError):
            dummy()

    # taneli error that hasn't been reproduced yet
    # point is that inspect sig can fail with ValueError (e.g. for print)
    #def test_uninspectable(self):
    #    with patch('loggo.Loggo.log') as logger:
    #        mock = Mock(autospec=True)
    #        self.loggo._handle_error = Mock()
    #        Loggo.log(print)
    #        arg = mock.call_args_list[-1]
    #        print(arg)





if __name__ == '__main__':
    unittest.main()
