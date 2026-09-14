"""On-disk HTTP cache: every external client in this project fetches through here.

What a cache is doing in a physics simulator
--------------------------------------------
Two of the inputs a scenario can ask for live on somebody else's server: the
TLE of a satellite (CelesTrak) and the cloud cover over a station (Open-Meteo).
Both are slow to fetch compared with the physics that consumes them, both are
rate-limited, and both change: a TLE is re-fitted several times a day, a
reanalysis is re-issued. A cache turns "fetch it" into "fetch it once, then
reuse the copy until it is too old", which is level (a) of the three-level
cache in ``notes/GUIA_REIMPLEMENTACION.md`` §2.2.

Three decisions, each with its reason
-------------------------------------
**Content-addressed by URL.** The key of an entry is the SHA-256 hash of the
URL's UTF-8 bytes, printed as 64 hexadecimal characters. "Content-addressed"
means the *name* of the file is a function of *what it holds*, so two callers
asking for the same URL land on the same file with no registry to keep in
sync, and a URL with characters a filesystem dislikes (``?``, ``&``, ``/``)
never has to be escaped. SHA-256 rather than something shorter because the
cost is nil (a hash of a hundred-byte string) and a collision — two URLs
sharing an entry — would be a silent substitution of one dataset for another,
exactly the failure class ``README.md`` forbids. The probability of one among
``n`` URLs is about ``n^2 / 2^257``; for a million URLs that is ``1e-65``.

**A time-to-live, with no default.** An entry is *fresh* if its age is below
``ttl_s`` and *stale* otherwise. The right TTL depends on what is cached — a
TLE goes measurably out of date in a day (``docs/adr/0007``), a 2025 ERA5
series will not change in a year — so :class:`HttpCache` refuses to guess and
makes ``ttl_s`` a required keyword. Age is measured with an injected clock,
``now()``, returning seconds since the Unix epoch. That is not an affectation:
it is what lets the TTL be tested by *moving the clock* instead of sleeping,
and what makes an expiry test run in microseconds rather than in ``ttl_s``.

**A stale entry is never used silently.** When a fetch fails, the obvious
convenience is to fall back to whatever is on disk. That is also how a paper
ends up plotted against a TLE from three weeks earlier without anyone knowing.
So the fallback is opt-in — ``allow_stale=True`` — and when it fires it records
a ``WARNING`` with code ``io.cache-stale-fallback`` in the caller's
:class:`~quoss.core.errors.DegradationLog`, naming the age of the entry and the
error that forced it. With the default ``allow_stale=False`` a failed fetch is a
:class:`~quoss.core.errors.DataError` that carries the URL and the HTTP status.

What is stored
--------------
For key ``k`` the directory holds ``k.bin`` (the raw payload bytes) and
``k.json`` (the URL, the fetch time as an ISO-8601 UTC string and as Unix
seconds, the SHA-256 of the payload and its size). The hash of the payload is
checked on every read; a mismatch means the file was edited or truncated after
it was written, and the entry is discarded and re-fetched with a ``WARNING``
(``io.cache-corrupt-entry``) — the URL, not the copy, is the source of truth.
Both files are written to a temporary name and renamed into place, so a crash
mid-write cannot leave a half payload with a matching manifest.

Measured (``tests/io/test_cache.py::TestTtl``): with ``ttl_s=3600`` and the
clock advanced by 3599 s the second ``get`` is a hit and the fake ``fetch`` is
called once; advanced by 3600 s it is a miss and ``fetch`` is called twice.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from quoss.core.errors import DegradationLog
>>> calls = []
>>> def fake_fetch(url: str) -> bytes:
...     calls.append(url)
...     return b"payload"
>>> with tempfile.TemporaryDirectory() as tmp:
...     cache = HttpCache(Path(tmp), ttl_s=60.0, fetch=fake_fetch, now=lambda: 1.0e9)
...     first = cache.get("https://example.org/a", degradations=DegradationLog())
...     second = cache.get("https://example.org/a", degradations=DegradationLog())
>>> first == second == b"payload"
True
>>> len(calls)
1
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from quoss.core.errors import DataError, DegradationLog, DomainError

__all__ = [
    "CachedResponse",
    "FetchFunction",
    "HttpCache",
    "cache_key",
    "urllib_fetch",
]

FetchFunction = Callable[[str], bytes]
"""Anything that turns a URL into the bytes it serves, or raises :class:`DataError`."""

Clock = Callable[[], float]
"""Anything that returns the current time in seconds since the Unix epoch."""

_ALLOWED_SCHEMES = frozenset({"http", "https"})

_WHERE = "quoss.io.cache.HttpCache.get"


def cache_key(url: str) -> str:
    """Return the cache key of a URL: the SHA-256 of its UTF-8 bytes, in hex.

    Parameters
    ----------
    url : str
        The URL exactly as it will be fetched. Two spellings of "the same"
        resource (``http`` versus ``https``, a trailing ``&``) are two keys,
        deliberately: the cache does not know which spellings a server treats
        as equivalent, and guessing wrong would merge two datasets.

    Returns
    -------
    str
        64 lowercase hexadecimal characters.

    Examples
    --------
    >>> cache_key("https://example.org/a")[:16]
    'b5b10dd0429e69ac'
    >>> len(cache_key(""))
    64
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def urllib_fetch(
    url: str,
    *,
    timeout_s: float = 30.0,
    urlopen: Callable[..., Any] = urllib.request.urlopen,
) -> bytes:
    """Fetch a URL with the standard library and return the response body.

    The default ``fetch`` of :class:`HttpCache`, and the *only* function in
    this package that can open a socket. It is a thin wrapper whose job is to
    convert the three ways ``urllib`` fails into one :class:`DataError` that
    says which URL and, when there is one, which HTTP status.

    Parameters
    ----------
    url : str
        Must use the ``http`` or ``https`` scheme. ``urllib`` would happily
        open ``file:///etc/passwd``; a cache that can be pointed at the local
        filesystem by a string in a scenario file is not a feature.
    timeout_s : float, optional
        Socket timeout in seconds. 30 s by default: CelesTrak and Open-Meteo
        answer in well under one, and a hung connection should fail rather than
        block a pipeline stage indefinitely.
    urlopen : callable, optional
        ``urllib.request.urlopen`` by default. Injected so the error mapping
        can be tested without a network — the tests hand in a callable that
        raises the ``urllib`` exceptions on demand.

    Returns
    -------
    bytes
        The complete response body.

    Raises
    ------
    DataError
        On a disallowed scheme, an HTTP error status, a URL/connection error,
        or a timeout. The message carries the URL and the status code.
    """
    scheme = urlsplit(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise DataError(
            f"Refusing to fetch {url!r}: scheme {scheme!r} is not http/https. "
            f"The HTTP cache is not a way to read arbitrary files."
        )
    try:
        with urlopen(url, timeout=timeout_s) as response:
            body: bytes = response.read()
    except urllib.error.HTTPError as exc:
        raise DataError(f"HTTP {exc.code} {exc.reason} fetching {url!r}.") from exc
    except urllib.error.URLError as exc:
        raise DataError(f"Could not reach {url!r}: {exc.reason}.") from exc
    except TimeoutError as exc:
        raise DataError(f"Timed out after {timeout_s} s fetching {url!r}.") from exc
    return body


@dataclass(frozen=True, slots=True)
class CachedResponse:
    """What :meth:`HttpCache.fetch` returns: the bytes plus where they came from.

    Parameters
    ----------
    url : str
        The URL requested.
    payload : bytes
        The response body.
    fetched_utc : str
        When the payload was obtained from the server, ISO-8601 UTC with
        second resolution, e.g. ``"2026-09-13T16:16:24+00:00"``. For a cache
        hit this is the *original* fetch time, not the time of the hit — it is
        the value that belongs in a result's provenance.
    sha256 : str
        SHA-256 of ``payload``, hex.
    from_cache : bool
        True if served from disk without calling ``fetch``.
    age_s : float
        Seconds between ``fetched_utc`` and the clock at the time of the call.
        Zero for a fresh fetch.
    """

    url: str
    payload: bytes
    fetched_utc: str
    sha256: str
    from_cache: bool
    age_s: float


class HttpCache:
    """A directory of ``<sha256(url)>.bin`` / ``.json`` pairs with a TTL.

    Parameters
    ----------
    directory : Path
        Where entries live. Created on first write if absent.
    ttl_s : float
        Time-to-live in seconds. Finite and non-negative; ``0`` means "always
        re-fetch, but keep a copy for ``allow_stale``". No default — see the
        module docstring.
    fetch : FetchFunction, optional
        The function that performs a real request. :func:`urllib_fetch` by
        default; tests inject a fake.
    now : Clock, optional
        Returns the current Unix time in seconds. ``time.time`` by default;
        tests inject a controllable clock.

    Raises
    ------
    DomainError
        If ``ttl_s`` is negative or not finite.
    """

    __slots__ = ("_directory", "_fetch", "_now", "_ttl_s")

    def __init__(
        self,
        directory: Path,
        *,
        ttl_s: float,
        fetch: FetchFunction | None = None,
        now: Clock | None = None,
    ) -> None:
        ttl = float(ttl_s)
        if not (ttl >= 0.0 and ttl != float("inf")):
            raise DomainError(f"ttl_s must be finite and non-negative, got {ttl_s!r}.")
        self._directory = Path(directory)
        self._ttl_s = ttl
        self._fetch: FetchFunction = urllib_fetch if fetch is None else fetch
        self._now: Clock = _unix_time if now is None else now

    # -- introspection ------------------------------------------------------ #
    @property
    def directory(self) -> Path:
        """Directory holding the entries."""
        return self._directory

    @property
    def ttl_s(self) -> float:
        """Time-to-live in seconds."""
        return self._ttl_s

    def paths(self, url: str) -> tuple[Path, Path]:
        """Return the ``(payload, metadata)`` paths an entry for ``url`` uses.

        Parameters
        ----------
        url : str
            The URL.

        Returns
        -------
        tuple[Path, Path]
            ``<dir>/<key>.bin`` and ``<dir>/<key>.json``.
        """
        key = cache_key(url)
        return self._directory / f"{key}.bin", self._directory / f"{key}.json"

    # -- the operation ------------------------------------------------------ #
    def get(self, url: str, *, degradations: DegradationLog, allow_stale: bool = False) -> bytes:
        """Return the payload for ``url``, from disk if fresh, else fetched.

        Parameters
        ----------
        url : str
            The URL.
        degradations : DegradationLog
            Required. Receives ``io.cache-hit`` (INFO) on a hit,
            ``io.cache-corrupt-entry`` (WARNING) if an on-disk entry failed its
            hash check and was discarded, and ``io.cache-stale-fallback``
            (WARNING) if a stale entry was served because the fetch failed.
        allow_stale : bool, optional
            If True and the fetch fails, serve the stale entry (if any) with a
            WARNING instead of raising. False by default: a result computed on
            data older than its own TTL must be asked for, not stumbled into.

        Returns
        -------
        bytes
            The payload.

        Raises
        ------
        DataError
            If the fetch fails and no stale fallback is allowed or available.
        """
        return self.fetch(url, degradations=degradations, allow_stale=allow_stale).payload

    def fetch(
        self, url: str, *, degradations: DegradationLog, allow_stale: bool = False
    ) -> CachedResponse:
        """Like :meth:`get`, returning the payload together with its provenance.

        Parameters
        ----------
        url : str
            The URL.
        degradations : DegradationLog
            See :meth:`get`.
        allow_stale : bool, optional
            See :meth:`get`.

        Returns
        -------
        CachedResponse
            Payload, original fetch time, hash, and whether it came from disk.

        Raises
        ------
        DataError
            See :meth:`get`.
        """
        now = self._now()
        entry = self._read_entry(url, degradations=degradations)

        if entry is not None:
            age_s = now - entry.fetched_unix
            if age_s < self._ttl_s:
                degradations.info(
                    "io.cache-hit",
                    f"Served {url!r} from the on-disk cache, {age_s:.0f} s old "
                    f"(TTL {self._ttl_s:.0f} s).",
                    where=_WHERE,
                    url=url,
                    age_s=age_s,
                    ttl_s=self._ttl_s,
                    fetched_utc=entry.fetched_utc,
                )
                return CachedResponse(
                    url=url,
                    payload=entry.payload,
                    fetched_utc=entry.fetched_utc,
                    sha256=entry.sha256,
                    from_cache=True,
                    age_s=age_s,
                )

        try:
            payload = self._fetch(url)
        except DataError as exc:
            if entry is None or not allow_stale:
                raise
            age_s = now - entry.fetched_unix
            degradations.warn(
                "io.cache-stale-fallback",
                f"Fetch of {url!r} failed ({exc}); serving the stale cached copy "
                f"from {entry.fetched_utc}, {age_s:.0f} s old against a TTL of "
                f"{self._ttl_s:.0f} s.",
                where=_WHERE,
                url=url,
                age_s=age_s,
                ttl_s=self._ttl_s,
                fetched_utc=entry.fetched_utc,
                error=str(exc),
            )
            return CachedResponse(
                url=url,
                payload=entry.payload,
                fetched_utc=entry.fetched_utc,
                sha256=entry.sha256,
                from_cache=True,
                age_s=age_s,
            )

        written = self._write_entry(url, payload, fetched_unix=now)
        return CachedResponse(
            url=url,
            payload=payload,
            fetched_utc=written.fetched_utc,
            sha256=written.sha256,
            from_cache=False,
            age_s=0.0,
        )

    # -- storage ------------------------------------------------------------ #
    def _read_entry(self, url: str, *, degradations: DegradationLog) -> _Entry | None:
        """Read an entry from disk, or ``None`` if absent, unreadable or corrupt."""
        bin_path, json_path = self.paths(url)
        if not (bin_path.is_file() and json_path.is_file()):
            return None
        try:
            meta = json.loads(json_path.read_text(encoding="utf-8"))
            payload = bin_path.read_bytes()
            fetched_utc = str(meta["fetched_utc"])
            fetched_unix = float(meta["fetched_unix"])
            recorded_sha = str(meta["sha256"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._discard(url, degradations=degradations, reason=f"unreadable metadata: {exc}")
            return None
        actual_sha = hashlib.sha256(payload).hexdigest()
        if actual_sha != recorded_sha:
            self._discard(
                url,
                degradations=degradations,
                reason=f"payload sha256 {actual_sha[:12]}... != recorded {recorded_sha[:12]}...",
            )
            return None
        return _Entry(payload, fetched_utc, fetched_unix, actual_sha)

    def _discard(self, url: str, *, degradations: DegradationLog, reason: str) -> None:
        """Delete a corrupt entry and record that it happened."""
        degradations.warn(
            "io.cache-corrupt-entry",
            f"Cached entry for {url!r} discarded ({reason}); it will be re-fetched.",
            where=_WHERE,
            url=url,
            reason=reason,
        )
        for path in self.paths(url):
            path.unlink(missing_ok=True)

    def _write_entry(self, url: str, payload: bytes, *, fetched_unix: float) -> _Entry:
        """Write payload and metadata atomically (temp file + rename)."""
        self._directory.mkdir(parents=True, exist_ok=True)
        bin_path, json_path = self.paths(url)
        sha = hashlib.sha256(payload).hexdigest()
        fetched_utc = _iso_utc(fetched_unix)
        meta = {
            "url": url,
            "fetched_utc": fetched_utc,
            "fetched_unix": fetched_unix,
            "sha256": sha,
            "size": len(payload),
        }
        _atomic_write(bin_path, payload)
        _atomic_write(json_path, json.dumps(meta, indent=2, sort_keys=True).encode("utf-8"))
        return _Entry(payload, fetched_utc, fetched_unix, sha)

    def __repr__(self) -> str:
        return f"HttpCache({str(self._directory)!r}, ttl_s={self._ttl_s!r})"


@dataclass(frozen=True, slots=True)
class _Entry:
    payload: bytes
    fetched_utc: str
    fetched_unix: float
    sha256: str


def _unix_time() -> float:
    return datetime.now(UTC).timestamp()


def _iso_utc(unix_s: float) -> str:
    return datetime.fromtimestamp(unix_s, tz=UTC).isoformat(timespec="seconds")


def _atomic_write(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via a sibling temp file and ``Path.replace``.

    ``Path.replace`` (``os.replace`` underneath) is atomic on POSIX within one
    filesystem, so a reader sees either the old file or the complete new one,
    never a prefix.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
