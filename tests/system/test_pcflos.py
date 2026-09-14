"""Tests for `quoss.system.pcflos`.

Organised by the claim each block defends.

- ``TestTheZenithValueIsExactAndTheRestIsAGap`` — ``1 - f`` at the zenith, a
  warning on every call, and the negative control: **no signature in the module
  accepts an elevation**, the same guard ``channel/background.py`` has.
- ``TestTheThreeReadingsOfAnHourlySeries`` — the measurement the default rests
  on: on a synthetic front at hourly resolution the mean, culmination and
  minimum readings of a pass differ by at most 0.023, and the ordering
  ``minimum <= mean`` holds by construction.
- ``TestPassAvailabilityRefusesToInventWeather`` — a series that does not cover
  a pass is a ``DomainError``, not a clamped end value; epochs reconcile through
  Julian dates; interpolation is recorded.
- ``TestAgainstAHandComputedInterpolant`` — **V3 within the project**: the
  vectorised mean and minimum against a per-pass Python loop over the same
  piecewise-linear function, and the minimum against a dense-sampling brute
  force.
- ``TestSiteDiversity`` — the two-station Bernoulli law: exact at the extremes,
  between the bounds everywhere, the feasibility bound enforced, and the
  N > 2 case returning bounds with the gap in the log. Hypothesis over the
  marginals.
- ``TestStationSeparation`` — **V3**: the chord-through-the-ellipsoid arc
  against the haversine formula, to within the flattening.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from quoss.core.constants import WGS84_FLATTENING
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.types import TimeGrid
from quoss.system import pcflos
from quoss.system.passes import PassTable
from quoss.system.pcflos import (
    WGS84_MEAN_RADIUS_KM,
    AvailabilityRule,
    JointCloudFreeProbability,
    cloud_free_probability,
    joint_cloud_free_probability,
    pass_availability,
    station_separation_km,
)

from .reference import Link, link


@pytest.fixture(scope="module")
def reference_link() -> Link:
    return link()


@pytest.fixture(scope="module")
def table(reference_link: Link) -> PassTable:
    return reference_link.table


def hourly_grid(table: PassTable, hours: int = 24) -> TimeGrid:
    """Return an hourly series grid on the pass grid's epoch, covering ``hours`` hours."""
    return TimeGrid.uniform(epoch_jd=table.grid.epoch_jd, duration_s=3600.0 * hours, step_s=3600.0)


def synthetic_front(grid: TimeGrid) -> np.ndarray:
    """Cover rising 0.05 -> 0.95 over three hours, holding, and falling back.

    Shaped so that the reference day's morning passes (07:08-08:53 UTC) sit on
    the rising edge and the evening passes (18:13-19:59 UTC) on the falling one:
    the steepest slope an hourly ERA5 series can plausibly carry, which is the
    case that separates the three readings most.
    """
    hours = grid.t_s / 3600.0
    rise = np.clip((hours - 6.0) / 3.0, 0.0, 1.0)
    fall = np.clip((hours - 17.0) / 3.0, 0.0, 1.0)
    return 0.05 + 0.9 * (rise - fall)


class TestTheZenithValueIsExactAndTheRestIsAGap:
    """``1 - f`` is a definition at the zenith and a declared gap elsewhere."""

    @pytest.mark.physics
    @given(fraction=st.floats(min_value=0.0, max_value=1.0))
    @settings(max_examples=100, deadline=None)
    def test_one_minus_f(self, fraction: float) -> None:
        log = DegradationLog()
        assert float(cloud_free_probability(fraction, degradations=log)) == pytest.approx(
            1.0 - fraction, abs=1e-15
        )

    @pytest.mark.physics
    def test_vectorised_over_a_series_with_one_warning_per_call(self) -> None:
        log = DegradationLog()
        series = np.linspace(0.0, 1.0, 1001)
        probability = cloud_free_probability(series, degradations=log)
        assert probability.shape == (1001,)
        assert np.all((probability >= 0.0) & (probability <= 1.0))
        assert len(log) == 1
        entry = log.entries[0]
        assert entry.code == "pcflos.no-elevation-dependence"
        assert entry.severity is Severity.WARNING
        assert entry.details["n_values"] == 1001
        assert "upper bound" in entry.message

    def test_no_function_here_takes_an_elevation(self) -> None:
        """The negative control for the gap that would be easiest to fill wrongly.

        Lund & Shanklin's elevation dependence could not be opened, so no
        signature offers a place to put an elevation. If one ever appears it
        should arrive with a verified table, and this test is what notices.
        """
        for name in pcflos.__all__:
            attribute = getattr(pcflos, name)
            if not callable(attribute) or isinstance(attribute, type):
                continue
            parameters = inspect.signature(attribute).parameters
            assert not any("elevation" in parameter for parameter in parameters), name
            assert not any("zenith" in parameter for parameter in parameters), name

    def test_the_gap_is_named_in_the_module_docstring(self) -> None:
        assert pcflos.__doc__ is not None
        for phrase in ("Lund", "Shanklin", "Neither paper could be opened", "upper bound", "0009"):
            assert phrase in pcflos.__doc__

    @pytest.mark.parametrize("bad", [-0.1, 1.5, 50.0, np.nan])
    def test_a_fraction_outside_the_unit_interval_is_refused(self, bad: float) -> None:
        with pytest.raises(DomainError):
            cloud_free_probability(bad, degradations=DegradationLog())

    def test_a_percentage_is_named_as_the_likely_mistake(self) -> None:
        with pytest.raises(DomainError, match="divided by 100"):
            cloud_free_probability(50.0, degradations=DegradationLog())


class TestTheThreeReadingsOfAnHourlySeries:
    """The measurement behind the default rule, regenerated."""

    @pytest.mark.physics
    def test_the_spread_between_readings_is_small_at_hourly_resolution(
        self, table: PassTable
    ) -> None:
        """At most 0.023 across the reference day's passes under a steep front.

        The bound is derived, not tuned: a linear interpolant of an hourly series
        moves by at most (hourly change) x (window / 1 h) inside a window, and the
        longest pass is 562 s under a 0.3 per hour slope, so 0.3 x 562 / 3600 =
        0.047 is the ceiling on any spread. The measured 0.023 is half of it —
        the minimum sits a half-window's slope below the mean, and the mean and
        the culmination value agree to 1e-4 because the interpolant is nearly
        linear across a pass and the culmination is near its midpoint.
        """
        grid = hourly_grid(table)
        cover = synthetic_front(grid)
        readings = {}
        for rule in AvailabilityRule:
            readings[rule] = pass_availability(
                cover, grid=grid, table=table, degradations=DegradationLog(), rule=rule
            )
        spread = max(
            float(np.max(np.abs(readings[a] - readings[b])))
            for a in AvailabilityRule
            for b in AvailabilityRule
        )
        ceiling = 0.3 * float(table.duration_s.max()) / 3600.0
        assert ceiling == pytest.approx(0.047, abs=1e-3)
        assert spread == pytest.approx(0.023, abs=1e-3)
        assert spread < ceiling
        assert np.allclose(
            readings[AvailabilityRule.MEAN], readings[AvailabilityRule.CULMINATION], atol=2e-4
        )
        # And the front really does span the day: the readings are not all alike.
        assert float(np.ptp(readings[AvailabilityRule.MEAN])) > 0.5

    @pytest.mark.physics
    def test_the_minimum_never_exceeds_the_mean_or_the_culmination(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        cover = synthetic_front(grid)
        minimum = pass_availability(
            cover,
            grid=grid,
            table=table,
            degradations=DegradationLog(),
            rule="minimum",  # type: ignore[arg-type]  # a StrEnum accepts its own value
        )
        mean = pass_availability(cover, grid=grid, table=table, degradations=DegradationLog())
        culmination = pass_availability(
            cover,
            grid=grid,
            table=table,
            degradations=DegradationLog(),
            rule=AvailabilityRule.CULMINATION,
        )
        assert np.all(minimum <= mean + 1e-12)
        assert np.all(minimum <= culmination + 1e-12)

    @pytest.mark.physics
    def test_a_constant_series_makes_the_three_readings_identical(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        cover = np.full(grid.n, 0.3)
        for rule in AvailabilityRule:
            value = pass_availability(
                cover, grid=grid, table=table, degradations=DegradationLog(), rule=rule
            )
            assert np.allclose(value, 0.7, rtol=0.0, atol=1e-12)

    @pytest.mark.physics
    def test_the_log_carries_the_rule_the_interpolation_and_the_spread(
        self, table: PassTable
    ) -> None:
        grid = hourly_grid(table)
        log = DegradationLog()
        pass_availability(synthetic_front(grid), grid=grid, table=table, degradations=log)
        entry = next(e for e in log if e.code == "pcflos.pass-availability-rule")
        assert entry.severity is Severity.INFO
        assert entry.details["rule"] == "mean"
        assert entry.details["interpolation"] == "linear"
        assert entry.details["series_step_s"] == 3600.0
        assert entry.details["n_passes"] == 4
        assert entry.details["max_spread_between_rules"] == pytest.approx(0.023, abs=1e-3)
        assert len(entry.details["minimum"]) == 4
        # The zenith warning travels too: one per call.
        assert sum(e.code == "pcflos.no-elevation-dependence" for e in log) == 1

    @pytest.mark.physics
    def test_a_non_uniform_series_records_no_step(self, table: PassTable) -> None:
        knots = np.array([0.0, 20_000.0, 30_000.0, 60_000.0, 86_400.0])
        grid = TimeGrid(epoch_jd=table.grid.epoch_jd, t_s=knots)
        log = DegradationLog()
        pass_availability(np.full(5, 0.2), grid=grid, table=table, degradations=log)
        entry = next(e for e in log if e.code == "pcflos.pass-availability-rule")
        assert entry.details["series_step_s"] is None


class TestPassAvailabilityRefusesToInventWeather:
    """Coverage, epochs and shapes."""

    def test_a_series_that_stops_before_the_last_pass_is_refused(self, table: PassTable) -> None:
        grid = hourly_grid(table, hours=10)
        with pytest.raises(DomainError, match="does not cover"):
            pass_availability(
                np.zeros(grid.n), grid=grid, table=table, degradations=DegradationLog()
            )

    def test_a_series_that_starts_after_the_first_pass_is_refused(self, table: PassTable) -> None:
        grid = TimeGrid.uniform(
            epoch_jd=table.grid.epoch_jd + 0.5, duration_s=43_200.0, step_s=3600.0
        )
        with pytest.raises(DomainError, match="inventing weather"):
            pass_availability(
                np.zeros(grid.n), grid=grid, table=table, degradations=DegradationLog()
            )

    @pytest.mark.physics
    def test_epochs_are_reconciled_through_julian_dates(self, table: PassTable) -> None:
        """The same weather on a grid whose epoch is six hours earlier gives the same answer."""
        native = hourly_grid(table)
        cover = synthetic_front(native)
        expected = pass_availability(cover, grid=native, table=table, degradations=DegradationLog())
        earlier = TimeGrid.uniform(
            epoch_jd=table.grid.epoch_jd - 0.25, duration_s=3600.0 * 30, step_s=3600.0
        )
        shifted_cover = np.concatenate([np.full(6, cover[0]), cover])
        shifted = pass_availability(
            shifted_cover, grid=earlier, table=table, degradations=DegradationLog()
        )
        assert np.allclose(shifted, expected, rtol=0.0, atol=1e-12)

    def test_a_series_of_the_wrong_length_is_refused(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        with pytest.raises(DomainError, match="One cover fraction per sample"):
            pass_availability(
                np.zeros(grid.n - 1), grid=grid, table=table, degradations=DegradationLog()
            )

    def test_a_non_grid_or_non_table_is_refused(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        with pytest.raises(DomainError, match="grid must be a TimeGrid"):
            pass_availability(
                np.zeros(25),
                grid=grid.t_s,  # type: ignore[arg-type]
                table=table,
                degradations=DegradationLog(),
            )
        with pytest.raises(DomainError, match="table must be a PassTable"):
            pass_availability(np.zeros(25), grid=grid, table=grid, degradations=DegradationLog())  # type: ignore[arg-type]

    def test_an_unknown_rule_is_refused(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        with pytest.raises(ValueError):
            pass_availability(
                np.zeros(grid.n),
                grid=grid,
                table=table,
                degradations=DegradationLog(),
                rule="median",  # type: ignore[arg-type]
            )

    @pytest.mark.physics
    def test_an_empty_table_gives_an_empty_answer_and_no_coverage_check(
        self, table: PassTable
    ) -> None:
        """No passes, nothing to cover: the series may be as short as it likes."""
        empty = table.select(np.zeros(table.n_passes, dtype=bool))
        grid = hourly_grid(table, hours=1)
        log = DegradationLog()
        result = pass_availability(np.zeros(grid.n), grid=grid, table=empty, degradations=log)
        assert result.shape == (0,)
        assert len(log) == 0


class TestAgainstAHandComputedInterpolant:
    """**V3 within the project**: the vectorised readings against explicit loops."""

    @pytest.mark.physics
    def test_the_mean_matches_a_per_pass_loop(self, table: PassTable) -> None:
        grid = hourly_grid(table)
        cover = synthetic_front(grid)
        vectorised = pass_availability(cover, grid=grid, table=table, degradations=DegradationLog())
        samples = table.samples()
        fine_t = table.grid.t_s
        expected = []
        for index in range(table.n_passes):
            rows = samples.pass_index == index
            values = np.interp(fine_t[samples.sample_index[rows]], grid.t_s, 1.0 - cover)
            weights = samples.dwell_s[rows]
            expected.append(float(np.sum(values * weights) / np.sum(weights)))
        assert np.allclose(vectorised, expected, rtol=1e-13, atol=0.0)

    @pytest.mark.physics
    def test_the_minimum_matches_a_dense_brute_force(self, table: PassTable) -> None:
        """Sampling the interpolant every 0.1 s over each window can only overestimate the minimum.

        The exact minimum of a piecewise-linear function is at a knot or an
        endpoint, both of which the dense sampling hits to within 0.1 s x slope
        = 0.3 / 36 000 per sample, which is the tolerance.
        """
        grid = hourly_grid(table)
        cover = synthetic_front(grid)
        vectorised = pass_availability(
            cover,
            grid=grid,
            table=table,
            degradations=DegradationLog(),
            rule=AvailabilityRule.MINIMUM,
        )
        slope_per_s = 0.3 / 3600.0
        for index in range(table.n_passes):
            dense = np.arange(table.start_s[index], table.end_s[index], 0.1)
            dense = np.append(dense, table.end_s[index])
            brute = float(np.min(np.interp(dense, grid.t_s, 1.0 - cover)))
            assert brute >= float(vectorised[index]) - 1e-12
            assert brute - float(vectorised[index]) <= 0.1 * slope_per_s

    @pytest.mark.physics
    def test_the_minimum_finds_a_knot_strictly_inside_a_pass(self, table: PassTable) -> None:
        """A dip at a knot inside the window, invisible from the endpoints and the culmination."""
        knots = np.array([0.0, 25_900.0, 26_000.0, 26_100.0, 86_400.0])  # inside pass 1
        grid = TimeGrid(epoch_jd=table.grid.epoch_jd, t_s=knots)
        cover = np.array([0.0, 0.0, 0.8, 0.0, 0.0])
        minimum = pass_availability(
            cover,
            grid=grid,
            table=table,
            degradations=DegradationLog(),
            rule=AvailabilityRule.MINIMUM,
        )
        assert float(minimum[0]) == pytest.approx(0.2, abs=1e-12)
        assert np.allclose(minimum[1:], 1.0)


class TestSiteDiversity:
    """The two-station law, its bounds, its feasibility, and the N > 2 gap."""

    @staticmethod
    def pair(d_km: float) -> np.ndarray:
        return np.array([[0.0, d_km], [d_km, 0.0]])

    @pytest.mark.physics
    def test_zero_separation_is_perfect_correlation_and_infinite_is_independence(self) -> None:
        p = np.array([0.6, 0.6])
        close = joint_cloud_free_probability(
            p,
            separation_km=self.pair(0.0),
            decorrelation_length_km=500.0,
            degradations=DegradationLog(),
        )
        far = joint_cloud_free_probability(
            p,
            separation_km=self.pair(1e6),
            decorrelation_length_km=500.0,
            degradations=DegradationLog(),
        )
        assert close.exact is not None and far.exact is not None
        assert float(close.exact) == pytest.approx(float(close.comonotone), abs=1e-12)
        assert float(far.exact) == pytest.approx(float(far.independent), abs=1e-12)
        assert float(far.independent) == pytest.approx(1.0 - 0.16, abs=1e-12)

    @pytest.mark.physics
    def test_the_two_station_law_by_hand(self) -> None:
        """``P(both cloudy) = q1 q2 + rho sqrt(p1 q1 p2 q2)`` transcribed independently."""
        p1, p2, d, length = 0.7, 0.5, 300.0, 500.0
        joint = joint_cloud_free_probability(
            np.array([p1, p2]),
            separation_km=self.pair(d),
            decorrelation_length_km=length,
            degradations=DegradationLog(),
        )
        rho = np.exp(-d / length)
        both_cloudy = (1 - p1) * (1 - p2) + rho * np.sqrt(p1 * (1 - p1) * p2 * (1 - p2))
        assert joint.exact is not None
        assert float(joint.exact) == pytest.approx(1.0 - both_cloudy, abs=1e-15)
        assert float(joint.correlation[0, 1]) == pytest.approx(rho, abs=1e-15)
        assert float(joint.correlation[0, 0]) == 1.0

    @pytest.mark.physics
    @given(
        p1=st.floats(min_value=0.0, max_value=1.0),
        p2=st.floats(min_value=0.0, max_value=1.0),
        d=st.floats(min_value=0.0, max_value=5000.0),
    )
    @settings(max_examples=300, deadline=None)
    def test_the_exact_value_lies_between_the_bounds_or_the_pair_is_infeasible(
        self, p1: float, p2: float, d: float
    ) -> None:
        try:
            joint = joint_cloud_free_probability(
                np.array([p1, p2]),
                separation_km=self.pair(d),
                decorrelation_length_km=500.0,
                degradations=DegradationLog(),
            )
        except DomainError as refused:
            assert "can be correlated at most" in str(refused)
            return
        assert joint.exact is not None
        assert (
            float(joint.comonotone) - 1e-12
            <= float(joint.exact)
            <= float(joint.independent) + 1e-12
        )
        assert float(joint.comonotone) == pytest.approx(max(p1, p2), abs=1e-15)

    @pytest.mark.physics
    def test_the_feasibility_bound_is_the_frechet_one(self) -> None:
        """Just below the bound is accepted, just above is refused."""
        p1, p2 = 0.9, 0.3
        rho_max = np.sqrt(min(p1 * (1 - p2), p2 * (1 - p1)) / max(p1 * (1 - p2), p2 * (1 - p1)))
        assert rho_max == pytest.approx(0.2182, abs=1e-4)
        length = 500.0
        d_at_bound = -length * np.log(rho_max)
        ok = joint_cloud_free_probability(
            np.array([p1, p2]),
            separation_km=self.pair(d_at_bound * 1.001),
            decorrelation_length_km=length,
            degradations=DegradationLog(),
        )
        assert ok.exact is not None
        with pytest.raises(DomainError, match=r"can be correlated at most 0\.2182"):
            joint_cloud_free_probability(
                np.array([p1, p2]),
                separation_km=self.pair(d_at_bound * 0.999),
                decorrelation_length_km=length,
                degradations=DegradationLog(),
            )

    @pytest.mark.physics
    def test_a_constant_marginal_makes_the_correlation_irrelevant(self) -> None:
        """p = 1 or 0 is a constant variable: any rho is feasible and cannot act."""
        for p in (0.0, 1.0):
            joint = joint_cloud_free_probability(
                np.array([p, 0.4]),
                separation_km=self.pair(0.0),
                decorrelation_length_km=500.0,
                degradations=DegradationLog(),
            )
            assert joint.exact is not None
            assert float(joint.exact) == pytest.approx(float(joint.independent), abs=1e-15)

    @pytest.mark.physics
    def test_a_time_series_of_marginals_is_handled_along_the_trailing_axis(self) -> None:
        p = np.array([[0.2, 0.5, 0.9], [0.9, 0.5, 0.2]])
        joint = joint_cloud_free_probability(
            p,
            separation_km=self.pair(2000.0),
            decorrelation_length_km=500.0,
            degradations=DegradationLog(),
        )
        assert joint.exact is not None
        assert joint.exact.shape == (3,)
        assert joint.independent.shape == (3,)
        assert np.all(joint.exact <= joint.independent + 1e-12)
        assert np.all(joint.exact >= joint.comonotone - 1e-12)

    @pytest.mark.physics
    def test_one_station_returns_itself(self) -> None:
        joint = joint_cloud_free_probability(
            np.array([0.42]),
            separation_km=np.zeros((1, 1)),
            decorrelation_length_km=1.0,
            degradations=DegradationLog(),
        )
        assert joint.exact is not None
        assert float(joint.exact) == 0.42
        assert float(joint.independent) == pytest.approx(0.42, abs=1e-15)
        assert float(joint.comonotone) == 0.42
        assert joint.n_stations == 1

    @pytest.mark.physics
    def test_three_stations_return_bounds_and_declare_the_gap(self) -> None:
        log = DegradationLog()
        p = np.array([0.5, 0.6, 0.7])
        joint = joint_cloud_free_probability(
            p,
            separation_km=800.0 * (1.0 - np.eye(3)),
            decorrelation_length_km=500.0,
            degradations=log,
        )
        assert joint.exact is None
        assert not joint.is_exact
        assert float(joint.comonotone) == 0.7
        assert float(joint.independent) == pytest.approx(1.0 - 0.5 * 0.4 * 0.3, abs=1e-15)
        entry = next(e for e in log if e.code == "pcflos.joint-law-not-unique")
        assert entry.severity is Severity.WARNING
        assert entry.details["n_stations"] == 3
        assert "bounds only" in repr(joint)
        assert "exact" in repr(
            joint_cloud_free_probability(
                p[:2], separation_km=self.pair(1.0), decorrelation_length_km=1.0, degradations=log
            )
        )

    def test_the_decorrelation_length_has_no_default(self) -> None:
        parameter = inspect.signature(joint_cloud_free_probability).parameters[
            "decorrelation_length_km"
        ]
        assert parameter.default is inspect.Parameter.empty

    @pytest.mark.parametrize("length", [0.0, -1.0, np.inf, np.nan])
    def test_a_bad_decorrelation_length_is_refused(self, length: float) -> None:
        with pytest.raises(DomainError, match="decorrelation_length_km"):
            joint_cloud_free_probability(
                np.array([0.5, 0.5]),
                separation_km=self.pair(1.0),
                decorrelation_length_km=length,
                degradations=DegradationLog(),
            )


class TestStationSeparation:
    """**V3**: the ellipsoid chord as an arc, against the haversine formula."""

    @staticmethod
    def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        h = (
            np.sin(0.5 * (lat2 - lat1)) ** 2
            + np.cos(lat1) * np.cos(lat2) * np.sin(0.5 * (lon2 - lon1)) ** 2
        )
        return float(2.0 * WGS84_MEAN_RADIUS_KM * np.arcsin(np.sqrt(h)))

    @pytest.mark.physics
    def test_one_degree_on_the_equator_to_within_the_flattening(self) -> None:
        """The chord uses the equatorial radius, the haversine the mean one: f/3 apart."""
        lon = np.deg2rad(np.array([0.0, 1.0]))
        chord_arc = float(station_separation_km(np.zeros(2), lon)[0, 1])
        spherical = self.haversine_km(0.0, 0.0, 0.0, float(lon[1]))
        assert abs(chord_arc / spherical - 1.0) < WGS84_FLATTENING
        assert abs(chord_arc / spherical - 1.0) == pytest.approx(WGS84_FLATTENING / 3.0, rel=0.02)

    @pytest.mark.physics
    def test_one_degree_along_a_meridian_is_the_worst_case_and_it_is_derived(self) -> None:
        """A meridional arc at the equator is the ellipsoid's tightest curve.

        Its radius of curvature there is ``a (1 - e^2) = 6335.4 km``, 0.56 %
        below the mean radius the haversine uses — above the flattening, which
        is why the equatorial test above is not the general bound. Measured on
        a 37 x 37 x 37 grid of pairs, the worst deviation anywhere (0.557 %) is
        this one, and ``R / (a (1 - e^2)) - 1`` is the tolerance the Hypothesis
        test below derives from it.
        """
        from quoss.core.constants import WGS84_ECCENTRICITY_SQ, WGS84_RADIUS_EQUATORIAL_KM

        lat = np.deg2rad(np.array([0.0, 1.0]))
        chord_arc = float(station_separation_km(lat, np.zeros(2))[0, 1])
        spherical = self.haversine_km(float(lat[0]), 0.0, float(lat[1]), 0.0)
        meridional_km = WGS84_RADIUS_EQUATORIAL_KM * (1.0 - WGS84_ECCENTRICITY_SQ)
        floor = 1.0 - meridional_km / WGS84_MEAN_RADIUS_KM
        assert floor == pytest.approx(0.005583, abs=1e-6)
        assert 1.0 - chord_arc / spherical == pytest.approx(floor, rel=1e-3)
        assert 1.0 - chord_arc / spherical < floor
        assert 1.0 - chord_arc / spherical > WGS84_FLATTENING

    @pytest.mark.physics
    @given(
        lat1=st.floats(min_value=-89.0, max_value=89.0),
        lon1=st.floats(min_value=-180.0, max_value=180.0),
        lat2=st.floats(min_value=-89.0, max_value=89.0),
        lon2=st.floats(min_value=-180.0, max_value=180.0),
    )
    @settings(max_examples=200, deadline=None)
    def test_agrees_with_the_haversine_to_the_meridional_curvature_anywhere(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> None:
        """Relative deviation bounded by ``1 - a (1 - e^2) / R``, derived above.

        No slack: the bound is the infinitesimal meridional arc at the equator,
        which every finite arc approaches from below (0.005582 at 1 degree,
        0.005538 at worst over 200 000 random pairs between 50 and 15 000 km).
        """
        from quoss.core.constants import WGS84_ECCENTRICITY_SQ, WGS84_RADIUS_EQUATORIAL_KM

        lat = np.deg2rad(np.array([lat1, lat2]))
        lon = np.deg2rad(np.array([lon1, lon2]))
        matrix = station_separation_km(lat, lon)
        spherical = self.haversine_km(float(lat[0]), float(lon[0]), float(lat[1]), float(lon[1]))
        assume(50.0 < spherical < 15_000.0)
        assert matrix[0, 1] == matrix[1, 0]
        assert matrix[0, 0] == 0.0 and matrix[1, 1] == 0.0
        tolerance = 1.0 - WGS84_RADIUS_EQUATORIAL_KM * (1.0 - WGS84_ECCENTRICITY_SQ) / (
            WGS84_MEAN_RADIUS_KM
        )
        assert abs(float(matrix[0, 1]) / spherical - 1.0) <= tolerance

    @pytest.mark.physics
    def test_the_mean_radius_is_derived_from_the_two_axes(self) -> None:
        from quoss.core.constants import WGS84_RADIUS_EQUATORIAL_KM, WGS84_RADIUS_POLAR_KM

        assert WGS84_MEAN_RADIUS_KM == (2 * WGS84_RADIUS_EQUATORIAL_KM + WGS84_RADIUS_POLAR_KM) / 3
        assert WGS84_MEAN_RADIUS_KM == pytest.approx(6371.0088, abs=1e-4)

    def test_mismatched_or_invalid_coordinates_are_refused(self) -> None:
        with pytest.raises(DomainError, match="same length"):
            station_separation_km(np.zeros(2), np.zeros(3))
        with pytest.raises(DomainError, match="non-finite"):
            station_separation_km(np.array([0.0, np.nan]), np.zeros(2))
        with pytest.raises(DomainError, match="latitude_rad"):
            station_separation_km(np.array([0.0, 41.0]), np.zeros(2))


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError`` of `JointCloudFreeProbability` and the separation validator."""

    def test_bounds_in_the_wrong_order_are_refused(self) -> None:
        with pytest.raises(DomainError, match="cannot exceed independent"):
            JointCloudFreeProbability(
                independent=np.array([0.5]),
                comonotone=np.array([0.6]),
                exact=None,
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )

    def test_bounds_of_different_shapes_are_refused(self) -> None:
        with pytest.raises(DomainError, match="same instants"):
            JointCloudFreeProbability(
                independent=np.array([0.5, 0.5]),
                comonotone=np.array([0.4]),
                exact=None,
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )

    def test_an_exact_value_outside_the_bounds_is_refused(self) -> None:
        with pytest.raises(DomainError, match="between comonotone and independent"):
            JointCloudFreeProbability(
                independent=np.array([0.8]),
                comonotone=np.array([0.6]),
                exact=np.array([0.9]),
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )

    def test_an_exact_value_of_the_wrong_shape_is_refused(self) -> None:
        with pytest.raises(DomainError, match="exact has shape"):
            JointCloudFreeProbability(
                independent=np.array([0.8]),
                comonotone=np.array([0.6]),
                exact=np.array([0.7, 0.7]),
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )

    def test_a_probability_outside_the_unit_interval_is_refused(self) -> None:
        with pytest.raises(DomainError, match="must lie in \\[0, 1\\]"):
            JointCloudFreeProbability(
                independent=np.array([1.2]),
                comonotone=np.array([0.6]),
                exact=None,
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )
        with pytest.raises(DomainError, match="non-finite"):
            JointCloudFreeProbability(
                independent=np.array([np.nan]),
                comonotone=np.array([0.6]),
                exact=None,
                correlation=np.eye(2),
                decorrelation_length_km=1.0,
            )

    def test_a_non_square_correlation_or_bad_length_is_refused(self) -> None:
        with pytest.raises(DomainError, match="square matrix"):
            JointCloudFreeProbability(
                independent=np.array([0.8]),
                comonotone=np.array([0.6]),
                exact=None,
                correlation=np.ones((2, 3)),
                decorrelation_length_km=1.0,
            )
        with pytest.raises(DomainError, match="decorrelation_length_km"):
            JointCloudFreeProbability(
                independent=np.array([0.8]),
                comonotone=np.array([0.6]),
                exact=None,
                correlation=np.eye(2),
                decorrelation_length_km=-1.0,
            )

    def test_p_without_a_station_axis_or_empty_is_refused(self) -> None:
        with pytest.raises(DomainError, match="leading station axis"):
            joint_cloud_free_probability(
                np.float64(0.5),  # type: ignore[arg-type]
                separation_km=np.zeros((1, 1)),
                decorrelation_length_km=1.0,
                degradations=DegradationLog(),
            )
        with pytest.raises(DomainError, match="no stations"):
            joint_cloud_free_probability(
                np.zeros(0),
                separation_km=np.zeros((0, 0)),
                decorrelation_length_km=1.0,
                degradations=DegradationLog(),
            )
        with pytest.raises(DomainError, match="probability of a cloud-free"):
            joint_cloud_free_probability(
                np.array([1.5, 0.5]),
                separation_km=np.zeros((2, 2)),
                decorrelation_length_km=1.0,
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize(
        ("separation", "message"),
        [
            (np.zeros((3, 3)), "expected shape is \\(2, 2\\)"),
            (np.array([[0.0, -1.0], [-1.0, 0.0]]), "non-negative"),
            (np.array([[0.0, 1.0], [2.0, 0.0]]), "symmetric"),
            (np.array([[1.0, 1.0], [1.0, 0.0]]), "zero on the diagonal"),
        ],
    )
    def test_a_bad_separation_matrix_is_refused(self, separation: np.ndarray, message: str) -> None:
        with pytest.raises(DomainError, match=message):
            joint_cloud_free_probability(
                np.array([0.5, 0.5]),
                separation_km=separation,
                decorrelation_length_km=1.0,
                degradations=DegradationLog(),
            )
