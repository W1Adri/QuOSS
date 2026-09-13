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
worse the link, the more it overestimates. The correction lives in
``finite_key.py`` and is a **block-level** entry point, because a finite-key
statement is about a block of detections rather than about an instant: it takes
accumulated counts and returns a number of bits, where :mod:`quoss.qkd.bb84`
takes a transmittance and returns a rate. Nothing in this package can therefore
make the finite-key result the default *rate* -- the object that owns a pass,
and so a block, is ``system/key_volume.py``, and that is where the default will
be set. Until then every :class:`~quoss.qkd.base.KeyRate` here is
:attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` and says so in its own field, and
every :class:`~quoss.qkd.finite_key.FiniteKeyResult` is
:attr:`~quoss.qkd.base.KeyRegime.FINITE` and cannot say anything else.

Modules
-------
base
    The protocol interface and registry: transmittance and noise in, rate out.
bb84
    BB84 with weak coherent pulses and vacuum+weak decoy states.
finite_key
    The composable finite-key length: Lim et al. 2014's bound for decoy-state
    BB84, taking counts in a block and returning bits.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
