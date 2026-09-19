r"""A TLE from the CelesTrak GP API, validated before it is allowed to exist.

What is being fetched
---------------------
A **TLE** ("Two-Line Element set") is the form in which the orbit of a tracked
object is published: two lines of 69 characters, fitted by a tracking pipeline
so that the SGP4 analytic theory reproduces the object near a stated *epoch*
(the instant the elements refer to). :mod:`quoss.orbits.tle` explains the
format, its checksum, and why the elements are only meaningful together with
their epoch. This module's job is smaller: get those two lines from the
network, prove they are a TLE, and attach the provenance a result will need.

**CelesTrak** (celestrak.org, T. S. Kelso) republishes the public catalogue of
the US Space Force as "GP" (general perturbations) data through one endpoint::

    https://celestrak.org/NORAD/elements/gp.php?CATNR=<n>&FORMAT=TLE
    https://celestrak.org/NORAD/elements/gp.php?NAME=<text>&FORMAT=TLE

``CATNR`` is the catalogue number (25544 for the ISS); ``NAME`` is a substring
match on the object name and may return several objects. In ``FORMAT=TLE`` the
answer is three lines per object — a 24-character name line, then the two
element lines — with CRLF line endings, and the text ``No GP data found`` when
nothing matches. Verified by fetching the ISS on 2026-09-13 (the payload is
``quoss/data/snapshots/tle/iss_zarya.json``).

Why the epoch is the data version
---------------------------------
Provenance needs to say *which* TLE a result used, and "the ISS TLE" is not an
answer: CelesTrak re-fits it several times a day. The fetch time is not the
answer either — two fetches an hour apart usually return the identical
element set. What identifies an element set is its **epoch**, the Julian date
the elements are referred to, printed in columns 19-32 of line 1 with a
resolution of ``1e-8`` day (about a millisecond). So
:attr:`TleRecord.data_version` is ``"<catalog_number>@<epoch_jd>"``, e.g.
``"25544@2461296.67555434"``, and that string is what goes into
``Provenance.data_versions["tle"]``.

Why parsing happens *here* and not in the caller
------------------------------------------------
:func:`~quoss.orbits.tle.parse_tle` checks line length, line prefix, the
checksum digit and SGP4's own initialisation error, none of which the
``sgp4`` library checks for itself (see that module's docstring for the
corrupted-line experiment). Calling it before returning means a
:class:`TleRecord` cannot hold text that is not a TLE: a truncated response, a
proxy's HTML error page, or a ``No GP data found`` body all die here as a
:class:`~quoss.core.errors.DataError` with the URL in the message, instead of
surfacing later as an SGP4 failure at some sample.

Examples
--------
Parsing the exact bytes CelesTrak served for the ISS, with its trailing CRLFs:

>>> text = (
...     "ISS (ZARYA)             \r\n"
...     "1 25544U 98067A   26256.17555434  .00004898  00000+0  96695-4 0  9992\r\n"
...     "2 25544  51.6307 224.6171 0004917 134.6730 225.4659 15.49096932585393\r\n"
... )
>>> record = parse_tle_text(
...     text, source_url="https://example.org", fetched_utc="2026-09-13T16:16:24+00:00"
... )
>>> record.name, record.catalog_number
('ISS (ZARYA)', 25544)
>>> record.data_version
'25544@2461296.67555434'
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

from sgp4.api import Satrec

from quoss.core.errors import DataError, DegradationLog, DomainError
from quoss.io.cache import HttpCache
from quoss.orbits.tle import parse_tle, tle_epoch_jd

__all__ = [
    "CELESTRAK_GP_URL",
    "TleRecord",
    "celestrak_url",
    "fetch_tle",
    "parse_tle_text",
]

CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
"""The GP query endpoint. Verified live on 2026-09-13; see the module docstring."""

_NO_DATA_MARKER = "No GP data found"


@dataclass(frozen=True, slots=True)
class TleRecord:
    """A validated TLE with the provenance of where and when it was obtained.

    Parameters
    ----------
    name : str or None
        The object name from the optional first line, stripped of the padding
        CelesTrak adds; ``None`` if the source gave only two lines.
    line1, line2 : str
        The two element lines, exactly 69 characters each, already validated by
        :func:`~quoss.orbits.tle.parse_tle`.
    catalog_number : int
        The NORAD catalogue number, from columns 3-7 of line 1.
    epoch_jd : float
        The epoch of the elements as a Julian date (UTC), from
        :func:`~quoss.orbits.tle.tle_epoch_jd`.
    source_url : str
        Where the text came from — the query URL, or a snapshot's recorded URL.
    fetched_utc : str
        When it was obtained from the server, ISO-8601 UTC.
    """

    name: str | None
    line1: str
    line2: str
    catalog_number: int
    epoch_jd: float
    source_url: str
    fetched_utc: str

    @property
    def data_version(self) -> str:
        """``"<catalog_number>@<epoch_jd>"`` — the string for ``data_versions["tle"]``."""
        return f"{self.catalog_number}@{self.epoch_jd!r}"

    def satrec(self) -> Satrec:
        """Return a fresh ``sgp4`` record for :func:`~quoss.orbits.tle.propagate_tle`.

        Returns
        -------
        Satrec
            Parsed anew on every call; ``Satrec`` is mutable and this record is
            not, so handing out one shared instance would let a caller change
            what another sees.
        """
        return parse_tle(self.line1, self.line2)


def celestrak_url(*, catalog_number: int | None = None, name: str | None = None) -> str:
    """Build the GP query URL for exactly one of a catalogue number or a name.

    Parameters
    ----------
    catalog_number : int, optional
        NORAD catalogue number, a positive integer.
    name : str, optional
        Object-name substring. Percent-encoded; CelesTrak matches it against
        the name column and may return more than one object.

    Returns
    -------
    str
        The URL, always with ``FORMAT=TLE``.

    Raises
    ------
    DomainError
        If neither or both selectors are given, if ``catalog_number`` is not a
        positive integer, or if ``name`` is empty.

    Examples
    --------
    >>> celestrak_url(catalog_number=25544)
    'https://celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE'
    >>> celestrak_url(name="ISS (ZARYA)")
    'https://celestrak.org/NORAD/elements/gp.php?NAME=ISS%20%28ZARYA%29&FORMAT=TLE'
    """
    if (catalog_number is None) == (name is None):
        raise DomainError("Provide exactly one of catalog_number or name.")
    if catalog_number is not None:
        if (
            isinstance(catalog_number, bool)
            or int(catalog_number) != catalog_number
            or catalog_number <= 0
        ):
            raise DomainError(f"catalog_number must be a positive integer, got {catalog_number!r}.")
        return f"{CELESTRAK_GP_URL}?CATNR={int(catalog_number)}&FORMAT=TLE"
    assert name is not None  # narrowed by the exclusivity check
    if not name.strip():
        raise DomainError("name must not be empty.")
    return f"{CELESTRAK_GP_URL}?NAME={quote(name.strip(), safe='')}&FORMAT=TLE"


def parse_tle_text(text: str, *, source_url: str, fetched_utc: str) -> TleRecord:
    """Turn a two- or three-line TLE response into a validated :class:`TleRecord`.

    Parameters
    ----------
    text : str
        The response body. Line endings may be LF or CRLF; blank lines at
        either end are ignored. Either ``[name, line1, line2]`` or
        ``[line1, line2]``. A body with more than one object (a ``NAME=`` query
        that matched several) is rejected: this function returns one record,
        and picking the first silently would be picking an arbitrary satellite.
    source_url : str
        Recorded in the result.
    fetched_utc : str
        Recorded in the result.

    Returns
    -------
    TleRecord
        Validated through :func:`~quoss.orbits.tle.parse_tle`.

    Raises
    ------
    DataError
        On ``No GP data found``, a wrong number of lines, or any failure of
        :func:`~quoss.orbits.tle.parse_tle` (re-raised with the URL attached).
    """
    lines = [line.rstrip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    if any(_NO_DATA_MARKER in line for line in lines):
        raise DataError(f"CelesTrak returned {_NO_DATA_MARKER!r} for {source_url!r}.")
    if len(lines) == 3:
        name: str | None = lines[0]
        line1, line2 = lines[1], lines[2]
    elif len(lines) == 2:
        name = None
        line1, line2 = lines
    else:
        raise DataError(
            f"Expected 2 or 3 non-empty lines of TLE text from {source_url!r}, got "
            f"{len(lines)}: {text[:120]!r}."
        )
    try:
        satrec = parse_tle(line1, line2)
    except DomainError as exc:
        raise DataError(f"Text from {source_url!r} is not a valid TLE: {exc}") from exc
    return TleRecord(
        name=name,
        line1=line1,
        line2=line2,
        catalog_number=int(satrec.satnum),
        epoch_jd=tle_epoch_jd(satrec),
        source_url=source_url,
        fetched_utc=fetched_utc,
    )


def fetch_tle(
    *,
    catalog_number: int | None = None,
    name: str | None = None,
    cache: HttpCache,
    degradations: DegradationLog,
    allow_stale: bool = False,
) -> TleRecord:
    """Fetch one TLE from CelesTrak through the cache and validate it.

    Parameters
    ----------
    catalog_number : int, optional
        NORAD catalogue number. Exactly one of this or ``name``.
    name : str, optional
        Object-name substring; must match exactly one object.
    cache : HttpCache
        Every request goes through it. Choose its TTL for a TLE: one that is a
        day old has drifted by kilometres (``docs/adr/0007``), so an hour to a
        few hours is the sensible range.
    degradations : DegradationLog
        Required; receives the cache's records (hit, stale fallback).
    allow_stale : bool, optional
        Passed to :meth:`HttpCache.fetch`. False by default.

    Returns
    -------
    TleRecord
        With ``source_url`` set to the query URL and ``fetched_utc`` to the
        time the cache obtained the payload (not the time of this call).

    Raises
    ------
    DomainError
        Bad selector (see :func:`celestrak_url`).
    DataError
        Fetch failure, ``No GP data found``, or text that is not a TLE.
    """
    url = celestrak_url(catalog_number=catalog_number, name=name)
    response = cache.fetch(url, degradations=degradations, allow_stale=allow_stale)
    try:
        text = response.payload.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DataError(f"Response from {url!r} is not UTF-8 text.") from exc
    return parse_tle_text(text, source_url=url, fetched_utc=response.fetched_utc)
