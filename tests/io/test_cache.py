"""Tests for :mod:`quoss.io.cache` — and the proof that the whole ``io`` suite is offline."""

from __future__ import annotations

import hashlib
import json
import socket
import urllib.error
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quoss.core.errors import DataError, DegradationLog, DomainError, Severity
from quoss.io.cache import CachedResponse, HttpCache, cache_key, urllib_fetch
from quoss.io.celestrak import fetch_tle
from quoss.io.export import export_result
from quoss.io.openmeteo import fetch_cloud_cover
from quoss.io.snapshots import snapshot_cloud_cover, snapshot_tle
from quoss.io.stations import load_station_catalogue

URL = "https://example.org/data?x=1"
T0 = 1.0e9  # 2001-09-09T01:46:40Z


class Clock:
    """A clock the test moves by hand; the reason no test here sleeps."""

    def __init__(self, t: float = T0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class Fetcher:
    """A fake ``fetch`` that counts calls and can be told to fail."""

    def __init__(self, payload: bytes = b"payload-1") -> None:
        self.payload = payload
        self.calls: list[str] = []
        self.fail: DataError | None = None

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if self.fail is not None:
            raise self.fail
        return self.payload


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def fetcher() -> Fetcher:
    return Fetcher()


@pytest.fixture
def cache(tmp_path: Path, clock: Clock, fetcher: Fetcher) -> HttpCache:
    return HttpCache(tmp_path / "cache", ttl_s=3600.0, fetch=fetcher, now=clock)


class TestKey:
    @given(st.text())
    def test_key_is_sha256_of_utf8(self, url: str) -> None:
        assert cache_key(url) == hashlib.sha256(url.encode("utf-8")).hexdigest()
        assert len(cache_key(url)) == 64

    @given(st.text(), st.text())
    def test_distinct_urls_distinct_keys(self, a: str, b: str) -> None:
        assert (cache_key(a) == cache_key(b)) == (a == b)

    def test_paths_use_the_key(self, cache: HttpCache) -> None:
        bin_path, json_path = cache.paths(URL)
        assert bin_path.name == f"{cache_key(URL)}.bin"
        assert json_path.name == f"{cache_key(URL)}.json"
        assert bin_path.parent == cache.directory


class TestConstruction:
    @pytest.mark.parametrize("ttl", [-1.0, float("inf"), float("nan")])
    def test_bad_ttl(self, tmp_path: Path, ttl: float) -> None:
        with pytest.raises(DomainError, match="ttl_s"):
            HttpCache(tmp_path, ttl_s=ttl)

    def test_properties_and_repr(self, tmp_path: Path) -> None:
        cache = HttpCache(tmp_path / "c", ttl_s=5.0)
        assert cache.ttl_s == 5.0
        assert cache.directory == tmp_path / "c"
        assert repr(cache) == f"HttpCache({str(tmp_path / 'c')!r}, ttl_s=5.0)"


class TestMissAndStore:
    def test_first_get_fetches_and_writes_both_files(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        assert cache.get(URL, degradations=degradations) == b"payload-1"
        assert fetcher.calls == [URL]
        bin_path, json_path = cache.paths(URL)
        assert bin_path.read_bytes() == b"payload-1"
        meta = json.loads(json_path.read_text())
        assert meta == {
            "url": URL,
            "fetched_utc": "2001-09-09T01:46:40+00:00",
            "fetched_unix": T0,
            "sha256": hashlib.sha256(b"payload-1").hexdigest(),
            "size": 9,
        }
        assert not list(cache.directory.glob("*.tmp"))
        assert len(degradations) == 0

    def test_fetch_returns_provenance(self, cache: HttpCache, degradations: DegradationLog) -> None:
        response = cache.fetch(URL, degradations=degradations)
        assert response == CachedResponse(
            url=URL,
            payload=b"payload-1",
            fetched_utc="2001-09-09T01:46:40+00:00",
            sha256=hashlib.sha256(b"payload-1").hexdigest(),
            from_cache=False,
            age_s=0.0,
        )


class TestTtl:
    """Measured for the module docstring: 3599 s is a hit, 3600 s is a miss."""

    def test_hit_below_ttl(
        self, cache: HttpCache, clock: Clock, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        clock.t = T0 + 3599.0
        response = cache.fetch(URL, degradations=degradations)
        assert response.from_cache and response.age_s == 3599.0
        assert response.fetched_utc == "2001-09-09T01:46:40+00:00"
        assert fetcher.calls == [URL]
        (hit,) = degradations.entries
        assert hit.code == "io.cache-hit" and hit.severity is Severity.INFO
        assert hit.details["age_s"] == 3599.0 and hit.details["ttl_s"] == 3600.0

    def test_miss_at_ttl(
        self, cache: HttpCache, clock: Clock, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        clock.t = T0 + 3600.0
        fetcher.payload = b"payload-2"
        assert cache.get(URL, degradations=degradations) == b"payload-2"
        assert fetcher.calls == [URL, URL]
        assert len(degradations) == 0

    def test_zero_ttl_always_refetches(
        self, tmp_path: Path, clock: Clock, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache = HttpCache(tmp_path, ttl_s=0.0, fetch=fetcher, now=clock)
        cache.get(URL, degradations=degradations)
        cache.get(URL, degradations=degradations)
        assert fetcher.calls == [URL, URL]


class TestStalePolicy:
    def test_failed_fetch_with_no_entry_raises(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        fetcher.fail = DataError("HTTP 503 fetching it")
        with pytest.raises(DataError, match="503"):
            cache.get(URL, degradations=degradations, allow_stale=True)

    def test_stale_entry_not_used_by_default(
        self, cache: HttpCache, clock: Clock, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        clock.t = T0 + 7200.0
        fetcher.fail = DataError("HTTP 503 fetching it")
        with pytest.raises(DataError, match="503"):
            cache.get(URL, degradations=degradations)
        assert len(degradations) == 0

    def test_stale_entry_used_when_allowed_and_recorded(
        self, cache: HttpCache, clock: Clock, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        clock.t = T0 + 7200.0
        fetcher.fail = DataError("HTTP 503 fetching it")
        response = cache.fetch(URL, degradations=degradations, allow_stale=True)
        assert response.payload == b"payload-1" and response.from_cache
        assert response.age_s == 7200.0
        (warning,) = degradations.entries
        assert warning.code == "io.cache-stale-fallback"
        assert warning.severity is Severity.WARNING
        assert warning.details["age_s"] == 7200.0
        assert "503" in warning.details["error"]
        assert not degradations.has_degraded

    def test_fresh_entry_never_calls_fetch(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        fetcher.fail = DataError("would fail")
        assert cache.get(URL, degradations=degradations) == b"payload-1"


class TestCorruption:
    def test_edited_payload_is_discarded_and_refetched(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        bin_path, _ = cache.paths(URL)
        bin_path.write_bytes(b"edited")
        fetcher.payload = b"payload-2"
        assert cache.get(URL, degradations=degradations) == b"payload-2"
        (warning,) = degradations.entries
        assert warning.code == "io.cache-corrupt-entry"
        assert "sha256" in warning.details["reason"]
        assert bin_path.read_bytes() == b"payload-2"

    def test_half_entry_is_a_plain_miss(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog
    ) -> None:
        cache.get(URL, degradations=degradations)
        _, json_path = cache.paths(URL)
        json_path.unlink()
        cache.get(URL, degradations=degradations)
        assert fetcher.calls == [URL, URL]
        assert len(degradations) == 0

    @pytest.mark.parametrize(
        "meta",
        [
            "not json",
            '{"fetched_utc": "x"}',
            '{"fetched_unix": "abc", "fetched_utc": "x", "sha256": "y"}',
        ],
    )
    def test_unreadable_metadata_is_discarded(
        self, cache: HttpCache, fetcher: Fetcher, degradations: DegradationLog, meta: str
    ) -> None:
        cache.get(URL, degradations=degradations)
        _, json_path = cache.paths(URL)
        json_path.write_text(meta)
        cache.get(URL, degradations=degradations)
        assert fetcher.calls == [URL, URL]
        (warning,) = degradations.entries
        assert warning.code == "io.cache-corrupt-entry"
        assert "unreadable metadata" in warning.details["reason"]


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def _raising(exc: BaseException) -> Callable[..., Any]:
    def opener(url: str, *, timeout: float) -> Any:
        raise exc

    return opener


class TestUrllibFetch:
    def test_success_through_injected_opener(self) -> None:
        seen: list[tuple[str, float]] = []

        def opener(url: str, *, timeout: float) -> _FakeResponse:
            seen.append((url, timeout))
            return _FakeResponse(b"body")

        assert urllib_fetch("https://example.org/x", timeout_s=7.0, urlopen=opener) == b"body"
        assert seen == [("https://example.org/x", 7.0)]

    @pytest.mark.parametrize("url", ["file:///etc/passwd", "ftp://example.org/x", "example.org"])
    def test_refuses_non_http_schemes(self, url: str) -> None:
        with pytest.raises(DataError, match="not http/https"):
            urllib_fetch(url, urlopen=_raising(AssertionError("must not be called")))

    def test_http_error_carries_status(self) -> None:
        exc = urllib.error.HTTPError("https://example.org/x", 404, "Not Found", {}, None)  # type: ignore[arg-type]
        with pytest.raises(
            DataError, match=r"HTTP 404 Not Found fetching 'https://example\.org/x'"
        ):
            urllib_fetch("https://example.org/x", urlopen=_raising(exc))

    def test_url_error(self) -> None:
        with pytest.raises(DataError, match="Could not reach"):
            urllib_fetch("https://example.org/x", urlopen=_raising(urllib.error.URLError("dns")))

    def test_timeout(self) -> None:
        with pytest.raises(DataError, match=r"Timed out after 3\.0 s"):
            urllib_fetch("https://example.org/x", timeout_s=3.0, urlopen=_raising(TimeoutError()))


ISS_TEXT = (
    "ISS (ZARYA)             \r\n"
    "1 25544U 98067A   26256.17555434  .00004898  00000+0  96695-4 0  9992\r\n"
    "2 25544  51.6307 224.6171 0004917 134.6730 225.4659 15.49096932585393\r\n"
)

CLOUD_PAYLOAD = {
    "latitude": 41.300526,
    "longitude": 2.0659971,
    "elevation": 10.0,
    "utc_offset_seconds": 0,
    "hourly_units": {"time": "iso8601", "cloud_cover": "%"},
    "hourly": {"time": ["2025-01-01T00:00", "2025-01-01T01:00"], "cloud_cover": [100, 96]},
}


class _Result:
    def to_manifest_and_arrays(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return {"passes": [{"station": "s", "bits": 1}]}, {"series/s/t": np.array([0.0])}


class TestTheSuiteIsOffline:
    """Break the socket layer and show every code path in ``quoss.io`` still runs.

    This is the test the isolation principle rests on: if any function below
    reached for the network it would fail here, in CI, on the day it was
    written — not on the day the conference wifi was down.
    """

    @pytest.fixture(autouse=True)
    def _no_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def refuse(*args: object, **kwargs: object) -> object:
            raise OSError("network disabled by TestTheSuiteIsOffline")

        monkeypatch.setattr(socket, "socket", refuse)
        monkeypatch.setattr(socket, "create_connection", refuse)

    def test_the_real_fetch_cannot_succeed(self) -> None:
        with pytest.raises(DataError, match="Could not reach"):
            urllib_fetch("https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE")

    def test_every_path_runs_on_fakes(self, tmp_path: Path, degradations: DegradationLog) -> None:
        def fake(url: str) -> bytes:
            if "celestrak" in url:
                return ISS_TEXT.encode()
            return json.dumps(CLOUD_PAYLOAD).encode()

        cache = HttpCache(tmp_path / "c", ttl_s=60.0, fetch=fake, now=lambda: T0)
        tle = fetch_tle(catalog_number=25544, cache=cache, degradations=degradations)
        assert tle.catalog_number == 25544
        clouds = fetch_cloud_cover(
            latitude_deg=41.275,
            longitude_deg=1.9875,
            start_utc=date(2025, 1, 1),
            end_utc=date(2025, 1, 1),
            cache=cache,
            degradations=degradations,
        )
        assert clouds.grid.n == 2
        assert snapshot_tle("iss_zarya", degradations=degradations).catalog_number == 25544
        assert (
            snapshot_cloud_cover("castelldefels_2025-01-01_02", degradations=degradations).grid.n
            == 48
        )
        assert len(load_station_catalogue()) == 4
        out = export_result(_Result(), tmp_path / "out", degradations=degradations)
        assert out.manifest_path.is_file()
        assert not degradations.has_degraded
