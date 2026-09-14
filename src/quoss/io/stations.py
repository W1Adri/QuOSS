"""The optical-ground-station catalogue: ``data/ogs.yaml``, read and checked.

What a catalogue entry is
-------------------------
An **optical ground station** (OGS) is a telescope on the ground that receives
the satellite's photons; in this project it is described by four numbers —
latitude, longitude, altitude, receive aperture — and the aperture is the one
that matters most, because the geometric loss goes with its square. The
catalogue exists so that a scenario can say ``station: esa_ogs_tenerife`` and
get the same four numbers every time, and so that the numbers carry the
**source** they were read from and the **precision** that source printed.

Why the source and the precision are mandatory fields, not comments
-------------------------------------------------------------------
Because a coordinate is the kind of number that is plausible at any value.
41.27 N and 41.72 N are both in Catalonia; only one is Castelldefels, and
nothing in a link budget would notice the swap. The defence is the same one
``docs/adr/0009`` applies to formulas: a number in this file is a promise that
a reader can open the stated source and find it. The loader enforces that
``source`` and ``coordinates_precision`` are non-empty strings; it cannot
check that they are true, which is why the file says *when* each page was
opened.

Why the aperture may be ``null`` and what that costs the caller
---------------------------------------------------------------
Two of the four shipped stations (Matera, Graz) come from ILRS pages that
give coordinates but not the telescope diameter. The obvious move — filling
in the number "everybody knows" — is exactly the invented-number-labelled-
published move the project forbids. So ``receive_aperture_m`` is ``None`` for
them, and :meth:`StationEntry.to_station_spec_kwargs` raises
:class:`~quoss.core.errors.DataError` unless the caller passes an aperture of
their own. A scenario using such a station therefore has to state the
aperture where a reviewer can see it.

Why this is a small frozen dataclass and not ``scenario.StationSpec``
---------------------------------------------------------------------
The catalogue stores facts about a place; ``StationSpec`` (stage 4) adds the
modelling choices a link needs — ground ``Cn2``, wind speed, a cloud fraction
— and is validated by Pydantic against the rest of a scenario. Keeping the two
apart means this module does not import the scenario schema and cannot be
broken by it; ``to_station_spec_kwargs`` is the bridge, returning the
``StationSpec`` field names of the stage-4 contract as a plain dict.

Examples
--------
>>> catalogue = load_station_catalogue()
>>> [s.name for s in catalogue]
['castelldefels_cttc', 'esa_ogs_tenerife', 'matera_mlro', 'graz_lustbuehel']
>>> find_station(catalogue, "castelldefels_cttc").to_station_spec_kwargs()
{'name': 'castelldefels_cttc', 'latitude_deg': 41.275, 'longitude_deg': 1.9875, 'altitude_m': 30.0, 'receive_aperture_m': 0.75}
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from quoss.core.errors import DataError

__all__ = [
    "DEFAULT_CATALOGUE_PATH",
    "StationEntry",
    "find_station",
    "load_station_catalogue",
]

DEFAULT_CATALOGUE_PATH = Path(__file__).resolve().parents[3] / "data" / "ogs.yaml"
"""``<repo>/data/ogs.yaml`` for a checkout; see :mod:`quoss.io.snapshots` for the wheel caveat."""

_SCHEMA_VERSION = 1
_REQUIRED = (
    "name",
    "latitude_deg",
    "longitude_deg",
    "altitude_m",
    "receive_aperture_m",
    "source",
    "coordinates_precision",
)
_OPTIONAL = ("note",)

# Dead Sea shore to the highest plausible telescope site: outside this window a
# value is a typo (metres given as km, a sign error), not a station.
_ALTITUDE_MIN_M = -500.0
_ALTITUDE_MAX_M = 9000.0


@dataclass(frozen=True, slots=True)
class StationEntry:
    """One catalogue row, validated.

    Parameters
    ----------
    name : str
        Unique lowercase identifier a scenario refers to.
    latitude_deg : float
        Geodetic latitude, north positive, ``[-90, 90]``.
    longitude_deg : float
        Longitude, east positive, ``[-180, 180]``.
    altitude_m : float
        Height above mean sea level, ``[-500, 9000]``.
    receive_aperture_m : float or None
        Receive telescope primary diameter, positive; ``None`` if the source
        does not state it.
    source : str
        Where the numbers were read, with the date the source was opened.
    coordinates_precision : str
        How many digits the source printed and what that is worth on the ground.
    note : str, optional
        Free text.

    Raises
    ------
    DataError
        If any field is out of range or a required string is empty.
    """

    name: str
    latitude_deg: float
    longitude_deg: float
    altitude_m: float
    receive_aperture_m: float | None
    source: str
    coordinates_precision: str
    note: str = ""

    def __post_init__(self) -> None:
        """Check ranges; a catalogue is data, so failures are :class:`DataError`."""
        for label in ("name", "source", "coordinates_precision"):
            if not str(getattr(self, label)).strip():
                raise DataError(f"Station {self.name!r}: {label} must be a non-empty string.")
        if not (np.isfinite(self.latitude_deg) and -90.0 <= self.latitude_deg <= 90.0):
            raise DataError(
                f"Station {self.name!r}: latitude_deg {self.latitude_deg!r} outside [-90, 90]."
            )
        if not (np.isfinite(self.longitude_deg) and -180.0 <= self.longitude_deg <= 180.0):
            raise DataError(
                f"Station {self.name!r}: longitude_deg {self.longitude_deg!r} outside [-180, 180]."
            )
        if not (
            np.isfinite(self.altitude_m) and _ALTITUDE_MIN_M <= self.altitude_m <= _ALTITUDE_MAX_M
        ):
            raise DataError(
                f"Station {self.name!r}: altitude_m {self.altitude_m!r} outside "
                f"[{_ALTITUDE_MIN_M}, {_ALTITUDE_MAX_M}] m."
            )
        if self.receive_aperture_m is not None and not (
            np.isfinite(self.receive_aperture_m) and self.receive_aperture_m > 0.0
        ):
            raise DataError(
                f"Station {self.name!r}: receive_aperture_m must be positive or null, "
                f"got {self.receive_aperture_m!r}."
            )

    def to_station_spec_kwargs(
        self, *, receive_aperture_m: float | None = None
    ) -> dict[str, float | str]:
        """Return the ``StationSpec`` fields this entry can fill, as a dict.

        Parameters
        ----------
        receive_aperture_m : float, optional
            Overrides the catalogue aperture; required when the catalogue has
            none. Positive.

        Returns
        -------
        dict[str, float | str]
            ``name``, ``latitude_deg``, ``longitude_deg``, ``altitude_m``,
            ``receive_aperture_m`` — the stage-4 ``StationSpec`` names. The
            modelling fields (``ground_cn2_m23``, ``ground_wind_speed_m_s``,
            ``cloud_fraction``) are not the catalogue's to set.

        Raises
        ------
        DataError
            If neither the catalogue nor the caller gives an aperture, or the
            caller's is not positive.
        """
        aperture = self.receive_aperture_m if receive_aperture_m is None else receive_aperture_m
        if aperture is None:
            raise DataError(
                f"Station {self.name!r} has no sourced receive aperture ({self.note.strip() or 'see source'}); "
                f"pass receive_aperture_m explicitly."
            )
        if not (np.isfinite(aperture) and aperture > 0.0):
            raise DataError(f"receive_aperture_m must be positive, got {aperture!r}.")
        return {
            "name": self.name,
            "latitude_deg": float(self.latitude_deg),
            "longitude_deg": float(self.longitude_deg),
            "altitude_m": float(self.altitude_m),
            "receive_aperture_m": float(aperture),
        }


def load_station_catalogue(path: Path | None = None) -> tuple[StationEntry, ...]:
    """Read and validate the catalogue.

    Parameters
    ----------
    path : Path, optional
        :data:`DEFAULT_CATALOGUE_PATH` by default.

    Returns
    -------
    tuple[StationEntry, ...]
        In file order.

    Raises
    ------
    DataError
        If the file is missing or not YAML, the schema version is not 1, the
        ``stations`` list is absent or empty, an entry has missing or unknown
        keys or a value of the wrong type, or two entries share a name.
    """
    file = DEFAULT_CATALOGUE_PATH if path is None else Path(path)
    if not file.is_file():
        raise DataError(f"Station catalogue not found at {file}.")
    try:
        document = yaml.safe_load(file.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DataError(f"Station catalogue {file} is not valid YAML: {exc}") from exc
    if not isinstance(document, Mapping):
        raise DataError(
            f"Station catalogue {file} must be a mapping with 'schema_version' and 'stations'."
        )
    if document.get("schema_version") != _SCHEMA_VERSION:
        raise DataError(
            f"Station catalogue {file} has schema_version {document.get('schema_version')!r}, "
            f"this loader reads {_SCHEMA_VERSION}."
        )
    raw_stations = document.get("stations")
    if not isinstance(raw_stations, Sequence) or isinstance(raw_stations, str) or not raw_stations:
        raise DataError(f"Station catalogue {file} must hold a non-empty 'stations' list.")

    entries: list[StationEntry] = []
    seen: set[str] = set()
    for index, raw in enumerate(raw_stations):
        entry = _entry_from_mapping(raw, index=index, file=file)
        if entry.name in seen:
            raise DataError(f"Station catalogue {file}: duplicate station name {entry.name!r}.")
        seen.add(entry.name)
        entries.append(entry)
    return tuple(entries)


def find_station(catalogue: Sequence[StationEntry], name: str) -> StationEntry:
    """Return the entry called ``name``.

    Parameters
    ----------
    catalogue : Sequence[StationEntry]
        From :func:`load_station_catalogue`.
    name : str
        Exact identifier.

    Returns
    -------
    StationEntry
        The match.

    Raises
    ------
    DataError
        If absent; the message lists the available names.
    """
    for entry in catalogue:
        if entry.name == name:
            return entry
    raise DataError(
        f"No station {name!r} in the catalogue. Available: {', '.join(e.name for e in catalogue)}."
    )


def _entry_from_mapping(raw: Any, *, index: int, file: Path) -> StationEntry:
    if not isinstance(raw, Mapping):
        raise DataError(f"Station catalogue {file}: entry {index} is not a mapping.")
    keys = set(raw)
    missing = set(_REQUIRED) - keys
    unknown = keys - set(_REQUIRED) - set(_OPTIONAL)
    if missing or unknown:
        raise DataError(
            f"Station catalogue {file}: entry {index} ({raw.get('name', '?')!r}) "
            f"missing {sorted(missing)}, unknown {sorted(unknown)}."
        )
    name = _text(raw, "name", index=index, file=file)
    return StationEntry(
        name=name,
        latitude_deg=_number(raw, "latitude_deg", name=name, file=file),
        longitude_deg=_number(raw, "longitude_deg", name=name, file=file),
        altitude_m=_number(raw, "altitude_m", name=name, file=file),
        receive_aperture_m=(
            None
            if raw["receive_aperture_m"] is None
            else _number(raw, "receive_aperture_m", name=name, file=file)
        ),
        source=_text(raw, "source", index=index, file=file),
        coordinates_precision=_text(raw, "coordinates_precision", index=index, file=file),
        note=_text(raw, "note", index=index, file=file) if "note" in raw else "",
    )


def _number(raw: Mapping[str, Any], key: str, *, name: str, file: Path) -> float:
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DataError(
            f"Station catalogue {file}: {name!r}.{key} must be a number, got {value!r}."
        )
    return float(value)


def _text(raw: Mapping[str, Any], key: str, *, index: int, file: Path) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise DataError(
            f"Station catalogue {file}: entry {index}.{key} must be a string, got {value!r}."
        )
    return value
