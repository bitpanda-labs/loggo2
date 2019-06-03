[![Build Status](https://travis-ci.org/bitpanda-labs/loggo.svg?branch=master)](https://travis-ci.org/bitpanda-labs/loggo)
[![codecov.io](https://codecov.io/gh/bitpanda-labs/loggo/branch/master/graph/badge.svg)](https://codecov.io/gh/bitpanda-labs/loggo)
[![LoC](https://tokei.rs/b1/github/bitpanda-labs/loggo)](https://github.com/bitpanda-labs/loggo)

# Logging utilities for Python projects

<!--- Don't edit the version line below manually. Let bump2version do it for you. -->
> Version 5.1.0


> This module provides ways of logging the input, output and errors in classes and functions It can be hooked up to graylog, printed to console or saved to a log file. It requires very little configuration.

## Install

```
pip install loggo
# or
python setup.py install
```

## Setup

Setting up the tool as you like requires a small amount of configuration. Put this in the main `__init__.py`, or in a file called `log.py`. so you can import the same, ready-set-up logger easily. Let's call our app `tester`, so you would use `tester/__init__.py`:

```python
from loggo import Loggo
# All setup values are optional
setup = dict(facility='tester',             # name of program logging the message
             ip='0.0.0.0',                  # ip for graylog
             port=9999,                     # port for graylog
             do_print=True,                 # print to console
             do_write=True,                 # write to file
             logfile='mylog.txt',           # custom path to logfile
             line_length=200,               # line truncation for console logging
             truncation=1000,               # longest possible value in extra data
             private_data=['password'],     # list of sensitive args/kwargs
             obscured='[[[PRIVATE_DATA]]]') # string with which to obscure data
Loggo = Loggo(setup)
```

## Usage

In other parts of the project, you should then be able to access the configured logger components with:

```python
from tester import Loggo
```

### Decorators

You can use `@Loggo` as a decorator on a class, class method or function. On classes, it will log every method; on methods and functions it will log the call signature, return and errors.

Furthermore, you can use `@Loggo.ignore` to ignore a particular method of a class decorated by `@Loggo`. There is also `@Loggo.errors`, which will only log errors, not calls and returns.

For an example use, let's make a simple class that multiplies two numbers, but only if a password is supplied. We can ignore logging of the boring authentication system.

```python
@Loggo
class Multiplier(object):

    def __init__(self, base):
        self.base = base
        
    def multiply(self, n, password):
        """
        Multiply by the number given during initialisation--requires password
        """
        self.authenticated = self._do_authentication(password)
        if not self.authenticated:
            raise ValueError('Not authenticated!')
        return self.base * n

    @Loggo.ignore
    def _do_authentication(self, password):
        """Not exactly Fort Knox"""
        return password == 'tOpSeCrEt'
```

First, let's use it properly, with our secret password passed in:

```python
mult = Multiplier(50)
result = mult.multiply(50, 'tOpSeCrEt')
assert result == 2500 # True
```

We'll get some nice text in the console:

```
11.05 2018 17:14:54 *Called Multiplier.multiply(n=50, password='[PRIVATE_DATA]')
11.05 2018 17:14:54 *Returned from Multiplier.multiply(n=50, password='[PRIVATE_DATA]') with int (2500)
```

Notice that our private argument `password` was successfully obscured. If you used `do_write=True`, this log will also be in your specified log file, also with password obscured.

```python
result = Mult.multiply(7, 'password123')
```

An error will raise, a log will be generated and we'll get extra info in the console, including a traceback:

```
11.05 2018 17:19:43 *Called Multiplier.multiply(n=7, password='[PRIVATE_DATA]')
11.05 2018 17:19:43 *Errored during Multiplier.multiply(n=7, password='[PRIVATE_DATA]') with ValueError "Not authenticated!"    dev -- see below:
Traceback (most recent call last):
  File "/Users/danny/work/loggo/loggo/loggo.py", line 137, in full_decoration
    response = function(*args, **kwargs)
  File "tester.py", line 13, in multiply
    raise ValueError('Not authenticated!')
ValueError: Not authenticated!
```

### `@Loggo.events`

`@Loggo.events` allows you to pass in messages for particular events:

```python
@Loggo.events(
              called='Log string for method call',
              errored='Log string on exception',
              returned='Log string for return',
              error_level=50  # log level for errors
              )
def test():
    pass
```

### Logging without decorators

For logging manually, Loggo provides methods similar to the logging functions of the `logging` standard library: `Loggo.log`, `Loggo.debug`, `Loggo.info`, `Loggo.warning`, `Loggo.error`, `Loggo.critical`. The methods use the configuration that has already been defined. The main method `Loggo.log` takes three parameters:

```python
level = 50
msg = 'Message to log'
extra = dict(some='data', that='will', be='logged')
Loggo.log(level, msg, extra)
# console: 11.05 2018 17:36:24 Message to log  50
# extra_data in log file if `do_print` setting is True
```

Methods `Loggo.debug`, `Loggo.info`, `Loggo.warning`, `Loggo.error` and `Loggo.critical` are convenience methods for setting the log level. For instance,
```python
Loggo.warning('A message', dict(some='data'))
```
is equivalent to
```python
Loggo.log(logging.WARNING, 'A message', dict(some='data'))
```
where `logging.WARNING` is an integer constant imported from the standard library.

### Methods

You can also start and stop logging with `Loggo.start()` and `Loggo.stop()`, at any point in your code, though error logs will still get through. If you want to suppress errors too, you can pass in `allow_errors=False`.

### Context manager

You can suppress logs using a context manager. Errors are allowed here by default too:

```python
with Loggo.pause(allow_errors=False):
    do_something()
```

## Tests

```bash
python -m unittest
```

## Bumping version

Version bumps should be done using the `bump2version` utility. Install it with pip:

```bash
pip install bump2version
```

Whenever you need to bump version, in the project root directory do:

```bash
bump2version (major | minor | patch)
git push <remote> <branch> --follow-tags
```

If you don't want to remember to use the `--follow-tags` flag, you can edit your git config:

```bash
git config --global push.followTags true
```

After this you can simply push the version bump commit to remote as you would normally, and the tag will also be pushed.

## Limitations

`Loggo` uses Python's standard library (`logging`) to ultimately generate a log. There are some gotchas when using it: for instance, in terms of the extra data that can be passed in, key names for this extra data cannot clash with some internal names used within the `logging` module (`message`, `args`, etc.). To get around this, you'll get a warning that your data contains a bad key name, and it will be changed (i.e. from `message` to `protected_message`).
