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

import ast
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


# --------------------------------------------------------------------------- #
# Citations to a file in the tree resolve to a file that is in the tree
# --------------------------------------------------------------------------- #
#: Directories a path citation may start from. Two families, and the split is
#: the project's own habit rather than a rule invented here:
#:
#: * repository roots -- ``docs/adr/0018-….md``, ``scenarios/ge1_1km.yaml``;
#: * package-relative module paths -- ``channel/atmosphere.py``, ``cli/run.py``,
#:   which every ADR and docstring writes without the ``src/quoss/`` prefix.
#:
#: A citation is resolved against the repository root, against ``src/`` and
#: against ``src/quoss``, and only counts as broken when none of the three
#: exists. Three anchors because the tree really does use three spellings --
#: ``docs/adr/0018-….md``, ``quoss/data/ogs.yaml``, ``channel/atmosphere.py`` --
#: and insisting on one would fail 140 citations that are perfectly readable.
CITED_ROOTS = (
    # repository roots
    "src",
    "tests",
    "docs",
    "notes",
    "scenarios",
    "data",
    # These four were directories of this repository until 2026-09-19, when the
    # four `.gitkeep`s that were all they held were deleted: a directory that
    # promises a stage is a promise nobody can check. They stay in this list on
    # purpose, and the purpose is the opposite of the one they had. Before, they
    # let a citation of a file under one of them resolve; now they make one
    # **fail**, because the scan below asserts that every path it matches
    # exists. Taking them out would make such a citation invisible instead --
    # and this comment is the demonstration: naming an example file here was
    # itself caught by the test on the first run.
    "benchmarks",
    "deploy",
    "validation",
    "web",
    # src-relative
    "quoss",
    # package-relative
    "core",
    "orbits",
    "channel",
    "qkd",
    "system",
    "scenario",
    "engine",
    "io",
    "cli",
    "viz",
    "kernels",
    "api",
)

#: Extensions a citation may end in. Restricting to a list rather than accepting
#: ``\.\w+`` is not tidiness, it is what keeps the scan from reading Python
#: attribute access as a file: ``core/types.TimeGrid`` and
#: ``scenario/io.format_for_path`` are dotted names, not files, and an open
#: extension matches both.
CITED_SUFFIXES = ("py", "md", "toml", "yaml", "yml", "json", "csv", "npz", "lock", "txt")

#: A path, not preceded by a character that would make it the tail of a longer
#: one. The lookbehind is what stops ``<venv>/lib/python3.13/data/ogs.yaml`` --
#: prose about where an *installed* tree resolves a path to -- from being read
#: as a citation of ``data/ogs.yaml`` in this tree.
PATH_CITATION_RE = re.compile(
    r"(?<![\w/<.-])((?:" + "|".join(CITED_ROOTS) + r")/[\w./-]*\."
    r"(?:" + "|".join(CITED_SUFFIXES) + r"))(?![\w.])"
)

#: Where a path citation may live. Same three roots as the guide scan above,
#: plus ``notes/ROADMAP.md`` -- which is state, not history, so a dead path in
#: it is a defect -- and the same three root files.
#:
#: ``LAST_CHANGES.md``, ``INCONSISTENCIAS.md`` and ``archive/`` are out, and not
#: by oversight: they are a record of what was true on a date. §42 saying the
#: wheel did not carry ``data/ogs.yaml`` is a true sentence about 2026-09-19,
#: and rewriting it when the file moves would be falsifying the log.
PATH_CITING_ROOTS = ("src", "tests", "docs")
PATH_CITING_FILES = ("pyproject.toml", "CLAUDE.md", "README.md", "notes/ROADMAP.md")

#: Paths cited by name that deliberately do **not** exist, each with its reason.
#: Every one of them is asserted *absent* as well, so the day one gets written
#: this list fails and has to shrink: an allowlist that can only grow is the
#: kind of exception that outlives its reason.
PATHS_DECLARED_ABSENT = {
    # ADR 0027 names the four levels of distribution and says, in the same
    # bullet, "de los cuales **ninguno existe todavía**". Stages 9-11.
    "api/app.py": "stage 9, ADR 0027 declares it absent in the same sentence",
    "cli/serve.py": "stage 9, ADR 0027 declares it absent in the same sentence",
    "deploy/compose.yaml": "stage 11, ADR 0027 declares it absent in the same sentence",
    # ADR 0026 governs stage 2.4, which the roadmap marks as not justified by
    # any measurement of today. An ADR records a decision, not an implementation.
    "kernels/base.py": "stage 2.4, ADR 0026 governs a stage that is not written",
    "kernels/numpy_backend.py": "stage 2.4, ADR 0026 governs a stage that is not written",
    "kernels/numba_backend.py": "stage 2.4, ADR 0026 governs a stage that is not written",
    # A placeholder inside the doctest of ValidationCase, showing what the
    # `test` field looks like. Pointing it at a real node would be worse: the
    # case in that example is invented, so a real node would claim to reproduce
    # something it has never seen.
    "tests/x.py": "placeholder in the ValidationCase doctest, deliberately not a node",
}


def _path_citing_files(root: Path) -> list[Path]:
    files = [
        path
        for directory in PATH_CITING_ROOTS
        for path in (root / directory).rglob("*")
        if path.is_file() and path.suffix in CITING_SUFFIXES
    ]
    files.extend(root / name for name in PATH_CITING_FILES)
    return sorted(set(files))


def _path_citations(root: Path) -> list[tuple[Path, int, str]]:
    """Return ``(citing file, line, cited path)`` for every path citation found."""
    out: list[tuple[Path, int, str]] = []
    for path in _path_citing_files(root):
        text = path.read_text(encoding="utf-8")
        for match in PATH_CITATION_RE.finditer(text):
            cited = match.group(1)
            if "..." in cited:  # an elision in prose, not a path
                continue
            out.append((path, text[: match.start()].count("\n") + 1, cited))
    return out


def test_every_path_cited_from_the_code_exists() -> None:
    """A citation of a file in this tree resolves to a file that is in this tree.

    The sibling test above covers a citation of a *section*. This one covers a
    citation of a *file*, and it exists because the failure has already
    happened twice in this project by the same mechanism: something moved, and
    the citations kept pointing at where it used to be. §42 trimmed the guide
    and broke fourteen section citations (INCONSISTENCIAS #17); the stage that
    added this test moved ``data/`` into the package and had **fifteen** path
    citations to carry with it.

    What it does not cover, said out loud. Only paths ending in a known
    extension are checked, so a citation of a *directory* -- ``data/snapshots/``
    -- is invisible to it. That is not laziness: in prose a slash-terminated
    name is indistinguishable from a slash-separated list, and the tree has a
    real example, ``core ← orbits/channel/qkd ← system`` in ``README.md:205``,
    which any directory-shaped rule reads as a citation of
    ``src/quoss/orbits/channel/``. A scan that fires on that sentence would be
    turned off within a week, and a test that gets turned off protects nothing.

    Measured when written: **186 distinct paths cited**, seven of them absent
    and all seven in :data:`PATHS_DECLARED_ABSENT`. Checked by breaking one by
    hand -- renaming ``scenarios/ge1_1km.yaml`` to ``ge1_1km.yml`` made the test
    fail naming **26** citing lines, and restoring it made it pass again.
    """
    root = NOTES.parent
    anchors = (root, root / "src", root / "src" / "quoss")

    citations = _path_citations(root)
    assert citations, "no path citations found at all; the scan is broken"

    broken = sorted(
        f"{path.relative_to(root)}:{line} cites {cited}"
        for path, line, cited in citations
        if cited not in PATHS_DECLARED_ABSENT
        and not any((anchor / cited).exists() for anchor in anchors)
    )
    assert not broken, (
        f"citations pointing at a file that is not in the tree: {broken}. Either the "
        f"file moved and the citation did not, or the citation names something that was "
        f"never written -- in which case it belongs in PATHS_DECLARED_ABSENT with its "
        f"reason, not in an exception nobody can date."
    )


@pytest.mark.parametrize("cited", sorted(PATHS_DECLARED_ABSENT))
def test_a_path_declared_absent_is_still_absent(cited: str) -> None:
    """The allowlist above shrinks by itself when the file it excuses gets written."""
    root = NOTES.parent
    anchors = (root, root / "src", root / "src" / "quoss")
    assert not any((anchor / cited).exists() for anchor in anchors), (
        f"{cited} is listed in PATHS_DECLARED_ABSENT ({PATHS_DECLARED_ABSENT[cited]}) and now "
        f"exists. Remove the entry: the citations of it are no longer excused, they are correct."
    )


# --------------------------------------------------------------------------- #
# Citations of a pytest node resolve to a node that is defined
# --------------------------------------------------------------------------- #
#: A test file, then one or more ``::``-separated identifiers. No literal
#: example is written anywhere in this module, for the reason given above
#: :data:`GUIDE_STEM`: this file is inside the tree the scan walks, so an
#: illustrative broken citation would *be* one and would fail its own test.
#: The path part is matched loosely and resolved below; the segments are
#: plain identifiers, because a parametrised
#: ``[...]`` suffix names an argument set and not a definition, and checking it
#: would fail on every ``ids=`` change without a defect behind it.
NODE_CITATION_RE = re.compile(r"(?<![\w/<.-])([\w./-]+\.py)((?:::\w+)+)")

#: A node id written across two lines, which prose does constantly:
#: the file name and a trailing ``::`` at a line end, the class on the next.
#: Seven in the
#: tree when this was written. Joining them costs a few lines here and is the
#: difference between checking 132 citations and checking 125.
WRAPPED_NODE_RE = re.compile(r"::[ \t]*\n[ \t>*`]*")

#: Nodes cited by name that deliberately do not exist, same rule as
#: :data:`PATHS_DECLARED_ABSENT`: a reason each, and a test that they stay
#: absent so the list cannot quietly outlive it.
NODES_DECLARED_ABSENT = {
    "tests/x.py::TestX::test_x": "placeholder in the ValidationCase doctest",
    "tests/validation/test_base.py::TestSomething::test_something": (
        "placeholder in the fixture dict of tests/validation/cases.py, which is the "
        "example case the table's own tests are built from"
    ),
}


def _join_wrapped_nodes(text: str) -> tuple[str, list[int]]:
    """Return the text with wrapped node ids joined, and a map back to offsets.

    The offset map is what keeps the failure message useful: a line number
    computed on the joined text points at the wrong line of the real file, and
    a citation test whose message sends the reader to the wrong line has
    replaced one wild goose chase with another.
    """
    joined: list[str] = []
    offsets: list[int] = []
    pos = 0
    for match in WRAPPED_NODE_RE.finditer(text):
        joined.append(text[pos : match.start()])
        offsets.extend(range(pos, match.start()))
        joined.append("::")
        offsets.extend((match.start(), match.start() + 1))
        pos = match.end()
    joined.append(text[pos:])
    offsets.extend(range(pos, len(text)))
    return "".join(joined), offsets


def _resolve_test_file(root: Path, cited: str) -> list[Path]:
    """Return the files a cited path could mean, most specific first."""
    for anchor in (root, root / "src", root / "src" / "quoss"):
        candidate = anchor / cited
        if candidate.is_file():
            return [candidate]
    if "/" not in cited:
        # The tree cites bare file names, with no directory in front, and they
        # are unambiguous in practice because test modules are uniquely named.
        # When they are not, every match is tried and one hit is enough.
        return sorted((root / "tests").rglob(cited))
    return []


def _defines(path: Path, segments: list[str]) -> bool:
    """Report whether ``path`` defines the nested chain ``segments``.

    Resolved by parsing the file rather than by asking pytest to collect it.
    Two reasons, and the second is the one that matters: pytest inside pytest
    is a plugin-state problem nobody wants, and collection only sees *tests*,
    while the tree legitimately cites things that are not tests --
    ``tests/channel/test_horizontal.py::ge1_key`` is a fixture, and a
    collection-based check would call that citation broken.
    """
    try:
        tree: ast.AST = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:  # pragma: no cover - the suite would not import either
        return False
    node: ast.AST = tree
    for segment in segments:
        body = getattr(node, "body", [])
        found = next(
            (
                child
                for child in body
                if isinstance(child, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
                and child.name == segment
            ),
            None,
        )
        if found is None:
            return False
        node = found
    return True


def _node_citations(root: Path) -> list[tuple[Path, int, str, list[str]]]:
    out: list[tuple[Path, int, str, list[str]]] = []
    for path in _path_citing_files(root):
        raw = path.read_text(encoding="utf-8")
        text, offsets = _join_wrapped_nodes(raw)
        for match in NODE_CITATION_RE.finditer(text):
            segments = [part for part in match.group(2).split("::") if part]
            line = raw[: offsets[match.start()]].count("\n") + 1
            out.append((path, line, match.group(1), segments))
    return out


def test_every_pytest_node_cited_from_the_code_exists() -> None:
    """A citation naming a file, a class and a test resolves to something defined.

    The third and last of the citation tests, and the one §44 left named. Its
    two siblings check that a cited *section* and a cited *file* exist; nothing
    checked that a cited **node** exists, so a citation could name a real file
    and a test that had been renamed out of it, and read as perfectly specific
    while pointing at nothing.

    Two of those were fixed by hand during stage 8 without an inconsistency
    being opened, which was fine because they ended up fixed -- but the class
    is the same one as #17, and the remedy that worked there is a test. It
    found **eleven** more on 2026-09-19, of four different kinds, and none of
    them was noisy:

    * four cited a method without its class, so they resolved to a file and
      then to nothing -- ``test_the_published_answer_satisfies_keplers_equation``
      is a method of ``TestPublishedVallado21`` and was cited bare;
    * three named a class that had been renamed (``TestTheMaskSweep`` for
      ``TestTheMaskSweepInBothRegimes``, ``TestTheTwoFieldsWithoutADefault``
      for ``TestTheFieldsWithoutADefault``, ``TestTheStationSpecConversions``
      for ``TestUnitsConvertOnceAtTheBoundary``);
    * one used node syntax for a module constant -- ``REFERENCE_DAY_NUMBER`` of
      ``tests/system/reference.py``, which is not a node at all;
    * and one, the worst, named a test that **had never been written**:
      ``engine/horizontal.py`` justified dropping a scratch degradation log
      with "That is asserted, not assumed, by
      tests/engine/test_horizontal.py::TestNothingIsDroppedWithTheScratchLog",
      and the class did not exist. A comment claiming an assertion that is not
      there is worse than one claiming nothing, because it stops the next
      reader from checking. That one was closed by writing the test.

    Checked by breaking one by hand, the same way the fourteen were: renaming
    ``TestTheMaskSweepInBothRegimes`` makes this fail naming the citation in
    ``engine/sweep.py``.
    """
    root = NOTES.parent
    citations = _node_citations(root)
    assert citations, "no node citations found at all; the scan is broken"

    broken: list[str] = []
    for path, line, cited, segments in citations:
        node_id = cited + "::" + "::".join(segments)
        if node_id in NODES_DECLARED_ABSENT:
            continue
        candidates = _resolve_test_file(root, cited)
        if not candidates:
            broken.append(f"{path.relative_to(root)}:{line} cites {node_id} (no such file)")
        elif not any(_defines(candidate, segments) for candidate in candidates):
            where = ", ".join(str(c.relative_to(root)) for c in candidates)
            broken.append(f"{path.relative_to(root)}:{line} cites {node_id} (not in {where})")

    assert not broken, (
        f"citations naming a pytest node that is not defined: {sorted(broken)}. A renamed "
        f"class, a method cited without its class, or a test that was never written -- the "
        f"last is the one worth looking at twice, because the sentence around it usually "
        f"claims the code is asserted."
    )


@pytest.mark.parametrize("node_id", sorted(NODES_DECLARED_ABSENT))
def test_a_node_declared_absent_is_still_absent(node_id: str) -> None:
    """Same self-emptying rule as the path allowlist."""
    root = NOTES.parent
    cited, _, rest = node_id.partition("::")
    segments = rest.split("::")
    assert not any(_defines(c, segments) for c in _resolve_test_file(root, cited)), (
        f"{node_id} is listed in NODES_DECLARED_ABSENT "
        f"({NODES_DECLARED_ABSENT[node_id]}) and now exists. Remove the entry."
    )


# --------------------------------------------------------------------------- #
# The door's inventory claims match the tree they describe
# --------------------------------------------------------------------------- #
# Three rounds of auditing README.md, CLAUDE.md and notes/ROADMAP.md found the
# same class of defect by a different route each time, and each round closed its
# route with one of the scans above: a citation to a section of the guide, a
# citation to a path, a citation to a pytest node. The fourth round found the
# route those three cannot see, because it is not a citation at all.
#
# **It is a count.** "29 ADRs", "35 casos de ocho fuentes", "siete escenarios",
# "veintitrés huecos declarados", "dos entradas abiertas" -- sentences that name
# a number of things the repository contains. On 2026-09-19 four of them were
# wrong: CLAUDE.md said INCONSISTENCIAS.md had two open entries when the file
# said one, said fifteen had ever been recorded when nineteen had, and gave the
# line counts of LAST_CHANGES.md and ROADMAP.md as 910 and 321 against 1 068 and
# 401. None of the three scans above can see any of that: there is no identifier
# to resolve. `29` resolves to nothing; it is either the number of files in
# docs/adr/ or it is a lie, and telling those apart means counting the files.
#
# Why this is a fourth check and not the three generalised
# --------------------------------------------------------
# The three above share one operation -- take the identifier a citation names,
# and look it up. That makes them **total**: a regex finds every citation of the
# shape, so a new one written tomorrow is checked the day it is written, and
# nobody has to register it.
#
# A count has no identifier to look up, so it cannot share that operation. What
# it needs instead is a *recipe*: some code that recounts the thing from the
# tree, and only a person can write "this sentence is about the files in
# docs/adr/". So the registry below is unavoidable, and with it the weakness a
# registry always has -- a claim counting something nobody registered is
# invisible.
#
# That weakness is bounded the same way `CITED_ROOTS` bounds the path scan: the
# check is total over a **vocabulary**. It does not look for the claims it knows
# about; it scans for every sentence matching "<number> <counted noun>" over the
# nouns in COUNTED_NOUNS, and fails on a match no recipe covers. Adding a
# fifteenth sentence about ADRs to the README is caught with no edit here;
# inventing a new kind of countable thing is not, and that residue is the honest
# cost of the shape.
#
# What it cannot cover, and why that is not a hole to plug
# ---------------------------------------------------------
# **The test count.** "3 968 tests" is an inventory claim like the others, and
# this check will not touch it: counting the suite from inside the suite is
# self-referential -- collecting changes the number by the count of the tests
# doing the collecting, and adding a test to this module would change the number
# the module asserts. The README states it with the date it was measured on for
# that reason, which is what the project does everywhere a number cannot be
# reproduced by a test (CLAUDE.md, norm 1, "medido en este repo").
#
# **The physics.** "433 442 bits", "11.637 dB", "0.230 dB cenitales" are not in
# this registry either, and they do not need to be: every one of them is
# asserted by the test that measures it, and the README cites that test. The
# door's physics was never the unasserted part. Its arithmetic about itself was.

#: Small numbers written as words, which is how this project writes them in
#: prose. Not a general Spanish numeral parser: only the spellings the three
#: door files actually use, so an unrecognised word fails loudly at the sentence
#: rather than silently matching nothing.
_WORD_NUMBERS = {
    "cero": 0,
    "un": 1,
    "una": 1,
    "uno": 1,
    "dos": 2,
    "tres": 3,
    "cuatro": 4,
    "cinco": 5,
    "seis": 6,
    "siete": 7,
    "ocho": 8,
    "nueve": 9,
    "diez": 10,
    "once": 11,
    "doce": 12,
    "trece": 13,
    "catorce": 14,
    "quince": 15,
    "dieciséis": 16,
    "diecisiete": 17,
    "dieciocho": 18,
    "diecinueve": 19,
    "veinte": 20,
    "veintitrés": 23,
    "veintinueve": 29,
    "treinta": 30,
    "treinta y cinco": 35,
}

#: The files that are the project's front door: the three a reader meets before
#: any code. ``notes/LAST_CHANGES.md`` and ``notes/INCONSISTENCIAS.md`` are out
#: for the reason ``PATH_CITING_ROOTS`` leaves them out -- they record what was
#: true on a date, and "22 casos de tres fuentes" in §44 is a true sentence
#: about 2026-09-19 that this check would turn into a lie.
DOOR_FILES = ("README.md", "CLAUDE.md", "notes/ROADMAP.md")


def _adr_count(root: Path) -> int:
    """Count the ADRs written: one file per decision, numbered and never renumbered."""
    return len(list((root / "docs" / "adr").glob("[0-9][0-9][0-9][0-9]-*.md")))


def _scenario_counts(root: Path) -> dict[str, int]:
    """Versioned scenarios, split by the ``link`` tag that discriminates the union."""
    files = sorted((root / "scenarios").glob("*.yaml"))
    horizontal = [p for p in files if re.search(r"^link:[ \t]*horizontal\b", p.read_text(), re.M)]
    return {
        "escenarios": len(files),
        "escenarios de bajada": len(files) - len(horizontal),
        "escenarios de tierra": len(horizontal),
    }


def _validation_counts(root: Path) -> dict[str, int]:
    """Recompute the validation table rather than read the committed one.

    Reading ``docs/validation.md`` would make this check agree with a stale
    file; the file is what the door is quoting. ``run_all()`` is what the file
    is quoting, so that is what gets counted.
    """
    from quoss.validation.base import ValidationStatus as Status
    from quoss.validation.base import run_all

    cases = run_all()
    return {
        "casos": len(cases),
        "fuentes": len({case.source for case in cases}),
        "reproducidos": sum(1 for c in cases if c.status is Status.REPRODUCED),
        "compatibles": sum(1 for c in cases if c.status is Status.COMPATIBLE),
        "no reproducidos": sum(1 for c in cases if c.status is Status.NOT_REPRODUCED),
        "huecos de fuente": sum(1 for c in cases if c.status is Status.GAP),
        "huecos de cita": _declared_gap_count(root),
    }


def _declared_gap_count(root: Path) -> int:
    """Count the numbered entries of ADR 0009 §"Los huecos, declarados"."""
    text = (root / "docs" / "adr" / "0009-citation-policy.md").read_text(encoding="utf-8")
    start = text.index("### Los huecos, declarados")
    end = text.index("### El caveat de Ntanos", start)
    return len(re.findall(r"^ *(\d+)\. \*\*", text[start:end], re.M))


def _inconsistency_counts(root: Path) -> dict[str, int]:
    """Open entries, and every entry the file has ever carried.

    Both are counted from the table rows rather than from the file's own
    "Estado: **una abierta**" heading, because that heading is prose and is
    exactly the kind of sentence this check exists to catch.
    """
    text = (root / "notes" / "INCONSISTENCIAS.md").read_text(encoding="utf-8")
    start = text.index("## Estado")
    return {
        "entradas abiertas": len(
            re.findall(r"^\| (C?\d+) \|", text[start : text.index("\n---", start)], re.M)
        ),
        "inconsistencias registradas": len(set(re.findall(r"^\| (C?\d+) \|", text, re.M))),
    }


def _inventory(root: Path) -> dict[str, int]:
    """Every registered quantity, recounted from the tree."""
    counts: dict[str, int] = {"ADRs": _adr_count(root)}
    counts.update(_scenario_counts(root))
    counts.update(_validation_counts(root))
    counts.update(_inconsistency_counts(root))
    return counts


#: The vocabulary the scan is total over, as ``(pattern, quantity)``. The
#: pattern is what appears in the prose; the quantity is the key ``_inventory``
#: recounts. Longest first, so that ``no reproducidos`` wins over
#: ``reproducidos`` and ``escenarios de bajada`` over ``escenarios``: the scan
#: takes the first alternative that matches, and a shorter noun nested in a
#: longer one would otherwise check the wrong quantity with a right-looking
#: number.
#:
#: ``casos`` carries a lookahead because the bare word is ordinary Spanish --
#: "en los dos casos" is a sentence about two situations, not about the
#: validation table, and the first run of this check caught exactly that in
#: ``CLAUDE.md``. The lookahead is what makes the noun mean the table: the door
#: always writes the claim as "N casos de M fuentes", so requiring the tail
#: costs nothing and removes the whole class.
#:
#: **Every quantity here is a repository-wide total.** A sentence counting a
#: *subset* -- the two gap rows of one source, say -- must be spelled with a
#: noun that is not in this list, and if it is not, this check fails on it. That
#: is a false positive on purpose: it is loud, and the fix (name the scope) is
#: the sentence a cold reader needed anyway.
COUNTED_NOUNS: tuple[tuple[str, str], ...] = (
    ("inconsistencias registradas", "inconsistencias registradas"),
    ("escenarios de bajada", "escenarios de bajada"),
    ("escenarios de tierra", "escenarios de tierra"),
    ("huecos de fuente", "huecos de fuente"),
    ("huecos de cita", "huecos de cita"),
    (r"entradas? abiertas?", "entradas abiertas"),
    ("no reproducidos", "no reproducidos"),
    ("compatibles", "compatibles"),
    ("reproducidos", "reproducidos"),
    ("escenarios", "escenarios"),
    ("fuentes", "fuentes"),
    (r"casos(?=[\s*]+de[\s*]+\S+[\s*]+fuentes)", "casos"),
    ("ADRs", "ADRs"),
)


def _wrapped(pattern: str) -> str:
    """Let a multi-word noun survive a line break.

    These are prose files wrapped at eighty columns, so ``escenarios de
    bajada`` arrives with a newline and an indent somewhere inside it about as
    often as not. Every plain space in a pattern therefore becomes the same
    separator the scan uses between the number and the noun, which also lets
    the markup fall in the middle of the phrase.
    """
    return pattern.replace(" ", r"[\s*]+")


def _quantity_of(matched: str) -> str:
    """Return the quantity the matched noun counts.

    Resolved by re-matching rather than by a dictionary because a pattern may
    be a regex -- ``entradas? abiertas?`` covers both the plural of "there are
    three open entries" and the singular of "there is one" -- so the text that
    comes out of the scan is not always one of the patterns that went in.
    """
    for pattern, quantity in COUNTED_NOUNS:
        if re.fullmatch(_wrapped(re.sub(r"\(\?=.*", "", pattern)), matched):
            return quantity
    raise AssertionError(f"{matched!r} matched the scan but no pattern claims it")


#: ``<number><emphasis and space><noun>``. The separator accepts asterisks
#: because these files bold the number, the noun, or the pair: ``**siete**
#: escenarios``, ``**35 casos de ocho fuentes**`` and ``29 ADRs`` are all the
#: same claim wearing different markup. The number accepts the thin space this
#: project groups thousands with (``3 968``), which is why it is normalised
#: before ``int()``.
INVENTORY_CLAIM_RE = re.compile(
    r"(?<![\w.,-])(\d[\d\u00a0\u202f ]*\d|\d|"
    + "|".join(sorted(_WORD_NUMBERS, key=len, reverse=True))
    + r")[\s*]+("
    + "|".join(_wrapped(pattern) for pattern, _ in COUNTED_NOUNS)
    + r")(?![\wáéíóú])"
)


def _as_int(token: str) -> int:
    """Turn ``"3 968"``, ``"35"`` or ``"veintitrés"`` into an integer."""
    lowered = token.lower()
    if lowered in _WORD_NUMBERS:
        return _WORD_NUMBERS[lowered]
    return int(re.sub(r"[\s .]", "", token))


def test_every_inventory_claim_the_door_makes_matches_the_tree() -> None:
    """A number the door states about the repository, recounted from the repository.

    The fourth route into the same defect, and the first that is not a
    citation. See the block comment above for why it cannot be folded into the
    three scans that are, and for the two things it deliberately does not cover.
    """
    root = NOTES.parent
    inventory = _inventory(root)
    wrong: list[str] = []
    for name in DOOR_FILES:
        path = root / name
        text = path.read_text(encoding="utf-8")
        for match in INVENTORY_CLAIM_RE.finditer(text):
            claimed = _as_int(match.group(1))
            actual = inventory[_quantity_of(match.group(2))]
            if claimed != actual:
                line = text[: match.start()].count("\n") + 1
                wrong.append(f"{name}:{line} says {match.group(0)!r}, the tree has {actual}")
    assert not wrong, (
        f"inventory claims the tree does not sustain: {wrong}. Each of these is a sentence "
        f"at the front door counting something this repository contains, and the count is "
        f"recomputed above from the thing itself -- not from a committed file that quotes "
        f"it. Fix the sentence, or explain in the pull request why the recount is the thing "
        f"that is wrong."
    )


@pytest.mark.parametrize("quantity", [quantity for _, quantity in COUNTED_NOUNS])
def test_every_counted_noun_is_claimed_somewhere(quantity: str) -> None:
    """The vocabulary empties itself, like the two allowlists above.

    A noun no door sentence uses any more is a recipe nobody is checking, and a
    registry that can only grow is the kind of exception that outlives its
    reason. This is the direction that catches a claim being *deleted* from the
    README rather than being wrong in it.
    """
    root = NOTES.parent
    found = any(
        _quantity_of(match.group(2)) == quantity
        for name in DOOR_FILES
        for match in INVENTORY_CLAIM_RE.finditer((root / name).read_text(encoding="utf-8"))
    )
    assert found, (
        f"no door file counts {quantity!r} any more, so its recipe in _inventory() is dead "
        f"code that nothing can falsify. Remove it from COUNTED_NOUNS and from the "
        f"recipe it belongs to."
    )
