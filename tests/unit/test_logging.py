"""Tests for structured logging.

Chiefly two library-hygiene properties: QuOSS emits nothing until an application
asks it to, and configuring twice does not duplicate every line.
"""

import io
import json
import logging

import pytest

from quoss.core.logging import (
    ROOT_LOGGER_NAME,
    JsonLinesFormatter,
    TextFormatter,
    bind,
    configure_logging,
    get_logger,
)


@pytest.fixture(autouse=True)
def _restore_logging_state():
    """Leave the QuOSS logger tree exactly as it was found.

    Logging is process-global state; a test that reconfigures it and does not
    clean up leaks into every test that runs afterwards.
    """
    root = logging.getLogger(ROOT_LOGGER_NAME)
    saved_handlers = list(root.handlers)
    saved_level = root.level
    saved_propagate = root.propagate
    yield
    root.handlers = saved_handlers
    root.level = saved_level
    root.propagate = saved_propagate


class TestGetLogger:
    """Every logger must hang off the `quoss` root so one call configures all."""

    def test_dotted_quoss_name_is_used_verbatim(self) -> None:
        assert get_logger("quoss.channel.beam").name == "quoss.channel.beam"

    def test_foreign_name_is_nested_under_the_root(self) -> None:
        assert get_logger("mytool").name == "quoss.mytool"

    def test_none_returns_the_root(self) -> None:
        assert get_logger(None).name == ROOT_LOGGER_NAME

    def test_root_name_returns_the_root(self) -> None:
        assert get_logger(ROOT_LOGGER_NAME).name == ROOT_LOGGER_NAME

    def test_module_dunder_name_pattern(self) -> None:
        """The idiomatic call site: get_logger(__name__) from inside the package."""
        assert get_logger("quoss.core.units").name == "quoss.core.units"


class TestSilentByDefault:
    """A library that writes to stderr on import is a library that misbehaves."""

    def test_root_has_a_null_handler(self) -> None:
        root = logging.getLogger(ROOT_LOGGER_NAME)
        assert any(isinstance(h, logging.NullHandler) for h in root.handlers)

    def test_nothing_is_emitted_before_configuration(self, capsys) -> None:
        root = logging.getLogger(ROOT_LOGGER_NAME)
        root.handlers = [logging.NullHandler()]
        root.propagate = False
        get_logger("quoss.test").warning("should not appear")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""


class TestConfiguration:
    """configure_logging is the application's switch, and is idempotent."""

    def test_text_output_reaches_the_stream(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream)
        get_logger("quoss.test").info("hello")
        assert "hello" in stream.getvalue()

    def test_level_is_respected(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.WARNING, stream=stream)
        log = get_logger("quoss.test")
        log.debug("invisible")
        log.warning("visible")
        output = stream.getvalue()
        assert "invisible" not in output
        assert "visible" in output

    def test_level_accepts_a_name(self) -> None:
        stream = io.StringIO()
        configure_logging("DEBUG", stream=stream)
        get_logger("quoss.test").debug("shown")
        assert "shown" in stream.getvalue()

    def test_calling_twice_does_not_duplicate_records(self) -> None:
        """The reason the handler is marked: a second call replaces, not appends."""
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream)
        configure_logging(logging.INFO, stream=stream)
        get_logger("quoss.test").info("once")
        assert stream.getvalue().count("once") == 1

    def test_host_handlers_are_left_alone(self) -> None:
        """Only handlers QuOSS installed are removed; the host's own survive."""
        root = logging.getLogger(ROOT_LOGGER_NAME)
        host_handler = logging.NullHandler()
        root.addHandler(host_handler)
        configure_logging(logging.INFO, stream=io.StringIO())
        assert host_handler in root.handlers

    def test_records_do_not_propagate_to_the_python_root(self) -> None:
        """Otherwise the host application sees every line twice."""
        configure_logging(logging.INFO, stream=io.StringIO())
        assert logging.getLogger(ROOT_LOGGER_NAME).propagate is False


class TestStructuredContext:
    """Key-value fields, so a run can be filtered rather than grepped."""

    def test_text_format_appends_extra_fields(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream)
        get_logger("quoss.test").info("Pass detected", extra={"pass_index": 3})
        output = stream.getvalue()
        assert "Pass detected" in output
        assert "pass_index=3" in output

    def test_json_format_puts_fields_at_the_top_level(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        get_logger("quoss.test").info("stage done", extra={"stage": "channel", "elapsed_s": 0.4})
        record = json.loads(stream.getvalue().strip())
        assert record["message"] == "stage done"
        assert record["level"] == "INFO"
        assert record["logger"] == "quoss.test"
        assert record["stage"] == "channel"
        assert record["elapsed_s"] == 0.4

    def test_json_output_is_one_object_per_line(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        log = get_logger("quoss.test")
        log.info("a")
        log.info("b")
        lines = stream.getvalue().strip().splitlines()
        assert len(lines) == 2
        assert [json.loads(line)["message"] for line in lines] == ["a", "b"]

    def test_unserialisable_values_degrade_to_repr(self) -> None:
        """Logging must never be the thing that breaks a run."""
        import numpy as np

        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        get_logger("quoss.test").info("array", extra={"values": np.arange(3)})
        record = json.loads(stream.getvalue().strip())
        assert "0" in record["values"]

    def test_exception_info_is_captured_in_json(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.ERROR, stream=stream, json_lines=True)
        try:
            raise ValueError("boom")
        except ValueError:
            get_logger("quoss.test").exception("failed")
        record = json.loads(stream.getvalue().strip())
        assert "ValueError: boom" in record["exception"]


class TestBind:
    """Bound context is stamped once instead of repeated at each call site."""

    def test_bound_fields_appear_on_every_record(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        log = bind(get_logger("quoss.engine"), scenario_hash="ab12cd", seed=7)
        log.info("first")
        log.info("second")
        records = [json.loads(line) for line in stream.getvalue().strip().splitlines()]
        assert all(r["scenario_hash"] == "ab12cd" and r["seed"] == 7 for r in records)

    def test_per_call_extra_is_merged(self) -> None:
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        bind(get_logger("quoss.engine"), seed=7).info("x", extra={"pass_index": 2})
        record = json.loads(stream.getvalue().strip())
        assert record["seed"] == 7
        assert record["pass_index"] == 2

    def test_per_call_extra_wins_on_conflict(self) -> None:
        """The more specific value is the informative one."""
        stream = io.StringIO()
        configure_logging(logging.INFO, stream=stream, json_lines=True)
        bind(get_logger("quoss.engine"), stage="outer").info("x", extra={"stage": "inner"})
        assert json.loads(stream.getvalue().strip())["stage"] == "inner"

    def test_bound_context_is_readable(self) -> None:
        bound = bind(get_logger("quoss.engine"), seed=7).extra
        assert bound is not None
        assert bound["seed"] == 7


class TestFormattersInIsolation:
    """The formatters are public, so they are testable without global state."""

    def test_text_formatter_without_context(self) -> None:
        record = logging.LogRecord("quoss.x", logging.INFO, "f.py", 1, "plain", None, None)
        assert TextFormatter().format(record).endswith("plain")

    def test_json_formatter_emits_the_required_keys(self) -> None:
        record = logging.LogRecord("quoss.x", logging.INFO, "f.py", 1, "msg", None, None)
        payload = json.loads(JsonLinesFormatter().format(record))
        assert set(payload) >= {"time", "level", "logger", "message"}

    def test_json_formatter_does_not_leak_record_internals(self) -> None:
        """Only caller-supplied fields, not the 20-odd LogRecord attributes."""
        record = logging.LogRecord("quoss.x", logging.INFO, "f.py", 1, "msg", None, None)
        payload = json.loads(JsonLinesFormatter().format(record))
        assert "lineno" not in payload
        assert "pathname" not in payload
