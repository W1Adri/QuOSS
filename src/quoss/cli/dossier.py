"""``quoss dossier <scenario.yaml> --out <document.md>``: the experiment dossier of a scenario.

What this subcommand does
-------------------------
Three calls, in order: :func:`~quoss.scenario.io.load_scenario`,
:func:`~quoss.dossier.base.dossier_for` to find which document that scenario
produces, and :func:`~quoss.dossier.base.render` to build it. Then it writes the
text, prints the warnings and returns a status. Everything else is argument
parsing -- the same shape ``quoss run`` has, for the same reason.

Why there is no ``--kind`` flag, and no template
-------------------------------------------------
Because a dossier is **prose written for one experiment**, not a report shape
filled with whichever numbers a scenario happens to have. ``GE-0b.md`` exists to
say which of GE-1's questions a two-metre bench does not answer; no template
produces that sentence. So the registry maps a scenario's ``name`` to its
builder, a scenario with no builder is an error that lists the three that have
one, and there is nothing generic to fall back to.

That is a deliberate limit and not an oversight. The failure it prevents is the
one that would matter: a confident-looking document with a title and a table,
generated for a scenario nobody wrote sections for, carrying whichever figures
the generic path could reach and silent about everything it could not. An error
naming the three registered scenarios is a better outcome than a document whose
omissions are invisible.

Why the output path is required and not defaulted
--------------------------------------------------
Each spec knows where its document is committed, so ``--out`` could default to
it. It does not, because the default would make ``quoss dossier
scenarios/ge1_1km.yaml`` **overwrite a committed file** as the effect of a
command a reader might run just to look at the output. Writing over a tracked
document is worth four extra words on the command line. The path each document
is committed at is printed by ``--help`` and quoted in each document's own
header, and ``python -m quoss.dossier`` rewrites all three when that is what is
wanted.

Examples
--------
.. code-block:: bash

    uv run quoss dossier scenarios/ge1_1km.yaml --out docs/experiments/GE-1.md
    uv run quoss dossier scenarios/ge0b_bench.yaml --out -   # to standard output
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quoss.cli.report import exit_status, print_warnings
from quoss.dossier.base import dossier_for, dossiers, render
from quoss.scenario.io import load_scenario

__all__ = ["NAME", "add_parser", "execute"]

NAME = "dossier"
"""The subcommand's name on the command line."""

STDOUT = "-"
"""The ``--out`` value that means standard output rather than a file."""


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``dossier`` on ``subparsers``.

    Parameters
    ----------
    subparsers : argparse._SubParsersAction
        The object :func:`quoss.cli.main.build_parser` returns from
        ``add_subparsers``.
    """
    registered = "; ".join(f"{spec.scenario_path} -> {spec.document_path}" for spec in dossiers())
    parser = subparsers.add_parser(
        NAME,
        help="write the experiment dossier of a scenario as Markdown.",
        description=(
            "Build the experiment dossier of a scenario: the document somebody reads to "
            "decide, with every figure computed by the engine at generation time and none "
            "transcribed by hand. Which document a scenario produces is fixed by its name, "
            f"because a dossier is prose written for one experiment. Registered: {registered}."
        ),
    )
    parser.add_argument("scenario", type=Path, help="path to a scenario .yaml, .yml or .json.")
    parser.add_argument(
        "--out",
        required=True,
        metavar="PATH",
        help=f"where to write the Markdown; {STDOUT!r} for standard output. Required, so that "
        "running this command to look at the output cannot overwrite a committed document.",
    )
    parser.set_defaults(execute=execute)


def execute(args: argparse.Namespace) -> int:
    """Build the dossier, write it, print the warnings, return the status.

    Parameters
    ----------
    args : argparse.Namespace
        ``scenario`` and ``out``.

    Returns
    -------
    int
        :data:`~quoss.cli.report.EXIT_OK` or
        :data:`~quoss.cli.report.EXIT_UNDECLARED_DEGRADATION`.
    """
    scenario = load_scenario(args.scenario)
    spec = dossier_for(scenario)
    dossier = render(spec, scenario)

    if args.out == STDOUT:
        sys.stdout.write(dossier.text)
    else:
        target = Path(args.out)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dossier.text, encoding="utf-8")
        sys.stdout.write(
            f"{spec.identifier}\n"
            f"  scenario: {scenario.name}\n"
            f"  written:  {target}\n"
            f"  committed at: {spec.document_path}\n"
        )

    warnings = dossier.log.to_dicts()
    print_warnings(warnings, stream=sys.stderr)
    return exit_status(warnings, declared=scenario.expected_degradations, stream=sys.stderr)
