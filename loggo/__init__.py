"""
Simpler namespace
"""
from .exception import LoggedException
from .decorator import logme
from .loggo import Loggo
from .config import SETTINGS
Loggo = Loggo(**SETTINGS)
