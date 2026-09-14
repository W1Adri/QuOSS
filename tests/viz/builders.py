"""Hand-built `SimulationResult`s for the viz tests, so they need neither the engine nor time.

The pass table copies the *shape* of the reference day — four passes, finite
key 190 581, 0, 242 404, 0 bits against asymptotic 1 548 341.3, 319 898.3,
1 709 160.4, 199 280.8 (`tests/system/reference.py`) — because the plots'
special cases (a zero-key pass, asymptotic bars nine times taller than finite
ones) are exactly the ones that day exercises. The numbers here are fixture
values fed *into* a plot; nothing in `tests/viz` claims them as a measurement,
except the integration tests that run the real engine.

The series are synthetic on a 60 s grid: an elevation bump per pass that
crosses the 10 deg mask at the pass edges, a rate defined only inside passes
(NaN elsewhere, as the engine writes it), and an azimuth sweeping through the
pass.
"""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from typing import Any

import numpy as np
import pytest

from quoss.core.types import FloatArray, TimeGrid, TimeSeries
from quoss.core.units import deg_to_rad
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import Scenario
from quoss.scenario.result import (
    DailyResults,
    MonteCarloResults,
    MultiStationResults,
    PassResults,
    Provenance,
    RelayResults,
    SeriesResults,
    SimulationResult,
    StageTimings,
)

EPOCH_JD = 2_460_676.5
DAY_NUMBER = 2_460_677
STEP_S = 60.0

FINITE_BITS = (190_581.0, 0.0, 242_404.0, 0.0)
ASYMPTOTIC_BITS = (1_548_341.3, 319_898.3, 1_709_160.4, 199_280.8)
START_S = (20_040.0, 26_100.0, 60_060.0, 66_120.0)
DURATION_S = (540.0, 360.0, 600.0, 300.0)
PEAK_ELEVATION_DEG = (52.9, 17.6, 58.8, 14.2)
MASK_DEG = 10.0

QUANTILES = (0.05, 0.5, 0.95)
QUANTILE_BITS = (
    (329_229.0, 0.0, 395_324.0, 0.0),
    (345_658.0, 0.0, 412_512.0, 0.0),
    (361_865.0, 0.0, 429_023.0, 0.0),
)

DEGRADED_WARNING: Mapping[str, Any] = {
    "code": "channel.background-interpolated",
    "message": "ITU table interpolated.",
    "severity": "degraded",
    "where": "tests.viz.builders",
    "details": {},
}
INFO_WARNING: Mapping[str, Any] = {
    "code": "engine.cache-hit",
    "message": "served from cache.",
    "severity": "info",
    "where": "tests.viz.builders",
    "details": {},
}


def _grid() -> TimeGrid:
    return TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=86_400.0, step_s=STEP_S)


def _series(station: str, grid: TimeGrid, pass_indices: Sequence[int]) -> SeriesResults:
    """Build one station's series, with a bump only over the passes that station owns.

    ``pass_indices`` indexes into ``START_S``/``DURATION_S``/``PEAK_ELEVATION_DEG``
    rather than carrying the start times, because the three tuples are parallel and
    a station generally owns a *subset* of the four passes: zipping the subset of
    start times against the full duration and peak tuples would pair pass 2's start
    with pass 0's duration, which is how this builder silently drew the wrong day.
    """
    t = grid.t_s
    elevation_deg = np.full(t.shape, -30.0)
    azimuth_rad = np.zeros(t.shape)
    rate = np.full(t.shape, np.nan)
    for index in pass_indices:
        start = START_S[index]
        duration = DURATION_S[index]
        peak = PEAK_ELEVATION_DEG[index]
        middle = start + duration / 2.0
        # A parabola through (edges, MASK_DEG) and (middle, peak), extended a little
        # beyond the window so the curve visibly crosses the mask.
        u = (t - middle) / (duration / 2.0)
        bump = peak - (peak - MASK_DEG) * u**2
        near = np.abs(u) <= 1.6
        elevation_deg = np.where(near, np.maximum(elevation_deg, bump), elevation_deg)
        inside = np.abs(u) <= 1.0
        azimuth_rad = np.where(inside, deg_to_rad(180.0 + 90.0 * u), azimuth_rad)
        rate = np.where(inside, 500.0 + 2_000.0 * (1.0 - u**2), rate)
    channel = np.where(np.isnan(rate), np.nan, 1e-3)
    return SeriesResults(
        station=station,
        grid=grid,
        elevation_rad=TimeSeries(
            grid, np.asarray(deg_to_rad(elevation_deg)), name="elevation", unit="rad"
        ),
        azimuth_rad=TimeSeries(grid, azimuth_rad, name="azimuth", unit="rad"),
        range_km=TimeSeries(grid, np.full(t.shape, 1500.0), name="range", unit="km"),
        range_rate_km_s=TimeSeries(grid, np.full(t.shape, -3.0), name="range_rate", unit="km/s"),
        doppler_shift_hz=TimeSeries(grid, np.full(t.shape, 1.9e9), name="doppler_shift", unit="Hz"),
        doppler_rate_hz_s=TimeSeries(
            grid, np.full(t.shape, -1.0e7), name="doppler_rate", unit="Hz/s"
        ),
        point_ahead_angle_rad=TimeSeries(
            grid, np.full(t.shape, 4.0e-5), name="point_ahead", unit="rad"
        ),
        transmittance=TimeSeries(grid, channel, name="transmittance", unit=""),
        loss_total_db=TimeSeries(
            grid, np.where(np.isnan(rate), np.nan, 30.0), name="loss", unit="dB"
        ),
        noise_per_gate=TimeSeries(
            grid, np.where(np.isnan(rate), np.nan, 2e-6), name="noise", unit=""
        ),
        asymptotic_secure_bit_s=TimeSeries(grid, rate, name="skr", unit="bit/s"),
    )


def _provenance(scenario: Scenario, seed: int | None) -> Provenance:
    return Provenance(
        scenario_hash=scenario_hash(scenario),
        scenario_name=scenario.name,
        code_version="0.0.0",
        git_commit=None,
        python_version="3.13.0",
        numpy_version="2.0.0",
        scipy_version="1.14.0",
        data_versions={},
        seed=seed,
        created_utc="2026-09-13T00:00:00Z",
    )


def make_result(
    *,
    scenario: Scenario | None = None,
    monte_carlo: bool = False,
    multi_station: bool = False,
    relay: bool = False,
    warnings: Sequence[Mapping[str, Any]] = (),
    finite_bits: Sequence[float] = FINITE_BITS,
    truncated_end: Sequence[bool] = (False, False, False, False),
    second_station: str | None = None,
    no_passes: bool = False,
    no_days: bool = False,
    quantiles: Sequence[float] = QUANTILES,
    composed: bool = True,
) -> SimulationResult:
    """Return a reference-shaped result; every optional section is opt-in."""
    base = reference_castelldefels() if scenario is None else scenario
    if second_station is not None:
        data = base.model_dump(mode="python")
        data["stations"] = [data["stations"][0], {**data["stations"][0], "name": second_station}]
        base = Scenario.model_validate(data)
    grid = _grid()
    names = base.station_names
    n = 0 if no_passes else 4
    stations = tuple(names[i % len(names)] for i in range(n))
    starts = np.asarray(START_S[:n])
    series = [
        _series(name, grid, [i for i, owner in enumerate(stations) if owner == name])
        for name in names
    ]
    passes = PassResults(
        epoch_jd=EPOCH_JD,
        station=stations,
        satellite_index=np.zeros(n, dtype=np.int64),
        start_s=starts,
        end_s=starts + np.asarray(DURATION_S[:n]),
        culmination_s=starts + np.asarray(DURATION_S[:n]) / 2.0,
        culmination_elevation_rad=np.asarray(deg_to_rad(np.asarray(PEAK_ELEVATION_DEG[:n]))),
        max_abs_doppler_hz=np.full(n, 4.2e9),
        max_abs_doppler_rate_hz_s=np.full(n, 3.8e7),
        max_point_ahead_angle_rad=np.full(n, 5.06e-5),
        min_point_ahead_angle_rad=np.full(n, 2.6e-5),
        finite_bits=np.asarray(finite_bits[:n], dtype=np.float64),
        asymptotic_bits=np.asarray(ASYMPTOTIC_BITS[:n]),
        truncated_start=np.zeros(n, dtype=bool),
        truncated_end=np.asarray(truncated_end[:n], dtype=bool),
        day_number=np.full(n, DAY_NUMBER, dtype=np.int64),
    )
    days = 0 if no_days else 1
    daily = DailyResults(
        day_number=np.full(days, DAY_NUMBER, dtype=np.int64),
        finite_bits=np.full(days, float(np.sum(finite_bits[:n]))),
        asymptotic_bits=np.full(days, float(np.sum(ASYMPTOTIC_BITS[:n]))),
        pass_count=np.full(days, n, dtype=np.int64),
        passes_with_key=np.full(
            days, int(np.count_nonzero(np.asarray(finite_bits[:n]))), dtype=np.int64
        ),
        seconds=np.full(days, float(np.sum(DURATION_S[:n]))),
        composed_correctness=4e-10 if composed else None,
        composed_secrecy=4e-10 if composed else None,
        protocol="bb84-decoy",
    )
    mc = None
    if monte_carlo:
        rows = {0.05: QUANTILE_BITS[0], 0.5: QUANTILE_BITS[1], 0.95: QUANTILE_BITS[2]}
        mc = MonteCarloResults(
            quantiles=tuple(quantiles),
            quantile_bits=np.asarray([rows[q][:n] for q in quantiles]).reshape(len(quantiles), n),
            outage_probability=np.asarray([0.0, 1.0, 0.0, 1.0][:n]),
            mean_bits=np.asarray([345_700.0, 0.0, 412_600.0, 0.0][:n]),
            realisations=1000,
            seed=20_260_913,
        )
    ms = (
        MultiStationResults(
            station_names=("castelldefels", "calar_alto", "ogs_tenerife"),
            bits_per_station_day=np.asarray([[432_985.0], [0.0], [562_697.0]]),
            scheduled_pass_count=np.asarray([2, 0, 1]),
            policy="best_available",
        )
        if multi_station
        else None
    )
    rl = (
        RelayResults(
            pairs=(("castelldefels", "ogs_tenerife"), ("castelldefels", "calar_alto")),
            delivered_bits_per_day=np.asarray([[432_985.0], [0.0]]),
            mean_latency_s=np.asarray([15_199.0, np.nan]),
            residuals=np.asarray([129_712.0, 0.0]),
        )
        if relay
        else None
    )
    return SimulationResult(
        scenario=base,
        provenance=_provenance(base, 20_260_913 if monte_carlo else None),
        series=series,
        passes=passes,
        daily=daily,
        monte_carlo=mc,
        multi_station=ms,
        relay=rl,
        warnings=list(warnings),
        timings=StageTimings({"total": 0.0}),
    )


def xdata(line: Any) -> FloatArray:
    """Return a line's x data as a float array.

    ``Line2D.get_xdata`` is annotated as the union of everything matplotlib
    accepts as data, so passing its result straight to ``list`` or to
    ``assert_allclose`` is a type error even though it is an array at runtime.
    """
    return np.asarray(line.get_xdata(), dtype=np.float64)


def ydata(line: Any) -> FloatArray:
    """Return a line's y data as a float array; see :func:`xdata`."""
    return np.asarray(line.get_ydata(), dtype=np.float64)


def hide_matplotlib(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``import matplotlib`` fail for the rest of the test, as if the extra were absent.

    ``sys.modules[name] = None`` is the import system's own "this module cannot
    be imported" marker. Every already-imported ``matplotlib.*`` submodule is
    hidden too, so a cached submodule cannot make the absence partial.
    """
    for name in [n for n in sys.modules if n == "matplotlib" or n.startswith("matplotlib.")]:
        monkeypatch.setitem(sys.modules, name, None)
    monkeypatch.setitem(sys.modules, "matplotlib", None)
