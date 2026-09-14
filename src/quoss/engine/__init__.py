"""The orchestrator: one scenario in, one result out, and nothing added on the way.

Everything below this package is physics or bookkeeping about physics.
:mod:`quoss.orbits` places the satellite, :mod:`quoss.channel` prices the light,
:mod:`quoss.qkd` turns light into key per pulse, :mod:`quoss.system` integrates
that over a pass and a day, and :mod:`quoss.scenario` says, as a datum, which of
all those knobs a run uses. None of them runs a simulation. This package does,
and its whole claim is a negative one: **the engine computes nothing that a
person calling those modules by hand would not compute**. The end-to-end test
``tests/e2e/test_reference_scenarios.py`` proves it bit for bit against a chain
wired by hand; that is a V4 bridge (the orchestration adds and loses nothing),
not a validation of the physics.

Modules
-------
pipeline
    :func:`~quoss.engine.pipeline.run`: orbit, geometry, passes, channel, key,
    series, and the optional Monte Carlo, multi-station and relay stages, each
    timed, every degradation copied into the result.
cache
    Results addressed by what produced them: scenario hash, code version and,
    for an ensemble, the seed.
parallel
    One function over many items, in-process or in spawned worker processes,
    with results and logs joined in input order so the two are identical.
sweep
    Parameter sweeps as a first-class run: dotted scenario paths, every point
    re-validated, metrics reduced to a table.
profiling
    Wall-clock seconds per stage, carried inside the result.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
