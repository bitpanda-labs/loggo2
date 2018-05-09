"""
Loggo: decorators for logging
"""
import types
import inspect
import logging
import os
from datetime import datetime
import traceback

LOG_LEVELS = dict(critical='CRITICAL',
                  dev='ERROR',
                  minor='WARNING',
                  info='INFO',
                  debug='DEBUG')

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
FORMS = dict(pre='Called {modul}.{function} {callable} with {nargs} args, {nkwargs} kwargs\n',
             post='Returned a {return_type} {return_value} from {modul}.{function} {callable}\n',
             error='Errored with {error_type} "{error_string}" when calling {modul}.{function} {callable} with {nargs} args, {nkwargs} kwargs\n')

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
    def __init__(self, config):
        self.callable_type = 'function'
        self.config = config
        self.log_data = dict(config)
        self.facility = config.get('facility', 'loggo')
        self.ip = config.get('ip', None)
        self.port = config.get('port', None)
        self.do_print = config.get('do_print', True)
        self.do_write = config.get('do_write', True)
        self.logfile = config.get('logfile', './logs/logs.txt')
        self.line_length = config.get('line_length', 200)
        self.ignore_methods = config.get('ignore_methods', set())
        priv = {'token', 'password', 'prv', 'priv', 'xprv', 'secret', 'mnemonic'}
        self.private_data = config.get('private_data', priv)
        self.log = self.make_logger()
        # build logger object and add graylog support if possible
        self.logger = logging.getLogger(self.facility) # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

    def logme(self, function):
        """
        This the main decorator. After having instantiated Loggo, use it as a
        decorator like so:

        @Loggo.logme
        def f(): pass

        It will the call, return and errors that occurred during the function/method
        """

        def decorator_magic(*args, **kwargs):
            """
            This takes the args and kwargs for the decorated function
            """
            self.nargs = len(args)
            self.nkwargs = len(kwargs)
            self.log_data = dict(loggo=True, arguments=args, **kwargs)
            # pre log tells you what was called  and with what arguments
            self.generate_log('pre', None, function=function)
            try:
                # where the original function is actually run
                response = function(*args, **kwargs)
                kwargs['passed_args'] = args
                self.generate_log('post', response, function=function, **kwargs)
                return response
            except Exception as error:
                # if the function failed, you get an error log instead of a return log
                # the exception is then reraised
                kwargs['passed_args'] = args
                trace = traceback.format_exc()
                self.generate_log('error', error, trace, function=function, **kwargs)
                raise error.__class__(str(error))

        return decorator_magic

    def everything(self, cls):
        """
        Decorator for class, which attaches itself to any methods
        """
        class Decorated(cls):
            def __getattribute__(self_or_class, name):
                unwrapped = object.__getattribute__(self_or_class, name)
                if type(unwrapped) in {type(lambda x:x), type(self.__init__)}:
                    return self.logme(unwrapped)
                return unwrapped
        return Decorated

    def ignore(self, function):
        """
        A decorator that will override Loggo.everything, in case you do not want
        to log one particular method for some reason
        """
        function.do_logging = False

    def generate_log(self, where, response, trace=False, function=None, **kwargs):
        """
        General logger for before, after or error in function
        """
        # datatypes we will try to print in logs
        representable = (int, float, str, list, set, dict)
        if isinstance(response, representable):
            return_value = '({})'.format(self._force_string_and_truncate(response, 30))
        else:
            return_value = ''
        unformatted = FORMS.get(where)

        # get all the data to be fed into the strings
        forms = dict(modul=getattr(function, '__module__', 'modul'),
                     function=getattr(function, '__name__', 'func'),
                     callable=self.callable_type,
                     nargs=self.nargs,
                     nkwargs=self.nkwargs,
                     return_value=return_value,
                     return_type=type(response).__name__)

        # if you got was an initialised exception, put in kwargs:
        if isinstance(response, Exception):
            forms['error_type'] = response.__class__.__name__
            forms['error_string'] = str(response)

        formed = unformatted.format(**forms)

        # logs contain three things: a message string, a log level, and a dict of
        # extra data. there are three methods for these, which may be overwritten
        # by subclassing if you want
        msg = self.get_msg(response, formed)
        level = self.get_alert(response)
        log_data = self.get_log_data(response, forms)

        if trace:
            log_data['traceback'] = trace

        self.log(msg, level, log_data)

    def get_msg(self, response, existing):
        """
        Get a message to append to the main omne.
        Override/extend this method if you have a different kind of object
        """
        msg = getattr(self, 'msg', None)
        if not msg:
            return existing
        return '{old}: {new}'.format(old=existing, new=msg)

    def get_alert(self, response):
        """
        Get an alert level from either self or response
        Override/extend this method if you have a different kind of object
        """
        first_try = getattr(self, 'alert', -1)
        if first_try != -1:
            return first_try
        return 'dev' if isinstance(response, Exception) else None

    def get_log_data(self, response, forms):
        """
        Get a dict of log data from either self or pass your own in
        Override/extend this method if you have a different kind of object
        """
        data = dict(forms)
        if hasattr(self, 'log_data') and isinstance(self.log_data, dict):
            data.update(self.log_data)
        return data

    def _build_string(self, msg, level, log_data, truncate=0, colour=True):
        """
        Make a single line string, or multiline if traceback provided, for print
        and file logging
        """
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        # if there is a traceback, colour it or not
        trace = log_data.get('traceback', '')
        if trace:
            if colour:
                end = COLOUR_MAP.get('end', '')
                trace = '{}{}{}'.format(COLOUR_MAP.get('critical', ''), trace, end)
            trace = '\t' + trace.replace('\n', '\n\t')
        log_data = {k: v for k, v in log_data.items() if k != 'traceback'}
        datapoints = [tstamp, msg, level, log_data]
        strung = '\t' + '\t'.join([str(s).strip('\n') for s in datapoints])
        if truncate and len(strung) > truncate:
            strung = strung[:truncate] + '...'
        if trace:
            strung = '{} -- see below: \n{}\n'.format(strung, trace)
        return strung

    def write_to_file(self, line):
        """
        Very simple log writer, could expand. simple append the line to the file
        """
        if not os.path.isdir(os.path.dirname(self.logfile)):
            os.makedirs(os.path.dirname(self.logfile))
        with open(self.logfile, 'a') as fo:
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
                self.log('Should not use key {} in log data'.format(key), 'dev')
                key = 'protected_' + key
            out[key] = value
        return out

    def _parse_input(self, alert, log_data):
        """
        For compatibility reasons for bitpanda, to be deprecated
        """
        if isinstance(alert, str) and alert.lower() == 'none':
            alert = None
        if not alert and not log_data:
            return dict()
        elif not alert and log_data:
            if not isinstance(log_data, dict):
                log_data = dict(log_data=str(log_data))
            return log_data
        elif alert and isinstance(log_data, dict):
            log_data = dict(log_data)
            log_data['alert'] = alert
            return log_data
        elif alert and log_data and not isinstance(log_data, dict):
            return dict(log_data=log_data, alert=alert)
        elif isinstance(alert, str) and not log_data:
            return dict(alert=alert)
        elif isinstance(alert, dict):
            return alert
        # if none of these worked, here's a fallback, but log it
        meta_data = dict(alert=alert, log_data=log_data)
        self.log('Issue parsing log input', 'dev', meta_data)
        return log_data

    def sanitise(self, message, data=None):
        """
        Make data safe for logging
        """
        message = self._force_string_and_truncate(message)

        if data is None:
            data = dict()
        elif not isinstance(data, dict):
            data = dict(data=data)
        data = self._remove_private_keys(data)
        data = self._rename_protected_keys(data)
        data = self._stringify_dict(data)
        #string_data = self._force_string_and_truncate(string_data)
        return message, data

    def make_logger(self):
        """
        Dynamically generate a logger. It has to be done this way for reasons.
        """
        def generated_log(message, alert=None, data=None, self=self, **kwargs):
            """
            Main logging method. Takes message string, alert level, a dict
            """
            try:
                data = self._parse_input(alert, data)
                message, string_data = self.sanitise(message, data)
                single_string = self._build_string(message, alert, string_data, truncate=self.line_length)
                plain_string = self._build_string(message, alert, string_data, colour=False)
                string_data.pop('traceback', None)

                if self.config.get('do_print', False):
                    print(colour_msg(single_string, alert))

                if self.config.get('do_write', False):
                    self.write_to_file(plain_string)

                log_level = getattr(logging, LOG_LEVELS.get(alert, 'INFO'))
                self.logger.log(log_level, message, extra=string_data)

            except Exception as error:
                self._emergency_log('General log failure: ' + str(error), message, error)

        return generated_log

    def _emergency_log(self, error_msg, msg, exception):  #  no cover
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
                exit(999)
        except Exception as error:
            print('Emergency log exception... gl&hf')
            print(str(error))
            exit(999)
