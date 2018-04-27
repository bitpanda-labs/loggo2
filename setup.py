import os
from setuptools import setup

def read(fname):
    """
    Helper to read README
    """
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip()

setup(
    name='loggo',
    version=read('VERSION'),
    author='Danny McDonald',
    author_email='daniel.mcdonald@bitpanda.com',
    description=('Python logging tools'),
    keywords='bitpanda utilities',
    packages=['loggo', 'tests'],
    long_description=read('README.md'),
    install_requires=[],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Topic :: Utilities',
    ],
)
