"""Tests for `quoss.viz.figures`, against fake runners returning hand-built results.

- ``TestFiniteVsAsymptotic``, ``TestMaskOptimum``, ``TestMonteCarloSpread`` —
  the data a figure returns is exactly what it drew, from the scenario it
  claims; the refusals.
- ``TestTheEngineIsInjected`` — without the engine the defaults say so.
- ``TestWithoutMatplotlib`` — every figure names the extra.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Any

import pytest

from quoss.core.errors import ConfigurationError, DomainError
from quoss.scenario.defaults import ge1_two_terminals, ntanos_2021, reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import Scenario
from quoss.scenario.result import SimulationResult
from quoss.viz.figures import (
    ASYMPTOTIC_METRIC,
    FINITE_METRIC,
    MASK_PARAMETER,
    PaperFigure,
    figure_finite_vs_asymptotic,
    figure_mask_optimum,
    figure_monte_carlo_spread,
    monte_carlo_reference_scenario,
)
from quoss.viz.plots import DEGRADED_GID
from quoss.viz.style import ASYMPTOTIC_LABEL, FINITE_LABEL

from .builders import (
    ASYMPTOTIC_BITS,
    DEGRADED_WARNING,
    FINITE_BITS,
    QUANTILE_BITS,
    START_S,
    hide_matplotlib,
    make_result,
    ydata,
)

MASK_TABLE = {
    2.0: (408_946.0, 3_876_492.0),
    5.0: (426_988.0, 3_876_492.0),
    8.0: (434_938.0, 3_844_682.0),
    10.0: (432_985.0, 3_776_681.0),
    15.0: (400_000.0, 3_400_000.0),
}
"""Shape of ADR 0011 §5 (15 deg invented to fill the grid): fixture values, not a measurement."""


class FakeSweeper:
    def __init__(self, drop: float | None = None) -> None:
        self.calls: list[tuple[Scenario, dict[str, list[Any]], tuple[str, ...]]] = []
        self.drop = drop

    def __call__(
        self, scenario: Scenario, parameters: Mapping[str, Sequence[Any]], metrics: Sequence[str]
    ) -> list[dict[str, Any]]:
        self.calls.append((scenario, {k: list(v) for k, v in parameters.items()}, tuple(metrics)))
        rows = []
        for mask in parameters[MASK_PARAMETER]:
            if mask == self.drop:
                continue
            finite, asymptotic = MASK_TABLE[float(mask)]
            rows.append(
                {MASK_PARAMETER: mask, FINITE_METRIC: finite, ASYMPTOTIC_METRIC: asymptotic}
            )
        return rows[::-1]  # the figure must not depend on the sweeper's order


def legend_texts(figure: Any) -> list[str]:
    return [
        t.get_text() for ax in figure.axes if ax.get_legend() for t in ax.get_legend().get_texts()
    ]


class TestFiniteVsAsymptotic:
    def test_the_data_is_what_the_result_holds(self) -> None:
        seen: list[Scenario] = []

        def runner(scenario: Scenario) -> SimulationResult:
            seen.append(scenario)
            return make_result()

        paper = figure_finite_vs_asymptotic(runner=runner)
        assert isinstance(paper, PaperFigure)
        assert seen == [reference_castelldefels()]
        assert paper.name == "finite_vs_asymptotic"
        assert paper.data["finite_bits"] == FINITE_BITS
        assert paper.data["asymptotic_bits"] == ASYMPTOTIC_BITS
        assert paper.data["start_s"] == START_S
        assert paper.scenario_hash == scenario_hash(reference_castelldefels())
        assert paper.scenario_name == "reference_castelldefels"
        bars = [
            c for ax in paper.figure.axes for c in ax.containers if c.get_label() == FINITE_LABEL
        ]
        assert tuple(p.get_height() for p in bars[0]) == paper.data["finite_bits"]
        assert ASYMPTOTIC_LABEL in legend_texts(paper.figure)

    def test_the_data_is_frozen(self) -> None:
        paper = figure_finite_vs_asymptotic(runner=lambda s: make_result())
        with pytest.raises(TypeError):
            paper.data["finite_bits"] = ()  # type: ignore[index]

    def test_refuses_a_result_of_another_scenario(self) -> None:
        other = make_result(scenario=ntanos_2021(0.75))
        with pytest.raises(DomainError, match="another's numbers"):
            figure_finite_vs_asymptotic(runner=lambda s: other)

    def test_a_given_scenario_is_used(self) -> None:
        shorter = Scenario.model_validate(
            {**reference_castelldefels().model_dump(mode="python"), "name": "short"}
        )
        paper = figure_finite_vs_asymptotic(
            runner=lambda s: make_result(scenario=s), scenario=shorter
        )
        assert paper.scenario_name == "short"

    def test_a_degraded_run_is_marked(self) -> None:
        paper = figure_finite_vs_asymptotic(
            runner=lambda s: make_result(warnings=[DEGRADED_WARNING])
        )
        assert [t.get_gid() for t in paper.figure.texts] == [DEGRADED_GID]


class TestMaskOptimum:
    def test_sweeps_the_mask_and_finds_the_sampled_optimum(self) -> None:
        sweeper = FakeSweeper()
        paper = figure_mask_optimum(sweeper=sweeper)
        ((scenario, parameters, metrics),) = sweeper.calls
        assert scenario == reference_castelldefels()
        assert parameters == {MASK_PARAMETER: [2.0, 5.0, 8.0, 10.0, 15.0]}
        assert metrics == (FINITE_METRIC, ASYMPTOTIC_METRIC)
        assert paper.data["masks_deg"] == (2.0, 5.0, 8.0, 10.0, 15.0)
        assert paper.data["finite_bits"] == tuple(
            MASK_TABLE[m][0] for m in (2.0, 5.0, 8.0, 10.0, 15.0)
        )
        assert paper.data["asymptotic_bits"] == tuple(
            MASK_TABLE[m][1] for m in (2.0, 5.0, 8.0, 10.0, 15.0)
        )
        assert paper.data["optimum_mask_deg"] == (8.0,)
        finite_axes, asymptotic_axes = paper.figure.axes
        assert tuple(ydata(finite_axes.lines[0])) == paper.data["finite_bits"]
        assert tuple(ydata(asymptotic_axes.lines[0])) == paper.data["asymptotic_bits"]
        assert "optimum 8°" in [t.get_text() for t in finite_axes.texts]
        assert ASYMPTOTIC_LABEL in legend_texts(paper.figure)
        paper.figure.draw_without_rendering()

    @pytest.mark.parametrize("masks", [(10.0,), (5.0, 5.0, 10.0)])
    def test_refuses_fewer_than_two_distinct_masks(self, masks: tuple[float, ...]) -> None:
        with pytest.raises(DomainError, match="two distinct"):
            figure_mask_optimum(masks, sweeper=FakeSweeper())

    def test_refuses_a_sweep_that_dropped_a_point(self) -> None:
        with pytest.raises(DomainError, match="returned masks"):
            figure_mask_optimum(sweeper=FakeSweeper(drop=5.0))


class TestMonteCarloSpread:
    def test_the_reference_ensemble(self) -> None:
        scenario = monte_carlo_reference_scenario()
        assert scenario.monte_carlo is not None
        assert scenario.monte_carlo.scintillation_correlation_time_s == 0.002
        assert scenario.monte_carlo.pointing_correlation_time_s == 0.02
        base = reference_castelldefels().model_dump(mode="python")
        derived = scenario.model_dump(mode="python")
        assert {k for k in base if base[k] != derived[k]} == {"name", "monte_carlo"}

    def test_the_data_is_the_ensemble(self) -> None:
        scenario = monte_carlo_reference_scenario()
        paper = figure_monte_carlo_spread(
            runner=lambda s: make_result(scenario=s, monte_carlo=True)
        )
        assert paper.scenario_hash == scenario_hash(scenario)
        assert paper.data["design_finite_bits"] == FINITE_BITS
        assert paper.data["quantiles"] == (0.05, 0.5, 0.95)
        assert paper.data["quantile_0.05_bits"] == QUANTILE_BITS[0]
        assert paper.data["quantile_0.5_bits"] == QUANTILE_BITS[1]
        assert paper.data["quantile_0.95_bits"] == QUANTILE_BITS[2]
        assert paper.data["outage_probability"] == (0.0, 1.0, 0.0, 1.0)
        assert ASYMPTOTIC_LABEL not in legend_texts(paper.figure)
        assert paper.figure.axes[0].get_ylabel() == "finite key per pass"

    def test_refuses_a_scenario_without_monte_carlo(self) -> None:
        with pytest.raises(DomainError, match="no monte_carlo section"):
            figure_monte_carlo_spread(
                runner=lambda s: make_result(scenario=s), scenario=reference_castelldefels()
            )

    def test_refuses_a_result_without_monte_carlo(self) -> None:
        with pytest.raises(DomainError, match="returned no Monte Carlo"):
            figure_monte_carlo_spread(runner=lambda s: make_result(scenario=s))


class TestTheEngineIsInjected:
    def test_the_default_runner_without_the_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "quoss.engine.pipeline", None)
        with pytest.raises(ConfigurationError, match="runner="):
            figure_finite_vs_asymptotic()

    def test_the_default_sweeper_without_the_engine(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setitem(sys.modules, "quoss.engine.sweep", None)
        with pytest.raises(ConfigurationError, match="sweeper="):
            figure_mask_optimum()

    def test_the_default_runner_refuses_a_horizontal_scenario_by_name(self) -> None:
        """The paper figures are downlink figures, and ``run()`` now takes either kind.

        Since ADR 0024 ``quoss.engine.pipeline.run`` returns whichever result the
        scenario's ``link`` tag names, so the default runner can be handed
        something with no passes and no days to plot. It says so here, naming the
        figure that *is* the horizontal one, instead of failing on the first
        attribute a plotting routine reaches for.
        """
        with pytest.raises(ConfigurationError, match="horizontal_key_against_distance"):
            figure_finite_vs_asymptotic(scenario=ge1_two_terminals())  # type: ignore[arg-type]


class TestWithoutMatplotlib:
    def test_every_figure_names_the_extra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hide_matplotlib(monkeypatch)
        for build in (
            lambda: figure_finite_vs_asymptotic(runner=lambda s: make_result()),
            lambda: figure_mask_optimum(sweeper=FakeSweeper()),
            lambda: figure_monte_carlo_spread(runner=lambda s: make_result()),
        ):
            with pytest.raises(ConfigurationError, match=r"quoss\[viz\]"):
                build()


@pytest.mark.slow
class TestTheDefaultEngineIsTheRealOne:
    """The injected-engine tests above check the *absence* of the engine.

    They pass just as well if the import succeeds and the call never happens, so
    the path that actually runs the pipeline needs its own check. These two are
    the only places in `tests/viz` where a figure is drawn from numbers the
    engine computed rather than from a hand-built result.
    """

    def test_the_default_runner_draws_a_figure_from_a_real_run(self) -> None:
        paper = figure_finite_vs_asymptotic()
        assert paper.figure.axes
        assert paper.data["finite_bits"]
        assert all(value >= 0.0 for value in paper.data["finite_bits"])

    def test_the_default_sweeper_finds_the_optimum_the_sweep_module_measures(self) -> None:
        """Same five masks as `tests/engine/test_sweep.py`, through the figure API.

        The optimum is at 8 degrees there and has to be at 8 degrees here: the
        figure calls `run_sweep` and adds only presentation, so a different
        answer would mean the figure is computing physics of its own.
        """
        paper = figure_mask_optimum()
        assert paper.data["optimum_mask_deg"] == (8.0,)
