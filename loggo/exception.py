from .loggo import COLOUR_MAP

try:
    from colorama import init
    init()
except ImportError:
    init = None

def _get_logger(self, **kwargs):
    if hasattr(LoggedException, 'log'):
        return LoggedException.log
    if hasattr(LoggedException, 'logger'):
        return LoggedException.logger.log
    if hasattr(self, 'log'):
        return self.log
    if hasattr(self, 'logger'):
        return self.logger.log
    if 'log' in kwargs:
        return kwargs['log']
    if 'logger' in kwargs:
        return kwargs['logger'].log
    # potentially should fail here!
    from .loggo import Loggo
    return Loggo.log

class LoggedException(Exception):

    def __init__(self, message, level='dev', exception=ValueError, **kwargs):
        message = COLOUR_MAP.get('critical', '') + message
        log = _get_logger(self, **kwargs)
        log(message, level, kwargs)
        raise exception(message) from self
