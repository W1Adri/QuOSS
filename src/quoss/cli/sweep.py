"""``quoss sweep <scenario.yaml> <spec.yaml>``: one row per point of a sweep.

What a sweep is, and why the spec is a file
--------------------------------------------
A figure in a paper is almost always a sweep: the same scenario run at several
values of one or two parameters, with one number read off each run
(:mod:`quoss.engine.sweep`). This subcommand is that, from the shell.

**The spec is a file and not an inline string**, which is the one decision here
worth defending. ``quoss sweep scen.yaml "path.distance_m=200,1000,5000"`` is
shorter to type and it is the wrong shape, for the same reason the scenario is a
file: a figure has to be reproducible from something that is committed. An
inline string lives in a shell history, which is not versioned, is not hashed,
and is not what a reviewer can be handed. The file is a datum like the scenario
is a datum -- ADR 0014's first principle, applied one level up -- and writing one
costs three lines. It also keeps this module from becoming the parser of a
second little language whose escaping rules nobody wrote down.

The spec format
---------------
YAML or JSON, by suffix, the same rule :func:`~quoss.scenario.io.format_for_path`
applies to a scenario::

    parameters:                      # dotted scenario paths to value lists
      path.distance_m: [200.0, 1000.0, 2410.0, 5000.0]
    mode: grid                       # optional: grid (default) or zip
    metrics: [session.finite_bits]   # optional: default daily.finite_bits

``parameters`` are dotted paths into the scenario, exactly as
:class:`~quoss.engine.sweep.SweepSpec` takes them, and ``metrics`` are dotted
paths into the result. Which metric roots are legal depends on the scenario's
geometry and is checked **before the first point runs**
(:data:`~quoss.engine.sweep.HORIZONTAL_METRIC_ROOTS`), so a downlink metric on a
horizontal file fails in milliseconds and names the sections that do exist.

Two things this module does not do: it does not evaluate the metric (
:func:`~quoss.engine.sweep.metric_value` does) and it does not decide which
metric roots apply (:func:`~quoss.engine.sweep.run_sweep` does, from the
scenario's geometry). It reads a file, calls, and writes a table.

What it writes
--------------
The table goes to standard output as CSV -- one row per point, the parameter
columns first, then one column per metric, then ``scenario_hash``, which is what
ties a row to the exact inputs that produced it. With ``--out DIR`` the same CSV
is written to ``DIR/sweep.csv`` and the spec, the rows and the base scenario's
hash to ``DIR/sweep.json``.

Examples
--------
.. code-block:: bash

    uv run quoss sweep scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml
    uv run quoss sweep scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml --out out/distance
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

import yaml

from quoss.cli.report import exit_status, print_warnings
from quoss.core.errors import DegradationLog, ScenarioError
from quoss.engine.sweep import SweepSpec, run_sweep
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import format_for_path, load_scenario

__all__ = ["DEFAULT_METRICS", "add_parser", "execute", "load_sweep_spec"]

NAME = "sweep"
"""The subcommand's name on the command line."""

DEFAULT_METRICS = ("daily.finite_bits",)
"""What a spec that names no metric gets: the same default :func:`~quoss.engine.sweep.run_sweep` has.

Spelled here as well as there on purpose. A CLI that silently supplied its own
default would make ``quoss sweep`` and ``run_sweep`` disagree about what an
unspecified sweep measures, which is the class of divergence ADR 0016 exists to
refuse. The test that keeps them equal is in ``tests/cli/test_sweep.py``.
"""


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``sweep`` on ``subparsers``."""
    parser = subparsers.add_parser(
        NAME,
        help="run a scenario at every point of a sweep and tabulate the metrics.",
        description=(
            "Run a sweep. The spec is a .yaml/.yml/.json file holding 'parameters' (dotted "
            "scenario paths to value lists), optionally 'mode' (grid or zip) and 'metrics' "
            "(dotted result paths). It is a file and not an inline string because a figure "
            "has to be reproducible from something that is committed."
        ),
    )
    parser.add_argument("scenario", type=Path, help="path to the base scenario file.")
    parser.add_argument("spec", type=Path, help="path to the sweep spec file.")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="also write sweep.csv and sweep.json here; created if absent.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="worker processes, one point each. Default 1.",
    )
    parser.set_defaults(execute=execute)


def load_sweep_spec(path: Path) -> tuple[SweepSpec, tuple[str, ...]]:
    """Read a sweep spec file and return its spec and its metrics.

    Parameters
    ----------
    path : Path
        A ``.yaml``, ``.yml`` or ``.json`` file.

    Returns
    -------
    tuple[SweepSpec, tuple[str, ...]]
        The spec, and the metric paths (:data:`DEFAULT_METRICS` when the file
        names none).

    Raises
    ------
    ScenarioError
        If the suffix is not one of the three, the document is not a mapping,
        ``parameters`` is missing, ``metrics`` is not a list of strings, or the
        file holds a key that is none of the three. The last one matters: a
        typo such as ``parameter:`` would otherwise produce "a sweep needs at
        least one parameter" and leave the reader looking at a file that
        visibly has parameters in it.
    """
    format_for_path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioError(f"cannot read sweep spec {path}: {exc}") from exc
    try:
        document: Any = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ScenarioError(f"sweep spec {path} is not valid YAML/JSON: {exc}") from exc
    if not isinstance(document, dict):
        raise ScenarioError(
            f"sweep spec {path} must be a mapping with a 'parameters' key, got "
            f"{type(document).__name__}."
        )
    unknown = sorted(set(document) - {"parameters", "mode", "metrics"})
    if unknown:
        raise ScenarioError(
            f"sweep spec {path} holds unknown keys {unknown}; it takes 'parameters', "
            f"optionally 'mode' ('grid' or 'zip') and optionally 'metrics'."
        )
    if "parameters" not in document:
        raise ScenarioError(f"sweep spec {path} has no 'parameters' key.")
    metrics = document.get("metrics", list(DEFAULT_METRICS))
    if not isinstance(metrics, list) or not all(isinstance(m, str) for m in metrics):
        raise ScenarioError(f"sweep spec {path}: 'metrics' must be a list of strings.")
    parameters = document["parameters"]
    if not isinstance(parameters, dict):
        raise ScenarioError(
            f"sweep spec {path}: 'parameters' must be a mapping of dotted path to a list of "
            f"values, got {type(parameters).__name__}."
        )
    spec = SweepSpec(parameters=parameters, mode=document.get("mode", "grid"))
    return spec, tuple(metrics)


def execute(args: argparse.Namespace) -> int:
    """Run the sweep, write the table, print the warnings, return the status."""
    scenario = load_scenario(args.scenario)
    spec, metrics = load_sweep_spec(args.spec)
    log = DegradationLog()
    result = run_sweep(scenario, spec, metrics=metrics, workers=args.workers, degradations=log)
    records = result.to_records()
    columns = list(records[0]) if records else []

    writer = csv.DictWriter(sys.stdout, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(records)

    if args.out is not None:
        out_dir = Path(args.out)
        out_dir.mkdir(parents=True, exist_ok=True)
        with (out_dir / "sweep.csv").open("w", encoding="utf-8", newline="") as handle:
            file_writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
            file_writer.writeheader()
            file_writer.writerows(records)
        document = {
            "scenario": str(args.scenario),
            "scenario_hash": scenario_hash(scenario),
            "spec": {
                "parameters": {k: list(v) for k, v in spec.parameters.items()},
                "mode": spec.mode,
            },
            "metrics": list(metrics),
            "records": records,
            "warnings": log.to_dicts(),
        }
        (out_dir / "sweep.json").write_text(
            json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        sys.stderr.write(f"written: {out_dir}/sweep.csv, {out_dir}/sweep.json\n")

    warnings = log.to_dicts()
    print_warnings(warnings, stream=sys.stderr)
    return exit_status(warnings, declared=scenario.expected_degradations, stream=sys.stderr)
