"""Tests for :mod:`quoss.io.export`, against the real :class:`SimulationResult`."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

import quoss
from quoss.core.errors import ConfigurationError, DegradationLog, DomainError, Severity
from quoss.core.types import TimeGrid, TimeSeries
from quoss.io.export import ARRAY_MARKER, FORMATS, ExportedFile, export_result
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.result import (
    DailyResults,
    MonteCarloResults,
    PassResults,
    Provenance,
    SeriesResults,
    SimulationResult,
    StageTimings,
)

EPOCH_JD = 2_460_676.5
"""2025-01-01 00:00 UTC, the reference epoch of the suite."""

DAY_NUMBER = 2_460_677
"""JDN of 2025-01-01 (tests/system/reference.py::REFERENCE_DAY_NUMBER)."""

FINITE_BITS = (190_581.0, 0.0)
ASYMPTOTIC_BITS = (1_548_341.0, 319_898.0)
"""Passes 1 and 2 of the reference day (docs/adr/0011, decision 2 table)."""


def build_result(*, monte_carlo: bool = True) -> SimulationResult:
    """Build a small but complete result on the reference scenario: 5 samples, 2 passes, 1 day."""
    scenario = reference_castelldefels()
    (station,) = scenario.station_names
    grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=4.0, n=5)
    nan = np.nan

    def ts(name: str, unit: str, values: list[float]) -> TimeSeries:
        return TimeSeries(grid, np.array(values, dtype=np.float64), name=name, unit=unit)

    series = SeriesResults(
        station=station,
        grid=grid,
        elevation_rad=ts("elevation", "rad", [-0.1, 0.2, 0.9, 0.3, -0.05]),
        azimuth_rad=ts("azimuth", "rad", [0.0, 1.0, 2.0, 3.0, 4.0]),
        range_km=ts("range", "km", [2500.0, 1500.0, 720.0, 1400.0, 2400.0]),
        range_rate_km_s=ts("range_rate", "km/s", [-6.0, -4.0, 0.0, 4.0, 6.0]),
        doppler_shift_hz=ts("doppler_shift", "Hz", [3.9e9, 2.6e9, 0.0, -2.6e9, -3.9e9]),
        doppler_rate_hz_s=ts("doppler_rate", "Hz/s", [-1.3e9, -1.3e9, -1.7e9, -1.3e9, -1.3e9]),
        point_ahead_angle_rad=ts("point_ahead", "rad", [2.6e-5, 4.0e-5, 5.0e-5, 4.0e-5, 2.6e-5]),
        transmittance=ts("transmittance", "", [nan, 1e-4, 3e-3, 2e-4, nan]),
        loss_total_db=ts("loss_total", "dB", [nan, 40.0, 25.2, 37.0, nan]),
        noise_per_gate=ts("noise_per_gate", "", [nan, 1e-6, 2e-6, 1e-6, nan]),
        asymptotic_secure_bit_s=ts("skr", "bit/s", [nan, 100.0, 5000.0, 250.0, nan]),
    )
    passes = PassResults(
        epoch_jd=EPOCH_JD,
        station=(station, station),
        satellite_index=np.array([0, 0]),
        start_s=np.array([0.5, 2.5]),
        end_s=np.array([1.5, 3.75]),
        culmination_s=np.array([1.0, 3.0]),
        culmination_elevation_rad=np.array([0.9, 0.3]),
        peak_one_sided_doppler_hz=np.array([3.9e9, 2.6e9]),
        doppler_excursion_hz=np.array([7.8e9, 5.2e9]),
        peak_doppler_slew_hz_s=np.array([1.7e9, 1.3e9]),
        max_point_ahead_angle_rad=np.array([5.0e-5, 4.0e-5]),
        min_point_ahead_angle_rad=np.array([2.6e-5, 2.6e-5]),
        finite_bits=np.array(FINITE_BITS),
        asymptotic_bits=np.array(ASYMPTOTIC_BITS),
        truncated_start=np.array([False, False]),
        truncated_end=np.array([False, True]),
        day_number=np.array([DAY_NUMBER, DAY_NUMBER]),
    )
    daily = DailyResults(
        day_number=np.array([DAY_NUMBER]),
        finite_bits=np.array([sum(FINITE_BITS)]),
        asymptotic_bits=np.array([sum(ASYMPTOTIC_BITS)]),
        pass_count=np.array([2]),
        passes_with_key=np.array([1]),
        seconds=np.array([2.25]),
        composed_correctness=2e-10,
        composed_secrecy=2e-10,
        protocol="bb84_decoy",
    )
    mc = (
        MonteCarloResults(
            quantiles=(0.05, 0.5, 0.95),
            quantile_bits=np.array([[150_000.0, 0.0], [190_000.0, 0.0], [230_000.0, 12_000.0]]),
            outage_probability=np.array([0.0, 0.6]),
            mean_bits=np.array([190_100.0, 3_000.0]),
            realisations=100,
            seed=7,
        )
        if monte_carlo
        else None
    )
    provenance = Provenance(
        scenario_hash="0" * 64,
        scenario_name=scenario.name,
        code_version=quoss.__version__,
        git_commit=None,
        python_version="3.13.0",
        numpy_version=np.__version__,
        scipy_version="1.0.0",
        data_versions={"tle": "25544@2461296.67555434"},
        seed=7,
        created_utc="2026-09-13T00:00:00Z",
    )
    return SimulationResult(
        scenario=scenario,
        provenance=provenance,
        series=(series,),
        passes=passes,
        daily=daily,
        monte_carlo=mc,
        multi_station=None,
        relay=None,
        warnings=[
            {
                "code": "io.snapshot-used",
                "severity": "info",
                "message": "m",
                "where": "w",
                "details": {},
            }
        ],
        timings=StageTimings({"orbit": 0.01, "passes": 0.5}),
    )


class FakeResult:
    """A hand-shaped manifest/arrays pair, for the edge cases a real result cannot produce."""

    def __init__(self, manifest: dict[str, Any], arrays: dict[str, Any] | None = None) -> None:
        self.manifest = manifest
        self.arrays = arrays or {}

    def to_manifest_and_arrays(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return self.manifest, self.arrays


def read_csv(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="") as handle:
        rows = list(csv.reader(handle))
    return rows[0], rows[1:]


class TestFormats:
    @pytest.mark.parametrize("formats", [("xlsx",), ("json", "netcdf")])
    def test_unknown_format(
        self, tmp_path: Path, degradations: DegradationLog, formats: tuple[str, ...]
    ) -> None:
        with pytest.raises(DomainError, match="Unknown export format"):
            export_result(build_result(), tmp_path, formats=formats, degradations=degradations)
        assert not list(tmp_path.iterdir())

    @pytest.mark.parametrize("formats", [(), "csv"])
    def test_empty_or_string(
        self, tmp_path: Path, degradations: DegradationLog, formats: Any
    ) -> None:
        with pytest.raises(DomainError, match="non-empty sequence"):
            export_result(build_result(), tmp_path, formats=formats, degradations=degradations)

    def test_duplicates_collapse(self, tmp_path: Path, degradations: DegradationLog) -> None:
        out = export_result(
            build_result(), tmp_path, formats=("npz", "npz", "csv"), degradations=degradations
        )
        assert out.formats == ("npz", "csv")


class TestRealResultAllFormats:
    """Export the real result in every format and read each file back."""

    @pytest.fixture
    def exported(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> tuple[Path, Any, SimulationResult]:
        result = build_result()
        out = export_result(result, tmp_path / "run", formats=FORMATS, degradations=degradations)
        assert len(degradations) == 0
        return tmp_path / "run", out, result

    def test_file_list_and_hashes(self, exported: tuple[Path, Any, SimulationResult]) -> None:
        directory, out, result = exported
        assert [f.name for f in out.files] == [
            "passes.csv",
            "daily.csv",
            "series_castelldefels.csv",
            "arrays.npz",
            "passes.parquet",
            "daily.parquet",
            "series_castelldefels.parquet",
            "result.json",
        ]
        for f in out.files:
            data = (directory / f.name).read_bytes()
            assert f == ExportedFile(f.name, hashlib.sha256(data).hexdigest(), len(data))
        manifest = json.loads(out.manifest_path.read_text())
        assert manifest["files"] == [f.to_dict() for f in out.files]
        assert manifest["export"]["formats"] == list(FORMATS)
        assert manifest["export"]["quoss_version"] == quoss.__version__
        assert manifest["export"]["created_utc"] == out.created_utc
        assert manifest["result"] == result.to_manifest_and_arrays()[0]
        assert manifest["result"]["provenance"]["data_versions"] == {
            "tle": "25544@2461296.67555434"
        }
        assert manifest["result"]["passes"]["finite_bits"] == {ARRAY_MARKER: "passes.finite_bits"}
        readme = (directory / "README.txt").read_text()
        assert "manifest.json" in readme and all(f.sha256 in readme for f in out.files)
        assert out.directory == directory

    def test_passes_csv(self, exported: tuple[Path, Any, SimulationResult]) -> None:
        directory, _, _ = exported
        header, rows = read_csv(directory / "passes.csv")
        assert header == [
            "pass_index",
            "station",
            "satellite_index",
            "start_s",
            "end_s",
            "culmination_s",
            "culmination_elevation_rad",
            "peak_one_sided_doppler_hz",
            "doppler_excursion_hz",
            "peak_doppler_slew_hz_s",
            "max_point_ahead_angle_rad",
            "min_point_ahead_angle_rad",
            "finite_bits",
            "asymptotic_bits",
            "truncated_start",
            "truncated_end",
            "day_number",
            "start_jd",
            "end_jd",
            "culmination_jd",
            "duration_s",
            "culmination_elevation_deg",
            "has_key",
            "finite_bits_q0.05",
            "finite_bits_q0.5",
            "finite_bits_q0.95",
            "monte_carlo_outage_probability",
            "monte_carlo_mean_bits",
        ]
        row = dict(zip(header, rows[1], strict=True))
        assert row["pass_index"] == "1" and row["station"] == "castelldefels"
        assert row["finite_bits"] == "0.0" and row["asymptotic_bits"] == "319898.0"
        assert row["has_key"] == "false" and row["truncated_end"] == "true"
        assert float(row["start_jd"]) == EPOCH_JD + 2.5 / 86400.0
        assert row["duration_s"] == "1.25"
        assert float(row["culmination_elevation_deg"]) == float(np.rad2deg(0.3))
        assert (
            row["finite_bits_q0.95"] == "12000.0" and row["monte_carlo_outage_probability"] == "0.6"
        )
        assert dict(zip(header, rows[0], strict=True))["has_key"] == "true"

    def test_daily_csv(self, exported: tuple[Path, Any, SimulationResult]) -> None:
        directory, _, _ = exported
        header, rows = read_csv(directory / "daily.csv")
        assert header == [
            "day_number",
            "day_utc",
            "finite_bits",
            "asymptotic_bits",
            "pass_count",
            "passes_with_key",
            "seconds",
        ]
        assert rows == [["2460677", "2025-01-01", "190581.0", "1868239.0", "2", "1", "2.25"]]

    def test_series_csv_nan_as_empty_and_degrees_derived(
        self, exported: tuple[Path, Any, SimulationResult]
    ) -> None:
        directory, _, result = exported
        header, rows = read_csv(directory / "series_castelldefels.csv")
        assert header == [
            "time_s",
            "jd",
            "elevation_rad",
            "elevation_deg",
            "azimuth_rad",
            "azimuth_deg",
            "range_km",
            "range_rate_km_s",
            "doppler_shift_hz",
            "doppler_rate_hz_s",
            "point_ahead_angle_rad",
            "point_ahead_angle_deg",
            "transmittance",
            "loss_total_db",
            "noise_per_gate",
            "asymptotic_secure_bit_s",
        ]
        assert len(rows) == 5
        assert rows[0][0] == "0.0" and float(rows[0][1]) == EPOCH_JD
        transmittance = header.index("transmittance")
        # NaN outside the pass, repr inside. The acquisition series beside it are
        # geometry, so they are finite in both rows: that asymmetry is the schema's
        # claim that a satellite has a position even where the link has no budget.
        assert rows[0][transmittance] == "" and rows[2][transmittance] == "0.003"
        doppler = header.index("doppler_shift_hz")
        assert rows[0][doppler] != "" and rows[2][doppler] != ""
        series = result.series[0]
        for i, row in enumerate(rows):
            assert float(row[2]) == series.elevation_rad.values[i]
            assert float(row[3]) == float(np.rad2deg(series.elevation_rad.values[i]))

    def test_npz_and_manifest_rebuild_the_result(
        self, exported: tuple[Path, Any, SimulationResult]
    ) -> None:
        directory, out, result = exported
        manifest = json.loads(out.manifest_path.read_text())["result"]
        with np.load(directory / "arrays.npz") as loaded:
            rebuilt = SimulationResult.from_manifest_and_arrays(manifest, dict(loaded.items()))
        assert rebuilt.to_dict() == result.to_dict()

    def test_result_json_rebuilds_the_result(
        self, exported: tuple[Path, Any, SimulationResult]
    ) -> None:
        directory, _, result = exported
        document = json.loads((directory / "result.json").read_text())
        arrays = {k: np.asarray(v["data"], dtype=v["dtype"]) for k, v in document["arrays"].items()}
        entry = document["arrays"]["passes.finite_bits"]
        assert entry == {"dtype": "float64", "shape": [2], "data": [190581.0, 0.0]}
        rebuilt = SimulationResult.from_manifest_and_arrays(document["manifest"], arrays)
        assert rebuilt.passes.finite_bits.tolist() == list(FINITE_BITS)
        assert rebuilt.to_dict() == result.to_dict()

    def test_parquet_reads_back(self, exported: tuple[Path, Any, SimulationResult]) -> None:
        pq = pytest.importorskip("pyarrow.parquet")
        directory, _, _ = exported
        passes = pq.read_table(directory / "passes.parquet").to_pydict()
        assert passes["station"] == ["castelldefels", "castelldefels"]
        assert passes["finite_bits"] == list(FINITE_BITS) and passes["has_key"] == [True, False]
        series = pq.read_table(directory / "series_castelldefels.parquet").to_pydict()
        assert series["range_km"] == [2500.0, 1500.0, 720.0, 1400.0, 2400.0]
        assert np.isnan(series["transmittance"][0]) and series["transmittance"][2] == 3e-3
        daily = pq.read_table(directory / "daily.parquet").to_pydict()
        assert daily["day_utc"] == ["2025-01-01"] and daily["finite_bits"] == [190581.0]


class TestWithoutMonteCarlo:
    def test_no_quantile_columns(self, tmp_path: Path, degradations: DegradationLog) -> None:
        export_result(
            build_result(monte_carlo=False), tmp_path, formats=("csv",), degradations=degradations
        )
        header, _ = read_csv(tmp_path / "passes.csv")
        assert not any(h.startswith(("finite_bits_q", "monte_carlo_")) for h in header)
        assert header[-1] == "has_key"


class TestParquetWithoutPyarrow:
    def test_configuration_error_and_nothing_written(
        self, tmp_path: Path, degradations: DegradationLog, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setitem(sys.modules, "pyarrow", None)
        with pytest.raises(ConfigurationError, match=r"install quoss\[export\]"):
            export_result(
                build_result(), tmp_path, formats=("csv", "parquet"), degradations=degradations
            )
        assert not list(tmp_path.glob("*.parquet"))
        assert not (tmp_path / "manifest.json").exists()


class TestTablesFromHandMadeManifests:
    def test_rows_of_dicts_and_absent_tables(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        manifest = {
            "passes": [
                {"station": "a", "bits": 1, "x": None},
                {"station": "b", "bits": 2, "y": 0.5},
            ]
        }
        export_result(FakeResult(manifest), tmp_path, formats=("csv",), degradations=degradations)
        assert read_csv(tmp_path / "passes.csv") == (
            ["station", "bits", "x", "y"],
            [["a", "1", "", ""], ["b", "2", "", "0.5"]],
        )
        assert [(e.details["table"], e.severity) for e in degradations] == [
            ("daily", Severity.INFO),
            ("series", Severity.INFO),
        ]
        assert sorted(p.name for p in tmp_path.iterdir()) == [
            "README.txt",
            "manifest.json",
            "passes.csv",
        ]

    @pytest.mark.parametrize(
        "value", [[], {}, "rows", {"epoch_jd": 1.0}, [3, {"a": 1}], [[1, 2]], None]
    )
    def test_unusable_tables_are_absent(
        self, tmp_path: Path, degradations: DegradationLog, value: Any
    ) -> None:
        # A series list holding a mapping is a malformed entry, not an absent table
        # (see test_bad_series), so that case is emptied for the series slot.
        series = [] if value == [3, {"a": 1}] else value
        export_result(
            FakeResult({"passes": value, "daily": value, "series": series}),
            tmp_path,
            formats=("csv",),
            degradations=degradations,
        )
        assert [e.details["table"] for e in degradations] == ["passes", "daily", "series"]

    def test_marker_without_array(self, tmp_path: Path, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match=r"references array 'passes\.bits'"):
            export_result(
                FakeResult({"passes": {"bits": {ARRAY_MARKER: "passes.bits"}}}),
                tmp_path,
                formats=("csv",),
                degradations=degradations,
            )

    def test_unequal_columns(self, tmp_path: Path, degradations: DegradationLog) -> None:
        manifest = {"daily": {"a": [1, 2], "b": {ARRAY_MARKER: "daily.b"}}}
        with pytest.raises(DomainError, match="unequal lengths"):
            export_result(
                FakeResult(manifest, {"daily.b": np.array([1.0])}),
                tmp_path,
                formats=("csv",),
                degradations=degradations,
            )

    def test_two_dimensional_arrays_are_not_columns(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        manifest = {
            "passes": {
                "a": [1, 2],
                "m": {ARRAY_MARKER: "passes.m"},
                "nested": {"k": [1]},
                "lists": [[1], [2]],
            }
        }
        export_result(
            FakeResult(manifest, {"passes.m": np.zeros((2, 2))}),
            tmp_path,
            formats=("csv",),
            degradations=degradations,
        )
        assert read_csv(tmp_path / "passes.csv")[0] == ["pass_index", "a"]

    def test_pass_derivations_need_their_inputs(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        manifest = {
            "passes": {
                "epoch_jd": "not a number",
                "start_s": [0.0],
                "finite_bits": [1.0],
                "has_key": [False],
            },
            "monte_carlo": {
                "quantiles": [0.5],
                "quantile_bits": {ARRAY_MARKER: "mc.q"},
                "mean_bits": {ARRAY_MARKER: "mc.m"},
            },
        }
        arrays = {"mc.q": np.zeros((1, 3)), "mc.m": np.zeros(3)}
        export_result(
            FakeResult(manifest, arrays), tmp_path, formats=("csv",), degradations=degradations
        )
        header, rows = read_csv(tmp_path / "passes.csv")
        # No epoch -> no *_jd; no end_s -> no duration; a caller-supplied has_key is kept;
        # Monte Carlo blocks whose shape does not match the pass axis are ignored.
        assert header == ["pass_index", "start_s", "finite_bits", "has_key"]
        assert rows == [["0", "0.0", "1.0", "false"]]

    def test_only_present_instants_get_a_julian_date(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        manifest = {"passes": {"epoch_jd": EPOCH_JD, "start_s": [86400.0]}}
        export_result(FakeResult(manifest), tmp_path, formats=("csv",), degradations=degradations)
        assert read_csv(tmp_path / "passes.csv") == (
            ["pass_index", "start_s", "start_jd"],
            [["0", "86400.0", repr(EPOCH_JD + 1.0)]],
        )

    def test_day_utc_not_duplicated(self, tmp_path: Path, degradations: DegradationLog) -> None:
        export_result(
            FakeResult({"daily": {"day_number": [DAY_NUMBER], "day_utc": ["x"]}}),
            tmp_path,
            formats=("csv",),
            degradations=degradations,
        )
        assert read_csv(tmp_path / "daily.csv") == (["day_number", "day_utc"], [["2460677", "x"]])

    def test_series_entries(self, tmp_path: Path, degradations: DegradationLog) -> None:
        series = [
            {
                "station": "Izaña OGS",
                "grid": {"epoch_jd": 1.0, "t_s": [0.0, 1.0]},
                "elevation_rad": {"values": [0.0, 1.0]},
            },
            {
                "station": "b",
                "grid": {"t_s": {ARRAY_MARKER: "s.t"}},
                "range_km": {"unit": "km", "values": {ARRAY_MARKER: "s.r"}},
                "scalar": 3,
                "bad": {"values": 5},
            },
            "not an entry",
        ]
        arrays = {"s.t": np.array([0.0]), "s.r": np.array([700.0])}
        export_result(
            FakeResult({"series": series}, arrays),
            tmp_path,
            formats=("csv",),
            degradations=degradations,
        )
        assert read_csv(tmp_path / "series_Iza_a_OGS.csv") == (
            ["time_s", "jd", "elevation_rad", "elevation_deg"],
            [
                ["0.0", "1.0", "0.0", "0.0"],
                ["1.0", str(1.0 + 1.0 / 86400.0), "1.0", repr(float(np.rad2deg(1.0)))],
            ],
        )
        assert read_csv(tmp_path / "series_b.csv") == (["time_s", "range_km"], [["0.0", "700.0"]])

    @pytest.mark.parametrize(
        ("series", "match"),
        [
            (
                [
                    {"station": "a b", "grid": {"t_s": [0.0]}},
                    {"station": "a_b", "grid": {"t_s": [0.0]}},
                ],
                "already taken by 'a b'",
            ),
            ([{"station": "", "grid": {"t_s": [0.0]}}], "is empty"),
            ([{"a": 1}], "is empty"),
            ([{"station": "s", "grid": {}}], "holds no columns"),
            (
                [{"station": "s", "grid": {"t_s": [0.0, 1.0]}, "x": {"values": [1.0]}}],
                "unequal lengths",
            ),
        ],
    )
    def test_bad_series(
        self, tmp_path: Path, degradations: DegradationLog, series: list[Any], match: str
    ) -> None:
        with pytest.raises(DomainError, match=match):
            export_result(
                FakeResult({"series": series}),
                tmp_path,
                formats=("csv",),
                degradations=degradations,
            )

    def test_cells_of_every_kind(self, tmp_path: Path, degradations: DegradationLog) -> None:
        row = {
            "none": None,
            "bool": True,
            "npbool": np.bool_(False),
            "int": 3,
            "npint": np.int64(-4),
            "float": 2.5,
            "npfloat": np.float64(1e-300),
            "nan": float("nan"),
            "str": "a,b",
            "list": [1, "x"],
            "nested": {
                "n": np.int64(2),
                "f": np.float32(0.5),
                "b": np.bool_(True),
                "a": np.array([1.5]),
            },
        }
        export_result(
            FakeResult({"passes": [row]}),
            tmp_path,
            formats=("csv", "json"),
            degradations=degradations,
        )
        header, rows = read_csv(tmp_path / "passes.csv")
        assert header == list(row)
        assert rows == [
            [
                "",
                "true",
                "false",
                "3",
                "-4",
                "2.5",
                "1e-300",
                "",
                "a,b",
                '[1, "x"]',
                '{"a": [1.5], "b": true, "f": 0.5, "n": 2}',
            ]
        ]
        manifest = json.loads((tmp_path / "manifest.json").read_text())
        assert manifest["result"]["passes"][0]["nested"] == {
            "n": 2,
            "f": 0.5,
            "b": True,
            "a": [1.5],
        }
        assert (
            json.loads((tmp_path / "result.json").read_text())["manifest"]["passes"][0]["npint"]
            == -4
        )

    def test_unserialisable_manifest_value_still_raises(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        with pytest.raises(TypeError, match="not JSON serializable"):
            export_result(
                FakeResult({"passes": [{"x": object()}]}),
                tmp_path,
                formats=("csv",),
                degradations=degradations,
            )

    def test_existing_files_are_overwritten(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        (tmp_path / "arrays.npz").write_bytes(b"old")
        export_result(build_result(), tmp_path, formats=("npz",), degradations=degradations)
        assert (tmp_path / "arrays.npz").read_bytes() != b"old"


finite_floats = st.floats(allow_nan=False, width=64)


class TestRoundTrips:
    """Property-based: every finite float written to CSV or npz reads back *equal*."""

    @settings(max_examples=50, deadline=None)
    @given(
        values=st.lists(
            st.tuples(finite_floats, st.integers(min_value=-(2**62), max_value=2**62)),
            min_size=1,
            max_size=40,
        )
    )
    def test_csv_round_trip(
        self, values: list[tuple[float, int]], tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        tmp = tmp_path_factory.mktemp("csv")
        rows = [{"x": x, "n": n} for x, n in values]
        export_result(
            FakeResult({"passes": rows}), tmp, formats=("csv",), degradations=DegradationLog()
        )
        header, read = read_csv(tmp / "passes.csv")
        assert header == ["x", "n"]
        for (x, n), row in zip(values, read, strict=True):
            assert float(row[0]) == x and int(row[1]) == n

    @settings(max_examples=25, deadline=None)
    @given(values=st.lists(finite_floats, min_size=1, max_size=200))
    def test_npz_round_trip(
        self, values: list[float], tmp_path_factory: pytest.TempPathFactory
    ) -> None:
        tmp = tmp_path_factory.mktemp("npz")
        array = np.array(values, dtype=np.float64)
        export_result(
            FakeResult({}, {"passes.v": array}),
            tmp,
            formats=("npz",),
            degradations=DegradationLog(),
        )
        with np.load(tmp / "arrays.npz") as loaded:
            np.testing.assert_array_equal(loaded["passes.v"], array)
