"""From a channel to a key: BB84 with decoy states, and its finite-key bound.

This package takes what :mod:`quoss.channel` produces — a transmittance and a
background count rate at every instant — and returns a secure key rate and a
quantum bit error rate. It contains no optics and no geometry.

Scope, stated so the absences are not mistaken for oversights: **only BB84 with
weak coherent pulses and decoy states**. E91, continuous-variable QKD, MDI-QKD
and TF-QKD are not implemented and do not appear as names anywhere in the
protocol registry, following the rule ``docs/adr/0005-propagation.md`` settled
for :class:`~quoss.orbits.propagator.PropagationMethod`: an absent name forces
the question at the call site, while a present and unimplemented one invites
someone to select it.

A LEO pass is a few minutes long, so the block of detections it yields is
finite by construction, and the asymptotic rate overestimates the key -- the
worse the link, the more it overestimates. **That correction does not exist
yet**: ``finite_key.py`` is unwritten, so every rate this package returns today
is :attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` and says so in its own field.
When the bound lands it becomes the default and the asymptotic rate becomes the
explicit flag, not the other way round -- stated in the future tense on purpose,
because a default announced before it exists is the same silent overestimate the
label was added to make visible.

Modules
-------
base
    The protocol interface and registry: transmittance and noise in, rate out.
bb84
    BB84 with weak coherent pulses and vacuum+weak decoy states.
finite_key
    The composable finite-key length. **Not written yet** -- named here because
    the two modules above already point at it, not because it is importable.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
