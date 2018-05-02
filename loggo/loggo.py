"""
A general logger that can be used for exceptions, classes, etc.
"""
import inspect
import logging
import os
from datetime import datetime

try:
    from .config import LOG_LEVELS as log_levels
except ImportError:
    log_levels = dict(critical='CRITICAL',
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

from .config import SETTINGS

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
    A generalised logger for daemonKit and Transaction2, maybe your project too
    """

    def __init__(self, config, **kwargs):
        """
        Settomgs can be passed in from config.SETTINGS
        """
        self.config = config
        # copy all the args and kwargs into a dict for extra logging into
        # set the main config values
        self.facility = config.get('facility', 'loggo')
        self.ip = config.get('ip', None)
        self.port = config.get('port', None)
        self.do_print = config.get('do_print', True)
        self.do_write = config.get('do_write', True)
        # store our config as extra info for logger
        self.kwargs = config.copy()
        self.kwargs.update(**kwargs)

        # build logger object and add graylog support if possible
        self.logger = logging.getLogger(self.facility) # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

    @staticmethod
    def logme(function):
        """
        Decorator for methods that logs start, end and error
        """
        from .decorator import logme as _logme
        return _logme(function, SETTINGS)

    @staticmethod
    def everything(cls):
        """
        Decorator for classes which logs evyerthing
        """
        from .class_decorator import exhaustive as _exhaustive
        return _exhaustive(cls, SETTINGS)

    @staticmethod
    def errors(function):
        """
        Decorator for functions that only logs errors
        """
        from .decorator import logme as _logme
        return _logme(function, SETTINGS, just_errors=True)


    def get_logfile_path(self):
        """
        Subclass and change this if you like
        """
        fpath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        logpath = os.path.join('..', fpath, 'logs')
        if not os.path.exists(logpath):
            os.makedirs(logpath)
        return os.path.join(logpath, 'log.txt')

    def _build_string(self, msg, level, log_data, truncate=150, colour=True):
        """
        Make a single line string, or multiline if traceback provided, for print
        and file logging
        """
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        tb = log_data.pop('traceback', '')
        if tb:
            truncate += len(tb)
            if colour:
                tb = '{}{}{}'.format(COLOUR_MAP['critical'], tb, COLOUR_MAP['end'])
            tb = '\t' + tb.replace('\n', '\n\t')
        datapoints = [tstamp, msg, level, log_data]
        strung = '\t' + '\t'.join([str(s).strip('\n') for s in datapoints])
        if len(strung) > truncate:
            strung[:truncate] + '...'
        if tb:
            strung = '{} -- see below: \n{}\n'.format(strung, tb)
        return strung

    def write_to_file(self, line):
        """
        Very simple log writer, could expand
        """
        with open(self.get_logfile_path(), 'a') as fo:
            fo.write(line)

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
        if isinstance(obj, (list, set, tuple)):
            obj = ', '.join([self._force_string_and_truncate(i) for i in obj])
        elif isinstance(obj, dict):
            obj = self._stringify_dict(obj)
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
        private = {'token', 'password', 'prv', 'priv', 'xprv', 'secret', 'mnemonic'}
        out = dict()
        for key, value in dictionary.items():
            if isinstance(value, dict):
                value = self._remove_private_keys(value)
            newname = 'protected_' + key if key in private else key
            out[newname] = value
        return out

    def _remove_protected_keys(self, log_data):
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
        # data needs to become a dict, ideally with something in it
        if data is None:
            data = dict()
        elif not isinstance(data, dict):
            data = dict(data=data)
        data.update(self.kwargs)
        data = self._remove_private_keys(data)
        data = self._remove_protected_keys(data)
        data = self._stringify_dict(data)
        #string_data = self._force_string_and_truncate(string_data)
        return message, data

    def log(self, message, alert=None, data=None, **kwargs):
        """
        Main logging method. Takes message string, alert level, a dict
        """
        try:
            data = self._parse_input(alert, data)
            message, string_data = self.sanitise(message, data)
            single_string = self._build_string(message, alert, string_data)
            plain_string = self._build_string(message, alert, string_data, colour=False)

            if self.do_print:
                print(colour_msg(single_string, alert))

            if self.do_write:
                self.write_to_file(plain_string)

            log_level = getattr(logging, log_levels.get(alert, 'INFO'))
            self.logger.log(log_level, message, extra=string_data)

        except Exception as error:
            #trace = traceback.format_exc()
            #self.log_and_raise(error, trace, **kwargs)
            self._emergency_log('General log failure: ' + str(error), message, error)

    def log_and_raise(self, error, traceback, *args, **kwargs):
        """
        Log an exception and then raise it
        """
        extras = getattr(self, 'log_data', dict())
        extras.update(kwargs)
        if args:
            extras['pased_args'] = args
        if traceback:
            extras['traceback'] = traceback
        self.log(str(error), 'critical', extras)
        raise error.__class__('[LOGGED] ' + str(error))

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
