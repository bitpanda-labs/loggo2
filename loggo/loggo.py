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
from typing import Optional, Set, Dict, Union, Callable, Generator, Any, Mapping, Tuple

from typing_extensions import Literal, TypedDict

# you don't need graylog installed
try:
    import graypy
except ImportError:
    graypy = None


# Strings to be formatted for pre function, post function and error during function
DEFAULT_FORMS = dict(
    called="*Called {call_signature}",
    returned="*Returned from {call_signature} with {return_type} {return_value}",
    returned_none="*Returned None from {call_signature}",
    errored='*Errored during {call_signature} with {exception_type} "{exception_msg}"',
)
LOG_LEVEL = logging.DEBUG
LOG_THRESHOLD = logging.DEBUG  # Only log when log level is this or higher
MAX_DICT_OBSCURATION_DEPTH = 5
OBSCURED_STRING = "********"
# Callables with an attribute of this name set to True will not be logged by Loggo
NO_LOGS_ATTR_NAME = "_do_not_log_this_callable"


class Formatters(TypedDict, total=False):
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


CallableEvent = Literal["called", "errored", "returned", "returned_none"]


class Loggo:
    """
    A class for logging
    """

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
        raise_logging_errors: bool = False,
        logfile: str = "./logs/logs.txt",
        private_data: Optional[Set[str]] = None,
        log_if_graylog_disabled: bool = True,
    ) -> None:
        """
        On instantiation, pass in a dictionary containing the config. Currently
        accepted config values are:

        - facility: name of the app the log is coming from
        - graylog_address: A tuple (ip, port). Address for graylog.
        - logfile: path to a file to which logs will be written
        - do_print: print logs to console
        - do_write: write logs to file
        - truncation: truncate value of log data fields to this length
        - private_data: key names that should be filtered out of logging. when not
        - raise_logging_errors: should Loggo errors be allowed to happen?
        - log_if_graylog_disabled: boolean value, should a warning log be made when failing to
            connect to graylog
        """
        self.stopped = False
        self.allow_errors = True
        self.called = called
        self.returned = returned
        self.returned_none = self._best_returned_none(returned, returned_none)
        self.errored = errored
        self.facility = facility
        self.graylog_address = graylog_address
        self.do_print = do_print
        self.do_write = do_write
        self.truncation = truncation
        self.raise_logging_errors = raise_logging_errors
        self.logfile = logfile
        self.private_data = private_data or set()
        self.log_if_graylog_disabled = log_if_graylog_disabled
        self.logger = logging.getLogger(self.facility)
        self.logger.setLevel(LOG_THRESHOLD)
        self._add_graylog_handler()

    @staticmethod
    def _best_returned_none(returned: Optional[str], returned_none: Optional[str]) -> Optional[str]:
        """
        If the user has their own msg format for 'returned' logs, but not one
        for 'returned_none', we should use theirs over loggo's default
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

    def _can_decorate(self, candidate: Callable, name: Optional[str] = None) -> bool:
        """
        Decide if we can decorate a given object

        Must have non private name and be callable
        """
        name = name or getattr(candidate, "__name__", None)
        if not name:
            return False
        if name.startswith("__") and name.endswith("__"):
            return False
        if not callable(candidate):
            return False
        return True

    def _decorate_all_methods(self, cls: type, just_errors: bool = False) -> type:
        """
        Decorate all viable methods in a class
        """
        members = inspect.getmembers(cls)
        members = [(k, v) for k, v in members if self._can_decorate(v, name=k)]
        for name, candidate in members:
            deco = self.logme(candidate, just_errors=just_errors)
            # somehow, decorating classmethods as staticmethods is the only way
            # to make everything work properly. we should find out why, some day
            if isinstance(cls.__dict__[name], (staticmethod, classmethod)):
                # Make mypy ignore due to an open issue: https://github.com/python/mypy/issues/5530
                deco = staticmethod(deco)  # type: ignore
            try:
                setattr(cls, name, deco)
            # AttributeError happens if we can't write, as with __dict__
            except AttributeError:
                pass
        return cls

    def __call__(self, class_or_func: Union[Callable, type]) -> Union[Callable, type]:
        """
        Make Loggo itself a decorator of either a class or a method/function, so
        you can just use @Loggo on both classes and functions
        """
        if isinstance(class_or_func, type):
            return self._decorate_all_methods(class_or_func)
        if self._can_decorate(class_or_func):
            return self.logme(class_or_func)
        return class_or_func

    @contextmanager
    def pause(self, allow_errors: bool = True) -> Generator[None, None, None]:
        """
        A context manager that prevents loggo from logging in that context. By
        default, errors will still make it through, unless allow_errors==False
        """
        original = self.allow_errors, self.stopped
        self.stopped = True
        self.allow_errors = allow_errors
        try:
            yield
        finally:
            self.allow_errors, self.stopped = original

    def stop(self, allow_errors: bool = True) -> None:
        """
        Normal function: manually stop loggo from logging, but by default allow
        errors through
        """
        self.stopped = True
        self.allow_errors = allow_errors

    def start(self, allow_errors: bool = True) -> None:
        """
        Normal function: manually restart loggo, also allowing errors by default
        """
        self.stopped = False
        self.allow_errors = allow_errors

    @staticmethod
    def ignore(function: Callable) -> Callable:
        """
        A decorator that will override Loggo class deco, in case you do not want
        to log one particular method for some reason
        """
        setattr(function, NO_LOGS_ATTR_NAME, True)
        return function

    def errors(self, class_or_func: Union[Callable, type]) -> Union[Callable, type]:
        """
        Decorator: only log errors within a given method
        """
        if isinstance(class_or_func, type):
            return self._decorate_all_methods(class_or_func, just_errors=True)
        return self.logme(class_or_func, just_errors=True)

    def logme(self, function: Callable, just_errors: bool = False) -> Callable:
        """
        This the function decorator. After having instantiated Loggo, use it as a
        decorator like so:

        @Loggo.logme
        def f(): pass

        It will the call, return and errors that occurred during the function/method
        """

        # if logging has been turned off, just do nothing
        if getattr(function, NO_LOGS_ATTR_NAME, False):
            return function

        @wraps(function)
        def full_decoration(*args: Any, **kwargs: Any) -> Any:
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
            formatters = self._make_call_signature(function, param_strings)
            privates = [key for key in param_strings if key not in bound]

            # add more format strings
            more = Formatters(
                decorated=True,
                couplet=uuid.uuid1(),
                number_of_params=len(args) + len(kwargs),
                private_keys=", ".join(privates),
                timestamp=datetime.now().strftime("%d.%m %Y %H:%M:%S"),
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

    def _string_params(self, non_private_params: Dict, use_repr: bool = True) -> Dict[str, str]:
        """
        Turn every entry in log_data into truncated strings
        """
        params = dict()
        for key, val in non_private_params.items():
            truncation = self.truncation if key not in {"trace", "traceback"} else None
            safe_key = self._force_string_and_truncate(key, 50, use_repr=False)
            safe_val = self._force_string_and_truncate(val, truncation, use_repr=use_repr)
            params[safe_key] = safe_val
        return params

    @staticmethod
    def _make_call_signature(function: Callable, param_strings: Dict[str, str]) -> Formatters:
        """
        Represent the call as a string mimicking how it is written in Python.

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
        """
        This method can hook the logger up to anything else that logs using the
        Python logging module (i.e. another logger) and steals its logs
        """

        class LoggoHandler(logging.Handler):
            def emit(handler_self, record: logging.LogRecord) -> None:
                attributes = {
                    "msg",
                    "created",
                    "msecs",
                    "stack_info",
                    "levelname",
                    "filename",
                    "module",
                    "args",
                    "funcName",
                    "process",
                    "relativeCreated",
                    "exc_info",
                    "name",
                    "processName",
                    "threadName",
                    "lineno",
                    "exc_text",
                    "pathname",
                    "thread",
                    "levelno",
                }
                extra = dict(record.__dict__)
                [extra.pop(attrib, None) for attrib in attributes]
                extra["sublogger"] = facility
                loggo_self.log(record.levelno, record.msg, extra)

        other_loggo = logging.getLogger(facility)
        other_loggo.setLevel(LOG_THRESHOLD)
        other_loggo.addHandler(LoggoHandler())

    def _params_to_dict(self, function: Callable, *args: Any, **kwargs: Any) -> Mapping:
        """
        Turn args and kwargs into an OrderedDict of {param_name: value}
        """
        sig = inspect.signature(function)
        bound = sig.bind(*args, **kwargs).arguments
        if bound:
            first = list(bound)[0]
            if first == "self":
                bound.pop("self")
            elif first == "cls":
                bound.pop("cls")
        return bound

    def _obscure_private_keys(self, log_data: Any, dict_depth: int = 0) -> Any:
        """
        Obscure any private values in a dictionary recursively
        """
        if not isinstance(log_data, dict) or dict_depth >= MAX_DICT_OBSCURATION_DEPTH:
            return log_data

        out = dict()
        for key, value in log_data.items():
            if key in self.private_data:
                out[key] = OBSCURED_STRING
            else:
                out[key] = self._obscure_private_keys(value, dict_depth + 1)
        return out

    def _represent_return_value(self, response: Any) -> str:
        """
        Make a string representation of whatever a method returns
        """
        # some custom handling for request response objects
        if str(type(response)) == "<class 'requests.models.Response'>":
            response = response.text

        return "({})".format(self._force_string_and_truncate(response, truncate=None, use_repr=True))

    def _generate_log(
        self, where: CallableEvent, returned: Any, formatters: Formatters, safe_log_data: Dict[str, str]
    ) -> None:
        """
        generate message, level and log data for automated logs

        msg (str): the unformatted message
        returned (ANY): what the decorated callable returned
        formatters (dict): dict containing format strings needed for message
        safe_log_data (dict): dict of stringified, truncated, censored parameters
        """
        # if the user turned off logs of this type, do nothing immediately
        msg = getattr(self, where)
        if not msg:
            return

        # if errors not to be shown and this is an error, quit
        if not self.allow_errors and where == "errored":
            return

        # if state is stopped and not an error, quit
        if self.stopped and where != "errored":
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
        original_state = bool(self.stopped)
        # turn it on just for now, as if we shouldn't log we'd have returned
        self.stopped = False
        # do logging
        self.log(LOG_LEVEL, msg, extra=log_data, safe=True)
        # restore old stopped state
        self.stopped = original_state

    def add_custom_log_data(self) -> Dict[str, str]:
        """
        An overwritable method useful for adding custom log data
        """
        return dict()

    def write_to_file(self, line: str) -> None:
        """
        Very simple log writer, could expand. simple append the line to the file
        """
        needed_dir = os.path.dirname(self.logfile)
        if needed_dir and not os.path.isdir(needed_dir):
            os.makedirs(os.path.dirname(self.logfile))
        with open(self.logfile, "a") as fo:
            fo.write(line.rstrip("\n") + "\n")

    def _add_graylog_handler(self) -> None:
        if not self.graylog_address or not graypy:
            if self.log_if_graylog_disabled:
                self.warning("Graylog not configured! Disabling it")
            return
        handler = graypy.GELFUDPHandler(*self.graylog_address, debugging_fields=False)
        self.logger.addHandler(handler)

    def _force_string_and_truncate(self, obj: Any, truncate: Optional[int], use_repr: bool = False) -> str:
        """
        Return stringified and truncated obj. If stringification fails, log a warning
        and return the string '<<Unstringable input>>'
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
    def _rename_protected_keys(log_data: Dict) -> Dict:
        """
        Some names cannot go into logger; remove them here and log the problem
        """
        out = dict()
        # names that logger will not like
        protected = {"name", "message", "asctime", "msg", "module", "args", "exc_info"}
        for key, value in log_data.items():
            if key in protected:
                key = "protected_" + key
            out[key] = value
        return out

    def sanitise(self, unsafe_dict: Mapping, use_repr: bool = True) -> Dict[str, str]:
        """
        Ensure that log data is safe to log:

        - No private keys
        - Rename protected keys
        - Everything strings
        """
        obscured = self._obscure_private_keys(unsafe_dict)
        no_protected = self._rename_protected_keys(obscured)
        return self._string_params(no_protected, use_repr=use_repr)

    def sanitise_msg(self, msg: str) -> str:
        """
        Overwritable method to clean or alter log messages
        """
        return msg

    def log(self, level: int, msg: str, extra: Optional[Dict] = None, safe: bool = False) -> None:
        """
        Main logging method, called both in auto logs and manually by user

        level: int, priority of log
        msg: string to log
        extra: dict of extra fields to log
        safe: do we need to sanitise extra?
        """
        # don't log in a stopped state
        if self.stopped:
            return

        extra = extra or dict()

        if not safe:
            extra = self.sanitise(extra, use_repr=False)
            msg = self.sanitise_msg(msg)

        extra.update(dict(log_level=str(level), loggo="True"))

        # format logs for printing/writing to file
        if self.do_write or self.do_print:
            ts = extra.get("timestamp", datetime.now().strftime("%d.%m %Y %H:%M:%S"))
            line = f"{ts}\t{msg}\t{level}"
            trace = extra.get("traceback")
            if trace:
                line = f"{line} -- see below: \n{trace}\n"
        # do printing and writing to file
        if self.do_print:
            print(line)
        if self.do_write:
            self.write_to_file(line)

        try:
            self.logger.log(level, msg, extra=extra)
        # it has been known to fail, e.g. when extra contains weird stuff
        except Exception:
            if self.raise_logging_errors:
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
