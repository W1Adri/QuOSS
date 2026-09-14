"""Marks `tests/engine` as a package, so `from .workers import ...` resolves.

Same reason as `tests/system/__init__.py` and `tests/e2e/__init__.py`: these
tests share a helper module that cannot be a second `conftest.py`, and a
relative import of a plain module only resolves inside a package. Here the
package has a second job as well — `test_parallel.py` spawns worker processes,
and a spawned worker imports the work function **by name**, so the function has
to live in a module the child can import (`engine.workers`), not in the test
module's local scope.
"""
