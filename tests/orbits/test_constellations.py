"""Tests for `quoss.orbits.constellations`.

Organised by verification level, per `tests/golden/README.md`:

* ``TestWalkerDeltaInvariants`` / ``TestPhasingDirectionAgreesWithConvention`` /
  ``TestWalkerDeltaRejects`` — **V1**. No published, page-cited Walker-pattern
  worked example (in the style of the Vallado transcriptions in
  ``test_kepler.py``) was found with enough confidence to transcribe as V2 —
  see ``notes/LAST_CHANGES.md`` for what was searched and why nothing is
  asserted from it. Correctness instead rests on exact invariants (RAAN
  spacing, mean-anomaly spacing, total count, the direction of the phasing
  offset) plus independent agreement with how the pattern is documented
  elsewhere (MATLAB's Aerospace Toolbox ``walkerDelta``, Wikipedia's
  "Satellite constellation" article) — informational corroboration, not a
  frozen V3 oracle.
* ``TestSunSynchronousClosedForm`` — **V1, and one number that traces to an
  existing V1 example**: :func:`~quoss.orbits.perturbations.secular_rates_j2`'s
  own docstring states that ``a=7078.137 km, e=0.001, i=98.19 deg`` gives
  ``0.9859 deg/day``. Inverting the same ``a``, ``e`` here must recover
  ``i ~ 98.19 deg`` to the two-decimal precision that number was stated at,
  and feeding the recovered inclination back through ``secular_rates_j2``
  must reproduce the sun-synchronous rate to machine precision — both
  directions are the same closed-form algebra, so this is an unusually strong
  round trip, not merely "close".
* ``TestRepeatGroundTrackResonance`` — **V1**: solve for ``a``, then check the
  resonance condition the solver was built to satisfy actually holds, to a
  tolerance derived from how tightly ``brentq`` was asked to converge (not
  from what today's answer happens to be).
* ``TestRepeatGroundTrackConvergenceError`` — **V1**: a case chosen so the
  5 %-wide search bracket provably does not contain the root (extreme
  eccentricity blows up the J2 term far past what a two-body estimate
  anticipates), and the function must say so rather than hand back a number
  from outside the bracket it claims to have searched.
* ``TestRepeatGroundTrackAgainstLandsat8`` — **informational, explicitly not
  V2**: Landsat-8's published WRS-2 parameters (233 orbits / 16 days,
  98.2 deg, ~705 km) give a plausibility check, and the gap between the
  published altitude and what this solver returns is measured and reported
  honestly rather than rounded away — see the class docstring for why it is
  *not* claimed as validation.
"""

from collections.abc import Callable

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quoss.core.constants import (
    EARTH_ROTATION_RAD_S,
    EGM96_J2,
    EGM96_MU_KM3_S2,
    EGM96_RADIUS_EQUATORIAL_KM,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.orbits import constellations
from quoss.orbits.constellations import (
    SUN_SYNCHRONOUS_RAAN_RATE_RAD_S,
    repeat_ground_track_semi_major_axis_km,
    sun_synchronous_inclination_rad,
    walker_delta,
)
from quoss.orbits.constellations import (
    _resonance_residual_rad_s as resonance_residual_rad_s,
)
from quoss.orbits.frames import Frame
from quoss.orbits.kepler import (
    ClassicalElements,
    ElementType,
    mean_from_true_anomaly,
    semi_major_axis_from_period_km,
)
from quoss.orbits.perturbations import secular_rates_j2

LEO_SEMI_MAJOR_AXIS_KM = EGM96_RADIUS_EQUATORIAL_KM + 700.0


# --------------------------------------------------------------------------- #
# Walker-Delta
# --------------------------------------------------------------------------- #
class TestWalkerDeltaInvariants:
    """Properties the layout must have regardless of which pattern is asked for.

    These do not depend on any external reference — they follow from what
    "evenly spaced in P planes" and "evenly spaced within a plane" mean — which
    is exactly why they can carry the module's correctness in the absence of a
    citable worked example (see the module docstring above).
    """

    @pytest.mark.parametrize(
        ("total", "planes", "phasing"),
        [(1, 1, 0), (6, 3, 1), (24, 6, 2), (24, 3, 0), (60, 5, 4), (2, 2, 1)],
    )
    def test_returns_exactly_t_satellites(self, total: int, planes: int, phasing: int) -> None:
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=total,
            planes=planes,
            phasing_factor=phasing,
        )
        assert coe.n == total
        assert len(coe) == total

    @pytest.mark.parametrize(("total", "planes"), [(6, 3), (24, 6), (60, 5), (12, 4)])
    def test_raan_spacing_is_exactly_360_over_p(self, total: int, planes: int) -> None:
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=total,
            planes=planes,
            phasing_factor=0,
        )
        per_plane = total // planes
        # Plane-major ordering: entries [0, per_plane, 2*per_plane, ...] are the
        # first satellite of each plane in turn.
        raan_per_plane = coe.raan_rad[::per_plane]
        expected_step = 2.0 * np.pi / planes
        steps = np.diff(raan_per_plane)
        assert steps == pytest.approx(expected_step, abs=1e-13)

    @pytest.mark.parametrize("eccentricity", [0.0, 0.3])
    def test_mean_anomaly_spacing_within_plane_is_exact(self, eccentricity: float) -> None:
        """Within one plane, consecutive slots are exactly ``2 pi / (T/P)`` apart.

        Checked in *mean* anomaly, recovered from the stored true anomaly via
        :func:`~quoss.orbits.kepler.mean_from_true_anomaly` — the module
        docstring's "why mean anomaly" argument only has teeth if this actually
        holds once ``eccentricity`` is not zero, where true-anomaly spacing
        would *not* be exact.
        """
        total, planes = 12, 3
        per_plane = total // planes
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=eccentricity,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=total,
            planes=planes,
            phasing_factor=1,
        )
        mean_anomaly = mean_from_true_anomaly(coe.true_anomaly_rad, coe.eccentricity)
        # First plane's slots are entries [0, per_plane).
        first_plane = np.unwrap(mean_anomaly[:per_plane])
        steps = np.diff(first_plane)
        assert steps == pytest.approx(2.0 * np.pi / per_plane, abs=1e-12)

    def test_true_anomaly_spacing_is_not_exact_once_eccentric(self) -> None:
        """The negative control for the test above.

        If spacing in *true* anomaly were also exact for an eccentric orbit,
        the "why mean anomaly and not true anomaly" argument in the module
        docstring would be decorative rather than load-bearing. It is not:
        true-anomaly steps within a plane visibly differ from each other once
        ``e`` is not tiny.
        """
        total, planes, eccentricity = 12, 3, 0.3
        per_plane = total // planes
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=eccentricity,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=total,
            planes=planes,
            phasing_factor=1,
        )
        first_plane = np.unwrap(coe.true_anomaly_rad[:per_plane])
        steps = np.diff(first_plane)
        assert not np.allclose(steps, steps[0], atol=1e-6)

    def test_element_type_and_frame_pass_through(self) -> None:
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.001,
            inclination_rad=np.deg2rad(98.19),
            total_satellites=6,
            planes=2,
            phasing_factor=1,
            frame=Frame.GCRF,
            element_type=ElementType.MEAN_BROUWER,
        )
        assert coe.frame is Frame.GCRF
        assert coe.element_type is ElementType.MEAN_BROUWER

    def test_defaults_to_osculating_like_from_semi_major_axis(self) -> None:
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=4,
            planes=2,
            phasing_factor=1,
        )
        assert coe.element_type is ElementType.OSCULATING


class TestPhasingDirectionAgreesWithConvention:
    """The sign that is easy to get backwards, pinned down by hand and by formula.

    Direction is fixed by the standard Walker convention [1]_: the phase offset
    of plane ``p`` relative to plane 0 is ``+p * F * 360/T``, in the *same*
    sense RAAN increases with plane index. Reproduced independently by
    MATLAB's Aerospace Toolbox documentation for ``walkerDelta``, which states
    the between-plane step as exactly ``F * 360 / T`` degrees.
    """

    def test_six_six_three_one_by_hand(self) -> None:
        """``6:6/3/1``: RAAN steps 120 deg/plane, in-plane 180 deg, phase 60 deg/plane.

        Worked by hand: plane 0 = [0, 180], plane 1 = [60, 240] (=[0,180]+60),
        plane 2 = [120, 300] (=[0,180]+120). If the sign of the phasing term
        were flipped, plane 1 would read [-60, 120] = [300, 120] instead.
        """
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=6,
            planes=3,
            phasing_factor=1,
        )
        expected_raan_deg = [0.0, 0.0, 120.0, 120.0, 240.0, 240.0]
        expected_true_anomaly_deg = [0.0, 180.0, 60.0, 240.0, 120.0, 300.0]
        assert np.rad2deg(coe.raan_rad) == pytest.approx(expected_raan_deg, abs=1e-9)
        assert np.rad2deg(coe.true_anomaly_rad) == pytest.approx(
            expected_true_anomaly_deg, abs=1e-9
        )

    @pytest.mark.parametrize(
        ("total", "planes", "phasing"), [(24, 6, 1), (24, 3, 2), (60, 5, 3), (8, 4, 3)]
    )
    def test_phase_offset_between_planes_is_exactly_f_times_360_over_t(
        self, total: int, planes: int, phasing: int
    ) -> None:
        """Directly checks the formula, not just one worked instance of it."""
        per_plane = total // planes
        coe = walker_delta(
            semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
            eccentricity=0.0,
            inclination_rad=np.deg2rad(53.0),
            total_satellites=total,
            planes=planes,
            phasing_factor=phasing,
        )
        # Slot 0 of every plane: entries [0, per_plane, 2*per_plane, ...].
        slot_zero_true_anomaly = coe.true_anomaly_rad[::per_plane]
        expected_step = np.mod(phasing * 2.0 * np.pi / total, 2.0 * np.pi)
        for plane_index in range(1, planes):
            observed_step = np.mod(
                slot_zero_true_anomaly[plane_index] - slot_zero_true_anomaly[0], 2.0 * np.pi
            )
            assert observed_step == pytest.approx(
                np.mod(plane_index * expected_step, 2.0 * np.pi), abs=1e-9
            )


class TestWalkerDeltaRejects:
    def test_total_not_a_multiple_of_planes(self) -> None:
        with pytest.raises(DomainError, match="multiple"):
            walker_delta(
                semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
                eccentricity=0.0,
                inclination_rad=1.0,
                total_satellites=10,
                planes=3,
                phasing_factor=0,
            )

    @pytest.mark.parametrize("phasing", [-1, 3, 4])
    def test_phasing_factor_out_of_range(self, phasing: int) -> None:
        with pytest.raises(DomainError, match="phasing_factor"):
            walker_delta(
                semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
                eccentricity=0.0,
                inclination_rad=1.0,
                total_satellites=9,
                planes=3,
                phasing_factor=phasing,
            )

    def test_phasing_factor_not_an_integer(self) -> None:
        with pytest.raises(DomainError, match="integer"):
            walker_delta(
                semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
                eccentricity=0.0,
                inclination_rad=1.0,
                total_satellites=9,
                planes=3,
                phasing_factor=1.5,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(("total", "planes"), [(0, 3), (-6, 3), (6, 0), (6, -3)])
    def test_non_positive_total_or_planes(self, total: int, planes: int) -> None:
        with pytest.raises(DomainError):
            walker_delta(
                semi_major_axis_km=LEO_SEMI_MAJOR_AXIS_KM,
                eccentricity=0.0,
                inclination_rad=1.0,
                total_satellites=total,
                planes=planes,
                phasing_factor=0,
            )


# --------------------------------------------------------------------------- #
# Sun-synchronous inclination
# --------------------------------------------------------------------------- #
class TestSunSynchronousClosedForm:
    def test_recovers_the_secular_rates_j2_docstring_example(self) -> None:
        """``a=7078.137, e=0.001`` recovers ``i ~ 98.19 deg``.

        98.19 deg is the value ``secular_rates_j2``'s own docstring states
        (giving ``0.9859 deg/day``, close to but not exactly the sun-synchronous
        rate of ``0.98565 deg/day``, since 98.19 was quoted to a hundredth of a
        degree rather than derived from this formula). Recovered here to that
        same two-decimal precision.
        """
        inc = sun_synchronous_inclination_rad(7078.137, 0.001)
        assert float(np.round(np.rad2deg(inc[0]), 2)) == pytest.approx(98.19)

    def test_round_trip_through_secular_rates_j2_is_exact(self) -> None:
        """Feeding the result back in reproduces the target rate to ~machine eps.

        Not "close": both directions solve the same equation
        (``secular_rates_j2``'s ``raan_dot`` formula), one for ``i`` given the
        rate and one for the rate given ``i``, so nothing here is expected to
        leave a residual bigger than float64 rounding.
        """
        axis_km, ecc = 7078.137, 0.001
        inc = sun_synchronous_inclination_rad(axis_km, ecc)
        sso = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=axis_km,
            eccentricity=ecc,
            inclination_rad=float(inc[0]),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
            element_type=ElementType.MEAN_BROUWER,
        )
        recovered = float(secular_rates_j2(sso).raan_rad_s[0])
        assert recovered == pytest.approx(SUN_SYNCHRONOUS_RAAN_RATE_RAD_S, rel=0.0, abs=1e-17)

    @settings(max_examples=100, deadline=None)
    @given(
        axis_km=st.floats(min_value=6500.0, max_value=12_000.0, allow_nan=False),
        ecc=st.floats(min_value=0.0, max_value=0.05, allow_nan=False),
    )
    def test_round_trip_holds_across_the_feasible_range(self, axis_km: float, ecc: float) -> None:
        inc = sun_synchronous_inclination_rad(axis_km, ecc)
        sso = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=axis_km,
            eccentricity=ecc,
            inclination_rad=float(inc[0]),
            raan_rad=0.0,
            argp_rad=0.0,
            true_anomaly_rad=0.0,
            element_type=ElementType.MEAN_BROUWER,
        )
        recovered = float(secular_rates_j2(sso).raan_rad_s[0])
        assert recovered == pytest.approx(SUN_SYNCHRONOUS_RAAN_RATE_RAD_S, rel=1e-10)

    def test_prograde_regime_and_too_high_altitude_have_no_solution(self) -> None:
        """Above ~6000 km altitude, J2's node-drag cannot reach the sun-sync rate."""
        with pytest.raises(DomainError, match="No inclination"):
            sun_synchronous_inclination_rad(20_000.0, 0.0)

    def test_result_is_always_retrograde(self) -> None:
        for axis_km in (6600.0, 7000.0, 8000.0, 10_000.0):
            inc = sun_synchronous_inclination_rad(axis_km, 0.001)
            assert np.pi / 2.0 < float(inc[0]) <= np.pi

    def test_vectorises_and_broadcasts(self) -> None:
        axis_km = np.array([6900.0, 7078.137, 7500.0])
        inc = sun_synchronous_inclination_rad(axis_km, 0.001)
        assert inc.shape == (3,)
        inc_scalar_ecc = sun_synchronous_inclination_rad(axis_km, 0.0)
        assert inc_scalar_ecc.shape == (3,)

    def test_rejects_bad_inputs(self) -> None:
        with pytest.raises(DomainError):
            sun_synchronous_inclination_rad(-100.0, 0.0)
        with pytest.raises(DomainError):
            sun_synchronous_inclination_rad(7000.0, 1.0)
        with pytest.raises(DomainError):
            sun_synchronous_inclination_rad(7000.0, -0.1)

    def test_rejects_bad_gravity_parameters(self) -> None:
        with pytest.raises(DomainError, match="mu_km3_s2"):
            sun_synchronous_inclination_rad(7000.0, 0.0, mu_km3_s2=-1.0)
        with pytest.raises(DomainError, match="r_equatorial_km"):
            sun_synchronous_inclination_rad(7000.0, 0.0, r_equatorial_km=float("nan"))
        with pytest.raises(DomainError, match="j2"):
            sun_synchronous_inclination_rad(7000.0, 0.0, j2=float("inf"))

    def test_rejects_mismatched_lengths(self) -> None:
        """Two arrays that are neither length 1 nor equal cannot broadcast."""
        with pytest.raises(DomainError, match="neither 1 nor"):
            sun_synchronous_inclination_rad(
                np.array([7000.0, 7100.0, 7200.0]), np.array([0.001, 0.002])
            )


# --------------------------------------------------------------------------- #
# Repeat ground track
# --------------------------------------------------------------------------- #
class TestRepeatGroundTrackResonance:
    """The solver's own postcondition, checked rather than assumed.

    The tolerance is not picked to match today's number: it is derived from
    the root-finder's own ``xtol`` (a millimetre in ``a``) propagated through
    how sensitive the resonance residual is to ``a`` — measured, for every
    case below, at 12+ orders of magnitude below the ~1e-3 to 1e-2 rad/s scale
    of the two rates being balanced.
    """

    @pytest.mark.parametrize(
        ("orbits", "days", "inc_deg", "ecc"),
        [
            (233, 16, 98.2, 0.0001),
            (14, 1, 51.6, 0.001),
            (15, 1, 97.4, 0.0),
            (43, 3, 98.6, 0.01),
        ],
    )
    def test_resonance_condition_is_satisfied(
        self, orbits: int, days: int, inc_deg: float, ecc: float
    ) -> None:
        inc = np.deg2rad(inc_deg)
        axis_km = float(repeat_ground_track_semi_major_axis_km(orbits, days, inc, ecc)[0])
        residual = resonance_residual_rad_s(
            axis_km, ecc, inc, EGM96_MU_KM3_S2, EGM96_RADIUS_EQUATORIAL_KM, EGM96_J2, orbits, days
        )
        assert residual == pytest.approx(0.0, abs=1e-10)

    @pytest.mark.parametrize(("orbits", "days"), [(233, 16), (14, 1), (43, 3), (15, 1)])
    def test_reduces_to_the_two_body_closed_form_when_j2_is_zero(
        self, orbits: int, days: int
    ) -> None:
        """The self-consistency check the bracket's own docstring promises.

        With ``j2=0`` the resonance condition *is* the two-body one used to
        build the search bracket, so the solved ``a`` must equal
        :func:`~quoss.orbits.kepler.semi_major_axis_from_period_km` applied to
        ``2 pi days / (orbits * omega_earth)`` — not approximately, to the
        solver's own ``xtol``.
        """
        inc = np.deg2rad(97.0)
        period_s = 2.0 * np.pi * days / (orbits * EARTH_ROTATION_RAD_S)
        expected = float(semi_major_axis_from_period_km(np.array([period_s]))[0])
        solved = float(repeat_ground_track_semi_major_axis_km(orbits, days, inc, 0.0, j2=0.0)[0])
        assert solved == pytest.approx(expected, abs=1e-6)

    def test_vectorises_over_inclination_and_eccentricity(self) -> None:
        inc = np.deg2rad(np.array([97.0, 98.2, 51.6]))
        ecc = np.array([0.0, 0.0001, 0.001])
        axis_km = repeat_ground_track_semi_major_axis_km(14, 1, inc, ecc)
        assert axis_km.shape == (3,)
        for idx in range(3):
            residual = resonance_residual_rad_s(
                float(axis_km[idx]),
                float(ecc[idx]),
                float(inc[idx]),
                EGM96_MU_KM3_S2,
                EGM96_RADIUS_EQUATORIAL_KM,
                EGM96_J2,
                14,
                1,
            )
            assert residual == pytest.approx(0.0, abs=1e-10)

    def test_rejects_non_positive_or_non_integer_cycle_counts(self) -> None:
        with pytest.raises(DomainError):
            repeat_ground_track_semi_major_axis_km(0, 16, 1.0, 0.0)
        with pytest.raises(DomainError):
            repeat_ground_track_semi_major_axis_km(233, -16, 1.0, 0.0)
        with pytest.raises(DomainError):
            repeat_ground_track_semi_major_axis_km(233.5, 16, 1.0, 0.0)  # type: ignore[arg-type]

    def test_rejects_bad_eccentricity(self) -> None:
        with pytest.raises(DomainError, match="eccentricity"):
            repeat_ground_track_semi_major_axis_km(233, 16, 1.0, 1.0)
        with pytest.raises(DomainError, match="eccentricity"):
            repeat_ground_track_semi_major_axis_km(233, 16, 1.0, -0.1)


class TestRepeatGroundTrackConvergenceError:
    """A case built to provably fall outside the 5 % two-body bracket.

    The two-body estimate ignores J2 (and therefore ``e`` and ``i``)
    entirely. At high eccentricity the J2 term is inflated by ``(R/p)^2``,
    ``p = a(1-e^2)`` — so a high enough ``e`` makes the true root fall outside
    any bracket built only from the two-body period. ``orbits=16, days=1,
    i=63.4 deg, e=0.9`` was found by direct search to leave the resonance
    residual the *same sign* at both ends of the 5 % bracket (measured:
    +3.27e-4 rad/s at the low end, +3.78e-4 rad/s at the high end — both
    positive, so ``brentq`` has nothing to bisect). This is not a defect to
    work around by widening the bracket further: it is the solver correctly
    refusing to claim a root it has not actually located.
    """

    def test_raises_convergence_error_with_no_sign_change(self) -> None:
        with pytest.raises(ConvergenceError, match="sign change"):
            repeat_ground_track_semi_major_axis_km(16, 1, np.deg2rad(63.4), 0.9)


class TestTheBracketEndThatIsAlreadyTheRoot:
    """What happens when the residual is *exactly* zero at an end of the bracket.

    ``brentq`` locates a root strictly inside a bracket whose ends have opposite
    signs. An exact zero at an end has neither: ``(f_lo > 0) == (f_hi > 0)``
    would be true for ``f_lo = 0`` and any positive ``f_hi``, so without these
    two guards the solver would raise "no sign change" while standing on the
    answer. It is a guard against a boundary, not against a physical case — the
    residual is a difference of two irrational-looking rates and will not be
    bit-exactly zero on any real orbit — so the residual is stubbed rather than
    a semi-major axis hunted for.

    The two ends are separate tests because they are separate branches, and a
    guard that only worked at one end would pass a test that checked one.
    """

    @staticmethod
    def zero_at(target_km: float) -> Callable[..., float]:
        """Return a residual that vanishes exactly at ``target_km`` and is positive elsewhere."""

        def residual(a_km: float, *args: object, **kwargs: object) -> float:
            del args, kwargs
            return 0.0 if a_km == target_km else 1.0

        return residual

    def brackets(self) -> tuple[float, float]:
        """Return the two bracket ends the solver builds for the Landsat cycle."""
        period_s = 2.0 * np.pi / (233.0 / 16.0 * EARTH_ROTATION_RAD_S)
        axis_km = float(semi_major_axis_from_period_km(np.array([period_s]))[0])
        return (
            axis_km * (1.0 - constellations._BRACKET_RELATIVE_HALF_WIDTH),
            axis_km * (1.0 + constellations._BRACKET_RELATIVE_HALF_WIDTH),
        )

    def test_a_root_at_the_low_end_is_returned_and_not_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        lo_km, _ = self.brackets()
        monkeypatch.setattr(constellations, "_resonance_residual_rad_s", self.zero_at(lo_km))
        solved = repeat_ground_track_semi_major_axis_km(233, 16, np.deg2rad(98.2), 0.0)
        assert float(solved[0]) == lo_km

    def test_a_root_at_the_high_end_is_returned_and_not_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _, hi_km = self.brackets()
        monkeypatch.setattr(constellations, "_resonance_residual_rad_s", self.zero_at(hi_km))
        solved = repeat_ground_track_semi_major_axis_km(233, 16, np.deg2rad(98.2), 0.0)
        assert float(solved[0]) == hi_km


class TestRepeatGroundTrackAgainstLandsat8:
    """Landsat-8's WRS-2 grid, as a plausibility check — explicitly not V2.

    Landsat-8 flies a 705 km sun-synchronous orbit at 98.2 deg, repeating its
    ground track every 233 orbits / 16 days (NASA/USGS mission specification;
    the same source already used for the sun-synchronous check in
    ``test_perturbations.py::TestPublishedSunSynchronous``).

    This is **not** treated as V2: ``tests/golden/README.md`` requires a V2
    number to be a value a reader can check against a citable source, and
    "705 km" is a rounded, nominal mission figure, not a semi-major axis
    stated to a precision this first-order theory could be held to. Measured
    here: the solver returns an altitude of ~699.6 km, **5.4 km (0.08 %) below**
    the published figure. That gap is *not* explained by the published
    precision of the inclination (a +-0.05 deg window around 98.2 deg moves
    the solved altitude by only ~0.08 km, measured by direct search) or of the
    eccentricity (~0.00002 km for a spread of 0.001 in ``e``) — so it most
    likely reflects real-world effects this first-order, J2-only theory does
    not model (drag makeup manoeuvres, J4/J2^2, or "705 km" simply being a
    round nominal number rather than a precise element). The test below
    checks plausibility at the percent level, not agreement, and this
    docstring is where the honest gap is recorded rather than in a comment
    that could go stale.
    """

    def test_within_a_percent_of_the_published_altitude(self) -> None:
        axis_km = float(
            repeat_ground_track_semi_major_axis_km(233, 16, np.deg2rad(98.2), 0.0001)[0]
        )
        altitude_km = axis_km - EGM96_RADIUS_EQUATORIAL_KM
        assert altitude_km == pytest.approx(705.0, abs=10.0)
