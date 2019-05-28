Changelog
=========

This log should always be updated when doing backwards incompatible changes, resulting in a major version bump. Feel free to add a log for lesser version bumps as well, but for major bumps it's a must.

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
