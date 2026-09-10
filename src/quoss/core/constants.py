"""Physical, geodetic and time constants, each with its source.

Every value here is either **exact by definition** (the 2019 SI base units) or
quoted from a named reference model. Nothing is rounded for convenience and
nothing is derived silently: quantities that follow from others are marked as
derived and the relation is stated, so a reader can check them.

Unit suffixes follow the project convention (see :mod:`quoss.core.units`):
orbital distances in ``_km``, everything else strict SI.

Two Earth gravity models, and the distinction matters
-----------------------------------------------------
``EGM96_*`` is the accurate modern model, used for Keplerian propagation and
perturbation analysis. ``WGS72_*`` is the *older, less accurate* model that
SGP4 uses internally — and TLEs are **fitted** to it. Propagating a TLE with
EGM96 constants does not make it more accurate; it makes it inconsistent with
the data reduction that produced the TLE, introducing a systematic error of a
few hundred metres in position. Therefore: ``orbits/tle.py`` uses ``WGS72_*``,
everything else uses ``EGM96_*``.

References
----------
.. [1] BIPM, *The International System of Units (SI)*, 9th ed., 2019.
       Defining constants are exact.
.. [2] NIMA TR8350.2, *Department of Defense World Geodetic System 1984*,
       3rd ed., 2000. Ellipsoid parameters.
.. [3] Lemoine et al., *The Development of the Joint NASA GSFC and NIMA
       Geopotential Model EGM96*, NASA/TP-1998-206861, 1998. Zonal harmonics.
.. [4] Hoots & Roehrich, *Models for Propagation of NORAD Element Sets*,
       Spacetrack Report No. 3, 1980, rev. Vallado et al. 2006. WGS-72 set.
.. [5] Petit & Luzum (eds.), *IERS Conventions (2010)*, IERS TN 36.
       Earth rotation rate.
.. [6] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed., 2013.
       Time scales and Julian date conventions.
"""

from __future__ import annotations

from typing import Final

__all__ = [
    "BOLTZMANN_J_K",
    "EARTH_ROTATION_RAD_S",
    "EGM96_J2",
    "EGM96_J3",
    "EGM96_J4",
    "EGM96_MU_KM3_S2",
    "EGM96_RADIUS_EQUATORIAL_KM",
    "ELEMENTARY_CHARGE_C",
    "JD_J2000",
    "JD_UNIX_EPOCH",
    "MEAN_SIDEREAL_DAY_S",
    "MJD_OFFSET_JD",
    "PLANCK_J_S",
    "SECONDS_PER_DAY",
    "SPEED_OF_LIGHT_M_S",
    "STEFAN_BOLTZMANN_W_M2_K4",
    "TROPICAL_YEAR_S",
    "WGS72_J2",
    "WGS72_J3",
    "WGS72_J4",
    "WGS72_MU_KM3_S2",
    "WGS72_RADIUS_EQUATORIAL_KM",
    "WGS84_ECCENTRICITY",
    "WGS84_ECCENTRICITY_SQ",
    "WGS84_FLATTENING",
    "WGS84_RADIUS_EQUATORIAL_KM",
    "WGS84_RADIUS_POLAR_KM",
]

# --------------------------------------------------------------------------- #
# Fundamental physical constants — exact by the 2019 SI definitions [1]
#
# These four fix the metre, second, kilogram and ampere. They cannot be revised
# by future measurement, which is why they are written out rather than imported
# from `scipy.constants`: a CODATA update in a dependency must never change a
# published QuOSS number.
# --------------------------------------------------------------------------- #
SPEED_OF_LIGHT_M_S: Final = 299_792_458.0
"""Speed of light in vacuum, m/s. Exact [1]."""

PLANCK_J_S: Final = 6.626_070_15e-34
"""Planck constant, J.s. Exact [1]. Photon energy: E = h c / lambda."""

BOLTZMANN_J_K: Final = 1.380_649e-23
"""Boltzmann constant, J/K. Exact [1]. Thermal noise, blackbody radiance."""

ELEMENTARY_CHARGE_C: Final = 1.602_176_634e-19
"""Elementary charge, C. Exact [1]. Detector dark current conversion."""

STEFAN_BOLTZMANN_W_M2_K4: Final = 5.670_374_419e-8
"""Stefan-Boltzmann constant, W/(m^2 K^4). Derived from the exact constants [1].

sigma = 2 pi^5 k_B^4 / (15 h^3 c^2). Used for background thermal radiance.
"""

# --------------------------------------------------------------------------- #
# Earth shape — WGS-84 ellipsoid [2]
#
# Geodetic conversions (ECEF <-> lat/lon/alt) and ground-station positions.
# The semi-major axis and flattening are the defining parameters; the polar
# radius and eccentricities are derived from them.
# --------------------------------------------------------------------------- #
WGS84_RADIUS_EQUATORIAL_KM: Final = 6378.137
"""WGS-84 semi-major axis a, km. Defining parameter [2]."""

WGS84_FLATTENING: Final = 1.0 / 298.257_223_563
"""WGS-84 flattening f = (a - b) / a, dimensionless. Defining parameter [2]."""

WGS84_RADIUS_POLAR_KM: Final = WGS84_RADIUS_EQUATORIAL_KM * (1.0 - WGS84_FLATTENING)
"""WGS-84 semi-minor axis b = a (1 - f), km. **Derived** [2]. ~6356.752314 km."""

WGS84_ECCENTRICITY_SQ: Final = WGS84_FLATTENING * (2.0 - WGS84_FLATTENING)
"""First eccentricity squared e^2 = f (2 - f), dimensionless. **Derived** [2].

Appears directly in the geodetic-to-ECEF prime vertical radius of curvature.
"""

WGS84_ECCENTRICITY: Final = WGS84_ECCENTRICITY_SQ**0.5
"""First eccentricity e, dimensionless. **Derived** [2]. ~0.0818191908."""

# --------------------------------------------------------------------------- #
# Earth gravity — EGM96 [3]. The default for Keplerian and perturbed propagation.
# --------------------------------------------------------------------------- #
EGM96_MU_KM3_S2: Final = 398_600.441_8
"""Earth gravitational parameter GM, km^3/s^2. EGM96 [3].

Sets the orbital period: T = 2 pi sqrt(a^3 / mu).
"""

EGM96_RADIUS_EQUATORIAL_KM: Final = 6378.136_3
"""Reference equatorial radius of the EGM96 expansion, km [3].

**Not** interchangeable with :data:`WGS84_RADIUS_EQUATORIAL_KM`, even though the
two differ by only 0.7 m. A zonal harmonic is defined *with respect to* the
radius its expansion used: every J_n below multiplies ``(R / r)^n``, so mixing
the WGS-84 radius into an EGM96 harmonic changes the coefficient's meaning. The
resulting error is 2.2e-7 relative in the J2 term — negligible against that
model's own truncation, and free to avoid.

Geodesy uses WGS-84, gravity uses EGM96, SGP4 uses WGS-72. Three radii, three
purposes, and the suffix says which.
"""

EGM96_J2: Final = 1.082_626_68e-3
"""Second zonal harmonic J2, dimensionless. EGM96 [3].

Dominant perturbation in LEO: drives nodal regression and apsidal precession,
and is what makes sun-synchronous orbits possible.
"""

EGM96_J3: Final = -2.532_656_49e-6
"""Third zonal harmonic J3, dimensionless. EGM96 [3]. Pear-shape asymmetry."""

EGM96_J4: Final = -1.619_621_59e-6
"""Fourth zonal harmonic J4, dimensionless. EGM96 [3]."""

# --------------------------------------------------------------------------- #
# Earth gravity — WGS-72 [4]. **Only** for SGP4/TLE propagation.
#
# Less accurate than EGM96, and deliberately so: TLEs are fitted with these
# values, so consistency beats accuracy here. See the module docstring.
# --------------------------------------------------------------------------- #
WGS72_RADIUS_EQUATORIAL_KM: Final = 6378.135
"""SGP4 Earth equatorial radius, km. WGS-72 [4]. Note: not the WGS-84 value."""

WGS72_MU_KM3_S2: Final = 398_600.8
"""SGP4 Earth gravitational parameter GM, km^3/s^2. WGS-72 [4]."""

WGS72_J2: Final = 1.082_616e-3
"""SGP4 second zonal harmonic J2, dimensionless. WGS-72 [4]."""

WGS72_J3: Final = -2.538_81e-6
"""SGP4 third zonal harmonic J3, dimensionless. WGS-72 [4]."""

WGS72_J4: Final = -1.655_97e-6
"""SGP4 fourth zonal harmonic J4, dimensionless. WGS-72 [4]."""

# --------------------------------------------------------------------------- #
# Earth rotation [5]
# --------------------------------------------------------------------------- #
EARTH_ROTATION_RAD_S: Final = 7.292_115e-5
"""Earth nominal mean angular velocity omega, rad/s. IERS 2010 [5].

Used for the ECI <-> ECEF rotation and for the ground-station velocity that
contributes to Doppler.
"""

MEAN_SIDEREAL_DAY_S: Final = 86_164.090_530_833_0
"""Mean sidereal day, s. Quoted directly [5, 6]; **not** derived from omega.

Equal to 23h 56m 04.0905s: one rotation relative to the *precessing* mean
equinox. Used for GMST and for repeat-ground-track design.

Not the same quantity as ``2 pi / EARTH_ROTATION_RAD_S``, which evaluates to
86164.1006 s — about 10 ms longer. The two differ for two reasons: that ratio is
a rotation relative to an inertial direction (the stellar day, 86164.0989 s)
rather than to the moving equinox, and omega above is quoted to only seven
significant figures. Both values are correct for their own purpose, and neither
should be computed from the other. Deriving one from the other is a ~1.2e-7
relative error — negligible over one pass, but it accumulates to a visible
along-track offset over a multi-day repeat-track analysis.
"""

# --------------------------------------------------------------------------- #
# Time scales [6]
#
# QuOSS represents absolute time as a Julian date (float64 days) and simulation
# time as seconds elapsed from a stated epoch. See `quoss.core.types.TimeGrid`,
# which pairs the two so no module has to invent its own epoch.
# --------------------------------------------------------------------------- #
SECONDS_PER_DAY: Final = 86_400.0
"""Seconds in a Julian day, s. Exact by definition [6]."""

JD_J2000: Final = 2_451_545.0
"""Julian date of the J2000.0 epoch (2000-01-01 12:00:00 TT), days [6].

Reference epoch for GMST and for the ECI frame.
"""

MJD_OFFSET_JD: Final = 2_400_000.5
"""Offset between Julian and Modified Julian date, days: MJD = JD - this [6]."""

JD_UNIX_EPOCH: Final = 2_440_587.5
"""Julian date of the Unix epoch (1970-01-01 00:00:00 UTC), days [6]."""

TROPICAL_YEAR_S: Final = 365.242_189_7 * SECONDS_PER_DAY
"""Mean tropical year, s: 365.2421897 days, quoted directly [6].

The tropical year is the time the **mean Sun** — a fictitious sun that moves at
the ecliptic's average rate, used because the real Sun's apparent motion is not
uniform — takes to return to the same **ecliptic longitude**, the angle measured
eastward along the ecliptic (the plane of Earth's orbit) from the equinox. It is
*not* the same as the sidereal year (~365.256 days, one full circuit against the
fixed stars): the equinox itself drifts westward, slowly, because Earth's spin
axis precesses like a tilted top, so the mean Sun meets it about 20 minutes
early each year. That 20-minute gap is not a rounding difference to absorb —
using the sidereal year in place of this one would mis-size a sun-synchronous
design by the corresponding ~365.242/365.256 relative factor, a few hundredths
of a degree in the required inclination, which is a fair fraction of the ~1e-3
deg/day precision a J2-only theory is good for in the first place.

Used by :mod:`quoss.orbits.constellations` to set the sun-synchronous nodal
regression rate, ``2 pi / TROPICAL_YEAR_S`` ~ 0.98565 deg/day: a sun-synchronous
orbit is defined as one whose node regresses (or, being retrograde, advances) at
exactly this rate, so that the angle between the orbital plane and the
Sun-Earth line stays fixed and every pass of a given latitude happens at
(approximately) the same local solar time year-round. See
:func:`~quoss.orbits.constellations.sun_synchronous_inclination_rad`.
"""
