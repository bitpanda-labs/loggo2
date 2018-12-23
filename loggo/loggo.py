"""
Loggo: safe and automatable logging
"""

import inspect
import logging
import os
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

MAX_DICT_DEPTH = 5

# you don't need graylog installed, but it is really powerful
try:
    import graypy
except ImportError:
    graypy = None

# Strings to be formatted for pre function, post function and error during function
FORMS = dict(pre='*Called {call_signature}',
             post='*Returned from {call_signature} with {return_type} {return_value}',
             noreturn='*Returned None from {call_signature}',
             error='*Errored during {call_signature} with {error_type} "{error_string}"')


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
    - line_length: max length for console printed string
    - private_data: key names that should be filtered out of logging. when not
    provided, nothing is censored
      some sensible defaults are used
    """
    def __init__(self, config=None):
        if config is None:
            config = {}

        self.stopped = False
        self.allow_errors = True
        self.config = config
        self.sublogger = None
        # these things should always end up in the extra data provided to logger
        self.log_data = dict(loggo=True, loggo_config=dict(config), sublogger=self.sublogger)
        self.facility = config.get('facility', 'loggo')
        self.ip = config.get('ip')
        self.port = config.get('port')
        self.do_print = config.get('do_print')
        self.do_write = config.get('do_write')
        self.raise_logging_errors = config.get('raise_logging_errors', False)
        self.logfile = config.get('logfile', './logs/logs.txt')
        self.line_length = config.get('line_length', 200)
        self.obscured = config.get('obscure', '[PRIVATE_DATA]')
        self.private_data = set(config.get('private_data', set()))
        self.logger = logging.getLogger(self.facility)  # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

    def __call__(self, class_or_func):
        """
        Make Loggo itself a decorator of either a class or a method/function. so
        you can just use @Loggo on everything
        """
        if inspect.isclass(class_or_func):
            return self.everything(class_or_func)
        return self.logme(class_or_func)

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
        finally:
            self.allow_errors, self.stopped = original

    @contextmanager
    def verbose(self, allow_errors=True):
        """
        Context manager that makes, rather than suppresses, msgs
        """
        original = self.allow_errors, self.stopped
        self.stopped = False
        self.allow_errors = allow_errors
        try:
            yield self
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
        finally:
            self.allow_errors, self.stopped = original

    def stop(self, allow_errors=True):
        """
        Normal function: manually stop loggo from logging, but by default allow
        errors through
        """
        self.stopped = True
        self.allow_errors = allow_errors

    def start(self, allow_errors=True):
        """
        Normal function: manually restart loggo, also allowing errors by default
        """
        self.stopped = False
        self.allow_errors = allow_errors

    @staticmethod
    def ignore(function):
        """
        A decorator that will override Loggo.everything, in case you do not want
        to log one particular method for some reason
        """
        function._do_not_log_this_callable = True
        return function

    def errors(self, function):
        """
        Decorator: only log errors within a given method
        """
        function.just_errors = True
        return self._decorate_if_possible(function)

    def everything(self, cls):
        """
        Decorator for class, which attaches itself to any (non-dunder) methods
        """
        class Decorated(cls):
            def __getattribute__(self_or_class, name):
                unwrapped = object.__getattribute__(self_or_class, name)
                return self._decorate_if_possible(unwrapped)
        return Decorated

    def logme(self, function):
        """
        This the function decorator. After having instantiated Loggo, use it as a
        decorator like so:

        @Loggo.logme
        def f(): pass

        It will the call, return and errors that occurred during the function/method
        """

        # if logging has been turned off, just do nothing
        if getattr(function, '_do_not_log_this_callable', False):
            return function

        @wraps(function)
        def full_decoration(*args, **kwargs):
            """
            Main decorator logic. Generate a log before running the callable,
            then try to run it. If it errors, log the error. If it doesn't,
            log the return value.

            Args and kwargs are for/from the decorated function
            """
            bound = self._params_to_dict(function, *args, **kwargs)
            # bound will be none if inspect signature binding failed. in this
            # case, error log was created, raised if self.raise_logging_errors
            if bound is None:
                return function(*args, **kwargs)

            param_strings = self.sanitise(bound)
            signature, formatters = self._make_call_signature(function, param_strings)
            privates = [key for key in param_strings if key not in bound]

            # add an id and number of params for this couplet
            formatters['couplet'] = uuid.uuid1()
            formatters['number_of_params'] = len(args) + len(kwargs)
            formatters['private_keys'] = ', '.join(privates)

            # pre log tells you what was called and with what arguments
            if not getattr(function, 'just_errors', False):
                self._generate_log('pre', None, formatters, param_strings)

            try:
                # where the original function is actually run
                response = function(*args, **kwargs)
                where = 'post' if response is not None else 'noreturn'
                # the successful return log
                if not getattr(function, 'just_errors', False):
                    self._generate_log(where, response, formatters, param_strings)
                # return whatever the original callable did
                return response
            # handle any possible error
            except Exception as error:
                formatters['traceback'] = traceback.format_exc()
                self._generate_log('error', error, formatters, param_strings)
                raise
        return full_decoration

    def _string_params(self, non_private_params):
        params = dict()
        for key, val in non_private_params.items():
            safe_key = self._force_string_and_truncate(key, 50)

            safe_val = self._force_string_and_truncate(val, 1000, use_repr=True)
            params[safe_key] = safe_val
        return params

    def _make_call_signature(self, function, param_strings):
        signature = '{modul}.{callable}({params})'
        param_str = ', '.join('{}={}'.format(k, v) for k, v in param_strings.items())
        format_strings = dict(modul=getattr(function, '__module__', 'unknown_module'),
                              callable=getattr(function, '__name__', 'unknown_callable'),
                              params=param_str)
        formatted = signature.format(**format_strings)
        format_strings['call_signature'] = formatted
        return formatted, format_strings

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
                loggo_self.log(record.msg, alert, extra)
        other_loggo = logging.getLogger(facility)
        other_loggo.setLevel(logging.DEBUG)
        other_loggo.addHandler(LoggoHandler())

    def _params_to_dict(self, function, *args, **kwargs):
        """
        Turn args and kwargs into an OrderedDict of {param_name: value}
        """
        try:
            sig = inspect.signature(function)
            bound = sig.bind(*args, **kwargs).arguments
            # these names are for methods and classmethods, don't need
            bound.pop('self', None)
            bound.pop('cls', None)
            return bound
        except (ValueError, TypeError) as error:
            modul = getattr(function, '__module__', 'unknown_module')
            call = getattr(function, '__name__', 'unknown_callable')
            call_sig = '{}.{}(<logging-error>)'.format(modul, call)
            formatters = dict(call_signature=call_sig,
                              error_type=str(type(error)),
                              error_string=str(error),
                              modul=modul)
            self._generate_log('error', error, formatters, dict())
            if self.raise_logging_errors:
                raise error

    def _obscure_private_keys(self, dictionary, dict_depth=0):
        """
        Obscure any private values in a dictionary recursively
        """
        if not self.private_data:
            return dictionary

        modified_dict = dict()
        for key, value in dictionary.items():
            if key in self.private_data:
                modified_dict[key] = self.obscured
            else:
                # recursive for embedded dictionaries
                if isinstance(value, dict) and dict_depth < MAX_DICT_DEPTH:
                    modified_dict[key] = self._obscure_private_keys(value, dict_depth + 1)
                else:
                    modified_dict[key] = value
        return modified_dict

    def _decorate_if_possible(self, func):
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

    def _represent_return_value(self, response, truncate=140):
        """
        Make a string representation of whatever a method returns
        """
        representable = (int, float, str, list, set, dict, type(None), bool, tuple)
        if isinstance(response, representable):
            return '({})'.format(self._force_string_and_truncate(response, truncate, use_repr=True))
        # some custom handling for request response objects
        content = getattr(response, 'content', False)
        if content:
            return '({})'.format(self._force_string_and_truncate(content.decode('utf-8'), truncate, use_repr=True))
        # fallback, should not happen
        return ''

    def _generate_log(self, where, returned, formatters, safe_log_data):
        """
        generate message, level and log data for automated logs

        `where`: 'pre'/'post'/'noreturn'/'error'
        `returned`: what the decorated callable returned
        `formatters`: dict containing format strings needed for message
        `safe_log_data`: dict of stringified, truncated, censored parameters
        """
        # if errors not to be shown and this is an error, quit
        if not self.allow_errors and where == 'error':
            return

        # if state is stopped and not an error, quit
        if self.stopped and where != 'error':
            return

        # do not log loggo, because why would you ever want that?
        if formatters['modul'] == 'loggo.loggo':
            return

        # get the correct message
        unformatted_message = FORMS.get(where)

        # return value for log message
        if where == 'post':
            formatters['return_value'] = self._represent_return_value(returned)
            formatters['return_type'] = type(returned).__name__

        # if what is returned is an exception, do some special handling:
        if where == 'error':
            formatters['error_type'] = returned.__class__.__name__
            formatters['error_string'] = str(returned)

        msg = unformatted_message.format(**formatters).replace('  ', ' ')
        level = 'dev' if where == 'error' else None

        if where == 'post':
            formatters['return_value'] = self._represent_return_value(returned, truncate=False)

        # make the log data
        log_data = {**formatters, **safe_log_data}
        log_data['except'] = True if where == 'error' else False
        custom_log_data = self.add_custom_log_data()
        log_data.update(custom_log_data)

        # record if logging was on or off
        original_state = bool(self.stopped)
        # turn it on just for now, as if we shouldn't log we'd have returned
        self.stopped = False
        # do logging
        self.log(msg, level, log_data, safe=True)
        # restore old stopped state
        self.stopped = original_state

    def add_custom_log_data(self):
        """
        An overwritable method useful for adding custom log data
        """
        return dict()

    def _build_string(self, msg, level, traceback=None):
        """
        Make a single line string, or multiline if traceback provided, for print
        and file logging
        """
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        datapoints = [tstamp, msg, level]
        strung = '\t' + '\t'.join([str(s).strip('\n') for s in datapoints])
        if traceback:
            strung = '{} -- see below: \n{}\n'.format(strung, traceback)
        return strung.strip('\n') + '\n'

    def get_logfile(self):
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

    def _force_string_and_truncate(self, obj, max_length=30000, use_repr=False):
        """
        Return stringified and truncated obj, or log alert if not possible
        """
        try:
            obj = str(obj) if not use_repr else repr(obj)
        except Exception as error:
            self.log('Object could not be cast to string', 'dev', dict(error=str(error)))
            return '<<Unstringable input>>'
        # truncate and return
        return (obj[:max_length] + '...') if len(obj) > (max_length + 3) else obj

    def _rename_protected_keys(self, log_data):
        """
        Some names cannot go into logger; remove them here and log the problem
        """
        out = dict()
        # names that logger will not like
        protected = {'name', 'message', 'asctime', 'msg', 'module', 'args', 'exc_info'}
        for key, value in log_data.items():
            if key in protected:
                key = 'protected_' + key
            out[key] = value
        return out

    def sanitise(self, unsafe_dict):
        """
        Ensure that log data is safe to log:

        - No private keys
        - Rename protected keys
        - Everthing strings
        """
        obscured = self._obscure_private_keys(unsafe_dict)
        no_protected = self._rename_protected_keys(obscured)
        return self._string_params(no_protected)

    @staticmethod
    def _get_log_level(alert):
        if isinstance(alert, str):
            return getattr(logging, LOG_LEVELS.get(alert, 'INFO'))
        elif isinstance(alert, int):
            return alert
        return 20

    def log(self, message, alert=None, extra=None, safe=False):
        """
        Main logging method, called both in auto logs and manually by user

        message: string to log
        alert: numerical priority of log
        extra: dict of extra fields to log
        safe: do we need to sanitise extra?
        """
        if extra is None:
            extra = {}

        log_data = {k: v for k, v in self.log_data.items()}
        log_data.update(extra)

        # don't log in a stopped state
        if self.stopped:
            return

        # get parent function
        callable_name = inspect.stack()[1][3]

        if callable_name in {'add_handler', 'log'}:
            return

        # check for errors (can there even be any?)
        trace = extra.get('traceback')
        if trace:
            log_data['traceback'] = trace

        # translate log levels to an integer --- things to fix here still
        log_level = self._get_log_level(alert)

        if not safe:
            log_data = self.sanitise(log_data)

        log_data['alert'] = alert

        # print or write log lines
        line = None
        if self.do_print or self.do_write:
            line = self._build_string(message, alert, traceback=trace)
        if self.do_print:
            print(line)
        if self.do_write:
            logfile = self.get_logfile()
            self.write_to_file(line, logfile)

        # the only actual call to logging module!
        try:
            self.logger.log(log_level, message, extra=log_data)
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
