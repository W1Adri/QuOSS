"""Tests for `quoss.system.multi_ogs`.

Organised by the claim each block defends.

- ``TestTheSchedulerIsExact`` — **V3 within the project.** The dynamic
  programme against a brute force over every subset of small random instances
  (Hypothesis), with and without a slew gap; the hand-built instance where
  greedy-by-key loses; and the maximality property that makes "not selected"
  mean "conflicts with a selected pass".
- ``TestOnTheReferenceDay`` — the measurement of the module docstring: three
  stations, SUM against BEST_AVAILABLE, how many passes conflict, what the exact
  schedule keeps against greedy, and what site diversity bought.
- ``TestAvailabilityIsAnExpectation`` — expected bits are ``bits x
  availability``, the certified column is untouched, and the log says so.
- ``TestTheSlewGap`` — a positive gap can only remove passes, and the default
  of zero is the only non-invented value.
- ``TestTheStationSet`` — separations, indexing, and every ``DomainError``.
- ``TestTheContainersRefuseImpossibleContents`` — mismatched grids, regimes,
  counts, the ground-terminal conflict the module does not model, and the
  result containers' own validation.
"""

from __future__ import annotations

import inspect
from itertools import combinations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.types import TimeGrid
from quoss.qkd.base import KeyRegime
from quoss.system.multi_ogs import (
    AggregationPolicy,
    MultiStationKeyVolume,
    StationPassKeys,
    StationSet,
    aggregate_stations,
    greedy_schedule_passes,
    same_grid,
    schedule_passes,
)

from .reference import REFERENCE_DAY_NUMBER, REFERENCE_FINITE_BITS
from .reference_stations import (
    CALAR_ALTO_FINITE_BITS,
    TENERIFE_FINITE_BITS,
    StationLink,
    station_link,
    station_set,
    synthetic_volume,
)


@pytest.fixture(scope="module")
def castelldefels() -> StationLink:
    return station_link("castelldefels")


@pytest.fixture(scope="module")
def calar_alto() -> StationLink:
    return station_link("calar_alto")


@pytest.fixture(scope="module")
def tenerife() -> StationLink:
    return station_link("tenerife_ogs")


def brute_force_optimum(
    start: np.ndarray, end: np.ndarray, weight: np.ndarray, gap: float
) -> float:
    """Return the best total over every subset, by enumeration. Exponential, for n <= 9."""
    n = start.size
    best = 0.0
    for size in range(1, n + 1):
        for subset in combinations(range(n), size):
            feasible = all(
                end[a] + gap <= start[b] or end[b] + gap <= start[a]
                for a, b in combinations(subset, 2)
            )
            if feasible:
                best = max(best, float(weight[list(subset)].sum()))
    return best


def is_feasible(start: np.ndarray, end: np.ndarray, keep: np.ndarray, gap: float) -> bool:
    chosen = np.flatnonzero(keep)
    return all(
        end[a] + gap <= start[b] or end[b] + gap <= start[a] for a, b in combinations(chosen, 2)
    )


intervals = st.lists(
    st.tuples(
        st.floats(min_value=0.0, max_value=100.0),
        st.floats(min_value=0.5, max_value=30.0),
        st.floats(min_value=0.0, max_value=10.0),
    ),
    min_size=0,
    max_size=9,
)


class TestTheSchedulerIsExact:
    """**V3 within the project**: dynamic programme against enumeration."""

    @pytest.mark.physics
    @given(items=intervals, gap=st.sampled_from([0.0, 0.0, 2.5]))
    @settings(max_examples=300, deadline=None)
    def test_the_dynamic_programme_matches_a_brute_force_over_all_subsets(
        self, items: list[tuple[float, float, float]], gap: float
    ) -> None:
        start = np.array([s for s, _, _ in items])
        end = np.array([s + d for s, d, _ in items])
        weight = np.array([w for _, _, w in items])
        keep = schedule_passes(start, end, weight, minimum_gap_s=gap)
        assert is_feasible(start, end, keep, gap)
        assert float(weight[keep].sum()) == pytest.approx(
            brute_force_optimum(start, end, weight, gap), rel=1e-12, abs=1e-12
        )

    @pytest.mark.physics
    @given(items=intervals, gap=st.sampled_from([0.0, 2.5]))
    @settings(max_examples=200, deadline=None)
    def test_every_unselected_interval_conflicts_with_a_selected_one(
        self, items: list[tuple[float, float, float]], gap: float
    ) -> None:
        """Maximality: the completion step makes "dropped" mean "in conflict"."""
        start = np.array([s for s, _, _ in items])
        end = np.array([s + d for s, d, _ in items])
        weight = np.array([w for _, _, w in items])
        keep = schedule_passes(start, end, weight, minimum_gap_s=gap)
        for j in np.flatnonzero(~keep):
            conflicts = [
                i
                for i in np.flatnonzero(keep)
                if not (end[i] + gap <= start[j] or end[j] + gap <= start[i])
            ]
            assert conflicts, f"interval {j} was dropped but conflicts with nothing"

    @pytest.mark.physics
    @given(items=intervals)
    @settings(max_examples=200, deadline=None)
    def test_greedy_never_beats_the_exact_schedule(
        self, items: list[tuple[float, float, float]]
    ) -> None:
        start = np.array([s for s, _, _ in items])
        end = np.array([s + d for s, d, _ in items])
        weight = np.array([w for _, _, w in items])
        exact = float(weight[schedule_passes(start, end, weight)].sum())
        greedy = greedy_schedule_passes(start, end, weight)
        assert is_feasible(start, end, greedy, 0.0)
        assert float(weight[greedy].sum()) <= exact + 1e-12

    @pytest.mark.physics
    def test_the_instance_where_greedy_loses(self) -> None:
        """A rich pass between two poorer ones that together are worth more."""
        start = np.array([0.0, 4.0, 9.0])
        end = np.array([5.0, 10.0, 14.0])
        weight = np.array([4.0, 6.0, 4.0])
        exact = schedule_passes(start, end, weight)
        greedy = greedy_schedule_passes(start, end, weight)
        assert exact.tolist() == [True, False, True]
        assert greedy.tolist() == [False, True, False]
        assert float(weight[exact].sum()) == 8.0
        assert float(weight[greedy].sum()) == 6.0

    @pytest.mark.physics
    def test_a_dead_pass_that_conflicts_with_nothing_is_kept(self) -> None:
        keep = schedule_passes(np.array([0.0, 10.0]), np.array([5.0, 15.0]), np.array([1.0, 0.0]))
        assert keep.tolist() == [True, True]

    @pytest.mark.physics
    def test_two_dead_passes_that_overlap_each_other_keep_only_one(self) -> None:
        keep = schedule_passes(np.array([0.0, 2.0]), np.array([5.0, 7.0]), np.zeros(2))
        assert int(keep.sum()) == 1

    def test_an_empty_instance_schedules_nothing(self) -> None:
        assert schedule_passes(np.zeros(0), np.zeros(0), np.zeros(0)).shape == (0,)
        assert greedy_schedule_passes(np.zeros(0), np.zeros(0), np.zeros(0)).shape == (0,)

    @pytest.mark.parametrize(
        ("start", "end", "weight", "gap", "message"),
        [
            (np.zeros(2), np.ones(3), np.ones(2), 0.0, "one length"),
            (np.zeros(2), np.array([1.0, np.nan]), np.ones(2), 0.0, "non-finite"),
            (np.zeros(2), np.array([1.0, 0.0]), np.ones(2), 0.0, "strictly above"),
            (np.zeros(2), np.ones(2), np.array([1.0, -1.0]), 0.0, "non-negative"),
            (np.zeros(2), np.ones(2), np.ones(2), -1.0, "minimum_gap_s"),
        ],
    )
    def test_bad_intervals_are_refused_by_both_schedulers(
        self, start: np.ndarray, end: np.ndarray, weight: np.ndarray, gap: float, message: str
    ) -> None:
        for scheduler in (schedule_passes, greedy_schedule_passes):
            with pytest.raises(DomainError, match=message):
                scheduler(start, end, weight, minimum_gap_s=gap)


class TestOnTheReferenceDay:
    """The module docstring's measurement, regenerated."""

    @pytest.mark.reference
    def test_the_three_stations_key_per_pass(
        self, castelldefels: StationLink, calar_alto: StationLink, tenerife: StationLink
    ) -> None:
        assert castelldefels.volume.key_bits.tolist() == list(REFERENCE_FINITE_BITS)
        assert calar_alto.volume.key_bits.tolist() == list(CALAR_ALTO_FINITE_BITS)
        assert tenerife.volume.key_bits.tolist() == list(TENERIFE_FINITE_BITS)
        separations = station_set().separation_km()
        assert float(separations[0, 1]) == pytest.approx(596.0, abs=0.5)
        assert float(separations[0, 2]) == pytest.approx(2213.8, abs=0.5)

    @pytest.mark.reference
    def test_sum_against_best_available(
        self, castelldefels: StationLink, calar_alto: StationLink, tenerife: StationLink
    ) -> None:
        stations = station_set()
        volumes = [castelldefels.volume, calar_alto.volume, tenerife.volume]
        summed = aggregate_stations(
            stations,
            volumes,
            availability=None,
            policy=AggregationPolicy.SUM,
            degradations=DegradationLog(),
        )
        log = DegradationLog()
        best = aggregate_stations(
            stations,
            volumes,
            availability=None,
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=log,
        )
        assert summed.total_bits == pytest.approx(1_052_607.0, abs=1.0)
        assert best.total_bits == pytest.approx(995_682.0, abs=1.0)
        assert summed.passes_selected == 10 and summed.conflicts_dropped == 0
        assert best.passes_selected == 4 and best.conflicts_dropped == 6
        # Calar Alto loses both live passes to Castelldefels' richer ones.
        assert best.station_bits.tolist() == pytest.approx([432_985.0, 0.0, 562_697.0], abs=1.0)
        assert [p.selected.tolist() for p in best.per_station] == [
            [True, False, True, False],
            [False, False, False, False],
            [True, True],
        ]
        entry = next(e for e in log if e.code == "multi_ogs.passes-dropped-by-conflict")
        assert entry.severity is Severity.INFO
        assert entry.details["dropped"] == 6
        assert entry.details["dropped_expected_bits"] == pytest.approx(56_925.0, abs=1.0)
        assert 1.0 - best.total_bits / summed.total_bits == pytest.approx(0.054, abs=1e-3)
        # Site diversity, under one terminal, against the reference station alone.
        assert best.total_bits / castelldefels.volume.total_bits == pytest.approx(2.30, abs=0.01)

    @pytest.mark.reference
    def test_the_invariants_between_policies_and_stations(
        self, castelldefels: StationLink, calar_alto: StationLink, tenerife: StationLink
    ) -> None:
        """SUM >= BEST_AVAILABLE >= any single station."""
        stations = station_set()
        volumes = [castelldefels.volume, calar_alto.volume, tenerife.volume]
        # Plain strings, as a scenario file would write them: the StrEnum accepts its values.
        summed = aggregate_stations(
            stations,
            volumes,
            availability=None,
            policy="sum",  # type: ignore[arg-type]
            degradations=DegradationLog(),
        )
        best = aggregate_stations(
            stations,
            volumes,
            availability=None,
            policy="best_available",  # type: ignore[arg-type]
            degradations=DegradationLog(),
        )
        assert summed.total_bits >= best.total_bits
        assert best.total_bits >= max(v.total_bits for v in volumes)
        assert summed.regime is KeyRegime.FINITE and best.regime is KeyRegime.FINITE
        assert summed.day_number.tolist() == [REFERENCE_DAY_NUMBER]
        assert float(summed.daily_bits[0]) == pytest.approx(summed.total_bits, abs=1e-9)
        assert float(best.daily_bits[0]) == pytest.approx(best.total_bits, abs=1e-9)

    @pytest.mark.reference
    def test_greedy_happens_to_agree_on_this_day(
        self, castelldefels: StationLink, calar_alto: StationLink, tenerife: StationLink
    ) -> None:
        """The conflicts are pairwise and the richer pass wins each, so greedy is not wrong here.

        Recorded so that the docstring's "the two agree on the reference day" is
        a measurement and not an assumption; the instance where they differ is
        in `TestTheSchedulerIsExact`.
        """
        volumes = [castelldefels.volume, calar_alto.volume, tenerife.volume]
        start = np.concatenate([v.samples.table.start_s for v in volumes])
        end = np.concatenate([v.samples.table.end_s for v in volumes])
        weight = np.concatenate([np.asarray(v.key_bits) for v in volumes])
        exact = schedule_passes(start, end, weight)
        greedy = greedy_schedule_passes(start, end, weight)
        assert float(weight[exact].sum()) == float(weight[greedy].sum())

    @pytest.mark.reference
    def test_conflicts_are_where_the_docstring_says(
        self, castelldefels: StationLink, calar_alto: StationLink, tenerife: StationLink
    ) -> None:
        """Calar Alto overlaps Castelldefels on every pass; Tenerife only the dead ones."""
        a, c, t = castelldefels.table, calar_alto.table, tenerife.table
        for i in range(4):
            assert c.start_s[i] < a.end_s[i] and a.start_s[i] < c.end_s[i]
        dead = [1, 3]
        for j in range(2):
            assert t.start_s[j] < a.end_s[dead[j]] and a.start_s[dead[j]] < t.end_s[j]
            assert not (t.start_s[j] < a.end_s[0] and a.start_s[0] < t.end_s[j])
            assert not (t.start_s[j] < a.end_s[2] and a.start_s[2] < t.end_s[j])


class TestAvailabilityIsAnExpectation:
    """``bits x availability`` beside the certified column, never instead of it."""

    @pytest.mark.physics
    def test_expected_bits_scale_and_certified_bits_do_not(
        self, castelldefels: StationLink, tenerife: StationLink
    ) -> None:
        stations = station_set("castelldefels", "tenerife_ogs")
        availability = [np.array([0.5, 1.0, 0.25, 1.0]), np.array([1.0, 0.0])]
        log = DegradationLog()
        result = aggregate_stations(
            stations,
            [castelldefels.volume, tenerife.volume],
            availability=availability,
            policy=AggregationPolicy.SUM,
            degradations=log,
        )
        assert result.station_bits.tolist() == pytest.approx([432_985.0, 562_697.0], abs=1.0)
        assert result.station_expected_bits.tolist() == pytest.approx(
            [0.5 * 190_581.0 + 0.25 * 242_404.0, 228_851.0], abs=1.0
        )
        assert result.total_expected_bits < result.total_bits
        assert float(result.daily_expected_bits[0]) == pytest.approx(
            result.total_expected_bits, abs=1e-9
        )
        entry = next(e for e in log if e.code == "multi_ogs.expected-bits-are-an-expectation")
        assert entry.severity is Severity.INFO
        assert "not a key anyone holds" in entry.message

    @pytest.mark.physics
    def test_the_schedule_weighs_expected_bits_not_certified_ones(
        self, castelldefels: StationLink, calar_alto: StationLink
    ) -> None:
        """A cloudy Castelldefels loses its pass to a clear Calar Alto despite more key."""
        stations = station_set("castelldefels", "calar_alto")
        volumes = [castelldefels.volume, calar_alto.volume]
        clear_everywhere = aggregate_stations(
            stations,
            volumes,
            availability=None,
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=DegradationLog(),
        )
        # Castelldefels keeps everything, its dead passes included: they end
        # before Calar Alto's dead ones and conflict with nothing live.
        assert clear_everywhere.per_station[0].selected.tolist() == [True, True, True, True]
        assert clear_everywhere.per_station[1].selected.tolist() == [False, False, False, False]
        cloudy_first = aggregate_stations(
            stations,
            volumes,
            availability=[np.array([0.1, 1.0, 1.0, 1.0]), np.ones(4)],
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=DegradationLog(),
        )
        # 0.1 x 190 581 = 19 058 < 47 108, so pass 1 goes to Calar Alto...
        assert cloudy_first.per_station[0].selected.tolist() == [False, True, True, True]
        assert cloudy_first.per_station[1].selected.tolist() == [True, False, False, False]
        # ...and the certified column reports what those passes certify when they happen.
        assert cloudy_first.station_bits.tolist() == pytest.approx([242_404.0, 47_108.0], abs=1.0)

    def test_no_availability_means_expected_equals_certified(
        self, castelldefels: StationLink
    ) -> None:
        stations = station_set("castelldefels")
        log = DegradationLog()
        result = aggregate_stations(
            stations,
            [castelldefels.volume],
            availability=None,
            policy=AggregationPolicy.SUM,
            degradations=log,
        )
        assert result.station_expected_bits.tolist() == result.station_bits.tolist()
        assert len(log) == 0
        assert result.per_station[0].availability is None

    def test_availability_has_no_default(self) -> None:
        parameter = inspect.signature(aggregate_stations).parameters["availability"]
        assert parameter.default is inspect.Parameter.empty
        assert inspect.signature(aggregate_stations).parameters["policy"].default is (
            inspect.Parameter.empty
        )


class TestTheSlewGap:
    """A gap can only remove passes; zero is the only non-invented default."""

    def test_the_default_is_zero(self) -> None:
        for function in (aggregate_stations, schedule_passes, greedy_schedule_passes):
            assert inspect.signature(function).parameters["minimum_gap_s"].default == 0.0

    @pytest.mark.physics
    def test_a_gap_longer_than_the_spacing_drops_the_poorer_neighbour(self) -> None:
        """Two synthetic stations with back-to-back passes 100 s apart."""
        east = synthetic_volume([(1000.0, 1500.0, 0), (5000.0, 5600.0, 0)], [10.0, 30.0])
        west = synthetic_volume([(1600.0, 2100.0, 0), (5700.0, 6200.0, 0)], [20.0, 5.0])
        stations = station_set("castelldefels", "calar_alto")
        no_gap = aggregate_stations(
            stations,
            [east, west],
            availability=None,
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=DegradationLog(),
        )
        with_gap = aggregate_stations(
            stations,
            [east, west],
            availability=None,
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=DegradationLog(),
            minimum_gap_s=120.0,
        )
        assert no_gap.total_bits == 65.0 and no_gap.conflicts_dropped == 0
        assert with_gap.total_bits == 50.0 and with_gap.conflicts_dropped == 2
        assert with_gap.minimum_gap_s == 120.0
        assert with_gap.total_bits <= no_gap.total_bits

    @pytest.mark.physics
    def test_under_sum_the_gap_is_carried_but_changes_nothing(self) -> None:
        east = synthetic_volume([(1000.0, 1500.0, 0)], [10.0])
        west = synthetic_volume([(1600.0, 2100.0, 0)], [20.0])
        stations = station_set("castelldefels", "calar_alto")
        result = aggregate_stations(
            stations,
            [east, west],
            availability=None,
            policy=AggregationPolicy.SUM,
            degradations=DegradationLog(),
            minimum_gap_s=1e4,
        )
        assert result.total_bits == 30.0 and result.conflicts_dropped == 0

    def test_a_negative_gap_is_refused(self, castelldefels: StationLink) -> None:
        with pytest.raises(DomainError, match="minimum_gap_s"):
            aggregate_stations(
                station_set("castelldefels"),
                [castelldefels.volume],
                availability=None,
                policy=AggregationPolicy.BEST_AVAILABLE,
                degradations=DegradationLog(),
                minimum_gap_s=-1.0,
            )


class TestTheStationSet:
    """Positions, separations, and the validator."""

    @pytest.mark.physics
    def test_separations_are_symmetric_and_the_docstring_distances(self) -> None:
        stations = station_set()
        matrix = stations.separation_km()
        assert matrix.shape == (3, 3)
        assert np.allclose(matrix, matrix.T)
        assert np.all(np.diagonal(matrix) == 0.0)
        assert stations.n == len(stations) == 3
        assert stations.index("tenerife_ogs") == 2
        assert "names=" in repr(stations)

    def test_an_unknown_name_is_refused(self) -> None:
        with pytest.raises(DomainError, match="no station named"):
            station_set().index("matera")

    @pytest.mark.parametrize(
        ("names", "lat", "lon", "alt", "message"),
        [
            ((), np.zeros(0), np.zeros(0), np.zeros(0), "at least one station"),
            (("a", "a"), np.zeros(2), np.zeros(2), np.zeros(2), "unique"),
            (("a", ""), np.zeros(2), np.zeros(2), np.zeros(2), "non-empty string"),
            (("a", "b"), np.zeros(3), np.zeros(2), np.zeros(2), "One coordinate per station"),
            (("a", "b"), np.array([0.0, np.nan]), np.zeros(2), np.zeros(2), "non-finite"),
            (("a", "b"), np.array([0.0, 2.0]), np.zeros(2), np.zeros(2), "never converted"),
        ],
    )
    def test_invalid_station_sets_are_refused(
        self,
        names: tuple[str, ...],
        lat: np.ndarray,
        lon: np.ndarray,
        alt: np.ndarray,
        message: str,
    ) -> None:
        with pytest.raises(DomainError, match=message):
            StationSet(names=names, latitude_rad=lat, longitude_rad=lon, altitude_km=alt)


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError`` of the aggregation and the containers."""

    def test_same_grid_compares_contents_not_identity(self) -> None:
        one = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, step_s=1.0)
        two = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, step_s=1.0)
        assert same_grid(one, one) and same_grid(one, two)
        assert not same_grid(one, TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, step_s=2.0))
        assert not same_grid(one, TimeGrid(epoch_jd=2460676.5, t_s=one.t_s + 0.5))

    def test_a_non_station_set_is_refused(self, castelldefels: StationLink) -> None:
        with pytest.raises(DomainError, match="stations must be a StationSet"):
            aggregate_stations(
                ("castelldefels",),  # type: ignore[arg-type]
                [castelldefels.volume],
                availability=None,
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_the_wrong_number_of_volumes_is_refused(self, castelldefels: StationLink) -> None:
        with pytest.raises(DomainError, match="one PassKeyVolume per station"):
            aggregate_stations(
                station_set("castelldefels", "calar_alto"),
                [castelldefels.volume],
                availability=None,
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_a_non_volume_is_refused(self, castelldefels: StationLink) -> None:
        with pytest.raises(DomainError, match="must be a PassKeyVolume"):
            aggregate_stations(
                station_set("castelldefels"),
                [castelldefels.table],  # type: ignore[list-item]
                availability=None,
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_a_partial_availability_list_is_refused(
        self, castelldefels: StationLink, tenerife: StationLink
    ) -> None:
        with pytest.raises(DomainError, match="one array per station"):
            aggregate_stations(
                station_set("castelldefels", "tenerife_ogs"),
                [castelldefels.volume, tenerife.volume],
                availability=[np.ones(4)],
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_volumes_on_different_grids_are_refused(self, castelldefels: StationLink) -> None:
        other = synthetic_volume(
            [(1000.0, 1500.0, 0)],
            [1.0],
            grid=TimeGrid.uniform(epoch_jd=2460677.5, duration_s=86_400.0, step_s=1.0),
        )
        with pytest.raises(DomainError, match="different time grid"):
            aggregate_stations(
                station_set("castelldefels", "calar_alto"),
                [castelldefels.volume, other],
                availability=None,
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_volumes_in_different_regimes_are_refused(self, castelldefels: StationLink) -> None:
        other = synthetic_volume([(1000.0, 1500.0, 0)], [1.0])
        with pytest.raises(DomainError, match="not a total of anything"):
            aggregate_stations(
                station_set("castelldefels", "calar_alto"),
                [castelldefels.volume, other],
                availability=None,
                policy=AggregationPolicy.SUM,
                degradations=DegradationLog(),
            )

    def test_two_satellites_over_one_station_at_once_is_refused(self) -> None:
        """The ground terminal's conflict, which is out of scope and named as such."""
        crowded = synthetic_volume([(1000.0, 1500.0, 0), (1200.0, 1700.0, 1)], [1.0, 2.0])
        with pytest.raises(DomainError, match="GROUND terminal"):
            aggregate_stations(
                station_set("castelldefels"),
                [crowded],
                availability=None,
                policy=AggregationPolicy.BEST_AVAILABLE,
                degradations=DegradationLog(),
            )

    @pytest.mark.physics
    def test_two_satellites_are_scheduled_independently(self) -> None:
        """Passes of different satellites do not conflict with each other."""
        east = synthetic_volume([(1000.0, 1500.0, 0)], [10.0])
        west = synthetic_volume([(1100.0, 1600.0, 1), (5000.0, 5500.0, 0)], [20.0, 5.0])
        result = aggregate_stations(
            station_set("castelldefels", "calar_alto"),
            [east, west],
            availability=None,
            policy=AggregationPolicy.BEST_AVAILABLE,
            degradations=DegradationLog(),
        )
        assert result.total_bits == 35.0 and result.conflicts_dropped == 0

    def test_bad_availability_arrays_are_refused(self, castelldefels: StationLink) -> None:
        with pytest.raises(DomainError, match="One probability per pass"):
            StationPassKeys(
                station="x",
                volume=castelldefels.volume,
                availability=np.ones(3),
                selected=np.ones(4, dtype=bool),
            )
        with pytest.raises(DomainError, match="must lie in \\[0, 1\\]"):
            StationPassKeys(
                station="x",
                volume=castelldefels.volume,
                availability=np.array([0.5, 1.5, 0.5, 0.5]),
                selected=np.ones(4, dtype=bool),
            )
        with pytest.raises(DomainError, match="boolean mask"):
            StationPassKeys(
                station="x",
                volume=castelldefels.volume,
                availability=None,
                selected=np.ones(4),  # type: ignore[arg-type]
            )
        with pytest.raises(DomainError, match="volume must be a PassKeyVolume"):
            StationPassKeys(
                station="x",
                volume=castelldefels.table,  # type: ignore[arg-type]
                availability=None,
                selected=np.ones(4, dtype=bool),
            )

    @pytest.mark.physics
    def test_the_per_station_record_reports_its_selection(self, castelldefels: StationLink) -> None:
        record = StationPassKeys(
            station="castelldefels",
            volume=castelldefels.volume,
            availability=np.array([0.5, 0.5, 0.5, 0.5]),
            selected=np.array([True, True, False, False]),
        )
        assert record.scheduled_bits == pytest.approx(190_581.0)
        assert record.scheduled_expected_bits == pytest.approx(0.5 * 190_581.0)
        assert "selected=2" in repr(record)

    @staticmethod
    def _fields(result: MultiStationKeyVolume) -> dict[str, object]:
        return {
            "stations": result.stations,
            "policy": result.policy,
            "per_station": result.per_station,
            "station_bits": np.array(result.station_bits),
            "station_expected_bits": np.array(result.station_expected_bits),
            "day_number": np.array(result.day_number),
            "daily_bits": np.array(result.daily_bits),
            "daily_expected_bits": np.array(result.daily_expected_bits),
            "conflicts_dropped": result.conflicts_dropped,
            "minimum_gap_s": result.minimum_gap_s,
            "regime": result.regime,
        }

    @pytest.fixture
    def result(self, castelldefels: StationLink) -> MultiStationKeyVolume:
        return aggregate_stations(
            station_set("castelldefels"),
            [castelldefels.volume],
            availability=None,
            policy=AggregationPolicy.SUM,
            degradations=DegradationLog(),
        )

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("stations", "castelldefels", "stations must be a StationSet"),
            ("per_station", (), "one StationPassKeys per station"),
            ("station_bits", np.zeros(2), "there are 1 stations"),
            ("station_bits", np.array([-1.0]), "finite and non-negative"),
            ("day_number", np.array([[1]]), "strictly ascending"),
            ("day_number", np.array([3, 2]), "strictly ascending"),
            ("daily_bits", np.zeros(2), "but day_number has"),
            ("daily_expected_bits", np.array([np.inf]), "finite and non-negative"),
            ("conflicts_dropped", -1, "cannot be negative"),
            ("minimum_gap_s", -1.0, "minimum_gap_s"),
        ],
    )
    def test_invalid_results_are_refused(
        self, result: MultiStationKeyVolume, field: str, value: object, message: str
    ) -> None:
        fields = self._fields(result)
        fields[field] = value
        with pytest.raises(DomainError, match=message):
            MultiStationKeyVolume(**fields)  # type: ignore[arg-type]

    @pytest.mark.physics
    def test_the_repr_names_the_policy_and_the_counts(self, result: MultiStationKeyVolume) -> None:
        assert "sum" in repr(result)
        assert "passes_selected=4" in repr(result)
        assert "conflicts_dropped=0" in repr(result)
