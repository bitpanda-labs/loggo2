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

LOG_LEVELS = dict(critical='CRITICAL',
                  dev='ERROR',
                  error='ERROR',
                  minor='WARNING',
                  info='INFO',
                  debug='DEBUG')

DEFAULT_PRIVATE_KEYS = {'token', 'password', 'prv', 'priv', 'xprv', 'secret', 'mnemonic', 'headers'}

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
FORMS = dict(pre='*Called {modul}.{function} {callable} with {nargs} args, {nkwargs} kwargs: {kwa}\n',
             post='*Returned a {return_type} {return_value} from {modul}.{function} {callable}\n',
             noreturn='*Returned None from {modul}.{function} {callable}\n',
             error='*Errored with {error_type} "{error_string}" when calling {modul}.{function} {callable} with {nargs} args, {nkwargs} kwargs: {kwa}\n')

def colour_msg(msg, alert):
    """
    Try to colour a message if colorama is installed, based on alert level
    """
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
    - line_length: max length for console printed string
    - private_data: key names that should be filtered out of logging. if not set,
      some sensible defaults are used
    """
    def __init__(self, config={}):
        self.stopped = False
        self.allow_errors = True
        self.config = config
        self.log_data = dict(config)
        self.facility = config.get('facility', 'loggo')
        self.ip = config.get('ip', None)
        self.port = config.get('port', None)
        self.do_print = config.get('do_print', True)
        self.do_write = config.get('do_write', True)
        self.logfile = config.get('logfile', './logs/logs.txt')
        self.line_length = config.get('line_length', 200)
        self.obscured = config.get('obscure', '[PRIVATE_DATA]')
        self.private_data = config.get('private_data', DEFAULT_PRIVATE_KEYS)
        self.logger = logging.getLogger(self.facility) # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

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
            #self.stopped = False

    def __call__(self, class_or_func):
        """
        Make Loggo itself a decorator of either a class or a method/function
        """
        if inspect.isclass(class_or_func):
            return self.everything(class_or_func)
        return self.logme(class_or_func)

    def kwargify(self, function, *args, **kwargs):
        """
        This uses some weird inspection to figure out what the names of positional
        and keyword arguments were, so that even positional arguments with
        private names can be censored.

        This also definitively works out how many args/kwargs were passed in
        """
        # pylint: disable=attribute-defined-outside-init

        sig = inspect.signature(function)
        bound = sig.bind(*args, **kwargs).arguments
        self.nargs = 0
        self.nkwargs = 0
        for key, value in sig.parameters.items():
            self.log_data[key] = value if key not in self.private_data else self.obscured
            if key not in bound:
                continue
            is_keyword = int(value.default != inspect._empty)
            if is_keyword:
                self.nkwargs += 1
            else:
                self.nargs += 1
        return bound

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

    @staticmethod
    def get_call_type(inspected):
        """
        Find out, by way of signature, what kind of callable we have
        """
        if not inspected:
            return 'function'
        if list(inspected)[0] == 'self':
            return 'method'
        elif list(inspected)[0] == 'cls':
            return 'classmethod'
        return 'function'

    def logme(self, function):
        """
        This the main decorator. After having instantiated Loggo, use it as a
        decorator like so:

        @Loggo.logme
        def f(): pass

        It will the call, return and errors that occurred during the function/method
        """
        if getattr(function, 'no_log', False):
            def unlogged(*args, **kwargs):
                """
                A dummy decorator to be used if no_log is set
                """
                return function(*args, **kwargs)
            return unlogged

        def full_decoration(*args, **kwargs):
            """
            This takes the args and kwargs for the decorated function
            """
            extra = self.kwargify(function, *args, **kwargs)
            call_type = self.get_call_type(extra)
            call_args = {k: (v if k not in self.private_data else self.obscured) for k, v in extra.items()}
            self.log_data = dict(loggo=True, call_arguments=call_args)

            # pre log tells you what was called  and with what arguments
            idx = uuid.uuid1()
            self.generate_log('pre', None, function, call_type, extra=extra, idx=idx)

            try:
                # where the original function is actually run
                response = function(*args, **kwargs)
                # the succesfful return log
                self.generate_log('post', response, function, call_type, extra=extra, idx=idx)
                return response
            except Exception as error:
                # here, we try to remove the loggo layer from the traceback. will
                # basically use
                exc_type, exc_value, exc_traceback = sys.exc_info()
                if exc_traceback.tb_next:
                    exc_traceback = exc_traceback.tb_next
                tb = (exc_type, exc_value, exc_traceback)
                self.generate_log('error', error, function, call_type, trace=tb, extra=extra, idx=idx)
                raise error.__class__(str(error)).with_traceback(exc_traceback)
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
        if func.__name__.startswith('__') and func.__name__.endswith('__'):
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
        Decorator for class, which attaches itself to any methods
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
        representable = (int, float, str, list, set, dict, type(None), bool)
        if isinstance(response, representable):
            return '({})'.format(self._force_string_and_truncate(response, 30))
        return ''

    def safe_arg_display(self, kwargs):
        """
        Build a string showing keyword arguments if we can
        """
        original = len(kwargs)
        output_list = list()

        if not original:
            return ''

        copied = dict(kwargs)
        copied = self._remove_private_keys(copied)
        priv_names = ', '.join([i for i in kwargs if i not in copied])

        if not copied:
            rep = '{} private arguments ({}) not displayed'.format(original, priv_names)
        else:
            for k, v in copied.items():
                if k == 'self':
                    continue
                short = self._force_string_and_truncate(v, 10)
                representation = '{}={}({})'.format(k, type(v).__name__, short)
                output_list.append(representation)
            rep = ', '.join(output_list)

        if copied and len(copied) != original:
            num_priv = original-len(copied)
            rep += '. {} private arguments ({}) not displayed'.format(num_priv, priv_names)

        return rep + '.'

    def generate_log(self, where, returned, function, call_type, trace=False, extra=None, idx=None):
        """
        General log string and data for before, after or error in function
        """
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

        return_value = self._represent_return_value(returned)
        unformatted = FORMS.get(where)

        modul = getattr(function, '__module__', 'modul')
        if modul == 'loggo.loggo':
            return

        # get all the data to be fed into the strings
        forms = dict(modul=modul,
                     function=getattr(function, '__name__', 'func'),
                     callable=call_type,
                     nargs=self.nargs,
                     nkwargs=self.nkwargs,
                     return_value=return_value,
                     kwa=self.safe_arg_display(extra),
                     return_type=type(returned).__name__)

        # if you got was an initialised exception, put in kwargs:
        if isinstance(returned, Exception):
            forms['error_type'] = returned.__class__.__name__
            forms['error_string'] = str(returned)

        formed = unformatted.format(**forms)

        # logs contain three things: a message string, a log level, and a dict of
        # extra data. there are three methods for these, which may be overwritten
        # by subclassing if you want
        msg = self.get_msg(returned, formed)
        level = self.get_alert(returned)
        log_data = self.get_log_data(returned, forms)

        if trace:
            log_data['traceback'] = traceback.format_exception(*trace)

        original_state = bool(self.stopped)
        self.stopped = False
        log_data['deco'] = idx
        self.log(msg, level, log_data)
        self.stopped = original_state

    def get_msg(self, returned, existing):
        """
        Get a message to append to the main one.
        Override/extend this method if you have a different kind of object
        """
        msg = getattr(self, 'msg', None)
        if not msg:
            return existing
        return '{old}: {new}'.format(old=existing, new=msg)

    def get_alert(self, returned):
        """
        Get an alert level from either self or returned
        Override/extend this method if you have a different kind of object
        """
        first_try = getattr(self, 'alert', -1)
        if first_try != -1:
            return first_try
        return 'dev' if isinstance(returned, Exception) else None

    def get_log_data(self, returned, forms):
        """
        Get a dict of log data from either self or pass your own in
        Override/extend this method if you have a different kind of object
        """
        data = dict(forms)
        data['returned'] = returned
        if isinstance(returned, dict):
            data.update(returned)
        if hasattr(self, 'log_data') and isinstance(self.log_data, dict):
            data.update(self.log_data)
        return data

    @staticmethod
    def _format_traceback(trace, colour=True):
        """
        Check if there is a traceback, and format it if need be
        """
        if not trace or trace in ['False', 'None']:
            return False
        if colour:
            start = COLOUR_MAP.get('critical', '')
            end = COLOUR_MAP.get('end', '')
            trace = '{}{}{}'.format(start, trace, end)
        return '\t' + trace.replace('\n', '\n\t')

    def _build_string(self, msg, level, log_data, truncate=0, colour=True, include_data=True):
        """
        Make a single line string, or multiline if traceback provided, for print
        and file logging
        """
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        trace = self._format_traceback(log_data.get('traceback', ''), colour=colour)
        log_data = {k: v for k, v in log_data.items() if k != 'traceback'}
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
        if not self.ip or not self.port or not graypy: # pylint: disable=no-member
            self.log('Graylog not configured! Disabling it', 'dev')
            return
        handler = graypy.GELFHandler(self.ip, self.port, debugging_fields=False) # pylint: disable=no-member
        self.logger.addHandler(handler)

    def _force_string_and_truncate(self, obj, max_length=30000):
        """
        Return stringified and truncated obj, or log alert if not possible
        """
        typ = type(obj).__name__
        if isinstance(obj, (list, set, tuple)):
            obj = ', '.join([str(i) for i in obj])
            obj = '{typ}({obj})'.format(typ=typ, obj=obj)
        try:
            obj = str(obj)
        except Exception as error:
            log_data = dict(error=error)
            # if it wasn't made into string, let's log and ignore
            self.log('Object could not be cast to string', 'dev', log_data)
            return '<<Unstringable input>>'
        if len(obj) > max_length:
            obj = obj[:max_length] + '...'
        return obj

    def _stringify_dict(self, input_data):
        """
        Ensure that keys and values in a dict are strings
        """
        string_data = dict()
        if not isinstance(input_data, dict):
            input_data = dict(data=input_data)
        for key, value in input_data.items():
            string_key = self._force_string_and_truncate(key)
            string_value = self._force_string_and_truncate(value)
            string_data[string_key] = string_value
        return string_data

    def _remove_private_keys(self, dictionary):
        """
        names that could have sensitive data need to be removed
        """
        return {k: v for k, v in dictionary.items() if k not in self.private_data}

    def _rename_protected_keys(self, log_data):
        """
        Some names cannot go into logger; remove them here and log the problem
        """
        out = dict()
        # names that logger will not like
        protected = {'name', 'message', 'asctime', 'msg', 'module', 'args'}
        for key, value in log_data.items():
            if key in protected:
                self.log('WARNING: Should not use key "{}" in log data'.format(key), 'dev')
                key = 'protected_' + key
            out[key] = value
        return out

    def sanitise(self, message, data=None):
        """
        Make message and data safe for logging
        """
        message = self._force_string_and_truncate(message)
        if data is None:
            data = dict()
        elif not isinstance(data, dict):
            data = dict(data=data)
        data = self._remove_private_keys(data)
        data = self._rename_protected_keys(data)
        data = self._stringify_dict(data)
        return message, data

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

    def log(self, message, alert=None, data=None, **kwargs):
        """
        Main logging method. Takes message string, alert level, and a data dict
        that will be logged. anything (accidentally) passed as kwargs will get
        merged into the data dictionary
        """

        if self.stopped:
            return

        alert, data = self.compatibility_hack(alert, data)

        # correct a bad call signature, when an interpretable level was not passed
        # in as the second argument.
        if isinstance(alert, dict):
            alert.update(kwargs)
            if isinstance(data, dict):
                alert.update(data)
            if alert.get('error'):
                log_level = 'dev'
            else:
                log_level = alert.pop('alert', 'INFO')
            return self.log(message, log_level, alert)

        # data and kwargs together will become the extra dict for the logger
        # kwargs take precedence over data in the case of duplicate keys, because
        # kwargs are more likely to have been explicitly passed in
        data = dict() if data is None else data
        kwargs.update(data)
        data = kwargs

        # translate log levels to an integer
        log_level = 20
        if isinstance(alert, str):
            log_level = getattr(logging, LOG_LEVELS.get(alert, 'INFO'))
        elif isinstance(alert, int):
            log_level = alert

        # do all preprocessing of log data, like casting, truncation, etc.
        # then do printing, filelogging and actual logging as per options.
        # all failures will result in emergency log, which falls back to
        # whatever it can (i.e. print) and which stops infinite loops
        try:
            message, string_data = self.sanitise(message, data)
            opts = dict(truncate=self.line_length, include_data=False)
            single_string = self._build_string(message, alert, string_data, **opts)
            plain_string = self._build_string(message, alert, string_data, colour=False)
            string_data.pop('traceback', None)

            if self.do_print:
                print(colour_msg(single_string, alert))

            if self.do_write:
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
            if msg != error_msg:
                self.log(error_msg, 'dev')
                last_chance = getattr(exception, 'message', 'Unknown error in emergency log')
                self.log(str(last_chance), 'dev')
            else:
                print(msg)
                print('Exiting because the system is in infinite loop')
                error_msg = str(getattr(exception, 'message', exception))
                print(error_msg)
                quit()
        except Exception as error:
            print('Emergency log exception')
            print(str(error))
            quit()
