"""Marks `tests/viz` as a package, so `from .builders import ...` resolves.

Same reason as `tests/system/__init__.py`: the plots and the figures share one
helper module that builds `SimulationResult`s by hand, and a relative import of
a plain module only resolves inside a package.
"""
