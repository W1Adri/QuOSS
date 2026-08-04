"""Generate the reference data for `quoss.orbits.frames` from astropy and ERFA.

Run this by hand, never in CI. It writes ``tests/golden/data/frames_reference.json``,
which is committed and is what the test suite actually compares against. That
split is deliberate: CI stays offline and free of a heavy dependency, and
regenerating the reference numbers is an explicit, reviewable act rather than a
silent side effect of an upgrade.

This script must not import ``quoss``. Its whole value is being an independent
second opinion; importing the code under test would make it a mirror.

Usage
-----
    uv run --with astropy python tests/golden/generators/gen_frames_reference.py

Or against an existing environment that has astropy:

    <python-with-astropy> tests/golden/generators/gen_frames_reference.py

What each block is for
----------------------
``calendar_jd``
    Julian dates from calendar fields. astropy is the oracle for the leap-year
    and Gregorian bookkeeping.
``gmst``
    ``erfa.gmst82`` — the same IAU-1982 model QuOSS implements, so agreement
    tests the *implementation* (arithmetic, wrapping, units, vectorisation), not
    the model. ``erfa.gmst06`` is also recorded: the difference between the two
    is the size of the modelling choice, which the suite then asserts a bound on
    instead of assuming one.
``geodetic_to_itrf`` / ``itrf_to_geodetic``
    WGS-84 ellipsoid conversions, where astropy is exact to millimetres. The
    cases deliberately include high altitudes and near-polar latitudes, which is
    where a spherical-Earth shortcut fails worst.
``teme_to_itrf``
    astropy's full TEME to ITRS transformation, which applies polar motion and
    Earth-orientation parameters that QuOSS does not. The difference is the
    frame error budget from the module docstring, measured rather than claimed.
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import astropy
import erfa
import numpy as np
from astropy import units as u
from astropy.coordinates import ITRS, TEME, CartesianRepresentation, EarthLocation
from astropy.time import Time
from astropy.utils import iers

# Offline by design: the bundled astropy-iers-data table is what CI-adjacent
# reproducibility requires. A silent download would make this script's output
# depend on the day it ran.
iers.conf.auto_download = False
iers.conf.iers_degraded_accuracy = "ignore"

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "frames_reference.json"

# --------------------------------------------------------------------------- #
# Fixed inputs. Changing one of these changes the reference file, so they are
# written out explicitly rather than generated from a range.
# --------------------------------------------------------------------------- #
CALENDAR_CASES: list[tuple[int, int, int, int, int, float]] = [
    (2000, 1, 1, 12, 0, 0.0),  # J2000.0, the definitional anchor
    (1970, 1, 1, 0, 0, 0.0),  # Unix epoch, the other definitional anchor
    (1996, 10, 26, 14, 20, 0.0),  # a textbook worked-example date
    (2000, 2, 29, 0, 0, 0.0),  # leap day in a leap century (1 in 400)
    (1900, 1, 1, 0, 0, 0.0),  # before the non-leap century day: Vallado Alg. 14 is -1 d here
    (1900, 2, 28, 0, 0, 0.0),  # last day before 1900's missing leap day
    (1900, 3, 1, 0, 0, 0.0),  # first day after it
    (2024, 2, 29, 23, 59, 59.5),  # leap day, sub-second, end of day
    (2025, 1, 1, 0, 0, 0.0),  # the suite's reference epoch
    (2026, 7, 31, 18, 45, 30.25),  # arbitrary, with a fractional second
    (2100, 2, 28, 0, 0, 0.0),  # last day before 2100's missing leap day
    (2100, 3, 1, 0, 0, 0.0),  # first day after it: Vallado Alg. 14 is +1 d from here on
    (2100, 12, 31, 23, 59, 59.0),  # upper edge of the accepted year range
]

# Ground stations plus satellite sub-points. Latitude in degrees, longitude in
# degrees east, height in metres above the WGS-84 ellipsoid.
GEODETIC_CASES: list[tuple[str, float, float, float]] = [
    ("equator_zero", 0.0, 0.0, 0.0),
    ("north_pole", 90.0, 0.0, 0.0),
    ("south_pole", -90.0, 0.0, 0.0),
    ("mid_latitude_45", 45.0, 0.0, 0.0),
    ("castelldefels_cttc", 41.2750, 1.9875, 30.0),
    ("tenerife_ogs", 28.3000, -16.5097, 2393.0),
    ("matera_asi", 40.6486, 16.7046, 536.0),
    ("graz_slr", 47.0671, 15.4934, 541.0),
    ("high_altitude_500km", 35.0, 120.0, 500_000.0),
    ("high_altitude_1200km", -60.0, -75.0, 1_200_000.0),
    ("near_polar_2000km", 89.5, 45.0, 2_000_000.0),
    ("negative_height", 31.5, 35.5, -420.0),  # Dead Sea shore
]

# TEME position/velocity samples. Plausible LEO states rather than real ones:
# what is being tested is the frame rotation, not an ephemeris.
TEME_CASES: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = [
    ("leo_equatorial", (6878.137, 0.0, 0.0), (0.0, 7.6127, 0.0)),
    ("leo_polar", (0.0, 0.0, 7078.137), (0.0, 7.5049, 0.0)),
    ("sso_inclined", (-2456.7, 5921.3, 3120.8), (-4.512, -3.998, 3.981)),
    ("leo_descending", (4123.5, -4987.2, -2876.4), (5.102, 2.331, 3.442)),
]

# Epochs at which the TEME cases are evaluated, chosen to span a wide range of
# UT1-UTC so that the error budget is exercised at both ends.
#
# Deliberately *not* on a day carrying a leap second. QuOSS states that it does
# not model leap seconds, and the UT1-UTC table is discontinuous across one:
# anywhere on 2015-06-30, astropy's two DUT1 paths — `Time.get_delta_ut1_utc()`
# and the UT1 that `teme_to_itrs_mat` actually rotates through — disagree, by
# 0.5 s at midday and 1 s at 23:59:59, because one interpolates across the jump.
# Such a case measures leap-second bookkeeping, not the rotation under test.
# 2015-03-15 carries a similarly large negative DUT1 with both paths agreeing to
# 1e-5 s, which is what makes the error budget decomposable below.
TEME_EPOCHS_UTC: list[str] = [
    "2000-01-01T12:00:00.000",  # DUT1 ~ +0.36 s
    "2015-03-15T06:00:00.000",  # DUT1 ~ -0.55 s, near the historical extreme
    "2025-01-01T00:00:00.000",  # DUT1 ~ +0.05 s
    "2026-07-31T18:45:30.250",  # DUT1 ~ +0.01 s, and an awkward sub-second epoch
]


def _time(iso: str) -> Time:
    """Build an astropy UTC Time from an ISO string."""
    return Time(iso, format="isot", scale="utc")


def calendar_block() -> list[dict[str, Any]]:
    """Return reference Julian dates for the calendar cases."""
    rows: list[dict[str, Any]] = []
    for year, month, day, hour, minute, second in CALENDAR_CASES:
        iso = f"{year:04d}-{month:02d}-{day:02d}T{hour:02d}:{minute:02d}:{second:09.6f}"
        t = _time(iso)
        rows.append(
            {
                "year": year,
                "month": month,
                "day": day,
                "hour": hour,
                "minute": minute,
                "second": second,
                "iso_utc": iso,
                "jd_utc": float(t.jd),
            }
        )
    return rows


def gmst_block() -> list[dict[str, Any]]:
    """GMST from both the IAU-1982 and IAU-2006 models, at each calendar case."""
    rows: list[dict[str, Any]] = []
    for row in calendar_block():
        t = _time(row["iso_utc"])
        # Two-part Julian date, anchored at J2000, to keep full precision inside
        # ERFA. QuOSS passes a single float; the residual is part of what the
        # comparison measures.
        uta, utb = 2_451_545.0, float(t.jd) - 2_451_545.0
        tta, ttb = 2_451_545.0, float(t.tt.jd) - 2_451_545.0
        rows.append(
            {
                "jd_utc": float(t.jd),
                "iso_utc": row["iso_utc"],
                "gmst82_rad": float(erfa.gmst82(uta, utb)),
                "gmst06_rad": float(erfa.gmst06(uta, utb, tta, ttb)),
            }
        )
    return rows


def geodetic_block() -> list[dict[str, Any]]:
    """WGS-84 geodetic to Earth-fixed Cartesian, and back."""
    rows: list[dict[str, Any]] = []
    for name, lat_deg, lon_deg, height_m in GEODETIC_CASES:
        location = EarthLocation.from_geodetic(
            lon=lon_deg * u.deg,
            lat=lat_deg * u.deg,
            height=height_m * u.m,
            ellipsoid="WGS84",
        )
        x_km, y_km, z_km = (float(c.to_value(u.km)) for c in location.geocentric)
        back_lon, back_lat, back_height = EarthLocation.from_geocentric(
            x_km * u.km, y_km * u.km, z_km * u.km
        ).to_geodetic(ellipsoid="WGS84")
        rows.append(
            {
                "name": name,
                "latitude_deg": lat_deg,
                "longitude_deg": lon_deg,
                "height_m": height_m,
                "itrf_km": [x_km, y_km, z_km],
                "roundtrip_latitude_deg": float(back_lat.to_value(u.deg)),
                "roundtrip_longitude_deg": float(back_lon.to_value(u.deg)),
                "roundtrip_height_m": float(back_height.to_value(u.m)),
            }
        )
    return rows


def teme_block() -> list[dict[str, Any]]:
    """astropy's full TEME to ITRS transformation, including polar motion."""
    rows: list[dict[str, Any]] = []
    for iso in TEME_EPOCHS_UTC:
        t = _time(iso)
        uta, utb = 2_451_545.0, float(t.jd) - 2_451_545.0
        # astropy rotates through GMST(UT1); QuOSS passes UTC. Recording DUT1
        # lets the test separate that approximation from polar motion instead of
        # lumping both into one opaque tolerance.
        dut1_s = float(np.asarray(t.get_delta_ut1_utc().to_value(u.s)))
        jd_ut1 = float(t.jd) + dut1_s / 86_400.0
        gmst82_ut1 = float(erfa.gmst82(uta, jd_ut1 - 2_451_545.0))
        for name, r_km, v_km_s in TEME_CASES:
            teme = TEME(
                CartesianRepresentation(np.array(r_km) * u.km),
                obstime=t,
            )
            itrs = teme.transform_to(ITRS(obstime=t))
            r_itrs = itrs.cartesian.xyz.to_value(u.km)
            rows.append(
                {
                    "name": name,
                    "iso_utc": iso,
                    "jd_utc": float(t.jd),
                    "dut1_s": dut1_s,
                    "gmst82_rad": float(erfa.gmst82(uta, utb)),
                    "gmst82_ut1_rad": gmst82_ut1,
                    "r_teme_km": list(r_km),
                    "v_teme_km_s": list(v_km_s),
                    "r_itrs_astropy_km": [float(c) for c in r_itrs],
                }
            )
    return rows


def main() -> None:
    """Write the reference file."""
    payload: dict[str, Any] = {
        "manifest": {
            "purpose": (
                "Independent reference values for quoss.orbits.frames. Generated by "
                "tests/golden/generators/gen_frames_reference.py. Do not edit by hand."
            ),
            "generated_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "generator": "tests/golden/generators/gen_frames_reference.py",
            "versions": {
                "astropy": astropy.__version__,
                "pyerfa": erfa.__version__,
                "numpy": np.__version__,
                "python": platform.python_version(),
            },
            "iers_table": "bundled astropy-iers-data (auto_download disabled)",
            "notes": [
                "gmst82 is the same model QuOSS implements: agreement tests the "
                "implementation, not the model.",
                "gmst06 is recorded so the model difference can be bounded by a test "
                "instead of assumed.",
                "r_itrs_astropy_km applies polar motion and EOP; QuOSS applies only "
                "the GMST rotation. The residual is the documented frame budget.",
            ],
        },
        "calendar_jd": calendar_block(),
        "gmst": gmst_block(),
        "geodetic": geodetic_block(),
        "teme_to_itrf": teme_block(),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    counts = {k: len(v) for k, v in payload.items() if isinstance(v, list)}
    print(f"wrote {OUTPUT} with {counts}", file=sys.stderr)


if __name__ == "__main__":
    main()
