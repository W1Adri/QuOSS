"""The link budget: every loss in one place, and the two that are not numbers.

What this module is for
-----------------------
The six modules before this one each answer one question about the channel.
This one adds them up, which sounds like bookkeeping and is not, because two of
the six do not return a number at all. :mod:`quoss.channel.pointing` returns a
*distribution* over transmittance, and :mod:`quoss.channel.turbulence` returns a
*variance*. A budget line has to be a single decibel figure, so turning those two
into one requires a choice, and the choice is the whole content of this module.

The output is two things, kept apart on purpose:

- a :class:`LossBudget` — how much of the transmitted light arrives, split into
  terms a reviewer can check one at a time;
- a :class:`NoiseBudget` — how many counts per gate arrive that were not signal.

A link budget is the most reviewable object in a photon-starved simulation and
the easiest one to get quietly wrong, because every term is a decibel and
decibels add. Adding a term twice, or with the wrong sign, produces a total that
is wrong by exactly the size of the term and looks exactly as plausible as the
right answer.

The headline: two 1 % allowances do not make a 1 % allowance
------------------------------------------------------------
A *fade* is a loss that varies randomly in time. This link has two of them —
mechanical pointing jitter and atmospheric scintillation — and a budget cannot
quote a random variable, so it quotes a **quantile**: "the loss that is not
exceeded 99 % of the time", the 1 % *outage* allowance.

The published practice, which Ntanos et al. 2021 follow explicitly (§4.1 for
pointing, equation (18) for scintillation, both at their ``p_0 = 1 %``), is to
compute each fade's own 1 % quantile and add the two decibel figures. That is
wrong, and it is wrong in a direction and by an amount that can be stated
exactly, because both fades have a closed-form distribution **in decibels**:

- Pointing: :mod:`quoss.channel.pointing` derives the transmittance law
  ``F(x) = x^(gamma^2)``. Substituting ``L = -10 log10 x`` turns it into
  ``P(L > l) = exp(-l gamma^2 ln10 / 10)``. The pointing fade in dB is
  **exactly exponential**, with rate ``a = gamma^2 / 4.343``.
- Scintillation: the mean-normalised lognormal of Ntanos et al. equation (17)
  has ``ln I ~ N(-sigma^2/2, sigma^2)``. Substituting the same ``L`` makes the
  scintillation fade in dB **exactly Gaussian**, mean ``4.343 sigma^2 / 2``,
  standard deviation ``4.343 sigma``.

Their sum is therefore an *exponentially modified Gaussian*, whose cumulative
distribution is closed form, so the true joint quantile needs no Monte Carlo and
no approximation — :func:`combined_fade_db` computes it to the last bit.

Measured, for this project's reference downlink (0.75 m ground telescope,
600 km, 1550 nm, 0.15 m transmitter, 0.75 urad jitter, 20 degrees elevation):

==========================================  ==========  ===========
Quantity                                    1 % outage  0.1 % outage
==========================================  ==========  ===========
Pointing allowance alone                    1.030 dB    1.545 dB
Scintillation allowance alone               1.282 dB    1.692 dB
Their sum, as published budgets add them    2.312 dB    3.237 dB
The true joint quantile                     1.668 dB    2.217 dB
Margin added that nobody asked for          0.644 dB    1.020 dB
Outage the sum actually buys                0.066 %     0.0011 %
==========================================  ==========  ===========

The error is **conservative** — the sum over-states the fade — so nothing built
on it is unsafe. What it is, is *mislabelled*: a design that reports "20 dB at
1 % outage" is in fact reporting the loss at 0.066 % outage, fifteen times
stricter than the number printed beside it, and a secure key rate quoted at
"1 % outage" is not the key rate available at 1 % outage. Two systems compared
at the same stated outage are not being compared at the same outage unless their
fade terms happen to have the same shape.

:class:`FadeCombination` therefore has two members and no default that hides the
choice: :attr:`FadeCombination.EXACT` is what this module uses unless told
otherwise, and :attr:`FadeCombination.ADDITIVE` exists to reproduce a published
budget, with the difference between them available from the same call.

The trap this module is shaped to avoid: the receiver chain, twice
-----------------------------------------------------------------
:func:`quoss.channel.detector.click_probability` takes an ``efficiency``
argument and applies it to the signal and background means. A link budget also
naturally wants the receiver chain as a line item, because 6.36 dB of filter,
optics and quantum efficiency is the second largest term in the reference
receiver. Do both and the chain is counted twice: **12.71 dB instead of 6.36**,
a factor of 4.3 in key rate, and every intermediate number still looks ordinary.

This is the same shape of mistake as the ``A_0`` double-count that
:mod:`quoss.channel.pointing` is built to prevent, and the defence here is the
same: the ambiguity is removed from the API rather than from the documentation.
:attr:`LossBudget.transmittance` is the **complete** end-to-end factor, chain
included, so the mean photon number multiplied by it is already the mean photons
detected, and the correct follow-up call is
``click_probability(..., efficiency=1.0)``. For the other route,
:attr:`LossBudget.channel_transmittance` stops at the aperture and is the one to
pair with an explicit ``efficiency``. Both are stored, both are tested against
each other, and neither is the product of the other with anything the caller has
to remember.

Atmospheric extinction is an input to *this* function, and now has a model
--------------------------------------------------------------------------
"Extinction" is the light lost to the atmosphere by absorption in molecular
bands and by scattering off molecules and aerosols — distinct from turbulence,
which redistributes light rather than removing it, and distinct from cloud,
which is not a loss but an outage.

:func:`atmospheric_transmittance` implements Ntanos et al. equation (7),
``L_a = L_zen^(1/cos zeta)``: the vertical transmittance raised to the air mass.
The scaling law is published and numbered. **The number it is raised from was
not**, in any source this project could open: Ntanos et al. cite a reference for
equation (7) and never state ``L_zen``, and ITU-R P.1621-2 gives absorption in
its §2 and scattering in its §3 only as **figures** — Figures 1, 2 and 4 are
plots with no accompanying table or closed form. Reading a curve off a plot and
presenting the result as a published value is the thing
``docs/adr/0009-citation-policy.md`` exists to forbid.

:mod:`quoss.channel.extinction` now computes one, from visibility through ITU-R
P.1814 equations (4)-(5) — see ``docs/adr/0023-traceable-extinction.md``. That
does **not** change this signature, and the reason is worth stating rather than
inferring. This function's job is one line of a budget: transmittance raised to
air mass. The model needs a visibility, an aerosol scale height and a choice of
scaling law, none of which belong in a link budget's argument list, and one of
which (the scale height) still has no published value. So
``zenith_transmittance`` stays a **required** argument with no default: a caller
who has a modelled extinction computes it and passes it, a caller with a
measured one passes that, and a caller with none writes ``1.0`` and thereby says
so. There is still no argument value that quietly means "I did not think about
this", and the scenario schema mirrors the same shape one level up
(:class:`quoss.scenario.models.ChannelSpec`: a number or a model, never
neither).

What that term is worth, now that it can be computed: 23 km of visibility —
the clearest line in ITU-R P.1817-1's own weather code — is 0.230 dB straight
up at 1550 nm, and costs **22.7 %** of the reference day's certified key
(``tests/e2e/test_reference_scenarios.py::TestWhatTheExtinctionModelIsWorth``).
Every scenario in ``scenarios/`` declares ``1.0``, so every figure this project
has produced so far is for air that does not scatter.

What that gap costs, measured: Ntanos et al. state that their total downlink
loss "can get as low as 20 dB" for a 600 km link with a large telescope. Every
other term of that budget is reproducible from their own declared parameters and
sums to **19.09 dB** at zenith with their 2.3 m telescope, leaving **0.91 dB**.
Read through equation (7) that is ``L_zen = 0.81``, which *is* an ordinary
clear-sky zenith transmittance at 1550 nm — so the 20 dB is consistent with this
budget plus an unstated extinction of a plausible size, and that is as far as the
statement goes. It is a consistency, not a reproduction: the paper states no
extinction, and a residual that happens to land in a plausible range is not
evidence that it is the thing it resembles.

**Note what had to be added for the residual to be plausible at all, because it
is the more interesting half.** Before the transmit-aperture truncation term
below, the same budget summed to 15.74 dB and left 4.26 dB — which would have
needed ``L_zen = 0.375``, a 4.3 dB vertical extinction at 1550 nm under a clear
sky, an order of magnitude more than anything credible. The missing 3.35 dB was
not in the atmosphere; it was in the transmitter, and it is a term neither their
equations nor this package's ``beam.py`` contains.

The transmitter clips its own beam, and it costs more than it looks
-------------------------------------------------------------------
:mod:`quoss.channel.beam` propagates an **untruncated** Gaussian — one whose
power is integrated over the whole plane — with a waist radius equal to the
transmit aperture *radius*, which is the convention Ntanos et al. equation (6)
implies. A real aperture is a hole, and at that waist the rim cuts off
``exp(-2) = 13.5 %`` of the beam.

The tempting number is the 13.5 %: 0.63 dB of light that never leaves. It is the
wrong one, because on axis in the far field the *amplitude* is what integrates,
and the intensity is its square. Losing the tail of the amplitude integral costs
twice while the power normalisation recovers it once, so the untruncated far
field overstates the received power per unit launched power by

    eta_trunc(alpha) = [1 - exp(-alpha^2)]^2 / [1 - exp(-2 alpha^2)]

which at ``alpha = a/w_t = 1`` is 0.4621, **3.35 dB**. Derivation and the third
number (3.98 dB, relative to laser power rather than launched power) are in
:func:`gaussian_truncation_efficiency`, and a test checks the closed form against
the diffraction integral evaluated numerically instead of trusting the algebra.

Three consequences worth stating separately. It is a **transmitter** property,
so it is a scalar, does not vary over a pass, and is reported as its own budget
line. It is the one term here a beam expander removes: at ``alpha = 2`` it is
0.16 dB and at ``alpha = 3`` it is gone, which makes ``alpha`` a design variable
rather than a constant. And ``tests/golden/README.md`` predicted this term at
0.63 dB before the module existed; the prediction was the clipped-power number,
and it is corrected there now rather than quietly left standing.

The air mass, and where the secant stops being one
--------------------------------------------------
``1/cos(zeta)`` treats the atmosphere as a flat slab, which is exact overhead
and diverges at the horizon, where the real answer is finite. The honest
comparison is geometric rather than cited — the path length through a spherical
shell of thickness ``H`` around a sphere of radius ``R``:

    X(zeta) = sqrt((R/H)^2 cos^2 zeta + 2R/H + 1) - (R/H) cos zeta

With ``R = 6371 km`` and a scale height of 8.5 km the secant is high by 0.20 %
at 30 degrees, 0.50 % at 20 degrees — Ntanos et al.'s own elevation floor, so
the gap costs nothing where they work — 2.1 % at 10 degrees and 8.1 % at
5 degrees. :data:`SECANT_AIRMASS_ELEVATION_LIMIT_RAD` is where it reaches 5 %,
and below it :func:`atmospheric_transmittance` records a warning carrying both
air masses. The value returned is still the published model's.

Two sign conventions worth stating once
---------------------------------------
**Ntanos et al. equation (18) returns a negative number and calls it a loss.**
Written out, it is ``4.343 [erf^-1(2 p_0 - 1) sqrt(2 sigma^2_lnI) - sigma^2_lnI / 2]``,
which is ``10 log10`` of the ``p_0`` quantile of the irradiance — the signal
*level* relative to the mean, not the drop from it. At ``p_0 = 1 %`` and the
reference geometry it is ``-1.282 dB``. Added to a budget of positive losses as
printed, it subtracts the fade instead of adding it, and the total is wrong by
**twice** the fade depth. :func:`scintillation_fade_db` returns the negated
form, positive for a fade, and a test pins it against the published expression
transcribed verbatim.

**A variance of log-irradiance is not a scintillation index.** Equation (18) is
written in terms of ``sigma^2_I``, the scintillation index — the normalised
variance of the *irradiance* — and converts it with ``sigma^2_lnI =
ln(sigma^2_I + 1)``. What :func:`quoss.channel.turbulence.log_irradiance_variance`
returns is already ``sigma^2_lnI``, in Np^2, because ITU-R P.1622 equation (4b)
computes that quantity directly. Applying the conversion to it a second time is
a silent error worth 0.005 dB at the reference variance of 0.0153 Np^2 and
2.36 dB at the 1.0 Np^2 edge of weak-fluctuation theory. This module takes the
log-variance, its argument says so, and the conversion is not applied here.

What is deliberately not in here
--------------------------------
**Uplink.** Every fade term in :class:`LossBudget` is a downlink term. An uplink
has a third one — beam wander, :func:`quoss.channel.beam.uplink_beam_wander_angle_rad`
— whose distribution is not the same shape as either of these two, so the
exponentially modified Gaussian that makes :func:`combined_fade_db` exact stops
being exact. It also has no background model at all, because gap 7 of
``docs/adr/0009-citation-policy.md`` records that no source verified here
publishes the radiance of a sunlit Earth. A wrong uplink budget is worse than a
missing one.

**Cloud.** Cloud-free line of sight is a probability of the link existing, not a
decibel figure, and it belongs in ``system/pcflos.py`` where it can be applied
to a whole pass. Folding a cloud probability into an attenuation would turn an
outage into an average and make a link that never works look like a link that
works badly.

**Time correlation.** Both fades are quoted here as marginal quantiles at an
instant. A real pass fades in bursts lasting milliseconds, so the number of
*consecutive* gates lost is not what independent sampling implies. That is
``system/correlated_fading.py``, and until it exists no statement in this module
about a key *per pass* follows from one about a key *per gate*.

**Doppler, polarisation rotation, and the Faraday effect.** ``static_loss_db``
is a single scalar for everything constant that no module here models; the
reference value put into it, :data:`NTANOS_POLARISATION_LOSS_DB`, is the 0.3 dB
polarisation decoherence Ntanos et al. §4.1 declare. Naming it a static loss
rather than a polarisation model is the point: it is a placeholder with a
citation, not a physical treatment.

**Any protocol quantity.** Yield, QBER, sifting, decoy and key rate consume a
transmittance and a noise rate; they do not belong to the channel. This module
is where :mod:`quoss.channel` ends.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``zeta``                                zenith angle, ``pi/2 - elevation``
``X``                                   air mass, path length in vertical
                                        thicknesses (-)
``L_zen``                               vertical atmospheric transmittance (-)
``gamma``                               beam radius in units of pointing
                                        jitter (-)
``sigma^2_lnI``                         variance of log-irradiance (Np^2)
``a``                                   rate of the exponential pointing fade
                                        (1/dB)
``p_0``                                 outage probability (-)
``eta``                                 a transmittance, subscripted by term
``mu``                                  expected counts per gate (-)
======================================  ====================================

References
----------
A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021:
equation (7) (the air-mass scaling of atmospheric transmittance), equations
(8)-(10) (the pointing-error law), equations (17) and (18) (the lognormal fade
and its quantile), §4.1 (the reference system parameters reproduced as
constants here) and §4.2.1 (the "as low as 20 dB" total this module fails to
reproduce by 4.26 dB).

Recommendation ITU-R P.1621-2 (07/2015), §2 and §3: atmospheric absorption and
scattering, published as Figures 1, 2 and 4 and as no equation or table, which
is why ``zenith_transmittance`` is an argument.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import numpy as np
from scipy.special import erfcx, erfinv, log_ndtr, ndtr

from quoss.channel._validation import (
    validated_duration_s,
    validated_elevation,
    validated_positive_length_m,
    validated_wavelength_m,
)
from quoss.channel.atmosphere import ITU_GROUND_CN2_M23
from quoss.channel.background import (
    background_counts_per_gate,
    background_photon_rate_cps,
    background_power_w,
)
from quoss.channel.beam import geometric_transmittance
from quoss.channel.detector import afterpulsed_counts_per_gate, dark_counts_per_gate
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import ScintillationRegime, downlink_log_irradiance_variance
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import rad_to_deg, transmittance_to_loss_db

__all__ = [
    "DB_PER_NEPER",
    "GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE",
    "NTANOS_BEST_CASE_TOTAL_LOSS_DB",
    "NTANOS_FILTER_BANDWIDTH_M",
    "NTANOS_MINIMUM_ELEVATION_RAD",
    "NTANOS_OGS_APERTURES_M",
    "NTANOS_ORBIT_HEIGHT_KM",
    "NTANOS_OUTAGE_PROBABILITY",
    "NTANOS_POINTING_JITTER_RAD",
    "NTANOS_POLARISATION_LOSS_DB",
    "NTANOS_RECEIVER_FIELD_OF_VIEW_RAD",
    "NTANOS_TRANSMIT_APERTURE_M",
    "SECANT_AIRMASS_ELEVATION_LIMIT_RAD",
    "FadeCombination",
    "LossBudget",
    "NoiseBudget",
    "additive_fade_outage_probability",
    "atmospheric_transmittance",
    "combined_fade_db",
    "downlink_loss_budget",
    "downlink_noise_budget",
    "gaussian_truncation_efficiency",
    "pointing_fade_db",
    "scintillation_fade_db",
    "secant_airmass",
]

DB_PER_NEPER: Final[float] = 10.0 / np.log(10.0)
"""Decibels per neper, 4.342944819.

The ``4.343`` printed in front of Ntanos et al. equation (18), spelled as the
identity it is rather than as three digits. Every conversion in this module
between a log-irradiance statistic (natural log, nepers) and a budget line
(base-ten log, decibels) goes through this one name, which is what makes the
exponential and Gaussian fade laws below checkable by hand.
"""

SECANT_AIRMASS_ELEVATION_LIMIT_RAD: Final[float] = 0.112_176_364_273_748
"""Elevation below which ``sec(zeta)`` overstates the air mass by more than 5 %.

6.427 degrees, for a spherical shell of scale height 8.5 km around an Earth of
radius 6371 km. **Derived, not chosen:** it is the root of

    sec(zeta) / [sqrt((R/H)^2 sin^2 theta + 2R/H + 1) - (R/H) sin theta] = 1.05

and ``tests/channel/test_link_budget.py`` re-solves it rather than trusting the
digits here. The flat-slab secant of Ntanos et al. equation (7) diverges at the
horizon where the true path length is finite, so the overstatement has no upper
bound; 5 % is the same threshold the rest of :mod:`quoss.channel` uses for "two
defensible models have parted company".
"""

GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE: Final[float] = 1.0
"""Aperture radius in beam-waist radii implied by :mod:`quoss.channel.beam`, ``alpha = a / w_t``.

Exactly 1, and not by choice here: ``beam._WAIST_RADIUS_PER_DIAMETER = 0.5``
identifies the Gaussian waist radius with the transmitter's aperture *radius*,
which is what Ntanos et al. equation (6) implies. Any other value in a budget
built on that module is describing a different transmitter from the one its beam
radius was computed for, so this is the only value consistent with the rest of
the package — and it is the one place where that consistency is worth 3.35 dB.

A terminal with a beam expander, which illuminates a large aperture with a small
waist, has ``alpha`` well above 1 and pays almost nothing; see
:func:`gaussian_truncation_efficiency` for the curve and for what the number
means.
"""

NTANOS_TRANSMIT_APERTURE_M: Final[float] = 0.15
"""Satellite transmitter aperture of Ntanos et al. §4.1, m.

"we assumed an aperture of 0.15 m [24] for all three transmitters", giving the
"small beam divergence of about 13 urad" they quote, which is the **full** angle:
:func:`quoss.channel.beam.divergence_half_angle_rad` returns 6.58 urad for it.
"""

NTANOS_OGS_APERTURES_M: Final[tuple[float, float, float]] = (0.75, 1.3, 2.3)
"""Receiver apertures of the three Greek ground stations, m.

Cholomondas 0.75 m, Skinakas 1.3 m, Helmos 2.3 m (Ntanos et al. §4.1), in
increasing order rather than in the order the paper lists them. Kept as three
values and not as an average because the design conclusions differ between
them: the 0.75 m receiver is dark-count limited at night and the 2.3 m one is
sky limited, and gap 8 of ``docs/adr/0009-citation-policy.md`` only matters for
the large one.
"""

NTANOS_POINTING_JITTER_RAD: Final[float] = 0.75e-6
"""R.m.s. pointing error per axis of Ntanos et al. §4.1, rad.

"The pointing error variance was set to 0.75 urad" — named a variance in the
paper and used as a standard deviation, since equation (9) divides ``w_0^2`` by
``4 sigma_p^2`` and only that reading is dimensionally consistent.
"""

NTANOS_OUTAGE_PROBABILITY: Final[float] = 0.01
"""Outage probability Ntanos et al. §4.1 quote both fades at.

"the pointing loss was calculated for an outage probability of 1%", and
equation (18) is introduced "for a given probability (e.g., 1%) threshold". The
same ``p_0`` applied to both fades separately is exactly the practice the module
docstring measures: it buys 0.066 % joint outage, not 1 %.
"""

NTANOS_POLARISATION_LOSS_DB: Final[float] = 0.3
"""Polarisation decoherence loss of Ntanos et al. §4.1, dB.

"the polarization decoherence loss of the link was set to 0.3 dB [43]". Carried
as a static loss with its citation rather than modelled; nothing in
:mod:`quoss.channel` computes polarisation transport.
"""

NTANOS_RECEIVER_FIELD_OF_VIEW_RAD: Final[float] = 100e-6
"""Receiver field of view of Ntanos et al. §4.1, rad, full angle.

"we assumed a narrow FOV of 100 urad [27]". Read as a full angle by the
convention of gap 11 of ``docs/adr/0009-citation-policy.md``, which is the
reading ITU-R P.1621-2's own arithmetic forces and which
:func:`quoss.channel.background.receiver_solid_angle_sr` takes.
"""

NTANOS_FILTER_BANDWIDTH_M: Final[float] = 0.2e-9
"""Receiver band-pass filter width of Ntanos et al. §4.1, m.

"a narrow band-pass filter of 0.2 nm with an insertion loss of 3 dB". The
insertion loss is :data:`quoss.channel.detector.NTANOS_FILTER_INSERTION_LOSS_DB`
and belongs to the efficiency chain; this is the spectral width that sets how
much sky gets in.
"""

NTANOS_ORBIT_HEIGHT_KM: Final[float] = 600.0
"""Orbit altitude of the Ntanos et al. §4.2.1 best case, km.

Their 20 dB figure is explicitly "for an orbital height of 600 km that
corresponds only to the point when the satellite is exactly above the station",
so it is a slant range of 600 km at zenith, not an altitude to be converted.
"""

NTANOS_MINIMUM_ELEVATION_RAD: Final[float] = 0.349_065_850_398_866
"""Elevation floor of the Ntanos et al. §4.1 study, rad.

20 degrees: "only satellite elevation angle over 20 degrees was considered".
Worth a constant because three separate approximations in this package are
comfortable above it and get steadily worse below — the secant air mass (0.50 %
high here), the weak-fluctuation scintillation theory, and the sky radiance,
which gap 9 of ``docs/adr/0009-citation-policy.md`` records as zenith-only.
"""

NTANOS_BEST_CASE_TOTAL_LOSS_DB: Final[float] = 20.0
"""The published total downlink loss this module does not reproduce, dB.

Ntanos et al. §4.2.1: "the total link loss for a 600 km link distance can get as
low as 20 dB in total. To achieve this loss performance, a large enough
telescope in the receiver is required." Every term they list sums to 15.74 dB
from their own parameters. Present as a constant so the discrepancy has a name
and a test, not so that anything defaults to it.
"""

_MIN_OUTAGE_PROBABILITY: Final[float] = 0.0
_MAX_OUTAGE_PROBABILITY: Final[float] = 1.0
_BISECTION_ITERATIONS: Final[int] = 80
"""Halvings used to invert the exponentially modified Gaussian.

Derived from the bracket :func:`combined_fade_db` builds, which is never wider
than about 1e4 dB: ``1e4 / 2**80`` is 8e-21 dB, twenty orders of magnitude below
the resolution of a float64 decibel figure of order one. Bisection rather than
Newton because it is unconditionally convergent on a monotone function and,
unlike :func:`scipy.optimize.brentq`, vectorises over the time axis without a
Python loop.
"""
_AIRMASS_MODEL_DIVERGENCE_LIMIT: Final[float] = 1.05


def _validated_outage_probability(probability: float) -> float:
    """Return an outage probability in the open interval ``(0, 1)``.

    Both endpoints are excluded, and for different reasons that are worth
    keeping distinct. At zero there is no finite allowance: the pointing law
    reaches down to zero transmittance, so no loss is exceeded with certainty.
    At one there is no finite allowance either, and this is the end that
    surprises people — the lognormal has no upper bound on the *gain*, so the
    fade "exceeded 100 % of the time" is minus infinity decibels.

    Parameters
    ----------
    probability
        Outage probability.

    Returns
    -------
    float
        The validated probability.

    Raises
    ------
    DomainError
        If it is not finite, or not strictly inside ``(0, 1)``.

    Examples
    --------
    >>> _validated_outage_probability(0.01)
    0.01
    """
    outage = float(probability)
    if (
        not np.isfinite(outage)
        or outage <= _MIN_OUTAGE_PROBABILITY
        or outage >= _MAX_OUTAGE_PROBABILITY
    ):
        raise DomainError(
            f"outage_probability must lie strictly in (0, 1), got {outage}. It is a "
            "probability, not a percentage: 1 % is 0.01, not 1. Neither endpoint has a finite "
            "answer — at 0 the pointing law reaches zero transmittance, and at 1 the lognormal "
            "gain is unbounded above, so the fade level is -inf dB."
        )
    return outage


def _validated_transmittance(name: str, value: float) -> float:
    """Return a transmittance in ``(0, 1]``, named in the message."""
    eta = float(value)
    if not np.isfinite(eta) or eta <= 0.0 or eta > 1.0:
        raise DomainError(
            f"{name} must lie in (0, 1], got {eta}. It is a linear fraction, not a percentage "
            "and not a decibel figure: a 3 dB loss is 0.501, not 3. Zero is excluded because a "
            "channel that transmits nothing has infinite loss and no budget."
        )
    return eta


_ATMOSPHERE_SCALE_HEIGHT_M: Final[float] = 8500.0
"""Scale height used only to price the flat-slab air mass, m.

Not a model of anything: the density scale height of the lower atmosphere, used
by :func:`_spherical_shell_airmass` to say by how much ``sec(zeta)`` overstates
a path through a curved shell. Nothing in the returned budget depends on it —
it appears in a warning message and in the derivation of
:data:`SECANT_AIRMASS_ELEVATION_LIMIT_RAD`, and a factor of two in it moves that
limit by a few tenths of a degree.
"""
_EARTH_MEAN_RADIUS_M: Final[float] = 6_371_000.0
"""Mean Earth radius, m, for the same comparison and nothing else.

Mean rather than the WGS-84 equatorial radius of
:mod:`quoss.core.constants` because the quantity being computed is a ratio
``R/H`` of order 750, where a 0.3 % difference in ``R`` is invisible, and using
the geodetic radius would suggest a precision this comparison does not have.
"""


def _spherical_shell_airmass(elevation_rad: FloatArray | float) -> FloatArray:
    """Return the air mass of a uniform spherical shell, as a check on the secant.

    The path length through a shell of thickness ``H`` around a sphere of radius
    ``R``, in units of ``H``, from the law of cosines, with ``theta`` the
    elevation and ``sin theta = cos zeta``::

        X = sqrt((R/H)^2 sin^2 theta + 2 R/H + 1) - (R/H) sin theta

    This is geometry, not a citation: it is here as an independent statement of
    how far ``1 / cos(zeta)`` can be trusted, and it is deliberately *not* what
    :func:`atmospheric_transmittance` returns, because the published model is
    the secant and substituting a better one silently would leave the module
    reproducing nothing.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians.

    Returns
    -------
    FloatArray
        Air mass, dimensionless.

    Examples
    --------
    >>> round(float(_spherical_shell_airmass(np.radians(20.0))), 4)
    2.9092

    At the horizon the secant is infinite and this is not, which is the whole
    point of having it:

    >>> round(float(_spherical_shell_airmass(0.0)), 2)
    38.73
    """
    ratio = _EARTH_MEAN_RADIUS_M / _ATMOSPHERE_SCALE_HEIGHT_M
    horizontal = ratio * np.sin(np.asarray(elevation_rad, dtype=np.float64))
    airmass: FloatArray = np.sqrt(horizontal**2 + 2.0 * ratio + 1.0) - horizontal
    return airmass


def secant_airmass(elevation_rad: FloatArray | float) -> FloatArray:
    """Return the flat-slab air mass, ``1 / cos(zeta)``.

    *Air mass* is how many vertical thicknesses of atmosphere the path crosses:
    1 straight up, 2 where the path is twice as long. This is the plane-parallel
    form implied by the exponent of Ntanos et al. equation (7), where ``zeta`` is
    the zenith angle and the elevation is ``pi/2 - zeta``.

    It is exact overhead and increasingly optimistic towards the horizon, where
    it diverges and the true path length does not. See
    :data:`SECANT_AIRMASS_ELEVATION_LIMIT_RAD` for where the overstatement
    reaches 5 %, and :func:`atmospheric_transmittance` for the warning that
    fires below it.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, in ``(0, pi/2]``. Any shape;
        typically ``(n_samples,)`` over a pass.

    Returns
    -------
    FloatArray
        Air mass, dimensionless and at least 1, shaped like ``elevation_rad``.

    Raises
    ------
    DomainError
        If any elevation is non-finite or outside ``(0, pi/2]``.

    Examples
    --------
    Overhead is one thickness, and the elevation floor of Ntanos et al. §4.1 is
    just under three:

    >>> from quoss.core.units import deg_to_rad
    >>> float(secant_airmass(deg_to_rad(90.0)))
    1.0
    >>> round(float(secant_airmass(NTANOS_MINIMUM_ELEVATION_RAD)), 4)
    2.9238

    Vectorised over the time axis, which is what a pass is:

    >>> secant_airmass(deg_to_rad(np.array([90.0, 30.0, 20.0]))).round(3)
    array([1.   , 2.   , 2.924])
    """
    elevation = validated_elevation(elevation_rad)
    airmass: FloatArray = 1.0 / np.sin(elevation)
    return airmass


def atmospheric_transmittance(
    elevation_rad: FloatArray | float,
    *,
    zenith_transmittance: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the clear-sky atmospheric transmittance along the slant path.

    Ntanos et al. equation (7), ``L_a = L_zen^(1/cos zeta)``: the vertical
    transmittance raised to the air mass. The form is the Beer-Lambert law in
    disguise — an optical depth ``tau`` multiplied by the air mass is the same
    statement as a transmittance ``exp(-tau)`` raised to it — which is why the
    exponent and not the base is where the elevation enters.

    ``zenith_transmittance`` has **no default**, deliberately. The scaling law is
    published; the number it scales is not. Ntanos et al. never state ``L_zen``,
    and ITU-R P.1621-2 publishes absorption (§2) and scattering (§3) only as
    Figures 1, 2 and 4 — plots, with no table and no closed form. See the module
    docstring for what that gap is measured to cost.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, in ``(0, pi/2]``. Any shape.
    zenith_transmittance
        Vertical (zenith) transmittance of the whole atmosphere, in ``(0, 1]``.
        Pass ``1.0`` to state explicitly that extinction is being ignored.
    degradations
        Log that receives a warning when the elevation drops below
        :data:`SECANT_AIRMASS_ELEVATION_LIMIT_RAD`, where the flat-slab air mass
        of equation (7) leaves the spherical geometry by more than 5 %.

    Returns
    -------
    FloatArray
        Transmittance in ``(0, 1]``, shaped like ``elevation_rad``.

    Raises
    ------
    DomainError
        If the elevation is outside ``(0, pi/2]`` or the zenith transmittance is
        outside ``(0, 1]``.

    Examples
    --------
    A 1 dB vertical extinction — ``10 ** (-0.1)`` — costs nearly 3 dB at the
    20 degree floor, because the loss in decibels is the air mass times the
    zenith loss:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import deg_to_rad, transmittance_to_loss_db
    >>> log = DegradationLog()
    >>> eta = atmospheric_transmittance(
    ...     deg_to_rad(np.array([90.0, 20.0])), zenith_transmittance=0.7943, degradations=log
    ... )
    >>> transmittance_to_loss_db(eta).round(3)
    array([1.   , 2.924])

    Saying "no extinction" is allowed and silent, because it was said on purpose:

    >>> float(atmospheric_transmittance(1.0, zenith_transmittance=1.0, degradations=log))
    1.0
    >>> len(log)
    0
    """
    elevation = validated_elevation(elevation_rad)
    vertical = _validated_transmittance("zenith_transmittance", zenith_transmittance)
    airmass = secant_airmass(elevation)

    lowest = float(np.min(elevation)) if elevation.size else np.inf
    if lowest < SECANT_AIRMASS_ELEVATION_LIMIT_RAD:
        degradations.warn(
            "link_budget.secant-airmass-out-of-range",
            (
                f"Elevation reaches {rad_to_deg(lowest):.3f} degrees, below the "
                f"{rad_to_deg(SECANT_AIRMASS_ELEVATION_LIMIT_RAD):.3f} degrees where the "
                "flat-slab sec(zenith) of Ntanos et al. equation (7) overstates the spherical "
                f"air mass by 5 %. Secant there is {1.0 / np.sin(lowest):.3f} against "
                f"{_spherical_shell_airmass(lowest):.3f} for a shell of scale height 8.5 km, so "
                "the extinction returned is too large. The value is still that model's."
            ),
            where="quoss.channel.link_budget.atmospheric_transmittance",
            min_elevation_rad=lowest,
            limit_rad=SECANT_AIRMASS_ELEVATION_LIMIT_RAD,
            secant_airmass=float(1.0 / np.sin(lowest)),
            spherical_airmass=float(_spherical_shell_airmass(lowest)),
        )

    transmittance: FloatArray = vertical**airmass
    return transmittance


def gaussian_truncation_efficiency(truncation_ratio: float) -> float:
    """Return what an untruncated Gaussian far field overstates, for a real aperture.

    What the problem is
    -------------------
    :mod:`quoss.channel.beam` propagates an **untruncated** Gaussian: a beam whose
    power is integrated over the whole infinite plane. A transmitter is a hole of
    finite size, and with the waist convention that module uses — waist radius
    equal to the aperture *radius* — the rim of the telescope cuts off
    ``exp(-2) = 13.5 %`` of the beam. The far field of what actually leaves is
    then not the far field the module computes, and the difference is not the
    13.5 %.

    The derivation, which is three lines of Fraunhofer
    -------------------------------------------------
    On axis in the far field, the intensity is ``|integral E dA|^2 / (lambda L)^2``
    — the *amplitude* integrates, not the power. For a Gaussian field
    ``exp(-r^2/w^2)`` truncated at radius ``a``, writing ``alpha = a/w``::

        integral E dA   = pi w^2 [1 - exp(-alpha^2)]
        launched power  = |E|^2 pi w^2 / 2 [1 - exp(-2 alpha^2)]

    so the on-axis intensity **per unit launched power**, divided by the same
    quantity for the untruncated beam, is::

        eta_trunc(alpha) = [1 - exp(-alpha^2)]^2 / [1 - exp(-2 alpha^2)]

    At ``alpha = 1`` that is 0.4621, a loss of **3.352 dB**, and
    ``tests/channel/test_link_budget.py`` checks the closed form against the
    diffraction integral evaluated numerically rather than trusting the algebra.

    Why it is 3.35 dB and not 0.63 dB
    ---------------------------------
    0.63 dB is ``1 - exp(-2)``, the fraction of the *laser's* light the rim
    blocks, and it is the right answer to a different question. It does not
    include the part that costs more: the amplitude integral loses its tail
    *twice over*, because intensity goes as the square of it, while the power
    normalisation only recovers it once. Three numbers exist here and each has
    its own reference, which is why this docstring names all three rather than
    picking one:

    ============================================  ==========  ====================
    Quantity                                      At alpha=1  Reference power
    ============================================  ==========  ====================
    Light the rim blocks                          0.63 dB     laser
    What this function returns                    3.35 dB     out of the aperture
    Both together, ``[1-exp(-alpha^2)]^2``        3.98 dB     laser
    ============================================  ==========  ====================

    :func:`downlink_loss_budget` applies the middle one, because a link budget's
    transmit power is the power that left the telescope. If a caller's mean
    photon number is defined at the *source* instead, the extra 0.63 dB belongs
    in ``static_loss_db``, and saying which convention ``mu`` uses is the
    caller's job because no formula can tell.

    Parameters
    ----------
    truncation_ratio
        ``alpha = a / w_t``, the transmit aperture radius in beam-waist radii,
        finite and strictly positive. For the waist convention of
        :mod:`quoss.channel.beam` it is
        :data:`GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE`, exactly 1.

    Returns
    -------
    float
        Efficiency in ``(0, 1]``, relative to the untruncated far field.

    Raises
    ------
    DomainError
        If the ratio is not finite and strictly positive.

    Examples
    --------
    The convention this package uses, and what it costs:

    >>> from quoss.core.units import transmittance_to_loss_db
    >>> round(gaussian_truncation_efficiency(1.0), 6)
    0.462117
    >>> round(float(transmittance_to_loss_db(gaussian_truncation_efficiency(1.0))), 3)
    3.352

    The term dies quickly once the aperture is bigger than the beam, which is
    what a beam expander is for — and it is why this is a transmitter design
    parameter rather than a constant of nature:

    >>> for alpha in (1.0, 1.5, 2.0, 3.0):
    ...     loss = float(transmittance_to_loss_db(gaussian_truncation_efficiency(alpha)))
    ...     print(f"alpha = {alpha:3.1f} -> {loss:5.3f} dB")
    alpha = 1.0 -> 3.352 dB
    alpha = 1.5 -> 0.919 dB
    alpha = 2.0 -> 0.159 dB
    alpha = 3.0 -> 0.001 dB
    """
    alpha = float(truncation_ratio)
    if not np.isfinite(alpha) or alpha <= 0.0:
        raise DomainError(
            f"truncation_ratio must be finite and positive, got {alpha}. It is the transmit "
            "aperture *radius* divided by the beam waist radius, so it is dimensionless and of "
            "order one: quoss.channel.beam's waist convention makes it exactly 1."
        )
    numerator = -np.expm1(-(alpha**2))
    denominator = -np.expm1(-2.0 * alpha**2)
    return float(numerator**2 / denominator)


_POINTING_FADE_FREE_RATIO: Final[float] = 1e150
"""The beam-to-jitter ratio at and above which the pointing fade is exactly zero.

Two reasons for a threshold, and neither is a physical choice. First, ``gamma``
is legitimately **infinite**: :func:`quoss.channel.pointing.equivalent_beam_radius_m`
returns ``inf`` once the receiving aperture is more than about 21 beam radii
wide, which is the law's own limit (a beam that small never leaves a lens that
large) and a normal geometry on an optical bench. Second, ``gamma**2`` overflows
past 1.34e154, and :func:`combined_fade_db` multiplies it by a Gaussian width of
up to hundreds of decibels.

What the threshold costs is below anything a decibel can express: at
``gamma = 1e150`` the pointing fade at a 1e-15 outage is
``4.343 * ln(1e15) / 1e300 = 1.5e-298`` dB, and it is reported as ``0.0``.
"""


def _validated_beam_to_jitter_ratio(beam_to_jitter_ratio_value: FloatArray | float) -> FloatArray:
    """Return ``gamma`` as an array: strictly positive, not NaN, ``+inf`` accepted.

    ``+inf`` is the one non-finite value with a meaning: an aperture so much
    wider than the beam that equation (9) of Farid & Hranilovic predicts no
    pointing fade at all. See :data:`_POINTING_FADE_FREE_RATIO`.
    """
    gamma = np.asarray(beam_to_jitter_ratio_value, dtype=np.float64)
    if np.any(np.isnan(gamma)) or np.any(gamma <= 0.0):
        raise DomainError(
            "beam_to_jitter_ratio_value must be strictly positive and not NaN; it is a beam "
            "radius measured in pointing jitters, so zero would mean a beam of no width. "
            "+inf is accepted: it is an aperture so much wider than the beam that the pointing "
            f"law predicts no fade. Got range [{float(np.min(gamma))}, {float(np.max(gamma))}]."
        )
    return gamma


def pointing_fade_db(
    beam_to_jitter_ratio_value: FloatArray | float,
    *,
    outage_probability: float,
) -> FloatArray:
    """Return the pointing fade allowance, dB, positive for a loss.

    :mod:`quoss.channel.pointing` derives that the relative transmittance under
    Gaussian jitter obeys ``F(x) = x^(gamma^2)`` on ``[0, 1]``. Inverting it and
    converting to decibels gives Ntanos et al. equation (10)::

        L_point(p_0) = -10 log10(p_0^(1/gamma^2)) = 10 log10(1/p_0) / gamma^2

    which is worth reading twice, because it says the fade in decibels is an
    **exponential** random variable with rate ``a = gamma^2 / 4.343`` — the
    quantile is linear in ``log(1/p_0)``, which is the defining property. That
    fact is what makes :func:`combined_fade_db` a closed form rather than a
    simulation.

    Parameters
    ----------
    beam_to_jitter_ratio_value
        ``gamma``, the equivalent beam radius in units of r.m.s. jitter, from
        :func:`quoss.channel.pointing.beam_to_jitter_ratio`. Any shape.
    outage_probability
        Probability of being **worse** than the returned allowance, in
        ``(0, 1)``. Scalar: it is a design choice, not a per-sample quantity.

    Returns
    -------
    FloatArray
        Fade allowance in dB, positive, shaped like the ratio.

    Raises
    ------
    DomainError
        If the outage probability is outside ``(0, 1)``, or the ratio is
        non-finite or not strictly positive.

    Examples
    --------
    The reference geometry of Ntanos et al. §4.1 has ``gamma^2 = 19.42``, and
    this reproduces the 1.030 dB that
    :func:`quoss.channel.pointing.pointing_transmittance_quantile` gives from
    the transmittance side:

    >>> round(float(pointing_fade_db(np.sqrt(19.42), outage_probability=0.01)), 3)
    1.03

    Ten times less outage costs the same increment again, which is what "the
    quantile is linear in log(1/p)" means in practice:

    >>> for outage in (1e-2, 1e-3, 1e-4):
    ...     print(
    ...         f"{outage:g} -> {float(pointing_fade_db(4.407, outage_probability=outage)):.3f} dB"
    ...     )
    0.01 -> 1.030 dB
    0.001 -> 1.545 dB
    0.0001 -> 2.060 dB
    """
    outage = _validated_outage_probability(outage_probability)
    gamma = _validated_beam_to_jitter_ratio(beam_to_jitter_ratio_value)
    fade_free = gamma >= _POINTING_FADE_FREE_RATIO
    capped = np.where(fade_free, 1.0, gamma)
    fade: FloatArray = np.where(fade_free, 0.0, DB_PER_NEPER * np.log(1.0 / outage) / capped**2)
    return fade


def scintillation_fade_db(
    log_irradiance_variance_np2: FloatArray | float,
    *,
    outage_probability: float,
) -> FloatArray:
    """Return the scintillation fade allowance, dB, positive for a loss.

    Ntanos et al. equation (18), **negated**::

        L_sci(p_0) = -4.343 [erf^-1(2 p_0 - 1) sqrt(2 sigma^2_lnI) - sigma^2_lnI / 2]

    The published expression is ``10 log10`` of the ``p_0`` quantile of the
    irradiance, so it is the signal *level* relative to the mean and comes out
    negative for any ``p_0`` below about a half. Adding it to a budget of
    positive losses exactly as printed subtracts the fade instead of adding it,
    and the total is then wrong by twice the fade depth. This function returns
    the depth, positive.

    Read as a distribution rather than as a formula, it says the scintillation
    fade in decibels is **Gaussian**, with mean ``4.343 sigma^2 / 2`` and
    standard deviation ``4.343 sigma``. The mean is positive — a fade on
    average — because the lognormal of equation (17) is normalised to unit mean
    *irradiance*, and the mean of the logarithm of a positive variable is below
    the logarithm of its mean.

    Note the argument is the variance of **log**-irradiance, ``sigma^2_lnI`` in
    Np^2, which is what :func:`quoss.channel.turbulence.log_irradiance_variance`
    and its downlink and uplink wrappers return. Equation (18) is written in
    terms of the scintillation index ``sigma^2_I`` and converts it internally
    with ``sigma^2_lnI = ln(sigma^2_I + 1)``; applying that conversion to an
    argument that is already a log-variance costs 0.005 dB at the reference
    0.0153 Np^2 and 2.36 dB at the 1.0 Np^2 limit of weak-fluctuation theory.

    Parameters
    ----------
    log_irradiance_variance_np2
        ``sigma^2_lnI``, variance of log-irradiance in Np^2, non-negative. Any
        shape; typically one value per time sample of a pass.
    outage_probability
        Probability of being **worse** than the returned allowance, in
        ``(0, 1)``. Scalar.

    Returns
    -------
    FloatArray
        Fade allowance in dB, shaped like the variance. Positive for any outage
        probability below the median crossing; negative above it, where the
        "allowance" is a boost and the sign is meaningful rather than an error.

    Raises
    ------
    DomainError
        If the outage probability is outside ``(0, 1)``, or any variance is
        non-finite or negative.

    Examples
    --------
    The reference downlink at 20 degrees elevation with a 0.75 m telescope has
    ``sigma^2_lnI = 0.01528 Np^2``:

    >>> round(float(scintillation_fade_db(0.01528, outage_probability=0.01)), 3)
    1.282

    The sign carries information, and the place it changes is not where a
    reader expects. At ``p_0 = 0.5`` the allowance is still a small **loss**,
    0.033 dB, because a lognormal normalised to unit mean has its median below
    its mean — half the time the link is worse than average. Only well past the
    median does the allowance become a gain:

    >>> for outage in (0.5, 0.9):
    ...     print(
    ...         f"{outage} -> {float(scintillation_fade_db(0.01528, outage_probability=outage)):+.4f} dB"
    ...     )
    0.5 -> +0.0332 dB
    0.9 -> -0.6548 dB

    No turbulence, no allowance, at any outage:

    >>> float(scintillation_fade_db(0.0, outage_probability=1e-06))
    0.0
    """
    outage = _validated_outage_probability(outage_probability)
    variance = np.asarray(log_irradiance_variance_np2, dtype=np.float64)
    if not np.all(np.isfinite(variance)) or np.any(variance < 0.0):
        raise DomainError(
            "log_irradiance_variance_np2 must be finite and non-negative. It is a variance in "
            "Np^2 from quoss.channel.turbulence, not a scintillation index and not a decibel "
            f"figure. Got range [{float(np.min(variance))}, {float(np.max(variance))}]."
        )
    sigma = np.sqrt(variance)
    fade: FloatArray = -DB_PER_NEPER * (
        erfinv(2.0 * outage - 1.0) * np.sqrt(2.0) * sigma - 0.5 * variance
    )
    return fade


def _fade_distribution_parameters(
    beam_to_jitter_ratio_value: FloatArray | float,
    log_irradiance_variance_np2: FloatArray | float,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Return ``(mean, sd, rate)`` of the two fade laws, in decibels.

    The Gaussian mean and standard deviation of the scintillation fade and the
    rate of the exponential pointing fade — the three numbers that define the
    exponentially modified Gaussian their sum follows. Broadcast against each
    other so a pass can vary both.

    ``rate`` is ``+inf`` where ``gamma`` reaches :data:`_POINTING_FADE_FREE_RATIO`:
    an exponential with infinite rate is a fade that is always zero, and
    :func:`_emg_cdf` treats it as exactly that.
    """
    gamma = _validated_beam_to_jitter_ratio(beam_to_jitter_ratio_value)
    variance = np.asarray(log_irradiance_variance_np2, dtype=np.float64)
    if not np.all(np.isfinite(variance)) or np.any(variance < 0.0):
        raise DomainError(
            "log_irradiance_variance_np2 must be finite and non-negative, in Np^2. Got range "
            f"[{float(np.min(variance))}, {float(np.max(variance))}]."
        )
    gamma, variance = np.broadcast_arrays(gamma, variance)
    mean = DB_PER_NEPER * 0.5 * variance
    sd = DB_PER_NEPER * np.sqrt(variance)
    fade_free = gamma >= _POINTING_FADE_FREE_RATIO
    capped = np.where(fade_free, 1.0, gamma)
    rate = np.where(fade_free, np.inf, capped**2 / DB_PER_NEPER)
    return mean, sd, rate


def _emg_cdf(
    level_db: FloatArray, mean: FloatArray, sd: FloatArray, rate: FloatArray
) -> FloatArray:
    """Return ``P(Gaussian(mean, sd) + Exponential(rate) <= level_db)``.

    The exponentially modified Gaussian distribution function::

        F(l) = Phi(z) - exp(-a (l - m) + a^2 s^2 / 2) Phi(z - a s),   z = (l - m)/s

    **How the second term is evaluated is the whole content of this function.**
    Written as it stands, its exponent is the difference of two terms of size
    ``(a s)^2 / 2`` — one explicit, one inside ``log Phi(z - a s)`` — and they
    cancel to within a few units. When the pointing fade is weak (``a`` large,
    ``gamma`` large) that is cancellation at 1e20 or 1e60, the last bits of the
    exponent are noise, and ``exp`` of the noise is a wrong answer that looks
    like a right one. This function used to do exactly that: at
    ``gamma = 1e10`` with ``sigma^2 = 1e-4`` it made :func:`combined_fade_db`
    return **1.602 dB** where the joint fade is the scintillation fade alone,
    **0.101 dB**, and at ``gamma = 1e30`` with ``sigma^2 = 0.5`` it returned
    **124.9 dB** against **8.23**. Nothing on the reference downlink reached it
    (``gamma`` is about 4.4 there); a horizontal link, where the beam is wide
    against its own jitter, reaches it at once.

    The fix is an identity, not an approximation. With ``Phi(x) = erfc(-x/sqrt 2)/2``
    and the scaled complementary error function ``erfcx(t) = exp(t^2) erfc(t)``,
    the exponents combine exactly::

        exp(-a (l - m) + a^2 s^2 / 2) Phi(z - a s) = erfcx((a s - z) / sqrt 2) exp(-z^2 / 2) / 2

    which has no cancellation anywhere and is used wherever ``a s >= z`` — the
    bulk of the distribution. Where ``z > a s`` (far above the mean) ``erfcx``
    of a large negative argument would overflow instead, and there the original
    form is safe: its exponent is ``-a s (z - a s / 2) < 0`` and the two terms
    no longer cancel.

    Two degenerate cases are limits rather than divisions: a zero standard
    deviation is the pure exponential (a pass can reach a sample with no
    turbulence in it), and an infinite rate is the pure Gaussian (an aperture
    wide enough that the pointing law predicts no fade).
    """
    degenerate = sd <= 0.0
    fade_free = np.isinf(rate)
    safe_sd = np.where(degenerate, 1.0, sd)
    safe_rate = np.where(fade_free, 1.0, rate)
    offset = level_db - mean
    z = offset / safe_sd
    shifted = safe_rate * safe_sd - z
    far_above = shifted < 0.0
    rate_far_above = np.where(far_above, safe_rate, 0.0)
    exponent = (
        -rate_far_above * offset
        + 0.5 * (rate_far_above * safe_sd) ** 2
        + log_ndtr(z - rate_far_above * safe_sd)
    )
    bulk = 0.5 * erfcx(np.maximum(shifted, 0.0) / np.sqrt(2.0)) * np.exp(-0.5 * z * z)
    gaussian = ndtr(z)
    smooth = gaussian - np.where(far_above, np.exp(exponent), bulk)
    pure_exponential = -np.expm1(-safe_rate * np.maximum(offset, 0.0))
    step = np.where(offset >= 0.0, 1.0, 0.0)
    result: FloatArray = np.where(
        degenerate,
        np.where(fade_free, step, pure_exponential),
        np.where(fade_free, gaussian, smooth),
    )
    return result


def combined_fade_db(
    *,
    beam_to_jitter_ratio_value: FloatArray | float,
    log_irradiance_variance_np2: FloatArray | float,
    outage_probability: float,
) -> FloatArray:
    """Return the joint fade allowance of pointing and scintillation together, dB.

    The quantity a budget with two fades actually needs, and the one that
    published budgets do not compute: the level that the **sum** of the two
    fades exceeds with probability ``outage_probability``.

    It is exact. The pointing fade in dB is exponential with rate
    ``a = gamma^2 / 4.343`` (see :func:`pointing_fade_db`) and the scintillation
    fade in dB is Gaussian with mean ``4.343 sigma^2/2`` and standard deviation
    ``4.343 sigma`` (see :func:`scintillation_fade_db`). The two are independent
    — one is a servo and a gimbal, the other is air — so their sum is an
    *exponentially modified Gaussian*, whose distribution function is closed
    form. Inverting it needs a root solve, done here by bisection so that it
    vectorises over the time axis; the answer is converged to below a part in
    1e20 of a decibel, which is exact for any purpose a decibel has.

    What this replaces is adding the two separate quantiles, which is what
    Ntanos et al. §4.1 and equation (18) do at a common ``p_0``. For the
    reference geometry at 20 degrees that sum is 2.312 dB against a true 1 %
    allowance of 1.668 dB: 0.644 dB of margin nobody asked for, and an outage
    that is really 0.066 %. Use :func:`additive_fade_outage_probability` to get
    that second number for any geometry.

    Parameters
    ----------
    beam_to_jitter_ratio_value
        ``gamma`` from :func:`quoss.channel.pointing.beam_to_jitter_ratio`. Any
        shape, broadcast against the variance.
    log_irradiance_variance_np2
        ``sigma^2_lnI`` in Np^2 from :mod:`quoss.channel.turbulence`. Any shape,
        broadcast against the ratio.
    outage_probability
        Probability of the joint fade being worse than the returned allowance,
        in ``(0, 1)``. Scalar.

    Returns
    -------
    FloatArray
        Joint fade allowance in dB, shaped by broadcasting the two inputs.

    Raises
    ------
    DomainError
        If the outage probability is outside ``(0, 1)``, the ratio is not
        strictly positive, or the variance is negative.

    Examples
    --------
    The reference downlink at 20 degrees, where adding the marginals gives
    2.312 dB:

    >>> round(
    ...     float(
    ...         combined_fade_db(
    ...             beam_to_jitter_ratio_value=np.sqrt(19.42),
    ...             log_irradiance_variance_np2=0.01528,
    ...             outage_probability=0.01,
    ...         )
    ...     ),
    ...     3,
    ... )
    1.668

    With no turbulence it collapses onto the pointing law exactly, which is the
    degenerate case a bisection over a Gaussian of zero width has to survive:

    >>> without_turbulence = combined_fade_db(
    ...     beam_to_jitter_ratio_value=4.407,
    ...     log_irradiance_variance_np2=0.0,
    ...     outage_probability=0.01,
    ... )
    >>> abs(
    ...     float(without_turbulence) - float(pointing_fade_db(4.407, outage_probability=0.01))
    ... ) < 1e-12
    True
    """
    outage = _validated_outage_probability(outage_probability)
    mean, sd, rate = _fade_distribution_parameters(
        beam_to_jitter_ratio_value, log_irradiance_variance_np2
    )
    target = 1.0 - outage

    # A bracket wide enough for any outage down to 1e-15: 40 standard deviations
    # of the Gaussian part and 40 mean lifetimes of the exponential part, on top
    # of the mean. The +1 dB keeps it non-degenerate when both parts vanish.
    low = mean - 40.0 * sd - 1.0
    high = mean + 40.0 * sd + 40.0 / rate + 1.0
    for _ in range(_BISECTION_ITERATIONS):
        middle = 0.5 * (low + high)
        below = _emg_cdf(middle, mean, sd, rate) < target
        low = np.where(below, middle, low)
        high = np.where(below, high, middle)
    allowance: FloatArray = 0.5 * (low + high)
    return allowance


def additive_fade_outage_probability(
    *,
    beam_to_jitter_ratio_value: FloatArray | float,
    log_irradiance_variance_np2: FloatArray | float,
    outage_probability: float,
) -> FloatArray:
    """Return the outage a budget really buys when it adds two separate quantiles.

    Take each fade's own ``outage_probability`` allowance, add the two decibel
    figures as a published budget does, and ask how often the *joint* fade
    actually exceeds that sum. The answer is always smaller than
    ``outage_probability`` — the addition is conservative — and this function
    says by how much, which is the part a design review needs and the part that
    never appears beside the printed number.

    Parameters
    ----------
    beam_to_jitter_ratio_value
        ``gamma`` from :func:`quoss.channel.pointing.beam_to_jitter_ratio`.
    log_irradiance_variance_np2
        ``sigma^2_lnI`` in Np^2 from :mod:`quoss.channel.turbulence`.
    outage_probability
        The outage each fade's allowance was computed at, in ``(0, 1)``.

    Returns
    -------
    FloatArray
        The true exceedance probability of the summed allowance.

    Raises
    ------
    DomainError
        Same conditions as :func:`combined_fade_db`.

    Examples
    --------
    A budget that prints "1 % outage" for the reference geometry is quoting a
    loss exceeded 0.066 % of the time — a factor of fifteen:

    >>> effective = additive_fade_outage_probability(
    ...     beam_to_jitter_ratio_value=np.sqrt(19.42),
    ...     log_irradiance_variance_np2=0.01528,
    ...     outage_probability=0.01,
    ... )
    >>> float(f"{float(effective):.3g}")
    0.000659
    >>> round(0.01 / float(effective), 1)
    15.2
    """
    outage = _validated_outage_probability(outage_probability)
    mean, sd, rate = _fade_distribution_parameters(
        beam_to_jitter_ratio_value, log_irradiance_variance_np2
    )
    additive = np.log(1.0 / outage) / rate + mean + sd * np.sqrt(2.0) * erfinv(1.0 - 2.0 * outage)
    exceedance: FloatArray = 1.0 - _emg_cdf(additive, mean, sd, rate)
    return exceedance


class FadeCombination(StrEnum):
    """How the two fade allowances are combined into one budget line.

    Attributes
    ----------
    EXACT
        The joint quantile of the two fades taken together,
        :func:`combined_fade_db`. The stated outage probability is then the
        outage the link actually has.
    ADDITIVE
        The sum of each fade's own quantile at the same probability, which is
        what Ntanos et al. §4.1 and equation (18) do. Kept so a published budget
        can be reproduced; it over-states the fade, and
        :attr:`LossBudget.effective_outage_probability` says by how much in the
        unit that matters.
    """

    EXACT = "exact"
    ADDITIVE = "additive"


@dataclass(frozen=True, slots=True)
class LossBudget:
    """Every loss between the satellite's aperture and the detector, separated.

    Frozen because a budget that can be edited after the fact is a budget whose
    terms no longer add up to its total, and the total is the only number most
    readers look at.

    Attributes
    ----------
    geometric_db : FloatArray
        Diffraction spreading of the beam against the collecting area,
        :func:`quoss.channel.beam.geometric_transmittance`. Almost always the
        largest term.
    truncation_db : float
        What the untruncated Gaussian far field of that term overstates for a
        real aperture, :func:`gaussian_truncation_efficiency`. Separate from
        ``geometric_db`` rather than folded into it because it is a property of
        the *transmitter*, not of the range: it does not change over a pass, and
        it is the one term here that a beam expander removes.
    atmospheric_db : FloatArray
        Clear-sky extinction along the path: :func:`atmospheric_transmittance` on
        a slant path, zero exactly when the caller passed ``zenith_transmittance=1.0``;
        ``extinction_db_per_km`` times the length on a horizontal one
        (:func:`quoss.channel.horizontal.horizontal_loss_budget`).
    fade_db : FloatArray
        Pointing and scintillation together, at ``outage_probability``, combined
        by ``fade_combination``.
    pointing_db : FloatArray
        The pointing fade **alone**, for review. Already inside ``fade_db``; do
        not add it again.
    scintillation_db : FloatArray
        The scintillation fade **alone**, for review. Already inside
        ``fade_db``; do not add it again.
    receiver_chain_db : float
        Optics, filter and detector quantum efficiency, from
        :func:`quoss.channel.detector.receiver_efficiency`.
    static_db : float
        Everything constant that no module here models, carried with its
        citation by the caller — polarisation decoherence, connector loss.
    total_db : FloatArray
        ``geometric + truncation + atmospheric + fade + receiver_chain +
        static``. The two marginal fade terms above are not in this sum twice.
    transmittance : FloatArray
        ``total_db`` as a linear factor. **End to end**, receiver chain
        included: multiply a mean photon number by this and the result is mean
        photons *detected*, so the matching call is
        ``click_probability(..., efficiency=1.0)``.
    channel_transmittance : FloatArray
        Everything outside the receiver, chain excluded. The one to pair with an
        explicit ``efficiency`` argument. Exactly one of these two belongs in
        any given expression; using both is the 6.36 dB double count the module
        docstring describes.
    outage_probability : float
        The outage the fade term was quoted at.
    effective_outage_probability : FloatArray
        The outage the fade term actually delivers. Equal to
        ``outage_probability`` for :attr:`FadeCombination.EXACT`; smaller, often
        by more than a decade, for :attr:`FadeCombination.ADDITIVE`.
    fade_combination : FadeCombination
        Which rule produced ``fade_db``. Recorded rather than assumed, because
        a budget compared against a published one has to say which convention
        it used.
    """

    geometric_db: FloatArray
    truncation_db: float
    atmospheric_db: FloatArray
    fade_db: FloatArray
    pointing_db: FloatArray
    scintillation_db: FloatArray
    receiver_chain_db: float
    static_db: float
    total_db: FloatArray
    transmittance: FloatArray
    channel_transmittance: FloatArray
    outage_probability: float
    effective_outage_probability: FloatArray
    fade_combination: FadeCombination


@dataclass(frozen=True, slots=True)
class NoiseBudget:
    """Counts per gate that are not signal, separated by where they were born.

    The split is not cosmetic. Sky photons enter through the aperture and are
    attenuated by the receiver efficiency chain exactly as signal photons are;
    dark counts originate behind the optics and are not. Afterpulses are caused
    by clicks of any origin and scale with the click rate rather than with the
    gate. Merging any two of the three loses a term — see
    :mod:`quoss.channel.detector` for the 0.94 dB that the natural merge hides.

    Attributes
    ----------
    background_per_gate : FloatArray
        Sky photons, **after** the efficiency chain.
    dark_per_gate : FloatArray
        Detector dark counts, summed over the detectors, **not** through the
        chain.
    afterpulse_per_gate : FloatArray
        The excess caused by previous clicks, over all click origins including
        signal. Zero for a detector with no afterpulsing, such as the nanowire
        of Ntanos et al. §4.1.
    total_per_gate : FloatArray
        The sum, which is a **mean** and not a probability: it has no upper
        bound, and turning it into a click probability is
        :func:`quoss.channel.detector.click_probability`'s job, once, at the
        end.
    """

    background_per_gate: FloatArray
    dark_per_gate: FloatArray
    afterpulse_per_gate: FloatArray
    total_per_gate: FloatArray


def downlink_loss_budget(
    elevation_rad: FloatArray | float,
    *,
    range_km: FloatArray | float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    zenith_transmittance: float,
    pointing_jitter_rad: float,
    receiver_efficiency: float,
    degradations: DegradationLog,
    outage_probability: float = NTANOS_OUTAGE_PROBABILITY,
    static_loss_db: float = 0.0,
    transmit_truncation_ratio: float = GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE,
    fade_combination: FadeCombination = FadeCombination.EXACT,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
) -> LossBudget:
    """Assemble the satellite-to-ground loss budget at every sample of a pass.

    Calls :mod:`quoss.channel.beam` for the geometric term,
    :func:`atmospheric_transmittance` for extinction,
    :mod:`quoss.channel.pointing` and :mod:`quoss.channel.turbulence` for the
    two fades, and adds the receiver chain and whatever static loss the caller
    declares. Every warning those modules raise — the ``W/a > 6`` validity
    condition of the pointing law, the weak-fluctuation limit of the
    scintillation theory, the air-mass limit here — lands in ``degradations``
    with the sample that caused it, so a budget computed over a whole pass says
    which part of the pass it is unsure about.

    Downlink only; see the module docstring for why an uplink budget is absent
    rather than approximated.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, in ``(0, pi/2]``. Any shape,
        broadcast against ``range_km``.
    range_km
        Slant range from satellite to station, km, from
        :func:`quoss.orbits.geometry.look_angles`. Not the altitude.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Satellite transmitter aperture diameter, m.
    receive_aperture_m
        Ground telescope aperture diameter, m.
    zenith_transmittance
        Vertical atmospheric transmittance, in ``(0, 1]``. Required, with no
        default: no source verified for this project publishes a value, so the
        caller owns the assumption. Pass ``1.0`` to declare extinction ignored.
    pointing_jitter_rad
        R.m.s. residual pointing error per axis, radians.
    receiver_efficiency
        Linear efficiency of the receiver chain, in ``(0, 1]``, from
        :func:`quoss.channel.detector.receiver_efficiency`. Taken as a number
        rather than recomputed here so that one definition of the chain serves
        both the loss budget and the noise budget.
    degradations
        Log that receives every warning raised by the modules called.
    outage_probability
        Outage the fade term is quoted at, in ``(0, 1)``.
    static_loss_db
        Constant loss for everything no module here models, dB, non-negative.
        If the caller's mean photon number is defined at the source rather than
        at the transmit aperture, the 0.63 dB the aperture rim blocks belongs
        here too — see :func:`gaussian_truncation_efficiency`.
    transmit_truncation_ratio
        ``alpha``, transmit aperture radius in beam-waist radii. Defaults to
        :data:`GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE`, which is the only
        value consistent with the beam radii :mod:`quoss.channel.beam` computes,
        and costs 3.35 dB. Pass a larger value for a transmitter with a beam
        expander.
    fade_combination
        :attr:`FadeCombination.EXACT` (default) or
        :attr:`FadeCombination.ADDITIVE`.
    station_height_m
        Station altitude above mean sea level, m, where the turbulence
        profile starts; see :mod:`quoss.channel.atmosphere`.
    rms_wind_speed_m_s
        R.m.s. wind speed along the path, m/s.
    ground_cn2_m23
        ``C_n^2`` at ground level, m^(-2/3).

    regime
        :class:`~quoss.channel.turbulence.ScintillationRegime`. ``WEAK`` (the
        default) returns the first-order value itself and records
        ``turbulence.weak-fluctuation-limit-exceeded`` above
        :data:`~quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT`;
        ``MODERATE_TO_STRONG`` returns the saturated value of
        :func:`~quoss.channel.turbulence.saturated_log_irradiance_variance`
        instead. The default is ``WEAK`` because every V2 check in this project
        compares against a printed ITU number, and the saturated model is 3.4 %
        below ITU-R P.1622 Table 2 even at that table's own weak point — a
        difference worth seeing rather than absorbing. [ADR 0022](../../../docs/adr/0022-the-strong-regime.md)
        says what each buys.

    Returns
    -------
    LossBudget
        Every term, the total, and both transmittances.

    Raises
    ------
    DomainError
        If any argument is outside its own domain, or ``static_loss_db`` is
        negative or non-finite.

    Examples
    --------
    The Ntanos et al. §4.2.1 best case: their 600 km link at zenith with the
    2.3 m Helmos telescope, extinction declared ignored so that every term is
    one of theirs, and their additive fade convention so that the comparison is
    against the budget they actually built. The total is 19.09 dB against the
    20 dB they print — and the term that closes most of that gap is the one
    their equations do not have, the aperture truncation.

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.channel.detector import (
    ...     NTANOS_FILTER_INSERTION_LOSS_DB,
    ...     NTANOS_RECEIVER_LOSS_DB,
    ...     NTANOS_SNSPD_EFFICIENCY,
    ...     receiver_efficiency,
    ... )
    >>> log = DegradationLog()
    >>> chain = receiver_efficiency(
    ...     NTANOS_SNSPD_EFFICIENCY,
    ...     optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    ... )
    >>> budget = downlink_loss_budget(
    ...     np.pi / 2,
    ...     range_km=NTANOS_ORBIT_HEIGHT_KM,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
    ...     receive_aperture_m=NTANOS_OGS_APERTURES_M[2],
    ...     zenith_transmittance=1.0,
    ...     pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
    ...     receiver_efficiency=chain,
    ...     static_loss_db=NTANOS_POLARISATION_LOSS_DB,
    ...     fade_combination=FadeCombination.ADDITIVE,
    ...     degradations=log,
    ... )
    >>> for name, value in (
    ...     ("geometric", budget.geometric_db),
    ...     ("truncation", budget.truncation_db),
    ...     ("atmospheric", budget.atmospheric_db),
    ...     ("fade", budget.fade_db),
    ...     ("receiver chain", budget.receiver_chain_db),
    ...     ("static", budget.static_db),
    ...     ("total", budget.total_db),
    ... ):
    ...     print(f"{name:>14}: {float(value):6.3f} dB")
         geometric:  8.066 dB
        truncation:  3.352 dB
       atmospheric:  0.000 dB
              fade:  1.019 dB
    receiver chain:  6.356 dB
            static:  0.300 dB
             total: 19.094 dB

    That budget prints a 1 % outage and delivers a different one, which is the
    whole reason :class:`FadeCombination` has two members:

    >>> print(f"{float(budget.effective_outage_probability):.2e}")
    7.24e-03

    The two transmittances differ by exactly the chain, and mixing them is the
    double count the module docstring prices at 6.36 dB:

    >>> from quoss.core.units import rad_to_deg, transmittance_to_loss_db
    >>> round(
    ...     float(transmittance_to_loss_db(budget.transmittance / budget.channel_transmittance)),
    ...     3,
    ... )
    6.356
    """
    elevation = validated_elevation(elevation_rad)
    wavelength = validated_wavelength_m(wavelength_m)
    transmit = validated_positive_length_m(
        "transmit_aperture_m", transmit_aperture_m, hint="The unit is metres, not centimetres."
    )
    receive = validated_positive_length_m(
        "receive_aperture_m", receive_aperture_m, hint="The unit is metres, not centimetres."
    )
    chain = _validated_transmittance("receiver_efficiency", receiver_efficiency)
    outage = _validated_outage_probability(outage_probability)
    static = float(static_loss_db)
    if not np.isfinite(static) or static < 0.0:
        raise DomainError(
            f"static_loss_db must be finite and non-negative, got {static}. It is a loss in dB, "
            "so a lossless placeholder is 0.0, not 1.0."
        )
    combination = FadeCombination(fade_combination)

    geometric = geometric_transmittance(
        range_km,
        wavelength_m=wavelength,
        transmit_aperture_m=transmit,
        receive_aperture_m=receive,
    )
    atmospheric = atmospheric_transmittance(
        elevation, zenith_transmittance=zenith_transmittance, degradations=degradations
    )
    gamma = beam_to_jitter_ratio(
        range_km,
        jitter_rad=pointing_jitter_rad,
        wavelength_m=wavelength,
        transmit_aperture_m=transmit,
        receive_aperture_m=receive,
        degradations=degradations,
    )
    variance = downlink_log_irradiance_variance(
        elevation,
        aperture_diameter_m=receive,
        wavelength_m=wavelength,
        degradations=degradations,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
        regime=regime,
    )

    return _assembled_loss_budget(
        geometric=geometric,
        atmospheric_db=np.asarray(transmittance_to_loss_db(atmospheric), dtype=np.float64),
        gamma=gamma,
        variance=variance,
        chain=chain,
        outage=outage,
        static=static,
        transmit_truncation_ratio=transmit_truncation_ratio,
        combination=combination,
    )


def _assembled_loss_budget(
    *,
    geometric: FloatArray,
    atmospheric_db: FloatArray,
    gamma: FloatArray,
    variance: FloatArray,
    chain: float,
    outage: float,
    static: float,
    transmit_truncation_ratio: float,
    combination: FadeCombination,
) -> LossBudget:
    """Combine already-computed terms into a :class:`LossBudget`.

    The part of a budget that does not depend on the geometry of the path: the
    two fade laws, the combination rule, the truncation, the chain and the total.
    Shared by :func:`downlink_loss_budget` and
    :func:`quoss.channel.horizontal.horizontal_loss_budget` so that the two
    budgets cannot drift apart in how they add their terms.

    The strong-turbulence model of stage 1.2 is **not** here, although this
    docstring used to promise it would be. It is in
    :func:`quoss.channel.turbulence.saturated_log_irradiance_variance`, applied
    to the *point* variance before aperture averaging, because Gruneisen et al.
    equations (A8) and (A9) are point-receiver results: by the time a variance
    reaches this function it has already been multiplied by an averaging factor,
    and saturating it here would saturate the wrong quantity. What the two
    budgets share is therefore the model, not the call site — both reach it
    through their own ``regime`` argument. Inputs are validated by the callers.
    """
    pointing_db = pointing_fade_db(gamma, outage_probability=outage)
    scintillation_db = scintillation_fade_db(variance, outage_probability=outage)
    if combination is FadeCombination.EXACT:
        fade_db = combined_fade_db(
            beam_to_jitter_ratio_value=gamma,
            log_irradiance_variance_np2=variance,
            outage_probability=outage,
        )
        effective = np.broadcast_to(np.asarray(outage), fade_db.shape).astype(np.float64)
    else:
        fade_db = pointing_db + scintillation_db
        effective = additive_fade_outage_probability(
            beam_to_jitter_ratio_value=gamma,
            log_irradiance_variance_np2=variance,
            outage_probability=outage,
        )

    geometric_db = np.asarray(transmittance_to_loss_db(geometric), dtype=np.float64)
    chain_db = float(transmittance_to_loss_db(chain))
    truncation_db = float(
        transmittance_to_loss_db(gaussian_truncation_efficiency(transmit_truncation_ratio))
    )

    channel_db = geometric_db + truncation_db + atmospheric_db + fade_db
    total_db = channel_db + chain_db + static
    return LossBudget(
        geometric_db=geometric_db,
        truncation_db=truncation_db,
        atmospheric_db=atmospheric_db,
        fade_db=np.asarray(fade_db, dtype=np.float64),
        pointing_db=np.asarray(pointing_db, dtype=np.float64),
        scintillation_db=np.asarray(scintillation_db, dtype=np.float64),
        receiver_chain_db=chain_db,
        static_db=static,
        total_db=np.asarray(total_db, dtype=np.float64),
        transmittance=np.asarray(10.0 ** (-total_db / 10.0), dtype=np.float64),
        channel_transmittance=np.asarray(10.0 ** (-(channel_db + static) / 10.0), dtype=np.float64),
        outage_probability=outage,
        effective_outage_probability=np.asarray(effective, dtype=np.float64),
        fade_combination=combination,
    )


def downlink_noise_budget(
    sky_radiance_w_m2_um_sr: FloatArray | float,
    *,
    wavelength_m: float,
    receive_aperture_m: float,
    field_of_view_full_angle_rad: float,
    filter_bandwidth_m: float,
    gate_duration_s: float,
    receiver_efficiency: float,
    dark_count_rate_cps: FloatArray | float,
    degradations: DegradationLog,
    detector_count: int = 1,
    afterpulse_probability: float = 0.0,
    signal_counts_per_gate: FloatArray | float = 0.0,
) -> NoiseBudget:
    """Assemble the counts per gate that are not signal.

    Three sources, combined as **means** and never as probabilities, which is
    the composition rule :mod:`quoss.channel.detector` is built around: means of
    independent Poisson processes add, probabilities do not, and every published
    form that adds probabilities returns something above one somewhere in this
    project's parameter sweeps.

    Each source enters where it is born:

    - **Sky.** Photons through the aperture, so the receiver efficiency chain
      attenuates them exactly as it attenuates signal.
      :mod:`quoss.channel.background` deliberately stops at the aperture and
      hands the chain to this function.
    - **Dark counts.** Generated behind the optics, so the chain does **not**
      apply. Applying it anyway understates the total noise by 0.94 dB with the
      2.3 m reference telescope and 3.82 dB with the 0.75 m one, and moves the
      dark-count share of the night-time budget from 7 % to 25 %.
    - **Afterpulses.** Caused by previous clicks of any origin — signal
      included, which is why ``signal_counts_per_gate`` is an argument here and
      not a separate calculation. They do not scale with the gate, so narrowing
      the gate does not reduce them.

    Parameters
    ----------
    sky_radiance_w_m2_um_sr
        Sky radiance, W/(m^2 um sr), from :mod:`quoss.channel.background`.
        Constant over a pass in every source verified for this project, which is
        gap 9 of ``docs/adr/0009-citation-policy.md``; an array is accepted so a
        caller with a better model is not blocked.
    wavelength_m
        Optical wavelength, m.
    receive_aperture_m
        Ground telescope aperture diameter, m.
    field_of_view_full_angle_rad
        Receiver field of view, radians, **full angle** — see gap 11 of
        ``docs/adr/0009-citation-policy.md``, where reading it as a half angle
        is measured at 6.02 dB.
    filter_bandwidth_m
        Band-pass filter width, m. 0.2 nm is ``0.2e-9``.
    gate_duration_s
        Detection gate width, s. 1 ns is ``1e-9``.
    receiver_efficiency
        Linear efficiency of the receiver chain, in ``(0, 1]``. The same number
        passed to :func:`downlink_loss_budget`.
    dark_count_rate_cps
        Dark count rate of **one** detector, counts/s.
    degradations
        Log that receives the afterpulse-cascade warning if it fires.
    detector_count
        How many detectors contribute dark counts.
    afterpulse_probability
        Afterpulse probability per click, in ``[0, 1)``.
    signal_counts_per_gate
        Mean detected signal counts per gate, from
        ``mean_photon_number * budget.transmittance``. Needed only to price
        afterpulsing; leave at zero for the noise floor with no signal.

    Returns
    -------
    NoiseBudget
        The three terms and their sum, all as means per gate.

    Raises
    ------
    DomainError
        If any argument is outside its own domain.

    Examples
    --------
    The Ntanos et al. §4.1 receiver on their study night, with the 2.3 m
    telescope and two nanowires — which have no afterpulsing, so the third term
    is exactly zero:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
    >>> from quoss.channel.detector import (
    ...     NTANOS_FILTER_INSERTION_LOSS_DB,
    ...     NTANOS_RECEIVER_LOSS_DB,
    ...     NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    ...     NTANOS_SNSPD_EFFICIENCY,
    ...     receiver_efficiency,
    ... )
    >>> log = DegradationLog()
    >>> chain = receiver_efficiency(
    ...     NTANOS_SNSPD_EFFICIENCY,
    ...     optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    ... )
    >>> noise = downlink_noise_budget(
    ...     NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    ...     wavelength_m=1.55e-06,
    ...     receive_aperture_m=NTANOS_OGS_APERTURES_M[2],
    ...     field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    ...     filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
    ...     gate_duration_s=1e-09,
    ...     receiver_efficiency=chain,
    ...     dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    ...     detector_count=2,
    ...     degradations=log,
    ... )
    >>> print(f"{float(noise.background_per_gate):.3e} sky")
    1.768e-06 sky
    >>> print(f"{float(noise.dark_per_gate):.3e} dark")
    6.000e-07 dark
    >>> print(f"{float(noise.total_per_gate):.3e} total")
    2.368e-06 total

    The same night on the 0.75 m telescope is a different instrument: the sky
    term falls with the collecting area and the dark counts do not, so the
    budget inverts from sky limited to dark limited.

    >>> small = downlink_noise_budget(
    ...     NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    ...     wavelength_m=1.55e-06,
    ...     receive_aperture_m=NTANOS_OGS_APERTURES_M[0],
    ...     field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    ...     filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
    ...     gate_duration_s=1e-09,
    ...     receiver_efficiency=chain,
    ...     dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    ...     detector_count=2,
    ...     degradations=log,
    ... )
    >>> round(float(small.dark_per_gate / small.total_per_gate) * 100.0, 1)
    76.1
    """
    wavelength = validated_wavelength_m(wavelength_m)
    chain = _validated_transmittance("receiver_efficiency", receiver_efficiency)
    gate = validated_duration_s("gate_duration_s", gate_duration_s)

    power = background_power_w(
        sky_radiance_w_m2_um_sr,
        field_of_view_full_angle_rad=field_of_view_full_angle_rad,
        receive_aperture_m=receive_aperture_m,
        filter_bandwidth_m=filter_bandwidth_m,
    )
    at_aperture = background_counts_per_gate(
        background_photon_rate_cps(power, wavelength_m=wavelength), gate_duration_s=gate
    )
    background = chain * at_aperture
    dark = dark_counts_per_gate(
        dark_count_rate_cps, gate_duration_s=gate, detector_count=detector_count
    )

    signal = np.asarray(signal_counts_per_gate, dtype=np.float64)
    if not np.all(np.isfinite(signal)) or np.any(signal < 0.0):
        raise DomainError(
            "signal_counts_per_gate must be finite and non-negative. It is a mean number of "
            "detected counts per gate — mean_photon_number times the budget transmittance — "
            f"not a probability. Got range [{float(np.min(signal))}, {float(np.max(signal))}]."
        )
    primary = background + dark + signal
    afterpulsed = afterpulsed_counts_per_gate(
        primary, afterpulse_probability=afterpulse_probability, degradations=degradations
    )
    afterpulse = afterpulsed - primary

    total: FloatArray = background + dark + afterpulse
    return NoiseBudget(
        background_per_gate=np.asarray(background, dtype=np.float64),
        dark_per_gate=np.asarray(dark, dtype=np.float64),
        afterpulse_per_gate=np.asarray(afterpulse, dtype=np.float64),
        total_per_gate=np.asarray(total, dtype=np.float64),
    )
