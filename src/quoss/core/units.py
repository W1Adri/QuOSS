"""The unit convention, and the only place conversions are allowed to happen.

The guiding principle
---------------------
The canonical internal units are the ones the **physics formulas** use, not the
ones a human reads. Decibels and degrees are for people; radians and watts are
for equations.

=============================================  ====================  ========================
Domain                                         Canonical internal    Boundary unit (I/O only)
=============================================  ====================  ========================
Optical distances (aperture, beam, wavelength) m                     nm (wavelength)
Orbital distances (altitude, slant range)      **km**                km
Angles                                         rad                   deg
Losses / transmittances                        linear (0-1)          dB
Power                                          W                     dBm
Frequency                                      Hz                    GHz
Time (elapsed)                                 s                     s
Time (absolute)                                Julian date (days)    ISO-8601 UTC
=============================================  ====================  ========================

Orbital kilometres are the **single** exception to strict SI. ``sgp4``,
CelesTrak and essentially all of the astrodynamics literature work in km;
internalising metres would put a factor of 1000 on every SGP4 call and a factor
of 1/1000 on every comparison against a published number. The confusion that
buys is worse than the impurity it removes.

Linear, not dB, internally. QKD and channel formulas are written in linear
transmittance — ``eta_total = eta_geometric * eta_atmosphere * eta_detector``
composes by multiplication and vectorises cleanly. In dB only the *sum* is
convenient; the moment a transmittance is multiplied by anything else, or fed
into ``h(e)``, it has to come back to linear. Decibels are for the engineer's
link budget, not for the physicist's calculation.

The suffix convention
---------------------
A name states its unit so the reader never has to open a docstring:

* ``altitude_km``, ``slant_range_km`` — orbital, km
* ``aperture_m``, ``wavelength_m`` — optical, m
* ``elevation_rad`` — canonical angle; ``elevation_deg`` exists only at the boundary
* ``loss_db`` — boundary only; ``eta_total`` is the canonical linear form
* ``tx_power_w`` — power, W

**If there can be ambiguity, the suffix is mandatory.** No suffix means either
the canonical dimensionless form (a transmittance, an efficiency, a probability)
or a unit the surrounding context makes unmistakable.

Where conversions live
----------------------
Degrees and decibels are converted in ``scenario/io.py``, at the frontier with
the user, and nowhere else. There is one *internal* boundary that the table
above makes unavoidable: a slant range is orbital (km) but the geometric
coupling formula needs it in metres, alongside a wavelength in metres. That
conversion happens on entry to ``channel/`` via :func:`km_to_m`. Naming it,
rather than writing a bare ``* 1e3``, is what makes every crossing greppable.

Two decibel conventions, and why both are named
-----------------------------------------------
This is the one place a plausible-looking helper produces a silently wrong
number. A *loss* in dB is a positive quantity whose transmittance is below one:

>>> f"{db_to_linear(45.0):.12g}"  # a 45 dB *gain*
'31622.7766017'
>>> f"{loss_db_to_transmittance(45.0):.12g}"  # a 45 dB *loss*
'3.16227766017e-05'

A single ``db_to_linear`` used for both is off by nine orders of magnitude, and
the wrong answer still looks like a transmittance. Hence two explicitly named
pairs. Both use the ``10 log10`` power convention: every quantity QuOSS converts
is a power ratio, never a field amplitude.

Scalars in, scalars out
-----------------------
These helpers preserve shape: a Python ``float`` in gives a Python ``float`` out,
an array gives an array. That is not cosmetic. Left alone, ``np.log10`` returns
``np.float64``, which ``json.dumps`` and ``yaml.safe_dump`` both refuse — and
this module's whole job is to sit at the serialisation boundary.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np

from quoss.core.errors import UnitConversionError
from quoss.core.types import FloatArray, FloatLike

__all__ = [
    "M_PER_KM",
    "NM_PER_M",
    "db_to_linear",
    "dbm_to_w",
    "deg_to_rad",
    "km_to_m",
    "linear_to_db",
    "loss_db_to_transmittance",
    "m_to_km",
    "m_to_nm",
    "nm_to_m",
    "rad_to_deg",
    "transmittance_to_loss_db",
    "w_to_dbm",
]

# --------------------------------------------------------------------------- #
# Scale factors
#
# One factor per unit pair, always applied as multiply in one direction and
# divide in the other. Reusing a single exact power of ten beats defining a
# reciprocal: 1550 / 1e9 * 1e9 == 1550 exactly, whereas 1550 * 1e-9 * 1e9 is off
# by an ulp. The round trip is still only correct to within an ulp in general
# (15 / 1e9 * 1e9 == 14.999999999999998), but it is exact for the wavelengths a
# scenario actually states. Cheap to get right, annoying to debug later.
# --------------------------------------------------------------------------- #
M_PER_KM: float = 1.0e3
"""Metres per kilometre. The orbital/optical boundary factor."""

NM_PER_M: float = 1.0e9
"""Nanometres per metre. Wavelengths are quoted in nm, computed in m."""

_DBM_OFFSET_DB: float = 30.0
"""dBm is dB relative to 1 mW; a watt is 1000x larger, i.e. 30 dB up."""

_TRANSMITTANCE_TOLERANCE: float = 1e-12
"""A transmittance may exceed 1 only by rounding; beyond this it is a bug."""


def _like(value: Any, reference: FloatLike) -> FloatLike:
    """Return ``value`` shaped like ``reference``: plain float for scalar input.

    Parameters
    ----------
    value : Any
        Result of a numpy operation, typically ``np.float64`` or ``ndarray``.
    reference : float or FloatArray
        The original input, consulted only for whether it was an array.

    Returns
    -------
    float or FloatArray
        ``value`` unchanged if ``reference`` was an array, otherwise a plain
        ``float``.
    """
    if isinstance(reference, np.ndarray):
        return cast(FloatArray, value)
    return float(value)


# --------------------------------------------------------------------------- #
# Angles
# --------------------------------------------------------------------------- #
def deg_to_rad(x_deg: FloatLike) -> FloatLike:
    """Convert degrees to radians.

    Parameters
    ----------
    x_deg : float or FloatArray
        Angle in degrees.

    Returns
    -------
    float or FloatArray
        Angle in radians, the canonical internal unit.

    Examples
    --------
    >>> deg_to_rad(180.0)
    3.141592653589793
    >>> deg_to_rad(np.array([0.0, 90.0])).tolist()
    [0.0, 1.5707963267948966]
    """
    return _like(np.deg2rad(x_deg), x_deg)


def rad_to_deg(x_rad: FloatLike) -> FloatLike:
    """Convert radians to degrees.

    For output and human-facing labels only. A value in degrees must not travel
    back into a physics function.

    Parameters
    ----------
    x_rad : float or FloatArray
        Angle in radians.

    Returns
    -------
    float or FloatArray
        Angle in degrees.

    Examples
    --------
    >>> rad_to_deg(np.pi)
    180.0
    >>> round(rad_to_deg(np.pi / 6), 9)
    30.0
    """
    return _like(np.rad2deg(x_rad), x_rad)


# --------------------------------------------------------------------------- #
# Lengths
# --------------------------------------------------------------------------- #
def km_to_m(x_km: FloatLike) -> FloatLike:
    """Convert kilometres to metres.

    The orbital-to-optical boundary: a slant range travels in km, but the
    geometric coupling and diffraction formulas need metres to match the
    wavelength and aperture. Written as a named call rather than ``* 1e3`` so
    that every crossing of that boundary can be found by grep.

    Parameters
    ----------
    x_km : float or FloatArray
        Length in kilometres.

    Returns
    -------
    float or FloatArray
        Length in metres.

    Examples
    --------
    >>> km_to_m(1200.0)
    1200000.0
    """
    return _like(np.asarray(x_km) * M_PER_KM, x_km)


def m_to_km(x_m: FloatLike) -> FloatLike:
    """Convert metres to kilometres.

    Parameters
    ----------
    x_m : float or FloatArray
        Length in metres.

    Returns
    -------
    float or FloatArray
        Length in kilometres.

    Examples
    --------
    >>> m_to_km(1200000.0)
    1200.0
    """
    return _like(np.asarray(x_m) / M_PER_KM, x_m)


def nm_to_m(x_nm: FloatLike) -> FloatLike:
    """Convert nanometres to metres.

    Parameters
    ----------
    x_nm : float or FloatArray
        Wavelength in nanometres, as a scenario states it.

    Returns
    -------
    float or FloatArray
        Wavelength in metres, the canonical optical unit.

    Examples
    --------
    >>> nm_to_m(1550.0)
    1.55e-06
    >>> nm_to_m(810.0)
    8.1e-07
    """
    return _like(np.asarray(x_nm) / NM_PER_M, x_nm)


def m_to_nm(x_m: FloatLike) -> FloatLike:
    """Convert metres to nanometres.

    Parameters
    ----------
    x_m : float or FloatArray
        Wavelength in metres.

    Returns
    -------
    float or FloatArray
        Wavelength in nanometres.

    Examples
    --------
    >>> m_to_nm(1.55e-06)
    1550.0
    """
    return _like(np.asarray(x_m) * NM_PER_M, x_m)


# --------------------------------------------------------------------------- #
# Decibels — ratio convention (monotonically increasing)
# --------------------------------------------------------------------------- #
def db_to_linear(x_db: FloatLike) -> FloatLike:
    """Convert a decibel *ratio* to a linear power ratio.

    Sign convention: positive dB means a ratio above one. For an attenuation
    quoted as a positive number of dB, use :func:`loss_db_to_transmittance`
    instead — see the module docstring.

    Parameters
    ----------
    x_db : float or FloatArray
        Power ratio in dB, i.e. ``10 log10(ratio)``.

    Returns
    -------
    float or FloatArray
        Linear power ratio.

    Examples
    --------
    >>> db_to_linear(0.0)
    1.0
    >>> round(db_to_linear(3.0), 6)
    1.995262
    """
    return _like(10.0 ** (np.asarray(x_db) / 10.0), x_db)


def linear_to_db(x_linear: FloatLike) -> FloatLike:
    """Convert a linear power ratio to a decibel ratio.

    Zero maps to ``-inf``, which is the correct answer rather than a failure: a
    link below the horizon has exactly zero transmittance. numpy's ``divide``
    warning is suppressed for that case alone. A negative input is a different
    matter and raises.

    Parameters
    ----------
    x_linear : float or FloatArray
        Linear power ratio. Must be non-negative.

    Returns
    -------
    float or FloatArray
        Ratio in dB. ``-inf`` where the input is zero.

    Raises
    ------
    UnitConversionError
        If any input is negative. A negative power ratio has no decibel
        representation, and letting it through would produce a ``nan`` that
        propagates silently through a link budget.

    Examples
    --------
    >>> linear_to_db(1.0)
    0.0
    >>> linear_to_db(100.0)
    20.0
    >>> linear_to_db(0.0)
    -inf
    """
    arr = np.asarray(x_linear, dtype=np.float64)
    if np.any(arr < 0.0):
        raise UnitConversionError(
            "linear_to_db received a negative power ratio; there is no decibel "
            "representation for it. Check the sign convention at the call site."
        )
    with np.errstate(divide="ignore"):
        return _like(10.0 * np.log10(arr), x_linear)


# --------------------------------------------------------------------------- #
# Decibels — loss convention (sign-flipped)
# --------------------------------------------------------------------------- #
def loss_db_to_transmittance(loss_db: FloatLike) -> FloatLike:
    """Convert a positive loss in dB to a linear transmittance below one.

    The conversion a link budget actually needs: ``loss_db=45`` is a 45 dB
    attenuation, so the transmittance is ``1e-4.5``, not ``1e4.5``.

    Parameters
    ----------
    loss_db : float or FloatArray
        Loss in dB, positive for attenuation. A negative value means gain and is
        allowed — it yields a transmittance above one, meaningful for an
        amplifier but not for a passive channel.

    Returns
    -------
    float or FloatArray
        Linear transmittance ``10 ** (-loss_db / 10)``.

    Examples
    --------
    >>> loss_db_to_transmittance(0.0)
    1.0
    >>> f"{loss_db_to_transmittance(30.0):.12g}"
    '0.001'
    >>> f"{loss_db_to_transmittance(45.0):.12g}"
    '3.16227766017e-05'

    Printed to twelve digits and not seventeen, on purpose. ``10 ** -4.5`` goes
    through ``pow``, which no platform is required to round correctly: the exact
    value lies 0.29 ULP from the double this machine returns, so a library that
    is within 0.71 ULP — inside what any ``libm`` documents — may return the
    neighbour and print a different seventeenth digit. Twelve digits are the
    same on every conforming platform; see
    ``tests/e2e/test_reference_scenarios.py`` for the arithmetic of the rule.
    """
    return _like(10.0 ** (-np.asarray(loss_db) / 10.0), loss_db)


def transmittance_to_loss_db(eta: FloatLike) -> FloatLike:
    """Convert a linear transmittance to a positive loss in dB.

    Inverse of :func:`loss_db_to_transmittance`. A transmittance of zero maps to
    ``+inf`` dB of loss, the correct reading of a dead link.

    Parameters
    ----------
    eta : float or FloatArray
        Linear transmittance in ``[0, 1]``.

    Returns
    -------
    float or FloatArray
        Loss in dB, non-negative. ``+inf`` where ``eta`` is zero.

    Raises
    ------
    UnitConversionError
        If any value is negative, or exceeds one by more than rounding
        tolerance. A passive channel cannot transmit more than it receives, so a
        transmittance above one is an error in the model upstream, not a unit
        problem.

    Examples
    --------
    >>> transmittance_to_loss_db(1.0)
    0.0
    >>> transmittance_to_loss_db(1e-3)
    30.0
    >>> transmittance_to_loss_db(0.0)
    inf
    """
    arr = np.asarray(eta, dtype=np.float64)
    if np.any(arr < 0.0):
        raise UnitConversionError(
            "transmittance_to_loss_db received a negative transmittance. "
            "A transmittance lies in [0, 1]."
        )
    if np.any(arr > 1.0 + _TRANSMITTANCE_TOLERANCE):
        raise UnitConversionError(
            f"transmittance_to_loss_db received a transmittance above one "
            f"(max {float(np.max(arr))!r}). A passive channel cannot amplify; this "
            f"indicates a bug upstream, not a unit problem."
        )
    with np.errstate(divide="ignore"):
        # The trailing `+ 0.0` turns -0.0 into 0.0. Without it a lossless link
        # reports "-0.0 dB", which reads as a gain in a table of losses.
        return _like(-10.0 * np.log10(arr) + 0.0, eta)


# --------------------------------------------------------------------------- #
# Power
# --------------------------------------------------------------------------- #
def dbm_to_w(p_dbm: FloatLike) -> FloatLike:
    """Convert power in dBm to watts.

    Parameters
    ----------
    p_dbm : float or FloatArray
        Power in dBm, i.e. dB relative to 1 mW.

    Returns
    -------
    float or FloatArray
        Power in watts, the canonical internal unit.

    Examples
    --------
    >>> dbm_to_w(30.0)
    1.0
    >>> f"{dbm_to_w(0.0):.12g}"
    '0.001'
    """
    return _like(10.0 ** ((np.asarray(p_dbm) - _DBM_OFFSET_DB) / 10.0), p_dbm)


def w_to_dbm(p_w: FloatLike) -> FloatLike:
    """Convert power in watts to dBm.

    Parameters
    ----------
    p_w : float or FloatArray
        Power in watts. Must be non-negative.

    Returns
    -------
    float or FloatArray
        Power in dBm. ``-inf`` where the input is zero.

    Raises
    ------
    UnitConversionError
        If any input is negative.

    Examples
    --------
    >>> w_to_dbm(1.0)
    30.0
    >>> w_to_dbm(0.001)
    0.0
    """
    arr = np.asarray(p_w, dtype=np.float64)
    if np.any(arr < 0.0):
        raise UnitConversionError("w_to_dbm received a negative power.")
    with np.errstate(divide="ignore"):
        return _like(10.0 * np.log10(arr) + _DBM_OFFSET_DB, p_w)
