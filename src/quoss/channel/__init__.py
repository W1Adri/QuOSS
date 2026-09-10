"""The optical channel: how much light arrives, and how much noise arrives with it.

A satellite QKD link is a photon-starved optical link through a turbulent
atmosphere. Between the geometry that :mod:`quoss.orbits` produces and the key
rate that :mod:`quoss.qkd` computes, this package answers two questions at every
instant of a pass: what fraction of the transmitted photons reach the detector,
and how many counts that are not signal reach it as well.

Both answers are numbers nobody can sanity-check by eye. A link loss of 45 dB
looks exactly as plausible as the correct 39 dB, and a scintillation model that
silently returns "no scintillation" produces a curve with the right shape. That
is why every formula in this package carries a citation a reader can open, and
why the models that cannot be evaluated record a
:class:`~quoss.core.errors.Degradation` instead of substituting something
quietly. See ``docs/adr/0009-citation-policy.md`` for the rule and for the gaps
it declares.

Modules, in dependence order
---------------------------
atmosphere
    Refractive-index structure profiles :math:`C_n^2(h)`, air mass, refraction.
turbulence
    Fried parameter, Rytov variance, scintillation index, aperture averaging.
beam
    Divergence, geometric and diffraction coupling, beam wander.
pointing
    Pointing loss and the fading that mechanical jitter produces.
background
    Sky radiance, background count rate, and the detection time gate.
detector
    Efficiency, dark counts, dead time, afterpulsing, timing jitter.
link_budget
    Assembles the above into separable loss components and a noise rate.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
