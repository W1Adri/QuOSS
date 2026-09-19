"""``python -m quoss.dossier`` -- regenerate all three committed dossiers at once.

Why this exists beside ``quoss dossier``
-----------------------------------------
``quoss dossier <scenario> --out <path>`` writes **one** document, and its
command line is what each document's header quotes as the way to rewrite it.
That is the right shape for the header -- a reader who wants to check one file
should not be told to rebuild three -- and the wrong shape for the person who
just changed a physics function, who needs all three brought back into line
before the commit.

So this module is the second command, and it is deliberately not a flag on the
first one: ``--all`` on a subcommand that takes a scenario argument would have
to accept and then ignore that argument, and a command that ignores what it was
given is a command that will one day be given something else and ignore that
too.

What the exit status means
--------------------------
The same as everywhere else in this project (:mod:`quoss.cli.report`): ``0``
when no run recorded a ``DEGRADED`` its scenario did not declare, ``1`` when one
did and the files are written anyway, ``3`` when a document could not be built
at all. A regeneration that substituted a model is not a failure, and it is not
something to find out about later either.

Examples
--------
Rewrite every committed dossier:

.. code-block:: bash

    uv run python -m quoss.dossier

Check that all three would be written without touching the tree:

.. code-block:: bash

    uv run python -m quoss.dossier --check
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from quoss.cli.report import EXIT_OK, EXIT_UNDECLARED_DEGRADATION, exit_status, print_warnings
from quoss.dossier.base import dossiers, render
from quoss.scenario.io import load_scenario

__all__ = ["main"]


def main(argv: Sequence[str] | None = None) -> int:
    """Regenerate every committed dossier and return the worst exit status.

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments without the program name. ``None`` (default) reads
        ``sys.argv[1:]``.

    Returns
    -------
    int
        :data:`~quoss.cli.report.EXIT_OK`, or
        :data:`~quoss.cli.report.EXIT_UNDECLARED_DEGRADATION` if any document's
        runs recorded a ``DEGRADED`` its scenario did not declare. The worst of
        the three and not the last one, because "the third was fine" is not an
        answer about the first two.
    """
    parser = argparse.ArgumentParser(
        prog="python -m quoss.dossier",
        description=(
            "Regenerate every committed document under docs/experiments/. Each one is also "
            "writable on its own with `quoss dossier <scenario> --out <path>`, which is what "
            "each document's own header names."
        ),
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        metavar="DIR",
        help="repository root the documents' paths are relative to. Default: the working "
        "directory.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="render every document and write nothing; report which committed files differ. "
        "Exits 1 on a difference, so it can be used as a gate.",
    )
    args = parser.parse_args(argv)

    worst = EXIT_OK
    stale: list[str] = []
    for spec in dossiers():
        scenario = load_scenario(args.root / spec.scenario_path)
        dossier = render(spec, scenario)
        target = args.root / spec.document_path
        if args.check:
            current = target.read_text(encoding="utf-8") if target.is_file() else None
            if current != dossier.text:
                stale.append(spec.document_path)
                sys.stderr.write(f"stale: {spec.document_path}\n")
            else:
                sys.stderr.write(f"current: {spec.document_path}\n")
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(dossier.text, encoding="utf-8")
            sys.stderr.write(f"written: {spec.document_path}\n")
        warnings = dossier.log.to_dicts()
        print_warnings(warnings, stream=sys.stderr)
        status = exit_status(warnings, declared=scenario.expected_degradations, stream=sys.stderr)
        worst = max(worst, status)

    if stale:
        sys.stderr.write(
            f"{len(stale)} committed document(s) differ from what the code produces today: "
            f"{', '.join(stale)}. Rewrite them with `uv run python -m quoss.dossier` and read "
            "the diff: it names the figures this change moved.\n"
        )
        worst = max(worst, EXIT_UNDECLARED_DEGRADATION)
    return worst


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in tests
    raise SystemExit(main())
