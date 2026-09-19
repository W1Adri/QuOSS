"""``quoss validate``: recompute the validation table and print it.

What it runs
------------
:func:`quoss.validation.base.run_all` — every case in
:data:`~quoss.validation.base.CASE_MODULES`, each of which calls the same public
physics function the test suite calls, compares it with a published value under
a tolerance whose origin is written next to it, and **derives** its status
instead of carrying one somebody typed. Then
:func:`~quoss.validation.base.render_markdown` turns them into the table that
``docs/validation.md`` holds.

Why a disagreement is exit 0 here, which is the one decision
-------------------------------------------------------------
A table with ``not reproduced`` rows in it is a **correct** table. Deriving the
status rather than declaring it exists precisely so that a disagreement gets
published instead of hidden, and a command that failed on one would teach its
user to stop running it. So the status is zero unless the table could not be
computed at all -- a physics function refusing its inputs, a case whose declared
status its own numbers do not produce, two cases sharing an identifier -- which
arrives as an exception and becomes exit ``3``.

The gate that *does* fail on an unexpected disagreement is
``tests/validation/test_base.py``, against
:data:`~quoss.validation.base.EXPECTED_DISAGREEMENTS`. Keeping the two apart is
what lets a person regenerate the document on a branch where something
disagrees, see it in the diff and decide, while CI still refuses to let it
through unexplained. ADR 0018 records the decision; this module is the same
policy ``python -m quoss.validation`` already applies, reached from the one
command a user has installed.

Examples
--------
.. code-block:: bash

    uv run quoss validate
    uv run quoss validate --write docs/validation.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from quoss.cli.report import EXIT_OK
from quoss.validation.base import REGENERATE_COMMAND, render_markdown, run_all

__all__ = ["add_parser", "execute"]

NAME = "validate"
"""The subcommand's name on the command line."""


def add_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """Register ``validate`` on ``subparsers``."""
    parser = subparsers.add_parser(
        NAME,
        help="recompute every validation case and render the table.",
        description=(
            "Recompute quoss.validation and emit its Markdown table. A 'not reproduced' row "
            "is a correct table and exits 0; only being unable to compute the table fails. "
            f"The canonical invocation for rewriting the committed document is: "
            f"{REGENERATE_COMMAND}"
        ),
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        metavar="PATH",
        help="write the table to PATH instead of standard output.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="compute the table and emit nothing; for checking that the run succeeds.",
    )
    parser.set_defaults(execute=execute)


def execute(args: argparse.Namespace) -> int:
    """Recompute the table, emit it, and return :data:`~quoss.cli.report.EXIT_OK`."""
    text = render_markdown(run_all())
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
        sys.stderr.write(f"written: {args.write}\n")
    elif not args.quiet:
        sys.stdout.write(text)
    return EXIT_OK
