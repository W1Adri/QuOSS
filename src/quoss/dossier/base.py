"""What a dossier is, how it is rendered, and the boundary it may not cross.

Para quien llegue nuevo: this module computes no physics. It fixes the *shape*
of an experiment dossier -- the header that ties it to a scenario, the helpers
that turn a float into a cell, and the registry that maps a scenario to the
document it produces -- so that all three documents are made the same way and
fail the same way.

What a dossier is
-----------------
A **dossier** is the document somebody reads to decide: whether to buy a lens,
whether to lend an optical bench, what the experiment will be able to claim
when it is over. It is not a paper and it is not an ADR. An ADR records a
decision this project already took; a dossier states what this project's model
says about an experiment that has not been built, with every figure carrying
the unit it is in and the decision it changes.

Why it is generated and never typed
-----------------------------------
Because the alternative has a measured failure mode in this repository. A
number copied by hand into a document is the same defect ``LAST_CHANGES.md``
§46 closed in the docstrings and §14 closed in the notes: the "219 km" of the
Brouwer-Lyddane cost lived in fifteen places for months, was defended in prose
every time, and was **5.9 times too small**. Nothing caught it because nothing
could: prose does not run.

A dossier is worse than a docstring in exactly one way, and it is the way that
matters here -- **it gets taken to a meeting**. A stale docstring misleads the
next person to open the file; a stale dossier misleads a purchase order. So
every figure in ``docs/experiments/`` comes out of a run made when the file was
generated, the file is committed so that a change to the physics shows up as a
diff, and ``tests/dossier/test_docs.py`` compares the committed bytes with a
fresh render. That is the same three-part arrangement ``docs/validation.md``
has had since stage 8, for the same reason.

The boundary, which is the one rule of this package
----------------------------------------------------
**A dossier builder may read a result and it may ask the engine for another
run. It may not evaluate physics itself.** ADR 0028 states the rule for the CLI
("the CLI computes nothing"); a report generator is the same layer one step
further out, and the failure it would produce is worse, because a number
computed in a presentation layer is a number no test of the physics covers.

The rule is not free, and what it cost is worth writing down, because it is the
shape this will take again. Writing ``GE-1.md`` asked for three figures the
result did not carry: the aperture-averaging factor ``A``, the transmitter's
Rayleigh range, and the path length at which the weak theory stops applying.
All three are one call to a public function in :mod:`quoss.channel`, and making
that call here would have taken one line. Instead they went **up**, into
:class:`~quoss.scenario.result.HorizontalBudgetResults`, where the engine fills
them and ``tests/e2e/test_horizontal_scenario.py`` checks them against a
hand-wired chain. The line saved would have been a line of physics that no
end-to-end test reaches.

What a builder may therefore use: fields of a result; :func:`run_downlink`,
:func:`run_horizontal` and :func:`sweep_rows`, which are the engine; arithmetic that is presentation --
a ratio of two figures already reported, a difference, a percentage. What it
may not use: an import from :mod:`quoss.channel`, :mod:`quoss.qkd` or
:mod:`quoss.system`. ``tests/dossier/test_docs.py`` asserts that absence by
reading this package's imports, because a rule nobody checks is a rule that
lasts until the first hurry.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from importlib import import_module
from typing import Any, Final

import quoss
from quoss.core.errors import ConfigurationError, DegradationLog, ScenarioError
from quoss.engine.pipeline import run as run_scenario
from quoss.engine.sweep import SweepSpec, run_sweep
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import AnyScenario, HorizontalScenario, Scenario
from quoss.scenario.result import AnyResult, HorizontalResult, SimulationResult

__all__ = [
    "DOSSIER_DIRECTORY",
    "DOSSIER_MODULES",
    "Dossier",
    "DossierSpec",
    "Limit",
    "bits",
    "dossier_for",
    "dossiers",
    "em_dash",
    "identifiers",
    "limits_section",
    "logged_codes_section",
    "number",
    "percent",
    "provenance_block",
    "regenerate_command",
    "render",
    "run_downlink",
    "run_horizontal",
    "share",
    "signed",
    "sweep_rows",
    "table",
    "times",
]

DOSSIER_DIRECTORY: Final = "docs/experiments"
"""Where the committed documents live, relative to the repository root."""

EM_DASH: Final = "—"
"""The character used for "there is no number here"."""


# --------------------------------------------------------------------------- #
# Cells
# --------------------------------------------------------------------------- #
def em_dash() -> str:
    """Return the cell that means *nothing was computed*.

    A blank cell and a zero read the same to a hurried reader, and only one of
    them is ever true. Same choice ``quoss.validation.base`` makes.
    """
    return EM_DASH


def number(value: float | None, *, digits: int = 4) -> str:
    """Return ``value`` at ``digits`` significant figures, or an em dash.

    Four by default, which is the precision ``docs/validation.md`` renders at.
    It is a deliberate ceiling and not a shrug: a dossier is read by somebody
    deciding, and the twelfth digit of a number whose model is bounded by four
    declared gaps is noise dressed as precision.

    Examples
    --------
    >>> number(0.19884451224935693)
    '0.1988'
    >>> number(float("nan"))
    '—'
    """
    if value is None or not math.isfinite(float(value)):
        return EM_DASH
    return f"{float(value):.{digits}g}"


def bits(value: float | None) -> str:
    """Return a bit count as a whole number with thin groups, or an em dash.

    Spaces and not commas, because these documents quote figures such as
    ``449 308`` beside the notes that measured them and a reader comparing the
    two should be comparing the same string. ``1234.0`` is ``1 234``.

    Examples
    --------
    >>> bits(15236099.0)
    '15 236 099'
    >>> bits(0.0)
    '0'
    """
    if value is None or not math.isfinite(float(value)):
        return EM_DASH
    return f"{float(value):,.0f}".replace(",", " ")


def signed(value: float | None, *, digits: int = 4) -> str:
    """Return ``value`` with an explicit sign, or an em dash.

    For differences, where ``+457`` and ``457`` are different claims: the first
    says the term adds, the second leaves a reader to work out which column was
    subtracted from which.

    Examples
    --------
    >>> signed(457.0)
    '+457'
    >>> signed(-206.0)
    '-206'
    """
    if value is None or not math.isfinite(float(value)):
        return EM_DASH
    return f"{float(value):+.{digits}g}"


def percent(value: float | None, *, digits: int = 3) -> str:
    """Return a fraction as a signed percentage, or an em dash.

    Examples
    --------
    >>> percent(-0.0329)
    '-3.29 %'
    """
    if value is None or not math.isfinite(float(value)):
        return EM_DASH
    return f"{100.0 * float(value):+.{digits}g} %"


def share(value: float | None, *, digits: int = 3) -> str:
    """Return a fraction as an **unsigned** percentage, or an em dash.

    Separate from :func:`percent` and not a flag on it, because the two answer
    different questions and only one of them has a sign to carry. A *share* of
    a total is never negative in these documents -- every term of a loss budget
    is a loss -- so printing ``+54.6 %`` beside ``100 %`` would put a sign on a
    quantity that has no other one, and a reader would reasonably wonder what
    the negative case looks like.

    Examples
    --------
    >>> share(0.546)
    '54.6 %'
    """
    if value is None or not math.isfinite(float(value)):
        return EM_DASH
    return f"{100.0 * float(value):.{digits}g} %"


def times(numerator: float, denominator: float, *, digits: int = 4) -> str:
    """Return ``numerator / denominator`` as a factor, or an em dash on a zero.

    A factor is reported and never inverted silently: ``times(a, b)`` is "a is
    this many times b", so the caller decides which way round the sentence
    reads.

    Examples
    --------
    >>> times(0.2386, 4.45e-05)
    '5362'
    >>> times(1.0, 0.0)
    '—'
    """
    if denominator == 0.0 or not math.isfinite(numerator / denominator):
        return EM_DASH
    return number(numerator / denominator, digits=digits)


def table(headers: Sequence[str], rows: Iterable[Sequence[str]]) -> list[str]:
    """Return a GitHub-flavoured Markdown table as lines.

    Parameters
    ----------
    headers : sequence of str
        The column titles. Every one carries its unit where it has one, which
        is the rule of this package's audience: a dossier is read by somebody
        who did not write the code.
    rows : iterable of sequence of str
        Already-formatted cells, one sequence per row, each the length of
        ``headers``.

    Returns
    -------
    list[str]
        Header, separator, then one line per row.

    Raises
    ------
    ScenarioError
        If a row is not as wide as the header. A short row renders as a table
        that silently shifts every cell after it left.

    Examples
    --------
    >>> table(["a", "b"], [["1", "2"]])
    ['| a | b |', '|---|---|', '| 1 | 2 |']
    """
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        cells = list(row)
        if len(cells) != len(headers):
            raise ScenarioError(
                f"dossier table row {cells!r} has {len(cells)} cells against "
                f"{len(headers)} headers {list(headers)!r}."
            )
        lines.append("| " + " | ".join(cells) + " |")
    return lines


# --------------------------------------------------------------------------- #
# The engine, reached from here and nowhere else in this package
# --------------------------------------------------------------------------- #
def _run(scenario: AnyScenario, *, degradations: DegradationLog) -> AnyResult:
    """Run one scenario through the engine and return its result.

    One of the two ways a builder gets a number, the other being
    :func:`sweep_rows`. Both are thin on purpose: a builder that had its own way
    of reaching the physics would be a second engine entry point, and the
    property ADR 0016 asserts -- that the engine adds nothing a person calling
    the functions by hand would not get -- would stop covering what these
    documents print.
    """
    return run_scenario(scenario, degradations=degradations)


def run_downlink(
    scenario: AnyScenario, *, degradations: DegradationLog, what: str
) -> tuple[Scenario, SimulationResult]:
    """Narrow ``scenario`` to a downlink, run it, and return both.

    Why the narrowing happens here and not in each builder
    -------------------------------------------------------
    A dossier builder reads fields that exist on one member of the scenario
    union and not the other -- ``scenario.passes.minimum_elevation_deg`` has no
    meaning for a bench. The registry keys on the scenario's ``name``, so the
    wrong geometry can only arrive through a file that took a registered name
    and changed its ``link`` tag, but "can only happen through X" is how every
    unchecked assumption is introduced. Doing it once here gives the type
    checker the narrowing it needs *and* gives that case one message instead of
    six.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        The loaded inputs.
    degradations : DegradationLog
        Receives the run's entries.
    what : str
        How to name this scenario in the error, e.g. ``"the reference link"``.

    Returns
    -------
    tuple[Scenario, SimulationResult]
        The narrowed scenario and its result.

    Raises
    ------
    ScenarioError
        If the scenario is horizontal, or if the engine returned the other kind
        of result -- the second being unreachable today and checked anyway,
        because a result of the wrong shape would otherwise surface as an
        ``AttributeError`` deep inside a table.
    """
    if not isinstance(scenario, Scenario):
        raise ScenarioError(
            f"{what} has to be a downlink (`link: downlink`) and this scenario is "
            f"{type(scenario).__name__}. The sections of this dossier read fields -- passes, "
            "an elevation mask, a station -- that a horizontal scenario does not have and "
            "cannot have."
        )
    result = _run(scenario, degradations=degradations)
    if not isinstance(result, SimulationResult):
        raise ScenarioError(
            f"{what} is a downlink and the engine returned a {type(result).__name__}."
        )
    return scenario, result


def run_horizontal(
    scenario: AnyScenario, *, degradations: DegradationLog, what: str
) -> tuple[HorizontalScenario, HorizontalResult]:
    """Narrow ``scenario`` to a horizontal link, run it, and return both.

    The counterpart of :func:`run_downlink`; see there for why the narrowing is
    here.

    Raises
    ------
    ScenarioError
        If the scenario is a downlink, or the result is of the other shape.
    """
    if not isinstance(scenario, HorizontalScenario):
        raise ScenarioError(
            f"{what} has to be a horizontal link (`link: horizontal`) and this scenario is "
            f"{type(scenario).__name__}. The sections of this dossier read a path length and a "
            "single session, which a downlink has neither of."
        )
    result = _run(scenario, degradations=degradations)
    if not isinstance(result, HorizontalResult):
        raise ScenarioError(
            f"{what} is a horizontal link and the engine returned a {type(result).__name__}."
        )
    return scenario, result


def sweep_rows(
    scenario: AnyScenario,
    parameters: Mapping[str, Sequence[Any]],
    metrics: Sequence[str],
    *,
    mode: str = "grid",
    degradations: DegradationLog,
) -> list[dict[str, Any]]:
    """Run a sweep and return one plain row per point.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        The base scenario, which decides which metric roots are legal.
    parameters : mapping of str to sequence
        Dotted scenario paths to the values they take.
    metrics : sequence of str
        Dotted result paths.
    mode : {"grid", "zip"}
        Cartesian product, or the i-th values together.
    degradations : DegradationLog
        Receives every point's entries.

    Returns
    -------
    list[dict]
        The rows :meth:`~quoss.engine.sweep.SweepResult.to_records` gives:
        every parameter, every metric, and ``scenario_hash``.
    """
    spec = SweepSpec(parameters=parameters, mode=mode)  # type: ignore[arg-type]
    result = run_sweep(scenario, spec, metrics=metrics, degradations=degradations)
    return result.to_records()


# --------------------------------------------------------------------------- #
# The declared limits, which are the section every dossier ends with
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Limit:
    """One declared hole in the model, and what it costs the number above it.

    Parameters
    ----------
    gap : int or None
        Its number in the list of ``docs/adr/0009-citation-policy.md``, which is
        the register of declared gaps and is never renumbered. ``None`` for a
        limitation that is **not** a citation gap -- a model this project has
        and the scenario did not switch on, for instance. Those belong in this
        section too: a reader deciding cannot be expected to know that the
        register only covers things no source publishes.
    title : str
        One line, in words a reader who has not opened the ADR can follow.
    cost : str
        **What it is worth in the figure this document reports**, with a unit.
        This is the field that makes the section useful rather than pious: a
        list of caveats without magnitudes cannot be acted on, and a reader who
        cannot size a caveat will either ignore all of them or refuse to
        decide.
    reference : str
        Where the cost was measured, as a path or a pytest node.

    Raises
    ------
    ScenarioError
        If any field is empty. A limit with no cost written is the shape this
        section exists to refuse.
    """

    gap: int | None
    title: str
    cost: str
    reference: str

    def __post_init__(self) -> None:
        """Refuse a limit that states no cost."""
        for name in ("title", "cost", "reference"):
            if not str(getattr(self, name)).strip():
                raise ScenarioError(
                    f"Limit(gap={self.gap}) has an empty {name}. A declared gap without a "
                    "measured cost is a caveat a reader cannot size, which is the failure "
                    "this section exists to prevent."
                )


def limits_section(limits: Sequence[Limit]) -> list[str]:
    """Render the closing section: what the model cannot claim, and what it costs.

    Every dossier ends with this and none of them ends with a conclusion. The
    order is deliberate: the last thing read is the boundary of the claim, not
    the claim.
    """
    lines = [
        "## What this model cannot claim",
        "",
        "Each row is a **declared gap**: something no source this project could open states, "
        "so it was left as a hole rather than filled with the most plausible-looking value "
        "([ADR 0009](../adr/0009-citation-policy.md)) -- or, where the first column says so, a "
        "limitation of a different kind: a model this project has and this scenario did not "
        "switch on. The third column is **what it is worth in the figures above**. A caveat "
        "without a magnitude cannot be acted on, and a reader who cannot size a caveat will "
        "either ignore every one of them or refuse to decide, so a limit that has never been "
        "priced says exactly that in that column rather than being quietly left out.",
        "",
    ]
    lines += table(
        ["Gap", "What is missing", "What it costs here", "Measured by"],
        [
            [
                f"[{limit.gap}](../adr/0009-citation-policy.md)"
                if limit.gap is not None
                else "not a citation gap",
                limit.title,
                limit.cost,
                limit.reference,
            ]
            for limit in limits
        ],
    )
    return lines


def logged_codes_section(log: DegradationLog) -> list[str]:
    """Render every degradation code the runs behind this document recorded.

    Why a document and not only a console
    --------------------------------------
    :mod:`quoss.cli.report` already prints every warning in full on standard
    error, and that serves the person who ran the command. It does not serve
    the person the document is written for, who will never run it. A
    ``DEGRADED`` record means a model was **substituted**, so the figures above
    are not those of the model the scenario asked for -- and that is a sentence
    a reader deciding a purchase has to be able to find without a terminal.

    The codes are deduplicated and counted, and the count is navigation beside
    the message rather than instead of it: the rule of :mod:`quoss.cli.report`
    is that a count never replaces a finding.
    """
    seen: dict[str, tuple[str, str, int]] = {}
    for entry in log.to_dicts():
        code = str(entry.get("code", "?"))
        severity = str(entry.get("severity", "?"))
        message = str(entry.get("message", "")).strip()
        if code in seen:
            previous = seen[code]
            seen[code] = (previous[0], previous[1], previous[2] + 1)
        else:
            seen[code] = (severity, message, 1)
    lines = [
        "## What the runs behind this document recorded",
        "",
        "Every code the physics logged while computing the figures above, deduplicated, with "
        "how many of the runs raised it. A `degraded` entry means a model was **substituted**, "
        "so the figure it touched is not the one the scenario asked for; an `info` entry is the "
        "model stating an assumption it was given. Nothing here is a failure, and nothing here "
        "is hidden: the rule is that a count never replaces the finding, so each message is "
        "printed whole. Where several runs raised the same code with different numbers in the "
        "message, the one printed is the **first**, and the count beside it says how many "
        "others there were.",
        "",
    ]
    if not seen:
        lines += [
            "No entry was recorded, which is itself a statement: no model was "
            "substituted and no assumption needed naming.",
            "",
        ]
        return lines
    lines += table(
        ["Code", "Severity", "Runs", "What it says"],
        [
            [f"`{code}`", severity, str(count), message]
            for code, (severity, message, count) in sorted(seen.items())
        ],
    )
    return lines


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #
Body = Callable[[AnyScenario, DegradationLog], list[str]]
"""Builds one document's body from the scenario it was given and a log to fill."""


@dataclass(frozen=True, slots=True)
class DossierSpec:
    """One dossier: which scenario makes it, where it is committed, and how it is built.

    Parameters
    ----------
    identifier : str
        The experiment's name, e.g. ``"GE-1"``.
    subtitle : str
        The one line under the title, saying what the document decides.
    scenario_name : str
        The ``name`` field of the scenario this dossier is generated from. The
        registry is keyed on it rather than on a path, so that a copy of the
        file under another name still resolves -- and so that a file whose name
        matches nothing gets a message listing the three that do.
    scenario_path : str
        The canonical path of that scenario in this repository, which is what
        the regeneration command in the header names.
    document_path : str
        Where the rendered document is committed.
    body : Body
        The builder.
    """

    identifier: str
    subtitle: str
    scenario_name: str
    scenario_path: str
    document_path: str
    body: Body


@dataclass(frozen=True, slots=True)
class Dossier:
    """A rendered document and the log of the runs that produced it.

    Parameters
    ----------
    spec : DossierSpec
        Which dossier this is.
    text : str
        The Markdown, ending in a newline, ready to compare byte for byte with
        the committed file.
    log : DegradationLog
        Every entry every run recorded, so ``quoss dossier`` can print them and
        derive an exit status exactly as ``quoss run`` does.
    """

    spec: DossierSpec
    text: str
    log: DegradationLog


def regenerate_command(spec: DossierSpec) -> str:
    """Return the command that rewrites ``spec``'s committed document."""
    return f"uv run quoss dossier {spec.scenario_path} --out {spec.document_path}"


def provenance_block(spec: DossierSpec, scenario: AnyScenario) -> list[str]:
    """Render the header that ties this document to one exact set of inputs.

    The hash is of the scenario that was actually run, not of the file the spec
    names, and the difference is the point: regenerating this document from an
    edited copy produces a different hash, the committed bytes stop matching,
    and ``tests/dossier/test_docs.py`` fails. A document whose inputs cannot be
    named is a document whose figures cannot be reproduced.

    The version is here for the same reason and has the same consequence: a
    release that changes a number invalidates every dossier until each is
    regenerated, which is the behaviour wanted. A stale dossier is worse than
    no dossier, because it is the one that gets taken to the meeting.
    """
    return [
        *table(
            ["", ""],
            [
                ["Scenario", f"`{spec.scenario_path}`"],
                ["Scenario hash (SHA-256)", f"`{scenario_hash(scenario)}`"],
                ["QuOSS version", f"`{quoss.__version__}`"],
                ["Regenerate with", f"`{regenerate_command(spec)}`"],
            ],
        ),
        "",
        "Every figure below was computed by the engine when this file was generated, from the "
        "scenario whose hash is above. Nothing is transcribed by hand. "
        "`tests/dossier/test_docs.py` re-renders the document and fails when the committed "
        "bytes differ, so a figure here that the code no longer produces is a red build and "
        "not a quiet lie.",
        "",
    ]


def render(spec: DossierSpec, scenario: AnyScenario) -> Dossier:
    """Build one dossier from the scenario it was given.

    Parameters
    ----------
    spec : DossierSpec
        Which dossier to build.
    scenario : Scenario or HorizontalScenario
        The inputs, already loaded and validated. Passed in rather than read
        from ``spec.scenario_path`` so that ``quoss dossier`` renders the file
        the user named and not a different one with the same name.

    Returns
    -------
    Dossier
        The text and the runs' log.
    """
    log = DegradationLog()
    lines = [
        f"<!-- Generated by `{regenerate_command(spec)}`. Do not edit by hand: "
        "tests/dossier/test_docs.py fails when this file differs from the generated text. -->",
        "",
        f"# {spec.identifier} {EM_DASH} {spec.subtitle}",
        "",
        *provenance_block(spec, scenario),
        *spec.body(scenario, log),
    ]
    text = "\n".join(line.rstrip() for line in lines).rstrip("\n") + "\n"
    return Dossier(spec=spec, text=text, log=log)


DOSSIER_MODULES: Final = (
    "quoss.dossier.ge1",
    "quoss.dossier.ge0b",
    "quoss.dossier.reference",
)
"""The builder modules, in the order ``python -m quoss.dossier`` regenerates them.

Names and not imports, and the reason is mechanical rather than stylistic: every
builder imports this module for its formatters, so importing them back here at
module level makes a cycle that fails whichever of the two a caller happens to
reach first. Naming them as strings and resolving in :func:`dossiers` breaks it
in the one direction that has to be broken, and the resolution is checked --
``tests/dossier/test_docs.py`` calls :func:`dossiers`, so a module named here
and absent is a red build rather than a lazy surprise.
"""


@cache
def dossiers() -> tuple[DossierSpec, ...]:
    """Return the registered dossiers, in :data:`DOSSIER_MODULES` order.

    Cached because resolving it imports three modules and the answer cannot
    change within a process.

    Raises
    ------
    ConfigurationError
        If a named module cannot be imported or has no ``SPEC``.

    Examples
    --------
    >>> [spec.identifier for spec in dossiers()]
    ['GE-1', 'GE-0b', 'reference-link']
    """
    specs: list[DossierSpec] = []
    for name in DOSSIER_MODULES:
        try:
            module = import_module(name)
            spec = module.SPEC
        except (ImportError, AttributeError) as exc:
            raise ConfigurationError(
                f"dossier module {name!r} is registered in DOSSIER_MODULES and does not provide "
                f"a SPEC: {exc}"
            ) from exc
        specs.append(spec)
    return tuple(specs)


def identifiers() -> tuple[str, ...]:
    """Return the three experiment identifiers, in registry order.

    Examples
    --------
    >>> identifiers()
    ('GE-1', 'GE-0b', 'reference-link')
    """
    return tuple(spec.identifier for spec in dossiers())


def dossier_for(scenario: AnyScenario) -> DossierSpec:
    """Return the dossier a scenario produces, by its ``name`` field.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        A loaded scenario.

    Returns
    -------
    DossierSpec
        The registered dossier.

    Raises
    ------
    ScenarioError
        If no dossier is registered for that name, listing the ones that are.
        A dossier is a document somebody wrote for one experiment, so there is
        no generic fallback to fall back to: an unregistered scenario has no
        sections, and emitting an empty document under a confident title would
        be worse than the error.

    Examples
    --------
    >>> from quoss.scenario.defaults import ge1_two_terminals
    >>> dossier_for(ge1_two_terminals()).identifier
    'GE-1'
    """
    for spec in dossiers():
        if spec.scenario_name == scenario.name:
            return spec
    known = ", ".join(f"{spec.scenario_name} -> {spec.document_path}" for spec in dossiers())
    raise ScenarioError(
        f"no dossier is registered for scenario {scenario.name!r}. A dossier is prose written "
        f"for one experiment, so there is nothing generic to emit instead. Registered: {known}."
    )
