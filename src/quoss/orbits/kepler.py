"""Two-body motion: anomalies, Kepler's equation, and elements <-> state.

The closed-form half of the orbit problem. Everything here is exact for the
ideal two-body field; the departures from it (J2, J3, J4, drag) live in
:mod:`quoss.orbits.perturbations`, and stepping a state through time lives in
:mod:`quoss.orbits.propagator`. This module supplies the algebra those two are
built from, and nothing else: no time integration, no gravity model beyond a
single ``mu``.

Elliptical orbits only
----------------------
``0 <= e < 1``. Parabolic and hyperbolic trajectories raise
:class:`~quoss.core.errors.DomainError` rather than being silently handled by a
formula that degenerates: QuOSS simulates satellites in bound orbits, and an
eccentricity at or above one in a scenario is a mistake, not an escape
trajectory. The universal-variable formulation that would cover all conic
sections is real work to get right and would be validated by nothing this
project runs.

Kepler's equation is solved in closed form
------------------------------------------
:func:`eccentric_from_mean_anomaly` uses Markley's cubic starter followed by his
three-term correction cascade [3]_. It does not iterate, so it cannot fail to
converge — the failure mode that a Newton loop on a high-eccentricity orbit is
famous for simply does not exist here. The measured residual
``|E - e sin E - M|`` stays under 1.4e-15 rad for every ``e`` up to 0.9999,
sampled at 20 001 points per eccentricity; the solver checks its own residual on
every call and raises :class:`~quoss.core.errors.ConvergenceError` if that
post-condition is ever violated.

One caveat worth stating, because it is invisible otherwise: the residual is
absolute in *mean* anomaly, and ``dM/dE = 1 - e cos E``. Near periapsis of a
very eccentric orbit that derivative collapses, so the error in ``E`` itself is
the residual divided by ``1 - e``: about 1e-11 rad at ``e = 0.9999``, and
around 1e-15 rad at the eccentricities a LEO or SSO scenario actually uses.

Which angles come back wrapped, and which do not
------------------------------------------------
The anomaly conversions **preserve the revolution count**: feed them a mean
anomaly of 5 revolutions and the eccentric and true anomalies come back in that
same 5th revolution. This is what makes a propagated series continuous, so a
plot of true anomaly against time is a staircase-free ramp and any interpolation
over it is valid.

:func:`rv_to_coe` has no history to preserve and therefore wraps every angle it
returns to ``[0, 2 pi)``.

Degenerate orbits: the angles are folded, not lost
--------------------------------------------------
A circular orbit has no periapsis, so its argument of periapsis is undefined; an
equatorial orbit has no ascending node, so its right ascension is undefined.
Both cases occur in real scenarios — a nominally circular SSO written as
``e = 0`` in a YAML file, an equatorial relay orbit — and both make the classical
formulas divide by zero.

:func:`rv_to_coe` resolves them by folding the undefined angle into the next one
that *is* defined, and reporting which happened through
:attr:`ClassicalElements.is_circular` and
:attr:`ClassicalElements.is_equatorial`:

=================  ==============================  ===============================
Case               Convention applied              Angle that absorbs it
=================  ==============================  ===============================
Circular           ``argp = 0``                    ``nu`` becomes the argument of
                                                   latitude, ``u = omega + nu``
Equatorial         ``raan = 0``                    ``argp`` becomes the longitude
                                                   of periapsis
Circular equatorial ``raan = argp = 0``            ``nu`` becomes the true
                                                   longitude
=================  ==============================  ===============================

The folding is **lossless for the state**: only sums like ``omega + nu`` enter
the position and velocity, so :func:`coe_to_rv` reconstructs the original vectors
to machine precision in every degenerate case. What is lost is the *labelling* of
an angle that was never measurable, which is why the flags exist rather than a
silent zero.

Osculating or mean: the label travels with the elements
-------------------------------------------------------
Six numbers are not an orbit until you say *which* orbit they describe. There are
two answers in use, and they are different ellipses:

* **Osculating** — the ellipse the satellite would follow from this instant on if
  the Earth turned into a perfect sphere. It is tangent to the true path and it
  changes continuously. It is what :func:`rv_to_coe` produces, because a state
  vector cannot mean anything else.
* **Mean** — the same ellipse with the fast wobble already subtracted. It exists
  at no instant, but it is what an averaged theory such as
  :func:`~quoss.orbits.perturbations.secular_rates_j2` is a statement about.

The gap between them is ``O(J2)``, about one part in a thousand, and using one
where the other is meant is not a rounding error: converting a mean set to a
state as if it were osculating puts a 700 km sun-synchronous satellite **14.6 km**
off after one revolution and **219 km** off after a day, almost all of it
along-track, i.e. **~2 s of orbital clock per revolution**.

So :class:`ClassicalElements` carries an :class:`ElementType` the same way it
carries a :class:`~quoss.orbits.frames.Frame`, and the two functions that care
refuse the wrong one: :func:`coe_to_rv` takes osculating only,
:func:`~quoss.orbits.perturbations.secular_rates_j2` takes mean only. There is
no conversion between them yet — that is the Brouwer-Lyddane short-period
transformation — so today the flag is a gate, not a door. See
``docs/adr/0006-osculating-vs-mean-elements.md``.

Why the semi-latus rectum, not the semi-major axis
--------------------------------------------------
``p = a (1 - e^2)`` is the primary size element on :class:`ClassicalElements`,
with ``a`` available as a derived property. Three reasons: it is what the
published test case in the references takes as input, it is what
``h^2 / mu`` gives directly so :func:`rv_to_coe` computes it without a detour
through the energy, and it stays finite as ``e -> 1`` where ``a`` diverges. That
last point does not matter today, since this module rejects ``e >= 1``, but it
costs nothing to keep the door open.

Conventions in force
--------------------
Angles in radians, distances in kilometres, ``mu`` in km^3/s^2, per
``docs/adr/0001-unit-conventions.md``. ``mu`` defaults to
:data:`~quoss.core.constants.EGM96_MU_KM3_S2`; TLE work must pass
:data:`~quoss.core.constants.WGS72_MU_KM3_S2` instead, for the reason given in
:mod:`quoss.core.constants`. Every function is vectorised over the leading axis.

No function here takes a :class:`~quoss.core.errors.DegradationLog`: nothing in
this module can decide at runtime to compute something other than what its name
says. The degenerate-angle folding is not a degradation — the state it produces
is exact — and bad input raises. See ``docs/adr/0002-frames-and-time-scales.md``
for the project-wide rule, and ``docs/adr/0003-orbital-elements.md`` for the
decisions taken here.

References
----------
.. [1] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed., 2013.
       Sections 2.2 (Kepler's equation), 2.4-2.5 (classical elements),
       Algorithms 9 (RV2COE) and 10 (COE2RV).
.. [2] Bate, Mueller & White, *Fundamentals of Astrodynamics*, Dover, 1971,
       Chapter 2. The perifocal frame and the P-Q basis vectors.
.. [3] Markley, "Kepler equation solver", *Celestial Mechanics and Dynamical
       Astronomy* 63, 101-111, 1995. The non-iterative solution used here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

import numpy as np

from quoss.core.constants import EGM96_MU_KM3_S2
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import BoolArray, FloatArray, FloatLike, Vec3Array
from quoss.core.units import rad_to_deg
from quoss.orbits._validation import as_1d, as_vec3
from quoss.orbits.frames import Frame

__all__ = [
    "ClassicalElements",
    "ElementType",
    "advance_mean_anomaly",
    "coe_to_rv",
    "eccentric_from_mean_anomaly",
    "eccentric_from_true_anomaly",
    "mean_from_eccentric_anomaly",
    "mean_from_true_anomaly",
    "mean_motion_rad_s",
    "orbital_period_s",
    "rv_to_coe",
    "semi_major_axis_from_period_km",
    "true_from_eccentric_anomaly",
    "true_from_mean_anomaly",
]

_TWO_PI: Final = 2.0 * np.pi

_MAX_ECCENTRICITY: Final = 1.0
"""Open upper bound on eccentricity. At or above it the orbit is not bound."""

# --------------------------------------------------------------------------- #
# Degenerate-case threshold
#
# Both the eccentricity vector and the node vector are built from differences of
# comparable quantities, so each carries an absolute noise floor of a few times
# the float64 epsilon relative to its own scale: measured at ~3e-16 for a state
# generated from exactly circular elements, and identically zero for |n| on an
# exactly equatorial one.
#
# The threshold below is where the *direction* of those vectors stops carrying
# usable information. At e = 1e-11 the periapsis direction is uncertain by
# ~3e-16 / 1e-11 = 3e-5 rad; the uncertainty grows as 1/e from there and passes a
# milliradian at e ~ 3e-13. Choosing 1e-11 therefore folds the angle only once it
# is genuinely meaningless, three orders of magnitude tighter than the 1e-8 that
# is conventionally used — and folding costs nothing anyway, since it is lossless
# for the state.
# --------------------------------------------------------------------------- #
_DEGENERATE_TOLERANCE: Final = 1e-11

# --------------------------------------------------------------------------- #
# Kepler's equation
#
# Markley's constants [3, Eqs. 20-25]. The starter solves a cubic in closed form
# and lands within ~1e-5 rad; the three corrections that follow are a
# Newton/Halley/third-order cascade sharing one evaluation of sin and cos, which
# is why the whole solve costs about what a single Newton step would.
# --------------------------------------------------------------------------- #
_MARKLEY_ALPHA_NUM_0: Final = 3.0 * np.pi**2
_MARKLEY_ALPHA_NUM_1: Final = 1.6 * np.pi
_MARKLEY_ALPHA_DEN: Final = np.pi**2 - 6.0

_KEPLER_RESIDUAL_TOLERANCE_RAD: Final = 1e-12
"""Post-condition on ``|E - e sin E - M|``.

Measured worst case is 1.4e-15 rad over ``e`` up to 0.9999, so this leaves three
orders of magnitude of headroom. It is a self-check, not a convergence
criterion: nothing iterates, and a violation would mean the closed form was
evaluated outside the regime its author proved it on.
"""


# --------------------------------------------------------------------------- #
# Input validation
#
# Same discipline as `frames.py`: every public entry point funnels through these,
# because a physics function that trusts its inputs relocates the error to
# wherever the nan eventually surfaces.
# --------------------------------------------------------------------------- #


def _broadcast_to_common(
    names: tuple[str, ...], arrays: tuple[FloatArray, ...]
) -> list[FloatArray]:
    """Broadcast validated 1-D arrays to their common length.

    Parameters
    ----------
    names : tuple of str
        Argument names, in the same order as ``arrays``, used in the error
        message.
    arrays : tuple of FloatArray
        Validated 1-D arrays, each of length 1 or of the common length.

    Returns
    -------
    list of FloatArray
        The arrays, each of the common length.

    Raises
    ------
    DomainError
        If any length is neither 1 nor the common length.
    """
    n = max(a.size for a in arrays)
    out: list[FloatArray] = []
    for name, arr in zip(names, arrays, strict=True):
        if arr.size == n:
            out.append(arr)
        elif arr.size == 1:
            out.append(np.broadcast_to(arr, (n,)))
        else:
            raise DomainError(
                f"{name} has length {arr.size}, which is neither 1 nor {n}. "
                f"Give one value per sample, or a single value held fixed."
            )
    return out


def _validated_eccentricity(value: FloatLike) -> FloatArray:
    """Return the eccentricity as a validated array on ``[0, 1)``.

    Parameters
    ----------
    value : float or FloatArray
        Eccentricity, dimensionless.

    Returns
    -------
    FloatArray
        The validated array.

    Raises
    ------
    DomainError
        If any value is negative, or at or above one.
    """
    ecc = as_1d("eccentricity", value)
    if np.any(ecc < 0.0):
        raise DomainError(f"eccentricity must be non-negative, got minimum {ecc.min()!r}.")
    if np.any(ecc >= _MAX_ECCENTRICITY):
        raise DomainError(
            f"eccentricity must be below 1, got maximum {ecc.max()!r}. QuOSS models "
            f"bound orbits only; parabolic and hyperbolic trajectories are out of scope."
        )
    return ecc


def _validated_mu(mu_km3_s2: float) -> float:
    """Return a validated gravitational parameter.

    Parameters
    ----------
    mu_km3_s2 : float
        Gravitational parameter, km^3/s^2.

    Returns
    -------
    float
        The value, unchanged.

    Raises
    ------
    DomainError
        If it is not finite and positive.
    """
    if not (np.isfinite(mu_km3_s2) and mu_km3_s2 > 0.0):
        raise DomainError(f"mu_km3_s2 must be finite and positive, got {mu_km3_s2!r}.")
    return float(mu_km3_s2)


def _wrap_two_pi(angle_rad: FloatArray) -> FloatArray:
    """Wrap angles to ``[0, 2 pi)``.

    Parameters
    ----------
    angle_rad : FloatArray
        Angles in radians.

    Returns
    -------
    FloatArray
        The wrapped angles.
    """
    return np.asarray(np.mod(angle_rad, _TWO_PI), dtype=np.float64)


def _turns_and_principal(angle_rad: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Split an angle into whole turns and a principal part in ``(-pi, pi]``.

    The pair is what lets the anomaly conversions preserve the revolution count:
    the principal parts of the mean, eccentric and true anomalies always lie in
    the same half-open turn, so putting the turns back afterwards is exact.

    Parameters
    ----------
    angle_rad : FloatArray
        Angles in radians.

    Returns
    -------
    turns : FloatArray
        Whole turns, as a float.
    principal_rad : FloatArray
        The remainder, in ``(-pi, pi]``.
    """
    turns = np.floor((angle_rad + np.pi) / _TWO_PI)
    return turns, angle_rad - _TWO_PI * turns


# --------------------------------------------------------------------------- #
# Anomalies
# --------------------------------------------------------------------------- #
def eccentric_from_mean_anomaly(
    mean_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Solve Kepler's equation ``M = E - e sin E`` for the eccentric anomaly.

    Closed form, not iterative: Markley's cubic starter plus his three-term
    correction cascade [3]_. There is no iteration count to exhaust and no
    starting guess to get wrong, so the solve costs the same for a circular orbit
    and for ``e = 0.99``.

    Parameters
    ----------
    mean_anomaly_rad : float or FloatArray
        Mean anomaly, radians. Any value is accepted; whole revolutions are
        carried through to the result, so ``M = 4 pi + 0.3`` gives an eccentric
        anomaly in the third revolution.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching the mean anomaly.

    Returns
    -------
    FloatArray
        Eccentric anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.
    ConvergenceError
        If the residual ``|E - e sin E - M|`` exceeds
        ``_KEPLER_RESIDUAL_TOLERANCE_RAD``. This is a post-condition check on a
        closed-form expression, not a convergence failure; it has never fired.

    Notes
    -----
    The residual is absolute in mean anomaly. Since ``dM/dE = 1 - e cos E``, the
    error in ``E`` near periapsis of a very eccentric orbit is larger than the
    residual by ``1 / (1 - e)``. See the module docstring.

    Examples
    --------
    A circular orbit needs no solving at all:

    >>> import numpy as np
    >>> float(eccentric_from_mean_anomaly(1.25, 0.0)[0])
    1.25

    Vallado's worked example: ``M = 235.4 deg``, ``e = 0.4``:

    >>> e_rad = eccentric_from_mean_anomaly(np.deg2rad(235.4), 0.4)
    >>> float(np.round(np.rad2deg(e_rad[0]), 9))
    220.512074768

    Whole revolutions survive, so a propagated series stays continuous:

    >>> float(np.round(eccentric_from_mean_anomaly(4 * np.pi + 0.3, 0.2)[0], 12))
    12.939225798485
    """
    mean = as_1d("mean_anomaly_rad", mean_anomaly_rad)
    ecc = _validated_eccentricity(eccentricity)
    mean, ecc = _broadcast_to_common(("mean_anomaly_rad", "eccentricity"), (mean, ecc))

    turns, principal = _turns_and_principal(mean)

    # Markley solves for |M| on [0, pi] and the equation is odd in M, so the sign
    # is taken out first and put back at the end.
    sign = np.where(principal < 0.0, -1.0, 1.0)
    m_abs = np.abs(principal)

    alpha = (_MARKLEY_ALPHA_NUM_0 + _MARKLEY_ALPHA_NUM_1 * (np.pi - m_abs) / (1.0 + ecc)) / (
        _MARKLEY_ALPHA_DEN
    )
    d = 3.0 * (1.0 - ecc) + alpha * ecc
    q = 2.0 * alpha * d * (1.0 - ecc) - m_abs * m_abs
    r = 3.0 * alpha * d * (d - 1.0 + ecc) * m_abs + m_abs**3
    w = np.cbrt(np.abs(r) + np.sqrt(q**3 + r * r)) ** 2
    e_start = (2.0 * r * w / (w * w + w * q + q * q) + m_abs) / d

    # One sin/cos pair feeds all three corrections [3, Eqs. 26-29].
    f2 = ecc * np.sin(e_start)
    f3 = ecc * np.cos(e_start)
    f0 = e_start - f2 - m_abs
    f1 = 1.0 - f3
    f4 = -f2
    delta3 = -f0 / (f1 - 0.5 * f0 * f2)
    delta4 = -f0 / (f1 + 0.5 * delta3 * f2 + delta3**2 * f3 / 6.0)
    delta5 = -f0 / (f1 + 0.5 * delta4 * f2 + delta4**2 * f3 / 6.0 + delta4**3 * f4 / 24.0)

    principal_ecc = sign * (e_start + delta5)

    residual = np.abs(principal_ecc - ecc * np.sin(principal_ecc) - principal)
    if not np.all(residual <= _KEPLER_RESIDUAL_TOLERANCE_RAD):
        worst = float(np.max(residual))
        raise ConvergenceError(
            f"Kepler's equation left a residual of {worst:.3e} rad, above the "
            f"{_KEPLER_RESIDUAL_TOLERANCE_RAD:.0e} rad post-condition. The closed-form "
            f"solution was evaluated outside the regime it is proven on; check the "
            f"eccentricity (maximum {float(np.max(ecc))!r})."
        )
    return np.asarray(principal_ecc + _TWO_PI * turns, dtype=np.float64)


def mean_from_eccentric_anomaly(
    eccentric_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Evaluate Kepler's equation ``M = E - e sin E``.

    The exact inverse of :func:`eccentric_from_mean_anomaly`, and the cheap
    direction: no solving involved.

    Parameters
    ----------
    eccentric_anomaly_rad : float or FloatArray
        Eccentric anomaly, radians. Revolutions are carried through.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.

    Returns
    -------
    FloatArray
        Mean anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.

    Examples
    --------
    >>> import numpy as np
    >>> float(np.round(np.rad2deg(mean_from_eccentric_anomaly(3.84866174509717, 0.4)[0]), 9))
    235.4
    """
    ecc_anom = as_1d("eccentric_anomaly_rad", eccentric_anomaly_rad)
    ecc = _validated_eccentricity(eccentricity)
    ecc_anom, ecc = _broadcast_to_common(("eccentric_anomaly_rad", "eccentricity"), (ecc_anom, ecc))
    return np.asarray(ecc_anom - ecc * np.sin(ecc_anom), dtype=np.float64)


def true_from_eccentric_anomaly(
    eccentric_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Convert eccentric anomaly to true anomaly.

    Parameters
    ----------
    eccentric_anomaly_rad : float or FloatArray
        Eccentric anomaly, radians. Revolutions are carried through.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.

    Returns
    -------
    FloatArray
        True anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.

    Notes
    -----
    Uses the half-angle form ``tan(nu/2) = sqrt((1+e)/(1-e)) tan(E/2)``, split
    into an :func:`numpy.arctan2` of separate sine and cosine terms [1]_
    Eq. 2-14. The single-argument ``arctan`` version loses the quadrant and the
    ``cos nu = (cos E - e)/(1 - e cos E)`` version loses precision near
    periapsis, where the numerator is a difference of nearly equal numbers.

    Examples
    --------
    At periapsis and apoapsis all three anomalies coincide:

    >>> import numpy as np
    >>> float(true_from_eccentric_anomaly(0.0, 0.7)[0])
    0.0
    >>> float(np.round(true_from_eccentric_anomaly(np.pi, 0.7)[0], 12))
    3.14159265359
    """
    ecc_anom = as_1d("eccentric_anomaly_rad", eccentric_anomaly_rad)
    ecc = _validated_eccentricity(eccentricity)
    ecc_anom, ecc = _broadcast_to_common(("eccentric_anomaly_rad", "eccentricity"), (ecc_anom, ecc))
    turns, principal = _turns_and_principal(ecc_anom)
    half = 0.5 * principal
    true_principal = 2.0 * np.arctan2(
        np.sqrt(1.0 + ecc) * np.sin(half), np.sqrt(1.0 - ecc) * np.cos(half)
    )
    return np.asarray(true_principal + _TWO_PI * turns, dtype=np.float64)


def eccentric_from_true_anomaly(
    true_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Convert true anomaly to eccentric anomaly.

    The exact inverse of :func:`true_from_eccentric_anomaly`.

    Parameters
    ----------
    true_anomaly_rad : float or FloatArray
        True anomaly, radians. Revolutions are carried through.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.

    Returns
    -------
    FloatArray
        Eccentric anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.

    Examples
    --------
    >>> import numpy as np
    >>> float(np.round(eccentric_from_true_anomaly(np.deg2rad(92.335), 0.83285)[0], 9))
    0.60950797
    """
    true_anom = as_1d("true_anomaly_rad", true_anomaly_rad)
    ecc = _validated_eccentricity(eccentricity)
    true_anom, ecc = _broadcast_to_common(("true_anomaly_rad", "eccentricity"), (true_anom, ecc))
    turns, principal = _turns_and_principal(true_anom)
    half = 0.5 * principal
    ecc_principal = 2.0 * np.arctan2(
        np.sqrt(1.0 - ecc) * np.sin(half), np.sqrt(1.0 + ecc) * np.cos(half)
    )
    return np.asarray(ecc_principal + _TWO_PI * turns, dtype=np.float64)


def true_from_mean_anomaly(
    mean_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Convert mean anomaly to true anomaly, through Kepler's equation.

    Parameters
    ----------
    mean_anomaly_rad : float or FloatArray
        Mean anomaly, radians. Revolutions are carried through.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.

    Returns
    -------
    FloatArray
        True anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.
    ConvergenceError
        Propagated from :func:`eccentric_from_mean_anomaly`.

    Examples
    --------
    >>> import numpy as np
    >>> float(np.round(np.rad2deg(true_from_mean_anomaly(np.deg2rad(235.4), 0.4)[0]), 6))
    207.163992
    """
    ecc_anom = eccentric_from_mean_anomaly(mean_anomaly_rad, eccentricity)
    return true_from_eccentric_anomaly(ecc_anom, eccentricity)


def mean_from_true_anomaly(
    true_anomaly_rad: FloatLike,
    eccentricity: FloatLike,
) -> FloatArray:
    """Convert true anomaly to mean anomaly.

    The exact inverse of :func:`true_from_mean_anomaly`.

    Parameters
    ----------
    true_anomaly_rad : float or FloatArray
        True anomaly, radians. Revolutions are carried through.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.

    Returns
    -------
    FloatArray
        Mean anomaly, radians, in the same revolution as the input.

    Raises
    ------
    DomainError
        If eccentricity is outside ``[0, 1)``, an input is not finite, or the
        lengths do not broadcast.

    Examples
    --------
    >>> import numpy as np
    >>> float(np.round(np.rad2deg(mean_from_true_anomaly(np.deg2rad(207.163992), 0.4)[0]), 6))
    235.4
    """
    ecc_anom = eccentric_from_true_anomaly(true_anomaly_rad, eccentricity)
    return mean_from_eccentric_anomaly(ecc_anom, eccentricity)


# --------------------------------------------------------------------------- #
# Size and period
# --------------------------------------------------------------------------- #
def mean_motion_rad_s(
    semi_major_axis_km: FloatLike,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
) -> FloatArray:
    """Mean motion ``n = sqrt(mu / a^3)``, radians per second.

    Parameters
    ----------
    semi_major_axis_km : float or FloatArray
        Semi-major axis, km. Must be positive.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96. Pass the WGS-72
        value when working with TLE mean elements.

    Returns
    -------
    FloatArray
        Mean motion, rad/s.

    Raises
    ------
    DomainError
        If the semi-major axis is not positive, or ``mu`` is not positive.

    Examples
    --------
    A 550 km circular orbit turns roughly once every 95 minutes:

    >>> import numpy as np
    >>> n = mean_motion_rad_s(6378.137 + 550.0)
    >>> float(np.round(2 * np.pi / n[0] / 60.0, 3))
    95.65
    """
    axis = as_1d("semi_major_axis_km", semi_major_axis_km)
    mu = _validated_mu(mu_km3_s2)
    if np.any(axis <= 0.0):
        raise DomainError(
            f"semi_major_axis_km must be positive, got minimum {float(axis.min())!r}. "
            f"A non-positive axis means the orbit is not bound."
        )
    return np.asarray(np.sqrt(mu / axis**3), dtype=np.float64)


def orbital_period_s(
    semi_major_axis_km: FloatLike,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
) -> FloatArray:
    """Keplerian period ``T = 2 pi sqrt(a^3 / mu)``, seconds.

    Parameters
    ----------
    semi_major_axis_km : float or FloatArray
        Semi-major axis, km. Must be positive.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.

    Returns
    -------
    FloatArray
        Period, seconds.

    Raises
    ------
    DomainError
        If the semi-major axis is not positive, or ``mu`` is not positive.

    Notes
    -----
    This is the two-body period. The nodal and anomalistic periods of a real LEO
    differ from it by a few seconds through J2; that correction belongs to
    :mod:`quoss.orbits.perturbations`, not here.

    Examples
    --------
    >>> import numpy as np
    >>> float(np.round(orbital_period_s(42164.0)[0] / 3600.0, 4))
    23.9343
    """
    return np.asarray(_TWO_PI / mean_motion_rad_s(semi_major_axis_km, mu_km3_s2), dtype=np.float64)


def semi_major_axis_from_period_km(
    period_s: FloatLike,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
) -> FloatArray:
    """Invert :func:`orbital_period_s`: ``a = (mu (T / 2 pi)^2)^(1/3)``.

    The direction repeat-ground-track and sun-synchronous design work in, where
    the period is the requirement and the altitude is the answer.

    Parameters
    ----------
    period_s : float or FloatArray
        Keplerian period, seconds. Must be positive.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.

    Returns
    -------
    FloatArray
        Semi-major axis, km.

    Raises
    ------
    DomainError
        If the period is not positive, or ``mu`` is not positive.

    Examples
    --------
    A sidereal day gives the geostationary radius:

    >>> import numpy as np
    >>> float(np.round(semi_major_axis_from_period_km(86164.0905)[0], 3))
    42164.17
    """
    period = as_1d("period_s", period_s)
    mu = _validated_mu(mu_km3_s2)
    if np.any(period <= 0.0):
        raise DomainError(f"period_s must be positive, got minimum {float(period.min())!r}.")
    return np.asarray(np.cbrt(mu * (period / _TWO_PI) ** 2), dtype=np.float64)


def advance_mean_anomaly(
    mean_anomaly_rad: FloatLike,
    mean_motion_rad_s_: FloatLike,
    dt_s: FloatLike,
) -> FloatArray:
    """Advance the mean anomaly by an elapsed time: ``M = M0 + n dt``.

    The only place time enters this module, and the whole of two-body time
    dependence: everything else in a Keplerian orbit is constant. The result is
    **not** wrapped, so that the revolution count survives and the anomaly
    conversions stay continuous over a multi-orbit series.

    Parameters
    ----------
    mean_anomaly_rad : float or FloatArray
        Mean anomaly at the epoch, radians. Length 1 or matching.
    mean_motion_rad_s_ : float or FloatArray
        Mean motion, rad/s, from :func:`mean_motion_rad_s`. Trailing underscore
        because the name is taken by that function. Length 1 or matching.
    dt_s : float or FloatArray
        Elapsed time from the epoch, seconds. Negative values run backwards.

    Returns
    -------
    FloatArray
        Mean anomaly at ``dt_s``, radians, unwrapped.

    Raises
    ------
    DomainError
        If an input is not finite, or the lengths do not broadcast.

    Examples
    --------
    One period returns exactly one revolution later:

    >>> import numpy as np
    >>> n = mean_motion_rad_s(7000.0)
    >>> t = orbital_period_s(7000.0)
    >>> float(np.round(advance_mean_anomaly(0.5, n, t)[0] - 0.5, 12))
    6.28318530718
    """
    mean = as_1d("mean_anomaly_rad", mean_anomaly_rad)
    motion = as_1d("mean_motion_rad_s_", mean_motion_rad_s_)
    dt = as_1d("dt_s", dt_s)
    mean, motion, dt = _broadcast_to_common(
        ("mean_anomaly_rad", "mean_motion_rad_s_", "dt_s"), (mean, motion, dt)
    )
    return np.asarray(mean + motion * dt, dtype=np.float64)


# --------------------------------------------------------------------------- #
# Classical elements
# --------------------------------------------------------------------------- #
class ElementType(StrEnum):
    """Which of the two ellipses a set of six numbers describes.

    A tag, like :class:`~quoss.orbits.frames.Frame`, and for the same reason: the
    confusion it prevents does not raise anything on its own, it produces a
    plausible trajectory that is 219 km wrong after a day. Every
    :class:`ClassicalElements` carries one, and the functions that can only be
    correct for one of the two refuse the other.

    Attributes
    ----------
    OSCULATING : str
        The ellipse tangent to the true path at this instant — where the
        satellite would go if the Earth became a point mass right now. What
        :func:`rv_to_coe` returns, what :func:`coe_to_rv` accepts, and what a
        scenario file writes. The default, because it is the only kind this
        project can currently produce or consume.
    MEAN_BROUWER : str
        Brouwer-Lyddane mean elements referred to the EGM96 constants: the same
        orbit with the short-period wobble averaged out. The input the
        first-order theory in
        :func:`~quoss.orbits.perturbations.secular_rates_j2` is a statement
        about. Nothing in QuOSS produces these yet; the member exists so that the
        function which *requires* them can say so.

    Notes
    -----
    **There is no plain ``MEAN``, and that is the whole design.** "Mean" is not
    one thing, it is one thing per theory: the mean elements in a TLE are
    Brouwer's with Kozai's modification and the WGS-72 constants, while the ones
    :func:`~quoss.orbits.perturbations.secular_rates_j2` wants are Brouwer-Lyddane
    with EGM96. They are not interchangeable, and a two-valued flag whose second
    value was called ``MEAN`` would make them look as though they were — the exact
    mistake the flag exists to prevent.

    Naming the member after its theory is also what makes the enum safe to grow.
    The reason to fear a third value is that adding it later forces every caller
    that wrote ``MEAN`` to decide which one they meant; no caller can write
    ``MEAN`` here, so ``MEAN_KOZAI_SGP4`` can be added the day something produces
    it without touching a single existing call site. It is **not** added now
    because ``docs/adr/0005-propagation.md`` decided that ``tle.py`` never builds
    a :class:`ClassicalElements` at all: SGP4 returns a state in TEME, and the
    elements of that state are osculating. A member no code can produce is a
    label that only invites being applied by hand.

    Examples
    --------
    >>> ElementType.OSCULATING
    <ElementType.OSCULATING: 'osculating'>
    >>> ElementType("mean_brouwer") is ElementType.MEAN_BROUWER
    True
    >>> sorted(ElementType)
    [<ElementType.MEAN_BROUWER: 'mean_brouwer'>, <ElementType.OSCULATING: 'osculating'>]
    """

    OSCULATING = "osculating"
    MEAN_BROUWER = "mean_brouwer"


def _validated_element_type(element_type: ElementType) -> ElementType:
    """Resolve ``element_type`` to a member, accepting the equal string.

    Parameters
    ----------
    element_type : ElementType
        The member, or a string equal to one of its values, so that a scenario
        field can be YAML text.

    Returns
    -------
    ElementType
        The member.

    Raises
    ------
    DomainError
        If the value names no member.
    """
    try:
        return ElementType(element_type)
    except ValueError as exc:
        valid = ", ".join(repr(str(member)) for member in ElementType)
        raise DomainError(
            f"{element_type!r} is not an element type. Valid values are {valid}. "
            f"There is deliberately no bare 'mean': mean elements are mean *per theory*, "
            f"and QuOSS has no 'mean_kozai_sgp4' because nothing here builds elements "
            f"from a TLE. See docs/adr/0006-osculating-vs-mean-elements.md."
        ) from exc


class ClassicalElements:
    """The six classical orbital elements, vectorised over the leading axis.

    Immutable and validated at construction, so a function receiving one may
    assume the eccentricities are bound, the inclinations are in range and every
    field has the same length.

    Scalars are accepted for any element and broadcast against the others, so a
    single orbit reads naturally and a stack of them reads the same way. What is
    *stored* — and what every attribute returns — is always a 1-D ``float64``
    array of the common length, with a single orbit as length 1. That asymmetry
    is the point: construction is permissive so a scenario reads like a
    scenario, and every consumer downstream sees the array contract of
    :mod:`quoss.core.types` with no ``float`` case to handle.

    Not a dataclass, for that reason: a generated ``__init__`` would have to
    declare one type for both roles, and widening the attributes to
    ``float | FloatArray`` would push a branch into every caller for a case that
    cannot occur after ``__init__`` returns.

    Parameters
    ----------
    semi_latus_rectum_km : float or FloatArray
        Semi-latus rectum ``p = a (1 - e^2)``, km. Must be positive. The primary
        size element; see the module docstring for why it is ``p`` and not ``a``.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``.
    inclination_rad : float or FloatArray
        Inclination, radians, in ``[0, pi]``.
    raan_rad : float or FloatArray
        Right ascension of the ascending node, radians. Wrapped to ``[0, 2 pi)``
        on construction. Zero by convention for an equatorial orbit.
    argp_rad : float or FloatArray
        Argument of periapsis, radians. Wrapped to ``[0, 2 pi)``. Zero by
        convention for a circular orbit.
    true_anomaly_rad : float or FloatArray
        True anomaly, radians. Wrapped to ``[0, 2 pi)``.
    frame : Frame, optional
        Inertial frame the elements are referred to. Defaults to
        :attr:`~quoss.orbits.frames.Frame.TEME`, QuOSS's single inertial frame.
        An Earth-fixed or topocentric frame is rejected: orbital elements in a
        rotating frame are not orbital elements.
    element_type : ElementType, optional
        Which ellipse these six numbers describe. Defaults to
        :attr:`ElementType.OSCULATING`, the only kind QuOSS produces today. State
        it explicitly when writing mean elements by hand, because nothing
        downstream can infer it — see :class:`ElementType`.

    Raises
    ------
    DomainError
        If any value is out of range or not finite, if the lengths do not
        broadcast, if ``frame`` is not inertial, or if ``element_type`` names no
        member.

    Examples
    --------
    >>> import numpy as np
    >>> coe = ClassicalElements(
    ...     semi_latus_rectum_km=11067.790,
    ...     eccentricity=0.83285,
    ...     inclination_rad=np.deg2rad(87.87),
    ...     raan_rad=np.deg2rad(227.89),
    ...     argp_rad=np.deg2rad(53.38),
    ...     true_anomaly_rad=np.deg2rad(92.335),
    ... )
    >>> coe.n
    1
    >>> float(np.round(coe.semi_major_axis_km[0], 3))
    36126.643
    """

    __slots__ = (
        "_argp_rad",
        "_eccentricity",
        "_element_type",
        "_frame",
        "_inclination_rad",
        "_raan_rad",
        "_semi_latus_rectum_km",
        "_true_anomaly_rad",
    )

    def __init__(
        self,
        *,
        semi_latus_rectum_km: FloatLike,
        eccentricity: FloatLike,
        inclination_rad: FloatLike,
        raan_rad: FloatLike,
        argp_rad: FloatLike,
        true_anomaly_rad: FloatLike,
        frame: Frame = Frame.TEME,
        element_type: ElementType = ElementType.OSCULATING,
    ) -> None:
        if frame not in (Frame.TEME, Frame.GCRF):
            raise DomainError(
                f"Orbital elements must be referred to an inertial frame, got {frame!r}. "
                f"Elements expressed in a rotating frame are not orbital elements."
            )
        resolved_type = _validated_element_type(element_type)
        p = as_1d("semi_latus_rectum_km", semi_latus_rectum_km)
        if np.any(p <= 0.0):
            raise DomainError(
                f"semi_latus_rectum_km must be positive, got minimum {float(p.min())!r}."
            )
        ecc = _validated_eccentricity(eccentricity)
        inc = as_1d("inclination_rad", inclination_rad)
        if np.any(inc < 0.0) or np.any(inc > np.pi):
            raise DomainError(
                "inclination_rad must lie in [0, pi]. A value outside it is almost always "
                "degrees that were never converted."
            )
        raan = as_1d("raan_rad", raan_rad)
        argp = as_1d("argp_rad", argp_rad)
        nu = as_1d("true_anomaly_rad", true_anomaly_rad)

        names = (
            "semi_latus_rectum_km",
            "eccentricity",
            "inclination_rad",
            "raan_rad",
            "argp_rad",
            "true_anomaly_rad",
        )
        p, ecc, inc, raan, argp, nu = _broadcast_to_common(names, (p, ecc, inc, raan, argp, nu))

        self._semi_latus_rectum_km = p
        self._eccentricity = ecc
        self._inclination_rad = inc
        self._raan_rad = _wrap_two_pi(raan)
        self._argp_rad = _wrap_two_pi(argp)
        self._true_anomaly_rad = _wrap_two_pi(nu)
        self._frame = frame
        self._element_type = resolved_type

    @classmethod
    def from_semi_major_axis(
        cls,
        *,
        semi_major_axis_km: FloatLike,
        eccentricity: FloatLike,
        inclination_rad: FloatLike,
        raan_rad: FloatLike,
        argp_rad: FloatLike,
        true_anomaly_rad: FloatLike,
        frame: Frame = Frame.TEME,
        element_type: ElementType = ElementType.OSCULATING,
    ) -> ClassicalElements:
        """Build elements from the semi-major axis instead of ``p``.

        The form a scenario is written in: an altitude gives ``a``, not ``p``.

        Parameters
        ----------
        semi_major_axis_km : float or FloatArray
            Semi-major axis ``a``, km. Must be positive.
        eccentricity : float or FloatArray
            Eccentricity, in ``[0, 1)``.
        inclination_rad : float or FloatArray
            Inclination, radians, in ``[0, pi]``.
        raan_rad : float or FloatArray
            Right ascension of the ascending node, radians.
        argp_rad : float or FloatArray
            Argument of periapsis, radians.
        true_anomaly_rad : float or FloatArray
            True anomaly, radians.
        frame : Frame, optional
            Inertial frame of the elements.
        element_type : ElementType, optional
            Osculating or mean; see :class:`ElementType`. Defaults to
            osculating.

        Returns
        -------
        ClassicalElements
            The elements, with ``p = a (1 - e^2)``.

        Raises
        ------
        DomainError
            If the semi-major axis is not positive, or any other field is
            invalid.

        Examples
        --------
        >>> coe = ClassicalElements.from_semi_major_axis(
        ...     semi_major_axis_km=6928.137,
        ...     eccentricity=0.0,
        ...     inclination_rad=1.7,
        ...     raan_rad=0.0,
        ...     argp_rad=0.0,
        ...     true_anomaly_rad=0.0,
        ... )
        >>> float(coe.semi_latus_rectum_km[0])
        6928.137
        """
        axis = as_1d("semi_major_axis_km", semi_major_axis_km)
        if np.any(axis <= 0.0):
            raise DomainError(
                f"semi_major_axis_km must be positive, got minimum {float(axis.min())!r}."
            )
        ecc = _validated_eccentricity(eccentricity)
        axis, ecc = _broadcast_to_common(("semi_major_axis_km", "eccentricity"), (axis, ecc))
        return cls(
            semi_latus_rectum_km=axis * (1.0 - ecc * ecc),
            eccentricity=ecc,
            inclination_rad=inclination_rad,
            raan_rad=raan_rad,
            argp_rad=argp_rad,
            true_anomaly_rad=true_anomaly_rad,
            frame=frame,
            element_type=element_type,
        )

    def relabelled_as(self, element_type: ElementType) -> ClassicalElements:
        """Return the **same numbers** under a different :class:`ElementType`.

        This converts nothing. It changes a label, and the six numbers that come
        out are bit-for-bit the ones that went in. That is the point, and it is
        why the name says "relabelled" rather than "as" or "to".

        It exists for one legitimate use: **measuring what not converting
        costs**. ``TestSecularRatesAgainstIntegration`` in
        ``tests/orbits/test_perturbations.py`` feeds osculating elements to
        :func:`~quoss.orbits.perturbations.secular_rates_j2` deliberately — that
        is how the residual of the first-order theory was shown to be exactly
        proportional to J2, which is the measurement that separates "the theory
        is truncated" from "a coefficient is mistyped". With the flag in force
        that test cannot run without saying out loud that it is lying to the
        function, and this is where it says it.

        The alternative that was rejected: an ``assume_mean=True`` parameter on
        :func:`~quoss.orbits.perturbations.secular_rates_j2`. That is the same
        silent degradation the flag exists to stop, wearing a keyword's clothes —
        it would sit in the physics API, default to something, and be reachable
        from a scenario. A method on the container is reachable only by someone
        holding the container and writing the word.

        Parameters
        ----------
        element_type : ElementType
            The label to apply.

        Returns
        -------
        ClassicalElements
            A new object; ``self`` is unchanged, like every other operation on
            this class.

        Raises
        ------
        DomainError
            If ``element_type`` names no member.

        Examples
        --------
        >>> import numpy as np
        >>> coe = ClassicalElements.from_semi_major_axis(
        ...     semi_major_axis_km=7078.137,
        ...     eccentricity=0.001,
        ...     inclination_rad=np.deg2rad(98.19),
        ...     raan_rad=0.0,
        ...     argp_rad=0.0,
        ...     true_anomaly_rad=0.0,
        ... )
        >>> pretend = coe.relabelled_as(ElementType.MEAN_BROUWER)
        >>> pretend.element_type
        <ElementType.MEAN_BROUWER: 'mean_brouwer'>
        >>> bool(np.array_equal(pretend.semi_latus_rectum_km, coe.semi_latus_rectum_km))
        True
        >>> coe.element_type
        <ElementType.OSCULATING: 'osculating'>
        """
        return ClassicalElements(
            semi_latus_rectum_km=self._semi_latus_rectum_km,
            eccentricity=self._eccentricity,
            inclination_rad=self._inclination_rad,
            raan_rad=self._raan_rad,
            argp_rad=self._argp_rad,
            true_anomaly_rad=self._true_anomaly_rad,
            frame=self._frame,
            element_type=element_type,
        )

    # -- the six elements, as stored ----------------------------------------- #
    @property
    def semi_latus_rectum_km(self) -> FloatArray:
        """Semi-latus rectum ``p``, km."""
        return self._semi_latus_rectum_km

    @property
    def eccentricity(self) -> FloatArray:
        """Eccentricity, dimensionless, in ``[0, 1)``."""
        return self._eccentricity

    @property
    def inclination_rad(self) -> FloatArray:
        """Inclination, radians, in ``[0, pi]``."""
        return self._inclination_rad

    @property
    def raan_rad(self) -> FloatArray:
        """Right ascension of the ascending node, radians, in ``[0, 2 pi)``."""
        return self._raan_rad

    @property
    def argp_rad(self) -> FloatArray:
        """Argument of periapsis, radians, in ``[0, 2 pi)``."""
        return self._argp_rad

    @property
    def true_anomaly_rad(self) -> FloatArray:
        """True anomaly, radians, in ``[0, 2 pi)``."""
        return self._true_anomaly_rad

    @property
    def frame(self) -> Frame:
        """Inertial frame the elements are referred to."""
        return self._frame

    @property
    def element_type(self) -> ElementType:
        """Whether these are osculating or mean elements. See :class:`ElementType`."""
        return self._element_type

    # -- derived geometry ---------------------------------------------------- #
    @property
    def n(self) -> int:
        """Number of orbits held."""
        return int(self._eccentricity.size)

    @property
    def semi_major_axis_km(self) -> FloatArray:
        """Semi-major axis ``a = p / (1 - e^2)``, km. Finite because ``e < 1``."""
        ecc = self._eccentricity
        return np.asarray(self._semi_latus_rectum_km / (1.0 - ecc * ecc), dtype=np.float64)

    @property
    def periapsis_radius_km(self) -> FloatArray:
        """Periapsis radius ``r_p = p / (1 + e)``, km, from the Earth's centre."""
        return np.asarray(self._semi_latus_rectum_km / (1.0 + self._eccentricity), dtype=np.float64)

    @property
    def apoapsis_radius_km(self) -> FloatArray:
        """Apoapsis radius ``r_a = p / (1 - e)``, km, from the Earth's centre."""
        return np.asarray(self._semi_latus_rectum_km / (1.0 - self._eccentricity), dtype=np.float64)

    @property
    def argument_of_latitude_rad(self) -> FloatArray:
        """Angle from the ascending node to the satellite, ``u = omega + nu``.

        Well defined for any non-equatorial orbit, circular or not, which is why
        the circular convention folds ``argp`` into ``true_anomaly_rad``: that
        makes this sum correct in both cases without a branch.
        """
        return _wrap_two_pi(self._argp_rad + self._true_anomaly_rad)

    # -- degeneracy flags ---------------------------------------------------- #
    @property
    def is_circular(self) -> BoolArray:
        """True where the eccentricity is too small for a periapsis to be located.

        Where this holds and the elements came from :func:`rv_to_coe`,
        ``argp_rad`` is zero by convention and ``true_anomaly_rad`` carries the
        argument of latitude. See the module docstring.
        """
        return np.asarray(self._eccentricity < _DEGENERATE_TOLERANCE, dtype=np.bool_)

    @property
    def is_equatorial(self) -> BoolArray:
        """True where the orbit plane is too close to the equator to have a node.

        Tested on ``sin(i)``, not on ``i``, so a retrograde equatorial orbit
        (``i = pi``) is caught as well as a prograde one. Where this holds and
        the elements came from :func:`rv_to_coe`, ``raan_rad`` is zero by
        convention.
        """
        return np.asarray(
            np.abs(np.sin(self._inclination_rad)) < _DEGENERATE_TOLERANCE, dtype=np.bool_
        )

    def __len__(self) -> int:
        return self.n

    def __repr__(self) -> str:
        if self.n == 1:
            return (
                f"ClassicalElements(p_km={float(self._semi_latus_rectum_km[0]):.3f}, "
                f"e={float(self._eccentricity[0]):.6f}, "
                f"i={rad_to_deg(float(self._inclination_rad[0])):.4f} deg, "
                f"frame={self._frame}, type={self._element_type})"
            )
        return f"ClassicalElements(n={self.n}, frame={self._frame}, type={self._element_type})"


# --------------------------------------------------------------------------- #
# Elements <-> state
# --------------------------------------------------------------------------- #
def coe_to_rv(
    elements: ClassicalElements,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
) -> tuple[Vec3Array, Vec3Array]:
    """Convert classical elements to an inertial position and velocity.

    Parameters
    ----------
    elements : ClassicalElements
        The orbits to convert, which must be
        :attr:`ElementType.OSCULATING`. The result is expressed in
        ``elements.frame``.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.

    Returns
    -------
    r_km : Vec3Array
        Position, km, shape ``(n, 3)``.
    v_km_s : Vec3Array
        Velocity, km/s, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If ``mu`` is not positive, or if ``elements`` are not osculating.

    Notes
    -----
    **Why mean elements are refused here, and not only where they are consumed.**
    The obvious place to guard the osculating/mean distinction is
    :func:`~quoss.orbits.perturbations.secular_rates_j2`, which is the function
    whose theory needs mean elements. But the kilometres are lost on *this* side:
    an averaged rate fed osculating elements is wrong by the theory's own
    truncation error, ``O(J2)``, whereas a mean element set converted to a state
    as if it were osculating misplaces a 700 km sun-synchronous satellite by
    14.6 km after one revolution and 219 km after a day. Guarding only the first
    would leave the larger hole open, so both directions are closed.

    Vallado [1]_ Algorithm 10. Built from the perifocal basis vectors ``P``
    (towards periapsis) and ``Q`` (90 deg ahead of it in the orbit plane) rather
    than by assembling and applying a ``(n, 3, 3)`` rotation stack: same
    arithmetic, but it never materialises the matrices, which for a million-sample
    grid is 72 MB that no one needs.

    The degenerate conventions of :func:`rv_to_coe` need no special handling
    here. Only the sums ``omega + nu`` and ``Omega + omega`` reach the result, so
    folding an undefined angle into the next one leaves the state unchanged.

    Examples
    --------
    Vallado's worked COE2RV case:

    >>> import numpy as np
    >>> coe = ClassicalElements(
    ...     semi_latus_rectum_km=11067.790,
    ...     eccentricity=0.83285,
    ...     inclination_rad=np.deg2rad(87.87),
    ...     raan_rad=np.deg2rad(227.89),
    ...     argp_rad=np.deg2rad(53.38),
    ...     true_anomaly_rad=np.deg2rad(92.335),
    ... )
    >>> r_km, v_km_s = coe_to_rv(coe)
    >>> np.round(r_km, 3)
    array([[6525.368, 6861.532, 6449.119]])
    >>> np.round(v_km_s, 6)
    array([[ 4.902279,  5.53314 , -1.97571 ]])
    """
    if elements.element_type is not ElementType.OSCULATING:
        raise DomainError(
            f"coe_to_rv received {str(elements.element_type)!r} elements, and a state "
            f"vector is osculating by definition. Converting mean elements as though "
            f"they were osculating costs 14.6 km after one revolution and 219 km after "
            f"a day for a 700 km SSO, almost all of it along-track — a drift of about "
            f"2 s of orbital clock per revolution, not a bias that averages out. The "
            f"transformation that would make this legal is Brouwer-Lyddane short-period, "
            f"which QuOSS does not have: see docs/adr/0006-osculating-vs-mean-elements.md. "
            f"If you are deliberately measuring the mismatch, "
            f"ClassicalElements.relabelled_as is how you say so."
        )
    mu = _validated_mu(mu_km3_s2)
    p = elements.semi_latus_rectum_km
    ecc = elements.eccentricity
    cos_raan, sin_raan = np.cos(elements.raan_rad), np.sin(elements.raan_rad)
    cos_inc, sin_inc = np.cos(elements.inclination_rad), np.sin(elements.inclination_rad)
    cos_argp, sin_argp = np.cos(elements.argp_rad), np.sin(elements.argp_rad)
    cos_nu, sin_nu = np.cos(elements.true_anomaly_rad), np.sin(elements.true_anomaly_rad)

    # Perifocal basis expressed in the inertial frame [2, Sec. 2.6].
    basis_p = np.empty((elements.n, 3), dtype=np.float64)
    basis_p[:, 0] = cos_raan * cos_argp - sin_raan * sin_argp * cos_inc
    basis_p[:, 1] = sin_raan * cos_argp + cos_raan * sin_argp * cos_inc
    basis_p[:, 2] = sin_argp * sin_inc

    basis_q = np.empty((elements.n, 3), dtype=np.float64)
    basis_q[:, 0] = -cos_raan * sin_argp - sin_raan * cos_argp * cos_inc
    basis_q[:, 1] = -sin_raan * sin_argp + cos_raan * cos_argp * cos_inc
    basis_q[:, 2] = cos_argp * sin_inc

    radius_km = p / (1.0 + ecc * cos_nu)
    speed_scale = np.sqrt(mu / p)

    r_km = (radius_km * cos_nu)[:, np.newaxis] * basis_p + (radius_km * sin_nu)[
        :, np.newaxis
    ] * basis_q
    v_km_s = (-speed_scale * sin_nu)[:, np.newaxis] * basis_p + (speed_scale * (ecc + cos_nu))[
        :, np.newaxis
    ] * basis_q
    return r_km, v_km_s


def rv_to_coe(
    r_km: Vec3Array,
    v_km_s: Vec3Array,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
    frame: Frame = Frame.TEME,
) -> ClassicalElements:
    """Convert an inertial position and velocity to classical elements.

    Parameters
    ----------
    r_km : Vec3Array
        Position, km, shape ``(n, 3)``, in an inertial frame.
    v_km_s : Vec3Array
        Velocity, km/s, same shape.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.
    frame : Frame, optional
        The inertial frame the state is expressed in, carried through to the
        result. Defaults to :attr:`~quoss.orbits.frames.Frame.TEME`.

    Returns
    -------
    ClassicalElements
        The elements, labelled :attr:`ElementType.OSCULATING` — a state vector
        determines the tangent ellipse and nothing else. Every angle wrapped to
        ``[0, 2 pi)``. Degenerate cases
        follow the folding convention described in the module docstring and are
        reported by :attr:`ClassicalElements.is_circular` and
        :attr:`ClassicalElements.is_equatorial`.

    Raises
    ------
    DomainError
        If the shapes are invalid or mismatched, if a position is at the Earth's
        centre, if the angular momentum vanishes (a rectilinear trajectory), or
        if the specific orbital energy is not negative — that is, if the state
        is parabolic or hyperbolic rather than bound.

    Notes
    -----
    Vallado [1]_ Algorithm 9, with every angle recovered through
    :func:`numpy.arctan2` on an explicit sine and cosine pair rather than through
    ``arccos`` plus a quadrant test. The two agree, but ``arccos`` loses half its
    significant digits where its argument approaches ``+-1``, which is exactly
    where a near-equatorial or near-circular orbit sits. The sine terms come from
    triple products against the angular momentum, which fixes the quadrant
    without a separate branch.

    Examples
    --------
    Vallado's worked RV2COE case:

    >>> import numpy as np
    >>> r_km = np.array([[6524.834, 6862.875, 6448.296]])
    >>> v_km_s = np.array([[4.901327, 5.533756, -1.976341]])
    >>> coe = rv_to_coe(r_km, v_km_s)
    >>> float(np.round(coe.semi_latus_rectum_km[0], 3))
    11067.798
    >>> float(np.round(coe.eccentricity[0], 6))
    0.832853
    >>> float(np.round(np.rad2deg(coe.true_anomaly_rad[0]), 3))
    92.335
    """
    r = as_vec3("r_km", r_km)
    v = as_vec3("v_km_s", v_km_s)
    if r.shape != v.shape:
        raise DomainError(
            f"r_km has shape {r.shape} but v_km_s has {v.shape}; a state pair must be "
            f"sampled on the same axis."
        )
    mu = _validated_mu(mu_km3_s2)

    r_mag = np.linalg.norm(r, axis=1)
    v_mag = np.linalg.norm(v, axis=1)
    if np.any(r_mag == 0.0):
        raise DomainError("rv_to_coe received a position at the Earth's centre.")

    h_vec = np.cross(r, v)
    h_mag = np.linalg.norm(h_vec, axis=1)
    if np.any(h_mag == 0.0):
        raise DomainError(
            "rv_to_coe received a state with zero angular momentum: the position and "
            "velocity are parallel, which is a radial fall, not an orbit."
        )

    energy = 0.5 * v_mag * v_mag - mu / r_mag
    if np.any(energy >= 0.0):
        worst = float(np.max(energy))
        raise DomainError(
            f"rv_to_coe received an unbound state: specific orbital energy {worst:.6g} "
            f"km^2/s^2 is not negative, so the trajectory is parabolic or hyperbolic. "
            f"QuOSS models bound orbits only."
        )

    # Node vector n = z_hat x h, which lies along the line of nodes.
    node = np.empty_like(r)
    node[:, 0] = -h_vec[:, 1]
    node[:, 1] = h_vec[:, 0]
    node[:, 2] = 0.0
    node_mag = np.linalg.norm(node, axis=1)

    r_dot_v = np.einsum("ij,ij->i", r, v)
    ecc_vec = ((v_mag * v_mag - mu / r_mag)[:, np.newaxis] * r - r_dot_v[:, np.newaxis] * v) / mu
    ecc = np.linalg.norm(ecc_vec, axis=1)

    p_km = h_mag * h_mag / mu
    inc = np.arccos(np.clip(h_vec[:, 2] / h_mag, -1.0, 1.0))

    equatorial = node_mag < _DEGENERATE_TOLERANCE * h_mag
    circular = ecc < _DEGENERATE_TOLERANCE
    # Guard the divisions so the unused branches produce no warnings; the values
    # they compute are discarded by the np.where below.
    safe_node = np.where(equatorial, 1.0, node_mag)
    safe_ecc = np.where(circular, 1.0, ecc)
    prograde_sign = np.where(h_vec[:, 2] < 0.0, -1.0, 1.0)

    def _angle_between(first: Vec3Array, second: Vec3Array, scale: FloatArray) -> FloatArray:
        """Signed angle from ``first`` to ``second`` about the momentum vector."""
        cosine = np.einsum("ij,ij->i", first, second) / scale
        sine = np.einsum("ij,ij->i", np.cross(first, second), h_vec) / (scale * h_mag)
        return np.asarray(np.arctan2(sine, cosine), dtype=np.float64)

    raan = np.arctan2(node[:, 1], node[:, 0])
    argp = _angle_between(node, ecc_vec, safe_node * safe_ecc)
    nu = _angle_between(ecc_vec, r, safe_ecc * r_mag)

    # Argument of latitude: node to satellite. Replaces nu when there is no
    # periapsis to measure from.
    arg_lat = _angle_between(node, r, safe_node * r_mag)
    # Longitude of periapsis and true longitude, both measured from the inertial
    # x axis in the orbit plane. The sign flip keeps a retrograde equatorial orbit
    # increasing in the direction it actually travels.
    lon_periapsis = np.arctan2(prograde_sign * ecc_vec[:, 1], ecc_vec[:, 0])
    true_longitude = np.arctan2(prograde_sign * r[:, 1], r[:, 0])

    raan = np.where(equatorial, 0.0, raan)
    argp = np.where(equatorial, lon_periapsis, argp)
    argp = np.where(circular, 0.0, argp)
    nu = np.where(circular, np.where(equatorial, true_longitude, arg_lat), nu)

    return ClassicalElements(
        semi_latus_rectum_km=p_km,
        eccentricity=ecc,
        inclination_rad=inc,
        raan_rad=raan,
        argp_rad=argp,
        true_anomaly_rad=nu,
        frame=frame,
        # Not the default by accident: a state vector describes the ellipse
        # tangent to the path right now, so these can only be osculating. Stated
        # explicitly so the one place that mints the label is greppable.
        element_type=ElementType.OSCULATING,
    )
