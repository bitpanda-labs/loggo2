## Setup

To get started, import and instantiate the main class, ideally somewhere at the core of your project. If you have a module with multiple files, do the initial configuration in the main `__init__.py`, or in a file called `log.py`. so you can import the same, ready-set-up logger easily.

For example, if your app was called `tester`, you could add the following to `tester/__init__.py`:

```python
from loggo import Loggo

# all setup values are optional
loggo = Loggo(
    facility="tester",  # name of program logging the message
    graylog_address=("0.0.0.0", 9999),  # address for graylog (ip, port)
    do_print=True,  # print each log to console
    do_write=True,  # write each log to file
    logfile="mylog.txt",  # custom path to logfile
    line_length=200,  # line truncation for console logging
    truncation=1000,  # longest possible value in extra data
    private_data={"password"},  # set of sensitive args/kwargs
    obscured="******", # string with which to obscure data
)

```
