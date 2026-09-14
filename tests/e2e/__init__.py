"""Marks `tests/e2e` as a package, so `from .oracle import ...` resolves.

Same reason as `tests/system/__init__.py`: the end-to-end tests share a helper
module that cannot be a second `conftest.py`, and a relative import of a plain
module only resolves inside a package.
"""
