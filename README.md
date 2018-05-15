# Logging utilities for Python projects

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
from loggo import Loggo, LoggedException
# All setup values are optional
setup = dict(facility='tester',             # name of program logging the message
             ip='0.0.0.0',                  # ip for graylog
             port=9999,                     # port for graylog
             do_print=True,                 # print to console
             do_write=True,                 # write to file
             logfile='mylog.txt',           # custom path to logfile
             line_length=200,               # line truncation for console logging
             private_data=['password'],     # list of sensitive args/kwargs
             obscured='[[[PRIVATE_DATA]]]') # string with which to obscure data
Loggo = Loggo(setup)
log = Loggo.log
LoggedException.log = log
```

What you've done here is instantiated a logger with the given settings, and then attached this specific logger to the `LoggedException`

## Usage

In other parts of the project, you should then be able to access the configured logger components with:

```python
from tester import Loggo, LoggedException, log
```

### Decorators

You can use `@Loggo` as a decorator on a class, class method or function. On classes, it will log every method (same as `Loggo.everything`), on methods and functions it will log the call signature, return and errors (the same as `Loggo.logme`)

`Loggo` provides a number of specific decorators:

* `@Loggo.logme` will log the call, return and possible errors of a function/method
* `@Loggo.everything` attaches the `@Loggo.logme` decorator to all methods in a class
* `@Loggo.ignore` will not log a particular method of a class decorated by `Loggo.everything` 
* `@Loggo.errors` will only log errors, not function calls and returns

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
Mult = Multiplier(50)
result = Mult.multiply(50, 'tOpSeCrEt')
assert result == 2500 # True
```

We'll get some nice green-coloured text in the console:

```
11.05 2018 17:14:54 Called tester.multiply method with 2 args, 0 kwargs: n=int(50). 1 private arguments (password) not displayed. None
11.05 2018 17:14:54 Returned a int (2500) from tester.multiply method None
```

Notice that our private argument `password` was successfully identified and omitted. Additional information goes into `mylog.txt`, as well, but the `obscure` option `'[[[PRIVATE_DATA]]]'` is used in place of the password. If we use try to use our class with incorrect authentication:

```python
result = Mult.multiply(7, 'password123')
```

An error will raise, and we'll get extra info in the console, including a traceback:

```
11.05 2018 17:19:43 Called tester.multiply method with 2 args, 0 kwargs: n=int(7). 1 private arguments (password) not displayed.  None
11.05 2018 17:19:43 Errored with ValueError "Not authenticated! Provide password" when calling tester.multiply method with 2 args, 0 kwargs: n=int(7). 1 private arguments (password) not displayed.  ... -- see below: 
Traceback (most recent call last):
  File "/Users/danny/work/loggo/loggo/loggo.py", line 137, in full_decoration
    response = function(*args, **kwargs)
  File "tester.py", line 13, in multiply
    raise ValueError('Not authenticated!')
ValueError: Not authenticated!
```

### Log function

The standalone `log` function takes three parameters:

```python
alert_level = 'dev'
extra_data = dict(some='data', that='will', be='logged')
log('Message to log', alert_level, extra_data)
# console: 11.05 2018 17:36:24 Message to log  dev
# extra_data in log file
```

It uses the configuration that has already been defined.

### LoggedException

`LoggedException` is an `Exception` that will log itself before raising. Like other exceptions, it takes a `message` parameter, but you can also include some extra information:

```python
if True:
    alert_level = 'critical'
    raise LoggedException('Boom!', alert_level, exception=AttributeError, **kwargs)
    # 11.05 2018 17:40:05 Boom!   dev
```

Notably, you can choose the exception type to be raised. Also, any keyword arguments are treated as extra data for the logger.

## Tests

```bash
cd tests
python tests.py
```

