"""Tests for `python -m quoss.validation`, the command the generated file names.

`docs/validation.md` carries `REGENERATE_COMMAND` in its first line as the one
way to rewrite it. That line is an instruction to a reader, so the command has
to exist and has to do what the line says — which is the whole content of this
file. It was a command with no module behind it until `__main__.py` was written.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quoss.validation.__main__ import main
from quoss.validation.base import REGENERATE_COMMAND, render_markdown, run_all


class TestTheCommandTheGeneratedFileNames:
    def test_the_quoted_command_is_this_module(self) -> None:
        """The string in the file header names `python -m quoss.validation --write <path>`.

        Asserted against the constant rather than retyped, so the two cannot
        drift apart: a header quoting a command nobody can run is worse than no
        header, because a reader who tries it cannot tell whether the file is
        stale, wrong or fine.
        """
        assert "python -m quoss.validation" in REGENERATE_COMMAND
        assert "--write docs/validation.md" in REGENERATE_COMMAND

    def test_write_produces_exactly_the_rendered_table(self, tmp_path: Path) -> None:
        """Byte for byte, so a committed file can be diffed against a fresh run."""
        target = tmp_path / "validation.md"
        assert main(["--write", str(target)]) == 0
        assert target.read_text(encoding="utf-8") == render_markdown(run_all())

    def test_write_creates_the_directory_it_is_pointed_at(self, tmp_path: Path) -> None:
        """A first run into `docs/` on a fresh checkout must not fail on a missing parent."""
        target = tmp_path / "made" / "up" / "validation.md"
        assert main(["--write", str(target)]) == 0
        assert target.is_file()

    def test_without_write_the_table_goes_to_standard_output(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main([]) == 0
        assert capsys.readouterr().out == render_markdown(run_all())

    def test_quiet_computes_the_table_and_says_nothing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """For a CI step that only asks whether the table can be produced at all.

        Which is not a rhetorical question here: `run_all` raised
        `ModuleNotFoundError` on every call for as long as `CASE_MODULES`
        listed a module nobody had written.
        """
        assert main(["--quiet"]) == 0
        assert capsys.readouterr().out == ""

    def test_a_disagreement_is_not_a_failure_of_this_command(self) -> None:
        """Exit zero with a `not reproduced` row in the table, on purpose.

        Deriving the status instead of declaring it exists so that a
        disagreement gets *published*. A generator that refused to write the
        document while one was present would push whoever hit it towards making
        the disagreement go away, which is the failure this package is for.

        The gate that does fail on an unexpected disagreement is
        `test_base.py::TestTheTableRuns`, against `EXPECTED_DISAGREEMENTS`.
        """
        text = render_markdown(run_all())
        assert "**not reproduced**" in text
        assert main(["--quiet"]) == 0
