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
* ``TestModuleSurface`` — the deliberately incomplete enum, and its one member
  that is complete but lives elsewhere. Every member ``propagate()`` implements
  dispatches, ``PropagationMethod.SGP4`` does not and says so loudly (it is
  ``quoss.orbits.tle.propagate_tle``'s), ``method`` has no default, and the
  member set is asserted so that adding ``J2_SECULAR_ANALYTIC`` is a decision
  someone takes rather than a diff that slips through.
* ``TestTrajectoryIsWhatItSaysItIs`` — the container's own claims: the states are
  read-only (frozen views, deliberately not copies) and the frame is stored as an
  enum member rather than as whatever string was handed in. Both were false until
  2026-08-04 and neither was detectable by any existing test.
* ``TestWhatNotHavingBrouwerLyddaneCosts`` — the figures the module docstring, two
  ADRs and a user-facing ``DomainError`` quote. Writing this class is what showed
  the previously documented ones were 5.9 times too small, and that no single
  number is right because the cost depends on orbital phase.
* ``TestRejectsBadInput`` — V1.

The integrations are the expensive part. Everything is one revolution except the
day-long case in ``TestTheTwoModesAreNotInterchangeable`` and the fifteen-revolution
cases in ``TestWhatNotHavingBrouwerLyddaneCosts``, which are marked ``slow`` and cost
1.5 s together.
"""

import inspect

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from quoss.core.constants import EGM96_J2, EGM96_MU_KM3_S2, EGM96_RADIUS_EQUATORIAL_KM
from quoss.core.errors import ConvergenceError, DomainError
from quoss.core.types import TimeGrid
from quoss.orbits import perturbations as perturbations_module
from quoss.orbits.frames import Frame
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    advance_mean_anomaly,
    coe_to_rv,
    mean_from_true_anomaly,
    orbital_period_s,
    rv_to_coe,
    true_from_mean_anomaly,
)
from quoss.orbits.perturbations import (
    EGM96_ZONAL,
    ZonalGravity,
    propagate_zonal,
    secular_rates_j2,
)
from quoss.orbits.propagator import (
    PropagationMethod,
    Trajectory,
    propagate,
)

EPOCH_JD = 2460676.5
"""2025-01-01 00:00 UTC. Any epoch would do — that is the point of `TestEpoch`."""

PROPAGATE_MODES = (PropagationMethod.TWO_BODY, PropagationMethod.ZONAL_NUMERIC)
"""Members ``propagate()`` can actually run. ``PropagationMethod.SGP4`` is
deliberately excluded from every parametrisation that calls ``propagate()``
expecting success — it belongs to ``quoss.orbits.tle.propagate_tle`` instead,
and is tested on its own in ``TestModuleSurface.test_sgp4_is_not_wired_into_propagate``
and in ``tests/orbits/test_tle.py``."""

TWO_BODY_ONLY = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
)
"""Every harmonic zero. Makes "no oblateness" a model rather than a mode."""

J2_ONLY = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
    j2=EGM96_J2,
)
"""J2 and nothing else, on **both** sides of the mean/osculating comparison.

`secular_rates_j2` is a first-order J2 theory and has nowhere to put a J3 or a
J4, so leaving them on in the reference would add a second, unrelated difference
to what `TestWhatNotHavingBrouwerLyddaneCosts` measures. With J2 alone the only
thing separating the two paths is which ellipse the six numbers describe.
"""

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
    @pytest.mark.parametrize("method", PROPAGATE_MODES)
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
# The number in the error message
# --------------------------------------------------------------------------- #
def _secular_analytic_states(
    elements: ClassicalElements, t_s: np.ndarray, gravity: ZonalGravity
) -> tuple[np.ndarray, np.ndarray]:
    """Run the analytic J2 propagator ``PropagationMethod`` deliberately omits.

    Four lines of physics: take the three secular rates, advance ``Omega``,
    ``omega`` and ``M`` with them, and convert back. It lives here and not in
    ``src/`` for the reason ADR 0005 gives — shipping it would mean shipping a
    mode that returns plausible numbers and is wrong by the table below — but it
    has to exist *somewhere* for that table to be a measurement rather than a
    claim.

    Both directions of ``relabelled_as`` appear, and that is the most honest use
    the flag has. Going in, the osculating elements are relabelled mean because
    that is the lie under test: the secular theory is a statement about mean
    elements and these are not. Coming out, the advanced set is relabelled
    osculating so that :func:`coe_to_rv` will convert it. Neither call changes a
    number; each one is the test saying out loud which check it is stepping around
    and why.
    """
    rates = secular_rates_j2(
        elements.relabelled_as(ElementType.MEAN_BROUWER),
        mu_km3_s2=gravity.mu_km3_s2,
        r_equatorial_km=gravity.r_equatorial_km,
        j2=gravity.j2,
    )
    n = t_s.size
    mean_at_epoch = mean_from_true_anomaly(elements.true_anomaly_rad, elements.eccentricity)
    mean_anomaly = advance_mean_anomaly(
        np.repeat(mean_at_epoch, n), np.repeat(rates.mean_anomaly_rad_s, n), t_s
    )
    eccentricity = np.repeat(elements.eccentricity, n)
    advanced = ClassicalElements(
        semi_latus_rectum_km=np.repeat(elements.semi_latus_rectum_km, n),
        eccentricity=eccentricity,
        inclination_rad=np.repeat(elements.inclination_rad, n),
        raan_rad=np.repeat(elements.raan_rad, n) + rates.raan_rad_s[0] * t_s,
        argp_rad=np.repeat(elements.argp_rad, n) + rates.argp_rad_s[0] * t_s,
        true_anomaly_rad=true_from_mean_anomaly(mean_anomaly, eccentricity),
        element_type=ElementType.MEAN_BROUWER,
    )
    return coe_to_rv(advanced.relabelled_as(ElementType.OSCULATING), gravity.mu_km3_s2)


def _rsw_components(
    error_km: np.ndarray, r_km: np.ndarray, v_km_s: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Split an error vector into radial, along-track and cross-track parts.

    The decomposition is what turns "they differ by 86 km" into an argument: a
    short-period wobble shows up as bounded radial and cross-track terms, while a
    rate error shows up as an along-track term that grows. Only the second one
    moves a pass window.

    Basis at each sample of the *reference* trajectory: ``r_hat`` outward,
    ``w_hat`` along the angular momentum (normal to the orbit plane), and
    ``s_hat = w_hat x r_hat`` completing the triad in the direction of motion.
    """
    r_hat = r_km / np.linalg.norm(r_km, axis=-1, keepdims=True)
    h = np.cross(r_km, v_km_s)
    w_hat = h / np.linalg.norm(h, axis=-1, keepdims=True)
    s_hat = np.cross(w_hat, r_hat)
    return (
        np.einsum("ij,ij->i", error_km, r_hat),
        np.einsum("ij,ij->i", error_km, s_hat),
        np.einsum("ij,ij->i", error_km, w_hat),
    )


def _osculating_axis_offset_km(elements: ClassicalElements, gravity: ZonalGravity) -> float:
    """Return ``a`` at the epoch minus its own time-average over one revolution.

    The predictor of the whole effect, and computable with what this project
    already has — no Brouwer-Lyddane required. Under J2 the osculating semi-major
    axis oscillates about a mean value with the short-period term; how far the
    stated epoch sits from that mean is what sets the rate error, and therefore
    the drift.

    The time average over one Keplerian period is a stand-in for the Brouwer mean,
    not the same thing: they differ at ``O(J2)`` relative. That is why the
    tolerances on the prediction below are a few per cent rather than a few per
    mille.
    """
    period_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
    dense_s = np.linspace(0.0, period_s, 401)[1:]
    r_km, v_km_s = propagate_zonal(*coe_to_rv(elements, gravity.mu_km3_s2), dense_s, gravity)
    axis_km = rv_to_coe(r_km, v_km_s, gravity.mu_km3_s2).semi_major_axis_km
    return float(elements.semi_major_axis_km[0]) - float(axis_km.mean())


def _sso(true_anomaly_rad: float = 0.0) -> ClassicalElements:
    """700 km sun-synchronous, the orbit every quoted figure of the mismatch uses."""
    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=7078.137,
        eccentricity=0.001,
        inclination_rad=np.deg2rad(98.2),
        raan_rad=0.0,
        argp_rad=0.0,
        true_anomaly_rad=true_anomaly_rad,
    )


class TestWhatNotHavingBrouwerLyddaneCosts:
    """The figures the docstrings and the ``DomainError`` quote, measured here.

    Why this class exists at all: the cost of confusing mean and osculating
    elements is quoted in the module docstring, in two ADRs, and — the part that
    makes it load-bearing — in the text of an exception a user reads. It had been
    measured once, by hand, and written down in prose. Nothing reproduced it, so a
    changed constant or integrator default could have left every one of those
    numbers stale with no test going red. It is the only quantitative claim in the
    project without an oracle, which is exactly the situation
    ``tests/golden/README.md`` exists to forbid.

    Writing it down found that the numbers *were* wrong — the earlier figures of
    14.6 km per revolution and 219 km per day are 5.9 times too small — and, more
    usefully, that no single number can be right: the drift depends on where in
    the orbit the elements are stated, over three orders of magnitude. Both
    findings are asserted below.

    This is V1 in the sense of ``tests/golden/README.md``: an internal consistency
    measurement, with ``propagate_zonal`` as the reference and J2 alone on both
    sides so that the only difference between the two paths is the mean/osculating
    mismatch and not different physics. The instrument is checked by
    ``test_with_j2_off_both_paths_are_the_same_two_body_problem``, which closes to
    0.08 mm.
    """

    ORBITS = (
        ("sso_700km_i98", 7078.137, 0.001, 98.2),
        ("iss_like_i51", 6798.0, 0.0005, 51.6),
        ("polar_i90", 7078.137, 0.001, 90.0),
        ("low_inclination_i28", 7078.137, 0.001, 28.5),
    )

    @staticmethod
    def _elements(a_km: float, ecc: float, inclination_deg: float) -> ClassicalElements:
        return ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=a_km,
            eccentricity=ecc,
            inclination_rad=np.deg2rad(inclination_deg),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )

    @pytest.mark.physics
    @pytest.mark.slow
    @pytest.mark.parametrize(("name", "a_km", "ecc", "inclination_deg"), ORBITS)
    def test_the_drift_is_the_semi_major_axis_error_integrating(
        self, name: str, a_km: float, ecc: float, inclination_deg: float
    ) -> None:
        """Not a bound on the drift — an attribution of it.

        A test that only checked "the two paths differ by roughly 86 km" would
        pass just as happily if the mechanism were something else entirely, and
        would have to be rewritten the day a constant moved. So the drift is
        *predicted* from a quantity measured on the reference trajectory itself:

        The osculating semi-major axis at the epoch differs from its own
        one-revolution average by ``da``. The mean motion goes as ``a**-1.5``, so
        ``dn/n = -1.5 da/a``; over one revolution that is an angular error of
        ``2 pi * 1.5 * da/a`` radians, and multiplying by ``a`` gives an
        along-track displacement of ``3 pi da`` — independent of the orbit's size,
        which is why the four cases below span 20 to 88 km purely through ``da``.

        Tolerance: 5 %, and it is derived rather than fitted. The predictor is
        itself first order — it substitutes a time average for the Brouwer mean
        (``O(J2)`` relative), and it linearises ``n(a)`` — so agreement is expected
        at the per-cent level, and the measured spread across the four orbits is
        0.1 % to 1.8 %. Five per cent leaves a factor of ~3 in margin while still
        being an order of magnitude tighter than the factor-of-two error a dropped
        or doubled J2 would produce.
        """
        elements = self._elements(a_km, ecc, inclination_deg)
        period_s = float(orbital_period_s(a_km)[0])
        t_s = np.array([period_s])

        r_reference, v_reference = propagate_zonal(
            *coe_to_rv(elements, J2_ONLY.mu_km3_s2), t_s, J2_ONLY
        )
        r_analytic, _ = _secular_analytic_states(elements, t_s, J2_ONLY)
        _, along_track_km, _ = _rsw_components(r_analytic - r_reference, r_reference, v_reference)

        offset_km = _osculating_axis_offset_km(elements, J2_ONLY)
        predicted_km = 3.0 * np.pi * abs(offset_km)

        assert predicted_km > 15.0, "the prediction itself must be kilometres, not metres"
        assert abs(abs(float(along_track_km[0])) - predicted_km) < 0.05 * predicted_km

    @pytest.mark.physics
    @pytest.mark.slow
    def test_the_drift_grows_linearly_so_it_cannot_be_calibrated_away(self) -> None:
        """Growth, not size, is what makes the mismatch fatal rather than inaccurate.

        A fixed offset could be absorbed once and forgotten. A drift cannot: after
        fifteen revolutions the along-track error is fifteen times the one-orbit
        value, because what is wrong is the *rate* at which the orbit turns.

        Measured 86.3 km after one revolution and 1287 km after fifteen, a ratio
        of 14.92 against the 15.0 that exact linearity would give. The 0.5 %
        shortfall is real and expected — the secular rates are themselves being
        evaluated with the wrong elements, so the error in the error grows too —
        and the assertion allows 5 %, which still excludes anything quadratic
        (a ``t**2`` term would show up as a ratio above 20).
        """
        elements = _sso()
        period_s = float(orbital_period_s(7078.137)[0])
        t_s = np.array([period_s, 15.0 * period_s])

        r_reference, v_reference = propagate_zonal(
            *coe_to_rv(elements, J2_ONLY.mu_km3_s2), t_s, J2_ONLY
        )
        r_analytic, _ = _secular_analytic_states(elements, t_s, J2_ONLY)
        _, along_track_km, _ = _rsw_components(r_analytic - r_reference, r_reference, v_reference)

        one_rev_km, fifteen_revs_km = (abs(float(v)) for v in along_track_km)
        assert one_rev_km > 50.0
        assert fifteen_revs_km > 1000.0
        assert abs(fifteen_revs_km / one_rev_km - 15.0) < 0.05 * 15.0

    @pytest.mark.physics
    def test_the_error_is_along_track_and_the_other_two_axes_stay_put(self) -> None:
        """Which is what converts kilometres into a shifted pass window.

        The radial and cross-track components are the short-period wobble: they
        oscillate with the orbit and do not accumulate, measured at 0.53 km and
        0.03 km after one revolution against 86.3 km along-track. The bound is set
        at a factor of 20 — the measured ratios are 164 and 2800, so a factor of
        20 cannot be satisfied by accident, and it is loose enough not to depend on
        which sample the comparison lands on.

        The decomposition is only meaningful while the separation is small. After
        fifteen revolutions the along-track error is 1290 km, which is 10.4 deg of
        arc, and the *chord* to a point that far along a curved orbit has a radial
        component of ``a (1 - cos 10.4 deg)`` = 117 km — geometry of the
        measurement, not a radial error. That is why this test uses one revolution
        and why the earlier prose figures of "radial 11.7 km" at fifteen
        revolutions were an artefact.
        """
        elements = _sso()
        t_s = np.array([float(orbital_period_s(7078.137)[0])])

        r_reference, v_reference = propagate_zonal(
            *coe_to_rv(elements, J2_ONLY.mu_km3_s2), t_s, J2_ONLY
        )
        r_analytic, _ = _secular_analytic_states(elements, t_s, J2_ONLY)
        radial_km, along_track_km, cross_track_km = _rsw_components(
            r_analytic - r_reference, r_reference, v_reference
        )

        along = abs(float(along_track_km[0]))
        assert along > 20.0 * abs(float(radial_km[0]))
        assert along > 20.0 * abs(float(cross_track_km[0]))

    @pytest.mark.physics
    @pytest.mark.slow
    def test_with_j2_off_both_paths_are_the_same_two_body_problem(self) -> None:
        """The instrument control, and it is what licenses every number above.

        With J2 zero the secular rates are all zero and ``dM/dt`` is exactly the
        two-body mean motion, so the analytic path *is* Kepler in closed form and
        the reference is DOP853 on the same two-body field. Any residual is the
        integrator, not the mismatch. Measured 0.08 mm over fifteen revolutions.

        The bound is 1 mm, the same one ``TestTheTwoModesAgreeOnAFlatEarth``
        derives from the integrator's 1 nm absolute tolerance over its ~250 steps
        per revolution — not a number chosen to let today's result through. Without
        this test the table above could be reporting a comparison artefact, and a
        1290 km artefact and 1290 km of physics look identical from the outside.
        """
        elements = _sso()
        period_s = float(orbital_period_s(7078.137)[0])
        t_s = np.array([period_s, 15.0 * period_s])

        r_reference, _ = propagate_zonal(
            *coe_to_rv(elements, TWO_BODY_ONLY.mu_km3_s2), t_s, TWO_BODY_ONLY
        )
        r_analytic, _ = _secular_analytic_states(elements, t_s, TWO_BODY_ONLY)

        residual_km = np.linalg.norm(r_analytic - r_reference, axis=-1)
        assert float(residual_km.max()) < 1e-6

    @pytest.mark.physics
    @pytest.mark.slow
    def test_the_cost_depends_on_where_in_the_orbit_the_elements_are_stated(self) -> None:
        """The finding that says no single number can be quoted, and why.

        The short-period J2 term makes the osculating semi-major axis oscillate
        about the mean one — peak to peak 18.3 km on this orbit — so the drift is
        set by how far the stated epoch sits from the crossing, not by the orbit
        alone. Two epochs of the *same* orbit:

        =============  =====================  ==================
        Stated at      ``a(epoch) - <a>``     15 revolutions
        =============  =====================  ==================
        ``nu = 0``     9.15 km                1293 km
        ``nu = 45``    -0.014 km              1.1 km
        =============  =====================  ==================

        A factor of 1100 between two scenarios that differ only in when the
        elements were written down. That is why the guard is a refusal and not a
        documented warning with a number attached: there is no number to attach,
        and a scenario cannot know which case it is in.

        Bounds: the first case is asserted above 500 km and the second below 20 km,
        so the claim under test is the *separation of regimes* — a factor of 25 at
        minimum — rather than either figure. Both are far from the measured 1293
        and 1.1.
        """
        period_s = float(orbital_period_s(7078.137)[0])
        t_s = np.array([15.0 * period_s])

        def drift_km(true_anomaly_rad: float) -> tuple[float, float]:
            elements = _sso(true_anomaly_rad)
            r_reference, _ = propagate_zonal(*coe_to_rv(elements, J2_ONLY.mu_km3_s2), t_s, J2_ONLY)
            r_analytic, _ = _secular_analytic_states(elements, t_s, J2_ONLY)
            separation_km = float(np.linalg.norm(r_analytic[0] - r_reference[0]))
            return separation_km, _osculating_axis_offset_km(elements, J2_ONLY)

        worst_km, worst_offset_km = drift_km(0.0)
        best_km, best_offset_km = drift_km(float(np.deg2rad(45.0)))

        assert worst_km > 500.0
        assert best_km < 20.0
        # And it is the axis offset that explains the collapse, not luck.
        assert abs(worst_offset_km) > 5.0
        assert abs(best_offset_km) < 0.5


# --------------------------------------------------------------------------- #
# The (S, n, 3) decision
# --------------------------------------------------------------------------- #
class TestSatelliteAxis:
    @pytest.mark.parametrize("method", PROPAGATE_MODES)
    def test_a_single_orbit_is_still_three_dimensional(self, method: PropagationMethod) -> None:
        """``(1, n, 3)``, never ``(n, 3)``, so no consumer branches on shape."""
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)

        traj = propagate(_iss_like(), grid, method=method)

        assert traj.r_km.shape == (1, grid.n, 3)
        assert traj.v_km_s.shape == (1, grid.n, 3)
        assert (traj.n_satellites, traj.n_samples) == (1, grid.n)

    @pytest.mark.physics
    @pytest.mark.parametrize("method", PROPAGATE_MODES)
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
    @pytest.mark.parametrize("method", PROPAGATE_MODES)
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
    @pytest.mark.parametrize("method", PROPAGATE_MODES)
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
# The container keeps the promises its docstring makes
# --------------------------------------------------------------------------- #
class TestTrajectoryIsWhatItSaysItIs:
    """Immutable *and* tagged with members, both asserted rather than assumed.

    A ``Trajectory`` is what every stage downstream of here consumes, and its
    docstring tells those consumers they may assume the arrays line up with the
    grid without re-checking. Two things had to change for that to be true: the
    arrays are now read-only, and the frame is resolved to a member instead of
    being stored as whatever was passed.
    """

    @staticmethod
    def _propagated() -> Trajectory:
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=600.0, step_s=60.0)
        return propagate(_iss_like(), grid, method=PropagationMethod.TWO_BODY)

    @pytest.mark.parametrize("field", ["r_km", "v_km_s"])
    def test_the_states_cannot_be_edited_in_place(self, field: str) -> None:
        """A result other consumers still hold must not be editable underneath them.

        ``frozen=True`` on the dataclass stops ``traj.r_km = ...`` and nothing
        else; the assignment that actually corrupts a shared result is into the
        array.
        """
        traj = self._propagated()
        with pytest.raises(ValueError, match="read-only"):
            getattr(traj, field)[0, 0, 0] = 0.0

    def test_freezing_costs_no_copy(self) -> None:
        """Deliberately a view, and the test says so, because the choice is a trade.

        These arrays are produced by the propagator and handed to nobody first, so
        there is no second writeable reference to guard against — and a copy of an
        ``(S, n, 3)`` block is 24 MB per array for a million samples. The looser
        guarantee is the right one *here*, unlike in ``ClassicalElements`` and
        ``TimeGrid``, which take arrays from their callers and therefore copy.
        """
        r_km = np.zeros((1, 2, 3))
        v_km_s = np.zeros((1, 2, 3))
        traj = Trajectory(
            r_km=r_km,
            v_km_s=v_km_s,
            grid=TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0])),
            frame=Frame.TEME,
            method=PropagationMethod.TWO_BODY,
        )

        assert np.shares_memory(traj.r_km, r_km)
        assert r_km.flags.writeable, "freezing a view must not freeze the argument"

    def test_a_string_frame_is_stored_as_the_member(self) -> None:
        """So that ``traj.frame is Frame.TEME`` is a safe thing to write.

        This is the assertion that fails against the old code, and it is the one
        that matters: a raw ``"teme"`` stored here is how a silent wrong-branch bug
        would reach ``geometry.py``, which is the next module to be written and
        will compare frames with ``is``.
        """
        traj = Trajectory(
            r_km=np.zeros((1, 2, 3)),
            v_km_s=np.zeros((1, 2, 3)),
            grid=TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0])),
            frame="teme",  # type: ignore[arg-type]
            method=PropagationMethod.TWO_BODY,
        )

        assert traj.frame is Frame.TEME

    def test_the_frame_a_propagation_carries_is_a_member_even_from_a_string(self) -> None:
        """End to end: a string on the elements comes out as a member on the result."""
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=ISS_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0005,
            inclination_rad=ISS_INCLINATION_RAD,
            raan_rad=0.3,
            argp_rad=1.0,
            true_anomaly_rad=0.5,
            frame="teme",  # type: ignore[arg-type]
        )
        grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=60.0, step_s=30.0)

        traj = propagate(elements, grid, method=PropagationMethod.TWO_BODY)

        assert traj.frame is Frame.TEME

    def test_an_unknown_frame_and_a_rotating_one_stay_two_different_errors(self) -> None:
        """Resolving must not swallow the message that teaches something."""
        args = {
            "r_km": np.zeros((1, 2, 3)),
            "v_km_s": np.zeros((1, 2, 3)),
            "grid": TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0])),
            "method": PropagationMethod.TWO_BODY,
        }
        with pytest.raises(DomainError, match="is not a frame"):
            Trajectory(frame="ecef", **args)  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="inertial frame"):
            Trajectory(frame=Frame.ITRF, **args)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# The module surface: the enum is incomplete on purpose
# --------------------------------------------------------------------------- #


class TestModuleSurface:
    def test_the_enum_holds_exactly_the_implemented_modes(self) -> None:
        """The deliberate gap, asserted so that closing it is a decision.

        ``J2_SECULAR_ANALYTIC`` is missing entirely because the analytic mode
        needs mean elements and this project has only osculating ones — a gap of
        ~1300 km per day, not a rounding error, measured in
        ``TestWhatNotHavingBrouwerLyddaneCosts``. When Brouwer-Lyddane lands,
        this test fails, and updating it is the moment to also update the module
        docstring and ADR 0005. That is the intended workflow, not an
        inconvenience: a failing test here means someone added a mode, and the
        question is whether they added the model with it.

        ``PropagationMethod.SGP4`` is a different kind of addition to this same
        set: present, correct, and simply not ``propagate()``'s to run (see
        ``docs/adr/0007-tle-and-sgp4-propagation.md``). This test only pins the
        *name set*; which of those names ``propagate()`` itself implements is
        ``test_every_propagate_mode_actually_propagates`` below.
        """
        assert {member.value for member in PropagationMethod} == {
            "two_body",
            "zonal_numeric",
            "sgp4",
        }
        assert not hasattr(PropagationMethod, "J2_SECULAR_ANALYTIC")

    @pytest.mark.parametrize("method", PROPAGATE_MODES)
    def test_every_propagate_mode_actually_propagates(self, method: PropagationMethod) -> None:
        """A member with no branch behind it raises ``NotImplementedError``.

        Parametrising over the members ``propagate()`` claims to implement,
        rather than over a hand-written list, is the whole point: adding one of
        *these* without wiring it fails here immediately. ``PropagationMethod.SGP4``
        is excluded on purpose — it is not one of these members, and asserting
        that exclusion is the next test's job, not this one's.
        """
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))

        traj = propagate(_iss_like(), grid, method=method)

        assert traj.method is method
        assert np.all(np.isfinite(traj.r_km))

    def test_sgp4_is_not_wired_into_propagate(self) -> None:
        """``PropagationMethod.SGP4`` exists and is not ``propagate()``'s to run.

        SGP4 takes a parsed TLE record, not ``ClassicalElements`` — there is no
        branch this function could have for it, and the fallback that used to be
        marked "unreachable until the enum grows" is now exactly this case,
        reachable and correct. The model this member names is
        ``quoss.orbits.tle.propagate_tle``, tested in ``tests/orbits/test_tle.py``;
        this test only pins that asking *this* function for it fails loud rather
        than silently returning nonsense of the right shape.
        """
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0, 60.0]))

        with pytest.raises(NotImplementedError, match=r"PropagationMethod\.SGP4"):
            propagate(_iss_like(), grid, method=PropagationMethod.SGP4)

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
        """Provenance: a trajectory can always say which model made it.

        Over ``PROPAGATE_MODES``, not the full enum: ``PropagationMethod.SGP4``
        never reaches this return statement (see
        ``test_sgp4_is_not_wired_into_propagate``), so it has nothing to travel
        with here — its ``Trajectory.method`` is asserted in
        ``tests/orbits/test_tle.py`` instead, on the object ``propagate_tle``
        actually returns.
        """
        grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.array([0.0]))

        for method in PROPAGATE_MODES:
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

    @pytest.mark.parametrize("method", PROPAGATE_MODES)
    def test_every_mode_refuses_mean_elements(self, method: PropagationMethod) -> None:
        """Both modes propagate osculating elements, and neither can tell by itself.

        Parametrised over ``PROPAGATE_MODES`` rather than the full enum, and for
        the same reason ``test_every_propagate_mode_actually_propagates`` is:
        ``PropagationMethod.SGP4`` never reaches the ``coe_to_rv`` guard this test
        is about — asking ``propagate()`` for it raises ``NotImplementedError``
        first, which is ``test_sgp4_is_not_wired_into_propagate``'s claim, not
        this one's. The day ``J2_SECULAR_ANALYTIC`` arrives it will be the one
        mode in this set that *wants* mean elements, and this test failing is the
        reminder that its branch needs its own rule rather than inheriting this
        one.

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
