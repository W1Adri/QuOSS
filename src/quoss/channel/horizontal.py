"""Turbulence and loss along a horizontal path: a bench, or a link a few kilometres long.

What this module is for
-----------------------
Everything else in :mod:`quoss.channel` describes a satellite. Its path starts
at a ground station and leaves the atmosphere; its turbulence is an integral of
the Hufnagel-Valley profile over height; and its geometry changes every second,
because the elevation does. The first experiments this project will build are
neither of those: a **bench** with a turbulence emulator, and a **horizontal
link** of a few hundred metres to a few kilometres. On both, the light crosses
air at one height and of one turbulence strength, so the refractive-index
structure parameter ``C_n^2`` — the number that says how strongly the air
bends light, in m^(-2/3) — is **a constant of the path**, and there is **no
elevation**.

That is not the slant-path formulas with the angle set to zero, and the
difference is not a detail. :func:`quoss.channel.turbulence.log_irradiance_variance`
integrates the profile from the station to 20 km along ``1 / sin(theta)``: at
0.1 degrees it is a path of 11 000 km through the whole atmosphere, not one
kilometre at two metres off the ground. So nothing here takes an elevation, and
the tests assert that by absence (``TestNoSignatureTakesAnElevation``).

The quantities, and what each answers
-------------------------------------
**Rytov variance**, :func:`plane_wave_rytov_variance`. How strongly the path
scintillates — makes the received power flicker — measured as the variance of
the natural logarithm of the irradiance that a point-sized detector would see,
in Np^2. It is also the number that says whether the theory applies at all:
below 1 is *weak* turbulence, where the formulas here hold; above 1 they keep
returning numbers that are too large (see "Weak turbulence only").

**Which wave**, :class:`PathWave`. A collimated beam still inside its Rayleigh
range is close to a *plane* wave; a beam that has spread far beyond it looks, at
the receiver, like light from a point: a *spherical* wave. The spherical wave
scintillates 2.46 times less on the same path, because the turbulence near the
source is seen through a narrowing cone.

**Aperture averaging**, :func:`horizontal_aperture_averaging_factor`. A
receiving lens wider than the speckle pattern adds several speckles together,
and their flicker partly cancels. On a horizontal path this is not a small
correction: a 10 cm lens at 1 km averages the variance down by a factor of 17.
It is the reason the receiving aperture is a design variable for a horizontal
link and not only for a satellite one.

**The loss budget**, :func:`horizontal_loss_budget`: geometry, extinction,
pointing and scintillation, in the same :class:`~quoss.channel.link_budget.LossBudget`
the downlink returns, assembled by the same private function so the two cannot
add their terms differently.

Where the numbers come from, and how they are checked
------------------------------------------------------
**The plane-wave variance is ITU-R P.1814 §5 equation (8)**,
``sigma_chi^2 = 23.17 k^(7/6) C_n^2 L^(11/6)`` in dB^2. The recommendation calls
``chi`` the log-amplitude in dB; since the amplitude in dB is ``20 log10`` and the
irradiance in dB is ``10 log10`` of its square, it is the same number as the
log-irradiance variance in dB^2, and dividing by
:data:`~quoss.channel.turbulence.NEPER_SQ_TO_DB_SQ` gives **1.2285** in Np^2.
The textbook Rytov coefficient is 1.23; the 0.13 % between them is the printed
precision of 23.17. It is checked three ways
(``tests/channel/test_horizontal.py``):

- **V2**, against P.1814 **Table 4** — six fade depths at 1 km, two
  wavelengths, three turbulence strengths — to the printed two decimals.
- **Between sources**, against **ITU-R P.1622 equation (4a)**, which is the
  slant-path integral this project already uses. Integrated along a uniform
  horizontal path its coefficient 2.253 becomes ``2.253 * 6/11 = 1.2289``, 0.04 %
  from P.1814 — two recommendations, four years apart, one written for a path
  to space.
- **Between sources**, against Kaushal & Kaddoum equation (8), which prints 1.23.

**The spherical wave and aperture averaging are Kaushal & Kaddoum**, equations
(9), (20) and (21): an open-access survey, which is priority (b) of
[ADR 0009](../../../docs/adr/0009-citation-policy.md) and a secondary source —
it quotes Churnside 1991 and Andrews 1992, which this project could not open.
That is why the plane-wave averaging factor is also checked against the one
primary source available: **P.1622 equations (6) and (7)** applied to a uniform
horizontal path give ``A = 1 / (1 + 1.8 (D^2 / (lambda L))^(7/6))`` — the
turbulence scale height becomes ``(11/18)^(6/7) L`` and the coefficient becomes
exactly ``1.1 * 18/11 = 1.8`` — against Kaushal & Kaddoum's
``1.07 (pi/2)^(7/6) = 1.812``. **0.67 %**, inside the 4.5 % that P.1622's
two-figure "1.1" allows. The spherical-wave factor has no such second source.

Weak turbulence only
--------------------
Every closed form here is first-order (Rytov) perturbation theory. Above a
plane-wave Rytov variance of
:data:`~quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT` the real
scintillation saturates and these formulas overestimate it, silently and more
the stronger the turbulence. So the variance functions record a WARNING there
(``horizontal.weak-fluctuation-limit-exceeded``), and the warning carries a
measure of the cost: the strong-turbulence asymptote of Kaushal & Kaddoum
equations (10) and (11), ``sigma_I^2 = 1 + c / sigma_R^(4/5)``, converted to the
same log-variance. It is a measure and not a substitute — the asymptote itself
holds only for ``sigma_R^2 >> 1`` — and the value returned stays the weak-theory
one, as on the slant path.

P.1814's own Table 4 is the example: its "High" column, ``C_n^2 = 1e-13`` at
1 km, is a Rytov variance of 1.99 at 1550 nm and 3.39 at 980 nm, and the
recommendation prints 12.25 and 16.00 dB for it from the weak-turbulence
equation it has just said saturates.

**Stage 1.2** (the strong regime) will have to decide for this path as well: the
fade laws are in :mod:`quoss.channel.link_budget`, which this module calls, so
a saturation model placed there is inherited here, and one placed in
:mod:`quoss.channel.turbulence` is not.

What is not here, stated rather than approximated
-------------------------------------------------
- **The Gaussian beam wave.** A real beam is neither a plane nor a spherical
  wave, and near its Rayleigh range neither closed form is right. The formulas
  exist (Andrews & Phillips) and could not be opened: ADR 0009 gap 1.
  :func:`horizontal_loss_budget` warns when the declared wave contradicts the
  beam's own Rayleigh range, with both variances, so the size of the choice is
  on the page.
- **A retroreflector.** A link that goes out and comes back crosses the same air
  twice, and the two passes are correlated (enhanced backscatter). Modelling it
  as one path of twice the length is an approximation with no source here.
- **Beam wander and turbulent beam spreading.** Kaushal & Kaddoum print
  ``sigma_BW^2 = 1.44 C_n^2 L^2 W_0^(-1/3)`` without an equation number; it is
  not implemented.
- **Turbulence emulators.** A hot-air chamber is roughly Kolmogorov; a phase
  screen on a spatial light modulator is whatever spectrum was written into it.
  ``C_n^2`` here means Kolmogorov turbulence, and an emulator has to be
  characterised in those terms before its value can be passed.
- **Inner and outer scale.** Kolmogorov's inertial range is assumed throughout.
- **Background light.** A horizontal path looks at the horizon or at a wall, not
  at the zenith sky. :func:`quoss.channel.link_budget.downlink_noise_budget`
  has no geometry in it and serves both cases; the radiance is the caller's, and
  on a bench it is zero.

======================  ====================================================
Symbol                  Meaning
======================  ====================================================
``L``                   path length (m)
``C_n^2``               refractive-index structure parameter (m^(-2/3))
``k``                   wavenumber, ``2 pi / lambda`` (1/m)
``sigma_R^2``           plane-wave Rytov variance (Np^2)
``D``                   receiving aperture diameter (m)
``A``                   aperture averaging factor (0 to 1)
``z_R``                 Rayleigh range of the transmitted beam (m)
======================  ====================================================

References
----------
Recommendation ITU-R P.1814 (08/2007), *Prediction methods required for the
design of terrestrial free-space optical links*, §4 equation (3), §5 equation (8)
and Table 4.

Recommendation ITU-R P.1622 (04/2003), §4.1 equations (4a), (6) and (7).

H. Kaushal and G. Kaddoum, "Free Space Optical Communication: Challenges and
Mitigation Techniques", arXiv:1506.04836 (2015), §II equations (8)-(11) and
§III-A equations (20)-(21). Read in the arXiv PDF; equation numbers refer to it.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from quoss.channel._validation import validated_positive_length_m, validated_wavelength_m
from quoss.channel.beam import geometric_transmittance, rayleigh_range_km
from quoss.channel.link_budget import (
    GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE,
    NTANOS_OUTAGE_PROBABILITY,
    FadeCombination,
    LossBudget,
    _assembled_loss_budget,
    _validated_outage_probability,
    _validated_transmittance,
)
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import (
    NEPER_SQ_TO_DB_SQ,
    WEAK_FLUCTUATION_VARIANCE_LIMIT,
    PathWave,
    ScintillationRegime,
    saturated_log_irradiance_variance,
)
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import km_to_m

__all__ = [
    "ITU_P1814_SCINTILLATION_COEFFICIENT_DB2",
    "KAUSHAL_PLANE_APERTURE_AVERAGING_COEFFICIENT",
    "KAUSHAL_PLANE_STRONG_TURBULENCE_COEFFICIENT",
    "KAUSHAL_SPHERICAL_APERTURE_AVERAGING_COEFFICIENT",
    "KAUSHAL_SPHERICAL_STRONG_TURBULENCE_COEFFICIENT",
    "KAUSHAL_SPHERICAL_WAVE_COEFFICIENT",
    "PLANE_WAVE_RYTOV_COEFFICIENT",
    "PathWave",
    "ScintillationRegime",
    "equivalent_bench_cn2_m23",
    "horizontal_aperture_averaging_factor",
    "horizontal_log_irradiance_variance",
    "horizontal_loss_budget",
    "horizontal_point_log_irradiance_variance",
    "plane_wave_rytov_variance",
    "weak_theory_path_limit_m",
]

ITU_P1814_SCINTILLATION_COEFFICIENT_DB2: Final[float] = 23.17
"""Coefficient of ITU-R P.1814 equation (8), for a variance in dB^2 and SI units.

``k`` in 1/m, ``L`` in m, ``C_n^2`` in m^(-2/3) — the recommendation defines all
three that way right below the equation, so unlike P.1622 there is no
micrometre hidden in it.
"""

PLANE_WAVE_RYTOV_COEFFICIENT: Final[float] = (
    ITU_P1814_SCINTILLATION_COEFFICIENT_DB2 / NEPER_SQ_TO_DB_SQ
)
"""The same coefficient for a log-irradiance variance in Np^2: 1.2285.

The textbook value is 1.23 (Kaushal & Kaddoum equation (8)); the difference is
the rounding of 23.17 to four figures, and the tests hold both to it.
"""

KAUSHAL_SPHERICAL_WAVE_COEFFICIENT: Final[float] = 0.5
"""Kaushal & Kaddoum equation (9): ``sigma_I^2 = 0.5 C_n^2 k^(7/6) L^(11/6)``, spherical wave."""

KAUSHAL_PLANE_APERTURE_AVERAGING_COEFFICIENT: Final[float] = 1.07
"""Kaushal & Kaddoum equation (20), Churnside's plane-wave averaging factor."""

KAUSHAL_SPHERICAL_APERTURE_AVERAGING_COEFFICIENT: Final[float] = 0.214
"""Kaushal & Kaddoum equation (21), the spherical-wave averaging factor."""

KAUSHAL_PLANE_STRONG_TURBULENCE_COEFFICIENT: Final[float] = 0.86
"""Kaushal & Kaddoum equation (10): ``sigma_I^2 = 1 + 0.86 / sigma_R^(4/5)``, ``sigma_R^2 >> 1``."""

KAUSHAL_SPHERICAL_STRONG_TURBULENCE_COEFFICIENT: Final[float] = 2.73
"""Kaushal & Kaddoum equation (11): ``sigma_I^2 = 1 + 2.73 / sigma_R^(4/5)``, ``sigma_R^2 >> 1``."""


# ``PathWave`` now lives in :mod:`quoss.channel.turbulence`, because the saturation
# model of :func:`~quoss.channel.turbulence.saturated_log_irradiance_variance` is
# shared with the slant path and needs it too. It is re-exported here, and stays in
# ``__all__``, so every existing import keeps working.


def _validated_path_length_m(path_length_m: FloatArray | float) -> FloatArray:
    """Return the path length as an array, finite and strictly positive, in metres."""
    path = np.asarray(path_length_m, dtype=np.float64)
    if not np.all(np.isfinite(path)) or np.any(path <= 0.0):
        raise DomainError(
            "path_length_m must be finite and strictly positive. The unit is metres: a 2 km "
            "link is 2000.0, and 2.0 would be a bench, whose Rytov variance is 3.2e5 times "
            f"smaller. Got range [{float(np.min(path))}, {float(np.max(path))}]."
            if path.size
            else "path_length_m must be finite and strictly positive."
        )
    return path


def _validated_cn2(cn2_m23: FloatArray | float) -> FloatArray:
    """Return ``C_n^2`` as an array, finite and non-negative."""
    cn2 = np.asarray(cn2_m23, dtype=np.float64)
    if not np.all(np.isfinite(cn2)) or np.any(cn2 < 0.0):
        raise DomainError(
            "cn2_m23 must be finite and non-negative, in m^(-2/3). ITU-R P.1814 §5 gives "
            "1e-16 to 1e-13 for optical wavelengths near the ground; zero is still air and "
            f"is exact. Got range [{float(np.min(cn2))}, {float(np.max(cn2))}]."
        )
    return cn2


def _wavenumber(wavelength_m: float) -> float:
    return float(2.0 * np.pi / validated_wavelength_m(wavelength_m))


def plane_wave_rytov_variance(
    path_length_m: FloatArray | float,
    *,
    cn2_m23: FloatArray | float,
    wavelength_m: float,
) -> FloatArray:
    """Return the plane-wave Rytov variance of a horizontal path, Np^2.

    ITU-R P.1814 §5 equation (8), converted from dB^2::

        sigma_R^2 = (23.17 / 18.861) C_n^2 k^(7/6) L^(11/6) = 1.2285 C_n^2 k^(7/6) L^(11/6)

    **What it is.** The variance of the log-irradiance a point detector would
    see at the end of a path of uniform turbulence, in weak turbulence — and,
    whatever wave actually propagates, the conventional measure of *how strong*
    the path is. That second role is why it has its own function: it is the
    number compared against
    :data:`~quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT`.

    **Why it grows so fast with distance.** ``L^(11/6)`` — doubling the path
    multiplies the variance by 3.6 — because a longer path both collects more
    turbulence and gives each eddy's focusing more distance to turn into an
    intensity change.

    No degradation log: this is the regime parameter, not a model output. The
    functions that return a variance to use record the warning.

    Parameters
    ----------
    path_length_m
        Path length, m, strictly positive. Any shape; broadcast against ``cn2_m23``.
    cn2_m23
        ``C_n^2`` along the path, m^(-2/3), non-negative. Any shape.
    wavelength_m
        Optical wavelength, m.

    Returns
    -------
    FloatArray
        ``sigma_R^2`` in Np^2, shaped by broadcasting the two arrays.

    Raises
    ------
    DomainError
        If a length is not finite and positive, a ``C_n^2`` is negative or not
        finite, or the wavelength fails its guard.

    Examples
    --------
    P.1814's "moderate" turbulence, 1e-14, over its 1 km at 1550 nm — weak, but
    not by a wide margin:

    >>> round(float(plane_wave_rytov_variance(1000.0, cn2_m23=1e-14, wavelength_m=1.55e-06)), 4)
    0.1988

    The same air across a two-metre bench is ninety thousand times weaker, which is
    why an emulator has to reach ``C_n^2`` far above anything outdoors:

    >>> f"{float(plane_wave_rytov_variance(2.0, cn2_m23=1e-14, wavelength_m=1.55e-06)):.3e}"
    '2.241e-06'
    """
    path = _validated_path_length_m(path_length_m)
    cn2 = _validated_cn2(cn2_m23)
    k = _wavenumber(wavelength_m)
    variance: FloatArray = (
        PLANE_WAVE_RYTOV_COEFFICIENT * cn2 * k ** (7.0 / 6.0) * path ** (11.0 / 6.0)
    )
    return variance


def _saturated_and_logged(
    own_rytov: FloatArray,
    *,
    plane_rytov: FloatArray,
    wave: PathWave,
    path_length_m: FloatArray | float,
    cn2_m23: FloatArray | float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the saturated point variance, and say so in the log where it matters.

    Split out of :func:`horizontal_point_log_irradiance_variance` so the two
    regimes read as two branches of the same length rather than one branch with
    a tail.

    The regime test is on the **plane-wave** Rytov variance even when the
    spherical wave was asked for, for the same reason the weak branch does it:
    ``sigma_R^2`` is the conventional measure of how strong the path is, a
    property of the air and the distance, not of which idealisation of the beam
    the caller chose.
    """
    saturated: FloatArray = saturated_log_irradiance_variance(own_rytov, wave=wave)
    if not plane_rytov.size or float(np.max(plane_rytov)) <= WEAK_FLUCTUATION_VARIANCE_LIMIT:
        return saturated
    index = np.unravel_index(int(np.argmax(plane_rytov)), plane_rytov.shape)
    peak = float(plane_rytov[index])
    weak = float(np.broadcast_to(own_rytov, plane_rytov.shape)[index])
    returned = float(np.broadcast_to(saturated, plane_rytov.shape)[index])
    path = np.broadcast_to(np.asarray(path_length_m, dtype=np.float64), plane_rytov.shape)
    cn2 = np.broadcast_to(np.asarray(cn2_m23, dtype=np.float64), plane_rytov.shape)
    degradations.warn(
        "horizontal.scintillation-saturated",
        (
            f"The plane-wave Rytov variance reaches {peak:.3g} Np^2 over "
            f"{float(path[index]):.4g} m at C_n^2 = {float(cn2[index]):.3g} m^(-2/3), above the "
            f"{WEAK_FLUCTUATION_VARIANCE_LIMIT} Np^2 where the first-order theory of ITU-R "
            "P.1814 equation (8) holds, so the value returned is the saturated "
            f"{returned:.3g} Np^2 of "
            f"{'Ntanos et al. equation (12)' if wave is PathWave.PLANE else 'Gruneisen et al. equation (A9)'}"
            f" rather than that theory's "
            f"{weak:.3g} Np^2 — a factor {returned / weak:.3f}. Gruneisen et al. is a heuristic "
            "fit assuming Kolmogorov turbulence with no outer scale, and the aperture averaging "
            "applied after it is still ITU-R P.1622's, on the log-variance: see ADR 0022. "
            "ScintillationRegime.WEAK returns the unsaturated value."
        ),
        where="quoss.channel.horizontal.horizontal_point_log_irradiance_variance",
        peak_rytov_variance_np2=peak,
        weak_variance_np2=weak,
        peak_variance_np2=returned,
        limit_np2=WEAK_FLUCTUATION_VARIANCE_LIMIT,
        wave=wave.value,
    )
    return saturated


def horizontal_point_log_irradiance_variance(
    path_length_m: FloatArray | float,
    *,
    cn2_m23: FloatArray | float,
    wavelength_m: float,
    wave: PathWave,
    degradations: DegradationLog,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
) -> FloatArray:
    """Return the log-irradiance variance a point detector sees, Np^2, for either wave.

    ``PLANE`` is :func:`plane_wave_rytov_variance`; ``SPHERICAL`` is Kaushal &
    Kaddoum equation (9), ``0.5 C_n^2 k^(7/6) L^(11/6)``, which is 0.407 of it —
    the "0.4" the equation prints beside it, to its printed precision.

    Records ``horizontal.weak-fluctuation-limit-exceeded`` if the plane-wave
    Rytov variance of any element exceeds
    :data:`~quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT`, whichever
    wave was asked for: the regime is a property of the path, not of the
    idealisation. The details carry the strong-turbulence asymptote of Kaushal
    & Kaddoum equation (10) or (11) at the same Rytov variance, as
    ``ln(1 + sigma_I^2)`` so it is comparable with the value returned.

    Parameters
    ----------
    path_length_m
        Path length, m. Any shape; broadcast against ``cn2_m23``.
    cn2_m23
        ``C_n^2`` along the path, m^(-2/3).
    wavelength_m
        Optical wavelength, m.
    wave
        :class:`PathWave`, required.
    degradations
        Log that receives the weak-turbulence warning.

    regime
        :class:`~quoss.channel.turbulence.ScintillationRegime`. ``WEAK`` (the
        default) returns the first-order value itself and records
        ``horizontal.weak-fluctuation-limit-exceeded`` above
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
    FloatArray
        Variance in Np^2, shaped by broadcasting the two arrays.

    Raises
    ------
    DomainError
        As :func:`plane_wave_rytov_variance`, or if ``wave`` is not a
        :class:`PathWave`.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> plane = horizontal_point_log_irradiance_variance(
    ...     1000.0, cn2_m23=1e-14, wavelength_m=1.55e-06, wave=PathWave.PLANE, degradations=log
    ... )
    >>> spherical = horizontal_point_log_irradiance_variance(
    ...     1000.0, cn2_m23=1e-14, wavelength_m=1.55e-06, wave=PathWave.SPHERICAL, degradations=log
    ... )
    >>> round(float(spherical / plane), 3), len(log)
    (0.407, 0)
    """
    selected = PathWave(wave)
    selected_regime = ScintillationRegime(regime)
    rytov = plane_wave_rytov_variance(path_length_m, cn2_m23=cn2_m23, wavelength_m=wavelength_m)
    if selected is PathWave.PLANE:
        own_rytov = rytov
        strong_coefficient = KAUSHAL_PLANE_STRONG_TURBULENCE_COEFFICIENT
    else:
        own_rytov = rytov * (KAUSHAL_SPHERICAL_WAVE_COEFFICIENT / PLANE_WAVE_RYTOV_COEFFICIENT)
        strong_coefficient = KAUSHAL_SPHERICAL_STRONG_TURBULENCE_COEFFICIENT

    if selected_regime is ScintillationRegime.MODERATE_TO_STRONG:
        return _saturated_and_logged(
            own_rytov,
            plane_rytov=rytov,
            wave=selected,
            path_length_m=path_length_m,
            cn2_m23=cn2_m23,
            degradations=degradations,
        )

    variance = own_rytov
    if rytov.size and float(np.max(rytov)) > WEAK_FLUCTUATION_VARIANCE_LIMIT:
        index = np.unravel_index(int(np.argmax(rytov)), rytov.shape)
        peak = float(rytov[index])
        returned = float(np.broadcast_to(variance, rytov.shape)[index])
        strong_index = 1.0 + strong_coefficient / peak ** (2.0 / 5.0)
        strong_log_variance = float(np.log1p(strong_index))
        path = np.broadcast_to(np.asarray(path_length_m, dtype=np.float64), rytov.shape)
        cn2 = np.broadcast_to(np.asarray(cn2_m23, dtype=np.float64), rytov.shape)
        degradations.warn(
            "horizontal.weak-fluctuation-limit-exceeded",
            (
                f"The plane-wave Rytov variance reaches {peak:.3g} Np^2 over "
                f"{float(path[index]):.4g} m at C_n^2 = {float(cn2[index]):.3g} m^(-2/3), above "
                f"the {WEAK_FLUCTUATION_VARIANCE_LIMIT} Np^2 where the first-order theory behind "
                "ITU-R P.1814 equation (8) and Kaushal & Kaddoum (9), (20), (21) holds. The "
                f"{selected.value}-wave value returned, {returned:.3g} Np^2, is that theory's; "
                "real scintillation saturates instead of growing. For scale, the strong-"
                f"turbulence asymptote of Kaushal & Kaddoum ({10 if selected is PathWave.PLANE else 11}) "
                f"at the same Rytov variance is a log-variance of {strong_log_variance:.3g} Np^2 "
                f"({returned / strong_log_variance:.2g} times less) — itself valid only for "
                "sigma_R^2 >> 1, so a measure of the error and not a correction."
            ),
            where="quoss.channel.horizontal.horizontal_point_log_irradiance_variance",
            peak_rytov_variance_np2=peak,
            returned_variance_np2=returned,
            strong_turbulence_scintillation_index=strong_index,
            strong_turbulence_log_variance_np2=strong_log_variance,
            limit_np2=WEAK_FLUCTUATION_VARIANCE_LIMIT,
            path_length_m=float(path[index]),
            cn2_m23=float(cn2[index]),
            wave=selected.value,
        )
    result: FloatArray = np.asarray(variance, dtype=np.float64)
    return result


def weak_theory_path_limit_m(
    *,
    cn2_m23: float,
    wavelength_m: float,
) -> float:
    """Return the path length at which the plane-wave Rytov variance reaches 1 Np^2, m.

    **What it is, and why it is a design constraint rather than a note.** Every
    closed form in this module is first-order perturbation theory, valid while
    the plane-wave Rytov variance stays below
    :data:`~quoss.channel.turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT`. That
    condition is not a property of the equipment: it is a property of the air
    and the distance, so for a given site it is a **maximum path length**. A
    horizontal experiment longer than this one cannot be dimensioned with
    ``ScintillationRegime.WEAK`` at all, whatever lens is bought.

    It is exposed as a function, and not left as a sentence in an ADR, for the
    reason ADR 0009 gives for every other quoted number: a sentence cannot be
    called, cannot be re-derived when a coefficient changes, and was in fact
    wrong in fifteen places once.

    **Where the closed form comes from.** ``sigma_R^2 = 1.2285 C_n^2 k^(7/6)
    L^(11/6)`` is monotone in ``L``, so setting it to 1 and solving gives::

        L* = (1 / (1.2285 C_n^2 k^(7/6)))^(6/11)

    The ``6/11`` is the inverse of the ``11/6`` in the variance, and it is why
    this limit is so insensitive to the site: a hundred times more turbulence
    only shortens the usable path by a factor ``100^(6/11) = 12.3``.

    **What it does not say.** Past ``L*`` the path is not unusable, it is
    unusable *with the weak model*.
    :attr:`~quoss.channel.turbulence.ScintillationRegime.MODERATE_TO_STRONG`
    continues past it, on a heuristic rather than an ITU recommendation. So this
    is the boundary of what this project can cite, not the boundary of what a
    link can do.

    Parameters
    ----------
    cn2_m23
        ``C_n^2`` along the path, m^(-2/3), strictly positive. Scalar: a limit
        is one number, and a path with a varying ``C_n^2`` has no single one.
    wavelength_m
        Optical wavelength, m.

    Returns
    -------
    float
        The path length in metres at which ``sigma_R^2 = 1``.

    Raises
    ------
    DomainError
        If ``C_n^2`` is not finite and strictly positive, or the wavelength
        fails its guard.

    Examples
    --------
    GE-1's design case — ITU-R P.1814's "moderate" turbulence at 1550 nm:

    >>> round(weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=1.55e-06))
    2413

    Two orders of magnitude quieter air buys only a factor 12.3, which is the
    ``6/11`` at work and the reason a horizontal QKD link is a kilometre-scale
    experiment and not a hundred-kilometre one:

    >>> round(weak_theory_path_limit_m(cn2_m23=1e-16, wavelength_m=1.55e-06))
    29753

    And the wavelength matters much less than the air: 980 nm instead of 1550 nm
    shortens it by a quarter, against the factor 12.3 two decades of ``C_n^2``
    are worth.

    >>> round(weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=9.8e-07))
    1803
    """
    cn2 = float(cn2_m23)
    if not np.isfinite(cn2) or cn2 <= 0.0:
        raise DomainError(
            "cn2_m23 must be finite and strictly positive to have a path limit: in perfectly "
            f"still air the Rytov variance is zero at every distance. Got {cn2}."
        )
    k = _wavenumber(wavelength_m)
    coefficient = PLANE_WAVE_RYTOV_COEFFICIENT * cn2 * k ** (7.0 / 6.0)
    limit_m: float = float(WEAK_FLUCTUATION_VARIANCE_LIMIT / coefficient) ** (6.0 / 11.0)
    return limit_m


def equivalent_bench_cn2_m23(
    *,
    bench_length_m: float,
    path_length_m: float,
    cn2_m23: float,
) -> float:
    """Return the ``C_n^2`` a bench needs to scintillate like a longer outdoor path, m^(-2/3).

    **The question this answers.** GE-0b is a bench standing in for GE-1. A
    bench is two metres long and the link is one kilometre, so the emulator has
    to make two metres of air behave like a kilometre of it. Since the Rytov
    variance goes as ``L^(11/6)`` and is linear in ``C_n^2``, matching it needs::

        C_n^2(bench) = C_n^2(path) * (L_path / L_bench)^(11/6)

    **Why the answer is enormous, and why that is the point.** ``(1000/2)^(11/6)
    = 8.87e4``. Matching P.1814's "moderate" 1e-14 over 1 km on two metres needs
    ``8.9e-10`` — five orders of magnitude above the strongest turbulence anyone
    measures outdoors, and nine above a quiet night. A number that large is not
    a specification an emulator meets; it is the reason a bench cannot simply be
    handed a ``C_n^2``.

    **What matching this number would still not buy** (ADR 0009 gap 20). Rytov
    variance is only one of the parameters of a turbulent path, and the one a
    single phase screen is worst at reproducing. Scintillation is the *phase*
    distortion a screen imposes turned into *amplitude* by propagation, so it
    needs distance after the screen: a screen at the transmitter of a 2 m bench
    has 2 m in which to develop the irradiance fluctuations that a kilometre of
    distributed air develops continuously. Laboratory practice is therefore to
    match the dimensionless numbers — the Fried ratio ``D/r_0`` and the Rytov
    number — with several screens and relay optics between them, not to match a
    ``C_n^2``. This function returns the ``C_n^2`` because that is the input
    this module takes; it is a *necessary* condition on an emulator and not a
    sufficient one.

    Parameters
    ----------
    bench_length_m
        Physical length of the bench path, m, strictly positive.
    path_length_m
        Length of the outdoor path being stood in for, m, strictly positive.
    cn2_m23
        ``C_n^2`` of that outdoor path, m^(-2/3), non-negative.

    Returns
    -------
    float
        The bench ``C_n^2`` in m^(-2/3) that gives the same Rytov variance.

    Raises
    ------
    DomainError
        If either length is not finite and strictly positive, or ``C_n^2`` is
        negative or not finite.

    Examples
    --------
    Two metres standing in for GE-1's kilometre of moderate air:

    >>> f"{equivalent_bench_cn2_m23(bench_length_m=2.0, path_length_m=1000.0, cn2_m23=1e-14):.2e}"
    '8.87e-10'

    Ten metres of folded path — four passes across a 2.5 m bench — costs a
    factor 19.1 less, which is the strongest argument there is for folding:

    >>> f"{equivalent_bench_cn2_m23(bench_length_m=10.0, path_length_m=1000.0, cn2_m23=1e-14):.2e}"
    '4.64e-11'

    It is an identity by construction, and the test says so rather than trusting
    the exponent: the two paths have the same Rytov variance to machine
    precision.
    """
    bench = _validated_path_length_m(bench_length_m)
    path = _validated_path_length_m(path_length_m)
    cn2 = _validated_cn2(cn2_m23)
    if bench.shape != () or path.shape != () or cn2.shape != ():
        raise DomainError(
            "weak_theory_path_limit_m and equivalent_bench_cn2_m23 take scalars: an "
            "experiment has one bench and one path, and broadcasting them would produce a "
            "table nobody asked for."
        )
    required: float = float(cn2) * (float(path) / float(bench)) ** (11.0 / 6.0)
    return required


def horizontal_aperture_averaging_factor(
    path_length_m: FloatArray | float,
    *,
    aperture_diameter_m: float,
    wavelength_m: float,
    wave: PathWave,
) -> FloatArray:
    """Return the factor by which a receiving aperture suppresses scintillation.

    Kaushal & Kaddoum equations (20) and (21)::

        A = 1 / (1 + c (k D^2 / (4 L))^(7/6)),   c = 1.07 (plane), 0.214 (spherical)

    **What it is.** The ratio of the variance a lens of diameter ``D`` sees to
    the variance a point would see (their equation (19)): 1 for a point, towards
    0 for a lens much wider than the speckle.

    **Why the path length is in it.** ``k D^2 / 4L`` is the aperture measured
    against the Fresnel scale ``sqrt(lambda L)`` — the size of the speckles a
    path of length ``L`` produces. A longer path makes bigger speckles, so the
    same lens averages fewer of them. This is the horizontal counterpart of
    ITU-R P.1622 equation (7), which does the same with the turbulence scale
    height and the elevation, and which must not be used here: at zero elevation
    its ``sin(theta)`` removes the averaging altogether.

    **Weak turbulence only**, like the variance it multiplies; the warning lives
    in :func:`horizontal_point_log_irradiance_variance`.

    Parameters
    ----------
    path_length_m
        Path length, m. Any shape.
    aperture_diameter_m
        Receiving aperture diameter, m.
    wavelength_m
        Optical wavelength, m.
    wave
        :class:`PathWave`, required.

    Returns
    -------
    FloatArray
        ``A``, in ``(0, 1]``, shaped like ``path_length_m``.

    Raises
    ------
    DomainError
        If the length, diameter or wavelength fails its guard.

    Examples
    --------
    A lens the size of the Fresnel scale, ``D = sqrt(lambda L)``, already
    removes two thirds of the plane-wave variance, and ten centimetres at one
    kilometre remove 94 %:

    >>> fresnel = float(np.sqrt(1.55e-06 * 1000.0))
    >>> round(
    ...     float(
    ...         horizontal_aperture_averaging_factor(
    ...             1000.0, aperture_diameter_m=fresnel, wavelength_m=1.55e-06, wave=PathWave.PLANE
    ...         )
    ...     ),
    ...     3,
    ... )
    0.356
    >>> round(
    ...     float(
    ...         horizontal_aperture_averaging_factor(
    ...             1000.0, aperture_diameter_m=0.1, wavelength_m=1.55e-06, wave=PathWave.PLANE
    ...         )
    ...     ),
    ...     4,
    ... )
    0.059
    """
    path = _validated_path_length_m(path_length_m)
    diameter = validated_positive_length_m(
        "aperture_diameter_m",
        aperture_diameter_m,
        hint="The unit is metres: a 10 cm lens is 0.1, and 10.0 would average a hundred "
        "times too much.",
    )
    coefficient = (
        KAUSHAL_PLANE_APERTURE_AVERAGING_COEFFICIENT
        if PathWave(wave) is PathWave.PLANE
        else KAUSHAL_SPHERICAL_APERTURE_AVERAGING_COEFFICIENT
    )
    fresnel_ratio = _wavenumber(wavelength_m) * diameter * diameter / (4.0 * path)
    factor: FloatArray = 1.0 / (1.0 + coefficient * fresnel_ratio ** (7.0 / 6.0))
    return factor


def horizontal_log_irradiance_variance(
    path_length_m: FloatArray | float,
    *,
    cn2_m23: FloatArray | float,
    aperture_diameter_m: float,
    wavelength_m: float,
    wave: PathWave,
    degradations: DegradationLog,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
) -> FloatArray:
    """Return the log-irradiance variance a receiving lens sees, Np^2.

    The point-detector variance of :func:`horizontal_point_log_irradiance_variance`
    times the averaging factor of :func:`horizontal_aperture_averaging_factor` —
    equation (19) of Kaushal & Kaddoum read backwards. This is the number the
    fade laws of :mod:`quoss.channel.link_budget` take.

    Parameters
    ----------
    path_length_m
        Path length, m. Any shape; broadcast against ``cn2_m23``.
    cn2_m23
        ``C_n^2`` along the path, m^(-2/3).
    aperture_diameter_m
        Receiving aperture diameter, m.
    wavelength_m
        Optical wavelength, m.
    wave
        :class:`PathWave`, required.
    degradations
        Log that receives the weak-turbulence warning.

    regime
        :class:`~quoss.channel.turbulence.ScintillationRegime`. ``WEAK`` (the
        default) returns the first-order value itself and records
        ``horizontal.weak-fluctuation-limit-exceeded`` above
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
    FloatArray
        Variance in Np^2.

    Examples
    --------
    P.1814's moderate turbulence over 1 km, into a 10 cm lens: the 0.199 Np^2 a
    point would see becomes 0.0117.

    >>> from quoss.core.errors import DegradationLog
    >>> variance = horizontal_log_irradiance_variance(
    ...     1000.0,
    ...     cn2_m23=1e-14,
    ...     aperture_diameter_m=0.1,
    ...     wavelength_m=1.55e-06,
    ...     wave=PathWave.PLANE,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(variance), 4)
    0.0117
    """
    point = horizontal_point_log_irradiance_variance(
        path_length_m,
        cn2_m23=cn2_m23,
        wavelength_m=wavelength_m,
        wave=wave,
        degradations=degradations,
        regime=regime,
    )
    factor = horizontal_aperture_averaging_factor(
        path_length_m, aperture_diameter_m=aperture_diameter_m, wavelength_m=wavelength_m, wave=wave
    )
    result: FloatArray = factor * point
    return result


def _warn_if_the_wave_contradicts_the_beam(
    path_m: FloatArray,
    *,
    wave: PathWave,
    wavelength_m: float,
    transmit_aperture_m: float,
    degradations: DegradationLog,
) -> None:
    """Record a WARNING where the declared wave is the wrong side of the Rayleigh range.

    The Rayleigh range is where the beam has grown by ``sqrt(2)`` — the
    conventional boundary between collimated and spreading
    (:func:`quoss.channel.beam.rayleigh_range_km`) — not a threshold fitted to
    anything. Past it a plane wave overstates the variance; inside it a
    spherical wave understates it; and the two differ by the factor carried in
    the warning.
    """
    rayleigh_km = rayleigh_range_km(
        wavelength_m=wavelength_m, transmit_aperture_m=transmit_aperture_m
    )
    rayleigh_m = float(km_to_m(rayleigh_km))
    ratio = path_m / rayleigh_m
    plane_over_spherical = PLANE_WAVE_RYTOV_COEFFICIENT / KAUSHAL_SPHERICAL_WAVE_COEFFICIENT
    if wave is PathWave.PLANE and float(np.max(ratio)) > 1.0:
        code, worst, direction = (
            "horizontal.plane-wave-beyond-the-rayleigh-range",
            float(np.max(ratio)),
            "longer",
        )
    elif wave is PathWave.SPHERICAL and float(np.min(ratio)) < 1.0:
        code, worst, direction = (
            "horizontal.spherical-wave-inside-the-rayleigh-range",
            float(np.min(ratio)),
            "shorter",
        )
    else:
        return
    degradations.warn(
        code,
        (
            f"A {wave.value} wave was declared, but the path is {worst:.3g} times the "
            f"{rayleigh_m:.4g} m Rayleigh range of a {transmit_aperture_m} m transmitter — "
            f"{direction} than the range where that idealisation describes the beam. The two "
            f"closed forms differ by a factor {plane_over_spherical:.3g} in the point variance, "
            "and near the Rayleigh range neither is the Gaussian beam wave, whose formulas are "
            "ADR 0009 gap 1. Compute the budget with both waves to see what the choice is worth."
        ),
        where="quoss.channel.horizontal.horizontal_loss_budget",
        wave=wave.value,
        rayleigh_range_m=rayleigh_m,
        path_to_rayleigh_range_ratio=worst,
        plane_to_spherical_variance_ratio=plane_over_spherical,
    )


def horizontal_loss_budget(
    path_length_m: FloatArray | float,
    *,
    wavelength_m: float,
    transmit_aperture_m: float,
    receive_aperture_m: float,
    cn2_m23: FloatArray | float,
    extinction_db_per_km: float,
    wave: PathWave,
    pointing_jitter_rad: float,
    receiver_efficiency: float,
    degradations: DegradationLog,
    outage_probability: float = NTANOS_OUTAGE_PROBABILITY,
    static_loss_db: float = 0.0,
    transmit_truncation_ratio: float = GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE,
    fade_combination: FadeCombination = FadeCombination.EXACT,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
) -> LossBudget:
    """Assemble the loss budget of a horizontal path, at one or many path lengths.

    Term by term, and where each comes from:

    - **geometric**: :func:`quoss.channel.beam.geometric_transmittance` at the
      path length. That function is the exact Gaussian beam, not the far-field
      shorthand, so it is right on a bench too — where it saturates at 1 once
      the lens is wider than the beam, instead of promising more light than was
      sent. ITU-R P.1814 equation (2) uses a cone and has to be clipped to zero
      by hand in the same case.
    - **atmospheric**: ``extinction_db_per_km`` times the length, which is the
      form of P.1814 equation (3), ``gamma_atmo`` in dB/km. **Required, with no
      default**, for the reason ``zenith_transmittance`` is required on the
      downlink (ADR 0009 gap 14): P.1814 gives the fog, rain and snow laws but no
      clear-air number, and 0.0 has to be written by whoever means it.
      :func:`quoss.channel.extinction.aerosol_specific_attenuation_db_per_km` is
      what computes one from a visibility, and it returns exactly this unit —
      see ``docs/adr/0023-traceable-extinction.md``, including why P.1814's own
      equation (4) prints dB/km for a quantity that is in nepers per km.
    - **pointing** and **scintillation**: the fade laws of
      :mod:`quoss.channel.link_budget`, with ``gamma`` from
      :func:`quoss.channel.pointing.beam_to_jitter_ratio` and the variance from
      :func:`horizontal_log_irradiance_variance`, combined exactly as the downlink
      combines them — by the same private function.

    No elevation anywhere, and no ``station_height_m``: the turbulence is
    ``cn2_m23``, constant along the path, and a value measured at the height
    the link actually runs at is the only one that means anything.

    Parameters
    ----------
    path_length_m
        Path length, m, strictly positive. Any shape: pass an array to sweep the
        distance. Broadcast against ``cn2_m23``.
    wavelength_m
        Optical wavelength, m.
    transmit_aperture_m
        Transmitter aperture diameter, m; the beam waist is half of it
        (:func:`quoss.channel.beam.divergence_half_angle_rad`).
    receive_aperture_m
        Receiving aperture diameter, m.
    cn2_m23
        ``C_n^2`` along the path, m^(-2/3). Any shape, broadcast against the length.
    extinction_db_per_km
        Specific attenuation of the air, dB/km, non-negative. Required.
    wave
        :class:`PathWave`, required. A WARNING is recorded if it contradicts the
        transmitter's Rayleigh range.
    pointing_jitter_rad
        R.m.s. pointing jitter per axis, rad, strictly positive.
    receiver_efficiency
        Linear efficiency of the receiver chain, in ``(0, 1]``.
    degradations
        Log for every warning of the modules called.
    outage_probability
        Outage the fade term is quoted at, in ``(0, 1)``.
    static_loss_db
        Constant loss no module here models, dB, non-negative.
    transmit_truncation_ratio
        ``alpha``, as in :func:`quoss.channel.link_budget.downlink_loss_budget`.
    fade_combination
        :attr:`FadeCombination.EXACT` (default) or :attr:`FadeCombination.ADDITIVE`.

    regime
        :class:`~quoss.channel.turbulence.ScintillationRegime`. ``WEAK`` (the
        default) returns the first-order value itself and records
        ``horizontal.weak-fluctuation-limit-exceeded`` above
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
        The same container as the downlink, shaped by broadcasting length and ``C_n^2``.

    Raises
    ------
    DomainError
        If any argument is outside its domain, or ``extinction_db_per_km`` or
        ``static_loss_db`` is negative or not finite.
    """
    path = _validated_path_length_m(path_length_m)
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
    extinction = float(extinction_db_per_km)
    if not np.isfinite(extinction) or extinction < 0.0:
        raise DomainError(
            f"extinction_db_per_km must be finite and non-negative, got {extinction}. It is "
            "ITU-R P.1814's gamma_atmo, a loss per kilometre: clear air is a fraction of a dB/km, "
            "and 0.0 declares it ignored."
        )
    combination = FadeCombination(fade_combination)
    selected = PathWave(wave)

    _warn_if_the_wave_contradicts_the_beam(
        path,
        wave=selected,
        wavelength_m=wavelength,
        transmit_aperture_m=transmit,
        degradations=degradations,
    )
    range_km = path / km_to_m(1.0)
    geometric = geometric_transmittance(
        range_km, wavelength_m=wavelength, transmit_aperture_m=transmit, receive_aperture_m=receive
    )
    gamma = beam_to_jitter_ratio(
        range_km,
        jitter_rad=pointing_jitter_rad,
        wavelength_m=wavelength,
        transmit_aperture_m=transmit,
        receive_aperture_m=receive,
        degradations=degradations,
    )
    variance = horizontal_log_irradiance_variance(
        path,
        cn2_m23=cn2_m23,
        aperture_diameter_m=receive,
        wavelength_m=wavelength,
        wave=selected,
        degradations=degradations,
        regime=regime,
    )
    return _assembled_loss_budget(
        geometric=geometric,
        atmospheric_db=np.asarray(extinction * range_km, dtype=np.float64),
        gamma=gamma,
        variance=variance,
        chain=chain,
        outage=outage,
        static=static,
        transmit_truncation_ratio=transmit_truncation_ratio,
        combination=combination,
    )
