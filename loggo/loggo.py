"""
Loggo: decorators for logging
"""

import inspect
import logging
import os
import sys
import traceback
import uuid
from contextlib import contextmanager
from datetime import datetime
from functools import wraps

LOG_LEVELS = dict(critical='CRITICAL',
                  dev='ERROR',
                  error='ERROR',
                  minor='WARNING',
                  info='INFO',
                  debug='DEBUG')

DEFAULT_PRIVATE_KEYS = {'token', 'password', 'prv', 'priv', 'xprv', 'secret', 'mnemonic', 'headers'}
MAX_DICT_DEPTH = 5

# you don't need graylog installed, but it is really powerful
try:
    import graypy
except ImportError:
    graypy = None

# colorama can be used to color your log messages, but also isn't needed
try:
    from colorama import init
    init()
    from colorama import Fore, Back, Style
    COLOUR_MAP = dict(red=Fore.RED + Style.BRIGHT,
                      green=Fore.GREEN + Style.BRIGHT,
                      critical=Fore.WHITE + Back.RED + Style.BRIGHT,
                      dev=Fore.RED + Style.BRIGHT,
                      debug=Style.DIM,
                      greenbright=Fore.GREEN + Style.BRIGHT,
                      end=Style.RESET_ALL)
except ImportError:
    COLOUR_MAP = dict()

# Strings to be formatted for pre function, post function and error during function
FORMS = dict(pre='*Called {modul}.{function} {callable} with {nparams} parameters: {kwa}\n',
             post='*Returned a {return_type} {return_value} from {modul}.{function} {callable}\n',
             noreturn='*Returned None from {modul}.{function} {callable}\n',
             error='*Errored with {error_type} "{error_string}" when calling {modul}.{function} {callable} with {nparams} parameters: {kwa}\n')


def colour_msg(msg, alert, do_colour):
    """
    Try to colour a message if colorama is installed, and do_colour is True.

    Colours are based on alert levels
    """
    if not do_colour:
        return msg
    if alert is None:
        alert = COLOUR_MAP.get('greenbright', '')
    else:
        alert = COLOUR_MAP.get(alert, '')
    return '{colour}{msg}\x1b[0m'.format(colour=alert, msg=msg)


class Loggo(object):
    """
    A class for logging

    On instantiation, pass in a dictionary containing the config. Currently
    accepted config values are:

    - facility: name of the app the log is coming from
    - ip: ip address for graylog
    - port: port for graylog
    - logfile: path to a file to which logs will be written
    - do_print: print logs to console
    - do_write: write logs to file
    - do_colour: try to colour console text
    - line_length: max length for console printed string
    - private_data: key names that should be filtered out of logging. if not set,
      some sensible defaults are used
    """
    def __init__(self, config={}):
        self.stopped = False
        self.allow_errors = True
        self.config = config
        self.sublogger = None
        # these things should always end up in the extra data provided to logger
        self.log_data = dict(loggo=True, loggo_config=dict(config), sublogger=self.sublogger)
        self.facility = config.get('facility', 'loggo')
        self.ip = config.get('ip', None)
        self.port = config.get('port', None)
        self.do_print = config.get('do_print', False)
        self.do_write = config.get('do_write', False)
        self.do_colour = config.get('do_colour', False)
        self.logfile = config.get('logfile', './logs/logs.txt')
        self.line_length = config.get('line_length', 200)
        self.obscured = config.get('obscure', '[PRIVATE_DATA]')
        self.private_data = config.get('private_data', DEFAULT_PRIVATE_KEYS)
        self.logger = logging.getLogger(self.facility)  # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

    def listen_to(loggo_self, facility, no_graylog_disable_log=False):
        """
        This method can hook the logger up to anything else that logs using the
        Python logging module (i.e. another logger) and steals its logs
        """
        loggo_self.no_graylog_disable_log = no_graylog_disable_log

        class LoggoHandler(logging.Handler):
            def emit(handler_self, record):
                attributes = {'msg', 'created', 'msecs', 'stack_info',
                              'levelname', 'filename', 'module', 'args',
                              'funcName', 'process', 'relativeCreated',
                              'exc_info', 'name', 'processName', 'threadName',
                              'lineno', 'exc_text', 'pathname', 'thread',
                              'levelno'}
                extra = dict(record.__dict__)
                [extra.pop(attrib, None) for attrib in attributes]
                alert = extra.get('alert')
                loggo_self.log_data['sublogger'] = facility
                loggo_self.sublogger = facility
                extra['sublogger'] = facility
                loggo_self.log(record.msg, alert, data=extra)
        other_loggo = logging.getLogger(facility)
        other_loggo.setLevel(logging.DEBUG)
        other_loggo.addHandler(LoggoHandler())

    @contextmanager
    def pause(self, allow_errors=True):
        """
        A context manager that prevents loggo from logging in that context. By
        default, errors will still make it through, unless allow_errors==False
        """
        original = self.allow_errors, self.stopped
        self.stopped = True
        self.allow_errors = allow_errors
        try:
            yield self
        except Exception as error:
            raise error
        finally:
            self.allow_errors, self.stopped = original

    @contextmanager
    def verbose(self, allow_errors=True):
        """
        Context manager that makes, rather than suppresses, msgs
        """
        original = self.allow_errors, self.stopped
        self.stopped = False
        try:
            yield self
        except Exception as error:
            raise error
        finally:
            self.allow_errors, self.stopped = original

    @contextmanager
    def log_errors(self):
        """
        Context manager that logs errors only
        """
        original = self.allow_errors, self.stopped
        try:
            yield self
        except Exception as error:
            raise error
        finally:
            self.allow_errors, self.stopped = original

    def __call__(self, class_or_func):
        """
        Make Loggo itself a decorator of either a class or a method/function. so
        you can just use @Loggo on everything
        """
        if inspect.isclass(class_or_func):
            return self.everything(class_or_func)
        return self.logme(class_or_func)

    def stop(self, allow_errors=True):
        """
        Manually stop loggo from logging, but by default allow errors through
        """
        self.stopped = True
        self.allow_errors = allow_errors

    def start(self, allow_errors=True):
        """
        Manually restart loggo, also allowing errors by default
        """
        self.stopped = False
        self.allow_errors = allow_errors

    def params_to_log_data(self, function, *args, **kwargs):
        """
        This uses some weird inspection to figure out what the names of positional
        and keyword arguments were, so that even positional arguments with
        private names can be censored.

        If anything fails here, which it can, then log the error and empty params
        """
        try:
            sig = inspect.signature(function)
            bound = sig.bind(*args, **kwargs).arguments
            bound.pop('self', None)
            bound.pop('cls', None)
            return self.sanitise_dict(bound)
        except (ValueError, TypeError) as error:
            self.generate_log('error', error, function, 'callable')

    @staticmethod
    def get_call_type(inspected):
        """
        Find out, by way of signature, what kind of callable we have. Currently
        does not distinguish between staticmethods and functions!
        """
        if not inspected:
            return 'function'
        if list(inspected)[0] == 'self':
            return 'method'
        elif list(inspected)[0] == 'cls':
            return 'classmethod'
        return 'function'

    def _obscure_private_keys(self, dictionary, dict_depth=0):
        """
        Obscure any private values in a dictionary recursively
        """
        keys_set = set(self.private_data)  # Just an optimization for the "if key in keys" lookup.

        modified_dict = dict()
        for key, value in dictionary.items():
            if key in keys_set:
                modified_dict[key] = self.obscured
            else:
                # recursive for embedded dictionaries
                if isinstance(value, dict) and dict_depth < MAX_DICT_DEPTH:
                    modified_dict[key] = self._obscure_private_keys(value, dict_depth + 1)
                else:
                    modified_dict[key] = value
        return modified_dict

    def logme(self, function):
        """
        This the function decorator. After having instantiated Loggo, use it as a
        decorator like so:

        @Loggo.logme
        def f(): pass

        It will the call, return and errors that occurred during the function/method
        """

        # if logging has been turned off, just do nothing
        if getattr(function, 'no_log', False):
            @wraps(function)
            def unlogged(*args, **kwargs):
                """
                A dummy decorator to be used if no_log is set
                """
                return function(*args, **kwargs)
            return unlogged

        @wraps(function)
        def full_decoration(*args, **kwargs):
            """
            Main decorator logic. Generate a log before running the callable,
            then try to run it. If it errors, log the error. If it doesn't,
            log the return value.

            Args and kwargs are for/from the decorated function
            """
            # turn all passed parameters into a dict of loggable extras
            extra = self.params_to_log_data(function, *args, **kwargs)
            
            # add a unique identifier for this set of logs
            extra['couplet'] = uuid.uuid1()
            extra['number_of_params'] = len(args) + len(kwargs)

            # function, method or classmethod?
            call_type = self.get_call_type(extra)

            # make 100% sure we destroy tracebacks from earlier runs
            trace = None

            # pre log tells you what was called and with what arguments
            self.generate_log('pre', None, function, call_type, extra=extra)

            try:
                # where the original function is actually run
                response = function(*args, **kwargs)
                # make extra sure traceback hasn't persisted
                extra.pop('traceback', None)
                # the successful return log
                self.generate_log('post', response, function, call_type, extra=extra)
                # return whatever the original callable did
                return response
            # handle any possible error
            except Exception as error:
                trace = sys.exc_info()
                extra['traceback'] = traceback.format_exception(*trace)
                self.generate_log('error', error, function, call_type, extra=extra)
                raise error.__class__(str(error)).with_traceback(trace[-1])
            # always kill traceback at the conclusion of a log cycle
            finally:
                del trace

        return full_decoration

    @staticmethod
    def ignore(function):
        """
        A decorator that will override Loggo.everything, in case you do not want
        to log one particular method for some reason
        """
        function.no_log = True
        return function

    def decorate_if_possible(self, func):
        """
        To be decorable, the func must be callable, and have a non-magic __name__
        """
        name = getattr(func, '__name__', False)
        if not name:
            return func
        if name.startswith('__') and name.endswith('__'):
            return func
        if callable(func):
            return self.logme(func)
        return func

    def errors(self, function):
        """
        Only log errors within a given method
        """
        function.just_errors = True
        return self.decorate_if_possible(function)

    def everything(self, cls):
        """
        Decorator for class, which attaches itself to any (non-dunder) methods
        """
        class Decorated(cls):
            def __getattribute__(self_or_class, name):
                unwrapped = object.__getattribute__(self_or_class, name)
                return self.decorate_if_possible(unwrapped)
        return Decorated

    def _represent_return_value(self, response):
        """
        Make a string representation of whatever a method returns
        """
        representable = (int, float, str, list, set, dict, type(None), bool, tuple)
        if isinstance(response, representable):
            return '({})'.format(self._force_string_and_truncate(response, 70))
        # some custom handling for request response objects
        content = getattr(response, 'content', False)
        if content:
            return '({})'.format(self._force_string_and_truncate(content.decode('utf-8'), 70))
        # fallback, should not happen
        return ''

    def safe_param_display(self, kwargs, truncate=True):
        """
        Build a string showing keyword arguments if we can
        """
        original = len(kwargs)
        output_list = list()

        if not original:
            return ''

        copied = dict(kwargs)
        copied = self._obscure_private_keys(copied)
        priv_names = ', '.join([i for i in kwargs if i not in copied])

        if not copied:
            rep = '{} private arguments ({}) not displayed'.format(original, priv_names)
        else:
            for k, v in copied.items():
                if k == 'self':
                    continue
                trunc = 10 if truncate else 9999
                short = self._force_string_and_truncate(v, trunc)
                if k in {'args', 'kwargs'}:
                    representation = '{}={}'.format(k, short)
                else:
                    representation = '{}={}({})'.format(k, type(v).__name__, short)
                output_list.append(representation)
            rep = ', '.join(output_list)

        if copied and len(copied) != original:
            num_priv = original - len(copied)
            rep += '. {} private arguments ({}) not displayed'.format(num_priv, priv_names)

        return rep + '.'

    def generate_log(self, where, returned, function, call_type, extra={}):
        """
        General log string and data for before, after or error in function
        """
        # if errors not to be shown and this is an error, quit
        if not self.allow_errors and where == 'error':
            return

        # if we've used Loggo.errors on this method and it's not an error, quit
        if getattr(function, 'just_errors', False) and where != 'error':
            return

        # if state is stopped and not an error, quit
        if self.stopped and where != 'error':
            return

        # this just stops the annoying 'returned a NoneType (None)'
        if where == 'post' and returned is None:
            where = 'noreturn'

        # do not log loggo, because why would you ever want that?
        if getattr(function, '__module__', 'modul') == 'loggo.loggo':
            return

        # get the correct message
        unformatted_message = FORMS.get(where)

        # return value for log message
        return_value = self._represent_return_value(returned)

        # get all the data to be fed into the strings
        forms = dict(modul=modul,
                     function=getattr(function, '__name__', 'func'),
                     callable=call_type,
                     nparams=extra.get('number_of_params', '?'),
                     return_value=return_value,
                     kwa=self.safe_param_display(extra, truncate=False),
                     return_type=type(returned).__name__)

        # if what is returned is an exception, do some special handling:
        if isinstance(returned, Exception):
            forms['error_type'] = returned.__class__.__name__
            forms['error_string'] = str(returned)

        # add exception info for errors
        extra['exc_info'] = True if where == 'error' else False

        # make the message from the template and info
        formed = unformatted_message.format(**forms).replace('  ', ' ')

        # no colon in message if there is nothing to go after it
        if not extra:
            formed = formed.replace(': \n', '\n')

        # logs contain three things: a message string, a log level, and a dict of
        # extra data. there are three methods for these, which may be overwritten
        # by subclassing the methods used below if you want
        msg = self.get_msg(returned, formed)
        level = self.get_alert(returned)
        log_data = self.get_log_data(returned, forms, extra)
        # perhaps not the ideal place for this?
        custom_log_data = self.add_custom_log_data()
        log_data.update(custom_log_data)

        # record if logging was on or off
        original_state = bool(self.stopped)
        # turn it on just for now, as if we shouldn't log we'd have returned
        self.stopped = False
        # do logging
        self.log(msg, level, log_data)
        # restore old stopped state
        self.stopped = original_state

    def add_custom_log_data(self):
        """
        An overwritable method useful for adding custom log data
        """
        return dict()

    def get_msg(self, returned, existing):
        """
        Get a message to append to the main one.
        Override/extend this method if you have a different kind of object
        """
        return existing

    def get_alert(self, returned):
        """
        Get an alert level from either self or returned
        Override/extend this method if you have a different kind of object
        """
        return 'dev' if isinstance(returned, Exception) else None

    def get_log_data(self, returned, forms, extra):
        """
        Get any possible log data and make a single dictionary

        Priority should be: extra, log_data, forms, returned
        """
        if isinstance(returned, dict):
            returned = self.sanitise_dict(returned)
        forms['returned'] = self._force_string_and_truncate(returned, 10000)
        forms.pop('return_value', None)
        return {**forms, **self.log_data, **extra}

    @staticmethod
    def _format_traceback(trace, colour=True):
        """
        Check if there is a traceback, and format it if need be
        """
        if not trace:
            return False
        if colour:
            start = COLOUR_MAP.get('critical', '')
            end = COLOUR_MAP.get('end', '')
            trace = '{}{}{}\n'.format(start, trace, end)
        return '\t' + trace.replace('\n', '\n\t')

    def _build_string(self, msg, level, log_data, truncate=0, colour=False, include_data=True):
        """
        Make a single line string, or multiline if traceback provided, for print
        and file logging
        """
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        trace = self._format_traceback(log_data.get('traceback'), colour=colour)
        datapoints = [tstamp, msg, level]
        if include_data:
            datapoints.append(log_data)
        strung = '\t' + '\t'.join([str(s).strip('\n') for s in datapoints])
        if truncate and len(strung) > truncate:
            strung = strung[:truncate] + '...'
        if trace:
            strung = '{} -- see below: \n{}\n'.format(strung, trace)
        return strung

    def get_logfile(self, data):
        """
        This method exists so that it can be overwritten for applications requiring
        more complex logfile choices.
        """
        return self.logfile

    def write_to_file(self, line, logfile=None):
        """
        Very simple log writer, could expand. simple append the line to the file
        """
        if not logfile:
            logfile = self.logfile

        needed_dir = os.path.dirname(logfile)
        if needed_dir and not os.path.isdir(needed_dir):
            os.makedirs(os.path.dirname(logfile))
        with open(logfile, 'a') as fo:
            fo.write(line.rstrip('\n') + '\n')

    def add_handler(self):
        """
        Add a handler for Graylog
        """
        if not self.ip or not self.port or not graypy and not self.no_graylog_disable_log:  # pylint: disable=no-member
            self.log('Graylog not configured! Disabling it', 'dev')
            return
        handler = graypy.GELFHandler(self.ip, self.port, debugging_fields=False)  # pylint: disable=no-member
        self.logger.addHandler(handler)

    def _force_string_and_truncate(self, obj, max_length=30000):
        """
        Return stringified and truncated obj, or log alert if not possible
        """
        try:
            obj = str(obj)
        except Exception as error:
            self.log('Object could not be cast to string', 'dev', dict(error=error))
            return '<<Unstringable input>>'
        # truncate and return
        return (obj[:max_length] + '...') if len(obj) > (max_length + 3) else obj

    def _stringify_dict(self, input_data):
        """
        Ensure that keys and values in a dict are strings
        """
        string_data = dict()
        for key, value in input_data.items():
            string_key = self._force_string_and_truncate(key)
            string_value = self._force_string_and_truncate(value)
            string_data[string_key] = string_value
        return string_data

    def _rename_protected_keys(self, log_data):
        """
        Some names cannot go into logger; remove them here and log the problem
        """
        out = dict()
        # names that logger will not like
        protected = {'name', 'message', 'asctime', 'msg', 'module', 'args'}
        for key, value in log_data.items():
            if key in protected:
                key = 'protected_' + key
            out[key] = value
        return out

    def sanitise_dict(self, log_data):
        """
        Ensure that log data is safe to log:

        - No private keys
        - Rename protected keys
        - Everthing strings
        """
        log_data = self._obscure_private_keys(log_data)
        log_data = self._rename_protected_keys(log_data)
        log_data = self._stringify_dict(log_data)
        return message, log_data

    @staticmethod
    def compatibility_hack(alert, data):
        """
        Brief hack to allow tx2 ugly call syntax
        """
        if isinstance(alert, dict) and data is None:
            log_data = dict(alert)
            alert = alert.get('alert', alert.get('level', None))
        else:
            log_data = data
        return alert, log_data

    @staticmethod
    def _get_log_level(alert):
        if isinstance(alert, str):
            return getattr(logging, LOG_LEVELS.get(alert, 'INFO'))
        elif isinstance(alert, int):
            return alert
        return 20


    def log(self, message, alert=None, extra=None, **kwargs):
        """
        Main logging method. Takes message string, alert level, and a data dict
        that will be logged. anything (accidentally) passed as kwargs will get
        merged into the data dictionary
        """
        # don't log in a stopped state
        if self.stopped:
            return

        # crazy bit of code to get things from the parent function
        outer = inspect.getouterframes(inspect.currentframe())[1]
        frame = outer.frame
        func_name = inspect.stack()[1][3]

        if func_name == 'add_handler':
            return

        args, _, _, local_dict = inspect.getargvalues(frame)
        kwa = {a: local_dict[a] for a in args}

        if not args:
            # static method? :(
            return

        classy = local_dict[args[0]]
        func = getattr(classy, func_name, None)
        if func is None:
            # no func name
            return

        class_name = classy.__class__.__name__
        joined = '{}.{}'.format(class_name, func_name)
        self.log_data['callable'] = joined

        kwa = self.params_to_log_data(func, **kwa)

        kwargs.update(kwa)

        # check for errors (can there even be any?)
        if sys.exc_info() != (None, None, None):
            trace = sys.exc_info()
            self.log_data['traceback'] = traceback.format_exception(*trace)

        # bitpanda internal hack, to remove after some modernising of our code
        alert, data = self.compatibility_hack(alert, data)

        # translate log levels to an integer --- things to fix here still
        log_level = self._get_log_level(alert)

        # do all preprocessing of log data, like casting, truncation, etc.
        # then do printing, filelogging and actual logging as per options.
        # all failures will result in emergency log, which falls back to
        # whatever it can (i.e. print) and which stops infinite loops
        try:
            message = self._force_string_and_truncate(message)
            string_data = self.sanitise_dict(data)
            string_data['alert'] = alert
            if self.do_print:
                opts = dict(truncate=self.line_length, include_data=False, colour=self.do_colour)
                single_string = self._build_string(message, alert, string_data, **opts)
                print(colour_msg(single_string, alert, self.do_colour))

            if self.do_write:
                plain_string = self._build_string(message, alert, string_data, colour=False)
                logfile = self.get_logfile(data)
                self.write_to_file(plain_string, logfile)

            self.logger.log(log_level, message, extra=string_data)

        except Exception as error:
            self._emergency_log('General log failure: {}'.format(str(error)), message, error)

    def _emergency_log(self, error_msg, msg, exception):
        """
        If there is an exception during logging, log/print it
        """
        try:
            print(msg, error_msg)
            if msg != error_msg:
                self.log(error_msg, 'dev')
                last_chance = getattr(exception, 'message', 'Unknown error in emergency log')
                self.log(str(last_chance), 'dev')
            else:
                print(msg)
                print('Exiting because the system is in infinite loop')
                error_msg = str(getattr(exception, 'message', exception))
                print(error_msg)
                raise SystemExit(1)
        except Exception as error:
            print('Emergency log exception')
            print(str(error))
            raise SystemExit(1)
