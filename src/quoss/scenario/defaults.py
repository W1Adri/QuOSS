"""Named scenarios: the project's reference link, and Ntanos et al. 2021's three stations.

Why builders and not YAML files only
------------------------------------
The versioned files under ``scenarios/`` are what a user edits. The builders
here are what a *test* calls, and they exist because a number that lives only
in a file cannot be asserted against the constants it came from. Every value
below is either a module constant of the physics layer with its citation
(``NTANOS_*``) or a project choice named as such, so that
``tests/scenario/test_defaults.py`` can check that
:func:`reference_castelldefels` converts into exactly the inputs
``tests/system/reference.py`` builds by hand — the link every number in
``docs/adr/0011-the-block-is-the-pass.md`` was measured on — and
``tests/scenario/test_scenario_files.py`` can check that the committed YAML
equals the builder. A drift between the three is then a failing test, not a
figure caption that quietly stopped describing its data.

What is a Ntanos number and what is a choice
--------------------------------------------
:func:`ntanos_2021` takes its receiver, transmitter, protocol and elevation
floor from the ``NTANOS_*`` constants, each of which cites a sentence of the
paper (``docs/adr/0009-citation-policy.md``). The station coordinates and the
orbit's altitude and inclination are also printed in the paper (§2 and §4.3,
re-read from the PDF on 2026-09-13 while writing this module). What the paper
does **not** state, and this module therefore chooses and says so:

* The orbit's right ascension of the ascending node, argument of periapsis,
  true anomaly and eccentricity: the paper propagates ten satellites with STK
  and never prints their elements. One satellite, circular, RAAN 0 deg,
  starting at the node. That fixes *which* passes occur; it is not a paper
  number and no test claims it is.
* The epoch: 2025-01-01T00:00Z, the same as the reference link.
* One UTC day at 1 s — the paper's Figure 6 covers a month at 10 s.

One thing has to be said in the open because copying it would be wrong: the
paper's §2 prints "Skinakas (South, longitude: 35.2118°, latitude: 24.8981°)",
and the same for Helmos and Cholomondas. Those labels are **swapped**. Skinakas
Observatory is on Crete, at 35.2° north and 24.9° east — 35° east longitude
is in Anatolia, nowhere near a Greek observatory — and the same holds for the
other two sites (Helmos 37.99 N 22.20 E, Cholomondas 40.34 N 23.51 E). The
numbers are used as printed and the labels are corrected, which the docstring
of :func:`ntanos_2021` repeats so a reader comparing against the PDF is not
surprised.

And the inclination: the paper prints 97.4 deg for its 600 km sun-synchronous
constellation (§4.3). The sun-synchronous condition at 600 km circular gives
97.79 deg (:func:`quoss.orbits.constellations.sun_synchronous_inclination_rad`,
measured in ``tests/scenario/test_defaults.py::TestNtanos2021::test_the_printed_inclination_is_not_the_sun_synchronous_one``).
The scenario uses the **printed** value, because that is the paper's parameter
and the point of the scenario is to reproduce the paper; the 0.4 deg is the
paper's to explain, and it is written here so nobody "fixes" it into
``sun_synchronous: true`` without knowing what changes.
"""

from __future__ import annotations

import datetime as dt

from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
)
from quoss.channel.link_budget import (
    NTANOS_OGS_APERTURES_M,
    NTANOS_ORBIT_HEIGHT_KM,
    NTANOS_OUTAGE_PROBABILITY,
    NTANOS_TRANSMIT_APERTURE_M,
)
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.scenario.models import (
    BackgroundSpec,
    ChannelSpec,
    KeplerOrbit,
    OrbitSpec,
    PassSpec,
    ProtocolSpec,
    ReceiverSpec,
    Scenario,
    SecuritySpec,
    StationSpec,
    TimeSpec,
    TransmitterSpec,
)

__all__ = [
    "NTANOS_DEAD_TIME_NS",
    "NTANOS_FIELD_OF_VIEW_URAD",
    "NTANOS_FILTER_BANDWIDTH_NM",
    "NTANOS_GATE_NS",
    "NTANOS_MINIMUM_ELEVATION_DEG",
    "NTANOS_POINTING_JITTER_URAD",
    "NTANOS_STATIONS",
    "NTANOS_TIMING_JITTER_FWHM_PS",
    "REFERENCE_EPOCH_UTC",
    "ntanos_2021",
    "reference_castelldefels",
]

REFERENCE_EPOCH_UTC = dt.datetime(2025, 1, 1, tzinfo=dt.UTC)
"""2025-01-01T00:00Z, Julian date 2460676.5: the epoch of ``tests/system/reference.py``."""

_WAVELENGTH_NM = 1550.0
_MISALIGNMENT_ERROR = 0.01
"""The 1 % intrinsic error of the reference link (``tests/system/reference.py``)."""

# The Ntanos et al. 2021 §4.1 receiver and transmitter in the *user's* units, as
# literals. Not derived from the SI constants at run time, because the derivation
# is not exact in binary: NTANOS_SNSPD_DEAD_TIME_S * 1e9 is 29.999999999999996,
# and a scenario file that says that instead of 30 is a file nobody would write
# — and one whose hash differs from the hand-written YAML's. Each literal is tied
# to its constant by tests/scenario/test_defaults.py::TestTheDefaultsAreTheNtanosConstants,
# which converts the literal back to SI and compares to within float rounding.
NTANOS_POINTING_JITTER_URAD = 0.75
"""NTANOS_POINTING_JITTER_RAD in microradians."""
NTANOS_DEAD_TIME_NS = 30.0
"""NTANOS_SNSPD_DEAD_TIME_S in nanoseconds."""
NTANOS_GATE_NS = 1.0
"""NTANOS_SNSPD_GATE_DURATION_S in nanoseconds."""
NTANOS_TIMING_JITTER_FWHM_PS = 50.0
"""NTANOS_SNSPD_TIMING_JITTER_FWHM_S in picoseconds."""
NTANOS_FIELD_OF_VIEW_URAD = 100.0
"""NTANOS_RECEIVER_FIELD_OF_VIEW_RAD in microradians, full angle."""
NTANOS_FILTER_BANDWIDTH_NM = 0.2
"""NTANOS_FILTER_BANDWIDTH_M in nanometres."""

NTANOS_STATIONS: dict[float, tuple[str, float, float, float]] = {
    0.75: ("cholomondas", 40.3419, 23.5060, 850.0),
    1.3: ("skinakas", 35.2118, 24.8981, 1750.0),
    2.3: ("helmos", 37.9855, 22.1984, 2340.0),
}
"""Aperture (m) -> (name, latitude deg N, longitude deg E, height m), Ntanos et al. 2021 §2.

The paper prints each pair with the labels swapped ("longitude: 35.2118°,
latitude: 24.8981°" for Skinakas, which is on Crete at 35.2 N); see the module
docstring. Apertures from §4.1, in the same order as
:data:`quoss.channel.link_budget.NTANOS_OGS_APERTURES_M`.
"""

_NTANOS_INCLINATION_DEG = 97.4
"""Printed in §4.3: "an inclination angle of 97.4°". Not the SSO value at 600 km (97.79)."""

NTANOS_MINIMUM_ELEVATION_DEG = 20.0
"""The §4.1 elevation floor in the user's unit.

Written as the literal the paper prints rather than as
``rad_to_deg(NTANOS_MINIMUM_ELEVATION_RAD)``, which is ``20.000000000000007``:
the file a user reads should say 20, and ``tests/scenario/test_defaults.py``
asserts the two agree to float precision so they cannot drift apart.
"""


def _ntanos_transmitter() -> TransmitterSpec:
    return TransmitterSpec(
        wavelength_nm=_WAVELENGTH_NM,
        aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        pointing_jitter_urad=NTANOS_POINTING_JITTER_URAD,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    )


def _ntanos_receiver() -> ReceiverSpec:
    return ReceiverSpec(
        detector_efficiency=NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        detector_count=2,
        afterpulse_probability=NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
        dead_time_ns=NTANOS_DEAD_TIME_NS,
        gate_ns=NTANOS_GATE_NS,
        timing_jitter_fwhm_ps=NTANOS_TIMING_JITTER_FWHM_PS,
        field_of_view_urad=NTANOS_FIELD_OF_VIEW_URAD,
        filter_bandwidth_nm=NTANOS_FILTER_BANDWIDTH_NM,
    )


def _ntanos_protocol() -> ProtocolSpec:
    protocol = Bb84DecoyProtocol.ntanos_2021()
    return ProtocolSpec(
        name=Bb84DecoyProtocol.name,
        signal_intensity=protocol.signal_intensity,
        decoy_intensity=protocol.decoy_intensity,
        signal_probability=protocol.signal_probability,
        decoy_probability=protocol.decoy_probability,
        vacuum_probability=protocol.vacuum_probability,
        error_correction_efficiency=protocol.error_correction_efficiency,
        misalignment_error=_MISALIGNMENT_ERROR,
    )


def reference_castelldefels() -> Scenario:
    """Return the project's reference scenario, field for field the reference link.

    CTTC's own station at Castelldefels (41.2750 N, 1.9875 E, 30 m; the
    coordinates ``orbits/geometry.py`` uses) with a 0.75 m telescope; a 700 km
    sun-synchronous satellite with ``e = 0.001`` and RAAN 30 deg, starting at
    the node at 2025-01-01T00:00Z; one UTC day at 1 s; the Ntanos et al. 2021
    transmitter, receiver chain and protocol; the study-night radiance
    1.5e-4 W/(m^2 um sr); no atmospheric extinction (``zenith_transmittance =
    1.0``, declared, ADR 0009 gap 14); a 10 deg mask; ``eps = 1e-10`` each.

    On this link ``docs/adr/0011-the-block-is-the-pass.md`` measured four
    passes, 432 985 finite bits against 3.78 Mbit asymptotic
    (``tests/system/test_key_volume.py::TestWhatTheAsymptoticRateOverstates``).
    ``tests/scenario/test_defaults.py::TestReferenceCastelldefels`` asserts the
    conversion reproduces every physics input of ``tests/system/reference.py``.

    Returns
    -------
    Scenario
        The reference scenario.
    """
    return Scenario(
        name="reference_castelldefels",
        description=(
            "QuOSS reference downlink: Castelldefels 0.75 m, 700 km SSO, Ntanos et al. 2021 "
            "receiver and protocol, clear moonless study night, 10 deg mask, one UTC day at 1 s."
        ),
        orbit=OrbitSpec(
            kepler=KeplerOrbit(
                altitude_km=700.0,
                eccentricity=0.001,
                sun_synchronous=True,
                raan_deg=30.0,
                argp_deg=0.0,
                true_anomaly_deg=0.0,
                method="two_body",
            )
        ),
        stations=[
            StationSpec(
                name="castelldefels",
                latitude_deg=41.2750,
                longitude_deg=1.9875,
                altitude_m=30.0,
                receive_aperture_m=0.75,
            )
        ],
        transmitter=_ntanos_transmitter(),
        channel=ChannelSpec(
            zenith_transmittance=1.0,
            static_loss_db=0.0,
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
        ),
        receiver=_ntanos_receiver(),
        background=BackgroundSpec(sky_radiance_w_m2_um_sr=NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR),
        protocol=_ntanos_protocol(),
        security=SecuritySpec(correctness=1e-10, secrecy=1e-10, compose_daily=True),
        time=TimeSpec(epoch_utc=REFERENCE_EPOCH_UTC, duration_s=86_400.0, step_s=1.0),
        passes=PassSpec(minimum_elevation_deg=10.0),
    )


def ntanos_2021(aperture_m: float) -> Scenario:
    """Return the Ntanos et al. 2021 link for one of their three ground stations.

    Parameters
    ----------
    aperture_m : float
        One of ``0.75``, ``1.3`` or ``2.3`` — Cholomondas, Skinakas and Helmos
        (§4.1), the keys of :data:`NTANOS_STATIONS`.

    Returns
    -------
    Scenario
        Their 600 km orbit (§4.3, inclination 97.4 deg as printed; RAAN,
        anomaly and the circular shape are this module's choice), the station
        at its printed coordinates with the latitude/longitude labels corrected
        (module docstring), the §4.1 transmitter and receiver, the §4.1 decoy
        protocol, the §4.2.2 study-night radiance, their 1 % outage and 20 deg
        elevation floor, no extinction (they state none; ADR 0009 gap 14).

    Raises
    ------
    ValueError
        If ``aperture_m`` is not one of the three published apertures. The
        paper's design conclusions differ between the three, so an
        interpolated fourth station is not a Ntanos scenario.

    Examples
    --------
    >>> scenario = ntanos_2021(2.3)
    >>> scenario.stations[0].name
    'helmos'
    >>> scenario.passes.minimum_elevation_deg
    20.0
    """
    if aperture_m not in NTANOS_STATIONS:
        raise ValueError(
            f"aperture_m must be one of {list(NTANOS_OGS_APERTURES_M)} (Ntanos et al. 2021 "
            f"§4.1), got {aperture_m!r}."
        )
    name, latitude_deg, longitude_deg, altitude_m = NTANOS_STATIONS[aperture_m]
    return Scenario(
        name=f"ntanos2021_{name}",
        description=(
            f"Ntanos et al. 2021 (Photonics 8(12):544) downlink to {name.capitalize()} "
            f"({aperture_m} m): 600 km orbit at the printed 97.4 deg inclination, §4.1 "
            "transmitter, receiver and protocol, study-night radiance, 20 deg floor. RAAN, "
            "anomaly, epoch and circular shape are QuOSS choices; the paper does not state them."
        ),
        orbit=OrbitSpec(
            kepler=KeplerOrbit(
                altitude_km=NTANOS_ORBIT_HEIGHT_KM,
                eccentricity=0.0,
                inclination_deg=_NTANOS_INCLINATION_DEG,
                raan_deg=0.0,
                argp_deg=0.0,
                true_anomaly_deg=0.0,
                method="two_body",
            )
        ),
        stations=[
            StationSpec(
                name=name,
                latitude_deg=latitude_deg,
                longitude_deg=longitude_deg,
                altitude_m=altitude_m,
                receive_aperture_m=aperture_m,
            )
        ],
        transmitter=_ntanos_transmitter(),
        channel=ChannelSpec(
            zenith_transmittance=1.0,
            static_loss_db=0.0,
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
        ),
        receiver=_ntanos_receiver(),
        background=BackgroundSpec(sky_radiance_w_m2_um_sr=NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR),
        protocol=_ntanos_protocol(),
        security=SecuritySpec(correctness=1e-10, secrecy=1e-10, compose_daily=True),
        time=TimeSpec(epoch_utc=REFERENCE_EPOCH_UTC, duration_s=86_400.0, step_s=1.0),
        passes=PassSpec(minimum_elevation_deg=NTANOS_MINIMUM_ELEVATION_DEG),
    )
