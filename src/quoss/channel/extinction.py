"""Atmospheric extinction from visibility: the number the budget used to be handed.

What extinction is, for whoever arrives new
-------------------------------------------
Light crossing air loses power two ways that have nothing to do with turbulence.
**Absorption** is a molecule swallowing a photon and turning it into heat.
**Scattering** is a molecule or a suspended particle sending the photon off in
another direction. Together they are **extinction**: light that leaves the
transmitter and never reaches the receiver, gone rather than merely rearranged.
Turbulence, by contrast, moves light around — a photon that scintillates away
this millisecond comes back the next — and cloud is not a loss at all but an
outage, the pass simply not happening (:mod:`quoss.system.pcflos`).

Extinction is measured as a **specific attenuation**, decibels per kilometre of
path. Beer-Lambert says the loss in decibels grows linearly with the path
length, so a specific attenuation times a length is a loss, and a vertical
column of air has a single number of its own: the **zenith transmittance**, the
fraction of light that survives straight up through the whole atmosphere.

Why this module exists
----------------------
Until it did, QuOSS did not model extinction — it *received* it.
:func:`quoss.channel.link_budget.atmospheric_transmittance` takes
``zenith_transmittance`` as a required argument with no default, and
:func:`quoss.channel.horizontal.horizontal_loss_budget` takes
``extinction_db_per_km`` the same way, both because of gap 14 of
``docs/adr/0009-citation-policy.md``: the **scaling law** is published (Ntanos
et al. 2021 equation (7)) and the **number it scales** is not, and ITU-R
P.1621-2 prints absorption (§2) and scattering (§3) only as Figures 1, 2 and 4 —
plots, with no table and no closed form beside them. That gap was real, and it
was also incomplete: a *different* ITU recommendation prints a closed form for
the dominant term, numbered, with two independent published tables to check it
against. This module is that closed form. See
``docs/adr/0023-traceable-extinction.md``.

The dominant term is aerosol scattering, and visibility measures it
-------------------------------------------------------------------
An **aerosol** is a solid or liquid particle small enough to stay suspended:
dust, salt, smoke, haze droplets, fog droplets. Their radii — hundredths to
tens of micrometres — bracket the wavelengths a QKD link uses, and a particle
the size of the wavelength scatters far more strongly than a molecule does
(ITU-R P.1814 Table 1: ``Q ~ lambda^-4`` for molecules against ``lambda^-1.6``
to ``lambda^0`` for aerosols). So aerosols dominate, and the obstacle is that
nobody knows the particle size distribution over a given path at a given hour.

**Visibility** solves that. Visibility, or visual range, is *defined* as the
distance over which light falls to 2 % of its original power, and it is recorded
hourly at every airport in the world. Inverting the definition —
``exp(-sigma V) = 0.02``, so ``sigma = ln(1/0.02)/V = 3.912/V`` — turns an
archived meteorological number into an extinction coefficient at the wavelength
where visibility is defined, 550 nm. Scaling it to the wavelength in use needs
one exponent, and that exponent is what the two laws below disagree about.

The two laws, and why the choice is in the signature
----------------------------------------------------
:class:`VisibilityScalingLaw` has two members and **no default**, for the same
reason :class:`quoss.channel.turbulence.PathWave` has none: the two are
different physics below half a kilometre of visibility, and which one is right
decides a hardware question.

* :attr:`VisibilityScalingLaw.ITU_P1814` — ITU-R P.1814 equations (4) and (5),
  which are Kim et al. 2001 equation (6), which is the law Kruse published:
  ``q = 1.6`` above 50 km of visibility, ``1.3`` between 6 and 50 km, and
  ``0.585 V^(1/3)`` below 6 km.
* :attr:`VisibilityScalingLaw.KIM_2001` — the same equation with Kim et al.
  2001 equation (9) replacing the third branch: ``q = 0`` in fog below 500 m,
  ``q = V - 0.5`` in the mist between 500 m and 1 km, ``q = 0.16 V + 0.34`` in
  the haze from 1 to 6 km.

The hardware question is whether 1550 nm sees through fog better than 780 nm.
Kruse's ``0.585 V^(1/3)`` says yes: at 50 m of visibility it leaves ``q = 0.22``,
so 1550 nm is attenuated **314.6 dB/km against 271.7**, a 43 dB advantage over a
kilometre. Kim et al. say no, and their argument is not a preference: the data
Löhle fitted ``0.585 V^(1/3)`` to were collected in "fog and dense haze", which
Middleton had already flagged as doubtful below 1 km, and the measurements that
do exist in real fog show no wavelength dependence at all — fog droplets are
several micrometres across, twenty times a wavelength, which is the
**non-selective** regime where geometric optics applies and colour cannot
matter. With ``q = 0`` both wavelengths lose **339.6 dB/km** and the advantage
is exactly zero.

So the law is chosen at the call site, and both are reproduced against their
authors' own tables (32 published cells, ``tests/channel/test_extinction.py``).

What this module does *not* model, and what that is measured to cost
--------------------------------------------------------------------
**Molecular absorption is still a gap** — gap 14 is narrowed, not closed. Two
openable sources say in words that it is negligible at the wavelengths in use
(ITU-R P.1814 §4.1: "usually the laser wavelengths are selected to fall inside
atmospheric transmission windows, so ``gamma_clear_air`` is negligible"; Kim et
al. §3: "the contributions of absorption to the total attenuation coefficient
are very small"), and **neither prints a number**. ITU-R P.1621-2 Figures 1 and
2 are plots. HITRAN answers, and a line list is not a specific attenuation: the
conversion is a radiative-transfer computation of the LBLRTM/MODTRAN class,
which this project does not have and which would itself need verifying. So
there is no absorption function here, the argument stays required, and the
declaration is gap 23 of the citation policy.

**Molecular scattering is inside the visibility law already, at the wrong
exponent.** Visibility at 550 nm is set by *all* extinction, molecules
included, and the law then scales the whole coefficient by the aerosol
exponent. :func:`molecular_scattering_specific_attenuation_db_per_km` exists to
measure the mis-attribution rather than to correct it: at 550 nm the molecular
share is 3.1 % of the coefficient at 10 km of visibility and **15.2 % at
50 km**, and carrying that share to 1550 nm with ``q = 1.3`` or ``1.6`` instead
of its own ``lambda^-4`` leaves the total **2.9 % too high at 10 km and 14.0 %
too high at 50 km**. Subtracting it first and adding back Rayleigh is not what
either source publishes, so it is not what this module computes — gap 22.

Example with numbers
--------------------
"Very clear air" in ITU-R P.1817-1's own visibility code is 23 km. At 1550 nm
that is ``q = 1.3``, a specific attenuation of **0.192 dB/km**, and through an
aerosol layer of 1.2 km scale height a zenith loss of **0.230 dB**
(``L_zen = 0.948``). The same air at 785 nm costs 0.465 dB/km and 0.558 dB
vertically. Castelldefels culminates at 26 degrees on the reference orbit, where
the secant air mass is 2.28, so the modelled extinction there is 0.53 dB of a
budget whose total is about 30 — small, and it was previously being set to zero.

References
----------
Recommendation ITU-R P.1814 (08/2007), *Prediction methods required for the
design of terrestrial free-space optical links*, §4.1 and §4.2.1 equations (4)
and (5). Read in the ITU PDF; equation (4) is rendered as an image and read as
such, because its printed unit is wrong — see
:data:`KOSCHMIEDER_CONSTANT_P1814`.

Recommendation ITU-R P.1817-1 (02/2012), *Propagation data required for the
design of terrestrial free-space optical links*, §3 equations (3) and (4)
(molecular scattering), §12 equation (12) (the Koschmieder relation) and §12's
International Visibility Code table.

I. I. Kim, B. McArthur and E. Korevaar, "Comparison of laser beam propagation at
785 nm and 1550 nm in fog and haze for optical wireless communications",
*Proc. SPIE* **4214**:26 (2001), equations (5), (6) and (9) and Tables 2 and 4.
Read in the manuscript the second author hosts.

M. T. Gruneisen et al., "Adaptive-Optics-Enabled Quantum Communication: A
Technique for Daytime Space-To-Earth Links", *Phys. Rev. Applied* **16**,
014067 (2021), §III A — the published MODTRAN ratio between 775 nm and 1550 nm.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import numpy as np

from quoss.channel._validation import (
    MICROMETRES_PER_METRE,
    validated_positive_length_m,
    validated_wavelength_m,
)
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import m_to_km

__all__ = [
    "AEROSOL_EXPONENT_BRANCH_BOUNDARIES_KM",
    "KIM_FOG_VISIBILITY_KM",
    "KIM_MIST_VISIBILITY_KM",
    "KOSCHMIEDER_CONSTANT_P1814",
    "KOSCHMIEDER_CONSTANT_P1817",
    "MOLECULAR_SCATTERING_COEFFICIENT_KM_UM4",
    "MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA",
    "MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K",
    "NEPER_TO_DB",
    "VISIBILITY_REFERENCE_WAVELENGTH_M",
    "VisibilityScalingLaw",
    "aerosol_specific_attenuation_db_per_km",
    "molecular_scattering_specific_attenuation_db_per_km",
    "specific_attenuation_at_altitude_db_per_km",
    "visibility_scaling_exponent",
    "zenith_optical_depth_from_visibility",
    "zenith_transmittance_from_visibility",
]


# --------------------------------------------------------------------------- #
# Constants, each with the document it was read from
# --------------------------------------------------------------------------- #
NEPER_TO_DB: Final[float] = 10.0 / np.log(10.0)
"""4.3429: decibels per neper, for an amplitude-squared quantity.

An optical depth ``tau`` in nepers is a transmittance ``exp(-tau)``, which is
``-10 log10(exp(-tau)) = 10 tau / ln 10`` decibels of loss. It is the square
root of :data:`quoss.channel.turbulence.NEPER_SQ_TO_DB_SQ`, and a test asserts
that so the two cannot drift apart.
"""

VISIBILITY_REFERENCE_WAVELENGTH_M: Final[float] = 550.0e-9
"""The wavelength visibility is defined at, 550 nm.

ITU-R P.1817-1 §12: "It is measured at 550 nm, the wavelength that corresponds
to the maximum intensity of the solar spectrum." It is the ``550 nm`` in the
denominator of ITU-R P.1814 equation (4) and Kim et al. equation (6).
"""

KOSCHMIEDER_CONSTANT_P1814: Final[float] = 3.91
"""The numerator of ITU-R P.1814 equation (4) and Kim et al. equation (6).

It is ``ln(1/0.02) = 3.912`` rounded to three figures: the 2 % contrast
threshold in the definition of visual range, inverted. So the quantity the
equation returns is an extinction coefficient in **nepers per kilometre**.

**ITU-R P.1814 equation (4) says decibels per kilometre, and that is wrong by
the factor 4.343.** The statement was read from a rendered image of page 5, not
from a text layer, because a units label is exactly the sort of thing a text
extractor garbles. Two published tables settle it, both computed from this same
equation: Kim et al.'s Table 2 prints 14 dB/km at 1 km of visibility and 785 nm,
where the equation returns 3.91 -- ``4.343 * 3.91 * 0.812 = 13.8`` -- and ITU-R
P.1817-1's own International Visibility Code prints 13.8 at the same point.
Reading equation (4) as printed understates a 1 km fog by **9.9 dB/km**, and a
kilometre of it by 9.9 dB. Every function here returns decibels per kilometre
and has done the conversion once.
"""

KOSCHMIEDER_CONSTANT_P1817: Final[float] = 3.912
"""The same constant as ITU-R P.1817-1 §12 equation (12) prints it.

Two recommendations print the inversion of the same definition to three and
four figures. The difference is **0.051 %**, or 0.0002 dB/km at 23 km of
visibility; the four-figure value is the exact ``-ln(0.02) = 3.91202``. The
functions here use :data:`KOSCHMIEDER_CONSTANT_P1814`, because that is the
constant inside the equation they implement and inside the two tables they are
checked against. This one exists so the discrepancy is measured rather than
rediscovered.
"""

MOLECULAR_SCATTERING_COEFFICIENT_KM_UM4: Final[float] = 1.09e-3
"""``A`` of ITU-R P.1817-1 §3 equation (4), in km^-1 um^4.

Its equation (3) is ``beta_m(lambda) = A lambda^-4`` with ``lambda`` in
micrometres, and equation (4) gives ``A = 1.09e-3 (P/P0)(T0/T)``.
"""

MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA: Final[float] = 101_300.0
"""``P0`` of ITU-R P.1817-1 equation (4): 1013 mbar, written in pascals.

1013 mbar exactly, as the recommendation prints it -- not the 1013.25 hPa of the
standard atmosphere, which is a different number by 0.025 %.
"""

MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K: Final[float] = 273.15
"""``T0`` of ITU-R P.1817-1 equation (4): 273.15 K."""

KIM_FOG_VISIBILITY_KM: Final[float] = 0.5
"""Where Kim et al. equation (9) puts the fog/mist boundary, 500 m.

Below it their exponent is exactly zero and extinction is achromatic. The
boundary is Eldridge's, from observed particle size distributions, and it is the
visibility below which ITU-R P.1814's third branch is the one Kim et al. argue
against.
"""

KIM_MIST_VISIBILITY_KM: Final[float] = 1.0
"""Where Kim et al. equation (9) puts the mist/haze boundary, 1 km."""

_HAZE_VISIBILITY_KM: Final[float] = 6.0
"""Where both laws leave the ``q = 1.3`` branch, as equation (5) prints it."""

_CLEAR_VISIBILITY_KM: Final[float] = 50.0
"""Where both laws enter the ``q = 1.6`` branch."""

AEROSOL_EXPONENT_BRANCH_BOUNDARIES_KM: Final[tuple[float, ...]] = (
    KIM_FOG_VISIBILITY_KM,
    KIM_MIST_VISIBILITY_KM,
    _HAZE_VISIBILITY_KM,
    _CLEAR_VISIBILITY_KM,
)
"""Every visibility at which either law changes branch, in kilometres.

Only two of the four are **discontinuities**, and only for one of the laws --
see :func:`visibility_scaling_exponent`.
"""

_KRUSE_LOW_VISIBILITY_COEFFICIENT: Final[float] = 0.585
"""``0.585`` of ITU-R P.1814 equation (5) and Kim et al. equation (6)."""

_HAZE_EXPONENT: Final[float] = 1.3
"""``q`` for 6 km < V < 50 km, both laws."""

_CLEAR_EXPONENT: Final[float] = 1.6
"""``q`` for V > 50 km, both laws."""

_KIM_HAZE_SLOPE: Final[float] = 0.16
"""Slope of Kim et al. equation (9)'s haze segment, per kilometre."""

_KIM_HAZE_INTERCEPT: Final[float] = 0.34
"""Intercept of Kim et al. equation (9)'s haze segment."""

_WHERE = "quoss.channel.extinction"


class VisibilityScalingLaw(StrEnum):
    """Which published exponent turns a 550 nm extinction into one at ``lambda``.

    No default anywhere, on purpose: below 500 m of visibility the two are
    different physics and the difference is 43 dB over a kilometre at 1550 nm.
    See the module docstring.
    """

    ITU_P1814 = "itu-p1814"
    """ITU-R P.1814 equations (4)-(5); Kim et al. equation (6); Kruse's law."""

    KIM_2001 = "kim-2001"
    """ITU-R P.1814 equation (4) with Kim et al. equation (9) below 6 km."""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _validated_visibility_km(visibility_km: FloatArray | float) -> FloatArray:
    """Return the visibility as an array, rejecting anything that is not one.

    ``+inf`` is **allowed**, and is the reason this is not
    :func:`~quoss.channel._validation.validated_positive_length_m`: infinite
    visibility is the physically meaningful statement "no extinction", the limit
    the whole law has to reproduce, and it produces exactly zero attenuation
    rather than a ``nan``.
    """
    visibility = np.asarray(visibility_km, dtype=np.float64)
    if np.any(np.isnan(visibility)) or np.any(visibility <= 0.0):
        # min/max and not nanmin/nanmax: a nan propagates into the message,
        # which is the right thing to show, and nanmin warns about it instead.
        raise DomainError(
            "visibility_km must be positive (+inf allowed, meaning no extinction), got a range "
            f"of [{float(np.min(visibility))}, {float(np.max(visibility))}]. The unit is "
            "kilometres: dense fog is 0.05, very clear air is 23, and 1000 would be a "
            "visibility in metres handed over as kilometres."
        )
    return visibility


def _validated_positive(name: str, value: float, *, hint: str) -> float:
    """Return a finite, strictly positive scalar, named in the message.

    Not :func:`~quoss.channel._validation.validated_positive_length_m`, whose
    name promises a length: the two quantities validated here are a pressure and
    a temperature, and a message that called either a length would be the kind
    of small lie that ends up quoted in a traceback.
    """
    quantity = float(value)
    if not np.isfinite(quantity) or quantity <= 0.0:
        raise DomainError(f"{name} must be finite and positive, got {quantity}. {hint}".strip())
    return quantity


def _validated_altitude_m(name: str, value: float) -> float:
    """Return a finite altitude, which may be negative."""
    altitude = float(value)
    if not np.isfinite(altitude):
        raise DomainError(
            f"{name} must be finite, got {altitude}. The unit is metres above the ellipsoid, "
            "the same as StationSpec.altitude_m (ADR 0016), and it may be negative."
        )
    return altitude


# --------------------------------------------------------------------------- #
# The exponent
# --------------------------------------------------------------------------- #
def visibility_scaling_exponent(
    visibility_km: FloatArray | float,
    *,
    law: VisibilityScalingLaw,
) -> FloatArray:
    """Return ``q``, the exponent of the wavelength ratio, for each visibility.

    What it is
    ----------
    ``q`` is the power law by which aerosol scattering depends on wavelength:
    the specific attenuation goes as ``(lambda / 550 nm)^-q``. Physically it is
    a statement about particle size relative to wavelength -- ``q = 4`` is
    Rayleigh scattering off things much smaller than a wavelength, ``q`` around
    1.3 is Mie scattering off haze whose size is comparable to it, and ``q = 0``
    is geometric scattering off fog droplets much larger than it, where colour
    cannot matter. It is fitted to measurements, not derived, which is why two
    sources print two different fits below 6 km.

    Where the branches come from, and which joins are jumps
    ------------------------------------------------------
    ITU-R P.1814 equation (5) prints ``1.6`` above 50 km, ``1.3`` between 6 and
    50 km, and ``0.585 V^(1/3)`` below 6 km, with **strict** inequalities that
    leave 6 and 50 undefined. This function reads the intervals half-open --
    ``[6, 50)`` takes 1.3 and ``[50, inf)`` takes 1.6 -- and that is not a
    coin toss: ITU-R P.1817-1's own visibility code table prints 0.19 dB/km at
    exactly 50 km, which is the ``q = 1.6`` value (0.192) and not the ``q = 1.3``
    one (0.214).

    **Two of the four joins are discontinuities, and only under
    :attr:`VisibilityScalingLaw.ITU_P1814`.** At 6 km its third branch reaches
    ``0.585 * 6^(1/3) = 1.063`` where the next one starts at 1.300, a **22.3 %**
    step, which at 1550 nm is a **21.8 %** step down in specific attenuation
    (0.941 to 0.736 dB/km); at 50 km the step from 1.3 to 1.6 is 23.1 % in ``q``
    and **26.7 %** at 1550 nm. Kim et al. equation (9) removes the first one --
    ``0.16 * 6 + 0.34`` is exactly 1.3, and its own two joins at 500 m and 1 km
    are exact too (``0 = 0.5 - 0.5`` and ``1 - 0.5 = 0.16 + 0.34``) -- and their
    paper says so: equation (9) "transitions better to a q value of 1.3".
    Neither law removes the 50 km step.

    The step matters more than a percentage suggests, because it makes some
    extinctions unreachable. Through an aerosol layer of 1.2 km scale height at
    1550 nm, no visibility at all produces a zenith loss between **0.883 and
    1.129 dB** -- and the 0.906 dB residual of Ntanos et al.'s published budget
    (``docs/adr/0009-citation-policy.md`` gap 14) falls inside that window.

    Parameters
    ----------
    visibility_km
        Visual range, km, strictly positive; ``+inf`` allowed. Any shape.
    law
        Which published exponent to use. **No default.**

    Returns
    -------
    FloatArray
        ``q``, dimensionless, shaped like ``visibility_km``.

    Raises
    ------
    DomainError
        If any visibility is not positive, or is ``nan``.

    Examples
    --------
    The two laws are the same above 6 km and different below it:

    >>> v = np.array([0.05, 0.5, 1.0, 3.0, 10.0, 60.0])
    >>> visibility_scaling_exponent(v, law=VisibilityScalingLaw.ITU_P1814).round(4)
    array([0.2155, 0.4643, 0.585 , 0.8437, 1.3   , 1.6   ])
    >>> visibility_scaling_exponent(v, law=VisibilityScalingLaw.KIM_2001).round(4)
    array([0.  , 0.  , 0.5 , 0.82, 1.3 , 1.6 ])

    Infinite visibility sits on the clear-air branch, and the attenuation it
    produces is zero because the ``3.91/V`` in front of it is:

    >>> float(visibility_scaling_exponent(np.inf, law=VisibilityScalingLaw.KIM_2001))
    1.6
    """
    visibility = _validated_visibility_km(visibility_km)
    haze = np.full_like(visibility, _HAZE_EXPONENT)
    clear = np.full_like(visibility, _CLEAR_EXPONENT)

    if law is VisibilityScalingLaw.ITU_P1814:
        low: FloatArray = _KRUSE_LOW_VISIBILITY_COEFFICIENT * np.cbrt(visibility)
    else:
        low = np.where(
            visibility >= KIM_MIST_VISIBILITY_KM,
            _KIM_HAZE_SLOPE * visibility + _KIM_HAZE_INTERCEPT,
            np.where(visibility >= KIM_FOG_VISIBILITY_KM, visibility - KIM_FOG_VISIBILITY_KM, 0.0),
        )

    exponent: FloatArray = np.where(
        visibility >= _CLEAR_VISIBILITY_KM,
        clear,
        np.where(visibility >= _HAZE_VISIBILITY_KM, haze, low),
    )
    return exponent


def _discontinuities_km(law: VisibilityScalingLaw) -> tuple[float, ...]:
    """Return the branch boundaries where ``q`` jumps under this law."""
    if law is VisibilityScalingLaw.ITU_P1814:
        return (_HAZE_VISIBILITY_KM, _CLEAR_VISIBILITY_KM)
    return (_CLEAR_VISIBILITY_KM,)


# --------------------------------------------------------------------------- #
# Specific attenuation
# --------------------------------------------------------------------------- #
def aerosol_specific_attenuation_db_per_km(
    visibility_km: FloatArray | float,
    *,
    wavelength_m: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the specific attenuation from visibility, dB/km.

    ITU-R P.1814 equation (4), which is Kim et al. equation (6)::

        sigma(lambda) = (3.91 / V) (lambda / 550 nm)^-q     nepers per km

    converted once to decibels per kilometre. The ``3.91`` is the inversion of
    the 2 % definition of visual range, so the equation's own output is in
    nepers -- **not** the decibels its printed unit in P.1814 claims; see
    :data:`KOSCHMIEDER_CONSTANT_P1814` for the two published tables that settle
    it and for the 9.9 dB/km the misreading costs.

    Two warnings, and what each is for
    ----------------------------------
    ``extinction.kruse-exponent-below-the-fog-threshold`` fires under
    :attr:`VisibilityScalingLaw.ITU_P1814` below 500 m of visibility, the region
    Kim et al. argue the ``0.585 V^(1/3)`` fit does not describe, and carries
    both attenuations so the reader sees the size of the disagreement rather
    than being told it exists. The value returned is still the law that was
    asked for -- substituting the other one quietly is what
    ``docs/adr/0009-citation-policy.md`` forbids.

    ``extinction.visibility-spans-a-branch-boundary`` fires when the visibilities
    given reach a boundary where the chosen law's exponent **jumps**, because a
    time series of visibility crossing it produces a step in the answer that is
    an artefact of the fit and not weather.

    Parameters
    ----------
    visibility_km
        Visual range, km, strictly positive; ``+inf`` allowed. Any shape --
        vectorised over the time axis, which is the real case: visibility
        arrives as an hourly series from a weather archive.
    wavelength_m
        Optical wavelength, m.
    law
        Which published exponent. **No default.**
    degradations
        Log that receives the two warnings above.

    Returns
    -------
    FloatArray
        Specific attenuation, dB/km, non-negative, shaped like ``visibility_km``.

    Raises
    ------
    DomainError
        If any visibility is not positive, or the wavelength is not positive.

    Examples
    --------
    "Very clear air", 23 km, at 1550 nm and at 785 nm:

    >>> from quoss.core.errors import DegradationLog
    >>> itu, kim = VisibilityScalingLaw.ITU_P1814, VisibilityScalingLaw.KIM_2001
    >>> def gamma(v: float, nm: float, law: VisibilityScalingLaw) -> float:
    ...     got = aerosol_specific_attenuation_db_per_km(
    ...         v, wavelength_m=nm * 1e-9, law=law, degradations=DegradationLog()
    ...     )
    ...     return float(got)
    >>> [round(gamma(23.0, nm, kim), 4) for nm in (1550.0, 785.0)]
    [0.192, 0.4649]

    Dense fog at 50 m, where the two laws disagree and Kim et al.'s is
    achromatic:

    >>> [round(gamma(0.05, nm, itu), 1) for nm in (785.0, 1550.0)]
    [314.6, 271.7]
    >>> [round(gamma(0.05, nm, kim), 1) for nm in (785.0, 1550.0)]
    [339.6, 339.6]

    Infinite visibility is exactly transparent:

    >>> gamma(float("inf"), 1550.0, kim)
    0.0
    """
    visibility = _validated_visibility_km(visibility_km)
    wavelength = validated_wavelength_m(wavelength_m)
    ratio = wavelength / VISIBILITY_REFERENCE_WAVELENGTH_M
    exponent = visibility_scaling_exponent(visibility, law=law)

    nepers_per_km = (KOSCHMIEDER_CONSTANT_P1814 / visibility) * ratio ** (-exponent)
    attenuation: FloatArray = NEPER_TO_DB * nepers_per_km

    _warn_if_below_the_fog_threshold(visibility, ratio, law, degradations)
    _warn_if_a_branch_boundary_is_spanned(visibility, ratio, law, degradations)
    return attenuation


def _specific_attenuation_at(visibility_km: float, ratio: float, exponent: float) -> float:
    """Return dB/km at one visibility and one exponent, for a warning's payload."""
    return float(NEPER_TO_DB * (KOSCHMIEDER_CONSTANT_P1814 / visibility_km) * ratio**-exponent)


def _warn_if_below_the_fog_threshold(
    visibility: FloatArray,
    ratio: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> None:
    """Say, in fog, that the chosen exponent is the one Kim et al. dispute."""
    if law is not VisibilityScalingLaw.ITU_P1814 or not visibility.size:
        return
    lowest = float(np.min(visibility))
    if lowest >= KIM_FOG_VISIBILITY_KM:
        return
    kruse = float(visibility_scaling_exponent(lowest, law=VisibilityScalingLaw.ITU_P1814))
    kim = float(visibility_scaling_exponent(lowest, law=VisibilityScalingLaw.KIM_2001))
    as_kruse = _specific_attenuation_at(lowest, ratio, kruse)
    as_kim = _specific_attenuation_at(lowest, ratio, kim)
    degradations.warn(
        "extinction.kruse-exponent-below-the-fog-threshold",
        (
            f"Visibility reaches {lowest:.4g} km, below the {KIM_FOG_VISIBILITY_KM:.3g} km where "
            "Kim et al. 2001 equation (9) sets q = 0 because fog droplets are far larger than a "
            "wavelength. ITU-R P.1814 equation (5) gives q = "
            f"{kruse:.4f} there, so this wavelength is attenuated {as_kruse:.4g} dB/km against "
            f"{as_kim:.4g} dB/km achromatic — a factor {as_kim / as_kruse:.4g}. The value "
            "returned is P.1814's; VisibilityScalingLaw.KIM_2001 returns the other."
        ),
        where=f"{_WHERE}.aerosol_specific_attenuation_db_per_km",
        min_visibility_km=lowest,
        fog_threshold_km=KIM_FOG_VISIBILITY_KM,
        exponent_itu_p1814=kruse,
        exponent_kim_2001=kim,
        db_per_km_itu_p1814=as_kruse,
        db_per_km_kim_2001=as_kim,
    )


def _warn_if_a_branch_boundary_is_spanned(
    visibility: FloatArray,
    ratio: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> None:
    """Say when the visibilities reach a boundary at which the fit jumps."""
    if not visibility.size:
        return
    lowest = float(np.min(visibility))
    highest = float(np.max(visibility))
    for boundary in _discontinuities_km(law):
        if not lowest <= boundary <= highest:
            continue
        below = float(visibility_scaling_exponent(np.nextafter(boundary, 0.0), law=law))
        above = float(visibility_scaling_exponent(boundary, law=law))
        as_below = _specific_attenuation_at(boundary, ratio, below)
        as_above = _specific_attenuation_at(boundary, ratio, above)
        degradations.warn(
            "extinction.visibility-spans-a-branch-boundary",
            (
                f"The visibilities given, [{lowest:.4g}, {highest:.4g}] km, reach {boundary:.4g} "
                f"km, where {law.value}'s exponent jumps from {below:.4f} to {above:.4f} — "
                f"{as_below:.4g} against {as_above:.4g} dB/km at this wavelength, a step of "
                f"{as_above / as_below - 1.0:+.1%}. The step is in the empirical fit, not in the "
                "weather: a visibility series crossing it will show an attenuation "
                "discontinuity that no aerosol produced."
            ),
            where=f"{_WHERE}.aerosol_specific_attenuation_db_per_km",
            boundary_km=boundary,
            exponent_below=below,
            exponent_above=above,
            db_per_km_below=as_below,
            db_per_km_above=as_above,
        )


def molecular_scattering_specific_attenuation_db_per_km(
    wavelength_m: float,
    *,
    pressure_pa: float,
    temperature_k: float,
) -> float:
    """Return Rayleigh scattering off air molecules, dB/km.

    ITU-R P.1817-1 §3 equations (3) and (4)::

        beta_m(lambda) = A lambda^-4,    A = 1.09e-3 (P / P0) (T0 / T)   km^-1 um^4

    with ``lambda`` in micrometres. **Molecules, not aerosols**: the
    ``lambda^-4`` is the signature of scattering off particles far smaller than
    a wavelength, which is why the sky is blue and why the effect all but
    vanishes in the infrared.

    Why this is here when the visibility law already contains it
    -----------------------------------------------------------
    Visibility is set by *total* extinction at 550 nm, molecules included, and
    :func:`aerosol_specific_attenuation_db_per_km` then scales the whole
    coefficient by an aerosol exponent of 1.3 or 1.6 instead of 4. This function
    is how that mis-attribution gets a number rather than a mention. At the ITU
    reference state the molecular term is **0.0517 dB/km at 550 nm, 0.0125 at
    785 nm and 0.00082 at 1550 nm**; the first of those is 3.1 % of the
    visibility coefficient at 10 km of visibility and **15.2 % at 50 km**, and
    carrying that share to 1550 nm at the aerosol exponent leaves the total
    **2.9 % too high at 10 km and 14.0 % too high at 50 km**. Correcting it
    means subtracting at 550 and adding back at ``lambda``, which neither source
    publishes, so it is not done -- gap 22 of the citation policy.

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m.
    pressure_pa
        Air pressure, Pa. **No default:** the equation's ``P0`` is a reference,
        not a value for the site, and
        :data:`MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA` is available for a
        caller who wants to say "sea level, as the recommendation prints it".
    temperature_k
        Air temperature, K. No default, same reason.

    Returns
    -------
    float
        Specific attenuation, dB/km.

    Raises
    ------
    DomainError
        If the wavelength, pressure or temperature is not finite and positive.

    Examples
    --------
    >>> at_sea_level = dict(
    ...     pressure_pa=MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
    ...     temperature_k=MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
    ... )
    >>> round(molecular_scattering_specific_attenuation_db_per_km(550e-9, **at_sea_level), 4)
    0.0517
    >>> round(molecular_scattering_specific_attenuation_db_per_km(1.55e-6, **at_sea_level), 6)
    0.00082

    Thinner air scatters less, exactly in proportion to pressure:

    >>> half = molecular_scattering_specific_attenuation_db_per_km(
    ...     1.55e-6,
    ...     pressure_pa=0.5 * MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
    ...     temperature_k=MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
    ... )
    >>> whole = molecular_scattering_specific_attenuation_db_per_km(1.55e-6, **at_sea_level)
    >>> round(half / whole, 12)
    0.5
    """
    wavelength = validated_wavelength_m(wavelength_m)
    pressure = _validated_positive(
        "pressure_pa", pressure_pa, hint="The unit is pascals: 1013 mbar is 101300."
    )
    temperature = _validated_positive(
        "temperature_k", temperature_k, hint="The unit is kelvin, so 0 C is 273.15."
    )
    micrometres = wavelength * MICROMETRES_PER_METRE
    coefficient = (
        MOLECULAR_SCATTERING_COEFFICIENT_KM_UM4
        * (pressure / MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA)
        * (MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K / temperature)
    )
    return float(NEPER_TO_DB * coefficient / micrometres**4)


# --------------------------------------------------------------------------- #
# The vertical column
# --------------------------------------------------------------------------- #
def zenith_optical_depth_from_visibility(
    visibility_km: FloatArray | float,
    *,
    wavelength_m: float,
    aerosol_scale_height_m: float,
    station_altitude_m: float,
    visibility_altitude_m: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the vertical aerosol optical depth above the station, nepers.

    What an optical depth is, and why the vertical one is a single number
    --------------------------------------------------------------------
    An **optical depth** ``tau`` is extinction counted in the exponent: a path
    transmits ``exp(-tau)``, so ``tau = 1`` passes 37 % of the light and
    ``tau = 0.1`` passes 90 %. It is the integral of the extinction coefficient
    along the path, which for a vertical path through the whole atmosphere is
    one number per wavelength -- the quantity Ntanos et al. equation (7) calls
    ``L_zen`` and raises to the air mass.

    The profile, which is a convention and not a citation
    ----------------------------------------------------
    Aerosols live in the boundary layer, the few kilometres of air that the
    ground stirs, and their concentration falls off roughly exponentially with
    height. Writing the extinction coefficient as ``beta(h) = beta_v
    exp(-(h - h_v)/H)``, where ``h_v`` is the altitude the visibility was
    measured at and ``H`` the **scale height** -- the height over which the
    aerosol thins by a factor ``e`` -- the integral from the station upward is

        tau = beta_v * H * exp(-(h_s - h_v) / H)

    which is where the station altitude enters and why it enters
    *exponentially*. Two consequences worth having in mind before reading a
    number out of this function:

    * **If the visibility was measured at the station, the altitude cancels
      exactly** and ``tau = beta * H``. That is the ordinary case -- an airport
      or a site meteorological station reports its own visibility -- and it is
      why ``visibility_altitude_m`` is a separate required argument rather than
      assumed: the *other* reading, a climatological sea-level visibility
      applied to a mountain site, is a different and much smaller optical depth,
      and nothing in a visibility figure says which it is. Teide OGS at 2390 m
      with a sea-level 23 km visibility and a 1.2 km scale height gets
      ``exp(-1.99) = 0.137`` of the aerosol column, **0.031 dB against 0.230**.
    * **No openable source publishes ``H``**, which is why it has no default.
      Values in use range from about 1.2 to 2 km, and that spread is a factor
      1.67 in optical depth -- 0.230 against 0.384 dB at 23 km of visibility and
      1550 nm. Gap 22 of ``docs/adr/0009-citation-policy.md``.

    The altitude is height above the WGS-84 ellipsoid, as
    :attr:`quoss.scenario.models.StationSpec.altitude_m` is and as ADR 0016
    settled for the turbulence integral. The geoid is within about 50 m of the
    ellipsoid in Europe, which is 4 % of a 1.2 km scale height and 0.009 dB at
    23 km of visibility: smaller than the scale height's own uncertainty, and
    said here rather than left as an exercise.

    Parameters
    ----------
    visibility_km
        Visual range, km, at ``visibility_altitude_m``. ``+inf`` allowed. Any
        shape.
    wavelength_m
        Optical wavelength, m.
    aerosol_scale_height_m
        Height over which the aerosol extinction falls by a factor ``e``, m.
        **No default** -- see above.
    station_altitude_m
        Station height above the WGS-84 ellipsoid, m. May be negative.
    visibility_altitude_m
        The altitude the visibility describes, m. Equal to
        ``station_altitude_m`` for a locally measured visibility; ``0.0`` for a
        sea-level climatological one.
    law
        Which published exponent. **No default.**
    degradations
        Log, passed through to :func:`aerosol_specific_attenuation_db_per_km`.

    Returns
    -------
    FloatArray
        Vertical optical depth, nepers, shaped like ``visibility_km``.

    Raises
    ------
    DomainError
        If any visibility is not positive, the wavelength or scale height is not
        finite and positive, or either altitude is not finite.

    Examples
    --------
    23 km of visibility measured at a station 30 m up, 1.2 km of scale height,
    1550 nm — the altitude cancels, so this is ``beta * H``:

    >>> from quoss.core.errors import DegradationLog
    >>> tau = zenith_optical_depth_from_visibility(
    ...     23.0,
    ...     wavelength_m=1.55e-6,
    ...     aerosol_scale_height_m=1200.0,
    ...     station_altitude_m=30.0,
    ...     visibility_altitude_m=30.0,
    ...     law=VisibilityScalingLaw.KIM_2001,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(tau), 5)
    0.05305

    The same visibility read as a sea-level figure, from 2390 m up:

    >>> higher = zenith_optical_depth_from_visibility(
    ...     23.0,
    ...     wavelength_m=1.55e-6,
    ...     aerosol_scale_height_m=1200.0,
    ...     station_altitude_m=2390.0,
    ...     visibility_altitude_m=0.0,
    ...     law=VisibilityScalingLaw.KIM_2001,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(higher), 6)
    0.007239
    """
    scale_height_m = validated_positive_length_m(
        "aerosol_scale_height_m",
        aerosol_scale_height_m,
        hint="The unit is metres: a 1.2 km boundary layer is 1200.0, not 1.2.",
    )
    station = _validated_altitude_m("station_altitude_m", station_altitude_m)
    reference = _validated_altitude_m("visibility_altitude_m", visibility_altitude_m)

    db_per_km = aerosol_specific_attenuation_db_per_km(
        visibility_km, wavelength_m=wavelength_m, law=law, degradations=degradations
    )
    nepers_per_km = db_per_km / NEPER_TO_DB
    thinning = _aerosol_thinning(
        altitude_m=station, visibility_altitude_m=reference, aerosol_scale_height_m=scale_height_m
    )
    depth: FloatArray = nepers_per_km * float(m_to_km(scale_height_m)) * thinning
    return depth


def _aerosol_thinning(
    *, altitude_m: float, visibility_altitude_m: float, aerosol_scale_height_m: float
) -> float:
    """Return ``exp(-(h - h_v) / H)``: how much of the aerosol survives at ``h``.

    The one line both the vertical column and the horizontal path need, in one
    place so that the two cannot disagree about which way the exponent points.
    Its arguments are already validated by the two callers, which is why it is
    private: a public function taking unvalidated altitudes would be a third way
    into the same profile.
    """
    return float(np.exp(-(altitude_m - visibility_altitude_m) / aerosol_scale_height_m))


def specific_attenuation_at_altitude_db_per_km(
    visibility_km: FloatArray | float,
    *,
    wavelength_m: float,
    aerosol_scale_height_m: float,
    altitude_m: float,
    visibility_altitude_m: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the aerosol specific attenuation at one altitude, dB/km.

    What this is, and how it differs from the zenith one
    ----------------------------------------------------
    :func:`zenith_optical_depth_from_visibility` answers "how much light is lost
    on the way **up**", which is an integral over the whole column and therefore
    one dimensionless number. A **horizontal** path has no column to integrate:
    it crosses air of one composition at one height, so what it needs is the
    extinction **coefficient there** -- a loss *per kilometre*, which multiplied
    by the path length gives the loss. That is the ``extinction_db_per_km`` of
    :func:`quoss.channel.horizontal.horizontal_loss_budget`, and this function is
    what computes one from a visibility instead of asserting it.

    The same profile, used one step earlier
    ---------------------------------------
    Both functions read the same aerosol profile,
    ``beta(h) = beta_v exp(-(h - h_v) / H)``. The vertical one integrates it from
    the station upward and gets ``beta_v H exp(-(h_s - h_v) / H)``; this one
    **evaluates** it at ``h`` and stops. So the scale height enters here only
    through the exponential, and **cancels exactly when the visibility was
    measured at the link's own height** -- which is the ordinary case for a
    horizontal link, where the visibility sensor and the terminals stand on the
    same ground. In that case this function returns
    :func:`aerosol_specific_attenuation_db_per_km` unchanged, and
    ``aerosol_scale_height_m`` (ADR 0009 gap 22, the field with no published
    value) has no influence on the answer at all. It is still required, because
    nothing in a visibility figure says at what height it was taken, and the
    other reading -- a sea-level climatological visibility applied to a link on a
    2 km plateau -- is a different number by ``exp(-2000/H)``, a factor 5.3 at
    ``H = 1200 m``.

    Parameters
    ----------
    visibility_km
        Visual range at ``visibility_altitude_m``, km, strictly positive.
        ``+inf`` allowed and gives exactly 0.0. Any shape.
    wavelength_m
        Optical wavelength, m.
    aerosol_scale_height_m
        Height over which the aerosol extinction falls by a factor ``e``, m.
        **No default** (ADR 0009 gap 22).
    altitude_m
        The height the path runs at, m above the WGS-84 ellipsoid.
    visibility_altitude_m
        The altitude the visibility describes, m. Equal to ``altitude_m`` for a
        locally measured visibility, in which case the two cancel exactly.
    law
        Which published exponent. **No default.**
    degradations
        Log, passed through to :func:`aerosol_specific_attenuation_db_per_km`.

    Returns
    -------
    FloatArray
        Specific attenuation, dB/km, shaped like ``visibility_km``.

    Raises
    ------
    DomainError
        If any visibility is not positive, the wavelength or scale height is not
        finite and positive, or either altitude is not finite.

    Examples
    --------
    23 km of visibility, measured where the link runs, at 1550 nm: the 0.192
    dB/km that ADR 0021's worked example assumes by hand as "0.2".

    >>> from quoss.core.errors import DegradationLog
    >>> gamma = specific_attenuation_at_altitude_db_per_km(
    ...     23.0,
    ...     wavelength_m=1.55e-6,
    ...     aerosol_scale_height_m=1200.0,
    ...     altitude_m=30.0,
    ...     visibility_altitude_m=30.0,
    ...     law=VisibilityScalingLaw.KIM_2001,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(gamma), 4)
    0.192

    The scale height cannot matter when the two altitudes agree, and that is an
    identity rather than an approximation:

    >>> other = specific_attenuation_at_altitude_db_per_km(
    ...     23.0,
    ...     wavelength_m=1.55e-6,
    ...     aerosol_scale_height_m=2000.0,
    ...     altitude_m=30.0,
    ...     visibility_altitude_m=30.0,
    ...     law=VisibilityScalingLaw.KIM_2001,
    ...     degradations=DegradationLog(),
    ... )
    >>> float(other) == float(gamma)
    True

    A sea-level figure read on a plateau is a different number:

    >>> plateau = specific_attenuation_at_altitude_db_per_km(
    ...     23.0,
    ...     wavelength_m=1.55e-6,
    ...     aerosol_scale_height_m=1200.0,
    ...     altitude_m=2000.0,
    ...     visibility_altitude_m=0.0,
    ...     law=VisibilityScalingLaw.KIM_2001,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(plateau), 5)
    0.03626
    """
    scale_height_m = validated_positive_length_m(
        "aerosol_scale_height_m",
        aerosol_scale_height_m,
        hint="The unit is metres: a 1.2 km boundary layer is 1200.0, not 1.2.",
    )
    altitude = _validated_altitude_m("altitude_m", altitude_m)
    reference = _validated_altitude_m("visibility_altitude_m", visibility_altitude_m)
    db_per_km = aerosol_specific_attenuation_db_per_km(
        visibility_km, wavelength_m=wavelength_m, law=law, degradations=degradations
    )
    thinning = _aerosol_thinning(
        altitude_m=altitude,
        visibility_altitude_m=reference,
        aerosol_scale_height_m=scale_height_m,
    )
    result: FloatArray = db_per_km * thinning
    return result


def zenith_transmittance_from_visibility(
    visibility_km: FloatArray | float,
    *,
    wavelength_m: float,
    aerosol_scale_height_m: float,
    station_altitude_m: float,
    visibility_altitude_m: float,
    law: VisibilityScalingLaw,
    degradations: DegradationLog,
) -> FloatArray:
    """Return ``L_zen``: the vertical transmittance above the station, in ``(0, 1]``.

    ``exp(-tau)`` of :func:`zenith_optical_depth_from_visibility`, which is the
    base of Ntanos et al. equation (7) and therefore exactly what
    :func:`quoss.channel.link_budget.atmospheric_transmittance` and
    :attr:`quoss.scenario.models.ChannelSpec.zenith_transmittance` want. It
    models **aerosol scattering only**: molecular absorption has no published
    number (gap 23) and molecular scattering is inside the visibility law at the
    wrong exponent (gap 22). Both are stated in the module docstring with their
    size.

    Parameters
    ----------
    visibility_km, wavelength_m, aerosol_scale_height_m, station_altitude_m, visibility_altitude_m, law, degradations
        As :func:`zenith_optical_depth_from_visibility`.

    Returns
    -------
    FloatArray
        Vertical transmittance in ``(0, 1]``, shaped like ``visibility_km``.

    Raises
    ------
    DomainError
        As :func:`zenith_optical_depth_from_visibility`.

    Examples
    --------
    The three labels ITU-R P.1817-1's visibility code puts on clear weather, at
    1550 nm, measured at the station, through 1.2 km of scale height:

    >>> from quoss.core.errors import DegradationLog
    >>> def l_zen(v: float) -> float:
    ...     return float(
    ...         zenith_transmittance_from_visibility(
    ...             v,
    ...             wavelength_m=1.55e-6,
    ...             aerosol_scale_height_m=1200.0,
    ...             station_altitude_m=0.0,
    ...             visibility_altitude_m=0.0,
    ...             law=VisibilityScalingLaw.KIM_2001,
    ...             degradations=DegradationLog(),
    ...         )
    ...     )
    >>> [round(l_zen(v), 4) for v in (10.0, 23.0, 50.0)]
    [0.8851, 0.9483, 0.9823]

    Infinite visibility is exactly 1, which is the value the required argument
    of :func:`~quoss.channel.link_budget.atmospheric_transmittance` has always
    meant by "no extinction modelled":

    >>> l_zen(float("inf"))
    1.0
    """
    depth = zenith_optical_depth_from_visibility(
        visibility_km,
        wavelength_m=wavelength_m,
        aerosol_scale_height_m=aerosol_scale_height_m,
        station_altitude_m=station_altitude_m,
        visibility_altitude_m=visibility_altitude_m,
        law=law,
        degradations=degradations,
    )
    transmittance: FloatArray = np.exp(-depth)
    return transmittance
