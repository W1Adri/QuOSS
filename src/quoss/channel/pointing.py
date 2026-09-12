"""Pointing error: the beam is aimed almost at the telescope, and almost is not enough.

What this module is for
-----------------------
:mod:`quoss.channel.beam` computes how much power lands in the receiving
telescope when the beam is aimed **exactly** at it. Nothing is ever aimed
exactly. A satellite terminal tracks a moving ground station with gimbals and a
fast steering mirror against a star tracker, and what is left over after the
control loop has done its best is a residual angular error of a microradian or
so, wandering in time. This module says what that costs.

It is not a small correction, and it is not a fixed one. A microradian of
residual error on a beam whose half-angle is six microradians is a sixth of the
way to the edge, which by itself is cheap — but the error is *random*, so the
link spends a fraction of its time much further off than that, and a QKD link
is judged on the bad moments, not the average ones. That is why the output of
this module is a **distribution**, not a number.

Pointing error is not beam wander
---------------------------------
They look alike and they are different mechanisms, so they are in different
modules with different names:

- **Beam wander** (:func:`quoss.channel.beam.uplink_beam_wander_angle_rad`) is
  *turbulence* tilting the beam. It happens to a beam leaving the ground, it is
  driven by :math:`C_n^2`, and there is nothing a control loop can do about the
  part faster than its bandwidth.
- **Pointing error**, here, is the *terminal* aiming the beam wrongly:
  mechanical jitter, platform micro-vibration, tracking-loop residual, imperfect
  point-ahead. It happens in both directions, and it is a property of the
  hardware rather than of the sky.

They add, in the sense that their variances add if they are independent. This
module models one of them, and takes the total jitter as an argument so a caller
who wants both can pass the combined standard deviation and say so.

**The trap this module is shaped to avoid**
--------------------------------------------
Farid & Hranilovic's equation (9) writes the collected fraction with a pointing
displacement ``r`` as::

    h_p(r) = A_0 exp(-2 r^2 / w_zeq^2)

and ``A_0`` — the value at ``r = 0`` — **is the geometric coupling**, the same
quantity :func:`quoss.channel.beam.geometric_transmittance` returns. So a link
budget that multiplies "the geometric loss" by "the pointing loss", with the
pointing loss taken as the published ``h_p``, counts ``A_0`` **twice**.

At the reference geometry of this repo that is a factor of 0.0179 applied
twice: **17.5 dB of loss invented from nothing**. It would not look wrong in a
table, because 35 dB and 17.5 dB are both plausible numbers for a satellite
downlink.

Every function here therefore returns the **relative** factor, the ``exp``
alone, normalised so that perfect pointing gives exactly 1. The rule is:

    total = beam.geometric_transmittance(...) * pointing.<anything here>

and nothing in this module ever returns the absolute coupling. What it costs to
follow the source literally instead is measured in
``tests/channel/test_pointing.py::TestTheDoubleCountingTrap``.

Why the fading law is a power law
---------------------------------
This is the part worth reading once, because the shape is not obvious and the
derivation is three lines. Let ``x = h_p / A_0`` be the relative factor, so
``x = exp(-2 r^2 / w_zeq^2)`` and therefore
``r^2 = -(w_zeq^2 / 2) ln x``.

The radial error ``r`` is the length of a vector whose two components are
independent zero-mean Gaussians of standard deviation ``sigma_s`` — one for
elevation, one for cross-elevation — which makes ``r`` **Rayleigh**
distributed (Farid & Hranilovic equation (10)), with
``P(r >= R) = exp(-R^2 / (2 sigma_s^2))``.

Since ``x`` decreases as ``r`` grows, being *below* a transmittance ``x`` is the
same event as being *beyond* the corresponding radius::

    F(x) = P(r >= r(x)) = exp(-r(x)^2 / (2 sigma_s^2))
         = exp( (w_zeq^2 / (4 sigma_s^2)) ln x )
         = x^(gamma^2),      gamma = w_zeq / (2 sigma_s)

A power law, with one dimensionless parameter: **the beam radius measured in
units of jitter**. Everything else in this module is a consequence of that one
line — the mean is ``gamma^2 / (gamma^2 + 1)``, the quantile is
``p^(1 / gamma^2)``, and both are the exponent doing all the work.

The shape of that law is what makes pointing error dangerous. With
``gamma = 4.4`` (this repo's reference case) the *mean* loss is 0.22 dB and
the 1-in-100 loss is 1.03 dB — a factor of five between the average and the
tail, from the same distribution. Doubling the jitter to 2 urad takes the mean
to 1.35 dB and the 1-in-100 to **7.3 dB**: the mean grew sixfold and the tail
sevenfold, and the tail was five times larger to begin with. A link designed on
averages is designed for a link that does not exist.

Two independent sources, and they agree
---------------------------------------
Farid & Hranilovic 2007 equation (11) gives the exponent as
``gamma^2 = (w_zeq / 2 sigma_s)^2``, with ``w_zeq`` the equivalent beam radius
at the receiver plane and ``sigma_s`` the jitter as a **displacement**. Ntanos
et al. 2021 equation (9) gives it as ``beta_p = (theta_div / 2 sigma_p)^2``,
with both quantities **angles**. Those are the same ratio, divided top and
bottom by the range — except that Ntanos et al. use the plain divergence angle
where Farid & Hranilovic use the equivalent one, which carries a correction for
the finite size of the receiving aperture.

Measured at this repo's reference geometry: ``gamma^2 = 19.42`` against
``beta_p = 19.23``, a difference of 1 %, i.e. **0.01 dB** in the 1-in-100
pointing loss (1.030 dB against 1.040 dB). Two papers, two notations, fourteen
years apart, agreeing to a hundredth of a decibel is the strongest statement
this module can make about being right, and
``tests/channel/test_pointing.py::TestTwoPublishedSourcesAgree`` is where it is
asserted rather than claimed.

A consequence worth noticing: because both the beam radius and the jitter
displacement grow in proportion to the range, ``gamma`` is **almost constant
over a pass**. The pointing loss in decibels barely changes between culmination
and the horizon, unlike every other term in the channel. What changes with
range is the geometric coupling, not this.

What is deliberately not in here
--------------------------------
**Non-zero boresight.** The model assumes the jitter is zero-mean: the terminal
is aimed at the right place on average and shakes around it. A *systematic* aim
offset — a miscalibrated star tracker, a thermal bias — makes ``r`` Rician
rather than Rayleigh (Beckmann or Hoyt in the FSO literature), and no free
verified source for that was located. It is declared gap 3 of
``docs/adr/0009-citation-policy.md`` and it is **not** approximated here: a
boresight offset that is known can be passed to
:func:`pointing_transmittance` as a deterministic displacement, which is exact,
but the *distribution* under a boresight offset is absent rather than guessed.

**The turbulence convolution.** The full channel state is the product of
turbulence fading and pointing fading, and its distribution is Farid &
Hranilovic equation (14) — an integral over the log-normal. This module returns
the pointing factor alone, because combining it with
:mod:`quoss.channel.turbulence` is a link-budget decision (which turbulence
model, which regime) and belongs where the terms are assembled.

**Temporal correlation.** Everything here is a marginal distribution: it says
what fraction of the time the link is faded, not for how long at a stretch. A
pointing error has a correlation time of milliseconds to tens of milliseconds,
which matters enormously for how a QKD post-processing block sees it. That is
``system/correlated_fading.py``, the AR(1) process, and it is the point of
novelty in ``notes/ROADMAP.md`` rather than an omission here.

**Sampling.** There is no random number generator in this module, and that is
deliberate: the quantile function *is* the sampler. Feeding
:func:`pointing_transmittance_quantile` a uniform draw gives an exact sample of
the distribution by inverse transform, so ``system/monte_carlo.py`` can own the
generator (the single injectable :class:`~quoss.core.rng.RandomSource`) without
this module needing to know it exists.

======================  ====================================================
Symbol                  Meaning
======================  ====================================================
``r``                   radial pointing displacement at the receiver (m)
``sigma_s``             r.m.s. jitter as a displacement, ``sigma * z`` (m)
``a``                   receiving aperture radius, ``D_r / 2`` (m)
``W``                   beam radius at the receiver, at ``1/e^2`` (m)
``v``                   ``sqrt(pi) a / (sqrt(2) W)``, aperture in beam widths
``A_0``                 collected fraction at zero displacement (0 to 1)
``w_zeq``               equivalent beam radius of equation (9) (m)
``gamma``               ``w_zeq / (2 sigma_s)``, beam radius in jitters
``gamma^2``             the fading exponent; Ntanos et al.'s ``beta_p``
======================  ====================================================

References
----------
A. A. Farid and S. Hranilovic, "Outage Capacity Optimization for Free-Space
Optical Links With Pointing Errors", *J. Lightwave Technol.* **25**(7):1702,
2007, §III-C (equations (7)-(11) and Table I). Opened at the authors' own copy,
per ``docs/adr/0009-citation-policy.md``.

A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
§3.5 (equations (8)-(10)).
"""

from __future__ import annotations

from typing import Final

import numpy as np
from scipy.special import erf

from quoss.channel._validation import validated_positive_length_m
from quoss.channel.beam import beam_radius_m
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import km_to_m

__all__ = [
    "GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT",
    "beam_to_jitter_ratio",
    "equivalent_beam_radius_m",
    "mean_pointing_transmittance",
    "pointing_outage_probability",
    "pointing_transmittance",
    "pointing_transmittance_quantile",
]

GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT: Final[float] = 6.0
"""Ratio ``W / a`` below which equation (9) leaves its published range.

Farid & Hranilovic state the condition themselves, which is why it is a
threshold rather than a judgement: "The proposed approximation is in good
agreement with the exact value when ``w_z/a > 6``, i.e., NMSE < 1e-3", with
their Table I printing the error at ``W/a`` = 2, 4, 6, 8, 10 and 12.

**It is not a decorative guard.** The reference system of Ntanos et al. 2021
violates it at its largest station: a 2.3 m telescope at 600 km sees
``W/a = 3.4``. So the condition fires for a configuration this project cares
about, and the honest response is to say so rather than to widen the condition.

Measured in this repo, because "out of published range" and "wrong" are not the
same claim (``tests/channel/test_pointing.py::TestAgainstTheExactIntegral``,
which integrates their exact equation (8) numerically as the oracle): at
``W/a = 3.4`` the closed form is still within **0.36 %** of the exact integral
over the displacements a 0.75 urad jitter actually produces, within 0.7 % out to
a full beam radius, and only degrades in the deep tail — 8 % at two beam radii
and 35 % at three. That tail is reached with probability 1e-17 at the reference
jitter, and matters only when the jitter becomes comparable to the beam radius
itself. The warning says which of those situations the caller is in.
"""

_MIN_OUTAGE_PROBABILITY: Final[float] = 0.0
_MAX_OUTAGE_PROBABILITY: Final[float] = 1.0


def _validated_jitter_rad(jitter_rad: float) -> float:
    """Return the r.m.s. angular jitter, rejecting zero as well as negatives."""
    jitter = float(jitter_rad)
    if not np.isfinite(jitter) or jitter <= 0.0:
        raise DomainError(
            f"jitter_rad must be finite and positive, got {jitter}. Zero is rejected rather "
            "than treated as perfect pointing, because the fading exponent gamma^2 diverges "
            "there: for a link with no jitter the answer is exactly 1, and the absolute "
            "coupling is quoss.channel.beam.geometric_transmittance, which is this model's "
            "value at zero displacement. The unit is radians, so a 1 microradian jitter is "
            "1e-6, not 1."
        )
    return jitter


def _beam_and_aperture(
    range_km: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
) -> tuple[FloatArray, float]:
    """Return the beam radius at the receiver and the receiving aperture radius, m."""
    radius_m = beam_radius_m(
        range_km, wavelength_m=wavelength_m, transmit_aperture_m=transmit_aperture_m
    )
    receiver_m = validated_positive_length_m(
        "receive_aperture_m",
        receive_aperture_m,
        hint="The unit is metres: this is the same aperture "
        "quoss.channel.beam.geometric_transmittance takes, and the two must agree or the "
        "pointing factor and the coupling it multiplies describe different telescopes.",
    )
    return radius_m, 0.5 * receiver_m


def equivalent_beam_radius_m(
    range_km: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the equivalent beam radius that sets the pointing sensitivity, m.

    Farid & Hranilovic equation (9)::

        v        = sqrt(pi) a / (sqrt(2) W)
        w_zeq^2  = W^2 * sqrt(pi) erf(v) / (2 v exp(-v^2))

    **What it is, and why it is not just the beam radius.** How fast the
    collected power falls off as the beam drifts sideways depends on two lengths:
    how wide the beam is, and how wide the telescope is. A point detector loses
    power as fast as the beam profile falls; a telescope comparable to the beam
    keeps catching the near edge of it as the far edge leaves, so it tolerates
    more drift. ``w_zeq`` is the width of the single Gaussian that reproduces
    that combined behaviour, and it is always **larger** than ``W`` — the
    aperture always helps.

    The correction is small when the telescope is small against the beam, which
    is the usual satellite case: measured here, a 0.75 m telescope at 600 km
    gets ``w_zeq / W = 1.0047``, so ignoring the correction would understate
    pointing tolerance by half a percent. A 2.3 m telescope at the same range
    gets 1.046.

    Parameters
    ----------
    range_km
        Distance from the transmitter, km, strictly positive. Any shape.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if ``W / a`` falls below
        :data:`GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT`.

    Returns
    -------
    FloatArray
        The equivalent beam radius in metres, shaped like ``range_km``.

    Raises
    ------
    DomainError
        If any range is non-positive or non-finite, or either aperture or the
        wavelength is not finite and positive.

    Examples
    --------
    The reference downlink of this repo — 0.15 m transmitter, 0.75 m ground
    telescope, 1550 nm, 600 km:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> equivalent = equivalent_beam_radius_m(
    ...     600.0,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(equivalent), 4)
    3.9665

    Which is slightly wider than the beam itself, because the aperture has a
    size:

    >>> from quoss.channel.beam import beam_radius_m
    >>> plain = beam_radius_m(600.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15)
    >>> round(float(equivalent / plain), 4)
    1.0047
    """
    radius_m, aperture_radius_m = _beam_and_aperture(
        range_km,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
    )
    beam_to_aperture = radius_m / aperture_radius_m
    worst = (
        float(np.min(beam_to_aperture))
        if beam_to_aperture.size
        else GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT
    )
    if worst < GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT:
        degradations.warn(
            "pointing.gaussian-approximation-out-of-published-range",
            (
                f"The beam radius is only {worst:.2f} times the receiving aperture radius, "
                f"below the {GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT} that Farid & Hranilovic "
                "2007 state for their equation (9) ('in good agreement with the exact value "
                "when w_z/a > 6'). Measured against their exact equation (8): the closed form "
                "is still within a fraction of a percent over the displacements an ordinary "
                "jitter produces, and only diverges beyond about two beam radii of offset — so "
                "this matters if the jitter approaches the beam radius, and is harmless if it "
                "does not. Compare jitter_rad against equivalent_beam_radius_m / range to tell "
                "which case this is."
            ),
            where="quoss.channel.pointing.equivalent_beam_radius_m",
            beam_to_aperture_radius_ratio=worst,
            limit=GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT,
            receive_aperture_m=float(receive_aperture_m),
        )

    v = np.sqrt(np.pi) * aperture_radius_m / (np.sqrt(2.0) * radius_m)
    equivalent_sq = radius_m**2 * np.sqrt(np.pi) * erf(v) / (2.0 * v * np.exp(-(v**2)))
    equivalent: FloatArray = np.sqrt(equivalent_sq)
    return equivalent


def pointing_transmittance(
    offset_rad: FloatArray | float,
    *,
    range_km: FloatArray | float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the power fraction kept when the beam is aimed ``offset_rad`` off target.

    The ``exp`` of Farid & Hranilovic equation (9), **without** its ``A_0``::

        eta_point = exp(-2 r^2 / w_zeq^2),    r = offset_rad * range

    This is the deterministic case: a *known* aim error, such as a measured
    boresight bias or a worst-case tracking budget. For the random case use
    :func:`pointing_transmittance_quantile`.

    The ``A_0`` is absent on purpose and the module docstring explains at length
    why: it is the geometric coupling, :func:`quoss.channel.beam.geometric_transmittance`
    already returns it, and multiplying both is a 17.5 dB error at this repo's
    reference geometry. So this function returns 1 for perfect pointing, and the
    total is the product of the two.

    Parameters
    ----------
    offset_rad
        Radial angular offset between the beam axis and the receiver,
        radians, non-negative. Broadcast against ``range_km``.
    range_km
        Distance from the transmitter, km, strictly positive.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if the geometry leaves the published range
        of equation (9).

    Returns
    -------
    FloatArray
        Relative transmittance between 0 and 1, broadcast over the inputs.

    Raises
    ------
    DomainError
        If any offset is negative or non-finite, or any range or aperture or the
        wavelength fails its own guard.

    Examples
    --------
    One microradian of aim error at 600 km puts the beam 0.6 m off a beam whose
    equivalent radius is 3.97 m, which costs a fifth of a decibel:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import transmittance_to_loss_db
    >>> log = DegradationLog()
    >>> kept = pointing_transmittance(
    ...     1e-06,
    ...     range_km=600.0,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(kept), 5)
    0.95527
    >>> round(float(transmittance_to_loss_db(kept)), 3)
    0.199

    The cost is quadratic in the offset — quadratic *inside an exponential*, so
    it stays cheap and then stops being cheap all at once: five microradians is
    5 dB, ten is 20 dB.

    >>> for offset_urad in (1.0, 5.0, 10.0):
    ...     loss = transmittance_to_loss_db(
    ...         pointing_transmittance(
    ...             offset_urad * 1e-06,
    ...             range_km=600.0,
    ...             wavelength_m=1.55e-06,
    ...             transmit_aperture_m=0.15,
    ...             receive_aperture_m=0.75,
    ...             degradations=log,
    ...         )
    ...     )
    ...     print(f"{offset_urad:4.1f} urad -> {float(loss):5.2f} dB")
     1.0 urad ->  0.20 dB
     5.0 urad ->  4.97 dB
    10.0 urad -> 19.88 dB

    Perfect pointing keeps everything, which is what makes this factor safe to
    multiply by the geometric coupling:

    >>> float(
    ...     pointing_transmittance(
    ...         0.0,
    ...         range_km=600.0,
    ...         wavelength_m=1.55e-06,
    ...         transmit_aperture_m=0.15,
    ...         receive_aperture_m=0.75,
    ...         degradations=log,
    ...     )
    ... )
    1.0
    """
    offset = np.asarray(offset_rad, dtype=np.float64)
    if not np.all(np.isfinite(offset)):
        raise DomainError("offset_rad contains non-finite values.")
    if np.any(offset < 0.0):
        raise DomainError(
            "offset_rad must be non-negative: it is a radial distance from the beam axis, so "
            "the sign carries no information and a negative value means a vector component was "
            f"passed instead of its magnitude. Minimum given: {float(np.min(offset))} rad."
        )
    equivalent_m = equivalent_beam_radius_m(
        range_km,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        degradations=degradations,
    )
    displacement_m = offset * km_to_m(np.asarray(range_km, dtype=np.float64))
    transmittance: FloatArray = np.exp(-2.0 * displacement_m**2 / equivalent_m**2)
    return transmittance


def beam_to_jitter_ratio(
    range_km: FloatArray | float,
    *,
    jitter_rad: float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return ``gamma``, the equivalent beam radius in units of jitter.

    Farid & Hranilovic equation (11)::

        gamma = w_zeq / (2 sigma_s),    sigma_s = jitter_rad * range

    One dimensionless number, and the module docstring's derivation shows it is
    the *only* parameter of the pointing fading law: the distribution of the
    relative transmittance is ``F(x) = x^(gamma^2)``, so every summary of the
    fading — mean, median, any quantile — is a function of ``gamma`` alone.

    How to read it: ``gamma`` is how many jitter standard deviations fit into
    half the equivalent beam width. Large ``gamma`` is a beam much wider than
    its own shake, so the fading is a nuisance; ``gamma`` near 1 is a beam about
    as wide as its shake, and the link is in deep fade a good part of the time.

    Nearly constant over a pass, which is worth knowing before plotting it: both
    ``w_zeq`` and ``sigma_s`` are proportional to the range, so they cancel. The
    residual variation is the aperture correction inside ``w_zeq``.

    Parameters
    ----------
    range_km
        Distance from the transmitter, km, strictly positive. Any shape.
    jitter_rad
        R.m.s. residual pointing error per axis, radians, strictly positive.
        This is the total the caller wants modelled: if mechanical jitter and
        turbulent beam wander are both in play and independent, pass the root
        sum of squares.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if the geometry leaves the published range
        of equation (9).

    Returns
    -------
    FloatArray
        The dimensionless ratio ``gamma``, shaped like ``range_km``.

    Raises
    ------
    DomainError
        If the jitter is not finite and positive, or any range or aperture or
        the wavelength fails its own guard.

    Examples
    --------
    The 0.75 urad jitter Ntanos et al. §4.1 declares, at 600 km:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> gamma = beam_to_jitter_ratio(
    ...     600.0,
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(gamma), 4)
    4.4072
    >>> round(float(gamma**2), 3)
    19.423

    And it barely moves across a pass, unlike everything else in the channel:

    >>> import numpy as np
    >>> over_a_pass = beam_to_jitter_ratio(
    ...     np.array([600.0, 1200.0, 2400.0]),
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> np.round(over_a_pass, 3)
    array([4.407, 4.391, 4.387])
    """
    jitter = _validated_jitter_rad(jitter_rad)
    equivalent_m = equivalent_beam_radius_m(
        range_km,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        degradations=degradations,
    )
    jitter_displacement_m = jitter * km_to_m(np.asarray(range_km, dtype=np.float64))
    ratio: FloatArray = equivalent_m / (2.0 * jitter_displacement_m)
    return ratio


def pointing_transmittance_quantile(
    probability: float,
    *,
    range_km: FloatArray | float,
    jitter_rad: float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the relative transmittance exceeded all but ``probability`` of the time.

    Inverting ``F(x) = x^(gamma^2)`` (module docstring) gives Ntanos et al.
    equation (10) exactly::

        eta_point(p) = p^(1 / gamma^2)

    This is the number a link budget wants: "what pointing loss do I have to
    survive if I am willing to be in outage 1 % of the time". Pass ``0.01`` and
    get 0.789 — a 1.03 dB allowance — for this repo's reference geometry.

    Note what ``probability`` means, because getting it backwards is a silent
    error of the same size as the answer: it is the probability of being
    **below** the returned value. Small ``probability`` therefore gives a small
    transmittance and a large loss, and a design that quotes a 1e-5 outage is
    quoting a *bigger* margin than one quoting 1e-2.

    Parameters
    ----------
    probability
        Outage probability, in ``(0, 1]``. Scalar: it is a design choice, not a
        per-sample quantity, and making it an array would invite indexing it
        against the time axis, which it does not share.
    range_km
        Distance from the transmitter, km, strictly positive. Any shape.
    jitter_rad
        R.m.s. residual pointing error per axis, radians.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if the geometry leaves the published range
        of equation (9).

    Returns
    -------
    FloatArray
        Relative transmittance between 0 and 1, shaped like ``range_km``.

    Raises
    ------
    DomainError
        If ``probability`` is outside ``(0, 1]``, or any other argument fails
        its own guard.

    Examples
    --------
    The reference geometry, at the 1 % outage Ntanos et al. §4.1 uses:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import transmittance_to_loss_db
    >>> log = DegradationLog()
    >>> kept = pointing_transmittance_quantile(
    ...     0.01,
    ...     range_km=600.0,
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(kept), 5)
    0.78892
    >>> round(float(transmittance_to_loss_db(kept)), 3)
    1.03

    The tail is where pointing error lives. Ten times less outage costs only
    half a decibel more here — the law is a power law, so the margin grows
    logarithmically:

    >>> for outage in (0.5, 0.01, 0.001):
    ...     loss = transmittance_to_loss_db(
    ...         pointing_transmittance_quantile(
    ...             outage,
    ...             range_km=600.0,
    ...             jitter_rad=0.75e-06,
    ...             wavelength_m=1.55e-06,
    ...             transmit_aperture_m=0.15,
    ...             receive_aperture_m=0.75,
    ...             degradations=log,
    ...         )
    ...     )
    ...     print(f"{outage:6.3f} -> {float(loss):5.3f} dB")
     0.500 -> 0.155 dB
     0.010 -> 1.030 dB
     0.001 -> 1.545 dB

    Certainty costs nothing, which is the boundary case the exponent has to get
    right:

    >>> float(
    ...     pointing_transmittance_quantile(
    ...         1.0,
    ...         range_km=600.0,
    ...         jitter_rad=0.75e-06,
    ...         wavelength_m=1.55e-06,
    ...         transmit_aperture_m=0.15,
    ...         receive_aperture_m=0.75,
    ...         degradations=log,
    ...     )
    ... )
    1.0
    """
    outage = float(probability)
    if (
        not np.isfinite(outage)
        or outage <= _MIN_OUTAGE_PROBABILITY
        or outage > _MAX_OUTAGE_PROBABILITY
    ):
        raise DomainError(
            f"probability must lie in (0, 1], got {outage}. Zero is excluded because no "
            "transmittance is exceeded with certainty under this model — the distribution "
            "reaches down to zero — so an outage target of exactly 0 has no finite answer. It "
            "is a probability, not a percentage: 1 % is 0.01, not 1."
        )
    gamma = beam_to_jitter_ratio(
        range_km,
        jitter_rad=jitter_rad,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        degradations=degradations,
    )
    quantile: FloatArray = outage ** (1.0 / gamma**2)
    return quantile


def pointing_outage_probability(
    transmittance: FloatArray | float,
    *,
    range_km: FloatArray | float,
    jitter_rad: float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return how often the relative pointing transmittance falls below a level.

    The cumulative distribution derived in the module docstring, which is the
    inverse of :func:`pointing_transmittance_quantile`::

        F(x) = x^(gamma^2)

    The question this answers is the one a system model asks: given the terminal
    I have, what fraction of the time is the pointing loss worse than the
    allowance I budgeted?

    Parameters
    ----------
    transmittance
        Relative pointing transmittance, in ``[0, 1]``. Broadcast against
        ``range_km``.
    range_km
        Distance from the transmitter, km, strictly positive.
    jitter_rad
        R.m.s. residual pointing error per axis, radians.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if the geometry leaves the published range
        of equation (9).

    Returns
    -------
    FloatArray
        Probability between 0 and 1, broadcast over the inputs.

    Raises
    ------
    DomainError
        If any transmittance is outside ``[0, 1]`` or non-finite, or any other
        argument fails its own guard.

    Examples
    --------
    Budgeting 1 dB of pointing loss at the reference geometry leaves the link in
    outage about 1.1 % of the time:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import loss_db_to_transmittance
    >>> log = DegradationLog()
    >>> probability = pointing_outage_probability(
    ...     loss_db_to_transmittance(1.0),
    ...     range_km=600.0,
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(probability), 5)
    0.01142

    Budgeting 3 dB instead buys nearly four orders of magnitude, which is the
    shape of a power law seen from the other side:

    >>> generous = pointing_outage_probability(
    ...     loss_db_to_transmittance(3.0),
    ...     range_km=600.0,
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> f"{float(generous):.2e}"
    '1.49e-06'
    """
    level = np.asarray(transmittance, dtype=np.float64)
    if not np.all(np.isfinite(level)):
        raise DomainError("transmittance contains non-finite values.")
    if np.any(level < 0.0) or np.any(level > 1.0):
        raise DomainError(
            "transmittance must lie in [0, 1]: it is the *relative* pointing factor, already "
            "normalised so that perfect pointing is 1, and the geometric coupling it multiplies "
            "lives in quoss.channel.beam.geometric_transmittance. A value above 1 usually means "
            "an absolute transmittance was passed. Range given: "
            f"[{float(np.min(level))}, {float(np.max(level))}]."
        )
    gamma = beam_to_jitter_ratio(
        range_km,
        jitter_rad=jitter_rad,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        degradations=degradations,
    )
    probability: FloatArray = level ** (gamma**2)
    return probability


def mean_pointing_transmittance(
    range_km: FloatArray | float,
    *,
    jitter_rad: float,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the average relative pointing transmittance.

    The mean of the power law ``F(x) = x^(gamma^2)``, which integrates to
    Ntanos et al. equation (8)'s ``I_pp = beta_p / (beta_p + 1)``::

        mean = gamma ^ 2 / (gamma ^ 2 + 1)

    **Provided with a warning about what it is for.** This is the right quantity
    for an average data rate over a long session, and the wrong one for a QKD
    link budget, because a QKD link is judged on its bad moments: the key rate
    is not linear in the transmittance, and a deep fade costs more key than a
    shallow one saves. At this repo's reference geometry the mean loss is
    0.22 dB while the 1-in-100 loss is 1.03 dB, a factor of five — so quoting
    the mean as "the pointing loss" understates the margin a real link needs.
    Use :func:`pointing_transmittance_quantile` for that.

    It is here because it is cheap, because it is published in two independent
    places, and because the ratio between it and the quantile is the single
    clearest statement of how skewed this distribution is.

    Parameters
    ----------
    range_km
        Distance from the transmitter, km, strictly positive. Any shape.
    jitter_rad
        R.m.s. residual pointing error per axis, radians.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.
    receive_aperture_m
        Diameter of the receiving aperture, m.
    degradations
        Log that receives a warning if the geometry leaves the published range
        of equation (9).

    Returns
    -------
    FloatArray
        The mean relative transmittance, between 0 and 1, shaped like
        ``range_km``.

    Raises
    ------
    DomainError
        If any argument fails its own guard.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import transmittance_to_loss_db
    >>> log = DegradationLog()
    >>> mean = mean_pointing_transmittance(
    ...     600.0,
    ...     jitter_rad=0.75e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(mean), 5)
    0.95104
    >>> round(float(transmittance_to_loss_db(mean)), 3)
    0.218

    A terminal with 3.3 urad of jitter instead of 0.75 has ``gamma`` near 1, and
    then the mean is exactly the wrong number to quote: it says 3 dB, while one
    per cent of the time the link is 20 dB down.

    >>> shaky = mean_pointing_transmittance(
    ...     600.0,
    ...     jitter_rad=3.3e-06,
    ...     wavelength_m=1.55e-06,
    ...     transmit_aperture_m=0.15,
    ...     receive_aperture_m=0.75,
    ...     degradations=log,
    ... )
    >>> round(float(transmittance_to_loss_db(shaky)), 2)
    3.0
    """
    gamma = beam_to_jitter_ratio(
        range_km,
        jitter_rad=jitter_rad,
        wavelength_m=wavelength_m,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        degradations=degradations,
    )
    exponent = gamma**2
    mean: FloatArray = exponent / (exponent + 1.0)
    return mean
