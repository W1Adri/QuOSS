"""Orbital geometry: time scales, frames, Keplerian motion and propagation.

The deepest physics layer. Everything here is a pure function of arrays over the
time axis, with no I/O and no state, and depends only on :mod:`quoss.core`.

Read :mod:`quoss.orbits.frames` first: it fixes the time scales and the reference
frames that every other module in this package expresses its results in. See
``docs/adr/0002-frames-and-time-scales.md`` for the decisions behind it and the
error budget they imply.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""
