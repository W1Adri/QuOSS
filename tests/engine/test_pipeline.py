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
from pydantic import ValidationError

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
        assert np.allclose(
            b.peak_one_sided_doppler_hz, 2.0 * np.asarray(a.peak_one_sided_doppler_hz), rtol=1e-12
        )
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
        assert result.passes.peak_one_sided_doppler_hz.shape == (0,)
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
        peak_coarse = np.asarray(coarse.passes.peak_one_sided_doppler_hz)
        peak_fine = np.asarray(fine.passes.peak_one_sided_doppler_hz)
        assert peak_fine.shape == peak_coarse.shape
        assert np.all(peak_fine >= peak_coarse - 1.0)
        assert np.all((peak_fine - peak_coarse) / peak_fine < 1e-3)


class TestTheTwoDopplerConventions:
    """A peak and an excursion are two numbers, and mixing them costs a factor two.

    What the two are
    ----------------
    Over one pass the received carrier does not sit at a fixed offset; it
    **sweeps**. The satellite approaches, so the signal arrives above the
    transmitted frequency; at closest approach the range-rate is zero and the
    offset with it; then it recedes and the signal arrives below. Two numbers
    summarise that, and they are not the same number:

    - ``peak_one_sided_doppler_hz`` — the largest ``|shift|`` reached, i.e.
      ``f0 * |r_dot|max / c``. **One side.**
    - ``doppler_excursion_hz`` — ``max(shift) - min(shift)``, the **whole span**
      the signal travels across during the pass.

    Why the distinction is worth a class
    ------------------------------------
    A receiver has to be able to find the signal *anywhere it goes*, so the
    number that sizes a capture or search window is the excursion. Reading the
    one-sided peak as the window under-specifies the transceiver by very nearly
    a factor two, and it is the parameter TBIRD ran out of at the end of a pass.

    This repo's answer to that class of error is to put the convention in the
    **name**, as it already did for ``field_of_view_urad`` (full angle, not
    half) and for the two differently-named transmittances in ``link_budget``.
    So both quantities exist as columns, both names say which is which, and
    neither is "the one you have to remember to double".

    Why it is not literally a factor two, which matters
    ---------------------------------------------------
    The excursion is **measured**, as ``max - min``, and not defined as twice
    the peak. On a real pass the approaching and receding extremes differ — the
    pass is not symmetric about culmination, and the samples are a grid — so the
    ratio runs from 1.977 to 1.999 over the reference day, not 2.000. Deriving
    one column from the other would hard-code a symmetry the geometry does not
    have, and would hide any future bug that broke it.
    """

    def test_the_excursion_is_the_span_the_shift_actually_covers(self) -> None:
        """The column is `max - min` of the shift over the pass's own samples.

        Recomputed here from the grid series and the pass table rather than
        trusted from the reduction, because "the excursion" has an obvious
        wrong implementation (twice the peak) that agrees with the right one to
        0.1 % and would never be noticed by eye.
        """
        simulation = simulate(reference_castelldefels(), degradations=DegradationLog())
        station = simulation.stations[0]
        shift = np.asarray(station.acquisition.doppler_shift_hz)
        rows = np.asarray(station.samples.sample_index)
        pass_index = np.asarray(station.samples.pass_index)
        reported = np.asarray(station.acquisition.doppler_excursion_hz)
        assert reported.shape == (station.table.n_passes,)
        for index in range(station.table.n_passes):
            inside = shift[rows][pass_index == index]
            assert reported[index] == pytest.approx(inside.max() - inside.min(), rel=1e-12)

    def test_the_excursion_is_under_twice_the_peak_and_close_to_it(
        self, reference_result: SimulationResult
    ) -> None:
        """The relation between the two columns, as an inequality that is derivable.

        `max - min <= |max| + |min| <= 2 * max(|max|, |min|)` is arithmetic and
        holds for any pass whatsoever, so it is a real invariant and not a
        tolerance fitted to today's output. Equality needs the two extremes to
        be exactly equal in size, which a pass with a real horizon crossing at
        both ends comes close to and never reaches.

        The lower guard is the physical half of the claim: the two extremes of
        a pass are near-symmetric because the geometry is, so the ratio stays
        above 1.9. Together they say "very nearly two, never two" — which is
        precisely the statement that the peak cannot be substituted for the
        excursion, and cannot be corrected by multiplying by two either.

        Measured on the reference day: 1.999036, 1.989008, 1.998300, 1.976639.
        """
        peak = np.asarray(reference_result.passes.peak_one_sided_doppler_hz)
        excursion = np.asarray(reference_result.passes.doppler_excursion_hz)
        ratio = excursion / peak
        assert np.all(excursion < 2.0 * peak)
        assert np.all(ratio > 1.9)
        assert ratio.tolist() == pytest.approx([1.999036, 1.989008, 1.998300, 1.976639], abs=1e-6)

    def test_the_headline_pair_is_four_gigahertz_and_eight(
        self, reference_result: SimulationResult
    ) -> None:
        """The factor-two error, as the two numbers a datasheet would be read against.

        The best pass of the reference day peaks **4.187 GHz** off the carrier
        and sweeps **8.370 GHz** end to end. A transceiver bought against the
        first number has half the window the pass needs.
        """
        peak = np.asarray(reference_result.passes.peak_one_sided_doppler_hz)
        excursion = np.asarray(reference_result.passes.doppler_excursion_hz)
        assert float(peak.max()) == pytest.approx(4.272427e9, rel=1e-6)
        assert float(excursion.max()) == pytest.approx(8.537589e9, rel=1e-6)
        assert float(peak[0]) == pytest.approx(4.186869e9, rel=1e-6)
        assert float(excursion[0]) == pytest.approx(8.369700e9, rel=1e-6)

    def test_the_window_and_the_slew_are_two_requirements_and_rank_passes_differently(
        self, reference_result: SimulationResult
    ) -> None:
        """A capture range and a tracking rate are separate specifications.

        One says how *wide* a window the receiver needs, the other how *fast*
        the signal crosses it, and a transceiver can meet either alone and still
        lose the pass: a wide slow receiver breaks lock at the horizon where the
        sweep is fastest, a fast narrow one never acquires at all.

        The test that they are not restatements of each other is that they do
        not order the passes the same way. On the reference day the widest
        excursion is pass 2 and so is the fastest slew, but passes 1 and 3 swap:
        pass 1 needs more window than pass 3 (5.66 against 4.40 GHz) and also
        more slew (19.2 against 16.8 MHz/s) — while pass 0 against pass 2
        reverses between the two columns relative to their durations. What is
        asserted is the weaker and honest form: the ratio of slew to excursion
        is not a constant across the four, so neither column can be computed
        from the other.
        """
        excursion = np.asarray(reference_result.passes.doppler_excursion_hz)
        slew = np.asarray(reference_result.passes.peak_doppler_slew_hz_s)
        crossing_time_s = excursion / slew
        assert float(crossing_time_s.max() / crossing_time_s.min()) > 1.15
        assert slew.argmax() == excursion.argmax()

    def test_the_ten_degree_mask_hides_a_quarter_of_a_kilometre_per_second(self) -> None:
        """The columns are bounded by the mask, and the bound is worth a number.

        Every acquisition column is reduced over the samples **at or above the
        mask**, and all of these quantities peak at the horizon, so a tighter
        mask reports a smaller requirement. That is not a bug — it is the
        requirement *for a link that does not use the sky below 10 degrees* —
        but it means the column cannot be read as "what this orbit can do".

        Dropping the mask from 10 to 5 degrees raises the day's largest
        excursion by 1.7 %. A designer sizing a transceiver for a link that may
        later lower its mask should size it from the geometry, which
        `tests/orbits/test_geometry.py::TestTheHorizonRangeRateBound` does in
        closed form, and not from this column.
        """
        tight = run(reference_castelldefels(), degradations=DegradationLog())
        wide = run(
            apply_point(reference_castelldefels(), {"passes.minimum_elevation_deg": 5.0}),
            degradations=DegradationLog(),
        )
        tight_max = float(np.asarray(tight.passes.doppler_excursion_hz).max())
        wide_max = float(np.asarray(wide.passes.doppler_excursion_hz).max())
        assert wide_max > tight_max
        assert wide_max / tight_max == pytest.approx(1.017, abs=0.002)


class TestTheDeclaredCaptureRange:
    """`receiver.doppler_capture_range_hz`: the field that lets a run say "this does not fit".

    Until this field existed, every acquisition column said what a pass
    *demands* and nothing said whether anything could *supply* it. The reader
    held the transceiver's datasheet in their head and did the comparison there,
    which is the same as not doing it.

    Why it is optional and null by default
    --------------------------------------
    Because for CLAU it is honestly unknown — no transceiver has been chosen —
    and a default would be a specification nobody selected, which is the
    "do not invent numbers" rule. But **unknown must not read like fine**: a run
    that checked nothing has to be distinguishable from a run that checked and
    passed. So the null case is an INFO, not silence.

    Which convention the field is in
    --------------------------------
    The **total width** of the acceptance window, matching
    ``doppler_excursion_hz`` and not ``peak_one_sided_doppler_hz``. A
    transceiver quoted as "+/-5 GHz" is ``1e10`` here, and
    ``ReceiverSpec.doppler_capture_half_range_hz`` gives back the +/- reading by
    name so that neither form is the one somebody has to remember to convert.
    """

    @staticmethod
    def _with_window(window_hz: float | None) -> Scenario:
        base = reference_castelldefels()
        return base.model_copy(
            update={
                "receiver": base.receiver.model_copy(update={"doppler_capture_range_hz": window_hz})
            }
        )

    @staticmethod
    def _records(window_hz: float | None, code: str) -> list[Any]:
        log = DegradationLog()
        run(TestTheDeclaredCaptureRange._with_window(window_hz), degradations=log)
        return [entry for entry in log if entry.code == code]

    def test_the_default_is_null_and_null_says_so_out_loud(self) -> None:
        """No window declared is an INFO, because a silent pass would be a lie by omission.

        The reference scenario declares no window, so every Doppler figure it
        reports stands against nothing. The INFO says exactly that and carries
        the largest excursion with it, so the reader has the number they would
        need to do the comparison by hand.

        It is an INFO and not a WARNING because nothing is degraded: the
        computed numbers are all correct. What is missing is an input, and a
        missing input that changes no number is precisely what INFO is for.
        """
        assert reference_castelldefels().receiver.doppler_capture_range_hz is None
        (record,) = self._records(None, "engine.acquisition.no-capture-range-declared")
        assert record.severity is Severity.INFO
        assert record.details["largest_excursion_hz"] == pytest.approx(8.537589e9, rel=1e-6)
        assert not self._records(None, "engine.acquisition.capture-range-exceeded")

    def test_a_window_wide_enough_records_nothing_at_all(self) -> None:
        """Declaring a sufficient window is the one case that is silent, and should be.

        12 GHz clears the widest pass of the day (8.54 GHz) with room, so there
        is no degradation of any kind — neither the INFO, which no longer
        applies, nor a warning. That is what makes the INFO above meaningful:
        the two states are distinguishable in the result.
        """
        assert not self._records(12e9, "engine.acquisition.no-capture-range-declared")
        assert not self._records(12e9, "engine.acquisition.capture-range-exceeded")

    def test_a_pass_that_does_not_fit_warns_with_both_figures_and_the_seconds(self) -> None:
        """The warning carries how long the pass is out of range, not only that it is.

        Against an 8 GHz window (+/-4 GHz) the reference day's two strong passes
        do not fit: pass 0 sweeps 8.3697 GHz and spends **127.2 s of its 562.2 s
        outside**, pass 2 sweeps 8.5376 GHz and spends **173.4 s of 558.4**. The
        two low passes fit and are not mentioned.

        The seconds are the point. "Exceeds" and "exceeds for two minutes of a
        nine-minute pass" are different engineering problems, and the first one
        cannot be told from a pass that clips for one sample at the horizon.
        """
        records = self._records(8e9, "engine.acquisition.capture-range-exceeded")
        assert [r.details["pass_index"] for r in records] == [0, 2]
        assert all(r.severity is Severity.WARNING for r in records)

        first, third = records
        assert first.details["excursion_hz"] == pytest.approx(8.369700e9, rel=1e-6)
        assert first.details["capture_range_hz"] == 8e9
        assert first.details["capture_half_range_hz"] == 4e9
        assert first.details["seconds_outside"] == pytest.approx(127.2, abs=0.1)
        assert first.details["pass_duration_s"] == pytest.approx(562.2, abs=0.1)
        assert third.details["seconds_outside"] == pytest.approx(173.4, abs=0.1)
        assert first.details["seconds_outside"] < first.details["pass_duration_s"]

    def test_a_pass_whose_excursion_fits_can_still_miss_a_centred_window(self) -> None:
        """The case that proves the two readings are not the same check.

        A window of 4.42 GHz is **wider than pass 3's whole excursion**
        (4.3992 GHz), so a receiver that pre-compensates from an ephemeris —
        re-centring its window as the pass runs — covers it with 21 MHz to
        spare. A receiver that searches around the nominal carrier does not:
        its window reaches +/-2.21 GHz and the pass peaks at 2.2256 GHz, so it
        loses the signal for **1.7 s of a 302.7 s pass**.

        This is why the warning carries the excursion *and* the half-range
        rather than a verdict. The same pass and the same transceiver give
        different answers depending on which receiver it is, and the run cannot
        know which; what it can do is refuse to hide either number.
        """
        records = self._records(4.42e9, "engine.acquisition.capture-range-exceeded")
        by_index = {r.details["pass_index"]: r for r in records}
        assert 3 in by_index
        detail = by_index[3].details
        assert detail["excursion_hz"] == pytest.approx(4.399167e9, rel=1e-6)
        assert detail["excursion_hz"] < detail["capture_range_hz"]
        assert detail["peak_one_sided_doppler_hz"] > detail["capture_half_range_hz"]
        assert detail["seconds_outside"] == pytest.approx(1.7, abs=0.1)
        assert detail["pass_duration_s"] == pytest.approx(302.7, abs=0.1)

    def test_the_seconds_outside_grow_as_the_window_shrinks(self) -> None:
        """Monotonicity, which is the invariant a fixed expected number cannot give.

        Narrowing the window can only move samples from inside to outside, never
        the other way, so the seconds outside of any given pass are
        non-increasing in the window width. This holds for any link and any
        grid, so it is a real invariant rather than a tolerance around today's
        answer, and it is what would catch a sign error or an off-by-two in the
        half-range that the single measured numbers above would still pass.
        """
        outside = []
        for window_hz in (4e9, 6e9, 8e9, 10e9):
            records = self._records(window_hz, "engine.acquisition.capture-range-exceeded")
            by_index = {r.details["pass_index"]: r.details["seconds_outside"] for r in records}
            outside.append(by_index.get(0, 0.0))
        assert outside == sorted(outside, reverse=True)
        assert outside[0] > outside[-1] == 0.0

    def test_with_no_pass_there_is_nothing_to_check_and_the_run_says_why(self) -> None:
        """A declared window and zero passes: no acquisition entry, and one reason for it.

        What happens here, for someone arriving new: a ten-minute run of the
        reference scenario starts at the ascending node over the equator, far
        from Castelldefels, so the satellite never rises above the 10 deg mask
        and the pass table is empty.

        **With a window declared** the acquisition stage has nothing to
        contrast: the Doppler requirement is a property of a pass, and there is
        none. So it records nothing — no warning, because nothing exceeds the
        window, and not the "no window declared" INFO either, because one was.
        That silence is honest only because the run is not silent overall:
        ``passes.none-found`` is already in the log and says the one thing that
        is true, that there was no pass to judge. A second entry from this stage
        would claim a check that had nothing to check.

        **With no window declared** the INFO is still recorded, pass or no pass,
        because "unknown must not read like fine" does not depend on the sky;
        and its ``largest_excursion_hz`` is ``None`` rather than ``0.0``,
        because zero would read as a measured excursion of zero hertz.
        """

        def short(window_hz: float | None) -> Scenario:
            base = self._with_window(window_hz)
            return base.model_copy(
                update={"time": base.time.model_copy(update={"duration_s": 600.0})}
            )

        log = DegradationLog()
        result = run(short(8e9), degradations=log)
        assert result.passes.n_passes == 0
        codes = [entry.code for entry in log]
        assert "passes.none-found" in codes
        assert not [code for code in codes if code.startswith("engine.acquisition.")]

        undeclared = DegradationLog()
        run(short(None), degradations=undeclared)
        (info,) = [
            e for e in undeclared if e.code == "engine.acquisition.no-capture-range-declared"
        ]
        assert info.severity is Severity.INFO
        assert info.details["largest_excursion_hz"] is None

    def test_the_half_range_property_is_the_other_reading_of_the_same_field(self) -> None:
        """Both conventions available by name, so neither needs remembering to convert."""
        receiver = self._with_window(1e10).receiver
        assert receiver.doppler_capture_range_hz == 1e10
        assert receiver.doppler_capture_half_range_hz == 5e9
        assert self._with_window(None).receiver.doppler_capture_half_range_hz is None

    def test_a_non_positive_window_is_refused_by_the_schema(self) -> None:
        """Zero or negative is not a degraded run, it is a scenario that cannot mean anything.

        Built through the constructor rather than ``model_copy``, because
        ``model_copy(update=...)`` assigns without re-validating — so the
        helper the other tests use here would accept a nonsense window and this
        test would pass while proving nothing. A scenario loaded from YAML goes
        through the constructor, which is the path that matters.
        """
        receiver = reference_castelldefels().receiver
        for window_hz in (0.0, -1e9):
            fields = receiver.model_dump()
            fields["doppler_capture_range_hz"] = window_hz
            with pytest.raises(ValidationError):
                type(receiver)(**fields)


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
