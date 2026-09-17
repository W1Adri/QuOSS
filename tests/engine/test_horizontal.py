"""Tests for `quoss.engine.horizontal` and the containers it fills.

The physics is checked against a hand-wired chain in
``tests/e2e/test_horizontal_scenario.py``; what is checked here is the
orchestration and the refusals — which stages run, what the log says, what the
containers refuse to hold, and that ``run()`` dispatches on the ``link`` tag and
not on what the object happens to carry.
"""

from __future__ import annotations

import dataclasses
import math
from typing import Any

import numpy as np
import pytest

from quoss.core.errors import DegradationLog, DomainError, ScenarioError, Severity
from quoss.engine.cache import ResultCache
from quoss.engine.horizontal import (
    HORIZONTAL_STAGES,
    HorizontalSimulation,
    simulate_horizontal,
)
from quoss.engine.pipeline import run
from quoss.scenario.defaults import ge0b_bench, ge1_two_terminals, reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.result import (
    HorizontalBudgetResults,
    HorizontalResult,
    HorizontalSessionResults,
    SimulationResult,
)


def horizontal_run() -> HorizontalSimulation:
    return simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())


def horizontal_result() -> HorizontalResult:
    result = run(ge1_two_terminals())
    assert isinstance(result, HorizontalResult)
    return result


class TestRunDispatchesOnTheTag:
    def test_a_horizontal_scenario_gives_a_horizontal_result(self) -> None:
        assert isinstance(run(ge1_two_terminals()), HorizontalResult)
        assert isinstance(run(ge0b_bench()), HorizontalResult)

    def test_a_downlink_scenario_still_gives_a_simulation_result(self) -> None:
        scenario = reference_castelldefels().model_copy(
            update={"time": reference_castelldefels().time.model_copy(update={"duration_s": 600.0})}
        )
        assert isinstance(run(scenario), SimulationResult)

    def test_simulate_horizontal_refuses_a_downlink_and_says_where_it_goes(self) -> None:
        with pytest.raises(ScenarioError, match=r"quoss\.engine\.pipeline\.simulate"):
            simulate_horizontal(
                reference_castelldefels(),  # type: ignore[arg-type]
                degradations=DegradationLog(),
            )

    def test_run_refuses_something_that_is_neither(self) -> None:
        with pytest.raises(ScenarioError, match="HorizontalScenario"):
            run("scenarios/ge1_1km.yaml")  # type: ignore[arg-type]


class TestTheThingsAHorizontalRunDoesNotDo:
    def test_a_cache_is_declined_out_loud_rather_than_ignored(self, tmp_path: Any) -> None:
        """A cache that silently did nothing is the kind of no-op this project forbids."""
        log = DegradationLog()
        result = run(ge1_two_terminals(), cache=ResultCache(tmp_path), degradations=log)
        assert isinstance(result, HorizontalResult)
        (entry,) = [e for e in log if e.code == "engine.horizontal-is-not-cached"]
        assert entry.severity is Severity.INFO
        assert ".npz" in entry.message
        assert not list(tmp_path.iterdir())

    def test_without_a_cache_nothing_is_said(self) -> None:
        log = DegradationLog()
        run(ge1_two_terminals(), degradations=log)
        assert not [e for e in log if e.code == "engine.horizontal-is-not-cached"]

    def test_the_timings_name_the_three_stages_that_ran(self) -> None:
        result = horizontal_result()
        assert tuple(result.timings.seconds) == HORIZONTAL_STAGES
        assert all(value >= 0.0 for value in result.timings.seconds.values())


class TestTheSessionWithoutKey:
    """The horizontal counterpart of ADR 0011's cliff, and the INFO that explains it."""

    def test_a_five_kilometre_link_certifies_nothing_and_says_the_asymptotic_figure(self) -> None:
        """The most important thing this module can report, so it is reported.

        At 5 km GE-1's asymptotic rate is still about 4 kbit/s and the certified
        key is exactly zero: the phase-error inference returns its maximum and
        the single-photon term vanishes, while error correction keeps charging.
        A study quoting the asymptotic figure would have called the link
        working.
        """
        scenario = ge1_two_terminals()
        far = scenario.model_copy(
            update={"path": scenario.path.model_copy(update={"path_length_m": 5000.0})}
        )
        log = DegradationLog()
        engine = simulate_horizontal(far, degradations=log)
        assert engine.result.session.finite_bits == 0.0
        assert engine.result.session.has_key is False
        assert engine.result.session.asymptotic_bits > 0.0
        (entry,) = [e for e in log if e.code == "horizontal.session-without-key"]
        assert entry.severity is Severity.INFO
        assert entry.details["asymptotic_bits"] == engine.result.session.asymptotic_bits
        assert entry.details["phase_error_rate"] == engine.result.session.phase_error_rate

    def test_a_link_that_closes_says_nothing_of_the_sort(self) -> None:
        log = DegradationLog()
        simulate_horizontal(ge1_two_terminals(), degradations=log)
        assert not [e for e in log if e.code == "horizontal.session-without-key"]


class TestTheProvenance:
    def test_the_hash_is_the_scenarios_own(self) -> None:
        scenario = ge1_two_terminals()
        assert horizontal_result().provenance.scenario_hash == scenario_hash(scenario)

    def test_no_seed_is_recorded_because_nothing_was_drawn(self) -> None:
        assert horizontal_result().provenance.seed is None

    def test_the_two_geometries_never_share_a_hash(self) -> None:
        assert scenario_hash(ge1_two_terminals()) != scenario_hash(reference_castelldefels())


class TestTheResultRoundTrips:
    def test_to_dict_and_back(self) -> None:
        result = horizontal_result()
        again = HorizontalResult.from_dict(result.to_dict())
        assert again.scenario == result.scenario
        assert again.budget == result.budget
        assert again.session == result.session
        assert again.provenance == result.provenance
        assert list(again.warnings) == list(result.warnings)
        assert again.timings.seconds == result.timings.seconds

    def test_the_dict_is_json(self) -> None:
        import json

        text = json.dumps(horizontal_result().to_dict(), allow_nan=False)
        assert '"link": "horizontal"' in text

    def test_the_warnings_are_copied_and_not_shared(self) -> None:
        entries = [{"code": "x", "details": {"a": 1}}]
        result = dataclasses.replace(horizontal_result(), warnings=entries)
        entries[0]["details"]["a"] = 2  # type: ignore[index]
        assert result.warnings[0]["details"]["a"] == 1


class TestTheBudgetContainerRefuses:
    @staticmethod
    def _fields(**overrides: float) -> dict[str, float]:
        base = {
            "geometric_db": 1.0,
            "atmospheric_db": 0.2,
            "pointing_db": 0.1,
            "scintillation_db": 1.4,
            "fade_db": 1.5,
            "receiver_chain_db": 6.3,
            "static_db": 0.0,
            "total_db": 11.6,
            "transmittance": 0.07,
            "extinction_db_per_km": 0.2,
            "log_irradiance_variance_np2": 0.2,
            "rytov_variance_np2": 0.2,
            "beam_to_jitter_ratio": 1200.0,
        }
        base.update(overrides)
        return base

    def test_it_accepts_the_ordinary_case(self) -> None:
        assert HorizontalBudgetResults(**self._fields()).total_db == 11.6

    def test_a_non_finite_term_is_refused(self) -> None:
        with pytest.raises(DomainError, match="must be finite"):
            HorizontalBudgetResults(**self._fields(total_db=float("nan")))

    def test_a_negative_decibel_term_is_refused_because_it_would_be_gain(self) -> None:
        with pytest.raises(DomainError, match="would be gain"):
            HorizontalBudgetResults(**self._fields(atmospheric_db=-0.1))

    def test_an_infinite_gamma_is_legal_because_it_is_the_no_jitter_limit(self) -> None:
        """``gamma = +inf`` means "no pointing fade", which ADR 0021 made a legal value."""
        budget = HorizontalBudgetResults(**self._fields(beam_to_jitter_ratio=math.inf))
        assert budget.beam_to_jitter_ratio == math.inf

    def test_it_round_trips_through_its_tree(self) -> None:
        budget = HorizontalBudgetResults(**self._fields())
        assert HorizontalBudgetResults._from_tree(budget._tree()) == budget


class TestTheSessionContainerRefuses:
    @staticmethod
    def _fields(**overrides: float) -> dict[str, float]:
        base = {
            "duration_s": 60.0,
            "pulses": 6e9,
            "finite_bits": 15_236_099.0,
            "asymptotic_bits": 3.5e7,
            "qber": 0.01,
            "phase_error_rate": 0.02,
            "noise_counts_per_gate": 6e-7,
            "correctness": 1e-10,
            "secrecy": 1e-10,
        }
        base.update(overrides)
        return base

    def test_the_rates_are_per_second_of_the_declared_session(self) -> None:
        session = HorizontalSessionResults(**self._fields())
        assert session.finite_bit_s == 15_236_099.0 / 60.0
        assert session.asymptotic_bit_s == 3.5e7 / 60.0
        assert session.has_key is True

    def test_a_non_finite_field_is_refused(self) -> None:
        with pytest.raises(DomainError, match="must be finite"):
            HorizontalSessionResults(**self._fields(qber=float("inf")))

    def test_a_negative_count_is_refused(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            HorizontalSessionResults(**self._fields(finite_bits=-1.0))

    def test_a_probability_above_one_is_refused(self) -> None:
        with pytest.raises(DomainError, match="at most 1"):
            HorizontalSessionResults(**self._fields(qber=1.5))

    def test_zero_key_is_legal_and_is_not_a_missing_value(self) -> None:
        session = HorizontalSessionResults(**self._fields(finite_bits=0.0))
        assert session.has_key is False
        assert session.finite_bit_s == 0.0

    def test_it_round_trips_through_its_tree(self) -> None:
        session = HorizontalSessionResults(**self._fields())
        assert HorizontalSessionResults._from_tree(session._tree()) == session


class TestTheObjectsBehindTheResult:
    def test_the_simulation_carries_what_a_test_needs_to_check_the_physics(self) -> None:
        engine = horizontal_run()
        assert float(np.asarray(engine.loss.total_db)) == engine.result.budget.total_db
        assert float(np.asarray(engine.finite.length_bits)) == engine.result.session.finite_bits
        assert float(np.asarray(engine.conditions.transmittance)) == (
            engine.result.budget.transmittance
        )
        assert float(np.asarray(engine.noise.total_per_gate)) == (
            engine.result.session.noise_counts_per_gate
        )
