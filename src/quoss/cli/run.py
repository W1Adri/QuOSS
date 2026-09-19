"""``quoss run <scenario.yaml> --out <dir>``: run one scenario and export it.

What this subcommand does, and what it deliberately does not
------------------------------------------------------------
Three calls, in order: :func:`~quoss.scenario.io.load_scenario`,
:func:`~quoss.engine.pipeline.run`, :func:`~quoss.io.export.export_result`. Then
it prints the warnings and returns a status. Everything else is argument
parsing.

**It does not ask which geometry the file describes.** Since ADR 0024 a
scenario is a discriminated union tagged by ``link``, and the file says
``link: horizontal`` in its first lines. So there is no ``--horizontal`` flag
and no sniffing of which sections are present: ``load_scenario`` validates into
one of the two members, ``run`` dispatches on the tag, and the result comes back
as whichever container matches. A flag here would be a second place where the
geometry is stated, and two places is one too many -- the day they disagree, the
flag wins and the file is read as something it is not.

**It does not decide which files the export writes.** The result's shape does:
a :class:`~quoss.scenario.result.SimulationResult` has arrays and a pass axis, a
:class:`~quoss.scenario.result.HorizontalResult` has neither, and
:func:`~quoss.io.export.export_result` narrows on which method the result
offers. ``manifest.json`` names the shape it chose. So this module exports both
geometries with one call and no branch, which is the property that makes the
chain checkable end to end.

The test that holds it
----------------------
``tests/cli/test_run.py`` asserts what ADR 0016 asserts about the engine, one
layer up: the ``result.json`` this subcommand writes rebuilds into a result
**equal term by term** to :func:`~quoss.engine.pipeline.run` called by hand on
the same file, for both geometries. Two fields are excluded and named: the
provenance timestamp and the stage timings, which are wall-clock readings and
differ between any two runs of anything.

Examples
--------
.. code-block:: bash

    uv run quoss run scenarios/reference_castelldefels.yaml --out out/reference
    uv run quoss run scenarios/ge1_1km.yaml --out out/ge1 --format json csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quoss.cli.report import exit_status, print_warnings
from quoss.core.errors import DegradationLog
from quoss.engine.pipeline import run as run_scenario
from quoss.io.export import FORMATS, export_result
from quoss.scenario.io import load_scenario

__all__ = ["add_parser", "execute"]

NAME = "run"
"""The subcommand's name on the command line."""


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``run`` on ``subparsers``.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The object :func:`quoss.cli.main.build_parser` returns from
        ``add_subparsers``.
    """
    parser = subparsers.add_parser(
        NAME,
        help="run one scenario and write it to a directory.",
        description=(
            "Run one scenario file and export the result. The file's 'link' field decides "
            "which geometry is run and which directory shape is written; there is no flag "
            "for either."
        ),
    )
    parser.add_argument("scenario", type=Path, help="path to a scenario .yaml, .yml or .json.")
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="DIR",
        help="directory to write the result into; created if absent.",
    )
    parser.add_argument(
        "--format",
        dest="formats",
        nargs="+",
        default=["json", "csv", "npz"],
        choices=list(FORMATS),
        metavar="FMT",
        help=f"export formats, any of {', '.join(FORMATS)}. Default: json csv npz.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="worker processes for the per-station stages. Default 1. The result is "
        "identical for any value.",
    )
    parser.set_defaults(execute=execute)


def execute(args: argparse.Namespace) -> int:
    """Run the scenario, export it, print the warnings, return the status.

    Parameters
    ----------
    args : argparse.Namespace
        ``scenario``, ``out``, ``formats``, ``workers``.

    Returns
    -------
    int
        :data:`~quoss.cli.report.EXIT_OK` or
        :data:`~quoss.cli.report.EXIT_UNDECLARED_DEGRADATION`.
    """
    scenario = load_scenario(args.scenario)
    log = DegradationLog()
    result = run_scenario(scenario, workers=args.workers, degradations=log)
    manifest = export_result(result, args.out, formats=args.formats, degradations=log)

    sys.stdout.write(
        f"{scenario.name}\n"
        f"  link:     {scenario.link}\n"
        f"  hash:     {result.provenance.scenario_hash}\n"
        f"  shape:    {manifest.shape}\n"
        f"  written:  {manifest.directory}\n"
    )
    for written in (*manifest.files, None):
        name = "manifest.json" if written is None else written.name
        sys.stdout.write(f"            {name}\n")
    # The log and not ``result.warnings``: the two differ by exactly the entries the
    # *export* recorded, which a result cannot carry because it was already built when
    # they happened. ``io.export-no-arrays`` is one of them, and it is the line that says
    # why a horizontal directory has no arrays.npz. Printing the result's copy would drop
    # it -- and dropping a recorded entry is the failure this whole module exists to avoid.
    warnings = log.to_dicts()
    print_warnings(warnings, stream=sys.stderr)
    return exit_status(warnings, declared=scenario.expected_degradations, stream=sys.stderr)
