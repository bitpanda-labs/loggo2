"""
Loggo: safe and automatable logging
"""

from contextlib import contextmanager
from functools import wraps
import inspect
import logging
import os
import pathlib
import sys
import time
import traceback
from typing import Any, Callable, Dict, Generator, Mapping, Optional, Set, Tuple, TypeVar
import uuid

if sys.version_info < (3, 8):
    from typing_extensions import Literal, TypedDict
else:
    from typing import Literal, TypedDict

# you don't need graylog installed
try:
    import graypy
except ImportError:
    graypy = None


# Types for the typechecker
CallableEvent = Literal["called", "errored", "returned", "returned_none"]
CallableOrType = TypeVar("CallableOrType", Callable, type)

# Strings to be formatted for pre function, post function and error during function
DEFAULT_FORMS: Mapping[CallableEvent, str] = dict(
    called="*Called {call_signature}",
    returned="*Returned from {call_signature} with {return_type} {return_value}",
    returned_none="*Returned None from {call_signature}",
    errored='*Errored during {call_signature} with {exception_type} "{exception_msg}"',
)

# Miscellaneous constants
LOG_LEVEL = logging.DEBUG  # Log level used for Loggo decoration logs
LOG_THRESHOLD = logging.DEBUG  # Only log when log level is this or higher
MAX_DICT_OBSCURATION_DEPTH = 5
OBSCURED_STRING = "********"
# Callables with an attribute of this name set to True will not be logged by Loggo
NO_LOGS_ATTR_NAME = "_do_not_log_this_callable"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S %Z"

# Make a dummy logging.LogRecord object, so that we can inspect what
# attributes instances of that class have.
dummy_log_record = logging.LogRecord("dummy_name", logging.INFO, "dummy_pathname", 1, "dummy_msg", {}, None)
LOG_RECORD_ATTRS = vars(dummy_log_record).keys()


class Formatters(TypedDict, total=False):
    """A dictionary of data that can be input into log messages.

    The keys can be used in log message forms e.g. "*Called
    {call_signature}". In the final log message {call_signature} will
    then be replaced by its value in this formatter dict.
    """

    call_signature: str
    callable: str
    params: str

    decorated: bool
    couplet: uuid.UUID
    number_of_params: int
    private_keys: str
    timestamp: str
    log_level: int

    # Only available if 'errored'
    traceback: str
    exception_type: str
    exception_msg: str

    # Only available if 'returned' or 'returned_none'
    return_value: str
    return_type: str


class LocalLogFormatter(logging.Formatter):
    """Formatter for file logs and stdout logs."""

    def __init__(self) -> None:
        super().__init__("%(asctime)s\t%(message)s\t%(levelno)s", DATE_FORMAT)

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        msg = super().format(record)
        traceback = getattr(record, "traceback", None)
        if traceback:
            msg += " -- see below:\n" + traceback.rstrip("\n")
        return msg


class Loggo:
    """A class for logging."""

    def __init__(
        self,
        *,  # Reject positional arguments
        called: Optional[str] = DEFAULT_FORMS["called"],
        returned: Optional[str] = DEFAULT_FORMS["returned"],
        returned_none: Optional[str] = DEFAULT_FORMS["returned_none"],
        errored: Optional[str] = DEFAULT_FORMS["errored"],
        facility: str = "loggo",
        graylog_address: Optional[Tuple[str, int]] = None,
        do_print: bool = False,
        do_write: bool = False,
        truncation: int = 7500,
        raise_logging_errors: bool = True,
        logfile: str = "./logs/logs.txt",
        private_data: Optional[Set[str]] = None,
        log_if_graylog_disabled: bool = True,
    ) -> None:
        """Initializes a Loggo object.

        On instantiation, pass in a dictionary containing the config.
        Currently accepted config values are:
        - facility: name of the app the log is coming from
        - graylog_address: A tuple (ip, port). Address for graylog.
        - logfile: path to a file to which logs will be written
        - do_print: print logs to console
        - do_write: write logs to file
        - truncation: truncate value of log data fields to this length
        - private_data: key names that should be filtered out of logging. when not
        - raise_logging_errors: should stdlib `log` call errors be suppressed or no?
        - log_if_graylog_disabled: boolean value, should a warning log be made when failing to
            connect to graylog
        """
        self._stopped = False
        self._allow_errors = True
        self._msg_forms: Dict[CallableEvent, Optional[str]] = {
            "called": called,
            "returned": returned,
            "returned_none": self._best_returned_none(returned, returned_none),
            "errored": errored,
        }
        self._truncation = truncation
        self._raise_logging_errors = raise_logging_errors
        self._private_data = private_data or set()
        self._logger = logging.getLogger(facility)
        self._logger.setLevel(LOG_THRESHOLD)

        if do_write:
            logfile = os.path.abspath(os.path.expanduser(logfile))
            # create the directory where logs are stored if it does not exist yet
            pathlib.Path(os.path.dirname(logfile)).mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(logfile, delay=True)
            file_handler.setFormatter(LocalLogFormatter())
            self._logger.addHandler(file_handler)

        if do_print:
            print_handler = logging.StreamHandler(sys.stdout)
            print_handler.setFormatter(LocalLogFormatter())
            self._logger.addHandler(print_handler)

        self._add_graylog_handler(graylog_address, log_if_disabled=log_if_graylog_disabled)

    def __call__(self, class_or_func: CallableOrType) -> CallableOrType:
        """Make Loggo object itself a decorator.

        Allow decorating either a class or a method/function, so @loggo
        can be used on both classes and functions.
        """
        if isinstance(class_or_func, type):
            return self._decorate_all_methods(class_or_func)
        if self._can_decorate(class_or_func):
            return self._logme(class_or_func)
        return class_or_func

    @staticmethod
    def _get_timestamp() -> str:
        """Return current time as a string.

        Formatted as follows: "2019-07-17 09:35:06 CEST".
        """
        return time.strftime(DATE_FORMAT, time.localtime())

    @staticmethod
    def _best_returned_none(returned: Optional[str], returned_none: Optional[str]) -> Optional[str]:
        """Resolve the format for a log message, when a function returns None.

        If the user has their own msg format for 'returned' logs, but
        not one for 'returned_none', we should use theirs over loggo's
        default.
        """
        # if the user explicitly doesn't want logs for returns, set to none
        if not returned_none or not returned:
            return None
        # if they provided their own, use that
        if returned_none != DEFAULT_FORMS["returned_none"]:
            return returned_none
        # if the user just used the defaults, use those
        if returned == DEFAULT_FORMS["returned"]:
            return returned_none
        # the switch: use the user provided returned for returned_none
        return returned

    @staticmethod
    def _can_decorate(candidate: Callable, name: Optional[str] = None) -> bool:
        """Decide if we can decorate a given callable.

        Don't decorate python magic methods.
        """
        name = name or getattr(candidate, "__name__", None)
        if not name:
            return False
        if name.startswith("__") and name.endswith("__"):
            return False
        return True

    def _decorate_all_methods(self, cls: type, just_errors: bool = False) -> type:
        """Decorate all viable methods in a class."""
        members = inspect.getmembers(cls)
        members = [(k, v) for k, v in members if callable(v) and self._can_decorate(v, name=k)]
        for name, candidate in members:
            deco = self._logme(candidate, just_errors=just_errors)
            # somehow, decorating classmethods as staticmethods is the only way
            # to make everything work properly. we should find out why, some day
            if isinstance(vars(cls)[name], (staticmethod, classmethod)):
                # Make mypy ignore due to an open issue: https://github.com/python/mypy/issues/5530
                deco = staticmethod(deco)  # type: ignore
            try:
                setattr(cls, name, deco)
            # AttributeError happens if we can't write, as with __dict__
            except AttributeError:
                pass
        return cls

    @contextmanager
    def pause(self, allow_errors: bool = True) -> Generator[None, None, None]:
        """A context manager that prevents loggo from logging in that context.

        By default, errors will still make it through, unless
        allow_errors==False
        """
        original = self._allow_errors, self._stopped
        self._stopped = True
        self._allow_errors = allow_errors
        try:
            yield
        finally:
            self._allow_errors, self._stopped = original

    def stop(self, allow_errors: bool = True) -> None:
        """Stop loggo from logging.

        By default still log raised exceptions.
        """
        self._stopped = True
        self._allow_errors = allow_errors

    def start(self, allow_errors: bool = True) -> None:
        """Continue logging after a call to `stop` or inside a `pause`."""
        self._stopped = False
        self._allow_errors = allow_errors

    @staticmethod
    def ignore(function: Callable) -> Callable:
        """A decorator that will override Loggo class decorator.

        If a class is decorated with @loggo, logging can still be
        disabled for certain methods using this decorator.
        """
        setattr(function, NO_LOGS_ATTR_NAME, True)
        return function

    def errors(self, class_or_func: CallableOrType) -> CallableOrType:
        """
        Decorator: only log errors within a given method
        """
        if isinstance(class_or_func, type):
            return self._decorate_all_methods(class_or_func, just_errors=True)
        return self._logme(class_or_func, just_errors=True)

    def _logme(self, function: Callable, just_errors: bool = False) -> Callable:
        """A decorator for automated input/output logging.

        Used by @loggo and @loggo.errors decorators. Makes a log when a
        callable is called, returns, or raises. If `just_errors` is
        True, only logs when a callable raises.
        """
        # if logging has been turned off, just do nothing
        if getattr(function, NO_LOGS_ATTR_NAME, False):
            return function

        @wraps(function)
        def full_decoration(*args: Any, **kwargs: Any) -> Any:
            """Main decorator logic.

            Generate a log before running the callable, then try to run
            it. If it errors, log the error. If it doesn't, log the
            return value.
            """
            bound = self._params_to_dict(function, *args, **kwargs)
            if bound is None:
                self.warning(
                    "Failed getting function signature, or coupling arguments with signature's parameters",
                    extra={"callable_name": getattr(function, "__qualname__", "unknown_callable")},
                )
                return function(*args, **kwargs)

            param_strings = self.sanitise(bound)
            formatters = self._make_call_signature(function, param_strings)
            privates = [key for key in param_strings if key not in bound]

            # add more format strings
            more = Formatters(
                decorated=True,
                couplet=uuid.uuid1(),
                number_of_params=len(args) + len(kwargs),
                private_keys=", ".join(privates),
                timestamp=self._get_timestamp(),
            )
            formatters.update(more)

            # 'called' log tells you what was called and with what arguments
            if not just_errors:
                self._generate_log("called", None, formatters, param_strings)

            try:
                # where the original function is actually run
                response = function(*args, **kwargs)
            # handle any possible error in the original function
            except Exception as error:
                formatters["traceback"] = traceback.format_exc()
                self._generate_log("errored", error, formatters, param_strings)
                raise
            where: CallableEvent = "returned_none" if response is None else "returned"
            # the successful return log
            if not just_errors:
                self._generate_log(where, response, formatters, param_strings)
            # return whatever the original callable did
            return response

        return full_decoration

    def _string_params(self, non_private_params: Mapping, use_repr: bool = True) -> Dict[str, str]:
        """Turn every entry in log_data into truncated strings."""
        params = dict()
        for key, val in non_private_params.items():
            truncation = self._truncation if key not in {"trace", "traceback"} else None
            safe_key = self._force_string_and_truncate(key, 50, use_repr=False)
            safe_val = self._force_string_and_truncate(val, truncation, use_repr=use_repr)
            params[safe_key] = safe_val
        return params

    @staticmethod
    def _make_call_signature(function: Callable, param_strings: Mapping[str, str]) -> Formatters:
        """Represent the call as a string mimicking how it is written in
        Python.

        Return it within a dict containing some other format strings.
        """
        signature = "{callable}({params})"
        param_str = ", ".join(f"{k}={v}" for k, v in param_strings.items())
        format_strings = Formatters(
            callable=getattr(function, "__qualname__", "unknown_callable"), params=param_str
        )
        format_strings["call_signature"] = signature.format(**format_strings)
        return format_strings

    def listen_to(loggo_self, facility: str) -> None:
        """Listen to logs from another logger and make loggo log them.

        This method can hook the logger up to anything else that logs
        using the Python logging module (i.e. another logger) and steals
        its logs. This can be useful for instance for logging logs of a
        library using a shared Loggo configuration.
        """

        class LoggoHandler(logging.Handler):
            def emit(handler_self, record: logging.LogRecord) -> None:
                extra = {k: v for k, v in vars(record).items() if k not in LOG_RECORD_ATTRS}
                extra["sublogger"] = facility
                loggo_self.log(record.levelno, record.msg, extra)

        other_logger = logging.getLogger(facility)
        other_logger.setLevel(LOG_THRESHOLD)
        other_logger.addHandler(LoggoHandler())

    @staticmethod
    def _params_to_dict(function: Callable, *args: Any, **kwargs: Any) -> Optional[Mapping]:
        """Turn args and kwargs into an OrderedDict of {param_name: value}.

        Returns None if getting the signature, or binding arguments to
        the signature's parameters fails.
        """
        try:
            sig = inspect.signature(function)
        except ValueError:
            return None

        try:
            bound_obj = sig.bind(*args, **kwargs)
        except TypeError:
            return None

        bound = bound_obj.arguments
        if bound:
            first = list(bound)[0]
            if first == "self":
                bound.pop("self")
            elif first == "cls":
                bound.pop("cls")
        return bound

    def _obscure_private_keys(self, log_data: Any, dict_depth: int = 0) -> Any:
        """Obscure any private values in a dictionary recursively."""
        if not isinstance(log_data, dict) or dict_depth >= MAX_DICT_OBSCURATION_DEPTH:
            return log_data

        out = dict()
        for key, value in log_data.items():
            if key in self._private_data:
                out[key] = OBSCURED_STRING
            else:
                out[key] = self._obscure_private_keys(value, dict_depth + 1)
        return out

    def _represent_return_value(self, response: Any) -> str:
        """Make a string representation of whatever a method returns."""
        # some custom handling for request response objects
        if str(type(response)) == "<class 'requests.models.Response'>":
            response = response.text

        return "({})".format(self._force_string_and_truncate(response, truncate=None, use_repr=True))

    def _generate_log(
        self, where: CallableEvent, returned: Any, formatters: Formatters, safe_log_data: Mapping[str, str]
    ) -> None:
        """Generate message, level and log data for automated logs.

        - msg (str): the unformatted message
        - returned (ANY): what the decorated callable returned
        - formatters (dict): dict containing format strings needed for message
        - safe_log_data (Mapping): A mapping of stringified, truncated, censored parameters
        """
        # if the user turned off logs of this type, do nothing immediately
        msg = self._msg_forms[where]
        if not msg:
            return

        # if errors not to be shown and this is an error, quit
        if not self._allow_errors and where == "errored":
            return

        # if state is stopped and not an error, quit
        if self._stopped and where != "errored":
            return

        # do not log loggo, because why would you ever want that?
        if "loggo.loggo" in formatters["call_signature"]:
            return

        # return value for log message
        if where in {"returned", "returned_none"}:
            ret_str = self._represent_return_value(returned)
            formatters["return_value"] = ret_str
            formatters["return_type"] = type(returned).__name__

        # if what is 'returned' is an exception, get the error formatters
        if where == "errored":
            formatters["exception_type"] = type(returned).__name__
            formatters["exception_msg"] = str(returned)
        formatters["log_level"] = LOG_LEVEL

        # format the string template
        msg = msg.format(**formatters).replace("  ", " ")

        # make the log data
        log_data = {**formatters, **safe_log_data}
        custom_log_data = self.add_custom_log_data()
        log_data.update(custom_log_data)

        # record if logging was on or off
        original_state = self._stopped
        # turn it on just for now, as if we shouldn't log we'd have returned
        self._stopped = False
        try:
            self.log(LOG_LEVEL, msg, extra=log_data, safe=True)
        finally:
            # restore old stopped state
            self._stopped = original_state

    def add_custom_log_data(self) -> Dict[str, str]:
        """An overwritable method useful for adding custom log data."""
        return dict()

    def _add_graylog_handler(self, address: Optional[Tuple[str, int]], log_if_disabled: bool) -> None:
        if not graypy:
            if address:
                raise ValueError("Misconfiguration: Graylog configured but graypy not installed")
            return

        if not address:
            if log_if_disabled:
                self.warning("Graypy installed, but Graylog not configured! Disabling it")
            return

        handler = graypy.GELFUDPHandler(*address, debugging_fields=False)
        self._logger.addHandler(handler)

    def _force_string_and_truncate(self, obj: Any, truncate: Optional[int], use_repr: bool = False) -> str:
        """Return stringified and truncated obj.

        If stringification fails, log a warning and return the string
        '<<Unstringable input>>'
        """
        try:
            obj = str(obj) if not use_repr else repr(obj)
        except Exception as exc:
            self.warning(
                "Object could not be cast to string", extra=dict(exception_type=type(exc), exception=exc)
            )
            return "<<Unstringable input>>"
        if truncate is None:
            return obj
        # truncate and return
        return (obj[:truncate] + "...") if len(obj) > (truncate + 3) else obj

    @staticmethod
    def _rename_protected_keys(log_data: Mapping) -> Dict:
        """Rename log data keys with valid names.

        Some names cannot go into logger. Rename the invalid keys with a
        prefix before logging.
        """
        out = dict()
        # Names that stdlib logger will not like. Based on [1]
        # [1]: https://github.com/python/cpython/blob/04c79d6088a22d467f04dbe438050c26de22fa85/Lib/logging/__init__.py#L1550  # noqa: E501
        protected = {"message", "asctime"} | LOG_RECORD_ATTRS
        for key, value in log_data.items():
            if key in protected:
                key = "protected_" + key
            out[key] = value
        return out

    def sanitise(self, unsafe_dict: Mapping, use_repr: bool = True) -> Dict[str, str]:
        """Ensure that log data is safe to log.

        - No private keys
        - Rename protected keys
        - Everything strings
        """
        obscured = self._obscure_private_keys(unsafe_dict)
        no_protected = self._rename_protected_keys(obscured)
        return self._string_params(no_protected, use_repr=use_repr)

    def sanitise_msg(self, msg: str) -> str:
        """Overwritable method to clean or alter log messages."""
        return msg

    def log(self, level: int, msg: str, extra: Mapping = None, safe: bool = False) -> None:
        """Main logging method, called both in auto logs and manually by user.

        level: int, priority of log
        msg: string to log
        extra: dict of extra fields to log
        safe: do we need to sanitise extra?
        """
        # don't log in a stopped state
        if self._stopped:
            return

        if extra is None:
            extra = dict()
        else:  # Make a copy of the user input to not mutate the original
            extra = dict(extra)

        if not safe:
            extra = self.sanitise(extra, use_repr=False)
            msg = self.sanitise_msg(msg)

        extra.update(dict(log_level=str(level), loggo="True"))

        try:
            self._logger.log(level, msg, extra=extra)
        # The log call shouldn't ever fail, because of the way we rename protected
        # keys in `extra`. For the paranoid, we still keep the option to swallow
        # any unexpected errors (due to possible bugs in a 3rd party Handler etc.).
        except Exception:
            if self._raise_logging_errors:
                raise

    def debug(self, *args: Any, **kwargs: Any) -> None:
        return self.log(logging.DEBUG, *args, **kwargs)

    def info(self, *args: Any, **kwargs: Any) -> None:
        return self.log(logging.INFO, *args, **kwargs)

    def warning(self, *args: Any, **kwargs: Any) -> None:
        return self.log(logging.WARNING, *args, **kwargs)

    def error(self, *args: Any, **kwargs: Any) -> None:
        return self.log(logging.ERROR, *args, **kwargs)

    def critical(self, *args: Any, **kwargs: Any) -> None:
        return self.log(logging.CRITICAL, *args, **kwargs)
