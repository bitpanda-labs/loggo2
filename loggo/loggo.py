"""
A general logger
"""
import inspect
import logging
import os
from datetime import datetime

from .config import LOG_LEVELS as log_levels

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
                      greendim=Style.DIM+Fore.GREEN,
                      end=Style.RESET_ALL)
except ImportError:
    COLOUR_MAP = dict()

def colour_msg(msg, alert):
    """
    Try to colour a message, if we can
    """
    if alert is None:
        alert = COLOUR_MAP.get('greendim', '')
    else:
        alert = COLOUR_MAP.get(alert, '')
    return '{colour}{msg}\x1b[0m'.format(colour=alert, msg=msg)

class Loggo(object):
    """
    A generalised logger for daemonKit and Transaction2
    """

    def __init__(self, facility='loggo', ip=None, port=None, do_print=True, do_write=False, **kwargs):
        """
        Settomgs can be passed in from config.SETTINGS
        """
        from .decorator import logme
        from .exception import LoggedException
        # copy all the args and kwargs into a dict for extra logging into
        self.log_data = locals().copy()
        self.facility = facility
        self.ip = ip
        self.port = port
        self.do_print = do_print
        self.do_write = do_write
        self.kwargs = kwargs
        # this is a way to provide a loggable exception
        self.LoggedException = LoggedException
        # the below is to be used as a decorator function
        self.logme = logme

        # build logger object and add graylog support if possible
        self.logger = logging.getLogger(self.facility) # pylint: disable=no-member
        self.logger.setLevel(logging.DEBUG)
        self.add_handler()

    def get_logfile_path(self):
        """
        Subclass and change this if you like
        """
        fpath = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
        logpath = os.path.join('..', fpath, 'logs')
        if not os.path.exists(logpath):
            os.makedirs(logpath)
        return os.path.join(logpath, 'log.txt')

    def _build_string(self, msg, level, log_data):
        tstamp = datetime.now().strftime('%d.%m %Y %H:%M:%S')
        datapoints = [tstamp, msg, level, log_data]
        return '\t'.join([str(s) for s in datapoints])

    def write_to_file(self, line):
        with open(self.get_logfile_path(), 'a') as fo:
            fo.write('\t'.join(line))

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
            if not any(key in i for i in private):
                if isinstance(value, dict):
                    value = self._remove_private_keys(value)
                out['protected_' + key] = value
        return out

    def _remove_protected_keys(self, log_data):
        """
        Some names cannot go into logger; remove them here and log the problem
        """
        out = dict()
        # names that logger will not like
        protected = {'name', 'message', 'asctime', 'msg', 'module'}
        for key, value in log_data.items():
            if key in protected:
                self.log('Should not use key {} in log data'.format(key), 'dev')
                key = 'protected_' + key
            out[key] = value
        return out

    def _parse_input(self, alert, log_data):
        """
        For compatibility reasons, the user can pass arguments to log in a many
        different ways.

        Returns:
            log_data (dict): key-value pairs for graylog
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
        string_data = self._stringify_dict(data)
        return message, string_data

    def log(self, message, alert=None, data=None, **kwargs):
        """
        Main logging method. Takes message string, alert level, a dict
        """
        try:
            data = self._parse_input(alert, data)
            message, string_data = self.sanitise(message, data)
            single_string = self._build_string(message, alert, string_data)

            if self.do_write: # pylint: disable=no-member
                self.write_to_file(single_string)

            if self.do_print: # pylint: disable=no-member
                print(colour_msg(single_string, alert))

            log_level = getattr(logging, log_levels.get(alert, 'INFO'))
            self.logger.log(log_level, message, extra=string_data)

        except Exception as error:
            self._emergency_log('General log failure: ' + str(error), message, error)

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
