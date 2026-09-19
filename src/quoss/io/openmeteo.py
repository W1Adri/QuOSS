"""Hourly cloud cover over a station from the Open-Meteo historical archive.

What is being fetched, and what it is not
-----------------------------------------
A free-space optical link does not go through a cloud. The one number that
decides whether a pass is usable at all is the **cloud fraction** over the
station — the share of the sky covered, 0 for clear and 1 for overcast — and
``system/pcflos.py`` turns a time series of it into a probability that a pass
finds a cloud-free line of sight. This module obtains that series.

The source is **Open-Meteo's historical weather API** (open-meteo.com), which
serves **ERA5**, the fifth-generation global *reanalysis* of the European
Centre for Medium-Range Weather Forecasts (ECMWF). A reanalysis is not an
observation at the station: it is a weather model re-run over the past and
nudged to every observation available, on a grid of about 0.25° (25 km) for
ERA5 or 0.1° (11 km) for ERA5-Land, hourly. Two consequences a user of this
data must know:

* **The value is for a grid cell, not for the telescope.** The response
  reports the coordinates of the cell it actually used; for Castelldefels
  (41.2750 N, 1.9875 E) that is 41.3005 N, 2.0660 E, **7.2 km** away
  (measured in ``tests/io/test_openmeteo.py::TestGridOffset``). The offset is
  recorded as an ``INFO`` degradation (``io.openmeteo-grid-offset``) so it
  travels into the result.
* **Cloud cover is an area fraction of a 25 km cell, hourly.** A 5-minute pass
  sees one line of sight, not a cell average. The gap between the two is a
  model question that belongs to ``system/pcflos.py``, not here.

The endpoint and its fields, as verified
----------------------------------------
Verified by fetching ``https://open-meteo.com/en/docs/historical-weather-api``
and the endpoint itself on 2026-09-13 (the payload is
``quoss/data/snapshots/cloud_cover/castelldefels_2025-01-01_02.json``)::

    https://archive-api.open-meteo.com/v1/archive
        ?latitude=<deg>&longitude=<deg>
        &start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
        &hourly=cloud_cover&timezone=UTC

The response is JSON with ``latitude``, ``longitude``, ``elevation`` (the
cell), ``utc_offset_seconds`` (0 when ``timezone=UTC``), ``hourly_units``
(``{"time": "iso8601", "cloud_cover": "%"}``) and ``hourly`` with two
equal-length arrays: ``time`` as ``"YYYY-MM-DDTHH:MM"`` strings and
``cloud_cover`` as numbers in percent. The response does **not** say which
reanalysis served the cell (the documentation describes a "best match" among
ERA5, ERA5-Land, ECMWF IFS and CERRA by region and date), so
:attr:`CloudCoverSeries.model` carries the endpoint's own label rather than a
model name this code cannot verify. Missing hours are ``null`` in the JSON —
the documentation does not say so explicitly; the behaviour is assumed from
the API's general convention and is rejected either way, see below.

Why a missing hour is an error and not an interpolation
-------------------------------------------------------
Cloud cover is not smooth: the 48 hours in the snapshot go 0 → 39 → 82 → 14 %
in three consecutive hours. Linear interpolation across a gap would fabricate
a number with no bound on its error, and a bound is the condition this project
sets for recording a ``DEGRADED`` substitution instead of raising. So a
``null`` anywhere in the series is a :class:`~quoss.core.errors.DataError`
naming the missing hours. The caller can shorten the window or choose another
source; the code will not guess.

Examples
--------
>>> from quoss.core.errors import DegradationLog
>>> payload = {
...     "latitude": 41.300526,
...     "longitude": 2.0659971,
...     "elevation": 10.0,
...     "utc_offset_seconds": 0,
...     "hourly_units": {"time": "iso8601", "cloud_cover": "%"},
...     "hourly": {"time": ["2025-01-01T00:00", "2025-01-01T01:00"], "cloud_cover": [100, 96]},
... }
>>> log = DegradationLog()
>>> series = parse_cloud_cover(
...     payload,
...     source_url="https://example.org",
...     fetched_utc="2026-09-13T16:16:24+00:00",
...     degradations=log,
... )
>>> series.grid.n, float(series.grid.step_s)
(2, 3600.0)
>>> series.cloud_fraction.tolist()
[1.0, 0.96]
>>> series.data_version
'open-meteo-archive:2025-01-01:2025-01-01:fetched=2026-09-13'
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import numpy as np

from quoss.core.constants import WGS84_RADIUS_EQUATORIAL_KM
from quoss.core.errors import DataError, DegradationLog, DomainError
from quoss.core.types import FloatArray, TimeGrid, frozen_copy
from quoss.core.units import deg_to_rad
from quoss.io.cache import HttpCache
from quoss.orbits.frames import calendar_to_jd

__all__ = [
    "OPEN_METEO_ARCHIVE_URL",
    "OPEN_METEO_MODEL_LABEL",
    "CloudCoverSeries",
    "fetch_cloud_cover",
    "openmeteo_url",
    "parse_cloud_cover",
]

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
"""The historical-archive endpoint. Verified live on 2026-09-13; see the module docstring."""

OPEN_METEO_MODEL_LABEL = "open-meteo-archive:best_match"
"""What :attr:`CloudCoverSeries.model` says when the API does not name the reanalysis.

The response carries no model field; the documentation describes the default
as a best match among the ERA5 family by region and date. This label is
honest about that: it names the endpoint's default, not a model this code has
verified.
"""

_TIME_FORMAT = "%Y-%m-%dT%H:%M"
_WHERE_PARSE = "quoss.io.openmeteo.parse_cloud_cover"


@dataclass(frozen=True, slots=True)
class CloudCoverSeries:
    """Hourly cloud fraction on a :class:`~quoss.core.types.TimeGrid`.

    Parameters
    ----------
    grid : TimeGrid
        ``epoch_jd`` is the first hour of the series; ``t_s`` counts seconds
        from it (3600 per step when nothing is missing).
    cloud_fraction : FloatArray
        Total cloud cover as a fraction in ``[0, 1]``, one value per grid
        sample. Stored as a read-only copy.
    source_url : str
        The query URL, or a snapshot's recorded URL.
    model : str
        Which reanalysis produced the values; :data:`OPEN_METEO_MODEL_LABEL`
        when the API does not say.
    latitude_deg, longitude_deg : float
        The grid cell the API actually used — not the coordinates requested.
    elevation_m : float
        The cell's elevation as reported by the API.
    fetched_utc : str
        When the payload was obtained, ISO-8601 UTC.
    data_version : str
        ``"open-meteo-archive:<first date>:<last date>:fetched=<date>"`` — the
        string for ``Provenance.data_versions["cloud_cover"]``. The fetch date
        is part of it because a reanalysis can be re-issued and the response
        carries no version of its own.

    Raises
    ------
    DomainError
        If ``cloud_fraction`` is not one value per sample or leaves ``[0, 1]``.
    """

    grid: TimeGrid
    cloud_fraction: FloatArray
    source_url: str
    model: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    fetched_utc: str
    data_version: str

    def __post_init__(self) -> None:
        """Validate the shape and range, then freeze the array."""
        values = np.asarray(self.cloud_fraction, dtype=np.float64)
        if values.shape != (self.grid.n,):
            raise DomainError(
                f"cloud_fraction has shape {values.shape}, but the grid has {self.grid.n} samples."
            )
        if not np.all(np.isfinite(values)) or np.any(values < 0.0) or np.any(values > 1.0):
            raise DomainError("cloud_fraction must be finite and within [0, 1].")
        object.__setattr__(self, "cloud_fraction", frozen_copy(values))


def openmeteo_url(
    *,
    latitude_deg: float,
    longitude_deg: float,
    start_utc: date,
    end_utc: date,
) -> str:
    """Build the archive query URL for hourly total cloud cover in UTC.

    Parameters
    ----------
    latitude_deg : float
        Geodetic latitude, ``[-90, 90]``. Formatted with four decimals
        (11 m), far below the 25 km grid, so nearby requests share a cache
        entry only when they are genuinely the same request.
    longitude_deg : float
        Longitude, ``[-180, 180]``, east positive.
    start_utc, end_utc : date
        First and last calendar day (inclusive, UTC). ``start_utc`` must not
        be after ``end_utc``.

    Returns
    -------
    str
        The URL.

    Raises
    ------
    DomainError
        On an out-of-range coordinate or an inverted date range.

    Examples
    --------
    >>> from datetime import date
    >>> openmeteo_url(
    ...     latitude_deg=41.275,
    ...     longitude_deg=1.9875,
    ...     start_utc=date(2025, 1, 1),
    ...     end_utc=date(2025, 1, 2),
    ... )
    'https://archive-api.open-meteo.com/v1/archive?latitude=41.2750&longitude=1.9875&start_date=2025-01-01&end_date=2025-01-02&hourly=cloud_cover&timezone=UTC'
    """
    if not (np.isfinite(latitude_deg) and -90.0 <= latitude_deg <= 90.0):
        raise DomainError(f"latitude_deg must be within [-90, 90], got {latitude_deg!r}.")
    if not (np.isfinite(longitude_deg) and -180.0 <= longitude_deg <= 180.0):
        raise DomainError(f"longitude_deg must be within [-180, 180], got {longitude_deg!r}.")
    if start_utc > end_utc:
        raise DomainError(f"start_utc {start_utc} is after end_utc {end_utc}.")
    return (
        f"{OPEN_METEO_ARCHIVE_URL}?latitude={latitude_deg:.4f}&longitude={longitude_deg:.4f}"
        f"&start_date={start_utc.strftime('%Y-%m-%d')}&end_date={end_utc.strftime('%Y-%m-%d')}"
        f"&hourly=cloud_cover&timezone=UTC"
    )


def parse_cloud_cover(
    payload: Mapping[str, Any],
    *,
    source_url: str,
    fetched_utc: str,
    degradations: DegradationLog,
    requested_latitude_deg: float | None = None,
    requested_longitude_deg: float | None = None,
) -> CloudCoverSeries:
    """Validate a decoded archive response and build a :class:`CloudCoverSeries`.

    Parameters
    ----------
    payload : Mapping[str, Any]
        The decoded JSON.
    source_url : str
        Recorded in the result.
    fetched_utc : str
        Recorded in the result and, as a date, in ``data_version``.
    degradations : DegradationLog
        Receives ``io.openmeteo-grid-offset`` (INFO) with the distance between
        the requested point and the cell the API used, when the requested
        point is given.
    requested_latitude_deg, requested_longitude_deg : float, optional
        The coordinates that were asked for, to measure the offset. Both or
        neither.

    Returns
    -------
    CloudCoverSeries
        The series.

    Raises
    ------
    DataError
        If the payload reports an error, is not in UTC, has units other than
        ``%``, has mismatched or empty arrays, unparseable timestamps, any
        ``null`` (missing hour), a value outside ``[0, 100]``, or timestamps
        that are not strictly increasing.
    """
    if payload.get("error"):
        raise DataError(
            f"Open-Meteo returned an error for {source_url!r}: {payload.get('reason', 'no reason given')!r}."
        )
    offset = payload.get("utc_offset_seconds")
    if offset != 0:
        raise DataError(
            f"Open-Meteo response for {source_url!r} has utc_offset_seconds={offset!r}; "
            f"the query must use timezone=UTC."
        )
    units = payload.get("hourly_units", {})
    if not isinstance(units, Mapping) or units.get("cloud_cover") != "%":
        raise DataError(
            f"Open-Meteo response for {source_url!r} reports cloud_cover unit "
            f"{units.get('cloud_cover') if isinstance(units, Mapping) else units!r}, expected '%'."
        )
    hourly = payload.get("hourly")
    if not isinstance(hourly, Mapping):
        raise DataError(f"Open-Meteo response for {source_url!r} has no 'hourly' block.")
    times = hourly.get("time")
    values = hourly.get("cloud_cover")
    if not isinstance(times, list) or not isinstance(values, list) or len(times) != len(values):
        raise DataError(
            f"Open-Meteo response for {source_url!r}: hourly.time and hourly.cloud_cover must be "
            f"lists of equal length."
        )
    if not times:
        raise DataError(f"Open-Meteo response for {source_url!r} holds no hours.")

    missing = [t for t, v in zip(times, values, strict=True) if v is None]
    if missing:
        shown = ", ".join(str(t) for t in missing[:5])
        raise DataError(
            f"Open-Meteo response for {source_url!r} has {len(missing)} missing hour(s) "
            f"({shown}{', ...' if len(missing) > 5 else ''}). Cloud cover is not smooth enough "
            f"to interpolate with a bounded error, so the gap is rejected rather than filled."
        )

    try:
        stamps = [datetime.strptime(str(t), _TIME_FORMAT) for t in times]
    except ValueError as exc:
        raise DataError(
            f"Open-Meteo response for {source_url!r} has a timestamp not in {_TIME_FORMAT!r}: {exc}"
        ) from exc

    try:
        percent = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise DataError(
            f"Open-Meteo response for {source_url!r} has non-numeric cloud_cover values."
        ) from exc
    if not np.all(np.isfinite(percent)) or np.any(percent < 0.0) or np.any(percent > 100.0):
        raise DataError(
            f"Open-Meteo response for {source_url!r} has cloud_cover outside [0, 100] %: "
            f"min {np.nanmin(percent)!r}, max {np.nanmax(percent)!r}."
        )

    first = stamps[0]
    t_s = np.array([(s - first).total_seconds() for s in stamps], dtype=np.float64)
    epoch_jd = calendar_to_jd(first.year, first.month, first.day, first.hour, first.minute)
    try:
        grid = TimeGrid(epoch_jd=epoch_jd, t_s=t_s)
    except DomainError as exc:
        raise DataError(f"Open-Meteo response for {source_url!r}: {exc}") from exc

    latitude_deg = float(payload["latitude"])
    longitude_deg = float(payload["longitude"])
    if (requested_latitude_deg is None) != (requested_longitude_deg is None):
        raise DomainError(
            "Give both requested_latitude_deg and requested_longitude_deg, or neither."
        )
    if requested_latitude_deg is not None and requested_longitude_deg is not None:
        distance_km = great_circle_km(
            requested_latitude_deg, requested_longitude_deg, latitude_deg, longitude_deg
        )
        degradations.info(
            "io.openmeteo-grid-offset",
            f"Open-Meteo served the reanalysis cell at ({latitude_deg:.4f}, {longitude_deg:.4f}), "
            f"{distance_km:.1f} km from the requested ({requested_latitude_deg:.4f}, "
            f"{requested_longitude_deg:.4f}).",
            where=_WHERE_PARSE,
            requested_latitude_deg=requested_latitude_deg,
            requested_longitude_deg=requested_longitude_deg,
            cell_latitude_deg=latitude_deg,
            cell_longitude_deg=longitude_deg,
            distance_km=distance_km,
        )

    return CloudCoverSeries(
        grid=grid,
        cloud_fraction=percent / 100.0,
        source_url=source_url,
        model=OPEN_METEO_MODEL_LABEL,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        elevation_m=float(payload.get("elevation", float("nan"))),
        fetched_utc=fetched_utc,
        data_version=(
            f"open-meteo-archive:{first.strftime('%Y-%m-%d')}:{stamps[-1].strftime('%Y-%m-%d')}"
            f":fetched={fetched_utc[:10]}"
        ),
    )


def great_circle_km(lat1_deg: float, lon1_deg: float, lat2_deg: float, lon2_deg: float) -> float:
    """Distance between two points on a sphere of the WGS-84 equatorial radius.

    The haversine formula, chosen over the spherical law of cosines because it
    does not lose precision for nearby points — which is the only case this
    is used for. A sphere rather than the ellipsoid: the flattening is
    ``1/298``, a 0.3 % effect on a distance that is itself only reported to
    one decimal, to describe a 25 km grid cell.

    Parameters
    ----------
    lat1_deg, lon1_deg, lat2_deg, lon2_deg : float
        Geodetic coordinates in degrees.

    Returns
    -------
    float
        Distance in km.

    Examples
    --------
    One degree of latitude along a meridian:

    >>> round(great_circle_km(0.0, 0.0, 1.0, 0.0), 2)
    111.32
    """
    lat1, lon1, lat2, lon2 = np.asarray(
        deg_to_rad(np.asarray([lat1_deg, lon1_deg, lat2_deg, lon2_deg], dtype=np.float64))
    )
    h = (
        np.sin((lat2 - lat1) / 2) ** 2
        + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    )
    return float(2.0 * WGS84_RADIUS_EQUATORIAL_KM * np.arcsin(np.sqrt(h)))


def fetch_cloud_cover(
    *,
    latitude_deg: float,
    longitude_deg: float,
    start_utc: date,
    end_utc: date,
    cache: HttpCache,
    degradations: DegradationLog,
    allow_stale: bool = False,
) -> CloudCoverSeries:
    """Fetch hourly total cloud cover for a point and a date range, through the cache.

    Parameters
    ----------
    latitude_deg, longitude_deg : float
        Station coordinates; see :func:`openmeteo_url`.
    start_utc, end_utc : date
        Inclusive UTC calendar days.
    cache : HttpCache
        A long TTL is appropriate: a finished reanalysis month does not change.
    degradations : DegradationLog
        Required; receives the cache's records and the grid-offset INFO.
    allow_stale : bool, optional
        Passed to :meth:`HttpCache.fetch`. False by default.

    Returns
    -------
    CloudCoverSeries
        The series.

    Raises
    ------
    DomainError
        Bad coordinates or dates.
    DataError
        Fetch failure, undecodable JSON, or any of the checks in
        :func:`parse_cloud_cover`.
    """
    url = openmeteo_url(
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        start_utc=start_utc,
        end_utc=end_utc,
    )
    response = cache.fetch(url, degradations=degradations, allow_stale=allow_stale)
    try:
        payload = json.loads(response.payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DataError(f"Response from {url!r} is not JSON: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise DataError(f"Response from {url!r} is JSON but not an object.")
    return parse_cloud_cover(
        payload,
        source_url=url,
        fetched_utc=response.fetched_utc,
        degradations=degradations,
        requested_latitude_deg=latitude_deg,
        requested_longitude_deg=longitude_deg,
    )
