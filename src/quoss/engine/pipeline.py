"""From a scenario to a result: every stage, in order, and nothing the stages did not compute.

What the pipeline does, for someone arriving new
------------------------------------------------
:func:`run` takes a :class:`~quoss.scenario.models.Scenario` — the complete,
validated description of one simulation — and returns a
:class:`~quoss.scenario.result.SimulationResult`. In between it calls, in this
order, the functions a person would call by hand:

1. **orbit** — :meth:`~quoss.scenario.models.KeplerOrbit.to_elements` and
   :func:`~quoss.orbits.propagator.propagate`, or
   :func:`~quoss.orbits.tle.propagate_tle` for a two-line element set;
2. **geometry** — :func:`~quoss.orbits.geometry.look_angles`, per station;
3. **passes** — :func:`~quoss.system.passes.find_passes` and
   :meth:`~quoss.system.passes.PassTable.samples`;
4. **channel** — :func:`~quoss.channel.link_budget.downlink_loss_budget` and
   :func:`~quoss.channel.link_budget.downlink_noise_budget` at the in-pass
   samples, into one :class:`~quoss.qkd.base.LinkConditions` per station;
5. **key** — :func:`~quoss.system.key_volume.pass_key_volume` (finite, the
   default) and :func:`~quoss.system.key_volume.asymptotic_pass_key_volume`,
   each summed by :func:`~quoss.system.key_volume.daily_key_volume`;
6. **series** — the look angles everywhere, the channel and the asymptotic
   rate at the in-pass samples;
7. **monte_carlo** (if asked) —
   :func:`~quoss.system.monte_carlo.monte_carlo_pass_key_volume`;
8. **multi_station** (if asked) — :func:`~quoss.system.pcflos.cloud_free_probability`
   and :func:`~quoss.system.multi_ogs.aggregate_stations`;
9. **relay** (if asked) — :func:`~quoss.system.relay.trusted_node_relay` per pair;
10. **result** — the containers of :mod:`quoss.scenario.result` and a
    :class:`~quoss.scenario.result.Provenance` record.

Steps 2-7 are one function of one station (:func:`_run_station`) and run through
:func:`~quoss.engine.parallel.map_workers`, so ``workers > 1`` puts stations in
separate processes without changing a bit of the result.

The claim, and what proves it
-----------------------------
**The engine adds nothing and loses nothing.** Every number in a result is a
number one of the functions above returned, moved into a container. The proof
is ``tests/e2e/test_reference_scenarios.py``: the same chain written out by
hand, parameter by parameter, gives the same bits as :func:`run`. That is a V4
bridge in the language of ``tests/golden/README.md`` — it shows the
orchestration is faithful, and says nothing about whether the physics is right,
which is what V2 and V3 are for.

Where the result is not a copy, it is an aggregation the result schema forces,
and each one is stated where it happens: several stations' days summed into one
day table (:func:`_daily_results`), a relay's per-delivery latency weighted into
one number per pair (:func:`_relay_results`).

One scenario field that the reference link never wired
-------------------------------------------------------
``StationSpec.altitude_m`` is both where the station is (it enters
:func:`~quoss.orbits.geometry.look_angles`) and where the turbulence profile
starts (``station_height_m`` of every turbulence function); the scenario
contract says so in its field description. The hand-built reference link of
``tests/system/reference.py`` passes the 30 m to the geometry and leaves the
turbulence at its default of 0 m. The engine wires the field, so on the
reference day it reports **433 442** finite bits (190 807, 0, 242 635, 0) where
the system tests quote **432 985** — 457 bits, 0.106 %, less turbulence above a
station 30 m up. Both numbers are reproduced to the bit by
``tests/e2e/test_reference_scenarios.py::TestTheEngineAddsNothing``, one with
the hand chain at each height, so the difference is proven to be that term
alone. Ignoring the field to match the older number would be a silent
degradation of a user input.

Randomness
----------
Only the Monte Carlo draws random numbers. The source is the ``random_source``
argument, or :meth:`~quoss.core.rng.RandomSource.from_seed` of
``scenario.monte_carlo.seed`` (which draws and records a seed when that is
``None``). **One station uses the source itself**; several stations each get a
:meth:`~quoss.core.rng.RandomSource.spawn` child, in station order. The single
station case is not spawned so that a one-station scenario reproduces the
ensemble ``tests/system/test_monte_carlo.py`` measures from the same seed; the
several-station case is spawned because two stations drawing from one stream
would make one station's fades depend on how many passes the other had.

Examples
--------
The reference day on a 10 s grid is enough to see the shape of a result:

>>> from quoss.engine.sweep import apply_point
>>> from quoss.scenario.defaults import reference_castelldefels
>>> scenario = apply_point(reference_castelldefels(), {"time.step_s": 10.0})
>>> result = run(scenario)
>>> result.passes.n_passes, result.series[0].grid.n
(4, 8641)
>>> list(result.timings.seconds)[:3]
['orbit', 'geometry', 'passes']
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import numpy as np

from quoss.channel.link_budget import (
    LossBudget,
    NoiseBudget,
    downlink_loss_budget,
    downlink_noise_budget,
)
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import downlink_log_irradiance_variance
from quoss.core.constants import SECONDS_PER_DAY, SPEED_OF_LIGHT_M_S
from quoss.core.errors import DegradationLog, DomainError, ScenarioError
from quoss.core.rng import RandomSource
from quoss.core.types import FloatArray, IntArray, TimeGrid, TimeSeries
from quoss.engine.parallel import map_workers
from quoss.engine.profiling import StageTimer
from quoss.orbits.geometry import (
    LookAngles,
    doppler_rate_hz_s,
    doppler_shift_hz,
    look_angles,
)
from quoss.orbits.propagator import Trajectory, propagate
from quoss.orbits.tle import propagate_tle
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import FiniteKeyResult, SecurityParameters
from quoss.scenario.models import Scenario, StationSpec
from quoss.scenario.result import (
    DailyResults,
    MonteCarloResults,
    MultiStationResults,
    PassResults,
    Provenance,
    RelayResults,
    SeriesResults,
    SimulationResult,
)
from quoss.system.correlated_fading import FadingParameters
from quoss.system.key_volume import (
    DailyKeyVolume,
    PassKeyVolume,
    asymptotic_pass_key_volume,
    composed_security,
    daily_key_volume,
    pass_key_volume,
)
from quoss.system.monte_carlo import (
    MonteCarloDailyKeyVolume,
    MonteCarloKeyVolume,
    MonteCarloOptions,
    monte_carlo_daily_key_volume,
    monte_carlo_pass_key_volume,
)
from quoss.system.multi_ogs import (
    AggregationPolicy,
    MultiStationKeyVolume,
    StationSet,
    aggregate_stations,
)
from quoss.system.passes import PassSamples, PassTable, find_passes
from quoss.system.pcflos import (
    JointCloudFreeProbability,
    cloud_free_probability,
    joint_cloud_free_probability,
)
from quoss.system.relay import RelayKeyVolume, trusted_node_relay

if TYPE_CHECKING:
    from quoss.engine.cache import ResultCache

__all__ = ["STAGES", "Simulation", "StationRun", "run", "simulate"]

_WHERE = "quoss.engine.pipeline"

STAGES: tuple[str, ...] = (
    "orbit",
    "geometry",
    "passes",
    "channel",
    "key",
    "series",
    "monte_carlo",
    "multi_station",
    "relay",
    "result",
)
"""Every stage name a result's timings can hold, in run order."""


# --------------------------------------------------------------------------- #
# Containers
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False, slots=True)
class Acquisition:
    """What a terminal has to track, on the whole grid and reduced per pass.

    Separate from :class:`~quoss.scenario.result.SeriesResults` because it is
    computed before the pass table is scored and read afterwards, and separate
    from the key stage because **none of it depends on the link budget**. A
    satellite that certifies no key still sweeps a carrier and still has to be
    pointed ahead; the numbers here say whether a transceiver could have
    followed it, which is a different question from whether it was worth it.

    Why it exists as a named object rather than four loose arrays: the four are
    read together (a capture range and a tracking rate are one specification)
    and they share one assumption — the carrier — which a container can carry
    and four arrays cannot.

    Attributes
    ----------
    carrier_frequency_hz : float
        ``c / lambda`` of the scenario's transmitter. The one assumption
        behind ``doppler_shift_hz`` and ``doppler_rate_hz_s``.
    range_rate_km_s, doppler_shift_hz, doppler_rate_hz_s, point_ahead_angle_rad : FloatArray
        Shape ``(n_samples,)``, the whole grid, defined everywhere.
    max_abs_doppler_hz, max_abs_doppler_rate_hz_s : FloatArray
        Shape ``(n_passes,)``, reduced over the samples inside each pass.
    max_point_ahead_angle_rad, min_point_ahead_angle_rad : FloatArray
        Shape ``(n_passes,)``.
    """

    carrier_frequency_hz: float
    range_rate_km_s: FloatArray
    doppler_shift_hz: FloatArray
    doppler_rate_hz_s: FloatArray
    point_ahead_angle_rad: FloatArray
    max_abs_doppler_hz: FloatArray
    max_abs_doppler_rate_hz_s: FloatArray
    max_point_ahead_angle_rad: FloatArray
    min_point_ahead_angle_rad: FloatArray


@dataclass(frozen=True, eq=False, slots=True)
class StationRun:
    """Everything the per-station stages produced, before it is moved into a result.

    The result schema keeps what a consumer of a finished run needs; this keeps
    the physics objects themselves, which is what a test comparing the engine
    with a hand-wired chain needs, and what a notebook digging into one pass
    wants. Returned by :func:`simulate`, never cached.

    Attributes
    ----------
    name : str
        Station name.
    angles : LookAngles
        Look angles on the whole grid.
    table : PassTable
        The passes above the scenario's mask.
    samples : PassSamples
        The in-pass ``(pass, sample)`` entries, possibly empty.
    loss, noise : LossBudget or None, NoiseBudget or None
        The budgets at ``samples``; ``None`` for a station with no pass.
    conditions : LinkConditions or None
        What the key stage consumed; ``None`` for a station with no pass.
    finite, asymptotic : PassKeyVolume
        Per-pass key in each regime. A station with no pass gets a volume with
        zero passes, which is what the multi-station and relay functions take.
    finite_daily, asymptotic_daily : DailyKeyVolume or None
        Per-day sums; ``None`` for a station with no pass, because a day table
        of no passes has no rows to compose.
    monte_carlo : MonteCarloKeyVolume or None
        The ensemble, when the scenario asks for one and the station has passes.
    monte_carlo_daily : MonteCarloDailyKeyVolume or None
        Its per-day quantiles.
    series : SeriesResults
        The station's series as they go into the result.
    acquisition : Acquisition
        The Doppler pair and the point-ahead angle, on the whole grid and
        reduced per pass. Geometry only, so a station with no pass still has
        the series and simply has no rows of extrema.
    seconds : dict[str, float]
        Seconds spent per stage for this station.
    """

    name: str
    angles: LookAngles
    table: PassTable
    samples: PassSamples
    loss: LossBudget | None
    noise: NoiseBudget | None
    conditions: LinkConditions | None
    finite: PassKeyVolume
    asymptotic: PassKeyVolume
    finite_daily: DailyKeyVolume | None
    asymptotic_daily: DailyKeyVolume | None
    monte_carlo: MonteCarloKeyVolume | None
    monte_carlo_daily: MonteCarloDailyKeyVolume | None
    series: SeriesResults
    acquisition: Acquisition
    seconds: dict[str, float]


@dataclass(frozen=True, eq=False, slots=True)
class Simulation:
    """A result together with the system-level objects it was built from.

    Attributes
    ----------
    result : SimulationResult
        What :func:`run` returns.
    trajectory : Trajectory
        The propagated satellite on the scenario's grid.
    stations : tuple[StationRun, ...]
        One per station, in scenario order.
    multi_station : MultiStationKeyVolume or None
        The aggregation, when the scenario asks for it.
    joint_cloud_free : JointCloudFreeProbability or None
        Site diversity, when a cloud decorrelation length was given.
    relays : tuple[RelayKeyVolume, ...]
        One per relay pair, in the scenario's order.
    """

    result: SimulationResult
    trajectory: Trajectory
    stations: tuple[StationRun, ...]
    multi_station: MultiStationKeyVolume | None
    joint_cloud_free: JointCloudFreeProbability | None
    relays: tuple[RelayKeyVolume, ...]


@dataclass(frozen=True, eq=False, slots=True)
class _StationTask:
    """What one worker needs to run one station: picklable, self-contained."""

    scenario: Scenario
    index: int
    trajectory: Trajectory
    random_source: RandomSource | None


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #
def run(
    scenario: Scenario,
    *,
    random_source: RandomSource | None = None,
    cache: ResultCache | None = None,
    workers: int = 1,
    degradations: DegradationLog | None = None,
) -> SimulationResult:
    """Run one scenario and return its result.

    Parameters
    ----------
    scenario : Scenario
        The validated inputs.
    random_source : RandomSource, optional
        The source of the Monte Carlo. Defaults to
        ``RandomSource.from_seed(scenario.monte_carlo.seed)``. Ignored, and no
        seed recorded, when the scenario has no Monte Carlo — a run that drew
        no random number has no seed to reproduce.
    cache : ResultCache, optional
        A result cache. A hit returns the stored result with an ``INFO``
        ``engine.cache-hit`` appended; a miss runs and stores. A Monte Carlo
        scenario without a seed is never cached (see :mod:`quoss.engine.cache`).
    workers : int, optional
        Worker processes for the per-station stages. ``1`` (default) runs in
        this process. The result is identical for any value; with several
        workers the per-stage timings are sums of worker seconds.
    degradations : DegradationLog, optional
        Receives every entry of the run. Created when not given. Either way,
        the result's ``warnings`` hold every entry of this log at the end of
        the run, in order.

    Returns
    -------
    SimulationResult
        The result.

    Raises
    ------
    ScenarioError
        If the scenario asks for something the engine cannot compute from it
        (see :func:`simulate`), or a TLE window SGP4 cannot propagate.
    DomainError
        If ``workers`` is not a positive integer, or a physics function
        refuses its inputs.
    """
    log = DegradationLog() if degradations is None else degradations
    _require_scenario(scenario)
    source = _random_source_for(scenario, random_source)
    seed = source.seed if source is not None else None
    if cache is not None:
        hit = cache.get(scenario, seed=seed, degradations=log)
        if hit is not None:
            return dataclasses.replace(hit, warnings=log.to_dicts())
    result = simulate(scenario, random_source=source, workers=workers, degradations=log).result
    if cache is not None:
        cache.put(result, degradations=log)
        result = dataclasses.replace(result, warnings=log.to_dicts())
    return result


def simulate(
    scenario: Scenario,
    *,
    random_source: RandomSource | None = None,
    workers: int = 1,
    degradations: DegradationLog,
) -> Simulation:
    """Run one scenario and return the result with the objects behind it.

    :func:`run` is this plus the cache. Use this when the per-station budgets,
    key volumes or ensembles are needed and not only the result.

    Parameters
    ----------
    scenario : Scenario
        The validated inputs.
    random_source : RandomSource, optional
        As in :func:`run`.
    workers : int, optional
        As in :func:`run`.
    degradations : DegradationLog
        Receives every entry of the run.

    Returns
    -------
    Simulation
        The result and the system-level objects.

    Raises
    ------
    ScenarioError
        If ``multi_station`` is asked for with fewer than two stations; if
        some stations give a ``cloud_fraction`` and others do not while
        ``multi_station`` is asked for; if a cloud decorrelation length is
        given with no cloud fraction to correlate; or if SGP4 cannot propagate
        a TLE over the scenario's window. Each is a question the scenario
        asks and cannot be answered from it, refused before any computation.
    DomainError
        If ``workers`` is not a positive integer, or a physics function
        refuses its inputs.
    """
    _require_scenario(scenario)
    _check_preconditions(scenario, degradations)
    timer = StageTimer()
    source = _random_source_for(scenario, random_source)
    grid = scenario.time.grid()

    with timer.stage("orbit"):
        trajectory, data_versions = _propagate(scenario, grid, degradations)

    sources = _station_sources(scenario, source)
    tasks = [
        _StationTask(scenario=scenario, index=i, trajectory=trajectory, random_source=sources[i])
        for i in range(len(scenario.stations))
    ]
    stations = tuple(map_workers(_run_station, tasks, workers=workers, degradations=degradations))
    for station in stations:
        timer.merge(station.seconds)

    with timer.stage("result"):
        passes = _pass_results(grid, stations)
        daily = _daily_results(scenario, stations, degradations)

    multi: MultiStationKeyVolume | None = None
    joint: JointCloudFreeProbability | None = None
    multi_results: MultiStationResults | None = None
    if scenario.multi_station is not None:
        with timer.stage("multi_station"):
            multi, joint, multi_results = _multi_station(scenario, stations, daily, degradations)

    relays: tuple[RelayKeyVolume, ...] = ()
    relay_results: RelayResults | None = None
    if scenario.relay is not None:
        with timer.stage("relay"):
            relays, relay_results = _relay_results(scenario, stations, daily, degradations)

    with timer.stage("result"):
        monte_carlo = _monte_carlo_results(scenario, stations, source, degradations)
        provenance = Provenance.collect(
            scenario,
            seed=source.seed if source is not None else None,
            data_versions=data_versions,
        )
        series = tuple(station.series for station in stations)

    result = SimulationResult(
        scenario=scenario,
        provenance=provenance,
        series=series,
        passes=passes,
        daily=daily,
        monte_carlo=monte_carlo,
        multi_station=multi_results,
        relay=relay_results,
        warnings=degradations.to_dicts(),
        timings=timer.timings(),
    )
    return Simulation(
        result=result,
        trajectory=trajectory,
        stations=stations,
        multi_station=multi,
        joint_cloud_free=joint,
        relays=relays,
    )


# --------------------------------------------------------------------------- #
# Preconditions and randomness
# --------------------------------------------------------------------------- #
def _require_scenario(scenario: Any) -> None:
    if not isinstance(scenario, Scenario):
        raise ScenarioError(
            f"run expects a quoss.scenario.models.Scenario, got {type(scenario).__name__}. Load "
            "a file with quoss.scenario.io.load_scenario."
        )


def _check_preconditions(scenario: Scenario, degradations: DegradationLog) -> None:
    """Refuse, before computing anything, the questions a scenario cannot answer."""
    fractions = [station.cloud_fraction for station in scenario.stations]
    given = [f is not None for f in fractions]
    spec = scenario.multi_station
    if spec is not None:
        if len(scenario.stations) < 2:
            raise ScenarioError(
                f"multi_station is set but the scenario has {len(scenario.stations)} station; "
                "aggregating stations needs at least two. Remove multi_station or add a station."
            )
        if any(given) and not all(given):
            missing = [s.name for s in scenario.stations if s.cloud_fraction is None]
            raise ScenarioError(
                f"stations {missing} have no cloud_fraction while the others do. The aggregation "
                "weights every pass by its cloud-free probability or none of them: a station "
                "with no cloud model would be counted as always clear next to stations that are "
                "not. Give every station a cloud_fraction, or none."
            )
        if spec.cloud_decorrelation_length_km is not None and not any(given):
            raise ScenarioError(
                "multi_station.cloud_decorrelation_length_km is set but no station has a "
                "cloud_fraction: there is no cloud-free probability to correlate."
            )
    elif any(given):
        degradations.warn(
            "engine.cloud-fraction-unused",
            "cloud_fraction is given for at least one station but the scenario has no "
            "multi_station section, which is the only stage that reads it. The pass table and "
            "the daily key are certified figures for a pass that happens and are not weighted "
            "by weather.",
            where=f"{_WHERE}.simulate",
            stations=[s.name for s in scenario.stations if s.cloud_fraction is not None],
        )


def _random_source_for(
    scenario: Scenario, random_source: RandomSource | None
) -> RandomSource | None:
    if scenario.monte_carlo is None:
        return None
    if random_source is not None:
        if not isinstance(random_source, RandomSource):
            raise DomainError(
                f"random_source must be a RandomSource, got {type(random_source).__name__}."
            )
        return random_source
    return RandomSource.from_seed(scenario.monte_carlo.seed)


def _station_sources(scenario: Scenario, source: RandomSource | None) -> list[RandomSource | None]:
    count = len(scenario.stations)
    if source is None:
        return [None] * count
    if count == 1:
        return [source]
    return list(source.spawn(count))


# --------------------------------------------------------------------------- #
# Stage 1: orbit
# --------------------------------------------------------------------------- #
def _propagate(
    scenario: Scenario, grid: TimeGrid, degradations: DegradationLog
) -> tuple[Trajectory, dict[str, str]]:
    """Propagate the scenario's orbit onto its grid.

    A TLE is propagated at seconds from **its own** epoch — the only epoch its
    elements are from — and the positions are then placed on the scenario's
    grid. :func:`~quoss.orbits.geometry.look_angles` reads the Earth's rotation
    angle from ``trajectory.grid``, so the grid the trajectory carries must be
    the one whose instants the positions describe; keeping the TLE's grid
    would rotate the Earth by the wrong amount by the whole epoch offset.
    """
    kepler, tle = scenario.orbit.kepler, scenario.orbit.tle
    if kepler is not None:
        return propagate(kepler.to_elements(), grid, method=kepler.propagation_method), {}
    assert tle is not None  # OrbitSpec guarantees exactly one
    satrec = tle.to_satrec()
    epoch_jd = tle.epoch_jd
    offset_s = (grid.epoch_jd - epoch_jd) * SECONDS_PER_DAY
    try:
        raw = propagate_tle(satrec, offset_s + grid.t_s)
    except DomainError as error:
        raise ScenarioError(
            f"the TLE (epoch JD {epoch_jd!r}) cannot be propagated over the scenario window "
            f"starting {scenario.time.epoch_utc.isoformat()} ({offset_s / SECONDS_PER_DAY:+.3f} "
            f"days from the TLE epoch, {grid.duration_s:g} s long): {error}"
        ) from error
    degradations.info(
        "engine.tle-window-offset",
        f"the scenario window starts {offset_s / SECONDS_PER_DAY:+.4f} days from the TLE epoch. "
        "SGP4 propagates the element set from its epoch; the further the window, the older the "
        "fit it extrapolates.",
        where=f"{_WHERE}._propagate",
        offset_days=offset_s / SECONDS_PER_DAY,
        tle_epoch_jd=epoch_jd,
        satellite_number=int(satrec.satnum),
    )
    trajectory = Trajectory(
        r_km=np.asarray(raw.r_km),
        v_km_s=np.asarray(raw.v_km_s),
        grid=grid,
        frame=raw.frame,
        method=raw.method,
    )
    return trajectory, {"tle": f"{satrec.satnum}@{epoch_jd!r}"}


# --------------------------------------------------------------------------- #
# Stages 2-7: one station
# --------------------------------------------------------------------------- #
def _run_station(task: _StationTask, degradations: DegradationLog) -> StationRun:
    """Geometry, passes, channel, key, series and ensemble of one station."""
    timer = StageTimer()
    scenario = task.scenario
    station = scenario.stations[task.index]
    trajectory = task.trajectory
    grid = trajectory.grid
    protocol = scenario.protocol.to_protocol()
    security = scenario.security.to_security()

    with timer.stage("geometry"):
        angles = look_angles(
            trajectory,
            station_latitude_rad=station.latitude_rad,
            station_longitude_rad=station.longitude_rad,
            station_altitude_km=station.altitude_km,
        )
    with timer.stage("passes"):
        table = find_passes(
            angles,
            grid=grid,
            minimum_elevation_rad=scenario.passes.minimum_elevation_rad,
            minimum_duration_s=scenario.passes.minimum_duration_s,
            degradations=degradations,
        )
        samples = table.samples()

    loss: LossBudget | None = None
    noise: NoiseBudget | None = None
    conditions: LinkConditions | None = None
    finite_daily: DailyKeyVolume | None = None
    asymptotic_daily: DailyKeyVolume | None = None
    monte_carlo: MonteCarloKeyVolume | None = None
    monte_carlo_daily: MonteCarloDailyKeyVolume | None = None

    if samples.size == 0:
        finite = _empty_volume(samples, KeyRegime.FINITE, protocol, security)
        asymptotic = _empty_volume(samples, KeyRegime.ASYMPTOTIC, protocol, security)
    else:
        rows = (samples.satellite_index, samples.sample_index)
        elevation = np.asarray(angles.elevation_rad)[rows]
        slant_range = np.asarray(angles.range_km)[rows]
        with timer.stage("channel"):
            loss, noise, conditions = _channel(
                scenario, station, elevation, slant_range, degradations
            )
        with timer.stage("key"):
            finite = pass_key_volume(
                conditions,
                samples=samples,
                protocol=protocol,
                security=security,
                degradations=degradations,
                key_basis_probability=scenario.protocol.key_basis_probability,
            )
            asymptotic = asymptotic_pass_key_volume(
                conditions, samples=samples, protocol=protocol, degradations=degradations
            )
            finite_daily = daily_key_volume(finite, degradations=degradations)
            asymptotic_daily = daily_key_volume(asymptotic, degradations=degradations)
        if scenario.monte_carlo is not None:
            assert task.random_source is not None  # _station_sources gives one per station
            with timer.stage("monte_carlo"):
                spec = scenario.monte_carlo
                transmitter = scenario.transmitter
                variance = downlink_log_irradiance_variance(
                    elevation,
                    aperture_diameter_m=station.receive_aperture_m,
                    wavelength_m=transmitter.wavelength_m,
                    degradations=degradations,
                    station_height_m=station.station_height_m,
                    rms_wind_speed_m_s=station.rms_wind_speed_m_s,
                    ground_cn2_m23=station.ground_cn2_m23,
                )
                gamma = beam_to_jitter_ratio(
                    slant_range,
                    jitter_rad=transmitter.pointing_jitter_rad,
                    wavelength_m=transmitter.wavelength_m,
                    transmit_aperture_m=transmitter.aperture_m,
                    receive_aperture_m=station.receive_aperture_m,
                    degradations=degradations,
                )
                monte_carlo = monte_carlo_pass_key_volume(
                    conditions,
                    samples=samples,
                    nominal_fade_db=np.asarray(loss.fade_db),
                    log_irradiance_variance_np2=np.asarray(variance, dtype=np.float64),
                    beam_to_jitter_ratio=np.asarray(gamma, dtype=np.float64),
                    protocol=protocol,
                    security=security,
                    fading=FadingParameters(
                        scintillation_correlation_time_s=spec.scintillation_correlation_time_s,
                        pointing_correlation_time_s=spec.pointing_correlation_time_s,
                    ),
                    options=MonteCarloOptions(
                        realisations=spec.realisations,
                        sample_counts=spec.sample_counts,
                        quantiles=tuple(spec.quantiles),
                    ),
                    random_source=task.random_source,
                    degradations=degradations,
                    key_basis_probability=scenario.protocol.key_basis_probability,
                )
                monte_carlo_daily = monte_carlo_daily_key_volume(
                    monte_carlo, degradations=degradations
                )

    with timer.stage("series"):
        acquisition = _acquisition(scenario, angles, samples, grid)
        series = _series(
            station.name, grid, angles, samples, loss, noise, conditions, protocol, acquisition
        )

    return StationRun(
        name=station.name,
        angles=angles,
        table=table,
        samples=samples,
        loss=loss,
        noise=noise,
        conditions=conditions,
        finite=finite,
        asymptotic=asymptotic,
        finite_daily=finite_daily,
        asymptotic_daily=asymptotic_daily,
        monte_carlo=monte_carlo,
        monte_carlo_daily=monte_carlo_daily,
        series=series,
        acquisition=acquisition,
        seconds=timer.to_dict(),
    )


def _channel(
    scenario: Scenario,
    station: StationSpec,
    elevation_rad: FloatArray,
    range_km: FloatArray,
    degradations: DegradationLog,
) -> tuple[LossBudget, NoiseBudget, LinkConditions]:
    """Both budgets at the in-pass samples, every scenario field wired.

    The afterpulse term needs the mean detected signal per gate, which
    :func:`~quoss.channel.link_budget.downlink_noise_budget` documents as
    ``mean_photon_number * transmittance``. A decoy source emits three
    intensities, and an afterpulse follows a click whichever intensity caused
    it, so the mean photon number is the emission-weighted mean
    ``p_s mu_s + p_d mu_d`` (the vacuum contributes nothing). With
    ``afterpulse_probability = 0`` — every scenario in ``scenarios/`` — the
    term is exactly zero whatever this mean is, which the end-to-end identity
    checks.
    """
    transmitter, receiver, channel = scenario.transmitter, scenario.receiver, scenario.channel
    spec = scenario.protocol
    loss = downlink_loss_budget(
        elevation_rad,
        range_km=range_km,
        wavelength_m=transmitter.wavelength_m,
        transmit_aperture_m=transmitter.aperture_m,
        receive_aperture_m=station.receive_aperture_m,
        zenith_transmittance=channel.zenith_transmittance,
        pointing_jitter_rad=transmitter.pointing_jitter_rad,
        receiver_efficiency=receiver.chain_efficiency,
        degradations=degradations,
        outage_probability=channel.outage_probability,
        static_loss_db=channel.static_loss_db,
        transmit_truncation_ratio=transmitter.truncation_ratio,
        fade_combination=channel.fade_combination,
        station_height_m=station.station_height_m,
        rms_wind_speed_m_s=station.rms_wind_speed_m_s,
        ground_cn2_m23=station.ground_cn2_m23,
    )
    mean_photon_number = (
        spec.signal_probability * spec.signal_intensity
        + spec.decoy_probability * spec.decoy_intensity
    )
    noise = downlink_noise_budget(
        scenario.background.radiance_w_m2_um_sr(
            transmitter.wavelength_m, degradations=degradations
        ),
        wavelength_m=transmitter.wavelength_m,
        receive_aperture_m=station.receive_aperture_m,
        field_of_view_full_angle_rad=receiver.field_of_view_rad,
        filter_bandwidth_m=receiver.filter_bandwidth_m,
        gate_duration_s=receiver.gate_s,
        receiver_efficiency=receiver.chain_efficiency,
        dark_count_rate_cps=receiver.dark_count_rate_cps,
        degradations=degradations,
        detector_count=receiver.detector_count,
        afterpulse_probability=receiver.afterpulse_probability,
        signal_counts_per_gate=mean_photon_number * np.asarray(loss.transmittance),
    )
    conditions = LinkConditions(
        transmittance=loss.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=spec.misalignment_error,
        pulse_rate_hz=transmitter.pulse_rate_hz,
        gate_duration_s=receiver.gate_s,
    )
    return loss, noise, conditions


def _acquisition(
    scenario: Scenario, angles: LookAngles, samples: PassSamples, grid: TimeGrid
) -> Acquisition:
    """Return the Doppler pair and the point-ahead angle, on the grid and per pass.

    Two things are worth reading rather than skipping.

    **The series are computed over the whole grid and only then indexed.** A
    derivative taken inside a pass would see the pass boundary as an edge and
    return a one-sided difference there — exactly at the horizon, which is the
    instant the whole quantity exists to describe. Differentiating the full
    grid and slicing afterwards has no such edge.

    **The carrier is derived, not configured.** ``f0 = c / lambda`` of the
    scenario's own transmitter, so a run cannot carry a Doppler for a carrier
    the scenario does not transmit. A system with a separate classical downlink
    has a second carrier; it needs a second field, and inventing one here would
    be a value nobody declared.
    """
    carrier_frequency_hz = float(SPEED_OF_LIGHT_M_S / scenario.transmitter.wavelength_m)
    range_rate = np.asarray(angles.range_rate_km_s, dtype=np.float64)[0]
    point_ahead = np.asarray(angles.point_ahead_angle_rad, dtype=np.float64)[0]
    shift = np.asarray(doppler_shift_hz(range_rate, carrier_frequency_hz), dtype=np.float64)
    rate = np.asarray(
        doppler_rate_hz_s(
            range_rate, t_s=np.asarray(grid.t_s), carrier_frequency_hz=carrier_frequency_hz
        ),
        dtype=np.float64,
    )
    rows = np.asarray(samples.sample_index)
    empty = np.zeros(samples.table.n_passes, dtype=np.float64)
    return Acquisition(
        carrier_frequency_hz=carrier_frequency_hz,
        range_rate_km_s=range_rate,
        doppler_shift_hz=shift,
        doppler_rate_hz_s=rate,
        point_ahead_angle_rad=point_ahead,
        max_abs_doppler_hz=(
            empty if samples.size == 0 else samples.segment_max(np.abs(shift[rows]))
        ),
        max_abs_doppler_rate_hz_s=(
            empty if samples.size == 0 else samples.segment_max(np.abs(rate[rows]))
        ),
        max_point_ahead_angle_rad=(
            empty if samples.size == 0 else samples.segment_max(point_ahead[rows])
        ),
        min_point_ahead_angle_rad=(
            empty if samples.size == 0 else samples.segment_min(point_ahead[rows])
        ),
    )


def _empty_volume(
    samples: PassSamples,
    regime: KeyRegime,
    protocol: Bb84DecoyProtocol,
    security: SecurityParameters,
) -> PassKeyVolume:
    """Return a key volume of zero passes, for a station the satellite never rose over.

    :func:`~quoss.system.key_volume.pass_key_volume` refuses empty samples,
    rightly for a direct caller; :func:`~quoss.system.multi_ogs.aggregate_stations`
    needs one volume per station, pass or no pass. Zero passes, zero bits, and
    in the finite regime a bound evaluated over zero blocks.
    """
    empty = np.zeros(0, dtype=np.float64)
    finite = (
        FiniteKeyResult(**dict.fromkeys(FiniteKeyResult._ARRAYS, empty), security=security)
        if regime is KeyRegime.FINITE
        else None
    )
    return PassKeyVolume(
        samples=samples,
        regime=regime,
        key_bits=empty,
        pulses=empty,
        seconds=empty,
        finite=finite,
        protocol=protocol.name,
    )


def _series(
    name: str,
    grid: TimeGrid,
    angles: LookAngles,
    samples: PassSamples,
    loss: LossBudget | None,
    noise: NoiseBudget | None,
    conditions: LinkConditions | None,
    protocol: Bb84DecoyProtocol,
    acquisition: Acquisition,
) -> SeriesResults:
    """Return the station's series on the whole grid; channel and rate only inside passes.

    **Why NaN outside a pass, and not a number.** Below the mask the channel
    is either undefined — at negative elevation the line of sight goes through
    the Earth, and the secant air mass the atmospheric term uses has no meaning
    — or defined and useless: a loss budget at 3 degrees is a number nobody
    should plot as a link that exists, because the pass table says it does
    not, and the key volume never reads it. A zero would be worse than either:
    it is a transmittance that says "opaque" and a rate that says "no key",
    both claims about a link that was never evaluated. NaN is what a plot
    leaves blank and a sum refuses.

    **Why the rate is evaluated a second time.** The per-sample asymptotic rate
    is inside :func:`~quoss.system.key_volume.asymptotic_pass_key_volume`, which
    returns only its integral. The same protocol call on the same conditions
    produces the same numbers and the same log entries, which that function
    already recorded; they are recorded once, into a scratch log here, and the
    equality of the two logs is tested
    (``tests/engine/test_pipeline.py::TestTheSeries``).
    """
    elevation = np.asarray(angles.elevation_rad, dtype=np.float64)[0]
    azimuth = np.asarray(angles.azimuth_rad, dtype=np.float64)[0]
    slant = np.asarray(angles.range_km, dtype=np.float64)[0]

    def inside(values: FloatArray | None) -> FloatArray:
        out = np.full(grid.n, np.nan, dtype=np.float64)
        if values is not None:
            out[samples.sample_index] = values
        return out

    rate: FloatArray | None = None
    if conditions is not None:
        rate = np.asarray(
            protocol.key_rate(conditions, degradations=DegradationLog()).secure_bit_s,
            dtype=np.float64,
        )
    return SeriesResults(
        station=name,
        grid=grid,
        elevation_rad=TimeSeries(grid, elevation, name="elevation", unit="rad"),
        azimuth_rad=TimeSeries(grid, azimuth, name="azimuth", unit="rad"),
        range_km=TimeSeries(grid, slant, name="range", unit="km"),
        range_rate_km_s=TimeSeries(
            grid, acquisition.range_rate_km_s, name="range_rate", unit="km/s"
        ),
        doppler_shift_hz=TimeSeries(
            grid, acquisition.doppler_shift_hz, name="doppler_shift", unit="Hz"
        ),
        doppler_rate_hz_s=TimeSeries(
            grid, acquisition.doppler_rate_hz_s, name="doppler_rate", unit="Hz/s"
        ),
        point_ahead_angle_rad=TimeSeries(
            grid, acquisition.point_ahead_angle_rad, name="point_ahead", unit="rad"
        ),
        transmittance=TimeSeries(
            grid,
            inside(None if loss is None else np.asarray(loss.transmittance)),
            name="transmittance",
            unit="",
        ),
        loss_total_db=TimeSeries(
            grid,
            inside(None if loss is None else np.asarray(loss.total_db)),
            name="loss_total",
            unit="dB",
        ),
        noise_per_gate=TimeSeries(
            grid,
            inside(None if noise is None else np.asarray(noise.total_per_gate)),
            name="noise_per_gate",
            unit="counts/gate",
        ),
        asymptotic_secure_bit_s=TimeSeries(
            grid, inside(rate), name="asymptotic_secure_rate", unit="bit/s"
        ),
    )


# --------------------------------------------------------------------------- #
# Stage 10 pieces: passes and days
# --------------------------------------------------------------------------- #
def _pass_results(grid: TimeGrid, stations: Sequence[StationRun]) -> PassResults:
    """Concatenate the stations' pass tables and key, in station order."""
    tables = [s.table for s in stations]
    return PassResults(
        epoch_jd=grid.epoch_jd,
        station=tuple(name for s in stations for name in [s.name] * s.table.n_passes),
        satellite_index=_concatenate([t.satellite_index for t in tables], np.int64),
        start_s=_concatenate([t.start_s for t in tables], np.float64),
        end_s=_concatenate([t.end_s for t in tables], np.float64),
        culmination_s=_concatenate([t.culmination_s for t in tables], np.float64),
        culmination_elevation_rad=_concatenate(
            [t.culmination_elevation_rad for t in tables], np.float64
        ),
        max_abs_doppler_hz=_concatenate(
            [s.acquisition.max_abs_doppler_hz for s in stations], np.float64
        ),
        max_abs_doppler_rate_hz_s=_concatenate(
            [s.acquisition.max_abs_doppler_rate_hz_s for s in stations], np.float64
        ),
        max_point_ahead_angle_rad=_concatenate(
            [s.acquisition.max_point_ahead_angle_rad for s in stations], np.float64
        ),
        min_point_ahead_angle_rad=_concatenate(
            [s.acquisition.min_point_ahead_angle_rad for s in stations], np.float64
        ),
        finite_bits=_concatenate([s.finite.key_bits for s in stations], np.float64),
        asymptotic_bits=_concatenate([s.asymptotic.key_bits for s in stations], np.float64),
        truncated_start=_concatenate([t.truncated_start for t in tables], np.bool_),
        truncated_end=_concatenate([t.truncated_end for t in tables], np.bool_),
        day_number=_concatenate([t.day_number for t in tables], np.int64),
    )


def _concatenate(parts: Sequence[Any], dtype: type[np.generic]) -> Any:
    return np.concatenate([np.asarray(p, dtype=dtype) for p in parts]).astype(dtype)


def _day_axis(stations: Sequence[StationRun]) -> IntArray:
    """Every UTC day, as a Julian Day Number, that holds at least one pass of any station."""
    days: IntArray = np.unique(_concatenate([s.table.day_number for s in stations], np.int64))
    return days


def _onto_days(days: IntArray, day_number: IntArray, values: FloatArray) -> FloatArray:
    """Add per-day values onto the result's day axis, in the order given."""
    index = np.searchsorted(days, day_number)
    if index.size and (
        np.any(index >= days.size) or np.any(days[np.minimum(index, days.size - 1)] != day_number)
    ):
        raise DomainError(
            f"day numbers {np.asarray(day_number).tolist()} are not all on the result's day axis "
            f"{days.tolist()}; the stages disagree about which days hold passes."
        )
    out = np.zeros(days.size, dtype=np.float64)
    np.add.at(out, index, np.asarray(values, dtype=np.float64))
    return out


def _daily_results(
    scenario: Scenario, stations: Sequence[StationRun], degradations: DegradationLog
) -> DailyResults:
    """Sum the stations' days into one table and state the security of the sum.

    **With one station** every column is that station's
    :func:`~quoss.system.key_volume.daily_key_volume` copied: adding a day's
    bits to a zero is exact, and the composed ``eps`` is
    :func:`~quoss.system.key_volume.composed_security` of the same busiest-day
    block count, so the two agree to the bit.

    **With several** the table is the sum over stations — each station's key is
    certified on its own passes, so lengths add — and the composed ``eps`` is the
    union bound over the most blocks any one day holds across all stations. It is
    *not* what one satellite terminal could deliver when two stations' passes
    overlap; that question is :attr:`~quoss.scenario.result.SimulationResult.multi_station`.

    **``compose_daily``.** :func:`~quoss.system.key_volume.daily_key_volume`
    always composes, because the concatenation of ``n`` blocks each
    ``eps``-secure is ``n eps``-secure whether or not anybody writes it down.
    The flag therefore decides only whether the table *states* the composed
    value: ``False`` leaves the two fields ``None`` and records a ``WARNING`` that
    the sum carries no failure probability, so a "bits per day" read from it
    has no ``eps`` to quote.
    """
    days = _day_axis(stations)
    finite_bits = np.zeros(days.size, dtype=np.float64)
    asymptotic_bits = np.zeros(days.size, dtype=np.float64)
    pass_count = np.zeros(days.size, dtype=np.float64)
    passes_with_key = np.zeros(days.size, dtype=np.float64)
    seconds = np.zeros(days.size, dtype=np.float64)
    for station in stations:
        finite, asymptotic = station.finite_daily, station.asymptotic_daily
        if finite is None or asymptotic is None:
            continue
        finite_bits += _onto_days(days, finite.day_number, finite.key_bits)
        asymptotic_bits += _onto_days(days, asymptotic.day_number, asymptotic.key_bits)
        pass_count += _onto_days(days, finite.day_number, finite.pass_count.astype(np.float64))
        passes_with_key += _onto_days(
            days, finite.day_number, finite.passes_with_key.astype(np.float64)
        )
        seconds += _onto_days(days, finite.day_number, finite.seconds)

    correctness: float | None = None
    secrecy: float | None = None
    if days.size:
        if scenario.security.compose_daily:
            composed = composed_security(scenario.security.to_security(), int(pass_count.max()))
            correctness, secrecy = composed.correctness, composed.secrecy
        else:
            degradations.warn(
                "engine.daily-not-composed",
                "security.compose_daily is false, so the daily table states no failure "
                "probability. Each pass's key is secure at the per-block eps; the day's "
                f"concatenation of up to {int(pass_count.max())} blocks is secure only at the "
                "union bound, which is true whether or not it is reported.",
                where=f"{_WHERE}._daily_results",
                blocks=int(pass_count.max()),
            )
    return DailyResults(
        day_number=days,
        finite_bits=finite_bits,
        asymptotic_bits=asymptotic_bits,
        pass_count=pass_count.astype(np.int64),
        passes_with_key=passes_with_key.astype(np.int64),
        seconds=seconds,
        composed_correctness=correctness,
        composed_secrecy=secrecy,
        protocol=scenario.protocol.name,
    )


# --------------------------------------------------------------------------- #
# Optional stages
# --------------------------------------------------------------------------- #
def _monte_carlo_results(
    scenario: Scenario,
    stations: Sequence[StationRun],
    source: RandomSource | None,
    degradations: DegradationLog,
) -> MonteCarloResults | None:
    """Concatenate the ensembles' per-pass columns in pass-table order.

    The per-day quantiles have no field in the result schema; they are
    recorded as an ``INFO`` entry per station so that the headline number of an
    ensemble is not lost between the physics and the file.
    """
    spec = scenario.monte_carlo
    if spec is None:
        return None
    assert source is not None  # _random_source_for builds one whenever spec is set
    count = len(spec.quantiles)
    quantile_bits = [np.zeros((count, 0))]
    outage = [np.zeros(0)]
    mean_bits = [np.zeros(0)]
    for station in stations:
        volume, daily = station.monte_carlo, station.monte_carlo_daily
        if volume is None or daily is None:
            continue
        quantile_bits.append(np.asarray(volume.quantile_bits))
        outage.append(np.asarray(volume.outage_probability))
        mean_bits.append(np.asarray(volume.mean_bits))
        degradations.info(
            "engine.monte-carlo-daily",
            f"ensemble quantiles of the day's key at {station.name!r}; the result schema has no "
            "per-day Monte Carlo field, so they are recorded here.",
            where=f"{_WHERE}._monte_carlo_results",
            station=station.name,
            day_number=np.asarray(daily.day_number).tolist(),
            quantiles=list(daily.quantiles),
            quantile_bits=np.asarray(daily.quantile_bits).tolist(),
            mean_bits=np.asarray(daily.mean_bits).tolist(),
            expected_bits=np.asarray(daily.expected_bits).tolist(),
            design_bits=np.asarray(daily.design_bits).tolist(),
        )
    return MonteCarloResults(
        quantiles=tuple(spec.quantiles),
        quantile_bits=np.concatenate(quantile_bits, axis=1),
        outage_probability=np.concatenate(outage),
        mean_bits=np.concatenate(mean_bits),
        realisations=spec.realisations,
        seed=source.seed,
    )


def _multi_station(
    scenario: Scenario,
    stations: Sequence[StationRun],
    daily: DailyResults,
    degradations: DegradationLog,
) -> tuple[MultiStationKeyVolume, JointCloudFreeProbability | None, MultiStationResults]:
    """Aggregate the stations under the scenario's policy.

    A station's ``cloud_fraction`` is a climatology — one number for the site —
    so its cloud-free probability is the same for every pass of that station.
    The columns of ``bits_per_station_day`` are the days of
    :attr:`~quoss.scenario.result.SimulationResult.daily`, with a zero where a
    station had no selected pass that day, so that the two tables share one
    axis.
    """
    spec = scenario.multi_station
    assert spec is not None  # the caller checks
    specs = scenario.stations
    station_set = StationSet(
        names=scenario.station_names,
        latitude_rad=np.array([s.latitude_rad for s in specs], dtype=np.float64),
        longitude_rad=np.array([s.longitude_rad for s in specs], dtype=np.float64),
        altitude_km=np.array([s.altitude_km for s in specs], dtype=np.float64),
    )
    availability: list[FloatArray] | None = None
    probability: FloatArray | None = None
    if all(s.cloud_fraction is not None for s in specs):
        fractions = np.array([s.cloud_fraction for s in specs], dtype=np.float64)
        probability = np.asarray(
            cloud_free_probability(fractions, degradations=degradations), dtype=np.float64
        )
        availability = [
            np.full(run.finite.n_passes, float(p), dtype=np.float64)
            for run, p in zip(stations, probability, strict=True)
        ]
    volume = aggregate_stations(
        station_set,
        [run.finite for run in stations],
        availability=availability,
        policy=AggregationPolicy(spec.policy.value),
        degradations=degradations,
    )
    joint: JointCloudFreeProbability | None = None
    if spec.cloud_decorrelation_length_km is not None:
        assert probability is not None  # _check_preconditions refuses the other case
        joint = joint_cloud_free_probability(
            probability,
            separation_km=station_set.separation_km(),
            decorrelation_length_km=spec.cloud_decorrelation_length_km,
            degradations=degradations,
        )
        degradations.info(
            "engine.joint-cloud-free-probability",
            "probability that at least one station has a cloud-free line of sight; the result "
            "schema has no field for it, so it is recorded here.",
            where=f"{_WHERE}._multi_station",
            independent=np.asarray(joint.independent).tolist(),
            comonotone=np.asarray(joint.comonotone).tolist(),
            exact=None if joint.exact is None else np.asarray(joint.exact).tolist(),
            decorrelation_length_km=joint.decorrelation_length_km,
        )
    degradations.info(
        "engine.multi-station-totals",
        f"{spec.policy.value}: the result keeps certified bits per station and day; the "
        "availability-weighted totals and the conflicts are recorded here.",
        where=f"{_WHERE}._multi_station",
        station_bits=np.asarray(volume.station_bits).tolist(),
        station_expected_bits=np.asarray(volume.station_expected_bits).tolist(),
        conflicts_dropped=int(volume.conflicts_dropped),
    )
    rows = []
    for record in volume.per_station:
        table = record.volume.samples.table
        keep = np.asarray(record.selected)
        rows.append(
            _onto_days(
                daily.day_number,
                np.asarray(table.day_number)[keep],
                np.asarray(record.volume.key_bits)[keep],
            )
        )
    results = MultiStationResults(
        station_names=scenario.station_names,
        bits_per_station_day=np.vstack(rows),
        scheduled_pass_count=np.array([int(np.sum(r.selected)) for r in volume.per_station]),
        policy=spec.policy.value,
    )
    return volume, joint, results


def _relay_results(
    scenario: Scenario,
    stations: Sequence[StationRun],
    daily: DailyResults,
    degradations: DegradationLog,
) -> tuple[tuple[RelayKeyVolume, ...], RelayResults]:
    """Relay every pair and reduce each to the schema's per-pair row.

    **The one reduction.** :class:`~quoss.system.relay.RelayKeyVolume` carries a
    bit-weighted mean age per delivery; the schema holds one latency per pair.
    The pair's value is the bit-weighted mean over all deliveries,
    ``sum(mean_latency_e * bits_e) / sum(bits_e)`` — the mean age of a delivered
    bit, which is what the per-delivery values average to when every bit counts
    once. A pair that delivered nothing gets NaN: no bit has an age, and zero
    would claim instant delivery.
    """
    spec = scenario.relay
    assert spec is not None  # the caller checks
    names = scenario.station_names
    volumes: list[RelayKeyVolume] = []
    delivered_rows: list[FloatArray] = []
    latency: list[float] = []
    residual: list[float] = []
    for a, b in spec.pairs:
        volume = trusted_node_relay(
            stations[names.index(a)].finite,
            stations[names.index(b)].finite,
            degradations=degradations,
            names=(a, b),
        )
        volumes.append(volume)
        delivered_rows.append(_onto_days(daily.day_number, volume.day_number, volume.daily_bits))
        bits = np.asarray(volume.delivered_bits, dtype=np.float64)
        total = float(bits.sum())
        latency.append(
            float(np.sum(np.asarray(volume.mean_latency_s) * bits) / total)
            if total > 0.0
            else float("nan")
        )
        residual.append(float(volume.stranded_bits))
    results = RelayResults(
        pairs=tuple((a, b) for a, b in spec.pairs),
        delivered_bits_per_day=np.vstack(delivered_rows),
        mean_latency_s=np.array(latency, dtype=np.float64),
        residuals=np.array(residual, dtype=np.float64),
    )
    return tuple(volumes), results
