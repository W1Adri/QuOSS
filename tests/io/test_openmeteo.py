"""Tests for :mod:`quoss.io.openmeteo`."""

from __future__ import annotations

import copy
import json
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quoss.core.errors import DataError, DegradationLog, DomainError, Severity
from quoss.core.types import TimeGrid
from quoss.io.cache import HttpCache
from quoss.io.openmeteo import (
    OPEN_METEO_ARCHIVE_URL,
    OPEN_METEO_MODEL_LABEL,
    CloudCoverSeries,
    fetch_cloud_cover,
    great_circle_km,
    openmeteo_url,
    parse_cloud_cover,
)
from quoss.io.snapshots import load_snapshot
from quoss.orbits.frames import calendar_to_jd

SRC = "https://example.org/archive"
WHEN = "2026-09-13T16:16:24+00:00"

REQUESTED = (41.2750, 1.9875)
"""Castelldefels, as in tests/system/reference.py."""

EXPECTED_URL = (
    f"{OPEN_METEO_ARCHIVE_URL}?latitude=41.2750&longitude=1.9875"
    "&start_date=2025-01-01&end_date=2025-01-02&hourly=cloud_cover&timezone=UTC"
)


def payload(hours: int = 3, **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "latitude": 41.300526,
        "longitude": 2.0659971,
        "generationtime_ms": 0.28,
        "utc_offset_seconds": 0,
        "timezone": "GMT",
        "timezone_abbreviation": "GMT",
        "elevation": 10.0,
        "hourly_units": {"time": "iso8601", "cloud_cover": "%"},
        "hourly": {
            "time": [f"2025-01-01T{h:02d}:00" for h in range(hours)],
            "cloud_cover": [100, 96, 69, 52, 60, 60, 55][:hours],
        },
    }
    base.update(overrides)
    return base


class TestUrl:
    def test_castelldefels_reference_day(self) -> None:
        url = openmeteo_url(
            latitude_deg=41.275,
            longitude_deg=1.9875,
            start_utc=date(2025, 1, 1),
            end_utc=date(2025, 1, 2),
        )
        assert url == EXPECTED_URL

    @pytest.mark.parametrize(
        ("lat", "lon", "start", "end"),
        [
            (91.0, 0.0, date(2025, 1, 1), date(2025, 1, 1)),
            (float("nan"), 0.0, date(2025, 1, 1), date(2025, 1, 1)),
            (0.0, -180.5, date(2025, 1, 1), date(2025, 1, 1)),
            (0.0, 0.0, date(2025, 1, 2), date(2025, 1, 1)),
        ],
    )
    def test_rejects(self, lat: float, lon: float, start: date, end: date) -> None:
        with pytest.raises(DomainError):
            openmeteo_url(latitude_deg=lat, longitude_deg=lon, start_utc=start, end_utc=end)


class TestParse:
    def test_valid_payload(self, degradations: DegradationLog) -> None:
        series = parse_cloud_cover(
            payload(), source_url=SRC, fetched_utc=WHEN, degradations=degradations
        )
        assert series.grid.epoch_jd == calendar_to_jd(2025, 1, 1)
        assert series.grid.t_s.tolist() == [0.0, 3600.0, 7200.0]
        assert series.cloud_fraction.tolist() == [1.0, 0.96, 0.69]
        assert series.model == OPEN_METEO_MODEL_LABEL
        assert (series.latitude_deg, series.longitude_deg, series.elevation_m) == (
            41.300526,
            2.0659971,
            10.0,
        )
        assert series.data_version == "open-meteo-archive:2025-01-01:2025-01-01:fetched=2026-09-13"
        assert series.source_url == SRC and series.fetched_utc == WHEN
        assert not series.cloud_fraction.flags.writeable
        assert len(degradations) == 0  # no requested point given, no offset to report

    def test_missing_elevation_is_nan(self, degradations: DegradationLog) -> None:
        p = payload()
        del p["elevation"]
        series = parse_cloud_cover(p, source_url=SRC, fetched_utc=WHEN, degradations=degradations)
        assert np.isnan(series.elevation_m)

    def test_api_error_object(self, degradations: DegradationLog) -> None:
        with pytest.raises(DataError, match="Latitude must be in range"):
            parse_cloud_cover(
                {"error": True, "reason": "Latitude must be in range"},
                source_url=SRC,
                fetched_utc=WHEN,
                degradations=degradations,
            )

    def test_api_error_without_reason(self, degradations: DegradationLog) -> None:
        with pytest.raises(DataError, match="no reason given"):
            parse_cloud_cover(
                {"error": True}, source_url=SRC, fetched_utc=WHEN, degradations=degradations
            )

    @pytest.mark.parametrize(
        ("overrides", "match"),
        [
            ({"utc_offset_seconds": 3600}, "timezone=UTC"),
            ({"hourly_units": {"cloud_cover": "okta"}}, "expected '%'"),
            ({"hourly_units": "percent"}, "expected '%'"),
            ({"hourly": None}, "no 'hourly' block"),
            ({"hourly": {"time": ["2025-01-01T00:00"], "cloud_cover": [1, 2]}}, "equal length"),
            ({"hourly": {"time": "2025-01-01T00:00", "cloud_cover": [1]}}, "equal length"),
            ({"hourly": {"time": [], "cloud_cover": []}}, "holds no hours"),
            ({"hourly": {"time": ["2025-01-01 00:00"], "cloud_cover": [1]}}, "timestamp not in"),
            ({"hourly": {"time": ["2025-01-01T00:00"], "cloud_cover": ["cloudy"]}}, "non-numeric"),
            (
                {"hourly": {"time": ["2025-01-01T00:00"], "cloud_cover": [101]}},
                "outside \\[0, 100\\]",
            ),
            (
                {"hourly": {"time": ["2025-01-01T00:00"], "cloud_cover": [-1]}},
                "outside \\[0, 100\\]",
            ),
            (
                {
                    "hourly": {
                        "time": ["2025-01-01T01:00", "2025-01-01T00:00"],
                        "cloud_cover": [1, 2],
                    }
                },
                "strictly increasing",
            ),
        ],
    )
    def test_rejects_malformed(
        self, degradations: DegradationLog, overrides: dict[str, Any], match: str
    ) -> None:
        with pytest.raises(DataError, match=match):
            parse_cloud_cover(
                payload(**overrides), source_url=SRC, fetched_utc=WHEN, degradations=degradations
            )

    def test_null_hours_are_listed_not_interpolated(self, degradations: DegradationLog) -> None:
        p = payload(hours=7)
        for i in (1, 2, 3, 4, 5, 6):
            p["hourly"]["cloud_cover"][i] = None
        with pytest.raises(DataError, match="6 missing hour") as info:
            parse_cloud_cover(p, source_url=SRC, fetched_utc=WHEN, degradations=degradations)
        message = str(info.value)
        assert (
            "2025-01-01T01:00, 2025-01-01T02:00, 2025-01-01T03:00, 2025-01-01T04:00, 2025-01-01T05:00, ..."
            in message
        )
        assert "2025-01-01T06:00" not in message
        assert not degradations.has_degraded

    def test_single_null_message_has_no_ellipsis(self, degradations: DegradationLog) -> None:
        p = payload()
        p["hourly"]["cloud_cover"][2] = None
        with pytest.raises(DataError, match=r"1 missing hour\(s\) \(2025-01-01T02:00\)\."):
            parse_cloud_cover(p, source_url=SRC, fetched_utc=WHEN, degradations=degradations)

    def test_requested_point_must_come_in_pairs(self, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match="both"):
            parse_cloud_cover(
                payload(),
                source_url=SRC,
                fetched_utc=WHEN,
                degradations=degradations,
                requested_latitude_deg=41.0,
            )


class TestGridOffset:
    """The ERA5 cell is not the telescope: 7.2 km away for Castelldefels."""

    def test_meridian_degree(self) -> None:
        # 2 pi R / 360 with R = 6378.137 km is 111.3195 km, exact for a sphere.
        assert great_circle_km(0.0, 0.0, 1.0, 0.0) == pytest.approx(111.3195, abs=5e-5)
        assert great_circle_km(10.0, 20.0, 10.0, 20.0) == 0.0

    def test_offset_recorded_for_the_shipped_castelldefels_payload(
        self, degradations: DegradationLog
    ) -> None:
        snapshot = load_snapshot("cloud_cover", "castelldefels_2025-01-01_02")
        series = parse_cloud_cover(
            snapshot.payload,
            source_url=SRC,
            fetched_utc=WHEN,
            degradations=degradations,
            requested_latitude_deg=REQUESTED[0],
            requested_longitude_deg=REQUESTED[1],
        )
        (info,) = degradations.entries
        assert info.code == "io.openmeteo-grid-offset" and info.severity is Severity.INFO
        # Spherical haversine; the ellipsoid correction is below 0.34 % (the
        # flattening), i.e. below 0.025 km here, so one decimal is what the
        # number is worth and what the docstring quotes.
        assert round(info.details["distance_km"], 1) == 7.2
        assert info.details["cell_latitude_deg"] == series.latitude_deg == 41.300526
        assert info.details["requested_longitude_deg"] == REQUESTED[1]
        assert "7.2 km" in info.message


class TestSeriesContainer:
    def test_shape_and_range_checks(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=3600.0, n=2)
        kwargs: dict[str, Any] = {
            "grid": grid,
            "source_url": SRC,
            "model": "m",
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "elevation_m": 0.0,
            "fetched_utc": WHEN,
            "data_version": "v",
        }
        with pytest.raises(DomainError, match="shape"):
            CloudCoverSeries(cloud_fraction=np.zeros(3), **kwargs)
        with pytest.raises(DomainError, match=r"\[0, 1\]"):
            CloudCoverSeries(cloud_fraction=np.array([0.0, 1.5]), **kwargs)
        with pytest.raises(DomainError, match=r"\[0, 1\]"):
            CloudCoverSeries(cloud_fraction=np.array([0.0, np.nan]), **kwargs)
        ok = CloudCoverSeries(cloud_fraction=np.array([0.0, 1.0]), **kwargs)
        assert ok.cloud_fraction.dtype == np.float64


class TestFetch:
    def test_through_cache(self, tmp_path: Path, degradations: DegradationLog) -> None:
        calls: list[str] = []

        def fake(url: str) -> bytes:
            calls.append(url)
            return json.dumps(payload()).encode()

        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=fake, now=lambda: 1.0e9)
        series = fetch_cloud_cover(
            latitude_deg=41.275,
            longitude_deg=1.9875,
            start_utc=date(2025, 1, 1),
            end_utc=date(2025, 1, 2),
            cache=cache,
            degradations=degradations,
        )
        assert calls == [EXPECTED_URL]
        assert series.source_url == EXPECTED_URL
        assert series.fetched_utc == "2001-09-09T01:46:40+00:00"
        assert series.data_version.endswith(":fetched=2001-09-09")
        codes = [e.code for e in degradations]
        assert codes == ["io.openmeteo-grid-offset"]

    @pytest.mark.parametrize(
        ("body", "match"), [(b"not json", "not JSON"), (b"[1, 2]", "not an object")]
    )
    def test_bad_bodies(
        self, tmp_path: Path, degradations: DegradationLog, body: bytes, match: str
    ) -> None:
        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=lambda url: body)
        with pytest.raises(DataError, match=match):
            fetch_cloud_cover(
                latitude_deg=0.0,
                longitude_deg=0.0,
                start_utc=date(2025, 1, 1),
                end_utc=date(2025, 1, 1),
                cache=cache,
                degradations=degradations,
            )

    def test_payload_is_not_mutated(self, degradations: DegradationLog) -> None:
        p = payload()
        before = copy.deepcopy(p)
        parse_cloud_cover(p, source_url=SRC, fetched_utc=WHEN, degradations=degradations)
        assert p == before
