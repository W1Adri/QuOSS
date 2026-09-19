"""The reading path stays readable, asserted rather than remembered.

``CLAUDE.md`` tells every session to read ``notes/LAST_CHANGES.md`` before
touching anything. That file reached **6 834 lines**, and a log that does not
fit in the session that has to read it is not a log, it is an archive: what
actually happens is that the first screens get read and the entries describing
today's tree do not. ``LAST_CHANGES.md`` §41 has the measurement and the
archiving rule; this module is the part that fails when the rule is broken.

**What is asserted, and why no total line count.** Five long entries can weigh
more than six short ones, so a total cannot tell "the rule was broken" from
"this month's entries are long": every candidate number is either unreachable or
incapable of failing, and a bound that cannot fail does not test anything. What
gets asserted is the rule — at most five entries, an index covering every
archived one exactly once, no entry in both places, contiguous numbering — plus
two *derived* line bounds that between them imply a total: one on the header,
which is the part that actually crept (352 lines of stacked "previous entry"
summaries, 5.2 % of the file), and one on a single entry, taken from the longest
entry the project has ever written.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

NOTES = Path(__file__).resolve().parents[2] / "notes"
LOG = NOTES / "LAST_CHANGES.md"
ARCHIVE = NOTES / "archive"

#: The log keeps the five most recent entries; everything older is archived.
#: Five is the rule, not a measurement: it is how many entries a session can
#: read before it starts skipping, and it is what §41 committed to.
MAX_LIVE_ENTRIES = 5

#: Header plus index, derived rather than chosen. The index costs one row per
#: archived entry and the header is prose that should not grow with them, so the
#: bound is an intercept plus a per-entry slope. Two lines per entry is twice
#: what a row needs, which leaves room for a row to wrap without failing over
#: formatting. Measured when written: 66 against a bound of 132.
HEADER_BASE_LINES = 60
HEADER_LINES_PER_ARCHIVED_ENTRY = 2

#: The longest entry ever written is §29 at 307 lines, over 41 entries. 320 is
#: that with 4 % of headroom: it passes for every entry the project has actually
#: produced and fires on anything longer than any of them.
#:
#: This is what a total line count cannot be. A total cannot tell "the rule was
#: broken" from "this month's entries are long", so any total bound is either
#: unreachable (900, which §41 measured: four entries alone are 847) or so loose
#: it never fires -- and a bound that cannot fail does not test anything, which
#: is the tolerance rule of CLAUDE.md. Bounding the header and each entry
#: separately bounds the total by construction, at 132 + 5 x 320 = 1 732, and
#: that number is a consequence rather than a choice.
LONGEST_ENTRY_LINES = 320

ENTRY_RE = re.compile(r"^## (\d+)\. ", re.MULTILINE)


def _log_text() -> str:
    return LOG.read_text(encoding="utf-8")


def _entries(text: str) -> list[int]:
    return [int(m.group(1)) for m in ENTRY_RE.finditer(text)]


def _archived() -> dict[int, Path]:
    out: dict[int, Path] = {}
    for path in sorted(ARCHIVE.glob("LAST_CHANGES-*.md")):
        for number in _entries(path.read_text(encoding="utf-8")):
            assert number not in out, f"§{number} appears in two archive files"
            out[number] = path
    return out


def _index_rows(text: str) -> dict[int, str]:
    """Index rows, and only those: the scan stops at the first entry.

    An entry body may contain a table whose first column is also ``| §37 |`` --
    §41 has one, comparing the length of each kept entry -- and counting those
    as index rows makes a live entry look archived. Scoping the scan to the
    header is what the index *is*: the part of the file before the entries.
    """
    first = ENTRY_RE.search(text)
    header = text[: first.start()] if first else text
    rows: dict[int, str] = {}
    for line in header.split("\n"):
        m = re.match(r"^\| §(\d+) \|", line)
        if m:
            rows[int(m.group(1))] = line
    return rows


def test_the_log_holds_at_most_five_entries() -> None:
    live = _entries(_log_text())
    assert len(live) <= MAX_LIVE_ENTRIES, (
        f"notes/LAST_CHANGES.md holds {len(live)} entries ({live}); the rule is "
        f"at most {MAX_LIVE_ENTRIES}. Move the oldest to notes/archive/ and add "
        f"its row to the index -- but first check that everything load-bearing "
        f"in it lives in an ADR, a test or a docstring (LAST_CHANGES.md §41)."
    )


def test_the_index_covers_every_archived_entry() -> None:
    text = _log_text()
    archived = set(_archived())
    indexed = set(_index_rows(text))
    assert archived, "no archived entries found under notes/archive/"
    missing = sorted(archived - indexed)
    assert not missing, (
        f"archived but not in the index of notes/LAST_CHANGES.md: "
        f"{[f'§{n}' for n in missing]}. An archived entry with no index row is "
        f"an entry nobody will find again."
    )
    stray = sorted(indexed - archived)
    assert not stray, f"indexed but not archived anywhere: {[f'§{n}' for n in stray]}"


def test_no_entry_lives_in_both_places() -> None:
    live = set(_entries(_log_text()))
    both = sorted(live & set(_archived()))
    assert not both, (
        f"{[f'§{n}' for n in both]} are in notes/LAST_CHANGES.md *and* in "
        f"notes/archive/. Two copies of an entry is how they start to differ."
    )


def test_the_numbering_has_no_holes() -> None:
    """Archived plus live must be 1..N with nothing missing and nothing twice."""
    numbers = sorted(set(_archived()) | set(_entries(_log_text())))
    assert numbers == list(range(1, len(numbers) + 1)), (
        f"entry numbers are not contiguous from 1: {numbers}. A hole means an "
        f"entry was deleted rather than archived."
    )


def test_every_archive_link_in_the_index_resolves() -> None:
    text = _log_text()
    broken = []
    for number, row in sorted(_index_rows(text).items()):
        for target in re.findall(r"\]\((archive/[^)]+)\)", row):
            if not (NOTES / target).exists():
                broken.append(f"§{number} -> {target}")
    assert not broken, f"index rows pointing at files that do not exist: {broken}"


def test_the_header_does_not_grow_with_the_archive() -> None:
    """The failure that actually happened, and the one a total count misses."""
    text = _log_text()
    first = ENTRY_RE.search(text)
    assert first is not None, "notes/LAST_CHANGES.md has no entries at all"
    header_lines = text[: first.start()].count("\n")
    bound = HEADER_BASE_LINES + HEADER_LINES_PER_ARCHIVED_ENTRY * len(_archived())
    assert header_lines <= bound, (
        f"the header and index of notes/LAST_CHANGES.md are {header_lines} lines "
        f"against a bound of {bound}. This is the shape the old file failed in: "
        f"a header that grew to 352 lines by stacking a summary of every entry "
        f"on top of the entry itself."
    )


def test_no_single_entry_outgrows_every_entry_ever_written() -> None:
    """The other half of the total: the header is bounded, so entries must be.

    Together with ``test_the_log_holds_at_most_five_entries`` and
    ``test_the_header_does_not_grow_with_the_archive`` this bounds the file
    without ever asserting a total, which is the only bound that would be both
    reachable and capable of failing.
    """
    text = _log_text()
    marks = [(int(m.group(1)), m.start()) for m in ENTRY_RE.finditer(text)]
    over = []
    for k, (number, start) in enumerate(marks):
        end = marks[k + 1][1] if k + 1 < len(marks) else len(text)
        length = text[start:end].count("\n")
        if length > LONGEST_ENTRY_LINES:
            over.append(f"§{number} ({length} lines)")
    assert not over, (
        f"{over} exceed {LONGEST_ENTRY_LINES} lines, which is longer than any of "
        f"the 41 entries written so far (§29, 307). An entry that long is not a "
        f"log entry -- split it, or move the standing part into the ADR that "
        f"owns it."
    )


@pytest.mark.parametrize("name", ["ROADMAP.md", "INCONSISTENCIAS.md", "GUIA_REIMPLEMENTACION.md"])
def test_the_other_notes_stay_readable(name: str) -> None:
    """ROADMAP.md reached 935 lines by holding justification that its own ADRs held.

    The bound is 500: the file is a status table per stage, and eleven stages at
    the current density (321 lines) leave room to grow by half before the same
    failure -- prose creeping back in next to a link to the ADR that owns it.
    """
    lines = (NOTES / name).read_text(encoding="utf-8").count("\n") + 1
    assert lines <= 500, (
        f"notes/{name} is {lines} lines. These files are state and decisions; "
        f"the justification belongs in the ADR that owns it (notes/ROADMAP.md, "
        f"header). If it has no ADR owner, that is a finding, not a reason to "
        f"write it here."
    )


# --------------------------------------------------------------------------- #
# Citations to a section of the guide resolve to a section that exists
# --------------------------------------------------------------------------- #
#: The guide's file name, without the extension. Kept as a variable and never
#: written next to a section sign in this module, because this module is inside
#: the tree the scan below walks: a literal example of a broken citation, written
#: to illustrate the failure, would *be* one and would fail its own test.
GUIDE_STEM = "GUIA_REIMPLEMENTACION"

#: Where a citation may live. ``notes/`` is out on purpose and not by oversight:
#: it is where the renumbering is *described* -- "§41 renumbered the document,
#: the v3 had §0-§5" -- and prose about which sections used to exist is not a
#: citation of them.
CITING_ROOTS = ("src", "tests", "docs")

#: Single files outside those roots that cite the guide too. Named one by one
#: rather than scanning the repository root, so that adding a file does not
#: silently widen the scan to somebody's scratch notes.
CITING_FILES = ("pyproject.toml", "CLAUDE.md", "README.md")

CITING_SUFFIXES = (".py", ".md", ".toml", ".yaml", ".yml")

#: ``…GUIA_REIMPLEMENTACION.md`` or ``…-v3.md``, then up to forty characters of
#: punctuation and closing markup, then ``§`` and a number. Forty is what fits a
#: closing double backtick, a Markdown link target and a comma; past that the
#: section sign belongs to the next sentence and is not part of the citation.
CITATION_RE = re.compile(GUIDE_STEM + r"(-v3)?\.md[^\n§]{0,40}§\s*(\d+(?:\.\d+)?)")

#: A Markdown heading numbered ``N`` or ``N.M``, and the one heading that covers
#: two numbers at once -- ``## 2 y 3 — se fueron a docs/adr/`` in the trimmed
#: guide, which is a real section for citation purposes even though what it says
#: is "this moved".
HEADING_RE = re.compile(r"^#+\s*(\d+(?:\.\d+)?)(?:\s+y\s+(\d+))?[.\s]", re.MULTILINE)


def _guide_sections(path: Path) -> set[str]:
    """Return every section number the guide at ``path`` has a heading for."""
    found: set[str] = set()
    for match in HEADING_RE.finditer(path.read_text(encoding="utf-8")):
        found.add(match.group(1))
        if match.group(2) is not None:
            found.add(match.group(2))
    return found


def _citing_files(root: Path) -> list[Path]:
    files = [
        path
        for directory in CITING_ROOTS
        for path in (root / directory).rglob("*")
        if path.is_file() and path.suffix in CITING_SUFFIXES
    ]
    files.extend(root / name for name in CITING_FILES)
    return sorted(set(files))


def _citations(root: Path) -> list[tuple[Path, int, str, str]]:
    """Return ``(path, line, target_file_name, section)`` for every numbered citation."""
    out: list[tuple[Path, int, str, str]] = []
    for path in _citing_files(root):
        text = path.read_text(encoding="utf-8")
        for match in CITATION_RE.finditer(text):
            name = f"{GUIDE_STEM}-v3.md" if match.group(1) else f"{GUIDE_STEM}.md"
            out.append((path, text[: match.start()].count("\n") + 1, name, match.group(2)))
    return out


def test_every_guide_section_cited_from_the_code_exists() -> None:
    """A citation to a section the cited file does not have, from src/, tests/ or docs/.

    The failure this exists for is not the loud one. ``§5`` in a docstring when
    the file stops at ``§3`` merely sends the reader nowhere, and they will
    notice. What happened on 2026-09-19 (LAST_CHANGES §41, §42, INCONSISTENCIAS
    #17) is the quiet one: trimming the guide renumbered it, ``viz/__init__.py``
    kept citing ``§1`` for "one formula, one place", and ``§1`` still existed --
    as "what SimulCTTC was". The citation resolved, to the wrong text, with
    nothing anywhere saying so. That is the same family as a plausible wrong
    number, and it is why this is an assertion and not a convention.

    Eleven of fourteen numbered citations did not resolve and one resolved
    wrongly; the fix moved each to ``archive/`` or to the ADR that owns the
    decision today. Without this test, the next trim breaks them again.
    """
    root = NOTES.parent
    guides = {
        f"{GUIDE_STEM}.md": NOTES / f"{GUIDE_STEM}.md",
        f"{GUIDE_STEM}-v3.md": ARCHIVE / f"{GUIDE_STEM}-v3.md",
    }
    sections = {name: _guide_sections(path) for name, path in guides.items()}
    for name, found in sections.items():
        assert found, f"no numbered headings found in notes/.../{name}; the scan is broken"

    citations = _citations(root)
    assert citations, "no numbered citations of the guide found at all; the scan is broken"

    broken = [
        f"{path.relative_to(root)}:{line} cites {name} §{section}"
        for path, line, name, section in citations
        if section not in sections[name]
    ]
    present = {name: sorted(found) for name, found in sections.items()}
    assert not broken, (
        f"citations pointing at a section that does not exist: {broken}. The sections that "
        f"do exist are {present}. Point the citation at "
        f"notes/archive/{GUIDE_STEM}-v3.md, where the old numbering is frozen, or at the ADR "
        f"that owns the decision today."
    )
