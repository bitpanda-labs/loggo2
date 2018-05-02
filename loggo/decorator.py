try:
    from .config import SETTINGS
except ImportError:
    raise ImportError('Please create a config.py file in {}. '\
                       'You can can use the config.py.example file as a template.')

import traceback
from inspect import ismethod

from .loggo import Loggo

# potentially customisable messages called before, after or on error
FORMS = dict(pre='Called {module}.{function} {callable} with {nargs} args, {nkwargs} kwargs\n',
             post='Returned a {return_type} from {module}.{function} {callable}\n',
             error='Errored with {error_type} "{error_string}" when calling {module}.{function} {callable} with {nargs} args, {nkwargs} kwargs\n')

class logme(Loggo):
    """
    A decorator that logs function calls, returns and errors in between

    function is the function to be decorated
    config is the needed configuration, with default provided in config.py
    """
    def __init__(self, function=None, config=SETTINGS, just_errors=False):

        self.callable_type = 'function' if not ismethod(function) else 'class method'
        self.function = function
        self.just_errors = just_errors
        super().__init__(config)

    def __call__(self, *args, **kwargs):
        """ This part calls the decorated function, logging all the while"""
        self.nargs = len(args)
        self.nkwargs = len(kwargs)
        # an initial log
        self.generate_log('pre', None)
        try:
            response = self.function(*args, **kwargs)
            self.generate_log('post', response)
            return response
        except Exception as error:
            trace = traceback.format_exc()
            self.generate_log('error', error, trace)
            raise error.__class__('[LOGGED] ' + str(error))

    def get_msg(self, response):
        """
        Get a message to append to the main omne.
        Override/extend this method if you have a different kind of object
        """
        return getattr(self, 'msg', None)

    def get_alert(self, response):
        """
        Get an alert level from either self or response
        Override/extend this method if you have a different kind of object
        """
        first_try = getattr(self, 'alert', None)
        if first_try:
            return first_try
        return 'dev' if isinstance(response, Exception) else None

    def get_log_data(self, response):
        """
        Get a dict of log data from either self or pass your own in
        Override/extend this method if you have a different kind of object
        """
        data = dict()
        #if traceback:
        #    data['error_traceback'] = traceback
        if hasattr(self, 'log_data') and isinstance(self.log_data, dict):
            data.update(self.log_data)
        return data

    def generate_log(self, where, response, trace=False):
        """
        General logger for before, after or error in function
        """
        if self.just_errors:
            return
        unformatted = FORMS.get(where)
        # format args
        forms = dict(module=getattr(self.function, '__module__', 'modul'),
                     function=getattr(self.function, '__name__', 'func'),
                     callable=self.callable_type,
                     nargs=self.nargs,
                     nkwargs=self.nkwargs,
                     return_type=type(response).__name__)

        # if you got was an initialised exception, put in kwargs:
        if isinstance(response, Exception):
            forms['error_type'] = response.__class__.__name__
            forms['error_string'] = str(response)
        # traceback in kwargs too

        formed = unformatted.format(**forms)
        msg = self.get_msg(response)
        # add extra info to formatted sting
        msg = formed if not msg else '{old}: {new}'.format(old=formed, new=msg)
        level = self.get_alert(response)
        log_data = self.get_log_data(response)
        if trace:
            log_data['traceback'] = trace
        self.log(msg, level, log_data)
