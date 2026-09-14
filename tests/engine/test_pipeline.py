"""Tests for `quoss.engine.pipeline`.

- ``TestWhatRunRefusesBeforeComputing`` — a non-scenario, a wrong random source,
  a bad worker count, and the four questions a scenario can ask that no engine
  can answer from it.
- ``TestTheKeplerPath`` / ``TestTheTlePath`` — the two ways an orbit arrives, and
  what the TLE path records about the window it extrapolates over.
- ``TestAStationTheSatelliteNeverRoseOver`` — zero passes is a shape, not a
  failure, and none of the numbers it produces claims anything.
- ``TestTheSeries`` — NaN outside a pass and not zero, and the claim the module
  docstring makes about evaluating the rate a second time.
- ``TestTheDayAxis`` — every station's days land on one axis, and the refusal
  when they do not.
- ``TestTheDailySecurityClaim`` — composed or explicitly not composed, never
  quietly absent.
- ``TestTheEnsembleStage`` — the seed that is recorded, and the per-day quantiles
  that have no schema field and so go into the log.
- ``TestTheMultiStationStage`` and ``TestTheRelayStage`` — the optional stages,
  their tables and their one reduction.
- ``TestWorkersDoNotChangeTheRun`` — two processes give the same result as one.
- ``TestTheTimingsCoverEveryStageThatRan`` — what the profiling rows mean when a
  stage ran once per station.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quoss.core.errors import DegradationLog, DomainError, ScenarioError, Severity
from quoss.core.rng import RandomSource
from quoss.engine.pipeline import STAGES, _onto_days, run, simulate
from quoss.engine.sweep import apply_point
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.io import load_scenario
from quoss.scenario.models import (
    MonteCarloSpec,
    MultiStationSpec,
    RelaySpec,
    Scenario,
    SecuritySpec,
)
from quoss.scenario.result import SimulationResult

CALAR_ALTO = {"name": "calar_alto", "latitude_deg": 37.2236, "longitude_deg": -2.5464}
OGS_TENERIFE = {"name": "ogs_tenerife", "latitude_deg": 28.3000, "longitude_deg": -16.5100}
"""Two more sites, far enough from Castelldefels that they see different passes.

Coordinates rounded from the public positions of Calar Alto and the Teide
Observatory. They are here to make the satellite rise over three places at
different times, not as a claim about either telescope, so nothing in this file
reads them as a measurement.
"""


def three_stations(**station_extra: Any) -> Scenario:
    """Return the reference scenario with two more stations, everything else unchanged."""
    base = reference_castelldefels()
    first = base.stations[0]
    return base.model_copy(
        update={
            "stations": [
                first.model_copy(update=dict(station_extra)),
                first.model_copy(update={**CALAR_ALTO, "altitude_m": 2168.0, **station_extra}),
                first.model_copy(update={**OGS_TENERIFE, "altitude_m": 2393.0, **station_extra}),
            ]
        }
    )


def with_monte_carlo(scenario: Scenario | None = None, *, seed: int | None = 7) -> Scenario:
    base = reference_castelldefels() if scenario is None else scenario
    return base.model_copy(
        update={
            "monte_carlo": MonteCarloSpec(
                realisations=16,
                seed=seed,
                scintillation_correlation_time_s=0.002,
                pointing_correlation_time_s=0.02,
            )
        }
    )


def no_pass_scenario() -> Scenario:
    """Return a scenario with an 85-degree mask: the satellite is never that high."""
    base = reference_castelldefels()
    return base.model_copy(
        update={"passes": base.passes.model_copy(update={"minimum_elevation_deg": 85.0})}
    )


@pytest.fixture(scope="module")
def reference_result() -> SimulationResult:
    return run(reference_castelldefels(), degradations=DegradationLog())


@pytest.fixture(scope="module")
def tle_scenario(request: pytest.FixtureRequest) -> Scenario:
    root = Path(str(request.config.rootpath))
    return load_scenario(root / "scenarios" / "tle_example.yaml")


class TestWhatRunRefusesBeforeComputing:
    def test_something_that_is_not_a_scenario(self) -> None:
        with pytest.raises(ScenarioError, match=r"expects a quoss\.scenario\.models\.Scenario"):
            run({"name": "not a scenario"}, degradations=DegradationLog())  # type: ignore[arg-type]

    def test_the_message_says_how_to_get_one(self) -> None:
        with pytest.raises(ScenarioError, match=r"quoss\.scenario\.io\.load_scenario"):
            run("scenarios/reference_castelldefels.yaml", degradations=DegradationLog())  # type: ignore[arg-type]

    def test_a_random_source_that_is_not_one(self) -> None:
        with pytest.raises(DomainError, match="random_source must be a RandomSource"):
            run(with_monte_carlo(), random_source=12345, degradations=DegradationLog())  # type: ignore[arg-type]

    def test_a_bad_worker_count(self) -> None:
        with pytest.raises(DomainError, match="workers must be an integer >= 1"):
            run(reference_castelldefels(), workers=0, degradations=DegradationLog())

    def test_multi_station_with_one_station(self) -> None:
        scenario = reference_castelldefels().model_copy(
            update={"multi_station": MultiStationSpec(policy="best_available")}
        )
        with pytest.raises(ScenarioError, match="aggregating stations needs at least two"):
            run(scenario, degradations=DegradationLog())

    def test_some_stations_with_a_cloud_fraction_and_some_without(self) -> None:
        """Half a cloud model is worse than none, and the message says why.

        A station with no ``cloud_fraction`` would be weighted as always clear
        beside stations that are not, so the aggregation would prefer it for
        reasons that are an absence of data rather than a property of the site.
        """
        base = three_stations()
        stations = list(base.stations)
        stations[0] = stations[0].model_copy(update={"cloud_fraction": 0.4})
        scenario = base.model_copy(
            update={
                "stations": stations,
                "multi_station": MultiStationSpec(policy="best_available"),
            }
        )
        with pytest.raises(ScenarioError, match=r"have no cloud_fraction while the others do"):
            run(scenario, degradations=DegradationLog())

    def test_a_decorrelation_length_with_nothing_to_correlate(self) -> None:
        scenario = three_stations().model_copy(
            update={
                "multi_station": MultiStationSpec(
                    policy="best_available", cloud_decorrelation_length_km=500.0
                )
            }
        )
        with pytest.raises(ScenarioError, match="no station has a cloud_fraction"):
            run(scenario, degradations=DegradationLog())

    def test_a_cloud_fraction_nothing_reads_is_a_warning_and_not_a_refusal(self) -> None:
        """The scenario is answerable; the field just does nothing, and it says so.

        A refusal here would be wrong — every number of the run is well defined
        — but silence would let somebody read the daily key as weather-weighted
        when it is the key of a pass that happens.
        """
        base = reference_castelldefels()
        scenario = base.model_copy(
            update={"stations": [base.stations[0].model_copy(update={"cloud_fraction": 0.4})]}
        )
        log = DegradationLog()
        run(scenario, degradations=log)
        (entry,) = [e for e in log if e.code == "engine.cloud-fraction-unused"]
        assert entry.severity is Severity.WARNING
        assert entry.details["stations"] == ["castelldefels"]


class TestTheKeplerPath:
    def test_the_reference_day_has_four_passes(self, reference_result: SimulationResult) -> None:
        assert reference_result.passes.n_passes == 4
        assert reference_result.provenance.data_versions == {}

    def test_no_ensemble_means_no_seed_recorded(self, reference_result: SimulationResult) -> None:
        """A run that drew no random number has no seed to reproduce.

        Recording one anyway would suggest the numbers depend on it, and a reader
        chasing a difference between two runs would spend the afternoon on the
        one thing that cannot have caused it.
        """
        assert reference_result.provenance.seed is None
        assert reference_result.monte_carlo is None

    def test_a_random_source_is_ignored_without_an_ensemble(self) -> None:
        result = run(
            reference_castelldefels(),
            random_source=RandomSource.from_seed(999),
            degradations=DegradationLog(),
        )
        assert result.provenance.seed is None


class TestTheTlePath:
    def test_the_data_version_names_the_element_set(self, tle_scenario: Scenario) -> None:
        result = run(tle_scenario, degradations=DegradationLog())
        assert result.provenance.data_versions["tle"].startswith("25544@")

    def test_the_run_says_how_far_the_window_is_from_the_tle_epoch(
        self, tle_scenario: Scenario
    ) -> None:
        """SGP4 extrapolates an element set; the age of the fit is the error bar.

        The example scenario starts at the TLE epoch, so the offset is a few
        hours at most; the entry exists so that a scenario whose window is a
        month away says so instead of quietly returning a trajectory nobody
        should trust.
        """
        log = DegradationLog()
        run(tle_scenario, degradations=log)
        (entry,) = [e for e in log if e.code == "engine.tle-window-offset"]
        assert entry.severity is Severity.INFO
        assert abs(float(entry.details["offset_days"])) < 1.0
        assert entry.details["satellite_number"] == 25544

    def test_a_window_sgp4_cannot_propagate_is_a_scenario_error(
        self, tle_scenario: Scenario
    ) -> None:
        """Decades from the epoch the fit decays; the refusal names the offset.

        The message has to carry the offset, because the scenario file says only
        when the *window* starts and the reader has to compare that with a TLE
        epoch encoded as two digits of year and a fractional day.
        """
        far = tle_scenario.model_copy(
            update={
                "time": tle_scenario.time.model_copy(
                    update={
                        "epoch_utc": tle_scenario.time.epoch_utc.replace(year=2099),
                    }
                )
            }
        )
        with pytest.raises(ScenarioError, match="cannot be propagated over the scenario window"):
            run(far, degradations=DegradationLog())


class TestAStationTheSatelliteNeverRoseOver:
    def test_zero_passes_is_a_shape_and_not_a_failure(self) -> None:
        result = run(no_pass_scenario(), degradations=DegradationLog())
        assert result.passes.n_passes == 0
        assert result.daily.day_number.size == 0
        assert result.daily.finite_bits.size == 0

    def test_the_empty_volumes_have_the_columns_a_later_stage_reads(self) -> None:
        """``aggregate_stations`` needs one volume per station, pass or no pass.

        ``pass_key_volume`` itself refuses an empty sample set, rightly for a
        direct caller: summing zero blocks is a question nobody means to ask.
        The engine is the one caller that does mean it, and builds the empty
        volume explicitly rather than letting a station drop out of the list and
        shift every index after it.
        """
        simulation = simulate(no_pass_scenario(), degradations=DegradationLog())
        (station,) = simulation.stations
        assert station.finite.key_bits.size == 0
        assert station.asymptotic.key_bits.size == 0
        assert station.finite.finite is not None
        assert station.asymptotic.finite is None
        assert station.loss is None
        assert station.conditions is None
        assert station.finite_daily is None

    def test_the_series_of_such_a_station_are_all_nan_below_the_mask(self) -> None:
        simulation = simulate(no_pass_scenario(), degradations=DegradationLog())
        (station,) = simulation.stations
        assert np.all(np.isnan(station.series.transmittance.values))
        assert np.all(np.isnan(station.series.asymptotic_secure_bit_s.values))
        assert np.all(np.isfinite(station.series.elevation_rad.values))


class TestTheSeries:
    def test_the_channel_is_nan_outside_a_pass_and_finite_inside(
        self, reference_result: SimulationResult
    ) -> None:
        """Not zero: a zero transmittance says "opaque", which is a claim.

        Below the mask the channel is either undefined — a negative elevation
        looks through the Earth — or defined and useless. NaN is what a plot
        leaves blank and a sum refuses; zero is a number somebody will average.
        """
        series = reference_result.series_for("castelldefels")
        transmittance = series.transmittance.values
        assert np.any(np.isnan(transmittance))
        assert np.any(np.isfinite(transmittance))
        assert np.all(np.asarray(transmittance)[np.isfinite(transmittance)] > 0.0)

    def test_the_geometry_is_defined_everywhere_because_it_always_is(
        self, reference_result: SimulationResult
    ) -> None:
        series = reference_result.series_for("castelldefels")
        assert np.all(np.isfinite(series.elevation_rad.values))
        assert np.all(np.isfinite(series.azimuth_rad.values))
        assert np.all(series.range_km.values > 0.0)

    def test_evaluating_the_rate_a_second_time_records_nothing_new(self) -> None:
        """The claim the module docstring makes, checked rather than asserted.

        The per-sample rate lives inside ``asymptotic_pass_key_volume``, which
        returns only its integral, so the series recomputes it. The same call on
        the same conditions produces the same log entries, which were already
        recorded once — so the second call writes into a scratch log, and this
        test is what says that scratch log holds nothing the run's log does not.
        """
        simulation = simulate(reference_castelldefels(), degradations=DegradationLog())
        (station,) = simulation.stations
        assert station.conditions is not None

        protocol = simulation.result.scenario.protocol.to_protocol()
        scratch = DegradationLog()
        rate = protocol.key_rate(station.conditions, degradations=scratch).secure_bit_s

        run_log = DegradationLog()
        run(reference_castelldefels(), degradations=run_log)
        assert {entry.code for entry in scratch} <= {entry.code for entry in run_log}

        inside = station.series.asymptotic_secure_bit_s.values[station.samples.sample_index]
        np.testing.assert_allclose(inside, np.asarray(rate))


class TestTheAcquisitionStage:
    """Doppler and point-ahead: what a terminal has to track, whatever the key says.

    The stage is geometry only, and its independence from the link budget is the
    property worth pinning: a station that certifies nothing still has a
    satellite sweeping a carrier over it, and an acquisition question is asked
    about exactly the part of the sky the key stage refuses to score.
    """

    def test_the_carrier_is_the_scenarios_own_wavelength_and_not_a_constant(self) -> None:
        """``f0 = c / lambda`` of the transmitter, so a run cannot carry a foreign carrier.

        Halving the wavelength doubles every Doppler number and leaves the
        geometry — range-rate and point-ahead — untouched, which is the whole
        content of "the carrier is an assumption and the geometry is not".
        """
        base = reference_castelldefels()
        halved = base.model_copy(
            update={
                "transmitter": base.transmitter.model_copy(
                    update={"wavelength_nm": base.transmitter.wavelength_nm / 2.0}
                )
            }
        )
        a = simulate(base, degradations=DegradationLog()).stations[0].acquisition
        b = simulate(halved, degradations=DegradationLog()).stations[0].acquisition
        assert b.carrier_frequency_hz == pytest.approx(2.0 * a.carrier_frequency_hz, rel=1e-12)
        assert np.allclose(b.doppler_shift_hz, 2.0 * np.asarray(a.doppler_shift_hz), rtol=1e-12)
        assert np.allclose(b.max_abs_doppler_hz, 2.0 * np.asarray(a.max_abs_doppler_hz), rtol=1e-12)
        assert np.array_equal(b.range_rate_km_s, a.range_rate_km_s)
        assert np.array_equal(b.point_ahead_angle_rad, a.point_ahead_angle_rad)

    def test_the_series_are_defined_where_the_channel_is_not(self) -> None:
        """Finite over the whole grid, against a channel that is NaN outside a pass."""
        result = run(reference_castelldefels(), degradations=DegradationLog())
        (series,) = result.series
        assert np.any(np.isnan(series.transmittance.values))
        for name in (
            "range_rate_km_s",
            "doppler_shift_hz",
            "doppler_rate_hz_s",
            "point_ahead_angle_rad",
        ):
            assert np.all(np.isfinite(getattr(series, name).values)), name

    def test_a_station_with_no_pass_still_has_the_series_and_has_no_extrema(self) -> None:
        """Zero passes is a shape here too: full series, an empty extremum column.

        Not zeros of length four, and not an exception. The satellite went over
        the sky; no pass cleared the mask, so there is no pass to take an
        extremum of.
        """
        result = run(no_pass_scenario(), degradations=DegradationLog())
        (series,) = result.series
        assert np.all(np.isfinite(series.doppler_shift_hz.values))
        assert result.passes.n_passes == 0
        assert result.passes.max_abs_doppler_hz.shape == (0,)
        assert result.passes.min_point_ahead_angle_rad.shape == (0,)

    def test_the_peak_doppler_of_a_pass_is_at_its_edges_and_not_its_culmination(self) -> None:
        """Which is why an end-of-pass Doppler problem is a thing at all.

        At culmination the satellite is moving across the line of sight, so the
        range-rate — and with it the shift — passes through zero. The extremes
        are at the horizon, where the elevation is lowest and the link is worst:
        the receiver has to work hardest exactly where it has least signal.
        """
        simulation = simulate(reference_castelldefels(), degradations=DegradationLog())
        station = simulation.stations[0]
        doppler = np.asarray(station.acquisition.doppler_shift_hz)
        table = station.table
        for index in range(table.n_passes):
            first = int(table.first_index[index])
            last = int(table.last_index[index])
            culmination = int(
                np.argmin(np.abs(np.asarray(table.grid.t_s) - table.culmination_s[index]))
            )
            edge = max(abs(doppler[first]), abs(doppler[last]))
            assert abs(doppler[culmination]) < edge

    def test_the_extrema_are_bounds_and_the_grid_says_how_tight(self) -> None:
        """A pass begins between samples, so a sampled peak is a lower bound.

        Refining the grid can only raise the reported maximum, never lower it,
        and on this link ten times finer sampling moves it by less than
        0.1 % — which is the measurement that licenses quoting the 1 s number
        as a requirement at all.
        """
        coarse = run(reference_castelldefels(), degradations=DegradationLog())
        fine = run(
            apply_point(reference_castelldefels(), {"time.step_s": 0.1}),
            degradations=DegradationLog(),
        )
        peak_coarse = np.asarray(coarse.passes.max_abs_doppler_hz)
        peak_fine = np.asarray(fine.passes.max_abs_doppler_hz)
        assert peak_fine.shape == peak_coarse.shape
        assert np.all(peak_fine >= peak_coarse - 1.0)
        assert np.all((peak_fine - peak_coarse) / peak_fine < 1e-3)


class TestTheDayAxis:
    def test_every_station_lands_on_one_day_axis(self) -> None:
        result = run(three_stations(), degradations=DegradationLog())
        assert result.daily.day_number.size >= 1
        assert result.daily.pass_count.sum() == result.passes.n_passes

    def test_a_day_that_is_not_on_the_axis_is_refused(self) -> None:
        """The guard behind ``_onto_days``, which no scenario should ever trip.

        It exists because the day axis is built by one stage and indexed by
        another: if they ever disagreed, ``np.searchsorted`` would silently put
        a day's bits on the neighbouring day rather than raise, and the daily
        table would be wrong by exactly one row with nothing to show for it.
        """
        days = np.array([2_460_677, 2_460_678], dtype=np.int64)
        with pytest.raises(DomainError, match="not all on the result's day axis"):
            _onto_days(days, np.array([2_460_999], dtype=np.int64), np.array([1.0]))

    def test_a_day_past_the_end_of_the_axis_is_refused_too(self) -> None:
        days = np.array([2_460_677], dtype=np.int64)
        with pytest.raises(DomainError, match="not all on the result's day axis"):
            _onto_days(days, np.array([2_460_678], dtype=np.int64), np.array([1.0]))

    def test_an_empty_day_list_is_not_an_error(self) -> None:
        days = np.array([2_460_677], dtype=np.int64)
        out = _onto_days(days, np.zeros(0, dtype=np.int64), np.zeros(0))
        assert out.tolist() == [0.0]


class TestTheDailySecurityClaim:
    def test_the_day_composes_the_blocks_it_concatenated(
        self, reference_result: SimulationResult
    ) -> None:
        assert reference_result.daily.composed_correctness is not None
        assert reference_result.daily.composed_secrecy is not None
        assert reference_result.daily.composed_correctness > 0.0

    def test_turning_composition_off_says_what_is_being_left_unsaid(self) -> None:
        """A day of several blocks is secure at the union bound whether or not it says so.

        ``compose_daily: false`` is allowed, because a reader may want the
        per-block numbers alone. What is not allowed is leaving the field empty
        with no explanation, which reads as "the question was not asked".
        """
        base = reference_castelldefels()
        scenario = base.model_copy(
            update={
                "security": SecuritySpec(**{**base.security.model_dump(), "compose_daily": False})
            }
        )
        log = DegradationLog()
        result = run(scenario, degradations=log)
        assert result.daily.composed_correctness is None
        (entry,) = [e for e in log if e.code == "engine.daily-not-composed"]
        assert entry.severity is Severity.WARNING
        assert entry.details["blocks"] == int(result.daily.pass_count.max())

    def test_a_day_with_no_pass_composes_nothing_and_says_nothing(self) -> None:
        log = DegradationLog()
        result = run(no_pass_scenario(), degradations=log)
        assert result.daily.composed_correctness is None
        assert [e for e in log if e.code == "engine.daily-not-composed"] == []


class TestTheEnsembleStage:
    def test_the_seed_is_recorded_and_the_ensemble_reproduces(self) -> None:
        scenario = with_monte_carlo(seed=7)
        one = run(scenario, degradations=DegradationLog())
        two = run(scenario, degradations=DegradationLog())
        assert one.provenance.seed == 7
        assert one.monte_carlo is not None
        assert two.monte_carlo is not None
        np.testing.assert_array_equal(one.monte_carlo.quantile_bits, two.monte_carlo.quantile_bits)

    def test_a_drawn_seed_is_recorded_so_the_run_can_be_replayed(self) -> None:
        result = run(with_monte_carlo(seed=None), degradations=DegradationLog())
        assert result.provenance.seed is not None
        replayed = run(with_monte_carlo(seed=result.provenance.seed), degradations=DegradationLog())
        assert result.monte_carlo is not None
        assert replayed.monte_carlo is not None
        np.testing.assert_array_equal(
            replayed.monte_carlo.quantile_bits, result.monte_carlo.quantile_bits
        )

    def test_the_per_day_quantiles_go_into_the_log_because_the_schema_has_no_field(self) -> None:
        """Quantiles of a day are not the sum of the passes' quantiles (ADR 0012 §8).

        The schema keeps per-*pass* quantiles, so the per-day ones cannot be
        rebuilt from the result; recording them in the log is the alternative to
        either dropping them or adding a field that invites the wrong sum.
        """
        log = DegradationLog()
        run(with_monte_carlo(seed=7), degradations=log)
        (entry,) = [e for e in log if e.code == "engine.monte-carlo-daily"]
        assert entry.severity is Severity.INFO

    def test_a_given_source_overrides_the_scenarios_seed(self) -> None:
        scenario = with_monte_carlo(seed=7)
        result = run(
            scenario, random_source=RandomSource.from_seed(4242), degradations=DegradationLog()
        )
        assert result.provenance.seed == 4242

    def test_a_station_with_no_pass_contributes_no_ensemble_and_no_zeros(self) -> None:
        """An ensemble of nothing is skipped, not padded with zeros.

        A column of zeros in ``quantile_bits`` would read as "the ensemble says
        this pass yields no key at any quantile", which is a result; what
        happened is that there was no pass to draw fading for. The pass axis of
        the Monte Carlo table therefore holds exactly the passes that exist.
        """
        scenario = with_monte_carlo(no_pass_scenario(), seed=7)
        log = DegradationLog()
        result = run(scenario, degradations=log)
        assert result.passes.n_passes == 0
        assert result.monte_carlo is not None
        assert result.monte_carlo.quantile_bits.shape[1] == 0
        assert [e for e in log if e.code == "engine.monte-carlo-daily"] == []

    def test_each_station_of_an_ensemble_draws_from_its_own_child(self) -> None:
        """Otherwise two stations would share one stream, and their fading would correlate.

        Two ground stations hundreds of kilometres apart see independent
        turbulence; sharing a generator would make their ensembles march in step
        and the multi-station totals too smooth.
        """
        result = run(with_monte_carlo(three_stations(), seed=7), degradations=DegradationLog())
        assert result.monte_carlo is not None
        assert result.monte_carlo.quantile_bits.shape[1] == result.passes.n_passes


class TestTheMultiStationStage:
    @pytest.fixture(scope="module")
    def aggregated(self) -> SimulationResult:
        return run(
            three_stations().model_copy(
                update={"multi_station": MultiStationSpec(policy="best_available")}
            ),
            degradations=DegradationLog(),
        )

    def test_the_table_has_one_row_per_station_and_one_column_per_day(
        self, aggregated: SimulationResult
    ) -> None:
        assert aggregated.multi_station is not None
        table = aggregated.multi_station
        assert table.bits_per_station_day.shape == (3, aggregated.daily.day_number.size)
        assert table.station_names == aggregated.scenario.station_names

    def test_a_station_with_no_selected_pass_holds_zero_and_not_a_gap(
        self, aggregated: SimulationResult
    ) -> None:
        """The two tables share one day axis, which is what makes them addable."""
        assert aggregated.multi_station is not None
        assert np.all(aggregated.multi_station.bits_per_station_day >= 0.0)
        assert int(aggregated.multi_station.scheduled_pass_count.sum()) <= (
            aggregated.passes.n_passes
        )

    def test_the_totals_that_have_no_schema_field_are_in_the_log(
        self, aggregated: SimulationResult
    ) -> None:
        codes = [str(w["code"]) for w in aggregated.warnings]
        assert "engine.multi-station-totals" in codes

    def test_cloud_fractions_weight_the_selection_and_the_joint_law_is_recorded(self) -> None:
        scenario = three_stations(cloud_fraction=0.3).model_copy(
            update={
                "multi_station": MultiStationSpec(
                    policy="best_available", cloud_decorrelation_length_km=500.0
                )
            }
        )
        log = DegradationLog()
        result = run(scenario, degradations=log)
        assert result.multi_station is not None
        (entry,) = [e for e in log if e.code == "engine.joint-cloud-free-probability"]
        assert entry.severity is Severity.INFO
        # Two bounds on the same probability, and the site-diversity question is
        # which of them the weather is nearer: independent stations give the
        # higher joint cloud-free probability, perfectly correlated ones the lower.
        assert entry.details["independent"] >= entry.details["comonotone"]


class TestTheRelayStage:
    @pytest.fixture(scope="module")
    def relayed(self) -> SimulationResult:
        return run(
            three_stations().model_copy(
                update={
                    "relay": RelaySpec(
                        pairs=[
                            ("castelldefels", "ogs_tenerife"),
                            ("castelldefels", "calar_alto"),
                        ]
                    )
                }
            ),
            degradations=DegradationLog(),
        )

    def test_one_row_per_pair_on_the_results_day_axis(self, relayed: SimulationResult) -> None:
        assert relayed.relay is not None
        assert relayed.relay.delivered_bits_per_day.shape == (
            2,
            relayed.daily.day_number.size,
        )
        assert relayed.relay.pairs == (
            ("castelldefels", "ogs_tenerife"),
            ("castelldefels", "calar_alto"),
        )

    def test_the_pair_latency_is_the_mean_age_of_a_delivered_bit(
        self, relayed: SimulationResult
    ) -> None:
        """The one reduction the stage makes, and why the weights are the bits.

        The relay carries a mean age per *delivery*; the schema holds one number
        per pair. Weighting each delivery by the bits it carried is what makes
        the pair's number the average over bits rather than over deliveries — a
        delivery of ten bits and one of a million would otherwise count the same.
        """
        assert relayed.relay is not None
        delivered = relayed.relay.delivered_bits_per_day.sum(axis=1)
        for bits, latency in zip(delivered, relayed.relay.mean_latency_s, strict=True):
            if bits > 0.0:
                assert np.isfinite(latency)
                assert latency > 0.0

    def test_a_pair_that_delivered_nothing_gets_nan_and_not_zero(self) -> None:
        """Zero would claim instant delivery of key that was never delivered."""
        never = three_stations().model_copy(
            update={
                "passes": no_pass_scenario().passes,
                "relay": RelaySpec(pairs=[("castelldefels", "ogs_tenerife")]),
            }
        )
        result = run(never, degradations=DegradationLog())
        assert result.relay is not None
        assert np.all(np.isnan(result.relay.mean_latency_s))
        assert np.all(result.relay.delivered_bits_per_day == 0.0)


@pytest.mark.slow
class TestWorkersDoNotChangeTheRun:
    def test_three_stations_across_two_processes_give_one_process_numbers(self) -> None:
        scenario = three_stations()
        one = run(scenario, workers=1, degradations=DegradationLog())
        many = run(scenario, workers=2, degradations=DegradationLog())

        one_manifest, one_arrays = one.to_manifest_and_arrays()
        many_manifest, many_arrays = many.to_manifest_and_arrays()
        assert [w["code"] for w in one_manifest["warnings"]] == [
            w["code"] for w in many_manifest["warnings"]
        ]
        for name, array in one_arrays.items():
            floating = np.issubdtype(array.dtype, np.floating)
            assert np.array_equal(array, many_arrays[name], equal_nan=floating), name

    def test_the_warnings_are_in_station_order_and_not_in_completion_order(self) -> None:
        scenario = three_stations()
        log = DegradationLog()
        run(scenario, workers=3, degradations=log)
        reference = DegradationLog()
        run(scenario, workers=1, degradations=reference)
        assert [e.code for e in log] == [e.code for e in reference]


class TestTheTimingsCoverEveryStageThatRan:
    def test_every_recorded_stage_is_a_declared_one(
        self, reference_result: SimulationResult
    ) -> None:
        assert set(reference_result.timings.seconds) <= set(STAGES)

    def test_the_optional_stages_appear_only_when_asked_for(self) -> None:
        plain = run(reference_castelldefels(), degradations=DegradationLog())
        assert "multi_station" not in plain.timings.seconds
        assert "relay" not in plain.timings.seconds
        assert "monte_carlo" not in plain.timings.seconds

        full = run(
            with_monte_carlo(three_stations()).model_copy(
                update={
                    "multi_station": MultiStationSpec(policy="best_available"),
                    "relay": RelaySpec(pairs=[("castelldefels", "ogs_tenerife")]),
                }
            ),
            degradations=DegradationLog(),
        )
        assert {"monte_carlo", "multi_station", "relay"} <= set(full.timings.seconds)

    def test_a_per_station_stage_sums_the_stations_rather_than_splitting_the_rows(self) -> None:
        """One row per stage whatever the scenario, so the table's shape is fixed.

        ``channel[castelldefels]`` and ``channel[calar_alto]`` would make the
        table's *columns* depend on the scenario, which is exactly what a
        comparison between two runs cannot afford. The price is that with worker
        processes the number is worker seconds and not elapsed seconds.
        """
        one = run(reference_castelldefels(), degradations=DegradationLog())
        three = run(three_stations(), degradations=DegradationLog())
        assert set(three.timings.seconds) == set(one.timings.seconds)
        assert three.timings.seconds["channel"] > 0.0


class TestSimulateReturnsThePhysicsBehindTheResult:
    def test_the_objects_a_hand_wired_comparison_needs(self) -> None:
        simulation = simulate(reference_castelldefels(), degradations=DegradationLog())
        assert simulation.trajectory.r_km.shape[0] == 1
        (station,) = simulation.stations
        assert station.name == "castelldefels"
        assert station.loss is not None
        assert station.noise is not None
        assert station.finite.key_bits.size == simulation.result.passes.n_passes
        assert simulation.multi_station is None
        assert simulation.joint_cloud_free is None
        assert simulation.relays == ()

    def test_the_result_of_simulate_is_the_result_of_run(self) -> None:
        """``run`` is ``simulate`` plus the cache, so the numbers must be identical.

        Two things are allowed to differ, and both are records of *when* rather
        than of *what*: the per-stage seconds, which are wall-clock measurements
        of two separate executions, and the provenance's ``created_utc``.
        """
        through_simulate = simulate(reference_castelldefels(), degradations=DegradationLog()).result
        through_run = run(reference_castelldefels(), degradations=DegradationLog())
        one, one_arrays = through_simulate.to_manifest_and_arrays()
        two, two_arrays = through_run.to_manifest_and_arrays()
        for manifest in (one, two):
            del manifest["timings"]
            del manifest["provenance"]["created_utc"]
        assert one == two
        for name, array in one_arrays.items():
            floating = np.issubdtype(array.dtype, np.floating)
            assert np.array_equal(array, two_arrays[name], equal_nan=floating), name
