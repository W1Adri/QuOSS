"""``quoss validate``: the same table ``python -m quoss.validation`` prints, exit 0."""

from __future__ import annotations

from pathlib import Path

import pytest

from quoss.cli.main import main
from quoss.cli.report import EXIT_OK
from quoss.validation.base import render_markdown, run_all


class TestTheCliAddsNothingToTheTable:
    def test_the_printed_table_is_the_rendered_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status = main(["validate"])
        assert status == EXIT_OK
        assert capsys.readouterr().out == render_markdown(run_all())

    def test_write_puts_the_same_text_in_a_file(self, tmp_path: Path) -> None:
        target = tmp_path / "nested" / "validation.md"
        assert main(["validate", "--write", str(target)]) == EXIT_OK
        assert target.read_text(encoding="utf-8") == render_markdown(run_all())

    def test_quiet_computes_and_says_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        assert main(["validate", "--quiet"]) == EXIT_OK
        assert capsys.readouterr().out == ""


class TestADisagreementIsNotAFailureHere:
    def test_the_table_holds_a_not_reproduced_row_and_the_status_is_still_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The decision of ADR 0018, asserted rather than described.

        The Micius row does not reproduce, deliberately and with the
        disagreement written down. A command that failed on it would teach its
        user to stop running it, and the gate that *does* fail on an unexpected
        disagreement is ``tests/validation/test_base.py``.
        """
        status = main(["validate"])
        assert "not reproduced" in capsys.readouterr().out
        assert status == EXIT_OK
