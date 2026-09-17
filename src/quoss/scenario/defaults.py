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
from quoss.channel.extinction import VisibilityScalingLaw
from quoss.channel.horizontal import PathWave, equivalent_bench_cn2_m23
from quoss.channel.link_budget import (
    NTANOS_OGS_APERTURES_M,
    NTANOS_ORBIT_HEIGHT_KM,
    NTANOS_OUTAGE_PROBABILITY,
    NTANOS_TRANSMIT_APERTURE_M,
)
from quoss.channel.turbulence import ScintillationRegime
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.scenario.models import (
    BackgroundSpec,
    ChannelSpec,
    ExtinctionSpec,
    HorizontalPathSpec,
    HorizontalScenario,
    KeplerOrbit,
    LinkKind,
    OrbitSpec,
    PassSpec,
    ProtocolSpec,
    ReceiverSpec,
    Scenario,
    SecuritySpec,
    SessionSpec,
    StationSpec,
    TimeSpec,
    TransmitterSpec,
)

__all__ = [
    "GE0B_BENCH_LENGTH_M",
    "GE0B_SESSION_DURATION_S",
    "GE1_CN2_M23",
    "GE1_PATH_LENGTH_M",
    "GE1_POINTING_JITTER_URAD",
    "GE1_RECEIVE_APERTURE_M",
    "GE1_SESSION_DURATION_S",
    "GE1_TRANSMIT_APERTURE_M",
    "NTANOS_DEAD_TIME_NS",
    "NTANOS_FIELD_OF_VIEW_URAD",
    "NTANOS_FILTER_BANDWIDTH_NM",
    "NTANOS_GATE_NS",
    "NTANOS_MINIMUM_ELEVATION_DEG",
    "NTANOS_POINTING_JITTER_URAD",
    "NTANOS_STATIONS",
    "NTANOS_TIMING_JITTER_FWHM_PS",
    "REFERENCE_EPOCH_UTC",
    "ge0b_bench",
    "ge1_two_terminals",
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

    **Run through the engine this scenario gives 433 442 finite bits, not
    432 985, and the 457-bit difference is one term.** The stage-3 fixture
    leaves the turbulence profile at its default starting height of 0 m while
    placing the station at 30 m for the geometry; :attr:`StationSpec.altitude_m`
    is both, so the engine starts the profile at 30 m and there is that much
    less air above the telescope. Both figures are reproduced to the bit, from
    one hand-wired chain with only that argument changed, by
    ``tests/e2e/test_reference_scenarios.py``; see
    ``docs/adr/0016-the-engine-adds-nothing-and-one-altitude.md`` for why the
    engine's is the one to report.
    ``tests/scenario/test_defaults.py::TestReferenceCastelldefels`` asserts the
    conversion reproduces the physics inputs of ``tests/system/reference.py``
    field by field, passing that one height explicitly on the hand-built side.

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
            scintillation_regime=ScintillationRegime.WEAK,
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
            scintillation_regime=ScintillationRegime.WEAK,
        ),
        receiver=_ntanos_receiver(),
        background=BackgroundSpec(sky_radiance_w_m2_um_sr=NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR),
        protocol=_ntanos_protocol(),
        security=SecuritySpec(correctness=1e-10, secrecy=1e-10, compose_daily=True),
        time=TimeSpec(epoch_utc=REFERENCE_EPOCH_UTC, duration_s=86_400.0, step_s=1.0),
        passes=PassSpec(minimum_elevation_deg=NTANOS_MINIMUM_ELEVATION_DEG),
    )


# --------------------------------------------------------------------------- #
# The horizontal links: GE-0b (bench) and GE-1 (two terminals)
# --------------------------------------------------------------------------- #
GE1_PATH_LENGTH_M = 1000.0
"""One kilometre: the recommendation of ``docs/adr/0025-two-terminals-one-way.md``.

Not an arbitrary round number. Below ~500 m the link is inside the 316.7 m
Rayleigh range of a 2.5 cm transmitter, where neither the plane nor the
spherical closed form describes the beam and the bracket between them narrows
for the wrong reason; past 2413 m the weak theory stops being citable at all
(:func:`~quoss.channel.horizontal.weak_theory_path_limit_m` for
``C_n^2 = 1e-14`` at 1550 nm). One kilometre is in the clean middle.
"""

GE1_TRANSMIT_APERTURE_M = 0.025
"""2.5 cm. A collimator, not a telescope: what a two-terminal ground link actually uses."""

GE1_RECEIVE_APERTURE_M = 0.10
"""10 cm. The lens, and the largest single lever there is on this link.

Going from 2.5 cm to 10 cm is worth a factor **between 8.4 and 11.2** in key
rate -- an interval and not a number, because the plane and spherical waves
bracket it in opposite senses at the two diameters (ADR 0021).
"""

GE1_CN2_M23 = 1e-14
"""ITU-R P.1814 Table 4's "moderate" column, near the ground."""

GE1_POINTING_JITTER_URAD = 5.0
"""5 urad r.m.s. per axis: a ground terminal on a tripod, not a tracking telescope.

Not from a publication -- it is the value ``tests/channel/test_horizontal.py``
sizes GE-1 with, and it is here so that the scenario says what it assumed.
"""

GE0B_BENCH_LENGTH_M = 2.0
"""Two metres of optical bench, which is what GE-0b physically is."""

GE0B_SESSION_DURATION_S = 60.0
GE1_SESSION_DURATION_S = 60.0
"""One minute of measurement, and the number this project is least able to defend.

It is the finite-key **block** (``docs/adr/0024-the-horizontal-scenario.md``),
and unlike a pass nothing in the physics fixes it: it is a promise by whoever
runs the experiment that the link was stationary for that long. Sixty seconds
at the 100 MHz source of Ntanos et al. is 6e9 pulses, three orders of magnitude
above the reference day's best pass, so the bound is nowhere near its
small-block cliff -- which is a statement about the bound, not a defence of the
minute.
"""


def _ge_transmitter(aperture_m: float) -> TransmitterSpec:
    """Return the GE transmitter: the Ntanos source through a small collimator."""
    return TransmitterSpec(
        wavelength_nm=_WAVELENGTH_NM,
        aperture_m=aperture_m,
        pointing_jitter_urad=GE1_POINTING_JITTER_URAD,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    )


def ge1_two_terminals() -> HorizontalScenario:
    """Return GE-1: two terminals, one way, one kilometre.

    What the experiment is
    ----------------------
    Two fixed terminals on the ground, a kilometre apart, one sending and one
    receiving. **Not** a retroreflector: the light does not come back. That is
    the recommendation of ``docs/adr/0025-two-terminals-one-way.md``, and the
    reason is that a monostatic retroreflected link crosses correlated air twice
    and its scintillation is *enhanced*, which Mahon et al. measured at 1.1 km
    and whose theory is Andrews & Phillips -- ADR 0009 gap 1, the source this
    project could not open. One architecture can be sized with the sources it
    has and the other cannot.

    Every number, and where it comes from
    -------------------------------------
    2.5 cm transmitter, 10 cm receiving lens, ``C_n^2 = 1e-14`` (P.1814 Table
    4's "moderate"), 1550 nm, 5 urad of jitter, a **spherical** wave, 23 km of
    visibility through the Kim et al. law -- which is 0.192 dB/km at this
    wavelength, against the 0.2 that ADR 0021's worked example assumed by hand
    -- the Ntanos et al. receiver and protocol, a moonless study night, and a
    60 s measurement session.

    Why ``spherical`` and not ``plane``: the Rayleigh range of a 2.5 cm
    transmitter at 1550 nm is 316.7 m, so a kilometre is **3.16 Rayleigh
    ranges** and the beam has spread to 3.3 times its waist. The plane wave is
    the other edge of the bracket, not a second opinion, and the budget records
    ``horizontal.plane-wave-beyond-the-rayleigh-range`` if it is declared.

    Why ``weak``: the plane-wave Rytov variance here is 0.199, a fifth of the
    limit, so first-order theory is inside its own validity range and the
    saturated model would be a correction to a number that does not need one.
    At 5 km the same declaration would be wrong, and
    ``scenarios/ge1_1km.yaml`` says so in a comment.

    Returns
    -------
    HorizontalScenario
        The GE-1 scenario.
    """
    return HorizontalScenario(
        link=LinkKind.HORIZONTAL,
        name="ge1_1km",
        description=(
            "GE-1: two ground terminals, one way, 1 km, 2.5 cm transmitter, 10 cm receiving "
            "lens, C_n^2 = 1e-14, 23 km visibility, Ntanos et al. 2021 receiver and protocol, "
            "moonless study night, 60 s measurement session."
        ),
        path=HorizontalPathSpec(
            path_length_m=GE1_PATH_LENGTH_M,
            cn2_m23=GE1_CN2_M23,
            wave=PathWave.SPHERICAL,
            altitude_m=30.0,
            receive_aperture_m=GE1_RECEIVE_APERTURE_M,
            extinction=ExtinctionSpec(
                visibility_km=23.0,
                visibility_altitude_m=30.0,
                aerosol_scale_height_m=1200.0,
                scaling_law=VisibilityScalingLaw.KIM_2001,
            ),
            scintillation_regime=ScintillationRegime.WEAK,
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
        ),
        transmitter=_ge_transmitter(GE1_TRANSMIT_APERTURE_M),
        receiver=_ntanos_receiver(),
        background=BackgroundSpec(sky_radiance_w_m2_um_sr=NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR),
        protocol=_ntanos_protocol(),
        security=SecuritySpec(correctness=1e-10, secrecy=1e-10, compose_daily=False),
        session=SessionSpec(duration_s=GE1_SESSION_DURATION_S),
    )


def ge0b_bench() -> HorizontalScenario:
    """Return GE-0b: two metres of bench with a turbulence emulator.

    What the experiment is, and the question it is really asking
    ------------------------------------------------------------
    A two-metre optical bench with a phase-screen emulator between the two
    terminals, standing in for GE-1 before anything is put on a roof. The
    ``C_n^2`` written here is
    :func:`~quoss.channel.horizontal.equivalent_bench_cn2_m23` for two metres
    against GE-1's kilometre: **8.87e-10**, because the Rytov variance goes as
    ``L^(11/6)`` and ``(1000/2)^(11/6) = 8.87e4``.

    **That number is a necessary condition and not a sufficient one, and the
    scenario file says so rather than leaving it to a reader** (ADR 0009 gap
    20). An emulator does not produce a ``C_n^2`` over a length; it produces a
    *phase screen* with a given Fried parameter ``r_0``. Scintillation is phase
    distortion converted into amplitude **by propagation**, so a screen needs
    distance behind it: one screen at the start of a 2 m bench has 2 m in which
    to develop what a kilometre of distributed air develops continuously. The
    question to put to a manufacturer is therefore **not** "do you reach
    8.87e-10?" but "what ``D/r_0`` and what Rytov number do you reach, and with
    how many screens?".

    ``background`` is zero radiance, which on a closed bench is a statement
    about the enclosure and not a default; ``extinction_db_per_km`` is 0.0,
    which over two metres of laboratory air is exact to well below a thousandth
    of a dB.

    Returns
    -------
    HorizontalScenario
        The GE-0b scenario.
    """
    return HorizontalScenario(
        link=LinkKind.HORIZONTAL,
        name="ge0b_bench",
        description=(
            "GE-0b: 2 m bench with a turbulence emulator, C_n^2 set to the equivalent of GE-1's "
            "kilometre at 1e-14 (8.87e-10 — a necessary and not a sufficient condition, ADR "
            "0009 gap 20), dark enclosure, 60 s measurement session."
        ),
        path=HorizontalPathSpec(
            path_length_m=GE0B_BENCH_LENGTH_M,
            cn2_m23=equivalent_bench_cn2_m23(
                bench_length_m=GE0B_BENCH_LENGTH_M,
                path_length_m=GE1_PATH_LENGTH_M,
                cn2_m23=GE1_CN2_M23,
            ),
            wave=PathWave.PLANE,
            altitude_m=30.0,
            receive_aperture_m=GE1_RECEIVE_APERTURE_M,
            extinction_db_per_km=0.0,
            scintillation_regime=ScintillationRegime.WEAK,
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
        ),
        transmitter=_ge_transmitter(GE1_TRANSMIT_APERTURE_M),
        receiver=_ntanos_receiver(),
        background=BackgroundSpec(sky_radiance_w_m2_um_sr=0.0),
        protocol=_ntanos_protocol(),
        security=SecuritySpec(correctness=1e-10, secrecy=1e-10, compose_daily=False),
        session=SessionSpec(duration_s=GE0B_SESSION_DURATION_S),
    )
