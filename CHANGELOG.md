Changelog
=========

This log should always be updated when doing backwards incompatible changes, resulting in a major version bump. Feel free to add a log for lesser version bumps as well, but for major bumps it's a must.

9.0.0
-----
- Changed
    - `private_data` kwarg of `Loggo.__init__` no longer accepts `None` value.
- Fixed
  - `@loggo` decorator no longer crashes when decorating a derived class

8.0.0
-----
- Removed
    - The remaining public data members of a Loggo object: `called`, `returned`, `returned_none` and `errored`
- Fixed
    - Logging calls no longer mutate extra data

7.0.0
-----
- Changed
    - Graypy dependency is not installed by default. To install with Graylog support, install with the `graylog` extra: `pip install loggo[graylog]`
    - Don't allow using @loggo.logme to decorate callables. Use @loggo instead.
    - Make Loggo.write_to_file() a private method.
    - Make Loggo init param `raise_logging_errors` default to True
    - Make loggo.loggo module private
    - Reduce a Loggo object's public data members to minimum. Only `called`, `returned`, `returned_none` and `errored` remain public now.

6.0.0
-----
- Added
    - `called`, `returned`, `returned_none` and `errored` kwargs on instantiation for custom log strings

- Changed
    - do not pass a config dict on instantiation, instead just keyword arguments
    - Graylog address is given to init as tuple named graylog_address instead of having the ip and port in separate arguments.
    - default obscured data string `[PRIVATE_DATA] -> ********`. This string is not configurable anymore.
    - default log level changed from logging.INFO to logging.DEBUG

- Removed
    - loggo.events; its functionality is still available during instantiation
    - line_length config, which was not respected anyway, and not really needed.
    - max_dict_depth config. Now always set to the previous default value 5.
    - error_level config. Now always set to the LOG_LEVEL
    - Loggo.verbose contextmanager
    - Loggo.log_errors contextmanager

5.0.0
-----
- Changed
    - `Loggo.listen_to()` no longer takes positional argument `no_graylog_disable_log`. Instead of this, the key-value-pair `'log_if_graylog_disabled': bool` can be included in the config dict when instantiating Loggo.
    - The `error_alert` kwarg of `Loggo.events()` was renamed to `error_level` and is now expected to be integer.
    - The signature `Loggo.log(self, message: str, alert: Optional[str] = None, extra: Optional[Dict] = None, safe: bool = False)` is now `Loggo.log(self, level: int, msg: str, extra: Optional[Dict] = None, safe: bool = False)`.

4.0.0
-----
- Changed
    - Drop support for Python versions lower than 3.6

3.0.0
-----
- Added
    - Added config option: `truncation (int)`, which determines extra data value max length

- Changed
    - Internals updated to allow auto-logging of static/class methods in uninstantiated classes.
    - Slight reformatting of auto-generated messages (better getting of class name, no `__main__`)

- Removed
    - Loggo.everything (the class decorator), now simply use Loggo

2.0.0
-----
- Changed
    - Major refactor, affecting numerous call signatures

- Removed
    - LoggedException
    - colours
