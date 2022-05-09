from os import path

from setuptools import setup

EXTRAS_REQUIRE = {
    "graylog": ["graypy>=2.0.0,<3.0.0"],
    "tests": ["pytest", "pytest-randomly", "pytest-cov"],
    "lint": [
        "isort",
        "black",
        "flake8",
        "flake8-bugbear",
        "flake8-builtins",
        "flake8-comprehensions",
        "mypy",
        "docformatter",
        "pre-commit",
    ],
    "tools": ["codecov", "bump2version"],
}
# Install all dependencies for development
EXTRAS_REQUIRE["dev"] = (
    EXTRAS_REQUIRE["graylog"] + EXTRAS_REQUIRE["tests"] + EXTRAS_REQUIRE["lint"] + EXTRAS_REQUIRE["tools"]
)


def read(fname: str) -> str:
    """Helper to read README."""
    this_directory = path.abspath(path.dirname(__file__))
    with open(path.join(this_directory, fname), encoding="utf-8") as f:
        return f.read()


setup(
    name="loggo2",
    version="10.1.1",  # DO NOT EDIT THIS LINE MANUALLY. LET bump2version UTILITY DO IT
    author="Bitpanda GmbH",
    author_email="nosupport@bitpanda.com",
    description="Python logging tools",
    url="https://github.com/bitpanda-labs/loggo2",
    project_urls={"Changelog": "https://github.com/bitpanda-labs/loggo2/blob/master/CHANGELOG.md"},
    keywords="bitpanda utilities logging",
    packages=["loggo2"],
    package_data={"loggo2": ["py.typed"]},
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    install_requires=["typing-extensions>=3.7.4,<4.0.0; python_version<='3.9'"],
    extras_require=EXTRAS_REQUIRE,
    python_requires=">=3.6",
    license="MIT",
    classifiers=[
        "Topic :: Utilities",
        "Typing :: Typed",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3 :: Only",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
)
