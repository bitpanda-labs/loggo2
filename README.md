# Logging utilities for Python projects

> This module provides ways of logging the input, output and errors in classes and functions It can be hooked uo to graylog, printed to console or saved to a log file. It requires very little configuration.

## Install

```
pip install loggo
```

## Setup

Setting up the tool as you like requires a small amount of configuration. Put this in the main `__init__.py`. so you can import the same, ready-set-up logger easily. Let's call our app `tester`, so you would use `tester/__init__.py`


```python
from loggo import Loggo, LoggedException
#You need to make/import a `dict` object with these attribute names and values
log_setup = dict(facility='Example', ip='0.0.0.0', port=9999, do_print=True, do_write=True)
Loggo.setup(log_setup)
```

### Usage

In other parts of the project, you should then be able to access the configured logger with:

```python
from tester import Loggo, LoggedException
```

#### Decorate a funtion or method

Then, you can use it to decorate classes, functions and methods

```python
# A decorated function:
@Loggo
def multiply(a, b=False):
    """Raise an error if B not given"""
    if not isinstance(b, (int, float)):
        raise TypeError('b needs to be an integer or float!')
    return a * b
```

We can run this function and ensure that it behaved as expected:

```python
res = multiply(7, b=8)
assert 56 == res
```
 d
Because we enabled printing and logging to file, we can see their contents, which describe the running and returning of a function,
the log level in these cases `None`, and a dictionary of extra information.

Console output (should be colourised)

```
03.05 2018 10:34:31 Called app.tester.multiply function with 1 args, 1 kwargs   None    {'facility': 'Example', 'ip': 'None', 'port': 'None', 'do_print': 'True', 'do_write': 'True'}
03.05 2018 10:34:31 Returned a int (56) from app.tester.multiply function       None    {'facility': 'Example', 'ip': 'None', 'port': 'None', 'do_print': 'True', 'do_write': 'True', 'b': '8'}
```

`log.txt`:

```
```

#### Error handling

Loggo automatically logs errors before raising them. If we throw an error for the function defined earlier, we can see the error output in both the console and `log.txt`. Note that for the sake of readability, exceptions are printed over numerous lines.

```python
# throws an error because it lacks a keyword arg
res = multiply(7)
```

Console output (when `do_write` is set:

```
```

`log.txt` (when the `do_print` is set):

```python

```


### Decorate all methods in a class

You can also use Loggo to automatically log all methods in a given class. All you need to do is use the `@Loggo.everything` pattern:

```python
@Loggo.everything
class DummyClass(object):
    """
    A class with regular methods, static methods and errors
    """

    def add(self, a, b):
        """Simple case, add two things"""
        return a + b

    def positive_math(self, a, b, c=False):
        """Random math that allows an exception, uses keyword argument"""
        added = a + b
        if c:
            added = added - c
        if added < 0:
            raise ValueError('Only works with positive outputs!')
        return added

    @staticmethod
    def static_method(number):
        """Works for static/class methods too"""
        return number*number
```

Each of these methods is now decorated using `Loggo`. So if we run a method, we can see that it still works

```python
res = DummyClass().add(3, 4)
assert res == 7
```

Console output (when `do_write` is set:

```
```

`log.txt` (when the `do_print` is set):

```

```

And for an error log:

```python

```


