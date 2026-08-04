"""Tests for `quoss.orbits.propagator`.

This module adds no physics, so there is nothing here to validate against a
published number: `kepler.py` and `perturbations.py` already carry the V2 and V3
levels for the models being run. What has to be proved instead is that the
plumbing does not corrupt them, and that the choices the module makes are the
ones it says it makes.

Organised by claim, per `tests/golden/README.md`:

* ``TestTwoBodyIsKepler`` — V1: at the epoch the trajectory *is* ``coe_to_rv``,
  bit for bit, and one period later it closes on itself. Both are exact
  statements, so both are asserted at the floating-point floor rather than at a
  chosen tolerance.
* ``TestTheTwoModesAgreeOnAFlatEarth`` — V3, and the load-bearing test of the
  file: with every harmonic set to zero the two modes are two independent
  implementations of the same physics — a closed-form Kepler solve and a DOP853
  integration — and they must agree to the integrator's own accuracy.
* ``TestTheTwoModesAreNotInterchangeable`` — the other half of that: with the
  harmonics restored they must *disagree*, by an amount predicted from the node
  regression rather than from whatever the code happens to produce.
* ``TestSatelliteAxis`` — the ``(S, n, 3)`` decision. A satellite's slice must
  equal that satellite propagated alone, which is what catches a
  ``repeat``/``tile`` swap in the flattening.
* ``TestEpoch`` — the epoch is carried, never read: two grids differing only in
  ``epoch_jd`` return identical states. And negative elapsed times work, which
  is what an epoch in the middle of a window needs.
* ``TestModuleSurface`` — the deliberately incomplete enum. Every member
  dispatches, ``method`` has no default, and the member set is asserted so that
  adding ``J2_SECULAR_ANALYTIC`` is a decision someone takes rather than a diff
  that slips through.
* ``TestRejectsBadInput`` — V1.

The integrations are the expensive part. Everything is one revolution except the
single day-long case in ``TestTheTwoModesAreNotInterchangeable``.
"""

import inspect

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from quoss.core.constants import EGM96_MU_KM3_S2, EGM96_RADIUS_EQUATORIAL_KM
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import TimeGrid
from quoss.orbits import perturbations as perturbations_module
from quoss.orbits.frames import Frame
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    coe_to_rv,
    orbital_period_s,
)
from quoss.orbits.perturbations import (
    EGM96_ZONAL,
    ZonalGravity,
    secular_rates_j2,
)
from quoss.orbits.propagator import (
    PropagationMethod,
    Trajectory,
    propagate,
)

EPOCH_JD = 2460676.5
"""2025-01-01 00:00 UTC. Any epoch would do — that is the point of `TestEpoch`."""

TWO_BODY_ONLY = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
)
"""Every harmonic zero. Makes "no oblateness" a model rather than a mode."""

ISS_SEMI_MAJOR_AXIS_KM = 6798.0
ISS_INCLINATION_RAD = np.deg2rad(51.6)


def _iss_like() -> ClassicalElements:
    """One ISS-like orbit, with no angle left at zero.

    Every angle is deliberately non-zero and none of them equal: a bug that
    dropped or transposed one of ``Omega``, ``omega``, ``nu`` would survive a
    test case where they are all zero, and that is the cheapest kind of bug to
    ship.
    """
    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=ISS_SEMI_MAJOR_AXIS_KM,
        eccentricity=0.0005,
        inclination_rad=ISS_INCLINATION_RAD,
        raan_rad=0.3,
        argp_rad=1.0,
        true_anomaly_rad=0.5,
    )


def _constellation() -> ClassicalElements:
    """Three orbits that differ in every element, so no two can be confused."""
    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=np.array([6798.0, 7078.137, 7200.0]),
        eccentricity=np.array([0.0005, 0.001, 0.01]),
        inclination_rad=np.deg2rad(np.array([51.6, 98.19, 28.5])),
        raan_rad=np.array([0.3, 2.0, 4.0]),
        argp_rad=np.array([1.0, 3.0, 5.0]),
        true_anomaly_rad=np.array([0.5, 2.5, 4.5]),
    )


def _period_s(semi_major_axis_km: float = ISS_SEMI_MAJOR_AXIS_KM) -> float:
    return float(orbital_period_s(semi_major_axis_km)[0])


# --------------------------------------------------------------------------- #
# The two-body mode against the module it delegates to
# --------------------------------------------------------------------------- #
class TestTwoBodyIsKepler:
    @pytest.mark.physics
    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_the_epoch_sample_is_the_initial_state_exactly(self, method: PropagationMethod) -> None:
        """At ``t = 0`` no propagation has happened, so nothing may change.

        Exact equality, not ``allclose``: the analytic mode evaluates the same
        expression as ``coe_to_rv`` with ``M = M0``, and the numerical one writes
        the initial state straight into the output rather than integrating a
        zero-length span. Both are exact by construction, so a tolerance here
        would only hide a wiring mistake.
        """
        elements = _iss_like()
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))
        r0_km, v0_km_s = coe_to_rv(elements)

        traj = propagate(elements, grid, method=method)

        np.testing.assert_array_equal(traj.r_km[0, 0], r0_km[0])
        np.testing.assert_array_equal(traj.v_km_s[0, 0], v0_km_s[0])

    @pytest.mark.physics
    def test_one_keplerian_period_closes_the_orbit(self) -> None:
        """Two-body motion is periodic, so ``T`` later the state repeats.

        The residual is 6.2e-12 km — 6 nanometres — which is the accumulated
        rounding of one mean-anomaly advance and one element-to-state conversion,
        not a modelling error. The bound is set at 1e-6 km (1 mm), five orders
        above the measurement, because what would break this is a wrong period or
        a mishandled revolution count, and either would show up as kilometres.
        """
        elements = _iss_like()
        period_s = _period_s()
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, period_s]))

        traj = propagate(elements, grid, method=PropagationMethod.TWO_BODY)

        closure_km = float(np.linalg.norm(traj.r_km[0, 1] - traj.r_km[0, 0]))
        assert closure_km < 1e-6

    @pytest.mark.physics
    def test_specific_energy_and_angular_momentum_are_conserved(self) -> None:
        """The two two-body integrals of motion, over a full revolution.

        A propagator that advanced the anomaly correctly but rebuilt the state
        from a corrupted element would still look plausible in a plot; it would
        not conserve these. Both are checked *relative* to their own size, so the
        bound means the same thing for any orbit.
        """
        elements = _iss_like()
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=_period_s(), n=64)

        traj = propagate(elements, grid, method=PropagationMethod.TWO_BODY)

        r_km, v_km_s = traj.r_km[0], traj.v_km_s[0]
        r_mag = np.linalg.norm(r_km, axis=1)
        energy = 0.5 * np.sum(v_km_s**2, axis=1) - EGM96_MU_KM3_S2 / r_mag
        momentum = np.linalg.norm(np.cross(r_km, v_km_s), axis=1)

        assert float(np.ptp(energy) / np.abs(energy).mean()) < 1e-12
        assert float(np.ptp(momentum) / momentum.mean()) < 1e-12

    @pytest.mark.physics
    def test_negative_times_run_backwards(self) -> None:
        """Propagating back one period must land on the forward result.

        This is the property an epoch in the middle of a scenario window relies
        on, and it is worth its own test because "backwards" is where an
        unwrapped anomaly or a sign convention goes wrong.
        """
        elements = _iss_like()
        period_s = _period_s()
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([-period_s, 0.0, period_s]))

        traj = propagate(elements, grid, method=PropagationMethod.TWO_BODY)

        assert float(np.linalg.norm(traj.r_km[0, 0] - traj.r_km[0, 1])) < 1e-6
        assert float(np.linalg.norm(traj.r_km[0, 2] - traj.r_km[0, 1])) < 1e-6


# --------------------------------------------------------------------------- #
# The two modes against each other — V3, in both directions
# --------------------------------------------------------------------------- #
class TestTheTwoModesAgreeOnAFlatEarth:
    """With no harmonics, the two modes are the same physics by two routes.

    This is the only cross-check in the file that qualifies as V3, and it is
    genuinely independent: one side solves Kepler's equation in closed form
    (Markley, no iteration) and rotates a perifocal state; the other steps an
    eighth-order Runge-Kutta through ``-mu r / |r|^3``. They share nothing but
    the initial state and ``mu``, so agreement is evidence and not a tautology.
    """

    @pytest.mark.physics
    @pytest.mark.parametrize("revolutions", [1.0, 3.0])
    def test_positions_agree_to_the_integrator_tolerance(self, revolutions: float) -> None:
        """Measured: 13 micrometres over one revolution, 40 over three.

        The bound is 1 mm, which is derived rather than fitted: the integrator
        runs with ``atol_km = 1e-9`` (a micrometre) per step and takes a few
        hundred steps per revolution, so tens of micrometres is what its own
        stated accuracy allows to accumulate. A millimetre leaves ~75x of
        headroom and is still six orders below anything the link budget can see.
        """
        elements = _iss_like()
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=_period_s() * revolutions, n=40)

        kepler = propagate(elements, grid, method=PropagationMethod.TWO_BODY, gravity=TWO_BODY_ONLY)
        integrated = propagate(
            elements, grid, method=PropagationMethod.ZONAL_NUMERIC, gravity=TWO_BODY_ONLY
        )

        separation_km = np.linalg.norm(kepler.r_km - integrated.r_km, axis=-1)
        assert float(separation_km.max()) < 1e-6

    @pytest.mark.physics
    def test_velocities_agree_too(self) -> None:
        """Measured 1.4e-5 mm/s; bounded at 1e-3 mm/s.

        Velocity is checked separately because it is the field a Doppler shift
        is computed from, and a state that is right in position and wrong in
        velocity is exactly the failure a position-only test would pass.
        """
        elements = _iss_like()
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=_period_s(), n=40)

        kepler = propagate(elements, grid, method=PropagationMethod.TWO_BODY, gravity=TWO_BODY_ONLY)
        integrated = propagate(
            elements, grid, method=PropagationMethod.ZONAL_NUMERIC, gravity=TWO_BODY_ONLY
        )

        difference_km_s = np.linalg.norm(kepler.v_km_s - integrated.v_km_s, axis=-1)
        assert float(difference_km_s.max()) < 1e-9


class TestTheTwoModesAreNotInterchangeable:
    """And with the harmonics restored, they must disagree — by a predicted amount.

    The enum exists because the two modes are different physics. A test that only
    proved they agree in the flat-Earth limit would leave that claim unmeasured,
    and a scenario could pick ``TWO_BODY`` for a multi-day study without anything
    complaining.
    """

    @pytest.mark.physics
    @pytest.mark.slow
    def test_one_day_of_j2_separates_them_by_the_node_regression(self) -> None:
        """Measured 720 km after a day; the node term alone predicts 460 km.

        The prediction is computed here from ``secular_rates_j2`` rather than
        written down: rotating the orbital plane by ``dOmega`` displaces a
        satellite at radius ``r`` by about ``r * dOmega * sin i``. The measured
        separation is 1.56 times that, and the excess is the other two secular
        effects the same theory carries — apsidal precession and the gap between
        the Keplerian and the anomalistic period — so the window is set at
        ``[0.5, 3.0]`` times the node term: wide enough not to be a fit, narrow
        enough that a missing or doubled J2 falls outside it.
        """
        elements = _iss_like()
        seconds_per_day = 86400.0
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=seconds_per_day, n=25)

        kepler = propagate(elements, grid, method=PropagationMethod.TWO_BODY)
        zonal = propagate(elements, grid, method=PropagationMethod.ZONAL_NUMERIC)

        separation_km = float(np.linalg.norm(kepler.r_km[0, -1] - zonal.r_km[0, -1]))
        # Relabelled, not converted: the prediction only needs the size of the
        # node rate to within a few per mille, and the mean/osculating gap is
        # O(J2) ~ 1e-3. The assertion below spans a factor of six, so it cannot
        # be sensitive to it — but the flag makes saying so compulsory.
        as_mean = elements.relabelled_as(ElementType.MEAN_BROUWER)
        node_shift_rad = abs(float(secular_rates_j2(as_mean).raan_rad_s[0])) * seconds_per_day
        predicted_km = ISS_SEMI_MAJOR_AXIS_KM * node_shift_rad * np.sin(ISS_INCLINATION_RAD)

        assert 0.5 * predicted_km < separation_km < 3.0 * predicted_km

    @pytest.mark.physics
    def test_the_gap_grows_with_time(self) -> None:
        """It is not an offset, it is a drift, and that is what makes it fatal.

        A constant 40 km error would be a bias a scenario could live with. This
        one accumulates: after fifteen revolutions it is an order of magnitude
        larger than after one, because J2 changes the *rate* at which the orbit
        turns, not just where it sits.
        """
        elements = _iss_like()
        period_s = _period_s()
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([period_s, 15.0 * period_s]))

        kepler = propagate(elements, grid, method=PropagationMethod.TWO_BODY)
        zonal = propagate(elements, grid, method=PropagationMethod.ZONAL_NUMERIC)

        gap_km = np.linalg.norm(kepler.r_km[0] - zonal.r_km[0], axis=-1)
        assert gap_km[1] > 8.0 * gap_km[0]


# --------------------------------------------------------------------------- #
# The (S, n, 3) decision
# --------------------------------------------------------------------------- #
class TestSatelliteAxis:
    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_a_single_orbit_is_still_three_dimensional(self, method: PropagationMethod) -> None:
        """``(1, n, 3)``, never ``(n, 3)``, so no consumer branches on shape."""
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)

        traj = propagate(_iss_like(), grid, method=method)

        assert traj.r_km.shape == (1, grid.n, 3)
        assert traj.v_km_s.shape == (1, grid.n, 3)
        assert (traj.n_satellites, traj.n_samples) == (1, grid.n)

    @pytest.mark.physics
    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_each_slice_equals_that_orbit_propagated_alone(self, method: PropagationMethod) -> None:
        """The test that makes the flattening honest.

        ``_two_body_states`` builds one stack of ``S * n`` element sets with
        ``np.repeat`` on the elements and ``np.tile`` on the times, then reshapes
        to ``(S, n, 3)``. Swapping those two calls produces an array of exactly
        the right shape, full of the right numbers, in the wrong places — and
        every shape assertion in this file would still pass. Only comparing a
        slice against an independent single-orbit run catches it.

        Exact equality is demanded because both routes perform the same
        arithmetic on the same values; anything but bit-identical would mean the
        stacking changed a number.
        """
        constellation = _constellation()
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=1200.0, step_s=120.0)

        together = propagate(constellation, grid, method=method)

        assert together.r_km.shape == (3, grid.n, 3)
        for index in range(constellation.n):
            single = ClassicalElements(
                semi_latus_rectum_km=constellation.semi_latus_rectum_km[index],
                eccentricity=constellation.eccentricity[index],
                inclination_rad=constellation.inclination_rad[index],
                raan_rad=constellation.raan_rad[index],
                argp_rad=constellation.argp_rad[index],
                true_anomaly_rad=constellation.true_anomaly_rad[index],
                frame=constellation.frame,
            )
            alone = propagate(single, grid, method=method)
            np.testing.assert_array_equal(together.r_km[index], alone.r_km[0])
            np.testing.assert_array_equal(together.v_km_s[index], alone.v_km_s[0])

    def test_a_slice_is_contiguous_and_ready_for_the_frames_layer(self) -> None:
        """Satellite-major was chosen for this: ``traj.r_km[s]`` needs no copy.

        Under the rejected ``(n, S, 3)`` layout the same track is ``r[:, s]``,
        which is a strided view: still a view, but not contiguous, so every
        downstream call that wants a C-ordered buffer materialises a copy. The
        assertions are on the array's own flags and on shared memory, so they
        fail if the layout is ever transposed.
        """
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)

        traj = propagate(_constellation(), grid, method=PropagationMethod.TWO_BODY)

        track = traj.r_km[1]
        assert track.shape == (grid.n, 3)
        assert track.flags["C_CONTIGUOUS"]
        assert np.shares_memory(track, traj.r_km)
        # And the rejected layout would not be. Built explicitly rather than as a
        # transposed view, because a view shares this array's own C order and
        # would make the comparison meaningless.
        time_major = np.ascontiguousarray(traj.r_km.transpose(1, 0, 2))
        assert not time_major[:, 1].flags["C_CONTIGUOUS"]


# --------------------------------------------------------------------------- #
# The epoch decision
# --------------------------------------------------------------------------- #
class TestEpoch:
    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_the_epoch_is_carried_but_never_read(self, method: PropagationMethod) -> None:
        """Two grids differing only in ``epoch_jd`` give identical states.

        This is the module's claim that the physics is a function of elapsed
        seconds alone. It matters in the other direction too: the day the states
        *do* start depending on absolute time — a solar or lunar model, drag with
        a real atmosphere — this test fails, and that is the moment to notice
        rather than three modules later.
        """
        elements = _iss_like()
        t_s = np.array([0.0, 300.0, 600.0])
        early = propagate(elements, TimeGrid(epoch_jd=2451545.0, t_s=t_s), method=method)
        late = propagate(elements, TimeGrid(epoch_jd=EPOCH_JD, t_s=t_s), method=method)

        np.testing.assert_array_equal(early.r_km, late.r_km)
        np.testing.assert_array_equal(early.v_km_s, late.v_km_s)
        assert early.grid.epoch_jd == 2451545.0
        assert late.grid.epoch_jd == EPOCH_JD

    @pytest.mark.physics
    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_a_grid_straddling_the_epoch_works(self, method: PropagationMethod) -> None:
        """What a TLE gives: elements from an epoch inside the window.

        Both modes must run outwards in both directions. The sample at ``t = 0``
        is still the initial state exactly, so the check is that the negative
        half was not silently dropped or evaluated forwards.
        """
        elements = _iss_like()
        quarter_s = _period_s() / 4.0
        grid = TimeGrid(
            epoch_jd=EPOCH_JD, t_s=np.array([-2.0 * quarter_s, -quarter_s, 0.0, quarter_s])
        )
        r0_km, _ = coe_to_rv(elements)

        traj = propagate(elements, grid, method=method)

        np.testing.assert_array_equal(traj.r_km[0, 2], r0_km[0])
        # A quarter period before and a quarter after are distinct points, each
        # about one orbital radius away from the epoch position.
        for index in (1, 3):
            offset_km = float(np.linalg.norm(traj.r_km[0, index] - r0_km[0]))
            assert 0.5 * ISS_SEMI_MAJOR_AXIS_KM < offset_km < 2.5 * ISS_SEMI_MAJOR_AXIS_KM

    @pytest.mark.physics
    def test_a_grid_that_never_reaches_the_epoch_is_fine(self) -> None:
        """All-negative samples: elements from *after* the window of interest."""
        elements = _iss_like()
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([-600.0, -300.0]))

        forward = propagate(
            elements,
            TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0])),
            method=PropagationMethod.ZONAL_NUMERIC,
        )
        backward = propagate(elements, grid, method=PropagationMethod.ZONAL_NUMERIC)

        assert backward.r_km.shape == (1, 2, 3)
        # 300 s before the epoch is a fifth of a revolution away, so the states
        # are neither equal to nor wildly far from the epoch state.
        offset_km = float(np.linalg.norm(backward.r_km[0, 1] - forward.r_km[0, 0]))
        assert 100.0 < offset_km < 2.0 * ISS_SEMI_MAJOR_AXIS_KM


# --------------------------------------------------------------------------- #
# The module surface: the enum is incomplete on purpose
# --------------------------------------------------------------------------- #
class TestModuleSurface:
    def test_the_enum_holds_exactly_the_implemented_modes(self) -> None:
        """The deliberate gap, asserted so that closing it is a decision.

        ``J2_SECULAR_ANALYTIC`` is missing because the analytic mode needs mean
        elements and this project has only osculating ones — a ~219 km/day gap,
        not a rounding error. When the Brouwer-Lyddane transformation lands, this
        test fails, and updating it is the moment to also update the module
        docstring and ADR 0005. That is the intended workflow, not an
        inconvenience: a failing test here means someone added a mode, and the
        question is whether they added the model with it.
        """
        assert {member.value for member in PropagationMethod} == {"two_body", "zonal_numeric"}
        assert not hasattr(PropagationMethod, "J2_SECULAR_ANALYTIC")

    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_every_declared_member_actually_propagates(self, method: PropagationMethod) -> None:
        """A member with no branch behind it raises ``NotImplementedError``.

        Parametrising over the enum rather than over a hand-written list is the
        whole point: adding a member without wiring it fails here immediately,
        which is what lets the enum grow "without touching anyone".
        """
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))

        traj = propagate(_iss_like(), grid, method=method)

        assert traj.method is method
        assert np.all(np.isfinite(traj.r_km))

    def test_method_is_keyword_only_and_has_no_default(self) -> None:
        """A default would be a modelling decision taken for the caller.

        Asserted on the signature, in the same spirit as the test in
        ``test_perturbations.py`` that pins ``secular_rates_j2`` to having no
        parameter where a J3 could be passed: the shape of the API is the
        safeguard, so a refactor must not be able to soften it quietly.
        """
        parameter = inspect.signature(propagate).parameters["method"]

        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
        assert parameter.default is inspect.Parameter.empty

    def test_a_string_is_accepted_and_resolved(self) -> None:
        """So a scenario field can be YAML text without a converter."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        traj = propagate(_iss_like(), grid, method="two_body")  # type: ignore[arg-type]

        assert traj.method is PropagationMethod.TWO_BODY

    def test_the_method_travels_with_the_result(self) -> None:
        """Provenance: a trajectory can always say which model made it."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        for method in PropagationMethod:
            assert propagate(_iss_like(), grid, method=method).method is method

    def test_the_frame_is_inherited_from_the_elements(self) -> None:
        """Not defaulted here: a trajectory is in whatever frame its orbit was."""
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=ISS_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0005,
            inclination_rad=ISS_INCLINATION_RAD,
            raan_rad=0.3,
            argp_rad=1.0,
            true_anomaly_rad=0.5,
            frame=Frame.GCRF,
        )
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        assert propagate(elements, grid, method=PropagationMethod.TWO_BODY).frame is Frame.GCRF

    def test_a_trajectory_is_immutable(self) -> None:
        """Frozen, like every other container in the physics layer."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))
        traj = propagate(_iss_like(), grid, method=PropagationMethod.TWO_BODY)

        with pytest.raises(AttributeError):
            traj.method = PropagationMethod.ZONAL_NUMERIC  # type: ignore[misc]

    def test_repr_says_what_it_is(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)

        text = repr(propagate(_constellation(), grid, method=PropagationMethod.TWO_BODY))

        assert "n_satellites=3" in text
        assert "n_samples=11" in text
        assert "two_body" in text


# --------------------------------------------------------------------------- #
# Bad input
# --------------------------------------------------------------------------- #
class TestRejectsBadInput:
    def test_an_unknown_method_names_the_valid_ones(self) -> None:
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        with pytest.raises(DomainError, match="not a propagation method"):
            propagate(_iss_like(), grid, method="j2_secular")  # type: ignore[arg-type]

    @pytest.mark.parametrize("method", list(PropagationMethod))
    def test_every_mode_refuses_mean_elements(self, method: PropagationMethod) -> None:
        """Both modes propagate osculating elements, and neither can tell by itself.

        Parametrised over the enum for the same reason
        ``test_every_declared_member_actually_propagates`` is: the day
        ``J2_SECULAR_ANALYTIC`` arrives it will be the one mode that *wants* mean
        elements, and this test failing is the reminder that its branch needs its
        own rule rather than inheriting this one.

        The ``TWO_BODY`` half is the load-bearing case. That mode does not hand
        the caller's elements to ``coe_to_rv``; it builds a flattened ``S * n``
        stack first, and if that stack took the default label it would launder
        mean elements straight past the only guard there is. Nothing about the
        output shape would look wrong.
        """
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))
        mean_elements = _iss_like().relabelled_as(ElementType.MEAN_BROUWER)

        with pytest.raises(DomainError, match="osculating by definition"):
            propagate(mean_elements, grid, method=method)

    def test_a_state_vector_is_not_elements(self) -> None:
        """The conversion is the caller's, and greppable, on purpose."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))
        r_km, _ = coe_to_rv(_iss_like())

        with pytest.raises(DomainError, match="rv_to_coe"):
            propagate(r_km, grid, method=PropagationMethod.TWO_BODY)  # type: ignore[arg-type]

    def test_a_bare_array_of_seconds_is_not_a_time_grid(self) -> None:
        """Because it carries no epoch, and an unstated epoch is the wall clock."""
        with pytest.raises(DomainError, match="epoch"):
            propagate(
                _iss_like(),
                np.array([0.0, 60.0]),  # type: ignore[arg-type]
                method=PropagationMethod.TWO_BODY,
            )

    @pytest.mark.parametrize(
        ("rtol", "atol_km"),
        [(0.0, 1e-9), (-1e-12, 1e-9), (1e-12, 0.0), (1e-12, -1e-9)],
    )
    def test_non_positive_tolerances_are_rejected(self, rtol: float, atol_km: float) -> None:
        """Forwarded to the integrator, which is where the check already lives."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))

        with pytest.raises(DomainError, match="must be finite and positive"):
            propagate(
                _iss_like(),
                grid,
                method=PropagationMethod.ZONAL_NUMERIC,
                rtol=rtol,
                atol_km=atol_km,
            )

    def test_an_integrator_failure_also_names_the_orbit(self) -> None:
        """The second failure path, forced the same way ``test_perturbations.py`` does.

        Every state that genuinely breaks DOP853 is rejected earlier by the force
        model's domain check, so this branch cannot be reached physically — and
        the day it *is* reached is the day someone needs its message to name the
        orbit. The stub fails on the second call rather than the first, so the
        index is shown to track the loop instead of being a hard-coded zero.
        """
        real_solve_ivp = solve_ivp
        calls = {"n": 0}

        class _FailedSolution:
            success = False
            message = "Required step size is less than spacing between numbers."

        def _fails_the_second_time(*args: object, **kwargs: object) -> object:
            calls["n"] += 1
            if calls["n"] < 2:
                return real_solve_ivp(*args, **kwargs)
            return _FailedSolution()

        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(perturbations_module, "solve_ivp", _fails_the_second_time)
            with pytest.raises(ConvergenceError, match=r"Orbit 1 of 3"):
                propagate(_constellation(), grid, method=PropagationMethod.ZONAL_NUMERIC)

    @pytest.mark.physics
    def test_a_decayed_orbit_names_which_one_it_was(self) -> None:
        """A constellation of sixty must not report "an orbit" failed.

        The perigee of the second orbit here is below the reference radius, so
        the force model rejects it when the integration arrives — which is the
        per-evaluation validation ``perturbations.py`` does on purpose. What this
        test pins is the added context: the index, and how many there were.
        """
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=np.array([7078.137, 7078.137]),
            eccentricity=np.array([0.001, 0.2]),
            inclination_rad=ISS_INCLINATION_RAD,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=_period_s(7078.137), n=20)

        with pytest.raises((DomainError, ConvergenceError), match=r"Orbit 1 of 2"):
            propagate(elements, grid, method=PropagationMethod.ZONAL_NUMERIC)

    def test_a_trajectory_checks_its_arrays_against_its_grid(self) -> None:
        """The container validates rather than trusting whoever built it."""
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)
        good = np.zeros((1, grid.n, 3))

        with pytest.raises(DomainError, match="same samples"):
            Trajectory(
                r_km=good,
                v_km_s=np.zeros((1, grid.n - 1, 3)),
                grid=grid,
                frame=Frame.TEME,
                method=PropagationMethod.TWO_BODY,
            )
        with pytest.raises(DomainError, match=r"\(1, n, 3\)"):
            Trajectory(
                r_km=np.zeros((grid.n, 3)),
                v_km_s=np.zeros((grid.n, 3)),
                grid=grid,
                frame=Frame.TEME,
                method=PropagationMethod.TWO_BODY,
            )
        with pytest.raises(DomainError, match="but the grid has"):
            Trajectory(
                r_km=np.zeros((1, grid.n + 1, 3)),
                v_km_s=np.zeros((1, grid.n + 1, 3)),
                grid=grid,
                frame=Frame.TEME,
                method=PropagationMethod.TWO_BODY,
            )
        with pytest.raises(DomainError, match="at least one satellite"):
            Trajectory(
                r_km=np.zeros((0, grid.n, 3)),
                v_km_s=np.zeros((0, grid.n, 3)),
                grid=grid,
                frame=Frame.TEME,
                method=PropagationMethod.TWO_BODY,
            )

    def test_a_trajectory_rejects_a_rotating_frame(self) -> None:
        """States in ITRF are not a propagation result; they are a conversion of one."""
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        with pytest.raises(DomainError, match="inertial frame"):
            Trajectory(
                r_km=np.zeros((1, 1, 3)),
                v_km_s=np.zeros((1, 1, 3)),
                grid=grid,
                frame=Frame.ITRF,
                method=PropagationMethod.TWO_BODY,
            )

    def test_the_zonal_mode_rejects_a_position_inside_the_earth(self) -> None:
        """Inherited from the force model, and worth pinning at this level too."""
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=1000.0,
            eccentricity=0.0,
            inclination_rad=0.0,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))

        with pytest.raises(DomainError, match="reference radius"):
            propagate(elements, grid, method=PropagationMethod.ZONAL_NUMERIC, gravity=EGM96_ZONAL)
