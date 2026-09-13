"""Marks `tests/system` as a package, so `from .reference import ...` resolves.

The only test directory that needs one, because it is the only one with a shared
helper module. `reference.py` cannot be a `conftest.py` — `tests/conftest.py`
already holds that name for the whole suite and a second one collides under
`mypy` — and a relative import of a plain module only resolves inside a package.
"""
