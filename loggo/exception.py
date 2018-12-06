from .loggo import COLOUR_MAP

try:
    from colorama import init
    init()
except ImportError:
    init = None


class LoggedException(Exception):

    log = None

    def __init__(self, message, level='dev', exception=ValueError, **kwargs):

        if LoggedException.log is None:
            raise ValueError('LoggedException not configured. Please set the log function as a class attribute.')

        message = COLOUR_MAP.get('critical', '') + message
        LoggedException.log(message, level, kwargs)
        raise exception(message) from self
