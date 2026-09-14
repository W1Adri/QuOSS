r"""The paper's figures: each one a versioned scenario, a run, a plot, and the numbers it drew.

What this module is for, for someone arriving new
-------------------------------------------------
A figure in a paper is a claim, and a claim needs a pedigree: which inputs,
which code, which numbers. So a paper figure here is not a script that happens
to produce a PDF; it is a function that

1. starts from a **versioned scenario** — :func:`quoss.scenario.defaults.reference_castelldefels`,
   which ``tests/scenario/test_scenario_files.py`` proves equal to the committed
   ``scenarios/reference_castelldefels.yaml`` and ``tests/scenario/test_defaults.py``
   proves equal to the link every number of ``docs/adr/0011-the-block-is-the-pass.md``
   was measured on;
2. runs the engine on it (``runner``/``sweeper``, injectable);
3. checks that what came back is a result *of that scenario* (by
   :func:`~quoss.scenario.hash.scenario_hash`), so a cached or mis-wired result
   for other inputs cannot be drawn under this figure's caption;
4. draws it under :func:`~quoss.viz.style.use_publication_style` with the
   plots of :mod:`quoss.viz.plots`;
5. returns a :class:`PaperFigure`: the figure **and** the numbers it plotted,
   so a test asserts the bars rather than squinting at a PNG.

The three figures, and the finding each one exists to show
----------------------------------------------------------
:func:`figure_finite_vs_asymptotic`
    Key per pass on the reference day, finite against asymptotic. The finding
    (ADR 0011): 432 985 certified bits against 3.78 Mbit asymptotic, and two of
    four passes certify **exactly zero** where the asymptotic integral claims
    320 and 199 kbit.
:func:`figure_mask_optimum`
    The day's key against the elevation mask. The finding (ADR 0011 §5): the
    asymptotic key can only grow as the mask drops, while the finite key has an
    **interior optimum** (8 deg on the reference day, 434 938 bits against
    408 946 at 2 deg), because low-elevation samples add errors to the whole
    block. Two panels, not two axes on one: the two curves differ by a factor
    of nine and a twin axis would decide where they cross.
:func:`figure_monte_carlo_spread`
    Finite key per pass with the Monte Carlo P5-P95 whisker. The findings
    (``notes`` §28, ADR 0012): the design number — the fade quantile held for
    the whole pass — under-reports the typical day by 43 % (432 985 against a
    758 314-bit median), and the spread at the physical correlation times is a
    few percent, set by counting statistics rather than by fading.

Why ``runner`` and ``sweeper`` are arguments
--------------------------------------------
So that the figures are testable without the engine (a fake returning a
constructed result is milliseconds; a real day is seconds) and so that the CLI
can pass a runner with a cache or several workers. The defaults import
:func:`quoss.engine.pipeline.run` and :func:`quoss.engine.sweep.run_sweep`
lazily; if the engine cannot be imported the call raises
:class:`~quoss.core.errors.ConfigurationError` rather than an ``ImportError``
from deep inside.

The sweeper's contract is deliberately narrower than ``run_sweep``: it takes
``(scenario, parameters, metrics)`` and returns records, so a fake does not
need to build a ``SweepSpec`` (an engine type). The default adapts it.

What it deliberately leaves out
-------------------------------
Figures of the Ntanos et al. 2021 stations (stage 8, ``validation/``, owns the
comparison with the paper) and multi-station or relay figures (no versioned
scenario with those sections yet; the plots exist in :mod:`quoss.viz.plots`).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

import numpy as np

from quoss.core.errors import ConfigurationError, DomainError
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import MonteCarloSpec, Scenario
from quoss.scenario.result import SimulationResult
from quoss.viz.plots import mark_degradations, plot_pass_key_volume, plot_sweep
from quoss.viz.style import (
    COLUMN_WIDTH_IN,
    INK,
    SMALL_FONT_SIZE_PT,
    require_matplotlib,
    use_publication_style,
)

if TYPE_CHECKING:
    from matplotlib.figure import Figure

__all__ = [
    "ASYMPTOTIC_METRIC",
    "FINITE_METRIC",
    "MASK_PARAMETER",
    "MONTE_CARLO_REFERENCE",
    "PaperFigure",
    "Runner",
    "Sweeper",
    "figure_finite_vs_asymptotic",
    "figure_mask_optimum",
    "figure_monte_carlo_spread",
    "monte_carlo_reference_scenario",
]

Runner = Callable[[Scenario], SimulationResult]
"""Runs one scenario. Default: :func:`quoss.engine.pipeline.run`."""

Sweeper = Callable[
    [Scenario, Mapping[str, Sequence[Any]], Sequence[str]], Sequence[Mapping[str, Any]]
]
"""Runs ``(scenario, {dotted parameter: values}, metrics)`` and returns one record per point."""

MASK_PARAMETER = "passes.minimum_elevation_deg"
"""The dotted scenario path the mask figure sweeps."""

FINITE_METRIC = "daily.finite_bits"
"""The sweep metric of the finite key per day, summed over days (engine contract)."""

ASYMPTOTIC_METRIC = "daily.asymptotic_bits"
"""The sweep metric of the asymptotic key per day, summed over days."""

MONTE_CARLO_REFERENCE: Mapping[str, Any] = MappingProxyType(
    {
        "realisations": 1000,
        "seed": 20_260_913,
        "sample_counts": True,
        "scintillation_correlation_time_s": 0.002,
        "pointing_correlation_time_s": 0.02,
        "quantiles": (0.05, 0.5, 0.95),
    }
)
"""The ensemble of ``tests/system/test_monte_carlo.py::...::test_the_headline_quantiles``.

1000 realisations, Poisson counts, seed 20260913, correlation times 2 ms
(scintillation) and 20 ms (pointing) — the Taylor-hypothesis order of magnitude
derived in ``notes`` §28, where the width entering it is a declared gap. The
day's quantiles on the reference link are 735 329 / 758 314 / 782 391 bits.
"""

_TWO_PANEL_HEIGHT_IN = 3.4
_ONE_PANEL_HEIGHT_IN = 2.5


@dataclass(frozen=True, slots=True)
class PaperFigure:
    """A drawn figure together with the numbers it drew and the inputs they came from.

    Parameters
    ----------
    name : str
        Stable identifier, used as the file stem by callers.
    figure : Figure
        The ``matplotlib`` figure.
    data : Mapping[str, tuple[float, ...]]
        Every plotted series, by name, as immutable tuples.
    scenario_name : str
        The base scenario's label.
    scenario_hash : str
        :func:`~quoss.scenario.hash.scenario_hash` of the base scenario (for a
        sweep, of the scenario before the swept parameter is set).
    """

    name: str
    figure: Figure
    data: Mapping[str, tuple[float, ...]]
    scenario_name: str
    scenario_hash: str

    def __post_init__(self) -> None:
        """Freeze the data mapping and its series."""
        frozen = {str(k): tuple(float(v) for v in values) for k, values in self.data.items()}
        object.__setattr__(self, "data", MappingProxyType(frozen))


def _default_runner(scenario: Scenario) -> SimulationResult:
    try:
        from quoss.engine.pipeline import run
    except ImportError as exc:
        raise ConfigurationError(
            "the paper figures run the engine, and quoss.engine.pipeline cannot be imported; "
            "pass runner= explicitly or install a build that includes the engine."
        ) from exc
    return run(scenario)


def _default_sweeper(
    scenario: Scenario, parameters: Mapping[str, Sequence[Any]], metrics: Sequence[str]
) -> Sequence[Mapping[str, Any]]:
    try:
        from quoss.engine.sweep import SweepSpec, run_sweep
    except ImportError as exc:
        raise ConfigurationError(
            "the mask figure sweeps with the engine, and quoss.engine.sweep cannot be imported; "
            "pass sweeper= explicitly or install a build that includes the engine."
        ) from exc
    spec = SweepSpec(parameters={k: list(v) for k, v in parameters.items()}, mode="grid")
    return run_sweep(scenario, spec, metrics=tuple(metrics)).to_records()


def _run_checked(scenario: Scenario, runner: Runner | None) -> SimulationResult:
    result = (runner or _default_runner)(scenario)
    expected = scenario_hash(scenario)
    if result.provenance.scenario_hash != expected:
        raise DomainError(
            f"the runner returned a result for scenario hash {result.provenance.scenario_hash[:12]}... "
            f"({result.provenance.scenario_name!r}), not for the requested {expected[:12]}... "
            f"({scenario.name!r}); drawing it would caption one scenario with another's numbers."
        )
    return result


def monte_carlo_reference_scenario() -> Scenario:
    """Return the reference scenario with the headline Monte Carlo ensemble switched on.

    :func:`~quoss.scenario.defaults.reference_castelldefels` plus a
    ``monte_carlo`` section equal to :data:`MONTE_CARLO_REFERENCE`, renamed
    ``reference_castelldefels_monte_carlo``. Built through
    ``Scenario.model_validate`` so the section is validated like one read from
    a file.

    Returns
    -------
    Scenario
        The scenario.

    Examples
    --------
    >>> s = monte_carlo_reference_scenario()
    >>> s.monte_carlo.realisations, s.monte_carlo.seed
    (1000, 20260913)
    >>> s.passes.minimum_elevation_deg
    10.0
    """
    data = reference_castelldefels().model_dump(mode="python")
    data["name"] = "reference_castelldefels_monte_carlo"
    data["monte_carlo"] = MonteCarloSpec(**dict(MONTE_CARLO_REFERENCE)).model_dump(mode="python")
    return Scenario.model_validate(data)


def figure_finite_vs_asymptotic(
    *, runner: Runner | None = None, scenario: Scenario | None = None
) -> PaperFigure:
    """Draw the key per pass on the reference day: finite (certified) against asymptotic (not certified).

    Parameters
    ----------
    runner : Runner, optional
        Runs the scenario; default :func:`quoss.engine.pipeline.run`.
    scenario : Scenario, optional
        Defaults to :func:`~quoss.scenario.defaults.reference_castelldefels`.
        Tests pass a shortened copy.

    Returns
    -------
    PaperFigure
        ``name = "finite_vs_asymptotic"``; ``data`` holds ``finite_bits``,
        ``asymptotic_bits`` and ``start_s`` per pass.

    Raises
    ------
    DomainError
        If the runner returns a result for another scenario.
    ConfigurationError
        If ``matplotlib`` or the default engine is unavailable.
    """
    require_matplotlib()
    base = reference_castelldefels() if scenario is None else scenario
    result = _run_checked(base, runner)
    with use_publication_style():
        figure = plot_pass_key_volume(result)
    p = result.passes
    return PaperFigure(
        name="finite_vs_asymptotic",
        figure=figure,
        data={
            "finite_bits": tuple(p.finite_bits),
            "asymptotic_bits": tuple(p.asymptotic_bits),
            "start_s": tuple(p.start_s),
        },
        scenario_name=base.name,
        scenario_hash=scenario_hash(base),
    )


def figure_mask_optimum(
    masks_deg: Sequence[float] = (2.0, 5.0, 8.0, 10.0, 15.0),
    *,
    sweeper: Sweeper | None = None,
    scenario: Scenario | None = None,
) -> PaperFigure:
    """Draw the day's key against the elevation mask: finite (interior optimum) over asymptotic.

    Sweeps :data:`MASK_PARAMETER` over ``masks_deg`` on the reference scenario
    and draws two panels sharing the mask axis: the finite key per day on top,
    with its largest value ringed and labelled, and the asymptotic key below.
    The optimum is the sampled maximum — which of the requested masks gave the
    most key — not an interpolated one: between samples nothing was computed.

    Parameters
    ----------
    masks_deg : Sequence[float]
        Masks to evaluate, deg; at least two, distinct.
    sweeper : Sweeper, optional
        Runs the sweep; default wraps :func:`quoss.engine.sweep.run_sweep`.
    scenario : Scenario, optional
        Base scenario; defaults to the reference one.

    Returns
    -------
    PaperFigure
        ``name = "mask_optimum"``; ``data`` holds ``masks_deg``,
        ``finite_bits``, ``asymptotic_bits`` (sorted by mask) and
        ``optimum_mask_deg`` (one value).

    Raises
    ------
    DomainError
        If fewer than two distinct masks are asked for, or the records do not
        cover exactly the requested masks (a sweeper that dropped or invented a
        point).
    ConfigurationError
        If ``matplotlib`` or the default engine is unavailable.
    """
    require_matplotlib()
    masks = tuple(float(m) for m in masks_deg)
    if len(set(masks)) < 2 or len(set(masks)) != len(masks):
        raise DomainError(f"masks_deg needs at least two distinct values, got {masks}.")
    base = reference_castelldefels() if scenario is None else scenario
    records = list(
        (sweeper or _default_sweeper)(
            base, {MASK_PARAMETER: list(masks)}, (FINITE_METRIC, ASYMPTOTIC_METRIC)
        )
    )
    returned = sorted(float(r[MASK_PARAMETER]) for r in records if MASK_PARAMETER in r)
    if returned != sorted(masks):
        raise DomainError(
            f"the sweep returned masks {returned}, the figure asked for {sorted(masks)}."
        )

    with use_publication_style():
        matplotlib_figure = _two_panel_figure()
        ax_finite, ax_asymptotic = matplotlib_figure.subplots(2, 1, sharex=True)
        plot_sweep(
            records,
            x=MASK_PARAMETER,
            y=FINITE_METRIC,
            ax=ax_finite,
            xlabel="",
            ylabel="finite key per day [bit]",
        )
        plot_sweep(
            records,
            x=MASK_PARAMETER,
            y=ASYMPTOTIC_METRIC,
            ax=ax_asymptotic,
            xlabel="elevation mask [deg]",
            ylabel="asymptotic key per day [bit]",
        )
        order = np.argsort([float(r[MASK_PARAMETER]) for r in records])
        sorted_masks = np.array([float(records[i][MASK_PARAMETER]) for i in order])
        finite = np.array([float(records[i][FINITE_METRIC]) for i in order])
        asymptotic = np.array([float(records[i][ASYMPTOTIC_METRIC]) for i in order])
        best = int(np.argmax(finite))
        ax_finite.plot(
            sorted_masks[best],
            finite[best],
            marker="o",
            markersize=9.0,
            markerfacecolor="none",
            markeredgecolor=INK,
            linestyle="none",
        )
        ax_finite.annotate(
            f"optimum {sorted_masks[best]:g}°",
            (sorted_masks[best], finite[best]),
            xytext=(6.0, -10.0),
            textcoords="offset points",
            fontsize=SMALL_FONT_SIZE_PT,
            color=INK,
        )
        for ax in (ax_finite, ax_asymptotic):
            ax.legend(loc="lower right")

    return PaperFigure(
        name="mask_optimum",
        figure=matplotlib_figure,
        data={
            "masks_deg": tuple(sorted_masks),
            "finite_bits": tuple(finite),
            "asymptotic_bits": tuple(asymptotic),
            "optimum_mask_deg": (float(sorted_masks[best]),),
        },
        scenario_name=base.name,
        scenario_hash=scenario_hash(base),
    )


def figure_monte_carlo_spread(
    *, runner: Runner | None = None, scenario: Scenario | None = None
) -> PaperFigure:
    """Draw the finite key per pass with the Monte Carlo spread over the design number.

    Parameters
    ----------
    runner : Runner, optional
        Runs the scenario; default :func:`quoss.engine.pipeline.run`.
    scenario : Scenario, optional
        Defaults to :func:`monte_carlo_reference_scenario`. Must have a
        ``monte_carlo`` section.

    Returns
    -------
    PaperFigure
        ``name = "monte_carlo_spread"``; ``data`` holds ``design_finite_bits``,
        ``mean_bits``, ``outage_probability``, ``quantiles`` and one
        ``quantile_<p>_bits`` series per quantile (``quantile_0.05_bits`` ...).

    Raises
    ------
    DomainError
        If the scenario has no ``monte_carlo`` section, the result came back
        without one, or it is a result of another scenario.
    ConfigurationError
        If ``matplotlib`` or the default engine is unavailable.
    """
    require_matplotlib()
    base = monte_carlo_reference_scenario() if scenario is None else scenario
    if base.monte_carlo is None:
        raise DomainError(
            f"scenario {base.name!r} has no monte_carlo section; the spread figure needs one."
        )
    result = _run_checked(base, runner)
    mc = result.monte_carlo
    if mc is None:
        raise DomainError(
            f"the run of {base.name!r} returned no Monte Carlo section although the scenario "
            "asked for one."
        )
    with use_publication_style():
        figure = plot_pass_key_volume(result, show_asymptotic=False)
        figure.axes[0].set_ylabel("finite key per pass")
        mark_degradations(figure, result.warnings)
    data: dict[str, tuple[float, ...]] = {
        "design_finite_bits": tuple(result.passes.finite_bits),
        "mean_bits": tuple(mc.mean_bits),
        "outage_probability": tuple(mc.outage_probability),
        "quantiles": tuple(mc.quantiles),
    }
    for q, row in zip(mc.quantiles, mc.quantile_bits, strict=True):
        data[f"quantile_{q:g}_bits"] = tuple(row)
    return PaperFigure(
        name="monte_carlo_spread",
        figure=figure,
        data=data,
        scenario_name=base.name,
        scenario_hash=scenario_hash(base),
    )


def _two_panel_figure() -> Any:
    from matplotlib.figure import Figure

    return Figure(figsize=(COLUMN_WIDTH_IN, _TWO_PANEL_HEIGHT_IN), layout="constrained")
