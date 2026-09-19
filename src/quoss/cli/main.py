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

Why ``--version`` prints more than a version
---------------------------------------------
``0.1.0`` names a release; it does not name a tree. Between two tags the same
string covers every commit made in between, so a figure somebody copied out of
a run and labelled "QuOSS 0.1.0" cannot be traced back to the code that
produced it. :func:`version_report` therefore prints the commit as well, and
the interpreter and the two numeric libraries -- the same four fields
:class:`~quoss.scenario.result.Provenance` already writes into every result
directory, so that the question "what produced this" has one answer whether it
is asked of a file or of the command.

The commit is ``None`` for an installed wheel, which has no repository. That is
printed as a sentence and not omitted: a reader who sees no commit line cannot
tell "installed from PyPI" from "this build forgot to record it".

>>> main(["--version"])
Traceback (most recent call last):
    ...
SystemExit: 0
"""

from __future__ import annotations

import argparse
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version

import numpy as np

import quoss
from quoss.cli import dossier, run, sweep, validate
from quoss.cli.report import EXIT_ERROR, EXIT_USAGE
from quoss.core.errors import QuossError
from quoss.scenario.result import git_commit

__all__ = ["build_parser", "main", "version_report"]

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


NO_COMMIT = "commit  unknown (not running from a git checkout)"
"""What the commit line says when there is no repository to ask.

An installed wheel carries no ``.git``, so
:func:`~quoss.scenario.result.git_commit` returns ``None`` there by design --
provenance must never be the reason a run fails. Printing this sentence rather
than dropping the line keeps the report the same shape in both cases, which is
what lets a reader tell an installed package from a build that failed to record
its own commit.
"""


def _dependency_version(name: str) -> str:
    """Return the installed version of ``name``, or ``"not installed"``.

    ``scipy`` is a hard dependency and will be there; asking through
    ``importlib.metadata`` rather than importing it keeps ``--version`` from
    paying for a scipy import, which is the slowest thing this command would
    otherwise do.
    """
    try:
        return _package_version(name)
    except PackageNotFoundError:  # pragma: no cover - scipy is a core dependency
        return "not installed"


def version_report() -> str:
    """Return the text ``--version`` prints: the release, the tree, the stack.

    Returns
    -------
    str
        Four lines without a trailing newline. The first is the conventional
        ``<prog> <version>`` that every tool prints and that scripts parse; the
        rest answer "which tree, on what".

    Examples
    --------
    >>> report = version_report()
    >>> report.splitlines()[0] == f"{PROG} {quoss.__version__}"
    True
    >>> len(report.splitlines())
    4
    """
    commit = git_commit()
    return "\n".join(
        (
            f"{PROG} {quoss.__version__}",
            NO_COMMIT if commit is None else f"commit  {commit}",
            f"python  {platform.python_version()}",
            f"numpy   {np.__version__}, scipy {_dependency_version('scipy')}",
        )
    )


class _VersionAction(argparse.Action):
    """Print :func:`version_report` verbatim and exit, instead of argparse's own.

    Two reasons this is not ``action="version"``.

    **The text.** ``argparse``'s version action hands its string to the help
    formatter, which re-wraps it to the terminal width -- four lines come out
    as two, broken wherever the width falls. A report whose line breaks depend
    on the window is not something a script can read.

    **The cost.** ``action="version"`` takes the string at parser-construction
    time, so every ``quoss run`` would pay for the ``git rev-parse``
    subprocess that :func:`version_report` makes. Here the report is built only
    when the flag is actually given.
    """

    def __init__(self, option_strings: Sequence[str], dest: str, **kwargs: object) -> None:
        kwargs.pop("nargs", None)
        super().__init__(list(option_strings), dest, nargs=0, **kwargs)  # type: ignore[arg-type]

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,  # noqa: ARG002 - argparse fixes this signature
        values: object,  # noqa: ARG002 - argparse fixes this signature
        option_string: str | None = None,  # noqa: ARG002 - argparse fixes this signature
    ) -> None:
        """Write the report to stdout and raise ``SystemExit(0)``."""
        sys.stdout.write(version_report() + "\n")
        parser.exit()


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
    parser.add_argument(
        "--version",
        action=_VersionAction,
        help="show the version, the commit, and the numeric stack, then exit",
    )
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
