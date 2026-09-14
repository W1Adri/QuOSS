"""The reference satellite seen from several stations, for the stage-3 aggregation tests.

`reference.py` builds one station's link — Castelldefels — and memoises the
geometry on the grid alone, because `look_angles` takes one station. The
modules `multi_ogs.py` and `relay.py` need the *same* satellite on the *same*
day from other stations, so this helper propagates the reference orbit once
and evaluates the look angles, passes, channel and finite key per station,
reusing `reference.conditions_at` so that the receiver is the one every other
number in this directory is measured with.

The stations, with where each coordinate came from
--------------------------------------------------
- ``castelldefels`` — CTTC's station, the module constants of `reference.py`.
- ``calar_alto`` — Calar Alto observatory, Almería. 37°13'25"N 2°32'46"W from
  the English Wikipedia infobox (2026-09-13; the observatory's own site,
  caha.es, states the altitude of 2168 m but prints no coordinates). Treat the
  coordinates as **approximate to the arc-second the infobox prints**; a few
  hundred metres do not move a pass.
- ``tenerife_ogs`` — ESA's Optical Ground Station at the Teide observatory,
  from the IAC's institutional page for the telescope (28.298 N, 16.511833 W,
  "2400 above the sea level"; 2026-09-13).

Separations from Castelldefels, measured by `station_separation_km`: 596.0 km
to Calar Alto and 2213.8 km to the OGS, so one station shares the reference
station's passes and the other sees different ones — which is exactly the pair
of cases the scheduler and the relay need.

Whole day, 1 s grid, 10 degree mask: the propagation is 0.05 s and the look
angles 0.03 s per station, so nothing here needs a coarser grid, and the
per-station key volumes are memoised.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from quoss.core.errors import DegradationLog
from quoss.core.types import TimeGrid
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.geometry import LookAngles, look_angles
from quoss.orbits.kepler import ClassicalElements
from quoss.orbits.propagator import PropagationMethod, Trajectory, propagate
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.system.key_volume import PassKeyVolume, pass_key_volume
from quoss.system.multi_ogs import StationSet
from quoss.system.passes import PassSamples, PassTable, find_passes

from .reference import (
    EPOCH_JD,
    ORBIT_ALTITUDE_KM,
    ORBIT_ECCENTRICITY,
    ORBIT_RAAN_RAD,
    REFERENCE_MASK_DEG,
    STATION_ALTITUDE_KM,
    STATION_LATITUDE_RAD,
    STATION_LONGITUDE_RAD,
    conditions_at,
    reference_protocol,
    reference_security,
)

STATIONS: dict[str, tuple[float, float, float]] = {
    "castelldefels": (
        float(np.rad2deg(STATION_LATITUDE_RAD)),
        float(np.rad2deg(STATION_LONGITUDE_RAD)),
        STATION_ALTITUDE_KM,
    ),
    "calar_alto": (37.22361, -2.54611, 2.168),
    "tenerife_ogs": (28.298, -16.511833, 2.400),
}
"""``name -> (latitude_deg, longitude_deg, altitude_km)``; sources in the module docstring."""

# Measured by `TestOnTheReferenceDay` in `test_multi_ogs.py`; repeated here
# because `test_relay.py` compares against the same passes.
CALAR_ALTO_FINITE_BITS = (47_108.0, 0.0, 9_817.0, 0.0)
TENERIFE_FINITE_BITS = (228_851.0, 333_846.0)


def station_set(*names: str) -> StationSet:
    """Return a `StationSet` of the named stations, in the order given."""
    chosen = names or tuple(STATIONS)
    return StationSet(
        names=tuple(chosen),
        latitude_rad=np.deg2rad(np.array([STATIONS[n][0] for n in chosen])),
        longitude_rad=np.deg2rad(np.array([STATIONS[n][1] for n in chosen])),
        altitude_km=np.array([STATIONS[n][2] for n in chosen]),
    )


@lru_cache(maxsize=4)
def trajectory(step_s: float = 1.0, duration_s: float = 86_400.0) -> tuple[Trajectory, TimeGrid]:
    """Propagate the reference orbit once for a window, memoised on the grid."""
    semi_major_axis_km = 6378.137 + ORBIT_ALTITUDE_KM
    inclination = float(
        np.ravel(
            sun_synchronous_inclination_rad(
                semi_major_axis_km=semi_major_axis_km, eccentricity=ORBIT_ECCENTRICITY
            )
        )[0]
    )
    elements = ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=ORBIT_ECCENTRICITY,
        inclination_rad=inclination,
        raan_rad=ORBIT_RAAN_RAD,
        argp_rad=0.0,
        true_anomaly_rad=0.0,
    )
    grid = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=duration_s, step_s=step_s)
    return propagate(elements, grid, method=PropagationMethod.TWO_BODY), grid


@dataclass(frozen=True)
class StationLink:
    """One station's fully wired link on the shared trajectory."""

    name: str
    angles: LookAngles
    grid: TimeGrid
    table: PassTable
    samples: PassSamples
    conditions: LinkConditions
    volume: PassKeyVolume


@lru_cache(maxsize=16)
def station_link(
    name: str,
    *,
    mask_deg: float = REFERENCE_MASK_DEG,
    step_s: float = 1.0,
    duration_s: float = 86_400.0,
) -> StationLink:
    """Return the whole chain — angles, passes, conditions, finite key — for one station."""
    latitude_deg, longitude_deg, altitude_km = STATIONS[name]
    path, grid = trajectory(step_s, duration_s)
    angles = look_angles(
        path,
        station_latitude_rad=float(np.deg2rad(latitude_deg)),
        station_longitude_rad=float(np.deg2rad(longitude_deg)),
        station_altitude_km=altitude_km,
    )
    table = find_passes(
        angles,
        grid=grid,
        minimum_elevation_rad=float(np.deg2rad(mask_deg)),
        degradations=DegradationLog(),
    )
    samples = table.samples()
    conditions = conditions_at(angles, samples)
    volume = pass_key_volume(
        conditions,
        samples=samples,
        protocol=reference_protocol(),
        security=reference_security(),
        degradations=DegradationLog(),
    )
    return StationLink(
        name=name,
        angles=angles,
        grid=grid,
        table=table,
        samples=samples,
        conditions=conditions,
        volume=volume,
    )


def synthetic_volume(
    windows: Sequence[tuple[float, float, int]],
    bits: Sequence[float],
    *,
    grid: TimeGrid | None = None,
    protocol: str = "synthetic",
) -> PassKeyVolume:
    """Build an ASYMPTOTIC `PassKeyVolume` from hand-written pass windows.

    ``windows`` are ``(start_s, end_s, satellite_index)`` on a 1 s grid of one
    day (or the ``grid`` given); ``bits`` is the key of each. Asymptotic because
    a FINITE volume must carry a `FiniteKeyResult` and this helper exists to
    exercise scheduling and relaying, not the bound. The windows must be at
    least one grid step long and, per satellite, strictly ordered, which is what
    `PassTable` demands of any real day.
    """
    axis = (
        grid
        if grid is not None
        else TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=86_400.0, step_s=1.0)
    )
    order = sorted(range(len(windows)), key=lambda i: (windows[i][2], windows[i][0]))
    starts = np.array([windows[i][0] for i in order], dtype=np.float64)
    ends = np.array([windows[i][1] for i in order], dtype=np.float64)
    satellites = np.array([windows[i][2] for i in order], dtype=np.int64)
    key = np.array([bits[i] for i in order], dtype=np.float64)
    first = np.searchsorted(axis.t_s, starts, side="left")
    last = np.searchsorted(axis.t_s, ends, side="right") - 1
    table = PassTable(
        satellite_index=satellites,
        first_index=first.astype(np.int64),
        last_index=last.astype(np.int64),
        start_s=starts,
        end_s=ends,
        culmination_s=0.5 * (starts + ends),
        culmination_elevation_rad=np.full(starts.size, 0.5),
        sampled_culmination_elevation_rad=np.full(starts.size, 0.5),
        truncated_start=np.zeros(starts.size, dtype=np.bool_),
        truncated_end=np.zeros(starts.size, dtype=np.bool_),
        minimum_elevation_rad=float(np.deg2rad(10.0)),
        grid=axis,
    )
    samples = table.samples()
    seconds = samples.segment_sum(np.asarray(samples.dwell_s))
    return PassKeyVolume(
        samples=samples,
        regime=KeyRegime.ASYMPTOTIC,
        key_bits=key,
        pulses=1e8 * seconds,
        seconds=seconds,
        finite=None,
        protocol=protocol,
    )
