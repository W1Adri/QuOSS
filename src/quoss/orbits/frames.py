"""Time scales and reference frames — the geometry everything else rests on.

This module answers three questions once, so that no later module has to answer
them again differently: *what time is it*, *which inertial frame are we in*, and
*where is the ground station*. Getting any of the three wrong produces curves
that look entirely plausible and are silently offset, which is the failure mode
this project exists to avoid.

Which inertial frame, exactly
-----------------------------
"ECI" is not a frame; it is a family of them, and they differ by tens of
kilometres over a decade. QuOSS commits to **TEME** — True Equator, Mean Equinox
of date — as its single inertial frame, for one decisive reason: it is what SGP4
returns, and SGP4 is not optional in a satellite simulator. Converting TEME to
GCRF and back around every propagation would add error, not remove it.

The Earth-fixed frame is reached by a single rotation about the pole through the
Greenwich Mean Sidereal Time angle. Strictly that lands in **PEF**
(Pseudo-Earth-Fixed), which differs from the true ITRF by polar motion only.
QuOSS treats the result as ITRF and calls it ECEF.

The resulting error budget, stated once and quantified
------------------------------------------------------
Three approximations are made here on purpose. All three are negligible for an
optical link budget, and none is negligible enough to leave undocumented. These
are **measured**, not asserted: ``tests/orbits/test_frames.py`` compares this
module against astropy's full reduction and holds each row to its bound.

=================================  ==========================  ====================
Approximation                      Satellite position error    Effect on the link
=================================  ==========================  ====================
Polar motion ignored (PEF ~ ITRF)  14.4 m, measured worst case  ~14 urad at 1000 km
UT1 ~ UTC (|DUT1| <= 0.9 s)        <= 460 m (274 m measured)    <= 0.03 deg in
                                                                elevation
GMST from the IAU-82 series        ~2 m (0.06 arcsec, 2000-2030) negligible
=================================  ==========================  ====================

The polar-motion figure is the residual left once the UT1 offset is put back,
over epochs from 2000 to 2026; the UT1 bound is the arc that 0.9 s of Earth
rotation subtends at LEO radius, and 274 m is what the largest DUT1 in the
reference set (-0.55 s, March 2015) actually produces. The two do not add
coherently: the UT1 error is a rotation about the pole, so it vanishes for a
satellite over the pole and peaks over the equator.

An elevation error of 0.03 deg changes airmass by about 0.1 % at 10 deg
elevation and shifts the predicted time of a pass by under 0.1 s. Neither is
visible in a secret-key rate. The one place these numbers *would* matter is
open-loop pointing at microradian precision, which QuOSS does not model — a real
terminal closes that loop on a beacon.

Leap seconds are not modelled, and that is a real restriction rather than a
rounding one: QuOSS's absolute time is a UTC Julian date, so an epoch on a day
carrying a leap second is off by up to a second in UT1. Such epochs are excluded
from the reference set for the same reason — see the generator script.

Upgrading to a full GCRF <-> ITRF reduction (precession, nutation, polar motion,
Earth-orientation parameters) means adding :mod:`erfa` and externally maintained
EOP tables that expire. The hook for it is :class:`Frame`, which tags every
array so that a TEME position can never be silently consumed as a GCRF one; the
day the reduction is added, the existing call sites still typecheck and the
tagged arrays make the missing conversions findable by grep.

Why no ``DegradationLog`` in any signature here
-----------------------------------------------
A :class:`~quoss.core.errors.DegradationLog` argument marks a function that may
*choose a fallback at runtime* — evaluate a lesser model because the better one
was not available for these inputs. Nothing in this module does that. The three
approximations above are model choices, fixed for every run and recorded once by
whoever assembles the pipeline; recording them per call would emit one entry per
time sample and drown the log it exists to keep readable. Bad input is an error,
not a degradation, and raises :class:`~quoss.core.errors.DomainError`.

This is the project-wide rule, settled here with the first physics module:
**a physics function takes a log only if it can decide to compute something
different from what its name promises.**

Conventions in force
--------------------
Angles are radians, distances are kilometres, absolute time is a Julian date in
days (UTC), per ``docs/adr/0001-unit-conventions.md``. Degrees appear only in
:func:`calendar_to_jd`-style calendar fields, which are not angles. Every
function is vectorised over the leading axis; a stack of positions has shape
``(n, 3)`` with time first.

References
----------
.. [1] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed., 2013,
       Sections 3.5 (Julian date, sidereal time) and 3.7 (geodetic coordinates).
.. [2] Aoki et al., "The new definition of Universal Time", *Astron. Astrophys.*
       105, 359-361, 1982. The GMST series used here (IAU 1982).
.. [3] Vallado, Crawford, Hujsak & Kelso, "Revisiting Spacetrack Report #3",
       AIAA 2006-6753. TEME definition and the TEME -> PEF rotation.
.. [4] NIMA TR8350.2, *World Geodetic System 1984*, 3rd ed., 2000. Ellipsoid.
.. [5] Meeus, *Astronomical Algorithms*, 2nd ed., 1998, Chapter 7. The Julian
       date to calendar inversion.
"""

from __future__ import annotations

import calendar
from enum import StrEnum
from typing import Final

import numpy as np

from quoss.core.constants import (
    EARTH_ROTATION_RAD_S,
    JD_J2000,
    SECONDS_PER_DAY,
    WGS84_ECCENTRICITY_SQ,
    WGS84_RADIUS_EQUATORIAL_KM,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import FloatArray, FloatLike, Vec3Array
from quoss.orbits._validation import as_1d, as_vec3

__all__ = [
    "Frame",
    "calendar_to_jd",
    "enu_from_itrf",
    "geodetic_to_itrf",
    "gmst_rad",
    "itrf_to_geodetic",
    "itrf_to_teme",
    "itrf_to_teme_state",
    "jd_to_calendar",
    "teme_to_itrf",
    "teme_to_itrf_state",
]

_TWO_PI: Final = 2.0 * np.pi
_JULIAN_CENTURY_DAYS: Final = 36_525.0
"""Days in a Julian century. Exact by definition of the Julian year."""

_SECONDS_PER_HOUR: Final = 3_600.0
_SECONDS_PER_MINUTE: Final = 60.0

# --------------------------------------------------------------------------- #
# GMST (IAU 1982) series, in *seconds of time* [1, Eq. 3-47; 2]
#
# Kept in seconds of time rather than degrees on purpose: a full turn is exactly
# SECONDS_PER_DAY seconds of time, so the conversion to radians is a turn count,
# not a degree-to-radian conversion. That keeps the unit boundary where the
# project convention puts it (see docs/adr/0001) and matches the formulation
# `erfa.gmst82` uses, which is what the reference data is generated from.
# --------------------------------------------------------------------------- #
_GMST82_C0: Final = 67_310.548_41
_GMST82_C1: Final = 876_600.0 * _SECONDS_PER_HOUR + 8_640_184.812_866
_GMST82_C2: Final = 0.093_104
_GMST82_C3: Final = -6.2e-6

# --------------------------------------------------------------------------- #
# Calendar / Julian date
#
# The conversion uses the Fliegel-Van Flandern integer expression, which is exact
# for every Gregorian date. The obvious alternative, Vallado Alg. 14, is *not*:
# its leap term `int(7 (y + int((m+9)/12)) / 4)` is the Julian every-fourth-year
# rule, so it is off by a day across a non-leap century year. Measured against
# astropy, it is exact only from 1900-03-01 to 2100-02-28 and wrong by one day on
# either side. That was found by the reference-data suite on its first run, and
# is the reason this module does not use it.
#
# The year range below is therefore a *plausibility* check, not a limit of the
# algorithm: a three-digit year in a satellite scenario is a typo, not an epoch.
# --------------------------------------------------------------------------- #
_YEAR_MIN: Final = 1900
_YEAR_MAX: Final = 2100

# --------------------------------------------------------------------------- #
# Geodetic inversion
#
# The fixed-point iteration converges geometrically, measured ratio ~4.7e-3 per
# pass (of order e^2), so each pass buys a bit over two decimal digits. Over
# latitudes from pole to pole and altitudes to 2000 km, the successive shifts run
# 6.5e-4, 2.1e-6, 9.0e-9, 4.3e-11, 2.1e-13, 1.1e-15 rad: **seven** passes reach
# the tolerance below, and the cap of 12 leaves a factor of ~5 in margin. A test
# pins that margin so it cannot silently erode; the cap and the check exist for
# pathological input (a point near the Earth's centre), not for real geometry.
# --------------------------------------------------------------------------- #
_GEODETIC_MAX_ITER: Final = 12
_GEODETIC_TOLERANCE_RAD: Final = 1e-14


class Frame(StrEnum):
    """The coordinate frames QuOSS arrays may be expressed in.

    A tag, not a container: it exists so that a state array carries which frame
    it belongs to and a mismatch is a type-level error rather than a plausible
    wrong number. The propagators in this package attach one to every state they
    return.

    Attributes
    ----------
    TEME
        True Equator, Mean Equinox of date. The inertial frame QuOSS computes
        in, and the frame SGP4 outputs. Origin at the Earth's centre of mass.
    ITRF
        Earth-fixed, Earth-centred (what engineers call ECEF). Reached from TEME
        by a single rotation through GMST, so it is strictly PEF; see the module
        docstring for the polar-motion error that approximation costs.
    ENU
        Local topocentric East-North-Up at a ground station, defined against the
        WGS-84 geodetic normal. The frame look angles are measured in.
    GCRF
        Geocentric Celestial Reference Frame, the modern inertial standard.
        **Declared but not implemented**: no function here produces or consumes
        it. It exists so that the day a full reduction is added, every array
        already carries a tag and the conversion sites are findable.
    """

    TEME = "teme"
    ITRF = "itrf"
    ENU = "enu"
    GCRF = "gcrf"


# --------------------------------------------------------------------------- #
# Input validation
#
# Every public function funnels its arguments through these. A physics function
# that trusts its inputs pushes the error to wherever the nan finally surfaces,
# which is never where the mistake was made.
# --------------------------------------------------------------------------- #


def _broadcast_against(name: str, values: FloatArray, n: int) -> FloatArray:
    """Return ``values`` broadcast to length ``n``.

    Station coordinates are parameters, not time series, so a fixed site may be
    given as a scalar while the satellite positions span the whole grid.

    Parameters
    ----------
    name : str
        Argument name, used in the error message.
    values : FloatArray
        Validated 1-D array, of length 1 or ``n``.
    n : int
        Target length.

    Returns
    -------
    FloatArray
        An array of length ``n``.

    Raises
    ------
    DomainError
        If the length is neither 1 nor ``n``.
    """
    if values.size == n:
        return values
    if values.size == 1:
        return np.broadcast_to(values, (n,))
    raise DomainError(
        f"{name} has length {values.size}, which is neither 1 nor {n}. "
        f"Give one value per sample, or a single value for a fixed site."
    )


# --------------------------------------------------------------------------- #
# Calendar <-> Julian date
#
# Not a unit conversion but an astronomical algorithm, which is why it lives
# here and not in `scenario/io.py`. That module parses ISO-8601 strings into
# calendar fields; turning those fields into a Julian date is this module's job,
# and it has published test values of its own.
# --------------------------------------------------------------------------- #
def calendar_to_jd(
    year: int,
    month: int,
    day: int,
    hour: int = 0,
    minute: int = 0,
    second: float = 0.0,
) -> float:
    """Convert a UTC calendar date and time to a Julian date.

    Parameters
    ----------
    year : int
        Gregorian year. Restricted to ``[1900, 2100]`` as a plausibility check —
        see Notes; the algorithm itself has no such limit.
    month : int
        Month, ``1``-``12``.
    day : int
        Day of month, validated against the month's real length including leap
        years.
    hour : int, optional
        Hour, ``0``-``23``.
    minute : int, optional
        Minute, ``0``-``59``.
    second : float, optional
        Second, ``[0, 61)``. The upper bound admits a leap second; QuOSS does
        not model leap seconds, so a value at or above 60 is carried through
        arithmetically rather than being interpreted.

    Returns
    -------
    float
        Julian date in days, UTC.

    Raises
    ------
    DomainError
        If any field is out of range, or the date does not exist.

    Notes
    -----
    Uses the Fliegel-Van Flandern integer expression, exact for every Gregorian
    date, including century years. The year range is a plausibility check on the
    input, not a limitation of the formula; see the comment above ``_YEAR_MIN``
    for why the alternative expression in [1]_ Algorithm 14 is not used.

    Examples
    --------
    The J2000.0 epoch, 2000 January 1 at 12:00 UTC:

    >>> calendar_to_jd(2000, 1, 1, 12, 0, 0.0)
    2451545.0

    The Unix epoch:

    >>> calendar_to_jd(1970, 1, 1)
    2440587.5

    1900 and 2100 are *not* leap years, which is where the Julian leap rule fails:

    >>> calendar_to_jd(2100, 3, 1) - calendar_to_jd(2100, 2, 28)
    1.0
    """
    if not _YEAR_MIN <= year <= _YEAR_MAX:
        raise DomainError(
            f"year must be in [{_YEAR_MIN}, {_YEAR_MAX}], got {year}. That range is a "
            f"plausibility check on scenario input, not a limit of the conversion."
        )
    if not 1 <= month <= 12:
        raise DomainError(f"month must be in [1, 12], got {month}.")
    days_in_month = calendar.monthrange(year, month)[1]
    if not 1 <= day <= days_in_month:
        raise DomainError(f"day must be in [1, {days_in_month}] for {year}-{month:02d}, got {day}.")
    if not 0 <= hour <= 23:
        raise DomainError(f"hour must be in [0, 23], got {hour}.")
    if not 0 <= minute <= 59:
        raise DomainError(f"minute must be in [0, 59], got {minute}.")
    if not 0.0 <= second < 61.0:
        raise DomainError(f"second must be in [0, 61), got {second}.")

    # Fliegel-Van Flandern: `jdn` is the Julian day *number*, which starts at
    # noon, so subtracting half a day gives the JD at midnight UTC.
    shift = (14 - month) // 12
    y = year + 4800 - shift
    m = month + 12 * shift - 3
    jdn = day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32_045
    whole_days = jdn - 0.5
    day_fraction = (
        hour * _SECONDS_PER_HOUR + minute * _SECONDS_PER_MINUTE + second
    ) / SECONDS_PER_DAY
    return float(whole_days + day_fraction)


def jd_to_calendar(jd: float) -> tuple[int, int, int, int, int, float]:
    """Convert a Julian date to UTC calendar fields.

    The inverse of :func:`calendar_to_jd`, for labelling axes and reporting
    provenance. Nothing in the physics consumes calendar fields.

    Parameters
    ----------
    jd : float
        Julian date in days, UTC. Must fall inside the 1900-2100 window that
        :func:`calendar_to_jd` accepts.

    Returns
    -------
    tuple of (int, int, int, int, int, float)
        ``(year, month, day, hour, minute, second)``. The seconds field is a
        float and is *not* rounded, so a round trip through
        :func:`calendar_to_jd` is exact to floating-point resolution.

    Raises
    ------
    DomainError
        If ``jd`` is not finite, or falls outside 1900-2100.

    Notes
    -----
    Meeus [5]_, Chapter 7, restricted to Gregorian dates.

    Examples
    --------
    >>> jd_to_calendar(2451545.0)
    (2000, 1, 1, 12, 0, 0.0)
    >>> jd_to_calendar(2440587.5)
    (1970, 1, 1, 0, 0, 0.0)
    """
    if not np.isfinite(jd):
        raise DomainError(f"jd must be finite, got {jd!r}.")
    jd_min = calendar_to_jd(_YEAR_MIN, 1, 1)
    jd_max = calendar_to_jd(_YEAR_MAX, 12, 31, 23, 59, 60.0)
    if not jd_min <= jd <= jd_max:
        raise DomainError(
            f"jd={jd!r} falls outside {_YEAR_MIN}-{_YEAR_MAX} "
            f"(JD {jd_min} to {jd_max}), the validity window of the conversion."
        )

    shifted = jd + 0.5
    z = int(np.floor(shifted))
    fraction = shifted - z

    alpha = int((z - 1_867_216.25) // 36_524.25)
    a = z + 1 + alpha - alpha // 4
    b = a + 1524
    c = int((b - 122.1) // 365.25)
    d = int(365.25 * c)
    e = int((b - d) // 30.6001)

    day = b - d - int(30.6001 * e)
    month = e - 1 if e < 14 else e - 13
    year = c - 4716 if month > 2 else c - 4715

    seconds_of_day = fraction * SECONDS_PER_DAY
    hour = int(seconds_of_day // _SECONDS_PER_HOUR)
    remainder = seconds_of_day - hour * _SECONDS_PER_HOUR
    minute = int(remainder // _SECONDS_PER_MINUTE)
    second = remainder - minute * _SECONDS_PER_MINUTE
    return year, month, day, hour, minute, second


# --------------------------------------------------------------------------- #
# Sidereal time
# --------------------------------------------------------------------------- #
def gmst_rad(jd_utc: FloatArray) -> FloatArray:
    """Greenwich Mean Sidereal Time, in radians, from a Julian date.

    The angle between the Greenwich meridian and the mean equinox of date: the
    single rotation that carries TEME into the Earth-fixed frame.

    Parameters
    ----------
    jd_utc : FloatArray
        Julian dates in days. GMST is strictly a function of UT1; QuOSS passes
        UTC and absorbs DUT1 into the error budget stated in the module
        docstring (at most 0.9 s of Earth rotation, ~415 m on the ground).

    Returns
    -------
    FloatArray
        GMST in radians, wrapped to ``[0, 2 pi)``, same shape as the input.

    Raises
    ------
    DomainError
        If the input is not a finite 1-D array of Julian dates.

    Notes
    -----
    The IAU 1982 series [2]_, as given by Vallado [1]_ Eq. 3-47, evaluated in
    seconds of time and converted to radians as a fraction of a full turn.
    Superseded for arcsecond work by the IAU 2006 expression, which differs from
    this one by under 0.1 arcsec over QuOSS's epoch range — a difference the
    reference-data suite measures rather than assumes.

    Examples
    --------
    GMST advances by slightly more than a full turn per solar day, because the
    Earth also moves along its orbit:

    >>> import numpy as np
    >>> theta = gmst_rad(np.array([2451545.0, 2451546.0]))
    >>> float(np.round(theta[0], 9))
    4.894961213
    >>> daily_advance = float(theta[1] - theta[0] + 2 * np.pi)
    >>> float(np.round(daily_advance / (2 * np.pi), 6))
    1.002738
    """
    jd = as_1d("jd_utc", jd_utc)
    t = (jd - JD_J2000) / _JULIAN_CENTURY_DAYS
    seconds = _GMST82_C0 + t * (_GMST82_C1 + t * (_GMST82_C2 + t * _GMST82_C3))
    turns = seconds / SECONDS_PER_DAY
    return np.asarray((turns % 1.0) * _TWO_PI, dtype=np.float64)


# --------------------------------------------------------------------------- #
# TEME <-> ITRF
# --------------------------------------------------------------------------- #
def _rotate_about_pole(vectors: Vec3Array, theta_rad: FloatArray) -> Vec3Array:
    """Apply the rotation ``ROT3(theta)`` to a stack of vectors.

    Parameters
    ----------
    vectors : Vec3Array
        Stack of shape ``(n, 3)``.
    theta_rad : FloatArray
        Rotation angle per sample, length ``n``. A positive angle rotates the
        *frame* about ``+z`` by ``theta``, i.e. it rotates the components of a
        fixed vector by ``-theta``.

    Returns
    -------
    Vec3Array
        The rotated stack.
    """
    cos_t = np.cos(theta_rad)
    sin_t = np.sin(theta_rad)
    out = np.empty_like(vectors)
    out[:, 0] = cos_t * vectors[:, 0] + sin_t * vectors[:, 1]
    out[:, 1] = -sin_t * vectors[:, 0] + cos_t * vectors[:, 1]
    out[:, 2] = vectors[:, 2]
    return out


def teme_to_itrf(r_teme_km: Vec3Array, theta_gmst_rad: FloatArray) -> Vec3Array:
    """Rotate positions from TEME to the Earth-fixed frame.

    Parameters
    ----------
    r_teme_km : Vec3Array
        Positions in TEME, km, shape ``(n, 3)``.
    theta_gmst_rad : FloatArray
        GMST per sample, radians, from :func:`gmst_rad`. Length 1 or ``n``.

    Returns
    -------
    Vec3Array
        Positions in ITRF (treated as ECEF), km, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If shapes are invalid or do not broadcast.

    Notes
    -----
    A single rotation about the pole [3]_. The result is strictly PEF; polar
    motion is not applied. See the module docstring for what that costs.

    Examples
    --------
    At GMST zero the two frames coincide:

    >>> import numpy as np
    >>> teme_to_itrf(np.array([[7000.0, 0.0, 0.0]]), np.array([0.0]))
    array([[7000.,    0.,    0.]])

    After a quarter turn, a vector along TEME +x lies along ITRF -y:

    >>> r = teme_to_itrf(np.array([[7000.0, 0.0, 0.0]]), np.array([np.pi / 2]))
    >>> np.round(r, 9)
    array([[    0., -7000.,     0.]])
    """
    r_teme = as_vec3("r_teme_km", r_teme_km)
    theta = _broadcast_against(
        "theta_gmst_rad", as_1d("theta_gmst_rad", theta_gmst_rad), r_teme.shape[0]
    )
    return _rotate_about_pole(r_teme, theta)


def itrf_to_teme(r_itrf_km: Vec3Array, theta_gmst_rad: FloatArray) -> Vec3Array:
    """Rotate positions from the Earth-fixed frame to TEME.

    The exact inverse of :func:`teme_to_itrf`.

    Parameters
    ----------
    r_itrf_km : Vec3Array
        Positions in ITRF, km, shape ``(n, 3)``.
    theta_gmst_rad : FloatArray
        GMST per sample, radians. Length 1 or ``n``.

    Returns
    -------
    Vec3Array
        Positions in TEME, km, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If shapes are invalid or do not broadcast.

    Examples
    --------
    >>> import numpy as np
    >>> r_itrf = np.array([[0.0, -7000.0, 0.0]])
    >>> np.round(itrf_to_teme(r_itrf, np.array([np.pi / 2])), 9) + 0.0  # kill -0.0
    array([[7000.,    0.,    0.]])
    """
    r_itrf = as_vec3("r_itrf_km", r_itrf_km)
    theta = _broadcast_against(
        "theta_gmst_rad", as_1d("theta_gmst_rad", theta_gmst_rad), r_itrf.shape[0]
    )
    return _rotate_about_pole(r_itrf, -theta)


def teme_to_itrf_state(
    r_teme_km: Vec3Array,
    v_teme_km_s: Vec3Array,
    theta_gmst_rad: FloatArray,
) -> tuple[Vec3Array, Vec3Array]:
    """Rotate a position *and velocity* pair from TEME to the Earth-fixed frame.

    Velocity needs its own function because a rotating frame is not an inertial
    one: the Earth's rotation contributes a term that a bare rotation matrix does
    not capture. Omitting it is a 0.46 km/s error at the equator, which would
    corrupt every Doppler shift in the simulation.

    Parameters
    ----------
    r_teme_km : Vec3Array
        Positions in TEME, km, shape ``(n, 3)``.
    v_teme_km_s : Vec3Array
        Velocities in TEME, km/s, same shape.
    theta_gmst_rad : FloatArray
        GMST per sample, radians. Length 1 or ``n``.

    Returns
    -------
    r_itrf_km : Vec3Array
        Positions in ITRF, km.
    v_itrf_km_s : Vec3Array
        Velocities in ITRF, km/s, including the ``-omega x r`` term.

    Raises
    ------
    DomainError
        If shapes are invalid, do not match, or do not broadcast.

    Notes
    -----
    ``v_ITRF = ROT3(theta) v_TEME - omega x r_ITRF`` with
    ``omega = (0, 0, EARTH_ROTATION_RAD_S)``.

    Examples
    --------
    A point fixed on the equator has zero velocity in ITRF, and in TEME moves at
    the Earth's surface speed:

    >>> import numpy as np
    >>> from quoss.core.constants import EARTH_ROTATION_RAD_S
    >>> r = np.array([[6378.137, 0.0, 0.0]])
    >>> v = np.array([[0.0, 6378.137 * EARTH_ROTATION_RAD_S, 0.0]])
    >>> _, v_itrf = teme_to_itrf_state(r, v, np.array([0.0]))
    >>> np.round(v_itrf, 12)
    array([[0., 0., 0.]])
    """
    r_teme = as_vec3("r_teme_km", r_teme_km)
    v_teme = as_vec3("v_teme_km_s", v_teme_km_s)
    if r_teme.shape != v_teme.shape:
        raise DomainError(
            f"r_teme_km has shape {r_teme.shape} but v_teme_km_s has {v_teme.shape}; "
            f"a state pair must be sampled on the same axis."
        )
    theta = _broadcast_against(
        "theta_gmst_rad", as_1d("theta_gmst_rad", theta_gmst_rad), r_teme.shape[0]
    )

    r_itrf = _rotate_about_pole(r_teme, theta)
    v_rotated = _rotate_about_pole(v_teme, theta)
    v_itrf = np.empty_like(v_rotated)
    v_itrf[:, 0] = v_rotated[:, 0] + EARTH_ROTATION_RAD_S * r_itrf[:, 1]
    v_itrf[:, 1] = v_rotated[:, 1] - EARTH_ROTATION_RAD_S * r_itrf[:, 0]
    v_itrf[:, 2] = v_rotated[:, 2]
    return r_itrf, v_itrf


def itrf_to_teme_state(
    r_itrf_km: Vec3Array,
    v_itrf_km_s: Vec3Array,
    theta_gmst_rad: FloatArray,
) -> tuple[Vec3Array, Vec3Array]:
    """Rotate a position and velocity pair from the Earth-fixed frame to TEME.

    The exact inverse of :func:`teme_to_itrf_state`.

    Parameters
    ----------
    r_itrf_km : Vec3Array
        Positions in ITRF, km, shape ``(n, 3)``.
    v_itrf_km_s : Vec3Array
        Velocities in ITRF, km/s, same shape.
    theta_gmst_rad : FloatArray
        GMST per sample, radians. Length 1 or ``n``.

    Returns
    -------
    r_teme_km : Vec3Array
        Positions in TEME, km.
    v_teme_km_s : Vec3Array
        Velocities in TEME, km/s.

    Raises
    ------
    DomainError
        If shapes are invalid, do not match, or do not broadcast.

    Examples
    --------
    A ground station is at rest in ITRF and carries the Earth's rotation in TEME:

    >>> import numpy as np
    >>> from quoss.core.constants import EARTH_ROTATION_RAD_S
    >>> r = np.array([[6378.137, 0.0, 0.0]])
    >>> _, v_teme = itrf_to_teme_state(r, np.zeros((1, 3)), np.array([0.0]))
    >>> float(np.round(v_teme[0, 1] / (6378.137 * EARTH_ROTATION_RAD_S), 12))
    1.0
    """
    r_itrf = as_vec3("r_itrf_km", r_itrf_km)
    v_itrf = as_vec3("v_itrf_km_s", v_itrf_km_s)
    if r_itrf.shape != v_itrf.shape:
        raise DomainError(
            f"r_itrf_km has shape {r_itrf.shape} but v_itrf_km_s has {v_itrf.shape}; "
            f"a state pair must be sampled on the same axis."
        )
    theta = _broadcast_against(
        "theta_gmst_rad", as_1d("theta_gmst_rad", theta_gmst_rad), r_itrf.shape[0]
    )

    v_inertial_in_itrf = np.empty_like(v_itrf)
    v_inertial_in_itrf[:, 0] = v_itrf[:, 0] - EARTH_ROTATION_RAD_S * r_itrf[:, 1]
    v_inertial_in_itrf[:, 1] = v_itrf[:, 1] + EARTH_ROTATION_RAD_S * r_itrf[:, 0]
    v_inertial_in_itrf[:, 2] = v_itrf[:, 2]

    r_teme = _rotate_about_pole(r_itrf, -theta)
    v_teme = _rotate_about_pole(v_inertial_in_itrf, -theta)
    return r_teme, v_teme


# --------------------------------------------------------------------------- #
# Geodetic <-> ITRF
#
# On the WGS-84 ellipsoid, and geodetic throughout. Geocentric latitude is a
# different quantity, larger by up to 0.19 deg, and a "radius plus altitude"
# height is wrong by up to 21 km at the pole. Both mistakes are present in the
# code this project replaces; both put a ground station in the wrong place and
# bias every elevation angle computed from it.
# --------------------------------------------------------------------------- #
def geodetic_to_itrf(
    latitude_rad: FloatLike,
    longitude_rad: FloatLike,
    altitude_km: FloatLike,
) -> Vec3Array:
    """Convert WGS-84 geodetic coordinates to Earth-fixed Cartesian ones.

    Parameters
    ----------
    latitude_rad : float or FloatArray
        Geodetic latitude, radians, in ``[-pi/2, pi/2]``.
    longitude_rad : float or FloatArray
        Longitude, radians, positive east. Not range-checked: any branch is a
        valid angle.
    altitude_km : float or FloatArray
        Height above the WGS-84 ellipsoid, km. Positive up.

    Returns
    -------
    Vec3Array
        Positions in ITRF, km, shape ``(n, 3)`` where ``n`` is the broadcast
        length of the three inputs. Always 2-D, so a single site is ``(1, 3)``.

    Raises
    ------
    DomainError
        If latitude is outside ``[-pi/2, pi/2]``, or the inputs do not broadcast
        to a common length.

    Notes
    -----
    Vallado [1]_ Section 3.7. ``N`` is the radius of curvature in the prime
    vertical, ``N = a / sqrt(1 - e^2 sin^2 phi)``.

    Examples
    --------
    A point on the equator at zero longitude sits at the semi-major axis:

    >>> import numpy as np
    >>> np.round(geodetic_to_itrf(0.0, 0.0, 0.0), 6)
    array([[6378.137,    0.   ,    0.   ]])

    At the pole the radius is the semi-minor axis, ~21 km smaller — the error a
    spherical Earth would make:

    >>> r = geodetic_to_itrf(np.pi / 2, 0.0, 0.0)
    >>> float(np.round(r[0, 2], 6))
    6356.752314
    """
    lat = as_1d("latitude_rad", latitude_rad)
    lon = as_1d("longitude_rad", longitude_rad)
    alt = as_1d("altitude_km", altitude_km)
    if np.any(np.abs(lat) > np.pi / 2 + _GEODETIC_TOLERANCE_RAD):
        raise DomainError(
            "latitude_rad must lie in [-pi/2, pi/2]. A value outside it is almost "
            "always degrees that were never converted."
        )

    n = max(lat.size, lon.size, alt.size)
    lat = _broadcast_against("latitude_rad", lat, n)
    lon = _broadcast_against("longitude_rad", lon, n)
    alt = _broadcast_against("altitude_km", alt, n)

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    curvature_km = WGS84_RADIUS_EQUATORIAL_KM / np.sqrt(
        1.0 - WGS84_ECCENTRICITY_SQ * sin_lat * sin_lat
    )

    out = np.empty((n, 3), dtype=np.float64)
    out[:, 0] = (curvature_km + alt) * cos_lat * np.cos(lon)
    out[:, 1] = (curvature_km + alt) * cos_lat * np.sin(lon)
    out[:, 2] = (curvature_km * (1.0 - WGS84_ECCENTRICITY_SQ) + alt) * sin_lat
    return out


def itrf_to_geodetic(r_itrf_km: Vec3Array) -> tuple[FloatArray, FloatArray, FloatArray]:
    """Convert Earth-fixed Cartesian coordinates to WGS-84 geodetic ones.

    The inverse of :func:`geodetic_to_itrf`, and the function a ground track is
    made of.

    Parameters
    ----------
    r_itrf_km : Vec3Array
        Positions in ITRF, km, shape ``(n, 3)``.

    Returns
    -------
    latitude_rad : FloatArray
        Geodetic latitude, radians, in ``[-pi/2, pi/2]``.
    longitude_rad : FloatArray
        Longitude, radians, in ``(-pi, pi]``, positive east.
    altitude_km : FloatArray
        Height above the WGS-84 ellipsoid, km.

    Raises
    ------
    DomainError
        If the shape is invalid, or any position is at the Earth's centre where
        latitude and longitude are undefined.
    ConvergenceError
        If the latitude iteration fails to converge, which for any position at
        or above the surface it does not.

    Notes
    -----
    Fixed-point iteration on ``phi = atan2(z + N e^2 sin phi, p)``, then a
    height expression valid at the poles: ``h = p cos phi + z sin phi -
    a sqrt(1 - e^2 sin^2 phi)``. The commonly seen ``h = p / cos phi - N`` is
    algebraically equivalent and numerically useless within a degree of the pole.

    Examples
    --------
    >>> import numpy as np
    >>> lat, lon, alt = itrf_to_geodetic(np.array([[6378.137 + 500.0, 0.0, 0.0]]))
    >>> float(np.round(alt[0], 9))
    500.0
    >>> bool(np.allclose([lat[0], lon[0]], 0.0))
    True
    """
    r = as_vec3("r_itrf_km", r_itrf_km)
    x, y, z = r[:, 0], r[:, 1], r[:, 2]
    if np.any(np.hypot(np.hypot(x, y), z) == 0.0):
        raise DomainError(
            "itrf_to_geodetic received a position at the Earth's centre, where "
            "latitude and longitude are undefined."
        )

    p = np.hypot(x, y)
    lon = np.arctan2(y, x)
    lat = np.arctan2(z, p * (1.0 - WGS84_ECCENTRICITY_SQ))

    # Initialised so that the failure branch is well defined even if the iteration
    # cap were ever set to zero. Reporting the last shift is the whole value of
    # that branch, and an unbound name there would raise NameError instead.
    shift = float("inf")
    for _ in range(_GEODETIC_MAX_ITER):
        sin_lat = np.sin(lat)
        curvature_km = WGS84_RADIUS_EQUATORIAL_KM / np.sqrt(
            1.0 - WGS84_ECCENTRICITY_SQ * sin_lat * sin_lat
        )
        lat_next = np.arctan2(z + curvature_km * WGS84_ECCENTRICITY_SQ * sin_lat, p)
        shift = float(np.max(np.abs(lat_next - lat)))
        lat = lat_next
        if shift < _GEODETIC_TOLERANCE_RAD:
            break
    else:
        raise ConvergenceError(
            f"Geodetic latitude did not converge in {_GEODETIC_MAX_ITER} iterations "
            f"(last shift {shift:.3e} rad). Check that the input is a plausible "
            f"Earth-fixed position in km."
        )

    sin_lat = np.sin(lat)
    cos_lat = np.cos(lat)
    alt = (
        p * cos_lat
        + z * sin_lat
        - WGS84_RADIUS_EQUATORIAL_KM * np.sqrt(1.0 - WGS84_ECCENTRICITY_SQ * sin_lat * sin_lat)
    )
    return (
        np.asarray(lat, dtype=np.float64),
        np.asarray(lon, dtype=np.float64),
        np.asarray(alt, dtype=np.float64),
    )


# --------------------------------------------------------------------------- #
# Local topocentric frame
# --------------------------------------------------------------------------- #
def enu_from_itrf(
    vector_itrf_km: Vec3Array,
    latitude_rad: FloatLike,
    longitude_rad: FloatLike,
) -> Vec3Array:
    """Express an Earth-fixed *vector* in a station's East-North-Up frame.

    Takes a vector, not a position: to get look angles, pass the difference
    ``r_satellite_itrf - r_station_itrf``. Keeping the subtraction at the call
    site is what stops a position from being rotated as though it were a
    topocentric offset.

    The basis is built on the WGS-84 geodetic normal, so "up" is the local
    vertical a levelled telescope sees, not the direction to the Earth's centre.
    The two differ by up to 0.19 deg.

    Parameters
    ----------
    vector_itrf_km : Vec3Array
        Vectors in ITRF, km, shape ``(n, 3)``.
    latitude_rad : float or FloatArray
        Station geodetic latitude, radians. Scalar for a fixed site, or one
        value per sample.
    longitude_rad : float or FloatArray
        Station longitude, radians, positive east.

    Returns
    -------
    Vec3Array
        The same vectors in ENU, km, shape ``(n, 3)``: columns are east, north
        and up.

    Raises
    ------
    DomainError
        If shapes are invalid or do not broadcast, or latitude is out of range.

    Examples
    --------
    At a station on the equator at zero longitude, ITRF ``+x`` is straight up and
    ITRF ``+z`` is due north:

    >>> import numpy as np
    >>> v = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, 1.0, 0.0]])
    >>> np.round(enu_from_itrf(v, 0.0, 0.0), 12)
    array([[0., 0., 1.],
           [0., 1., 0.],
           [1., 0., 0.]])
    """
    vec = as_vec3("vector_itrf_km", vector_itrf_km)
    n = vec.shape[0]
    lat = as_1d("latitude_rad", latitude_rad)
    lon = as_1d("longitude_rad", longitude_rad)
    if np.any(np.abs(lat) > np.pi / 2 + _GEODETIC_TOLERANCE_RAD):
        raise DomainError("latitude_rad must lie in [-pi/2, pi/2].")
    lat = _broadcast_against("latitude_rad", lat, n)
    lon = _broadcast_against("longitude_rad", lon, n)

    sin_lat, cos_lat = np.sin(lat), np.cos(lat)
    sin_lon, cos_lon = np.sin(lon), np.cos(lon)

    out = np.empty_like(vec)
    out[:, 0] = -sin_lon * vec[:, 0] + cos_lon * vec[:, 1]
    out[:, 1] = -sin_lat * cos_lon * vec[:, 0] - sin_lat * sin_lon * vec[:, 1] + cos_lat * vec[:, 2]
    out[:, 2] = cos_lat * cos_lon * vec[:, 0] + cos_lat * sin_lon * vec[:, 1] + sin_lat * vec[:, 2]
    return out
