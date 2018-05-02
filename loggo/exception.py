from .config import SETTINGS
from .loggo import COLOUR_MAP

try:
    from colorama import init
    init()
except ImportError:
    init = None

def _get_logger(self, **kwargs):
    if hasattr(self, 'log'):
        return self.log
    if hasattr(self, 'logger'):
        return self.logger.log
    if 'log' in kwargs:
        return kwargs['log']
    if 'logger' in kwargs:
        return kwargs['logger'].log
    from .loggo import Loggo
    return Loggo(SETTINGS).log

def LoggedException(self, error, traceback=None, args=None, kwargs=None): # pylint: disable=invalid-name
    """
    This function is dressed up to look and behave like an exception, but is not.
    It tries to recover the best possible logger from namespace, from class, from
    keyword argument passing, or then finally builds a new one if it must.

    It then logs the message and returns an exception to be used with raise
    """
    # little hack to know if we are a function or a method

    log = _get_logger(self, **kwargs)

    if isinstance(self, str):
        message = self

    coin = getattr(self, 'coin', None)
    if coin:
        kwargs['coin'] = coin

    extras = getattr(self, 'log_data', dict())
    extras.update(kwargs)

    if args:
        extras['pased_args'] = args
    if traceback:
        extras['traceback'] = traceback

    log(str(error), 'critical', extras)
    return error

#class LoggedException(Exception):
#    def __init__(self, message, level='dev', exception=ValueError, **kwargs):
#
#        super().__init__(message)
#
#        if isinstance(self, str):
#            message = self
#            log_data = dicct()
#        else:
#            log_data = getattr(self, 'log_data', dict())
#
#        log_data.update(kwargs)
#
#        self.log = _get_logger(self, **kwargs)
#
#        message = COLOUR_MAP.get('critical', '') + message
#
#        self.log(message, level, log_data)
#
#        exception(message)
