"""Tests for :mod:`quoss.io.stations` and the shipped ``src/quoss/data/ogs.yaml``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from quoss.core.errors import DataError
from quoss.io.stations import (
    DEFAULT_CATALOGUE_PATH,
    StationEntry,
    find_station,
    load_station_catalogue,
)

REFERENCE_CASTELLDEFELS = {
    "latitude_deg": 41.2750,
    "longitude_deg": 1.9875,
    "altitude_m": 30.0,
    "receive_aperture_m": 0.75,
}
"""tests/system/reference.py: STATION_LATITUDE_RAD, STATION_LONGITUDE_RAD, STATION_ALTITUDE_KM, RECEIVE_APERTURE_M."""


def entry(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "name": "x",
        "latitude_deg": 1.0,
        "longitude_deg": 2.0,
        "altitude_m": 3.0,
        "receive_aperture_m": 0.5,
        "source": "s",
        "coordinates_precision": "p",
    }
    base.update(overrides)
    return base


def write(tmp_path: Path, document: Any) -> Path:
    path = tmp_path / "ogs.yaml"
    path.write_text(yaml.safe_dump(document) if not isinstance(document, str) else document)
    return path


class TestShippedCatalogue:
    def test_path_is_the_packaged_file(self, data_dir: Path) -> None:
        assert DEFAULT_CATALOGUE_PATH == data_dir / "ogs.yaml"

    def test_names_in_order(self) -> None:
        names = [s.name for s in load_station_catalogue()]
        assert names == ["castelldefels_cttc", "esa_ogs_tenerife", "matera_mlro", "graz_lustbuehel"]

    def test_castelldefels_matches_the_reference_link(self) -> None:
        station = find_station(load_station_catalogue(), "castelldefels_cttc")
        assert station.to_station_spec_kwargs() == {
            "name": "castelldefels_cttc",
            **REFERENCE_CASTELLDEFELS,
        }

    def test_every_entry_cites_a_source_and_a_precision(self) -> None:
        for station in load_station_catalogue():
            assert (
                len(station.source) > 40 and "2026-09-13" in station.source
            ) or "reference.py" in station.source
            assert len(station.coordinates_precision) > 20

    def test_esa_ogs_from_iac_page(self) -> None:
        ogs = find_station(load_station_catalogue(), "esa_ogs_tenerife")
        assert (ogs.latitude_deg, ogs.longitude_deg, ogs.altitude_m, ogs.receive_aperture_m) == (
            28.298,
            -16.5118,
            2400.0,
            1.0,
        )
        assert "iac.es" in ogs.source

    @pytest.mark.parametrize("name", ["matera_mlro", "graz_lustbuehel"])
    def test_unsourced_apertures_are_null_and_must_be_supplied(self, name: str) -> None:
        station = find_station(load_station_catalogue(), name)
        assert station.receive_aperture_m is None and "ilrs.gsfc.nasa.gov" in station.source
        with pytest.raises(DataError, match="no sourced receive aperture"):
            station.to_station_spec_kwargs()
        assert station.to_station_spec_kwargs(receive_aperture_m=1.5)["receive_aperture_m"] == 1.5

    def test_missing_name_lists_available(self) -> None:
        with pytest.raises(DataError, match="Available: castelldefels_cttc, esa_ogs_tenerife"):
            find_station(load_station_catalogue(), "nowhere")


class TestEntryValidation:
    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("name", " ", "name must be a non-empty"),
            ("source", "", "source must be a non-empty"),
            ("coordinates_precision", "", "coordinates_precision must be"),
            ("latitude_deg", 90.5, "latitude_deg"),
            ("latitude_deg", float("nan"), "latitude_deg"),
            ("longitude_deg", -181.0, "longitude_deg"),
            ("altitude_m", 9001.0, "altitude_m"),
            ("altitude_m", -501.0, "altitude_m"),
            ("receive_aperture_m", 0.0, "receive_aperture_m must be positive"),
            ("receive_aperture_m", float("inf"), "receive_aperture_m must be positive"),
        ],
    )
    def test_rejects(self, field: str, value: Any, match: str) -> None:
        with pytest.raises(DataError, match=match):
            StationEntry(**entry(**{field: value}))

    def test_override_must_be_positive(self) -> None:
        with pytest.raises(DataError, match=r"must be positive, got -1\.0"):
            StationEntry(**entry()).to_station_spec_kwargs(receive_aperture_m=-1.0)

    def test_note_defaults_to_empty_and_is_used_in_the_error(self) -> None:
        station = StationEntry(**entry(receive_aperture_m=None))
        assert station.note == ""
        with pytest.raises(DataError, match="see source"):
            station.to_station_spec_kwargs()


class TestLoader:
    def test_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="not found"):
            load_station_catalogue(tmp_path / "none.yaml")

    def test_invalid_yaml(self, tmp_path: Path) -> None:
        with pytest.raises(DataError, match="not valid YAML"):
            load_station_catalogue(write(tmp_path, "stations: [unclosed"))

    @pytest.mark.parametrize(
        ("document", "match"),
        [
            ([1, 2], "must be a mapping"),
            ({"schema_version": 2, "stations": [entry()]}, "schema_version 2"),
            ({"schema_version": 1}, "non-empty 'stations' list"),
            ({"schema_version": 1, "stations": []}, "non-empty 'stations' list"),
            ({"schema_version": 1, "stations": "x"}, "non-empty 'stations' list"),
            ({"schema_version": 1, "stations": [3]}, "entry 0 is not a mapping"),
            ({"schema_version": 1, "stations": [{"name": "a"}]}, "missing \\["),
            ({"schema_version": 1, "stations": [entry(colour="red")]}, "unknown \\['colour'\\]"),
            (
                {"schema_version": 1, "stations": [entry(latitude_deg="41")]},
                "latitude_deg must be a number",
            ),
            (
                {"schema_version": 1, "stations": [entry(altitude_m=True)]},
                "altitude_m must be a number",
            ),
            (
                {"schema_version": 1, "stations": [entry(receive_aperture_m="big")]},
                "receive_aperture_m must be a number",
            ),
            ({"schema_version": 1, "stations": [entry(source=3)]}, "source must be a string"),
            (
                {"schema_version": 1, "stations": [entry(name="a"), entry(name="a")]},
                "duplicate station name 'a'",
            ),
        ],
    )
    def test_rejects(self, tmp_path: Path, document: Any, match: str) -> None:
        with pytest.raises(DataError, match=match):
            load_station_catalogue(write(tmp_path, document))

    def test_minimal_valid_file(self, tmp_path: Path) -> None:
        document = {
            "schema_version": 1,
            "stations": [entry(), entry(name="y", receive_aperture_m=None, note="n")],
        }
        x, y = load_station_catalogue(write(tmp_path, document))
        assert x == StationEntry(**entry())
        assert y.receive_aperture_m is None and y.note == "n"
