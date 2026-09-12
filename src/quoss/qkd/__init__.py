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

The finite-key bound is on by default and the asymptotic rate is an explicit
flag, not the other way round. A LEO pass is a few minutes long, so the block
of detections it yields is finite by construction, and the asymptotic rate
overestimates the key -- the worse the link, the more it overestimates.

Modules
-------
base
    The protocol interface and registry: transmittance and noise in, rate out.
bb84
    BB84 with weak coherent pulses and vacuum+weak decoy states.
finite_key
    The composable finite-key length.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
