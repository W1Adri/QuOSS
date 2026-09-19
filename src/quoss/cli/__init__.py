"""The command line: the only thing in this project a person runs directly.

What this package is, for someone arriving new
----------------------------------------------
Everything under ``quoss`` is a library: functions that take validated inputs
and return typed results. This package is the thin shell that turns a shell
command into one of those calls and the result into files. It is **level 0** of
the four distribution levels of
:doc:`ADR 0027 <../../docs/adr/0027-four-levels-of-distribution>`, and the other
three -- ``serve``, a Docker image, a hosted service -- are clients of the same
engine, never a second copy of it.

The rule that shapes every module here: **the CLI computes nothing.**
``run.py`` does not decide which geometry a scenario is (the file's ``link``
field does, and :func:`quoss.engine.pipeline.run` dispatches on it); it does not
decide which files an export contains (the result's shape does, and
:func:`quoss.io.export.export_result` dispatches on that); it does not sum a
metric (:func:`quoss.engine.sweep.metric_value` does). What is left for the CLI
is argument parsing, printing, and the exit status. ADR 0028 records the
decision and the test that holds it: the result ``quoss run`` writes is equal,
term by term, to :func:`~quoss.engine.pipeline.run` called by hand on the same
file -- the same assertion ADR 0016 makes about the engine, one layer up.

Modules
-------
main
    ``main(argv) -> int``, the entry point ``[project.scripts]`` names. Builds
    the parser, dispatches to a subcommand, and maps an exception to a status.
run
    ``quoss run <scenario.yaml> --out <dir>``: run and export.
sweep
    ``quoss sweep <scenario.yaml> <spec.yaml>``: a sweep as a table.
validate
    ``quoss validate``: recompute the validation table.
dossier
    ``quoss dossier <scenario.yaml> --out <document.md>``: the experiment
    dossier of a scenario -- the document somebody outside the code reads to
    decide. Same rule as the rest of this package, one step further out: it
    computes nothing, and a figure the result does not carry goes **up** into
    the result rather than down into the report (:mod:`quoss.dossier`).
report
    What every subcommand shares: printing the warnings **whole**, and deciding
    the exit status from them.

No re-exports, deliberately -- see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
