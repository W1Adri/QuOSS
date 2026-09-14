"""Tests for :mod:`quoss.io.snapshots`, including the two shipped real snapshots."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quoss.core.errors import DataError, DegradationLog, Severity
from quoss.io.snapshots import (
    DEFAULT_SNAPSHOT_ROOT,
    Snapshot,
    SnapshotManifest,
    list_snapshots,
    load_snapshot,
    payload_sha256,
    save_snapshot,
    snapshot_cloud_cover,
    snapshot_path,
    snapshot_tle,
)

FETCHED = "2026-09-13T16:16:24+00:00"
"""When both shipped snapshots were fetched (curl, HTTP 200; see each manifest note)."""

ISS_TEXT = (
    "ISS (ZARYA)             \r\n"
    "1 25544U 98067A   26256.17555434  .00004898  00000+0  96695-4 0  9992\r\n"
    "2 25544  51.6307 224.6171 0004917 134.6730 225.4659 15.49096932585393\r\n"
)


class TestShippedSnapshots:
    """Both shipped snapshots are real fetches: the manifests say so and the payloads parse."""

    def test_root_is_the_repository_data_directory(self, data_dir: Path) -> None:
        assert DEFAULT_SNAPSHOT_ROOT == data_dir / "snapshots"

    def test_listing(self) -> None:
        assert list_snapshots("tle") == ("iss_zarya",)
        assert list_snapshots("cloud_cover") == ("castelldefels_2025-01-01_02",)
        assert list_snapshots("does_not_exist") == ()

    def test_iss_tle(self, degradations: DegradationLog) -> None:
        snapshot = load_snapshot("tle", "iss_zarya")
        m = snapshot.manifest
        assert not m.is_synthetic
        assert m.source_url == "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"
        assert m.fetched_utc == FETCHED
        assert m.data_version == "25544@2461296.67555434"
        assert "Real fetch" in m.note and "synthetic" not in m.note.lower()
        assert snapshot.payload == ISS_TEXT
        record = snapshot_tle("iss_zarya", degradations=degradations)
        assert record.catalog_number == 25544 and record.name == "ISS (ZARYA)"
        assert record.source_url == m.source_url and record.fetched_utc == FETCHED
        (info,) = degradations.entries
        assert info.code == "io.snapshot-used" and info.severity is Severity.INFO
        assert info.details == {
            "kind": "tle",
            "name": "iss_zarya",
            "fetched_utc": FETCHED,
            "data_version": "25544@2461296.67555434",
            "synthetic": False,
            "source_url": m.source_url,
        }

    def test_castelldefels_cloud_cover(self, degradations: DegradationLog) -> None:
        snapshot = load_snapshot("cloud_cover", "castelldefels_2025-01-01_02")
        m = snapshot.manifest
        assert not m.is_synthetic and m.fetched_utc == FETCHED
        assert m.source_url.startswith(
            "https://archive-api.open-meteo.com/v1/archive?latitude=41.2750&longitude=1.9875"
        )
        assert m.data_version == "open-meteo-archive:2025-01-01:2025-01-02:fetched=2026-09-13"
        series = snapshot_cloud_cover("castelldefels_2025-01-01_02", degradations=degradations)
        assert series.grid.n == 48 and series.grid.step_s == 3600.0
        assert series.cloud_fraction.min() == 0.0 and series.cloud_fraction.max() == 1.0
        assert series.cloud_fraction[:4].tolist() == [1.0, 1.0, 0.96, 0.69]
        assert (series.latitude_deg, series.longitude_deg) == (41.300526, 2.0659971)
        assert [e.code for e in degradations] == ["io.snapshot-used"]


class TestHashing:
    def test_canonical_form_ignores_layout(self) -> None:
        assert payload_sha256({"b": [1, 2], "a": "x"}) == payload_sha256({"a": "x", "b": [1, 2]})
        assert payload_sha256("s\r\n") != payload_sha256("s\n")

    def test_hand_edit_is_detected(self, tmp_path: Path) -> None:
        path = save_snapshot(
            "tle",
            "edited",
            ISS_TEXT,
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="test",
            root=tmp_path,
        )
        document = json.loads(path.read_text())
        document["payload"] = ISS_TEXT.replace("9992", "9990")
        path.write_text(json.dumps(document))
        with pytest.raises(DataError, match=r"payload hash .* != manifest sha256"):
            load_snapshot("tle", "edited", root=tmp_path)


class TestSaveAndLoad:
    def test_round_trip(self, tmp_path: Path) -> None:
        payload = {"hourly": {"time": ["2025-01-01T00:00"], "cloud_cover": [3]}}
        path = save_snapshot(
            "cloud_cover",
            "x",
            payload,
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="why",
            root=tmp_path,
        )
        assert path == tmp_path / "cloud_cover" / "x.json"
        loaded = load_snapshot("cloud_cover", "x", root=tmp_path)
        assert loaded == Snapshot(
            manifest=SnapshotManifest(
                kind="cloud_cover",
                name="x",
                source_url="u",
                fetched_utc=FETCHED,
                sha256=payload_sha256(payload),
                data_version="v",
                note="why",
            ),
            payload=payload,
        )
        assert list_snapshots("cloud_cover", root=tmp_path) == ("x",)

    def test_synthetic_name_needs_synthetic_note(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="note does not say"):
            save_snapshot(
                "tle",
                "synthetic_a",
                "p",
                source_url="u",
                fetched_utc=FETCHED,
                data_version="v",
                note="hand made",
                root=tmp_path,
            )

    def test_synthetic_note_needs_synthetic_name(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="does not start with"):
            save_snapshot(
                "tle",
                "real_a",
                "p",
                source_url="u",
                fetched_utc=FETCHED,
                data_version="v",
                note="Synthetic TLE",
                root=tmp_path,
            )

    def test_synthetic_pair_is_accepted_and_flagged(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        save_snapshot(
            "tle",
            "synthetic_iss",
            ISS_TEXT,
            source_url="written by hand",
            fetched_utc=FETCHED,
            data_version="v",
            note="Synthetic copy for a test.",
            root=tmp_path,
        )
        record = snapshot_tle("synthetic_iss", degradations=degradations, root=tmp_path)
        assert record.catalog_number == 25544
        assert degradations.entries[0].details["synthetic"] is True
        assert "SYNTHETIC" in degradations.entries[0].message

    def test_empty_note(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="non-empty note"):
            save_snapshot(
                "tle",
                "a",
                "p",
                source_url="u",
                fetched_utc=FETCHED,
                data_version="v",
                note="  ",
                root=tmp_path,
            )

    @pytest.mark.parametrize("bad", ["../x", "A", ".hidden", "a/b", "", "a..b"])
    def test_invalid_identifiers(self, bad: str) -> None:
        with pytest.raises(DataError, match="not a valid identifier"):
            snapshot_path("tle", bad)
        with pytest.raises(DataError, match="not a valid identifier"):
            snapshot_path(bad, "ok")

    def test_missing_lists_available(self, tmp_path: Path) -> None:
        save_snapshot(
            "tle",
            "one",
            "p",
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="n",
            root=tmp_path,
        )
        with pytest.raises(DataError, match="Available of this kind: one"):
            load_snapshot("tle", "two", root=tmp_path)
        with pytest.raises(DataError, match="Available of this kind: none"):
            load_snapshot("other", "two", root=tmp_path)

    def _write(self, tmp_path: Path, text: str) -> None:
        (tmp_path / "tle").mkdir(exist_ok=True)
        (tmp_path / "tle" / "bad.json").write_text(text)

    def test_invalid_json(self, tmp_path: Path) -> None:
        self._write(tmp_path, "{not json")
        with pytest.raises(DataError, match="not valid JSON"):
            load_snapshot("tle", "bad", root=tmp_path)

    @pytest.mark.parametrize("document", ["[1]", '{"manifest": {}}', '{"payload": 1}'])
    def test_not_a_snapshot_object(self, tmp_path: Path, document: str) -> None:
        self._write(tmp_path, document)
        with pytest.raises(DataError, match="'manifest' and 'payload'"):
            load_snapshot("tle", "bad", root=tmp_path)

    @pytest.mark.parametrize("manifest", ['"str"', '{"kind": "tle"}'])
    def test_manifest_fields(self, tmp_path: Path, manifest: str) -> None:
        self._write(tmp_path, f'{{"manifest": {manifest}, "payload": "p"}}')
        with pytest.raises(DataError, match="manifest fields"):
            load_snapshot("tle", "bad", root=tmp_path)

    def test_manifest_disagrees_with_path(self, tmp_path: Path) -> None:
        path = save_snapshot(
            "tle",
            "bad",
            "p",
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="n",
            root=tmp_path,
        )
        document = json.loads(path.read_text())
        document["manifest"]["name"] = "other"
        path.write_text(json.dumps(document))
        with pytest.raises(DataError, match="manifest says tle/other"):
            load_snapshot("tle", "bad", root=tmp_path)

    def test_tle_payload_must_be_text(self, tmp_path: Path, degradations: DegradationLog) -> None:
        save_snapshot(
            "tle",
            "obj",
            {"a": 1},
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="n",
            root=tmp_path,
        )
        with pytest.raises(DataError, match="must be the response text, got dict"):
            snapshot_tle("obj", degradations=degradations, root=tmp_path)

    def test_cloud_payload_must_be_object(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        save_snapshot(
            "cloud_cover",
            "txt",
            "p",
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="n",
            root=tmp_path,
        )
        with pytest.raises(DataError, match="must be the response object, got str"):
            snapshot_cloud_cover("txt", degradations=degradations, root=tmp_path)

    def test_unicode_payload_survives(self, tmp_path: Path) -> None:
        payload: dict[str, Any] = {"nota": "Castelldefels — Izaña"}
        save_snapshot(
            "cloud_cover",
            "u",
            payload,
            source_url="u",
            fetched_utc=FETCHED,
            data_version="v",
            note="n",
            root=tmp_path,
        )
        assert load_snapshot("cloud_cover", "u", root=tmp_path).payload == payload
