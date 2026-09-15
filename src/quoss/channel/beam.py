"""Beam geometry: how wide the beam gets, and how little of it lands in the telescope.

What this module is for
-----------------------
:mod:`quoss.channel.turbulence` answers "how much does the received power
*flicker*". This module answers the flat question underneath it: **how much
power arrives at all**, before any flicker, in a vacuum, with perfect pointing.

For a satellite QKD downlink that single number is the largest term in the whole
link budget — tens of decibels, against a couple of decibels for absorption and
a couple more for scintillation — and it comes from something very simple. Light
cannot be collimated perfectly. A beam leaving a 15 cm telescope spreads to
about 8 m across after 600 km, and a 0.75 m telescope on the ground intercepts
under 2 % of it. Everything else in the channel is a correction to that.

Three quantities, and what each is for
--------------------------------------
**Divergence.** How fast the beam widens, quoted as an angle. A beam is not a
ray: diffraction at the transmitting aperture forces an angular spread of
roughly "wavelength over aperture", so a *bigger* transmitter makes a *narrower*
beam. The convention used here (and the trap in it) is spelled out in
:func:`divergence_half_angle_rad`.

**Geometric coupling.** The fraction of the transmitted power that falls inside
the receiving aperture, :func:`geometric_transmittance`. This is the tens of
decibels. It is pure geometry: two apertures, one range, one wavelength.

**Beam wander.** Turbulence near the transmitter tilts the whole beam, so its
centre wanders around the aim point instead of sitting on it. This one is
**uplink-only**, for a reason ITU-R P.1622 §4.3 states outright, and the
functions are named ``uplink_*`` so that using them for a downlink has to be a
deliberate act. See :func:`uplink_beam_wander_angle_rad`.

The transmit aperture appears twice, pulling opposite ways
----------------------------------------------------------
This is the one design conclusion in the module that is not obvious, and it is
measurable here rather than a matter of taste.

Making the transmitting telescope bigger narrows the beam as ``1/D_T``
(:func:`divergence_half_angle_rad`), which is the whole reason to want a big
telescope. But it reduces beam wander only as ``D_T^(-1/6)``
(:func:`uplink_beam_wander_angle_rad`), because wander is set by the wavefront
tilt averaged across the aperture, and averaging over a wider aperture removes
tilt slowly. So the ratio *wander / divergence* **grows** as ``D_T^(5/6)``:
narrowing the beam does not help an uplink past the point where the beam is
thinner than its own jitter.

Measured in this repo, at 1550 nm under the nominal ITU profile, straight up
(``tests/channel/test_beam.py::TestTheTransmitApertureCutsBothWays``):

=========  =====================  ==================  ==================
``D_T``    divergence half-angle  r.m.s. wander       wander/divergence
=========  =====================  ==================  ==================
5 cm       19.7 urad              5.12 urad           0.26
15 cm      6.58 urad              4.27 urad           0.65
1 m        0.99 urad              3.11 urad           **3.15**
=========  =====================  ==================  ==================

A 1 m uplink transmitter therefore spends most of its time pointing its beam
somewhere other than at the spacecraft, and no amount of extra aperture fixes
it. It is also exactly what ITU-R P.1622 §4.3 says in prose — beam wander "can
be on the order of a beamwidth" — turned into a number.

What is deliberately not in here
--------------------------------
**Turbulence-induced beam spreading**, and on the recommendation's own
authority. ITU-R P.1622 §4.4: beam spreading "is typically very small with
respect to divergence and does not account for an appreciable loss of signal in
either the Earth-to-space or space-to-Earth directions". So the beam radius here
is the vacuum-diffraction one, and that omission is a quoted decision rather
than an oversight.

**Pointing error and its fading.** Beam wander is turbulence moving the beam;
pointing error is the terminal aiming it wrongly. They add, they have different
statistics, and the second one plus its outage statistics is
``channel/pointing.py``. The downlink counterpart of wander — turbulence moving
the *arriving* wavefront, ITU-R P.1622 equation (10) — belongs there too, because
what it disturbs is the tracking loop, not the beam width.

**Truncation at the transmitting aperture.** Taking the beam waist radius as
``D_T / 2`` (the convention of the source, see
:func:`divergence_half_angle_rad`) means the transmitter's own aperture clips
the Gaussian tails: ``1 - exp(-2) = 86.5 %`` of the power gets out, and the
missing 13.5 % is a flat **0.63 dB** that this module does not apply. Every
transmittance here is therefore a fraction *of the power in the beam*, not of
the power at the laser. That is one number, it belongs where all the fixed
losses are collected, and ``channel/link_budget.py`` is where it will be
applied.

Where these numbers come from
-----------------------------
Divergence and the coupling identity: **Ntanos et al. 2021**, *Photonics*
8(12):544, equations (2)-(6) — open access, numbered, and with declared system
parameters. Beam wander: **ITU-R P.1622** §4.3, equations (11a) and (11b) —
free and numbered.

One finding, because a citation is a promise somebody can check and this one
does not close. Ntanos et al. equation (5) prints the transmitter gain as
``G_t = (8 / w_0)^2``. The product ``G_t G_r L_fsl`` of their equations (3) and
(5) is the geometric coupling, and with ``G_t = 8 / w_0^2`` — the standard
optical-antenna form — that product is **exactly** the Gaussian result derived
in :func:`geometric_transmittance`, to the last digit. As printed, with the
square outside, it is **8x larger, i.e. 9.03 dB optimistic**, and at the
paper's own largest ground aperture (2.3 m at 600 km) it returns a transmittance
of **1.36** — more power collected than transmitted. This module uses the form
that conserves energy, ``tests/channel/test_beam.py::TestPublishedGainProduct``
asserts both halves of that statement, and the discrepancy is recorded in
``tests/golden/README.md`` rather than quietly fixed.

======================  ====================================================
Symbol                  Meaning
======================  ====================================================
``D_T``                 transmitting aperture diameter (m)
``D_r``                 receiving aperture diameter (m)
``w_t``                 beam waist radius at the transmitter, ``D_T / 2`` (m)
``theta_div``           divergence half-angle, ``2 lambda / (pi D_T)`` (rad)
``z_R``                 Rayleigh range, ``pi w_t^2 / lambda`` (m)
``W(z)``                beam radius at range ``z``, at ``1/e^2`` (m)
``eta_geo``             geometric transmittance (dimensionless, 0 to 1)
``mu``                  integrated ``C_n^2`` over height (m^(1/3))
``sigma_wc``            r.m.s. beam wander angle (rad)
``sigma_rc``            r.m.s. beam wander displacement (m)
======================  ====================================================

References
----------
A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
§3.1-§3.3 (equations (2), (3), (5), (6)) and §4.1 (system parameters).

Recommendation ITU-R P.1622 (04/2003), *Prediction methods required for the
design of Earth-space systems operating between 20 THz and 375 THz*, §4.3
(equations (11a), (11b)) and §4.4 (beam spreading).

A. A. Farid and S. Hranilovic, "Outage Capacity Optimization for Free-Space
Optical Links With Pointing Errors", *J. Lightwave Technol.* **25**(7):1702,
2007, §III-C equation (7) for the Gaussian irradiance profile and equation (8)
for the collected fraction. The rest of that paper is
:mod:`quoss.channel.pointing`.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from quoss.channel._validation import (
    validated_elevation,
    validated_positive_length_m,
    validated_wavelength_m,
)
from quoss.channel.atmosphere import ITU_GROUND_CN2_M23, integrated_cn2_m13
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import km_to_m

__all__ = [
    "BEAM_WANDER_ANGLE_COEFFICIENT",
    "BEAM_WANDER_DISPLACEMENT_COEFFICIENT",
    "UPLINK_WANDER_BEAMWIDTH_LIMIT",
    "beam_radius_m",
    "divergence_half_angle_rad",
    "geometric_transmittance",
    "rayleigh_range_km",
    "uplink_beam_wander_angle_rad",
    "uplink_beam_wander_displacement_m",
    "uplink_wander_to_divergence_ratio",
]

BEAM_WANDER_ANGLE_COEFFICIENT: Final[float] = 2.08
"""Coefficient of ITU-R P.1622 equation (11b), the r.m.s. wander *angle*.

Dimensionless, and that is worth checking rather than assuming: what it
multiplies is ``sqrt(mu / (D_T^(1/3) sin theta))``, and ``mu`` carries m^(1/3)
(P.1622 equation (9)) against the m^(1/3) of ``D_T^(1/3)``, so the square root
is a pure number and the result is an angle in radians.
"""

BEAM_WANDER_DISPLACEMENT_COEFFICIENT: Final[float] = 2080.0
"""Coefficient of ITU-R P.1622 equation (11a), the r.m.s. wander *displacement*.

It is :data:`BEAM_WANDER_ANGLE_COEFFICIENT` times 1000, and not because the
physics changed: equation (11a) takes its propagation distance ``L`` **in
kilometres** and returns metres, so the factor of 1000 is the unit crossing,
which the recommendation itself makes explicit by writing equation (11b) as
``sigma_rc / (L x 10^3)``.

That is exactly why :func:`uplink_beam_wander_displacement_m` is built as
"angle times range in metres" instead of transcribing 2080: passing a range in
metres to the 2080 form is a silent factor-1000 error, and there is no shape or
sign check that would catch it.
``tests/channel/test_beam.py::TestPublishedBeamWander`` asserts the two printed
forms agree.
"""

UPLINK_WANDER_BEAMWIDTH_LIMIT: Final[float] = 1.0
"""Wander/divergence ratio above which an uplink is no longer a pointed link.

When the r.m.s. wander angle reaches the divergence half-angle, turbulence is
throwing the beam centre a full beam radius off the aim point, so for a
substantial fraction of the time the spacecraft is *outside* the beam. A mean
transmittance computed from the on-axis geometry then describes a situation that
does not occur, and it does so without ever leaving [0, 1].

The threshold is 1 because that is where the displacement equals the beam
radius, not because a fit was tuned there — the same reasoning as
:data:`quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT`. Crossing it
records a :class:`~quoss.core.errors.Severity.WARNING`; nothing is substituted.
"""

_WAIST_RADIUS_PER_DIAMETER: Final[float] = 0.5
"""Beam waist radius as a fraction of the transmitting aperture diameter.

Named because it is a **modelling convention, not a law**, and it is the single
assumption every number in this module inherits. Ntanos et al. equation (6)
fixes it implicitly: ``theta_div = 2 lambda / (pi D_T)`` is the far-field
divergence of a Gaussian whose waist radius is ``D_T / 2``, so the source has
chosen to identify the ``1/e^2`` beam radius with the aperture *radius*.

Other conventions exist and differ by tens of percent — truncating at
``w_t = D_T / 2.2`` maximises on-axis far-field intensity for a hard-edged
aperture, for instance — so the convention is stated here, and the 13.5 % of
power it clips at the transmitter is declared in the module docstring instead of
being folded in silently.
"""


def _validated_range_km(range_km: FloatArray | float) -> FloatArray:
    """Return the range as an array, rejecting zero and negative distances."""
    ranges = np.asarray(range_km, dtype=np.float64)
    if not np.all(np.isfinite(ranges)):
        raise DomainError("range_km contains non-finite values.")
    if np.any(ranges <= 0.0):
        raise DomainError(
            "range_km must be strictly positive: a transmitter and a receiver at the same point "
            "have no beam between them, and every formula here divides by the range. Range "
            f"given: [{float(np.min(ranges))}, {float(np.max(ranges))}] km. The unit is "
            "kilometres, matching quoss.orbits.geometry.LookAngles.range_km."
        )
    return ranges


def divergence_half_angle_rad(*, wavelength_m: float, transmit_aperture_m: float) -> float:
    """Return the far-field divergence half-angle of the transmitted beam, rad.

    Ntanos et al. 2021 §3.3 equation (6)::

        theta_div = 2 lambda / (pi D_T)

    What it is: light leaving an aperture of diameter ``D_T`` cannot stay
    parallel. Diffraction spreads it into a cone, and this is the half-angle of
    that cone measured to where the irradiance has fallen to ``1/e^2`` (13.5 %)
    of its on-axis value. At range ``z`` the beam radius is ``theta_div * z``,
    so this one angle sets the whole geometric budget.

    Why a *half*-angle, and why that matters more than it should. The source
    writes this quantity ``w_0``, which in the standard optics literature means
    the beam waist *radius in metres* — a different quantity with different
    units. Worse, divergence is quoted both ways in practice: the same beam is
    "6.6 urad" (half-angle) or "13 urad" (full angle). The paper does both, and
    consistently: equation (6) gives the half-angle, while §4.1 describes the
    same 0.15 m transmitter at 1550 nm as "providing a small beam divergence of
    about 13 urad" — the full angle, twice equation (6). Reading one as the other
    is a factor of 2 in angle and therefore **6 dB** in received power. Hence the
    name here says ``half_angle`` and the suffix says ``rad``.

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m. The waist radius is taken as
        half of it (see ``_WAIST_RADIUS_PER_DIAMETER``).

    Returns
    -------
    float
        The divergence half-angle, radians.

    Raises
    ------
    DomainError
        If the wavelength or the aperture is not finite and positive.

    Examples
    --------
    The transmitter Ntanos et al. §4.1 declares — 0.15 m at 1550 nm — for which
    the paper quotes "about 13 urad" as the full angle:

    >>> half_angle = divergence_half_angle_rad(wavelength_m=1.55e-06, transmit_aperture_m=0.15)
    >>> f"{half_angle:.3e}"
    '6.578e-06'
    >>> round(2.0 * half_angle * 1e6, 1)
    13.2

    Doubling the telescope halves the divergence, which is the entire argument
    for a large transmitter:

    >>> big = divergence_half_angle_rad(wavelength_m=1.55e-06, transmit_aperture_m=0.30)
    >>> round(half_angle / big, 3)
    2.0
    """
    wavelength = validated_wavelength_m(wavelength_m)
    diameter = validated_positive_length_m(
        "transmit_aperture_m",
        transmit_aperture_m,
        hint="The unit is metres: an aperture given in centimetres would report a beam ten "
        "times wider than it is.",
    )
    return 2.0 * wavelength / (np.pi * diameter)


def rayleigh_range_km(*, wavelength_m: float, transmit_aperture_m: float) -> float:
    """Return the Rayleigh range of the transmitted beam, km.

    The Rayleigh range is where the beam has grown to ``sqrt(2)`` times its
    waist radius; it is the boundary between "the beam is still roughly the size
    of the telescope" (near field) and "the beam grows in proportion to the
    distance" (far field)::

        z_R = pi w_t^2 / lambda,     w_t = D_T / 2

    Why it is exposed rather than kept private: it is the number that says
    whether the far-field shorthand ``W = theta_div * z`` is legitimate. For a
    satellite link it always is, by a wide margin — the Rayleigh range of a
    15 cm terminal at 1550 nm is 11 km, against a 600 km slant range — and
    :func:`beam_radius_m` does not use the shorthand anyway. Quoting the number
    is what turns "far field, obviously" into a checkable claim.

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.

    Returns
    -------
    float
        The Rayleigh range, kilometres.

    Raises
    ------
    DomainError
        If the wavelength or the aperture is not finite and positive.

    Examples
    --------
    >>> round(rayleigh_range_km(wavelength_m=1.55e-06, transmit_aperture_m=0.15), 1)
    11.4

    It grows as the *square* of the aperture, so a metre-class terminal is still
    in its near field at the altitude of the ISS:

    >>> round(rayleigh_range_km(wavelength_m=1.55e-06, transmit_aperture_m=1.0), 0)
    507.0
    """
    wavelength = validated_wavelength_m(wavelength_m)
    diameter = validated_positive_length_m("transmit_aperture_m", transmit_aperture_m)
    waist_m = _WAIST_RADIUS_PER_DIAMETER * diameter
    range_m = np.pi * waist_m * waist_m / wavelength
    return float(range_m / km_to_m(1.0))


def beam_radius_m(
    range_km: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
) -> FloatArray:
    """Return the ``1/e^2`` radius of the beam at one or more ranges, m.

    Exact Gaussian propagation, not the far-field shorthand::

        W(z) = w_t sqrt(1 + (z / z_R)^2),    w_t = D_T / 2

    "``1/e^2`` radius" means the radius at which the irradiance has fallen to
    13.5 % of the value on the axis; 86.5 % of the power is inside it. It is the
    standard way to give a size to something that has no edge.

    Why the exact form when everyone writes ``W = theta_div * z``: the exact
    expression costs one square root, cannot be wrong in the near field, and
    makes the far-field claim measurable instead of assumed. Measured here, for a
    15 cm terminal at 1550 nm: the shorthand is low by **1.8e-4 relative at
    600 km**, by 6.5e-3 at 100 km, and by a factor of ``sqrt(2)`` at the Rayleigh
    range itself, where it is simply wrong. Since 1.8e-4 in radius is 3.6e-4 in
    collected power — 0.0016 dB — the shorthand would have been defensible; the
    point is that the number is now in a test rather than in someone's memory.

    Parameters
    ----------
    range_km
        Distance from the transmitter, km, strictly positive. Any shape;
        typically ``(n_samples,)`` from
        :attr:`quoss.orbits.geometry.LookAngles.range_km`.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting aperture, m.

    Returns
    -------
    FloatArray
        The beam radius in metres, shaped like ``range_km``.

    Raises
    ------
    DomainError
        If any range is non-positive or non-finite, or the wavelength or
        aperture is not finite and positive.

    Examples
    --------
    A 15 cm transmitter at 1550 nm, seen from 600 km away — a beam about 8 m
    across, from a telescope 15 cm across:

    >>> radius = beam_radius_m(600.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15)
    >>> round(float(radius), 2)
    3.95

    Vectorised over the time axis of a pass, and the growth is very nearly
    linear in range because 600 km is deep in the far field:

    >>> import numpy as np
    >>> radii = beam_radius_m(
    ...     np.array([400.0, 600.0, 1200.0]), wavelength_m=1.55e-06, transmit_aperture_m=0.15
    ... )
    >>> np.round(radii, 2)
    array([2.63, 3.95, 7.89])
    """
    ranges_km = _validated_range_km(range_km)
    wavelength = validated_wavelength_m(wavelength_m)
    diameter = validated_positive_length_m("transmit_aperture_m", transmit_aperture_m)
    waist_m = _WAIST_RADIUS_PER_DIAMETER * diameter
    rayleigh_m = np.pi * waist_m * waist_m / wavelength
    radius: FloatArray = waist_m * np.sqrt(1.0 + (km_to_m(ranges_km) / rayleigh_m) ** 2)
    return radius


def geometric_transmittance(
    range_km: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
) -> FloatArray:
    """Return the fraction of the transmitted power that enters the receiver.

    The beam is a Gaussian of total power ``P`` and radius ``W``, so its
    irradiance at a distance ``r`` from the axis is
    ``I(r) = (2P / (pi W^2)) exp(-2 r^2 / W^2)`` — Farid & Hranilovic 2007
    equation (7), which is where the ``2 / pi W^2`` normalisation can be checked
    rather than rederived. Integrating that over a circular aperture of radius
    ``a`` centred on the axis is elementary — the substitution
    ``u = 2 r^2 / W^2`` turns it into ``exp(-u) du`` — and gives::

        eta_geo = 1 - exp(-2 a^2 / W^2) = 1 - exp(-D_r^2 / (2 W^2))

    Three things follow, and each is a reason to prefer this form to the
    published product of gains discussed in the module docstring:

    1. **It cannot exceed 1.** As the receiver grows it collects the whole beam
       and saturates. The small-aperture limit of the same expression,
       ``D_r^2 / (2 W^2)``, is what the literature's gain product evaluates to,
       and *that* form passes 1 without complaint.
    2. **It is exact for the model it states.** No far-field or small-aperture
       approximation is left implicit.
    3. **It errs the safe way.** Where the two differ, this one is the smaller:
       at 2.3 m and 600 km it gives 8.07 dB of loss against the linearised
       7.70 dB.

    And it has a **second, independent published source**, which is the strongest
    thing that can be said for a formula in this project. Farid & Hranilovic
    2007 equation (8) writes the same collected fraction as an explicit double
    integral over the detector area, for the general case of a beam displaced
    from the aperture centre. At zero displacement that integral is this
    expression, and
    ``tests/channel/test_pointing.py::TestAgainstTheExactIntegral`` evaluates it
    numerically and finds agreement to eight digits. Two papers fourteen years
    apart, one via antenna gains and one via a surface integral, arriving at the
    same number.

    What it assumes, and therefore what it is not: perfect pointing (the beam is
    centred on the receiver), no central obstruction in the receiving telescope,
    vacuum, and the beam-waist convention of
    :func:`divergence_half_angle_rad`. Pointing error is ``channel/pointing.py``;
    absorption is :mod:`quoss.channel.atmosphere`; the 0.63 dB clipped at the
    transmitter is in the module docstring.

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

    Returns
    -------
    FloatArray
        Transmittance between 0 and 1, shaped like ``range_km``. Convert to
        decibels with :func:`quoss.core.units.transmittance_to_loss_db`.

    Raises
    ------
    DomainError
        If any range is non-positive or non-finite, or either aperture or the
        wavelength is not finite and positive.

    Examples
    --------
    The Ntanos et al. §4.1 downlink — 0.15 m transmitter, 0.75 m ground
    telescope, 1550 nm — at 600 km. Under 2 % of the light gets in, which is
    17.5 dB, and this single term dominates the link budget:

    >>> from quoss.core.units import transmittance_to_loss_db
    >>> eta = geometric_transmittance(
    ...     600.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15, receive_aperture_m=0.75
    ... )
    >>> f"{float(eta):.5f}"
    '0.01788'
    >>> round(float(transmittance_to_loss_db(eta)), 2)
    17.48

    Their largest station, 2.3 m, buys 9.4 dB of that back — the reason the
    paper's own conclusion is that a large receiving telescope is what makes the
    link close:

    >>> big = geometric_transmittance(
    ...     600.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15, receive_aperture_m=2.3
    ... )
    >>> round(float(transmittance_to_loss_db(big)), 2)
    8.07

    A receiver much wider than the beam collects nearly all of it, and the
    formula saturates instead of promising more than was sent:

    >>> everything = geometric_transmittance(
    ...     1.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15, receive_aperture_m=2.0
    ... )
    >>> round(float(everything), 6)
    1.0
    """
    radius_m = beam_radius_m(
        range_km, wavelength_m=wavelength_m, transmit_aperture_m=transmit_aperture_m
    )
    receiver_m = validated_positive_length_m(
        "receive_aperture_m",
        receive_aperture_m,
        hint="The unit is metres: a 0.75 m telescope entered as 75 would collect 10 000 times "
        "too much light.",
    )
    transmittance: FloatArray = 1.0 - np.exp(
        -(receiver_m * receiver_m) / (2.0 * radius_m * radius_m)
    )
    return transmittance


def uplink_beam_wander_angle_rad(
    elevation_rad: FloatArray | float,
    *,
    transmit_aperture_m: float,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the r.m.s. angular wander of an uplink beam, rad.

    ITU-R P.1622 §4.3 equation (11b)::

        sigma_wc = 2.08 sqrt( integral(Cn2 dh) / (D_T^(1/3) sin(theta)) )

    What wander is, and how it differs from the flicker in
    :mod:`quoss.channel.turbulence`. A beam leaving the ground is only 15 cm
    wide, which is comparable to the size of the turbulent cells it first meets.
    Those cells act as weak prisms across the *whole* beam, so instead of
    scrambling it internally they deflect it bodily: the beam stays a beam and
    the aim point moves. Scintillation redistributes power inside the beam;
    wander moves the beam.

    Why this is an uplink quantity, and why the name says so. P.1622 §4.3:
    "Beam wander is significant in the Earth-to-space direction and can be on
    the order of a beamwidth", and "Beam wander is not a significant problem in
    the space-to-Earth direction. Beams travelling in this direction only
    propagate through turbulence in the final 10 to 20 km of the path." A
    downlink beam arrives already several metres wide, so tilting the last 20 km
    of its path moves it by centimetres. Same asymmetry as
    :func:`quoss.channel.turbulence.uplink_log_irradiance_variance`, and handled
    the same way: by naming, so that reaching for it in a downlink budget is
    visible in the diff.

    The aperture dependence is the surprising part: ``D_T^(-1/6)``, gentle enough
    that a bigger transmitter loses the race against its own narrowing beam.
    The module docstring measures that.

    One thing this module does **not** claim. P.1622 gives the arriving-wavefront
    angle-of-arrival variance in equation (10) with the identical structure,
    ``2.914 mu D_R^(-1/3) / sin(theta)``, while squaring the 2.08 here gives
    ``4.326 mu D_T^(-1/3) / sin(theta)`` — the same shape with a coefficient
    1.485 times larger. The recommendation does not explain the difference, and
    the plausible reason (equation (10) describes a plane wave filling the
    aperture, this one a narrow beam leaving it) is not stated there, so it is
    recorded rather than asserted. Both are transcribed as printed.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive. Any shape.
    transmit_aperture_m
        Diameter of the transmitting aperture, m — the ground terminal's, since
        this is an uplink.
    station_height_m
        Altitude of the ground station above mean sea level, m; see
        :mod:`quoss.channel.atmosphere` on what the recommendation's
        "above ground level" means.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The r.m.s. wander angle in radians, shaped like ``elevation_rad``.

    Raises
    ------
    DomainError
        If any elevation is outside ``(0, pi/2]`` or non-finite, or the aperture
        is not finite and positive.

    Examples
    --------
    A 15 cm ground terminal pointing straight up through the nominal ITU
    profile wanders by 4.3 microradians r.m.s.:

    >>> from quoss.core.units import deg_to_rad
    >>> zenith = uplink_beam_wander_angle_rad(deg_to_rad(90.0), transmit_aperture_m=0.15)
    >>> round(float(zenith) * 1e6, 2)
    4.26

    Low on the horizon there is more atmosphere in the way, and the growth is
    exactly ``sin(theta)^(-1/2)`` — much gentler than the ``sin^(-11/6)`` of
    scintillation, because wander is a first-order tilt:

    >>> low = uplink_beam_wander_angle_rad(deg_to_rad(20.0), transmit_aperture_m=0.15)
    >>> round(float(low / zenith), 3)
    1.71
    """
    elevation = validated_elevation(elevation_rad)
    diameter = validated_positive_length_m(
        "transmit_aperture_m",
        transmit_aperture_m,
        hint="The unit is metres. Note this is the *transmitting* aperture, which for an "
        "uplink is the ground terminal, not the spacecraft.",
    )
    integrated_cn2 = integrated_cn2_m13(
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
        station_height_m=station_height_m,
    )
    angle: FloatArray = BEAM_WANDER_ANGLE_COEFFICIENT * np.sqrt(
        integrated_cn2 / (diameter ** (1.0 / 3.0) * np.sin(elevation))
    )
    return angle


def uplink_beam_wander_displacement_m(
    elevation_rad: FloatArray | float,
    *,
    range_km: FloatArray | float,
    transmit_aperture_m: float,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the r.m.s. wander of an uplink beam at the spacecraft, m.

    ITU-R P.1622 §4.3 equation (11a), which is equation (11b) multiplied by the
    path length::

        sigma_rc = sigma_wc * L

    The recommendation prints (11a) with its own coefficient, 2080, and its own
    unit convention: ``L`` in **kilometres**, result in metres. That is
    reconstructed here as "angle times range in metres" instead of transcribing
    2080, because the two differ only by the km-to-m factor
    (:data:`BEAM_WANDER_DISPLACEMENT_COEFFICIENT` explains why) and a range
    handed to the 2080 form in metres would be wrong by exactly 1000 while
    remaining finite, positive and plausibly shaped.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    range_km
        Slant range from the ground terminal to the spacecraft, km. Broadcast
        against ``elevation_rad``, so a pass passes both as arrays of the same
        length.
    transmit_aperture_m
        Diameter of the transmitting (ground) aperture, m.
    station_height_m
        Altitude of the ground station above mean sea level, m; see
        :mod:`quoss.channel.atmosphere` on what the recommendation's
        "above ground level" means.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The r.m.s. displacement in metres, broadcast over both inputs.

    Raises
    ------
    DomainError
        If any elevation or range is out of range or non-finite, or the aperture
        is not finite and positive.

    Examples
    --------
    Straight up from a 15 cm terminal to a satellite 600 km away, the beam
    centre wanders 2.6 m — against a beam radius of 3.9 m at the same range,
    which is ITU-R P.1622's "on the order of a beamwidth" as a pair of numbers:

    >>> from quoss.core.units import deg_to_rad
    >>> displacement = uplink_beam_wander_displacement_m(
    ...     deg_to_rad(90.0), range_km=600.0, transmit_aperture_m=0.15
    ... )
    >>> round(float(displacement), 2)
    2.56
    >>> round(float(beam_radius_m(600.0, wavelength_m=1.55e-06, transmit_aperture_m=0.15)), 2)
    3.95
    """
    ranges_km = _validated_range_km(range_km)
    angle = uplink_beam_wander_angle_rad(
        elevation_rad,
        transmit_aperture_m=transmit_aperture_m,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    displacement: FloatArray = angle * km_to_m(ranges_km)
    return displacement


def uplink_wander_to_divergence_ratio(
    elevation_rad: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
    degradations: DegradationLog,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the r.m.s. wander angle in units of the divergence half-angle.

    The ratio of :func:`uplink_beam_wander_angle_rad` to
    :func:`divergence_half_angle_rad`, and the number that says whether an
    uplink geometry makes sense at all::

        ratio = sigma_wc / theta_div

    Both are angles, so the ratio is how far the beam centre strays measured in
    beam radii. Below 1 the spacecraft stays inside the beam and a mean
    transmittance describes the link. Above 1 it does not: the beam spends much
    of its time pointing elsewhere, the received power becomes a deep fading
    process rather than a level, and :func:`geometric_transmittance` — which
    assumes the beam is centred on the receiver — is answering a question nobody
    asked. Crossing :data:`UPLINK_WANDER_BEAMWIDTH_LIMIT` therefore records a
    warning; the value returned is unchanged.

    This function exists because the ratio grows with aperture
    (``D_T^(5/6)``, since divergence falls as ``D_T^(-1)`` and wander only as
    ``D_T^(-1/6)``), which is the opposite of what "bigger telescope, better
    link" suggests, and because nothing in the returned array of either
    ingredient would reveal it.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Diameter of the transmitting (ground) aperture, m.
    degradations
        Log that receives a warning if the wander reaches the divergence
        half-angle.
    station_height_m
        Altitude of the ground station above mean sea level, m; see
        :mod:`quoss.channel.atmosphere` on what the recommendation's
        "above ground level" means.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The dimensionless ratio, shaped like ``elevation_rad``.

    Raises
    ------
    DomainError
        If any elevation is outside ``(0, pi/2]``, or the wavelength or aperture
        is not finite and positive.

    Examples
    --------
    A 15 cm uplink terminal at 1550 nm, straight up, is comfortably inside its
    own beam:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import deg_to_rad
    >>> log = DegradationLog()
    >>> ratio = uplink_wander_to_divergence_ratio(
    ...     deg_to_rad(90.0), wavelength_m=1.55e-06, transmit_aperture_m=0.15, degradations=log
    ... )
    >>> round(float(ratio), 3)
    0.648
    >>> len(log)
    0

    A metre-class terminal, same site and same sky, is not — and it says so
    rather than returning a comfortable-looking transmittance:

    >>> big = uplink_wander_to_divergence_ratio(
    ...     deg_to_rad(90.0), wavelength_m=1.55e-06, transmit_aperture_m=1.0, degradations=log
    ... )
    >>> round(float(big), 2)
    3.15
    >>> log.entries[0].code
    'beam.uplink-wander-exceeds-divergence'
    """
    wander = uplink_beam_wander_angle_rad(
        elevation_rad,
        transmit_aperture_m=transmit_aperture_m,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    divergence = divergence_half_angle_rad(
        wavelength_m=wavelength_m, transmit_aperture_m=transmit_aperture_m
    )
    ratio: FloatArray = wander / divergence

    # An empty time axis is a pass that has not started, not an error: nothing
    # to warn about, and `np.max` of nothing raises. Same guard as
    # `detector.observed_count_rate_cps`.
    peak = float(np.max(ratio)) if ratio.size else 0.0
    if peak > UPLINK_WANDER_BEAMWIDTH_LIMIT:
        degradations.warn(
            "beam.uplink-wander-exceeds-divergence",
            (
                f"Uplink beam wander reaches {peak:.2f} times the divergence half-angle, above "
                f"the {UPLINK_WANDER_BEAMWIDTH_LIMIT} where the beam centre strays a full beam "
                "radius off the aim point. ITU-R P.1622 §4.3 puts uplink wander 'on the order "
                "of a beamwidth', so this is the expected regime, not a numerical failure — but "
                "geometric_transmittance assumes the beam is centred on the receiver, and at "
                "this ratio the link is a fading process rather than a level."
            ),
            where="quoss.channel.beam.uplink_wander_to_divergence_ratio",
            peak_ratio=peak,
            limit=UPLINK_WANDER_BEAMWIDTH_LIMIT,
            transmit_aperture_m=float(transmit_aperture_m),
        )
    return ratio
