"""Atmospheric turbulence profile and refraction, from ITU-R P.1621-2.

What this module is for
-----------------------
The atmosphere is not a uniform slab of glass. Sunlight heats the ground, the
ground heats the air above it unevenly, and the result is a stack of air parcels
at slightly different temperatures drifting past each other. Temperature sets the
refractive index, so those parcels are weak, moving lenses. A beam crossing them
arrives wrinkled: it wanders, it breaks into speckle, and its intensity flickers.

**Everything the channel says about turbulence traces back to one number as a
function of height**, and this module is where that number is computed.

`C_n^2(h)` — the *refractive-index structure parameter* — measures how strongly
the refractive index varies between two points a given distance apart at height
`h`. Its units, m^(-2/3), look strange because it is the constant in front of a
two-thirds power law, not a variance. What matters here is only that **bigger
means more turbulence**, that it falls off steeply with height, and that
integrals of it along the path are what every later formula actually consumes.

Why ITU-R and not the usual textbook
------------------------------------
The canonical reference for this material is Andrews & Phillips, *Laser Beam
Propagation through Random Media*. It is paywalled, and none of the equation
numbers usually attributed to it could be verified. Recommendation ITU-R
P.1621-2 is free, numbered, and carries the same models, so it is the source
used here. See ``docs/adr/0009-citation-policy.md`` for the full argument and for
the gaps that decision declares — including the fact that the Bufton wind
coefficients in equation (5) below differ from the ones usually quoted from
Andrews & Phillips (30.69 and 348.91 rather than 33.11 and 360.31).

What varies over a pass, and what does not
------------------------------------------
The vertical `C_n^2` profile is a property of the site and the weather, not of
where the satellite is. In this model it does **not** change during a pass, so
:func:`integrated_cn2_m13` returns a scalar. What changes second by second is the
*geometry* — how much atmosphere the beam crosses — and that enters later, as a
`sec(zenith)` factor in :mod:`quoss.channel.turbulence`. Keeping the two apart is
what lets the expensive profile integral be computed once per scenario instead of
once per time sample.

What "above ground level" means here, which is not what it sounds like
----------------------------------------------------------------------
Every height in this module is measured from **mean sea level**, not from the
dirt under the telescope, and the recommendation's own wording makes that worth
spelling out once rather than rediscovering.

P.1621-2 defines the profile variable of equation (6) as "``h``: height above
ground level (m)" and the station parameter of equations (8a)-(13) as "``h0``:
height of the earth station above ground-level (m)". Read literally, ``h0``
would be the height of the telescope above the field it stands in — a few
metres anywhere on Earth. It is not, and the recommendation says so itself in
the sentence after equation (13) (§5.1.2, p. 11): the approximation "has been
derived ... for an **earth station altitude between 0 km and 5 km above sea
level**". A range of 0 to 5 km is a range of *sites*, not of masts. So
"ground-level" in P.1621-2 means "the ground, i.e. the sea-level datum the
profile is anchored to", and ``h0`` is the site's altitude.

That reading is what :class:`~quoss.scenario.models.StationSpec` wires: one
``altitude_m`` per station, which is both where the station is for the geometry
and where the turbulence integral starts. It is also what the difference is
worth: integrating from 2 168 m instead of 0 m leaves **9.8 times** less
turbulence overhead, because the surface term of equation (6) has a 100 m scale
height, and on the reference day that is a third of Calar Alto's key
(``tests/e2e/test_reference_scenarios.py``). The other reading would put every
mountain observatory back under the whole boundary layer, which is the opposite
of why observatories are on mountains.

Units
-----
Heights and wavelengths here are in **metres**, following the recommendation's
own equations rather than rewriting their constants — a needless transcription
risk, which is exactly what ADR 0009 exists to avoid. Station altitudes arriving
from :mod:`quoss.orbits` are in kilometres and convert on entry via
:func:`quoss.core.units.km_to_m`.

======================  ====================================================
Symbol                  Meaning
======================  ====================================================
``h``                   height above the sea-level datum (m); see above
``v_g``                 ground wind speed (m/s)
``v_rms``               r.m.s. wind speed along the vertical path (m/s)
``C_0``                 nominal ``C_n^2`` at ground level (m^(-2/3))
``C_n^2``               refractive-index structure parameter (m^(-2/3))
``n_eff``               effective refractive index of air (dimensionless)
======================  ====================================================

References
----------
Recommendation ITU-R P.1621-2 (07/2015), *Propagation data required for the
design of Earth-space systems operating between 20 THz and 375 THz*, §4
(refraction, equations (2)-(4)) and §5.1.1 (turbulence profile, equations
(5)-(7)).
"""

from __future__ import annotations

from typing import Final

import numpy as np

from quoss.core.errors import DomainError
from quoss.core.types import FloatArray

__all__ = [
    "ITU_GROUND_CN2_M23",
    "ITU_GROUND_WIND_SPEED_M_S",
    "ITU_LAYER_COUNT",
    "ITU_TURBULENCE_TOP_HEIGHT_M",
    "air_refractive_index",
    "bufton_rms_wind_speed_m_s",
    "hufnagel_valley_cn2_m23",
    "integrated_cn2_m13",
    "itu_layer_heights_m",
    "itu_layer_thicknesses_m",
    "refracted_elevation_rad",
]

ITU_GROUND_CN2_M23: Final[float] = 1.7e-14
"""Nominal ``C_n^2`` at ground level, m^(-2/3).

ITU-R P.1621-2 §5.1.1 calls this value "typical". Paired with ``v_rms`` = 21 m/s
it is described there as "typical of nighttime astronomical observation
conditions" — that is, a *good* site on a *good* night, not an average one.
"""

ITU_GROUND_WIND_SPEED_M_S: Final[float] = 2.3
"""Ground wind speed to assume when it is unknown, m/s.

ITU-R P.1621-2 §5.1.1, step 1: "When the ground wind speed is unknown, a value
of vg = 2.3 m/s may be used as an approximation resulting in vrms = 21 m/s."
"""

ITU_TURBULENCE_TOP_HEIGHT_M: Final[float] = 20_000.0
"""Effective top of the turbulent atmosphere, m.

ITU-R P.1621-2 §5.1.2 calls 20 km the "effective height of the turbulence
(typically 20 km)", and §5.1.1 states that ``C_n^2`` "becomes negligible at
heights greater than 20 km above the Earth's surface".
"""

ITU_LAYER_COUNT: Final[int] = 139
"""Number of integration layers in the ITU-R P.1621-2 equation (7) grid."""

_HIGH_ALTITUDE_COEFFICIENT: Final[float] = 8.148e-56
_HIGH_ALTITUDE_POWER: Final[int] = 10
_HIGH_ALTITUDE_SCALE_HEIGHT_M: Final[float] = 1000.0
_BACKGROUND_COEFFICIENT_M23: Final[float] = 2.7e-16
_BACKGROUND_SCALE_HEIGHT_M: Final[float] = 1500.0
_SURFACE_SCALE_HEIGHT_M: Final[float] = 100.0
"""The six constants of ITU-R P.1621-2 equation (6), named rather than inline.

Two reasons, and the second is the one that matters. The obvious one is that
``exp(-h / 1000)`` reads as a kilometre conversion and is not: 1000 m is the
scale height of the jet-stream term, and ``tests/unit/test_conventions.py``
flags a bare ``1e3`` precisely because it usually *is* a unit conversion.

The second is that the peak of the high-altitude term sits at
``_HIGH_ALTITUDE_POWER * _HIGH_ALTITUDE_SCALE_HEIGHT_M`` = 10 km — the "5/7"
model's jet stream — so the relationship between two of these constants is a
physical claim, and naming them is what lets a test assert it.
"""

_MAX_MODEL_HEIGHT_M: Final[float] = 100_000.0
"""Hard ceiling on an accepted height, m.

Not a modelling parameter: a guard. The Karman line at 100 km is the
conventional edge of the atmosphere, so a height above it is a caller error
rather than a thin atmosphere. It also keeps the ``h^10`` term of equation (6)
far from overflow, which a height of 1e31 m would otherwise reach.
"""


def bufton_rms_wind_speed_m_s(ground_wind_speed_m_s: float) -> float:
    """Return the r.m.s. wind speed along the vertical path.

    Wind matters to turbulence because it is what drags air of different
    temperatures past a given height, and the high-altitude jet stream is the
    single biggest contributor. The Bufton model summarises a whole vertical wind
    profile in one number, driven by the wind measured at the ground.

    ITU-R P.1621-2 §5.1.1 equation (5)::

        v_rms = sqrt(v_g ^ 2 + 33.11 * v_g + 360.31)

    The constant term dominates for any ordinary ground wind: even in dead calm
    the model returns sqrt(360.31) = 19 m/s, because the jet stream blows whether
    or not it is windy at the observatory.

    Parameters
    ----------
    ground_wind_speed_m_s
        Wind speed at ground level, m/s. Must be finite and non-negative.

    Returns
    -------
    float
        The r.m.s. wind speed along the vertical path, m/s.

    Raises
    ------
    DomainError
        If the ground wind speed is negative or not finite.

    Examples
    --------
    The value the recommendation itself prints for an unknown ground wind:

    >>> round(bufton_rms_wind_speed_m_s(ITU_GROUND_WIND_SPEED_M_S), 2)
    21.02

    Dead calm still leaves the jet stream:

    >>> round(bufton_rms_wind_speed_m_s(0.0), 2)
    18.98
    """
    value = float(ground_wind_speed_m_s)
    if not np.isfinite(value):
        raise DomainError(f"ground_wind_speed_m_s must be finite, got {value}.")
    if value < 0.0:
        raise DomainError(f"ground_wind_speed_m_s must be non-negative, got {value} m/s.")
    return float(np.sqrt(value * value + 33.11 * value + 360.31))


def hufnagel_valley_cn2_m23(
    height_m: FloatArray | float,
    *,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
) -> FloatArray:
    """Return ``C_n^2`` at one or more heights, from the Hufnagel-Valley 5/7 model.

    ITU-R P.1621-2 §5.1.1 equation (6)::

        C_n^2(h) = 8.148e-56 * v_rms^2 * h^10 * exp(-h/1000)
                 + 2.7e-16 * exp(-h/1500)
                 + C_0 * exp(-h/100)

    The three terms are three different physical places, which is why the model
    has the shape it does and why no single exponential would do:

    1. the **high-altitude term**, peaking near 10 km where the jet stream is.
       The ``h^10`` looks alarming but is tamed by the exponential; it exists to
       make the term negligible below the tropopause and to put a bump there.
    2. the **background term**, a thin, wind-independent floor through the
       whole troposphere.
    3. the **surface term**, which decays with a 100 m scale height. This is the
       boundary layer, and near the ground it dominates everything else by two
       orders of magnitude.

    Parameters
    ----------
    height_m
        Height above mean sea level, m (the module docstring says why
        the recommendation calls this "above ground level"). Any shape;
        scalars are accepted.
    rms_wind_speed_m_s
        The r.m.s. wind speed from :func:`bufton_rms_wind_speed_m_s`, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).

    Returns
    -------
    FloatArray
        ``C_n^2`` in m^(-2/3), with the shape of ``height_m``.

    Raises
    ------
    DomainError
        If any height is negative, non-finite, or above 100 km; or if the wind
        speed or ground turbulence is negative or non-finite.

    Examples
    --------
    At the ground the surface term dominates: it contributes the whole of
    ``C_0`` = 1.7e-14, against 2.7e-16 from the background term.

    >>> float(hufnagel_valley_cn2_m23(0.0))
    1.727e-14

    A hundred metres up, one scale height of the surface term, it has already
    dropped by a factor e and the profile has fallen by more than half:

    >>> f"{float(hufnagel_valley_cn2_m23(100.0)):.3g}"
    '6.51e-15'

    The profile is vectorised over height, and falls four orders of magnitude
    over the first 20 km:

    >>> heights = np.array([0.0, 1000.0, 10000.0, 20000.0])
    >>> np.round(np.log10(hufnagel_valley_cn2_m23(heights)), 2)
    array([-13.76, -15.86, -16.78, -18.12])
    """
    heights = np.asarray(height_m, dtype=np.float64)
    if not np.all(np.isfinite(heights)):
        raise DomainError("height_m contains non-finite values.")
    if np.any(heights < 0.0):
        raise DomainError(
            "height_m must be a height above mean sea level, so it cannot be negative. "
            f"Minimum given: {float(np.min(heights))} m."
        )
    if np.any(heights > _MAX_MODEL_HEIGHT_M):
        raise DomainError(
            "height_m above the Karman line (100 km) is outside any atmosphere; "
            f"maximum given: {float(np.max(heights))} m. Note heights here are in "
            "metres above mean sea level, not kilometres — pass km_to_m(...) if that "
            "was the mistake."
        )
    wind = float(rms_wind_speed_m_s)
    ground = float(ground_cn2_m23)
    if not np.isfinite(wind) or wind < 0.0:
        raise DomainError(f"rms_wind_speed_m_s must be finite and non-negative, got {wind}.")
    if not np.isfinite(ground) or ground < 0.0:
        raise DomainError(f"ground_cn2_m23 must be finite and non-negative, got {ground}.")

    high = (
        _HIGH_ALTITUDE_COEFFICIENT
        * wind
        * wind
        * heights**_HIGH_ALTITUDE_POWER
        * np.exp(-heights / _HIGH_ALTITUDE_SCALE_HEIGHT_M)
    )
    background = _BACKGROUND_COEFFICIENT_M23 * np.exp(-heights / _BACKGROUND_SCALE_HEIGHT_M)
    surface = ground * np.exp(-heights / _SURFACE_SCALE_HEIGHT_M)
    result: FloatArray = high + background + surface
    return result


def itu_layer_thicknesses_m() -> FloatArray:
    """Return the thicknesses of the 139 integration layers of equation (7).

    ``C_n^2`` varies over five orders of magnitude across the profile, almost all
    of that in the lowest kilometre, so a uniform grid would either miss the
    surface layer or waste thousands of points in the stratosphere. ITU-R
    P.1621-2 §5.1.1 prescribes layers whose thickness grows exponentially::

        h_i = exp((i - 1) / 20)   metres,   i = 1 .. 139

    **These are thicknesses, not altitudes.** The recommendation is explicit —
    "layer thickness or integration step size in height should increase
    exponentially, from 0.001 km at the lowest layer (ground level) to 1 km at an
    altitude of 20 km" — and reading them as altitudes is an easy and silent
    mistake: it would put the top of the atmosphere at 992 m. The altitudes are
    the running sum, which is what :func:`itu_layer_heights_m` returns.

    Returns
    -------
    FloatArray
        Layer thicknesses in metres, shape ``(139,)``, increasing.

    Examples
    --------
    The two checks the recommendation prints for itself — the top layer is about
    1 km thick, and the layers together span about 20 km:

    >>> thicknesses = itu_layer_thicknesses_m()
    >>> thicknesses.shape
    (139,)
    >>> round(float(thicknesses[0]), 3)
    1.0
    >>> round(float(thicknesses[-1]))
    992
    >>> round(float(thicknesses.sum()) / 1000.0, 1)
    20.3
    """
    index = np.arange(1, ITU_LAYER_COUNT + 1, dtype=np.float64)
    thicknesses: FloatArray = np.exp((index - 1.0) / 20.0)
    return thicknesses


def itu_layer_heights_m() -> FloatArray:
    """Return the mid-point height of each integration layer, m.

    The layer boundaries are the running sum of
    :func:`itu_layer_thicknesses_m`; the mid-points are where ``C_n^2`` is
    sampled, which makes the quadrature a midpoint rule rather than a left- or
    right-endpoint one. That choice matters more here than it usually would: the
    surface term of equation (6) falls by a factor e every 100 m, so evaluating
    the first layers at their lower edge would bias the integral high.

    Returns
    -------
    FloatArray
        Mid-point heights above mean sea level in metres, shape ``(139,)``.

    Examples
    --------
    The first layer is 1 m thick, so its mid-point sits half a metre up:

    >>> heights = itu_layer_heights_m()
    >>> round(float(heights[0]), 3)
    0.5

    The last mid-point is just under the 20 km the model calls its ceiling:

    >>> round(float(heights[-1]) / 1000.0, 2)
    19.83
    """
    thicknesses = itu_layer_thicknesses_m()
    upper_edges = np.cumsum(thicknesses)
    midpoints: FloatArray = upper_edges - 0.5 * thicknesses
    return midpoints


def integrated_cn2_m13(
    *,
    rms_wind_speed_m_s: float = 21.0,
    ground_cn2_m23: float = ITU_GROUND_CN2_M23,
    station_height_m: float = 0.0,
) -> float:
    """Return the vertical integral of ``C_n^2`` over the atmosphere, m^(1/3).

    This single number is what every later turbulence formula consumes: the Fried
    parameter, the scintillation index and the isoplanatic angle are all powers
    of an integral like this one. It is computed on the exponential layer grid of
    ITU-R P.1621-2 equation (7), evaluating equation (6) at each layer mid-point.

    The integral is **vertical**, and it is a scalar. The dependence on where the
    satellite is does not belong here: ITU-R P.1621-2 equation (8a) carries the
    slant path as a separate ``sec(zeta)`` factor outside the integral, so a pass
    needs this computed once, not once per time sample.

    Layers below ``station_height_m`` are excluded — a mountain-top observatory
    is above the worst of the boundary layer, which is the entire reason
    observatories are on mountains.

    Parameters
    ----------
    rms_wind_speed_m_s
        The r.m.s. wind speed from :func:`bufton_rms_wind_speed_m_s`, m/s.
    ground_cn2_m23
        Nominal ``C_n^2`` at ground level, m^(-2/3).
    station_height_m
        Altitude of the ground station above mean sea level, m — P.1621-2's
        ``h0``, whose 0-5 km validity range settles the reading (module
        docstring). Layers below it do not contribute.

    Returns
    -------
    float
        The integral of ``C_n^2`` over height, in m^(1/3).

    Raises
    ------
    DomainError
        If ``station_height_m`` is negative, non-finite, or at or above the 20 km
        top of the turbulent atmosphere.

    Examples
    --------
    A sea-level site under the recommendation's own nominal conditions:

    >>> total = integrated_cn2_m13()
    >>> f"{total:.3e}"
    '2.234e-12'

    Putting the station 2 500 m up — a real observatory altitude — leaves the
    worst of the boundary layer below the telescope and cuts the integrated
    turbulence by an order of magnitude. This is why observatories are on
    mountains, expressed as a number:

    >>> high_site = integrated_cn2_m13(station_height_m=2500.0)
    >>> round(total / high_site, 1)
    10.8
    """
    station = float(station_height_m)
    if not np.isfinite(station):
        raise DomainError(f"station_height_m must be finite, got {station}.")
    if station < 0.0:
        raise DomainError(f"station_height_m must be non-negative, got {station} m.")
    if station >= ITU_TURBULENCE_TOP_HEIGHT_M:
        raise DomainError(
            f"station_height_m of {station} m is at or above the {ITU_TURBULENCE_TOP_HEIGHT_M} m "
            "top of the turbulent atmosphere, leaving no path to integrate. Heights here are "
            "metres above mean sea level, not kilometres."
        )

    heights = itu_layer_heights_m()
    thicknesses = itu_layer_thicknesses_m()
    profile = hufnagel_valley_cn2_m23(
        heights,
        rms_wind_speed_m_s=rms_wind_speed_m_s,
        ground_cn2_m23=ground_cn2_m23,
    )
    above = heights >= station
    return float(np.sum(profile[above] * thicknesses[above]))


def air_refractive_index(
    wavelength_m: float,
    *,
    temperature_c: float = 15.0,
    pressure_hpa: float = 1013.25,
) -> float:
    """Return the effective refractive index of air at a wavelength.

    Air is very slightly denser to light than vacuum — about 1.00027 at optical
    wavelengths — and that tiny excess is what bends a beam coming in at a slant.
    It is also wavelength-dependent (blue bends more than red), which is why this
    takes a wavelength rather than a constant.

    ITU-R P.1621-2 §4.1 equation (2), at 15 C and 1013.25 hPa, with the vacuum
    wavelength in **micrometres**::

        n_eff = 1 + 1e-8 * (6432.8 + 2949810 / (146 - lam ^ -2) + 25540 / (41 - lam ^ -2))

    and equation (3) rescales it for other conditions::

        n_eff(T, P) = 1 + (n_eff - 1) * 1.162 P (1 + P(0.7868 - 0.0113 T) 1e-6)
                                      / (760.4696 (1 + 0.0366 T))

    Water vapour is neglected, which the recommendation licenses explicitly:
    "less than 1%" influence in this frequency range.

    .. note::

       **Equation (3) is not a no-op at equation (2)'s own reference
       conditions.** Equation (2) is stated for 15 C and 1013.25 hPa, so
       rescaling to exactly those values ought to leave it untouched; evaluated,
       the factor comes out as 1.000140519 rather than 1. That is a 140 ppm
       internal inconsistency in the recommendation, not a transcription error
       here, and it is recorded because a reader who evaluates equation (2) by
       hand will get 1.000273241 where this function returns 1.000273279 and
       will otherwise go looking for the bug.

       This function applies equation (3) always, rather than skipping it at the
       reference point, because the alternative is a discontinuity in
       temperature and pressure at one arbitrary spot. The cost of the choice is
       bounded and tiny: refraction is proportional to ``n_eff - 1``, so 140 ppm
       of the 5.3 arcmin bend at 10 degrees elevation is 0.04 arcsec.

    Parameters
    ----------
    wavelength_m
        Vacuum wavelength, m. Must be finite and positive.
    temperature_c
        Air temperature at the station, degrees Celsius.
    pressure_hpa
        Atmospheric pressure at the station, hPa. Must be positive.

    Returns
    -------
    float
        The effective refractive index, dimensionless and slightly above 1.

    Raises
    ------
    DomainError
        If the wavelength is not finite and positive, if the pressure is not
        finite and positive, or if the temperature is not finite.

    Examples
    --------
    At 1550 nm, the telecom wavelength this project defaults to:

    >>> round(air_refractive_index(1.55e-06), 9)
    1.000273279

    Thinner air bends less. At 500 hPa, roughly 5.5 km up, the excess over 1 is
    about half what it is at sea level:

    >>> thin = air_refractive_index(1.55e-06, pressure_hpa=500.0)
    >>> round((thin - 1.0) / (air_refractive_index(1.55e-06) - 1.0), 3)
    0.493
    """
    wavelength = float(wavelength_m)
    if not np.isfinite(wavelength) or wavelength <= 0.0:
        raise DomainError(f"wavelength_m must be finite and positive, got {wavelength}.")
    temperature = float(temperature_c)
    pressure = float(pressure_hpa)
    if not np.isfinite(temperature):
        raise DomainError(f"temperature_c must be finite, got {temperature}.")
    if not np.isfinite(pressure) or pressure <= 0.0:
        raise DomainError(f"pressure_hpa must be finite and positive, got {pressure}.")

    # Equation (2) is written in micrometres; the conversion is local and explicit
    # rather than a caller-facing unit, because the coefficients are only valid
    # in those units.
    wavelength_um = wavelength * 1.0e6
    inverse_square = 1.0 / (wavelength_um * wavelength_um)
    excess = 1.0e-8 * (
        6432.8 + 2_949_810.0 / (146.0 - inverse_square) + 25_540.0 / (41.0 - inverse_square)
    )
    scale = (
        1.162
        * pressure
        * (1.0 + pressure * (0.7868 - 0.0113 * temperature) * 1.0e-6)
        / (760.4696 * (1.0 + 0.0366 * temperature))
    )
    return float(1.0 + excess * scale)


def refracted_elevation_rad(
    true_elevation_rad: FloatArray | float,
    refractive_index: float,
) -> FloatArray:
    """Return the apparent elevation of a target seen through the atmosphere.

    A satellite is not where it looks. The atmosphere bends the incoming ray
    downwards, so the satellite *appears* higher than it geometrically is, and
    the effect grows as the path flattens: negligible overhead, several arcminutes
    near the horizon.

    ITU-R P.1621-2 §4.2 equation (4), from Snell's law::

        theta_obs = arccos(cos(theta_true) / n_eff)

    The recommendation states the assumption this rests on: "the Earth's
    atmosphere has uniform thickness and a constant temperature and pressure".
    That is a slab, not a real atmosphere, so the result is an acquisition-grade
    correction rather than an astrometric one — which is all a link budget needs,
    since what it feeds is the air mass.

    This is where refraction lives, rather than in
    :func:`quoss.orbits.geometry.look_angles`: that function returns the
    **geometric** elevation, and refraction is an atmospheric property that
    belongs next to the air mass that consumes it.

    Parameters
    ----------
    true_elevation_rad
        Geometric elevation above the horizon, radians. Any shape.
    refractive_index
        Effective refractive index, from :func:`air_refractive_index`.

    Returns
    -------
    FloatArray
        Apparent elevation in radians, always greater than or equal to the
        geometric one, with the shape of ``true_elevation_rad``.

    Raises
    ------
    DomainError
        If any elevation is non-finite or outside ``[0, pi/2]``, or if the
        refractive index is below 1.

    Examples
    --------
    Refraction near the horizon is worth several arcminutes. At 10 degrees, using
    the 1550 nm index:

    >>> from quoss.core.units import deg_to_rad, rad_to_deg
    >>> n = air_refractive_index(1.55e-06)
    >>> apparent = refracted_elevation_rad(deg_to_rad(10.0), n)
    >>> round(float(rad_to_deg(apparent) - 10.0) * 60.0, 2)
    5.3

    Straight overhead the ray crosses every layer head-on, so there is nothing to
    bend and the correction vanishes exactly:

    >>> zenith = deg_to_rad(90.0)
    >>> float(refracted_elevation_rad(zenith, n) - zenith)
    0.0
    """
    elevation = np.asarray(true_elevation_rad, dtype=np.float64)
    if not np.all(np.isfinite(elevation)):
        raise DomainError("true_elevation_rad contains non-finite values.")
    if np.any(elevation < 0.0) or np.any(elevation > 0.5 * np.pi):
        raise DomainError(
            "true_elevation_rad must lie in [0, pi/2]; this model is for a target above the "
            f"horizon. Range given: [{float(np.min(elevation))}, {float(np.max(elevation))}] rad. "
            "Note the unit is radians, not degrees."
        )
    index = float(refractive_index)
    if not np.isfinite(index) or index < 1.0:
        raise DomainError(f"refractive_index must be finite and at least 1, got {index}.")

    # Clipping guards the arccos against a cosine pushed just past 1 by rounding
    # when the target is at the zenith, where cos(elevation) / n_eff is already
    # below 1 by construction and only floating point can break the inequality.
    cosine = np.clip(np.cos(elevation) / index, -1.0, 1.0)
    apparent: FloatArray = np.arccos(cosine)
    return apparent
