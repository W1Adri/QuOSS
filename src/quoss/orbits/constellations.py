"""Constellation geometry: Walker-Delta layout, sun-synchronous and repeat-track design.

:mod:`quoss.orbits.kepler` places one orbit. :mod:`quoss.orbits.perturbations`
says how one orbit's node and perigee drift under J2. This module answers the
question a scenario actually asks: *which* orbits, and *how many*, to cover the
Earth on a schedule. Three questions, three functions, and they do not share
much code because they are not the same kind of problem:

============================================  ====================================
:func:`walker_delta`                          Pure geometry: lay ``T`` satellites
                                               out in ``P`` planes with a chosen
                                               relative phasing. No physics at
                                               all — every orbit gets the same
                                               size, shape and inclination, so
                                               the only question is *where*.
:func:`sun_synchronous_inclination_rad`        Physics, closed form: invert
                                               :func:`~quoss.orbits.perturbations.secular_rates_j2`'s
                                               node-rate formula so the answer is
                                               an algebraic rearrangement, not a
                                               search.
:func:`repeat_ground_track_semi_major_axis_km` Physics, root-find: the same
                                               secular theory, but the unknown
                                               (``a``) appears on both sides of a
                                               transcendental equation, so this
                                               one needs :func:`scipy.optimize.brentq`.
============================================  ====================================

What this module is not
------------------------
No visibility, no pass geometry, no CLI, no scenario schema. Those are later
roadmap stages (``orbits/geometry.py``, ``scenario/``, ``cli/``) and pulling any
of them in here would make this module answer a question nobody asked it.
:func:`walker_delta` returns **one** :class:`~quoss.orbits.kepler.ClassicalElements`
holding all ``T`` orbits — never a list, never a loop the caller has to run —
because that array-of-orbits contract is the whole point of
:mod:`quoss.core.types`: every function downstream that already knows how to
take one satellite's elements and broadcast over time takes a constellation for
free, with no second code path.

The gap this module inherits, and does not hide
-------------------------------------------------
:func:`sun_synchronous_inclination_rad` and
:func:`repeat_ground_track_semi_major_axis_km` both work by inverting or
solving :func:`~quoss.orbits.perturbations.secular_rates_j2`, and that function
is a statement about **mean** elements (see
``docs/adr/0006-osculating-vs-mean-elements.md``): the ellipse with the J2
short-period wobble already averaged out, not the one a state vector or a
scenario's epoch elements describe. So the semi-major axis or inclination this
module hands back is correct as a *mean* quantity — feed it straight back into
:func:`~quoss.orbits.perturbations.secular_rates_j2` (labelled
:attr:`~quoss.orbits.kepler.ElementType.MEAN_BROUWER`, as both functions here
require) and the resonance or sun-synchronous condition holds to numerical
precision, exactly, because that is a closed loop through the same formula.

What it is *not* correct as, without more work QuOSS cannot do yet, is the
**osculating** semi-major axis or inclination at one specific epoch — the six
numbers :func:`~quoss.orbits.kepler.coe_to_rv` would need to hand back a state
vector. Converting mean to osculating is the Brouwer-Lyddane short-period
transformation, which nothing in QuOSS implements
(``docs/adr/0003-orbital-elements.md``, ``docs/adr/0006-osculating-vs-mean-elements.md``).
This is not a new hole this module digs: it is the *same* gap
``orbits/tle.py`` and ``orbits/propagator.py`` already live with, arriving here
from the opposite direction — they receive mean elements from somewhere else
(a TLE, an averaged theory) and must not feed them to code that wants
osculating ones; this module *produces* mean-theory numbers and must not let a
caller mistake them for osculating ones either. The size of getting it wrong
is not re-measured here — it does not need to be, because it is the exact same
formula and the exact same regime (a first-order-J2 near-circular LEO) already
measured in ``kepler.py``'s module docstring and reproduced by
``tests/orbits/test_propagator.py::TestWhatNotHavingBrouwerLyddaneCosts``: up to
**86 km after one revolution and 1290 km after a day** for a 700 km
sun-synchronous orbit, and *not* a single number — it depends on where in the
orbit the mismatch is measured from, by a factor of over a thousand between the
best and worst case. Because :class:`~quoss.orbits.kepler.ElementType` gates
:func:`~quoss.orbits.kepler.coe_to_rv` on osculating elements, the failure mode
this module could otherwise cause — quietly handing a mean semi-major axis to
code that treats it as an epoch state — is not silent: it is a
:class:`~quoss.core.errors.DomainError`, the moment anyone tries to turn the
result into a position and velocity without going through
:meth:`~quoss.orbits.kepler.ClassicalElements.relabelled_as` and saying, in
writing, that they are doing that on purpose. Neither function in this module
constructs a :class:`~quoss.orbits.kepler.ClassicalElements` at all — each
returns the raw number (radians, kilometres), the same choice
:func:`~quoss.orbits.kepler.semi_major_axis_from_period_km` already makes, and
for the same reason: the caller decides how to label what they build with it.

Conventions in force
---------------------
Distances in km, angles in radians, ``mu`` in km^3/s^2, per
``docs/adr/0001-unit-conventions.md``. No function here takes a
:class:`~quoss.core.errors.DegradationLog`: an unreachable sun-synchronous
inclination or an unresonant repeat cycle is not a model that degrades
gracefully to a worse answer, it is a request with no solution, so it raises.

References
----------
.. [1] Walker, J. G., "Continuous Whole-Earth Coverage by Circular-Orbit
       Satellite Patterns", Royal Aircraft Establishment Technical Report
       77044, 1977. The ``i:T/P/F`` notation and the phasing convention.
.. [2] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed.,
       2013, Sec. 9.6 (secular rates; sun-synchronous and repeat ground track
       design build directly on the formulas there) and Sec. 11.4 (repeat
       ground tracks). No page-cited worked numeric example from this book is
       transcribed here (unlike ``tests/orbits/test_kepler.py``'s Vallado
       examples): a specific Walker-pattern or repeat-track worked example was
       looked for and not confidently located, so nothing is asserted as V2
       from it. See ``tests/orbits/test_constellations.py`` module docstring
       and ``notes/LAST_CHANGES.md`` for what was checked instead.
"""

from __future__ import annotations

from typing import Final

import numpy as np
from scipy.optimize import brentq

from quoss.core.constants import (
    EARTH_ROTATION_RAD_S,
    EGM96_J2,
    EGM96_MU_KM3_S2,
    EGM96_RADIUS_EQUATORIAL_KM,
    TROPICAL_YEAR_S,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import FloatArray, FloatLike
from quoss.core.units import rad_to_deg
from quoss.orbits._validation import as_1d
from quoss.orbits.frames import Frame
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    semi_major_axis_from_period_km,
    true_from_mean_anomaly,
)
from quoss.orbits.perturbations import secular_rates_j2

__all__ = [
    "SUN_SYNCHRONOUS_RAAN_RATE_RAD_S",
    "repeat_ground_track_semi_major_axis_km",
    "sun_synchronous_inclination_rad",
    "walker_delta",
]

_TWO_PI: Final = 2.0 * np.pi

SUN_SYNCHRONOUS_RAAN_RATE_RAD_S: Final = _TWO_PI / TROPICAL_YEAR_S
"""The node-regression rate a sun-synchronous orbit must have, rad/s.

``2 pi`` per tropical year (:data:`~quoss.core.constants.TROPICAL_YEAR_S`), the
rate the mean Sun's ecliptic longitude advances. Public, not folded into
:func:`sun_synchronous_inclination_rad` as a bare literal, because
``tests/orbits/test_constellations.py`` needs the exact same number the
function inverts against — a second copy typed independently in the test file
would let the two silently drift if the tropical-year constant ever changed.

~0.98565 deg/day, measured against :data:`~quoss.core.constants.TROPICAL_YEAR_S`
in this module's own doctest below.

Examples
--------
>>> import numpy as np
>>> float(np.round(np.rad2deg(SUN_SYNCHRONOUS_RAAN_RATE_RAD_S) * 86400.0, 5))
0.98565
"""


# --------------------------------------------------------------------------- #
# Shared broadcasting
#
# A third private copy of the same ~10-line pattern in `frames.py` and
# `kepler.py`. Not collapsed into `_validation.py`, on purpose: that module's
# own docstring already explains why broadcasting stays local to each caller —
# the shapes and the advice in the error message differ enough between modules
# that a shared helper would say less than any of the three.
# --------------------------------------------------------------------------- #
def _broadcast_to_common(
    names: tuple[str, ...], arrays: tuple[FloatArray, ...]
) -> list[FloatArray]:
    """Broadcast validated 1-D arrays to their common length.

    Parameters
    ----------
    names : tuple of str
        Argument names, in the same order as ``arrays``.
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
                f"{name} has length {arr.size}, which is neither 1 nor {n}. Give one "
                f"value per sample, or a single value held fixed."
            )
    return out


def _validated_positive_int(name: str, value: int) -> int:
    """Return ``value`` as a validated positive Python ``int``.

    Parameters
    ----------
    name : str
        Argument name, used in the error message.
    value : int
        Value to validate. A NumPy integer scalar is accepted; a ``bool`` is
        not, even though ``bool`` is a subclass of ``int`` in Python — accepting
        it would let a typo like a stray ``True`` silently mean ``1``.

    Returns
    -------
    int
        The validated value.

    Raises
    ------
    DomainError
        If ``value`` is not an integer, or is not positive.
    """
    if isinstance(value, bool) or not isinstance(value, int | np.integer):
        raise DomainError(f"{name} must be an integer, got {value!r}.")
    if value <= 0:
        raise DomainError(f"{name} must be positive, got {value!r}.")
    return int(value)


# --------------------------------------------------------------------------- #
# Walker-Delta
# --------------------------------------------------------------------------- #
def walker_delta(
    *,
    semi_major_axis_km: float,
    eccentricity: float,
    inclination_rad: float,
    total_satellites: int,
    planes: int,
    phasing_factor: int,
    argp_rad: float = 0.0,
    raan_offset_rad: float = 0.0,
    mean_anomaly_offset_rad: float = 0.0,
    frame: Frame = Frame.TEME,
    element_type: ElementType = ElementType.OSCULATING,
) -> ClassicalElements:
    r"""Lay out a Walker-Delta constellation: notation ``i:T/P/F``.

    A Walker-Delta pattern [1]_ places ``T`` identical orbits — same size, same
    shape, same inclination — into ``P`` equally-spaced planes, with ``T/P``
    satellites evenly spaced within each plane, and a fixed relative offset
    between neighbouring planes so the whole pattern repeats with a period
    shorter than ``P`` planes' worth of orbits. It is the standard building
    block for constellations designed for even global or zonal coverage — GPS
    (24 satellites, 6 planes) and Galileo (24 satellites, 3 planes) are both
    Walker-Delta patterns.

    Parameters
    ----------
    semi_major_axis_km : float
        Semi-major axis, common to every satellite, km. Must be positive.
    eccentricity : float
        Eccentricity, common to every satellite, in ``[0, 1)``.
    inclination_rad : float
        Inclination, common to every satellite, radians, in ``[0, pi]``.
    total_satellites : int
        ``T``, the total number of satellites. Must be a positive multiple of
        ``planes``.
    planes : int
        ``P``, the number of orbital planes. Must be positive.
    phasing_factor : int
        ``F``, the relative phasing between neighbouring planes, as an integer
        satellite-slot count. Must satisfy ``0 <= F < P``: this is the
        parameter people get backwards (see Notes), and the valid range itself
        catches the commonest version of that mistake, an ``F`` typed as if it
        counted planes rather than one of ``T`` phase slots.
    argp_rad : float, optional
        Argument of periapsis, common to every satellite, radians. Defaults to
        0, the only choice that means anything for a near-circular
        constellation orbit (see
        :attr:`~quoss.orbits.kepler.ClassicalElements.is_circular`).
    raan_offset_rad : float, optional
        RAAN of the first plane (plane 0), radians. Defaults to 0; every other
        plane's RAAN is this plus a multiple of ``2 pi / P``.
    mean_anomaly_offset_rad : float, optional
        Mean anomaly of the first satellite of the first plane, radians.
        Defaults to 0; every other satellite's mean anomaly is this plus the
        within-plane and between-plane offsets described in Notes.
    frame : Frame, optional
        Inertial frame of the returned elements. Defaults to
        :attr:`~quoss.orbits.frames.Frame.TEME`.
    element_type : ElementType, optional
        Label carried by the returned elements. Defaults to
        :attr:`~quoss.orbits.kepler.ElementType.OSCULATING`, matching
        :meth:`~quoss.orbits.kepler.ClassicalElements.from_semi_major_axis`.
        Pass :attr:`~quoss.orbits.kepler.ElementType.MEAN_BROUWER` when
        ``semi_major_axis_km``/``inclination_rad`` came from
        :func:`sun_synchronous_inclination_rad` or
        :func:`repeat_ground_track_semi_major_axis_km` — see the module
        docstring for why defaulting that case to ``OSCULATING`` would be the
        silent mean/osculating mismatch
        ``docs/adr/0006-osculating-vs-mean-elements.md`` exists to prevent.

    Returns
    -------
    ClassicalElements
        **All** ``T`` satellites as one object of length ``T`` — never a list
        of ``T`` single-satellite objects. Ordered plane-major: the first
        ``T/P`` entries are plane 0 (slots ``0..T/P-1`` in order), the next
        ``T/P`` are plane 1, and so on.

    Raises
    ------
    DomainError
        If ``total_satellites`` or ``planes`` is not a positive integer, if
        ``total_satellites`` is not a multiple of ``planes``, if
        ``phasing_factor`` is not an integer in ``[0, planes)``, or if any
        orbital element is out of range (propagated from
        :meth:`~quoss.orbits.kepler.ClassicalElements.from_semi_major_axis`).

    Notes
    -----
    **Which anomaly is spaced, and why it has to be the mean one.** Two
    satellites sharing one semi-major axis share one mean motion ``n``, so
    their mean anomalies are ``M_1(t) = M_{1,0} + n t`` and
    ``M_2(t) = M_{2,0} + n t``: the *difference* ``M_2 - M_1`` is exactly
    constant for all time, under pure two-body motion — spacing satellites in
    mean anomaly is spacing them in a quantity time cannot disturb. True
    anomaly has no such property: ``d(nu)/dt`` is not constant over an
    eccentric orbit (it is fastest at periapsis), so two satellites started at
    a fixed true-anomaly separation drift apart and back together every
    revolution, the very "wobble" that gives an eccentric orbit's ground track
    its characteristic analemma shape. This function therefore spaces
    satellites in **mean** anomaly and converts to true anomaly, once, at
    construction, through :func:`~quoss.orbits.kepler.true_from_mean_anomaly` —
    not the other way around.

    For the near-circular orbits (``e`` of a few ``1e-3`` or less) that almost
    every real constellation flies, this choice is close to moot: mean and true
    anomaly agree to ``O(e)``, i.e. a few thousandths of a radian, tenths of a
    degree. It stops being moot the moment ``eccentricity`` is not small, which
    is precisely why the choice is made explicitly here rather than left for
    whichever anomaly happened to be convenient.

    **The phasing direction — the part people get backwards.** Within one
    plane, satellite ``s`` (0-indexed) sits at mean anomaly
    ``s * (2 pi / (T/P))``. Between planes, plane ``p`` (0-indexed) is offset by
    an *additional* ``p * F * (2 pi / T)`` on top of its own within-plane
    spacing — so the full expression for satellite ``s`` of plane ``p`` is

    .. math:: M_{p,s} = M_0 + s \frac{2\pi}{T/P} + p \, F \frac{2\pi}{T}

    with :math:`\Omega_p = \Omega_0 + p \, (2\pi / P)`. The offset direction —
    *increasing* with plane index, in the *same* sense RAAN increases with
    plane index — is the standard Walker convention [1]_, reproduced
    independently by MATLAB's Aerospace Toolbox
    (``satelliteScenario.walkerDelta``, which documents the between-plane
    step as exactly ``F * 360 / T`` degrees of true anomaly for circular
    orbits, where true and mean anomaly coincide). Reversing the sign — putting
    a *later* plane's satellites *behind* rather than ahead — still produces a
    pattern with the right RAAN spacing and the right within-plane spacing, so
    it looks correct at a glance and is exactly the mistake this docstring
    exists to keep out: :class:`TestPhasingDirectionAgreesWithConvention` in
    ``tests/orbits/test_constellations.py`` pins the sign down with a worked
    ``6:6/3/1`` case computed by hand.

    A published, page-cited Walker-pattern worked example (in the spirit of the
    Vallado transcriptions in ``tests/orbits/test_kepler.py``) was looked for
    and not confidently located, so nothing here is asserted as V2 from a
    textbook; correctness rests on the V1 invariants above (exact RAAN and
    mean-anomaly spacing, exact count) plus the independent-source agreement
    just described. See ``notes/LAST_CHANGES.md``.

    Examples
    --------
    A minimal pattern, ``6:6/3/1`` — 6 satellites, 3 planes, phasing 1 — worked
    by hand: RAAN steps by 120 deg per plane, mean anomaly steps by 180 deg
    within a plane, and by ``1 * 360/6 = 60`` deg between planes:

    >>> import numpy as np
    >>> coe = walker_delta(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.0,
    ...     inclination_rad=np.deg2rad(53.0),
    ...     total_satellites=6,
    ...     planes=3,
    ...     phasing_factor=1,
    ... )
    >>> coe.n
    6
    >>> np.round(np.rad2deg(coe.raan_rad), 3)
    array([  0.,   0., 120., 120., 240., 240.])
    >>> np.round(np.rad2deg(coe.true_anomaly_rad), 3)
    array([  0., 180.,  60., 240., 120., 300.])
    """
    total = _validated_positive_int("total_satellites", total_satellites)
    plane_count = _validated_positive_int("planes", planes)
    if total % plane_count != 0:
        raise DomainError(
            f"total_satellites={total} is not a multiple of planes={plane_count}. A "
            f"Walker-Delta pattern needs the same number of satellites in every plane."
        )
    if isinstance(phasing_factor, bool) or not isinstance(phasing_factor, int | np.integer):
        raise DomainError(f"phasing_factor must be an integer, got {phasing_factor!r}.")
    if not (0 <= phasing_factor < plane_count):
        raise DomainError(
            f"phasing_factor={phasing_factor} must satisfy 0 <= F < planes ({plane_count}). "
            f"F counts one of T phase slots, not a number of planes — the usual way this "
            f"goes wrong is passing a value meant for P instead."
        )

    per_plane = total // plane_count
    plane_index = np.repeat(np.arange(plane_count, dtype=np.float64), per_plane)
    slot_index = np.tile(np.arange(per_plane, dtype=np.float64), plane_count)

    raan_rad = raan_offset_rad + plane_index * (_TWO_PI / plane_count)
    mean_anomaly_rad = (
        mean_anomaly_offset_rad
        + slot_index * (_TWO_PI / per_plane)
        + plane_index * (int(phasing_factor) * _TWO_PI / total)
    )
    true_anomaly_rad = true_from_mean_anomaly(mean_anomaly_rad, eccentricity)

    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=eccentricity,
        inclination_rad=inclination_rad,
        raan_rad=raan_rad,
        argp_rad=argp_rad,
        true_anomaly_rad=true_anomaly_rad,
        frame=frame,
        element_type=element_type,
    )


# --------------------------------------------------------------------------- #
# Sun-synchronous design
# --------------------------------------------------------------------------- #
def sun_synchronous_inclination_rad(
    semi_major_axis_km: FloatLike,
    eccentricity: FloatLike,
    *,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
    r_equatorial_km: float = EGM96_RADIUS_EQUATORIAL_KM,
    j2: float = EGM96_J2,
) -> FloatArray:
    r"""Invert the J2 node-rate formula for the sun-synchronous inclination.

    A **sun-synchronous orbit** (SSO) is one whose node regresses at exactly
    :data:`SUN_SYNCHRONOUS_RAAN_RATE_RAD_S`, the rate the mean Sun's ecliptic
    longitude advances (see the module docstring of
    :mod:`quoss.core.constants`). The payoff is that the angle between the
    orbital plane and the Earth-Sun line stays fixed all year, so a satellite
    crosses a given latitude at (approximately) the same local solar time on
    every pass — which is why almost every Earth-observation satellite flies
    one.

    :func:`~quoss.orbits.perturbations.secular_rates_j2` already gives
    ``raan_dot`` as a function of ``a``, ``e`` and ``i``. Setting it equal to
    the target rate and solving for ``cos(i)`` is **algebra, not search** — the
    unknown ``i`` appears nowhere but inside that one cosine — so this function
    is a rearrangement of that module's own formula, never a second copy of it:

    .. math:: \cos i = \frac{-\dot\Omega_\odot}
        {\tfrac{3}{2} n J_2 (R/p)^2}, \qquad
        \dot\Omega_\odot = \texttt{SUN\_SYNCHRONOUS\_RAAN\_RATE\_RAD\_S}

    with ``n = sqrt(mu/a^3)`` and ``p = a(1-e^2)``, exactly the ``n`` and ``p``
    :func:`~quoss.orbits.perturbations.secular_rates_j2` uses. If a
    ``scipy.optimize`` import turns out to feel necessary here, that is a sign
    the algebra above was not done — see
    ``docs/adr/0004-zonal-perturbations.md`` and
    ``docs/adr/0006-osculating-vs-mean-elements.md`` for why ``secular_rates_j2``
    is trusted rather than re-derived.

    Parameters
    ----------
    semi_major_axis_km : float or FloatArray
        Semi-major axis, km. Must be positive. Length 1 or matching
        ``eccentricity``.
    eccentricity : float or FloatArray
        Eccentricity, in ``[0, 1)``. Length 1 or matching.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96, matching
        :func:`~quoss.orbits.perturbations.secular_rates_j2`'s default.
    r_equatorial_km : float, optional
        Reference radius of the J2 coefficient, km. Defaults to the EGM96
        radius.
    j2 : float, optional
        Second zonal harmonic. Defaults to EGM96.

    Returns
    -------
    FloatArray
        Inclination, radians, in ``(pi/2, pi]`` — always retrograde, because
        ``cos i`` must be negative for a positive (eastward, sun-tracking)
        node rate; see :func:`~quoss.orbits.perturbations.secular_rates_j2`'s
        own note on the sign.

    Raises
    ------
    DomainError
        If ``semi_major_axis_km`` is not positive, ``eccentricity`` is outside
        ``[0, 1)``, ``mu_km3_s2``/``r_equatorial_km`` is not finite and
        positive, ``j2`` is not finite, the lengths do not broadcast, or — most
        interesting — if ``|cos i| > 1``: **no** inclination makes this
        ``a``/``e`` sun-synchronous. This happens above roughly 6000 km
        altitude, where J2's node-drag has fallen too far below the target
        rate for any tilt of the plane to make up the difference; the message
        reports the offending ``cos i`` so the caller can see how far short.

    Notes
    -----
    **The mean/osculating gap this result carries.** The inclination returned
    here solves the *mean*-element sun-synchronous condition exactly — see the
    module docstring's "gap this module inherits" section, and the round-trip
    example below, which closes to machine precision because it is the same
    formula both ways. Whether it is close enough to the true condition for an
    orbit whose elements are stated as *osculating* at one particular epoch is
    the same open question ``kepler.py`` already states a size for (up to
    1290 km/day for a 700 km SSO, phase-dependent) and this module does not
    reopen it.

    Examples
    --------
    :func:`~quoss.orbits.perturbations.secular_rates_j2`'s own docstring states
    that ``a=7078.137 km, e=0.001, i=98.19 deg`` gives ``0.9859 deg/day`` — close
    to, but not exactly, the sun-synchronous rate of ``0.98565 deg/day``, since
    98.19 deg is quoted to hundredths of a degree, not derived from this
    formula. Inverting the same ``a``, ``e`` recovers that inclination to the
    precision it was originally stated at:

    >>> import numpy as np
    >>> i = sun_synchronous_inclination_rad(7078.137, 0.001)
    >>> float(np.round(np.rad2deg(i[0]), 2))
    98.19

    The round trip closes exactly, because both directions are the same
    formula solved for a different unknown:

    >>> from quoss.orbits.kepler import ClassicalElements, ElementType
    >>> from quoss.orbits.perturbations import secular_rates_j2
    >>> sso = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=float(i[0]),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ...     element_type=ElementType.MEAN_BROUWER,
    ... )
    >>> recovered = float(secular_rates_j2(sso).raan_rad_s[0])
    >>> bool(np.isclose(recovered, SUN_SYNCHRONOUS_RAAN_RATE_RAD_S, rtol=0.0, atol=1e-18))
    True

    A too-high altitude has no solution, and says so rather than returning a
    number outside ``[0, pi]``:

    >>> try:
    ...     sun_synchronous_inclination_rad(50_000.0, 0.0)
    ... except Exception as exc:
    ...     print(type(exc).__name__)
    DomainError
    """
    axis = as_1d("semi_major_axis_km", semi_major_axis_km)
    if np.any(axis <= 0.0):
        raise DomainError(
            f"semi_major_axis_km must be positive, got minimum {float(axis.min())!r}."
        )
    ecc = as_1d("eccentricity", eccentricity)
    if np.any(ecc < 0.0) or np.any(ecc >= 1.0):
        raise DomainError(
            f"eccentricity must be in [0, 1), got range "
            f"[{float(ecc.min())!r}, {float(ecc.max())!r}]."
        )
    axis, ecc = _broadcast_to_common(("semi_major_axis_km", "eccentricity"), (axis, ecc))

    for name, value in (("mu_km3_s2", mu_km3_s2), ("r_equatorial_km", r_equatorial_km)):
        if not (np.isfinite(value) and value > 0.0):
            raise DomainError(f"{name} must be finite and positive, got {value!r}.")
    if not np.isfinite(j2):
        raise DomainError(f"j2 must be finite, got {j2!r}.")

    p_km = axis * (1.0 - ecc * ecc)
    mean_motion = np.sqrt(mu_km3_s2 / axis**3)
    scale = mean_motion * j2 * (r_equatorial_km / p_km) ** 2
    cos_inc = -SUN_SYNCHRONOUS_RAAN_RATE_RAD_S / (1.5 * scale)

    if np.any(np.abs(cos_inc) > 1.0):
        worst = float(cos_inc[np.argmax(np.abs(cos_inc))])
        raise DomainError(
            f"No inclination makes this orbit sun-synchronous: |cos(i)| = {abs(worst):.6g} "
            f"> 1 (cos(i) = {worst:.6g}). J2's node-drag at this altitude cannot reach "
            f"{float(rad_to_deg(SUN_SYNCHRONOUS_RAAN_RATE_RAD_S)) * 86400.0:.5f} deg/day at any "
            f"inclination; this is the usual outcome above roughly 6000 km altitude."
        )
    return np.asarray(np.arccos(cos_inc), dtype=np.float64)


# --------------------------------------------------------------------------- #
# Repeat ground track design
# --------------------------------------------------------------------------- #
_BRACKET_RELATIVE_HALF_WIDTH: Final = 0.05
"""Half-width of the root-finding bracket, relative to the two-body estimate.

J2's contribution to both sides of the resonance condition is ``O(J2)`` ~ 1e-3
relative, and the Earth-rotation side is perturbed by at most a few percent
(``raan_dot`` tops out around 5 deg/day against Earth's 360.99 deg/day, i.e.
~1.4 %) — so the true root sits within a fraction of a percent of the two-body
estimate in every regime this project targets (LEO, near-circular). 5 % is
generous headroom over that, chosen once here rather than re-derived at every
call site, and cheap: :func:`scipy.optimize.brentq` does not care how wide a
correct bracket is, only whether the sign changes across it.
"""

_BRENTQ_XTOL_KM: Final = 1e-9
"""Absolute tolerance on the solved semi-major axis, km — a millimetre.

Matches the spirit of :data:`~quoss.orbits.perturbations.DEFAULT_ZONAL_ATOL_KM`:
far below any physically meaningful altitude precision, so the root-finder is
never the limiting error.
"""

_BRENTQ_RTOL: Final = 4.0 * np.finfo(np.float64).eps
"""Relative tolerance on the solved semi-major axis — the tightest ``brentq``
will accept.

``scipy.optimize.brentq`` rejects any ``rtol`` below ``4 * eps`` (raises
``ValueError``), so this is not a chosen precision, it is the floor: with
:data:`_BRENTQ_XTOL_KM` already at a millimetre, there is no reason to accept
anything looser than the solver's own limit.
"""


def _resonance_residual_rad_s(
    semi_major_axis_km: float,
    eccentricity: float,
    inclination_rad: float,
    mu_km3_s2: float,
    r_equatorial_km: float,
    j2: float,
    orbits_per_cycle: int,
    days_per_cycle: int,
) -> float:
    """Evaluate the repeat-ground-track resonance condition at one ``a``.

    Zero exactly at the semi-major axis :func:`repeat_ground_track_semi_major_axis_km`
    is looking for; see that function's docstring for the physics. Kept
    separate so the same expression is what both the bracket check and
    :func:`scipy.optimize.brentq` evaluate — one definition of "resonant",
    not two that could quietly disagree.

    Parameters
    ----------
    semi_major_axis_km : float
        Trial semi-major axis, km.
    eccentricity : float
        Eccentricity, in ``[0, 1)``.
    inclination_rad : float
        Inclination, radians.
    mu_km3_s2 : float
        Gravitational parameter, km^3/s^2.
    r_equatorial_km : float
        Reference radius of the J2 coefficient, km.
    j2 : float
        Second zonal harmonic.
    orbits_per_cycle : int
        Revolutions per repeat cycle.
    days_per_cycle : int
        Node-relative Earth rotations per repeat cycle.

    Returns
    -------
    float
        ``orbits_per_cycle * (omega_earth - raan_dot) - days_per_cycle * nodal_rate``,
        rad/s. Zero at resonance.
    """
    elements = ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=eccentricity,
        inclination_rad=inclination_rad,
        raan_rad=0.0,
        argp_rad=0.0,
        true_anomaly_rad=0.0,
        element_type=ElementType.MEAN_BROUWER,
    )
    rates = secular_rates_j2(elements, mu_km3_s2=mu_km3_s2, r_equatorial_km=r_equatorial_km, j2=j2)
    nodal_rate_rad_s = float(rates.mean_anomaly_rad_s[0] + rates.argp_rad_s[0])
    earth_relative_to_node_rad_s = EARTH_ROTATION_RAD_S - float(rates.raan_rad_s[0])
    return orbits_per_cycle * earth_relative_to_node_rad_s - days_per_cycle * nodal_rate_rad_s


def repeat_ground_track_semi_major_axis_km(
    orbits_per_cycle: int,
    days_per_cycle: int,
    inclination_rad: FloatLike,
    eccentricity: FloatLike = 0.0,
    *,
    mu_km3_s2: float = EGM96_MU_KM3_S2,
    r_equatorial_km: float = EGM96_RADIUS_EQUATORIAL_KM,
    j2: float = EGM96_J2,
) -> FloatArray:
    r"""Solve for the semi-major axis of a repeat ground track orbit.

    A **repeat ground track** orbit is one whose sub-satellite point traces
    the same path over the Earth's surface on a fixed schedule: after
    ``orbits_per_cycle`` revolutions, spanning ``days_per_cycle`` rotations of
    the Earth relative to the satellite's (regressing) orbital node, the
    ground track closes and starts over. Landsat's WRS-2 grid (233 orbits, 16
    days) and most Earth-observation missions with a fixed revisit schedule
    are designed this way.

    **The resonance condition.** Let ``dot_M + dot_omega`` be the satellite's
    nodal rate — how fast its argument of latitude advances, i.e.
    ``2 pi / `` :attr:`~quoss.orbits.perturbations.SecularRates.nodal_period_s`
    — and let ``omega_E - dot_Omega`` be the Earth's rotation rate *as seen
    from the regressing node*: the node itself moves, so it is not quite
    :data:`~quoss.core.constants.EARTH_ROTATION_RAD_S` that matters, it is the
    difference. The ground track repeats exactly when these two rates are in
    the ``orbits_per_cycle : days_per_cycle`` ratio the caller asked for:

    .. math:: \texttt{orbits\_per\_cycle} \cdot (\omega_E - \dot\Omega)
        = \texttt{days\_per\_cycle} \cdot (\dot M + \dot\omega)

    Both ``dot_Omega`` and ``dot omega`` (and the mean motion inside ``dot_M``)
    depend on ``a`` — through :func:`~quoss.orbits.perturbations.secular_rates_j2`
    — so ``a`` appears on both sides and this is **not** algebra: it is solved
    numerically with :func:`scipy.optimize.brentq`, bracketed around the
    two-body estimate (see Notes) rather than with a hand-rolled Newton
    iteration, because ``brentq`` is guaranteed to converge for any bracket
    that changes sign and needs no derivative — exactly the same reasoning
    ``frames.py``'s geodetic inversion documents for its own iterative solver.

    Parameters
    ----------
    orbits_per_cycle : int
        Number of revolutions per repeat cycle. Must be a positive integer.
    days_per_cycle : int
        Number of node-relative Earth rotations per repeat cycle. Must be a
        positive integer. Numerically close to, but not exactly, a count of
        86400 s solar days — see Notes.
    inclination_rad : float or FloatArray
        Inclination, radians. Length 1 or matching ``eccentricity``.
    eccentricity : float or FloatArray, optional
        Eccentricity, in ``[0, 1)``. Defaults to 0 (circular), the design
        almost every repeat-track mission actually flies. Length 1 or matching.
    mu_km3_s2 : float, optional
        Gravitational parameter, km^3/s^2. Defaults to EGM96.
    r_equatorial_km : float, optional
        Reference radius of the J2 coefficient, km. Defaults to the EGM96
        radius.
    j2 : float, optional
        Second zonal harmonic. Defaults to EGM96.

    Returns
    -------
    FloatArray
        Semi-major axis, km, one per ``(inclination_rad, eccentricity)`` pair.

    Raises
    ------
    DomainError
        If ``orbits_per_cycle``/``days_per_cycle`` is not a positive integer,
        if ``eccentricity`` is outside ``[0, 1)``, if the lengths do not
        broadcast, or if any other input is invalid (propagated from
        :func:`~quoss.orbits.perturbations.secular_rates_j2`).
    ConvergenceError
        If the resonance condition does not change sign across the search
        bracket, so :func:`scipy.optimize.brentq` has nothing to bisect. In
        the regimes this project targets that should not happen (see Notes);
        it is the signal that the requested ``(orbits_per_cycle,
        days_per_cycle)`` ratio and ``inclination_rad`` combination is far
        from anything physically sensible — e.g. an orbital period so short or
        so long that ``a`` would be negative or absurdly large before J2 could
        matter.

    Notes
    -----
    **Why "days" means node-relative Earth rotations, not literal 86400 s
    days, and why the difference is small enough not to matter for the
    bracket.** The resonance condition above is a ratio of two *rates*, so
    ``days_per_cycle`` really counts full turns of ``(omega_E - dot_Omega)``,
    not calendar days. For a LEO, ``dot_Omega`` is a few degrees per day
    against Earth's 360.99 deg/day rotation — at most a percent or two — so a
    "node-relative day" and a solar day differ by minutes, not hours, and using
    :data:`~quoss.core.constants.EARTH_ROTATION_RAD_S` alone (``dot_Omega = 0``)
    for the **two-body starting bracket** is accurate enough to bracket the true
    root without needing the correction it is itself solving for.

    **The bracket.** The two-body estimate ignores J2 entirely (``dot_Omega =
    dot_omega = 0``), reducing the resonance condition to
    ``orbits_per_cycle * omega_E = days_per_cycle * n``, i.e. exactly
    :func:`~quoss.orbits.kepler.semi_major_axis_from_period_km` applied to the
    period ``2 pi days_per_cycle / (orbits_per_cycle * omega_E)``. The search
    bracket is that estimate, ``a_0``, widened by
    :data:`_BRACKET_RELATIVE_HALF_WIDTH` (5 %) on each side — see that
    constant's docstring for why 5 % is generous rather than tight. If ``j2 =
    0`` is passed, the two-body estimate **is** the exact root (the resonance
    condition becomes the two-body one identically), which is a cheap
    self-consistency check exercised in
    ``tests/orbits/test_constellations.py``.

    **The mean/osculating gap.** As with :func:`sun_synchronous_inclination_rad`,
    the ``a`` returned here satisfies the resonance condition for *mean*
    elements. See the module docstring.

    Examples
    --------
    Landsat's WRS-2 grid: 233 orbits every 16 days, at the mission's published
    sun-synchronous inclination. The solved altitude comes out within a few
    km of the mission's published ~705 km (see
    ``tests/orbits/test_constellations.py`` for the honestly-stated size of
    that gap — it is *not* explained by the precision of the published
    inclination, and stays as a documented, unresolved discrepancy rather
    than a claimed match):

    >>> import numpy as np
    >>> a = repeat_ground_track_semi_major_axis_km(233, 16, np.deg2rad(98.2), 0.0001)
    >>> 690.0 < float(a[0]) - 6378.1363 < 710.0
    True

    With ``j2=0`` the resonance condition collapses to the two-body one, and
    the solver recovers the closed-form two-body answer:

    >>> from quoss.orbits.kepler import semi_major_axis_from_period_km
    >>> period_s = 2 * np.pi * 16.0 / (233.0 * 7.292115e-5)
    >>> expected = float(semi_major_axis_from_period_km(period_s)[0])
    >>> solved = float(repeat_ground_track_semi_major_axis_km(233, 16, np.deg2rad(98.2), j2=0.0)[0])
    >>> bool(np.isclose(solved, expected, rtol=0.0, atol=1e-6))
    True
    """
    orbits = _validated_positive_int("orbits_per_cycle", orbits_per_cycle)
    days = _validated_positive_int("days_per_cycle", days_per_cycle)

    inc = as_1d("inclination_rad", inclination_rad)
    ecc = as_1d("eccentricity", eccentricity)
    if np.any(ecc < 0.0) or np.any(ecc >= 1.0):
        raise DomainError(
            f"eccentricity must be in [0, 1), got range "
            f"[{float(ecc.min())!r}, {float(ecc.max())!r}]."
        )
    inc, ecc = _broadcast_to_common(("inclination_rad", "eccentricity"), (inc, ecc))

    mean_motion_two_body_rad_s = orbits / days * EARTH_ROTATION_RAD_S
    period_two_body_s = _TWO_PI / mean_motion_two_body_rad_s
    axis_two_body_km = float(
        semi_major_axis_from_period_km(np.array([period_two_body_s]), mu_km3_s2)[0]
    )
    lo_km = axis_two_body_km * (1.0 - _BRACKET_RELATIVE_HALF_WIDTH)
    hi_km = axis_two_body_km * (1.0 + _BRACKET_RELATIVE_HALF_WIDTH)

    out = np.empty(inc.size, dtype=np.float64)
    for idx in range(inc.size):
        i_rad, e = float(inc[idx]), float(ecc[idx])

        def residual(a_km: float, i_rad: float = i_rad, e: float = e) -> float:
            return _resonance_residual_rad_s(
                a_km, e, i_rad, mu_km3_s2, r_equatorial_km, j2, orbits, days
            )

        f_lo, f_hi = residual(lo_km), residual(hi_km)
        if f_lo == 0.0:
            out[idx] = lo_km
            continue
        if f_hi == 0.0:
            out[idx] = hi_km
            continue
        if (f_lo > 0.0) == (f_hi > 0.0):
            raise ConvergenceError(
                f"No sign change in the resonance residual across the search bracket "
                f"[{lo_km:.3f}, {hi_km:.3f}] km (two-body estimate {axis_two_body_km:.3f} km, "
                f"+-{_BRACKET_RELATIVE_HALF_WIDTH * 100:.0f} %) for orbits_per_cycle={orbits}, "
                f"days_per_cycle={days}, inclination={float(rad_to_deg(i_rad)):.4f} deg, "
                f"eccentricity={e!r}. residual(lo)={f_lo:.6e}, residual(hi)={f_hi:.6e} rad/s. "
                f"J2's contribution to the resonance condition is O(J2) ~ 1e-3 relative, so "
                f"a bracket this wide failing to change sign means the requested cycle is far "
                f"from the two-body estimate it was built around, not that the bracket was "
                f"merely too narrow."
            )
        out[idx] = brentq(residual, lo_km, hi_km, xtol=_BRENTQ_XTOL_KM, rtol=_BRENTQ_RTOL)

    return out
