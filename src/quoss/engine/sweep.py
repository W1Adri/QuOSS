"""Parameter sweeps as a first-class run: every point a validated scenario, every metric a column.

What a sweep is, for someone arriving new
-----------------------------------------
A figure in a paper is almost always a sweep: the same simulation run at
several values of one or two parameters, and one number read off each run.
``notes/GUIA_REIMPLEMENTACION.md`` §5 names the symptom of not having them in the
engine — a 544-line ``routers/paper.py`` in SimulCTTC. :func:`run_sweep` takes
a base :class:`~quoss.scenario.models.Scenario`, a :class:`SweepSpec` naming
**dotted paths** into it (``passes.minimum_elevation_deg``,
``stations.0.receive_aperture_m``) with the values to try, and a list of
**metrics** — dotted paths into the :class:`~quoss.scenario.result.SimulationResult`
(``daily.finite_bits``) — and returns one row per point.

Why every point goes back through the validators
------------------------------------------------
The obvious implementation edits the frozen model in place with
``model_copy(update=...)``. Pydantic does not validate a ``model_copy``, so a
sweep of ``passes.minimum_elevation_deg`` over ``[-5, 5]`` would hand the engine
a negative mask that no scenario file could contain, and the physics would
refuse it three stages later with a message about radians. Here each point is
dumped to plain JSON, edited, and read back with
:func:`~quoss.scenario.io.loads_scenario`, so **every** validator runs on every
point — field bounds, the cross-model rules, the TLE checksum — and an invalid
point is a :class:`~quoss.core.errors.ScenarioError` naming the point and the
field before any point has run.

Grid and zip
------------
``mode="grid"`` is the Cartesian product, the last parameter varying fastest
(the order of nested ``for`` loops written in the parameters' order).
``mode="zip"`` pairs the i-th values of every parameter, which is how a sweep
moves two coupled parameters together (an aperture and the station that has
it); lists of different lengths are refused, because :func:`zip` would silently
drop the tail.

Metrics are reduced to one number, and one reduction is flagged
---------------------------------------------------------------
A metric path ends on an array — ``daily.finite_bits`` has one entry per day,
``passes.finite_bits`` one per pass — and the row holds its **sum**, which for
bits is the total over the window. Integer segments index into arrays
(``monte_carlo.quantile_bits.1`` is the median row). Summing a quantile over
passes is **not** a quantile of the day
(``docs/adr/0012-correlated-fading-and-monte-carlo.md`` §8: quantiles of sums,
not sums of quantiles), so a metric through ``quantile_bits`` records a
``WARNING`` saying so.

The measurement that justifies the module
-----------------------------------------
``docs/adr/0011-the-block-is-the-pass.md`` §5 found by hand that the finite-key
day has an **interior optimum in the elevation mask near 8 degrees**. The same
sweep, as a :class:`SweepSpec` over ``passes.minimum_elevation_deg`` on the
reference scenario, reproduces it: 2, 5, 8, 10 and 15 degrees give
409 584 / 427 602 / 435 462 / 433 442 / 407 794 finite bits with the station's
30 m wired into the turbulence profile, and a chain wired by hand gives the same
numbers to the bit (``tests/e2e/test_reference_scenarios.py::TestTheMaskSweep``).
The maximum is at 8 degrees, and the hand chain at the 0 m turbulence height of
``tests/system/reference.py`` gives the system tests' 408 946 at 2 degrees and
434 938 at 8 — the same optimum from the same mechanism, 0.1-0.2 % lower.

Examples
--------
>>> from quoss.scenario.defaults import reference_castelldefels
>>> spec = SweepSpec({"passes.minimum_elevation_deg": [5.0, 10.0], "time.step_s": [10.0]})
>>> [point for point in spec.points()]
[{'passes.minimum_elevation_deg': 5.0, 'time.step_s': 10.0}, {'passes.minimum_elevation_deg': 10.0, 'time.step_s': 10.0}]
>>> scenario = apply_point(reference_castelldefels(), {"passes.minimum_elevation_deg": 8.0})
>>> scenario.passes.minimum_elevation_deg
8.0
"""

from __future__ import annotations

import dataclasses
import itertools
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

import numpy as np

from quoss.core.errors import DegradationLog, DomainError, ScenarioError
from quoss.core.rng import RandomSource
from quoss.engine.cache import ResultCache
from quoss.engine.parallel import map_workers, validated_workers
from quoss.engine.pipeline import run
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import loads_scenario
from quoss.scenario.models import AnyScenario, HorizontalScenario
from quoss.scenario.result import (
    AnyResult,
    DailyResults,
    HorizontalBudgetResults,
    HorizontalSessionResults,
    MonteCarloResults,
    MultiStationResults,
    PassResults,
    RelayResults,
)

__all__ = [
    "DOWNLINK_METRIC_ROOTS",
    "HORIZONTAL_METRIC_ROOTS",
    "METRIC_ROOTS",
    "SweepResult",
    "SweepSpec",
    "apply_point",
    "metric_value",
    "run_sweep",
]

_WHERE = "quoss.engine.sweep"

DOWNLINK_METRIC_ROOTS: Mapping[str, type] = MappingProxyType(
    {
        "passes": PassResults,
        "daily": DailyResults,
        "monte_carlo": MonteCarloResults,
        "multi_station": MultiStationResults,
        "relay": RelayResults,
    }
)
"""Sections of a :class:`~quoss.scenario.result.SimulationResult` a metric may start from."""

HORIZONTAL_METRIC_ROOTS: Mapping[str, type] = MappingProxyType(
    {
        "budget": HorizontalBudgetResults,
        "session": HorizontalSessionResults,
    }
)
"""Sections of a :class:`~quoss.scenario.result.HorizontalResult`.

Two, against the downlink's five, and the names do not overlap — which is what
lets :func:`run_sweep` refuse ``daily.finite_bits`` on a horizontal scenario
**before the first point runs**, naming the sections that do exist, instead of
running every point and failing on the first metric lookup.
"""

METRIC_ROOTS: Mapping[str, type] = MappingProxyType(
    {**DOWNLINK_METRIC_ROOTS, **HORIZONTAL_METRIC_ROOTS}
)
"""Every result section a metric may start from, of either geometry."""


@dataclass(frozen=True, slots=True)
class SweepSpec:
    """Which scenario paths to vary, over which values, combined how.

    Parameters
    ----------
    parameters : Mapping[str, Sequence[Any]]
        Dotted scenario path to the values it takes, in order. At least one
        path, each with at least one value.
    mode : {"grid", "zip"}
        Cartesian product, or the i-th values together.

    Raises
    ------
    ScenarioError
        On an empty sweep, an empty value list, an unknown mode, or ``zip``
        lists of different lengths.

    Examples
    --------
    >>> SweepSpec({"a": [1, 2], "b": [3]}, mode="zip")
    Traceback (most recent call last):
        ...
    quoss.core.errors.ScenarioError: zip sweep needs equal-length value lists, got lengths {'a': 2, 'b': 1}.
    """

    parameters: Mapping[str, Sequence[Any]]
    mode: Literal["grid", "zip"] = "grid"

    def __post_init__(self) -> None:
        """Freeze the value lists and check the combination rule."""
        if self.mode not in ("grid", "zip"):
            raise ScenarioError(f"sweep mode must be 'grid' or 'zip', got {self.mode!r}.")
        frozen: dict[str, tuple[Any, ...]] = {}
        for path, values in dict(self.parameters).items():
            if not isinstance(path, str) or not path:
                raise ScenarioError(
                    f"sweep parameter paths must be non-empty strings, got {path!r}."
                )
            if isinstance(values, str | bytes) or not isinstance(values, Sequence):
                raise ScenarioError(
                    f"sweep parameter {path!r} needs a list of values, got {type(values).__name__}."
                )
            if len(values) == 0:
                raise ScenarioError(f"sweep parameter {path!r} has no values.")
            frozen[path] = tuple(values)
        if not frozen:
            raise ScenarioError("a sweep needs at least one parameter.")
        if self.mode == "zip":
            lengths = {path: len(values) for path, values in frozen.items()}
            if len(set(lengths.values())) != 1:
                raise ScenarioError(
                    f"zip sweep needs equal-length value lists, got lengths {lengths}."
                )
        object.__setattr__(self, "parameters", MappingProxyType(frozen))

    @property
    def paths(self) -> tuple[str, ...]:
        """The parameter paths, in declaration order."""
        return tuple(self.parameters)

    def points(self) -> list[dict[str, Any]]:
        """Return every point as ``{path: value}``, in sweep order."""
        columns = [self.parameters[path] for path in self.paths]
        combos = itertools.product(*columns) if self.mode == "grid" else zip(*columns, strict=True)
        return [dict(zip(self.paths, combo, strict=True)) for combo in combos]


@dataclass(frozen=True, slots=True)
class SweepResult:
    """One row per point: the parameter values, the metrics and the scenario hash.

    Parameters
    ----------
    points : tuple[Mapping[str, Any], ...]
        The ``{path: value}`` of each point, in sweep order.
    records : tuple[Mapping[str, Any], ...]
        One row per point: every path with its value, every metric with its
        summed value, and ``"scenario_hash"``.
    """

    points: tuple[Mapping[str, Any], ...]
    records: tuple[Mapping[str, Any], ...]

    def to_records(self) -> list[dict[str, Any]]:
        """Return the rows as plain, independent dicts."""
        return [dict(record) for record in self.records]

    def column(self, name: str) -> list[Any]:
        """Return one column — a parameter path, a metric or ``scenario_hash``.

        Raises
        ------
        KeyError
            If no row has that column.
        """
        if not self.records or name not in self.records[0]:
            raise KeyError(
                f"no column {name!r}; columns: {list(self.records[0]) if self.records else []}."
            )
        return [record[name] for record in self.records]


# --------------------------------------------------------------------------- #
# Points
# --------------------------------------------------------------------------- #
def apply_point(scenario: AnyScenario, point: Mapping[str, Any]) -> AnyScenario:
    """Return the scenario with every ``path: value`` of a point set and re-validated.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        The base scenario, of either geometry.
    point : Mapping[str, Any]
        Dotted path to value. A path segment that is an integer indexes a
        list (``stations.1.altitude_m``).

    Returns
    -------
    Scenario or HorizontalScenario
        A new scenario of the same kind, that passed every validator. The kind
        cannot change: the ``link`` tag is part of the dump a point edits, and
        a point that tried to rewrite it would have to supply a whole other
        scenario's sections and would be refused by name.

    Raises
    ------
    ScenarioError
        If a path does not name an existing field, or the edited scenario
        fails validation; the message names the point.
    """
    data = scenario.model_dump(mode="json")
    for path, value in point.items():
        _set_path(data, path, value, point)
    try:
        return loads_scenario(json.dumps(data), format="json")
    except ScenarioError as error:
        raise ScenarioError(
            f"sweep point {dict(point)!r} is not a valid scenario: {error}"
        ) from error


def _set_path(data: dict[str, Any], path: str, value: Any, point: Mapping[str, Any]) -> None:
    node: Any = data
    parts = path.split(".")
    for depth, part in enumerate(parts):
        last = depth == len(parts) - 1
        where = ".".join(parts[: depth + 1])
        if isinstance(node, list):
            if not part.isdigit() or int(part) >= len(node):
                raise ScenarioError(
                    f"sweep point {dict(point)!r}: {where!r} indexes a list of {len(node)} items; "
                    "use an integer segment below that."
                )
            if last:
                node[int(part)] = value
            else:
                node = node[int(part)]
        elif isinstance(node, dict):
            if part not in node:
                raise ScenarioError(
                    f"sweep point {dict(point)!r}: {where!r} is not a scenario field; fields "
                    f"here: {sorted(node)}."
                )
            if last:
                node[part] = value
            else:
                node = node[part]
        else:
            raise ScenarioError(
                f"sweep point {dict(point)!r}: {where!r} goes inside a value "
                f"({type(node).__name__}), not a section of the scenario."
            )


# --------------------------------------------------------------------------- #
# Metrics
# --------------------------------------------------------------------------- #
def _check_metric(metric: str, roots: Mapping[str, type] = METRIC_ROOTS) -> None:
    """Refuse a metric path that no result section could answer.

    ``roots`` narrows the check to one geometry's sections, which is how
    :func:`run_sweep` turns "this metric belongs to the other kind of scenario"
    into a message naming the sections that do exist.
    """
    if not isinstance(metric, str) or not metric:
        raise ScenarioError(f"a metric must be a non-empty dotted path, got {metric!r}.")
    parts = metric.split(".")
    root = parts[0]
    if root not in roots:
        elsewhere = (
            f" It is a section of the other link geometry's result; this sweep's scenario is "
            f"the {'horizontal' if roots is HORIZONTAL_METRIC_ROOTS else 'downlink'} one."
            if root in METRIC_ROOTS
            else ""
        )
        raise ScenarioError(
            f"metric {metric!r} starts at {root!r}, which is not a result section; valid roots: "
            f"{sorted(roots)}.{elsewhere}"
        )
    if len(parts) < 2 or not hasattr(roots[root], parts[1]):
        attribute = parts[1] if len(parts) > 1 else ""
        names = sorted(f.name for f in dataclasses.fields(roots[root]))
        raise ScenarioError(
            f"metric {metric!r}: {root} has no attribute {attribute!r}; fields: {names}."
        )


def metric_value(result: AnyResult, metric: str) -> float:
    """Resolve a dotted metric path in a result and sum it to one number.

    Parameters
    ----------
    result : SimulationResult or HorizontalResult
        A finished run of either geometry.
    metric : str
        ``<section>.<attribute>[.<index>...]``, the section one of
        :data:`METRIC_ROOTS`. A horizontal result's sections hold scalars rather
        than arrays, and summing a scalar is the identity, so the same resolver
        serves both.

    Returns
    -------
    float
        The sum of every element the path reaches.

    Raises
    ------
    ScenarioError
        If the path is unknown, the section is absent from this result (a
        Monte Carlo metric of a scenario without one), an index is out of
        range, or the value is not numeric.
    """
    _check_metric(metric)
    parts = metric.split(".")
    node: Any = result
    for depth, part in enumerate(parts):
        where = ".".join(parts[: depth + 1])
        if node is None:
            raise ScenarioError(
                f"metric {metric!r}: {'.'.join(parts[:depth])!r} is absent from this result; the "
                "scenario did not ask for that stage."
            )
        if isinstance(node, np.ndarray | list | tuple) and part.lstrip("-").isdigit():
            try:
                node = node[int(part)]
            except IndexError as error:
                raise ScenarioError(
                    f"metric {metric!r}: index {where!r} is out of range."
                ) from error
        elif hasattr(node, part):
            node = getattr(node, part)
        else:
            raise ScenarioError(f"metric {metric!r}: {where!r} does not exist in the result.")
    if node is None:
        raise ScenarioError(f"metric {metric!r} is absent from this result.")
    try:
        values = np.asarray(node, dtype=np.float64)
    except (TypeError, ValueError) as error:
        raise ScenarioError(f"metric {metric!r} is not numeric ({type(node).__name__}).") from error
    return float(np.sum(values))


# --------------------------------------------------------------------------- #
# The sweep
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class _PointTask:
    scenario: AnyScenario
    point: Mapping[str, Any]
    metrics: tuple[str, ...]
    random_source: RandomSource | None
    cache: ResultCache | None


def _run_point(task: _PointTask, degradations: DegradationLog) -> tuple[str, tuple[float, ...]]:
    degradations.info(
        "engine.sweep-point",
        f"sweep point {dict(task.point)!r}; the entries until the next point are its run's.",
        where=f"{_WHERE}.run_sweep",
        point=dict(task.point),
    )
    result = run(
        task.scenario,
        random_source=task.random_source,
        cache=task.cache,
        workers=1,
        degradations=degradations,
    )
    return result.provenance.scenario_hash, tuple(metric_value(result, m) for m in task.metrics)


def run_sweep(
    scenario: AnyScenario,
    spec: SweepSpec,
    *,
    metrics: Sequence[str] = ("daily.finite_bits",),
    workers: int = 1,
    cache: ResultCache | None = None,
    random_source: RandomSource | None = None,
    degradations: DegradationLog | None = None,
) -> SweepResult:
    """Run a scenario at every point of a sweep and tabulate the metrics.

    Every point is built and validated before the first one runs, so a sweep
    whose fifth point is invalid fails in milliseconds rather than after four
    runs.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        The base scenario. Its geometry decides which metric roots are legal,
        and a metric from the other geometry is refused before the first point
        runs, with the sections that do exist named.
    spec : SweepSpec
        The points.
    metrics : Sequence[str], optional
        Dotted result paths, each summed to one number per point. Default the
        day's finite key.
    workers : int, optional
        Worker processes, one point each; each point's run uses one process.
    cache : ResultCache, optional
        Passed to every point's run.
    random_source : RandomSource, optional
        When given, each point gets its own :meth:`~quoss.core.rng.RandomSource.spawn`
        child, in sweep order. When not, each point seeds from its own
        scenario's ``monte_carlo.seed`` — the **same** seed at every point
        unless the sweep varies it, which is deliberate: common random numbers
        make the difference between two points the parameter's effect and not
        two ensembles' noise.
    degradations : DegradationLog, optional
        Receives every point's entries, in sweep order, each block opened by an
        ``INFO`` ``engine.sweep-point``. Created when not given.

    Returns
    -------
    SweepResult
        One row per point.

    Raises
    ------
    ScenarioError
        On an invalid point, an unknown metric, or a metric absent from a
        point's result.
    DomainError
        If ``workers`` is not a positive integer.
    """
    log = DegradationLog() if degradations is None else degradations
    if not isinstance(spec, SweepSpec):
        raise DomainError(f"spec must be a SweepSpec, got {type(spec).__name__}.")
    count = validated_workers(workers)
    names = tuple(metrics)
    if not names:
        raise ScenarioError("a sweep needs at least one metric.")
    roots = (
        HORIZONTAL_METRIC_ROOTS
        if isinstance(scenario, HorizontalScenario)
        else (DOWNLINK_METRIC_ROOTS)
    )
    for metric in names:
        _check_metric(metric, roots)
        if "quantile_bits" in metric.split("."):
            log.warn(
                "engine.sweep-sums-quantiles",
                f"metric {metric!r} sums per-pass ensemble quantiles; a sum of quantiles is not "
                "the quantile of the summed key (ADR 0012 §8). Read the day's quantiles from the "
                "engine.monte-carlo-daily entries instead.",
                where=f"{_WHERE}.run_sweep",
                metric=metric,
            )
    points = spec.points()
    scenarios = [apply_point(scenario, point) for point in points]
    children: list[RandomSource | None] = (
        list(random_source.spawn(len(points)))
        if random_source is not None
        else [None] * len(points)
    )
    tasks = [
        _PointTask(scenario=s, point=p, metrics=names, random_source=c, cache=cache)
        for s, p, c in zip(scenarios, points, children, strict=True)
    ]
    outcomes = map_workers(_run_point, tasks, workers=count, degradations=log)
    records: list[Mapping[str, Any]] = []
    for point, point_scenario, (hash_, values) in zip(points, scenarios, outcomes, strict=True):
        assert hash_ == scenario_hash(point_scenario)
        row: dict[str, Any] = dict(point)
        row.update(zip(names, values, strict=True))
        row["scenario_hash"] = hash_
        records.append(MappingProxyType(row))
    return SweepResult(
        points=tuple(MappingProxyType(dict(p)) for p in points),
        records=tuple(records),
    )
