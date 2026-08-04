"""Tests for `quoss.orbits.kepler`.

Organised by verification level, per `tests/golden/README.md`:

* ``TestPublishedVallado*`` — V2, the worked examples of Vallado, *Fundamentals
  of Astrodynamics and Applications*, 4th ed., 2013, transcribed with their
  page numbers. The strongest level available, and the first V2 data in the
  project.
* ``TestInvariants*`` / ``TestDegenerate*`` / ``TestRejects*`` — V1,
  self-consistency with no external data.
* ``TestAgainstNumericalIntegration`` — V3, an independent implementation of the
  same physics: SciPy's DOP853 integrator on the two-body equation of motion.
* ``TestTheElementTypeFlag`` — V1 on a label rather than a number: the
  osculating/mean distinction is worth kilometres and shows up in no output, so
  what can be asserted is the shape of the API that makes confusing them
  impossible.

There is no V4 block. A snapshot of this module's own output would add nothing
that the round-trip invariants do not already pin down.
"""

import math
from typing import Any

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st
from scipy.integrate import solve_ivp

from quoss.core.constants import EGM96_MU_KM3_S2, WGS84_RADIUS_EQUATORIAL_KM
from quoss.core.errors import ConvergenceError, DomainError
from quoss.orbits import kepler as kepler_module
from quoss.orbits.frames import Frame
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    advance_mean_anomaly,
    coe_to_rv,
    eccentric_from_mean_anomaly,
    eccentric_from_true_anomaly,
    mean_from_eccentric_anomaly,
    mean_from_true_anomaly,
    mean_motion_rad_s,
    orbital_period_s,
    rv_to_coe,
    semi_major_axis_from_period_km,
    true_from_eccentric_anomaly,
    true_from_mean_anomaly,
)

# --------------------------------------------------------------------------- #
# Vallado's worked examples, transcribed
#
# Rule 5 of tests/golden/README.md: inputs written out explicitly, so which cases
# are covered is readable. These are V2 data — hand-entered from a citable
# source — and therefore live next to their citation rather than in a generated
# file under tests/golden/data/.
#
# Vallado works in mu = 398600.4418 km^3/s^2, which is the EGM96 value QuOSS
# defaults to, so no override is needed.
# --------------------------------------------------------------------------- #
VALLADO_2_1_MEAN_ANOMALY_DEG = 235.4
VALLADO_2_1_ECCENTRICITY = 0.4
VALLADO_2_1_ECCENTRIC_ANOMALY_DEG = 220.512074767522
VALLADO_2_1_ECCENTRIC_ANOMALY_RAD = 3.84866174509717
"""Example 2-1, pp. 66-68: Kepler's equation, solved for E."""

VALLADO_2_5_R_IJK_KM = (6524.834, 6862.875, 6448.296)
VALLADO_2_5_V_IJK_KM_S = (4.901327, 5.533756, -1.976341)
VALLADO_2_5_EXPECTED = {
    "r_magnitude_km": 11456.57,
    "v_magnitude_km_s": 7.651888,
    "specific_energy_km2_s2": -5.516604,
    "p_km": 11067.790,
    "a_km": 36127.343,
    "eccentricity": 0.832853,
    "inclination_deg": 87.870,
    "raan_deg": 227.898,
    "argp_deg": 53.38,
    "true_anomaly_deg": 92.335,
}
"""Example 2-5, pp. 114-116: RV2COE.

The argument of latitude ``u`` is asserted separately — see
``VALLADO_2_5_U_CORRECT_DEG`` — because the value the book *prints* (145.60549°)
is a confirmed erratum and is documented as one rather than used as a reference.
``TestPublishedVallado25.test_argument_of_latitude_errata`` establishes the
correct value from the published state, and
``TestPublishedVallado25.test_argument_of_latitude_property_carries_the_v2_value``
ties it to ``ClassicalElements.argument_of_latitude_rad``, which is the
accessor every caller will use.

The other two auxiliary angles of Algorithm 9 are **not** transcribed here. This
orbit is neither circular nor equatorial, so the longitude of periapsis and the
true longitude are not part of its element set; the values our elements imply are
281.2832° and 13.6183°, and if the scanned page prints either of them they are a
free V2 pair waiting to be added.
"""

# Argument of latitude u = omega + nu for Example 2-5.
#
# The book (p. 116) prints u = 145.60549 deg and shows the formula:
#
#   u = arccos( n.r / (|n| |r|) )
#
# with operands  |n| = 66374.17,  |r| = 11456.67,
#   n.r = (-44500.5)(6524.834) + (-49246.7)(6862.875).
#
# Two errors are present on that page:
#
#   1. |r| is printed as 11456.67 km instead of the correct 11456.57 km --
#      a digit transposition (57 -> 67).  With the wrong value the formula
#      evaluates to 145.7193794974 deg, not 145.60549 deg.
#
#   2. Even using those wrong operands, the printed result 145.60549 deg is
#      arithmetically wrong: the expression yields 145.7193 deg, not 145.606 deg.
#      There is no third definition of u that recovers the printed number.
#
# The correct value, computed from the published r and v vectors with full
# double precision, is 145.720087380597 deg, confirmed by two independent routes:
#
#   Route 1 -- vector formula (definition):
#     h = r x v = (-49246.67792015, 44500.50424119, 2469.64476138)
#     n = k_hat x h = (-44500.50424119, -49246.67792015, 0)
#     cos u = (n.r) / (|n| |r|) = -0.8262958108435008
#     r_z > 0  ->  no 360 deg correction needed
#     u = arccos(-0.826296) = 145.720087380597 deg
#
#   Route 2 -- elements (omega + nu):
#     omega = 53.384930618460 deg,  nu = 92.335156762137 deg
#     u = omega + nu = 145.720087380597 deg   (exact to numerical precision)
#
# The value 145.60549 deg must not be used as a reference.
VALLADO_2_5_U_CORRECT_DEG = 145.720087380597
VALLADO_2_5_U_PRINTED_ERRATA_DEG = 145.60549

VALLADO_2_5_PRINTED_NODE_MAGNITUDE = 66374.17
VALLADO_2_5_PRINTED_R_KM = 11456.67
"""The two denominators as printed on p. 116. The second carries the 57 -> 67 typo."""

VALLADO_2_5_U_WITH_WRONG_R_DEG = 145.7193794974
"""What the page's expression gives when evaluated with the page's own operands.

Not typed in from anywhere: ``test_argument_of_latitude_errata`` recomputes it
from ``VALLADO_2_5_PRINTED_NODE_MAGNITUDE``, ``VALLADO_2_5_PRINTED_R_KM`` and the
node components as the book rounds them, and asserts the two agree to 1e-9 deg.
Reproducing the book's arithmetic is what localises the error: it shows the
formula was transcribed correctly, which leaves the printed *result* as the only
thing that does not follow.
"""

VALLADO_2_6_INPUT = {
    "p_km": 11067.790,
    "eccentricity": 0.83285,
    "inclination_deg": 87.87,
    "raan_deg": 227.89,
    "argp_deg": 53.38,
    "true_anomaly_deg": 92.335,
}
VALLADO_2_6_R_PQW_KM = (-466.7639, 11447.0219, 0.0)
VALLADO_2_6_V_PQW_KM_S = (-5.996222, 4.753601, 0.0)
VALLADO_2_6_R_IJK_KM = (6525.344, 6861.535, 6449.125)
VALLADO_2_6_V_IJK_KM_S = (4.902276, 5.533124, -1.975709)
"""Example 2-6, pp. 119-120: COE2RV.

Note that Algorithm 10 takes the semi-latus rectum, not the semi-major axis, and
that the input elements are printed more coarsely than Example 2-5 computed
them. The output vectors are therefore close to, but not equal to, Example 2-5's
inputs — see ``TestPublishedVallado26`` for how much that is worth.
"""


def _elements_from_degrees(
    p_km: float,
    eccentricity: float,
    inclination_deg: float,
    raan_deg: float,
    argp_deg: float,
    true_anomaly_deg: float,
) -> ClassicalElements:
    """Build elements from the degree-valued form a book prints them in."""
    return ClassicalElements(
        semi_latus_rectum_km=p_km,
        eccentricity=eccentricity,
        inclination_rad=math.radians(inclination_deg),
        raan_rad=math.radians(raan_deg),
        argp_rad=math.radians(argp_deg),
        true_anomaly_rad=math.radians(true_anomaly_deg),
    )


def _vallado_25_elements() -> ClassicalElements:
    """Run Algorithm 9 on Example 2-5's published state vector."""
    return rv_to_coe(np.array([VALLADO_2_5_R_IJK_KM]), np.array([VALLADO_2_5_V_IJK_KM_S]))


def _vallado_26_elements() -> ClassicalElements:
    """Assemble Example 2-6's published input elements."""
    return _elements_from_degrees(
        VALLADO_2_6_INPUT["p_km"],
        VALLADO_2_6_INPUT["eccentricity"],
        VALLADO_2_6_INPUT["inclination_deg"],
        VALLADO_2_6_INPUT["raan_deg"],
        VALLADO_2_6_INPUT["argp_deg"],
        VALLADO_2_6_INPUT["true_anomaly_deg"],
    )


# --------------------------------------------------------------------------- #
# V2 — published values
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestPublishedVallado21:
    """Example 2-1, pp. 66-68: ``M = 235.4 deg``, ``e = 0.4``."""

    def test_mean_anomaly_in_radians_matches_the_printed_conversion(self) -> None:
        """The book prints the input in both units; check we start from the same number."""
        assert math.radians(VALLADO_2_1_MEAN_ANOMALY_DEG) == pytest.approx(
            4.10850505919465, abs=1e-14
        )

    def test_eccentric_anomaly(self) -> None:
        """The published solution, to every digit the book prints.

        The bound is one part in 1e14 of a radian, which is a few ulp at this
        magnitude: the book quotes 15 significant figures, so there is no
        transcription slack to hide behind here. This is the tightest V2
        assertion in the project, and it is tight because the source is exact.
        """
        got = eccentric_from_mean_anomaly(
            math.radians(VALLADO_2_1_MEAN_ANOMALY_DEG), VALLADO_2_1_ECCENTRICITY
        )
        assert float(got[0]) == pytest.approx(VALLADO_2_1_ECCENTRIC_ANOMALY_RAD, abs=1e-14)
        assert math.degrees(float(got[0])) == pytest.approx(
            VALLADO_2_1_ECCENTRIC_ANOMALY_DEG, abs=1e-11
        )

    def test_the_published_answer_satisfies_keplers_equation(self) -> None:
        """Independent of our solver: put the book's E back into M = E - e sin E.

        If the published value were mistranscribed, this would catch it without
        consulting the code under test at all.
        """
        ecc_anomaly = VALLADO_2_1_ECCENTRIC_ANOMALY_RAD
        mean = ecc_anomaly - VALLADO_2_1_ECCENTRICITY * math.sin(ecc_anomaly)
        assert math.degrees(mean) == pytest.approx(VALLADO_2_1_MEAN_ANOMALY_DEG, abs=1e-12)

    def test_inverse_returns_the_published_mean_anomaly(self) -> None:
        got = mean_from_eccentric_anomaly(
            VALLADO_2_1_ECCENTRIC_ANOMALY_RAD, VALLADO_2_1_ECCENTRICITY
        )
        assert math.degrees(float(got[0])) == pytest.approx(VALLADO_2_1_MEAN_ANOMALY_DEG, abs=1e-12)


@pytest.mark.physics
class TestPublishedVallado25:
    """Example 2-5, pp. 114-116: RV2COE.

    Every bound below is half a unit in the last printed digit — the most the
    source can license — except for the inclination, which needs its own
    explanation and gets one.
    """

    def test_state_magnitudes(self) -> None:
        """The intermediate scalars the book prints on the way to the elements."""
        r = np.array(VALLADO_2_5_R_IJK_KM)
        v = np.array(VALLADO_2_5_V_IJK_KM_S)
        r_mag = float(np.linalg.norm(r))
        v_mag = float(np.linalg.norm(v))
        assert r_mag == pytest.approx(VALLADO_2_5_EXPECTED["r_magnitude_km"], abs=5e-3)
        assert v_mag == pytest.approx(VALLADO_2_5_EXPECTED["v_magnitude_km_s"], abs=5e-7)
        energy = 0.5 * v_mag**2 - EGM96_MU_KM3_S2 / r_mag
        assert energy == pytest.approx(VALLADO_2_5_EXPECTED["specific_energy_km2_s2"], abs=5e-7)

    def test_semi_latus_rectum(self) -> None:
        """Published to 3 decimals; we land 8 m away, ~17x the print rounding.

        That excess is the book's own working precision, not ours: Example 2-5
        carries about seven significant figures through several intermediate
        steps. The bound is therefore stated as a relative one, 1e-6, which is
        the accuracy the printed digits actually support and which every other
        magnitude in this example also meets.
        """
        coe = _vallado_25_elements()
        assert float(coe.semi_latus_rectum_km[0]) == pytest.approx(
            VALLADO_2_5_EXPECTED["p_km"], rel=1e-6
        )

    def test_semi_major_axis(self) -> None:
        coe = _vallado_25_elements()
        assert float(coe.semi_major_axis_km[0]) == pytest.approx(
            VALLADO_2_5_EXPECTED["a_km"], rel=1e-6
        )

    def test_eccentricity(self) -> None:
        coe = _vallado_25_elements()
        assert float(coe.eccentricity[0]) == pytest.approx(
            VALLADO_2_5_EXPECTED["eccentricity"], abs=5e-7
        )

    def test_inclination_disagrees_with_the_printed_digit(self) -> None:
        """87.8691 deg, where the book prints 87.870 deg.

        The gap is 0.00087 deg: 1.7 times the half-unit that three printed
        decimals allow, and the only quantity in the example that exceeds its
        own print rounding. It is recorded here rather than absorbed into a
        looser tolerance, because a V2 test whose bound is widened until it
        passes has stopped being V2.

        The value produced here is the one the published state vector implies:
        the elements round-trip back to that state to 15 nm (see
        ``TestInvariantsElementsState``), so the inclination is consistent with
        every other element in the set. The most likely explanation is a rounding
        of 87.8691 in the last printed place.
        """
        coe = _vallado_25_elements()
        got_deg = math.degrees(float(coe.inclination_rad[0]))
        assert got_deg == pytest.approx(87.86913, abs=1e-5)
        assert abs(got_deg - float(VALLADO_2_5_EXPECTED["inclination_deg"])) == pytest.approx(
            8.7e-4, abs=1e-5
        )

    def test_raan(self) -> None:
        """Printed to 3 decimals, matched inside the half-unit that allows."""
        coe = _vallado_25_elements()
        assert math.degrees(float(coe.raan_rad[0])) == pytest.approx(
            VALLADO_2_5_EXPECTED["raan_deg"], abs=5e-4
        )

    def test_argument_of_periapsis(self) -> None:
        """Printed to 2 decimals only, so the bound is 0.005 deg."""
        coe = _vallado_25_elements()
        assert math.degrees(float(coe.argp_rad[0])) == pytest.approx(
            VALLADO_2_5_EXPECTED["argp_deg"], abs=5e-3
        )

    def test_true_anomaly(self) -> None:
        coe = _vallado_25_elements()
        assert math.degrees(float(coe.true_anomaly_rad[0])) == pytest.approx(
            VALLADO_2_5_EXPECTED["true_anomaly_deg"], abs=5e-4
        )

    def test_neither_degeneracy_flag_is_raised(self) -> None:
        """A strongly eccentric, near-polar orbit: no angle should have been folded."""
        coe = _vallado_25_elements()
        assert not bool(coe.is_circular[0])
        assert not bool(coe.is_equatorial[0])

    def test_the_elements_reproduce_the_published_state(self) -> None:
        """Round trip back through the module, to sub-micrometre.

        The strongest statement available about this example: whatever the last
        digit of the printed inclination, the six elements we extract carry the
        whole of the input state and nothing has been lost or invented.
        """
        coe = _vallado_25_elements()
        r_km, v_km_s = coe_to_rv(coe)
        assert np.allclose(r_km[0], VALLADO_2_5_R_IJK_KM, atol=1e-9, rtol=0.0)
        assert np.allclose(v_km_s[0], VALLADO_2_5_V_IJK_KM_S, atol=1e-12, rtol=0.0)

    def test_argument_of_latitude_errata(self) -> None:
        """u = omega + nu = 145.720087 deg -- the value printed in Vallado (145.60549 deg) is wrong.

        Vallado p. 116 prints u = 145.60549 deg via arccos(n.r / (|n||r|)), but
        two errors are present on that page:

        1. ``|r|`` is given as 11456.67 km instead of the correct 11456.57 km
           (a digit transposition, 57 -> 67).  Evaluating the printed formula
           with those wrong operands yields 145.7193794974 deg, not 145.60549 deg.

        2. Even the wrong-|r| result does not match the printed 145.60549 deg.
           There is no arithmetic path from the page's own numbers to that value.

        The correct u follows from two independent routes that agree to numerical
        precision, and is asserted against both.  The printed value is recorded
        here as a documented book erratum, not used as a bound.
        """
        coe = _vallado_25_elements()
        omega_deg = math.degrees(float(coe.argp_rad[0]))
        nu_deg = math.degrees(float(coe.true_anomaly_rad[0]))
        u_from_elements_deg = omega_deg + nu_deg

        # Route 1: omega + nu (mod 360 not needed; both angles are in (0 deg, 180 deg))
        assert u_from_elements_deg == pytest.approx(VALLADO_2_5_U_CORRECT_DEG, abs=1e-9)

        # Route 2: vector formula  cos u = (n.r) / (|n| |r|)
        r = np.array(VALLADO_2_5_R_IJK_KM)
        v = np.array(VALLADO_2_5_V_IJK_KM_S)
        h = np.cross(r, v)
        k = np.array([0.0, 0.0, 1.0])
        n_vec = np.cross(k, h)
        cos_u = np.dot(n_vec, r) / (np.linalg.norm(n_vec) * np.linalg.norm(r))
        # r_z > 0, so no (360 deg - u) correction
        u_from_vectors_deg = math.degrees(math.acos(float(np.clip(cos_u, -1.0, 1.0))))
        assert u_from_vectors_deg == pytest.approx(VALLADO_2_5_U_CORRECT_DEG, abs=1e-9)

        # Confirm the two routes agree with each other exactly
        assert u_from_elements_deg == pytest.approx(u_from_vectors_deg, abs=1e-12)

        # Layer 1 of the erratum, reproduced rather than asserted from memory.
        #
        # Evaluating the page's own expression with the page's own operands has
        # to give the page's own intermediate value, and it does — to ten
        # decimals. That is what turns "the book is wrong" into "the book is
        # wrong *here*": the transcription of the formula is verified, so the
        # only thing left unexplained is the printed result.
        #
        # Both roundings on the page matter and both are used: |r| carries the
        # 57 -> 67 transposition, and the node components are printed to one
        # decimal, which shifts the result in the tenth digit.
        printed_node = np.array([-44500.5, -49246.7, 0.0])
        printed_dot = float(printed_node[0] * r[0] + printed_node[1] * r[1])
        u_from_printed_operands_deg = math.degrees(
            math.acos(printed_dot / (VALLADO_2_5_PRINTED_NODE_MAGNITUDE * VALLADO_2_5_PRINTED_R_KM))
        )
        assert u_from_printed_operands_deg == pytest.approx(
            VALLADO_2_5_U_WITH_WRONG_R_DEG, abs=1e-9
        )

        # Layer 2: that value is *not* the one the book prints. The gap is
        # 0.1146 deg, 160 times the 7.1e-4 deg the |r| typo alone is worth, so
        # the transposition cannot account for the printed number and nothing
        # else on the page does either.
        typo_cost_deg = abs(u_from_printed_operands_deg - VALLADO_2_5_U_CORRECT_DEG)
        printed_gap_deg = abs(VALLADO_2_5_U_PRINTED_ERRATA_DEG - VALLADO_2_5_U_CORRECT_DEG)
        assert typo_cost_deg == pytest.approx(7.1e-4, abs=1e-5)
        assert printed_gap_deg == pytest.approx(0.1146, abs=1e-4)
        assert printed_gap_deg > 100.0 * typo_cost_deg

    def test_argument_of_latitude_property_carries_the_v2_value(self) -> None:
        """The published ``u`` validates the accessor, not just a sum written in this file.

        ``test_argument_of_latitude_errata`` derives the correct u by two routes
        it computes itself. That proves the *number*, and proves the book wrong,
        but it never touches
        :attr:`~quoss.orbits.kepler.ClassicalElements.argument_of_latitude_rad`
        — so the only V2 datum the project holds for u would validate arithmetic
        living in the test file rather than the code every caller reaches for.
        This closes that gap: same published state, same expected value, through
        the property.

        Example 2-5 keeps ``omega + nu`` under 360 deg, so the wrap the property
        applies is a no-op here. That it is not always a no-op is
        ``TestInvariantsElementsState.test_argument_of_latitude_wraps_past_one_turn``.
        """
        coe = _vallado_25_elements()
        u_deg = math.degrees(float(np.asarray(coe.argument_of_latitude_rad)[0]))
        assert u_deg == pytest.approx(VALLADO_2_5_U_CORRECT_DEG, abs=1e-9)


@pytest.mark.physics
class TestPublishedVallado26:
    """Example 2-6, pp. 119-120: COE2RV.

    The example is a decomposition test as much as a value test, because the
    printed inputs are rounded harder than Example 2-5 computed them. Each stage
    is therefore held to its own bound, and the two bounds say different things.
    """

    def test_perifocal_state_matches_to_the_last_printed_digit(self) -> None:
        """The PQW stage depends only on p, e and nu, all printed precisely.

        Isolated by setting the three orientation angles to zero, which makes the
        perifocal basis the identity, so :func:`coe_to_rv` returns exactly the
        vectors the book prints as its intermediate result. No rotation is
        involved, so this bound is tight: 0.1 m and 0.1 mm/s, which is the
        printing precision itself.
        """
        perifocal = _elements_from_degrees(
            VALLADO_2_6_INPUT["p_km"],
            VALLADO_2_6_INPUT["eccentricity"],
            0.0,
            0.0,
            0.0,
            VALLADO_2_6_INPUT["true_anomaly_deg"],
        )
        r_km, v_km_s = coe_to_rv(perifocal)
        assert np.allclose(r_km[0], VALLADO_2_6_R_PQW_KM, atol=1e-4, rtol=0.0)
        assert np.allclose(v_km_s[0], VALLADO_2_6_V_PQW_KM_S, atol=1e-6, rtol=0.0)

    def test_inertial_state_is_within_the_printed_element_rounding(self) -> None:
        """The claim the published digits actually license.

        The orientation angles are printed to two decimals, so the true elements
        lie anywhere in a box of half a hundredth of a degree per angle. Rotating
        through the corner of that box moves the satellite by up to 1.3 km at
        this radius, and that — not anything tighter — is what Example 2-6
        guarantees. Asserted explicitly so the honest bound is on the record.
        """
        elements = _vallado_26_elements()
        r_km, v_km_s = coe_to_rv(elements)
        assert float(np.linalg.norm(r_km[0] - np.array(VALLADO_2_6_R_IJK_KM))) < 1.4
        assert float(np.linalg.norm(v_km_s[0] - np.array(VALLADO_2_6_V_IJK_KM_S))) < 1.1e-3

    def test_inertial_state_is_in_fact_far_closer_than_that(self) -> None:
        """And the measured agreement, which is 25 m rather than 1.3 km.

        This bound is stronger than the source licenses, so it is a regression
        guard rather than a V2 claim, and it is separated from the assertion
        above for exactly that reason. The residual is Vallado's own accumulated
        rounding: the perifocal stage above matches to 0.1 m, so the whole 25 m
        enters in the rotation, where he carries fewer digits than he prints.
        """
        elements = _vallado_26_elements()
        r_km, v_km_s = coe_to_rv(elements)
        assert float(np.linalg.norm(r_km[0] - np.array(VALLADO_2_6_R_IJK_KM))) < 0.03
        assert float(np.linalg.norm(v_km_s[0] - np.array(VALLADO_2_6_V_IJK_KM_S))) < 2e-5

    def test_it_does_not_return_example_2_5s_input(self) -> None:
        """The two examples are not a round trip, and pretending otherwise hides a bug.

        Example 2-6's elements are Example 2-5's, rounded. Feeding them back
        gives a state about 1.4 km from where 2-5 started. A test that asserted
        the round trip closed would have to use a tolerance loose enough to hide
        a real error, so the gap is pinned instead.
        """
        elements = _vallado_26_elements()
        r_km, _ = coe_to_rv(elements)
        gap_km = float(np.linalg.norm(r_km[0] - np.array(VALLADO_2_5_R_IJK_KM)))
        assert 1.0 < gap_km < 2.0


# --------------------------------------------------------------------------- #
# V1 — invariants
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestInvariantsKeplerEquation:
    def test_residual_over_a_dense_grid(self) -> None:
        """``|E - e sin E - M|`` across the whole supported eccentricity range.

        The bound is the machine floor, not a tuned number: the residual is a
        difference of terms of order 1 rad, so a few ulp of a float64 near 1 is
        ~4e-16 and anything under a handful of those is as good as the
        representation allows. Measured worst case is 1.4e-15.
        """
        ecc_values = np.array([0.0, 1e-9, 0.001, 0.05, 0.2, 0.4, 0.7, 0.9, 0.95, 0.99, 0.9999])
        mean = np.linspace(-math.pi, math.pi, 2001)
        worst = 0.0
        for ecc in ecc_values:
            ecc_anomaly = eccentric_from_mean_anomaly(mean, float(ecc))
            residual = np.abs(ecc_anomaly - ecc * np.sin(ecc_anomaly) - mean)
            worst = max(worst, float(np.max(residual)))
        assert worst < 2e-15

    def test_circular_orbit_needs_no_solving(self) -> None:
        """At e = 0 Kepler's equation is the identity, and must be exactly so."""
        mean = np.linspace(-10.0, 10.0, 101)
        assert np.array_equal(eccentric_from_mean_anomaly(mean, 0.0), mean)

    def test_odd_symmetry(self) -> None:
        """E(-M) = -E(M): Kepler's equation is odd in the mean anomaly."""
        mean = np.linspace(0.0, math.pi, 257)
        forward = eccentric_from_mean_anomaly(mean, 0.6)
        backward = eccentric_from_mean_anomaly(-mean, 0.6)
        assert np.allclose(backward, -forward, atol=1e-15, rtol=0.0)

    def test_strictly_increasing_in_mean_anomaly(self) -> None:
        """dE/dM = 1/(1 - e cos E) > 0, so the solution can never fold back."""
        mean = np.linspace(-3.0 * math.pi, 3.0 * math.pi, 5001)
        assert np.all(np.diff(eccentric_from_mean_anomaly(mean, 0.85)) > 0.0)

    @pytest.mark.parametrize("revolutions", [-3, -1, 0, 1, 7])
    def test_revolutions_are_carried_through(self, revolutions: int) -> None:
        """E(M + 2 pi k) = E(M) + 2 pi k, exactly.

        This is what keeps a propagated series continuous. Without it, a plot of
        eccentric anomaly against time is a sawtooth and any interpolation across
        a revolution boundary is silently wrong.
        """
        mean = np.linspace(-math.pi + 1e-6, math.pi - 1e-6, 97)
        base = eccentric_from_mean_anomaly(mean, 0.5)
        shifted = eccentric_from_mean_anomaly(mean + 2.0 * math.pi * revolutions, 0.5)
        assert np.allclose(shifted, base + 2.0 * math.pi * revolutions, atol=1e-13, rtol=0.0)

    def test_periapsis_and_apoapsis_are_fixed_points(self) -> None:
        """All three anomalies coincide at 0 and pi, for every eccentricity."""
        for ecc in (0.0, 0.1, 0.6, 0.95):
            assert float(eccentric_from_mean_anomaly(0.0, ecc)[0]) == 0.0
            assert float(true_from_mean_anomaly(0.0, ecc)[0]) == 0.0
            assert float(eccentric_from_mean_anomaly(math.pi, ecc)[0]) == pytest.approx(
                math.pi, abs=1e-15
            )
            assert float(true_from_mean_anomaly(math.pi, ecc)[0]) == pytest.approx(
                math.pi, abs=1e-15
            )

    def test_true_anomaly_leads_mean_anomaly_before_apoapsis(self) -> None:
        """A satellite spends less than half its period on the inbound leg.

        Between periapsis and apoapsis the true anomaly runs ahead of the mean
        one, and behind it after. Sign of the whole construction, and the check
        that would fail if the two were ever swapped.
        """
        mean = np.linspace(0.1, math.pi - 0.1, 101)
        assert np.all(true_from_mean_anomaly(mean, 0.6) > mean)
        assert np.all(true_from_mean_anomaly(mean + math.pi, 0.6) < mean + math.pi)

    def test_post_condition_can_fire(self) -> None:
        """The residual guard is real code, so it is exercised rather than trusted.

        Nothing iterates in this solver, so the guard cannot fire on any input;
        tightening its threshold below the machine floor is the only way to reach
        it. A branch that is never executed is a branch that raises ``NameError``
        the first time it matters.
        """
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(kepler_module, "_KEPLER_RESIDUAL_TOLERANCE_RAD", 1e-18)
            with pytest.raises(ConvergenceError, match="post-condition"):
                eccentric_from_mean_anomaly(np.linspace(0.0, math.pi, 51), 0.9)


@pytest.mark.physics
class TestInvariantsAnomalyConversions:
    @settings(max_examples=400, deadline=None)
    @given(
        mean_deg=st.floats(min_value=-1440.0, max_value=1440.0, allow_nan=False),
        ecc=st.floats(min_value=0.0, max_value=0.98, allow_nan=False),
    )
    def test_mean_eccentric_roundtrip(self, mean_deg: float, ecc: float) -> None:
        mean = math.radians(mean_deg)
        ecc_anomaly = eccentric_from_mean_anomaly(mean, ecc)
        assert float(mean_from_eccentric_anomaly(ecc_anomaly, ecc)[0]) == pytest.approx(
            mean, abs=1e-12
        )

    @settings(max_examples=400, deadline=None)
    @given(
        true_deg=st.floats(min_value=-1440.0, max_value=1440.0, allow_nan=False),
        ecc=st.floats(min_value=0.0, max_value=0.98, allow_nan=False),
    )
    def test_true_eccentric_roundtrip(self, true_deg: float, ecc: float) -> None:
        true_anomaly = math.radians(true_deg)
        ecc_anomaly = eccentric_from_true_anomaly(true_anomaly, ecc)
        assert float(true_from_eccentric_anomaly(ecc_anomaly, ecc)[0]) == pytest.approx(
            true_anomaly, abs=1e-12
        )

    @settings(max_examples=400, deadline=None)
    @given(
        mean_deg=st.floats(min_value=-1440.0, max_value=1440.0, allow_nan=False),
        ecc=st.floats(min_value=0.0, max_value=0.98, allow_nan=False),
    )
    def test_mean_true_roundtrip(self, mean_deg: float, ecc: float) -> None:
        mean = math.radians(mean_deg)
        true_anomaly = true_from_mean_anomaly(mean, ecc)
        assert float(mean_from_true_anomaly(true_anomaly, ecc)[0]) == pytest.approx(mean, abs=1e-12)

    def test_all_three_agree_at_low_eccentricity(self) -> None:
        """As e -> 0 the three anomalies converge, with the leading gap 2 e sin M.

        Checks the *rate*, not just the limit: an implementation with the wrong
        sign or a factor of two in the series would still pass a bare "they get
        close" assertion.
        """
        mean = np.linspace(0.2, 3.0, 41)
        ecc = 1e-4
        true_anomaly = true_from_mean_anomaly(mean, ecc)
        assert np.allclose(true_anomaly - mean, 2.0 * ecc * np.sin(mean), rtol=1e-3, atol=0.0)

    def test_vectorises_and_broadcasts(self) -> None:
        mean = np.linspace(0.0, 2.0 * math.pi, 64)
        assert eccentric_from_mean_anomaly(mean, 0.3).shape == (64,)
        assert eccentric_from_mean_anomaly(mean, np.full(64, 0.3)).shape == (64,)
        assert eccentric_from_mean_anomaly(1.0, np.linspace(0.0, 0.9, 16)).shape == (16,)


@pytest.mark.physics
class TestInvariantsSizeAndPeriod:
    @settings(max_examples=200, deadline=None)
    @given(axis_km=st.floats(min_value=6500.0, max_value=50_000.0, allow_nan=False))
    def test_period_axis_roundtrip(self, axis_km: float) -> None:
        period = orbital_period_s(axis_km)
        assert float(semi_major_axis_from_period_km(period)[0]) == pytest.approx(axis_km, rel=1e-13)

    def test_period_and_mean_motion_are_reciprocal(self) -> None:
        axis = np.linspace(6600.0, 45_000.0, 64)
        assert np.allclose(
            mean_motion_rad_s(axis) * orbital_period_s(axis), 2.0 * math.pi, rtol=1e-14
        )

    def test_keplers_third_law(self) -> None:
        """T^2 / a^3 is the same constant for every orbit around the same body."""
        axis = np.array([6878.0, 12_000.0, 26_560.0, 42_164.0])
        ratio = orbital_period_s(axis) ** 2 / axis**3
        assert np.allclose(ratio, ratio[0], rtol=1e-14)
        assert float(ratio[0]) == pytest.approx(4.0 * math.pi**2 / EGM96_MU_KM3_S2, rel=1e-14)

    def test_a_550_km_orbit_takes_about_95_minutes(self) -> None:
        """A sanity anchor anyone can check against a LEO mission page."""
        period_min = float(orbital_period_s(WGS84_RADIUS_EQUATORIAL_KM + 550.0)[0]) / 60.0
        assert 95.0 < period_min < 96.0

    def test_advance_by_one_period_is_one_revolution(self) -> None:
        axis = 7000.0
        motion = mean_motion_rad_s(axis)
        period = orbital_period_s(axis)
        advanced = advance_mean_anomaly(0.7, motion, period)
        assert float(advanced[0]) == pytest.approx(0.7 + 2.0 * math.pi, abs=1e-12)

    def test_advance_runs_backwards_too(self) -> None:
        motion = mean_motion_rad_s(7000.0)
        assert float(advance_mean_anomaly(0.0, motion, -100.0)[0]) < 0.0

    def test_advance_does_not_wrap(self) -> None:
        """Wrapping here would break the revolution count the conversions preserve."""
        motion = mean_motion_rad_s(7000.0)
        period = orbital_period_s(7000.0)
        assert float(advance_mean_anomaly(0.0, motion, 5.0 * period)[0]) > 30.0


@pytest.mark.physics
class TestInvariantsElementsState:
    @staticmethod
    def _grid() -> ClassicalElements:
        """Return a spread of non-degenerate orbits: LEO to GEO, prograde and retrograde."""
        return ClassicalElements(
            semi_latus_rectum_km=np.array([6878.0, 11_067.79, 26_000.0, 42_164.0, 8000.0]),
            eccentricity=np.array([0.001, 0.83285, 0.72, 0.0004, 0.15]),
            inclination_rad=np.deg2rad([51.6, 87.87, 63.4, 5.0, 120.0]),
            raan_rad=np.deg2rad([10.0, 227.89, 300.0, 45.0, 190.0]),
            argp_rad=np.deg2rad([0.5, 53.38, 270.0, 120.0, 33.0]),
            true_anomaly_rad=np.deg2rad([12.0, 92.335, 200.0, 355.0, 179.0]),
        )

    def test_elements_state_roundtrip(self) -> None:
        coe = self._grid()
        r_km, v_km_s = coe_to_rv(coe)
        back = rv_to_coe(r_km, v_km_s)
        assert np.allclose(back.semi_latus_rectum_km, coe.semi_latus_rectum_km, rtol=1e-13)
        assert np.allclose(back.eccentricity, coe.eccentricity, atol=1e-13)
        assert np.allclose(back.inclination_rad, coe.inclination_rad, atol=1e-13)
        assert np.allclose(back.raan_rad, coe.raan_rad, atol=1e-13)
        assert np.allclose(back.argp_rad, coe.argp_rad, atol=1e-12)
        assert np.allclose(back.true_anomaly_rad, coe.true_anomaly_rad, atol=1e-12)

    def test_state_elements_state_roundtrip(self) -> None:
        """The direction that matters for a propagator: the state must survive."""
        coe = self._grid()
        r_km, v_km_s = coe_to_rv(coe)
        r_back, v_back = coe_to_rv(rv_to_coe(r_km, v_km_s))
        assert np.max(np.abs(r_back - r_km)) < 1e-9
        assert np.max(np.abs(v_back - v_km_s)) < 1e-12

    def test_angular_momentum_matches_the_semi_latus_rectum(self) -> None:
        """``p = h^2 / mu`` — the defining relation, checked against the state."""
        coe = self._grid()
        r_km, v_km_s = coe_to_rv(coe)
        h_mag = np.linalg.norm(np.cross(r_km, v_km_s), axis=1)
        assert np.allclose(h_mag**2 / EGM96_MU_KM3_S2, coe.semi_latus_rectum_km, rtol=1e-13)

    def test_vis_viva(self) -> None:
        """``v^2 = mu (2/r - 1/a)``, the energy integral, independent of the angles."""
        coe = self._grid()
        r_km, v_km_s = coe_to_rv(coe)
        r_mag = np.linalg.norm(r_km, axis=1)
        v_mag = np.linalg.norm(v_km_s, axis=1)
        expected = EGM96_MU_KM3_S2 * (2.0 / r_mag - 1.0 / coe.semi_major_axis_km)
        assert np.allclose(v_mag**2, expected, rtol=1e-13)

    def test_radius_at_periapsis_and_apoapsis(self) -> None:
        """The derived radii, checked by actually going there."""
        coe = self._grid()
        at_periapsis = ClassicalElements(
            semi_latus_rectum_km=coe.semi_latus_rectum_km,
            eccentricity=coe.eccentricity,
            inclination_rad=coe.inclination_rad,
            raan_rad=coe.raan_rad,
            argp_rad=coe.argp_rad,
            true_anomaly_rad=np.zeros(coe.n),
        )
        at_apoapsis = ClassicalElements(
            semi_latus_rectum_km=coe.semi_latus_rectum_km,
            eccentricity=coe.eccentricity,
            inclination_rad=coe.inclination_rad,
            raan_rad=coe.raan_rad,
            argp_rad=coe.argp_rad,
            true_anomaly_rad=np.full(coe.n, math.pi),
        )
        r_peri, _ = coe_to_rv(at_periapsis)
        r_apo, _ = coe_to_rv(at_apoapsis)
        assert np.allclose(np.linalg.norm(r_peri, axis=1), coe.periapsis_radius_km, rtol=1e-14)
        assert np.allclose(np.linalg.norm(r_apo, axis=1), coe.apoapsis_radius_km, rtol=1e-14)

    def test_velocity_is_perpendicular_to_the_radius_at_the_apsides(self) -> None:
        coe = ClassicalElements(
            semi_latus_rectum_km=9000.0,
            eccentricity=0.3,
            inclination_rad=1.1,
            raan_rad=2.2,
            argp_rad=0.4,
            true_anomaly_rad=np.array([0.0, math.pi]),
        )
        r_km, v_km_s = coe_to_rv(coe)
        # Normalised, so the bound is the cosine of the angle between them rather
        # than a dot product whose scale is ~4e4 km^2/s and whose float64 floor is
        # therefore several picometres per second.
        cosine = np.einsum("ij,ij->i", r_km, v_km_s) / (
            np.linalg.norm(r_km, axis=1) * np.linalg.norm(v_km_s, axis=1)
        )
        assert np.allclose(cosine, 0.0, atol=1e-15)

    def test_orbit_plane_normal_matches_the_inclination(self) -> None:
        coe = self._grid()
        r_km, v_km_s = coe_to_rv(coe)
        h_vec = np.cross(r_km, v_km_s)
        inc = np.arccos(h_vec[:, 2] / np.linalg.norm(h_vec, axis=1))
        assert np.allclose(inc, coe.inclination_rad, atol=1e-14)

    def test_semi_major_axis_and_semi_latus_rectum_agree(self) -> None:
        coe = self._grid()
        assert np.allclose(
            coe.semi_latus_rectum_km,
            coe.semi_major_axis_km * (1.0 - coe.eccentricity**2),
            rtol=1e-14,
        )

    def test_from_semi_major_axis_is_the_same_orbit(self) -> None:
        coe = self._grid()
        rebuilt = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=coe.semi_major_axis_km,
            eccentricity=coe.eccentricity,
            inclination_rad=coe.inclination_rad,
            raan_rad=coe.raan_rad,
            argp_rad=coe.argp_rad,
            true_anomaly_rad=coe.true_anomaly_rad,
        )
        assert np.allclose(rebuilt.semi_latus_rectum_km, coe.semi_latus_rectum_km, rtol=1e-14)

    def test_scalar_construction_gives_length_one(self) -> None:
        coe = ClassicalElements(
            semi_latus_rectum_km=7000.0,
            eccentricity=0.01,
            inclination_rad=1.0,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        assert coe.n == 1
        assert len(coe) == 1
        r_km, _ = coe_to_rv(coe)
        assert r_km.shape == (1, 3)

    def test_angles_are_wrapped_on_construction(self) -> None:
        coe = ClassicalElements(
            semi_latus_rectum_km=7000.0,
            eccentricity=0.01,
            inclination_rad=1.0,
            raan_rad=-1.0,
            argp_rad=7.0,
            true_anomaly_rad=-9.0,
        )
        for angle in (coe.raan_rad, coe.argp_rad, coe.true_anomaly_rad):
            assert 0.0 <= float(np.asarray(angle)[0]) < 2.0 * math.pi

    def test_argument_of_latitude_wraps_past_one_turn(self) -> None:
        """``u = omega + nu`` folds back inside the turn, and does so without a branch.

        Both operands are already wrapped to ``[0, 2 pi)`` on construction, so
        their sum reaches 720 deg and the property is the only place the fold
        can happen. Vallado 2-5 cannot exercise it — its ``omega + nu`` is
        145.7 deg — so the case is built here: 310 deg + 200 deg = 510 deg has
        to read as 150 deg.

        Run over a stack that mixes a wrapping orbit with a non-wrapping one,
        because the fold is vectorised and a branch would only show up when
        both cases share a call.
        """
        coe = ClassicalElements(
            semi_latus_rectum_km=np.array([7000.0, 7000.0]),
            eccentricity=np.array([0.01, 0.01]),
            inclination_rad=np.deg2rad([51.6, 51.6]),
            raan_rad=np.deg2rad([10.0, 10.0]),
            argp_rad=np.deg2rad([310.0, 40.0]),
            true_anomaly_rad=np.deg2rad([200.0, 100.0]),
        )
        u_deg = np.degrees(np.asarray(coe.argument_of_latitude_rad))
        assert u_deg[0] == pytest.approx(150.0, abs=1e-10)  # 510 deg, wrapped
        assert u_deg[1] == pytest.approx(140.0, abs=1e-10)  # 140 deg, untouched
        assert np.all((u_deg >= 0.0) & (u_deg < 360.0))

    def test_repr_is_readable_for_one_and_for_many(self) -> None:
        one = repr(
            ClassicalElements(
                semi_latus_rectum_km=7000.0,
                eccentricity=0.01,
                inclination_rad=1.0,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
            )
        )
        assert "7000.000" in one and "teme" in one
        assert "n=5" in repr(self._grid())

    def test_frame_travels_with_the_elements(self) -> None:
        r_km = np.array([VALLADO_2_5_R_IJK_KM])
        v_km_s = np.array([VALLADO_2_5_V_IJK_KM_S])
        assert rv_to_coe(r_km, v_km_s).frame is Frame.TEME
        assert rv_to_coe(r_km, v_km_s, frame=Frame.GCRF).frame is Frame.GCRF


# --------------------------------------------------------------------------- #
# The osculating/mean flag
# --------------------------------------------------------------------------- #
class TestTheElementTypeFlag:
    """Six numbers are not an orbit until they say which ellipse they describe.

    Nothing here measures physics, because the hazard produces no wrong number
    *in this module*: labelling a mean element set as osculating and converting
    it costs 14.6 km after one revolution and 219 km after a day, and every
    intermediate quantity on the way there is finite and plausible. So what is
    asserted is the shape of the API — that the label exists, that it travels,
    that the two functions which can only be right for one kind refuse the
    other, and that the escape hatch escapes nothing.
    """

    @staticmethod
    def _elements(element_type: ElementType = ElementType.OSCULATING) -> ClassicalElements:
        return ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=7078.137,
            eccentricity=0.001,
            inclination_rad=np.deg2rad(98.19),
            raan_rad=0.4,
            argp_rad=1.2,
            true_anomaly_rad=0.7,
            element_type=element_type,
        )

    def test_the_enum_holds_exactly_the_two_kinds_that_exist(self) -> None:
        """And in particular there is no bare ``MEAN``.

        Same pattern as ``PropagationMethod`` in ``test_propagator.py``: the set
        is pinned so that widening it is a decision someone takes deliberately.
        The two absences are different in kind and both deliberate.
        ``MEAN_KOZAI_SGP4`` is missing because ADR 0005 decided ``tle.py`` never
        builds a ``ClassicalElements`` — SGP4 returns a state, whose elements are
        osculating — so nothing could produce it. A plain ``MEAN`` is missing for
        a stronger reason: it would be *wrong*, because Brouwer-Lyddane/EGM96
        mean elements and Brouwer-Kozai/WGS-72 ones are not interchangeable, and
        a single name for both would assert that they are.

        Naming the member after its theory is also what keeps the enum cheap to
        grow: no call site can have written ``MEAN``, so adding a second mean
        flavour later touches none of them.
        """
        assert {member.value for member in ElementType} == {"osculating", "mean_brouwer"}
        assert not hasattr(ElementType, "MEAN")
        assert not hasattr(ElementType, "MEAN_KOZAI_SGP4")

    def test_elements_are_osculating_unless_told_otherwise(self) -> None:
        """The default is the only kind QuOSS can currently produce."""
        assert self._elements().element_type is ElementType.OSCULATING

    def test_rv_to_coe_mints_osculating_elements(self) -> None:
        """A state vector determines the tangent ellipse and nothing else."""
        r_km = np.array([VALLADO_2_5_R_IJK_KM])
        v_km_s = np.array([VALLADO_2_5_V_IJK_KM_S])

        assert rv_to_coe(r_km, v_km_s).element_type is ElementType.OSCULATING

    def test_coe_to_rv_refuses_mean_elements(self) -> None:
        """The direction where the kilometres are actually lost.

        The intuitive place to guard the distinction is ``secular_rates_j2``,
        whose theory needs mean elements. But feeding *that* osculating elements
        costs ``O(J2)`` — the theory's own truncation error — whereas converting
        mean elements to a state as though they were osculating is the 219 km/day
        error. Guarding only the first would have left the larger hole open.
        """
        with pytest.raises(DomainError, match="osculating by definition"):
            coe_to_rv(self._elements(ElementType.MEAN_BROUWER))

    def test_the_refusal_says_what_is_missing_and_what_to_do(self) -> None:
        """Naming Brouwer-Lyddane is the point: the conversion does not exist yet.

        A caller who hits this has no way to proceed correctly today, and the
        message has to say so rather than implying a function they will go
        looking for and not find.
        """
        with pytest.raises(DomainError) as caught:
            coe_to_rv(self._elements(ElementType.MEAN_BROUWER))

        message = str(caught.value)
        assert "Brouwer-Lyddane" in message
        assert "relabelled_as" in message

    def test_osculating_elements_still_convert(self) -> None:
        """The gate has an open side, and it is the one everything uses."""
        r_km, v_km_s = coe_to_rv(self._elements())

        assert r_km.shape == (1, 3)
        assert np.all(np.isfinite(v_km_s))

    def test_relabelling_moves_the_label_and_nothing_else(self) -> None:
        """Bit-for-bit identical numbers, asserted rather than promised.

        ``relabelled_as`` exists so that the tests which feed the secular theory
        osculating elements on purpose have to say so. If it ever grew a
        conversion, this fails — and it should, because a conversion hiding
        behind the word "relabel" would be worse than the confusion the flag was
        added to prevent.
        """
        osculating = self._elements()
        relabelled = osculating.relabelled_as(ElementType.MEAN_BROUWER)

        assert relabelled.element_type is ElementType.MEAN_BROUWER
        assert relabelled is not osculating
        assert osculating.element_type is ElementType.OSCULATING  # not mutated
        for name in (
            "semi_latus_rectum_km",
            "eccentricity",
            "inclination_rad",
            "raan_rad",
            "argp_rad",
            "true_anomaly_rad",
        ):
            assert np.array_equal(getattr(relabelled, name), getattr(osculating, name))

    def test_relabelling_keeps_the_frame(self) -> None:
        """The other tag travels through unchanged; they are independent."""
        elements = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=7078.137,
            eccentricity=0.001,
            inclination_rad=1.7,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
            frame=Frame.GCRF,
        )

        assert elements.relabelled_as(ElementType.MEAN_BROUWER).frame is Frame.GCRF

    def test_a_string_is_accepted_and_resolved(self) -> None:
        """So a stage-4 scenario field can be YAML text with no converter.

        Permissive at the boundary, strict inside: what is *stored* is a member,
        so no consumer downstream ever compares against a bare string.
        """
        elements = self._elements(element_type="mean_brouwer")  # type: ignore[arg-type]

        assert elements.element_type is ElementType.MEAN_BROUWER

    def test_an_unknown_label_names_the_valid_ones(self) -> None:
        """Including why the name someone most likely reached for is absent."""
        with pytest.raises(DomainError, match="not an element type"):
            self._elements(element_type="mean")  # type: ignore[arg-type]

    def test_the_label_is_in_the_repr(self) -> None:
        """A repr that hid it would defeat the purpose of carrying it."""
        assert "osculating" in repr(self._elements())
        assert "mean_brouwer" in repr(self._elements(ElementType.MEAN_BROUWER))


@pytest.mark.physics
class TestDegenerateOrbits:
    """Circular and equatorial orbits: the cases the classical angles cannot name.

    Each one asserts two things: that the state survives exactly, and that the
    convention applied is the documented one rather than whatever fell out.
    """

    @staticmethod
    def _roundtrip(coe: ClassicalElements) -> tuple[ClassicalElements, float]:
        r_km, v_km_s = coe_to_rv(coe)
        back = rv_to_coe(r_km, v_km_s)
        r_back, v_back = coe_to_rv(back)
        worst = max(
            float(np.max(np.abs(r_back - r_km))),
            float(np.max(np.abs(v_back - v_km_s))),
        )
        return back, worst

    def test_circular_inclined(self) -> None:
        """No periapsis: argp folds into the true anomaly, which becomes ``u``."""
        coe = ClassicalElements(
            semi_latus_rectum_km=6928.137,
            eccentricity=0.0,
            inclination_rad=math.radians(97.4),
            raan_rad=1.0,
            argp_rad=0.0,
            true_anomaly_rad=2.5,
        )
        back, worst = self._roundtrip(coe)
        assert worst < 1e-9
        assert bool(back.is_circular[0])
        assert not bool(back.is_equatorial[0])
        assert float(np.asarray(back.argp_rad)[0]) == 0.0
        assert float(np.asarray(back.true_anomaly_rad)[0]) == pytest.approx(2.5, abs=1e-12)
        assert float(np.asarray(back.raan_rad)[0]) == pytest.approx(1.0, abs=1e-12)

    def test_circular_inclined_folds_a_nonzero_argp(self) -> None:
        """With argp = 40 deg and nu = 100 deg, the answer must be u = 140 deg."""
        coe = ClassicalElements(
            semi_latus_rectum_km=6928.137,
            eccentricity=0.0,
            inclination_rad=math.radians(97.4),
            raan_rad=1.0,
            argp_rad=math.radians(40.0),
            true_anomaly_rad=math.radians(100.0),
        )
        back, worst = self._roundtrip(coe)
        assert worst < 1e-9
        assert math.degrees(float(np.asarray(back.true_anomaly_rad)[0])) == pytest.approx(
            140.0, abs=1e-9
        )
        assert math.degrees(float(np.asarray(back.argument_of_latitude_rad)[0])) == pytest.approx(
            140.0, abs=1e-9
        )

    @pytest.mark.parametrize("inclination_deg", [0.0, 180.0])
    def test_equatorial_eccentric(self, inclination_deg: float) -> None:
        """No node: raan folds into argp, which becomes the longitude of periapsis.

        Run for both the prograde and the retrograde equator, because the node
        vector vanishes in both and only the sign convention distinguishes them.
        """
        coe = ClassicalElements(
            semi_latus_rectum_km=42_164.0,
            eccentricity=0.01,
            inclination_rad=math.radians(inclination_deg),
            raan_rad=0.0,
            argp_rad=0.7,
            true_anomaly_rad=1.3,
        )
        back, worst = self._roundtrip(coe)
        assert worst < 1e-8
        assert bool(back.is_equatorial[0])
        assert not bool(back.is_circular[0])
        assert float(np.asarray(back.raan_rad)[0]) == 0.0
        assert float(np.asarray(back.argp_rad)[0]) == pytest.approx(0.7, abs=1e-11)

    @pytest.mark.parametrize("inclination_deg", [0.0, 180.0])
    def test_circular_equatorial(self, inclination_deg: float) -> None:
        """Both angles undefined: the true anomaly becomes the true longitude."""
        coe = ClassicalElements(
            semi_latus_rectum_km=42_164.0,
            eccentricity=0.0,
            inclination_rad=math.radians(inclination_deg),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=1.3,
        )
        back, worst = self._roundtrip(coe)
        assert worst < 1e-8
        assert bool(back.is_circular[0])
        assert bool(back.is_equatorial[0])
        assert float(np.asarray(back.raan_rad)[0]) == 0.0
        assert float(np.asarray(back.argp_rad)[0]) == 0.0
        assert float(np.asarray(back.true_anomaly_rad)[0]) == pytest.approx(1.3, abs=1e-11)

    def test_folding_is_lossless_for_the_state(self) -> None:
        """The claim the whole convention rests on, over a mixed stack.

        Degenerate and ordinary orbits together in one array, so the vectorised
        ``np.where`` branches are all exercised at once and a mask that selected
        the wrong rows would show up here rather than in a single-orbit test.
        """
        coe = ClassicalElements(
            semi_latus_rectum_km=np.array([6928.0, 42_164.0, 42_164.0, 11_067.79, 7000.0]),
            eccentricity=np.array([0.0, 0.01, 0.0, 0.83285, 0.001]),
            inclination_rad=np.deg2rad([97.4, 0.0, 180.0, 87.87, 51.6]),
            raan_rad=np.deg2rad([57.3, 0.0, 0.0, 227.89, 10.0]),
            argp_rad=np.deg2rad([0.0, 40.0, 0.0, 53.38, 25.0]),
            true_anomaly_rad=np.deg2rad([143.2, 74.5, 74.5, 92.335, 12.0]),
        )
        r_km, v_km_s = coe_to_rv(coe)
        back = rv_to_coe(r_km, v_km_s)
        r_back, v_back = coe_to_rv(back)
        assert np.max(np.abs(r_back - r_km)) < 1e-8
        assert np.max(np.abs(v_back - v_km_s)) < 1e-11
        assert list(back.is_circular) == [True, False, True, False, False]
        assert list(back.is_equatorial) == [False, True, True, False, False]

    def test_a_real_near_circular_orbit_keeps_its_periapsis(self) -> None:
        """e = 1e-6 is small but perfectly measurable, so nothing may be folded.

        The threshold is 1e-11 rather than the conventional 1e-8 precisely so
        that an orbit like this one — an ordinary "circular" LEO as a real
        ephemeris describes it — keeps a meaningful argument of periapsis.
        """
        coe = ClassicalElements(
            semi_latus_rectum_km=7000.0,
            eccentricity=1e-6,
            inclination_rad=1.0,
            raan_rad=2.0,
            argp_rad=3.0,
            true_anomaly_rad=0.4,
        )
        r_km, v_km_s = coe_to_rv(coe)
        back = rv_to_coe(r_km, v_km_s)
        assert not bool(back.is_circular[0])
        assert float(np.asarray(back.argp_rad)[0]) == pytest.approx(3.0, abs=1e-6)


@pytest.mark.physics
class TestRejectsBadInput:
    @pytest.mark.parametrize("ecc", [1.0, 1.5, 100.0])
    def test_unbound_eccentricity(self, ecc: float) -> None:
        with pytest.raises(DomainError, match="bound orbits only"):
            eccentric_from_mean_anomaly(0.5, ecc)

    def test_negative_eccentricity(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            eccentric_from_mean_anomaly(0.5, -1e-9)

    @pytest.mark.parametrize("bad", [np.array([]), np.zeros((2, 2)), np.array([np.nan])])
    def test_malformed_anomaly_input(self, bad: np.ndarray) -> None:
        with pytest.raises(DomainError):
            eccentric_from_mean_anomaly(bad, 0.1)

    def test_non_broadcastable_lengths(self) -> None:
        with pytest.raises(DomainError, match="neither 1 nor"):
            eccentric_from_mean_anomaly(np.zeros(5), np.zeros(3))

    @pytest.mark.parametrize("axis", [0.0, -7000.0])
    def test_non_positive_semi_major_axis(self, axis: float) -> None:
        with pytest.raises(DomainError, match="must be positive"):
            mean_motion_rad_s(axis)

    def test_non_positive_period(self) -> None:
        with pytest.raises(DomainError, match="must be positive"):
            semi_major_axis_from_period_km(0.0)

    @pytest.mark.parametrize("mu", [0.0, -1.0, float("inf"), float("nan")])
    def test_bad_gravitational_parameter(self, mu: float) -> None:
        with pytest.raises(DomainError, match="mu_km3_s2"):
            mean_motion_rad_s(7000.0, mu)

    def test_non_positive_semi_latus_rectum(self) -> None:
        with pytest.raises(DomainError, match="semi_latus_rectum_km must be positive"):
            ClassicalElements(
                semi_latus_rectum_km=0.0,
                eccentricity=0.0,
                inclination_rad=0.0,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
            )

    def test_inclination_in_degrees(self) -> None:
        """The same trap frames.py guards against: 97.4 passed as radians."""
        with pytest.raises(DomainError, match="degrees that were never converted"):
            ClassicalElements(
                semi_latus_rectum_km=7000.0,
                eccentricity=0.0,
                inclination_rad=97.4,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
            )

    @pytest.mark.parametrize("frame", [Frame.ITRF, Frame.ENU])
    def test_elements_reject_a_rotating_frame(self, frame: Frame) -> None:
        """Elements in an Earth-fixed frame are not elements. Made unrepresentable."""
        with pytest.raises(DomainError, match="inertial frame"):
            ClassicalElements(
                semi_latus_rectum_km=7000.0,
                eccentricity=0.0,
                inclination_rad=0.0,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
                frame=frame,
            )

    def test_from_semi_major_axis_rejects_a_non_positive_axis(self) -> None:
        with pytest.raises(DomainError, match="semi_major_axis_km must be positive"):
            ClassicalElements.from_semi_major_axis(
                semi_major_axis_km=-1.0,
                eccentricity=0.0,
                inclination_rad=0.0,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
            )

    def test_mismatched_state_shapes(self) -> None:
        with pytest.raises(DomainError, match="state pair"):
            rv_to_coe(np.zeros((3, 3)) + 7000.0, np.zeros((2, 3)))

    @pytest.mark.parametrize(
        ("bad", "reason"),
        [
            (np.zeros((2, 4)), "trailing axis is not 3"),
            (np.zeros((2, 3, 3)), "not 2-D"),
            (np.zeros((0, 3)), "empty"),
            (np.full((1, 3), np.nan), "not finite"),
        ],
    )
    def test_malformed_state_arrays(self, bad: np.ndarray, reason: str) -> None:
        """Every rejection branch of the vector validator, exercised.

        ``(n, 3)`` with time first is the array contract of
        :mod:`quoss.core.types`; a transposed ``(3, n)`` stack is the mistake it
        exists to catch, and it is caught here as "trailing axis is not 3".
        """
        with pytest.raises(DomainError):
            rv_to_coe(bad, bad)

    def test_position_at_the_earth_centre(self) -> None:
        with pytest.raises(DomainError, match="Earth's centre"):
            rv_to_coe(np.zeros((1, 3)), np.array([[1.0, 0.0, 0.0]]))

    def test_radial_trajectory(self) -> None:
        """Position parallel to velocity: zero angular momentum, so no orbit plane."""
        with pytest.raises(DomainError, match="radial fall"):
            rv_to_coe(np.array([[7000.0, 0.0, 0.0]]), np.array([[1.0, 0.0, 0.0]]))

    def test_hyperbolic_state(self) -> None:
        """Escape speed at 7000 km is ~10.67 km/s; 12 km/s is unbound."""
        with pytest.raises(DomainError, match="unbound state"):
            rv_to_coe(np.array([[7000.0, 0.0, 0.0]]), np.array([[0.0, 12.0, 0.0]]))

    def test_exactly_parabolic_state_is_rejected_too(self) -> None:
        """Zero energy is the boundary, and the boundary is out."""
        escape = math.sqrt(2.0 * EGM96_MU_KM3_S2 / 7000.0)
        with pytest.raises(DomainError, match="unbound state"):
            rv_to_coe(np.array([[7000.0, 0.0, 0.0]]), np.array([[0.0, escape, 0.0]]))

    def test_coe_to_rv_rejects_a_bad_gravitational_parameter(self) -> None:
        coe = ClassicalElements(
            semi_latus_rectum_km=7000.0,
            eccentricity=0.0,
            inclination_rad=0.0,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        with pytest.raises(DomainError, match="mu_km3_s2"):
            coe_to_rv(coe, -1.0)


# --------------------------------------------------------------------------- #
# V3 — against an independent implementation
# --------------------------------------------------------------------------- #
@pytest.mark.reference
class TestAgainstNumericalIntegration:
    """The analytic solution, checked against a numerical one.

    SciPy's DOP853 integrating ``r'' = -mu r / |r|^3`` is an independent
    implementation of the same physics: nothing it does resembles Kepler's
    equation or the perifocal basis, so an error shared between the two is
    implausible. It closes the whole chain at once —
    ``rv_to_coe -> advance_mean_anomaly -> true_from_mean_anomaly -> coe_to_rv``
    — which no single-function test can do.

    Unlike the astropy reference data in ``tests/golden/data/``, this oracle is
    not frozen to a file. Freezing buys nothing here: SciPy is already a core
    dependency, the integrator is deterministic, and the comparison is made at a
    tolerance three orders of magnitude looser than the integrator's own error,
    so a version bump cannot move it. What a frozen file protects against — a
    reference that silently changes — does not apply to a solver whose accuracy
    is set by an explicit tolerance argument.

    The reference implementation for ``perturbations.py`` will be this same
    integrator with the zonal terms switched on; that module is where it becomes
    a shared fixture rather than a local helper.
    """

    @staticmethod
    def _integrate(
        r0_km: np.ndarray, v0_km_s: np.ndarray, t_s: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Integrate the two-body equation of motion and sample it on ``t_s``."""

        def acceleration(_t: float, state: np.ndarray) -> np.ndarray:
            position = state[:3]
            radius = float(np.linalg.norm(position))
            return np.concatenate([state[3:], -EGM96_MU_KM3_S2 * position / radius**3])

        solution = solve_ivp(
            acceleration,
            (0.0, float(t_s[-1])),
            np.concatenate([r0_km, v0_km_s]),
            method="DOP853",
            t_eval=t_s,
            rtol=1e-13,
            atol=1e-12,
        )
        assert solution.success, solution.message
        return solution.y[:3].T, solution.y[3:].T

    @staticmethod
    def _propagate_analytically(
        r0_km: np.ndarray, v0_km_s: np.ndarray, t_s: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Propagate the same state through the closed-form Kepler chain."""
        coe = rv_to_coe(np.array([r0_km]), np.array([v0_km_s]))
        ecc = np.asarray(coe.eccentricity)
        mean0 = mean_from_true_anomaly(np.asarray(coe.true_anomaly_rad), ecc)
        motion = mean_motion_rad_s(coe.semi_major_axis_km)
        mean = advance_mean_anomaly(mean0, motion, t_s)
        stepped = ClassicalElements(
            semi_latus_rectum_km=coe.semi_latus_rectum_km,
            eccentricity=ecc,
            inclination_rad=coe.inclination_rad,
            raan_rad=coe.raan_rad,
            argp_rad=coe.argp_rad,
            true_anomaly_rad=true_from_mean_anomaly(mean, ecc),
        )
        return coe_to_rv(stepped)

    @pytest.mark.parametrize(
        ("name", "elements"),
        [
            ("leo near-circular", (6878.0, 0.001, 51.6, 10.0, 25.0, 12.0)),
            ("sso", (7078.0, 0.0012, 98.2, 120.0, 90.0, 300.0)),
            ("molniya-like", (11_067.79, 0.72, 63.4, 227.9, 270.0, 40.0)),
            ("geo", (42_164.0, 0.0002, 0.5, 45.0, 120.0, 200.0)),
            ("retrograde", (8000.0, 0.15, 120.0, 190.0, 33.0, 179.0)),
        ],
    )
    def test_matches_a_numerical_two_body_propagation(
        self, name: str, elements: tuple[float, ...]
    ) -> None:
        """One full revolution, sampled 25 times, compared position and velocity.

        The bound is 1 m and 1 mm/s. The integrator is run at rtol 1e-13, which
        over one LEO revolution accumulates well under a millimetre, so a metre
        is roughly a thousand-fold margin over the oracle's own error — loose
        enough that no SciPy version will move it, tight enough that a sign error
        anywhere in the chain is thousands of kilometres out.
        """
        coe = _elements_from_degrees(*elements)
        r0_km, v0_km_s = coe_to_rv(coe)
        period = float(orbital_period_s(coe.semi_major_axis_km)[0])
        t_s = np.linspace(0.0, period, 25)

        r_numeric, v_numeric = self._integrate(r0_km[0], v0_km_s[0], t_s)
        r_analytic, v_analytic = self._propagate_analytically(r0_km[0], v0_km_s[0], t_s)

        assert np.max(np.abs(r_analytic - r_numeric)) < 1e-3, name
        assert np.max(np.abs(v_analytic - v_numeric)) < 1e-6, name

    def test_the_orbit_closes_after_one_period(self) -> None:
        """A pure invariant, and the cheapest check that the period is right.

        If the period were wrong by a part in 1e6, a LEO satellite would be 7 m
        off after one revolution and hundreds of metres off after a day.
        """
        coe = _elements_from_degrees(6878.0, 0.001, 51.6, 10.0, 25.0, 12.0)
        r0_km, v0_km_s = coe_to_rv(coe)
        period = float(orbital_period_s(coe.semi_major_axis_km)[0])
        r_end, v_end = self._propagate_analytically(r0_km[0], v0_km_s[0], np.array([0.0, period]))
        assert np.max(np.abs(r_end[1] - r0_km[0])) < 1e-9
        assert np.max(np.abs(v_end[1] - v0_km_s[0])) < 1e-12

    @given(
        altitude_km=st.floats(min_value=300.0, max_value=1500.0),
        eccentricity=st.floats(min_value=0.0, max_value=0.2),
        inclination_deg=st.floats(min_value=0.0, max_value=180.0),
    )
    @settings(max_examples=15, deadline=None, suppress_health_check=[HealthCheck.too_slow])
    def test_matches_numerically_over_random_leo_orbits(
        self, altitude_km: float, eccentricity: float, inclination_deg: float
    ) -> None:
        """The same comparison, over orbits nobody chose by hand.

        Fifteen examples only: each one runs a stiff-tolerance integration, and
        the parametrised cases above already cover the interesting corners. This
        exists to catch a regime between them, not to be the primary check.
        """
        axis_km = WGS84_RADIUS_EQUATORIAL_KM + altitude_km
        assume(axis_km * (1.0 - eccentricity) > WGS84_RADIUS_EQUATORIAL_KM + 200.0)
        coe = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=axis_km,
            eccentricity=eccentricity,
            inclination_rad=math.radians(inclination_deg),
            raan_rad=0.9,
            argp_rad=2.1,
            true_anomaly_rad=0.3,
        )
        r0_km, v0_km_s = coe_to_rv(coe)
        t_s = np.linspace(0.0, float(orbital_period_s(axis_km)[0]), 9)
        r_numeric, _ = self._integrate(r0_km[0], v0_km_s[0], t_s)
        r_analytic, _ = self._propagate_analytically(r0_km[0], v0_km_s[0], t_s)
        assert np.max(np.abs(r_analytic - r_numeric)) < 1e-3


@pytest.mark.physics
class TestVectorisation:
    """The array contract: shapes in, shapes out, no scalar entry point."""

    def test_a_thousand_orbits_at_once(self) -> None:
        rng = np.random.default_rng(20_260_801)
        count = 1000
        coe = ClassicalElements(
            semi_latus_rectum_km=rng.uniform(6800.0, 42_000.0, count),
            eccentricity=rng.uniform(0.0, 0.7, count),
            inclination_rad=rng.uniform(0.0, math.pi, count),
            raan_rad=rng.uniform(0.0, 2.0 * math.pi, count),
            argp_rad=rng.uniform(0.0, 2.0 * math.pi, count),
            true_anomaly_rad=rng.uniform(0.0, 2.0 * math.pi, count),
        )
        r_km, v_km_s = coe_to_rv(coe)
        assert r_km.shape == (count, 3)
        assert v_km_s.shape == (count, 3)
        r_back, v_back = coe_to_rv(rv_to_coe(r_km, v_km_s))
        assert np.max(np.abs(r_back - r_km)) < 1e-7
        assert np.max(np.abs(v_back - v_km_s)) < 1e-10

    def test_a_bare_three_vector_is_promoted(self) -> None:
        coe = rv_to_coe(np.array(VALLADO_2_5_R_IJK_KM), np.array(VALLADO_2_5_V_IJK_KM_S))
        assert coe.n == 1

    def test_scalar_fields_broadcast_against_array_ones(self) -> None:
        coe = ClassicalElements(
            semi_latus_rectum_km=7000.0,
            eccentricity=0.01,
            inclination_rad=1.0,
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=np.linspace(0.0, 6.0, 32),
        )
        assert coe.n == 32
        assert np.asarray(coe.semi_latus_rectum_km).shape == (32,)

    def test_mismatched_field_lengths_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="neither 1 nor"):
            ClassicalElements(
                semi_latus_rectum_km=np.zeros(4) + 7000.0,
                eccentricity=np.zeros(3),
                inclination_rad=0.0,
                raan_rad=0.0,
                argp_rad=0.0,
                true_anomaly_rad=0.0,
            )


@pytest.mark.physics
class TestNoSilentDegradation:
    """Nothing here records a degradation, and that is a decision, not an oversight.

    Per ``docs/adr/0002-frames-and-time-scales.md``: a physics function takes a
    :class:`~quoss.core.errors.DegradationLog` only if it can decide at runtime
    to compute something other than what its name promises. The degenerate-angle
    folding does not qualify — the state it produces is exact — so no signature
    in this module accepts one.
    """

    def test_no_public_function_takes_a_log(self) -> None:
        import inspect

        for name in kepler_module.__all__:
            member: Any = getattr(kepler_module, name)
            if not inspect.isfunction(member):
                continue
            parameters = inspect.signature(member).parameters
            assert "log" not in parameters, name
            assert not any("degrad" in p.lower() for p in parameters), name
