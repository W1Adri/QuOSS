"""Marks `tests/cli` as a package, so its `conftest.py` is a module of its own.

Same reason as `tests/e2e/__init__.py` and the three beside it: without it,
`tests/conftest.py` and `tests/cli/conftest.py` are both the top-level module
`conftest`, and `mypy` refuses the duplicate before it checks anything.
"""
