from os import path

from setuptools import setup


def read(fname: str) -> str:
    """Helper to read README."""
    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, fname), encoding="utf-8") as f:
        return f.read()


setup(
    name="loggo",
    version="7.1.0",  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT
    author="Bitpanda GmbH",
    author_email="nosupport@bitpanda.com",
    description="Python logging tools",
    url="https://github.com/bitpanda-labs/loggo",
    keywords="bitpanda utilities logging",
    packages=["loggo"],
    package_data={"loggo": ["py.typed"]},
    zip_safe=False,  # For mypy to be able to find the installed package
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    install_requires=["typing-extensions>=3.7.4,<4.0.0; python_version<'3.8'"],
    extras_require={"graylog": ["graypy>=1.1.2,<2.0.0"]},
    python_requires=">=3.6",
    classifiers=[
        "Topic :: Utilities",
        "Typing :: Typed",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
    ],
)
