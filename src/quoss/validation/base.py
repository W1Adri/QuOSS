"""A validation case, how its status is derived, and the table that collects them.

Para quien llegue nuevo: this module does not compute any physics. It fixes the
*shape* of a validation claim, so that every claim in ``docs/validation.md`` is
made the same way and can fail the same way.

What a case is
--------------
A **validation case** is one number printed in a source (a paper, a
recommendation) set beside the same quantity recomputed by this project, with
four things that make the comparison mean something:

- a **locator** — the equation, table, figure or section where the number is
  printed, so a reader can open the source at the right page;
- a **tolerance** in the case's own unit, and its **basis** — where the width
  comes from (the source's printed precision, the size of a term a published
  approximation drops, float error). Never "what today's result needed";
- a **status**, derived from the three numbers above and never typed by hand;
- a **test** — the pytest node that measures the same number, so a row of the
  table is traceable to an assertion that runs in CI.

Why the status is derived and not declared
------------------------------------------
Because a declared status is a badge, and a badge outlives the agreement it
described. If a refactor moves the ITU-R P.1622 Table 2 variance at 1.55 µm
from 0.0659 to 0.0759, a hand-written ``REPRODUCED`` would still say
reproduced; a derived one says ``NOT_REPRODUCED`` the first time
``run_all`` is called, and ``tests/validation`` fails because the case is not
in :data:`EXPECTED_DISAGREEMENTS`. So :class:`ValidationCase` recomputes its
own status in ``__post_init__`` and raises :class:`~quoss.core.errors.DomainError`
if the one it was given differs — editing a status in a case module is not a
quiet lie, it is an exception.

The four statuses, and the rule
-------------------------------
With ``p`` the published value, ``c`` the computed one and ``t`` the tolerance:

1. ``GAP`` — there is nothing to compute against, or nothing was computed:
   the source prints the number only in a figure, or leaves out an input the
   computation needs (ADR 0009 style: a declared hole beats a false V2).
2. ``REPRODUCED`` — the comparison holds within ``t``: ``|c - p| <= t`` for
   :attr:`Comparison.EQUAL`, ``c <= p + t`` for :attr:`Comparison.AT_MOST`,
   ``c >= p - t`` for :attr:`Comparison.AT_LEAST`.
3. ``COMPATIBLE`` — it does not hold, but the residual ``p - c`` lies inside the
   admissible interval of a declared :class:`AccountedTerm`, widened by ``t``.
   The term is something the source leaves out and this project can bound: an
   aperture correction computed exactly, or an extinction the source never
   states and that can only add loss (interval ``[0, inf)``).
4. ``NOT_REPRODUCED`` — neither. The disagreement is written into the case's
   note and its identifier into :data:`EXPECTED_DISAGREEMENTS`.

Worked example, the one that motivated ``COMPATIBLE``: Ntanos et al. 2021
§4.2.1 print a best-case downlink loss of 20 dB; their own parameters give
19.094 dB here, and 20 is printed to the unit, so ``t = 0.5`` dB and
``|19.094 - 20| = 0.906 > 0.5`` — not reproduced. But the paper states no
atmospheric extinction, and an extinction can only add loss: the accounted term
``[0, inf)`` contains the residual 0.906, so the status is ``COMPATIBLE``.
(``tests/channel/test_link_budget.py::TestAgainstNtanosEtAl::test_their_twenty_decibel_best_case_does_not_reproduce``.)
A one-sided term like that one is the weakest form of compatibility, and the
table says which cases rest on it.

What this module leaves out
---------------------------
No V4. A frozen snapshot of this project's own output is not validation
(``tests/golden/README.md``), so :class:`ValidationCase` rejects any level other
than ``"V2"`` and ``"V3"``. And no network: every published number lives in a
case module next to its citation, transcribed from a document that was opened
when the case was written.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from importlib import import_module
from types import MappingProxyType
from typing import Final, Literal

from quoss.core.errors import DomainError

__all__ = [
    "CASE_MODULES",
    "EXPECTED_DISAGREEMENTS",
    "PENDING_DISAGREEMENTS",
    "REGENERATE_COMMAND",
    "AccountedTerm",
    "Comparison",
    "ValidationCase",
    "ValidationStatus",
    "classify",
    "render_markdown",
    "run_all",
]

Level = Literal["V2", "V3"]

REGENERATE_COMMAND: Final = "uv run python -m quoss.validation --write docs/validation.md"
"""The one command that writes ``docs/validation.md``; quoted in the file and in the test."""

CASE_MODULES: Final = (
    "quoss.validation.channel",
    "quoss.validation.ntanos2021",
    "quoss.validation.satquma",
    "quoss.validation.micius",
)
"""The modules :func:`run_all` collects, in the order the table lists them.

Channel recommendations first because every link number downstream depends on
them, then the paper the reference link is assembled from together with the two
protocol papers it is evaluated with, then the two external systems.

**The second entry was missing for as long as this package existed**, and the
way it was missing is worth keeping. The tuple listed
``quoss.validation.ntanos2021`` before that module was written, so
:func:`run_all` — the package's only entry point — raised
``ModuleNotFoundError`` on every call: the table that exists to stop
"validated" from being a badge could not be produced at all. The entry was then
removed and the hole declared in :data:`PENDING_DISAGREEMENTS`, on the rule that
a table with a declared hole says more than a table nobody can render. The
module now exists, so the entry is back and the hole is closed — except for
one identifier, which stays pending with its reason measured.
"""

EXPECTED_DISAGREEMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "micius2017.diffraction-loss-1200km": (
            "22 dB at 1200 km is not the diffraction loss of the printed 300 mm aperture; the "
            "printed ~10 urad divergence is 2.8x its diffraction limit."
        ),
        "ntanos2021.eq5-printed-gain-product": (
            "Eq. (5) as printed, (8/w0)^2, is 8x the energy-conserving 8/w0^2 and returns a "
            "transmittance of 1.36 at their own largest station; ADR 0009, Ntanos caveat."
        ),
        "ntanos2021.eq20-background-click-probability": (
            "Eq. (20) calls t_gate x R_back a probability; under ITU-R bright sunshine at the "
            "2.3 m station it is 3.42, and the exact 1 - exp(-mu) is 0.967."
        ),
        "ntanos2021.full-moon-background": (
            "\u00a74.2.2 '10 kcps at most' is 76.4 kcps from their own Eq. (19) at the 2.3 m station; "
            "ADR 0009, Ntanos caveat."
        ),
        "ntanos2021.protocol-efficiency-as-printed": (
            "\u00a74.1 prints 4:1:16 and q = 2/5 in one sentence; Eq. (A1) gives 0.095 for that order, "
            "a factor 4.2 away."
        ),
        "ntanos2021.single-pass-peak-skr": (
            "\u00a74.3.1's 3.33e-4 bits/pulse needs 24.07 dB of total loss, 4.07 dB more than the "
            "20 dB \u00a74.2.1 declares as the best case; the two printed claims disagree with each other."
        ),
        "ntanos2021.aperture-ratio-helmos-skinakas": (
            "\u00a74.3.2 'about four times' is 3.06 at zenith, rising to 3.25 at their 20 deg floor."
        ),
        "ntanos2021.skinakas-latitude-as-printed": (
            "\u00a72 prints 'longitude: 35.2118, latitude: 24.8981' for a station on Crete; the labels "
            "are swapped, systematically, in all three stations."
        ),
    }
)
"""Every case expected to come out ``NOT_REPRODUCED``, with why, one line each.

Both directions are enforced by ``tests/validation/test_base.py``: a new
disagreement that is not listed here fails CI, and so does a listed one that
starts agreeing \u2014 which is good news, but news that must be read, because the
case note and the ADR paragraph behind it describe a disagreement that no
longer exists. Enforcing both directions is also why this mapping may not hold a
key no module produces: an entry nobody can reach is a claim nobody can check,
and those live in :data:`PENDING_DISAGREEMENTS` instead.

**Seven of the eight are Ntanos et al. 2021**, and that is not a verdict on the
paper. It is the most fully parameterised source this project has \u2014 numbered
equations, a stated receiver, a stated transmitter, stated protocol parameters
\u2014 so more of its printed consequences can be checked at all. A vaguer source
produces a shorter list and a false sense of agreement.
"""

PENDING_DISAGREEMENTS: Final[Mapping[str, str]] = MappingProxyType(
    {
        "lim2014.block-1e4-reach": (
            "Fig. 1's 1e4 block reaching 135 km does not reproduce \u2014 this project certifies no "
            "key at any fibre length with that block, and its 1e5 curve is their 1e4 one; "
            "ADR 0009 gap 16, measured in tests/qkd/test_finite_key.py."
        ),
    }
)
"""Disagreements that are known and measured but have **no row** in the table.

This mapping held six entries until ``quoss.validation.ntanos2021`` was written:
five Ntanos et al. findings and this one. The five have moved into
:data:`EXPECTED_DISAGREEMENTS` with rows behind them, and
``tests/validation/test_base.py`` checks that the two mappings never share a
key, so the move cannot be half-done.

**Why this one stays, and it is a cost paid in the wrong currency if it does
not.** Lim et al. state that "even if we use a block size of 1e4, cryptographic
keys can still be distributed over a fiber length of 135 km". Reaching their
number needs their optimisation over five free parameters \u2014 the basis bias, the
two state probabilities and the two intensities \u2014 which is about 120 lines of
transcription of their Evaluation section, living today beside the test that
measures the disagreement
(``tests/qkd/test_finite_key.py::TestLim2014Evaluation``). Lifting it into
``src/`` to buy one row would leave this project with **two** implementations of
that section, and one formula in two places is the defect
``docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md`` exists to prevent:
the two drift, and the one that drifts is the one nobody runs. A declared hole
with its measurement named is the cheaper honest answer, which is the same rule
ADR 0009 applies to citations.

What is measured, so the hole is not vague: with a block of 1e4 detections in
the key basis this project certifies **zero** key at 0, 100 and 135 km \u2014 not a
small key, no key \u2014 while its 1e5 block gives a positive rate at 135 km and
zero by 150 km, which is the shape of the curve they draw one decade lower. The
disagreement is therefore exactly one decade in block size, and the two
candidate causes (a different convention for what ``n_X`` counts, and a
different resolution of the ``e_k`` ambiguity of their Evaluation section) are
settled by nothing printed in the paper.
"""


class ValidationStatus(StrEnum):
    """What a comparison between a published and a computed number came to.

    Derived by :func:`classify`, never assigned; the module docstring gives the
    rule with a worked example.
    """

    REPRODUCED = "reproduced"
    COMPATIBLE = "compatible"
    NOT_REPRODUCED = "not_reproduced"
    GAP = "gap"


class Comparison(StrEnum):
    """Which inequality the published number asserts.

    Most published numbers are points (``EQUAL``). Some are bounds, and reading
    a bound as a point would invent precision the source does not claim:
    Ntanos et al. write "10 kcps **at most**" (``AT_MOST``) and "more than eight
    times higher" (``AT_LEAST``). A published *range* — Liao et al.'s "3 dB to
    8 dB" — is an ``EQUAL`` comparison against its midpoint with its half-width
    as the tolerance, which is the same interval written the other way.
    """

    EQUAL = "equal"
    AT_MOST = "at_most"
    AT_LEAST = "at_least"


@dataclass(frozen=True, slots=True, kw_only=True)
class AccountedTerm:
    """A term the source leaves out, bounded, that can close a residual.

    Parameters
    ----------
    name : str
        What the term is, in words ("unstated atmospheric extinction").
    lower, upper : float
        The admissible interval for the residual ``published - computed`` that
        this term can explain, in the case's unit. ``-inf``/``inf`` are allowed
        for a term whose size is unbounded on one side but whose *sign* is
        known — an extinction can only add loss.
    basis : str
        Where the interval comes from. Same standard as a tolerance basis.

    Why an interval and not a value: some terms are computed exactly (Farid &
    Hranilovic's finite-aperture correction to the pointing exponent is
    ``lower == upper``), and some are only known to be one-signed. One shape
    covers both, and the rendered table shows the interval so a reader can see
    how much the compatibility rests on.

    Examples
    --------
    >>> AccountedTerm(
    ...     name="unstated extinction", lower=0.0, upper=math.inf, basis="a loss is >= 0"
    ... ).upper
    inf
    """

    name: str
    lower: float
    upper: float
    basis: str

    def __post_init__(self) -> None:
        if not self.name.strip() or not self.basis.strip():
            raise DomainError("AccountedTerm needs a name and a basis, both non-empty.")
        if math.isnan(self.lower) or math.isnan(self.upper) or self.lower > self.upper:
            raise DomainError(
                f"AccountedTerm {self.name!r}: need lower <= upper and neither NaN, got "
                f"[{self.lower!r}, {self.upper!r}]."
            )


def classify(
    *,
    published: float | None,
    computed: float | None,
    tolerance: float | None,
    comparison: Comparison = Comparison.EQUAL,
    accounted: AccountedTerm | None = None,
) -> ValidationStatus:
    """Derive the status of a comparison. The only place a status is decided.

    Parameters
    ----------
    published, computed : float or None
        The printed value and this project's value, in the same unit. ``None``
        for either means there is no comparison, and the answer is ``GAP``.
    tolerance : float or None
        Non-negative width in the same unit. Required when both values exist.
    comparison : Comparison
        Which inequality the published value asserts.
    accounted : AccountedTerm or None
        A bounded term the source omits, consulted only when the comparison
        itself fails.

    Returns
    -------
    ValidationStatus
        By the rule in the module docstring.

    Raises
    ------
    DomainError
        If both values exist and the tolerance is missing, negative or not
        finite, or either value is not finite.

    Examples
    --------
    The Ntanos et al. 20 dB budget: 0.906 dB outside a 0.5 dB printed precision,
    closed by an extinction that can only add loss.

    >>> extinction = AccountedTerm(name="extinction", lower=0.0, upper=math.inf, basis=">= 0")
    >>> classify(published=20.0, computed=19.094, tolerance=0.5).value
    'not_reproduced'
    >>> classify(published=20.0, computed=19.094, tolerance=0.5, accounted=extinction).value
    'compatible'
    >>> classify(published=20.0, computed=None, tolerance=None).value
    'gap'
    """
    if published is None or computed is None:
        return ValidationStatus.GAP
    if tolerance is None or not math.isfinite(tolerance) or tolerance < 0.0:
        raise DomainError(f"a comparison needs a finite tolerance >= 0, got {tolerance!r}.")
    if not (math.isfinite(published) and math.isfinite(computed)):
        raise DomainError(
            f"published and computed must be finite, got {published!r} and {computed!r}."
        )
    if comparison is Comparison.EQUAL:
        holds = abs(computed - published) <= tolerance
    elif comparison is Comparison.AT_MOST:
        holds = computed <= published + tolerance
    else:
        holds = computed >= published - tolerance
    if holds:
        return ValidationStatus.REPRODUCED
    if accounted is not None:
        residual = published - computed
        if accounted.lower - tolerance <= residual <= accounted.upper + tolerance:
            return ValidationStatus.COMPATIBLE
    return ValidationStatus.NOT_REPRODUCED


@dataclass(frozen=True, slots=True, kw_only=True)
class ValidationCase:
    """One published number beside this project's value for it.

    Build it with :meth:`evaluate`, which derives the status. The constructor
    accepts a status only so the object is a plain record; it recomputes the
    status and raises if the two differ, which is what makes a hand-edited
    status fail instead of rendering.

    Parameters
    ----------
    identifier : str
        Stable, dotted, lowercase: ``"<source>.<quantity>"``. The key of
        :data:`EXPECTED_DISAGREEMENTS`.
    source : str
        Full citation: authors, title, venue, year, and the copy that was opened.
    locator : str
        Equation, table, figure or section — and the parameters it is printed at.
    quantity : str
        What the number is, in words.
    published, computed : float or None
        In ``unit``. ``computed`` is ``None`` for a declared gap.
    unit : str
        Unit of both values and of the tolerance; ``"1"`` if dimensionless.
    tolerance : float or None
        Absolute width in ``unit``; ``None`` only when there is nothing to compare.
    tolerance_basis : str
        Where the width comes from. Never "tuned".
    status : ValidationStatus
        Must equal :func:`classify` of the fields above.
    level : {"V2", "V3"}
        V2: a printed value. V3: an independent implementation.
    note : str
        What the comparison found, with the numbers a reader needs.
    test : str
        Pytest node id, ``path::Class::test``, that measures the same number.
    comparison : Comparison
        Default :attr:`Comparison.EQUAL`.
    accounted : AccountedTerm or None
        The bounded term behind a ``COMPATIBLE``; only with ``EQUAL``.
    degradations : tuple of str
        Codes of the :class:`~quoss.core.errors.Degradation` entries the physics
        recorded while computing this case. A model that warned while producing
        a validation number has to say so in the table, not only in a log.

    Examples
    --------
    >>> case = ValidationCase.evaluate(
    ...     identifier="example.point",
    ...     source="A. Author, Journal 1, 1 (2000)",
    ...     locator="Eq. (1)",
    ...     quantity="a number",
    ...     published=0.07,
    ...     computed=0.0659,
    ...     unit="Np^2",
    ...     tolerance=0.005,
    ...     tolerance_basis="half a unit in the last printed digit",
    ...     level="V2",
    ...     note="example",
    ...     test="tests/x.py::TestX::test_x",
    ... )
    >>> case.status.value, round(case.deviation or 0.0, 4)
    ('reproduced', -0.0586)
    """

    identifier: str
    source: str
    locator: str
    quantity: str
    published: float | None
    computed: float | None
    unit: str
    tolerance: float | None
    tolerance_basis: str
    status: ValidationStatus
    level: Level
    note: str
    test: str
    comparison: Comparison = Comparison.EQUAL
    accounted: AccountedTerm | None = None
    degradations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "identifier",
            "source",
            "locator",
            "quantity",
            "unit",
            "tolerance_basis",
            "note",
            "test",
        ):
            if not str(getattr(self, name)).strip():
                raise DomainError(f"ValidationCase.{name} must not be empty ({self.identifier!r}).")
        if self.identifier != self.identifier.lower() or " " in self.identifier:
            raise DomainError(
                f"identifier must be lowercase without spaces, got {self.identifier!r}."
            )
        if self.level not in ("V2", "V3"):
            raise DomainError(
                f"{self.identifier}: level must be 'V2' or 'V3', got {self.level!r}; a V4 "
                "snapshot of this project's own output is not validation."
            )
        if "::" not in self.test:
            raise DomainError(
                f"{self.identifier}: test must be a pytest node id, got {self.test!r}."
            )
        if self.published is None and self.computed is not None:
            raise DomainError(
                f"{self.identifier}: a computed value with nothing published is not a comparison."
            )
        if self.accounted is not None and self.comparison is not Comparison.EQUAL:
            raise DomainError(
                f"{self.identifier}: an accounted term closes a residual, which only a point "
                "comparison has."
            )
        derived = classify(
            published=self.published,
            computed=self.computed,
            tolerance=self.tolerance,
            comparison=self.comparison,
            accounted=self.accounted,
        )
        if derived is not self.status:
            raise DomainError(
                f"{self.identifier}: status {self.status.value!r} was declared but the numbers "
                f"give {derived.value!r}. The status is derived, not typed; build cases with "
                "ValidationCase.evaluate."
            )

    @classmethod
    def evaluate(
        cls,
        *,
        identifier: str,
        source: str,
        locator: str,
        quantity: str,
        published: float | None,
        computed: float | None,
        unit: str,
        tolerance: float | None,
        tolerance_basis: str,
        level: Level,
        note: str,
        test: str,
        comparison: Comparison = Comparison.EQUAL,
        accounted: AccountedTerm | None = None,
        degradations: tuple[str, ...] = (),
    ) -> ValidationCase:
        """Build a case with its status derived by :func:`classify`.

        Same parameters as the class, minus ``status``. The way every case
        module builds its rows.
        """
        return cls(
            identifier=identifier,
            source=source,
            locator=locator,
            quantity=quantity,
            published=published,
            computed=computed,
            unit=unit,
            tolerance=tolerance,
            tolerance_basis=tolerance_basis,
            status=classify(
                published=published,
                computed=computed,
                tolerance=tolerance,
                comparison=comparison,
                accounted=accounted,
            ),
            level=level,
            note=note,
            test=test,
            comparison=comparison,
            accounted=accounted,
            degradations=degradations,
        )

    @property
    def deviation(self) -> float | None:
        """Relative deviation ``(computed - published) / |published|``.

        ``None`` when either value is missing or the published value is zero,
        where a relative deviation has no meaning (a threshold of zero is
        compared absolutely, through the tolerance).
        """
        if self.published is None or self.computed is None or self.published == 0.0:
            return None
        return (self.computed - self.published) / abs(self.published)


def run_all() -> tuple[ValidationCase, ...]:
    """Recompute every case, in the stable order of :data:`CASE_MODULES`.

    Nothing is cached: each call runs the physics again, so the statuses it
    returns describe the code that is installed now. That is affordable and
    measured: ``tests/validation/test_base.py::TestTheTableRuns`` collects the
    whole table in a module-scoped fixture, and the thirty-five cases take
    about 0.2 s together, because every one of them is a closed form or a
    single integral over the 139-layer ITU grid.

    Returns
    -------
    tuple of ValidationCase
        Each module's ``cases()`` concatenated.

    Raises
    ------
    DomainError
        If two cases share an identifier, which would make
        :data:`EXPECTED_DISAGREEMENTS` ambiguous.
    """
    cases: list[ValidationCase] = []
    for name in CASE_MODULES:
        # Imported here and not at the top: the case modules import this one.
        module = import_module(name)
        cases.extend(module.cases())
    identifiers = [case.identifier for case in cases]
    duplicated = sorted({i for i in identifiers if identifiers.count(i) > 1})
    if duplicated:
        raise DomainError(f"duplicate validation case identifiers: {duplicated}.")
    return tuple(cases)


_STATUS_ORDER: Final = (
    ValidationStatus.REPRODUCED,
    ValidationStatus.COMPATIBLE,
    ValidationStatus.NOT_REPRODUCED,
    ValidationStatus.GAP,
)

_STATUS_LABEL: Final = {
    ValidationStatus.REPRODUCED: "reproduced",
    ValidationStatus.COMPATIBLE: "compatible",
    ValidationStatus.NOT_REPRODUCED: "**not reproduced**",
    ValidationStatus.GAP: "gap",
}


def _number(value: float | None) -> str:
    """Four significant figures, or an em dash for nothing."""
    return "—" if value is None else f"{value:.4g}"


def _cell(text: str) -> str:
    """Escape a table cell: a literal pipe would end the cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _tolerance(case: ValidationCase) -> str:
    if case.tolerance is None:
        return "—"
    width = _number(case.tolerance)
    if case.comparison is Comparison.AT_MOST:
        return f"≤ published + {width}"
    if case.comparison is Comparison.AT_LEAST:
        return f"≥ published − {width}"
    return f"± {width}"


def _deviation(case: ValidationCase) -> str:
    deviation = case.deviation
    return "—" if deviation is None else f"{100.0 * deviation:+.3g} %"


def render_markdown(cases: Sequence[ValidationCase]) -> str:
    """Render the validation table as the text of ``docs/validation.md``.

    Parameters
    ----------
    cases : sequence of ValidationCase
        Usually ``run_all()``.

    Returns
    -------
    str
        A header saying the file is generated and by which command, a count per
        status, then one table per source in order of first appearance, each
        followed by the notes of its cases. Deterministic: no timestamps, no
        timings, numbers at four significant figures, so the committed file can
        be compared with the generated text byte for byte.

    Examples
    --------
    >>> text = render_markdown(())
    >>> text.splitlines()[0].startswith("<!-- Generated")
    True
    """
    lines: list[str] = [
        f"<!-- Generated by `{REGENERATE_COMMAND}`. Do not edit by hand: "
        "tests/validation/test_docs.py fails when this file differs from the generated text. -->",
        "",
        "# Validation",
        "",
        "Every row below is a number printed in a source, recomputed by this project at the "
        "moment this file was generated, and compared under a tolerance whose origin is "
        "written beside it. The status is **derived** from those three numbers "
        "(`quoss.validation.base.classify`), never typed: *reproduced* within the tolerance; "
        "*compatible* once a declared, bounded term the source omits is accounted for; "
        "**not reproduced**, with the disagreement written down; *gap* where the source "
        "gives nothing computable. Only V2 (a printed value) and V3 (an independent "
        "implementation) appear: a snapshot of this project's own output is not validation "
        "(`tests/golden/README.md`).",
        "",
        "## Summary",
        "",
        "| Status | Cases |",
        "|---|---|",
    ]
    for status in _STATUS_ORDER:
        count = sum(1 for case in cases if case.status is status)
        lines.append(f"| {_STATUS_LABEL[status]} | {count} |")
    lines.append(f"| total | {len(cases)} |")

    sources: list[str] = []
    for case in cases:
        if case.source not in sources:
            sources.append(case.source)
    for source in sources:
        group = [case for case in cases if case.source == source]
        lines += [
            "",
            f"## {_cell(source)}",
            "",
            "| Case | Quantity | Locator | Published | Computed | Deviation | Tolerance | Unit "
            "| Status | Level |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for case in group:
            lines.append(
                f"| `{case.identifier}` | {_cell(case.quantity)} | {_cell(case.locator)} "
                f"| {_number(case.published)} | {_number(case.computed)} | {_deviation(case)} "
                f"| {_tolerance(case)} | {_cell(case.unit)} | {_STATUS_LABEL[case.status]} "
                f"| {case.level} |"
            )
        lines.append("")
        for case in group:
            lines.append(f"- **`{case.identifier}`** — {case.note}")
            lines.append(f"  - *Tolerance basis:* {case.tolerance_basis}")
            if case.accounted is not None:
                lines.append(
                    f"  - *Accounted term:* {case.accounted.name}, residual admitted in "
                    f"[{_number(case.accounted.lower)}, {_number(case.accounted.upper)}] "
                    f"{case.unit}. {case.accounted.basis}"
                )
            if case.degradations:
                codes = ", ".join(f"`{code}`" for code in case.degradations)
                lines.append(f"  - *Logged by the physics while computing:* {codes}")
            lines.append(f"  - *Measured by:* `{case.test}`")
    lines.append("")
    return "\n".join(lines)
