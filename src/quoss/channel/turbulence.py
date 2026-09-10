"""Turbulence strength along a slant path: scintillation, r0, isoplanatic angle.

What this module is for
-----------------------
:mod:`quoss.channel.atmosphere` says how turbulent the air is at each height.
This module says what that does to a beam travelling through it at a given
elevation angle, and it is where the time axis enters the channel: the profile
is fixed for a pass, but the satellite climbs and sets, so the amount of
atmosphere in the way changes every second.

Three quantities come out, and they answer three different questions.

**Scintillation** — the twinkling of a star, and the reason a link fades. As the
beam crosses those moving lenses, parts of the wavefront are focused together
and parts are spread apart, so the power arriving at the receiver flickers. It is
measured by the variance of the natural logarithm of the received irradiance,
written ``sigma^2_lnN`` and quoted in "nepers squared" — which only means the
logarithm is natural rather than base ten. A variance of 0.1 Np^2 is roughly a
30 % r.m.s. swing in received power.

**The Fried parameter r0** — the diameter over which the arriving wavefront is
still flat enough to be considered coherent. A telescope bigger than ``r0`` does
not see a sharper image, it sees a blurrier one made of more speckles. At a good
site at optical wavelengths ``r0`` is 10-20 cm, which is why a 1 m telescope
needs adaptive optics to reach its diffraction limit.

**The isoplanatic angle** — how far apart two directions can be before they have
travelled through appreciably different turbulence. It matters for point-ahead:
if the angle a terminal must lead by exceeds this, the outgoing beam is being
pre-compensated for turbulence that is not on its actual path.

Uplink and downlink are not symmetric
-------------------------------------
This is the trap that catches implementations, and ITU-R P.1622 splits it into
two numbered sections precisely because of it. On the **downlink** the beam
arrives having already been scrambled, and a receiver aperture wider than the
speckle pattern averages several speckles together, which suppresses the
flicker: that is *aperture averaging*, §4.1.2. On the **uplink** the perturbation
happens at the start of a very long free-space path, and by the time the light
reaches the spacecraft, diffraction has spread each perturbation over an area far
larger than any plausible receiving aperture — so **no aperture averaging occurs
at all**, §4.1.1. Applying the downlink formula to an uplink silently removes a
suppression that is not there.

This project models the **downlink**, which is the direction Micius and the ITU
example scenarios use. The uplink variance is exposed as its own function so the
asymmetry is visible rather than implied.

Where these numbers come from
-----------------------------
ITU-R P.1622 §4.1 for scintillation and aperture averaging; ITU-R P.1621-2
§5.1.2 and §5.1.3 for the Fried parameter and the isoplanatic angle. Both are
free and numbered. See ``docs/adr/0009-citation-policy.md`` for why the usual
textbook is not cited by equation number here.

======================  ====================================================
Symbol                  Meaning
======================  ====================================================
``theta``               elevation angle above the horizon (rad)
``zeta``                zenith angle, ``pi/2 - theta`` (rad)
``k``                   wavenumber, ``2 pi / lambda`` (1/m)
``sigma^2_lnN``         variance of log-irradiance (Np^2)
``A``                   aperture averaging factor (dimensionless, 0 to 1)
``z0``                  turbulence scale height (m)
``r0``                  Fried parameter, atmospheric coherence length (m)
``theta_0``             isoplanatic angle (rad)
======================  ====================================================

References
----------
Recommendation ITU-R P.1622 (04/2003), *Prediction methods required for the
design of Earth-space systems operating between 20 THz and 375 THz*, §4.1
(equations (4a)-(8)).

Recommendation ITU-R P.1621-2 (07/2015), §5.1.2 (equations (8a), (8b)) and
§5.1.3 (equations (14a), (14b)).
"""

from __future__ import annotations

from typing import Final

import numpy as np

from quoss.channel.atmosphere import (
    ITU_GROUND_CN2_M23,
    ITU_TURBULENCE_TOP_HEIGHT_M,
    hufnagel_valley_cn2_m23,
    itu_layer_heights_m,
    itu_layer_thicknesses_m,
)
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray

__all__ = [
    "NEPER_SQ_TO_DB_SQ",
    "WEAK_FLUCTUATION_VARIANCE_LIMIT",
    "aperture_averaging_factor",
    "cn2_path_moment",
    "downlink_log_irradiance_variance",
    "fried_parameter_m",
    "isoplanatic_angle_rad",
    "log_irradiance_variance",
    "turbulence_scale_height_m",
    "uplink_log_irradiance_variance",
]

NEPER_SQ_TO_DB_SQ: Final[float] = (10.0 / np.log(10.0)) ** 2
"""Convert a log-irradiance variance from Np^2 to dB^2.

ITU-R P.1622 equation (4c) is equation (4b) "multiplied by the change-of-base
ratio and a factor of 10", which is this squared. It evaluates to 18.861, and
Table 2 of that recommendation is internally consistent with it: 0.23 Np^2 is
printed alongside 4.35 dB^2, and 0.23 * 18.861 = 4.34.
"""

WEAK_FLUCTUATION_VARIANCE_LIMIT: Final[float] = 1.0
"""Above this log-irradiance variance, weak-fluctuation theory is out of its range.

Equation (4a) comes from a first-order (Rytov) perturbation treatment, which
assumes the fluctuation it is computing is small. Once the answer approaches 1
the assumption that produced it has failed, and the true scintillation index
saturates rather than continuing to grow. The formula keeps returning numbers,
which is exactly the danger: they are too large, and nothing about them looks
wrong.

The limit is 1 because that is where the expansion parameter reaches unity, not
because a fit was tuned there. Crossing it records a
:class:`~quoss.core.errors.Severity.WARNING`, not a substitution: the value
returned is still the model the caller asked for.
"""

_APERTURE_AVERAGING_COEFFICIENT: Final[float] = 1.1e7
"""Coefficient of ITU-R P.1622 equation (7), which wants its wavelength in micrometres.

Worth its own note because getting it wrong is silent and enormous. The equation
is usually written with a coefficient of 1.1 and the wavelength in metres; the
recommendation prints 1.1e7 because it takes micrometres, and
``(1e6)^(7/6) = 1e7`` exactly absorbs the conversion.

Feeding metres into the 1.1e7 form was the first bug written in this module: it
made a 1 m telescope suppress scintillation by a factor of 2e9, which is
physically impossible and still produced a number between 0 and 1 that no shape
or range assertion would have caught. What catches it is the Fresnel scale —
averaging should set in once the aperture exceeds ``sqrt(lambda L)``, about
11 cm here — and ``tests/channel/test_turbulence.py`` pins that comparison.
"""
_CLOSED_FORM_R0_COEFFICIENT: Final[float] = 1.1654e-8
_CLOSED_FORM_ISOPLANATIC_COEFFICIENT: Final[float] = 3.663e-9
_LOG_IRRADIANCE_COEFFICIENT: Final[float] = 1.924e8
"""Coefficients of the closed forms, which are written for a wavelength in micrometres.

The recommendations give each of these quantities twice: once as an integral
with an explicit wavenumber, and once as a closed form with a numeric
coefficient and the wavelength in micrometres. The two are consistent, and
recomputing the coefficient from the integral form is a check worth keeping —
0.423 * (2 pi)^2 raised to -3/5, converted to micrometres, gives 1.1652e-8
against the printed 1.1654e-8. ``tests/channel/test_turbulence.py`` asserts all
three, which is what catches a mistyped digit in any of them.
"""

_MICROMETRES_PER_METRE: Final[float] = 1.0e6


def _validated_elevation(elevation_rad: FloatArray | float) -> FloatArray:
    """Return the elevation as an array, rejecting anything not above the horizon."""
    elevation = np.asarray(elevation_rad, dtype=np.float64)
    if not np.all(np.isfinite(elevation)):
        raise DomainError("elevation_rad contains non-finite values.")
    if np.any(elevation <= 0.0) or np.any(elevation > 0.5 * np.pi):
        raise DomainError(
            "elevation_rad must lie in (0, pi/2]: a slant path through the atmosphere needs a "
            "target above the horizon, and every formula here carries a sec(zenith) that "
            "diverges at zero. Range given: "
            f"[{float(np.min(elevation))}, {float(np.max(elevation))}] rad. The unit is "
            "radians, not degrees; and quoss.orbits.geometry.look_angles reports elevation "
            "below the horizon without filtering, so segment the pass before calling this."
        )
    return elevation


def _validated_wavelength_um(wavelength_m: float) -> float:
    """Return the wavelength in micrometres, which is what the closed forms use."""
    wavelength = float(wavelength_m)
    if not np.isfinite(wavelength) or wavelength <= 0.0:
        raise DomainError(f"wavelength_m must be finite and positive, got {wavelength}.")
    return wavelength * _MICROMETRES_PER_METRE


def cn2_path_moment(
    power: float,
    *,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> float:
    """Return the vertical moment ``integral of Cn2(h) (h - h0)^power dh``.

    Every quantity in this module is a power of one of these moments, differing
    only in the exponent, so computing them through one function keeps the
    quadrature grid in a single place:

    ======  ==============================================
    power   Used by
    ======  ==============================================
    0       Fried parameter, ITU-R P.1621-2 equation (8a)
    5/6     Log-irradiance variance, ITU-R P.1622 (4a)
    5/3     Isoplanatic angle, ITU-R P.1621-2 (14a)
    2       Turbulence scale height, ITU-R P.1622 (6)
    ======  ==============================================

    The higher the power, the more the answer is dominated by high-altitude
    turbulence: the ``power = 0`` moment is mostly the boundary layer, while the
    ``power = 2`` moment is mostly the jet stream. That is the whole reason
    aperture averaging and scintillation behave differently from seeing.

    Parameters
    ----------
    power
        Exponent applied to the height above the station.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    float
        The moment, in units of m^(1/3) times metres to the given power.

    Raises
    ------
    DomainError
        If the power is not finite, or the station height is outside the
        atmosphere.

    Examples
    --------
    The zeroth moment is the plain integral of the profile:

    >>> f"{cn2_path_moment(0.0):.3e}"
    '2.234e-12'

    Weighting by height raises the contribution of the jet stream enormously:

    >>> f"{cn2_path_moment(2.0):.3e}"
    '1.849e-05'
    """
    exponent = float(power)
    if not np.isfinite(exponent):
        raise DomainError(f"power must be finite, got {exponent}.")
    station = float(station_height_m)
    if not np.isfinite(station):
        raise DomainError(f"station_height_m must be finite, got {station}.")
    if station < 0.0:
        raise DomainError(f"station_height_m must be non-negative, got {station} m.")
    if station >= ITU_TURBULENCE_TOP_HEIGHT_M:
        raise DomainError(
            f"station_height_m of {station} m is at or above the {ITU_TURBULENCE_TOP_HEIGHT_M} m "
            "top of the turbulent atmosphere, leaving no path to integrate."
        )

    heights = itu_layer_heights_m()
    thicknesses = itu_layer_thicknesses_m()
    profile = hufnagel_valley_cn2_m23(
        heights,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    above = heights > station
    offsets = heights[above] - station
    return float(np.sum(profile[above] * offsets**exponent * thicknesses[above]))


def log_irradiance_variance(
    elevation_rad: FloatArray | float,
    *,
    wavelength_m: float,
    degradations: DegradationLog,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the point-aperture variance of log-irradiance, Np^2.

    This is the raw scintillation strength before any aperture averaging: what a
    detector small compared with the speckle pattern would see. ITU-R P.1622
    §4.1 equation (4b), with the wavelength in micrometres::

        sigma^2_lnN = 1.924e8 * integral(Cn2(h) (h - h0)^(5/6) dh)
                    / (lambda^(7/6) * sin(theta)^(11/6))

    Equation (4a) writes the same thing with an explicit wavenumber and a
    ``sec(zeta)^(11/6)``; the two agree to four significant figures, and a test
    asserts that rather than trusting it.

    The elevation dependence is the steep part: ``sin(theta)^(-11/6)`` means that
    dropping from 75 degrees to 10 degrees multiplies the variance by 22. That is
    why a pass is not a slowly varying channel, and why this function is
    vectorised over the time axis.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive. Any shape;
        typically ``(n_samples,)`` or ``(n_satellites, n_samples)``.
    wavelength_m
        Optical wavelength, m.
    degradations
        Log that receives a warning if the variance leaves the range where
        weak-fluctuation theory holds.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        Variance of log-irradiance in Np^2, with the shape of ``elevation_rad``.

    Raises
    ------
    DomainError
        If any elevation is outside ``(0, pi/2]`` or non-finite, or the
        wavelength is not finite and positive.

    Examples
    --------
    The conditions of ITU-R P.1622 Table 2 — 75 degrees elevation, station 5.5 m
    above ground, 21 m/s r.m.s. wind — at 1.55 um, where the table prints 0.07:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import deg_to_rad
    >>> log = DegradationLog()
    >>> variance = log_irradiance_variance(
    ...     deg_to_rad(75.0), wavelength_m=1.55e-06, station_height_m=5.5, degradations=log
    ... )
    >>> round(float(variance), 3)
    0.066

    Low elevation is a different channel, not a slightly worse one:

    >>> low = log_irradiance_variance(
    ...     deg_to_rad(10.0), wavelength_m=1.55e-06, station_height_m=5.5, degradations=log
    ... )
    >>> round(float(low / variance), 1)
    23.2
    """
    elevation = _validated_elevation(elevation_rad)
    wavelength_um = _validated_wavelength_um(wavelength_m)
    moment = cn2_path_moment(
        5.0 / 6.0,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    variance: FloatArray = (
        _LOG_IRRADIANCE_COEFFICIENT
        * moment
        / (wavelength_um ** (7.0 / 6.0) * np.sin(elevation) ** (11.0 / 6.0))
    )

    peak = float(np.max(variance))
    if peak > WEAK_FLUCTUATION_VARIANCE_LIMIT:
        degradations.warn(
            "turbulence.weak-fluctuation-limit-exceeded",
            (
                f"Log-irradiance variance reaches {peak:.2f} Np^2, above the "
                f"{WEAK_FLUCTUATION_VARIANCE_LIMIT} Np^2 where the first-order theory behind "
                "ITU-R P.1622 equation (4a) holds. The value returned is still that model's, "
                "but real scintillation saturates instead of growing, so this overestimates it."
            ),
            where="quoss.channel.turbulence.log_irradiance_variance",
            peak_variance_np2=peak,
            limit_np2=WEAK_FLUCTUATION_VARIANCE_LIMIT,
            min_elevation_rad=float(np.min(elevation)),
        )
    return variance


def turbulence_scale_height_m(
    *,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> float:
    """Return the effective height of the turbulence that causes scintillation, m.

    ITU-R P.1622 §4.1.2 equation (6)::

        z0 = [integral(Cn2 h^2 dh) / integral(Cn2 h^(5/6) dh)] ^ (6/7)

    It is a ratio of two moments, so it answers "where, in an effective sense, is
    the turbulence that matters for scintillation?" — and the answer is high up,
    around 10 km, because the ``h^2`` weighting in the numerator picks out the
    jet stream. That is what makes the speckle pattern on the ground fine enough
    for a metre-class telescope to average over.

    Returns
    -------
    float
        The turbulence scale height, m.

    Examples
    --------
    >>> round(turbulence_scale_height_m() / 1000.0, 1)
    7.7
    """
    numerator = cn2_path_moment(
        2.0,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    denominator = cn2_path_moment(
        5.0 / 6.0,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    return float((numerator / denominator) ** (6.0 / 7.0))


def aperture_averaging_factor(
    elevation_rad: FloatArray | float,
    *,
    aperture_diameter_m: float,
    wavelength_m: float,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the factor by which a finite aperture suppresses scintillation.

    A point detector sees the full flicker. A telescope wider than the speckle
    pattern collects many independent speckles at once and their fluctuations
    partly cancel, so the total power it collects varies less. ITU-R P.1622
    §4.1.2 equation (7)::

        A = 1 / (1 + 1.1e7 * (D^2 sin(theta) / (lambda z0)) ^ (7/6))

    ``A`` runs from 1 (no suppression, a point aperture) down towards 0 (heavy
    suppression). It is a **downlink-only** quantity: see
    :func:`uplink_log_irradiance_variance` for why the uplink gets none of this.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    aperture_diameter_m
        Diameter of the ground station's receiving aperture, m.
    wavelength_m
        Optical wavelength, m.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The averaging factor, between 0 and 1, shaped like ``elevation_rad``.

    Raises
    ------
    DomainError
        If the aperture diameter is not finite and positive, or the elevation or
        wavelength fails its own guard.

    Examples
    --------
    A 1 m telescope at 1550 nm suppresses scintillation by a large factor at high
    elevation:

    >>> from quoss.core.units import deg_to_rad
    >>> factor = aperture_averaging_factor(
    ...     deg_to_rad(75.0), aperture_diameter_m=1.0, wavelength_m=1.55e-06
    ... )
    >>> round(float(factor), 4)
    0.0054

    A 1 cm aperture is comparable to the speckle size and averages almost
    nothing:

    >>> small = aperture_averaging_factor(
    ...     deg_to_rad(75.0), aperture_diameter_m=0.01, wavelength_m=1.55e-06
    ... )
    >>> round(float(small), 3)
    0.996
    """
    elevation = _validated_elevation(elevation_rad)
    wavelength_um = _validated_wavelength_um(wavelength_m)
    diameter = float(aperture_diameter_m)
    if not np.isfinite(diameter) or diameter <= 0.0:
        raise DomainError(
            f"aperture_diameter_m must be finite and positive, got {diameter}. The unit is "
            "metres: an aperture given in centimetres would understate the averaging."
        )
    scale_height = turbulence_scale_height_m(
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    argument = diameter * diameter * np.sin(elevation) / (wavelength_um * scale_height)
    factor: FloatArray = 1.0 / (1.0 + _APERTURE_AVERAGING_COEFFICIENT * argument ** (7.0 / 6.0))
    return factor


def downlink_log_irradiance_variance(
    elevation_rad: FloatArray | float,
    *,
    aperture_diameter_m: float,
    wavelength_m: float,
    degradations: DegradationLog,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the log-irradiance variance seen by a ground telescope, Np^2.

    ITU-R P.1622 §4.1.2 equation (8): the point-aperture variance of equation
    (4b), reduced by the aperture averaging factor of equation (7)::

        sigma^2_{s-E} = A * sigma^2_lnN

    This is the number the link budget wants for a satellite-to-ground QKD link.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    aperture_diameter_m
        Diameter of the ground station's receiving aperture, m.
    wavelength_m
        Optical wavelength, m.
    degradations
        Log that receives a warning if weak-fluctuation theory is out of range.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        Variance of log-irradiance in Np^2, shaped like ``elevation_rad``.

    Examples
    --------
    The aperture does most of the work: a 1 m telescope at 75 degrees turns a
    point-aperture 0.066 Np^2 into something eighty times smaller.

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import deg_to_rad
    >>> log = DegradationLog()
    >>> variance = downlink_log_irradiance_variance(
    ...     deg_to_rad(75.0),
    ...     aperture_diameter_m=1.0,
    ...     wavelength_m=1.55e-06,
    ...     station_height_m=5.5,
    ...     degradations=log,
    ... )
    >>> f"{float(variance):.3e}"
    '3.565e-04'
    """
    point_variance = log_irradiance_variance(
        elevation_rad,
        wavelength_m=wavelength_m,
        degradations=degradations,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    factor = aperture_averaging_factor(
        elevation_rad,
        aperture_diameter_m=aperture_diameter_m,
        wavelength_m=wavelength_m,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    result: FloatArray = factor * point_variance
    return result


def uplink_log_irradiance_variance(
    elevation_rad: FloatArray | float,
    *,
    wavelength_m: float,
    degradations: DegradationLog,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the log-irradiance variance seen by a spacecraft, Np^2.

    ITU-R P.1622 §4.1.1 equation (5)::

        sigma^2_{E-s} = sigma^2_lnN

    That is: **no aperture averaging**, and the function exists to make that a
    visible choice rather than a missing multiplication. The recommendation's
    reasoning is that the perturbations imposed near the ground are spread by
    diffraction over the whole long path to orbit, so "the phase coherence radius
    at the receiving aperture on a spacecraft is much larger than the probable
    size of the spacecraft receiver aperture".

    It takes no aperture diameter, and that absence is the point: a signature
    with a diameter to pass would invite someone to pass one. Same reasoning as
    ``secular_rates_j2`` having nowhere to put a J3.

    This project models the downlink; this function is here so the asymmetry is
    documented and testable, not because the uplink is wired up.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    wavelength_m
        Optical wavelength, m.
    degradations
        Log that receives a warning if weak-fluctuation theory is out of range.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        Variance of log-irradiance in Np^2, shaped like ``elevation_rad``.
    """
    return log_irradiance_variance(
        elevation_rad,
        wavelength_m=wavelength_m,
        degradations=degradations,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )


def fried_parameter_m(
    elevation_rad: FloatArray | float,
    *,
    wavelength_m: float,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the Fried parameter, the coherence length of the atmosphere, m.

    ITU-R P.1621-2 §5.1.2 equation (8b), the closed form with the wavelength in
    micrometres::

        r0 = 1.1654e-8 * lambda^1.2 * sin(theta)^0.6 / (integral Cn2 dh)^0.6

    Equation (8a) is the same quantity written as
    ``[0.423 k^2 sec(zeta) integral]^(-3/5)``.

    ``r0`` grows with wavelength as ``lambda^1.2``, which is why infrared links
    are so much less troubled by turbulence than visible ones: going from 532 nm
    to 1550 nm more than triples it.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    wavelength_m
        Optical wavelength, m.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The Fried parameter in metres, shaped like ``elevation_rad``.

    Examples
    --------
    At 1550 nm, straight up, from a sea-level site under nominal conditions:

    >>> from quoss.core.units import deg_to_rad
    >>> round(float(fried_parameter_m(deg_to_rad(90.0), wavelength_m=1.55e-06)), 3)
    0.193

    The same site in visible light has a coherence length three times smaller,
    which is the difference between needing adaptive optics and not:

    >>> round(float(fried_parameter_m(deg_to_rad(90.0), wavelength_m=5.32e-07)), 3)
    0.053
    """
    elevation = _validated_elevation(elevation_rad)
    wavelength_um = _validated_wavelength_um(wavelength_m)
    moment = cn2_path_moment(
        0.0,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    result: FloatArray = (
        _CLOSED_FORM_R0_COEFFICIENT * wavelength_um**1.2 * np.sin(elevation) ** 0.6 / moment**0.6
    )
    return result


def isoplanatic_angle_rad(
    elevation_rad: FloatArray | float,
    *,
    wavelength_m: float,
    station_height_m: float = 0.0,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return the isoplanatic angle, rad.

    ITU-R P.1621-2 §5.1.3 equation (14b), with the wavelength in micrometres::

        theta_0 = 3.663e-9 * lambda^1.2 * sin(theta)^1.6
                / (integral Cn2 (h - h0)^(5/3) dh)^0.6

    Equation (14a) writes it as
    ``[2.914 k^2 sec(zeta)^(8/3) integral]^(-3/5)``.

    The recommendation notes the values are "on the order of 1e-6 to 1e-4 rad",
    and that ``theta_0`` "decreases rapidly with elevation angles below about
    75 degrees" — the ``sin^1.6`` here against the ``sin^0.6`` of the Fried
    parameter is that statement in algebra.

    This is the number to compare a point-ahead angle against.
    :func:`quoss.orbits.geometry.look_angles` measured 50.6 microradians of
    point-ahead for a 700 km pass, so whether the outgoing beam is being
    corrected for the turbulence it will actually cross is a question this
    function answers.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians, strictly positive.
    wavelength_m
        Optical wavelength, m.
    station_height_m
        Height of the ground station above ground level, m.
    rms_wind_speed_m_s
        The r.m.s. wind speed, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        The isoplanatic angle in radians, shaped like ``elevation_rad``.

    Examples
    --------
    At 1550 nm overhead, in the microradian range the recommendation describes:

    >>> from quoss.core.units import deg_to_rad
    >>> overhead = isoplanatic_angle_rad(deg_to_rad(90.0), wavelength_m=1.55e-06)
    >>> f"{float(overhead):.3e}"
    '2.721e-05'

    And it collapses towards the horizon far faster than r0 does:

    >>> low = isoplanatic_angle_rad(deg_to_rad(20.0), wavelength_m=1.55e-06)
    >>> round(float(overhead / low), 1)
    5.6
    """
    elevation = _validated_elevation(elevation_rad)
    wavelength_um = _validated_wavelength_um(wavelength_m)
    moment = cn2_path_moment(
        5.0 / 3.0,
        station_height_m=station_height_m,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    result: FloatArray = (
        _CLOSED_FORM_ISOPLANATIC_COEFFICIENT
        * wavelength_um**1.2
        * np.sin(elevation) ** 1.6
        / moment**0.6
    )
    return result
