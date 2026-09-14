"""Tests for `quoss.scenario.result`.

- ``TestProvenance`` — every field filled, ``git_commit`` never raises, round trip.
- ``TestStageTimings`` — frozen mapping, refuses negative and non-finite.
- ``TestContainersRefuseWrongShapes`` — every ``DomainError`` of the containers.
- ``TestRoundTrip`` — ``to_dict``/``from_dict`` and ``to_manifest_and_arrays``/
  ``from_manifest_and_arrays`` for a result without optional stages and one
  with all three; strict JSON (NaN as ``null``); dtypes preserved through a
  real ``.npz``; an empty pass table keeps its integer dtype.
- ``TestViews`` — pass records, series lookup, derived properties.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import quoss
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import TimeGrid, TimeSeries
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import Scenario
from quoss.scenario.result import (
    ARRAY_MARKER,
    DailyResults,
    MonteCarloResults,
    MultiStationResults,
    PassRecord,
    PassResults,
    Provenance,
    RelayResults,
    SeriesResults,
    SimulationResult,
    StageTimings,
    git_commit,
)

EPOCH_JD = 2_460_676.5


def two_station_scenario() -> Scenario:
    data = reference_castelldefels().model_dump(mode="json")
    second = {
        **data["stations"][0],
        "name": "skinakas",
        "latitude_deg": 35.2118,
        "longitude_deg": 24.8981,
    }
    data["stations"] = [data["stations"][0], second]
    data["monte_carlo"] = {
        "realisations": 50,
        "seed": 7,
        "scintillation_correlation_time_s": 0.01,
        "pointing_correlation_time_s": 0.1,
    }
    data["multi_station"] = {"policy": "sum"}
    data["relay"] = {"pairs": [["castelldefels", "skinakas"]]}
    return Scenario.model_validate(data)


def grid(n: int = 11) -> TimeGrid:
    return TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=float(n - 1), step_s=1.0)


def series(station: str, g: TimeGrid) -> SeriesResults:
    n = g.n
    channel = np.full(n, np.nan)
    channel[3:8] = np.linspace(1e-3, 2e-3, 5)
    return SeriesResults(
        station=station,
        grid=g,
        elevation_rad=TimeSeries(g, np.linspace(-0.2, 0.8, n), name="elevation", unit="rad"),
        azimuth_rad=TimeSeries(g, np.linspace(0.0, 3.0, n), name="azimuth", unit="rad"),
        range_km=TimeSeries(g, np.linspace(2000.0, 700.0, n), name="range", unit="km"),
        transmittance=TimeSeries(g, channel, name="transmittance", unit=""),
        loss_total_db=TimeSeries(g, -10.0 * np.log10(channel), name="loss_total", unit="dB"),
        noise_per_gate=TimeSeries(
            g, np.where(np.isnan(channel), np.nan, 2.4e-6), name="noise", unit=""
        ),
        asymptotic_secure_bit_s=TimeSeries(g, channel * 1e5, name="skr", unit="bit/s"),
    )


def passes(station_names: tuple[str, ...]) -> PassResults:
    n = len(station_names)
    return PassResults(
        epoch_jd=EPOCH_JD,
        station=station_names,
        satellite_index=np.zeros(n, dtype=np.int64),
        start_s=np.arange(n, dtype=np.float64) * 1000.0 + 3.0,
        end_s=np.arange(n, dtype=np.float64) * 1000.0 + 7.5,
        culmination_s=np.arange(n, dtype=np.float64) * 1000.0 + 5.2,
        culmination_elevation_rad=np.full(n, 0.8),
        finite_bits=np.array([190_581.0, 0.0][:n]),
        asymptotic_bits=np.array([1_548_341.3, 319_898.3][:n]),
        truncated_start=np.zeros(n, dtype=bool),
        truncated_end=np.array([False, True][:n]),
        day_number=np.full(n, 2_460_677, dtype=np.int64),
    )


def daily() -> DailyResults:
    return DailyResults(
        day_number=np.array([2_460_677]),
        finite_bits=np.array([432_985.0]),
        asymptotic_bits=np.array([3_776_681.0]),
        pass_count=np.array([4]),
        passes_with_key=np.array([2]),
        seconds=np.array([1799.79]),
        composed_correctness=4e-10,
        composed_secrecy=4e-10,
        protocol="bb84-decoy",
    )


def provenance(scenario: Scenario, seed: int | None = None) -> Provenance:
    return Provenance(
        scenario_hash=scenario_hash(scenario),
        scenario_name=scenario.name,
        code_version="0.1.0",
        git_commit="0" * 40,
        python_version="3.13.0",
        numpy_version="2.0.0",
        scipy_version="1.14.0",
        data_versions={"tle": "2026-09-13"},
        seed=seed,
        created_utc="2026-09-13T12:00:00Z",
    )


def minimal_result() -> SimulationResult:
    scenario = reference_castelldefels()
    g = grid()
    log = DegradationLog()
    log.warn(
        "passes.truncated",
        "one pass cut by the grid edge",
        where="quoss.system.passes.find_passes",
        count=1,
    )
    return SimulationResult(
        scenario=scenario,
        provenance=provenance(scenario),
        series=[series("castelldefels", g)],
        passes=passes(("castelldefels",)),
        daily=daily(),
        monte_carlo=None,
        multi_station=None,
        relay=None,
        warnings=log.to_dicts(),
        timings=StageTimings({"orbit": 0.5, "channel": 1.25}),
    )


def full_result() -> SimulationResult:
    scenario = two_station_scenario()
    g = grid()
    names = ("castelldefels", "skinakas")
    return SimulationResult(
        scenario=scenario,
        provenance=provenance(scenario, seed=7),
        series=[series(n, g) for n in names],
        passes=passes(names),
        daily=daily(),
        monte_carlo=MonteCarloResults(
            quantiles=(0.05, 0.5, 0.95),
            quantile_bits=np.array([[1.0e5, 0.0], [1.9e5, 0.0], [2.5e5, 1.0e3]]),
            outage_probability=np.array([0.02, 0.9]),
            mean_bits=np.array([1.85e5, 50.0]),
            realisations=50,
            seed=7,
        ),
        multi_station=MultiStationResults(
            station_names=names,
            bits_per_station_day=np.array([[432_985.0], [120_000.0]]),
            scheduled_pass_count=np.array([4, 3]),
            policy="sum",
        ),
        relay=RelayResults(
            pairs=(("castelldefels", "skinakas"),),
            delivered_bits_per_day=np.array([[100_000.0]]),
            mean_latency_s=np.array([5400.0]),
            residuals=np.array([20_000.0]),
        ),
        warnings=[],
        timings=StageTimings({}),
    )


def assert_results_equal(a: SimulationResult, b: SimulationResult) -> None:
    assert a.scenario == b.scenario
    assert a.provenance == b.provenance
    assert a.timings == b.timings
    assert a.warnings == b.warnings
    assert_trees_equal(a._tree(), b._tree())


def assert_trees_equal(x: Any, y: Any) -> None:
    if isinstance(x, np.ndarray):
        assert isinstance(y, np.ndarray)
        assert x.dtype == y.dtype, (x.dtype, y.dtype)
        assert np.array_equal(x, y, equal_nan=True)
    elif isinstance(x, dict):
        assert set(x) == set(y)
        for k in x:
            assert_trees_equal(x[k], y[k])
    elif isinstance(x, list | tuple):
        assert len(x) == len(y)
        for u, v in zip(x, y, strict=True):
            assert_trees_equal(u, v)
    else:
        assert x == y


# --------------------------------------------------------------------------- #
class TestProvenance:
    def test_collect_fills_every_field(self) -> None:
        scenario = reference_castelldefels()
        p = Provenance.collect(scenario, seed=42, data_versions={"tle": "v1"})
        assert p.scenario_hash == scenario_hash(scenario)
        assert p.scenario_name == scenario.name
        assert p.code_version == quoss.__version__
        assert p.git_commit is None or re.fullmatch(r"[0-9a-f]{40}", p.git_commit)
        assert re.fullmatch(r"\d+\.\d+\.\d+.*", p.python_version)
        assert p.numpy_version == np.__version__
        assert p.scipy_version
        assert dict(p.data_versions) == {"tle": "v1"}
        assert p.seed == 42
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", p.created_utc)

    def test_git_commit_in_this_checkout(self) -> None:
        commit = git_commit()
        assert commit is None or re.fullmatch(r"[0-9a-f]{40}", commit)

    def test_git_commit_outside_a_repository_is_none(self, tmp_path: Path) -> None:
        assert git_commit(tmp_path) is None

    def test_git_commit_without_git_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def missing(*args: Any, **kwargs: Any) -> Any:
            raise FileNotFoundError("git")

        monkeypatch.setattr(subprocess, "run", missing)
        assert git_commit() is None

    def test_git_commit_that_hangs_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def hangs(*args: Any, **kwargs: Any) -> Any:
            raise subprocess.TimeoutExpired(cmd="git", timeout=5.0)

        monkeypatch.setattr(subprocess, "run", hangs)
        assert git_commit() is None

    def test_git_commit_with_empty_output_is_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def empty(*args: Any, **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(args=["git"], returncode=0, stdout="\n", stderr="")

        monkeypatch.setattr(subprocess, "run", empty)
        assert git_commit() is None

    def test_round_trip(self) -> None:
        p = provenance(reference_castelldefels(), seed=3)
        assert Provenance.from_dict(json.loads(json.dumps(p.to_dict()))) == p
        q = provenance(reference_castelldefels(), seed=None)
        q = Provenance(**{**q.to_dict(), "git_commit": None})
        assert Provenance.from_dict(q.to_dict()) == q

    def test_data_versions_are_frozen(self) -> None:
        p = provenance(reference_castelldefels())
        with pytest.raises(TypeError):
            p.data_versions["x"] = "y"  # type: ignore[index]


class TestStageTimings:
    def test_total_and_dict(self) -> None:
        t = StageTimings({"a": 1.0, "b": 2.5})
        assert t.total_s == 3.5
        assert StageTimings.from_dict(t.to_dict()) == t
        assert list(t.seconds) == ["a", "b"]

    def test_frozen(self) -> None:
        with pytest.raises(TypeError):
            StageTimings({"a": 1.0}).seconds["a"] = 2.0  # type: ignore[index]

    @pytest.mark.parametrize("bad", [-1.0, float("nan"), float("inf")])
    def test_refuses_impossible_durations(self, bad: float) -> None:
        with pytest.raises(DomainError, match="non-finite or negative"):
            StageTimings({"a": bad})


# --------------------------------------------------------------------------- #
class TestContainersRefuseWrongShapes:
    def test_pass_results(self) -> None:
        good = passes(("a", "b"))
        with pytest.raises(DomainError, match=r"PassResults\.start_s must have one entry per pass"):
            PassResults(**{**_fields(good), "start_s": np.zeros(3)})

    def test_daily_results(self) -> None:
        good = daily()
        with pytest.raises(DomainError, match=r"DailyResults\.seconds must have one entry per day"):
            DailyResults(**{**_fields(good), "seconds": np.zeros(2)})

    def test_series_results_on_another_axis(self) -> None:
        g = grid()
        other = TimeGrid.uniform(epoch_jd=EPOCH_JD + 1.0, duration_s=10.0, step_s=1.0)
        s = series("a", g)
        with pytest.raises(DomainError, match="different axis"):
            SeriesResults(
                **{**_fields(s), "range_km": TimeSeries(other, np.zeros(11), name="r", unit="km")}
            )

    def test_monte_carlo_results(self) -> None:
        with pytest.raises(DomainError, match=r"shape \(len\(quantiles\)=3, n_passes\)"):
            MonteCarloResults(
                quantiles=(0.05, 0.5, 0.95),
                quantile_bits=np.zeros((2, 4)),
                outage_probability=np.zeros(4),
                mean_bits=np.zeros(4),
                realisations=10,
                seed=1,
            )
        with pytest.raises(DomainError, match="mean_bits must have one entry per pass"):
            MonteCarloResults(
                quantiles=(0.5,),
                quantile_bits=np.zeros((1, 4)),
                outage_probability=np.zeros(4),
                mean_bits=np.zeros(3),
                realisations=10,
                seed=1,
            )
        with pytest.raises(DomainError, match="realisations must be positive"):
            MonteCarloResults(
                quantiles=(0.5,),
                quantile_bits=np.zeros((1, 4)),
                outage_probability=np.zeros(4),
                mean_bits=np.zeros(4),
                realisations=0,
                seed=1,
            )

    def test_multi_station_results(self) -> None:
        with pytest.raises(DomainError, match=r"shape \(n_stations=2, n_days\)"):
            MultiStationResults(
                station_names=("a", "b"),
                bits_per_station_day=np.zeros((3, 1)),
                scheduled_pass_count=np.zeros(2, dtype=np.int64),
                policy="sum",
            )
        with pytest.raises(
            DomainError, match="scheduled_pass_count must have one entry per station"
        ):
            MultiStationResults(
                station_names=("a", "b"),
                bits_per_station_day=np.zeros((2, 1)),
                scheduled_pass_count=np.zeros(3, dtype=np.int64),
                policy="sum",
            )

    def test_relay_results(self) -> None:
        with pytest.raises(DomainError, match=r"shape \(n_pairs=1, n_days\)"):
            RelayResults(
                pairs=(("a", "b"),),
                delivered_bits_per_day=np.zeros(1),
                mean_latency_s=np.zeros(1),
                residuals=np.zeros(1),
            )
        with pytest.raises(DomainError, match="residuals must have one entry per pair"):
            RelayResults(
                pairs=(("a", "b"),),
                delivered_bits_per_day=np.zeros((1, 1)),
                mean_latency_s=np.zeros(1),
                residuals=np.zeros(2),
            )

    def test_simulation_result_series_must_cover_the_scenarios_stations(self) -> None:
        r = minimal_result()
        with pytest.raises(DomainError, match="series cover stations"):
            SimulationResult(**{**_fields(r), "series": [series("elsewhere", grid())]})

    def test_simulation_result_monte_carlo_must_match_the_pass_table(self) -> None:
        r = full_result()
        assert r.monte_carlo is not None
        with pytest.raises(DomainError, match="monte_carlo has 2 passes, the pass table has 1"):
            SimulationResult(
                **{
                    **_fields(r),
                    "passes": passes(("castelldefels",)),
                    "series": [r.series[0]],
                    "scenario": reference_castelldefels(),
                }
            )


def _fields(obj: Any) -> dict[str, Any]:
    return {name: getattr(obj, name) for name in obj.__slots__}


# --------------------------------------------------------------------------- #
class TestRoundTrip:
    @pytest.mark.parametrize("builder", [minimal_result, full_result])
    def test_to_dict_from_dict(self, builder: Any) -> None:
        result = builder()
        data = result.to_dict()
        text = json.dumps(data, allow_nan=False)  # strict JSON: NaN went out as null
        assert_results_equal(SimulationResult.from_dict(json.loads(text)), result)

    def test_nan_becomes_null_and_comes_back(self) -> None:
        result = minimal_result()
        data = result.to_dict()
        values = data["series"][0]["transmittance"]["values"]
        assert values[0] is None and values[3] is not None
        back = SimulationResult.from_dict(data)
        assert np.isnan(back.series[0].transmittance.values[0])

    @pytest.mark.parametrize("builder", [minimal_result, full_result])
    def test_manifest_and_arrays(self, builder: Any, tmp_path: Path) -> None:
        result = builder()
        manifest, arrays = result.to_manifest_and_arrays()
        json.dumps(manifest, allow_nan=False)
        assert "series.0.elevation_rad.values" in arrays
        assert "passes.start_s" in arrays
        assert "series.0.grid.t_s" in arrays
        assert manifest["passes"]["start_s"] == {ARRAY_MARKER: "passes.start_s"}
        assert arrays["passes.satellite_index"].dtype == np.int64
        assert arrays["passes.truncated_end"].dtype == np.bool_
        # Through a real .npz, the way the cache stores them.
        path = tmp_path / "arrays.npz"
        np.savez(path, **arrays)
        with np.load(path) as loaded:
            back = SimulationResult.from_manifest_and_arrays(
                json.loads(json.dumps(manifest)), {k: loaded[k] for k in loaded.files}
            )
        assert_results_equal(back, result)

    def test_manifest_arrays_are_the_originals_and_the_dict_arrays_are_lists(self) -> None:
        result = full_result()
        _, arrays = result.to_manifest_and_arrays()
        assert "monte_carlo.quantile_bits" in arrays and arrays[
            "monte_carlo.quantile_bits"
        ].shape == (3, 2)
        assert "relay.delivered_bits_per_day" in arrays
        assert "multi_station.bits_per_station_day" in arrays
        assert isinstance(result.to_dict()["monte_carlo"]["quantile_bits"], list)

    def test_a_missing_array_is_refused(self) -> None:
        manifest, arrays = minimal_result().to_manifest_and_arrays()
        del arrays["passes.start_s"]
        with pytest.raises(
            DomainError, match=r"references array 'passes\.start_s' that was not supplied"
        ):
            SimulationResult.from_manifest_and_arrays(manifest, arrays)

    def test_an_empty_pass_table_keeps_its_dtypes(self) -> None:
        """Zero passes is a legitimate day; ``[]`` must not come back as float64."""
        empty = PassResults(
            epoch_jd=EPOCH_JD,
            station=(),
            satellite_index=np.zeros(0, dtype=np.int64),
            start_s=np.zeros(0),
            end_s=np.zeros(0),
            culmination_s=np.zeros(0),
            culmination_elevation_rad=np.zeros(0),
            finite_bits=np.zeros(0),
            asymptotic_bits=np.zeros(0),
            truncated_start=np.zeros(0, dtype=bool),
            truncated_end=np.zeros(0, dtype=bool),
            day_number=np.zeros(0, dtype=np.int64),
        )
        back = PassResults._from_tree(json.loads(json.dumps(_listified(empty._tree()))))
        assert back.n_passes == 0
        assert back.satellite_index.dtype == np.int64
        assert back.truncated_end.dtype == np.bool_

    def test_arrays_are_read_only(self) -> None:
        result = minimal_result()
        with pytest.raises(ValueError, match="read-only"):
            result.passes.start_s[0] = 1.0
        with pytest.raises(ValueError, match="read-only"):
            result.passes.satellite_index[0] = 1


def _listified(tree: Any) -> Any:
    from quoss.scenario.result import _listify

    return _listify(tree)


# --------------------------------------------------------------------------- #
class TestViews:
    def test_pass_records_without_monte_carlo(self) -> None:
        records = list(minimal_result().pass_records())
        assert len(records) == 1
        r = records[0]
        assert isinstance(r, PassRecord)
        assert r.station == "castelldefels" and r.pass_index == 0
        assert r.duration_s == pytest.approx(4.5)
        assert r.start_jd == EPOCH_JD + 3.0 / 86_400.0
        assert r.has_key and not r.truncated
        assert r.monte_carlo_quantile_bits is None

    def test_pass_records_with_monte_carlo(self) -> None:
        records = list(full_result().pass_records())
        assert records[0].monte_carlo_quantile_bits == (1.0e5, 1.9e5, 2.5e5)
        assert records[1].monte_carlo_quantile_bits == (0.0, 0.0, 1.0e3)
        assert not records[1].has_key and records[1].truncated

    def test_series_for(self) -> None:
        result = full_result()
        assert result.series_for("skinakas").station == "skinakas"
        with pytest.raises(KeyError, match="no series for station 'x'"):
            result.series_for("x")

    def test_derived_pass_properties(self) -> None:
        p = passes(("a", "b"))
        assert np.array_equal(p.has_key, [True, False])
        np.testing.assert_allclose(p.duration_s, [4.5, 4.5])
        # A Julian date near 2.46e6 resolves to 2.46e6 * 2^-52 = 5.5e-10 days (47 us);
        # a difference of two of them carries twice that. Derived, not tuned.
        jd_resolution = EPOCH_JD * 2**-52
        np.testing.assert_allclose(
            p.end_jd - p.start_jd, 4.5 / 86_400.0, rtol=0.0, atol=2 * jd_resolution
        )
        np.testing.assert_allclose(
            p.culmination_jd, EPOCH_JD + p.culmination_s / 86_400.0, rtol=0.0, atol=jd_resolution
        )
        assert daily().n_days == 1

    def test_warnings_are_copied_not_aliased(self) -> None:
        warnings = [{"code": "x", "details": {"k": 1}}]
        result = SimulationResult(**{**_fields(minimal_result()), "warnings": warnings})
        warnings[0]["details"]["k"] = 2  # type: ignore[index]
        assert result.warnings[0]["details"]["k"] == 1
