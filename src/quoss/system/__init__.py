"""From instants to system metrics: passes, key volume, and what they compose into.

Everything below this package answers a question about an *instant*.
:mod:`quoss.orbits` says where the satellite is now; :mod:`quoss.channel` says
how much light arrives now; :mod:`quoss.qkd` says what fraction of a pulse sent
now becomes key. None of them can answer the question a mission asks, which is
**how many bits do we get tonight**.

That question needs two things neither layer has. It needs a *window* — the
contiguous stretch of time during which the satellite is high enough to use,
which is ``passes.py`` — and it needs an *integral* over that window, which is
``key_volume.py``. The second is not the first multiplied by a duration, and
the reason is the whole point of this package:

**A finite-key bound is a statement about a block, and a block is a pass.**
:mod:`quoss.qkd.finite_key` can price the statistical uncertainty in a block of
counts, but it cannot know what the block is, because a block is an integral
over a time axis and ``qkd/`` has no time axis. So every rate leaving
:mod:`quoss.qkd.base` is labelled
:attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` and says so in its own field. This
package is where that stops being true: :func:`~quoss.system.key_volume.pass_key_volume`
returns :attr:`~quoss.qkd.base.KeyRegime.FINITE`, and the asymptotic answer is
only reachable through a function whose name says *asymptotic*.

Measured, for this project's reference downlink (0.75 m telescope at
Castelldefels, a 700 km sun-synchronous satellite, a clear moonless night, a
10 degree elevation mask, one UTC day): the asymptotic integral claims
**3.78 Mbit** across four passes; the finite bound certifies **0.43 Mbit**,
**11.5 %** of it, and **two of the four passes yield exactly zero** where the
asymptotic answer claims 320 and 199 kbit. Reporting the asymptotic figure as
available key would therefore not be 9 times optimistic on average — it would
be infinitely optimistic on half the passes. The numbers are in
``tests/system/test_key_volume.py::TestWhatTheAsymptoticRateOverstates``.

Modules
-------
passes
    Which stretches of a time grid are a usable pass, where exactly they begin
    and end, and how many seconds of the grid each sample speaks for.
key_volume
    The integral over a pass: bits per pass and bits per day, with the
    finite-key bound applied to the block the pass actually is.

Not written yet, in roadmap order (``notes/ROADMAP.md`` stage 3):
``monte_carlo.py`` (how much the answer scatters between passes, which is the
question :func:`~quoss.qkd.finite_key.expected_block_counts` explicitly does
not answer), ``correlated_fading.py``, ``pcflos.py``, ``multi_ogs.py``,
``relay.py``.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
