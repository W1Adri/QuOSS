"""The reference link wired by hand, parameterised by what the engine wires and the system tests do not.

What this is
------------
A copy of the three builders the system tests measure every stage-3 number on —
`tests/system/reference.py` (geometry, passes, budgets, conditions),
`tests/system/reference_fading.py` (the Monte Carlo inputs) and
`tests/system/reference_stations.py` (the same satellite seen from three
stations) — written out call by call with the module constants, **not** read
from a `Scenario`. It is the "person calling the modules by hand" the engine
claims to be indistinguishable from. Copied rather than imported because
`--import-mode=importlib` does not let one test directory import another's
helpers (BRIEF, and `tests/system/__init__.py`).

The one parameter the originals do not have
-------------------------------------------
``station_height_m``. The originals call every turbulence function with its
default height of 0 m while placing the station at its real altitude for the
geometry. The scenario schema says ``StationSpec.altitude_m`` is "also the
station height the turbulence profile starts from", and the engine wires it.
With ``station_height_m=0.0`` this module is the originals and reproduces their
numbers (432 985 bits, the Monte Carlo quantiles, the multi-station and relay
totals); with the station's altitude it is what the engine should compute. The
end-to-end tests assert both, which pins the difference between the engine and
the stage-3 numbers on that single term.
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
from quoss.channel.extinction import (
    VisibilityScalingLaw,
    specific_attenuation_at_altitude_db_per_km,
)
from quoss.channel.horizontal import (
    PathWave,
    horizontal_log_irradiance_variance,
    horizontal_loss_budget,
    plane_wave_rytov_variance,
)
from quoss.channel.link_budget import (
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    LossBudget,
    NoiseBudget,
    downlink_loss_budget,
    downlink_noise_budget,
)
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import ScintillationRegime, downlink_log_irradiance_variance
from quoss.core.constants import SPEED_OF_LIGHT_M_S
from quoss.core.errors import DegradationLog
from quoss.core.rng import RandomSource
from quoss.core.types import TimeGrid
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.geometry import (
    LookAngles,
    doppler_rate_hz_s,
    doppler_shift_hz,
    look_angles,
)
from quoss.orbits.kepler import ClassicalElements
from quoss.orbits.propagator import PropagationMethod, Trajectory, propagate
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, KeyRate, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import (
    FiniteKeyResult,
    SecurityParameters,
    expected_block_counts,
    secret_key_length,
)
from quoss.scenario.models import MonteCarloSpec, StationSpec
from quoss.system.correlated_fading import FadingParameters
from quoss.system.key_volume import (
    PassKeyVolume,
    asymptotic_pass_key_volume,
    decoy_settings_from_protocol,
    pass_key_volume,
)
from quoss.system.monte_carlo import (
    MonteCarloKeyVolume,
    MonteCarloOptions,
    monte_carlo_pass_key_volume,
)
from quoss.system.multi_ogs import StationSet
from quoss.system.passes import PassSamples, PassTable, find_passes

# -- tests/system/reference.py ------------------------------------------------ #
ORBIT_ALTITUDE_KM = 700.0
ORBIT_ECCENTRICITY = 0.001
ORBIT_RAAN_RAD = float(np.deg2rad(30.0))
EPOCH_JD = 2_460_676.5
WAVELENGTH_M = 1.55e-6
GATE_S = 1e-9
MISALIGNMENT_ERROR = 0.01
REFERENCE_DAY_NUMBER = 2_460_677

REFERENCE_FINITE_BITS = (190_581.0, 0.0, 242_404.0, 0.0)
REFERENCE_ASYMPTOTIC_BITS = (1_548_341.3, 319_898.3, 1_709_160.4, 199_280.8)
REFERENCE_FINITE_DAY_BITS = 432_985.0
"""Copied from `tests/system/reference.py`, where `TestWhatTheAsymptoticRateOverstates` measures them.

The asymptotic values are printed there to one decimal, so they are compared
here to half of that last digit, 0.05 bits.
"""

# -- tests/system/reference_fading.py ----------------------------------------- #
REFERENCE_SEED = 20_260_913
REFERENCE_FADING = FadingParameters(
    scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=20e-3
)
REFERENCE_MONTE_CARLO_DAY_QUANTILES = (735_329.0, 758_314.0, 782_391.0)
"""`tests/system/test_monte_carlo.py::TestWhatTheDesignNumberUnderReports::test_the_headline_quantiles`."""

# -- tests/system/reference_stations.py --------------------------------------- #
STATIONS: dict[str, tuple[float, float, float]] = {
    "castelldefels": (41.2750, 1.9875, 30.0),
    "calar_alto": (37.22361, -2.54611, 2168.0),
    "tenerife_ogs": (28.298, -16.511833, 2400.0),
}
"""``name -> (latitude_deg, longitude_deg, altitude_m)``; sources in `reference_stations.py`."""

REFERENCE_MULTI_SUM_BITS = 1_052_607.0
REFERENCE_MULTI_BEST_BITS = 995_682.0
REFERENCE_RELAY_DELIVERED_BITS = 432_985.0
REFERENCE_RELAY_STRANDED_BITS = 129_712.0
"""`tests/system/test_multi_ogs.py` and `test_relay.py`, `TestOnTheReferenceDay`."""


def reference_protocol() -> Bb84DecoyProtocol:
    """Ntanos et al.'s decoy configuration."""
    return Bb84DecoyProtocol.ntanos_2021()


def reference_security() -> SecurityParameters:
    """Return the per-block failure probabilities of every reference number."""
    return SecurityParameters(correctness=1e-10, secrecy=1e-10)


def chain_efficiency() -> float:
    """Return the receiver chain efficiency of `conditions_at`."""
    return receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )


def station_spec(name: str, *, receive_aperture_m: float = 0.75, **extra: float) -> StationSpec:
    """Return the station of `STATIONS` as a scenario would write it."""
    latitude_deg, longitude_deg, altitude_m = STATIONS[name]
    return StationSpec(
        name=name,
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        altitude_m=altitude_m,
        receive_aperture_m=receive_aperture_m,
        **extra,
    )


@lru_cache(maxsize=4)
def trajectory(step_s: float = 1.0, duration_s: float = 86_400.0) -> tuple[Trajectory, TimeGrid]:
    """Propagate the reference orbit by hand, as `reference_stations.trajectory` does."""
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
class HandLink:
    """One station's chain, wired by hand."""

    name: str
    angles: LookAngles
    grid: TimeGrid
    table: PassTable
    samples: PassSamples
    loss: LossBudget
    noise: NoiseBudget
    conditions: LinkConditions
    finite: PassKeyVolume
    asymptotic: PassKeyVolume
    station_height_m: float

    @property
    def acquisition(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """``(range_rate, doppler, doppler_rate, point_ahead)`` on the whole grid.

        Written out the way a person would: take the carrier from the
        wavelength, take the two geometric series `look_angles` already
        returned, and differentiate the Doppler over the **full** grid rather
        than inside each pass — a derivative taken inside a pass would see the
        pass edge as a boundary and return a one-sided difference exactly at
        the horizon, which is the instant the quantity is about.
        """
        carrier_hz = float(SPEED_OF_LIGHT_M_S / WAVELENGTH_M)
        range_rate = np.asarray(self.angles.range_rate_km_s, dtype=np.float64)[0]
        return (
            range_rate,
            np.asarray(doppler_shift_hz(range_rate, carrier_hz), dtype=np.float64),
            np.asarray(
                doppler_rate_hz_s(
                    range_rate, t_s=np.asarray(self.grid.t_s), carrier_frequency_hz=carrier_hz
                ),
                dtype=np.float64,
            ),
            np.asarray(self.angles.point_ahead_angle_rad, dtype=np.float64)[0],
        )

    @property
    def pass_acquisition(
        self,
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """``(one-sided |doppler|, doppler excursion, max|rate|, max lead, min lead)`` per pass.

        The first two are the pair the engine keeps apart on purpose: the
        amplitude of one side of the sweep, and the whole span from the
        approaching extreme to the receding one. The second is computed as
        ``max - min`` and not as twice the first, because on a real pass the
        two extremes are not equal.
        """
        _, doppler, rate, point_ahead = self.acquisition
        rows = np.asarray(self.samples.sample_index)
        return (
            self.samples.segment_max(np.abs(doppler[rows])),
            self.samples.segment_max(doppler[rows]) - self.samples.segment_min(doppler[rows]),
            self.samples.segment_max(np.abs(rate[rows])),
            self.samples.segment_max(point_ahead[rows]),
            self.samples.segment_min(point_ahead[rows]),
        )

    @property
    def fade_inputs(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """``(fade_db, sigma^2, gamma)`` at the samples, as `reference_fading.fading_inputs_of`."""
        rows = (self.samples.satellite_index, self.samples.sample_index)
        elevation = np.asarray(self.angles.elevation_rad)[rows]
        slant_range = np.asarray(self.angles.range_km)[rows]
        log = DegradationLog()
        variance = downlink_log_irradiance_variance(
            elevation,
            aperture_diameter_m=0.75,
            wavelength_m=WAVELENGTH_M,
            degradations=log,
            station_height_m=self.station_height_m,
        )
        gamma = beam_to_jitter_ratio(
            slant_range,
            jitter_rad=NTANOS_POINTING_JITTER_RAD,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=0.75,
            degradations=log,
        )
        return (
            np.asarray(self.loss.fade_db, dtype=np.float64),
            np.asarray(variance, dtype=np.float64),
            np.asarray(gamma, dtype=np.float64),
        )


@lru_cache(maxsize=64)
def hand_link(
    name: str = "castelldefels",
    *,
    station_height_m: float,
    mask_deg: float = 10.0,
    step_s: float = 1.0,
    duration_s: float = 86_400.0,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
    zenith_transmittance: float = 1.0,
) -> HandLink:
    """Return the whole chain for one station, one mask and one turbulence height, memoised.

    The station's geometry uses its altitude (km, as `reference_stations.py`
    writes it: ``altitude_m / 1000``); the turbulence uses ``station_height_m``.

    ``zenith_transmittance`` keeps its 1.0 here and nowhere in the package: this
    is the hand chain, and its job is to be the thing the engine is compared
    against, so its arguments carry the reference link's values. The scenario
    schema is where the absence of a default is enforced
    (`tests/scenario/test_models.py::TestTheFieldsWithoutADefault`).
    """
    latitude_deg, longitude_deg, altitude_m = STATIONS[name]
    path, grid = trajectory(step_s, duration_s)
    angles = look_angles(
        path,
        station_latitude_rad=float(np.deg2rad(latitude_deg)),
        station_longitude_rad=float(np.deg2rad(longitude_deg)),
        station_altitude_km=altitude_m / 1000.0,
    )
    table = find_passes(
        angles,
        grid=grid,
        minimum_elevation_rad=float(np.deg2rad(mask_deg)),
        degradations=DegradationLog(),
    )
    samples = table.samples()
    rows = (samples.satellite_index, samples.sample_index)
    elevation = np.asarray(angles.elevation_rad)[rows]
    slant_range = np.asarray(angles.range_km)[rows]
    log = DegradationLog()
    chain = chain_efficiency()
    loss = downlink_loss_budget(
        elevation,
        range_km=slant_range,
        wavelength_m=WAVELENGTH_M,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=0.75,
        zenith_transmittance=zenith_transmittance,
        pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
        receiver_efficiency=chain,
        degradations=log,
        station_height_m=station_height_m,
        regime=regime,
    )
    noise = downlink_noise_budget(
        NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
        wavelength_m=WAVELENGTH_M,
        receive_aperture_m=0.75,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
        gate_duration_s=GATE_S,
        receiver_efficiency=chain,
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        detector_count=2,
        degradations=log,
    )
    conditions = LinkConditions(
        transmittance=loss.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=MISALIGNMENT_ERROR,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=GATE_S,
    )
    finite = pass_key_volume(
        conditions,
        samples=samples,
        protocol=reference_protocol(),
        security=reference_security(),
        degradations=log,
    )
    asymptotic = asymptotic_pass_key_volume(
        conditions, samples=samples, protocol=reference_protocol(), degradations=log
    )
    return HandLink(
        name=name,
        angles=angles,
        grid=grid,
        table=table,
        samples=samples,
        loss=loss,
        noise=noise,
        conditions=conditions,
        finite=finite,
        asymptotic=asymptotic,
        station_height_m=station_height_m,
    )


def hand_monte_carlo(target: HandLink, spec: MonteCarloSpec) -> MonteCarloKeyVolume:
    """Return the ensemble on a hand link, as `reference_fading.run_monte_carlo` draws it."""
    assert spec.seed is not None
    fade_db, variance, gamma = target.fade_inputs
    return monte_carlo_pass_key_volume(
        target.conditions,
        samples=target.samples,
        nominal_fade_db=fade_db,
        log_irradiance_variance_np2=variance,
        beam_to_jitter_ratio=gamma,
        protocol=reference_protocol(),
        security=reference_security(),
        fading=FadingParameters(
            scintillation_correlation_time_s=spec.scintillation_correlation_time_s,
            pointing_correlation_time_s=spec.pointing_correlation_time_s,
        ),
        options=MonteCarloOptions(
            realisations=spec.realisations,
            sample_counts=spec.sample_counts,
            quantiles=tuple(spec.quantiles),
        ),
        random_source=RandomSource.from_seed(spec.seed),
        degradations=DegradationLog(),
    )


def station_set(*names: str) -> StationSet:
    """Return a `StationSet` of the named stations, as `reference_stations.station_set` builds it."""
    return StationSet(
        names=tuple(names),
        latitude_rad=np.deg2rad(np.array([STATIONS[n][0] for n in names])),
        longitude_rad=np.deg2rad(np.array([STATIONS[n][1] for n in names])),
        altitude_km=np.array([STATIONS[n][2] / 1000.0 for n in names]),
    )


def mean_log_transmittance(link: HandLink, pass_index: int | None = None) -> float:
    """Return the mean of `ln T` over a link's samples, or over one pass of it.

    Why the logarithm, and why the mean of it
    -----------------------------------------
    `T` is the transmittance: the fraction of the photons leaving the satellite
    that reach the detector. It is a number like 1.7e-4, and it changes by
    orders of magnitude along one pass, because the satellite goes from 10
    degrees above the horizon to overhead and back.

    Two things follow. First, the *mean of T* over a pass is dominated by the
    few seconds near culmination and says almost nothing about the rest, so it
    is the wrong summary. Second, what the altitude term does to the channel is
    **multiplicative** — it removes a fixed fraction of the turbulence integral,
    not a fixed number of photons — and the natural summary of a multiplicative
    change is a difference of logarithms: `ln T_up - ln T_sea` is the same
    number whether the link is bright or faint.

    That difference is also what makes the decomposition in
    `TestWhyTheHigherStationGainsLess` an identity rather than an analogy. With
    `x = mean(ln T)` and `y = ln(key bits)`, the elasticity `E = dy / dx` is
    defined so that `dy = E * dx` exactly, by construction. The content is not
    the algebra, it is that `dx` and `E` turn out to be two separable physical
    things: `dx` is the atmosphere and `E` is the finite-key bound.

    Worked example
    --------------
    Calar Alto, the reference day, all four passes' samples pooled:
    `mean(ln T)` is -8.665297 at sea level and -8.598190 from 2 168 m. The
    difference is +0.067107, i.e. the altitude multiplies the transmittance by
    `exp(0.067107) = 1.0694`, a **6.94 %** brighter channel on average.
    """
    transmittance = np.asarray(link.loss.transmittance, dtype=np.float64)
    if pass_index is None:
        return float(np.log(transmittance).mean())
    selected = np.asarray(link.samples.pass_index) == pass_index
    return float(np.log(transmittance[selected]).mean())


# --------------------------------------------------------------------------- #
# The horizontal link, wired the same way
# --------------------------------------------------------------------------- #
GE1_TRANSMIT_APERTURE_M = 0.025
GE1_RECEIVE_APERTURE_M = 0.10
GE1_PATH_LENGTH_M = 1000.0
GE1_CN2_M23 = 1e-14
GE1_JITTER_RAD = 5e-6
GE1_SESSION_S = 60.0
GE1_VISIBILITY_KM = 23.0
GE1_ALTITUDE_M = 30.0
GE1_SCALE_HEIGHT_M = 1200.0
"""The GE-1 link of ``scenarios/ge1_1km.yaml``, as literals rather than read from it.

Written out here for the reason the downlink constants above are: this module is
the person calling the physics functions by hand, and a hand chain that read the
scenario file would be comparing the engine against itself.
"""


@dataclass(frozen=True)
class HandHorizontal:
    """Every stage of a horizontal link, computed without touching ``quoss.engine``."""

    extinction_db_per_km: float
    loss: LossBudget
    noise: NoiseBudget
    conditions: LinkConditions
    finite: FiniteKeyResult
    asymptotic: KeyRate
    pulses: float
    variance_np2: float
    rytov_np2: float
    gamma: float


def hand_horizontal(
    *,
    path_length_m: float = GE1_PATH_LENGTH_M,
    cn2_m23: float = GE1_CN2_M23,
    wave: PathWave = PathWave.SPHERICAL,
    transmit_aperture_m: float = GE1_TRANSMIT_APERTURE_M,
    receive_aperture_m: float = GE1_RECEIVE_APERTURE_M,
    jitter_rad: float = GE1_JITTER_RAD,
    session_s: float = GE1_SESSION_S,
    regime: ScintillationRegime = ScintillationRegime.WEAK,
    radiance_w_m2_um_sr: float = NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    extinction_db_per_km: float | None = None,
) -> HandHorizontal:
    """Return the whole GE-1 chain, the five calls of ``engine/horizontal.py`` by hand.

    ``extinction_db_per_km=None`` means "resolve it from the visibility the way
    the scenario declares it", which is the interesting case: it exercises
    :func:`~quoss.channel.extinction.specific_attenuation_at_altitude_db_per_km`
    against the engine's call to the same function through
    :meth:`~quoss.scenario.models.HorizontalPathSpec.extinction_db_per_km_at`.
    A number is passed straight through, which is the other declaration.
    """
    log = DegradationLog()
    chain = chain_efficiency()
    if extinction_db_per_km is None:
        extinction = float(
            specific_attenuation_at_altitude_db_per_km(
                GE1_VISIBILITY_KM,
                wavelength_m=WAVELENGTH_M,
                aerosol_scale_height_m=GE1_SCALE_HEIGHT_M,
                altitude_m=GE1_ALTITUDE_M,
                visibility_altitude_m=GE1_ALTITUDE_M,
                law=VisibilityScalingLaw.KIM_2001,
                degradations=log,
            )
        )
    else:
        extinction = extinction_db_per_km
    loss = horizontal_loss_budget(
        path_length_m,
        wavelength_m=WAVELENGTH_M,
        transmit_aperture_m=transmit_aperture_m,
        receive_aperture_m=receive_aperture_m,
        cn2_m23=cn2_m23,
        extinction_db_per_km=extinction,
        wave=wave,
        pointing_jitter_rad=jitter_rad,
        receiver_efficiency=chain,
        degradations=log,
        regime=regime,
    )
    protocol = reference_protocol()
    mean_photon_number = (
        protocol.signal_probability * protocol.signal_intensity
        + protocol.decoy_probability * protocol.decoy_intensity
    )
    noise = downlink_noise_budget(
        radiance_w_m2_um_sr,
        wavelength_m=WAVELENGTH_M,
        receive_aperture_m=receive_aperture_m,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
        gate_duration_s=GATE_S,
        receiver_efficiency=chain,
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        degradations=log,
        detector_count=2,
        afterpulse_probability=0.0,
        signal_counts_per_gate=mean_photon_number * np.asarray(loss.transmittance),
    )
    conditions = LinkConditions(
        transmittance=loss.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=MISALIGNMENT_ERROR,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=GATE_S,
    )
    pulses = NTANOS_SOURCE_PULSE_RATE_HZ * session_s
    settings = decoy_settings_from_protocol(protocol)
    block = expected_block_counts(
        conditions, settings=settings, key_basis_probability=0.5, pulses=pulses
    )
    finite = secret_key_length(
        block,
        settings=settings,
        security=reference_security(),
        error_correction_efficiency=protocol.error_correction_efficiency,
        degradations=log,
    )
    asymptotic = protocol.key_rate(conditions, degradations=log)
    variance = float(
        horizontal_log_irradiance_variance(
            path_length_m,
            cn2_m23=cn2_m23,
            aperture_diameter_m=receive_aperture_m,
            wavelength_m=WAVELENGTH_M,
            wave=wave,
            degradations=log,
            regime=regime,
        )
    )
    rytov = float(
        plane_wave_rytov_variance(path_length_m, cn2_m23=cn2_m23, wavelength_m=WAVELENGTH_M)
    )
    gamma = float(
        beam_to_jitter_ratio(
            path_length_m / 1000.0,
            jitter_rad=jitter_rad,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=transmit_aperture_m,
            receive_aperture_m=receive_aperture_m,
            degradations=log,
        )
    )
    return HandHorizontal(
        extinction_db_per_km=extinction,
        loss=loss,
        noise=noise,
        conditions=conditions,
        finite=finite,
        asymptotic=asymptotic,
        pulses=float(pulses),
        variance_np2=variance,
        rytov_np2=rytov,
        gamma=gamma,
    )
