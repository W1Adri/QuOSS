"""Tests for `quoss.engine.sweep`.

- ``TestSweepSpec`` — what a sweep may be, and the refusals: no parameters, no
  values, a string mistaken for a list of values, an unknown mode, zip lists of
  different lengths.
- ``TestThePoints`` — grid order (last parameter fastest) and zip pairing.
- ``TestApplyPoint`` — every point goes back through the validators, which is the
  reason the module edits JSON instead of calling ``model_copy``.
- ``TestBadPaths`` — the four ways a dotted path can fail to name a field.
- ``TestMetrics`` — resolution, indexing, summing, and every refusal.
- ``TestSummingQuantilesIsFlagged`` — the one reduction that is not what it looks
  like, warned about rather than forbidden.
- ``TestTheMaskSweepReproducesTheKnownOptimum`` — the measurement that justifies
  the module: ADR 0011's interior optimum near 8 degrees, found again by a
  `SweepSpec` instead of by hand.
- ``TestSweepResult`` — rows, columns and the hash that ties a row to its point.
- ``TestWorkersDoNotChangeASweep`` — the same table from one process or three.
- ``TestCommonRandomNumbers`` — why a sweep without a random source gives every
  point the *same* seed, and what giving one changes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quoss.channel.turbulence import ScintillationRegime
from quoss.core.errors import DegradationLog, DomainError, ScenarioError, Severity
from quoss.core.rng import RandomSource
from quoss.engine.cache import ResultCache
from quoss.engine.pipeline import run
from quoss.engine.sweep import (
    METRIC_ROOTS,
    SweepResult,
    SweepSpec,
    apply_point,
    metric_value,
    run_sweep,
)
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import MonteCarloSpec, Scenario
from quoss.scenario.result import SimulationResult

MASK_PATH = "passes.minimum_elevation_deg"
REGIME_PATH = "channel.scintillation_regime"

MASK_SWEEP_DEG = (2.0, 5.0, 8.0, 10.0, 15.0)
MASK_SWEEP_FINITE_BITS = (409_584.0, 427_602.0, 435_462.0, 433_442.0, 407_794.0)
"""The reference day's finite key at five elevation masks, measured by this suite.

``docs/adr/0011-the-block-is-the-pass.md`` §5 found the interior optimum by hand;
these are the same five runs driven by a :class:`SweepSpec`, with the station's
30 m altitude wired into the turbulence profile (``tests/system/reference.py``
uses 0 m and lands 0.1-0.2 % lower, which is the same optimum from the same
mechanism and not a second measurement).
"""


def with_monte_carlo(*, seed: int | None, realisations: int = 8) -> Scenario:
    return reference_castelldefels().model_copy(
        update={
            "monte_carlo": MonteCarloSpec(
                realisations=realisations,
                seed=seed,
                scintillation_correlation_time_s=0.002,
                pointing_correlation_time_s=0.02,
            )
        }
    )


@pytest.fixture(scope="module")
def reference_result() -> SimulationResult:
    """One reference run, shared: it is read-only here and costs a tenth of a second."""
    return run(reference_castelldefels(), degradations=DegradationLog())


@pytest.fixture(scope="module")
def mask_sweep() -> SweepResult:
    """Return the five-mask sweep of :data:`MASK_SWEEP_DEG`, shared by its readers."""
    return run_sweep(
        reference_castelldefels(),
        SweepSpec({MASK_PATH: list(MASK_SWEEP_DEG)}),
        degradations=DegradationLog(),
    )


@pytest.fixture(scope="module")
def two_metric_sweep() -> SweepResult:
    """Two points and two metrics: the smallest sweep with a full-width table."""
    return run_sweep(
        reference_castelldefels(),
        SweepSpec({MASK_PATH: [8.0, 12.0]}),
        metrics=("daily.finite_bits", "daily.asymptotic_bits"),
        degradations=DegradationLog(),
    )


class TestSweepSpec:
    def test_a_single_parameter_is_a_sweep(self) -> None:
        spec = SweepSpec({MASK_PATH: [5.0, 10.0]})
        assert spec.paths == (MASK_PATH,)
        assert spec.mode == "grid"

    def test_the_value_lists_are_frozen_against_the_caller(self) -> None:
        """A caller's list must not be able to change a spec after the fact.

        A sweep is a record of what was run; a spec that followed a mutation
        would describe points nobody ran.
        """
        values = [5.0, 10.0]
        spec = SweepSpec({MASK_PATH: values})
        values.append(90.0)
        assert spec.parameters[MASK_PATH] == (5.0, 10.0)
        assert len(spec.points()) == 2

    def test_no_parameters_at_all_is_refused(self) -> None:
        with pytest.raises(ScenarioError, match="at least one parameter"):
            SweepSpec({})

    def test_a_parameter_with_no_values_is_refused(self) -> None:
        with pytest.raises(ScenarioError, match=r"has no values"):
            SweepSpec({MASK_PATH: []})

    @pytest.mark.parametrize("bad", ["", 5.0, None])
    def test_a_path_that_is_not_a_non_empty_string_is_refused(self, bad: Any) -> None:
        with pytest.raises(ScenarioError, match="non-empty strings"):
            SweepSpec({bad: [1.0]})

    @pytest.mark.parametrize("bad", ["5.0", b"5.0", 5.0, {"a": 1}])
    def test_a_single_value_where_a_list_belongs_is_refused(self, bad: Any) -> None:
        """``{"path": "abc"}`` would otherwise sweep over ``'a'``, ``'b'``, ``'c'``.

        A string is a ``Sequence``, so the obvious check passes it and the sweep
        silently runs three points nobody asked for. Bytes are refused for the
        same reason; a bare float and a dict are refused because they are the
        two ways a caller forgets the brackets.
        """
        with pytest.raises(ScenarioError, match="needs a list of values"):
            SweepSpec({MASK_PATH: bad})

    def test_an_unknown_mode_is_refused(self) -> None:
        with pytest.raises(ScenarioError, match="must be 'grid' or 'zip'"):
            SweepSpec({MASK_PATH: [1.0]}, mode="cartesian")  # type: ignore[arg-type]

    def test_zip_lists_of_different_lengths_are_refused(self) -> None:
        """``zip`` would drop the tail without a word, so the spec refuses first."""
        with pytest.raises(ScenarioError, match=r"equal-length value lists"):
            SweepSpec({"a": [1, 2], "b": [3]}, mode="zip")


class TestThePoints:
    def test_a_grid_is_the_product_with_the_last_parameter_fastest(self) -> None:
        spec = SweepSpec({"a": [1, 2], "b": [3, 4, 5]})
        assert spec.points() == [
            {"a": 1, "b": 3},
            {"a": 1, "b": 4},
            {"a": 1, "b": 5},
            {"a": 2, "b": 3},
            {"a": 2, "b": 4},
            {"a": 2, "b": 5},
        ]

    def test_zip_pairs_the_i_th_values(self) -> None:
        """How two *coupled* parameters move: an aperture and the station that has it."""
        spec = SweepSpec(
            {"stations.0.receive_aperture_m": [0.75, 1.3], "stations.0.name": ["a", "b"]},
            mode="zip",
        )
        assert spec.points() == [
            {"stations.0.receive_aperture_m": 0.75, "stations.0.name": "a"},
            {"stations.0.receive_aperture_m": 1.3, "stations.0.name": "b"},
        ]


class TestApplyPoint:
    def test_a_scalar_field_is_set(self) -> None:
        scenario = apply_point(reference_castelldefels(), {MASK_PATH: 8.0})
        assert scenario.passes.minimum_elevation_deg == 8.0

    def test_an_integer_segment_indexes_a_list(self) -> None:
        scenario = apply_point(reference_castelldefels(), {"stations.0.receive_aperture_m": 1.3})
        assert scenario.stations[0].receive_aperture_m == 1.3

    def test_several_paths_are_set_in_one_point(self) -> None:
        scenario = apply_point(reference_castelldefels(), {MASK_PATH: 12.0, "time.step_s": 5.0})
        assert scenario.passes.minimum_elevation_deg == 12.0
        assert scenario.time.step_s == 5.0

    def test_the_base_scenario_is_not_touched(self) -> None:
        base = reference_castelldefels()
        before = base.passes.minimum_elevation_deg
        apply_point(base, {MASK_PATH: before + 5.0})
        assert base.passes.minimum_elevation_deg == before

    def test_a_value_no_scenario_file_could_hold_is_refused_here(self) -> None:
        """The reason the module dumps to JSON instead of calling ``model_copy``.

        Pydantic does not validate a ``model_copy``, so a mask of -5 degrees
        would reach the physics and be refused three stages later with a message
        about radians. Here it is refused at the point, naming the point.
        """
        with pytest.raises(ScenarioError, match=r"is not a valid scenario"):
            apply_point(reference_castelldefels(), {MASK_PATH: -5.0})

    def test_the_message_names_the_point(self) -> None:
        with pytest.raises(ScenarioError, match=r"minimum_elevation_deg': -5.0"):
            apply_point(reference_castelldefels(), {MASK_PATH: -5.0})

    def test_an_enum_field_is_swept_by_its_string_value(self) -> None:
        """A sweep axis need not be a number, and the scintillation regime is the case.

        A point is applied to the scenario's **JSON** form, so an enum arrives
        as the string a YAML file would carry and comes back an enum member.
        That is what lets ADR 0022's two columns be one grid rather than two
        scripts, and the two points are two scenarios: they hash differently,
        so they cannot share a cache entry for a 3.7 % difference in key.
        """
        weak = apply_point(reference_castelldefels(), {REGIME_PATH: "weak"})
        saturated = apply_point(reference_castelldefels(), {REGIME_PATH: "moderate-to-strong"})
        assert weak.channel.scintillation_regime is ScintillationRegime.WEAK
        assert saturated.channel.scintillation_regime is ScintillationRegime.MODERATE_TO_STRONG
        assert scenario_hash(weak) != scenario_hash(saturated)
        assert scenario_hash(weak) == scenario_hash(reference_castelldefels())

    def test_a_regime_no_scenario_file_could_hold_is_refused_at_the_point(self) -> None:
        """``"strong"`` is not one of the two members, and the point says so."""
        with pytest.raises(ScenarioError, match=r"is not a valid scenario"):
            apply_point(reference_castelldefels(), {REGIME_PATH: "strong"})


class TestBadPaths:
    def test_an_unknown_field_names_the_fields_that_are_there(self) -> None:
        with pytest.raises(ScenarioError, match=r"is not a scenario field; fields here"):
            apply_point(reference_castelldefels(), {"passes.minimum_elevation": 8.0})

    def test_an_index_past_the_end_of_a_list(self) -> None:
        with pytest.raises(ScenarioError, match=r"indexes a list of 1 items"):
            apply_point(reference_castelldefels(), {"stations.7.receive_aperture_m": 1.0})

    def test_a_name_where_a_list_index_belongs(self) -> None:
        with pytest.raises(ScenarioError, match=r"indexes a list of 1 items"):
            apply_point(reference_castelldefels(), {"stations.first.receive_aperture_m": 1.0})

    def test_a_path_that_goes_inside_a_value(self) -> None:
        with pytest.raises(ScenarioError, match=r"goes inside a value"):
            apply_point(reference_castelldefels(), {f"{MASK_PATH}.deeper": 8.0})


class TestAPathMayEndOnAListElement:
    def test_an_element_of_a_list_of_numbers_is_set_in_place(self) -> None:
        """The last segment may itself be the index, not only a field below one.

        ``stations.0.receive_aperture_m`` ends on a field of the station;
        ``monte_carlo.quantiles.1`` ends on the list element. Both are dotted
        paths a caller will write, and they take different branches.
        """
        scenario = apply_point(with_monte_carlo(seed=7), {"monte_carlo.quantiles.1": 0.6})
        assert scenario.monte_carlo is not None
        assert scenario.monte_carlo.quantiles == (0.05, 0.6, 0.95)

    def test_an_element_that_breaks_a_cross_field_rule_is_still_refused(self) -> None:
        """The quantiles must increase, and the validators still say so.

        The point of routing every edit through the loader: this rule lives on
        the model, not on the field, so a ``model_copy`` would have let it past.
        """
        with pytest.raises(ScenarioError, match="not a valid scenario"):
            apply_point(with_monte_carlo(seed=7), {"monte_carlo.quantiles.1": 0.99})


class TestMetrics:
    def test_a_day_metric_is_the_sum_over_the_window(
        self, reference_result: SimulationResult
    ) -> None:
        assert metric_value(reference_result, "daily.finite_bits") == pytest.approx(
            float(reference_result.daily.finite_bits.sum())
        )

    def test_a_pass_metric_sums_the_passes(self, reference_result: SimulationResult) -> None:
        assert metric_value(reference_result, "passes.finite_bits") == pytest.approx(
            float(reference_result.passes.finite_bits.sum())
        )
        assert metric_value(reference_result, "passes.finite_bits") == pytest.approx(
            metric_value(reference_result, "daily.finite_bits")
        )

    def test_an_integer_segment_indexes_into_an_array(self) -> None:
        ensemble = run(with_monte_carlo(seed=7), degradations=DegradationLog())
        assert ensemble.monte_carlo is not None
        assert metric_value(ensemble, "monte_carlo.quantile_bits.1") == pytest.approx(
            float(ensemble.monte_carlo.quantile_bits[1].sum())
        )

    def test_every_declared_root_is_a_real_result_section(
        self, reference_result: SimulationResult
    ) -> None:
        for root in METRIC_ROOTS:
            assert hasattr(reference_result, root)

    @pytest.mark.parametrize("bad", ["", None, 5])
    def test_a_metric_that_is_not_a_dotted_path(
        self, reference_result: SimulationResult, bad: Any
    ) -> None:
        with pytest.raises(ScenarioError, match="non-empty dotted path"):
            metric_value(reference_result, bad)

    def test_a_root_that_is_not_a_result_section(self, reference_result: SimulationResult) -> None:
        with pytest.raises(ScenarioError, match="not a result section"):
            metric_value(reference_result, "provenance.seed")

    def test_a_root_with_no_attribute(self, reference_result: SimulationResult) -> None:
        with pytest.raises(ScenarioError, match=r"daily has no attribute 'nonsense'"):
            metric_value(reference_result, "daily.nonsense")

    def test_a_root_on_its_own(self, reference_result: SimulationResult) -> None:
        with pytest.raises(ScenarioError, match=r"has no attribute ''"):
            metric_value(reference_result, "daily")

    def test_a_section_the_scenario_did_not_ask_for(
        self, reference_result: SimulationResult
    ) -> None:
        """A Monte Carlo metric of a run without one: absent, not zero.

        Returning 0.0 would put a number in a table that reads as "the ensemble
        said zero" instead of "there was no ensemble".
        """
        assert reference_result.monte_carlo is None
        with pytest.raises(ScenarioError, match="absent from this result"):
            metric_value(reference_result, "monte_carlo.quantile_bits")

    def test_an_index_past_the_end(self) -> None:
        ensemble = run(with_monte_carlo(seed=7), degradations=DegradationLog())
        with pytest.raises(ScenarioError, match="out of range"):
            metric_value(ensemble, "monte_carlo.quantile_bits.9")

    def test_a_path_that_continues_past_a_leaf(self, reference_result: SimulationResult) -> None:
        with pytest.raises(ScenarioError, match="does not exist in the result"):
            metric_value(reference_result, "daily.finite_bits.deeper")

    def test_a_metric_that_is_not_numeric(self, reference_result: SimulationResult) -> None:
        with pytest.raises(ScenarioError, match="is not numeric"):
            metric_value(reference_result, "daily.protocol")

    def test_a_metric_whose_value_is_none_on_a_day_that_certified_nothing(self) -> None:
        """A day with no pass has no composed failure probability, and says so.

        ``composed_correctness`` is the union bound over the blocks that
        certified key; with no block there is nothing to compose, and the field
        is ``None``. The refusal matters more than it looks: the alternative is
        a metric column holding ``0.0``, which reads as "this day's key is
        certain to be correct" — the strongest possible claim — when what
        happened is that there was no key at all.
        """
        empty = run(
            apply_point(reference_castelldefels(), {MASK_PATH: 85.0}),
            degradations=DegradationLog(),
        )
        assert empty.passes.n_passes == 0
        assert empty.daily.composed_correctness is None
        with pytest.raises(ScenarioError, match="absent from this result"):
            metric_value(empty, "daily.composed_correctness")

    def test_a_scalar_metric_is_its_own_sum(self, reference_result: SimulationResult) -> None:
        """A metric need not end on an array; a lone float sums to itself."""
        assert reference_result.daily.composed_correctness is not None
        assert metric_value(reference_result, "daily.composed_correctness") == pytest.approx(
            reference_result.daily.composed_correctness
        )


class TestSummingQuantilesIsFlagged:
    def test_a_quantile_metric_records_a_warning_saying_what_it_is_not(self) -> None:
        """A sum of per-pass quantiles is not the quantile of the day's key.

        ADR 0012 §8: on the reference ensemble the day's P5 is 735 329 bits and
        the sum of the passes' P5 is 724 553 — close enough to be mistaken for
        the same number, which is exactly why it is warned about rather than
        left to the reader.
        """
        log = DegradationLog()
        run_sweep(
            with_monte_carlo(seed=7),
            SweepSpec({MASK_PATH: [10.0]}),
            metrics=("monte_carlo.quantile_bits.0",),
            degradations=log,
        )
        (entry,) = [e for e in log if e.code == "engine.sweep-sums-quantiles"]
        assert entry.severity is Severity.WARNING
        assert "not the quantile of the summed key" in entry.message

    def test_an_ordinary_metric_is_not_flagged(self) -> None:
        log = DegradationLog()
        run_sweep(
            reference_castelldefels(),
            SweepSpec({MASK_PATH: [10.0]}),
            degradations=log,
        )
        assert [e for e in log if e.code == "engine.sweep-sums-quantiles"] == []


class TestTheMaskSweepReproducesTheKnownOptimum:
    def test_the_five_masks_give_the_measured_key(self, mask_sweep: SweepResult) -> None:
        assert tuple(mask_sweep.column(MASK_PATH)) == MASK_SWEEP_DEG
        assert tuple(mask_sweep.column("daily.finite_bits")) == pytest.approx(
            MASK_SWEEP_FINITE_BITS
        )

    def test_the_optimum_is_interior_and_not_at_either_end(self, mask_sweep: SweepResult) -> None:
        """The finding, stated as the shape of the curve rather than as one number.

        A mask exists to throw away the passes that cost more error correction
        than they pay in key. Raising it therefore helps until it starts
        throwing away passes that were paying, and that turning point is
        somewhere in the middle — not at 0 degrees, where the worst geometry is
        kept, and not at 90, where nothing is.
        """
        bits = list(mask_sweep.column("daily.finite_bits"))
        best = bits.index(max(bits))
        assert 0 < best < len(bits) - 1
        assert mask_sweep.column(MASK_PATH)[best] == 8.0

    def test_a_sweep_of_one_point_agrees_with_a_plain_run(self) -> None:
        scenario = apply_point(reference_castelldefels(), {MASK_PATH: 8.0})
        direct = run(scenario, degradations=DegradationLog())
        swept = run_sweep(
            reference_castelldefels(),
            SweepSpec({MASK_PATH: [8.0]}),
            degradations=DegradationLog(),
        )
        assert swept.column("daily.finite_bits")[0] == pytest.approx(
            metric_value(direct, "daily.finite_bits")
        )


class TestSweepResult:
    def test_one_row_per_point_with_every_column(self, two_metric_sweep: SweepResult) -> None:
        rows = two_metric_sweep.to_records()
        assert len(rows) == 2
        assert set(rows[0]) == {
            MASK_PATH,
            "daily.finite_bits",
            "daily.asymptotic_bits",
            "scenario_hash",
        }

    def test_the_rows_are_independent_copies(self, two_metric_sweep: SweepResult) -> None:
        rows = two_metric_sweep.to_records()
        rows[0]["daily.finite_bits"] = -1.0
        assert two_metric_sweep.to_records()[0]["daily.finite_bits"] != -1.0

    def test_the_hash_of_a_row_is_the_hash_of_that_point(
        self, two_metric_sweep: SweepResult
    ) -> None:
        """What ties a table row back to a scenario that can be re-run.

        Without it a reader of the table has the parameter value and has to
        trust that nothing else moved; with it they can rebuild the point and
        check.
        """
        for point, row in zip(two_metric_sweep.points, two_metric_sweep.to_records(), strict=True):
            rebuilt = apply_point(reference_castelldefels(), point)
            assert row["scenario_hash"] == scenario_hash(rebuilt)

    def test_column_returns_one_column(self, two_metric_sweep: SweepResult) -> None:
        assert two_metric_sweep.column(MASK_PATH) == [8.0, 12.0]

    def test_an_unknown_column_names_the_ones_there_are(
        self, two_metric_sweep: SweepResult
    ) -> None:
        with pytest.raises(KeyError, match="no column"):
            two_metric_sweep.column("daily.nonsense")

    def test_an_empty_result_has_no_columns_at_all(self) -> None:
        with pytest.raises(KeyError, match=r"columns: \[\]"):
            SweepResult(points=(), records=()).column("anything")


class TestRefusalsBeforeAnythingRuns:
    def test_a_spec_that_is_not_a_sweepspec(self) -> None:
        with pytest.raises(DomainError, match="must be a SweepSpec"):
            run_sweep(
                reference_castelldefels(),
                {MASK_PATH: [8.0]},  # type: ignore[arg-type]
                degradations=DegradationLog(),
            )

    def test_no_metrics_at_all(self) -> None:
        with pytest.raises(ScenarioError, match="at least one metric"):
            run_sweep(
                reference_castelldefels(),
                SweepSpec({MASK_PATH: [8.0]}),
                metrics=(),
                degradations=DegradationLog(),
            )

    def test_an_unknown_metric_is_refused_before_the_first_run(self) -> None:
        with pytest.raises(ScenarioError, match="not a result section"):
            run_sweep(
                reference_castelldefels(),
                SweepSpec({MASK_PATH: [8.0]}),
                metrics=("nonsense.field",),
                degradations=DegradationLog(),
            )

    def test_a_bad_fifth_point_fails_before_the_first_four_have_run(self) -> None:
        """Every point is built and validated before any of them runs.

        The alternative costs four full runs to learn that the fifth point was
        never going to work, which on a real sweep is minutes.
        """
        log = DegradationLog()
        with pytest.raises(ScenarioError, match="not a valid scenario"):
            run_sweep(
                reference_castelldefels(),
                SweepSpec({MASK_PATH: [2.0, 5.0, 8.0, 10.0, -5.0]}),
                degradations=log,
            )
        assert [e for e in log if e.code == "engine.sweep-point"] == []

    def test_a_bad_worker_count(self) -> None:
        with pytest.raises(DomainError, match="workers must be an integer"):
            run_sweep(
                reference_castelldefels(),
                SweepSpec({MASK_PATH: [8.0]}),
                workers=0,
                degradations=DegradationLog(),
            )


class TestEveryPointOpensItsBlockInTheLog:
    def test_an_info_entry_separates_one_points_warnings_from_the_next(self) -> None:
        log = DegradationLog()
        run_sweep(
            reference_castelldefels(),
            SweepSpec({MASK_PATH: [8.0, 12.0]}),
            degradations=log,
        )
        opens = [e for e in log if e.code == "engine.sweep-point"]
        assert len(opens) == 2
        assert [e.details["point"][MASK_PATH] for e in opens] == [8.0, 12.0]
        assert all(entry.severity is Severity.INFO for entry in opens)


@pytest.mark.slow
class TestWorkersDoNotChangeASweep:
    def test_three_workers_give_the_table_one_worker_gives(self) -> None:
        spec = SweepSpec({MASK_PATH: list(MASK_SWEEP_DEG)})
        one = run_sweep(reference_castelldefels(), spec, degradations=DegradationLog())
        many = run_sweep(reference_castelldefels(), spec, workers=3, degradations=DegradationLog())
        assert many.to_records() == one.to_records()


class TestTheCacheIsPassedToEveryPoint:
    def test_a_second_sweep_is_served_from_the_cache(self, tmp_path: Path) -> None:
        cache = ResultCache(tmp_path / "results")
        spec = SweepSpec({MASK_PATH: [8.0, 12.0]})
        first = run_sweep(
            reference_castelldefels(), spec, cache=cache, degradations=DegradationLog()
        )
        log = DegradationLog()
        second = run_sweep(reference_castelldefels(), spec, cache=cache, degradations=log)
        assert second.to_records() == first.to_records()
        assert len([e for e in log if e.code == "engine.cache-hit"]) == 2


class TestCommonRandomNumbers:
    def test_without_a_source_every_point_uses_the_scenarios_own_seed(self) -> None:
        """Deliberate: the difference between two points is then the parameter.

        Give each point its own stream and the difference between two points is
        the parameter's effect *plus* two ensembles' noise, which on eight
        realisations is the larger of the two.
        """
        scenario = with_monte_carlo(seed=7)
        swept = run_sweep(
            scenario,
            SweepSpec({MASK_PATH: [10.0, 10.0]}),
            metrics=("monte_carlo.mean_bits",),
            degradations=DegradationLog(),
        )
        first, second = swept.column("monte_carlo.mean_bits")
        assert first == second

    def test_a_given_source_gives_each_point_its_own_child(self) -> None:
        scenario = with_monte_carlo(seed=7)
        swept = run_sweep(
            scenario,
            SweepSpec({MASK_PATH: [10.0, 10.0]}),
            metrics=("monte_carlo.mean_bits",),
            random_source=RandomSource.from_seed(20_260_914),
            degradations=DegradationLog(),
        )
        first, second = swept.column("monte_carlo.mean_bits")
        assert first != second

    def test_the_same_source_replays_the_same_sweep(self) -> None:
        scenario = with_monte_carlo(seed=7)
        spec = SweepSpec({MASK_PATH: [10.0, 12.0]})
        rows = [
            run_sweep(
                scenario,
                spec,
                metrics=("monte_carlo.mean_bits",),
                random_source=RandomSource.from_seed(20_260_914),
                degradations=DegradationLog(),
            ).to_records()
            for _ in range(2)
        ]
        assert rows[0] == rows[1]
