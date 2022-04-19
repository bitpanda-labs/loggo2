from typing import Mapping, Optional
from unittest.mock import patch

import pytest

from loggo2 import Loggo

strings: Mapping[str, str] = {
    "called": "Log string {call_signature}",
    "returned": "Log string for return",
    "errored": "Log string on exception",
}

custom_strings = Loggo(log_if_graylog_disabled=False, **strings)

nocalled: Mapping[str, Optional[str]] = {
    "called": None,
    "returned": "Log string for return",
    "returned_none": "Returned none!",
    "errored": "Log string on exception",
}

no_return: Mapping[str, Optional[str]] = {"called": "called fine", "returned": None, "returned_none": None}

custom_none_string = Loggo(log_if_graylog_disabled=False, **nocalled)

custom_no_return = Loggo(log_if_graylog_disabled=False, **no_return)


# custom message test data
@custom_strings
def custom_success():
    return 1


@custom_strings
def custom_none_user_returned():
    return


@custom_strings
def custom_fail():
    raise ValueError("Boom!")


@custom_none_string
def custom_none_default():
    return


@custom_no_return
def custom_without_return():
    return 1


class TestCustomStrings:
    def test_pass(self):
        with patch("logging.Logger.log") as logger:
            n = custom_success()
            assert n == 1
            assert logger.call_count == 2
            (alert, logged_msg), extras = logger.call_args_list[0]
            assert logged_msg == "Log string custom_success()"
            (alert, logged_msg), extras = logger.call_args_list[1]
            assert logged_msg == "Log string for return"

    def test_user_default_none(self):
        with patch("logging.Logger.log") as logger:
            n = custom_success()
            assert n == 1
            assert logger.call_count == 2
            (alert, logged_msg), extras = logger.call_args_list[0]
            assert logged_msg == "Log string custom_success()"
            (alert, logged_msg), extras = logger.call_args_list[1]
            assert logged_msg == "Log string for return"

    def custom_none_default(self):
        with patch("logging.Logger.log") as logger:
            n = custom_success()
            assert n == 1
            assert logger.call_count == 1
            (alert, logged_msg), extras = logger.call_args_list[1]
            assert logged_msg == "Log string for return"

    def test_fail(self):
        with patch("logging.Logger.log") as logger:
            with pytest.raises(ValueError):
                custom_fail()
            assert logger.call_count == 2
            (alert, logged_msg), extras = logger.call_args_list[0]
            assert logged_msg == "Log string custom_fail()"
            (alert, logged_msg), extras = logger.call_args_list[1]
            assert logged_msg == "Log string on exception"
            assert alert == 20

    def test_no_return_string(self):
        with patch("logging.Logger.log") as logger:
            n = custom_without_return()
            assert n == 1
            assert logger.call_count == 1
            (alert, logged_msg), extras = logger.call_args_list[0]
            assert logged_msg == "called fine"
