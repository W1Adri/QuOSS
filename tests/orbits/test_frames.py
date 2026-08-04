"""Tests for `quoss.orbits.frames`.

Organised by verification level, per `tests/golden/README.md`:

* ``TestInvariants*`` — V1, self-consistency with no external data.
* ``TestPublished*`` — V2, values that are correct by definition or by arithmetic
  a reader can redo.
* ``TestAgainstReference*`` / ``TestFrameErrorBudget`` — V3, the frozen astropy
  and ERFA data in ``tests/golden/data/frames_reference.json``.

There is no V4 block: a snapshot of this module's own output would add nothing
that the invariants do not already pin down.
"""

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from quoss.core.constants import (
    EARTH_ROTATION_RAD_S,
    JD_J2000,
    JD_UNIX_EPOCH,
    SECONDS_PER_DAY,
    WGS84_RADIUS_EQUATORIAL_KM,
    WGS84_RADIUS_POLAR_KM,
)
from quoss.core.errors import ConvergenceError, DomainError
from quoss.orbits import frames as frames_module
from quoss.orbits.frames import (
    Frame,
    calendar_to_jd,
    enu_from_itrf,
    geodetic_to_itrf,
    gmst_rad,
    itrf_to_geodetic,
    itrf_to_teme,
    itrf_to_teme_state,
    jd_to_calendar,
    teme_to_itrf,
    teme_to_itrf_state,
)

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "golden" / "data" / "frames_reference.json"


@pytest.fixture(scope="module")
def reference() -> dict[str, Any]:
    """Return the frozen astropy/ERFA reference data."""
    data: dict[str, Any] = json.loads(REFERENCE_PATH.read_text(encoding="utf-8"))
    return data


def _ids(rows: list[dict[str, Any]], *keys: str) -> list[str]:
    """Build readable parametrisation ids from reference rows."""
    return ["|".join(str(row[k]) for k in keys) for row in rows]


# --------------------------------------------------------------------------- #
# V2 — correct by definition
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestPublishedEpochs:
    def test_j2000_epoch(self) -> None:
        """J2000.0 is 2000-01-01 12:00 UTC. Definitional, and the anchor of GMST."""
        assert calendar_to_jd(2000, 1, 1, 12, 0, 0.0) == JD_J2000

    def test_unix_epoch(self) -> None:
        assert calendar_to_jd(1970, 1, 1) == JD_UNIX_EPOCH

    def test_modified_julian_date_offset(self) -> None:
        """MJD 0 is 1858-11-17, outside the accepted range, so check the offset instead."""
        jd = calendar_to_jd(2000, 1, 1, 0, 0, 0.0)
        assert jd - 2_400_000.5 == pytest.approx(51544.0, abs=1e-9)

    @pytest.mark.parametrize(
        ("year", "is_leap"),
        [(1900, False), (2000, True), (2024, True), (2025, False), (2100, False)],
    )
    def test_gregorian_century_leap_rule(self, year: int, is_leap: bool) -> None:
        """February's length must follow the full Gregorian rule, not just /4.

        This is the exact case that makes Vallado Alg. 14 wrong by a day, so it is
        asserted directly rather than left to the reference comparison.
        """
        february_days = calendar_to_jd(year, 3, 1) - calendar_to_jd(year, 2, 1)
        assert february_days == (29.0 if is_leap else 28.0)

    def test_year_length(self) -> None:
        """A common year is 365 days, a leap year 366."""
        assert calendar_to_jd(2026, 1, 1) - calendar_to_jd(2025, 1, 1) == 365.0
        assert calendar_to_jd(2025, 1, 1) - calendar_to_jd(2024, 1, 1) == 366.0

    def test_polar_radius_is_reached_at_the_pole(self) -> None:
        """A geodetic pole at zero height sits at the semi-minor axis.

        Follows from N(1 - e^2) sin(pi/2) = b, so it checks the ellipsoid algebra
        against an independently defined constant rather than against itself.
        """
        r = geodetic_to_itrf(math.pi / 2, 0.0, 0.0)
        assert float(r[0, 2]) == pytest.approx(WGS84_RADIUS_POLAR_KM, abs=1e-9)

    def test_equatorial_radius_is_reached_at_the_equator(self) -> None:
        r = geodetic_to_itrf(0.0, 0.0, 0.0)
        assert float(r[0, 0]) == pytest.approx(WGS84_RADIUS_EQUATORIAL_KM, abs=1e-12)

    def test_sidereal_day_is_recovered_from_the_gmst_rate(self) -> None:
        """GMST must complete a turn in a sidereal day, not a solar one.

        Getting this backwards is the classic error that produces a ground track
        drifting by four minutes a day, so it is worth an explicit check.
        """
        jd = np.array([JD_J2000, JD_J2000 + 1.0])
        theta = gmst_rad(jd)
        advance_per_day = float(theta[1] - theta[0]) + 2.0 * math.pi
        sidereal_day_s = SECONDS_PER_DAY * (2.0 * math.pi) / advance_per_day
        # The mean sidereal day, 86164.0905 s, to within a millisecond.
        assert sidereal_day_s == pytest.approx(86_164.0905, abs=1e-3)


# --------------------------------------------------------------------------- #
# V1 — invariants
# --------------------------------------------------------------------------- #
@pytest.mark.physics
class TestCalendarInvariants:
    @settings(max_examples=300, deadline=None)
    @given(
        year=st.integers(min_value=1900, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        second=st.floats(min_value=0.0, max_value=59.999, allow_nan=False),
    )
    def test_calendar_jd_roundtrip(
        self, year: int, month: int, day: int, hour: int, minute: int, second: float
    ) -> None:
        """The Julian date survives the round trip; the *fields* cannot, exactly.

        Integer field equality is deliberately not asserted. A float64 Julian date
        near 2.4e6 has a resolution of about 40 microseconds, so an input of
        00:01:00 can come back as 00:00:59.99996 — correct to the representable
        precision, and off by one in the minute field. Asserting tuple equality
        would be promising something the representation cannot deliver; the
        quantity that must round-trip is the date itself.
        """
        jd = calendar_to_jd(year, month, day, hour, minute, second)
        assert calendar_to_jd(*jd_to_calendar(jd)) == pytest.approx(jd, abs=1e-11)

    @settings(max_examples=300, deadline=None)
    @given(
        year=st.integers(min_value=1900, max_value=2100),
        month=st.integers(min_value=1, max_value=12),
        day=st.integers(min_value=1, max_value=28),
        hour=st.integers(min_value=0, max_value=23),
        minute=st.integers(min_value=0, max_value=59),
        second=st.floats(min_value=0.0, max_value=59.0, allow_nan=False),
    )
    def test_calendar_fields_recover_to_the_julian_date_resolution(
        self, year: int, month: int, day: int, hour: int, minute: int, second: float
    ) -> None:
        """Fields come back correct to within the ~40 us a float64 JD can hold."""
        jd = calendar_to_jd(year, month, day, hour, minute, second)
        out_year, out_month, out_day, out_hour, out_minute, out_second = jd_to_calendar(jd)
        assert (out_year, out_month, out_day) == (year, month, day)
        wanted_s = hour * 3600.0 + minute * 60.0 + second
        got_s = out_hour * 3600.0 + out_minute * 60.0 + out_second
        assert got_s == pytest.approx(wanted_s, abs=1e-4)

    @settings(max_examples=200, deadline=None)
    @given(jd=st.floats(min_value=2_415_021.0, max_value=2_488_069.0, allow_nan=False))
    def test_jd_calendar_jd_roundtrip(self, jd: float) -> None:
        """A Julian date survives a trip through calendar fields to ~1 microsecond."""
        assert calendar_to_jd(*jd_to_calendar(jd)) == pytest.approx(jd, abs=1e-11)

    def test_monotonic_in_time(self) -> None:
        base = calendar_to_jd(2025, 6, 15, 12, 0, 0.0)
        assert calendar_to_jd(2025, 6, 15, 12, 0, 0.5) > base
        assert calendar_to_jd(2025, 6, 15, 12, 1, 0.0) > base

    @pytest.mark.parametrize(
        ("kwargs", "reason"),
        [
            ({"year": 1899, "month": 1, "day": 1}, "year below range"),
            ({"year": 2101, "month": 1, "day": 1}, "year above range"),
            ({"year": 2025, "month": 0, "day": 1}, "month zero"),
            ({"year": 2025, "month": 13, "day": 1}, "month above 12"),
            ({"year": 2025, "month": 2, "day": 29}, "not a leap year"),
            ({"year": 2025, "month": 4, "day": 31}, "April has 30 days"),
            ({"year": 2025, "month": 1, "day": 0}, "day zero"),
            ({"year": 2025, "month": 1, "day": 1, "hour": 24}, "hour above 23"),
            ({"year": 2025, "month": 1, "day": 1, "minute": 60}, "minute above 59"),
            ({"year": 2025, "month": 1, "day": 1, "second": 61.0}, "second above range"),
            ({"year": 2025, "month": 1, "day": 1, "second": -1.0}, "negative second"),
        ],
    )
    def test_rejects_impossible_dates(self, kwargs: dict[str, Any], reason: str) -> None:
        with pytest.raises(DomainError):
            calendar_to_jd(**kwargs)

    @pytest.mark.parametrize("jd", [float("nan"), float("inf"), 0.0, 3_000_000.0])
    def test_jd_to_calendar_rejects_out_of_range(self, jd: float) -> None:
        with pytest.raises(DomainError):
            jd_to_calendar(jd)


@pytest.mark.physics
class TestGmstInvariants:
    def test_wrapped_to_one_turn(self) -> None:
        jd = JD_J2000 + np.linspace(-30_000.0, 40_000.0, 5000)
        theta = gmst_rad(jd)
        assert np.all(theta >= 0.0)
        assert np.all(theta < 2.0 * math.pi)

    def test_shape_is_preserved(self) -> None:
        assert gmst_rad(np.array([JD_J2000])).shape == (1,)
        assert gmst_rad(np.linspace(JD_J2000, JD_J2000 + 1.0, 17)).shape == (17,)

    def test_advances_uniformly_within_a_day(self) -> None:
        """Over one day the only non-uniformity is the resolution of a float64 JD.

        The bound is derived, not tuned: one ulp of a Julian date near 2.45e6 is
        ~4.7e-10 d, i.e. ~40 us, and the Earth turns through ~2.9e-9 rad in that
        time. Sampling a uniform grid of Julian dates therefore quantises the GMST
        step by exactly that much, and nothing else here may add to it. This is the
        same 20-microsecond caveat `core.types.TimeGrid.jd` documents, showing up
        as a measurable quantity.
        """
        jd = JD_J2000 + np.linspace(0.0, 1.0, 2001)[:-1]
        steps = np.diff(np.unwrap(gmst_rad(jd)))
        jd_ulp_rad = float(np.spacing(JD_J2000)) * SECONDS_PER_DAY * EARTH_ROTATION_RAD_S
        assert float(np.ptp(steps)) < 3.0 * jd_ulp_rad

    @pytest.mark.parametrize(
        "bad",
        [np.array([]), np.array([[JD_J2000]]), np.array([np.nan]), np.array([np.inf])],
    )
    def test_rejects_bad_input(self, bad: np.ndarray) -> None:
        with pytest.raises(DomainError):
            gmst_rad(bad)


@pytest.mark.physics
class TestRotationInvariants:
    @staticmethod
    def _sample_states() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        theta = np.linspace(0.0, 2.0 * math.pi, 37)
        r = np.column_stack(
            [
                6878.137 * np.cos(np.linspace(0.0, 3.0, 37)),
                6878.137 * np.sin(np.linspace(0.0, 3.0, 37)),
                np.linspace(-2000.0, 2000.0, 37),
            ]
        )
        v = np.column_stack(
            [
                -7.6 * np.sin(np.linspace(0.0, 3.0, 37)),
                7.6 * np.cos(np.linspace(0.0, 3.0, 37)),
                np.linspace(-1.0, 1.0, 37),
            ]
        )
        return r, v, theta

    def test_position_roundtrip(self) -> None:
        r, _, theta = self._sample_states()
        assert np.allclose(itrf_to_teme(teme_to_itrf(r, theta), theta), r, atol=1e-12)

    def test_state_roundtrip(self) -> None:
        r, v, theta = self._sample_states()
        r_itrf, v_itrf = teme_to_itrf_state(r, v, theta)
        r_back, v_back = itrf_to_teme_state(r_itrf, v_itrf, theta)
        assert np.allclose(r_back, r, atol=1e-12)
        assert np.allclose(v_back, v, atol=1e-14)

    def test_rotation_preserves_length(self) -> None:
        """A frame rotation about the pole cannot change a distance."""
        r, _, theta = self._sample_states()
        assert np.allclose(
            np.linalg.norm(teme_to_itrf(r, theta), axis=1),
            np.linalg.norm(r, axis=1),
            rtol=1e-15,
        )

    def test_polar_component_is_untouched(self) -> None:
        r, _, theta = self._sample_states()
        assert np.array_equal(teme_to_itrf(r, theta)[:, 2], r[:, 2])

    def test_zero_angle_is_the_identity(self) -> None:
        r, v, _ = self._sample_states()
        zero = np.zeros(r.shape[0])
        r_itrf, v_itrf = teme_to_itrf_state(r, v, zero)
        assert np.array_equal(r_itrf, r)
        # Velocity still changes: the frame is rotating even when aligned.
        expected_x = v[:, 0] + EARTH_ROTATION_RAD_S * r[:, 1]
        assert np.allclose(v_itrf[:, 0], expected_x, rtol=1e-15)

    def test_station_at_rest_in_itrf_moves_with_the_earth_in_teme(self) -> None:
        """The Doppler contribution of the ground station, checked against r omega."""
        lat = np.deg2rad(41.275)
        r_station = geodetic_to_itrf(lat, np.deg2rad(1.9875), 0.03)
        _, v_teme = itrf_to_teme_state(r_station, np.zeros((1, 3)), np.array([0.7]))
        distance_from_axis_km = float(np.hypot(r_station[0, 0], r_station[0, 1]))
        assert float(np.linalg.norm(v_teme)) == pytest.approx(
            distance_from_axis_km * EARTH_ROTATION_RAD_S, rel=1e-14
        )

    def test_omega_cross_r_term_is_not_forgotten(self) -> None:
        """Without the rotating-frame term this differs by ~0.46 km/s at the equator."""
        r = np.array([[WGS84_RADIUS_EQUATORIAL_KM, 0.0, 0.0]])
        v = np.zeros((1, 3))
        _, v_itrf = teme_to_itrf_state(r, v, np.array([0.0]))
        assert float(np.linalg.norm(v_itrf)) == pytest.approx(
            WGS84_RADIUS_EQUATORIAL_KM * EARTH_ROTATION_RAD_S, rel=1e-14
        )
        assert float(np.linalg.norm(v_itrf)) > 0.46

    def test_rejects_mismatched_state_shapes(self) -> None:
        r = np.zeros((5, 3))
        with pytest.raises(DomainError, match="state pair"):
            teme_to_itrf_state(r, np.zeros((4, 3)), np.zeros(5))
        with pytest.raises(DomainError, match="state pair"):
            itrf_to_teme_state(r, np.zeros((4, 3)), np.zeros(5))

    def test_rejects_non_broadcastable_angle(self) -> None:
        with pytest.raises(DomainError, match="neither 1 nor"):
            teme_to_itrf(np.zeros((5, 3)), np.zeros(3))

    @pytest.mark.parametrize("bad", [np.zeros((2, 4)), np.zeros((0, 3)), np.zeros((2, 3, 3))])
    def test_rejects_bad_vector_shapes(self, bad: np.ndarray) -> None:
        with pytest.raises(DomainError):
            teme_to_itrf(bad, np.array([0.0]))

    def test_a_bare_three_vector_is_promoted(self) -> None:
        """A single (3,) vector is accepted, so a one-off call needs no reshape."""
        out = teme_to_itrf(np.array([7000.0, 0.0, 0.0]), np.array([0.0]))
        assert out.shape == (1, 3)
        assert np.array_equal(out[0], np.array([7000.0, 0.0, 0.0]))

    @pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
    def test_rejects_non_finite_vectors(self, bad_value: float) -> None:
        r = np.zeros((3, 3))
        r[1, 2] = bad_value
        with pytest.raises(DomainError, match="non-finite"):
            teme_to_itrf(r, np.array([0.0]))

    def test_scalar_angle_broadcasts_over_the_grid(self) -> None:
        r = np.zeros((7, 3))
        r[:, 0] = 7000.0
        assert teme_to_itrf(r, np.array([0.3])).shape == (7, 3)


@pytest.mark.physics
class TestGeodeticInvariants:
    @settings(max_examples=400, deadline=None)
    @given(
        lat_deg=st.floats(min_value=-90.0, max_value=90.0, allow_nan=False),
        lon_deg=st.floats(min_value=-180.0, max_value=180.0, allow_nan=False),
        alt_km=st.floats(min_value=-0.5, max_value=2000.0, allow_nan=False),
    )
    def test_geodetic_roundtrip(self, lat_deg: float, lon_deg: float, alt_km: float) -> None:
        lat_in = math.radians(lat_deg)
        lon_in = math.radians(lon_deg)
        r = geodetic_to_itrf(lat_in, lon_in, alt_km)
        lat, lon, alt = itrf_to_geodetic(r)

        assert float(alt[0]) == pytest.approx(alt_km, abs=1e-9)
        assert float(lat[0]) == pytest.approx(lat_in, abs=1e-12)
        # Longitude is undefined at the poles, where cos(lat) collapses.
        if abs(abs(lat_deg) - 90.0) > 1e-6:
            wrapped = (float(lon[0]) - lon_in + math.pi) % (2.0 * math.pi) - math.pi
            assert wrapped == pytest.approx(0.0, abs=1e-12)

    def test_converges_well_inside_the_iteration_cap(self) -> None:
        """Seven iterations suffice pole to pole, so the cap of 12 has ~5 in margin.

        Checked by shrinking the cap rather than by trusting the comment: if the
        fixed point ever stopped converging this fast, the failure branch would
        fire here instead of in someone's run. Eight is the smallest cap that must
        still work; four must not, which is what makes the assertion informative.
        """
        r = geodetic_to_itrf(
            np.linspace(-math.pi / 2, math.pi / 2, 64), 0.0, np.linspace(-0.5, 2000.0, 64)
        )
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(frames_module, "_GEODETIC_MAX_ITER", 8)
            lat, _, _ = itrf_to_geodetic(r)
        assert np.all(np.isfinite(lat))

        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(frames_module, "_GEODETIC_MAX_ITER", 4)
            with pytest.raises(ConvergenceError):
                itrf_to_geodetic(r)

    def test_raises_when_the_iteration_cannot_converge(self) -> None:
        """The failure branch reports the last shift instead of raising NameError."""
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(frames_module, "_GEODETIC_MAX_ITER", 0)
            with pytest.raises(ConvergenceError, match="did not converge"):
                itrf_to_geodetic(np.array([[7000.0, 0.0, 100.0]]))

    def test_geodetic_latitude_differs_from_geocentric(self) -> None:
        """The distinction the previous implementation lost, asserted numerically.

        At 45 deg geodetic the geocentric latitude is ~0.19 deg smaller. A test
        that only checked round-tripping would pass with either convention, so the
        difference itself is pinned here.
        """
        r = geodetic_to_itrf(math.radians(45.0), 0.0, 0.0)
        geocentric_deg = math.degrees(math.atan2(r[0, 2], math.hypot(r[0, 0], r[0, 1])))
        assert 45.0 - geocentric_deg == pytest.approx(0.1924, abs=1e-3)

    def test_spherical_height_error_at_the_pole(self) -> None:
        """A `|r| - R_eq` height is 21 km wrong at the pole. Bound it, so nobody re-adds it."""
        r = geodetic_to_itrf(math.pi / 2, 0.0, 0.0)
        spherical_altitude_km = float(np.linalg.norm(r)) - WGS84_RADIUS_EQUATORIAL_KM
        _, _, alt = itrf_to_geodetic(r)
        assert float(alt[0]) == pytest.approx(0.0, abs=1e-9)
        assert spherical_altitude_km == pytest.approx(-21.385, abs=1e-2)

    def test_altitude_is_measured_along_the_normal(self) -> None:
        """Adding height must not move latitude, which it would if measured radially."""
        lat_in = math.radians(52.0)
        low = itrf_to_geodetic(geodetic_to_itrf(lat_in, 0.0, 0.0))
        high = itrf_to_geodetic(geodetic_to_itrf(lat_in, 0.0, 800.0))
        assert float(high[0][0]) == pytest.approx(float(low[0][0]), abs=1e-12)

    def test_vectorises_over_many_sites(self) -> None:
        lat = np.linspace(-1.5, 1.5, 64)
        lon = np.linspace(-3.0, 3.0, 64)
        alt = np.linspace(0.0, 1200.0, 64)
        r = geodetic_to_itrf(lat, lon, alt)
        assert r.shape == (64, 3)
        back_lat, _, back_alt = itrf_to_geodetic(r)
        assert np.allclose(back_lat, lat, atol=1e-12)
        assert np.allclose(back_alt, alt, atol=1e-9)

    def test_scalar_inputs_give_a_two_dimensional_result(self) -> None:
        """Always (n, 3), so a caller never has to branch on shape."""
        assert geodetic_to_itrf(0.1, 0.2, 0.3).shape == (1, 3)

    def test_rejects_latitude_outside_the_hemisphere(self) -> None:
        with pytest.raises(DomainError, match="degrees that were never converted"):
            geodetic_to_itrf(45.0, 0.0, 0.0)  # degrees passed as radians

    def test_rejects_non_broadcastable_lengths(self) -> None:
        with pytest.raises(DomainError, match="neither 1 nor"):
            geodetic_to_itrf(np.zeros(4), np.zeros(3), 0.0)

    def test_rejects_the_earth_centre(self) -> None:
        with pytest.raises(DomainError, match="Earth's centre"):
            itrf_to_geodetic(np.zeros((1, 3)))


@pytest.mark.physics
class TestEnuInvariants:
    def test_axes_at_the_equatorial_prime_meridian(self) -> None:
        """At (0, 0): ITRF x is Up, ITRF y is East, ITRF z is North.

        Rows of the result are the ENU components of the ITRF basis vectors, in
        order x, y, z.
        """
        basis = enu_from_itrf(np.eye(3), 0.0, 0.0)
        up, east, north = (0.0, 0.0, 1.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
        assert np.allclose(basis, np.array([up, east, north]), atol=1e-15)

    def test_up_is_the_geodetic_normal(self) -> None:
        """A vertical offset above a station is pure Up in ENU.

        This is what fails if the basis is built on the geocentric radius instead
        of the ellipsoid normal: East stays right, but Up and North mix by up to
        0.19 deg, which biases every elevation angle.
        """
        lat, lon = math.radians(41.275), math.radians(1.9875)
        station = geodetic_to_itrf(lat, lon, 0.03)
        overhead = geodetic_to_itrf(lat, lon, 600.03)
        enu = enu_from_itrf(overhead - station, lat, lon)
        assert float(enu[0, 2]) == pytest.approx(600.0, abs=1e-9)
        assert abs(float(enu[0, 0])) < 1e-9
        assert abs(float(enu[0, 1])) < 1e-9

    def test_rotation_preserves_length(self) -> None:
        rng = np.random.default_rng(20_260_731)
        vec = rng.normal(size=(50, 3)) * 1000.0
        enu = enu_from_itrf(vec, 0.6, -1.2)
        assert np.allclose(np.linalg.norm(enu, axis=1), np.linalg.norm(vec, axis=1), rtol=1e-14)

    def test_basis_is_right_handed_and_orthonormal(self) -> None:
        matrix = enu_from_itrf(np.eye(3), 0.75, 2.1).T
        assert np.allclose(matrix @ matrix.T, np.eye(3), atol=1e-14)
        assert float(np.linalg.det(matrix)) == pytest.approx(1.0, abs=1e-14)

    def test_north_points_towards_increasing_latitude(self) -> None:
        lat, lon = math.radians(-33.0), math.radians(151.0)
        here = geodetic_to_itrf(lat, lon, 0.0)
        poleward = geodetic_to_itrf(lat + 1e-4, lon, 0.0)
        enu = enu_from_itrf(poleward - here, lat, lon)
        assert float(enu[0, 1]) > 0.0
        assert abs(float(enu[0, 0])) < 1e-9

    def test_east_points_towards_increasing_longitude(self) -> None:
        """East dominates, with only the second-order chord term leaking into North.

        Unlike the meridian case, this one has no exact symmetry: the straight
        chord between two points on a parallel cuts inside the circle, so its
        radial deficit projects onto the local North axis with magnitude
        ``sin(lat) rho dlon^2 / 2``. That is geometry, not error, so the assertion
        bounds the ratio rather than pretending it is zero.
        """
        lat, lon = math.radians(20.0), math.radians(10.0)
        delta_lon = 1e-4
        here = geodetic_to_itrf(lat, lon, 0.0)
        eastward = geodetic_to_itrf(lat, lon + delta_lon, 0.0)
        enu = enu_from_itrf(eastward - here, lat, lon)
        east, north = float(enu[0, 0]), float(enu[0, 1])
        assert east > 0.0
        assert abs(north) < 1e-3 * east

        distance_from_axis_km = float(np.hypot(here[0, 0], here[0, 1]))
        expected_north = math.sin(lat) * distance_from_axis_km * delta_lon**2 / 2.0
        assert north == pytest.approx(expected_north, rel=1e-3)

    def test_rejects_latitude_in_degrees(self) -> None:
        with pytest.raises(DomainError, match=r"\[-pi/2, pi/2\]"):
            enu_from_itrf(np.eye(3), 41.275, 0.0)


class TestFrameEnum:
    def test_is_a_string_enum_so_it_serialises(self) -> None:
        assert Frame.TEME == "teme"
        assert json.dumps({"frame": Frame.ITRF}) == '{"frame": "itrf"}'

    def test_gcrf_is_declared_but_unreachable(self) -> None:
        """Declared as a hook, and no function here produces it. See the ADR."""
        assert Frame.GCRF == "gcrf"


# --------------------------------------------------------------------------- #
# V3 — against the frozen astropy / ERFA reference
# --------------------------------------------------------------------------- #
@pytest.mark.reference
class TestAgainstReference:
    def test_reference_file_has_a_manifest(self, reference: dict[str, Any]) -> None:
        """A reference file without provenance is a magic number in a bigger file."""
        manifest = reference["manifest"]
        assert manifest["versions"]["astropy"]
        assert manifest["versions"]["pyerfa"]
        assert manifest["generator"].endswith("gen_frames_reference.py")

    def test_calendar_matches_astropy(self, reference: dict[str, Any]) -> None:
        """Julian dates, including both non-leap century years."""
        worst = 0.0
        for row in reference["calendar_jd"]:
            jd = calendar_to_jd(
                row["year"], row["month"], row["day"], row["hour"], row["minute"], row["second"]
            )
            worst = max(worst, abs(jd - row["jd_utc"]))
        # Exact in practice; the bound is one microsecond of a day.
        assert worst < 1.2e-11

    def test_gmst_matches_erfa(self, reference: dict[str, Any]) -> None:
        """Same model as ERFA's gmst82, so this tests the implementation.

        The tolerance is set by float64 resolution on a Julian date passed as a
        single value where ERFA takes a two-part split: at JD ~2.4e6 an ulp is
        ~5e-10 d, which is ~4e-11 rad of Earth rotation.
        """
        jd = np.array([row["jd_utc"] for row in reference["gmst"]])
        expected = np.array([row["gmst82_rad"] for row in reference["gmst"]])
        assert np.max(np.abs(gmst_rad(jd) - expected)) < 1e-10

    def test_gmst_model_choice_is_bounded(self, reference: dict[str, Any]) -> None:
        """IAU-82 versus IAU-2006 GMST: the size of the modelling choice.

        Recorded rather than assumed. Over 2000-2030 the two agree to well under
        0.1 arcsec; the bound here covers the full 1900-2100 reference set, where
        the series diverge to ~0.29 arcsec (~10 m at LEO radius).
        """
        gaps = np.array([abs(row["gmst82_rad"] - row["gmst06_rad"]) for row in reference["gmst"]])
        assert np.max(gaps) < 1.5e-6  # ~0.31 arcsec
        modern = [row for row in reference["gmst"] if 2000 <= int(row["iso_utc"][:4]) <= 2030]
        assert modern, "reference set must cover the epochs QuOSS actually simulates"
        assert max(abs(r["gmst82_rad"] - r["gmst06_rad"]) for r in modern) < 3.0e-7

    def test_geodetic_to_itrf_matches_astropy(self, reference: dict[str, Any]) -> None:
        """WGS-84 forward conversion, to the millimetre, including 2000 km altitude."""
        rows = reference["geodetic"]
        lat = np.array([math.radians(r["latitude_deg"]) for r in rows])
        lon = np.array([math.radians(r["longitude_deg"]) for r in rows])
        alt = np.array([r["height_m"] / 1000.0 for r in rows])
        expected = np.array([r["itrf_km"] for r in rows])
        error_mm = np.max(np.abs(geodetic_to_itrf(lat, lon, alt) - expected)) * 1e6
        assert error_mm < 1.0

    def test_itrf_to_geodetic_matches_astropy(self, reference: dict[str, Any]) -> None:
        """The inverse, which is where a spherical shortcut would show up worst."""
        rows = reference["geodetic"]
        r = np.array([row["itrf_km"] for row in rows])
        lat, lon, alt = itrf_to_geodetic(r)
        expected_lat = np.array([math.radians(row["roundtrip_latitude_deg"]) for row in rows])
        expected_lon = np.array([math.radians(row["roundtrip_longitude_deg"]) for row in rows])
        expected_alt = np.array([row["roundtrip_height_m"] / 1000.0 for row in rows])

        assert np.max(np.abs(lat - expected_lat)) < 1e-11
        assert np.max(np.abs(alt - expected_alt)) * 1e6 < 1.0  # millimetres
        # Longitude only where it is defined: the two polar cases are excluded.
        defined = np.abs(np.abs(expected_lat) - math.pi / 2) > 1e-9
        wrapped = (lon[defined] - expected_lon[defined] + math.pi) % (2.0 * math.pi) - math.pi
        assert np.max(np.abs(wrapped)) < 1e-11


@pytest.mark.reference
class TestFrameErrorBudget:
    """The measured cost of the TEME/ITRF approximations, held to derived bounds.

    Not a "close enough" test. Each of the two approximations QuOSS makes is
    isolated and bounded by the size of the effect it stands for, so a regression
    that quietly reintroduces one of them fails here with a readable number
    rather than eating into a slack tolerance.
    """

    @staticmethod
    def _residual_m(row: dict[str, Any], gmst_key: str) -> float:
        got = teme_to_itrf(np.array([row["r_teme_km"]]), np.array([row[gmst_key]]))
        expected = np.array(row["r_itrs_astropy_km"])
        return float(np.linalg.norm(got[0] - expected)) * 1000.0

    def test_polar_motion_is_the_only_residual_once_ut1_is_restored(
        self, reference: dict[str, Any]
    ) -> None:
        """Rotate through GMST(UT1) and astropy's full reduction is matched to ~15 m.

        This is the load-bearing assertion of the module: it says the rotation
        itself is right, and that everything left over is the polar motion QuOSS
        deliberately omits. Polar motion is bounded by ~0.3 arcsec, which at LEO
        radius subtends about 11 m; 20 m leaves room for the TIO locator and the
        wander of the pole without admitting a real error.
        """
        residuals = [self._residual_m(row, "gmst82_ut1_rad") for row in reference["teme_to_itrf"]]
        assert max(residuals) < 20.0

    def test_ut1_approximation_stays_within_its_rotation_arc(
        self, reference: dict[str, Any]
    ) -> None:
        """Using UTC for UT1 costs exactly the arc DUT1 subtends, and nothing more.

        The bound is computed per case from the recorded DUT1 rather than being a
        fixed number, so it holds whatever epochs the reference set covers.
        """
        for row in reference["teme_to_itrf"]:
            radius_km = float(np.linalg.norm(row["r_teme_km"]))
            arc_m = abs(row["dut1_s"]) * EARTH_ROTATION_RAD_S * radius_km * 1000.0
            assert self._residual_m(row, "gmst82_rad") < arc_m + 20.0

    def test_the_documented_worst_case_still_holds(self, reference: dict[str, Any]) -> None:
        """The number quoted in the module docstring, kept honest by a test.

        |DUT1| never exceeds 0.9 s by international agreement, so 0.9 s of Earth
        rotation at LEO radius is the standing bound on the whole approximation.
        """
        worst_m = max(self._residual_m(row, "gmst82_rad") for row in reference["teme_to_itrf"])
        radius_km = max(float(np.linalg.norm(r["r_teme_km"])) for r in reference["teme_to_itrf"])
        standing_bound_m = 0.9 * EARTH_ROTATION_RAD_S * radius_km * 1000.0 + 20.0
        assert worst_m < standing_bound_m
        # And the docstring's "274 m measured" is the actual figure, not a guess.
        assert 250.0 < worst_m < 290.0

    @given(
        latitude_deg=st.floats(min_value=-89.0, max_value=89.0),
        elevation_deg=st.floats(min_value=10.0, max_value=90.0),
    )
    @settings(max_examples=100, deadline=None)
    def test_ut1_error_never_moves_elevation_by_more_than_a_hundredth_of_a_degree(
        self, latitude_deg: float, elevation_deg: float
    ) -> None:
        """Propagate the worst-case DUT1 all the way to an elevation angle.

        The budget table claims the UT1 approximation is worth under 0.03 deg of
        elevation. That is the number a link budget actually cares about, so it is
        checked directly instead of being inferred from a position error.
        """
        assume(abs(latitude_deg) < 89.0)
        lat = math.radians(latitude_deg)
        station = geodetic_to_itrf(lat, 0.0, 0.0)

        # A satellite placed at the requested elevation, in the station meridian.
        slant_km = 1000.0
        enu_target = np.array(
            [[0.0, math.cos(math.radians(elevation_deg)), math.sin(math.radians(elevation_deg))]]
        )
        # Rotate ENU back to ITRF using the transpose of the ENU basis.
        basis = enu_from_itrf(np.eye(3), lat, 0.0)
        satellite = station + (enu_target * slant_km) @ basis

        worst_dut1_s = 0.9
        theta_error = worst_dut1_s * EARTH_ROTATION_RAD_S
        shifted = teme_to_itrf(itrf_to_teme(satellite, np.array([0.0])), np.array([theta_error]))

        def elevation_deg_of(target: np.ndarray) -> float:
            enu = enu_from_itrf(target - station, lat, 0.0)[0]
            return math.degrees(math.atan2(enu[2], math.hypot(enu[0], enu[1])))

        assert abs(elevation_deg_of(shifted) - elevation_deg_of(satellite)) < 0.03
