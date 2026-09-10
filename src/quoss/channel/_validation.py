"""Input validators shared by the channel modules.

Private to :mod:`quoss.channel`, and the same reasoning as
``quoss.orbits._validation``: a physics function that trusts its inputs
relocates the error to wherever the ``nan`` eventually surfaces, which is never
where it was made.

Three arguments recur across every module of this package — an elevation angle,
a wavelength, and an aperture or other positive length — and each of the three
has a *specific* way of going wrong that a generic "must be positive" message
would not catch:

- **Elevation** arrives from :func:`quoss.orbits.geometry.look_angles`, which
  reports elevations *below* the horizon without filtering, because a pass has
  to be segmented before it is a pass. Every formula in the channel carries a
  ``sec(zenith)`` or a ``1/sin(theta)``, so zero is a divergence and a negative
  value is nonsense. It is also the one argument a caller is likely to hand over
  in degrees.
- **Wavelength** is the argument most likely to arrive in nanometres, and 1550
  is as finite and positive as 1.55e-6.
- **Apertures** are the argument most likely to arrive in centimetres.

Keeping the three in one place is what makes those messages identical wherever
they fire, which matters because the message *is* the documentation at the point
of failure.
"""

from __future__ import annotations

import numpy as np

from quoss.core.errors import DomainError
from quoss.core.types import FloatArray

__all__ = [
    "MICROMETRES_PER_METRE",
    "validated_elevation",
    "validated_positive_length_m",
    "validated_wavelength_m",
]

MICROMETRES_PER_METRE: float = 1.0e6
"""Metres to micrometres.

Not a general-purpose unit helper: it exists because several ITU-R closed forms
are printed with a numeric coefficient that already absorbs this factor (see
``turbulence._APERTURE_AVERAGING_COEFFICIENT``), so the conversion has to happen
at the entry point of exactly those functions and nowhere else.
"""


def validated_elevation(elevation_rad: FloatArray | float) -> FloatArray:
    """Return the elevation as an array, rejecting anything not above the horizon.

    Parameters
    ----------
    elevation_rad
        Elevation above the horizon, radians. Any shape.

    Returns
    -------
    FloatArray
        The elevation as a ``float64`` array, unchanged in shape.

    Raises
    ------
    DomainError
        If any value is non-finite, at or below zero, or above ``pi/2``.

    Examples
    --------
    >>> validated_elevation(1.0)
    array(1.)
    """
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


def validated_wavelength_m(wavelength_m: float) -> float:
    """Return the wavelength in metres, having checked it is finite and positive.

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m.

    Returns
    -------
    float
        The wavelength, in metres.

    Raises
    ------
    DomainError
        If the wavelength is not finite and positive.

    Examples
    --------
    >>> validated_wavelength_m(1.55e-06)
    1.55e-06
    """
    wavelength = float(wavelength_m)
    if not np.isfinite(wavelength) or wavelength <= 0.0:
        raise DomainError(f"wavelength_m must be finite and positive, got {wavelength}.")
    return wavelength


def validated_positive_length_m(name: str, value: float, *, hint: str = "") -> float:
    """Return a positive length, or raise with the argument's own name in the message.

    Parameters
    ----------
    name
        Argument name, quoted verbatim in the message so a traceback names the
        argument the caller wrote rather than a helper's parameter.
    value
        The length to validate, m.
    hint
        Extra sentence appended to the message. Used to say what the wrong unit
        would have done, which is the part a bare type error cannot say.

    Returns
    -------
    float
        The validated length, in metres.

    Raises
    ------
    DomainError
        If the value is not finite and positive.

    Examples
    --------
    >>> validated_positive_length_m("aperture_diameter_m", 0.75)
    0.75
    """
    length = float(value)
    if not np.isfinite(length) or length <= 0.0:
        message = f"{name} must be finite and positive, got {length}."
        raise DomainError(f"{message} {hint}".strip())
    return length
