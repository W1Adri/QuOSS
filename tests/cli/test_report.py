"""Warnings reach the reader whole, and only an undeclared substitution fails.

The property under test in the first class is deliberately awkward to state and
easy to check: **for every entry, every one of its five fields appears verbatim
in the printed block.** A summariser passes a test that looks for the code; it
does not pass one that looks for the ``details`` of the third entry.
"""

from __future__ import annotations

import io

import pytest

from quoss.cli.report import (
    EXIT_OK,
    EXIT_UNDECLARED_DEGRADATION,
    exit_status,
    print_warnings,
    undeclared_degradations,
)
from quoss.core.errors import DegradationLog

WHERE = "quoss.tests.cli.report"


def _log() -> DegradationLog:
    log = DegradationLog()
    log.info("a.info", "an informational thing happened.", where=WHERE, value=1)
    log.warn("b.warning", "a warning thing happened.", where=WHERE, value=2.5, other="x")
    log.degrade("c.degraded", "a model was substituted.", where=WHERE, replaced="exact")
    return log


class TestNothingRecordedIsLost:
    def test_every_field_of_every_entry_is_printed(self) -> None:
        entries = _log().to_dicts()
        stream = io.StringIO()

        print_warnings(entries, stream=stream)

        text = stream.getvalue()
        for entry in entries:
            assert entry["code"] in text
            assert entry["message"] in text
            assert entry["where"] in text
            assert str(entry["severity"]) in text
            for key, value in dict(entry["details"]).items():
                assert key in text
                assert str(value) in text or repr(value) in text

    def test_the_count_is_in_addition_and_not_instead(self) -> None:
        """``[2/3]`` is navigation. The entry still has to be there."""
        entries = _log().to_dicts()
        stream = io.StringIO()
        print_warnings(entries, stream=stream)
        text = stream.getvalue()
        assert "[2/3]" in text
        assert "a warning thing happened." in text

    def test_an_empty_log_says_so_rather_than_printing_nothing(self) -> None:
        """Silence would be indistinguishable from a printer that failed."""
        stream = io.StringIO()
        print_warnings([], stream=stream)
        assert stream.getvalue().strip() == "warnings: none recorded."

    def test_an_entry_without_details_gets_no_details_line(self) -> None:
        """Most entries carry details; the ones that do not must not print an empty field.

        An ``details: {}`` line reads as "the recorder had nothing to say about
        the values", which is a claim. The absence of the line says nothing,
        which is what is true.
        """
        log = DegradationLog()
        log.info("plain.entry", "nothing structured about this one.", where=WHERE)
        stream = io.StringIO()
        print_warnings(log.to_dicts(), stream=stream)
        text = stream.getvalue()
        assert "plain.entry" in text
        assert "details:" not in text

    def test_a_detail_json_cannot_hold_is_written_rather_than_dropped(self) -> None:
        stream = io.StringIO()
        print_warnings(
            [
                {
                    "code": "x.y",
                    "message": "m",
                    "severity": "info",
                    "where": WHERE,
                    "details": {"thing": object()},
                }
            ],
            stream=stream,
        )
        assert "thing" in stream.getvalue()


class TestOnlyUndeclaredSubstitutionsFail:
    def test_a_warning_is_not_a_substitution(self) -> None:
        """WARNING means "near an edge", DEGRADED means "a model was swapped"."""
        assert undeclared_degradations(_log().to_dicts(), declared=()) == ["c.degraded"]

    def test_a_declared_code_is_accepted(self) -> None:
        assert undeclared_degradations(_log().to_dicts(), declared=("c.degraded",)) == []

    def test_a_repeated_code_is_reported_once(self) -> None:
        log = _log()
        log.degrade("c.degraded", "again.", where=WHERE)
        assert undeclared_degradations(log.to_dicts(), declared=()) == ["c.degraded"]

    @pytest.mark.parametrize(
        ("declared", "expected"),
        [((), EXIT_UNDECLARED_DEGRADATION), (("c.degraded",), EXIT_OK)],
    )
    def test_the_status_follows_the_difference(
        self, declared: tuple[str, ...], expected: int
    ) -> None:
        assert exit_status(_log().to_dicts(), declared=declared, stream=io.StringIO()) == expected

    def test_the_failure_names_the_codes_and_the_way_out(self) -> None:
        stream = io.StringIO()
        exit_status(_log().to_dicts(), declared=(), stream=stream)
        text = stream.getvalue()
        assert "c.degraded" in text
        assert "expected_degradations" in text
