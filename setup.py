# Compatibility shim for pip < 21 (which doesn't support PEP 517 via pyproject.toml alone).
# All project metadata lives in pyproject.toml.
from setuptools import setup
setup()
