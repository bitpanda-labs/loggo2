import os

from setuptools import setup


def read(fname):
    """
    Helper to read README
    """
    return open(os.path.join(os.path.dirname(__file__), fname)).read().strip()


setup(
    name="loggo",
    version="6.0.1",  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT
    author="Bitpanda GmbH",
    author_email="nosupport@bitpanda.com",
    description="Python logging tools",
    url="https://github.com/bitpanda-labs/loggo",
    keywords="bitpanda utilities",
    packages=["loggo"],
    package_data={"loggo": ["py.typed"]},
    zip_safe=False,  # For mypy to be able to find the installed package
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    install_requires=["graypy>=1.1.2,<1.2.0", "typing-extensions>=3.7.4,<4.0.0"],
    python_requires=">=3.6",
    classifiers=["Topic :: Utilities"],
)
