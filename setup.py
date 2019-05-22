import os
from setuptools import setup


def read(fname):
    """
    Helper to read README
    """
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip()


setup(
    name='loggo',
    version='4.0.0',  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT
    author='Bitpanda GmbH',
    description='Python logging tools',
    keywords='bitpanda utilities',
    packages=['loggo', 'tests'],
    long_description=read('README.md'),
    install_requires=['graypy>=1.1.2,<1.2.0'],
    python_requires='>=3.6',
    classifiers=['Topic :: Utilities'],
)
