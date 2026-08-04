"""Structured logging: key-value context, and a library that stays quiet.

Logging in QuOSS answers "what did the run do and how long did each stage take",
never "was the physics valid". That second question is
:mod:`quoss.core.errors`: a warning written to a log is invisible to whoever
reads the result file, so anything affecting the numbers goes into the result's
:class:`~quoss.core.errors.DegradationLog`, not here.

Structured means every record can carry key-value fields, so a run can be
filtered and aggregated rather than grepped::

    log = get_logger(__name__)
    log.info("Pass detected", extra={"pass_index": 3, "duration_s": 412.0})

Two output formats: human-readable text for a terminal, and JSON Lines for
machine consumption. Nothing in the physics layer chooses between them —
:func:`configure_logging` is called by an application (the CLI, the API, a
notebook), never on import. Until it is called, QuOSS emits nothing: the package
attaches a ``NullHandler`` and leaves handler configuration to whoever owns the
process, which is the standard contract for a library.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping, MutableMapping
from typing import Any, TextIO

__all__ = [
    "JsonLinesFormatter",
    "TextFormatter",
    "bind",
    "configure_logging",
    "get_logger",
]

ROOT_LOGGER_NAME = "quoss"
"""Root of the QuOSS logger tree. All package loggers hang off this name."""

# Attributes present on every LogRecord. Anything outside this set was passed by
# the caller via `extra=` and is therefore structured context worth rendering.
_RESERVED_RECORD_KEYS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "taskName",
        "thread",
        "threadName",
    }
)


def _extract_context(record: logging.LogRecord) -> dict[str, Any]:
    """Return the caller-supplied ``extra`` fields of a record.

    Parameters
    ----------
    record : logging.LogRecord
        The record being formatted.

    Returns
    -------
    dict[str, Any]
        Fields the caller attached, in insertion order, with the reserved
        ``LogRecord`` attributes removed.
    """
    return {k: v for k, v in record.__dict__.items() if k not in _RESERVED_RECORD_KEYS}


class TextFormatter(logging.Formatter):
    """Human-readable one-line format with key-value context appended.

    Renders as ``HH:MM:SS LEVEL logger: message key=value key=value``. Intended
    for a terminal; use :class:`JsonLinesFormatter` when something downstream
    parses the output.
    """

    def __init__(self) -> None:
        super().__init__(
            fmt="%(asctime)s %(levelname)-8s %(name)s: %(message)s", datefmt="%H:%M:%S"
        )

    def format(self, record: logging.LogRecord) -> str:
        """Format a record, appending its structured context.

        Parameters
        ----------
        record : logging.LogRecord
            The record to format.

        Returns
        -------
        str
            The formatted line.
        """
        base = super().format(record)
        context = _extract_context(record)
        if not context:
            return base
        rendered = " ".join(f"{k}={v!r}" for k, v in context.items())
        return f"{base} {rendered}"


class JsonLinesFormatter(logging.Formatter):
    """One JSON object per record, for machine consumption.

    Emits ``time``, ``level``, ``logger``, ``message`` and every caller-supplied
    field at the top level. Values that are not JSON-serialisable fall back to
    ``repr``, so a stray numpy array degrades the log line rather than raising
    inside the logging call — logging must never be the thing that breaks a run.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a record as a single JSON object.

        Parameters
        ----------
        record : logging.LogRecord
            The record to format.

        Returns
        -------
        str
            A JSON object on one line.
        """
        payload: dict[str, Any] = {
            "time": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extract_context(record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=repr)


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a logger under the ``quoss`` tree.

    Parameters
    ----------
    name : str, optional
        Usually ``__name__``. A name already starting with ``quoss`` is used as
        given; anything else is nested under the root so that a single call to
        :func:`configure_logging` reaches it. ``None`` returns the root logger.

    Returns
    -------
    logging.Logger
        The logger. Carries a ``NullHandler`` at the root, so it stays silent
        until an application configures handlers.

    Examples
    --------
    >>> get_logger("quoss.channel.beam").name
    'quoss.channel.beam'
    >>> get_logger("mytool").name
    'quoss.mytool'
    """
    if name is None or name == ROOT_LOGGER_NAME:
        return logging.getLogger(ROOT_LOGGER_NAME)
    if name.startswith(f"{ROOT_LOGGER_NAME}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER_NAME}.{name}")


def bind(logger: logging.Logger, **context: Any) -> logging.LoggerAdapter[logging.Logger]:
    """Attach fixed context to every record a logger emits.

    Used to stamp the scenario hash, the seed or the pass index once, instead of
    repeating them at every call site — which is how they end up on some records
    and not others.

    Parameters
    ----------
    logger : logging.Logger
        The logger to wrap.
    **context : Any
        Fields added to every record. Per-call ``extra=`` fields win on conflict,
        since the more specific value is the informative one.

    Returns
    -------
    logging.LoggerAdapter
        A logger-like object with the context bound.

    Examples
    --------
    >>> log = bind(get_logger("quoss.engine"), scenario_hash="ab12cd", seed=7)
    >>> log.extra["seed"]
    7
    """
    return _ContextAdapter(logger, context)


class _ContextAdapter(logging.LoggerAdapter[logging.Logger]):
    """Adapter that merges bound context into each record's ``extra``."""

    def process(
        self, msg: Any, kwargs: MutableMapping[str, Any]
    ) -> tuple[Any, MutableMapping[str, Any]]:
        """Merge bound context beneath any per-call ``extra``.

        Parameters
        ----------
        msg : Any
            The log message, passed through unchanged.
        kwargs : MutableMapping[str, Any]
            Keyword arguments of the logging call.

        Returns
        -------
        tuple[Any, MutableMapping[str, Any]]
            The message and the updated keyword arguments.
        """
        bound: Mapping[str, Any] = self.extra or {}
        kwargs["extra"] = {**bound, **(kwargs.get("extra") or {})}
        return msg, kwargs


def configure_logging(
    level: int | str = logging.INFO,
    *,
    stream: TextIO | None = None,
    json_lines: bool = False,
) -> None:
    """Install a handler on the QuOSS logger tree.

    Call this from an application entry point — the CLI, the API factory, the top
    of a notebook — and nowhere else. Importing QuOSS must not configure logging,
    because a library that writes to stderr on import is a library that fights
    with its host.

    Idempotent: replaces any handler a previous call installed, so calling it
    twice does not double every line.

    Parameters
    ----------
    level : int or str, default ``logging.INFO``
        Threshold, as a :mod:`logging` level or its name.
    stream : TextIO, optional
        Destination. Defaults to ``sys.stderr``, keeping ``stdout`` clean for
        machine-readable command output.
    json_lines : bool, default False
        Emit JSON Lines instead of human-readable text.
    """
    logger = logging.getLogger(ROOT_LOGGER_NAME)
    for handler in [h for h in logger.handlers if getattr(h, "_quoss_managed", False)]:
        logger.removeHandler(handler)
        handler.close()

    new_handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    new_handler.setFormatter(JsonLinesFormatter() if json_lines else TextFormatter())
    # Marker so a second call replaces our handler without touching handlers the
    # host application installed itself.
    new_handler._quoss_managed = True  # type: ignore[attr-defined]
    logger.addHandler(new_handler)
    logger.setLevel(level)
    # Records stop here: the host's root logger should not receive a second copy.
    logger.propagate = False


# A library emits nothing until an application asks it to.
logging.getLogger(ROOT_LOGGER_NAME).addHandler(logging.NullHandler())
