"""Tests for `quoss.validation.base`: the rule, the refusals and the renderer.

- ``TestTheStatusRule`` — the four statuses, at and across each boundary.
- ``TestAStatusCannotBeTyped`` — the property the whole package rests on: a
  status that disagrees with its own numbers is an exception, not a row.
- ``TestWhatACaseRefuses`` — every malformed case, one test each.
- ``TestAccountedTerm`` — the interval's own invariants.
- ``TestTheTableRuns`` — `run_all` over the real modules, and the two mappings.
- ``TestTheRenderer`` — the Markdown a reader ends up with.
"""

from __future__ import annotations

import math
from importlib import import_module
from pathlib import Path

import pytest

from quoss.core.errors import DomainError
from quoss.validation.base import (
    CASE_MODULES,
    EXPECTED_DISAGREEMENTS,
    PENDING_DISAGREEMENTS,
    REGENERATE_COMMAND,
    AccountedTerm,
    Comparison,
    ValidationCase,
    ValidationStatus,
    classify,
    render_markdown,
    run_all,
)
from quoss.validation.ntanos2021 import NTANOS_2021

from .cases import ACCOUNTED, VALID, case


class TestTheStatusRule:
    """`classify` at each boundary, because a rule is only as good as its edges."""

    def test_inside_the_tolerance_is_reproduced(self) -> None:
        assert classify(published=10.0, computed=10.4, tolerance=0.5) is (
            ValidationStatus.REPRODUCED
        )

    def test_exactly_on_the_tolerance_is_reproduced(self) -> None:
        """Closed interval, and it is a choice: `<=`, not `<`.

        A published value quoted to one decimal carries a half-digit of
        uncertainty, and a computed value landing exactly on that half-digit is
        as consistent with the source as one landing inside it. An open
        interval would turn the most common transcription — a number printed to
        its last significant figure — into a coin flip on the last bit.
        """
        assert classify(published=10.0, computed=10.5, tolerance=0.5) is (
            ValidationStatus.REPRODUCED
        )

    def test_just_outside_is_not_reproduced(self) -> None:
        assert classify(published=10.0, computed=10.5 + 1e-12, tolerance=0.5) is (
            ValidationStatus.NOT_REPRODUCED
        )

    def test_a_zero_tolerance_demands_equality_and_is_allowed(self) -> None:
        """Legitimate for an exact identity, e.g. a count or an integer ratio."""
        assert classify(published=3.0, computed=3.0, tolerance=0.0) is ValidationStatus.REPRODUCED
        assert classify(published=3.0, computed=3.0 + 1e-15, tolerance=0.0) is (
            ValidationStatus.NOT_REPRODUCED
        )

    @pytest.mark.parametrize(
        ("published", "computed", "comparison", "expected"),
        [
            (10.0, 9.0, Comparison.AT_MOST, ValidationStatus.REPRODUCED),
            (10.0, 10.5, Comparison.AT_MOST, ValidationStatus.REPRODUCED),
            (10.0, 11.0, Comparison.AT_MOST, ValidationStatus.NOT_REPRODUCED),
            (10.0, 11.0, Comparison.AT_LEAST, ValidationStatus.REPRODUCED),
            (10.0, 9.5, Comparison.AT_LEAST, ValidationStatus.REPRODUCED),
            (10.0, 9.0, Comparison.AT_LEAST, ValidationStatus.NOT_REPRODUCED),
        ],
    )
    def test_a_one_sided_claim_is_one_sided(
        self,
        published: float,
        computed: float,
        comparison: Comparison,
        expected: ValidationStatus,
    ) -> None:
        """An "at most 10 dB" claim is not "10 dB": far below reproduces, above does not."""
        assert (
            classify(published=published, computed=computed, tolerance=0.5, comparison=comparison)
            is expected
        )

    def test_a_missing_value_on_either_side_is_a_gap(self) -> None:
        assert classify(published=None, computed=None, tolerance=None) is ValidationStatus.GAP
        assert classify(published=1.0, computed=None, tolerance=0.1) is ValidationStatus.GAP

    def test_an_accounted_term_is_consulted_only_after_the_comparison_fails(self) -> None:
        """A term never upgrades a pass or rescues a residual of the wrong sign.

        The residual is ``published - computed``, so a term admitting ``[0, 5]``
        closes a computation that came out *below* the source and says nothing
        about one that came out above. That asymmetry is the whole content of
        the term: an omitted loss can only make the real number bigger.
        """
        assert classify(published=10.0, computed=10.1, tolerance=0.5, accounted=ACCOUNTED) is (
            ValidationStatus.REPRODUCED
        )
        assert classify(published=10.0, computed=7.0, tolerance=0.5, accounted=ACCOUNTED) is (
            ValidationStatus.COMPATIBLE
        )
        assert classify(published=10.0, computed=13.0, tolerance=0.5, accounted=ACCOUNTED) is (
            ValidationStatus.NOT_REPRODUCED
        )

    def test_a_residual_past_the_terms_upper_bound_is_not_compatible(self) -> None:
        """The interval is widened by the tolerance and by nothing else.

        The term admits ``[0, 5]`` and the tolerance is 0.5, so the residual
        ``published - computed`` is admitted up to 5.5 and no further — which
        puts the boundary at ``computed = 4.5`` exactly. Asserted on both sides
        of it, because "widened by the tolerance" is the kind of clause that
        reads the same whether the code adds the tolerance once, twice or not
        at all.
        """
        assert classify(published=10.0, computed=4.5, tolerance=0.5, accounted=ACCOUNTED) is (
            ValidationStatus.COMPATIBLE
        )
        assert classify(
            published=10.0, computed=4.5 - 1e-9, tolerance=0.5, accounted=ACCOUNTED
        ) is (ValidationStatus.NOT_REPRODUCED)

    def test_an_unbounded_term_admits_any_residual_of_its_sign(self) -> None:
        """The Ntanos 20 dB case: an unstated extinction can only add loss."""
        unbounded = AccountedTerm(
            name="unstated extinction", lower=0.0, upper=math.inf, basis="a loss is >= 0"
        )
        assert classify(published=20.0, computed=19.094, tolerance=0.5) is (
            ValidationStatus.NOT_REPRODUCED
        )
        assert classify(published=20.0, computed=19.094, tolerance=0.5, accounted=unbounded) is (
            ValidationStatus.COMPATIBLE
        )
        assert classify(published=20.0, computed=-1e6, tolerance=0.5, accounted=unbounded) is (
            ValidationStatus.COMPATIBLE
        )

    @pytest.mark.parametrize("tolerance", [None, -0.1, math.inf, math.nan])
    def test_a_comparison_without_a_usable_tolerance_is_refused(self, tolerance: float) -> None:
        """Including infinity, which would make every case reproduce.

        A tolerance is the width the *source* licenses. An infinite one is not a
        generous reading of a source, it is the absence of a claim wearing the
        word "reproduced".
        """
        with pytest.raises(DomainError, match="finite tolerance"):
            classify(published=1.0, computed=2.0, tolerance=tolerance)

    @pytest.mark.parametrize(("published", "computed"), [(math.nan, 1.0), (1.0, math.inf)])
    def test_a_non_finite_value_is_refused(self, published: float, computed: float) -> None:
        with pytest.raises(DomainError, match="must be finite"):
            classify(published=published, computed=computed, tolerance=0.5)


class TestAStatusCannotBeTyped:
    """The property the package exists for: a badge that outlives its agreement fails.

    `ValidationCase` recomputes its own status in `__post_init__`. Hand-editing
    a status in a case module — the cheap way to make a red table green — is
    therefore not a quiet lie, it is a `DomainError` on the next `run_all`.
    """

    def test_a_declared_status_the_numbers_do_not_give_is_an_error(self) -> None:
        with pytest.raises(DomainError, match="was declared but the numbers give"):
            ValidationCase(**VALID, status=ValidationStatus.GAP)

    def test_the_message_names_the_case_and_both_statuses(self) -> None:
        with pytest.raises(DomainError) as excinfo:
            ValidationCase(**VALID, status=ValidationStatus.NOT_REPRODUCED)
        message = str(excinfo.value)
        assert VALID["identifier"] in message
        assert "'not_reproduced'" in message and "'reproduced'" in message
        assert "ValidationCase.evaluate" in message

    def test_evaluate_is_the_way_in_and_agrees_with_classify(self) -> None:
        built = case()
        assert built.status is ValidationStatus.REPRODUCED
        assert built.status is classify(
            published=built.published, computed=built.computed, tolerance=built.tolerance
        )


class TestWhatACaseRefuses:
    """One malformed case per test, so a failure names what is wrong."""

    @pytest.mark.parametrize(
        "field",
        ["identifier", "source", "locator", "quantity", "unit", "tolerance_basis", "note", "test"],
    )
    def test_an_empty_text_field(self, field: str) -> None:
        """Whitespace counts as empty: a cell of spaces renders as a cell of nothing."""
        with pytest.raises(DomainError, match="must not be empty"):
            case(**{field: "   "})

    @pytest.mark.parametrize("identifier", ["Source.Quantity", "source quantity"])
    def test_an_identifier_that_is_not_a_stable_key(self, identifier: str) -> None:
        with pytest.raises(DomainError, match="lowercase without spaces"):
            case(identifier=identifier)

    def test_a_level_that_is_not_v2_or_v3(self) -> None:
        """V4 is refused by name, and the message says why rather than listing the enum."""
        with pytest.raises(DomainError, match="not validation"):
            case(level="V4")

    def test_a_test_that_is_not_a_pytest_node_id(self) -> None:
        """A row has to be traceable to an assertion somebody can run."""
        with pytest.raises(DomainError, match="pytest node id"):
            case(test="tests/validation/test_base.py")

    def test_a_computed_value_with_nothing_published(self) -> None:
        """Not a comparison: it is this project quoting itself, which is V4."""
        with pytest.raises(DomainError, match="not a comparison"):
            case(published=None, computed=1.0, tolerance=0.5)

    def test_an_accounted_term_on_a_one_sided_comparison(self) -> None:
        """A term closes a residual, and only a point comparison has one."""
        with pytest.raises(DomainError, match="only a point comparison"):
            case(computed=20.0, comparison=Comparison.AT_MOST, accounted=ACCOUNTED)

    def test_nothing_published_and_nothing_computed_is_allowed_and_is_a_gap(self) -> None:
        """The declared-hole shape of ADR 0009, which the table has to be able to hold."""
        built = case(published=None, computed=None, tolerance=None)
        assert built.status is ValidationStatus.GAP


class TestAccountedTerm:
    def test_an_interval_that_is_not_one(self) -> None:
        with pytest.raises(DomainError, match="lower <= upper"):
            AccountedTerm(name="n", lower=1.0, upper=0.0, basis="b")

    @pytest.mark.parametrize(("lower", "upper"), [(math.nan, 1.0), (0.0, math.nan)])
    def test_a_nan_bound(self, lower: float, upper: float) -> None:
        with pytest.raises(DomainError, match="neither NaN"):
            AccountedTerm(name="n", lower=lower, upper=upper, basis="b")

    @pytest.mark.parametrize(("name", "basis"), [("  ", "b"), ("n", "  ")])
    def test_a_term_without_a_name_or_a_basis(self, name: str, basis: str) -> None:
        """A bound with no stated origin is the tolerance-chosen-to-pass problem again."""
        with pytest.raises(DomainError, match="needs a name and a basis"):
            AccountedTerm(name=name, lower=0.0, upper=1.0, basis=basis)

    def test_a_degenerate_interval_is_a_term_computed_exactly(self) -> None:
        """Farid & Hranilovic's finite-aperture correction is `lower == upper`."""
        exact = AccountedTerm(name="exact", lower=0.25, upper=0.25, basis="computed in closed form")
        assert exact.lower == exact.upper


class TestDeviation:
    def test_the_relative_deviation_is_signed_and_against_the_published_value(self) -> None:
        assert case(published=10.0, computed=11.0, tolerance=2.0).deviation == pytest.approx(0.1)
        assert case(published=10.0, computed=9.0, tolerance=2.0).deviation == pytest.approx(-0.1)

    def test_a_negative_published_value_still_divides_by_its_magnitude(self) -> None:
        assert case(published=-10.0, computed=-11.0, tolerance=2.0).deviation == pytest.approx(-0.1)

    def test_a_published_zero_has_no_relative_deviation(self) -> None:
        """Not infinity and not zero: a threshold of zero is compared absolutely."""
        assert case(published=0.0, computed=0.1, tolerance=0.5).deviation is None

    def test_a_gap_has_no_deviation(self) -> None:
        assert case(published=None, computed=None, tolerance=None).deviation is None


class TestTheTableRuns:
    """`run_all` over the real case modules, and what the two mappings must satisfy."""

    @pytest.fixture(scope="module")
    def cases(self) -> tuple[ValidationCase, ...]:
        return run_all()

    def test_every_declared_module_contributes(self, cases: tuple[ValidationCase, ...]) -> None:
        """The regression that motivated this directory: `run_all` used to raise.

        `CASE_MODULES` listed `quoss.validation.ntanos2021`, which was never
        written, so the package's only entry point raised `ModuleNotFoundError`
        on every call — the table that exists to stop "validated" from being a
        badge could not be produced at all. The name is back in the tuple and
        the module exists now, so what this asserts is the weaker, checkable
        thing that would have caught it either way: every name in the tuple
        imports and returns at least one case.
        """
        assert cases
        assert len(CASE_MODULES) == 4
        collected = 0
        for name in CASE_MODULES:
            module = import_module(name)
            own = module.cases()
            assert own, f"{name} contributes no case"
            collected += len(own)
        assert collected == len(cases)

    def test_identifiers_are_unique(self, cases: tuple[ValidationCase, ...]) -> None:
        identifiers = [c.identifier for c in cases]
        assert len(identifiers) == len(set(identifiers))

    def test_every_disagreement_is_expected_and_every_expectation_is_reachable(
        self, cases: tuple[ValidationCase, ...]
    ) -> None:
        """Both directions, which is what makes the mapping worth keeping.

        A new disagreement nobody wrote down fails here; so does a listed one
        that started agreeing, because the note and the ADR paragraph behind it
        describe something that no longer happens and must be rewritten rather
        than silently left.
        """
        disagreeing = {c.identifier for c in cases if c.status is ValidationStatus.NOT_REPRODUCED}
        assert disagreeing == set(EXPECTED_DISAGREEMENTS)

    def test_a_pending_disagreement_is_not_also_an_expected_one(self) -> None:
        """The two mappings partition, so moving one across cannot be half-done."""
        assert not set(PENDING_DISAGREEMENTS) & set(EXPECTED_DISAGREEMENTS)

    def test_no_pending_identifier_is_produced_by_a_module_that_exists(
        self, cases: tuple[ValidationCase, ...]
    ) -> None:
        """If one starts being produced, it belongs in EXPECTED_DISAGREEMENTS instead."""
        assert not {c.identifier for c in cases} & set(PENDING_DISAGREEMENTS)

    def test_the_paper_the_reference_link_is_built_on_is_in_the_table(
        self, cases: tuple[ValidationCase, ...]
    ) -> None:
        """Asserted the opposite until stage 8.1, and that inversion is the point of it.

        Ntanos et al. 2021 supplies the receiver, the transmitter, the protocol
        parameters and the study-night radiance of the reference link, and for
        as long as this package existed it had **no row here**. The assertion
        was written as an absence — `not [c for c in cases if ...]` — with a
        docstring saying "the day the module lands, this test fails and says
        so". It did, and this is the inversion.

        What is asserted now is what the absence was standing in for: the paper
        that supplies the link is covered, with more than a token row, and every
        one of its identifiers is namespaced to it so that
        `EXPECTED_DISAGREEMENTS` stays readable by source.
        """
        own = [c for c in cases if c.identifier.startswith("ntanos2021.")]
        assert len(own) == 11
        assert {c.source for c in own} == {NTANOS_2021}
        assert not set(PENDING_DISAGREEMENTS) & {c.identifier for c in cases}

    def test_the_one_disagreement_still_without_a_row_says_why(self) -> None:
        """`PENDING_DISAGREEMENTS` is down to one entry, and it is a decision.

        Five of the six entries were Ntanos et al. findings that became rows in
        stage 8.1. The sixth — Lim et al.'s 1e4 block reaching 135 km — stays,
        because reproducing it needs their optimisation over five free
        parameters, and lifting that into `src/` to buy one row would leave this
        project carrying two implementations of one published Evaluation
        section. The entry has to keep saying that: a pending disagreement whose
        note does not name where it *is* measured is indistinguishable from one
        nobody got round to.
        """
        assert set(PENDING_DISAGREEMENTS) == {"lim2014.block-1e4-reach"}
        note = PENDING_DISAGREEMENTS["lim2014.block-1e4-reach"]
        assert "tests/qkd/test_finite_key.py" in note

    def test_every_case_names_a_test_file_that_exists(
        self, cases: tuple[ValidationCase, ...], project_root: Path
    ) -> None:
        """A row is traceable to an assertion, so the path half of its node id must resolve."""
        root = project_root
        for c in cases:
            path = c.test.split("::")[0]
            assert (root / path).is_file(), f"{c.identifier} names {path}, which does not exist"

    def test_two_modules_producing_one_identifier_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A duplicate identifier would make EXPECTED_DISAGREEMENTS ambiguous.

        The mapping is keyed by identifier, so two cases sharing one would make
        "this disagreement is expected" true of a case nobody looked at. Forced
        here by collecting one real module twice, which is the cheapest way to
        produce the collision without a fake module that could drift.
        """
        import quoss.validation.base as base_module

        monkeypatch.setattr(
            base_module,
            "CASE_MODULES",
            ("quoss.validation.satquma", "quoss.validation.satquma"),
        )
        with pytest.raises(DomainError, match="duplicate validation case identifiers"):
            base_module.run_all()

    def test_a_status_is_never_typed_anywhere_in_the_real_table(
        self, cases: tuple[ValidationCase, ...]
    ) -> None:
        for c in cases:
            assert c.status is classify(
                published=c.published,
                computed=c.computed,
                tolerance=c.tolerance,
                comparison=c.comparison,
                accounted=c.accounted,
            )


class TestTheRenderer:
    def test_an_empty_table_still_says_what_it_is(self) -> None:
        text = render_markdown(())
        assert REGENERATE_COMMAND in text.splitlines()[0]
        assert "| total | 0 |" in text

    def test_the_summary_counts_every_status(self) -> None:
        built = (
            case(),
            case(identifier="source.gap", published=None, computed=None, tolerance=None),
            case(identifier="source.compat", computed=7.0, accounted=ACCOUNTED),
            case(identifier="source.bad", computed=100.0),
        )
        text = render_markdown(built)
        assert "| reproduced | 1 |" in text
        assert "| compatible | 1 |" in text
        assert "| **not reproduced** | 1 |" in text
        assert "| gap | 1 |" in text
        assert "| total | 4 |" in text

    def test_sources_appear_once_in_order_of_first_appearance(self) -> None:
        text = render_markdown(
            (
                case(identifier="a.one", source="Second Source"),
                case(identifier="b.one", source="First Source"),
                case(identifier="a.two", source="Second Source"),
            )
        )
        assert text.index("## Second Source") < text.index("## First Source")
        assert text.count("## Second Source") == 1

    def test_a_pipe_in_a_cell_is_escaped(self) -> None:
        """An unescaped pipe ends the cell and silently shifts every column after it."""
        text = render_markdown((case(quantity="a|b"),))
        assert "a\\|b" in text

    def test_a_newline_in_a_cell_becomes_a_space(self) -> None:
        text = render_markdown((case(locator="Eq. (1),\nTable 2"),))
        assert "Eq. (1), Table 2" in text

    def test_a_gap_renders_em_dashes_and_not_zeros(self) -> None:
        """A zero in a published column would be a number nobody printed."""
        text = render_markdown((case(published=None, computed=None, tolerance=None),))
        assert "| — | — | — | — |" in text

    @pytest.mark.parametrize(
        ("comparison", "expected"),
        [
            (Comparison.EQUAL, "± 0.5"),
            (Comparison.AT_MOST, "≤ published + 0.5"),
            (Comparison.AT_LEAST, "≥ published − 0.5"),
        ],
    )
    def test_the_tolerance_column_says_which_inequality(
        self, comparison: Comparison, expected: str
    ) -> None:
        computed = {Comparison.AT_LEAST: 10.4}.get(comparison, 10.1)
        text = render_markdown((case(computed=computed, comparison=comparison),))
        assert expected in text

    def test_an_accounted_term_is_shown_with_its_interval_and_basis(self) -> None:
        """So a reader can see how much the word "compatible" is resting on."""
        text = render_markdown((case(computed=7.0, accounted=ACCOUNTED),))
        assert "*Accounted term:* a term the source omits, residual admitted in [0, 5] dB" in text
        assert ACCOUNTED.basis in text

    def test_the_degradations_the_physics_logged_are_listed(self) -> None:
        text = render_markdown(
            (case(degradations=("turbulence.weak-fluctuation-limit-exceeded",)),)
        )
        assert "*Logged by the physics while computing:* `turbulence.weak-fluctuation" in text

    def test_a_case_without_degradations_gets_no_empty_bullet(self) -> None:
        assert "Logged by the physics" not in render_markdown((case(),))

    def test_every_case_carries_its_node_id_into_the_document(self) -> None:
        text = render_markdown((case(),))
        assert f"*Measured by:* `{VALID['test']}`" in text

    def test_the_render_is_deterministic(self) -> None:
        """No timestamps and no timings, so the committed file diffs byte for byte."""
        assert render_markdown(run_all()) == render_markdown(run_all())
