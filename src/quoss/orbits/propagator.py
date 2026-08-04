"""Propagation: elements at an epoch, states on a time grid.

The three modules before this one answer questions that have no clock in them. A
frame conversion needs an instant but not a history; a set of elements describes
an orbit, not a trajectory; a force field is evaluated at a position. This module
is where the simulation acquires **time**: it takes one set of elements stated at
an epoch and returns where the satellites are at every sample of a
:class:`~quoss.core.types.TimeGrid`.

It contains no new physics. Everything it computes already exists in
:mod:`quoss.orbits.kepler` and :mod:`quoss.orbits.perturbations`; what it adds is
the thing those two deliberately refused to decide — **which model runs**, and it
makes that choice a mandatory, recorded argument rather than a hidden default.

The choice is the point
-----------------------
:func:`~quoss.orbits.kepler.coe_to_rv` and
:func:`~quoss.orbits.perturbations.propagate_zonal` do not produce the same
numbers and must not pretend to. One treats the Earth as a point mass and has a
closed form; the other integrates the real zonal field and costs a Runge-Kutta
run per orbit. So :func:`propagate` takes a :class:`PropagationMethod` that is
keyword-only and **has no default**: a default is a modelling decision taken on
the caller's behalf without them noticing, and this is a project where a
plausible wrong number is the characteristic failure. The method travels in the
returned :class:`Trajectory`, so a result can always say how it was made.

========================================  ===================================
:attr:`~PropagationMethod.TWO_BODY`       Exact Keplerian motion. No Earth
                                          oblateness at all.
:attr:`~PropagationMethod.ZONAL_NUMERIC`  DOP853 through the J2/J3/J4 field.
                                          The reference model of this project.
========================================  ===================================

``TWO_BODY`` is not a cheap approximation of ``ZONAL_NUMERIC``; it is different
physics, and over a scenario of any length it is *wrong* rather than *coarse*.
J2 regresses the node of an ISS-like orbit by 4.95 deg/day, which is
``r * dOmega * sin i`` = 460 km of displacement after a single day. Measured, the
two modes are **720 km** apart after that day and 46 km after one revolution; the
excess over the node term is apsidal precession plus the difference between the
Keplerian and the anomalistic period. ``TWO_BODY`` has its uses — an analytically
closed baseline, a control in a test that isolates something else, a first look
at geometry — but a link budget that spans a day and uses it is reporting passes
that do not happen.

The enum is deliberately incomplete
-----------------------------------
The obvious third mode, an analytic J2 propagator built on
:func:`~quoss.orbits.perturbations.secular_rates_j2`, is **not** here, and the
absence is a decision rather than an omission. A secular rate is a statement
about *mean* elements — an ellipse with the fast wobble already subtracted —
while :func:`~quoss.orbits.kepler.rv_to_coe` and every scenario file speak
*osculating* elements, the ellipse tangent to the true path right now. The
difference between the two is itself ``O(J2)``, ~1e-3 relative, and feeding one
where the other is meant is not a rounding error:

========================  ==========  ==================  =============
Orbit (elements at nu=0)  1 rev       15 revs (~1 day)    Clock error
========================  ==========  ==================  =============
SSO 700 km, i = 98.2 deg  86.3 km     **1293 km**         11.5 s / rev
ISS-like, i = 51.6 deg    56.4 km     **845 km**          7.4 s / rev
LEO polar, i = 90 deg     88.1 km     **1319 km**         11.7 s / rev
LEO low-i, i = 28.5 deg   20.3 km     **305 km**          2.7 s / rev
========================  ==========  ==================  =============

measured against ``propagate_zonal`` with J2 only on both sides, so the
discrepancy is the mean/osculating mismatch alone and not different physics; with
J2 zero on both sides the same comparison closes to 0.08 mm over fifteen
revolutions, which is what says the table is physics and not the instrument.
Almost all of it is along-track: after one revolution the radial part is 0.5 km
and the cross-track 0.03 km, because those are the short-period wobble, which
oscillates and does not accumulate. The along-track part grows **linearly**, and
its size is not a coincidence to be quoted but a quantity to be derived — an
``O(J2)`` error in the semi-major axis is an ``O(J2)`` error in the angular
*rate*, and a rate integrates:

    along-track per revolution = ``3 pi * (a_osculating(epoch) - <a_osculating>)``

which for the SSO row is ``3 pi * 9.147 km`` = 86.2 km against 86.3 km measured.
Every row of the table agrees with that prediction to better than 2 %.

**And the size depends on orbital phase, which is why no single number is the
answer.** The osculating semi-major axis oscillates about the mean one with the
short-period J2 term — peak to peak 18.3 km on this orbit — so how far the epoch
sits from the crossing sets the drift. Stating the same SSO at ``nu`` near 45 deg
puts the epoch on the crossing, and the drift collapses to 0.07 km per revolution:
a factor of 1150. A scenario cannot know which case it is in, and the difference
between them is the difference between a usable propagator and a useless one.

For a pass that means: at ``nu = 0`` the visibility windows are ~2.9 minutes out of
place after one day, against a pass that lasts about ten.

The missing piece is the Brouwer-Lyddane short-period transformation, which this
project does not have and which ``docs/adr/0003-orbital-elements.md`` warns
against faking. What *does* exist now is the label:
:class:`~quoss.orbits.kepler.ElementType` travels inside the elements, and
because both modes here reach :func:`~quoss.orbits.kepler.coe_to_rv`, feeding
this function mean elements raises instead of returning the table above. When the
transformation lands, ``J2_SECULAR_ANALYTIC`` joins the enum and this module
gains a branch — the only branch that would *want* mean elements — and nothing
else changes, because no caller can be relying on a member that never existed. Adding a member without wiring it is caught by
``tests/orbits/test_propagator.py::TestModuleSurface``, which walks every member
of the enum and propagates with it.

That is the whole argument for shipping an incomplete enum rather than a complete
one with a broken mode: a name that is absent forces a compile-time-shaped
question at the call site, while a name that is present and quietly wrong is
exactly the failure mode ``README.md`` calls "degrading in silence".

Epoch
-----
The elements are stated at ``grid.epoch_jd``, i.e. at ``t_s == 0``, and there is
no other way to say when they are from. The epoch is **mandatory** because it
arrives inside the :class:`~quoss.core.types.TimeGrid`, which cannot be built
without one. This is a direct response to a defect in the previous codebase,
where a missing epoch fell back to ``datetime.utcnow()``: a run that cannot be
reproduced tomorrow, and no error anywhere.

``t_s`` need not start at zero and need not contain it. Negative samples are
propagated backwards, which is what an epoch in the middle of a scenario window —
what a TLE gives — actually needs. Nothing in this module reads ``epoch_jd``
numerically: the physics is a function of elapsed seconds only, and the Julian
date is carried through untouched so that the modules that *do* need absolute
time (GMST in :mod:`quoss.orbits.frames`, and later solar geometry) take it from
one place instead of each keeping its own. A test asserts that two grids
differing only in ``epoch_jd`` return bit-identical states.

Array shape: satellite-major, ``(S, n, 3)``
-------------------------------------------
:class:`Trajectory` holds positions and velocities of shape
``(n_satellites, n_samples, 3)``, always three-dimensional — a single satellite is
``(1, n, 3)``, in the same way a single ground site is ``(1, 3)`` in
:mod:`quoss.orbits.frames`, so that no consumer ever branches on shape.

Satellite-major rather than time-major because ``traj.r_km[s]`` is then a
contiguous ``(n, 3)`` block with time on the leading axis, which is precisely the
array contract every other function in the package already takes
(:data:`~quoss.core.types.Vec3Array`). Under the alternative ``(n, S, 3)``, one
satellite's track is ``r[:, s]``, a strided view that every downstream call would
have to copy.

Cost, so it is not a surprise
-----------------------------
``TWO_BODY`` is one vectorised pass over ``S * n`` samples: a stack of elements is
built once and handed to :func:`~quoss.orbits.kepler.coe_to_rv` in a single call,
so a hundred satellites cost what a hundred-fold longer time grid costs.
``ZONAL_NUMERIC`` is ``S`` independent integrations — an ODE cannot be broadcast
over initial conditions — at roughly 250 force evaluations per revolution. The
loop lives here rather than in
:func:`~quoss.orbits.perturbations.propagate_zonal` because this is the layer
that knows how many orbits there are, and it is where a future process pool would
go.

References
----------
.. [1] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed., 2013.
       Chapter 8 for the general propagation problem, 9.6 for the secular theory
       this module does not yet expose.
.. [2] ``docs/adr/0005-propagation.md`` — the decisions taken here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import FloatArray, TimeGrid, frozen_view
from quoss.orbits.frames import Frame, resolve_frame
from quoss.orbits.kepler import (
    ClassicalElements,
    advance_mean_anomaly,
    coe_to_rv,
    mean_from_true_anomaly,
    mean_motion_rad_s,
    true_from_mean_anomaly,
)
from quoss.orbits.perturbations import (
    DEFAULT_ZONAL_ATOL_KM,
    DEFAULT_ZONAL_RTOL,
    EGM96_ZONAL,
    ZonalGravity,
    propagate_zonal,
)

__all__ = [
    "PropagationMethod",
    "Trajectory",
    "propagate",
]


class PropagationMethod(StrEnum):
    """Which model :func:`propagate` runs. No default anywhere.

    A :class:`~enum.StrEnum` so that a scenario file can write the plain string
    ``"zonal_numeric"`` and get the member back, and so that the value serialises
    into a result's provenance without a converter.

    Attributes
    ----------
    TWO_BODY : str
        Exact Keplerian motion about a point mass. Closed form, vectorised over
        the whole grid at once, and **no Earth oblateness**: the node does not
        regress and the ground track does not drift. Use it as a baseline or a
        control, not as a cheap version of the truth — see the module docstring
        for what it costs over a day.
    ZONAL_NUMERIC : str
        DOP853 integration of the exact J2/J3/J4 field from
        :func:`~quoss.orbits.perturbations.gravitational_acceleration`. The
        reference model: it makes no averaging or first-order assumption, and it
        is what the secular theory in :mod:`quoss.orbits.perturbations` is
        measured against.

    Notes
    -----
    There is no ``J2_SECULAR_ANALYTIC``, and that is deliberate — the analytic
    mode needs mean elements, this project only has osculating ones, and the gap
    between them runs to ~1300 km after a day rather than a rounding error. The
    module docstring has the measured table, the derivation of its size, and the
    condition for the member to appear.

    Examples
    --------
    >>> PropagationMethod.ZONAL_NUMERIC
    <PropagationMethod.ZONAL_NUMERIC: 'zonal_numeric'>
    >>> PropagationMethod("two_body") is PropagationMethod.TWO_BODY
    True
    >>> sorted(PropagationMethod)
    [<PropagationMethod.TWO_BODY: 'two_body'>, <PropagationMethod.ZONAL_NUMERIC: 'zonal_numeric'>]
    """

    TWO_BODY = "two_body"
    ZONAL_NUMERIC = "zonal_numeric"


@dataclass(frozen=True, eq=False, slots=True)
class Trajectory:
    """States on a time grid, with how they were produced.

    What :func:`propagate` returns. Immutable and validated at construction, so a
    consumer may assume the arrays line up with the grid without re-checking.
    **Immutable includes the states**: they are stored as read-only views, so
    ``traj.r_km[0, 0, 0] = 0.0`` raises instead of quietly editing a result that
    other consumers still hold. Read-only *views* and not copies, because these
    arrays are produced by this module and handed to nobody else first — copying a
    ``(S, n, 3)`` block would cost 24 MB per array for a million samples to defend
    against a second reference that does not exist. See
    :func:`~quoss.core.types.frozen_view`.

    Parameters
    ----------
    r_km : FloatArray
        Positions, km, shape ``(n_satellites, n_samples, 3)``, in :attr:`frame`.
        Always 3-D: one satellite is ``(1, n, 3)``.
    v_km_s : FloatArray
        Velocities, km/s, same shape.
    grid : TimeGrid
        The time axis. ``grid.epoch_jd`` is the instant the input elements were
        stated at, and ``grid.t_s[k]`` is the elapsed time of sample ``k``.
    frame : Frame
        Inertial frame the states are expressed in, inherited from the elements. A
        string equal to a member's value is resolved to the member, so
        ``traj.frame is Frame.TEME`` holds however it was written; see
        :func:`~quoss.orbits.frames.resolve_frame`.
    method : PropagationMethod
        The model that produced them. Carried so a result never has to be asked
        how it was made.

    Raises
    ------
    DomainError
        If the two arrays disagree in shape, if the shape is not
        ``(S, n_samples, 3)`` with ``S >= 1``, if the sample axis does not match
        ``grid.n``, or if ``frame`` names no frame or names one that rotates.

    Notes
    -----
    The gravity model is **not** stored. A ``TWO_BODY`` trajectory does not depend
    on the harmonics, so keeping a :class:`~quoss.orbits.perturbations.ZonalGravity`
    beside it would assert a dependence that does not exist; the model belongs to
    the scenario, which is what stage 4 hashes for provenance.

    This is not a :class:`~quoss.core.types.TimeSeries` and does not try to be:
    that type holds one named, unit-labelled quantity, and how a full result is
    serialised is a stage 4 decision.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.types import TimeGrid
    >>> from quoss.orbits.kepler import ClassicalElements
    >>> coe = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=np.deg2rad(98.19),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ... )
    >>> grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=600.0, step_s=60.0)
    >>> traj = propagate(coe, grid, method=PropagationMethod.TWO_BODY)
    >>> traj.r_km.shape
    (1, 11, 3)
    >>> traj.n_satellites, traj.n_samples
    (1, 11)
    >>> traj.r_km[0].shape
    (11, 3)
    """

    # Typed FloatArray and not Vec3Array on purpose: the alias documents the
    # shape (n, 3) with time on the leading axis, which every *slice* of these
    # satisfies but the stacked array itself does not. Claiming the alias here
    # would make the one place it is wrong the place it is most read.
    r_km: FloatArray
    v_km_s: FloatArray
    grid: TimeGrid
    frame: Frame
    method: PropagationMethod

    def __post_init__(self) -> None:
        """Check the arrays against each other and against the grid."""
        if self.r_km.shape != self.v_km_s.shape:
            raise DomainError(
                f"r_km has shape {self.r_km.shape} but v_km_s has {self.v_km_s.shape}; "
                f"a trajectory's position and velocity describe the same samples."
            )
        if self.r_km.ndim != 3 or self.r_km.shape[2] != 3:
            raise DomainError(
                f"A Trajectory holds shape (n_satellites, n_samples, 3), got "
                f"{self.r_km.shape}. A single satellite is (1, n, 3), not (n, 3)."
            )
        if self.r_km.shape[0] < 1:
            raise DomainError("A Trajectory must hold at least one satellite.")
        if self.r_km.shape[1] != self.grid.n:
            raise DomainError(
                f"The sample axis has length {self.r_km.shape[1]} but the grid has "
                f"{self.grid.n} samples."
            )
        # Resolved before it is judged, so that what gets stored is the member and
        # `traj.frame is Frame.TEME` means what a reader expects. Same two-step as
        # ClassicalElements, and for the same StrEnum reason.
        resolved_frame = resolve_frame(self.frame)
        if resolved_frame not in (Frame.TEME, Frame.GCRF):
            raise DomainError(
                f"A trajectory is expressed in an inertial frame, got {self.frame!r}. "
                f"Convert to ITRF with quoss.orbits.frames after propagating, not before."
            )
        # `object.__setattr__` because the dataclass is frozen: freezing the arrays
        # and storing the resolved frame are exactly the assignments it forbids.
        object.__setattr__(self, "frame", resolved_frame)
        object.__setattr__(self, "r_km", frozen_view(self.r_km))
        object.__setattr__(self, "v_km_s", frozen_view(self.v_km_s))

    @property
    def n_satellites(self) -> int:
        """Number of orbits held, the leading axis."""
        return int(self.r_km.shape[0])

    @property
    def n_samples(self) -> int:
        """Number of time samples, equal to ``grid.n``."""
        return int(self.r_km.shape[1])

    # No __len__ on purpose: a trajectory has two lengths, and picking one would
    # make `len(traj)` a coin flip at every call site.

    def __repr__(self) -> str:
        return (
            f"Trajectory(n_satellites={self.n_satellites}, n_samples={self.n_samples}, "
            f"method={self.method}, frame={self.frame}, epoch_jd={self.grid.epoch_jd!r})"
        )


def _validated_method(method: PropagationMethod) -> PropagationMethod:
    """Resolve ``method`` to a member, accepting the equal string.

    Parameters
    ----------
    method : PropagationMethod
        The member, or a string equal to one of its values.

    Returns
    -------
    PropagationMethod
        The member.

    Raises
    ------
    DomainError
        If the value names no member. Permissive at the boundary, strict inside:
        the same discipline as :class:`~quoss.orbits.kepler.ClassicalElements`
        accepting scalars and storing arrays.
    """
    try:
        return PropagationMethod(method)
    except ValueError as exc:
        valid = ", ".join(repr(str(member)) for member in PropagationMethod)
        raise DomainError(
            f"{method!r} is not a propagation method. Valid values are {valid}. "
            f"There is deliberately no analytic J2 mode yet; see quoss.orbits.propagator."
        ) from exc


def _two_body_states(
    elements: ClassicalElements,
    grid: TimeGrid,
    mu_km3_s2: float,
) -> tuple[FloatArray, FloatArray]:
    """Keplerian states for every satellite at every sample.

    Parameters
    ----------
    elements : ClassicalElements
        The ``S`` orbits, stated at ``grid.epoch_jd``.
    grid : TimeGrid
        The time axis.
    mu_km3_s2 : float
        Gravitational parameter, km^3/s^2.

    Returns
    -------
    r_km : FloatArray
        Positions, km, shape ``(S, n, 3)``.
    v_km_s : FloatArray
        Velocities, km/s, same shape.

    Notes
    -----
    Five of the six elements are constant in two-body motion, so the only work is
    advancing the mean anomaly and converting it back. The satellite and time axes
    are flattened into one stack of ``S * n`` element sets so that
    :func:`~quoss.orbits.kepler.coe_to_rv` runs **once** rather than once per
    satellite; ``np.repeat`` on the per-satellite values and ``np.tile`` on the
    times is what makes the flat order satellite-major, which is what the final
    ``reshape`` then assumes.
    """
    n_sat, n_t = elements.n, grid.n
    repeat = np.repeat
    mean_motion = mean_motion_rad_s(elements.semi_major_axis_km, mu_km3_s2)
    mean_at_epoch = mean_from_true_anomaly(elements.true_anomaly_rad, elements.eccentricity)

    mean_anomaly = advance_mean_anomaly(
        repeat(mean_at_epoch, n_t),
        repeat(mean_motion, n_t),
        np.tile(grid.t_s, n_sat),
    )
    eccentricity = repeat(elements.eccentricity, n_t)

    stack = ClassicalElements(
        semi_latus_rectum_km=repeat(elements.semi_latus_rectum_km, n_t),
        eccentricity=eccentricity,
        inclination_rad=repeat(elements.inclination_rad, n_t),
        raan_rad=repeat(elements.raan_rad, n_t),
        argp_rad=repeat(elements.argp_rad, n_t),
        true_anomaly_rad=true_from_mean_anomaly(mean_anomaly, eccentricity),
        frame=elements.frame,
        # Carried, not defaulted. Both labels the caller can hold are meaningful
        # here, and letting the flattened stack fall back to the OSCULATING
        # default would launder mean elements past the guard in `coe_to_rv`
        # below — the one place that stops the error in the module docstring's table.
        element_type=elements.element_type,
    )
    r_flat, v_flat = coe_to_rv(stack, mu_km3_s2)
    return r_flat.reshape(n_sat, n_t, 3), v_flat.reshape(n_sat, n_t, 3)


def _zonal_numeric_states(
    elements: ClassicalElements,
    grid: TimeGrid,
    gravity: ZonalGravity,
    rtol: float,
    atol_km: float,
) -> tuple[FloatArray, FloatArray]:
    """Integrated states for every satellite at every sample.

    Parameters
    ----------
    elements : ClassicalElements
        The ``S`` orbits, stated at ``grid.epoch_jd``.
    grid : TimeGrid
        The time axis.
    gravity : ZonalGravity
        The force model.
    rtol, atol_km : float
        Integrator tolerances, passed through to
        :func:`~quoss.orbits.perturbations.propagate_zonal`.

    Returns
    -------
    r_km : FloatArray
        Positions, km, shape ``(S, n, 3)``.
    v_km_s : FloatArray
        Velocities, km/s, same shape.

    Raises
    ------
    DomainError
        Re-raised from the integrator with the offending orbit named.
    ConvergenceError
        Likewise. A constellation of sixty tells you *which* one decayed.
    """
    n_sat, n_t = elements.n, grid.n
    r0_km, v0_km_s = coe_to_rv(elements, gravity.mu_km3_s2)

    r_km = np.empty((n_sat, n_t, 3), dtype=np.float64)
    v_km_s = np.empty((n_sat, n_t, 3), dtype=np.float64)
    for index in range(n_sat):
        try:
            r_km[index], v_km_s[index] = propagate_zonal(
                r0_km[index],
                v0_km_s[index],
                grid.t_s,
                gravity,
                rtol=rtol,
                atol_km=atol_km,
            )
        except DomainError as exc:
            raise DomainError(f"Orbit {index} of {n_sat}: {exc}") from exc
        except ConvergenceError as exc:
            raise ConvergenceError(f"Orbit {index} of {n_sat}: {exc}") from exc
    return r_km, v_km_s


def propagate(
    elements: ClassicalElements,
    grid: TimeGrid,
    *,
    method: PropagationMethod,
    gravity: ZonalGravity = EGM96_ZONAL,
    rtol: float = DEFAULT_ZONAL_RTOL,
    atol_km: float = DEFAULT_ZONAL_ATOL_KM,
) -> Trajectory:
    """Propagate elements stated at an epoch onto a time grid.

    The single entry point of the module. ``method`` is keyword-only and has no
    default: which model runs is a modelling decision, and a default would make
    it on the caller's behalf.

    Parameters
    ----------
    elements : ClassicalElements
        The orbits at ``grid.epoch_jd``, one or many. Both modes need
        :attr:`~quoss.orbits.kepler.ElementType.OSCULATING` elements — the kind
        :func:`~quoss.orbits.kepler.rv_to_coe` returns and a scenario writes —
        and mean ones are refused by
        :func:`~quoss.orbits.kepler.coe_to_rv`, which both branches go through.
        That refusal is not an extra check here: it is the same single guard,
        reached from both paths, which is why the flattened ``TWO_BODY`` stack
        carries the label instead of rebuilding it. ``elements.frame`` is carried
        to the result.
    grid : TimeGrid
        The time axis. Its epoch is when ``elements`` are from; its samples are
        elapsed seconds and may be negative, zero, or straddle zero.
    method : PropagationMethod
        Which model to run. Mandatory. A string equal to a member's value is
        accepted and resolved, so a scenario field needs no converter.
    gravity : ZonalGravity, optional
        The force model, defaulting to :data:`~quoss.orbits.perturbations.EGM96_ZONAL`.
        ``ZONAL_NUMERIC`` reads all of it; ``TWO_BODY`` reads only
        ``gravity.mu_km3_s2``, because that is what two-body motion depends on.
        That is not the silent model substitution
        :func:`~quoss.orbits.perturbations.secular_rates_j2` refuses — there a
        function named for J2 would have quietly dropped the J3 and J4 it was
        handed, whereas here ``method`` is mandatory and states in the call which
        model is wanted.
    rtol : float, optional
        Relative tolerance of the integrator. ``ZONAL_NUMERIC`` only.
    atol_km : float, optional
        Absolute tolerance of the integrator, km. ``ZONAL_NUMERIC`` only.

    Returns
    -------
    Trajectory
        Positions and velocities of shape ``(S, n, 3)``, with the grid, the frame
        and the method carried alongside.

    Raises
    ------
    DomainError
        If ``method`` names no member, if ``elements`` or ``grid`` are not of the
        expected type, if ``elements`` are
        :attr:`~quoss.orbits.kepler.ElementType.MEAN_BROUWER` — **every** mode
        refuses them, raised from :func:`~quoss.orbits.kepler.coe_to_rv`, which
        both branches pass through — if the tolerances are not positive, or if an
        orbit leaves the domain of the force model: a perigee inside the Earth,
        typically an initial state that was not the one the caller meant.
    ConvergenceError
        If the integrator fails, with the offending orbit named.

    Notes
    -----
    Nothing here reads ``grid.epoch_jd`` numerically. The physics is a function of
    elapsed seconds; the Julian date is carried through so that the modules which
    do need absolute time — GMST in :mod:`quoss.orbits.frames`, later the solar
    geometry — take it from one place. Two grids differing only in ``epoch_jd``
    therefore return identical states, and a test asserts exactly that.

    Examples
    --------
    One satellite, ten minutes of a sun-synchronous orbit, both ways:

    >>> import numpy as np
    >>> from quoss.core.types import TimeGrid
    >>> from quoss.orbits.kepler import ClassicalElements
    >>> sso = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=np.deg2rad(98.19),
    ...     raan_rad=0.0,
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ... )
    >>> grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=600.0, step_s=60.0)
    >>> kepler_traj = propagate(sso, grid, method=PropagationMethod.TWO_BODY)
    >>> zonal_traj = propagate(sso, grid, method=PropagationMethod.ZONAL_NUMERIC)
    >>> kepler_traj.r_km.shape
    (1, 11, 3)

    Ten minutes is already 1.7 km of disagreement, and it is J2, not error:

    >>> separation_km = np.linalg.norm(kepler_traj.r_km - zonal_traj.r_km, axis=-1)
    >>> float(np.round(separation_km[0, -1], 3))
    1.719

    A constellation is the same call with a stack of elements, and satellite ``s``
    comes out as a contiguous ``(n, 3)`` block:

    >>> pair = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=np.deg2rad(98.19),
    ...     raan_rad=np.array([0.0, np.pi]),
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=0.0,
    ... )
    >>> propagate(pair, grid, method=PropagationMethod.TWO_BODY).r_km.shape
    (2, 11, 3)
    """
    resolved = _validated_method(method)
    if not isinstance(elements, ClassicalElements):
        raise DomainError(
            f"propagate expects ClassicalElements, got {type(elements).__name__}. A state "
            f"vector goes through quoss.orbits.kepler.rv_to_coe first, which is where the "
            f"frame and the two-body assumption are made explicit."
        )
    if not isinstance(grid, TimeGrid):
        raise DomainError(
            f"propagate expects a TimeGrid, got {type(grid).__name__}. A bare array of "
            f"seconds has no epoch, and an epoch that is not stated is the wall clock."
        )

    if resolved is PropagationMethod.TWO_BODY:
        r_km, v_km_s = _two_body_states(elements, grid, gravity.mu_km3_s2)
    elif resolved is PropagationMethod.ZONAL_NUMERIC:
        r_km, v_km_s = _zonal_numeric_states(elements, grid, gravity, rtol, atol_km)
    else:  # pragma: no cover - unreachable until the enum grows
        raise NotImplementedError(
            f"{resolved!r} is declared in PropagationMethod but propagate() has no branch "
            f"for it. A member is only added together with the model that implements it."
        )

    return Trajectory(
        r_km=r_km,
        v_km_s=v_km_s,
        grid=grid,
        frame=elements.frame,
        method=resolved,
    )
