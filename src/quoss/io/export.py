"""A simulation result written to a directory that describes itself.

What "export" has to achieve
----------------------------
A result leaves the simulator in two situations: a collaborator wants to look
at the passes in a spreadsheet, or a figure has to be regenerated a year
later. The first wants CSV. The second wants every array at full precision
and the provenance next to it — scenario hash, code version, data versions,
seed, warnings — so that "the figure in the paper" is a directory and not a
memory. This module writes both from the same object, and adds a
``manifest.json`` that lists every file it wrote with its SHA-256, so the
directory can be checked for completeness and for silent edits.

What is written
---------------
Given ``formats``, a subset of ``("json", "csv", "npz", "parquet")``:

``manifest.json`` (always)
    ``{"export": {...}, "files": [{name, sha256, size_bytes}, ...], "result": <manifest>}``
    where ``result`` is the manifest half of ``to_manifest_and_arrays()``
    verbatim — scenario, provenance, warnings, timings, and every scalar of
    the result with its arrays replaced by ``{"$array": "<key>"}`` markers.
    Written last, so the file list is complete.
``README.txt`` (always)
    The same file list, human-readable, including ``manifest.json`` itself.
``result.json`` (``"json"``)
    Manifest plus every array as a nested list with its dtype and shape: the
    single-file, dependency-free form. ``SimulationResult.from_manifest_and_arrays``
    rebuilds the result from it after ``np.asarray`` on each entry.
``passes.csv``, ``daily.csv`` (``"csv"``)
    One row per pass / per day, in the units the result stores plus a few
    derived columns a spreadsheet user wants (see below).
``series_<station>.csv`` (``"csv"``)
    One row per time sample for one station, one column per series.
``arrays.npz`` (``"npz"``)
    The arrays half of ``to_manifest_and_arrays()`` as ``numpy.savez_compressed``
    writes it, keys unchanged, full ``float64``; with ``manifest.json`` this is
    exactly what ``from_manifest_and_arrays`` takes.
``passes.parquet``, ``daily.parquet``, ``series_<station>.parquet`` (``"parquet"``)
    The same tables through ``pyarrow``, which is the optional ``quoss[export]``
    extra; if it is not installed the export raises
    :class:`~quoss.core.errors.ConfigurationError` and writes nothing for
    that format. It does not skip: a caller who asked for Parquet and got a
    directory without it would read the absence as "no data".

The tables, and the columns that are derived
---------------------------------------------
The tables are read from the manifest of ``scenario/result.py``
(``SimulationResult.to_manifest_and_arrays``, stage 4):

* ``manifest["passes"]`` is a mapping of parallel columns over the pass axis
  (``station``, ``start_s``, ``finite_bits``, ...) plus the scalar
  ``epoch_jd``. The CSV holds every column, led by ``pass_index``, and adds
  ``start_jd``/``end_jd``/``culmination_jd`` (``epoch_jd + t/86400``),
  ``duration_s``, ``culmination_elevation_deg`` and ``has_key``
  (``finite_bits > 0``). When ``manifest["monte_carlo"]`` is present its
  ``quantile_bits`` rows become ``finite_bits_q<quantile>`` columns and
  ``outage_probability``/``mean_bits`` come along as
  ``monte_carlo_outage_probability``/``monte_carlo_mean_bits``.
* ``manifest["daily"]`` is the same shape over the day axis; the CSV adds
  ``day_utc`` (the calendar date of the Julian day number).
* ``manifest["series"]`` is a list, one entry per station, each with a
  ``grid`` (``epoch_jd``, ``t_s``) and one ``{name, unit, values}`` block per
  series. The CSV has ``time_s``, ``jd``, then every series under its own
  name, and a ``<x>_deg`` column after every ``<x>_rad`` one.

Arrays are wherever the manifest's markers point; a marker whose key is
missing from the arrays mapping is a :class:`~quoss.core.errors.DomainError`,
because a result whose manifest and arrays disagree cannot be exported
faithfully. A table the result does not carry (an empty passes mapping, no
series) is not written, and an ``INFO`` degradation
(``io.export-table-absent``) says so, so an empty directory is never a
surprise. Plain lists of row dictionaries are also accepted for ``passes``
and ``daily``, which is what a hand-built result in a test looks like.

How floats reach a CSV
----------------------
Through ``repr``. ``str(0.1 + 0.2)`` in Python is ``'0.30000000000000004'``
too — the two agree since 3.2 — but ``repr`` is the documented promise of
round-trip: ``float(repr(x)) == x`` for every finite ``x``. A CSV written
with a fixed number of decimals is one a reader cannot re-derive a finite-key
bound from: the difference between ``1e-10`` and ``1.0000000000000001e-10``
is not visible, but the one between ``0.4329850`` Mbit and ``432985`` bits
is. Measured in ``tests/io/test_export.py::TestRoundTrips``: every float in a
property-based table of up to 40 rows reads back equal, not close, over 50
generated tables. NaN — which the series hold outside a pass — is written as
an empty cell, the convention every spreadsheet and ``pandas.read_csv``
reads back as missing.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> import numpy as np
>>> from quoss.core.errors import DegradationLog
>>> class Tiny:
...     def to_manifest_and_arrays(self):
...         manifest = {
...             "provenance": {"scenario_hash": "abc"},
...             "warnings": [],
...             "timings": {},
...             "passes": {"station": ["cttc"], "finite_bits": {"$array": "passes.finite_bits"}},
...             "daily": [{"day_number": 2460677, "finite_bits": 190581.0}],
...             "series": [],
...         }
...         return manifest, {"passes.finite_bits": np.array([190581.0])}
>>> with tempfile.TemporaryDirectory() as tmp:
...     out = export_result(Tiny(), Path(tmp), degradations=DegradationLog())
...     names = [f.name for f in out.files]
>>> names
['passes.csv', 'daily.csv', 'arrays.npz', 'result.json']
"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import numpy as np

import quoss
from quoss.core.errors import ConfigurationError, DegradationLog, DomainError
from quoss.core.units import rad_to_deg
from quoss.orbits.frames import jd_to_calendar

__all__ = [
    "ARRAY_MARKER",
    "FORMATS",
    "ExportManifest",
    "ExportableResult",
    "ExportedFile",
    "export_result",
]

FORMATS = ("json", "csv", "npz", "parquet")
"""Every format string :func:`export_result` accepts."""

ARRAY_MARKER = "$array"
"""Key of the placeholder a manifest holds where an array was pulled out (``scenario/result.py``)."""

_WHERE = "quoss.io.export.export_result"
_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")
_SECONDS_PER_DAY = 86_400.0

Table = tuple[tuple[str, ...], list[list[Any]]]
"""``(columns, rows)`` with every row the length of ``columns``."""


class ExportableResult(Protocol):
    """The one method a result needs for :func:`export_result`."""

    def to_manifest_and_arrays(self) -> tuple[dict[str, Any], dict[str, np.ndarray[Any, Any]]]:
        """Return a JSON-serialisable manifest and a flat dict of arrays."""
        ...


@dataclass(frozen=True, slots=True)
class ExportedFile:
    """One file written by :func:`export_result`.

    Parameters
    ----------
    name : str
        File name relative to the export directory.
    sha256 : str
        SHA-256 of the bytes on disk, hex.
    size_bytes : int
        Length of the file.
    """

    name: str
    sha256: str
    size_bytes: int

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON form used in ``manifest.json``."""
        return {"name": self.name, "sha256": self.sha256, "size_bytes": self.size_bytes}


@dataclass(frozen=True, slots=True)
class ExportManifest:
    """What :func:`export_result` wrote.

    Parameters
    ----------
    directory : Path
        The export directory.
    files : tuple[ExportedFile, ...]
        Every data file, in the order written; ``manifest.json`` and
        ``README.txt`` are not included because they are written after the
        list is closed (``manifest.json`` cannot contain its own hash).
    formats : tuple[str, ...]
        The formats requested, deduplicated, in request order.
    created_utc : str
        ISO-8601 UTC time of the export.
    """

    directory: Path
    files: tuple[ExportedFile, ...]
    formats: tuple[str, ...]
    created_utc: str

    @property
    def manifest_path(self) -> Path:
        """Path of ``manifest.json``."""
        return self.directory / "manifest.json"


def export_result(
    result: ExportableResult,
    directory: Path,
    *,
    formats: Sequence[str] = ("json", "csv", "npz"),
    degradations: DegradationLog,
) -> ExportManifest:
    """Write ``result`` to ``directory`` in the requested formats.

    Parameters
    ----------
    result : ExportableResult
        Anything with ``to_manifest_and_arrays()``.
    directory : Path
        Created if absent. Existing files with the same names are overwritten;
        other files are left alone and are *not* listed in the manifest.
    formats : Sequence[str], optional
        Subset of :data:`FORMATS`; ``("json", "csv", "npz")`` by default.
        The groups are written CSV, npz, Parquet, JSON regardless of order.
    degradations : DegradationLog
        Required; receives ``io.export-table-absent`` (INFO) for every table
        the result does not carry.

    Returns
    -------
    ExportManifest
        The files written, with hashes.

    Raises
    ------
    DomainError
        On an unknown or empty ``formats``; on a manifest marker whose array is
        missing; on a station name that collides with another after being
        made filesystem-safe; on table columns of unequal length.
    ConfigurationError
        If ``"parquet"`` is requested and ``pyarrow`` cannot be imported.
    """
    chosen = _validate_formats(formats)
    manifest, arrays = result.to_manifest_and_arrays()
    out_dir = Path(directory)
    out_dir.mkdir(parents=True, exist_ok=True)

    tables = _collect_tables(manifest, arrays, degradations=degradations)
    series = _collect_series(manifest, arrays, degradations=degradations)
    written: list[ExportedFile] = []

    if "csv" in chosen:
        for name, (columns, rows) in tables.items():
            written.append(_write_csv(out_dir / f"{name}.csv", columns, rows))
        for station, (columns, rows) in series.items():
            written.append(_write_csv(out_dir / f"series_{station}.csv", columns, rows))
    if "npz" in chosen:
        written.append(_write_npz(out_dir / "arrays.npz", arrays))
    if "parquet" in chosen:
        pyarrow = _import_pyarrow()
        for name, (columns, rows) in tables.items():
            written.append(_write_parquet(pyarrow, out_dir / f"{name}.parquet", columns, rows))
        for station, (columns, rows) in series.items():
            written.append(
                _write_parquet(pyarrow, out_dir / f"series_{station}.parquet", columns, rows)
            )
    if "json" in chosen:
        written.append(_write_result_json(out_dir / "result.json", manifest, arrays))

    created_utc = datetime.now(UTC).isoformat(timespec="seconds")
    document = {
        "export": {
            "created_utc": created_utc,
            "formats": list(chosen),
            "quoss_version": quoss.__version__,
        },
        "files": [f.to_dict() for f in written],
        "result": manifest,
    }
    manifest_file = _write_bytes(out_dir / "manifest.json", _json_bytes(document, indent=2))
    _write_bytes(
        out_dir / "README.txt", _readme([*written, manifest_file], created_utc).encode("utf-8")
    )

    return ExportManifest(
        directory=out_dir, files=tuple(written), formats=chosen, created_utc=created_utc
    )


# --------------------------------------------------------------------------- #
# Finding the tables in a result
# --------------------------------------------------------------------------- #
def _validate_formats(formats: Sequence[str]) -> tuple[str, ...]:
    if isinstance(formats, str) or not formats:
        raise DomainError(f"formats must be a non-empty sequence of {FORMATS}, got {formats!r}.")
    chosen: list[str] = []
    for fmt in formats:
        if fmt not in FORMATS:
            raise DomainError(f"Unknown export format {fmt!r}; choose from {FORMATS}.")
        if fmt not in chosen:
            chosen.append(fmt)
    return tuple(chosen)


def _resolve(node: Any, arrays: Mapping[str, np.ndarray[Any, Any]]) -> Any:
    """Put arrays back where the manifest holds ``{"$array": key}`` markers."""
    if isinstance(node, Mapping):
        if set(node) == {ARRAY_MARKER}:
            key = node[ARRAY_MARKER]
            if key not in arrays:
                raise DomainError(
                    f"manifest references array {key!r} that the arrays mapping does not hold."
                )
            return np.asarray(arrays[key])
        return {k: _resolve(v, arrays) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [_resolve(v, arrays) for v in node]
    return node


def _is_column(value: Any) -> bool:
    if isinstance(value, np.ndarray):
        return value.ndim == 1
    if not isinstance(value, list):
        return False
    return all(not isinstance(item, dict | list | np.ndarray) for item in value)


def _columns_of(node: Mapping[str, Any]) -> dict[str, list[Any]]:
    """Every 1-D column of a mapping, as lists; scalars and nested blocks are skipped."""
    return {
        str(k): (v.tolist() if isinstance(v, np.ndarray) else list(v))
        for k, v in node.items()
        if _is_column(v)
    }


def _table_from_columns(columns: Mapping[str, Sequence[Any]], *, what: str) -> Table:
    lengths = {name: len(col) for name, col in columns.items()}
    if len(set(lengths.values())) != 1:
        raise DomainError(f"Table {what!r}: columns have unequal lengths {lengths}.")
    names = tuple(columns)
    return names, [list(row) for row in zip(*(columns[n] for n in names), strict=True)]


def _table_from_rows(rows: Sequence[Mapping[str, Any]]) -> Table:
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(str(key))
    return tuple(columns), [[row.get(c) for c in columns] for row in rows]


def _collect_tables(
    manifest: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray[Any, Any]],
    *,
    degradations: DegradationLog,
) -> dict[str, Table]:
    tables: dict[str, Table] = {}
    for name, derive in (("passes", _derive_pass_columns), ("daily", _derive_daily_columns)):
        node = _resolve(manifest.get(name), arrays)
        if isinstance(node, list) and node and all(isinstance(r, Mapping) for r in node):
            tables[name] = _table_from_rows(node)
            continue
        columns = _columns_of(node) if isinstance(node, Mapping) else {}
        if columns:
            derive(columns, node, _resolve(manifest.get("monte_carlo"), arrays))
            tables[name] = _table_from_columns(columns, what=name)
            continue
        degradations.info(
            "io.export-table-absent",
            f"The result carries no {name!r} table; {name}.csv/.parquet not written.",
            where=_WHERE,
            table=name,
        )
    return tables


def _derive_pass_columns(
    columns: dict[str, list[Any]], node: Mapping[str, Any], monte_carlo: Any
) -> None:
    n = len(next(iter(columns.values())))
    derived: dict[str, list[Any]] = {"pass_index": list(range(n))}
    epoch_jd = node.get("epoch_jd")
    if isinstance(epoch_jd, int | float):
        for stem in ("start", "end", "culmination"):
            if f"{stem}_s" in columns:
                derived[f"{stem}_jd"] = [
                    float(epoch_jd) + float(t) / _SECONDS_PER_DAY for t in columns[f"{stem}_s"]
                ]
    if "start_s" in columns and "end_s" in columns:
        derived["duration_s"] = [
            float(e) - float(s) for s, e in zip(columns["start_s"], columns["end_s"], strict=True)
        ]
    if "culmination_elevation_rad" in columns:
        derived["culmination_elevation_deg"] = [
            float(rad_to_deg(float(v))) for v in columns["culmination_elevation_rad"]
        ]
    if "finite_bits" in columns:
        derived["has_key"] = [float(v) > 0.0 for v in columns["finite_bits"]]
    if isinstance(monte_carlo, Mapping):
        bits = np.asarray(monte_carlo.get("quantile_bits"))
        quantiles = monte_carlo.get("quantiles", ())
        if bits.ndim == 2 and bits.shape == (len(quantiles), n):
            for q, row in zip(quantiles, bits, strict=True):
                derived[f"finite_bits_q{q!r}"] = row.tolist()
        for key in ("outage_probability", "mean_bits"):
            value = monte_carlo.get(key)
            if isinstance(value, np.ndarray) and value.shape == (n,):
                derived[f"monte_carlo_{key}"] = value.tolist()
    columns.update({k: v for k, v in derived.items() if k not in columns})
    _move_first(columns, "pass_index")


def _derive_daily_columns(
    columns: dict[str, list[Any]], _node: Mapping[str, Any], _monte_carlo: Any
) -> None:
    if "day_number" in columns and "day_utc" not in columns:
        columns["day_utc"] = [_day_utc(d) for d in columns["day_number"]]
        _move_first(columns, "day_utc")
        _move_first(columns, "day_number")


def _day_utc(day_number: Any) -> str:
    """Calendar date of a Julian day number (the day that starts at ``JDN - 0.5``)."""
    year, month, day, *_ = jd_to_calendar(float(day_number) - 0.5)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _move_first(columns: dict[str, list[Any]], name: str) -> None:
    value = columns.pop(name)
    rest = dict(columns)
    columns.clear()
    columns[name] = value
    columns.update(rest)


def _collect_series(
    manifest: Mapping[str, Any],
    arrays: Mapping[str, np.ndarray[Any, Any]],
    *,
    degradations: DegradationLog,
) -> dict[str, Table]:
    node = _resolve(manifest.get("series"), arrays)
    entries = [e for e in node if isinstance(e, Mapping)] if isinstance(node, list) else []
    if not entries:
        degradations.info(
            "io.export-table-absent",
            "The result carries no per-station series; no series_<station> files written.",
            where=_WHERE,
            table="series",
        )
        return {}
    labels: dict[str, str] = {}
    out: dict[str, Table] = {}
    for entry in entries:
        station = str(entry.get("station", ""))
        safe = _SAFE_NAME.sub("_", station)
        if not safe or labels.setdefault(safe, station) != station:
            raise DomainError(
                f"Station {station!r} maps to file name 'series_{safe}', which is empty or "
                f"already taken by {labels.get(safe)!r}; rename one."
            )
        columns: dict[str, list[Any]] = {}
        grid = entry.get("grid")
        if isinstance(grid, Mapping) and _is_column(grid.get("t_s")):
            t_s = np.asarray(grid["t_s"], dtype=np.float64)
            columns["time_s"] = t_s.tolist()
            if isinstance(grid.get("epoch_jd"), int | float):
                columns["jd"] = (float(grid["epoch_jd"]) + t_s / _SECONDS_PER_DAY).tolist()
        for key, block in entry.items():
            if key in ("station", "grid") or not isinstance(block, Mapping):
                continue
            values = block.get("values")
            if not _is_column(values):
                continue
            columns[str(key)] = np.asarray(values).tolist()
            if str(key).endswith("_rad"):
                columns[f"{str(key)[:-4]}_deg"] = np.asarray(
                    rad_to_deg(np.asarray(values, dtype=np.float64))
                ).tolist()
        if not columns:
            raise DomainError(f"Series entry for station {station!r} holds no columns.")
        out[safe] = _table_from_columns(columns, what=f"series/{station}")
    return out


# --------------------------------------------------------------------------- #
# Writers
# --------------------------------------------------------------------------- #
def _json_default(value: Any) -> Any:
    """Let ``json.dumps`` write numpy scalars and arrays that leaked into a manifest.

    The contract says the manifest is JSON-serialisable, but a ``np.float32``
    in a pass record is the easiest mistake to make and the least worth
    failing an export over. Anything else still raises ``TypeError``.
    """
    if isinstance(value, np.bool_):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _json_bytes(document: Any, *, indent: int | None = None) -> bytes:
    text = json.dumps(document, indent=indent, ensure_ascii=False, default=_json_default)
    return (text + "\n").encode("utf-8")


def _cell(value: Any) -> str:
    """Render one CSV cell so that it reads back as the same value (NaN as empty)."""
    if value is None:
        return ""
    if isinstance(value, bool | np.bool_):
        return "true" if value else "false"
    if isinstance(value, int | np.integer):
        return str(int(value))
    if isinstance(value, float | np.floating):
        return "" if np.isnan(value) else repr(float(value))
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=_json_default)


def _write_csv(path: Path, columns: Sequence[str], rows: Sequence[Sequence[Any]]) -> ExportedFile:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(v) for v in row])
    return _describe(path)


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray[Any, Any]]) -> ExportedFile:
    payload: dict[str, Any] = {k: np.asarray(v) for k, v in arrays.items()}
    np.savez_compressed(path, **payload)
    return _describe(path)


def _write_result_json(
    path: Path, manifest: Mapping[str, Any], arrays: Mapping[str, np.ndarray[Any, Any]]
) -> ExportedFile:
    document = {
        "manifest": manifest,
        "arrays": {
            key: {
                "dtype": str(np.asarray(v).dtype),
                "shape": list(np.asarray(v).shape),
                "data": np.asarray(v).tolist(),
            }
            for key, v in arrays.items()
        },
    }
    return _write_bytes(path, _json_bytes(document))


def _import_pyarrow() -> Any:
    try:
        return importlib.import_module("pyarrow")
    except ImportError as exc:
        raise ConfigurationError(
            "Parquet export needs pyarrow, which is not installed: install quoss[export]."
        ) from exc


def _write_parquet(
    pyarrow: Any, path: Path, columns: Sequence[str], rows: Sequence[Sequence[Any]]
) -> ExportedFile:
    parquet = importlib.import_module("pyarrow.parquet")
    data = {name: [row[i] for row in rows] for i, name in enumerate(columns)}
    table = pyarrow.Table.from_pydict(data)
    parquet.write_table(table, str(path))
    return _describe(path)


def _write_bytes(path: Path, data: bytes) -> ExportedFile:
    path.write_bytes(data)
    return _describe(path)


def _describe(path: Path) -> ExportedFile:
    data = path.read_bytes()
    return ExportedFile(
        name=path.name, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data)
    )


def _readme(files: Sequence[ExportedFile], created_utc: str) -> str:
    lines = [
        f"QuOSS {quoss.__version__} result export, {created_utc}.",
        "Every file written by this export, with its SHA-256 (README.txt itself excluded):",
        "",
    ]
    lines.extend(f"{f.sha256}  {f.size_bytes:>10d}  {f.name}" for f in files)
    lines.append("")
    lines.append("manifest.json holds the provenance, warnings, timings and summary of the result.")
    return "\n".join(lines) + "\n"
