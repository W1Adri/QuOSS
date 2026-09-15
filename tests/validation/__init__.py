"""Marks `tests/validation` as a package, so `from .cases import ...` resolves.

Same reason as `tests/system/__init__.py` and `tests/e2e/__init__.py`: the files
here share a builder module that cannot be a second `conftest.py`, and a
relative import of a plain module only resolves inside a package.
"""
