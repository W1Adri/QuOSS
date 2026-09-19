"""The committed `docs/experiments/*.md` against a fresh render of each one.

Why these files are committed at all, when a command regenerates them
---------------------------------------------------------------------
The same reason `docs/validation.md` is, plus one that is specific to these
three. The shared reason is the diff: a generated file that is not committed
has no history, so a change to the physics that moved a figure in a document
somebody is holding in a meeting would leave no trace anywhere.

The reason specific to these three is the audience. `docs/validation.md` is
read by somebody who could, in principle, run the command; a dossier is written
for the person deciding whether to buy a lens or lend a bench, who has no
checkout, no Python and no reason to acquire either. For that reader the
committed file **is** the artefact, and the only defence they have against it
being stale is that somebody else's build goes red.

Why committing them needs this test
------------------------------------
Because a committed generated file is a claim about the code, and a dossier is
the worst kind of claim to let rot. The failure is not abstract: `GE-1.md`
prints a certified key against distance and says the link certifies nothing at
5 km. If a change to the fade model moved that cliff to 3 km and the document
still said 5, the document would be actively worse than absent -- it would be a
confident, sourced, hash-stamped argument for building a link that does not
close.

So the comparison is **byte for byte** and not "close enough". Everything in a
dossier was built to allow that: no timestamps, no timings, no git commit, four
significant figures, and a scenario hash that is a pure function of the inputs.
The one deliberately volatile thing in the header is the QuOSS version, and it
is there on purpose -- a release invalidates every dossier until each is
regenerated, which is the behaviour wanted.

What to do when this fails
---------------------------
Nothing is broken yet: the code moved and the documents did not. Run
`uv run python -m quoss.dossier` and **read the diff**. It names the figures
this change moved, in the documents where somebody would have acted on them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import quoss
from quoss.core.errors import ScenarioError
from quoss.dossier import ge0b
from quoss.dossier.base import Dossier, DossierSpec, dossier_for, dossiers, render
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import load_scenario

REGENERATE = "uv run python -m quoss.dossier"


@pytest.fixture(scope="module")
def rendered(project_root: Path) -> dict[str, Dossier]:
    """Render all three dossiers once, from the committed scenario files.

    Module-scoped because it is the expensive fixture in this file -- three
    downlink days, twenty-six sweep points and eight horizontal runs, about two
    and a half seconds -- and every test below reads the same three documents.
    """
    return {
        spec.identifier: render(spec, load_scenario(project_root / spec.scenario_path))
        for spec in dossiers()
    }


@pytest.fixture(scope="module")
def committed(project_root: Path) -> dict[str, str]:
    """Return the text of each committed document."""
    out: dict[str, str] = {}
    for spec in dossiers():
        path = project_root / spec.document_path
        assert path.is_file(), (
            f"{spec.document_path} is missing. It is a committed artefact; regenerate every "
            f"dossier with:\n    {REGENERATE}"
        )
        out[spec.identifier] = path.read_text(encoding="utf-8")
    return out


def _specs() -> list[DossierSpec]:
    return list(dossiers())


def _ids() -> list[str]:
    return [spec.identifier for spec in dossiers()]


class TestTheCommittedDocumentsAreTheGeneratedOnes:
    @pytest.mark.parametrize("spec", _specs(), ids=_ids())
    def test_each_one_matches_byte_for_byte(
        self, spec: DossierSpec, rendered: dict[str, Dossier], committed: dict[str, str]
    ) -> None:
        """The whole point of the files, and the failure message says how to fix it."""
        assert committed[spec.identifier] == rendered[spec.identifier].text, (
            f"{spec.document_path} is out of date with the code. Regenerate it with:\n"
            f"    {REGENERATE}\n"
            "and read the diff: it names the figures this change moved, in a document written "
            "for somebody who will act on them."
        )

    @pytest.mark.parametrize("spec", _specs(), ids=_ids())
    def test_the_header_names_the_command_that_writes_it(
        self, spec: DossierSpec, committed: dict[str, str]
    ) -> None:
        """A generated file naming a command nobody can run is worse than naming none.

        Asserted against the spec rather than a retyped string, so that the
        header and the command cannot drift. That the command *exists* is
        `tests/cli/test_dossier.py`'s job; that it lands in the header is this
        one's.
        """
        first = committed[spec.identifier].splitlines()[0]
        assert first.startswith("<!-- Generated by")
        assert spec.scenario_path in first
        assert spec.document_path in first
        assert "tests/dossier/test_docs.py" in first

    @pytest.mark.parametrize("spec", _specs(), ids=_ids())
    def test_it_carries_the_hash_of_the_scenario_it_was_built_from(
        self, spec: DossierSpec, project_root: Path, committed: dict[str, str]
    ) -> None:
        """The hash is the only thing tying a figure to one exact set of inputs.

        Checked against the hash of the scenario file on disk, so that a
        document regenerated from an edited copy carries the copy's hash and
        the byte comparison above fails rather than passing on a document whose
        inputs nobody can name.
        """
        digest = scenario_hash(load_scenario(project_root / spec.scenario_path))
        assert f"| Scenario hash (SHA-256) | `{digest}` |" in committed[spec.identifier]
        assert f"| QuOSS version | `{quoss.__version__}` |" in committed[spec.identifier]

    @pytest.mark.parametrize("spec", _specs(), ids=_ids())
    def test_it_ends_with_what_the_model_cannot_claim(
        self, spec: DossierSpec, committed: dict[str, str]
    ) -> None:
        """The last section is the boundary of the claim and never a conclusion.

        Order is the whole of it: a reader who stops early should stop having
        read the caveats, not having read a summary that omits them.
        """
        text = committed[spec.identifier]
        assert "## What this model cannot claim" in text
        tail = text.split("## What this model cannot claim", 1)[1]
        assert "\n## " not in tail, "a section was added after the limits; they go last"

    @pytest.mark.parametrize("spec", _specs(), ids=_ids())
    def test_every_declared_limit_carries_a_cost(
        self, spec: DossierSpec, committed: dict[str, str]
    ) -> None:
        """A caveat with no magnitude cannot be acted on, so an empty cost cell is a failure.

        `Limit.__post_init__` already refuses an empty string, so this is the
        same guarantee read from the rendered end: whatever a future renderer
        does, the column a person reads may not be blank.
        """
        tail = committed[spec.identifier].split("## What this model cannot claim", 1)[1]
        rows = [
            line
            for line in tail.splitlines()
            if line.startswith("| [") or line.startswith("| not a citation gap")
        ]
        assert rows, "the limits table has no rows"
        for row in rows:
            cells = [cell.strip() for cell in row.strip("|").split(" | ")]
            assert len(cells) == 4, row
            assert cells[2], f"a limit with no cost written: {row}"


class TestWhatTheDocumentsHaveToSay:
    """The three findings this round declared mandatory, asserted on the rendered text."""

    def test_ge1_prints_the_cliff_with_its_asymptotic_figure_on_the_same_line(
        self, committed: dict[str, str]
    ) -> None:
        """The one line of GE-1 that stops a link being dimensioned from an upper bound.

        A certified zero beside a positive asymptotic figure is the whole
        finding, and it is only a finding if the two are next to each other: a
        document that put them in different sections would be read by somebody
        who saw one of them.
        """
        section = committed["GE-1"].split("## 4. The cliff", 1)[1].split("## 5.", 1)[0]
        assert "certifies **0 bits**" in section
        assert "asymptotic calculation still claims" in section

    def test_ge1_says_the_band_is_not_an_error_bar(self, committed: dict[str, str]) -> None:
        """ADR 0017 §2's convention, in the document and not only in the ADR.

        The whole reason that ADR exists is that a shaded band reads as a
        confidence interval to everybody who was not told otherwise, and the
        reader of a dossier is exactly the person who was not told.
        """
        text = committed["GE-1"]
        assert "not an error bar" in text
        assert "not ordered the same way" in text

    def test_ge0b_carries_the_question_for_the_manufacturer_verbatim(
        self, committed: dict[str, str]
    ) -> None:
        """The line exists to be pasted into an email, so it has to survive rendering intact.

        Asserted against the constant and not a retyped copy: a question that
        drifts from the one this project can defend is worse than none, because
        a vendor will answer whichever one was asked.
        """
        assert ge0b.QUESTION_FOR_THE_MANUFACTURER in committed["GE-0b"]
        assert "Do not ask" in committed["GE-0b"]

    def test_reference_link_names_both_ntanos_claims_and_anchors_on_neither(
        self, committed: dict[str, str]
    ) -> None:
        """The section this round made mandatory.

        Two printed claims 4.07 dB apart, both in the validation table, neither
        used as an anchor. A document that named one of them would be
        presenting a contested figure as settled, and the reader has no way to
        know which.
        """
        section = committed["reference-link"].split("## 5. Which of the two", 1)[1]
        assert "§4.2.1" in section
        assert "§4.3.1" in section
        assert "4.07 dB apart" in section
        assert "neither is an anchor" in section.lower()
        assert "`ntanos2021.best-case-total-loss`" in section
        assert "`ntanos2021.single-pass-peak-skr`" in section

    def test_reference_link_reports_the_mask_optimum_with_its_regime(
        self, committed: dict[str, str]
    ) -> None:
        """A mask angle without its regime is not quotable, and the two disagree.

        The regime is not a tuning knob -- it says whether the weak theory
        applies at all -- so an optimum printed without it invites a reader to
        carry an angle from one air to another.
        """
        section = committed["reference-link"].split("## 3. The elevation mask", 1)[1]
        assert "`weak`" in section
        assert "`moderate-to-strong`" in section
        assert "sample and not a solve" in section

    def test_reference_link_warns_about_gap_21_where_the_altitude_term_is(
        self, committed: dict[str, str]
    ) -> None:
        """Gap 21 decides the *sign* of that column, so the warning belongs beside it.

        Putting it only in the closing table would leave the one reader who
        stops at section 4 -- the one deciding about a mountain site -- with an
        unqualified number whose sign is inside a declared hole.
        """
        section = (
            committed["reference-link"].split("## 4. The three stations", 1)[1].split("## 5.", 1)[0]
        )
        assert "gap 21" in section
        assert "449 308" in section


class TestTheGeneratorEvaluatesNoPhysics:
    """The one rule of `quoss.dossier`, asserted by reading its imports.

    Why a static check and not a convention
    ---------------------------------------
    Because the convention is one line away from being broken at any time and
    the break would be invisible. Calling
    `horizontal_aperture_averaging_factor` from a builder produces the right
    number today, reads as harmless in review, and quietly creates a figure in
    a document that no test of the physics covers -- which is the whole defect
    ADR 0028 names for the CLI, one layer further out where the reader has less
    defence.

    Writing `GE-1.md` needed three such figures and all three went **up**, into
    `HorizontalBudgetResults`. This test is what makes that the cheap path next
    time.
    """

    FORBIDDEN = ("quoss.channel", "quoss.qkd", "quoss.system", "quoss.orbits")

    def test_no_module_imports_a_physics_package(self, project_root: Path) -> None:
        package = project_root / "src" / "quoss" / "dossier"
        offenders: list[str] = []
        for path in sorted(package.glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                else:
                    continue
                for name in names:
                    if any(name == root or name.startswith(root + ".") for root in self.FORBIDDEN):
                        offenders.append(f"{path.name}:{node.lineno} imports {name}")
        assert not offenders, (
            "a dossier builder reached into the physics directly:\n  "
            + "\n  ".join(offenders)
            + "\nA figure a result does not carry goes UP into the result, not down into the "
            "report (quoss/dossier/base.py, 'The boundary')."
        )


class TestTheRegistry:
    def test_an_unregistered_scenario_is_an_error_that_lists_the_registered_ones(self) -> None:
        """No generic fallback, deliberately.

        An empty document under a confident title, generated for a scenario
        nobody wrote sections for, would carry whichever figures the generic
        path could reach and be silent about everything it could not. The error
        is the better outcome, and it is only better if it says what *is*
        available.
        """
        scenario = reference_castelldefels().model_copy(update={"name": "not_a_dossier"})
        with pytest.raises(ScenarioError, match="no dossier is registered"):
            dossier_for(scenario)

    def test_every_registered_document_lives_under_the_experiments_directory(self) -> None:
        for spec in dossiers():
            assert spec.document_path.startswith("docs/experiments/")
            assert spec.document_path.endswith(".md")

    def test_the_identifiers_are_distinct(self) -> None:
        identifiers = [spec.identifier for spec in dossiers()]
        assert len(set(identifiers)) == len(identifiers)
