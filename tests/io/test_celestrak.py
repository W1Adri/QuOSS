"""Tests for :mod:`quoss.io.celestrak`."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from quoss.core.errors import DataError, DegradationLog, DomainError
from quoss.io.cache import HttpCache
from quoss.io.celestrak import CELESTRAK_GP_URL, TleRecord, celestrak_url, fetch_tle, parse_tle_text
from quoss.orbits.tle import propagate_tle

NAME_LINE = "ISS (ZARYA)             "
LINE1 = "1 25544U 98067A   26256.17555434  .00004898  00000+0  96695-4 0  9992"
LINE2 = "2 25544  51.6307 224.6171 0004917 134.6730 225.4659 15.49096932585393"
CRLF_TEXT = f"{NAME_LINE}\r\n{LINE1}\r\n{LINE2}\r\n"
"""The ISS response CelesTrak served on 2026-09-13, byte for byte (see the snapshot)."""

EPOCH_JD = 2461296.67555434
"""Day 256.17555434 of 2026: JD(2026-01-01 00:00) = 2461041.5, plus 255.17555434."""

SRC = "https://example.org/tle"
WHEN = "2026-09-13T16:16:24+00:00"


class TestUrl:
    def test_by_catalog_number(self) -> None:
        assert celestrak_url(catalog_number=25544) == f"{CELESTRAK_GP_URL}?CATNR=25544&FORMAT=TLE"

    def test_by_name_is_percent_encoded(self) -> None:
        assert (
            celestrak_url(name=" ISS (ZARYA) ")
            == f"{CELESTRAK_GP_URL}?NAME=ISS%20%28ZARYA%29&FORMAT=TLE"
        )

    def test_integral_float_accepted(self) -> None:
        assert "CATNR=25544&" in celestrak_url(catalog_number=25544.0)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "kwargs",
        [
            {},
            {"catalog_number": 1, "name": "x"},
            {"catalog_number": 0},
            {"catalog_number": -3},
            {"catalog_number": 1.5},
            {"catalog_number": True},
            {"name": "   "},
        ],
    )
    def test_bad_selectors(self, kwargs: dict[str, object]) -> None:
        with pytest.raises(DomainError):
            celestrak_url(**kwargs)  # type: ignore[arg-type]


class TestParse:
    def test_three_lines_crlf(self) -> None:
        record = parse_tle_text(CRLF_TEXT, source_url=SRC, fetched_utc=WHEN)
        assert record == TleRecord(
            name="ISS (ZARYA)",
            line1=LINE1,
            line2=LINE2,
            catalog_number=25544,
            epoch_jd=EPOCH_JD,
            source_url=SRC,
            fetched_utc=WHEN,
        )
        assert record.data_version == "25544@2461296.67555434"

    def test_two_lines_without_name(self) -> None:
        record = parse_tle_text(f"\n{LINE1}\n{LINE2}\n\n", source_url=SRC, fetched_utc=WHEN)
        assert record.name is None and record.catalog_number == 25544

    def test_no_gp_data(self) -> None:
        with pytest.raises(DataError, match="No GP data found"):
            parse_tle_text("No GP data found\r\n", source_url=SRC, fetched_utc=WHEN)

    @pytest.mark.parametrize("text", ["", LINE1, f"{CRLF_TEXT}{CRLF_TEXT}"])
    def test_wrong_line_count(self, text: str) -> None:
        with pytest.raises(DataError, match="Expected 2 or 3"):
            parse_tle_text(text, source_url=SRC, fetched_utc=WHEN)

    def test_checksum_failure_becomes_data_error_with_url(self) -> None:
        corrupted = LINE1[:-1] + "0"
        with pytest.raises(DataError, match=SRC) as info:
            parse_tle_text(f"{corrupted}\n{LINE2}", source_url=SRC, fetched_utc=WHEN)
        assert isinstance(info.value.__cause__, DomainError)
        assert "checksum" in str(info.value)


class TestRecord:
    def test_satrec_is_fresh_each_call_and_propagates(self) -> None:
        record = parse_tle_text(CRLF_TEXT, source_url=SRC, fetched_utc=WHEN)
        a, b = record.satrec(), record.satrec()
        assert a is not b and a.satnum == b.satnum == 25544
        trajectory = propagate_tle(a, np.array([0.0, 60.0]))
        assert trajectory.r_km.shape == (1, 2, 3)
        assert trajectory.grid.epoch_jd == EPOCH_JD


class TestFetch:
    def test_through_cache(self, tmp_path: Path, degradations: DegradationLog) -> None:
        calls: list[str] = []

        def fake(url: str) -> bytes:
            calls.append(url)
            return CRLF_TEXT.encode()

        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=fake, now=lambda: 1.0e9)
        record = fetch_tle(catalog_number=25544, cache=cache, degradations=degradations)
        assert calls == [f"{CELESTRAK_GP_URL}?CATNR=25544&FORMAT=TLE"]
        assert record.source_url == calls[0]
        assert record.fetched_utc == "2001-09-09T01:46:40+00:00"
        assert record.data_version == "25544@2461296.67555434"
        again = fetch_tle(catalog_number=25544, cache=cache, degradations=degradations)
        assert again == record and len(calls) == 1
        assert degradations.entries[-1].code == "io.cache-hit"

    def test_by_name(self, tmp_path: Path, degradations: DegradationLog) -> None:
        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=lambda url: CRLF_TEXT.encode())
        assert fetch_tle(name="ISS", cache=cache, degradations=degradations).name == "ISS (ZARYA)"

    def test_non_utf8_payload(self, tmp_path: Path, degradations: DegradationLog) -> None:
        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=lambda url: b"\xff\xfe")
        with pytest.raises(DataError, match="not UTF-8"):
            fetch_tle(catalog_number=25544, cache=cache, degradations=degradations)

    def test_bad_selector_before_any_fetch(
        self, tmp_path: Path, degradations: DegradationLog
    ) -> None:
        cache = HttpCache(tmp_path, ttl_s=60.0, fetch=lambda url: b"unused")
        with pytest.raises(DomainError):
            fetch_tle(cache=cache, degradations=degradations)
