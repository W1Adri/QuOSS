"""Generate the reference data for `quoss.orbits.geometry` from astropy's AltAz frame.

Run this by hand, never in CI. It writes
``tests/golden/data/geometry_reference.json``, which is committed and is what
the test suite actually compares against — see ``tests/golden/README.md`` for
why the split exists and ``tests/golden/generators/gen_frames_reference.py``,
whose station list and TEME states this script deliberately reuses so the two
reference files describe the same satellites and sites.

This script must not import ``quoss``. Its whole value is being an independent
second opinion; importing the code under test would make it a mirror.

Usage
-----
    uv run --group reference python tests/golden/generators/gen_geometry_reference.py

What each case is
------------------
A station (geodetic latitude/longitude/height) paired with a satellite state
(TEME position and velocity, km and km/s) at a UTC epoch. astropy builds a
``TEME`` frame position, transforms it to ``AltAz`` at the station's
``EarthLocation`` and ``obstime``, and records the resulting altitude
(elevation), azimuth and distance (slant range) with atmospheric refraction
turned off (``pressure=0``, astropy's default) — the same purely geometric
quantity ``quoss.orbits.geometry.look_angles`` computes, with no refraction
model to disagree about.

Velocity is not used by this generator at all: AltAz is a function of position
only, so it says nothing about range-rate or the point-ahead angle.
``tests/golden/README.md`` states this as a known gap — no independent oracle
backs those two quantities yet — and the velocity is carried in the output
purely so the test file can build a complete ``Trajectory`` from each case.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import astropy
import numpy as np
from astropy import units as u
from astropy.coordinates import (
    TEME,
    AltAz,
    CartesianDifferential,
    CartesianRepresentation,
    EarthLocation,
)
from astropy.time import Time
from astropy.utils import iers

# Offline by design, same rationale as gen_frames_reference.py. auto_max_age
# additionally disables the "IERS table is stale" check: astropy's own TEME ->
# AltAz transform (unlike gen_frames_reference.py's direct erfa.gmst82 calls)
# converts through UT1 internally, which triggers that check for any epoch
# more than 30 days newer than the bundled table. The bundled table's
# UT1-UTC values are still accurate to well under a second at these epochs —
# see quoss.orbits.frames' module docstring for why that is negligible here
# (under ~460 m at LEO range) — so a fresher table would not change this
# comparison, only silence a warning about its own age.
iers.conf.auto_download = False
iers.conf.auto_max_age = None
iers.conf.iers_degraded_accuracy = "ignore"

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "geometry_reference.json"

# Stations: a subset of gen_frames_reference.py's GEODETIC_CASES, reused by
# name so a reader who has seen that file recognises these immediately.
# Latitude/longitude in degrees, height in km.
STATIONS: list[tuple[str, float, float, float]] = [
    ("castelldefels_cttc", 41.2750, 1.9875, 0.030),
    ("tenerife_ogs", 28.3000, -16.5097, 2.393),
    ("matera_asi", 40.6486, 16.7046, 0.536),
    ("graz_slr", 47.0671, 15.4934, 0.541),
]

# Satellite TEME states: plausible LEO position/velocity pairs, not computed
# by any propagator — what is being tested is the look-angle geometry, not an
# ephemeris. Two are the same vectors gen_frames_reference.py uses (so a
# reader can cross-reference), one is new and chosen to sit below the horizon
# for at least one station below, since a negative-elevation case is as
# important to check as a visible one.
TEME_STATES: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = [
    ("leo_polar", (0.0, 0.0, 7078.137), (0.0, 7.5049, 0.0)),
    ("sso_inclined", (-2456.7, 5921.3, 3120.8), (-4.512, -3.998, 3.981)),
    ("leo_descending", (4123.5, -4987.2, -2876.4), (5.102, 2.331, 3.442)),
]

EPOCHS_UTC: list[str] = [
    "2025-01-01T00:00:00.000",
    "2026-07-31T18:45:30.250",
]


def look_angles_block() -> list[dict[str, Any]]:
    """Elevation, azimuth and range for every station x satellite x epoch case."""
    rows: list[dict[str, Any]] = []
    for iso in EPOCHS_UTC:
        t = Time(iso, format="isot", scale="utc")
        for state_name, r_km, v_km_s in TEME_STATES:
            teme = TEME(
                CartesianRepresentation(np.array(r_km) * u.km).with_differentials(
                    CartesianDifferential(np.array(v_km_s) * u.km / u.s)
                ),
                obstime=t,
            )
            for station_name, lat_deg, lon_deg, height_km in STATIONS:
                location = EarthLocation.from_geodetic(
                    lon=lon_deg * u.deg,
                    lat=lat_deg * u.deg,
                    height=height_km * u.km,
                    ellipsoid="WGS84",
                )
                altaz = teme.transform_to(AltAz(obstime=t, location=location, pressure=0 * u.hPa))
                rows.append(
                    {
                        "name": f"{station_name}__{state_name}__{iso}",
                        "station_name": station_name,
                        "station_latitude_deg": lat_deg,
                        "station_longitude_deg": lon_deg,
                        "station_altitude_km": height_km,
                        "state_name": state_name,
                        "iso_utc": iso,
                        "jd_utc": float(t.jd),
                        "r_teme_km": list(r_km),
                        "v_teme_km_s": list(v_km_s),
                        "elevation_astropy_deg": float(altaz.alt.to_value(u.deg)),
                        "azimuth_astropy_deg": float(altaz.az.to_value(u.deg)),
                        "range_astropy_km": float(altaz.distance.to_value(u.km)),
                    }
                )
    return rows


def main() -> None:
    """Write the reference file."""
    rows = look_angles_block()
    payload: dict[str, Any] = {
        "manifest": {
            "purpose": (
                "Independent reference values for quoss.orbits.geometry.look_angles. "
                "Generated by tests/golden/generators/gen_geometry_reference.py. "
                "Do not edit by hand."
            ),
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "generator": "tests/golden/generators/gen_geometry_reference.py",
            "versions": {
                "astropy": astropy.__version__,
                "numpy": np.__version__,
                "python": platform.python_version(),
            },
            "iers_table": "bundled astropy-iers-data (auto_download disabled)",
            "notes": [
                "AltAz built with pressure=0 (astropy's default): no atmospheric "
                "refraction, matching look_angles' purely geometric elevation.",
                "Velocity fields are not used to derive anything in this file; AltAz "
                "is a function of position only. Range-rate and the point-ahead "
                "angle have no independent oracle here — see tests/golden/README.md.",
            ],
        },
        "look_angles": rows,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {OUTPUT} with {len(rows)} look_angles cases", file=sys.stderr)


if __name__ == "__main__":
    main()
