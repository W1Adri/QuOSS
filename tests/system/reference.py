"""Shared geometry and channel for the `quoss.system` tests.

One satellite, one station, one receiver, built once per session. Every number
quoted in the prose of :mod:`quoss.system.passes` and
:mod:`quoss.system.key_volume` comes from this link, so a fixture that differed
from what those docstrings describe would make the whole stage's measurements
unfalsifiable.

A plain module rather than a ``conftest.py``: ``tests/conftest.py`` already
owns that name for the whole suite, and a second one collides under ``mypy``
(``Duplicate module named "conftest"``). Nothing here needs to be a fixture — the
builders are memoised, so calling them is as cheap as injecting them, and the two
test files declare their own one-line fixtures over them.

The expensive part is the geometry — 86 401 samples of propagation plus look
angles — so it is session-scoped. The per-mask pipeline below is memoised on the
mask, because the mask sweep that measures the interior optimum asks for nine of
them and each one re-evaluates the channel over every in-pass instant.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    downlink_loss_budget,
    downlink_noise_budget,
)
from quoss.core.errors import DegradationLog
from quoss.core.types import TimeGrid
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.geometry import LookAngles, look_angles
from quoss.orbits.kepler import ClassicalElements
from quoss.orbits.propagator import PropagationMethod, propagate
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import SecurityParameters
from quoss.system.passes import PassSamples, PassTable, find_passes

STATION_LATITUDE_RAD = float(np.deg2rad(41.2750))
STATION_LONGITUDE_RAD = float(np.deg2rad(1.9875))
STATION_ALTITUDE_KM = 0.030
"""CTTC's own station at Castelldefels, the same one `orbits/geometry.py` uses."""

ORBIT_ALTITUDE_KM = 700.0
ORBIT_ECCENTRICITY = 0.001
ORBIT_RAAN_RAD = float(np.deg2rad(30.0))
EPOCH_JD = 2_460_676.5

WAVELENGTH_M = 1.55e-6
RECEIVE_APERTURE_M = 0.75
GATE_S = 1e-9
MISALIGNMENT_ERROR = 0.01
"""The 0.75 m Greek station of Ntanos et al. §4.1, the smallest of their three."""

REFERENCE_MASK_DEG = 10.0
REFERENCE_PASS_COUNT = 4
REFERENCE_DAY_NUMBER = 2_460_677
"""JDN of 2025-01-01, the UTC day every pass of the reference window starts in."""

# Measured by `TestWhatTheAsymptoticRateOverstates`; repeated here because three
# test classes compare against them and a second transcription would drift.
REFERENCE_FINITE_BITS = (190_581.0, 0.0, 242_404.0, 0.0)
REFERENCE_ASYMPTOTIC_BITS = (1_548_341.3, 319_898.3, 1_709_160.4, 199_280.8)
REFERENCE_FINITE_DAY_BITS = 432_985.0


def reference_security() -> SecurityParameters:
    """Return the per-block failure probabilities every measurement here uses."""
    return SecurityParameters(correctness=1e-10, secrecy=1e-10)


def reference_protocol() -> Bb84DecoyProtocol:
    """Return Ntanos et al.'s decoy configuration, driving both regimes."""
    return Bb84DecoyProtocol.ntanos_2021()


@lru_cache(maxsize=8)
def geometry(step_s: float = 1.0, duration_s: float = 86_400.0) -> tuple[LookAngles, TimeGrid]:
    """Return look angles and the grid for one window of the reference pass geometry.

    Memoised on ``(step_s, duration_s)``: the grid-resolution tests ask for a
    dozen steps and each propagation is the slowest thing in this directory.
    """
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
    trajectory = propagate(elements, grid, method=PropagationMethod.TWO_BODY)
    return (
        look_angles(
            trajectory,
            station_latitude_rad=STATION_LATITUDE_RAD,
            station_longitude_rad=STATION_LONGITUDE_RAD,
            station_altitude_km=STATION_ALTITUDE_KM,
        ),
        grid,
    )


def conditions_at(
    angles: LookAngles,
    samples: PassSamples,
    *,
    sky_radiance_w_m2_um_sr: float = NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    degradations: DegradationLog | None = None,
) -> LinkConditions:
    """Evaluate the reference channel at exactly the samples a pass table lists.

    This is the contract ``key_volume.py`` documents, written out once: the caller
    indexes the look angles with ``samples.satellite_index`` and
    ``samples.sample_index``, in that order, and hands back a flat
    :class:`~quoss.qkd.base.LinkConditions`.
    """
    log = degradations if degradations is not None else DegradationLog()
    chain = receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )
    elevation = np.asarray(angles.elevation_rad)[samples.satellite_index, samples.sample_index]
    slant_range = np.asarray(angles.range_km)[samples.satellite_index, samples.sample_index]
    loss = downlink_loss_budget(
        elevation,
        range_km=slant_range,
        wavelength_m=WAVELENGTH_M,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=RECEIVE_APERTURE_M,
        zenith_transmittance=1.0,
        pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
        receiver_efficiency=chain,
        degradations=log,
    )
    noise = downlink_noise_budget(
        sky_radiance_w_m2_um_sr,
        wavelength_m=WAVELENGTH_M,
        receive_aperture_m=RECEIVE_APERTURE_M,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
        gate_duration_s=GATE_S,
        receiver_efficiency=chain,
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        detector_count=2,
        degradations=log,
    )
    return LinkConditions(
        transmittance=loss.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=MISALIGNMENT_ERROR,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=GATE_S,
    )


@dataclass(frozen=True)
class Link:
    """One fully wired reference link: geometry, passes, samples and conditions."""

    angles: LookAngles
    grid: TimeGrid
    table: PassTable
    samples: PassSamples
    conditions: LinkConditions


@lru_cache(maxsize=32)
def link(
    mask_deg: float = REFERENCE_MASK_DEG,
    *,
    step_s: float = 1.0,
    duration_s: float = 86_400.0,
    sky_radiance_w_m2_um_sr: float = NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
) -> Link:
    """Return the whole chain for one elevation mask, memoised."""
    angles, grid = geometry(step_s, duration_s)
    table = find_passes(
        angles,
        grid=grid,
        minimum_elevation_rad=float(np.deg2rad(mask_deg)),
        degradations=DegradationLog(),
    )
    samples = table.samples()
    return Link(
        angles=angles,
        grid=grid,
        table=table,
        samples=samples,
        conditions=conditions_at(angles, samples, sky_radiance_w_m2_um_sr=sky_radiance_w_m2_um_sr),
    )
