Changelog
=========

This log should always be updated when doing backwards incompatible changes, resulting in a major version bump. Feel free to add a log for lesser version bumps as well, but for major bumps it's a must.

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
