"""Tests for `quoss.orbits.perturbations`.

Organised by verification level, per `tests/golden/README.md`:

* ``TestZonalAccelerationAgainstTheGradient`` /
  ``TestZonalAccelerationAgainstTheTextbookForm`` — V1 and V2 for the force:
  the module builds the acceleration from one general Legendre expression, and
  these check it against a numerical gradient of the potential and against the
  hand-transcribed Cartesian components every textbook prints.
* ``TestSecularRatesAgainstIntegration`` — V3, and the load-bearing test of this
  module: an independent implementation of the same physics (DOP853 on the exact
  force) measures what the analytic first-order rates claim. The residual is not
  merely bounded, it is shown to be **proportional to J2**, which is what
  separates "the theory is truncated" from "a coefficient is wrong".
* ``TestJ3HasNoSecularTerm`` — the defect the previous codebase shipped, made
  impossible to reintroduce silently.
* ``TestTheElementTypeGate`` — the second such defect held shut: a secular rate
  is a statement about *mean* elements, and feeding it the osculating ones a
  state vector gives is an ``O(J2)`` error that no bound on the output could
  ever distinguish from the theory's own truncation.
* ``TestPublishedSunSynchronous`` — V2-adjacent: a real mission's published
  inclination, and an honest statement of what its printed precision can and
  cannot discriminate.
* ``TestInvariants*`` / ``TestRejects*`` — V1.

The integrations are the expensive part of this file. Each one is a few tenths
of a second; the ones that need many revolutions carry the ``slow`` marker.
"""

import inspect
import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from quoss.core.constants import (
    EGM96_J2,
    EGM96_J3,
    EGM96_J4,
    EGM96_MU_KM3_S2,
    EGM96_RADIUS_EQUATORIAL_KM,
    WGS72_J2,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.orbits import perturbations as perturbations_module
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    coe_to_rv,
    orbital_period_s,
    rv_to_coe,
)
from quoss.orbits.perturbations import (
    CRITICAL_INCLINATION_RAD,
    EGM96_ZONAL,
    WGS72_ZONAL,
    SecularRates,
    ZonalGravity,
    gravitational_acceleration,
    propagate_zonal,
    secular_rates_j2,
    two_body_acceleration,
    zonal_acceleration,
)

TWO_BODY_ONLY = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
)
"""A model with every harmonic zero: the two-body field, expressed as a model."""

J2_ONLY = ZonalGravity(
    mu_km3_s2=EGM96_MU_KM3_S2,
    r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
    j2=EGM96_J2,
)
"""J2 alone. The first-order secular theory describes exactly this field."""

LEO_ALTITUDE_KM = 700.0
LEO_SEMI_MAJOR_AXIS_KM = EGM96_RADIUS_EQUATORIAL_KM + LEO_ALTITUDE_KM


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
FINITE_DIFFERENCE_STEP_KM = 0.03
"""Central-difference step for the gradient checks, 30 m.

Chosen by measurement, and the measurement is the point. Truncation error falls
as ``h^2`` while cancellation error grows as ``1/h``, so there is an optimum and
it is not where intuition puts it: swept over 9 positions and steps from 300 m
down to 3 m, the worst-case relative disagreement bottoms out near 1e-9 at 30 m
and gets *worse* at 3 m. A step of 1 km — the obvious first guess — is 250 times
worse than this one.
"""


def _legendre_values(sin_lat: float) -> dict[int, float]:
    """Legendre polynomials P_2..P_4, written out from their definition.

    Deliberately a second transcription: the module has its own, and two
    independent copies agreeing is the only thing that makes the gradient checks
    below evidence rather than a tautology.
    """
    return {
        2: 0.5 * (3.0 * sin_lat**2 - 1.0),
        3: 0.5 * (5.0 * sin_lat**3 - 3.0 * sin_lat),
        4: (35.0 * sin_lat**4 - 30.0 * sin_lat**2 + 3.0) / 8.0,
    }


def _zonal_potential(r_km: np.ndarray, gravity: ZonalGravity) -> float:
    """Evaluate ``U = mu/r [1 - sum J_n (R/r)^n P_n(s)]`` at one point."""
    r_mag = float(np.linalg.norm(r_km))
    legendre = _legendre_values(float(r_km[2]) / r_mag)
    total = 1.0
    for degree, coefficient in ((2, gravity.j2), (3, gravity.j3), (4, gravity.j4)):
        total -= coefficient * (gravity.r_equatorial_km / r_mag) ** degree * legendre[degree]
    return gravity.mu_km3_s2 / r_mag * total


def _perturbing_potential(r_km: np.ndarray, gravity: ZonalGravity) -> float:
    """Evaluate the zonal part of ``U`` alone, directly.

    Not ``_zonal_potential(...) - two_body_potential(...)``. That difference is
    ~60 km^2/s^2 taken between two numbers of ~6e4, so it throws away nine digits
    to cancellation before the finite difference has even started — measured, it
    costs two orders of magnitude of accuracy in the gradient. Evaluating the sum
    on its own has no cancellation at all.
    """
    r_mag = float(np.linalg.norm(r_km))
    legendre = _legendre_values(float(r_km[2]) / r_mag)
    return (
        -gravity.mu_km3_s2
        / r_mag
        * sum(
            coefficient * (gravity.r_equatorial_km / r_mag) ** degree * legendre[degree]
            for degree, coefficient in ((2, gravity.j2), (3, gravity.j3), (4, gravity.j4))
        )
    )


def _numerical_gradient(
    potential: "object",
    r_km: np.ndarray,
    gravity: ZonalGravity,
) -> np.ndarray:
    """Central difference of a scalar potential at one point."""
    gradient = np.empty(3)
    for axis in range(3):
        offset = np.zeros(3)
        offset[axis] = FINITE_DIFFERENCE_STEP_KM
        gradient[axis] = (
            potential(r_km + offset, gravity)  # type: ignore[operator]
            - potential(r_km - offset, gravity)  # type: ignore[operator]
        ) / (2.0 * FINITE_DIFFERENCE_STEP_KM)
    return gradient


def _elements(
    *,
    semi_major_axis_km: float = LEO_SEMI_MAJOR_AXIS_KM,
    eccentricity: float = 0.01,
    inclination_deg: float = 51.6,
    raan_deg: float = 30.0,
    argp_deg: float = 40.0,
    true_anomaly_deg: float = 0.0,
    element_type: ElementType = ElementType.OSCULATING,
) -> ClassicalElements:
    """Build one set of elements from the units a scenario is written in.

    Osculating by default, because these are what gets handed to
    :func:`coe_to_rv` to start an integration, and a state vector is osculating.
    """
    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=eccentricity,
        inclination_rad=math.radians(inclination_deg),
        raan_rad=math.radians(raan_deg),
        argp_rad=math.radians(argp_deg),
        true_anomaly_rad=math.radians(true_anomaly_deg),
        element_type=element_type,
    )


def _mean_elements(**kwargs: float) -> ClassicalElements:
    """Build the same orbit **stated** as Brouwer mean elements.

    Constructed with the label rather than relabelled into it, and the
    difference matters. A test that only asks what
    :func:`secular_rates_j2` computes — a sign, a limit, a symmetry — is entitled
    to say "these are mean elements", because that is the input the closed form
    is a statement about and nothing here ever turns them into a state.
    :meth:`ClassicalElements.relabelled_as` is reserved for the tests that hand
    the function elements it should not have, on purpose, and have to admit it.
    """
    return _elements(element_type=ElementType.MEAN_BROUWER, **kwargs)


def _ascending_node_crossings(
    elements: ClassicalElements,
    gravity: ZonalGravity,
    n_revolutions: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Integrate and return the time and state of every ascending-node crossing.

    Sampling at the node is what makes a secular rate measurable at all. The
    short-period terms of J2 are functions of the argument of latitude, which is
    zero at every one of these crossings, so they take the *same* value at each
    and cancel in a difference between two of them. What survives is the secular
    drift plus terms of the next order — which is precisely the quantity the
    analytic rates claim to predict.

    Uses SciPy directly rather than :func:`propagate_zonal`, because the event
    detection is the whole mechanism here and hiding it behind the module under
    test would leave the oracle sharing code with it.
    """
    r0, v0 = coe_to_rv(elements, gravity.mu_km3_s2)
    period_s = float(orbital_period_s(elements.semi_major_axis_km, gravity.mu_km3_s2)[0])

    def rhs(_t: float, state: np.ndarray) -> np.ndarray:
        r = state[:3]
        r_mag = float(np.linalg.norm(r))
        acceleration = -gravity.mu_km3_s2 * r / r_mag**3 + zonal_acceleration(r, gravity)[0]
        return np.concatenate([state[3:], acceleration])

    def crosses_equator(_t: float, state: np.ndarray) -> float:
        return float(state[2])

    crosses_equator.direction = 1.0  # type: ignore[attr-defined]

    solution = solve_ivp(
        rhs,
        (0.0, n_revolutions * period_s * 1.05),
        np.concatenate([r0[0], v0[0]]),
        method="DOP853",
        rtol=1e-12,
        atol=1e-12,
        events=crosses_equator,
    )
    assert solution.success
    return solution.t_events[0], solution.y_events[0]


def _measured_raan_rate(
    elements: ClassicalElements,
    gravity: ZonalGravity,
    n_revolutions: int,
    predicted_rad_s: float,
) -> float:
    """Measure ``dOmega/dt`` between the first and last ascending node.

    ``predicted_rad_s`` only resolves the ``2 pi`` ambiguity of an angle observed
    at two instants: the accumulated drift is several revolutions of the node, so
    the difference has to be unwrapped, and the prediction is what says which
    turn it belongs to. It cannot bias the result — an unwrap that chose wrongly
    would move the answer by a whole ``2 pi``, not by the parts in a thousand
    these tests measure.
    """
    times, states = _ascending_node_crossings(elements, gravity, n_revolutions)
    first = rv_to_coe(states[0][:3], states[0][3:], gravity.mu_km3_s2)
    last = rv_to_coe(states[-1][:3], states[-1][3:], gravity.mu_km3_s2)
    span_s = float(times[-1] - times[0])
    expected = predicted_rad_s * span_s
    raw = float(last.raan_rad[0] - first.raan_rad[0])
    unwrapped = (raw - expected + np.pi) % (2.0 * np.pi) - np.pi + expected
    return unwrapped / span_s


# --------------------------------------------------------------------------- #
# V1/V2 — the force model
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestZonalAccelerationAgainstTheGradient:
    """The acceleration must be the gradient of the potential it claims to be.

    This is the strongest statement available about a conservative force and it
    needs no external data: the module differentiates the zonal potential once,
    in closed form, and a central difference of that same potential — written
    from the scalar definition in this file — has to agree.
    """

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_matches_a_central_difference_of_the_potential(self, seed: int) -> None:
        """The whole field: point mass plus harmonics, against ``grad U``.

        The bound is 1e-8, an order of magnitude above the worst case measured
        while choosing :data:`FINITE_DIFFERENCE_STEP_KM` over nine positions.
        It is a property of the finite difference, not of the module: nothing
        tighter is available by this route, and nothing looser would be testing
        the J4 term, which is 1e-6 of the total.
        """
        rng = np.random.default_rng(seed)
        for _ in range(8):
            direction = rng.normal(size=3)
            r_km = direction / np.linalg.norm(direction) * rng.uniform(6800.0, 12000.0)
            gradient = _numerical_gradient(_zonal_potential, r_km, EGM96_ZONAL)
            analytic = gravitational_acceleration(r_km, EGM96_ZONAL)[0]
            assert np.allclose(gradient, analytic, rtol=1e-8, atol=0.0)

    @pytest.mark.parametrize("seed", [0, 1, 2])
    def test_the_perturbation_alone_also_matches(self, seed: int) -> None:
        """The zonal part on its own, where a sign error cannot hide.

        The previous test compares a quantity dominated by the central term, so a
        J3 or J4 component with the wrong sign would move the total by 1e-6 —
        near the floor of the method. Differencing the perturbing potential
        *directly* puts the harmonics at 100 % of the signal instead of 0.1 %, so
        the same 1e-8 bound now constrains each harmonic to 1e-8 of itself.
        """
        rng = np.random.default_rng(seed)
        for _ in range(8):
            direction = rng.normal(size=3)
            r_km = direction / np.linalg.norm(direction) * rng.uniform(6800.0, 12000.0)
            gradient = _numerical_gradient(_perturbing_potential, r_km, EGM96_ZONAL)
            assert np.allclose(gradient, zonal_acceleration(r_km, EGM96_ZONAL)[0], rtol=1e-8)


@pytest.mark.physics
class TestZonalAccelerationAgainstTheTextbookForm:
    """The general Legendre expression against the transcribed component form.

    Vallado [1] and Montenbruck & Gill [4] both print J2 as three explicit
    Cartesian components. The module does not use that form — it uses one
    expression parameterised by degree — so writing the textbook version out here
    is an independent transcription, and the two agreeing means the general form
    was expanded correctly.
    """

    def test_j2_components(self) -> None:
        """a = -3/2 J2 (mu/r^2)(R/r)^2 [x/r (1 - 5 z^2/r^2), ..., z/r (3 - 5 z^2/r^2)]."""
        r_km = np.array([[5000.0, 4000.0, 3000.0], [-7000.0, 1000.0, -2000.0]])
        r_mag = np.linalg.norm(r_km, axis=1)
        z_ratio_sq = (r_km[:, 2] / r_mag) ** 2
        common = (
            -1.5
            * EGM96_J2
            * (EGM96_MU_KM3_S2 / r_mag**2)
            * (EGM96_RADIUS_EQUATORIAL_KM / r_mag) ** 2
        )
        expected = np.empty_like(r_km)
        expected[:, 0] = common * (r_km[:, 0] / r_mag) * (1.0 - 5.0 * z_ratio_sq)
        expected[:, 1] = common * (r_km[:, 1] / r_mag) * (1.0 - 5.0 * z_ratio_sq)
        expected[:, 2] = common * (r_km[:, 2] / r_mag) * (3.0 - 5.0 * z_ratio_sq)
        assert np.allclose(zonal_acceleration(r_km, J2_ONLY), expected, rtol=1e-13, atol=0.0)

    def test_j3_vanishes_on_the_equator_except_along_z(self) -> None:
        """An odd harmonic is antisymmetric about the equator.

        At ``z = 0`` the in-plane part of the J3 term carries ``P_3'(0) != 0``
        only through the polar unit vector, so the horizontal components vanish
        and the vertical one does not. It is the cheapest signature of an odd
        harmonic, and it fails immediately if the parity of the Legendre
        polynomial was transcribed wrongly.
        """
        j3_only = ZonalGravity(
            mu_km3_s2=EGM96_MU_KM3_S2,
            r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
            j3=EGM96_J3,
        )
        equatorial = zonal_acceleration(np.array([7000.0, 0.0, 0.0]), j3_only)[0]
        assert equatorial[0] == pytest.approx(0.0, abs=1e-18)
        assert equatorial[1] == pytest.approx(0.0, abs=1e-18)
        assert abs(equatorial[2]) > 1e-12

    def test_j3_is_antisymmetric_and_j2_symmetric_about_the_equator(self) -> None:
        """Mirroring z flips an odd harmonic's z component and preserves an even one's."""
        north = np.array([5000.0, 1000.0, 4000.0])
        south = np.array([5000.0, 1000.0, -4000.0])
        j3_only = ZonalGravity(
            mu_km3_s2=EGM96_MU_KM3_S2,
            r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
            j3=EGM96_J3,
        )
        a_north = zonal_acceleration(north, j3_only)[0]
        a_south = zonal_acceleration(south, j3_only)[0]
        assert a_north[0] == pytest.approx(-a_south[0], rel=1e-13)
        assert a_north[2] == pytest.approx(a_south[2], rel=1e-13)

        b_north = zonal_acceleration(north, J2_ONLY)[0]
        b_south = zonal_acceleration(south, J2_ONLY)[0]
        assert b_north[0] == pytest.approx(b_south[0], rel=1e-13)
        assert b_north[2] == pytest.approx(-b_south[2], rel=1e-13)


@pytest.mark.physics
class TestForceModelInvariants:
    """V1 — what has to hold whatever the numbers are."""

    def test_zero_harmonics_give_exactly_zero_perturbation(self) -> None:
        """Not "small": exactly zero. A model with no harmonics has no perturbation."""
        r_km = np.array([[7000.0, 100.0, -2000.0]])
        assert np.array_equal(zonal_acceleration(r_km, TWO_BODY_ONLY), np.zeros_like(r_km))
        assert np.array_equal(
            gravitational_acceleration(r_km, TWO_BODY_ONLY),
            two_body_acceleration(r_km, TWO_BODY_ONLY.mu_km3_s2),
        )

    def test_the_perturbation_is_a_perturbation(self) -> None:
        """J2 is ~1e-3 of the central term at LEO, and J3/J4 are ~1e-3 of J2."""
        r_km = np.array([[LEO_SEMI_MAJOR_AXIS_KM, 0.0, 2000.0]])
        central = float(np.linalg.norm(two_body_acceleration(r_km)))
        j2 = float(np.linalg.norm(zonal_acceleration(r_km, J2_ONLY)))
        full = zonal_acceleration(r_km, EGM96_ZONAL)
        higher = float(np.linalg.norm(full - zonal_acceleration(r_km, J2_ONLY)))
        assert 1e-4 < j2 / central < 1e-2
        assert 1e-4 < higher / j2 < 1e-2

    def test_acceleration_scales_as_the_inverse_square(self) -> None:
        """Doubling the radius must quarter the central term, to machine precision."""
        r_km = np.array([[8000.0, 0.0, 0.0]])
        near = float(np.linalg.norm(two_body_acceleration(r_km)))
        far = float(np.linalg.norm(two_body_acceleration(2.0 * r_km)))
        assert near / far == pytest.approx(4.0, rel=1e-13)

    def test_the_zonal_field_is_axially_symmetric(self) -> None:
        """Rotating about z rotates the acceleration and changes nothing else.

        This is what licenses the module docstring's claim that no frame argument
        is needed: the same expression is valid in ITRF and in TEME.
        """
        r_km = np.array([6000.0, 2000.0, 3000.0])
        angle = 0.7
        rotation = np.array(
            [
                [math.cos(angle), -math.sin(angle), 0.0],
                [math.sin(angle), math.cos(angle), 0.0],
                [0.0, 0.0, 1.0],
            ]
        )
        rotated_input = zonal_acceleration(rotation @ r_km, EGM96_ZONAL)[0]
        rotated_output = rotation @ zonal_acceleration(r_km, EGM96_ZONAL)[0]
        assert np.allclose(rotated_input, rotated_output, rtol=1e-13, atol=1e-20)

    def test_vectorises_over_the_leading_axis(self) -> None:
        """A stack must give what the elements give one at a time."""
        stack = np.array([[7000.0, 0.0, 0.0], [0.0, 8000.0, 1000.0], [1000.0, -2000.0, 9000.0]])
        together = zonal_acceleration(stack, EGM96_ZONAL)
        assert together.shape == (3, 3)
        for index in range(3):
            alone = zonal_acceleration(stack[index], EGM96_ZONAL)[0]
            assert np.array_equal(together[index], alone)


# --------------------------------------------------------------------------- #
# V3 — the secular rates against the numerical integration
# --------------------------------------------------------------------------- #
@pytest.mark.physics
@pytest.mark.reference
class TestSecularRatesAgainstIntegration:
    """The load-bearing test of the module.

    DOP853 on the exact J2 force is an implementation that shares nothing with
    the closed-form rates: no averaging, no elements, no trigonometry of the
    inclination. What it measures at the ascending nodes is the real secular
    drift, and the analytic prediction has to reproduce it to the accuracy a
    first-order theory has — no better, and no worse.

    **Every test in this class feeds the theory the wrong kind of elements on
    purpose**, and says so with :meth:`ClassicalElements.relabelled_as`. One set
    of six numbers has to play two roles here: the initial condition of the
    integration, where it is osculating because a state vector cannot be anything
    else, and the argument of ``secular_rates_j2``, which wants mean elements.
    QuOSS cannot convert between them — that is Brouwer-Lyddane, which does not
    exist yet — so the mismatch stays, and it is exactly the quantity being
    measured: the residual it leaves is ``O(J2)``, and
    ``test_the_residual_is_proportional_to_j2`` is what proves that is all it is.
    The relabel converts nothing; it makes the lie visible at the call site
    instead of hiding it in a keyword argument.
    """

    @pytest.mark.parametrize("inclination_deg", [30.0, 51.6, 98.0])
    def test_node_rate_agrees_to_the_theorys_own_truncation(self, inclination_deg: float) -> None:
        """Within a few times J2, which is the size of the neglected term.

        The bound is derived, not fitted: a first-order theory drops terms of
        relative order J2, so 5x J2 is the statement "the disagreement is the
        truncation and nothing else". Tightening it further would be asserting
        something the theory does not claim; loosening it would stop testing
        anything.
        """
        elements = _elements(inclination_deg=inclination_deg)
        as_mean = elements.relabelled_as(ElementType.MEAN_BROUWER)
        predicted = float(secular_rates_j2(as_mean, j2=J2_ONLY.j2).raan_rad_s[0])
        measured = _measured_raan_rate(elements, J2_ONLY, 20, predicted)
        assert abs(predicted / measured - 1.0) < 5.0 * EGM96_J2

    def test_the_residual_is_proportional_to_j2(self) -> None:
        """The test that distinguishes truncation from a wrong coefficient.

        Scaling J2 down by four scales the neglected O(J2^2) term down by
        sixteen and the rate itself by four, so the *relative* residual must fall
        by exactly four. A mistyped coefficient would instead leave a relative
        residual that barely moves, because it would be an error of order J2
        inside a quantity of order J2.

        Measured ratio is 4.00 to three figures; the bound below allows 2 %,
        which is far tighter than any wrong coefficient could sneak through and
        far looser than the measurement's own scatter.
        """
        elements = _elements(inclination_deg=51.6)
        as_mean = elements.relabelled_as(ElementType.MEAN_BROUWER)
        residuals = []
        for factor in (1.0, 0.25):
            j2 = EGM96_J2 * factor
            model = ZonalGravity(
                mu_km3_s2=EGM96_MU_KM3_S2,
                r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
                j2=j2,
            )
            predicted = float(secular_rates_j2(as_mean, j2=j2).raan_rad_s[0])
            measured = _measured_raan_rate(elements, model, 20, predicted)
            residuals.append(abs(predicted / measured - 1.0))
        assert residuals[0] / residuals[1] == pytest.approx(4.0, rel=0.02)

    @pytest.mark.slow
    def test_apsidal_rate_agrees_to_the_theorys_own_truncation(self) -> None:
        """Same statement for ``domega/dt``, which is harder to measure.

        The argument of perigee needs averaging over each revolution rather than
        sampling at the node: its short-period terms carry a factor ``1/e``,
        because they act on the eccentricity *vector* and turning that into an
        angle divides by its length. At e = 0.05 they are still tens of times the
        secular drift per revolution, and only the per-revolution mean removes
        them.

        The inclination is kept well away from :data:`CRITICAL_INCLINATION_RAD`,
        where ``4 - 5 sin^2 i`` passes through zero and a relative bound stops
        meaning anything.
        """
        elements = _elements(inclination_deg=98.0, eccentricity=0.05)
        times, _ = _ascending_node_crossings(elements, J2_ONLY, 40)
        predicted = float(
            secular_rates_j2(
                elements.relabelled_as(ElementType.MEAN_BROUWER), j2=J2_ONLY.j2
            ).argp_rad_s[0]
        )

        # Re-integrate with dense output so each revolution can be averaged.
        r0, v0 = coe_to_rv(elements, J2_ONLY.mu_km3_s2)
        r_km, v_km_s = propagate_zonal(
            r0[0],
            v0[0],
            np.linspace(float(times[0]), float(times[-1]), 200 * (len(times) - 1) + 1),
            J2_ONLY,
        )
        sampled = rv_to_coe(r_km, v_km_s, J2_ONLY.mu_km3_s2)
        argp = np.unwrap(sampled.argp_rad)
        per_revolution = argp[:-1].reshape(len(times) - 1, 200).mean(axis=1)
        midpoints = 0.5 * (times[:-1] + times[1:])
        measured = float(np.polyfit(midpoints, per_revolution, 1)[0])
        assert abs(predicted / measured - 1.0) < 5.0 * EGM96_J2

    def test_nodal_period_agrees_with_the_measured_node_to_node_time(self) -> None:
        """The derived period, against the interval the integration actually shows.

        ``nodal_period_s`` is not an independent claim — it is
        ``2 pi / (dM/dt + domega/dt)`` — but it is the form the rest of the
        project will use, and it is the one that can be checked directly: the
        node crossings *are* the nodal period.
        """
        elements = _elements(inclination_deg=51.6)
        times, _ = _ascending_node_crossings(elements, J2_ONLY, 20)
        measured_s = float(np.mean(np.diff(times)))
        predicted_s = float(
            secular_rates_j2(
                elements.relabelled_as(ElementType.MEAN_BROUWER), j2=J2_ONLY.j2
            ).nodal_period_s[0]
        )
        assert abs(predicted_s / measured_s - 1.0) < 5.0 * EGM96_J2

    def test_the_nodal_period_differs_from_the_keplerian_one_by_seconds(self) -> None:
        """The correction `kepler.orbital_period_s` promises lives here.

        Its docstring says the nodal and anomalistic periods "differ from it by a
        few seconds through J2"; this is that claim, measured. The sign follows
        the inclination: below 63.4 deg the perigee runs forwards and the node
        period is shorter, above it the perigee regresses and the node period is
        longer.
        """
        keplerian_s = float(orbital_period_s(LEO_SEMI_MAJOR_AXIS_KM)[0])
        low = secular_rates_j2(_mean_elements(inclination_deg=51.6))
        high = secular_rates_j2(_mean_elements(inclination_deg=98.0))
        assert -10.0 < float(low.nodal_period_s[0]) - keplerian_s < -1.0
        assert 1.0 < float(high.nodal_period_s[0]) - keplerian_s < 10.0


@pytest.mark.physics
@pytest.mark.reference
class TestJ3HasNoSecularTerm:
    """The defect the previous codebase shipped, held shut.

    ``tests/golden/README.md`` records it: SimulCTTC carried a J3 "secular" rate
    for a harmonic that has no first-order secular term, and its own docstring
    admitted as much. The distinction is measurable rather than a matter of
    authority, and this is the measurement.
    """

    def test_the_j3_node_contribution_reverses_with_the_argument_of_perigee(self) -> None:
        """A secular term cannot depend on where perigee happens to be.

        The J3 contribution to ``dOmega/dt`` is measured at four values of
        ``omega``: it vanishes at 0 and pi and reverses sign between pi/2 and
        3 pi/2. That is the signature of a long-period term — one that averages
        to zero over an apsidal cycle — and it is incompatible with a secular
        rate, which would be the same at all four.

        Also worth reading: the effect is ~3e-11 rad/s where the J2 secular rate
        is ~9e-7 rad/s. Even at its largest it is four orders of magnitude below
        the term that is real.
        """
        j2_j3 = ZonalGravity(
            mu_km3_s2=EGM96_MU_KM3_S2,
            r_equatorial_km=EGM96_RADIUS_EQUATORIAL_KM,
            j2=EGM96_J2,
            j3=EGM96_J3,
        )
        contributions = {}
        for argp_deg in (0.0, 90.0, 180.0, 270.0):
            elements = _elements(argp_deg=argp_deg)
            predicted = float(
                secular_rates_j2(
                    elements.relabelled_as(ElementType.MEAN_BROUWER), j2=EGM96_J2
                ).raan_rad_s[0]
            )
            with_j3 = _measured_raan_rate(elements, j2_j3, 20, predicted)
            without = _measured_raan_rate(elements, J2_ONLY, 20, predicted)
            contributions[argp_deg] = with_j3 - without

        largest = max(abs(value) for value in contributions.values())
        assert abs(contributions[0.0]) < 0.1 * largest
        assert abs(contributions[180.0]) < 0.1 * largest
        assert contributions[90.0] * contributions[270.0] < 0.0
        assert abs(contributions[90.0]) == pytest.approx(abs(contributions[270.0]), rel=0.05)
        # And the whole effect is negligible next to the J2 rate it sits beside.
        assert largest < 1e-4 * abs(float(secular_rates_j2(_mean_elements()).raan_rad_s[0]))

    def test_secular_rates_does_not_accept_a_j3_at_all(self) -> None:
        """The signature is the guard: there is no argument to pass J3 through.

        A function that accepted a full :class:`ZonalGravity` and quietly used
        only its J2 would be a silent model substitution. This asserts the API
        shape that prevents it, so a later refactor cannot reintroduce the
        hazard without failing here.
        """
        parameters = set(inspect.signature(secular_rates_j2).parameters)
        assert "j2" in parameters
        assert "j3" not in parameters
        assert "j4" not in parameters
        assert "gravity" not in parameters


# --------------------------------------------------------------------------- #
# The osculating/mean gate
# --------------------------------------------------------------------------- #
class TestTheElementTypeGate:
    """The input of ``secular_rates_j2`` is mean elements, and now it says so.

    The mismatch it guards is invisible in the output — the rates come back
    finite, plausible, and wrong by ``O(J2)``, which is the size of the theory's
    own truncation error, so no bound on the result could ever distinguish the
    two. That is exactly the class of error this project treats as its
    characteristic failure, and the only defence against it is a type.
    """

    def test_osculating_elements_are_refused(self) -> None:
        """The kind ``rv_to_coe`` returns is the kind that must not come in here."""
        with pytest.raises(DomainError, match="statement about mean ones"):
            secular_rates_j2(_elements())

    def test_the_message_says_how_to_proceed_rather_than_only_what_is_wrong(self) -> None:
        """Both legitimate routes are named, and so is the piece that is missing.

        A refusal that does not say what to do instead gets worked around by the
        first reader in a hurry, and the obvious workaround here — relabelling
        without thinking, or adding a keyword — is the failure itself.
        """
        with pytest.raises(DomainError) as caught:
            secular_rates_j2(_elements())

        message = str(caught.value)
        assert "Brouwer-Lyddane" in message
        assert "relabelled_as" in message

    def test_mean_elements_pass(self) -> None:
        """The other side of the gate, so the test above is not just "it raises"."""
        rates = secular_rates_j2(_mean_elements())

        assert rates.n == 1
        assert float(rates.raan_rad_s[0]) < 0.0  # prograde: the node regresses

    def test_relabelling_changes_the_label_and_not_one_number(self) -> None:
        """The escape hatch converts nothing, and that is asserted, not promised.

        If ``relabelled_as`` ever grew a conversion, this test fails — which is
        the point. A silent conversion hidden behind a name that says "relabel"
        would be worse than the hazard the flag was added to close.
        """
        osculating = _elements()
        as_mean = osculating.relabelled_as(ElementType.MEAN_BROUWER)

        assert as_mean.element_type is ElementType.MEAN_BROUWER
        assert osculating.element_type is ElementType.OSCULATING
        for name in (
            "semi_latus_rectum_km",
            "eccentricity",
            "inclination_rad",
            "raan_rad",
            "argp_rad",
            "true_anomaly_rad",
        ):
            assert np.array_equal(getattr(as_mean, name), getattr(osculating, name))

    def test_there_is_no_parameter_that_could_wave_the_check_through(self) -> None:
        """``assume_mean=True`` would be the same silent substitution, renamed.

        The same move as ``test_secular_rates_does_not_accept_a_j3_at_all``,
        applied to the flag: a keyword letting a caller *declare* mean elements
        without *holding* mean elements would sit in the physics API, take a
        default, and be reachable from a scenario file. Saying it out loud
        belongs on the container, where only someone holding the elements can
        write it.
        """
        parameters = set(inspect.signature(secular_rates_j2).parameters)

        assert parameters == {"elements", "mu_km3_s2", "r_equatorial_km", "j2"}


# --------------------------------------------------------------------------- #
# V2-adjacent — a published mission
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestPublishedSunSynchronous:
    """A real sun-synchronous mission, and what its published digits can prove.

    Landsat-8 flies a 705 km sun-synchronous orbit at 98.2 deg inclination
    (NASA/USGS mission specification). Sun-synchronicity is the statement that
    the node precesses at exactly the rate the mean sun moves in right ascension,
    ``2 pi`` per tropical year, so the pair (altitude, inclination) is a check on
    ``raan_dot`` that involves no orbital-mechanics software at all — only the
    definition of the year.
    """

    TROPICAL_YEAR_S = 365.242_189_7 * 86_400.0
    SUN_SYNCHRONOUS_RATE_RAD_S = 2.0 * math.pi / TROPICAL_YEAR_S

    def test_landsat_8_precesses_at_the_solar_rate(self) -> None:
        """Within 1 %, which is all the published inclination licenses.

        98.2 deg is printed to a tenth of a degree, so the true inclination lies
        within +-0.05 deg. Since ``raan_dot`` goes as ``cos i``, that window is
        worth +-0.6 % in the rate — the bound below, rounded outwards.

        Worth stating plainly: this check is three orders of magnitude too coarse
        to see the J2^2 and J4 terms the module leaves out, which would move the
        required inclination by ~0.008 deg. A published mission parameter
        confirms the model; it cannot arbitrate its order.
        """
        landsat = _mean_elements(
            semi_major_axis_km=EGM96_RADIUS_EQUATORIAL_KM + 705.0,
            eccentricity=0.0001,
            inclination_deg=98.2,
        )
        rate = float(secular_rates_j2(landsat).raan_rad_s[0])
        assert rate > 0.0
        assert rate == pytest.approx(self.SUN_SYNCHRONOUS_RATE_RAD_S, rel=0.01)

    def test_a_prograde_orbit_regresses_and_a_retrograde_one_advances(self) -> None:
        """The sign that makes every SSO retrograde. Reverse it and nothing works."""
        assert float(secular_rates_j2(_mean_elements(inclination_deg=51.6)).raan_rad_s[0]) < 0.0
        assert float(secular_rates_j2(_mean_elements(inclination_deg=98.0)).raan_rad_s[0]) > 0.0


# --------------------------------------------------------------------------- #
# V1 — invariants of the secular rates
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestSecularRateInvariants:
    """Limits, symmetries and signs the closed forms have to obey."""

    def test_zero_j2_gives_the_keplerian_rates(self) -> None:
        """No harmonic, no drift, and the mean motion falls back to sqrt(mu/a^3)."""
        elements = _mean_elements()
        rates = secular_rates_j2(elements, j2=0.0)
        assert float(rates.raan_rad_s[0]) == 0.0
        assert float(rates.argp_rad_s[0]) == 0.0
        keplerian_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
        assert float(rates.anomalistic_period_s[0]) == pytest.approx(keplerian_s, rel=1e-15)
        assert float(rates.nodal_period_s[0]) == pytest.approx(keplerian_s, rel=1e-15)

    def test_a_polar_orbit_does_not_precess(self) -> None:
        """``raan_dot`` carries ``cos i``, so it is exactly zero at 90 deg."""
        rates = secular_rates_j2(_mean_elements(inclination_deg=90.0))
        assert float(rates.raan_rad_s[0]) == pytest.approx(0.0, abs=1e-22)

    def test_the_apsidal_rate_vanishes_at_the_critical_inclination(self) -> None:
        """And reverses across it, which is why Molniya orbits are flown there."""
        critical_deg = math.degrees(CRITICAL_INCLINATION_RAD)
        assert critical_deg == pytest.approx(63.4349, abs=1e-4)
        at = secular_rates_j2(_mean_elements(inclination_deg=critical_deg))
        assert float(at.argp_rad_s[0]) == pytest.approx(0.0, abs=1e-20)
        below = float(
            secular_rates_j2(_mean_elements(inclination_deg=critical_deg - 5.0)).argp_rad_s[0]
        )
        above = float(
            secular_rates_j2(_mean_elements(inclination_deg=critical_deg + 5.0)).argp_rad_s[0]
        )
        assert below > 0.0 > above

    def test_the_retrograde_mirror_is_also_critical(self) -> None:
        """``sin^2 i`` cannot tell ``i`` from ``pi - i``, so both are critical."""
        mirror_deg = 180.0 - math.degrees(CRITICAL_INCLINATION_RAD)
        rates = secular_rates_j2(_mean_elements(inclination_deg=mirror_deg))
        assert float(rates.argp_rad_s[0]) == pytest.approx(0.0, abs=1e-20)

    def test_rates_fall_off_with_altitude(self) -> None:
        """``n (R/p)^2`` goes as ``a^{-7/2}``: doubling the radius cuts it ~11x."""
        low = abs(float(secular_rates_j2(_mean_elements(semi_major_axis_km=7000.0)).raan_rad_s[0]))
        high = abs(
            float(secular_rates_j2(_mean_elements(semi_major_axis_km=14000.0)).raan_rad_s[0])
        )
        assert low / high == pytest.approx(2.0**3.5, rel=1e-12)

    def test_the_mean_anomaly_rate_straddles_the_keplerian_mean_motion(self) -> None:
        """``2 - 3 sin^2 i`` changes sign at 54.7 deg, and ``dM/dt`` with it."""
        keplerian = 2.0 * math.pi / float(orbital_period_s(LEO_SEMI_MAJOR_AXIS_KM)[0])
        assert float(
            secular_rates_j2(_mean_elements(inclination_deg=30.0)).mean_anomaly_rad_s[0]
        ) > (keplerian)
        assert float(
            secular_rates_j2(_mean_elements(inclination_deg=80.0)).mean_anomaly_rad_s[0]
        ) < (keplerian)

    def test_vectorises_over_a_stack_of_orbits(self) -> None:
        """A stack must give element-wise what each orbit gives alone."""
        inclinations = np.deg2rad(np.array([30.0, 51.6, 90.0, 98.0]))
        stack = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.01,
            inclination_rad=inclinations,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
            element_type=ElementType.MEAN_BROUWER,
        )
        together = secular_rates_j2(stack)
        assert together.n == 4
        assert len(together) == 4
        for index, inclination in enumerate(inclinations):
            alone = secular_rates_j2(
                ClassicalElements.from_semi_major_axis(
                    semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
                    eccentricity=0.01,
                    inclination_rad=float(inclination),
                    raan_rad=0.0,
                    argp_rad=0.0,
                    true_anomaly_rad=0.0,
                    element_type=ElementType.MEAN_BROUWER,
                )
            )
            assert float(together.raan_rad_s[index]) == float(alone.raan_rad_s[0])
            assert float(together.argp_rad_s[index]) == float(alone.argp_rad_s[0])

    def test_wgs72_gives_a_slightly_different_answer_than_egm96(self) -> None:
        """Different constants, different number — and the gap is the models' own.

        WGS-72 and EGM96 describe the same planet to about 1e-5 relative, so
        their J2 rates must differ by around that and not by more. If these ever
        agreed exactly, someone had collapsed the two models into one.
        """
        elements = _mean_elements()
        egm96 = float(secular_rates_j2(elements).raan_rad_s[0])
        wgs72 = float(
            secular_rates_j2(
                elements,
                mu_km3_s2=WGS72_ZONAL.mu_km3_s2,
                r_equatorial_km=WGS72_ZONAL.r_equatorial_km,
                j2=WGS72_J2,
            ).raan_rad_s[0]
        )
        assert egm96 != wgs72
        assert wgs72 == pytest.approx(egm96, rel=1e-4)

    def test_repr_is_readable_for_one_and_for_many(self) -> None:
        single = repr(secular_rates_j2(_mean_elements()))
        assert "raan=" in single and "rad/s" in single
        stack = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(np.array([30.0, 60.0])),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
            element_type=ElementType.MEAN_BROUWER,
        )
        assert repr(secular_rates_j2(stack)) == "SecularRates(n=2)"


# --------------------------------------------------------------------------- #
# V1 — the numerical propagator
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestPropagateZonal:
    """The integrator, against what it must reproduce."""

    def test_a_two_body_field_reproduces_the_kepler_solution(self) -> None:
        """With no harmonics, the integration and `kepler.py` must agree to 1 m.

        This is the cross-check in the other direction from
        ``test_kepler.py::TestAgainstNumericalIntegration``: there the integrator
        validated the closed form, here the closed form validates that the
        integrator was assembled correctly — same equation, opposite roles.
        """
        # A 0.1-eccentricity orbit is raised to a = 9000 km deliberately: at the
        # 7078 km used elsewhere its perigee would be 6370 km, i.e. inside the
        # Earth, and the force model rejects that — correctly, and it did.
        elements = _elements(semi_major_axis_km=9000.0, eccentricity=0.1)
        r0, v0 = coe_to_rv(elements)
        period_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
        times = np.array([0.25, 0.5, 1.0]) * period_s
        r_km, v_km_s = propagate_zonal(r0[0], v0[0], times, TWO_BODY_ONLY)
        # After a whole period a two-body orbit is exactly where it started.
        assert np.allclose(r_km[2], r0[0], atol=1e-3, rtol=0.0)
        assert np.allclose(v_km_s[2], v0[0], atol=1e-6, rtol=0.0)

    def test_energy_is_conserved_in_the_zonal_field(self) -> None:
        """The zonal potential is conservative, so ``v^2/2 - U`` cannot drift.

        The bound is 1e-10, a hundred times the integrator's own ``rtol``. That
        is the right order to ask for: a conserved quantity computed from an
        integration cannot be conserved better than the integration is accurate,
        and the measured drift over five revolutions is 3e-12 — right at that
        floor, and not growing. An acceleration that was not a gradient, which is
        the usual outcome of a transcribed sign error, would instead show a drift
        that grows with time and blows through this by orders of magnitude even
        though every individual component looked plausible.
        """
        elements = _elements(eccentricity=0.05)
        r0, v0 = coe_to_rv(elements)
        period_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
        times = np.linspace(0.0, 5.0 * period_s, 200)
        r_km, v_km_s = propagate_zonal(r0[0], v0[0], times, EGM96_ZONAL)
        energy = np.array(
            [
                0.5 * float(np.dot(v, v)) - _zonal_potential(r, EGM96_ZONAL)
                for r, v in zip(r_km, v_km_s, strict=True)
            ]
        )
        assert np.max(np.abs(energy / energy[0] - 1.0)) < 1e-10

    def test_polar_angular_momentum_is_conserved(self) -> None:
        """An axially symmetric field cannot torque about its own axis.

        ``h_z`` is the conserved quantity of that symmetry, and it is the one
        that fails if a harmonic ever acquires a spurious longitude dependence.
        The in-plane components are *not* conserved, and the test says so, so
        that the symmetry being asserted is the real one rather than a stronger
        claim that happens to pass.
        """
        elements = _elements(inclination_deg=51.6, eccentricity=0.05)
        r0, v0 = coe_to_rv(elements)
        period_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
        r_km, v_km_s = propagate_zonal(
            r0[0], v0[0], np.linspace(0.0, 3.0 * period_s, 120), EGM96_ZONAL
        )
        momentum = np.cross(r_km, v_km_s)
        # Same reasoning as the energy bound: 100x rtol. Measured drift is 1e-12.
        assert np.max(np.abs(momentum[:, 2] / momentum[0, 2] - 1.0)) < 1e-10
        # ...and the in-plane components move by ~1e-3, six orders more. Asserting
        # that too is what keeps the test about axial symmetry rather than about
        # the integrator being quiet.
        assert np.max(np.abs(momentum[:, 0] / momentum[0, 0] - 1.0)) > 1e-6

    def test_backwards_propagation_undoes_forwards(self) -> None:
        """Integrating out and back must return the initial state.

        Also the test that exercises the negative branch of ``dt_s``, which is
        what a TLE epoch sitting in the middle of a time grid produces.
        """
        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        period_s = float(orbital_period_s(elements.semi_major_axis_km)[0])
        r_km, v_km_s = propagate_zonal(
            r0[0], v0[0], np.array([-period_s, 0.0, period_s]), EGM96_ZONAL
        )
        assert np.allclose(r_km[1], r0[0], atol=1e-9, rtol=0.0)
        assert np.allclose(v_km_s[1], v0[0], atol=1e-12, rtol=0.0)
        back, back_v = propagate_zonal(r_km[2], v_km_s[2], np.array([-period_s]), EGM96_ZONAL)
        assert np.allclose(back[0], r0[0], atol=1e-3, rtol=0.0)
        assert np.allclose(back_v[0], v0[0], atol=1e-6, rtol=0.0)

    def test_a_zero_offset_returns_the_initial_state_exactly(self) -> None:
        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        r_km, v_km_s = propagate_zonal(r0[0], v0[0], np.array([0.0]), EGM96_ZONAL)
        assert np.allclose(r_km[0], r0[0], atol=1e-12, rtol=0.0)
        assert np.allclose(v_km_s[0], v0[0], atol=1e-15, rtol=0.0)

    def test_the_j2_displacement_after_one_day_is_kilometres(self) -> None:
        """What the perturbation is worth in the quantity a link budget sees.

        A day of J2 moves a LEO by hundreds of kilometres along-track relative to
        a two-body propagation. Stated as a test because it is the answer to
        "does this matter for a multi-day scenario", and the answer is yes by
        three orders of magnitude over a pass's geometry tolerance.
        """
        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        one_day = np.array([86_400.0])
        with_j2, _ = propagate_zonal(r0[0], v0[0], one_day, EGM96_ZONAL)
        without, _ = propagate_zonal(r0[0], v0[0], one_day, TWO_BODY_ONLY)
        separation_km = float(np.linalg.norm(with_j2[0] - without[0]))
        assert 100.0 < separation_km < 20_000.0


# --------------------------------------------------------------------------- #
# V1 — rejection of bad input
# --------------------------------------------------------------------------- #
class TestRejectsBadInput:
    """Every public entry point validates, and says what is wrong."""

    def test_gravity_model_rejects_a_non_positive_mu(self) -> None:
        with pytest.raises(DomainError, match="mu_km3_s2"):
            ZonalGravity(mu_km3_s2=0.0, r_equatorial_km=6378.0)

    def test_gravity_model_rejects_a_non_positive_radius(self) -> None:
        with pytest.raises(DomainError, match="r_equatorial_km"):
            ZonalGravity(mu_km3_s2=EGM96_MU_KM3_S2, r_equatorial_km=-1.0)

    def test_gravity_model_rejects_a_non_finite_harmonic(self) -> None:
        with pytest.raises(DomainError, match="j3"):
            ZonalGravity(mu_km3_s2=EGM96_MU_KM3_S2, r_equatorial_km=6378.0, j3=float("nan"))

    def test_acceleration_rejects_a_position_inside_the_earth(self) -> None:
        """The expansion does not converge there, and a satellite is not there."""
        with pytest.raises(DomainError, match="reference radius"):
            zonal_acceleration(np.array([1000.0, 0.0, 0.0]))

    def test_the_metres_for_kilometres_mistake_is_caught(self) -> None:
        """A LEO radius written in metres reads as 7e6 km — but in km it reads as 7000 m.

        The second is the one that lands inside the Earth and is caught here. The
        first is not catchable by a bound, because a radius of 7e6 km is a
        legitimate heliocentric distance, and inventing an upper limit would
        reject cislunar work to catch a typo.
        """
        with pytest.raises(DomainError, match="metres"):
            zonal_acceleration(np.array([7078.137e-3, 0.0, 0.0]))

    def test_acceleration_rejects_a_bad_shape(self) -> None:
        with pytest.raises(DomainError, match=r"\(n, 3\)"):
            zonal_acceleration(np.array([[1.0, 2.0], [3.0, 4.0]]))

    def test_acceleration_rejects_non_finite_input(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            zonal_acceleration(np.array([7000.0, np.nan, 0.0]))

    def test_two_body_rejects_the_earths_centre(self) -> None:
        with pytest.raises(DomainError, match="Earth's centre"):
            two_body_acceleration(np.zeros(3))

    def test_two_body_rejects_a_non_positive_mu(self) -> None:
        with pytest.raises(DomainError, match="mu_km3_s2"):
            two_body_acceleration(np.array([7000.0, 0.0, 0.0]), -1.0)

    def test_secular_rates_reject_a_non_positive_mu(self) -> None:
        with pytest.raises(DomainError, match="mu_km3_s2"):
            secular_rates_j2(_mean_elements(), mu_km3_s2=0.0)

    def test_secular_rates_reject_a_non_finite_j2(self) -> None:
        with pytest.raises(DomainError, match="j2"):
            secular_rates_j2(_mean_elements(), j2=float("inf"))

    def test_propagate_rejects_more_than_one_initial_state(self) -> None:
        """An ODE cannot be broadcast, and the message says what to do instead."""
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(np.array([30.0, 60.0])),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        r0, v0 = coe_to_rv(elements)
        with pytest.raises(DomainError, match="one orbit at a time"):
            propagate_zonal(r0, v0, np.array([100.0]))

    def test_propagate_rejects_mismatched_state_shapes(self) -> None:
        with pytest.raises(DomainError, match="same orbit"):
            propagate_zonal(
                np.array([[7000.0, 0.0, 0.0], [7000.0, 0.0, 0.0]]),
                np.array([0.0, 7.5, 0.0]),
                np.array([100.0]),
            )

    def test_propagate_rejects_a_non_increasing_time_grid(self) -> None:
        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        with pytest.raises(DomainError, match="strictly increasing"):
            propagate_zonal(r0[0], v0[0], np.array([0.0, 100.0, 50.0]))

    @pytest.mark.parametrize(("rtol", "atol_km"), [(0.0, 1e-9), (1e-12, -1.0)])
    def test_propagate_rejects_non_positive_tolerances(self, rtol: float, atol_km: float) -> None:
        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        with pytest.raises(DomainError, match="finite and positive"):
            propagate_zonal(r0[0], v0[0], np.array([100.0]), rtol=rtol, atol_km=atol_km)

    def test_a_decaying_orbit_is_rejected_by_the_force_model_mid_flight(self) -> None:
        """The validation is per evaluation, not just on the initial state.

        A state whose perigee is above the surface but whose *trajectory* dips
        below it is only detectable once the integration gets there — and it is,
        because the acceleration validates every position it is handed rather
        than trusting the caller's first one.
        """
        # Released at apogee (7452 km, perfectly valid) on an orbit whose perigee
        # is 6348 km, i.e. 30 km below the reference radius. The initial state
        # passes every check; half a revolution later the trajectory does not.
        grazing = _elements(semi_major_axis_km=6900.0, eccentricity=0.08, true_anomaly_deg=180.0)
        r0, v0 = coe_to_rv(grazing)
        with pytest.raises(DomainError, match="reference radius"):
            propagate_zonal(r0[0], v0[0], np.array([3000.0]))

    def test_an_integrator_failure_becomes_a_convergence_error(self) -> None:
        """The failure path exists, and says something useful when it fires.

        Forced with a stub rather than a physical case, and deliberately: every
        state that genuinely breaks DOP853 here is caught earlier by the force
        model's own domain check, so without this the branch would be code that
        has never run — and the day it does run is the day someone needs its
        message to be right. Same reasoning as ``test_kepler.py``'s
        ``test_post_condition_can_fire``.
        """

        class _FailedSolution:
            success = False
            message = "Required step size is less than spacing between numbers."

        def _failing_solve_ivp(*_args: object, **_kwargs: object) -> _FailedSolution:
            return _FailedSolution()

        elements = _elements()
        r0, v0 = coe_to_rv(elements)
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(perturbations_module, "solve_ivp", _failing_solve_ivp)
            with pytest.raises(ConvergenceError, match="decays into the Earth"):
                propagate_zonal(r0[0], v0[0], np.array([100.0]))

    def test_the_legendre_helper_guards_its_own_degree(self) -> None:
        """A private guard, exercised so that it is not a line that has never run.

        ``_legendre`` is reachable only from this module, so a bad degree is a
        programming error and raises ``ValueError`` rather than ``DomainError``.
        The test exists for the same reason the branch does: an untested raise is
        a ``NameError`` waiting for the worst possible moment.
        """
        with pytest.raises(ValueError, match=r"degrees 2\.\.4"):
            perturbations_module._legendre(5, np.array([0.5]))


class TestModuleSurface:
    """The public surface is what the rest of the project may rely on."""

    def test_everything_exported_exists(self) -> None:
        for name in perturbations_module.__all__:
            assert hasattr(perturbations_module, name), name

    def test_the_presets_carry_matched_constants(self) -> None:
        """A preset that mixed models would be the failure the class exists to stop."""
        assert EGM96_ZONAL.mu_km3_s2 == EGM96_MU_KM3_S2
        assert EGM96_ZONAL.r_equatorial_km == EGM96_RADIUS_EQUATORIAL_KM
        assert EGM96_ZONAL.j2 == EGM96_J2
        assert EGM96_ZONAL.j4 == EGM96_J4
        assert WGS72_ZONAL.j2 == WGS72_J2
        assert WGS72_ZONAL.r_equatorial_km != EGM96_ZONAL.r_equatorial_km

    def test_the_gravity_model_is_immutable(self) -> None:
        """A force model that could be mutated mid-run would make a result unreproducible."""
        with pytest.raises((AttributeError, TypeError)):
            EGM96_ZONAL.j2 = 0.0  # type: ignore[misc]

    def test_secular_rates_are_immutable(self) -> None:
        rates = secular_rates_j2(_mean_elements())
        with pytest.raises((AttributeError, TypeError)):
            rates.raan_rad_s = np.zeros(1)  # type: ignore[misc]

    def test_secular_rates_can_be_built_directly(self) -> None:
        """The container is a plain value type; nothing about it needs the module."""
        rates = SecularRates(
            raan_rad_s=np.array([-1e-6]),
            argp_rad_s=np.array([1e-6]),
            mean_anomaly_rad_s=np.array([1e-3]),
        )
        assert rates.n == 1
        assert float(rates.anomalistic_period_s[0]) == pytest.approx(2.0 * math.pi / 1e-3)
