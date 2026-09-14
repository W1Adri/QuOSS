"""Reading and writing scenarios: YAML or JSON in, a validated :class:`Scenario` out.

This is the user-facing boundary of the project, and the whole of it. A file
comes in as text, ``yaml.safe_load`` or ``json.loads`` turns it into plain
Python, :class:`~quoss.scenario.models.Scenario` validates it, and every way
that can fail is reported as one :class:`~quoss.core.errors.ScenarioError`
whose message lists **every** failing field by its dotted path
(``stations.0.latitude_deg``, ``protocol.name``) with the reason — a user with
three mistakes fixes three, not one per run.

Why ``safe_load`` and nothing else
----------------------------------
``yaml.load`` with the full loader instantiates arbitrary Python objects from
tags in the file; a scenario is data, and the ``!!python/object`` tag has no
business in one. ``safe_load`` reads scalars, sequences and mappings only.
``safe_dump`` is the same rule in the other direction: if a value cannot be
written as plain YAML, that is a bug in the schema and it should fail here,
not produce a file only Python can read.

Why the dump is the JSON-mode dump
----------------------------------
:meth:`~pydantic.BaseModel.model_dump` in ``mode="json"`` turns enums into
their values and the epoch into an ISO-8601 string, which are the forms a
person writes in a file. The scenario read back from that text equals the one
written (``tests/scenario/test_io.py::TestRoundTrip``), enum members and
timezone included. Dumping in Python mode would write a datetime object,
which ``safe_dump`` renders as a timestamp *without* the ``Z`` — legal YAML,
but a reader in another language would call it naive.

Examples
--------
>>> from quoss.scenario.defaults import reference_castelldefels
>>> scenario = reference_castelldefels()
>>> loads_scenario(dumps_scenario(scenario)) == scenario
True
>>> loads_scenario(dumps_scenario(scenario, format="json"), format="json") == scenario
True
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import ValidationError

from quoss.core.errors import ScenarioError
from quoss.scenario.models import Scenario

__all__ = [
    "ScenarioFormat",
    "dump_scenario",
    "dumps_scenario",
    "format_for_path",
    "load_scenario",
    "loads_scenario",
]

ScenarioFormat = Literal["yaml", "json"]

_SUFFIXES: dict[str, ScenarioFormat] = {".yaml": "yaml", ".yml": "yaml", ".json": "json"}


def format_for_path(path: Path) -> ScenarioFormat:
    """Return the format a path's suffix names.

    Parameters
    ----------
    path : Path
        A ``.yaml``, ``.yml`` or ``.json`` path.

    Returns
    -------
    ScenarioFormat
        ``"yaml"`` or ``"json"``.

    Raises
    ------
    ScenarioError
        For any other suffix. Guessing from content would let a JSON file
        named ``.yaml`` load (JSON is YAML) and a YAML file named ``.json``
        fail with a parser message about a brace.
    """
    suffix = path.suffix.lower()
    if suffix not in _SUFFIXES:
        raise ScenarioError(
            f"cannot tell the scenario format of {path}: expected a .yaml, .yml or .json suffix."
        )
    return _SUFFIXES[suffix]


def _describe(error: ValidationError) -> str:
    lines = []
    for item in error.errors(include_url=False):
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        message = item["msg"]
        if message.startswith("Value error, "):
            message = message[len("Value error, ") :]
        lines.append(f"  {location}: {message}")
    count = error.error_count()
    plural = "s" if count != 1 else ""
    return f"scenario has {count} invalid field{plural}:\n" + "\n".join(lines)


def _validate(data: Any) -> Scenario:
    if not isinstance(data, dict):
        raise ScenarioError(
            f"a scenario must be a mapping of field names to values, got {type(data).__name__}."
        )
    try:
        return Scenario.model_validate(data)
    except ValidationError as error:
        raise ScenarioError(_describe(error)) from error


def loads_scenario(text: str, *, format: ScenarioFormat = "yaml") -> Scenario:
    """Parse and validate a scenario from text.

    Parameters
    ----------
    text : str
        YAML or JSON source.
    format : {"yaml", "json"}
        Which parser to use. Default YAML.

    Returns
    -------
    Scenario
        The validated scenario.

    Raises
    ------
    ScenarioError
        If the text does not parse, is not a mapping, or fails validation;
        the message names every failing field.

    Examples
    --------
    >>> loads_scenario("orbit: {}", format="yaml")  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    quoss.core.errors.ScenarioError: scenario has ... invalid fields:
    ...
    """
    if format == "yaml":
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as error:
            raise ScenarioError(f"scenario is not valid YAML: {error}") from error
    elif format == "json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as error:
            raise ScenarioError(f"scenario is not valid JSON: {error}") from error
    else:
        raise ScenarioError(f"unknown scenario format {format!r}; use 'yaml' or 'json'.")
    return _validate(data)


def load_scenario(path: str | Path) -> Scenario:
    """Read and validate a scenario file, format from its suffix.

    Parameters
    ----------
    path : str or Path
        A ``.yaml``, ``.yml`` or ``.json`` file.

    Returns
    -------
    Scenario
        The validated scenario.

    Raises
    ------
    ScenarioError
        If the file cannot be read, has an unknown suffix, or its content
        fails :func:`loads_scenario`.
    """
    target = Path(path)
    format = format_for_path(target)
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as error:
        raise ScenarioError(f"cannot read scenario file {target}: {error}") from error
    return loads_scenario(text, format=format)


def dumps_scenario(scenario: Scenario, *, format: ScenarioFormat = "yaml") -> str:
    """Serialise a scenario to text in the form a person would write.

    Parameters
    ----------
    scenario : Scenario
        The scenario.
    format : {"yaml", "json"}
        Output format. YAML keeps the schema's field order (it reads top-down
        as orbit, stations, ...); JSON is indented by two spaces.

    Returns
    -------
    str
        The text; ``loads_scenario`` of it equals ``scenario``.

    Raises
    ------
    ScenarioError
        If ``format`` is not one of the two.
    """
    data = scenario.model_dump(mode="json")
    if format == "yaml":
        return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)
    if format == "json":
        return json.dumps(data, indent=2, allow_nan=False) + "\n"
    raise ScenarioError(f"unknown scenario format {format!r}; use 'yaml' or 'json'.")


def dump_scenario(scenario: Scenario, path: str | Path) -> None:
    """Write a scenario to a file, format from its suffix.

    Parameters
    ----------
    scenario : Scenario
        The scenario.
    path : str or Path
        Destination, ``.yaml``, ``.yml`` or ``.json``. Parent directories must
        exist.

    Raises
    ------
    ScenarioError
        For an unknown suffix or an unwritable path.
    """
    target = Path(path)
    text = dumps_scenario(scenario, format=format_for_path(target))
    try:
        target.write_text(text, encoding="utf-8")
    except OSError as error:
        raise ScenarioError(f"cannot write scenario file {target}: {error}") from error
