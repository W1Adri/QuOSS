"""The engine against the same chain wired by hand, number for number.

What this file is for, for someone arriving new
-----------------------------------------------
`quoss.engine.pipeline.run` takes one `Scenario` — a validated description of a
simulation, read from a YAML file — and returns a `SimulationResult`. In
between it calls the physics functions of `quoss.orbits`, `quoss.channel`,
`quoss.qkd` and `quoss.system`, in order, and moves what they return into
containers.

Its whole claim is a **negative** one: *the engine computes nothing that a
person calling those functions by hand would not compute*. That claim is easy
to write in a docstring and easy to break in code — an orchestrator is exactly
the kind of module where a forgotten keyword, a default that differs from the
one the caller would have chosen, or a re-derived quantity slips in and nobody
notices, because every number it returns still looks reasonable.

So `tests/e2e/oracle.py` is the person calling the functions by hand: the same
calls, written out with the module constants, importing nothing from
`quoss.engine`. This file compares the two.

What "bit for bit" means here, and why it is not `approx`
---------------------------------------------------------
Every assertion of equality in this file is exact float equality (`==`, or
`np.array_equal`), not `pytest.approx`. That is deliberate, and it is a
different kind of claim from the one a physics test makes.

A physics test compares two *computations* of the same quantity — a closed form
against an integral, say — and they legitimately differ in the last digits, so
it needs a tolerance derived from the size of the effect. This file compares
**the same computation reached by two routes**. The same function, with the
same arguments, in the same order, returns the same IEEE-754 doubles; floating
point is deterministic. If the engine's number differs from the hand chain's by
one unit in the last place, the two routes are not the same computation, and a
tolerance would hide precisely the difference this file exists to find.

In the language of `tests/golden/README.md` this is a **V4 bridge**: it shows
the orchestration is faithful, and says nothing about whether the physics is
right. That is what V2 and V3 are for.

The discrepancy this file closes
--------------------------------
`StationSpec.altitude_m` is two things at once, and the scenario schema says so
in the field's own description: it is where the station *is* (it enters
`look_angles`, which needs the observer's position) and it is where the
turbulence profile *starts* (`station_height_m` of every turbulence function,
because layers of air below the telescope are not on the path).

The hand-built reference link of `tests/system/reference.py` — the fixture every
stage-3 number is measured on — passes Castelldefels' 30 m to the geometry and
leaves the turbulence at its default of 0 m. The engine wires the field. So on
the reference day the engine reports **433 442** finite bits where the stage-3
tests quote **432 985**: 457 bits, 0.106 %.

Neither number is an arithmetic error, and this file proves that by reproducing
both, to the bit, from the *same* hand chain with only `station_height_m`
changed (`TestTheFourHundredAndFiftySevenBits`). They are two different links.
The engine's is the one a scenario describes, because in a scenario
`altitude_m` has one meaning; ignoring the field to match the older number
would be a silent degradation of a user input, which this project forbids.

Why the term is worth wiring, which is the half a 0.106 % makes easy to miss
---------------------------------------------------------------------------
At Castelldefels, 30 m above the sea, the term is a rounding. It is not a
rounding anywhere a telescope is actually put. Measured here, same satellite,
same day, same receiver, only the station moved (`test_what_the_term_is_worth_
at_a_station_that_is_actually_up_a_mountain`):

===============  ========  ==============  ==============  ========
station          altitude  turbulence 0 m  turbulence alt  change
===============  ========  ==============  ==============  ========
Castelldefels        30 m   432 985 bits    433 442 bits    +0.11 %
Calar Alto         2 168 m    56 925 bits     77 244 bits   +35.7 %
Teide OGS          2 400 m   562 697 bits    587 863 bits    +4.5 %
===============  ========  ==============  ==============  ========

and on Calar Alto's second pass alone, 9 817 bits against 19 724 — the term
**doubles** it. The reason is the shape of the atmosphere rather than anything
about the code: the Hufnagel-Valley profile puts most of the turbulence in the
first kilometre or two, so the vertical integral of ``C_n^2`` above 2 168 m is
9.8 times smaller than above the sea, against 1.26 times at 30 m. That is why
observatories are on mountains, and it is why the field cannot be quietly
dropped.

Classes
-------
TestTheEngineAddsNothing
    The reference scenario, stage by stage, against the hand chain.
TestTheOneTermThatIsNotACopy
    The single place the two differ, which is a shape and not a value.
TestTheFourHundredAndFiftySevenBits
    Both numbers reproduced from one hand chain, and what the term is worth.
TestTheEnsembleIsTheSameDraw
    The Monte Carlo stage: same seed, same stream, same quantiles.
TestTheAggregationAndTheRelayAddNothing
    Three stations, the scheduler and the trusted-node relay.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pytest

from quoss.channel.atmosphere import integrated_cn2_m13
from quoss.core.errors import DegradationLog
from quoss.engine.pipeline import Simulation, StationRun, simulate
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.models import (
    MonteCarloSpec,
    MultiStationSpec,
    RelaySpec,
    Scenario,
)
from quoss.system.multi_ogs import AggregationPolicy, aggregate_stations
from quoss.system.relay import trusted_node_relay

from .oracle import (
    REFERENCE_FINITE_BITS,
    REFERENCE_FINITE_DAY_BITS,
    STATIONS,
    HandLink,
    hand_link,
    hand_monte_carlo,
    station_set,
    station_spec,
)

CASTELLDEFELS_HEIGHT_M = STATIONS["castelldefels"][2]
"""30 m. The station's own altitude, which is what the engine wires."""

ENGINE_FINITE_BITS = (190_807.0, 0.0, 242_635.0, 0.0)
ENGINE_FINITE_DAY_BITS = 433_442.0
"""The reference day as the engine computes it, with the 30 m in the turbulence.

Measured here, and reproduced by the hand chain of `oracle.py` at the same
height. The stage-3 figures are `REFERENCE_FINITE_BITS` and
`REFERENCE_FINITE_DAY_BITS`, the same chain at 0 m.
"""

ENGINE_ASYMPTOTIC_DAY_BITS = 3_779_461.558061474
"""Full precision, because this file asserts exact equality and not a rounding."""

STAGE_THREE_ASYMPTOTIC_DAY_BITS = 3_776_680.752646787
"""The same, at 0 m: what `tests/system` quotes as 3.78 Mbit."""

MONTE_CARLO = MonteCarloSpec(
    realisations=16,
    seed=20_260_913,
    scintillation_correlation_time_s=2e-3,
    pointing_correlation_time_s=20e-3,
)
"""The reference seed and correlation times of `tests/system/reference_fading.py`.

Sixteen realisations rather than the two hundred that file draws: this test
asks whether the engine draws the *same* ensemble, not what the ensemble is
worth, and sixteen settles that as completely as two hundred for a fifth of
the time.
"""

MULTI_STATION_NAMES = ("castelldefels", "calar_alto", "tenerife_ogs")
"""The three stations of `tests/system/reference_stations.py`, in its order."""


def assert_identical(got: Any, expected: Any, what: str) -> None:
    """Assert two arrays are the same shape and the same doubles, NaN included.

    ``np.array_equal(..., equal_nan=True)`` and not ``assert_allclose``: see the
    module docstring on why a tolerance would defeat the purpose. The shape is
    checked separately so a broadcastable mismatch fails loudly rather than
    passing on a comparison numpy widened.
    """
    a, b = np.asarray(got), np.asarray(expected)
    assert a.shape == b.shape, f"{what}: shapes {a.shape} != {b.shape}"
    assert np.array_equal(a, b, equal_nan=True), f"{what}: values differ"


@pytest.fixture(scope="module")
def engine() -> Simulation:
    """Run the reference scenario through the engine, keeping the physics objects."""
    return simulate(reference_castelldefels(), degradations=DegradationLog())


@pytest.fixture(scope="module")
def station(engine: Simulation) -> StationRun:
    return engine.stations[0]


@pytest.fixture(scope="module")
def by_hand() -> HandLink:
    """Wire the same link by hand, call by call, at the station's own height."""
    return hand_link("castelldefels", station_height_m=CASTELLDEFELS_HEIGHT_M)


class TestTheEngineAddsNothing:
    """Stage by stage, the engine's arrays are the hand chain's arrays."""

    def test_the_geometry_is_the_hand_geometry(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        for field in ("elevation_rad", "azimuth_rad", "range_km"):
            assert_identical(
                getattr(station.angles, field), getattr(by_hand.angles, field), f"angles.{field}"
            )

    def test_the_pass_table_is_the_hand_pass_table(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        """Including the refined edges and culmination, which are found off the grid.

        `find_passes` does not report the first sample above the mask as the
        start of the pass: it interpolates the crossing between the two samples
        that straddle it, and fits a parabola through the three samples around
        the peak. Those are the numbers most likely to differ between two
        callers, because they are the ones a re-implementation would round.
        """
        for field in (
            "satellite_index",
            "first_index",
            "last_index",
            "start_s",
            "end_s",
            "culmination_s",
            "culmination_elevation_rad",
            "sampled_culmination_elevation_rad",
            "truncated_start",
            "truncated_end",
            "day_number",
        ):
            assert_identical(
                getattr(station.table, field), getattr(by_hand.table, field), f"table.{field}"
            )
        assert station.table.minimum_elevation_rad == by_hand.table.minimum_elevation_rad

    def test_the_samples_are_the_hand_samples(self, station: StationRun, by_hand: HandLink) -> None:
        for field in ("satellite_index", "sample_index", "pass_index", "dwell_s"):
            assert_identical(
                getattr(station.samples, field), getattr(by_hand.samples, field), f"samples.{field}"
            )

    def test_every_term_of_the_loss_budget_is_the_hand_term(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        """Term by term, not only the total: a total can agree by cancellation."""
        assert station.loss is not None
        for field in (
            "geometric_db",
            "atmospheric_db",
            "pointing_db",
            "scintillation_db",
            "fade_db",
            "total_db",
            "transmittance",
            "channel_transmittance",
            "effective_outage_probability",
        ):
            assert_identical(
                getattr(station.loss, field), getattr(by_hand.loss, field), f"loss.{field}"
            )
        assert station.loss.truncation_db == by_hand.loss.truncation_db
        assert station.loss.receiver_chain_db == by_hand.loss.receiver_chain_db
        assert station.loss.static_db == by_hand.loss.static_db
        assert station.loss.fade_combination is by_hand.loss.fade_combination

    def test_the_noise_the_protocol_reads_is_the_hand_noise(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        """At `LinkConditions`, which is the only form the protocol ever sees.

        The budget objects themselves differ in one field's *shape*; that is
        `TestTheOneTermThatIsNotACopy`, and it is gone by the time the counts
        reach here, because `LinkConditions` broadcasts them against the
        transmittance.
        """
        assert station.noise is not None
        assert station.conditions is not None
        for field in ("background_per_gate", "dark_per_gate"):
            assert_identical(
                getattr(station.noise, field), getattr(by_hand.noise, field), f"noise.{field}"
            )
        assert_identical(
            station.conditions.noise_counts_per_gate,
            by_hand.conditions.noise_counts_per_gate,
            "conditions.noise_counts_per_gate",
        )
        assert_identical(
            station.conditions.transmittance,
            by_hand.conditions.transmittance,
            "conditions.transmittance",
        )
        assert_identical(
            station.conditions.misalignment_error,
            by_hand.conditions.misalignment_error,
            "conditions.misalignment_error",
        )
        assert station.conditions.pulse_rate_hz == by_hand.conditions.pulse_rate_hz
        assert station.conditions.gate_duration_s == by_hand.conditions.gate_duration_s

    def test_the_finite_key_is_the_hand_finite_key(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        for field in ("key_bits", "pulses", "seconds"):
            assert_identical(
                getattr(station.finite, field), getattr(by_hand.finite, field), f"finite.{field}"
            )
        assert tuple(np.asarray(station.finite.key_bits).tolist()) == ENGINE_FINITE_BITS

    def test_the_finite_bound_is_the_hand_bound_column_by_column(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        """The key length is one number out of a bound with a dozen intermediates.

        Two chains can agree on the length and disagree on the phase-error rate
        that produced it — the bound is a difference of large terms — so the
        columns are compared as well as the answer.
        """
        assert station.finite.finite is not None
        assert by_hand.finite.finite is not None
        for field in station.finite.finite._ARRAYS:
            assert_identical(
                getattr(station.finite.finite, field),
                getattr(by_hand.finite.finite, field),
                f"finite.finite.{field}",
            )

    def test_the_asymptotic_key_is_the_hand_asymptotic_key(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        assert_identical(
            station.asymptotic.key_bits, by_hand.asymptotic.key_bits, "asymptotic.key_bits"
        )

    def test_the_daily_table_sums_the_passes_and_nothing_else(self, engine: Simulation) -> None:
        daily = engine.result.daily
        assert daily.day_number.tolist() == [2_460_677]
        assert float(np.asarray(daily.finite_bits)[0]) == ENGINE_FINITE_DAY_BITS
        assert float(np.asarray(daily.asymptotic_bits)[0]) == ENGINE_ASYMPTOTIC_DAY_BITS
        assert float(np.asarray(daily.finite_bits)[0]) == float(
            np.asarray(engine.result.passes.finite_bits).sum()
        )

    def test_the_series_inside_a_pass_are_the_budget_and_nan_outside(
        self, engine: Simulation, station: StationRun, by_hand: HandLink
    ) -> None:
        """The series are the budget scattered onto the grid, not a second evaluation."""
        (series,) = engine.result.series
        rows = np.asarray(station.samples.sample_index)
        for series_field, budget in (
            ("transmittance", np.asarray(by_hand.loss.transmittance)),
            ("loss_total_db", np.asarray(by_hand.loss.total_db)),
        ):
            values = np.asarray(getattr(series, series_field).values)
            assert_identical(values[rows], budget, f"series.{series_field} inside a pass")
            outside = np.ones(values.size, dtype=np.bool_)
            outside[rows] = False
            assert np.all(np.isnan(values[outside])), f"series.{series_field} outside a pass"

    def test_every_warning_in_the_result_was_raised_by_a_physics_module(
        self, engine: Simulation
    ) -> None:
        """The engine forwards what the physics said and namespaces anything of its own.

        A degradation entry carries a ``code`` whose prefix names the module
        that raised it (``turbulence.``, ``finite-key.``, ``key_volume.``), and
        the pipeline's own entries are all under ``engine.``. So "the engine
        adds nothing" is checkable on the log as well as on the numbers: on the
        reference run there is not one ``engine.`` entry, because nothing
        happened that only the orchestration could know about.

        The codes are listed rather than counted loosely, because a warning that
        stops being raised is exactly as much of a change as a number that
        moves — the weak-fluctuation limit below is the one the reference link
        is known to exceed (`notes/LAST_CHANGES.md` §18), and losing it would
        turn a declared limitation into a silent one.
        """
        codes = Counter(str(entry["code"]) for entry in engine.result.warnings)
        assert codes == Counter(
            {
                "turbulence.weak-fluctuation-limit-exceeded": 1,
                "finite-key.vacuum-events-uncertified": 2,
                "finite-key.phase-error-capped": 1,
                "finite-key.block-too-short": 1,
                "key_volume.passes-without-key": 1,
                "key_volume.asymptotic-upper-bound": 1,
                "key_volume.day-composes-blocks": 1,
                "key_volume.day-has-no-security-claim": 1,
            }
        )
        assert not [code for code in codes if code.startswith("engine.")]


class TestTheOneTermThatIsNotACopy:
    """The single difference between the two chains, which is a shape, not a value.

    `_channel` hands `downlink_noise_budget` a `signal_counts_per_gate` — the
    mean detected signal per gate, which an afterpulse needs because an
    afterpulse follows a click. The hand chain omits it. With the reference
    receiver's `afterpulse_probability = 0` ("no after-pulsing effect", Ntanos
    et al. §4.1) the term is exactly zero either way, so the two chains agree on
    every number; what they do not agree on is that the engine's zero is an
    array of 1 800 of them and the hand chain's is one scalar.

    This is asserted rather than smoothed over because it is the shape of a
    genuine coupling: the moment a scenario declares a non-zero afterpulse
    probability, the engine's noise stops being constant across a pass and the
    hand chain would be wrong. The identity holds *because* the term is zero,
    not because the two calls are the same call.
    """

    def test_the_afterpulse_term_is_identically_zero(self, station: StationRun) -> None:
        assert station.noise is not None
        assert np.all(np.asarray(station.noise.afterpulse_per_gate) == 0.0)

    def test_the_engine_carries_it_per_sample_and_the_hand_chain_as_a_scalar(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        assert station.noise is not None
        assert station.loss is not None
        assert np.asarray(station.noise.afterpulse_per_gate).shape == (
            np.asarray(station.loss.transmittance).size,
        )
        assert np.asarray(by_hand.noise.afterpulse_per_gate).shape == ()

    def test_and_the_totals_are_therefore_the_same_number_twice(
        self, station: StationRun, by_hand: HandLink
    ) -> None:
        assert station.noise is not None
        engine_total = np.unique(np.asarray(station.noise.total_per_gate))
        assert engine_total.size == 1
        assert float(engine_total[0]) == float(np.asarray(by_hand.noise.total_per_gate))


class TestTheFourHundredAndFiftySevenBits:
    """Both published day figures, reproduced from one hand chain, one argument apart."""

    @pytest.fixture(scope="module")
    def at_sea_level(self) -> HandLink:
        return hand_link("castelldefels", station_height_m=0.0)

    def test_the_stage_three_figure_is_the_hand_chain_at_sea_level(
        self, at_sea_level: HandLink
    ) -> None:
        bits = np.asarray(at_sea_level.finite.key_bits)
        assert tuple(bits.tolist()) == REFERENCE_FINITE_BITS
        assert float(bits.sum()) == REFERENCE_FINITE_DAY_BITS
        assert (
            float(np.asarray(at_sea_level.asymptotic.key_bits).sum())
            == STAGE_THREE_ASYMPTOTIC_DAY_BITS
        )

    def test_the_engine_figure_is_the_hand_chain_at_the_stations_own_height(
        self, station: StationRun
    ) -> None:
        bits = np.asarray(station.finite.key_bits)
        assert tuple(bits.tolist()) == ENGINE_FINITE_BITS
        assert float(bits.sum()) == ENGINE_FINITE_DAY_BITS

    def test_the_two_links_see_the_same_passes(
        self, at_sea_level: HandLink, by_hand: HandLink
    ) -> None:
        """So the difference cannot be geometry: the term enters through the channel alone.

        `station_height_m` is not the station's position — that is
        `station_altitude_km`, and both links pass the same 30 m to
        `look_angles`. If the two differed in when the satellite rose, the bit
        difference below would be a different pass set and not a different
        channel.
        """
        for field in ("start_s", "end_s", "culmination_s", "culmination_elevation_rad"):
            assert_identical(
                getattr(at_sea_level.table, field),
                getattr(by_hand.table, field),
                f"table.{field}",
            )
        assert_identical(
            at_sea_level.angles.elevation_rad, by_hand.angles.elevation_rad, "angles.elevation_rad"
        )

    def test_only_the_scintillation_term_of_the_budget_moves(
        self, at_sea_level: HandLink, by_hand: HandLink
    ) -> None:
        """The geometric, atmospheric and pointing terms do not know about the height."""
        for field in ("geometric_db", "atmospheric_db", "pointing_db"):
            assert_identical(
                getattr(at_sea_level.loss, field), getattr(by_hand.loss, field), f"loss.{field}"
            )
        sea = np.asarray(at_sea_level.loss.scintillation_db)
        up = np.asarray(by_hand.loss.scintillation_db)
        assert np.all(up <= sea), "30 m above the boundary layer cannot add scintillation"
        assert 0.0 < float((sea - up).max()) < 0.02

    def test_the_difference_is_four_hundred_and_fifty_seven_bits(
        self, at_sea_level: HandLink, by_hand: HandLink
    ) -> None:
        sea = np.asarray(at_sea_level.finite.key_bits)
        up = np.asarray(by_hand.finite.key_bits)
        assert (up - sea).tolist() == [226.0, 0.0, 231.0, 0.0]
        assert float(up.sum() - sea.sum()) == 457.0
        assert float(up.sum() / sea.sum() - 1.0) == pytest.approx(0.001055, abs=1e-6)

    @pytest.mark.parametrize(
        ("name", "at_zero_bits", "at_altitude_bits", "cn2_ratio"),
        [
            ("castelldefels", 432_985.0, 433_442.0, 1.26),
            ("calar_alto", 56_925.0, 77_244.0, 9.82),
            ("tenerife_ogs", 562_697.0, 587_863.0, 10.46),
        ],
    )
    def test_what_the_term_is_worth_at_a_station_that_is_actually_up_a_mountain(
        self, name: str, at_zero_bits: float, at_altitude_bits: float, cn2_ratio: float
    ) -> None:
        """0.106 % at Castelldefels, 35.7 % at Calar Alto. The term is not a rounding.

        Same satellite, same day, same receiver, same mask; only the station and
        therefore the height of the turbulence integral change. The `C_n^2`
        ratio is the mechanism: the Hufnagel-Valley profile puts most of the
        turbulence in the first kilometre, so a telescope 2 168 m up has an
        order of magnitude less of it overhead.

        This is why `tests/e2e` asserts the engine's number and not the older
        one. At 30 m the difference is invisible; at the altitudes real optical
        ground stations sit at, dropping the field would throw away a third of
        the day's key.
        """
        altitude_m = STATIONS[name][2]
        sea = np.asarray(hand_link(name, station_height_m=0.0).finite.key_bits)
        up = np.asarray(hand_link(name, station_height_m=altitude_m).finite.key_bits)
        assert float(sea.sum()) == at_zero_bits
        assert float(up.sum()) == at_altitude_bits
        assert integrated_cn2_m13() / integrated_cn2_m13(
            station_height_m=altitude_m
        ) == pytest.approx(cn2_ratio, abs=0.01)

    def test_the_second_pass_at_calar_alto_is_doubled_by_it(self) -> None:
        """The day totals average the term away; one pass shows what it can do.

        A low pass is where the key is nearly all consumed by the bound, so a
        few hundredths of a decibel of scintillation decide whether it
        certifies anything at all. Calar Alto's second live pass goes from
        9 817 bits to 19 724 — a factor 2.01 — on a station whose day total
        moves by 36 %.
        """
        sea = np.asarray(hand_link("calar_alto", station_height_m=0.0).finite.key_bits)
        up = np.asarray(hand_link("calar_alto", station_height_m=2168.0).finite.key_bits)
        assert float(sea[2]) == 9_817.0
        assert float(up[2]) == 19_724.0
        assert float(up[2] / sea[2]) == pytest.approx(2.009, abs=0.001)


class TestTheEnsembleIsTheSameDraw:
    """The Monte Carlo stage: same seed, same stream, same quantiles, to the bit.

    The ensemble is the one stage where "the engine adds nothing" could fail
    without any number looking wrong, because a different draw is still a
    plausible ensemble. What pins it is that a single-station run uses the
    random source itself rather than a spawned child — deliberately, so that a
    one-station scenario reproduces the ensemble `tests/system` measures from
    the same seed — and that is what this class checks.
    """

    @pytest.fixture(scope="module")
    def engine_ensemble(self) -> Simulation:
        scenario = reference_castelldefels().model_copy(update={"monte_carlo": MONTE_CARLO})
        return simulate(scenario, degradations=DegradationLog())

    @pytest.fixture(scope="module")
    def hand_ensemble(self, by_hand: HandLink) -> Any:
        return hand_monte_carlo(by_hand, MONTE_CARLO)

    def test_every_column_of_the_ensemble_is_the_hand_ensemble(
        self, engine_ensemble: Simulation, hand_ensemble: Any
    ) -> None:
        engine_volume = engine_ensemble.stations[0].monte_carlo
        assert engine_volume is not None
        for field in ("quantile_bits", "outage_probability", "mean_bits", "expected_bits"):
            assert_identical(
                getattr(engine_volume, field), getattr(hand_ensemble, field), f"ensemble.{field}"
            )

    def test_the_seed_the_result_records_is_the_seed_it_drew_with(
        self, engine_ensemble: Simulation
    ) -> None:
        assert engine_ensemble.result.provenance.seed == MONTE_CARLO.seed
        assert engine_ensemble.result.monte_carlo is not None
        assert engine_ensemble.result.monte_carlo.seed == MONTE_CARLO.seed

    def test_the_design_figure_sits_below_the_median_of_the_ensemble(
        self, engine_ensemble: Simulation, hand_ensemble: Any
    ) -> None:
        """Not a bridge test; the sanity check that the two agree on something real.

        The deterministic budget holds a fade allowance at the 1 % quantile for
        the whole pass, which is a worse channel than the pass typically has, so
        the median of the ensemble is above the deterministic figure on every
        pass that certifies anything.
        """
        median = np.asarray(hand_ensemble.quantile_bits)[1]
        deterministic = np.asarray(engine_ensemble.stations[0].finite.key_bits)
        live = deterministic > 0.0
        assert np.all(median[live] > deterministic[live])


class TestTheAggregationAndTheRelayAddNothing:
    """Three stations, the scheduler and the trusted-node relay.

    The two optional stages that combine stations are where an orchestrator has
    the most room to add something: both take *several* per-station volumes and
    return one answer, so an ordering mistake or a silently dropped station
    would still produce a number of the right size.
    """

    @pytest.fixture(scope="module")
    def three_stations(self) -> Scenario:
        return reference_castelldefels().model_copy(
            update={
                "stations": [station_spec(name) for name in MULTI_STATION_NAMES],
                "multi_station": MultiStationSpec(policy="best_available"),
                "relay": RelaySpec(
                    pairs=[
                        ("castelldefels", "tenerife_ogs"),
                        ("castelldefels", "calar_alto"),
                    ]
                ),
            }
        )

    @pytest.fixture(scope="module")
    def engine_three(self, three_stations: Scenario) -> Simulation:
        return simulate(three_stations, degradations=DegradationLog())

    @pytest.fixture(scope="module")
    def hand_three(self) -> list[HandLink]:
        return [hand_link(name, station_height_m=STATIONS[name][2]) for name in MULTI_STATION_NAMES]

    def test_each_station_is_its_own_hand_link(
        self, engine_three: Simulation, hand_three: list[HandLink]
    ) -> None:
        """Per station, and in scenario order, which is what the stages index by."""
        assert tuple(run.name for run in engine_three.stations) == MULTI_STATION_NAMES
        for run, hand in zip(engine_three.stations, hand_three, strict=True):
            assert_identical(run.finite.key_bits, hand.finite.key_bits, f"{run.name} finite")
            assert_identical(
                run.asymptotic.key_bits, hand.asymptotic.key_bits, f"{run.name} asymptotic"
            )

    def test_the_scheduler_selects_what_the_hand_scheduler_selects(
        self, engine_three: Simulation, hand_three: list[HandLink]
    ) -> None:
        assert engine_three.multi_station is not None
        volume = aggregate_stations(
            station_set(*MULTI_STATION_NAMES),
            [hand.finite for hand in hand_three],
            availability=None,
            policy=AggregationPolicy("best_available"),
            degradations=DegradationLog(),
        )
        assert_identical(
            engine_three.multi_station.station_bits, volume.station_bits, "station_bits"
        )
        assert engine_three.multi_station.conflicts_dropped == volume.conflicts_dropped
        for engine_record, hand_record in zip(
            engine_three.multi_station.per_station, volume.per_station, strict=True
        ):
            assert_identical(engine_record.selected, hand_record.selected, "selected")

    def test_the_relay_delivers_what_the_hand_relay_delivers(
        self, engine_three: Simulation, hand_three: list[HandLink]
    ) -> None:
        pairs = (("castelldefels", "tenerife_ogs"), ("castelldefels", "calar_alto"))
        for index, (a, b) in enumerate(pairs):
            expected = trusted_node_relay(
                hand_three[MULTI_STATION_NAMES.index(a)].finite,
                hand_three[MULTI_STATION_NAMES.index(b)].finite,
                degradations=DegradationLog(),
                names=(a, b),
            )
            got = engine_three.relays[index]
            assert_identical(got.delivered_bits, expected.delivered_bits, f"{a}-{b} delivered")
            assert_identical(got.daily_bits, expected.daily_bits, f"{a}-{b} daily")
            assert got.total_bits == expected.total_bits
            assert got.stranded_bits == expected.stranded_bits

    def test_the_relay_cannot_deliver_more_than_the_thinner_side_certified(
        self, engine_three: Simulation
    ) -> None:
        """The identity the relay module documents, read off the engine's own result.

        A trusted-node relay pairs one bit from each side, so the end-to-end key
        is bounded by the smaller of the two stores. Castelldefels certifies
        433 442 bits and the Teide OGS 587 863, and the pair delivers exactly
        433 442 with 154 421 left stranded on the OGS side.
        """
        assert engine_three.result.relay is not None
        delivered = np.asarray(engine_three.result.relay.delivered_bits_per_day)
        residual = np.asarray(engine_three.result.relay.residuals)
        assert float(delivered[0].sum()) == ENGINE_FINITE_DAY_BITS
        assert float(residual[0]) == 587_863.0 - ENGINE_FINITE_DAY_BITS
