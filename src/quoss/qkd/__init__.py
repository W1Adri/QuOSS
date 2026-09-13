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
and so a block, is :mod:`quoss.system.key_volume`, and that is where the default
**is** set: :func:`~quoss.system.key_volume.pass_key_volume` returns
:attr:`~quoss.qkd.base.KeyRegime.FINITE`, and the asymptotic integral is
reachable only through a function whose name says ``asymptotic``.

Inside this package the labelling is unchanged and will stay that way: every
:class:`~quoss.qkd.base.KeyRate` here is
:attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` and says so in its own field,
because a rate at an instant cannot be a block-level claim; and every
:class:`~quoss.qkd.finite_key.FiniteKeyResult` is
:attr:`~quoss.qkd.base.KeyRegime.FINITE` and cannot say anything else. What
changed one stage later is which of the two a caller gets by default, and the
measurement that makes the distinction worth the machinery: over one day of this
project's reference downlink the asymptotic integral claims 3.78 Mbit and the
finite bound certifies 0.43 Mbit, with **two of the four passes yielding exactly
zero** where the asymptotic answer claims 320 and 199 kbit.

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
