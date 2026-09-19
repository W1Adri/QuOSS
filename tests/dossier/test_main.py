"""Tests for `python -m quoss.dossier`, the command that brings all three back into line.

Why it is worth its own file
-----------------------------
`tests/dossier/test_docs.py` is the gate: it fails when a committed document
differs from what the code produces. A gate is only useful if the fix is one
command, and this is that command. It was a sentence in a failure message until
`__main__.py` existed.

`--check` is the same walk without writing, so that the state of the tree can be
asked about without changing it — which is what a pre-commit hook or a reviewer
wants.

Why there are three tests and not six
--------------------------------------
Every call to `main` here regenerates all three documents, which is about two
and a half seconds of real physics, and this suite runs five times in CI. So
each test makes every assertion it can from **one** call: the first deletes the
output directory *and* checks the bytes, the third breaks one document and
deletes another so that a single `--check` covers both ways a tree can be out
of date. Splitting them would read marginally better and cost a minute of CI
per push.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from quoss.cli.report import EXIT_OK, EXIT_UNDECLARED_DEGRADATION
from quoss.dossier.__main__ import main
from quoss.dossier.base import dossiers, render
from quoss.scenario.io import load_scenario


@pytest.fixture(scope="module")
def pristine(tmp_path_factory: pytest.TempPathFactory, project_root: Path) -> Path:
    """Build one throwaway checkout of the scenarios and documents, shared by every test.

    Module-scoped and never written to; a test that needs to break something
    copies it first. The real tree is never the subject, because a test that
    rewrote `docs/experiments/` would go on to pass on a tree it had itself
    just fixed.
    """
    root = tmp_path_factory.mktemp("checkout")
    shutil.copytree(project_root / "scenarios", root / "scenarios")
    shutil.copytree(project_root / "docs" / "experiments", root / "docs" / "experiments")
    return root


@pytest.fixture
def checkout(tmp_path: Path, pristine: Path) -> Path:
    """Return a private copy of `pristine`, for a test that changes it."""
    shutil.copytree(pristine, tmp_path / "tree")
    return tmp_path / "tree"


def test_it_creates_the_directory_and_writes_exactly_the_rendered_text(checkout: Path) -> None:
    """The first run on a checkout that has no `docs/experiments/` at all.

    Both halves in one call: that a missing output directory is created rather
    than being an error, and that what lands in it is the generator's text byte
    for byte. If those two ever came from different code paths, the document a
    user produced and the one CI checks would differ, and the difference would
    surface in the copy somebody carried into a meeting.
    """
    shutil.rmtree(checkout / "docs")
    assert main(["--root", str(checkout)]) == EXIT_OK
    for spec in dossiers():
        path = checkout / spec.document_path
        assert path.is_file()
        scenario = load_scenario(checkout / spec.scenario_path)
        assert path.read_text(encoding="utf-8") == render(spec, scenario).text


def test_check_passes_on_a_current_tree_and_writes_nothing(pristine: Path) -> None:
    """The gate's read-only form, on the documents this repository commits.

    It runs against a copy of the committed files, so it is also the assertion
    that those files are current -- the same thing `test_docs.py` says, reached
    through the command a person would actually type.
    """
    before = {
        spec.document_path: (pristine / spec.document_path).read_text(encoding="utf-8")
        for spec in dossiers()
    }
    assert main(["--root", str(pristine), "--check"]) == EXIT_OK
    for path, text in before.items():
        assert (pristine / path).read_text(encoding="utf-8") == text


def test_check_names_every_stale_document_and_rewrites_none(
    checkout: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both ways a tree goes out of date, in one call: edited, and absent.

    Naming the file matters more than the status does: the point of the gate is
    that somebody goes and looks at the diff, and a bare non-zero exit tells
    them to regenerate without telling them what moved.
    """
    edited, _, missing = dossiers()
    edited_path = checkout / edited.document_path
    edited_path.write_text(
        edited_path.read_text(encoding="utf-8").replace("kilometre", "mile"), encoding="utf-8"
    )
    (checkout / missing.document_path).unlink()

    assert main(["--root", str(checkout), "--check"]) == EXIT_UNDECLARED_DEGRADATION
    err = capsys.readouterr().err
    assert f"stale: {edited.document_path}" in err
    assert f"stale: {missing.document_path}" in err

    assert "mile" in edited_path.read_text(encoding="utf-8"), "--check rewrote what it reported"
    assert not (checkout / missing.document_path).exists(), "--check wrote a file it reported"
