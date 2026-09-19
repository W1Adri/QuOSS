"""``quoss``: the entry point ``[project.scripts]`` names, and the parser it builds.

What lives here
---------------
:func:`build_parser` wires the four subcommands onto one ``argparse`` parser,
and :func:`main` runs the one the arguments chose and turns whatever comes back
into a process exit status. That is all; every subcommand's own work is in its
own module.

Why ``argparse`` and not a CLI framework
-----------------------------------------
Four subcommands and a dozen flags do not need one, and a framework is a
dependency that everybody who installs the physics core would carry. The core's
dependency list is deliberately five packages (``pyproject.toml``), on the same
argument ADR 0027 makes about the distribution levels: the thing people install
to compute physics should not grow for the convenience of the shell in front of
it. ``argparse`` is in the standard library, its ``--help`` is the one every
Python user already reads, and its exit status for a usage error is ``2``, which
is the shell convention this project keeps rather than remaps
(:mod:`quoss.cli.report`).

Why an exception becomes a message and not a traceback
-------------------------------------------------------
A :class:`~quoss.core.errors.QuossError` is this project saying "your inputs are
wrong, and here is which field" -- the messages are written to be read, name the
path of the offending value, and are asserted in the test suite. Printing a
forty-line traceback above one of them buries the sentence that matters under
the machinery that produced it. So the four public error classes are caught,
their message is written to standard error, and the status is ``3``. Anything
else -- an ``OSError``, a bug in this project -- keeps its traceback, because
there the machinery *is* the information.

Exit statuses are :mod:`quoss.cli.report`'s, and are the same for every
subcommand.

Examples
--------
.. code-block:: bash

    uv run quoss --help
    uv run quoss run scenarios/ge1_1km.yaml --out out/ge1
    uv run quoss sweep scenarios/ge1_1km.yaml scenarios/sweeps/ge1_distance.yaml
    uv run quoss validate
    uv run quoss dossier scenarios/ge1_1km.yaml --out docs/experiments/GE-1.md

>>> main(["--version"])
Traceback (most recent call last):
    ...
SystemExit: 0
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

import quoss
from quoss.cli import dossier, run, sweep, validate
from quoss.cli.report import EXIT_ERROR, EXIT_USAGE
from quoss.core.errors import QuossError

__all__ = ["build_parser", "main"]

PROG = "quoss"
"""The program name, as installed."""

_DESCRIPTION = (
    "QuOSS — quantum optical satellite simulator. Run a scenario, sweep one, recompute the "
    "validation table, or write an experiment's dossier. The CLI computes nothing: it turns "
    "arguments into a call and a result into files "
    "(docs/adr/0028-the-cli-computes-nothing.md)."
)

_EPILOG = (
    "Exit status: 0 the run recorded no undeclared DEGRADED; 1 it recorded one, and the "
    "files are still written; 2 a usage error; 3 the run could not be made (an invalid "
    "scenario, a physics function refusing its inputs). Every warning is printed in full "
    "on standard error, never summarised and never counted."
)


def build_parser() -> argparse.ArgumentParser:
    """Return the parser with every subcommand registered.

    Returns
    -------
    argparse.ArgumentParser
        A parser whose ``parse_args`` sets ``execute`` to the chosen
        subcommand's function.

    Examples
    --------
    >>> parser = build_parser()
    >>> args = parser.parse_args(["run", "s.yaml", "--out", "o"])
    >>> args.execute.__module__
    'quoss.cli.run'
    """
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=_DESCRIPTION,
        epilog=_EPILOG,
    )
    parser.add_argument("--version", action="version", version=f"{PROG} {quoss.__version__}")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    run.add_parser(subparsers)
    sweep.add_parser(subparsers)
    validate.add_parser(subparsers)
    dossier.add_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Parse ``argv``, run the subcommand, return the exit status.

    Parameters
    ----------
    argv : sequence of str, optional
        Arguments without the program name. ``None`` (default) reads
        ``sys.argv[1:]``.

    Returns
    -------
    int
        See :mod:`quoss.cli.report`. ``argparse`` raises ``SystemExit(2)``
        itself on a usage error rather than returning; a bare ``quoss`` with no
        subcommand returns :data:`~quoss.cli.report.EXIT_USAGE` after printing
        the help, because "no arguments" is a usage error that deserves to show
        what the arguments are.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "execute", None) is None:
        parser.print_help(sys.stderr)
        return EXIT_USAGE
    try:
        status: int = args.execute(args)
    except QuossError as exc:
        sys.stderr.write(f"{PROG} {args.command}: {type(exc).__name__}: {exc}\n")
        return EXIT_ERROR
    return status


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in tests
    raise SystemExit(main())
