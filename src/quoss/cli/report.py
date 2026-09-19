"""Printing the warnings whole, and turning them into an exit status.

Why this is a module and not four lines in each subcommand
----------------------------------------------------------
Every QuOSS run carries a :class:`~quoss.core.errors.DegradationLog`, and the
project's first rule is that a degraded model is never silent: the result holds
``warnings[]`` and something has to show them. Two decisions live here, both
non-obvious enough to be worth one file and one ADR section (ADR 0028).

**1. The warnings are printed in full, never summarised and never counted.**

A degradation record has five parts -- ``code``, ``severity``, ``where``,
``message`` and ``details`` -- and each part is the only one that answers some
question a reader will have. The ``code`` is what a script greps for; the
``where`` is which function did it; the ``message`` is what was substituted for
what; the ``details`` carry the offending numbers. A line like
``3 warnings (1 degraded)`` answers none of them, and the failure it produces is
specific rather than hypothetical: on a horizontal run the log holds
``horizontal.block-is-the-declared-session`` -- "the finite-key block is the
session you declared, nothing in the geometry fixes it" -- and
``horizontal.session-without-key``, which carries the asymptotic figure beside
the certified zero. Those two are the difference between *the link does not
close* and *the asymptotic calculation still claims 4.4 kbit/s*, and a reader
who sees "2 warnings" has been handed the count and not the finding.

Counting is not forbidden *in addition*: ``[2/5]`` in front of each entry is
navigation, not a substitute. What is forbidden is the count *instead*.

**2. A DEGRADED the scenario did not declare is a non-zero exit.**

``DEGRADED`` means a model was substituted, so the numbers are no longer those
of the requested model (:class:`~quoss.core.errors.Severity`). A pipeline that
writes a figure from that without noticing has published something it did not
compute. But a substitution can be perfectly fine and already understood -- and
then failing on it would make the exit status useless, because the only way to
keep a script green is to stop checking it. So the scenario file says which ones
it expects, in ``expected_degradations``, and the exit status is about the
**difference**: a code the author has looked at and listed is accepted, a code
that appears without being listed is a failure.

The field is excluded from the scenario hash
(:data:`~quoss.scenario.models.HASH_EXCLUDED_FIELDS`), so accepting a warning
never re-runs a day of Monte Carlo.

Exit statuses
-------------
``0``
    The run completed and recorded no undeclared ``DEGRADED``.
``1``
    It completed, and recorded at least one. The files are written -- the run
    is not wrong, it is *not what was asked for*, and a reader must be told.
``2``
    Usage: a bad flag or a missing argument. ``argparse``'s own status, kept
    rather than remapped so that the shell's convention holds.
``3``
    The run could not be made: an invalid scenario, a physics function refusing
    its inputs, a missing file. One of :class:`~quoss.core.errors.QuossError`.

Examples
--------
>>> import io
>>> warnings = [
...     {
...         "code": "turbulence.saturated-regime",
...         "message": "weak theory left behind; saturated model substituted.",
...         "severity": "degraded",
...         "where": "quoss.channel.turbulence.rytov_variance",
...         "details": {"rytov_variance_np2": 1.7},
...     }
... ]
>>> stream = io.StringIO()
>>> print_warnings(warnings, stream=stream)
>>> "rytov_variance_np2" in stream.getvalue()
True
>>> exit_status(warnings, declared=(), stream=io.StringIO())
1
>>> exit_status(warnings, declared=("turbulence.saturated-regime",), stream=io.StringIO())
0
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from typing import Any, TextIO

from quoss.core.errors import Severity

__all__ = [
    "EXIT_ERROR",
    "EXIT_OK",
    "EXIT_UNDECLARED_DEGRADATION",
    "EXIT_USAGE",
    "exit_status",
    "print_warnings",
    "undeclared_degradations",
]

EXIT_OK = 0
"""The run completed with no undeclared ``DEGRADED``."""

EXIT_UNDECLARED_DEGRADATION = 1
"""The run completed and substituted a model the scenario did not declare."""

EXIT_USAGE = 2
"""A bad flag or a missing argument. ``argparse`` exits with this itself."""

EXIT_ERROR = 3
"""The run could not be made: a :class:`~quoss.core.errors.QuossError`."""


def print_warnings(warnings: Sequence[Mapping[str, Any]], *, stream: TextIO) -> None:
    """Write every warning to ``stream``, every field of every one.

    Parameters
    ----------
    warnings : Sequence[Mapping[str, Any]]
        :meth:`~quoss.core.errors.DegradationLog.to_dicts` of the run's log,
        which is what a result carries in ``warnings``.
    stream : TextIO
        Where to write. The subcommands pass ``sys.stderr``, so that a
        ``quoss run`` whose standard output is piped still shows them.

    Notes
    -----
    Nothing is truncated, wrapped or elided, including ``details``, which is
    written as compact JSON so that a value is readable *and* greppable. A
    detail that JSON cannot represent is written with ``repr`` rather than
    dropped: the point of the block is that nothing recorded is lost on the way
    to the reader.
    """
    total = len(warnings)
    if total == 0:
        stream.write("warnings: none recorded.\n")
        return
    stream.write(f"warnings: {total} recorded, in full:\n")
    for index, entry in enumerate(warnings, start=1):
        severity = str(entry.get("severity", "?"))
        stream.write(f"[{index}/{total}] [{severity}] {entry.get('code', '?')}\n")
        stream.write(f"          where:   {entry.get('where', '?')}\n")
        stream.write(f"          message: {entry.get('message', '')}\n")
        details = entry.get("details") or {}
        if details:
            stream.write(f"          details: {_details_text(details)}\n")


def _details_text(details: Any) -> str:
    try:
        return json.dumps(details, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        return repr(details)


def undeclared_degradations(
    warnings: Sequence[Mapping[str, Any]], declared: Iterable[str]
) -> list[str]:
    """Return the ``DEGRADED`` codes that ``declared`` does not list, in order, deduplicated.

    Parameters
    ----------
    warnings : Sequence[Mapping[str, Any]]
        The run's warnings.
    declared : Iterable[str]
        The scenario's ``expected_degradations``.

    Returns
    -------
    list[str]
        The codes, first-seen order. Empty when every substitution was declared.

    Examples
    --------
    >>> undeclared_degradations(
    ...     [
    ...         {"code": "a.b", "severity": "degraded"},
    ...         {"code": "c.d", "severity": "warning"},
    ...         {"code": "a.b", "severity": "degraded"},
    ...     ],
    ...     declared=(),
    ... )
    ['a.b']
    """
    accepted = set(declared)
    seen: list[str] = []
    for entry in warnings:
        if str(entry.get("severity", "")) != str(Severity.DEGRADED):
            continue
        code = str(entry.get("code", ""))
        if code not in accepted and code not in seen:
            seen.append(code)
    return seen


def exit_status(
    warnings: Sequence[Mapping[str, Any]], *, declared: Iterable[str], stream: TextIO
) -> int:
    """Return :data:`EXIT_OK` or :data:`EXIT_UNDECLARED_DEGRADATION`, saying which and why.

    Parameters
    ----------
    warnings : Sequence[Mapping[str, Any]]
        The run's warnings.
    declared : Iterable[str]
        The scenario's ``expected_degradations``.
    stream : TextIO
        Where the explanation goes when the status is non-zero.

    Returns
    -------
    int
        The status.
    """
    undeclared = undeclared_degradations(warnings, declared)
    if not undeclared:
        return EXIT_OK
    stream.write(
        f"DEGRADED, not declared by the scenario: {', '.join(undeclared)}\n"
        f"A DEGRADED record means a model was substituted, so these numbers are not those of "
        f"the model the scenario asked for. The files are written -- the run is not wrong, it "
        f"is not what was asked for. Read the entries above; if the substitution is the "
        f"intended one, list its code in the scenario's expected_degradations and this becomes "
        f"exit {EXIT_OK}.\n"
    )
    return EXIT_UNDECLARED_DEGRADATION
