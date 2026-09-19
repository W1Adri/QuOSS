"""Versioned offline copies of external data, verified on every load.

Why a simulator ships copies of somebody else's data
----------------------------------------------------
``notes/archive/GUIA_REIMPLEMENTACION-v3.md``
§5 sets the requirement in one line: *the
demo cannot depend on CelesTrak or Open-Meteo answering*. A conference demo,
a CI job and a reviewer re-running a figure all need the same TLE and the
same cloud series the paper used, on a machine that may have no network and
on a day when the live answer has changed. A **snapshot** is that: one
response, stored verbatim with a manifest saying where and when it was
obtained, under a name a scenario can refer to.

The layout is ``<root>/<kind>/<name>.json`` with::

    {
      "manifest": {
        "kind": "tle", "name": "iss_zarya",
        "source_url": "https://celestrak.org/...",
        "fetched_utc": "2026-09-13T16:16:24+00:00",
        "sha256": "<hex of the canonical payload>",
        "data_version": "25544@2461296.67555434",
        "note": "..."
      },
      "payload": <the response, verbatim>
    }

Three rules, each defended
--------------------------
**The payload is content-addressed and checked on load.** ``sha256`` is the
SHA-256 of the *canonical* JSON of the payload — sorted keys, no whitespace,
UTF-8 — so it does not depend on how the file was pretty-printed, and
:func:`load_snapshot` recomputes it and raises
:class:`~quoss.core.errors.DataError` on mismatch. The failure this closes is
not tampering; it is a hand edit. A snapshot is a JSON file in the repository,
and the cheapest way to "fix" a demo is to edit a number in it. With the hash,
that edit is a loud error until the manifest is regenerated through
:func:`save_snapshot`, which is the point at which somebody has to write a
``note`` saying why. For a string payload (a TLE) the canonical form is the
JSON string literal, so CRLF line endings and trailing spaces are part of
what is hashed — the ISS snapshot's hash is of exactly the bytes CelesTrak
served, decoded and re-encoded.

**A manifest never claims a fetch that did not happen.** ``fetched_utc`` and
``source_url`` are the record of a real request. A synthetic payload — one
written by hand for a test, or when the network was unavailable — must be
named ``synthetic_*`` and must say so in ``note``; :func:`save_snapshot`
refuses a name starting with ``synthetic_`` whose note does not contain the
word "synthetic", and refuses a name that does *not* start with it while the
note does. Neither of the two snapshots shipped with this stage is synthetic:
both were fetched live on 2026-09-13 (see
``tests/io/test_snapshots.py::TestShippedSnapshots``).

**Using a snapshot is recorded.** :func:`snapshot_tle` and
:func:`snapshot_cloud_cover` write an ``INFO`` degradation
(``io.snapshot-used``) with the snapshot's ``fetched_utc`` and
``data_version`` into the caller's log. A result computed from a snapshot is
a perfectly good result — but a reader of its manifest must be able to tell
that the TLE is from a stated date and not from this morning.

Where ``root`` points
---------------------
The default root is ``snapshots/`` inside the package, :data:`DATA_ROOT`, so it
is the same directory in a checkout and in an installed wheel. It was the
repository's ``<repo>/data/snapshots`` until 2026-09-19, found by walking three
directories up from this file, and that walk left the installed package
pointing above ``site-packages`` at a directory that does not exist -- see
:mod:`quoss.data` for the measurement and ``notes/INCONSISTENCIAS.md`` #18 for
the promise it broke. Every function still takes ``root`` explicitly, which is
what a caller keeping snapshots elsewhere uses.

Examples
--------
>>> from quoss.core.errors import DegradationLog
>>> log = DegradationLog()
>>> record = snapshot_tle("iss_zarya", degradations=log)
>>> record.catalog_number, record.name
(25544, 'ISS (ZARYA)')
>>> log.entries[0].code
'io.snapshot-used'
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from quoss.core.errors import DataError, DegradationLog
from quoss.data import DATA_ROOT
from quoss.io.celestrak import TleRecord, parse_tle_text
from quoss.io.openmeteo import CloudCoverSeries, parse_cloud_cover

__all__ = [
    "DEFAULT_SNAPSHOT_ROOT",
    "Snapshot",
    "SnapshotManifest",
    "list_snapshots",
    "load_snapshot",
    "payload_sha256",
    "save_snapshot",
    "snapshot_cloud_cover",
    "snapshot_path",
    "snapshot_tle",
]

DEFAULT_SNAPSHOT_ROOT = DATA_ROOT / "snapshots"
"""``<package>/data/snapshots``, the same directory in a checkout and in an installation."""

_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.-]*$")
_SYNTHETIC_PREFIX = "synthetic_"
_WHERE_TLE = "quoss.io.snapshots.snapshot_tle"
_WHERE_CLOUD = "quoss.io.snapshots.snapshot_cloud_cover"


@dataclass(frozen=True, slots=True)
class SnapshotManifest:
    """The provenance half of a snapshot file.

    Parameters
    ----------
    kind : str
        Directory under the root: ``"tle"``, ``"cloud_cover"``, or another
        lowercase identifier.
    name : str
        File stem. Lowercase letters, digits, ``_``, ``-``, ``.``; must start
        with ``synthetic_`` if and only if the payload was not fetched.
    source_url : str
        The request that produced the payload, or a statement of origin for a
        synthetic one.
    fetched_utc : str
        ISO-8601 UTC time of the real request; for a synthetic snapshot, the
        time it was written.
    sha256 : str
        SHA-256 of the canonical JSON of the payload; see :func:`payload_sha256`.
    data_version : str
        The string a result's ``Provenance.data_versions`` should carry.
    note : str
        Free text: why this snapshot exists, what it is for, and — mandatory
        for a synthetic one — the word "synthetic".
    """

    kind: str
    name: str
    source_url: str
    fetched_utc: str
    sha256: str
    data_version: str
    note: str

    @property
    def is_synthetic(self) -> bool:
        """True if the name carries the ``synthetic_`` prefix."""
        return self.name.startswith(_SYNTHETIC_PREFIX)


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A loaded snapshot: manifest plus the payload it vouches for.

    Parameters
    ----------
    manifest : SnapshotManifest
        As read from the file, hash already verified.
    payload : Any
        The decoded JSON payload — a string for a TLE, a mapping for an
        Open-Meteo response.
    """

    manifest: SnapshotManifest
    payload: Any


def payload_sha256(payload: Any) -> str:
    """SHA-256 of the canonical JSON encoding of ``payload``.

    Canonical means ``sort_keys=True``, ``separators=(",", ":")``,
    ``ensure_ascii=False``, UTF-8: a form that two writers produce identically
    from equal payloads, whatever indentation the file on disk uses.

    Parameters
    ----------
    payload : Any
        Anything ``json.dumps`` accepts.

    Returns
    -------
    str
        64 hex characters.

    Examples
    --------
    Key order and whitespace do not matter, values do:

    >>> payload_sha256({"a": 1, "b": 2}) == payload_sha256({"b": 2, "a": 1})
    True
    >>> payload_sha256({"a": 1}) == payload_sha256({"a": 2})
    False
    """
    return hashlib.sha256(_canonical(payload)).hexdigest()


def snapshot_path(kind: str, name: str, *, root: Path | None = None) -> Path:
    """Return ``<root>/<kind>/<name>.json`` after validating both identifiers.

    Parameters
    ----------
    kind, name : str
        See :class:`SnapshotManifest`.
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default.

    Returns
    -------
    Path
        The file path (which need not exist).

    Raises
    ------
    DataError
        If ``kind`` or ``name`` contains anything but lowercase letters,
        digits, ``_``, ``-`` and ``.``, or starts with a ``.``. The check is
        what stops ``"../../etc"`` from being a snapshot name.
    """
    for label, value in (("kind", kind), ("name", name)):
        if not _NAME_PATTERN.match(value) or ".." in value:
            raise DataError(
                f"Snapshot {label} {value!r} is not a valid identifier "
                f"(lowercase letters, digits, '_', '-', '.'; no '..')."
            )
    base = DEFAULT_SNAPSHOT_ROOT if root is None else Path(root)
    return base / kind / f"{name}.json"


def list_snapshots(kind: str, *, root: Path | None = None) -> tuple[str, ...]:
    """Return the names of every snapshot of one kind, sorted.

    Parameters
    ----------
    kind : str
        The kind directory.
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default.

    Returns
    -------
    tuple[str, ...]
        File stems; empty if the directory does not exist.
    """
    directory = snapshot_path(kind, "placeholder", root=root).parent
    if not directory.is_dir():
        return ()
    return tuple(sorted(p.stem for p in directory.glob("*.json")))


def save_snapshot(
    kind: str,
    name: str,
    payload: Any,
    *,
    source_url: str,
    fetched_utc: str,
    data_version: str,
    note: str,
    root: Path | None = None,
) -> Path:
    """Write a snapshot file with a freshly computed manifest.

    Parameters
    ----------
    kind, name : str
        See :class:`SnapshotManifest`.
    payload : Any
        JSON-serialisable content, stored verbatim.
    source_url, fetched_utc, data_version, note : str
        Manifest fields. ``note`` must not be empty: a snapshot with no stated
        purpose is one nobody will dare delete or trust.
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default. Created if absent.

    Returns
    -------
    Path
        The file written.

    Raises
    ------
    DataError
        On an invalid identifier, an empty note, or a name/note pair that
        disagrees about being synthetic (see the module docstring).
    """
    path = snapshot_path(kind, name, root=root)
    if not note.strip():
        raise DataError(f"Snapshot {kind}/{name} needs a non-empty note.")
    says_synthetic = "synthetic" in note.lower()
    if name.startswith(_SYNTHETIC_PREFIX) and not says_synthetic:
        raise DataError(
            f"Snapshot name {name!r} carries the synthetic_ prefix but the note does not say "
            f"'synthetic'. Say it, so the manifest cannot be read as a real fetch."
        )
    if says_synthetic and not name.startswith(_SYNTHETIC_PREFIX):
        raise DataError(
            f"Snapshot note says 'synthetic' but the name {name!r} does not start with "
            f"'{_SYNTHETIC_PREFIX}'. A synthetic payload must be visible from its filename."
        )
    manifest = SnapshotManifest(
        kind=kind,
        name=name,
        source_url=source_url,
        fetched_utc=fetched_utc,
        sha256=payload_sha256(payload),
        data_version=data_version,
        note=note,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    document = {"manifest": asdict(manifest), "payload": payload}
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_snapshot(kind: str, name: str, *, root: Path | None = None) -> Snapshot:
    """Read a snapshot and verify its payload against the manifest hash.

    Parameters
    ----------
    kind, name : str
        See :class:`SnapshotManifest`.
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default.

    Returns
    -------
    Snapshot
        Manifest and payload.

    Raises
    ------
    DataError
        If the file is missing, is not JSON, lacks ``manifest``/``payload``,
        has a manifest with missing or extra fields, has a manifest whose
        ``kind``/``name`` disagree with the path, or whose ``sha256`` does not
        match the payload.
    """
    path = snapshot_path(kind, name, root=root)
    if not path.is_file():
        available = ", ".join(list_snapshots(kind, root=root)) or "none"
        raise DataError(
            f"No snapshot {kind}/{name} at {path}. Available of this kind: {available}."
        )
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise DataError(f"Snapshot {path} is not valid JSON: {exc}") from exc
    if not isinstance(document, Mapping) or "manifest" not in document or "payload" not in document:
        raise DataError(f"Snapshot {path} must be an object with 'manifest' and 'payload'.")
    raw_manifest = document["manifest"]
    expected_fields = set(SnapshotManifest.__dataclass_fields__)
    if not isinstance(raw_manifest, Mapping) or set(raw_manifest) != expected_fields:
        present = set(raw_manifest) if isinstance(raw_manifest, Mapping) else set()
        raise DataError(
            f"Snapshot {path} manifest fields {sorted(present)} != expected {sorted(expected_fields)}."
        )
    manifest = SnapshotManifest(**{k: str(v) for k, v in raw_manifest.items()})
    if manifest.kind != kind or manifest.name != name:
        raise DataError(
            f"Snapshot {path} manifest says {manifest.kind}/{manifest.name}, "
            f"but was loaded as {kind}/{name}."
        )
    payload = document["payload"]
    actual = payload_sha256(payload)
    if actual != manifest.sha256:
        raise DataError(
            f"Snapshot {path} payload hash {actual} != manifest sha256 {manifest.sha256}. "
            f"The payload was edited after the manifest was written; regenerate it through "
            f"save_snapshot with a note saying why."
        )
    return Snapshot(manifest=manifest, payload=payload)


def snapshot_tle(name: str, *, degradations: DegradationLog, root: Path | None = None) -> TleRecord:
    """Load a ``tle`` snapshot as a validated :class:`~quoss.io.celestrak.TleRecord`.

    Parameters
    ----------
    name : str
        Snapshot name, e.g. ``"iss_zarya"``.
    degradations : DegradationLog
        Receives ``io.snapshot-used`` (INFO).
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default.

    Returns
    -------
    TleRecord
        With ``source_url`` and ``fetched_utc`` from the manifest.

    Raises
    ------
    DataError
        From :func:`load_snapshot`, if the payload is not a string, or if the
        text is not a TLE.
    """
    snapshot = load_snapshot("tle", name, root=root)
    if not isinstance(snapshot.payload, str):
        raise DataError(
            f"TLE snapshot {name!r} payload must be the response text, got {type(snapshot.payload).__name__}."
        )
    _record_use(snapshot.manifest, degradations, where=_WHERE_TLE)
    return parse_tle_text(
        snapshot.payload,
        source_url=snapshot.manifest.source_url,
        fetched_utc=snapshot.manifest.fetched_utc,
    )


def snapshot_cloud_cover(
    name: str, *, degradations: DegradationLog, root: Path | None = None
) -> CloudCoverSeries:
    """Load a ``cloud_cover`` snapshot as a :class:`~quoss.io.openmeteo.CloudCoverSeries`.

    Parameters
    ----------
    name : str
        Snapshot name, e.g. ``"castelldefels_2025-01-01_02"``.
    degradations : DegradationLog
        Receives ``io.snapshot-used`` (INFO).
    root : Path, optional
        :data:`DEFAULT_SNAPSHOT_ROOT` by default.

    Returns
    -------
    CloudCoverSeries
        Parsed by :func:`~quoss.io.openmeteo.parse_cloud_cover`. The
        grid-offset INFO is not recorded here, because the requested
        coordinates are not part of the response; the snapshot's ``note`` is
        where they are stated.

    Raises
    ------
    DataError
        From :func:`load_snapshot`, if the payload is not an object, or from
        the parser.
    """
    snapshot = load_snapshot("cloud_cover", name, root=root)
    if not isinstance(snapshot.payload, Mapping):
        raise DataError(
            f"Cloud-cover snapshot {name!r} payload must be the response object, got {type(snapshot.payload).__name__}."
        )
    _record_use(snapshot.manifest, degradations, where=_WHERE_CLOUD)
    return parse_cloud_cover(
        snapshot.payload,
        source_url=snapshot.manifest.source_url,
        fetched_utc=snapshot.manifest.fetched_utc,
        degradations=degradations,
    )


def _record_use(manifest: SnapshotManifest, degradations: DegradationLog, *, where: str) -> None:
    degradations.info(
        "io.snapshot-used",
        f"Using offline snapshot {manifest.kind}/{manifest.name} "
        f"({'SYNTHETIC, ' if manifest.is_synthetic else ''}fetched {manifest.fetched_utc}, "
        f"data version {manifest.data_version}).",
        where=where,
        kind=manifest.kind,
        name=manifest.name,
        fetched_utc=manifest.fetched_utc,
        data_version=manifest.data_version,
        synthetic=manifest.is_synthetic,
        source_url=manifest.source_url,
    )


def _canonical(payload: Any) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )
