"""Zonal gravity: the departure from the two-body field.

:mod:`quoss.orbits.kepler` solves the ideal problem, where the Earth is a point
mass. It is not. The equatorial bulge is ~1e-3 of the central term and it is what
makes a sun-synchronous orbit possible, what turns a ground track into something
that repeats, and what moves a LEO's node by several degrees a day — an effect a
link-budget study cannot round away over a multi-day scenario.

This module holds the two ways of accounting for it, and they check each other:

============================  ==============================================
:func:`zonal_acceleration`    The **exact** force, J2/J3/J4, as a closed-form
                              gradient of the zonal potential. No averaging, no
                              approximation beyond truncating the expansion.
:func:`secular_rates_j2`      The **averaged** description: the rates at which
                              J2 drags the node, the perigee and the mean
                              anomaly. First order, closed form, no integration.
:func:`propagate_zonal`       The numerical bridge: integrate the exact force
                              and see whether the averaged rates were right.
============================  ==============================================

The third is what makes the second trustworthy. See
``docs/adr/0004-zonal-perturbations.md``.

What is here, and what is deliberately not
------------------------------------------
The secular rates are **first order in J2 only**. The second-order terms —
``J2^2`` and ``J4``, both ~1e-6 relative — are *not* implemented, and the reason
is measured rather than assumed:

* A first-order secular rate is a statement about **mean** elements. The
  difference between a mean and an osculating element is itself ``O(J2)``, i.e.
  ~1e-3 relative — a thousand times larger than the second-order correction
  would be.
* Converting between the two requires the Brouwer-Lyddane short-period
  transformation, which this project does not have and which
  ``docs/adr/0003-orbital-elements.md`` explicitly warns against faking.
* So nothing QuOSS runs today can tell a correct second-order formula from a
  mistyped one. Adding it would mean shipping unvalidated code whose whole
  purpose is a correction smaller than the error already present in its inputs.

The first-order rates, by contrast, are validated to their own truncation error:
the residual against a DOP853 integration of the exact force is **exactly
proportional to J2** (measured: the ratio residual/J2 is constant to four
significant figures as J2 is scaled down by 8x). A wrong coefficient would leave
a residual independent of J2. See ``tests/orbits/test_perturbations.py``.

J3 has no first-order secular term
----------------------------------
This is not a simplification, it is a fact about odd zonal harmonics, and it is
the one thing in this module most likely to be reintroduced by mistake — the
previous codebase shipped a "secular" J3 rate whose own docstring admitted the
term does not exist. What J3 produces is a **long-period** term, and the
distinction is measurable: the J3 contribution to the node rate is proportional
to ``sin(omega)``, so it vanishes at ``omega = 0`` and ``omega = pi``, reverses
sign between ``omega = pi/2`` and ``omega = 3 pi/2``, and averages to zero over
one apsidal cycle. A secular term would do none of those things.

J3 therefore appears in :func:`zonal_acceleration`, where it belongs and where it
is exact, and nowhere in :func:`secular_rates_j2`.

Mean elements versus osculating elements
----------------------------------------
A first-order secular rate is a statement about **mean** elements, so
:func:`secular_rates_j2` requires
:attr:`~quoss.orbits.kepler.ElementType.MEAN_BROUWER` and raises
:class:`~quoss.core.errors.DomainError` on anything else. It used to accept
whatever it was handed, with a docstring explaining that osculating elements cost
``O(J2)``; a documented hazard is one a reader has to already know about, and
this one is invisible in the output — the rates come back finite, plausible, and
wrong by the same size as the theory's own truncation error.

Nothing in QuOSS produces mean elements yet: the Brouwer-Lyddane short-period
transformation is not implemented, and
``docs/adr/0003-orbital-elements.md`` warns against faking it. So today the
requirement is a gate rather than a step, and the two ways through it are stating
mean elements by hand (a scenario that says what it holds) or
:meth:`~quoss.orbits.kepler.ClassicalElements.relabelled_as`, which converts
nothing and exists so that the tests measuring the mismatch have to admit that is
what they are doing. See ``docs/adr/0006-osculating-vs-mean-elements.md``.

Conventions in force
--------------------
Distances in km, angles in radians, ``mu`` in km^3/s^2, per
``docs/adr/0001-unit-conventions.md``. Zonal harmonics are dimensionless and are
defined relative to the reference radius of the model they came from, which is
why :class:`ZonalGravity` carries the radius alongside them instead of reaching
for a global.

No function here takes a :class:`~quoss.core.errors.DegradationLog`. The
truncation of the expansion and the order of the secular theory are fixed model
choices, not runtime decisions, so by the rule in
``docs/adr/0002-frames-and-time-scales.md`` they are documented rather than
logged. Bad input raises.

References
----------
.. [1] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed., 2013.
       Sections 8.6 (the geopotential) and 9.6 (secular rates).
.. [2] Brouwer, "Solution of the problem of artificial satellite theory without
       drag", *Astronomical Journal* 64, 378-397, 1959. The mean-element theory
       whose first-order secular terms this module implements, and whose
       short-period transformation it does not.
.. [3] Kozai, "The motion of a close earth satellite", *Astronomical Journal* 64,
       367-377, 1959.
.. [4] Montenbruck & Gill, *Satellite Orbits*, Springer, 2000, Section 3.2.
       The zonal potential and its Cartesian gradient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np
from scipy.integrate import solve_ivp

from quoss.core.constants import (
    EGM96_J2,
    EGM96_J3,
    EGM96_J4,
    EGM96_MU_KM3_S2,
    EGM96_RADIUS_EQUATORIAL_KM,
    WGS72_J2,
    WGS72_J3,
    WGS72_J4,
    WGS72_MU_KM3_S2,
    WGS72_RADIUS_EQUATORIAL_KM,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import FloatArray, FloatLike, Vec3Array
from quoss.orbits._validation import as_1d, as_vec3
from quoss.orbits.kepler import ClassicalElements, ElementType

__all__ = [
    "CRITICAL_INCLINATION_RAD",
    "DEFAULT_ZONAL_ATOL_KM",
    "DEFAULT_ZONAL_RTOL",
    "EGM96_ZONAL",
    "WGS72_ZONAL",
    "SecularRates",
    "ZonalGravity",
    "gravitational_acceleration",
    "propagate_zonal",
    "secular_rates_j2",
    "two_body_acceleration",
    "zonal_acceleration",
]

_TWO_PI: Final = 2.0 * np.pi

CRITICAL_INCLINATION_RAD: Final = float(np.arcsin(np.sqrt(0.8)))
"""Inclination at which the first-order apsidal drift vanishes, ~63.4349 deg.

``argp_dot`` carries a factor ``4 - 5 sin^2 i``, so it is zero at
``sin^2 i = 4/5`` and at its retrograde mirror ``pi - i``. Molniya orbits are
flown here precisely so that apogee stays over the same hemisphere for years.

For QuOSS the value matters in the other direction: near it the *relative*
accuracy of :func:`secular_rates_j2`'s ``argp_dot`` collapses, because a small
absolute error sits next to a vanishing quantity. Nothing breaks — the absolute
error is unchanged — but a test that asserts a relative bound on ``argp_dot``
must stay away from this inclination, and a scenario that sits on it should not
be surprised that the second-order terms this module omits are what actually
governs the drift there.
"""


# --------------------------------------------------------------------------- #
# The force model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class ZonalGravity:
    """A zonal gravity model: ``mu``, a reference radius, and the harmonics.

    The three travel together because a zonal harmonic has no meaning without
    the radius its expansion was referred to: every term multiplies
    ``(r_equatorial_km / r)^n``. Mixing EGM96 harmonics with the WGS-84 radius,
    or WGS-72 harmonics with the EGM96 ``mu``, produces a model that is not any
    published model — the failure mode :mod:`quoss.core.constants` warns about,
    made unrepresentable by keeping the set in one object.

    Use :data:`EGM96_ZONAL` unless the work is TLE-consistent, in which case use
    :data:`WGS72_ZONAL`.

    Parameters
    ----------
    mu_km3_s2 : float
        Gravitational parameter GM, km^3/s^2. Must be finite and positive.
    r_equatorial_km : float
        Reference equatorial radius of the expansion, km. Must be finite and
        positive.
    j2, j3, j4 : float, optional
        Zonal harmonic coefficients, dimensionless, in the sign convention where
        the potential carries ``-J_n (R/r)^n P_n(sin phi)``. Any may be zero,
        which removes that term exactly; that is how a pure two-body or
        J2-only model is expressed.

    Raises
    ------
    DomainError
        If ``mu_km3_s2`` or ``r_equatorial_km`` is not finite and positive, or if
        any harmonic is not finite.

    Examples
    --------
    >>> EGM96_ZONAL.j2
    0.00108262668
    >>> j2_only = ZonalGravity(
    ...     mu_km3_s2=EGM96_ZONAL.mu_km3_s2,
    ...     r_equatorial_km=EGM96_ZONAL.r_equatorial_km,
    ...     j2=EGM96_ZONAL.j2,
    ... )
    >>> j2_only.j3, j2_only.j4
    (0.0, 0.0)
    """

    mu_km3_s2: float
    r_equatorial_km: float
    j2: float = 0.0
    j3: float = 0.0
    j4: float = 0.0

    def __post_init__(self) -> None:
        """Validate the model parameters."""
        for name, value in (
            ("mu_km3_s2", self.mu_km3_s2),
            ("r_equatorial_km", self.r_equatorial_km),
        ):
            if not (np.isfinite(value) and value > 0.0):
                raise DomainError(f"{name} must be finite and positive, got {value!r}.")
        for name, value in (("j2", self.j2), ("j3", self.j3), ("j4", self.j4)):
            if not np.isfinite(value):
                raise DomainError(f"{name} must be finite, got {value!r}.")


EGM96_ZONAL: Final = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
    j2=EGM96_J2,
    j3=EGM96_J3,
    j4=EGM96_J4,
)
"""EGM96 zonal set. The default for every propagation that is not a TLE."""

WGS72_ZONAL: Final = ZonalGravity(
    mu_km3_s2=WGS72_MU_KM3_S2,
    r_equatorial_km=WGS72_RADIUS_EQUATORIAL_KM,
    j2=WGS72_J2,
    j3=WGS72_J3,
    j4=WGS72_J4,
)
"""WGS-72 zonal set, for work that must stay consistent with SGP4.

Less accurate than :data:`EGM96_ZONAL` on purpose: a TLE is *fitted* with these
constants, so a propagation meant to agree with one must use them too. See
:mod:`quoss.core.constants`.
"""


# --------------------------------------------------------------------------- #
# Legendre polynomials of the sine of latitude, and their derivatives
#
# Written out rather than recursed. Three degrees is not enough to pay for a
# recurrence, and the closed forms can be read against any reference at a glance,
# which a recurrence cannot.
# --------------------------------------------------------------------------- #
def _legendre(degree: int, sin_lat: FloatArray) -> tuple[FloatArray, FloatArray]:
    """Return ``(P_n(s), dP_n/ds)`` for ``n`` in 2..4.

    Parameters
    ----------
    degree : int
        Degree ``n``, one of 2, 3, 4.
    sin_lat : FloatArray
        Sine of the geocentric latitude, ``z / |r|``.

    Returns
    -------
    value : FloatArray
        ``P_n(s)``.
    derivative : FloatArray
        ``dP_n/ds``.

    Raises
    ------
    ValueError
        If the degree is outside 2..4. Not a ``DomainError``: this is a private
        helper and reaching it with another degree is a programming error, not a
        user-facing one.
    """
    s2 = sin_lat * sin_lat
    if degree == 2:
        return 0.5 * (3.0 * s2 - 1.0), 3.0 * sin_lat
    if degree == 3:
        return 0.5 * sin_lat * (5.0 * s2 - 3.0), 1.5 * (5.0 * s2 - 1.0)
    if degree == 4:
        return (35.0 * s2 * s2 - 30.0 * s2 + 3.0) / 8.0, 2.5 * sin_lat * (7.0 * s2 - 3.0)
    raise ValueError(f"_legendre supports degrees 2..4, got {degree}.")


def _validated_positions(r_km: Vec3Array, r_equatorial_km: float) -> tuple[Vec3Array, FloatArray]:
    """Return validated positions and their magnitudes.

    Parameters
    ----------
    r_km : Vec3Array
        Positions, km, shape ``(n, 3)``.
    r_equatorial_km : float
        Reference radius, km. Positions at or inside it are rejected.

    Returns
    -------
    r : Vec3Array
        The validated positions.
    r_mag : FloatArray
        Their magnitudes, km.

    Raises
    ------
    DomainError
        If the shape is invalid, a value is not finite, or a position lies at or
        inside the reference radius.
    """
    r = as_vec3("r_km", r_km)
    r_mag = np.linalg.norm(r, axis=1)
    if np.any(r_mag <= r_equatorial_km):
        raise DomainError(
            f"r_km contains a position at or inside the reference radius "
            f"({float(np.min(r_mag)):.3f} km <= {r_equatorial_km:.3f} km). The spherical "
            f"harmonic expansion does not converge there, and a satellite is not there. "
            f"The usual cause is a position given in metres."
        )
    return r, np.asarray(r_mag, dtype=np.float64)


def two_body_acceleration(
    r_km: Vec3Array,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
) -> Vec3Array:
    """Point-mass acceleration ``-mu r / |r|^3``, km/s^2.

    The central term, on its own. Kept separate from
    :func:`zonal_acceleration` because the two differ by three orders of
    magnitude, and a test that compares them term by term is what shows the
    perturbation is a perturbation.

    Parameters
    ----------
    r_km : Vec3Array
        Position, km, shape ``(n, 3)``. A single ``(3,)`` vector is promoted.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.

    Returns
    -------
    Vec3Array
        Acceleration, km/s^2, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If the shape is invalid, a value is not finite, ``mu`` is not positive,
        or a position is at the Earth's centre.

    Examples
    --------
    Surface gravity comes out where it should, ~9.8 m/s^2:

    >>> import numpy as np
    >>> a = two_body_acceleration(np.array([6378.137, 0.0, 0.0]))
    >>> float(np.round(np.linalg.norm(a) * 1e3, 3))
    9.798
    """
    if not (np.isfinite(mu_km3_s2) and mu_km3_s2 > 0.0):
        raise DomainError(f"mu_km3_s2 must be finite and positive, got {mu_km3_s2!r}.")
    r = as_vec3("r_km", r_km)
    r_mag = np.linalg.norm(r, axis=1)
    if np.any(r_mag == 0.0):
        raise DomainError("two_body_acceleration received a position at the Earth's centre.")
    return np.asarray(-mu_km3_s2 * r / (r_mag**3)[:, np.newaxis], dtype=np.float64)


def zonal_acceleration(
    r_km: Vec3Array,
    gravity: ZonalGravity = EGM96_ZONAL,
) -> Vec3Array:
    r"""Perturbing acceleration of the zonal harmonics, km/s^2.

    The **perturbation only**: the central ``-mu r / |r|^3`` term is not
    included. For the whole field use :func:`gravitational_acceleration`.

    Parameters
    ----------
    r_km : Vec3Array
        Position, km, shape ``(n, 3)``, in an Earth-fixed *or* inertial frame —
        see the note below. A single ``(3,)`` vector is promoted.
    gravity : ZonalGravity, optional
        The model. Defaults to :data:`EGM96_ZONAL`.

    Returns
    -------
    Vec3Array
        Acceleration, km/s^2, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If the shape is invalid, a value is not finite, or a position lies at or
        inside ``gravity.r_equatorial_km``.

    Notes
    -----
    A zonal field is axially symmetric, so it does not rotate with the Earth: the
    same expression is valid in ITRF and in TEME, and no frame argument is
    needed. That symmetry is exactly what fails the moment a tesseral harmonic
    (``J22``, the term that drives geostationary station-keeping) enters, which
    is why this module is named for the zonal set and not for "gravity".

    The acceleration is the gradient of

    .. math:: U = \frac{\mu}{r}\left[1 - \sum_n J_n (R/r)^n P_n(s)\right],
        \qquad s = z/r

    taken in closed form. Writing ``rhat = r/|r|``, one differentiation of the
    chain ``P_n(z/r)`` gives a single expression covering every degree:

    .. math:: a_n = \frac{\mu J_n R^n}{r^{n+2}}
        \left\{ \left[(n+1)P_n(s) + s P_n'(s)\right]\hat{r}
        - P_n'(s)\,\hat{z} \right\}

    Expanded at ``n = 2`` this is the familiar Cartesian J2 formula; the point of
    keeping the general form is that J3 and J4 then cost a Legendre polynomial
    each instead of three hand-transcribed component expressions each, which is
    where sign errors live. ``tests/orbits/test_perturbations.py`` checks it
    against both a numerical gradient of ``U`` and the transcribed textbook
    components.

    Examples
    --------
    At 700 km the J2 perturbation is about 1e-3 of the central term:

    >>> import numpy as np
    >>> r_km = np.array([7078.137, 0.0, 0.0])
    >>> ratio = np.linalg.norm(zonal_acceleration(r_km)) / np.linalg.norm(
    ...     two_body_acceleration(r_km)
    ... )
    >>> float(np.round(ratio * 1e3, 3))
    1.321

    Over the equator the perturbation points straight down; over the pole it also
    points along the radius, and the two differ in sign:

    >>> equator = float(zonal_acceleration(np.array([7078.137, 0.0, 0.0]))[0, 0])
    >>> pole = float(zonal_acceleration(np.array([0.0, 0.0, 7078.137]))[0, 2])
    >>> equator < 0.0 < pole
    True
    """
    r, r_mag = _validated_positions(r_km, gravity.r_equatorial_km)
    sin_lat = r[:, 2] / r_mag

    out = np.zeros_like(r)
    for degree, coefficient in ((2, gravity.j2), (3, gravity.j3), (4, gravity.j4)):
        # A zero coefficient contributes exactly zero, so skipping it changes no
        # number; it only avoids the arithmetic for a two-body or J2-only model.
        if coefficient == 0.0:
            continue
        value, derivative = _legendre(degree, sin_lat)
        prefactor = (
            gravity.mu_km3_s2
            * coefficient
            * gravity.r_equatorial_km**degree
            / r_mag ** (degree + 2)
        )
        radial = prefactor * ((degree + 1) * value + sin_lat * derivative)
        out += (radial / r_mag)[:, np.newaxis] * r
        out[:, 2] -= prefactor * derivative
    return out


def gravitational_acceleration(
    r_km: Vec3Array,
    gravity: ZonalGravity = EGM96_ZONAL,
) -> Vec3Array:
    """Total gravitational acceleration: point mass plus zonal harmonics, km/s^2.

    What :func:`propagate_zonal` integrates.

    Parameters
    ----------
    r_km : Vec3Array
        Position, km, shape ``(n, 3)``.
    gravity : ZonalGravity, optional
        The model. Defaults to :data:`EGM96_ZONAL`.

    Returns
    -------
    Vec3Array
        Acceleration, km/s^2, shape ``(n, 3)``.

    Raises
    ------
    DomainError
        If the shape is invalid, a value is not finite, or a position lies at or
        inside ``gravity.r_equatorial_km``.

    Examples
    --------
    >>> import numpy as np
    >>> a = gravitational_acceleration(np.array([7078.137, 0.0, 0.0]))
    >>> float(np.round(np.linalg.norm(a) * 1e3, 4))
    7.9666
    """
    return np.asarray(
        two_body_acceleration(r_km, gravity.mu_km3_s2) + zonal_acceleration(r_km, gravity),
        dtype=np.float64,
    )


# --------------------------------------------------------------------------- #
# First-order secular theory
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SecularRates:
    """The three angles J2 drives, and the two periods that follow from them.

    Returned by :func:`secular_rates_j2`. Every field is a 1-D array of the
    length of the elements it came from, so a stack of orbits reads the same as
    one.

    Parameters
    ----------
    raan_rad_s : FloatArray
        ``dOmega/dt``, rad/s. Negative for a prograde orbit: the node regresses.
    argp_rad_s : FloatArray
        ``domega/dt``, rad/s. Changes sign at
        :data:`CRITICAL_INCLINATION_RAD`.
    mean_anomaly_rad_s : FloatArray
        ``dM/dt``, rad/s. The two-body mean motion plus its J2 correction, so it
        is *not* ``sqrt(mu/a^3)``.
    """

    raan_rad_s: FloatArray
    argp_rad_s: FloatArray
    mean_anomaly_rad_s: FloatArray

    @property
    def n(self) -> int:
        """Number of orbits held."""
        return int(self.raan_rad_s.size)

    @property
    def anomalistic_period_s(self) -> FloatArray:
        """Perigee to perigee, ``2 pi / (dM/dt)``, seconds.

        Shorter than the Keplerian period for a low-inclination orbit and longer
        for a high-inclination one, by a few seconds at LEO.
        """
        return np.asarray(_TWO_PI / self.mean_anomaly_rad_s, dtype=np.float64)

    @property
    def nodal_period_s(self) -> FloatArray:
        """Ascending node to ascending node, ``2 pi / (dM/dt + domega/dt)``, s.

        The period a ground track actually repeats on, and therefore the one
        repeat-track and revisit design uses. It differs from the Keplerian
        period by a few seconds at LEO — which is minutes of along-track error
        after a day, hence its own name rather than a footnote.
        """
        return np.asarray(_TWO_PI / (self.mean_anomaly_rad_s + self.argp_rad_s), dtype=np.float64)

    def __len__(self) -> int:
        return self.n

    def __repr__(self) -> str:
        if self.n == 1:
            return (
                f"SecularRates(raan={float(self.raan_rad_s[0]):.6e} rad/s, "
                f"argp={float(self.argp_rad_s[0]):.6e} rad/s, "
                f"M={float(self.mean_anomaly_rad_s[0]):.6e} rad/s)"
            )
        return f"SecularRates(n={self.n})"


def secular_rates_j2(
    elements: ClassicalElements,
    *,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
    r_equatorial_km: float = EGM96_RADIUS_EQUATORIAL_KM,
    j2: float = EGM96_J2,
) -> SecularRates:
    r"""First-order J2 secular rates of the node, the perigee and the anomaly.

    .. math::

        \dot{\Omega} &= -\tfrac{3}{2}\,n J_2 (R/p)^2 \cos i \\
        \dot{\omega} &= \tfrac{3}{4}\,n J_2 (R/p)^2 (4 - 5\sin^2 i) \\
        \dot{M} &= n + \tfrac{3}{4}\,n J_2 (R/p)^2 \sqrt{1-e^2}
                    (2 - 3\sin^2 i)

    with ``n = sqrt(mu/a^3)`` and ``p`` the semi-latus rectum, which is the
    element :class:`~quoss.orbits.kepler.ClassicalElements` stores, so no
    intermediate conversion happens here.

    The parameters are taken one at a time rather than as a
    :class:`ZonalGravity`, and that is on purpose: this model uses J2 and only
    J2. Accepting an object carrying J3 and J4 and then ignoring them would be a
    silent model substitution, which is the thing
    :mod:`quoss.core.errors` exists to prevent. A caller holding a
    :class:`ZonalGravity` writes ``j2=gravity.j2``, and the crossing is
    greppable.

    Parameters
    ----------
    elements : ClassicalElements
        The orbits, which must be
        :attr:`~quoss.orbits.kepler.ElementType.MEAN_BROUWER`. Osculating
        elements are rejected rather than silently costing ``O(J2)``; see the
        module docstring and
        :meth:`~quoss.orbits.kepler.ClassicalElements.relabelled_as`.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.
    r_equatorial_km : float, optional
        Reference radius of the J2 coefficient, km. Defaults to the EGM96
        radius, which is the one ``EGM96_J2`` is referred to.
    j2 : float, optional
        Second zonal harmonic, dimensionless. Defaults to EGM96. Passing zero
        returns the pure two-body rates, which is a legitimate way to ask for
        them and is what makes the J2 dependence testable.

    Returns
    -------
    SecularRates
        The three rates, and the two periods derived from them.

    Raises
    ------
    DomainError
        If ``elements`` are not mean elements, if ``mu_km3_s2`` or
        ``r_equatorial_km`` is not finite and positive, or ``j2`` is not finite.

    Notes
    -----
    The signs are worth reading once. For a prograde orbit ``cos i > 0`` so the
    node **regresses** — a sun-synchronous orbit inverts this by going
    retrograde, which is why every SSO is inclined near 98 deg rather than 82.
    ``argp_dot`` vanishes at :data:`CRITICAL_INCLINATION_RAD` and reverses past
    it. ``mean_anomaly_dot`` exceeds ``n`` below ``i = 54.7 deg`` and falls short
    of it above.

    Examples
    --------
    A 700 km sun-synchronous orbit turns its node by very nearly one degree a
    day, which is what keeps its local solar time fixed:

    >>> import numpy as np
    >>> from quoss.orbits.kepler import ClassicalElements, ElementType
    >>> sso = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=np.deg2rad(98.19),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ...     element_type=ElementType.MEAN_BROUWER,
    ... )
    >>> rates = secular_rates_j2(sso)
    >>> float(np.round(np.rad2deg(rates.raan_rad_s[0]) * 86400.0, 4))
    0.9859

    The node of the ISS, by contrast, regresses about 5 degrees a day:

    >>> iss = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=6798.0,
    ...     eccentricity=0.0005,
    ...     inclination_rad=np.deg2rad(51.6),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ...     element_type=ElementType.MEAN_BROUWER,
    ... )
    >>> float(np.round(np.rad2deg(secular_rates_j2(iss).raan_rad_s[0]) * 86400.0, 3))
    -4.951

    Handing it the osculating elements a state vector gives is refused, not
    absorbed into the truncation error:

    >>> from quoss.core.errors import DomainError
    >>> try:
    ...     secular_rates_j2(sso.relabelled_as(ElementType.OSCULATING))
    ... except DomainError as exc:
    ...     print(str(exc).split(",")[0])
    secular_rates_j2 received 'osculating' elements
    """
    if elements.element_type is not ElementType.MEAN_BROUWER:
        raise DomainError(
            f"secular_rates_j2 received {str(elements.element_type)!r} elements, and a "
            f"first-order secular rate is a statement about mean ones. The gap between "
            f"the two is itself O(J2), ~1e-3 relative — the same size as this theory's "
            f"own truncation error, so the answer would be finite, plausible and wrong "
            f"by as much as the model. QuOSS has no Brouwer-Lyddane transformation to "
            f"convert them (docs/adr/0006-osculating-vs-mean-elements.md); state mean "
            f"elements as such, or use ClassicalElements.relabelled_as if you are "
            f"deliberately measuring what not converting costs."
        )
    for name, value in (("mu_km3_s2", mu_km3_s2), ("r_equatorial_km", r_equatorial_km)):
        if not (np.isfinite(value) and value > 0.0):
            raise DomainError(f"{name} must be finite and positive, got {value!r}.")
    if not np.isfinite(j2):
        raise DomainError(f"j2 must be finite, got {j2!r}.")

    p_km = elements.semi_latus_rectum_km
    ecc = elements.eccentricity
    inc = elements.inclination_rad
    axis_km = elements.semi_major_axis_km

    mean_motion = np.sqrt(mu_km3_s2 / axis_km**3)
    # The factor every rate shares: n J2 (R/p)^2, dimension rad/s.
    scale = mean_motion * j2 * (r_equatorial_km / p_km) ** 2
    sin_inc_sq = np.sin(inc) ** 2

    return SecularRates(
        raan_rad_s=np.asarray(-1.5 * scale * np.cos(inc), dtype=np.float64),
        argp_rad_s=np.asarray(0.75 * scale * (4.0 - 5.0 * sin_inc_sq), dtype=np.float64),
        mean_anomaly_rad_s=np.asarray(
            mean_motion + 0.75 * scale * np.sqrt(1.0 - ecc * ecc) * (2.0 - 3.0 * sin_inc_sq),
            dtype=np.float64,
        ),
    )


# --------------------------------------------------------------------------- #
# Numerical integration of the exact force
# --------------------------------------------------------------------------- #
DEFAULT_ZONAL_RTOL: Final = 1e-12
"""Relative tolerance of the integrator.

Three orders below the 1e-9 (a nanometre at LEO) at which results are compared,
so the integration is never the limiting error. DOP853 reaches it in about 250
function evaluations per revolution, which is cheap enough to keep in CI.

Public, not private, because :mod:`quoss.orbits.propagator` forwards these to
:func:`propagate_zonal` and a second copy of the number in a second module is a
number that drifts.
"""

DEFAULT_ZONAL_ATOL_KM: Final = 1e-9
"""Absolute tolerance, km. A nanometre: below any physical quantity here."""


def propagate_zonal(
    r0_km: Vec3Array,
    v0_km_s: Vec3Array,
    dt_s: FloatLike,
    gravity: ZonalGravity = EGM96_ZONAL,
    *,
    rtol: float = DEFAULT_ZONAL_RTOL,
    atol_km: float = DEFAULT_ZONAL_ATOL_KM,
) -> tuple[Vec3Array, Vec3Array]:
    """Integrate one state through the zonal field with DOP853.

    The reference implementation of this module: it makes no secular, averaged
    or first-order assumption, so it is what :func:`secular_rates_j2` is measured
    against. It is also, deliberately, the slow way to propagate — an eighth
    order Runge-Kutta stepping a single orbit, not a vectorised expression over a
    time grid. Choosing between the two, and wrapping this in frames and time
    grids, is ``orbits/propagator.py``'s job.

    **One state in, one trajectory out.** An ODE has to be integrated per orbit,
    so there is no stack of initial conditions to broadcast over; a constellation
    is a loop, and the loop belongs to the caller who knows how to parallelise
    it.

    Parameters
    ----------
    r0_km : Vec3Array
        Initial position, km, shape ``(3,)`` or ``(1, 3)``, in an inertial frame.
    v0_km_s : Vec3Array
        Initial velocity, km/s, same shape.
    dt_s : float or FloatArray
        Elapsed seconds from the initial state, at which the trajectory is
        wanted. Strictly increasing. May be negative, positive or both: the
        integration runs outwards from ``t = 0`` in whichever directions are
        asked for, so an epoch in the middle of the grid — what a TLE gives —
        needs no special handling from the caller.
    gravity : ZonalGravity, optional
        The model. Defaults to :data:`EGM96_ZONAL`.
    rtol : float, optional
        Relative tolerance handed to the integrator. Defaults to
        :data:`DEFAULT_ZONAL_RTOL`.
    atol_km : float, optional
        Absolute tolerance, km. Defaults to :data:`DEFAULT_ZONAL_ATOL_KM`.

    Returns
    -------
    r_km : Vec3Array
        Positions, km, shape ``(len(dt_s), 3)``.
    v_km_s : Vec3Array
        Velocities, km/s, same shape.

    Raises
    ------
    DomainError
        If the shapes are invalid or mismatched, if more than one initial state
        is given, if ``dt_s`` is not strictly increasing, if the tolerances are
        not positive, or if the initial position lies at or inside
        ``gravity.r_equatorial_km``.
    ConvergenceError
        If the integrator fails, which for a bound orbit means the state left the
        domain of the force model — typically an orbit that decayed into the
        Earth because the initial state was not the one the caller meant.

    Notes
    -----
    Determinism is a requirement, not a nicety: this function is a test oracle,
    so its accuracy has to be set by an explicit argument rather than by a
    library default that a version bump could change. That is the third condition
    in ``tests/golden/README.md`` for an oracle that need not be frozen to a
    file, and it is why ``rtol`` and ``atol_km`` are parameters with stated
    values instead of being left to SciPy.

    Examples
    --------
    Start from a state that is *circular* in the two-body sense and run half a
    revolution. Two-body would return the same radius on the far side; the zonal
    field returns 11 km less, which is the short-period oscillation J2 imposes on
    an orbit whose elements were set as though the Earth were a sphere:

    >>> import numpy as np
    >>> from quoss.orbits.kepler import ClassicalElements, coe_to_rv, orbital_period_s
    >>> coe = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.0,
    ...     inclination_rad=np.deg2rad(51.6),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ... )
    >>> r0, v0 = coe_to_rv(coe)
    >>> half = float(orbital_period_s(7078.137)[0]) / 2.0
    >>> r_km, v_km_s = propagate_zonal(r0[0], v0[0], np.array([half]))
    >>> r_km.shape
    (1, 3)
    >>> float(np.round(np.linalg.norm(r_km[0]), 3))
    7067.129

    That 11 km is a real displacement, not decay: it is why "circular" has to
    mean *mean*-circular before an altitude in a scenario means anything.
    """
    if not (np.isfinite(rtol) and rtol > 0.0):
        raise DomainError(f"rtol must be finite and positive, got {rtol!r}.")
    if not (np.isfinite(atol_km) and atol_km > 0.0):
        raise DomainError(f"atol_km must be finite and positive, got {atol_km!r}.")

    r0 = as_vec3("r0_km", r0_km)
    v0 = as_vec3("v0_km_s", v0_km_s)
    if r0.shape != v0.shape:
        raise DomainError(
            f"r0_km has shape {r0.shape} but v0_km_s has {v0.shape}; a state pair must "
            f"describe the same orbit."
        )
    if r0.shape[0] != 1:
        raise DomainError(
            f"propagate_zonal integrates one orbit at a time, got {r0.shape[0]} initial "
            f"states. An ODE cannot be broadcast: loop over the orbits."
        )
    _validated_positions(r0, gravity.r_equatorial_km)

    times = as_1d("dt_s", dt_s)
    if times.size > 1 and not np.all(np.diff(times) > 0.0):
        raise DomainError(
            "dt_s must be strictly increasing; a repeated or out-of-order sample would "
            "make the returned trajectory ambiguous."
        )

    state0 = np.concatenate([r0[0], v0[0]])

    def _rhs(_t: float, state: FloatArray) -> FloatArray:
        """State derivative: velocity, then acceleration."""
        acceleration = gravitational_acceleration(state[np.newaxis, :3], gravity)[0]
        return np.concatenate([state[3:], acceleration])

    out = np.empty((times.size, 6), dtype=np.float64)
    # A sample at the epoch is the initial state, exactly. It is written straight
    # in rather than integrated: SciPy reports success on a zero-length span and
    # returns no samples at all, so asking it for t = 0 would silently leave a
    # row of this array uninitialised.
    out[times == 0.0] = state0

    # Integrate outwards from the epoch in each direction that was asked for.
    # Running forwards through a negative sample would mean starting the
    # trajectory somewhere the caller never specified.
    for backwards in (True, False):
        mask = times < 0.0 if backwards else times > 0.0
        if not np.any(mask):
            continue
        wanted = times[mask]
        # SciPy requires t_eval ordered along the direction of travel, which for
        # a backwards run is descending.
        ordered = wanted[::-1] if backwards else wanted
        solution = solve_ivp(
            _rhs,
            (0.0, float(ordered[-1])),
            state0,
            method="DOP853",
            t_eval=ordered,
            rtol=rtol,
            atol=atol_km,
        )
        if not solution.success:
            raise ConvergenceError(
                f"DOP853 failed to integrate the zonal field: {solution.message} "
                f"The usual cause is a state that decays into the Earth, where the "
                f"expansion stops converging."
            )
        values = np.asarray(solution.y, dtype=np.float64).T
        out[mask] = values[::-1] if backwards else values

    return out[:, :3], out[:, 3:]
