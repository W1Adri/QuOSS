"""Tests for `quoss.system.passes`.

Organised by the claim each block defends, not by the function it calls.

- ``TestTheRunSegmentation`` — **V1**. That a contiguous stretch above the mask
  is found, once, whole, and separately per satellite. The oracle is a
  deliberately slow Python loop over the mask, because the vectorised
  two-``nonzero`` version is the part with nowhere for an off-by-one to show.
- ``TestTheRefinedBoundaries`` — **V1**, against an exactly solvable case. On a
  synthetic linear elevation ramp the crossing time is known in closed form and
  the refinement must return it to machine precision; on the reference day it
  must recover the 3.79 s that the raw samples drop.
- ``TestTheCulmination`` — **V1** and **V4-free**. The three-point vertex is
  checked against an exact parabola (where it must be exact), against an exact
  parabola on a *non-uniform* grid (where the equal-spacing formula would not
  be), and against the 1 s geometry as ground truth for coarse grids — which is
  the measurement the module docstring's 0.029/0.51 degree figures come from.
- ``TestTheDwellTimes`` — **V1**. The identity the midpoint rule was chosen for:
  the dwell times of a pass sum to its refined duration exactly, on uniform and
  non-uniform grids alike, and the trapezoid rule on raw samples does not.
- ``TestTruncation`` — that a fragment is flagged and logged rather than reported
  as a short pass, with the size of the lie measured.
- ``TestTheGridResolutionGuard`` — that the warning fires on the sample count and
  not on an error estimate. The table it is calibrated against is regenerated in
  ``test_key_volume.py``, where bits live.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
- ``TestTheModuleSurface`` — that the mask has no default, that this module
  imports nothing from ``channel`` or ``qkd``, and that it does not filter on key.
"""

from __future__ import annotations

import ast
import inspect
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pytest

from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.types import BoolArray, TimeGrid
from quoss.orbits.geometry import LookAngles
from quoss.system import passes as passes_module
from quoss.system.passes import (
    MINIMUM_SAMPLES_PER_PASS,
    PassSamples,
    PassTable,
    find_passes,
)

from .reference import EPOCH_JD, Link, geometry, link


@pytest.fixture(scope="module")
def reference_link() -> Link:
    """Return the reference day at a 10 degree mask."""
    return link()


@pytest.fixture(scope="module")
def reference_table(reference_link: Link) -> PassTable:
    """Return the reference day's four passes."""
    return reference_link.table


def angles_from_elevation(elevation_rad: Sequence[float] | np.ndarray) -> LookAngles:
    """Build a LookAngles carrying only the elevation this test cares about.

    The other four fields are filled with plausible constants: `find_passes`
    reads none of them, and a test that had to invent a consistent range and
    range-rate would be testing `look_angles` instead.
    """
    elevation = np.atleast_2d(np.asarray(elevation_rad, dtype=np.float64))
    filler = np.full_like(elevation, 1000.0)
    return LookAngles(
        elevation_rad=elevation,
        azimuth_rad=np.zeros_like(elevation),
        range_km=filler,
        range_rate_km_s=np.zeros_like(elevation),
        point_ahead_angle_rad=np.zeros_like(elevation),
    )


def runs_by_loop(mask: BoolArray) -> list[tuple[int, int, int]]:
    """Return `(satellite, first, last)` of every True run, by explicit iteration.

    The independent oracle for `_runs_above`. Written as the obvious nested loop
    precisely because it has no cleverness to be wrong in.
    """
    found: list[tuple[int, int, int]] = []
    for s in range(mask.shape[0]):
        start: int | None = None
        for i in range(mask.shape[1]):
            if mask[s, i] and start is None:
                start = i
            elif not mask[s, i] and start is not None:
                found.append((s, start, i - 1))
                start = None
        if start is not None:
            found.append((s, start, mask.shape[1] - 1))
    return found


def table_from_elevation(
    elevation_deg: Sequence[float] | np.ndarray,
    *,
    mask_deg: float,
    step_s: float = 1.0,
    t_s: np.ndarray | None = None,
    degradations: DegradationLog | None = None,
    minimum_duration_s: float = 0.0,
) -> PassTable:
    """Segment a hand-written elevation curve."""
    elevation = np.atleast_2d(np.asarray(elevation_deg, dtype=np.float64))
    axis = t_s if t_s is not None else np.arange(elevation.shape[1], dtype=np.float64) * step_s
    grid = TimeGrid(epoch_jd=EPOCH_JD, t_s=np.asarray(axis, dtype=np.float64))
    return find_passes(
        angles_from_elevation(np.deg2rad(elevation)),
        grid=grid,
        minimum_elevation_rad=float(np.deg2rad(mask_deg)),
        degradations=degradations if degradations is not None else DegradationLog(),
        minimum_duration_s=minimum_duration_s,
    )


class TestTheRunSegmentation:
    """**V1.** Contiguous stretches above the mask, found once and whole."""

    @pytest.mark.parametrize(
        "pattern",
        [
            [0, 0, 1, 1, 1, 0, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 1, 1],
            [0, 0, 0],
            [1],
            [0, 1, 0, 1, 0, 1, 0],
        ],
    )
    @pytest.mark.physics
    def test_against_an_explicit_loop(self, pattern: list[int]) -> None:
        mask = np.atleast_2d(np.asarray(pattern, dtype=bool))
        expected = runs_by_loop(mask)
        satellite, first, last = passes_module._runs_above(mask)
        assert list(zip(satellite.tolist(), first.tolist(), last.tolist(), strict=True)) == expected

    @pytest.mark.physics
    def test_satellites_are_segmented_independently(self) -> None:
        """Two satellites with interleaved passes must not be merged or reordered."""
        mask = np.array(
            [
                [0, 1, 1, 0, 0, 0, 1, 0],
                [1, 0, 0, 1, 1, 1, 0, 0],
            ],
            dtype=bool,
        )
        satellite, first, last = passes_module._runs_above(mask)
        assert satellite.tolist() == [0, 0, 1, 1]
        assert first.tolist() == [1, 6, 0, 3]
        assert last.tolist() == [2, 6, 0, 5]

    @pytest.mark.physics
    def test_a_mask_nothing_reaches_gives_an_empty_table_and_says_so(self) -> None:
        log = DegradationLog()
        table = table_from_elevation([1.0, 2.0, 3.0], mask_deg=10.0, degradations=log)
        assert table.n_passes == 0
        assert len(table) == 0
        assert [entry.code for entry in log] == ["passes.none-found"]
        assert log.entries[0].details["maximum_elevation_deg"] == pytest.approx(3.0)
        assert not log.has_degraded

    @pytest.mark.physics
    def test_the_reference_day_holds_four_passes_at_ten_degrees(
        self, reference_table: PassTable
    ) -> None:
        assert reference_table.n_passes == 4
        assert reference_table.satellite_index.tolist() == [0, 0, 0, 0]
        assert np.all(np.diff(reference_table.first_index) > 0)

    @pytest.mark.physics
    def test_raising_the_mask_can_only_shrink_or_split_passes(self) -> None:
        """A stricter mask never adds usable seconds. The monotonicity of a threshold."""
        previous = np.inf
        for mask_deg in (5.0, 10.0, 15.0, 20.0, 30.0):
            table = link(mask_deg).table
            total = float(table.duration_s.sum())
            assert total <= previous
            previous = total


class TestTheRefinedBoundaries:
    """**V1** against a case with a closed-form answer, then on the real geometry."""

    @pytest.mark.physics
    def test_a_linear_ramp_crossing_is_exact(self) -> None:
        """Elevation rising 1 deg/s crosses a 10.5 deg mask at t = 10.5 s, exactly.

        The refinement interpolates linearly, so on a linear curve it is not an
        approximation at all and the only thing that can be wrong is the
        arithmetic — which is what this pins.
        """
        elevation = np.arange(0.0, 21.0, 1.0)  # deg, one sample per second
        table = table_from_elevation(elevation, mask_deg=10.5)
        assert table.n_passes == 1
        assert float(table.start_s[0]) == pytest.approx(10.5, abs=1e-12)
        # The curve never comes back down, so the pass is truncated at the end.
        assert bool(table.truncated_end[0])
        assert float(table.end_s[0]) == 20.0

    @pytest.mark.physics
    def test_a_symmetric_triangle_crosses_symmetrically(self) -> None:
        elevation = np.concatenate([np.arange(0.0, 21.0, 1.0), np.arange(19.0, -1.0, -1.0)])
        table = table_from_elevation(elevation, mask_deg=10.5)
        assert table.n_passes == 1
        assert float(table.start_s[0]) == pytest.approx(10.5, abs=1e-12)
        assert float(table.end_s[0]) == pytest.approx(29.5, abs=1e-12)
        assert float(table.duration_s[0]) == pytest.approx(19.0, abs=1e-12)

    @pytest.mark.physics
    def test_the_crossing_is_bracketed_by_the_two_samples(self, reference_table: PassTable) -> None:
        """A refined boundary must land inside the step it was interpolated across."""
        t = reference_table.grid.t_s
        first, last = reference_table.first_index, reference_table.last_index
        assert np.all(reference_table.start_s <= t[first] + 1e-12)
        assert np.all(reference_table.start_s >= t[np.maximum(first - 1, 0)] - 1e-12)
        assert np.all(reference_table.end_s >= t[last] - 1e-12)
        assert np.all(reference_table.end_s <= t[np.minimum(last + 1, t.size - 1)] + 1e-12)

    @pytest.mark.physics
    def test_refinement_recovers_the_seconds_the_raw_samples_drop(
        self, reference_table: PassTable
    ) -> None:
        """The 0.21 % of the module docstring, measured rather than cited."""
        t = reference_table.grid.t_s
        raw = float((t[reference_table.last_index] - t[reference_table.first_index]).sum())
        refined = float(reference_table.duration_s.sum())
        assert raw == pytest.approx(1796.0, abs=1e-9)
        assert refined == pytest.approx(1799.7857, abs=1e-3)
        assert refined - raw == pytest.approx(3.7857, abs=1e-3)
        assert (refined - raw) / refined == pytest.approx(0.00210, abs=1e-5)

    @pytest.mark.physics
    def test_the_refined_window_always_contains_the_sampled_one(self) -> None:
        """True for every mask, not just the reference one: refinement only widens."""
        for mask_deg in (5.0, 10.0, 20.0, 30.0):
            table = link(mask_deg).table
            t = table.grid.t_s
            interior_start = ~table.truncated_start
            interior_end = ~table.truncated_end
            assert np.all(
                table.start_s[interior_start] < t[table.first_index][interior_start] + 1e-12
            )
            assert np.all(table.end_s[interior_end] > t[table.last_index][interior_end] - 1e-12)


class TestTheCulmination:
    """**V1.** The three-point vertex, where it must be exact and where it helps."""

    @pytest.mark.physics
    def test_an_exact_parabola_is_recovered_exactly(self) -> None:
        """Elevation that *is* a parabola leaves the fit nothing to approximate."""
        t = np.arange(0.0, 41.0, 1.0)
        peak_t, peak_deg = 20.37, 55.0
        elevation = peak_deg - 0.05 * (t - peak_t) ** 2
        table = table_from_elevation(elevation, mask_deg=10.0, t_s=t)
        assert table.n_passes == 1
        assert float(table.culmination_s[0]) == pytest.approx(peak_t, abs=1e-9)
        assert float(np.rad2deg(table.culmination_elevation_rad[0])) == pytest.approx(
            peak_deg, abs=1e-9
        )

    @pytest.mark.physics
    def test_an_exact_parabola_on_a_non_uniform_grid_is_also_exact(self) -> None:
        """The reason the vertex is written in Newton form and not as ``x1 + h(...)``.

        The equal-spacing formula would be wrong here, and wrong in a way that
        looks like a small modelling error rather than a bug.
        """
        t = np.array([0.0, 3.0, 7.0, 12.0, 18.0, 21.0, 26.0, 30.0, 37.0, 41.0], dtype=np.float64)
        peak_t, peak_deg = 19.4, 48.0
        elevation = peak_deg - 0.06 * (t - peak_t) ** 2
        table = table_from_elevation(elevation, mask_deg=10.0, t_s=t)
        assert table.n_passes == 1
        assert not table.grid.is_uniform
        assert float(table.culmination_s[0]) == pytest.approx(peak_t, abs=1e-9)
        assert float(np.rad2deg(table.culmination_elevation_rad[0])) == pytest.approx(
            peak_deg, abs=1e-9
        )

    @pytest.mark.physics
    def test_the_refined_peak_is_never_below_the_sampled_one(self) -> None:
        for mask_deg in (5.0, 10.0, 20.0):
            table = link(mask_deg).table
            assert np.all(
                table.culmination_elevation_rad >= table.sampled_culmination_elevation_rad - 1e-15
            )

    @pytest.mark.physics
    def test_the_peak_stays_inside_the_pass(self) -> None:
        for mask_deg in (5.0, 10.0, 20.0):
            table = link(mask_deg).table
            assert np.all(table.culmination_s >= table.start_s)
            assert np.all(table.culmination_s <= table.end_s)

    @pytest.mark.physics
    def test_a_peak_at_the_edge_of_the_grid_falls_back_to_the_sample(self) -> None:
        """No interior bracket means no vertex to fit, so the discrete maximum stands."""
        elevation = np.array([40.0, 30.0, 20.0, 11.0])  # highest sample is the first
        table = table_from_elevation(elevation, mask_deg=10.0)
        assert table.n_passes == 1
        assert bool(table.truncated_start[0])
        assert float(table.culmination_s[0]) == 0.0
        assert float(np.rad2deg(table.culmination_elevation_rad[0])) == pytest.approx(40.0)

    @pytest.mark.physics
    def test_a_flat_top_has_no_vertex_and_keeps_the_sample(self) -> None:
        """Three equal samples give ``b_2 = 0``: a straight line has no maximum."""
        elevation = np.array([5.0, 20.0, 30.0, 30.0, 30.0, 20.0, 5.0])
        table = table_from_elevation(elevation, mask_deg=10.0)
        assert table.n_passes == 1
        assert float(np.rad2deg(table.culmination_elevation_rad[0])) == pytest.approx(30.0)
        assert float(table.culmination_s[0]) == 2.0

    @pytest.mark.reference
    @pytest.mark.parametrize(
        ("step_s", "discrete_error_deg", "parabolic_error_deg"),
        [(10.0, 0.0288, 0.0006), (30.0, 0.5075, 0.0810)],
    )
    def test_the_parabola_beats_the_discrete_peak_on_a_coarse_grid(
        self, step_s: float, discrete_error_deg: float, parabolic_error_deg: float
    ) -> None:
        """The module docstring's 0.029/0.51 and 0.0006/0.075 degrees, regenerated.

        Ground truth is the refined peak of the 1 s geometry, which the two
        preceding tests have established is exact on a parabola and which is
        100 times finer than the grid under test.
        """
        truth = link(step_s=1.0).table.culmination_elevation_rad
        coarse = link(step_s=step_s).table
        assert coarse.n_passes == truth.size
        discrete = np.rad2deg(truth - coarse.sampled_culmination_elevation_rad)
        parabolic = np.rad2deg(truth - coarse.culmination_elevation_rad)
        assert float(discrete.max()) == pytest.approx(discrete_error_deg, abs=5e-4)
        assert float(parabolic.max()) == pytest.approx(parabolic_error_deg, abs=5e-4)
        # The refinement is worth at least a factor of six, which is the claim.
        assert float(discrete.max()) / float(parabolic.max()) > 6.0


class TestTheDwellTimes:
    """**V1.** The identity the midpoint rule was chosen for."""

    @pytest.mark.physics
    def test_the_dwell_times_of_a_pass_sum_to_its_duration_exactly(
        self, reference_link: Link
    ) -> None:
        samples = reference_link.samples
        recovered = samples.segment_sum(np.asarray(samples.dwell_s))
        assert np.allclose(recovered, reference_link.table.duration_s, rtol=0.0, atol=1e-9)

    @pytest.mark.physics
    def test_that_identity_holds_on_a_non_uniform_grid(self) -> None:
        """Where the trapezoid rule's equal half-steps would stop being right."""
        t = np.array([0.0, 1.0, 3.0, 6.0, 10.0, 15.0, 17.0, 18.0], dtype=np.float64)
        elevation = np.array([2.0, 14.0, 30.0, 44.0, 38.0, 21.0, 13.0, 4.0])
        table = table_from_elevation(elevation, mask_deg=10.0, t_s=t)
        samples = table.samples()
        assert not table.grid.is_uniform
        assert float(samples.segment_sum(np.asarray(samples.dwell_s))[0]) == pytest.approx(
            float(table.duration_s[0]), abs=1e-12
        )

    @pytest.mark.physics
    def test_interior_dwell_times_are_the_grid_step(self, reference_link: Link) -> None:
        """Only the two edge samples differ from the step; everything between is it."""
        samples = reference_link.samples
        step = reference_link.grid.step_s
        interior = np.ones(samples.size, dtype=bool)
        for index in range(reference_link.table.n_passes):
            entries = np.flatnonzero(samples.pass_index == index)
            interior[entries[0]] = False
            interior[entries[-1]] = False
        assert np.allclose(samples.dwell_s[interior], step, rtol=0.0, atol=1e-12)

    @pytest.mark.physics
    def test_every_dwell_time_is_positive(self) -> None:
        for mask_deg in (5.0, 10.0, 20.0, 30.0):
            assert np.all(link(mask_deg).samples.dwell_s > 0.0)

    @pytest.mark.physics
    def test_the_trapezoid_rule_on_raw_samples_loses_the_edges(self, reference_link: Link) -> None:
        """The comparison that decides the quadrature, stated as a number.

        Trapezoid weights built from the samples integrate over
        ``[t_first, t_last]`` and cannot be told where the pass really started.
        """
        table = reference_link.table
        step = table.grid.step_s
        trapezoid = (table.n_samples - 1) * step
        midpoint = reference_link.samples.segment_sum(np.asarray(reference_link.samples.dwell_s))
        assert float(trapezoid.sum()) == pytest.approx(1796.0, abs=1e-9)
        assert np.all(midpoint > trapezoid)
        assert float((midpoint - trapezoid).sum()) == pytest.approx(3.7857, abs=1e-3)

    @pytest.mark.physics
    def test_a_single_sample_pass_owns_the_whole_refined_window(self) -> None:
        """The degenerate case both edge branches fire on at once."""
        elevation = np.array([5.0, 12.0, 5.0])
        table = table_from_elevation(elevation, mask_deg=10.0)
        samples = table.samples()
        assert table.n_samples.tolist() == [1]
        assert samples.size == 1
        assert float(samples.dwell_s[0]) == pytest.approx(float(table.duration_s[0]), abs=1e-12)

    @pytest.mark.physics
    def test_the_samples_are_ordered_by_pass_then_by_time(self, reference_link: Link) -> None:
        samples = reference_link.samples
        assert np.all(np.diff(samples.pass_index) >= 0)
        for index in range(reference_link.table.n_passes):
            entries = samples.sample_index[samples.pass_index == index]
            assert np.all(np.diff(entries) == 1)
            assert entries[0] == reference_link.table.first_index[index]
            assert entries[-1] == reference_link.table.last_index[index]

    @pytest.mark.physics
    def test_a_segment_sum_of_the_wrong_length_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="one value per entry"):
            reference_link.samples.segment_sum(np.zeros(3))


class TestTruncation:
    """A fragment clipped by the grid is flagged and logged, never reported as a pass."""

    @pytest.mark.physics
    def test_a_window_opening_mid_pass_is_flagged_at_the_start(self) -> None:
        log = DegradationLog()
        grid, angles = passes_module._reference_window(25_900.0, 600.0)
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
        )
        assert bool(table.truncated_start[0])
        assert bool(table.is_truncated[0])
        codes = [entry.code for entry in log]
        assert "passes.truncated-by-grid" in codes
        truncation = next(e for e in log if e.code == "passes.truncated-by-grid")
        assert truncation.severity is Severity.WARNING
        assert truncation.details["truncated_at_start"] == 1

    @pytest.mark.physics
    def test_a_fragment_understates_the_pass_it_came_from(self) -> None:
        """The size of the lie a truncation flag is there to prevent."""
        whole = link().table
        grid, angles = passes_module._reference_window(25_900.0, 600.0)
        fragment = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=DegradationLog(),
        )
        assert float(fragment.duration_s[0]) < float(whole.duration_s[0])
        # Roughly two thirds of the real pass, and nothing in the number says so.
        assert float(fragment.duration_s[0]) / float(whole.duration_s[0]) < 0.8

    @pytest.mark.physics
    def test_a_pass_open_at_both_ends_is_flagged_twice(self) -> None:
        log = DegradationLog()
        table = table_from_elevation([20.0, 30.0, 25.0], mask_deg=10.0, degradations=log)
        assert bool(table.truncated_start[0]) and bool(table.truncated_end[0])
        details = next(e for e in log if e.code == "passes.truncated-by-grid").details
        assert details["truncated_at_start"] == 1
        assert details["truncated_at_end"] == 1

    @pytest.mark.physics
    def test_an_untruncated_day_logs_nothing(self, reference_table: PassTable) -> None:
        log = DegradationLog()
        angles, grid = geometry()
        find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
        )
        assert len(log) == 0
        assert not np.any(reference_table.is_truncated)


class TestTheMinimumDurationFilter:
    """Dropping a short pass is allowed; dropping it quietly is not."""

    @pytest.mark.physics
    def test_the_default_drops_nothing(self, reference_table: PassTable) -> None:
        log = DegradationLog()
        angles, grid = geometry()
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
        )
        assert table.n_passes == reference_table.n_passes
        assert not any(e.code == "passes.below-minimum-duration" for e in log)

    @pytest.mark.physics
    def test_a_floor_drops_the_short_passes_and_names_them(self) -> None:
        log = DegradationLog()
        angles, grid = geometry()
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
            minimum_duration_s=400.0,
        )
        assert table.n_passes == 2
        entry = next(e for e in log if e.code == "passes.below-minimum-duration")
        assert entry.severity is Severity.WARNING
        assert entry.details["dropped"] == 2
        assert len(entry.details["dropped_durations_s"]) == 2

    @pytest.mark.physics
    def test_a_floor_above_every_pass_empties_the_table(self) -> None:
        log = DegradationLog()
        angles, grid = geometry()
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
            minimum_duration_s=10_000.0,
        )
        assert table.n_passes == 0
        assert any(e.code == "passes.below-minimum-duration" for e in log)


class TestTheGridResolutionGuard:
    """The warning fires on the sample count, which cannot be small by coincidence."""

    @pytest.mark.physics
    def test_a_fine_grid_is_silent(self) -> None:
        log = DegradationLog()
        angles, grid = geometry()
        find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
        )
        assert not any(e.code == "passes.grid-too-coarse" for e in log)

    @pytest.mark.physics
    def test_a_coarse_grid_warns_and_says_how_short(self) -> None:
        log = DegradationLog()
        angles, grid = geometry(step_s=60.0)
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
        )
        entry = next(e for e in log if e.code == "passes.grid-too-coarse")
        assert entry.severity is Severity.WARNING
        assert entry.details["shortest_pass_samples"] == int(table.n_samples.min())
        assert entry.details["shortest_pass_samples"] < MINIMUM_SAMPLES_PER_PASS
        assert entry.details["required_samples"] == MINIMUM_SAMPLES_PER_PASS

    @pytest.mark.physics
    def test_the_threshold_is_exactly_where_the_warning_turns_on(self) -> None:
        """Built from the sample count, so it must fire at N-1 and not at N."""
        below = np.concatenate([[5.0], np.full(MINIMUM_SAMPLES_PER_PASS - 1, 30.0), [5.0]])
        at = np.concatenate([[5.0], np.full(MINIMUM_SAMPLES_PER_PASS, 30.0), [5.0]])
        log_below, log_at = DegradationLog(), DegradationLog()
        table_from_elevation(below, mask_deg=10.0, degradations=log_below)
        table_from_elevation(at, mask_deg=10.0, degradations=log_at)
        assert any(e.code == "passes.grid-too-coarse" for e in log_below)
        assert not any(e.code == "passes.grid-too-coarse" for e in log_at)


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError``, because a validator with no test is a comment."""

    @staticmethod
    def _valid_table_fields(table: PassTable) -> dict[str, object]:
        return {
            name: np.array(getattr(table, name))
            for name in PassTable._INT_COLUMNS + PassTable._FLOAT_COLUMNS + PassTable._BOOL_COLUMNS
        } | {"minimum_elevation_rad": table.minimum_elevation_rad, "grid": table.grid}

    @pytest.mark.parametrize("mask", [0.0, -0.1, np.pi / 2, np.pi, np.nan, np.inf])
    def test_an_unusable_mask_is_refused(self, mask: float) -> None:
        with pytest.raises(DomainError, match="minimum_elevation_rad"):
            table_from_elevation([20.0], mask_deg=np.rad2deg(mask))

    def test_a_grid_of_the_wrong_length_is_refused(self) -> None:
        angles, _ = geometry()
        with pytest.raises(DomainError, match="same axis"):
            find_passes(
                angles,
                grid=TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=10.0, step_s=1.0),
                minimum_elevation_rad=0.17,
                degradations=DegradationLog(),
            )

    def test_a_non_timegrid_is_refused(self) -> None:
        angles, _ = geometry()
        with pytest.raises(DomainError, match="grid must be a TimeGrid"):
            find_passes(
                angles,
                grid="a day",  # type: ignore[arg-type]
                minimum_elevation_rad=0.17,
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize("floor", [-1.0, np.nan, -np.inf])
    def test_a_negative_duration_floor_is_refused(self, floor: float) -> None:
        with pytest.raises(DomainError, match="minimum_duration_s"):
            table_from_elevation([20.0, 30.0], mask_deg=10.0, minimum_duration_s=floor)

    def test_ragged_columns_are_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        fields["start_s"] = np.zeros(3)
        with pytest.raises(DomainError, match="every column describes the same passes"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_two_dimensional_columns_are_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        for name in PassTable._INT_COLUMNS + PassTable._FLOAT_COLUMNS + PassTable._BOOL_COLUMNS:
            fields[name] = np.asarray(fields[name]).reshape(2, 2)
        with pytest.raises(DomainError, match="columns must be 1-D"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_a_non_finite_column_is_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        broken = np.array(reference_table.start_s)
        broken[0] = np.nan
        fields["start_s"] = broken
        with pytest.raises(DomainError, match="non-finite"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_an_index_outside_the_grid_is_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        broken = np.array(reference_table.last_index)
        broken[-1] = reference_table.grid.n
        fields["last_index"] = broken
        with pytest.raises(DomainError, match="must index the grid"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_an_inverted_sample_range_is_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        fields["last_index"] = np.array(reference_table.first_index) - 1
        with pytest.raises(DomainError, match="last_index must be at least first_index"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_a_zero_length_pass_is_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        fields["end_s"] = np.array(reference_table.start_s)
        with pytest.raises(DomainError, match="end_s must be strictly above start_s"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_overlapping_passes_of_one_satellite_are_refused(
        self, reference_table: PassTable
    ) -> None:
        fields = self._valid_table_fields(reference_table)
        fields["first_index"] = np.zeros(reference_table.n_passes, dtype=np.int64)
        with pytest.raises(DomainError, match="strictly increasing time order"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_a_non_timegrid_inside_the_table_is_refused(self, reference_table: PassTable) -> None:
        fields = self._valid_table_fields(reference_table)
        fields["grid"] = None
        with pytest.raises(DomainError, match="grid must be a TimeGrid"):
            PassTable(**fields)  # type: ignore[arg-type]

    def test_select_refuses_a_non_mask(self, reference_table: PassTable) -> None:
        with pytest.raises(DomainError, match="boolean mask"):
            reference_table.select(np.array([0, 1, 2, 3]))
        with pytest.raises(DomainError, match="boolean mask"):
            reference_table.select(np.ones(2, dtype=bool))

    def test_select_keeps_the_mask_and_the_grid(self, reference_table: PassTable) -> None:
        kept = reference_table.select(np.array([True, False, True, False]))
        assert kept.n_passes == 2
        assert kept.minimum_elevation_rad == reference_table.minimum_elevation_rad
        assert kept.grid is reference_table.grid

    def test_pass_samples_refuses_a_foreign_table(self, reference_link: Link) -> None:
        samples = reference_link.samples
        with pytest.raises(DomainError, match="table must be a PassTable"):
            PassSamples(
                pass_index=samples.pass_index,
                satellite_index=samples.satellite_index,
                sample_index=samples.sample_index,
                dwell_s=np.asarray(samples.dwell_s),
                table=None,  # type: ignore[arg-type]
            )

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("dwell_s", "zeros_short", "same shape"),
            ("dwell_s", "negative", "strictly positive"),
            ("pass_index", "out_of_range", "must index the table"),
            ("pass_index", "unsorted", "non-decreasing"),
        ],
    )
    def test_pass_samples_validates_its_columns(
        self, reference_link: Link, field: str, value: str, message: str
    ) -> None:
        samples = reference_link.samples
        fields: dict[str, object] = {
            "pass_index": np.array(samples.pass_index),
            "satellite_index": np.array(samples.satellite_index),
            "sample_index": np.array(samples.sample_index),
            "dwell_s": np.array(samples.dwell_s),
            "table": samples.table,
        }
        if value == "zeros_short":
            fields[field] = np.zeros(3)
        elif value == "negative":
            broken = np.array(samples.dwell_s)
            broken[0] = -1.0
            fields[field] = broken
        elif value == "out_of_range":
            broken = np.array(samples.pass_index)
            broken[-1] = samples.table.n_passes
            fields[field] = broken
        else:
            fields[field] = np.array(samples.pass_index)[::-1].copy()
        with pytest.raises(DomainError, match=message):
            PassSamples(**fields)  # type: ignore[arg-type]

    def test_two_dimensional_samples_are_refused(self, reference_link: Link) -> None:
        samples = reference_link.samples
        with pytest.raises(DomainError, match="must be 1-D"):
            PassSamples(
                pass_index=np.array(samples.pass_index).reshape(-1, 2),
                satellite_index=np.array(samples.satellite_index).reshape(-1, 2),
                sample_index=np.array(samples.sample_index).reshape(-1, 2),
                dwell_s=np.array(samples.dwell_s).reshape(-1, 2),
                table=samples.table,
            )


class TestTheModuleSurface:
    """What the module refuses to know, checked on the code rather than the prose."""

    def test_the_mask_has_no_default(self) -> None:
        """A default mask would hide a design variable with a measured optimum."""
        signature = inspect.signature(find_passes)
        parameter = signature.parameters["minimum_elevation_rad"]
        assert parameter.default is inspect.Parameter.empty
        assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_it_imports_nothing_from_channel_or_qkd(self) -> None:
        """Layering, checked on the AST so a docstring mention does not trip it.

        ``core <- physics <- system``: pass segmentation is geometry and time,
        and an import of ``quoss.channel`` here would mean the mask had started
        depending on the link budget.
        """
        source = Path(passes_module.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        forbidden = {name for name in imported if name.startswith(("quoss.channel", "quoss.qkd"))}
        assert forbidden == set()

    def test_it_does_not_filter_on_key(self, reference_link: Link) -> None:
        """Two of the reference day's four passes yield no key, and all four are here.

        The claim of the module docstring: a pass with zero key is still a pass,
        and which ones those are is ``key_volume.py``'s most interesting output.
        """
        assert reference_link.table.n_passes == 4

    def test_the_minimum_samples_constant_is_the_documented_one(self) -> None:
        assert MINIMUM_SAMPLES_PER_PASS == 12


class TestWhatTheTableSays:
    """The derived columns and the reprs: small surface, read by every caller."""

    @pytest.mark.physics
    def test_the_julian_dates_bracket_the_pass(self, reference_table: PassTable) -> None:
        """``start_jd`` and ``end_jd`` are the refined seconds, in days from the epoch."""
        assert np.allclose(
            reference_table.start_jd,
            reference_table.grid.epoch_jd + reference_table.start_s / 86_400.0,
            rtol=0.0,
            atol=1e-12,
        )
        assert np.allclose(
            reference_table.end_jd,
            reference_table.grid.epoch_jd + reference_table.end_s / 86_400.0,
            rtol=0.0,
            atol=1e-12,
        )
        assert np.all(reference_table.end_jd > reference_table.start_jd)
        # A ten-minute pass is a seven-thousandth of a day, which is the scale at
        # which float64's ~20 us resolution on a JD stops mattering.
        assert np.all(reference_table.end_jd - reference_table.start_jd < 0.01)

    @pytest.mark.physics
    def test_the_reprs_say_what_they_hold(self, reference_link: Link) -> None:
        text = repr(reference_link.table)
        assert "n_passes=4" in text
        assert "mask=10.00 deg" in text
        assert "truncated=0" in text
        assert "PassSamples(size=1800, n_passes=4" in repr(reference_link.samples)

    @pytest.mark.physics
    def test_an_empty_table_has_a_repr_that_does_not_divide_by_nothing(self) -> None:
        """``min`` over an empty column would raise, so the empty case is its own branch."""
        table = table_from_elevation([1.0, 2.0, 3.0], mask_deg=10.0)
        assert table.n_passes == 0
        assert "n_passes=0" in repr(table)
        assert "mask=10.00 deg" in repr(table)

    @pytest.mark.physics
    def test_an_empty_table_expands_to_no_samples(self) -> None:
        """The degenerate expansion, which the offset arithmetic has to survive."""
        table = table_from_elevation([1.0, 2.0, 3.0], mask_deg=10.0)
        samples = table.samples()
        assert samples.size == 0
        assert samples.shape == (0,)
        assert samples.segment_sum(np.zeros(0)).tolist() == []

    @pytest.mark.physics
    def test_a_floor_that_drops_nothing_logs_nothing(self) -> None:
        """The filter is requested and fires on no pass: silence is the correct output."""
        log = DegradationLog()
        angles, grid = geometry()
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=log,
            minimum_duration_s=10.0,
        )
        assert table.n_passes == 4
        assert not any(e.code == "passes.below-minimum-duration" for e in log)


class TestTheConstellationCase:
    """The vectorisation claim, at the size the claim is about."""

    @pytest.mark.physics
    def test_a_sixty_satellite_day_is_segmented_without_a_loop(self) -> None:
        """5.2 million elevations, 240 passes, and no Python iteration over either axis.

        The module docstring and the ADR both claim this size works; measuring it
        is cheaper than asserting it. Sixty copies of the reference satellite is
        not a realistic constellation — every row has the same passes — but it is
        exactly the right shape to catch a segmentation that quietly iterates, and
        the per-row answer is known from the single-satellite table.
        """
        angles, grid = geometry()
        rows = 60
        elevation = np.tile(np.asarray(angles.elevation_rad), (rows, 1))
        assert elevation.size == rows * grid.n == 5_184_060
        table = find_passes(
            angles_from_elevation(elevation),
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=DegradationLog(),
        )
        single = link().table
        assert table.n_passes == rows * single.n_passes == 240
        # Rows are satellite-major and in order, and each row reproduces the
        # single-satellite answer exactly.
        assert table.satellite_index.tolist() == [
            s for s in range(rows) for _ in range(single.n_passes)
        ]
        for row in range(rows):
            block = table.select(table.satellite_index == row)
            assert np.allclose(block.duration_s, single.duration_s, rtol=0.0, atol=1e-12)
            assert np.allclose(
                block.culmination_elevation_rad,
                single.culmination_elevation_rad,
                rtol=0.0,
                atol=1e-12,
            )

    @pytest.mark.physics
    def test_the_samples_of_a_constellation_stay_grouped_by_pass(self) -> None:
        """The ordering a segment sum depends on, at a size where a bug would show."""
        angles, grid = geometry(step_s=10.0)
        elevation = np.tile(np.asarray(angles.elevation_rad), (12, 1))
        table = find_passes(
            angles_from_elevation(elevation),
            grid=grid,
            minimum_elevation_rad=float(np.deg2rad(10.0)),
            degradations=DegradationLog(),
        )
        samples = table.samples()
        assert np.all(np.diff(samples.pass_index) >= 0)
        assert samples.size == int(table.n_samples.sum())
        recovered = samples.segment_sum(np.asarray(samples.dwell_s))
        assert np.allclose(recovered, table.duration_s, rtol=0.0, atol=1e-9)
        # Every entry's satellite is the one its pass belongs to.
        assert np.array_equal(samples.satellite_index, table.satellite_index[samples.pass_index])
