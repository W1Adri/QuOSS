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

Two kinds of assertion, and only one of them is exact
-----------------------------------------------------
The argument above covers **route against route in one process**: the engine's
array and the hand chain's array, computed seconds apart by the same library on
the same CPU. Those stay ``==``, and they are what "the engine adds nothing"
rests on.

It does not cover a **literal written by hand** — ``ENGINE_ASYMPTOTIC_DAY_BITS =
3_779_461.558061474`` — compared against what *another* machine computes. That
is a golden across machines, and floating point is deterministic within a
platform, not across them: IEEE 754 requires ``+ - * / sqrt`` to be correctly
rounded and does not require it of ``exp``, ``log``, ``pow`` or ``erf``, so two
conforming libraries may return neighbouring doubles for the same call. On
2026-09-15 this file failed on a second machine in exactly its two non-integer
literals, by 9 ULP of the value (1.1e-15 relative), while every route-against-
route assertion passed there. The machine the literals were written on
reproduced neither failure under numpy 2.4.4 or 2.4.6, nor with numpy's x86
SIMD kernels switched off: it is the platform, not a version.

So a literal goes through `assert_matches_literal`, against a bound derived from
what may legitimately differ, `cross_platform_relative_bound`::

    bound = 2 u eps kappa (n + G) + (N - 1) eps

- ``eps = 2.22e-16``, and ``u = 1``: each elementary-function call is taken to
  be within one ULP of the exact result — what ``libm`` implementations
  document, and weaker than correct rounding, which is half a ULP.
- ``n``: elementary-function call sites (``exp``, ``log``, ``pow``, ``erf``,
  ``**`` with a non-integer exponent...) in the modules the chain runs through,
  **counted from their source by the test**, so a new call site widens the bound
  by itself. An iterative solver counts once: its converged answer is set by
  its last evaluations, not by all of them. 140 today.
- ``G``: the one cancellation upstream of the transmittance.
  ``beam.geometric_transmittance`` is ``1 - exp(-x)``, and a one-ULP error in
  ``exp`` becomes ``(1 - eta) / eta`` ULP in ``eta``. Read from the budget: 740
  at the lowest sample of the reference day, where ``eta = 1.35e-3``.
- ``kappa``: how much a relative change in the transmittance moves the day's
  key, ``sum |dS / d ln eta| dwell / sum S dwell``, **measured** by a finite
  difference on the protocol. It carries the cancellation of privacy
  amplification against error correction. 1.064 today.
- ``2``: both platforms may be wrong, in opposite directions.
- ``(N - 1) eps``: the sum over ``N = 1 800`` samples in another order — a
  different numpy may reduce differently, and each partial sum rounds by at
  most half a ULP of the total.

That is **8.15e-13 relative: 3.1e-6 bits, 6 618 ULP** — seven hundred times the
9 ULP observed, and three hundred thousand times smaller than one bit, which is
the smallest change to a day's key this file exists to catch
(`test_the_bound_is_far_below_one_bit_and_a_one_bit_error_fails`).

What the bound does **not** model is FMA contraction, a compiler fusing
``a*b + c`` into one instruction and so rounding plain arithmetic differently.
If a platform ever exceeds the bound, the failure says by how many ULP, and the
model is what needs revisiting before the literal does. CI runs this file on
macOS arm64 and on numpy 2.0 so that such a platform is found by CI and not by
a colleague.

The integer literals (``ENGINE_FINITE_BITS``, ``433_442.0``) stay ``==``, and
not by assumption: the finite key is ``floor`` of a real number, and
`test_no_finite_literal_sits_near_a_floor_boundary` shows every pass's
unfloored length is at least **0.039 bits** from the nearest integer, against a
derived error of 6e-7 bits.

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
TestTheScenarioChoosesTheRegime
    Stage 1.2 wired: ``run()`` in the saturated regime, against the hand chain.
TestTheFourHundredAndFiftySevenBitsChangeSignUnderSaturation
    The same 30 m, worth -206 bits instead of +457, and the two factors why.
TestTheEnsembleIsTheSameDraw
    The Monte Carlo stage: same seed, same stream, same quantiles.
TestTheAggregationAndTheRelayAddNothing
    Three stations, the scheduler and the trusted-node relay.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from quoss.channel.atmosphere import integrated_cn2_m13
from quoss.channel.extinction import (
    VisibilityScalingLaw,
    zenith_transmittance_from_visibility,
)
from quoss.channel.turbulence import (
    ScintillationRegime,
    aperture_averaging_factor,
    downlink_log_irradiance_variance,
    log_irradiance_variance,
)
from quoss.core.errors import DegradationLog
from quoss.engine.cache import ResultCache
from quoss.engine.pipeline import Simulation, StationRun, simulate
from quoss.engine.pipeline import run as run_scenario
from quoss.engine.sweep import SweepResult, SweepSpec, run_sweep
from quoss.qkd.base import LinkConditions, binary_entropy
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import (
    ChannelSpec,
    ExtinctionSpec,
    MonteCarloSpec,
    MultiStationSpec,
    RelaySpec,
    Scenario,
)
from quoss.system.key_volume import pass_key_volume
from quoss.system.multi_ogs import AggregationPolicy, aggregate_stations
from quoss.system.relay import trusted_node_relay

from .oracle import (
    REFERENCE_FINITE_BITS,
    REFERENCE_FINITE_DAY_BITS,
    STATIONS,
    WAVELENGTH_M,
    HandLink,
    hand_link,
    hand_monte_carlo,
    mean_log_transmittance,
    reference_protocol,
    reference_security,
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
"""Written at full precision on one machine, and compared through `assert_matches_literal`.

Never with ``==``: see "Two kinds of assertion" in the module docstring. The
digits are kept because the bound is 3.1e-6 bits, so the literal still pins the
number to five decimal places on any platform.
"""

STAGE_THREE_ASYMPTOTIC_DAY_BITS = 3_776_680.752646787
"""The same, at 0 m: what `tests/system` quotes as 3.78 Mbit. Same comparison."""

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

MASK_SWEEP_DEG = (2.0, 4.5, 8.0, 20.0)
"""The four masks stage 1.2 measured by hand, including both optima."""

STAGE_ONE_TWO_HAND_TABLE: dict[tuple[float, ScintillationRegime], float] = {
    (2.0, ScintillationRegime.WEAK): 408_946.0,
    (4.5, ScintillationRegime.WEAK): 424_448.0,
    (8.0, ScintillationRegime.WEAK): 434_938.0,
    (20.0, ScintillationRegime.WEAK): 360_978.0,
    (2.0, ScintillationRegime.MODERATE_TO_STRONG): 458_862.0,
    (4.5, ScintillationRegime.MODERATE_TO_STRONG): 462_945.0,
    (8.0, ScintillationRegime.MODERATE_TO_STRONG): 457_663.0,
    (20.0, ScintillationRegime.MODERATE_TO_STRONG): 364_740.0,
}
"""ADR 0022's table, transcribed from `tests/system/test_key_volume.py`.

Those are the stage-3 fixture's numbers: the same chain with the turbulence
profile left at 0 m, which is what `tests/system/reference.py` documents at
length. `TestTheMaskSweepInBothRegimes` reproduces every one of them from the
`oracle` chain and shows that the whole difference from the engine's own table
is that one argument.
"""

ENGINE_MASK_SWEEP_BITS: dict[tuple[float, ScintillationRegime], float] = {
    (2.0, ScintillationRegime.WEAK): 409_584.0,
    (4.5, ScintillationRegime.WEAK): 425_073.0,
    (8.0, ScintillationRegime.WEAK): 435_462.0,
    (20.0, ScintillationRegime.WEAK): 361_199.0,
    (2.0, ScintillationRegime.MODERATE_TO_STRONG): 458_076.0,
    (4.5, ScintillationRegime.MODERATE_TO_STRONG): 462_358.0,
    (8.0, ScintillationRegime.MODERATE_TO_STRONG): 457_341.0,
    (20.0, ScintillationRegime.MODERATE_TO_STRONG): 364_774.0,
}
"""The same eight cells as `run_sweep` computes them, with the station's 30 m wired."""


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


ELEMENTARY_FUNCTIONS = frozenset(
    {
        "exp", "expm1", "exp2", "log", "log1p", "log2", "log10", "power", "cbrt", "hypot",
        "sin", "cos", "tan", "arcsin", "arccos", "arctan", "arctan2", "sinh", "cosh", "tanh",
        "erf", "erfc", "erfcx", "erfinv", "erfcinv", "ndtr", "ndtri", "log_ndtr",
        "xlogy", "xlog1py", "gammaln", "lambertw",
    }
)  # fmt: skip
"""Calls whose result IEEE 754 does not require to be correctly rounded.

``sqrt`` is absent on purpose: the standard does require it, like ``+ - * /``.
"""

CHAIN_MODULES = (
    "quoss.core.units",
    "quoss.orbits.kepler",
    "quoss.orbits.frames",
    "quoss.orbits.geometry",
    "quoss.orbits.propagator",
    "quoss.orbits.perturbations",
    "quoss.orbits.constellations",
    "quoss.channel.atmosphere",
    "quoss.channel.turbulence",
    "quoss.channel.beam",
    "quoss.channel.pointing",
    "quoss.channel.background",
    "quoss.channel.detector",
    "quoss.channel.link_budget",
    "quoss.qkd.base",
    "quoss.qkd.bb84",
    "quoss.qkd.finite_key",
    "quoss.system.passes",
    "quoss.system.key_volume",
)
"""Every module the reference chain runs through, whole: an over-count, never an under-count."""

ULP_PER_ELEMENTARY_CALL = 1.0
"""``u``: how far from exact one call may be. One ULP; correct rounding would be half."""

DIFFERENCE_STEP = 1e-6
"""Relative step of the finite difference for ``kappa``.

Its truncation error is of order the step itself, a millionth of ``kappa``, and
its rounding noise of order ``eps / step = 2e-10``: both negligible against a
``kappa`` of order one, which is all the bound needs of it.
"""


def assert_matches_literal(got: float, literal: float, *, relative_bound: float, what: str) -> None:
    """Assert a computed value is within a derived cross-platform bound of a hand-written literal.

    See "Two kinds of assertion" in the module docstring. The failure message
    reports the distance in ULP, because that is the unit in which "another
    platform" and "a real change" are told apart.
    """
    difference = abs(got - literal)
    ulp = float(np.spacing(abs(literal)))
    allowed = relative_bound * abs(literal)
    assert difference <= allowed, (
        f"{what}: {got!r} is {difference / ulp:.0f} ULP from the literal {literal!r}; the "
        f"derived cross-platform bound is {allowed / ulp:.0f} ULP ({relative_bound:.2e} "
        "relative). Beyond it this is a change in the computation, not in the platform — "
        "unless the platform contracts arithmetic into FMA, which the bound does not model."
    )


def elementary_call_sites() -> int:
    """Return ``n``: elementary-function call sites in `CHAIN_MODULES`, counted from source."""
    count = 0
    for name in CHAIN_MODULES:
        tree = ast.parse(inspect.getsource(importlib.import_module(name)))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                function = node.func
                called = (
                    function.attr
                    if isinstance(function, ast.Attribute)
                    else getattr(function, "id", "")
                )
                count += called in ELEMENTARY_FUNCTIONS
            elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.Pow):
                exponent = node.right
                count += not (isinstance(exponent, ast.Constant) and type(exponent.value) is int)
    return count


def nudged_conditions(link: HandLink) -> LinkConditions:
    """Return the link's conditions with every transmittance raised by `DIFFERENCE_STEP`."""
    conditions = link.conditions
    return LinkConditions(
        transmittance=np.asarray(conditions.transmittance) * (1.0 + DIFFERENCE_STEP),
        noise_counts_per_gate=conditions.noise_counts_per_gate,
        misalignment_error=conditions.misalignment_error,
        pulse_rate_hz=conditions.pulse_rate_hz,
        gate_duration_s=conditions.gate_duration_s,
    )


def upstream_relative_error(link: HandLink) -> float:
    """Return ``2 u eps (n + G)``: how far apart two platforms may put the transmittance."""
    eps = float(np.finfo(np.float64).eps)
    eta = 10.0 ** (-np.asarray(link.loss.geometric_db, dtype=np.float64) / 10.0)
    cancellation = float(np.max((1.0 - eta) / eta))
    return 2.0 * ULP_PER_ELEMENTARY_CALL * eps * (elementary_call_sites() + cancellation)


def cross_platform_relative_bound(link: HandLink) -> float:
    """Return the derived relative bound for a day's asymptotic key; see the module docstring."""
    protocol = reference_protocol()
    log = DegradationLog()
    base = np.asarray(protocol.key_rate(link.conditions, degradations=log).secure_per_pulse)
    nudged = np.asarray(
        protocol.key_rate(nudged_conditions(link), degradations=log).secure_per_pulse
    )
    dwell = np.asarray(link.samples.dwell_s, dtype=np.float64)
    kappa = float(np.sum(np.abs(nudged - base) * dwell) / (DIFFERENCE_STEP * np.sum(base * dwell)))
    eps = float(np.finfo(np.float64).eps)
    return kappa * upstream_relative_error(link) + (dwell.size - 1) * eps


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


@pytest.fixture(scope="module")
def mask_regime_sweep() -> SweepResult:
    """Return the eight-cell mask-by-regime grid of `TestTheMaskSweepInBothRegimes`.

    Module-scoped because it is eight full days of the reference scenario and
    six tests read it; it is a record, so nothing mutates it.
    """
    return run_sweep(
        reference_castelldefels(),
        SweepSpec(
            {
                "passes.minimum_elevation_deg": list(MASK_SWEEP_DEG),
                "channel.scintillation_regime": [
                    ScintillationRegime.WEAK.value,
                    ScintillationRegime.MODERATE_TO_STRONG.value,
                ],
            }
        ),
        degradations=DegradationLog(),
    )


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

    def test_the_acquisition_series_are_the_hand_acquisition(
        self, engine: Simulation, station: StationRun, by_hand: HandLink
    ) -> None:
        """Range-rate, Doppler, Doppler rate and point-ahead, on the whole grid.

        Defined everywhere, unlike the channel: a satellite has a position and a
        velocity whether or not the link is worth scoring, and an acquisition
        question is asked precisely about the part of the sky the key stage
        refuses. So these are compared over all 86 401 samples, not only the
        1 800 in a pass.
        """
        (series,) = engine.result.series
        range_rate, doppler, rate, point_ahead = by_hand.acquisition
        for name, expected in (
            ("range_rate_km_s", range_rate),
            ("doppler_shift_hz", doppler),
            ("doppler_rate_hz_s", rate),
            ("point_ahead_angle_rad", point_ahead),
        ):
            values = np.asarray(getattr(series, name).values)
            assert np.all(np.isfinite(values)), f"series.{name} is not defined everywhere"
            assert_identical(values, expected, f"series.{name}")
        assert_identical(
            station.acquisition.doppler_shift_hz, doppler, "acquisition.doppler_shift_hz"
        )

    def test_the_per_pass_acquisition_extrema_are_the_hand_extrema(
        self, engine: Simulation, by_hand: HandLink
    ) -> None:
        peak_doppler, excursion, peak_rate, widest, narrowest = by_hand.pass_acquisition
        passes = engine.result.passes
        assert_identical(
            passes.peak_one_sided_doppler_hz, peak_doppler, "peak_one_sided_doppler_hz"
        )
        assert_identical(passes.doppler_excursion_hz, excursion, "doppler_excursion_hz")
        assert_identical(passes.peak_doppler_slew_hz_s, peak_rate, "peak_doppler_slew_hz_s")
        assert_identical(passes.max_point_ahead_angle_rad, widest, "max_point_ahead_angle_rad")
        assert_identical(passes.min_point_ahead_angle_rad, narrowest, "min_point_ahead_angle_rad")

    def test_what_the_reference_day_demands_of_a_transceiver(self, engine: Simulation) -> None:
        """The numbers the acquisition columns exist to produce, on the reference link.

        At 1550 nm (``f0 = 1.934e14`` Hz) the reference day's four passes reach
        a one-sided peak of **4.19, 2.85, 4.27 and 2.23 GHz**, sweep a total
        excursion of **8.37, 5.66, 8.54 and 4.40 GHz**, and demand a tracking
        rate of **37.9, 19.2, 41.5 and 16.8 MHz/s**. The point-ahead lead runs
        from 24.7 to 50.7 microradians — a factor two *within a single pass*,
        which is why the span and not only the peak is reported.

        The first two rows are the distinction this test exists to keep visible.
        "A capture range of 4.19 GHz" is the wrong reading of the first row and
        this docstring used to give it: the signal does not sit 4.19 GHz off the
        carrier, it *travels* from +4.18 to -4.19 GHz over the pass, and a
        receiver has to be able to find it anywhere in between. The requirement
        is **8.37 GHz** of window, or ±4.19 GHz written the other way, and
        reading the peak as the range under-specifies the transceiver by a
        factor two — in the parameter that ended TBIRD's passes early.

        Read as a requirement: a transceiver whose search window is under
        8.6 GHz cannot acquire the best pass of this link across its whole
        length, and one whose loop cannot slew 42 MHz/s cannot hold it at the
        horizon. That is the TBIRD end-of-pass failure written as two columns
        of a result — two columns, because they are two requirements.
        """
        passes = engine.result.passes
        assert np.asarray(passes.peak_one_sided_doppler_hz).round(-6).tolist() == [
            4_187_000_000.0,
            2_847_000_000.0,
            4_272_000_000.0,
            2_226_000_000.0,
        ]
        assert np.asarray(passes.doppler_excursion_hz).round(-6).tolist() == [
            8_370_000_000.0,
            5_662_000_000.0,
            8_538_000_000.0,
            4_399_000_000.0,
        ]
        assert np.asarray(passes.peak_doppler_slew_hz_s).round(-4).tolist() == [
            37_930_000.0,
            19_230_000.0,
            41_550_000.0,
            16_770_000.0,
        ]
        widest = np.asarray(passes.max_point_ahead_angle_rad)
        narrowest = np.asarray(passes.min_point_ahead_angle_rad)
        assert np.all(widest > narrowest)
        assert float(widest.max()) == pytest.approx(50.66e-6, rel=1e-3)
        assert float(narrowest.min()) == pytest.approx(24.69e-6, rel=1e-3)

    def test_the_daily_table_sums_the_passes_and_nothing_else(
        self, engine: Simulation, by_hand: HandLink
    ) -> None:
        daily = engine.result.daily
        assert daily.day_number.tolist() == [2_460_677]
        assert float(np.asarray(daily.finite_bits)[0]) == ENGINE_FINITE_DAY_BITS
        assert_matches_literal(
            float(np.asarray(daily.asymptotic_bits)[0]),
            ENGINE_ASYMPTOTIC_DAY_BITS,
            relative_bound=cross_platform_relative_bound(by_hand),
            what="daily.asymptotic_bits",
        )
        assert float(np.asarray(daily.asymptotic_bits)[0]) == float(
            np.asarray(engine.result.passes.asymptotic_bits).sum()
        )
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
        adds nothing" is checkable on the log as well as on the numbers.

        The codes are listed rather than counted loosely, because a warning that
        stops being raised is exactly as much of a change as a number that
        moves — the weak-fluctuation limit below is the one the reference link
        is known to exceed (`notes/LAST_CHANGES.md` §18), and losing it would
        turn a declared limitation into a silent one.

        **The one ``engine.`` entry, and why it is allowed to be here.** This
        test used to assert there were none at all, on the reasoning that
        nothing happens in a reference run that only the orchestration could
        know about. That stopped being true with
        [ADR 0020](../../docs/adr/0020-declared-doppler-capture-range.md): the
        engine is the only layer that sees the *scenario*, so it is the only one
        that can notice ``receiver.doppler_capture_range_hz`` was never
        declared. No physics module could raise that, because none of them is
        handed the field.

        It is an INFO, so it changes no number, and "the engine adds nothing"
        is unharmed — the claim is about values, not about silence. What would
        break the claim is an ``engine.`` entry at WARNING or worse, so that is
        what is asserted instead of a blanket absence.
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
                "engine.acquisition.no-capture-range-declared": 1,
            }
        )
        engine_entries = [
            entry for entry in engine.result.warnings if str(entry["code"]).startswith("engine.")
        ]
        assert [str(entry["severity"]) for entry in engine_entries] == ["info"]


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


class TestTheLiteralsHoldOnAnotherMachine:
    """The cross-platform bound itself: what it is today, and that it can still fail."""

    def test_the_bound_is_far_below_one_bit_and_a_one_bit_error_fails(
        self, by_hand: HandLink
    ) -> None:
        """A tolerance that cannot fail proves nothing; this one fails at a millionth of a bit.

        The numbers of the module docstring, recomputed: ``n = 140`` call
        sites, ``G = 740``, ``kappa = 1.064``, ``N = 1 800``, so 8.15e-13
        relative and 3.1e-6 bits. And the two directions that make it a test:
        the 9 ULP by which the second machine differed passes, and a literal
        one bit off does not.
        """
        bound = cross_platform_relative_bound(by_hand)
        allowed_bits = bound * ENGINE_ASYMPTOTIC_DAY_BITS
        assert elementary_call_sites() >= 140
        assert bound == pytest.approx(8.15e-13, rel=0.05)
        assert allowed_bits < 1e-5
        observed_on_the_second_machine = 3_779_461.558061478 - ENGINE_ASYMPTOTIC_DAY_BITS
        assert abs(observed_on_the_second_machine) < allowed_bits
        got = float(np.asarray(by_hand.asymptotic.key_bits).sum())
        with pytest.raises(AssertionError, match="ULP from the literal"):
            assert_matches_literal(
                got, ENGINE_ASYMPTOTIC_DAY_BITS + 1.0, relative_bound=bound, what="one bit off"
            )

    @pytest.mark.parametrize("height_m", [CASTELLDEFELS_HEIGHT_M, 0.0])
    def test_no_finite_literal_sits_near_a_floor_boundary(self, height_m: float) -> None:
        """Why ``ENGINE_FINITE_BITS`` and ``REFERENCE_FINITE_BITS`` may stay ``==``.

        Lim et al.'s length is ``floor`` of ``s_0 + s_1 (1 - h(phi)) - leak -
        penalty``. A cross-platform difference in that real number changes the
        integer only if the number sits within the difference of an integer —
        or, for a pass with no key, of 1, below which the length is zero. So the
        unfloored length is rebuilt from the bound's own columns (and checked to
        floor to the reported length), and its distance to the boundary is
        compared with a derived error:

        ``2 u eps (n + G) |d raw / d ln eta| + (N - 1) eps (s_0 + s_1 + leak + penalty)``

        the first term for the transmittance, measured by finite difference
        through the whole finite-key chain, and the second for the block sums.
        Measured: the closest pass is **0.039 bits** from an integer (the first
        pass at 30 m, 190 807.961) against **5.9e-7 bits** of possible error.
        """
        link = hand_link("castelldefels", station_height_m=height_m)
        security = reference_security()

        def unfloored(finite: Any) -> np.ndarray:
            return np.asarray(
                np.asarray(finite.vacuum_events)
                + np.asarray(finite.single_photon_events)
                * (1.0 - binary_entropy(np.asarray(finite.phase_error_rate)))
                - np.asarray(finite.leakage_bits)
                - security.penalty_bits,
                dtype=np.float64,
            )

        assert link.finite.finite is not None
        raw = unfloored(link.finite.finite)
        assert np.array_equal(
            np.maximum(np.floor(raw), 0.0), np.asarray(link.finite.key_bits, dtype=np.float64)
        )
        nudged = pass_key_volume(
            nudged_conditions(link),
            samples=link.samples,
            protocol=reference_protocol(),
            security=security,
            degradations=DegradationLog(),
        )
        assert nudged.finite is not None
        slope = np.abs(unfloored(nudged.finite) - raw) / DIFFERENCE_STEP
        magnitude = (
            np.asarray(link.finite.finite.vacuum_events)
            + np.asarray(link.finite.finite.single_photon_events)
            + np.asarray(link.finite.finite.leakage_bits)
            + security.penalty_bits
        )
        eps = float(np.finfo(np.float64).eps)
        samples = np.asarray(link.samples.dwell_s).size
        error = upstream_relative_error(link) * slope + (samples - 1) * eps * magnitude
        margin = np.where(raw < 1.0, 1.0 - raw, np.minimum(raw - np.floor(raw), np.ceil(raw) - raw))
        assert np.all(margin > error), f"margin {margin} against error {error}"
        assert float(np.max(error)) < 1e-6
        assert float(np.min(margin)) > 0.03


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
        assert_matches_literal(
            float(np.asarray(at_sea_level.asymptotic.key_bits).sum()),
            STAGE_THREE_ASYMPTOTIC_DAY_BITS,
            relative_bound=cross_platform_relative_bound(at_sea_level),
            what="asymptotic day at 0 m",
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
        ratio asserted alongside is *part* of the mechanism: the profile puts
        most of the turbulence in the first kilometre, so a telescope 2 168 m up
        has an order of magnitude less of it overhead.

        It is deliberately only part, and this docstring used to claim it was
        the whole thing. It cannot be: the `C_n^2` ratio rises with altitude
        (9.82 at Calar Alto, 10.46 at the Teide OGS) while the key gain falls
        (+35.7 %, +4.5 %). The turbulence integral explains a channel that is
        6.94 % brighter at Calar Alto and 4.80 % at the Teide; what turns those
        into +35.7 % and +4.5 % is the finite-key bound amplifying them by 4.55
        and 0.934. `TestWhyTheHigherStationGainsLess` takes that apart and is
        where the non-monotonicity is answered.

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


class TestWhyTheHigherStationGainsLess:
    """+35.7 % at Calar Alto (2 168 m) and +4.5 % at the Teide OGS (2 400 m), decomposed.

    The question this class exists to answer
    ----------------------------------------
    `TestTheFourHundredAndFiftySevenBits` reports both figures and explains
    neither. Read on its own it says something false by implication: that
    starting the turbulence integral higher up buys more key, and that the
    mechanism is "less atmosphere overhead". If that were the whole mechanism
    the effect would have to be **monotonic in altitude** — a higher telescope
    would always gain at least as much as a lower one. It is not. The Teide OGS
    is 232 m *higher* than Calar Alto and gains **eight times less**.

    An unexplained non-monotonicity in the headline number of an ADR is exactly
    the failure mode CLAUDE.md is written against: a plausible number, sitting
    next to a mechanism that does not produce it, with a passing suite
    underneath. So this class takes the effect apart into two factors that can
    be measured separately, and shows that the one people reach for (altitude)
    is not the one doing the work.

    The two factors, defined
    ------------------------
    Write `x = mean(ln T)` — the log-transmittance summary defined and defended
    in `oracle.mean_log_transmittance` — and `y = ln(key bits for the day)`.
    Moving the station's turbulence integral from sea level up to its real
    altitude changes both:

    - **`dx`, the channel factor.** How much brighter the link got. This is
      atmospheric physics and nothing else: the ITU-R P.1621-2 surface term has
      a 100 m scale height, so a telescope up a mountain has an order of
      magnitude less turbulence above it.
    - **`E = dy / dx`, the elasticity, or the bound's amplification.** How many
      per cent of key one per cent of transmittance buys. "Elasticity" is the
      economists' word for the ratio of two fractional changes, borrowed
      because that is exactly what it is; nothing in it is economics.

      `E = 1` means key is simply proportional to transmittance — one per cent
      more light, one per cent more key. That is the asymptotic regime, where
      the key rate is a rate and the pass just collects it.

      `E >> 1` means the pass is at the **certification cliff**: the finite-key
      bound subtracts a block of statistical penalties from the raw sifted key,
      and on a pass where almost all of the key is eaten by those penalties,
      what survives is a small difference of two large numbers. A small change
      in the larger one moves the difference enormously. That is not a property
      of the atmosphere; it is a property of the security proof.

    `dy = E * dx` is an identity, not a discovery — `E` is defined as the
    ratio. The content is that the two halves turn out to be separable and to
    have separate causes, and that the second one is what makes the effect
    non-monotonic.

    What the numbers are
    --------------------
    ==============  ===========  ===========  ===========  ==========
    station         altitude     `dx` (T)     `E`          `dy` (key)
    ==============  ===========  ===========  ===========  ==========
    Calar Alto       2 168 m      +6.94 %      4.55         +35.7 %
    Teide OGS        2 400 m      +4.80 %      0.934        +4.5 %
    ==============  ===========  ===========  ===========  ==========

    Both factors point the same way, and **neither of them is altitude**:

    1. Calar Alto's channel gains *more* (6.94 % against 4.80 %) despite being
       lower, because its passes are lower in the sky — they culminate at 21 to
       37 degrees, the Teide's at 57 and 72. A low pass looks through a long
       slant path, so the near-ground layer that altitude removes is a larger
       share of its turbulence integral. This is geometry, not height.
    2. Calar Alto's bound amplifies by 4.55 and the Teide's by 0.934. Its
       passes certify 1.1 % and 4.5 % of their own asymptotic key; the Teide's
       certify 13.7 % and 16.8 %. Calar Alto is on the cliff and the Teide is
       not.

    The second factor is the bigger one, and the tests below show it by
    swapping the elasticities: give the Teide OGS Calar Alto's `E` at its own
    unchanged channel gain and it would report **+23.7 %** instead of +4.5 %;
    give Calar Alto the Teide's `E` and it drops from +35.7 % to **+6.5 %**.

    Why this is worth a test class and not a paragraph
    --------------------------------------------------
    Stage 1.2 changes the scintillation model. When it lands, some passes will
    cross the cliff. Without this decomposition the only observable is the day
    total, and a day total that moves by a factor of two is equally consistent
    with "the turbulence model changed a lot" and "the turbulence model changed
    by 0.02 dB and the bound amplified it". Those two need different responses,
    and after the fact there is no way to tell them apart from the headline.
    `dx` and `E` separate them: `dx` is the model, `E` is the bound.
    """

    LIVE_PASSES = (
        ("calar_alto", 0),
        ("calar_alto", 2),
        ("castelldefels", 0),
        ("castelldefels", 2),
        ("tenerife_ogs", 0),
        ("tenerife_ogs", 1),
    )
    """The six passes of the reference day that certify any key at all, at sea level.

    The other four certify zero, so `ln(key)` is undefined on them and they
    carry no elasticity. That they are exactly the four lowest passes is the
    same cliff seen from one step further out.
    """

    @staticmethod
    def _factors(name: str, pass_index: int | None = None) -> tuple[float, float, float]:
        """Return `(dx, E, dy)` for a station's day, or for one of its passes."""
        altitude_m = STATIONS[name][2]
        sea = hand_link(name, station_height_m=0.0)
        up = hand_link(name, station_height_m=altitude_m)
        d_x = mean_log_transmittance(up, pass_index) - mean_log_transmittance(sea, pass_index)
        if pass_index is None:
            sea_bits = float(np.asarray(sea.finite.key_bits).sum())
            up_bits = float(np.asarray(up.finite.key_bits).sum())
        else:
            sea_bits = float(np.asarray(sea.finite.key_bits)[pass_index])
            up_bits = float(np.asarray(up.finite.key_bits)[pass_index])
        d_y = float(np.log(up_bits / sea_bits))
        return d_x, d_y / d_x, d_y

    def test_the_channel_on_its_own_is_monotonic_in_altitude(self) -> None:
        """Hold the geometry fixed and the physics behaves: more height, more key, always.

        This is the control. The claim under test in this class is that the
        non-monotonicity across stations comes from the pass geometry and the
        bound, *not* from the turbulence model — so the turbulence model had
        better be monotonic when nothing else is allowed to move.

        One station, one day, one set of passes; only the height the integral
        starts from changes. All three quantities rise together at every step
        from sea level to 4 km: the integrated `C_n^2` falls, the mean
        log-transmittance rises, the day's key rises. 56 925 bits at 0 m,
        77 244 at 2 168 m, 90 695 at 4 km, with no step backwards.

        If this test ever fails, the decomposition below is meaningless and the
        bug is in `atmosphere.py`, not in the story about the cliff.
        """
        heights = (0.0, 500.0, 1000.0, 2168.0, 2400.0, 3000.0, 4000.0)
        links = [hand_link("calar_alto", station_height_m=h) for h in heights]
        cn2 = [integrated_cn2_m13(station_height_m=h) for h in heights]
        log_transmittance = [mean_log_transmittance(link) for link in links]
        key_bits = [float(np.asarray(link.finite.key_bits).sum()) for link in links]

        assert cn2 == sorted(cn2, reverse=True)
        assert log_transmittance == sorted(log_transmittance)
        assert key_bits == sorted(key_bits)
        assert key_bits[0] == 56_925.0
        assert key_bits[3] == 77_244.0
        assert key_bits[-1] == 90_695.0

    def test_the_channel_factor_is_larger_at_the_lower_station(self) -> None:
        """Factor one: Calar Alto's link brightens by 6.94 %, the Teide's by 4.80 %.

        The lower station gains more channel, which already breaks "higher is
        better" before the bound is involved at all. The cause is in the
        culmination elevations asserted alongside: Calar Alto's live passes top
        out at 36.9 and 32.7 degrees, the Teide's at 57.4 and 72.1. Turbulence
        is integrated along the slant path, so at 33 degrees the path through
        the first kilometre is about `1 / sin(33 deg) = 1.8` times longer than
        at 57 degrees — the layer that altitude deletes is simply a bigger part
        of what a low pass looks through.

        The 0.75 % of channel gain that Calar Alto wins here is real but small.
        It is not what turns 4.5 % into 35.7 %; the next test is.
        """
        calar_dx, _, _ = self._factors("calar_alto")
        teide_dx, _, _ = self._factors("tenerife_ogs")

        assert np.expm1(calar_dx) == pytest.approx(0.0694, abs=5e-5)
        assert np.expm1(teide_dx) == pytest.approx(0.0480, abs=5e-5)
        assert calar_dx > teide_dx

        calar_culmination = np.rad2deg(
            np.asarray(
                hand_link("calar_alto", station_height_m=0.0).table.culmination_elevation_rad
            )
        )
        teide_culmination = np.rad2deg(
            np.asarray(
                hand_link("tenerife_ogs", station_height_m=0.0).table.culmination_elevation_rad
            )
        )
        assert calar_culmination.max() < teide_culmination.min()

    def test_the_bound_amplifies_by_five_at_calar_alto_and_not_at_all_at_the_teide(self) -> None:
        """Factor two, and the one that carries the effect: `E` is 4.55 against 0.934.

        The Teide's elasticity being just under 1 is the statement that its
        passes are in the ordinary regime — one per cent more light buys about
        one per cent more key, as it would if there were no finite-key bound at
        all. (Slightly under 1, because the penalties the bound subtracts grow
        a little as the pass gets brighter.)

        Calar Alto's 4.55 is the statement that its passes are not. The two
        stations differ by a factor 4.9 in how hard their bound bites, which is
        the whole of the eight-fold difference in the headline once the 1.4-fold
        difference in channel gain is taken out.
        """
        _, calar_e, _ = self._factors("calar_alto")
        _, teide_e, _ = self._factors("tenerife_ogs")

        assert calar_e == pytest.approx(4.548, abs=0.001)
        assert teide_e == pytest.approx(0.934, abs=0.001)
        assert calar_e / teide_e == pytest.approx(4.87, abs=0.01)

    def test_the_two_factors_reproduce_the_headline_figures(self) -> None:
        """`dy = E * dx` lands on +35.7 % and +4.5 %, the numbers the ADR reports.

        The identity is exact by construction, so what this checks is that the
        two factors measured above are the ones belonging to these two
        published figures and not to some neighbouring quantity — that the
        decomposition is *of* the claim, not merely near it.
        """
        for name, expected_gain in (("calar_alto", 0.35694), ("tenerife_ogs", 0.04472)):
            d_x, elasticity, d_y = self._factors(name)
            assert np.expm1(elasticity * d_x) == pytest.approx(expected_gain, abs=1e-5)
            assert np.expm1(d_y) == pytest.approx(expected_gain, abs=1e-5)

    def test_swapping_the_elasticities_swaps_the_headlines(self) -> None:
        """The counterfactual that shows which factor is load-bearing.

        Hold each station's own channel gain — its own atmosphere, its own
        passes — and give it the other station's bound amplification. The Teide
        OGS goes from +4.5 % to **+23.7 %** and Calar Alto from +35.7 % to
        **+6.5 %**: the two figures nearly trade places.

        That is the answer to "why does the higher station gain less". Almost
        none of it is the 232 m. It is that Calar Alto's passes sit on the
        certification cliff and the Teide's do not, and a station on the cliff
        converts a small optical improvement into a large key improvement.
        """
        calar_dx, calar_e, _ = self._factors("calar_alto")
        teide_dx, teide_e, _ = self._factors("tenerife_ogs")

        assert np.expm1(teide_dx * calar_e) == pytest.approx(0.2375, abs=5e-4)
        assert np.expm1(calar_dx * teide_e) == pytest.approx(0.0647, abs=5e-4)

    def test_the_elasticity_falls_as_the_pass_gets_further_from_the_cliff(self) -> None:
        """The mechanism, stated as an invariant over all six live passes.

        "Distance from the cliff" needs a measure, and the natural one is
        already computed: the fraction of a pass's **asymptotic** key that the
        finite bound certifies. The asymptotic key is what the same pass would
        yield with an unbounded block and no statistical penalties, so
        `finite / asymptotic` is exactly "how much of it survived the proof".
        Near 0 the bound is eating nearly everything, which is the cliff; at
        0.17 it is taking a large but ordinary toll.

        Ordered by that fraction, the elasticities fall strictly and across
        station boundaries — Calar Alto's worst pass at 1.1 % amplifies by
        12.2, its better one at 4.5 % by 3.8, then Castelldefels at 12.3 % by
        1.23, the Teide at 13.7 % by 1.09, Castelldefels at 14.2 % by 1.02, and
        the Teide's best at 16.8 % by 0.83.

        Six passes across three stations, two altitudes apiece, ordering
        perfectly by a quantity that is not altitude and not elevation. That is
        the claim: the amplifier is the bound's margin, full stop. It is also
        what makes the effect predictable rather than anecdotal — a pass's
        `finite / asymptotic` ratio is computable in advance, so which passes
        stage 1.2 will move is knowable before it is written.
        """
        measured = []
        for name, pass_index in self.LIVE_PASSES:
            sea = hand_link(name, station_height_m=0.0)
            finite = float(np.asarray(sea.finite.key_bits)[pass_index])
            asymptotic = float(np.asarray(sea.asymptotic.key_bits)[pass_index])
            _, elasticity, _ = self._factors(name, pass_index)
            measured.append((finite / asymptotic, elasticity))

        measured.sort()
        margins = [margin for margin, _ in measured]
        elasticities = [elasticity for _, elasticity in measured]
        assert elasticities == sorted(elasticities, reverse=True)

        assert margins[0] == pytest.approx(0.0108, abs=5e-5)
        assert elasticities[0] == pytest.approx(12.18, abs=0.01)
        assert margins[-1] == pytest.approx(0.1682, abs=5e-5)
        assert elasticities[-1] == pytest.approx(0.826, abs=0.001)


@pytest.mark.reference
class TestWhatTheSaturatedModelIsWorth:
    """**Stage 1.2, decomposed.** The interest `TestWhyTheHigherStationGainsLess` said to collect.

    That class ends by predicting this one: "Stage 1.2 changes the scintillation
    model. When it lands, some passes will cross the cliff. Without this
    decomposition the only observable is the day total, and a day total that
    moves by a factor of two is equally consistent with *the turbulence model
    changed a lot* and *the turbulence model changed by 0.02 dB and the bound
    amplified it*." Stage 1.2 has landed, so here are the two factors.

    The same `dx` and `E` as before, with the intervention swapped
    --------------------------------------------------------------
    `x = mean(ln T)` and `y = ln(key bits)`, exactly as
    `oracle.mean_log_transmittance` defines them. The intervention is no longer
    moving the station up a mountain; it is evaluating the channel with
    :attr:`~quoss.channel.turbulence.ScintillationRegime.MODERATE_TO_STRONG`
    instead of ``WEAK``, at the station's real altitude and the 10 degree mask.
    Everything else — orbit, geometry, pass table, protocol, security — is held.

    ==============  ==========  ==========  ==========  ==========
    station         culminates  `dx` (T)    `E`         `dy` (key)
    ==============  ==========  ==========  ==========  ==========
    Castelldefels    26 deg      +7.90 %     0.473       +3.66 %
    Calar Alto       21-37 deg   +3.05 %     2.91        +9.12 %
    Teide OGS        57-72 deg   +1.78 %     0.673       +1.20 %
    ==============  ==========  ==========  ==========  ==========

    What the split says, and it is not what the day totals say
    ----------------------------------------------------------
    Read the last column alone and the story is "Calar Alto benefits most from
    the new scintillation model". That is false as a statement about the
    channel: **Castelldefels' channel gains two and a half times more** than
    Calar Alto's, 7.90 % against 3.05 %, because its passes are the lowest in
    the sky and saturation only touches low-elevation samples.

    The key ranking is the other way round because of `E`. Calar Alto sits on
    the certification cliff — it certifies about 1 % and 4.5 % of its two
    passes' asymptotic key — so one per cent of transmittance buys it 2.91 % of
    key. Castelldefels and the Teide are off the cliff and their `E` is *below*
    one: there, a brighter channel buys proportionally **less** key, because the
    finite-key bound's leakage term grows with the detections the extra light
    brings.

    So the honest sentence is: the scintillation model is worth 1.8 % to 7.9 %
    of channel, everywhere, and between 1.2 % and 9.1 % of key depending on how
    close the station's passes sit to the cliff. Those are two different
    statements about two different things, and only the first one is about
    turbulence.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG

    @staticmethod
    def _factors(name: str, pass_index: int | None = None) -> tuple[float, float, float]:
        """Return `(dx, E, dy)` for swapping the regime, at the station's own altitude."""
        altitude_m = STATIONS[name][2]
        weak = hand_link(name, station_height_m=altitude_m)
        saturated = hand_link(
            name,
            station_height_m=altitude_m,
            regime=TestWhatTheSaturatedModelIsWorth.SATURATED,
        )
        d_x = mean_log_transmittance(saturated, pass_index) - mean_log_transmittance(
            weak, pass_index
        )
        if pass_index is None:
            weak_bits = float(np.asarray(weak.finite.key_bits).sum())
            saturated_bits = float(np.asarray(saturated.finite.key_bits).sum())
        else:
            weak_bits = float(np.asarray(weak.finite.key_bits)[pass_index])
            saturated_bits = float(np.asarray(saturated.finite.key_bits)[pass_index])
        d_y = float(np.log(saturated_bits / weak_bits))
        return d_x, d_y / d_x, d_y

    def test_the_channel_gain_is_largest_at_the_station_with_the_lowest_passes(self) -> None:
        """`dx`: +7.90 % at Castelldefels, +3.05 % at Calar Alto, +1.78 % at the Teide.

        Ordered by how low the passes are, not by altitude and not by key. This
        is the half of the effect that is turbulence, and it is monotone in the
        thing that drives it.
        """
        gains = {name: np.expm1(self._factors(name)[0]) for name in STATIONS}
        assert gains["castelldefels"] == pytest.approx(0.0790, abs=5e-4)
        assert gains["calar_alto"] == pytest.approx(0.0305, abs=5e-4)
        assert gains["tenerife_ogs"] == pytest.approx(0.0178, abs=5e-4)
        assert gains["castelldefels"] > gains["calar_alto"] > gains["tenerife_ogs"]

    def test_the_key_gain_is_largest_at_the_station_on_the_cliff(self) -> None:
        """`dy`: +9.12 % at Calar Alto against +3.66 % and +1.20 %. The opposite order."""
        gains = {name: np.expm1(self._factors(name)[2]) for name in STATIONS}
        assert gains["calar_alto"] == pytest.approx(0.0912, abs=1e-3)
        assert gains["castelldefels"] == pytest.approx(0.0366, abs=1e-3)
        assert gains["tenerife_ogs"] == pytest.approx(0.0120, abs=1e-3)
        assert gains["calar_alto"] > gains["castelldefels"] > gains["tenerife_ogs"]

    def test_the_two_orderings_disagree_and_the_elasticity_is_why(self) -> None:
        """The whole point of the decomposition, as one assertion.

        Castelldefels' channel gains 2.6 times more than Calar Alto's and its
        key gains 2.5 times less. Both statements are true, they are not in
        tension, and the ratio between them is the ratio of the two
        elasticities, 2.91 / 0.473 = 6.15.
        """
        low_x, low_e, low_y = self._factors("castelldefels")
        cliff_x, cliff_e, cliff_y = self._factors("calar_alto")
        assert low_x / cliff_x == pytest.approx(2.53, abs=0.05)
        assert cliff_y / low_y == pytest.approx(2.43, abs=0.05)
        assert cliff_e / low_e == pytest.approx(6.15, abs=0.2)
        assert (cliff_e / low_e) / (low_x / cliff_x) == pytest.approx(cliff_y / low_y, rel=1e-9)

    def test_off_the_cliff_a_brighter_channel_buys_less_than_proportionally(self) -> None:
        """`E < 1` at two of the three stations, which a rate-based intuition forbids.

        If key were a rate, `E` would be 1 by definition: one per cent more
        light, one per cent more key. It is 0.473 and 0.673 here, because error
        correction is charged on every detection the extra light brings while
        privacy amplification certifies only the single-photon part of them. The
        finite-key bound is not a rate, and this is the cheapest measurement in
        the project that says so.
        """
        assert self._factors("castelldefels")[1] == pytest.approx(0.473, abs=0.02)
        assert self._factors("tenerife_ogs")[1] == pytest.approx(0.673, abs=0.02)
        assert self._factors("calar_alto")[1] == pytest.approx(2.91, abs=0.05)

    def test_the_worst_pass_of_the_day_amplifies_by_six_and_a_half(self) -> None:
        """Calar Alto's second pass: +2.50 % of channel becomes +17.7 % of key.

        The single largest number stage 1.2 produces anywhere in the reference
        day, and it is almost entirely the bound. Quoting it without `E` beside
        it would be reporting the security proof as if it were the atmosphere.
        """
        d_x, elasticity, d_y = self._factors("calar_alto", 2)
        assert float(np.expm1(d_x)) == pytest.approx(0.0250, abs=5e-4)
        assert elasticity == pytest.approx(6.60, abs=0.1)
        assert float(np.expm1(d_y)) == pytest.approx(0.177, abs=3e-3)

    def test_no_pass_crosses_from_zero_to_some(self) -> None:
        """Nothing was resurrected, at this mask: the effect is on passes that already certified.

        Worth asserting because it is the first thing the decomposition would
        break on — `ln(key)` is undefined at zero, so a pass crossing would make
        `E` meaningless rather than large, and the tables above would silently
        be measuring a different set of passes in each column.
        """
        for name in STATIONS:
            altitude_m = STATIONS[name][2]
            weak = np.asarray(hand_link(name, station_height_m=altitude_m).finite.key_bits)
            saturated = np.asarray(
                hand_link(name, station_height_m=altitude_m, regime=self.SATURATED).finite.key_bits
            )
            assert ((weak > 0.0) == (saturated > 0.0)).all(), name


class TestTheScenarioChoosesTheRegime:
    """**Stage 1.2, wired.** The regime reaches `run()`, and `run()` reproduces the hand chain.

    What was missing, and why it mattered
    -------------------------------------
    `ScintillationRegime` and `saturated_log_irradiance_variance` landed in
    `quoss.channel.turbulence` with ADR 0022, and
    `TestWhatTheSaturatedModelIsWorth` above measures what they are worth. Every
    one of those measurements was made by **calling the channel by hand**:
    `ChannelSpec` had no field for the choice and `engine.pipeline` passed none,
    so `run()` could only ever produce the ``WEAK`` column. A result that cannot
    express the model it used is a result whose number is not traceable to its
    inputs, which is what `docs/adr/0014-scenario-contract-and-provenance.md`
    exists to prevent.

    `ChannelSpec.scintillation_regime` closes it, and this class is the proof
    that wiring a field is not the same as computing a new number: the engine's
    saturated day has to be the hand chain's saturated day, bit for bit, the
    same way its weak day already was.

    The reference day, both ways
    ----------------------------
    Same orbit, same station, same 10 degree mask, same protocol; the only
    difference is the field.

    ==================  ===============  ==================  ========
    regime              day (bits)       passes 1 and 3      change
    ==================  ===============  ==================  ========
    ``weak``            433 442          190 807 / 242 635   --
    ``moderate-to-strong``  449 308      198 673 / 250 635   +3.66 %
    ==================  ===============  ==================  ========

    Two passes of the four certify nothing in either column, which is
    ``docs/adr/0011-the-block-is-the-pass.md``'s cliff and not a change here.

    And the choice is in the hash, which is the point
    -------------------------------------------------
    The field enters `canonical_json`, so the two runs have different scenario
    hashes and therefore different `Provenance.scenario_hash` and different
    cache entries. A 3.66 % difference that shared an entry would be the worst
    kind of cache: correct, fast, and about the wrong physics.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG
    SATURATED_FINITE_BITS = (198_673.0, 0.0, 250_635.0, 0.0)
    SATURATED_FINITE_DAY_BITS = 449_308.0
    SATURATED_ASYMPTOTIC_DAY_BITS = 3_904_383.4674895606
    """Compared through `assert_matches_literal`, like `ENGINE_ASYMPTOTIC_DAY_BITS`."""

    @staticmethod
    def _scenario(regime: ScintillationRegime) -> Scenario:
        """Return the reference scenario with only the regime replaced."""
        scenario = reference_castelldefels()
        channel = scenario.channel
        return scenario.model_copy(
            update={
                "channel": ChannelSpec(
                    zenith_transmittance=channel.zenith_transmittance,
                    static_loss_db=channel.static_loss_db,
                    outage_probability=channel.outage_probability,
                    fade_combination=channel.fade_combination,
                    scintillation_regime=regime,
                )
            }
        )

    def test_the_default_is_weak_and_saying_so_changes_nothing(self) -> None:
        """A scenario that declares ``weak`` is the scenario that says nothing.

        Not only the same numbers: the same *hash*, which is the stronger claim
        and the one that keeps every result written before this field existed
        reachable in the cache it was written to.
        """
        assert ChannelSpec.model_fields["scintillation_regime"].default is (
            ScintillationRegime.WEAK
        )
        declared = self._scenario(ScintillationRegime.WEAK)
        assert scenario_hash(declared) == scenario_hash(reference_castelldefels())
        result = run_scenario(declared)
        assert_identical(
            np.asarray(result.passes.finite_bits), np.asarray(ENGINE_FINITE_BITS), "weak finite"
        )
        assert float(np.asarray(result.daily.finite_bits)[0]) == ENGINE_FINITE_DAY_BITS

    def test_the_saturated_run_is_the_hand_chain_term_by_term(self) -> None:
        """Every loss term, not only the total, and then the key the protocol read.

        `TestTheEngineAddsNothing` makes this claim for the default regime; a
        new argument is exactly the kind of change that makes it stop being
        true for one branch while staying true for the other, so the branch
        gets its own copy rather than a spot check on the day total.
        """
        engine_run = simulate(self._scenario(self.SATURATED), degradations=DegradationLog())
        station = engine_run.stations[0]
        by_hand = hand_link(
            "castelldefels", station_height_m=CASTELLDEFELS_HEIGHT_M, regime=self.SATURATED
        )
        assert station.loss is not None and station.conditions is not None
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
                getattr(station.loss, field),
                getattr(by_hand.loss, field),
                f"saturated loss.{field}",
            )
        assert_identical(
            station.conditions.transmittance,
            by_hand.conditions.transmittance,
            "saturated conditions.transmittance",
        )
        assert_identical(
            station.finite.key_bits, by_hand.finite.key_bits, "saturated finite.key_bits"
        )
        assert_identical(
            station.asymptotic.key_bits,
            by_hand.asymptotic.key_bits,
            "saturated asymptotic.key_bits",
        )

    def test_the_saturated_day_the_engine_now_reports(self) -> None:
        """449 308 bits, +3.66 % on the weak day, and the asymptotic figure with it."""
        result = run_scenario(self._scenario(self.SATURATED))
        assert tuple(np.asarray(result.passes.finite_bits).tolist()) == self.SATURATED_FINITE_BITS
        assert float(np.asarray(result.daily.finite_bits)[0]) == self.SATURATED_FINITE_DAY_BITS
        assert self.SATURATED_FINITE_DAY_BITS / ENGINE_FINITE_DAY_BITS - 1.0 == pytest.approx(
            0.0366, abs=5e-4
        )
        by_hand = hand_link(
            "castelldefels", station_height_m=CASTELLDEFELS_HEIGHT_M, regime=self.SATURATED
        )
        assert_matches_literal(
            float(np.asarray(result.daily.asymptotic_bits)[0]),
            self.SATURATED_ASYMPTOTIC_DAY_BITS,
            relative_bound=cross_platform_relative_bound(by_hand),
            what="saturated asymptotic day",
        )

    def test_the_two_regimes_are_two_scenarios_and_cannot_share_a_cache_entry(
        self, tmp_path: Path
    ) -> None:
        """The provenance half of the wiring, and it is not a formality.

        The cache is keyed on the scenario hash, so a field the hash did not see
        would make the saturated run collide with the weak one: the second run
        would return the first one's arrays, 3.66 % away, with a `Provenance`
        that named the right scenario.
        """
        weak, saturated = self._scenario(ScintillationRegime.WEAK), self._scenario(self.SATURATED)
        assert scenario_hash(weak) != scenario_hash(saturated)
        cache = ResultCache(tmp_path)
        stored = run_scenario(weak)
        assert stored.provenance.scenario_hash == scenario_hash(weak)
        cache.put(stored, degradations=DegradationLog())
        assert cache.get(weak, seed=None, degradations=DegradationLog()) is not None
        assert cache.get(saturated, seed=None, degradations=DegradationLog()) is None

    @pytest.mark.parametrize(
        ("regime", "code"),
        [
            (ScintillationRegime.WEAK, "turbulence.weak-fluctuation-limit-exceeded"),
            (SATURATED, "turbulence.scintillation-saturated"),
        ],
    )
    def test_whichever_is_chosen_the_run_says_so_and_names_the_other(
        self, regime: ScintillationRegime, code: str
    ) -> None:
        """Neither branch is silent, and each warning names the model it did not use.

        The reference day crosses 1 Np^2 of Rytov variance near the horizon
        whichever model is selected, so both runs have something to report:
        ``weak`` reports that it is past its own validity limit, ``saturated``
        reports that it replaced a value and by how much. A run that chose a
        model and said nothing would be the silent degradation this project
        forbids.
        """
        warnings = [w for w in run_scenario(self._scenario(regime)).warnings if w["code"] == code]
        assert len(warnings) == 1
        assert "ScintillationRegime." in warnings[0]["message"]
        assert float(warnings[0]["details"]["peak_variance_np2"]) > 0.0

    def test_the_saturated_engine_run_never_reports_less_key_than_the_weak_one(self) -> None:
        """V1, per pass and per day: the only sign the wiring is allowed to have.

        Saturation can only lower a variance, a lower variance can only lower a
        fade allowance and a lower allowance can only raise a transmittance. A
        pass that lost key would mean the argument reached something other than
        the scintillation model.
        """
        weak = run_scenario(self._scenario(ScintillationRegime.WEAK))
        saturated = run_scenario(self._scenario(self.SATURATED))
        assert np.all(
            np.asarray(saturated.passes.finite_bits) >= np.asarray(weak.passes.finite_bits)
        )
        assert np.all(
            np.asarray(saturated.passes.asymptotic_bits) >= np.asarray(weak.passes.asymptotic_bits)
        )


class TestTheFourHundredAndFiftySevenBitsChangeSignUnderSaturation:
    """The 457 bits of `TestTheFourHundredAndFiftySevenBits`, recomputed in the other regime.

    The claim being checked
    -----------------------
    `StationSpec.altitude_m` starts the turbulence profile 30 m up at
    Castelldefels, and that is worth **+457 bits** (+0.106 %) on the reference
    day under ``WEAK``: less air above the telescope, less scintillation, more
    key. The obvious expectation is that the same 30 m is worth a little
    *something* under the saturated model too, since it is the same air.

    It is not. Under ``MODERATE_TO_STRONG`` the same 30 m is worth **-206
    bits**: 449 514 at sea level against 449 308 at the station's own height.
    The sign flips, and that is a fact about the two models rather than about
    the plumbing, which is why it is measured here rather than explained away.

    Why the sign flips, in the two factors that make the variance
    -------------------------------------------------------------
    The downlink variance is a product, ITU-R P.1622 equation (8)::

        sigma^2 = A * sigma^2_point

    Raising the station moves both factors, in **opposite** directions:

    - ``sigma^2_point`` falls, because the first 30 m of air leave the path. At
      10 degrees elevation, 1.5446 -> 1.4780 Np^2, **-4.31 %**.
    - ``A``, the aperture averaging factor, **rises**: 0.072572 -> 0.075102,
      **+3.49 %**. A is equation (7)'s suppression of flicker by a telescope
      wider than the speckles, and it is set by the *height* of the turbulence,
      through the ``z_0`` of equation (9). Start the profile higher and the
      weighted turbulence sits further away, the speckles at the ground are
      larger, and a 0.75 m telescope averages fewer of them.

    Under ``WEAK`` the first factor moves the full 4.31 % and wins: the product
    falls 0.97 % and the day gains 457 bits. Under saturation the first factor
    is **compressed** — the saturated point variance falls only from 0.63542 to
    0.62602, **-1.48 %**, because near saturation a change in the Rytov variance
    mostly does not reach the output — while ``A`` rises by the same 3.49 %. The
    product now *rises* 1.96 %, and the day loses 206 bits.

    The crossing is at 27.02 degrees of elevation: above it the saturated
    variance still falls with height, below it, it rises. The reference day
    spends **67.7 % of its in-pass seconds below that crossing** (median
    elevation 17.4 degrees), because a pass spends most of its duration near
    the horizon, and those are exactly the samples whose fade allowance is
    largest. So the day total inherits the sign of the low samples rather than
    averaging the two signs away.

    What it does not say
    --------------------
    It does not say a mountain is a bad place for a telescope. 30 m is 30 m; the
    gap 21 of ADR 0009 -- aperture averaging in the saturated regime is P.1622's
    convention applied to a variance Ntanos et al. define as a ratio of indices
    -- is exactly the modelling choice this sign depends on, and it is declared
    open. What it says is that the two regimes are two models, and a quantity
    measured in one of them does not carry over to the other even in sign.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG
    SATURATED_SEA_LEVEL_DAY_BITS = 449_514.0
    SATURATED_STATION_DAY_BITS = 449_308.0

    @staticmethod
    def _day(height_m: float, regime: ScintillationRegime) -> float:
        return float(
            np.asarray(
                hand_link("castelldefels", station_height_m=height_m, regime=regime).finite.key_bits
            ).sum()
        )

    @staticmethod
    def _downlink_variance(
        elevation_deg: float, height_m: float, regime: ScintillationRegime
    ) -> float:
        return float(
            downlink_log_irradiance_variance(
                float(np.deg2rad(elevation_deg)),
                aperture_diameter_m=0.75,
                wavelength_m=WAVELENGTH_M,
                degradations=DegradationLog(),
                station_height_m=height_m,
                regime=regime,
            )
        )

    def test_the_term_is_worth_plus_four_hundred_and_fifty_seven_bits_and_minus_two_hundred_and_six(
        self,
    ) -> None:
        """The headline, both regimes, from the same hand chain with one argument changed."""
        weak_gain = self._day(CASTELLDEFELS_HEIGHT_M, ScintillationRegime.WEAK) - self._day(
            0.0, ScintillationRegime.WEAK
        )
        saturated_gain = self._day(CASTELLDEFELS_HEIGHT_M, self.SATURATED) - self._day(
            0.0, self.SATURATED
        )
        assert weak_gain == 457.0
        assert saturated_gain == -206.0
        assert self._day(0.0, self.SATURATED) == self.SATURATED_SEA_LEVEL_DAY_BITS
        assert self._day(CASTELLDEFELS_HEIGHT_M, self.SATURATED) == self.SATURATED_STATION_DAY_BITS

    def test_the_point_variance_falls_at_both_heights_and_saturation_compresses_the_fall(
        self,
    ) -> None:
        """-4.31 % of Rytov variance becomes -1.48 % once saturated. The first factor."""
        log = DegradationLog()
        point = {
            (height, regime): float(
                log_irradiance_variance(
                    float(np.deg2rad(10.0)),
                    wavelength_m=WAVELENGTH_M,
                    degradations=log,
                    station_height_m=height,
                    regime=regime,
                )
            )
            for height in (0.0, CASTELLDEFELS_HEIGHT_M)
            for regime in (ScintillationRegime.WEAK, self.SATURATED)
        }
        weak_fall = (
            point[(CASTELLDEFELS_HEIGHT_M, ScintillationRegime.WEAK)]
            / point[(0.0, ScintillationRegime.WEAK)]
            - 1.0
        )
        saturated_fall = (
            point[(CASTELLDEFELS_HEIGHT_M, self.SATURATED)] / point[(0.0, self.SATURATED)] - 1.0
        )
        assert weak_fall == pytest.approx(-0.0431, abs=5e-4)
        assert saturated_fall == pytest.approx(-0.0148, abs=5e-4)
        assert saturated_fall > weak_fall

    def test_the_aperture_averaging_factor_rises_with_the_station_in_both_regimes(self) -> None:
        """+3.49 %, and it does not depend on the regime at all. The second factor.

        `aperture_averaging_factor` takes no regime: the saturation model
        changes the point variance and nothing else, so this factor is shared.
        That is what makes the two effects separable and the sign flip
        attributable.
        """
        factors = [
            float(
                aperture_averaging_factor(
                    float(np.deg2rad(10.0)),
                    aperture_diameter_m=0.75,
                    wavelength_m=WAVELENGTH_M,
                    station_height_m=height,
                )
            )
            for height in (0.0, CASTELLDEFELS_HEIGHT_M)
        ]
        assert factors[1] / factors[0] - 1.0 == pytest.approx(0.0349, abs=5e-4)
        assert "regime" not in inspect.signature(aperture_averaging_factor).parameters

    def test_the_product_therefore_falls_under_weak_and_rises_under_saturation(self) -> None:
        """-0.97 % against +1.96 % at 10 degrees: the sign flip, before any key is computed."""
        weak = [
            self._downlink_variance(10.0, height, ScintillationRegime.WEAK)
            for height in (0.0, CASTELLDEFELS_HEIGHT_M)
        ]
        saturated = [
            self._downlink_variance(10.0, height, self.SATURATED)
            for height in (0.0, CASTELLDEFELS_HEIGHT_M)
        ]
        assert weak[1] / weak[0] - 1.0 == pytest.approx(-0.0097, abs=5e-4)
        assert saturated[1] / saturated[0] - 1.0 == pytest.approx(+0.0196, abs=5e-4)

    def test_the_crossing_sits_above_most_of_the_days_seconds(self) -> None:
        """27.02 degrees, found by bisection on the difference rather than read off a table.

        Two thirds of the day's in-pass seconds are below it, so the day total
        inherits the sign of the low samples instead of averaging the two signs
        away. The bisection is written out rather than imported from scipy
        because what is being asserted is the *location* of a sign change, and a
        root finder that silently returned an endpoint would assert nothing.
        """

        def difference(elevation_deg: float) -> float:
            return self._downlink_variance(
                elevation_deg, CASTELLDEFELS_HEIGHT_M, self.SATURATED
            ) - self._downlink_variance(elevation_deg, 0.0, self.SATURATED)

        low, high = 20.0, 40.0
        assert difference(low) > 0.0 > difference(high)
        for _ in range(60):
            middle = 0.5 * (low + high)
            if difference(middle) > 0.0:
                low = middle
            else:
                high = middle
        crossing = 0.5 * (low + high)
        assert crossing == pytest.approx(27.02, abs=0.01)
        link = hand_link("castelldefels", station_height_m=CASTELLDEFELS_HEIGHT_M)
        rows = (np.asarray(link.samples.satellite_index), np.asarray(link.samples.sample_index))
        elevation_deg = np.rad2deg(np.asarray(link.angles.elevation_rad)[rows])
        dwell_s = np.asarray(link.samples.dwell_s)
        below = elevation_deg < crossing
        assert float(dwell_s[below].sum() / dwell_s.sum()) == pytest.approx(0.677, abs=5e-3)
        assert float(np.median(elevation_deg)) == pytest.approx(17.4, abs=0.1)


class TestWhatTheExtinctionModelIsWorth:
    """**Stage 1.1.** The term the budget used to receive, priced by the same split.

    Every scenario in ``scenarios/`` declares ``zenith_transmittance: 1.0`` —
    honestly, because ``docs/adr/0009-citation-policy.md`` gap 14 had no number
    to offer — so every figure this project has produced is for an atmosphere
    that does not absorb or scatter. ``docs/adr/0023-traceable-extinction.md``
    gives it a model, and this class is what that costs on the reference day.

    The intervention is the third one through the same machinery
    ------------------------------------------------------------
    `x = mean(ln T)` and `y = ln(key bits)` as in
    `TestWhyTheHigherStationGainsLess` (which moved the station up a mountain)
    and `TestWhatTheSaturatedModelIsWorth` (which changed the scintillation
    model). Here the intervention is switching ``zenith_transmittance`` from
    1.0 to what :mod:`quoss.channel.extinction` returns for a stated visibility,
    everything else held.

    ==================================  ==========  ==========  ==========
    air over Castelldefels              `dx` (T)    `E`         `dy` (key)
    ==================================  ==========  ==========  ==========
    23 km, "very clear air"             -15.6 %      1.52        -22.7 %
    10 km, "clear"                      -32.3 %      1.67        -47.7 %
    2 km, "light mist"                  -97.7 %      -           -100 %
    ==================================  ==========  ==========  ==========

    What it says
    ------------
    **A quarter of a decibel at zenith is a fifth of the day.** 23 km of
    visibility is the clearest line in ITU-R P.1817-1's own weather code, and it
    is 0.230 dB straight up — and 22.7 % of the certified key, because `E` is
    1.52 rather than 1. The same station showed `E = 0.473` for a scintillation
    *gain* in `TestWhatTheSaturatedModelIsWorth`, so the elasticity is not a
    property of the station: it is a local derivative of a bound with a floor at
    zero, and it is measured here over a step eight times larger and in the
    other direction. Reporting either figure as "Castelldefels' elasticity"
    would be reporting a tangent as a constant.

    **At 2 km of visibility the day certifies nothing**, while the asymptotic
    figure still claims 424 kbit. That is the unbounded-error pattern of
    ``docs/adr/0011-the-block-is-the-pass.md`` again: the ratio between what the
    two regimes report is not a factor, it is a division by zero.

    **And infinite visibility reproduces the old numbers to the bit**, which is
    what makes the model safe to introduce: a scenario that declares no
    extinction and a scenario that models infinitely clear air are the same run.
    """

    VERY_CLEAR_KM = 23.0
    CLEAR_KM = 10.0
    LIGHT_MIST_KM = 2.0
    SCALE_HEIGHT_M = 1200.0
    """1.2 km. The thin end of the literature's spread (ADR 0009 gap 22)."""

    @staticmethod
    def _zenith(visibility_km: float, scale_height_m: float = 1200.0) -> float:
        """``L_zen`` at Castelldefels for a locally measured visibility."""
        return float(
            zenith_transmittance_from_visibility(
                visibility_km,
                wavelength_m=WAVELENGTH_M,
                aerosol_scale_height_m=scale_height_m,
                station_altitude_m=CASTELLDEFELS_HEIGHT_M,
                visibility_altitude_m=CASTELLDEFELS_HEIGHT_M,
                law=VisibilityScalingLaw.KIM_2001,
                degradations=DegradationLog(),
            )
        )

    @classmethod
    def _factors(cls, visibility_km: float) -> tuple[float, float, float]:
        """Return `(dx, E, dy)` for switching from no extinction to this air."""
        clear = hand_link("castelldefels", station_height_m=CASTELLDEFELS_HEIGHT_M)
        hazy = hand_link(
            "castelldefels",
            station_height_m=CASTELLDEFELS_HEIGHT_M,
            zenith_transmittance=cls._zenith(visibility_km),
        )
        d_x = mean_log_transmittance(hazy, None) - mean_log_transmittance(clear, None)
        d_y = float(
            np.log(
                float(np.asarray(hazy.finite.key_bits).sum())
                / float(np.asarray(clear.finite.key_bits).sum())
            )
        )
        return d_x, d_y / d_x, d_y

    def test_the_zenith_losses_of_the_three_airs(self) -> None:
        """0.230, 0.530 and 5.142 dB — the model's own output, stated first."""
        losses = {
            v: -10.0 * float(np.log10(self._zenith(v)))
            for v in (self.VERY_CLEAR_KM, self.CLEAR_KM, self.LIGHT_MIST_KM)
        }
        assert losses[self.VERY_CLEAR_KM] == pytest.approx(0.2304, abs=5e-4)
        assert losses[self.CLEAR_KM] == pytest.approx(0.5299, abs=5e-4)
        assert losses[self.LIGHT_MIST_KM] == pytest.approx(5.142, abs=5e-3)

    def test_the_clearest_air_in_the_itu_weather_code_costs_a_fifth_of_the_day(self) -> None:
        d_x, elasticity, d_y = self._factors(self.VERY_CLEAR_KM)
        assert float(np.expm1(d_x)) == pytest.approx(-0.1558, abs=2e-3)
        assert float(np.expm1(d_y)) == pytest.approx(-0.2274, abs=2e-3)
        assert elasticity == pytest.approx(1.523, abs=0.02)

    def test_clear_air_costs_half_of_it(self) -> None:
        d_x, elasticity, d_y = self._factors(self.CLEAR_KM)
        assert float(np.expm1(d_x)) == pytest.approx(-0.3227, abs=2e-3)
        assert float(np.expm1(d_y)) == pytest.approx(-0.4772, abs=3e-3)
        assert elasticity == pytest.approx(1.665, abs=0.02)

    def test_light_mist_certifies_nothing_while_the_asymptote_still_claims_a_day(self) -> None:
        """A ratio would be a division by zero, so the two numbers are stated apart."""
        hazy = hand_link(
            "castelldefels",
            station_height_m=CASTELLDEFELS_HEIGHT_M,
            zenith_transmittance=self._zenith(self.LIGHT_MIST_KM),
        )
        assert float(np.asarray(hazy.finite.key_bits).sum()) == 0.0
        assert float(np.asarray(hazy.asymptotic.key_bits).sum()) == pytest.approx(
            424_461.0, rel=2e-3
        )

    def test_the_engine_reproduces_the_hand_chain_through_the_schema(self) -> None:
        """The whole point of wiring it: `run()` and the hand chain, to the bit.

        The engine resolves the transmittance from
        :class:`~quoss.scenario.models.ExtinctionSpec` per station; the hand
        chain is handed the number. They have to be the same run.
        """
        scenario = reference_castelldefels()
        modelled = scenario.model_copy(
            update={
                "channel": ChannelSpec(
                    extinction=ExtinctionSpec(
                        visibility_km=self.VERY_CLEAR_KM,
                        visibility_altitude_m=CASTELLDEFELS_HEIGHT_M,
                        aerosol_scale_height_m=self.SCALE_HEIGHT_M,
                        scaling_law=VisibilityScalingLaw.KIM_2001,
                    ),
                    static_loss_db=scenario.channel.static_loss_db,
                    outage_probability=scenario.channel.outage_probability,
                    fade_combination=scenario.channel.fade_combination,
                )
            }
        )
        result = run_scenario(modelled)
        expected = hand_link(
            "castelldefels",
            station_height_m=CASTELLDEFELS_HEIGHT_M,
            zenith_transmittance=self._zenith(self.VERY_CLEAR_KM),
        )
        assert_identical(
            np.asarray(result.passes.finite_bits),
            np.asarray(expected.finite.key_bits),
            "modelled-extinction finite bits",
        )
        assert float(np.asarray(result.daily.finite_bits)[0]) == 334_883.0

    def test_declaring_no_extinction_and_modelling_infinite_visibility_are_one_run(self) -> None:
        """The identity that makes this safe to land: bit-for-bit, not nearly.

        A visibility of 1e300 km gives exactly 1.0 — the law's ``3.91/V`` is a
        true zero, not an underflow — so the modelled scenario and the declared
        one take the same branch of every subsequent floating-point operation.
        `ENGINE_FINITE_DAY_BITS` is unmoved, which is why the 3 600 assertions
        in this file did not have to be rewritten.
        """
        scenario = reference_castelldefels()
        modelled = scenario.model_copy(
            update={
                "channel": ChannelSpec(
                    extinction=ExtinctionSpec(
                        visibility_km=1e300,
                        visibility_altitude_m=CASTELLDEFELS_HEIGHT_M,
                        aerosol_scale_height_m=self.SCALE_HEIGHT_M,
                        scaling_law=VisibilityScalingLaw.KIM_2001,
                    ),
                    static_loss_db=scenario.channel.static_loss_db,
                    outage_probability=scenario.channel.outage_probability,
                    fade_combination=scenario.channel.fade_combination,
                )
            }
        )
        assert (
            modelled.channel.zenith_transmittance_at(
                wavelength_m=WAVELENGTH_M,
                station_altitude_m=CASTELLDEFELS_HEIGHT_M,
                degradations=DegradationLog(),
            )
            == 1.0
        )
        result = run_scenario(modelled)
        assert_identical(
            np.asarray(result.passes.finite_bits),
            np.asarray(ENGINE_FINITE_BITS),
            "infinite-visibility finite bits",
        )
        assert float(np.asarray(result.daily.finite_bits)[0]) == ENGINE_FINITE_DAY_BITS


class TestTheMaskSweepInBothRegimes:
    """**Stage 1.2's design finding**, produced by `run_sweep` instead of by hand.

    What is being closed
    --------------------
    ADR 0022's headline is that saturating the scintillation moves the elevation
    mask's interior optimum from **8 degrees to 4.5** and the reference day's
    certified key by **+6.4 %**. That table was built by calling the channel,
    the pass table and the protocol by hand, one mask at a time, because
    ``ChannelSpec`` had no field for the regime. A design finding that only a
    hand-written script can reproduce is a finding nobody can re-run against a
    scenario file, which is what `quoss.engine.sweep` exists to prevent
    (its module docstring: "a figure in a paper is almost always a sweep").

    Now the regime is a scenario field, so it is also a **sweep axis**: the
    eight cells below are one `SweepSpec` over two dotted paths, ``grid`` mode,
    and the row that produced each one carries its own scenario hash.

    ============  ===============  ==================  ========
    mask (deg)    ``weak``         saturated           change
    ============  ===============  ==================  ========
    2             409 584          458 076             +11.8 %
    4.5           425 073          **462 358**         +8.8 %
    8             **435 462**      457 341             +5.0 %
    20            361 199          364 774             +1.0 %
    ============  ===============  ==================  ========

    Why these are not the numbers ADR 0022 prints, and what the tolerance is
    ------------------------------------------------------------------------
    ADR 0022 prints 408 946 / 424 448 / 434 938 / 360 978 and 458 862 / 462 945
    / 457 663 / 364 740, up to 786 bits away. **The difference is not a
    tolerance and it is not noise**: it is the 30 m of `StationSpec.altitude_m`
    reaching the turbulence profile, the same discrepancy
    `TestTheFourHundredAndFiftySevenBits` exists for. The ADR's table comes from
    `tests/system/reference.py`, which leaves the profile at 0 m.

    So nothing here is compared with a fitted tolerance. The two ends are
    reproduced **exactly**, from one hand chain with one argument changed:

    - the eight swept cells equal `oracle.hand_link` at 30 m, bit for bit;
    - the eight published cells equal the same chain at 0 m, bit for bit;
    - therefore every residual equals ``hand(30 m) - hand(0 m)`` exactly, cell
      by cell, and there is nothing left over for a tolerance to absorb.

    That residual changes sign between the regimes — ``+638`` bits at 2 degrees
    under ``weak``, ``-786`` under saturation — which is not a mistake either;
    `TestTheFourHundredAndFiftySevenBitsChangeSignUnderSaturation` measures why.

    What survives the change of chain
    ---------------------------------
    Both optima, which is what the ADR claims: 8 degrees under ``weak``, 4.5
    under saturation, both interior. And the gain is monotone in how low the
    mask is, +11.8 % at 2 degrees against +1.0 % at 20, which is the signature
    of an effect that lives entirely in the low samples.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG
    REGIME_PATH = "channel.scintillation_regime"
    MASK_PATH = "passes.minimum_elevation_deg"

    @staticmethod
    def _hand(mask_deg: float, regime: ScintillationRegime, height_m: float) -> float:
        """Return the day's finite key from the hand chain, at one mask, regime and height."""
        link = hand_link(
            "castelldefels", mask_deg=mask_deg, station_height_m=height_m, regime=regime
        )
        return float(np.asarray(link.finite.key_bits).sum())

    def test_the_sweep_runs_both_regimes_as_one_grid(self, mask_regime_sweep: SweepResult) -> None:
        """Eight rows, two axes, and a distinct scenario hash on every one of them."""
        rows = mask_regime_sweep.to_records()
        assert len(rows) == 8
        assert tuple(mask_regime_sweep.column(self.MASK_PATH)) == (
            2.0,
            2.0,
            4.5,
            4.5,
            8.0,
            8.0,
            20.0,
            20.0,
        )
        assert len({row["scenario_hash"] for row in rows}) == 8

    def test_every_swept_cell_is_the_hand_chain_at_the_stations_own_height(
        self, mask_regime_sweep: SweepResult
    ) -> None:
        """The exact half of the claim: ``==``, through the sweep's JSON round trip.

        `run_sweep` dumps the scenario, edits a dotted path and revalidates, so
        this also checks that a regime written as a string survives that trip
        as the same physics.
        """
        for row in mask_regime_sweep.to_records():
            mask = float(row[self.MASK_PATH])
            regime = ScintillationRegime(row[self.REGIME_PATH])
            assert row["daily.finite_bits"] == ENGINE_MASK_SWEEP_BITS[(mask, regime)]
            assert row["daily.finite_bits"] == self._hand(mask, regime, CASTELLDEFELS_HEIGHT_M)

    def test_the_published_table_is_the_same_chain_at_sea_level(self) -> None:
        """The other exact half: ADR 0022's eight cells, reproduced to the bit."""
        for (mask, regime), published in STAGE_ONE_TWO_HAND_TABLE.items():
            assert self._hand(mask, regime, 0.0) == published

    def test_the_whole_residual_is_the_profile_height_and_nothing_else(
        self, mask_regime_sweep: SweepResult
    ) -> None:
        """No tolerance: the difference is an identity, cell by cell.

        A tolerance chosen to cover 786 bits would also cover a real 700-bit
        change in the physics, which is the failure mode
        ``notes/GUIA_REIMPLEMENTACION.md`` calls a tolerance that cannot fail.
        This asserts the residual **equals** what one argument is worth.
        """
        residuals: dict[tuple[float, ScintillationRegime], float] = {}
        for row in mask_regime_sweep.to_records():
            mask = float(row[self.MASK_PATH])
            regime = ScintillationRegime(row[self.REGIME_PATH])
            residual = row["daily.finite_bits"] - STAGE_ONE_TWO_HAND_TABLE[(mask, regime)]
            assert residual == self._hand(mask, regime, CASTELLDEFELS_HEIGHT_M) - self._hand(
                mask, regime, 0.0
            )
            residuals[(mask, regime)] = residual
        assert residuals.keys() == STAGE_ONE_TWO_HAND_TABLE.keys()
        assert max(abs(residual) for residual in residuals.values()) == 786.0
        assert (
            max(
                abs(residual) / STAGE_ONE_TWO_HAND_TABLE[key] for key, residual in residuals.items()
            )
            < 2e-3
        )
        assert residuals[(2.0, ScintillationRegime.WEAK)] == 638.0
        assert residuals[(2.0, self.SATURATED)] == -786.0

    def test_both_optima_survive_the_change_of_chain(self, mask_regime_sweep: SweepResult) -> None:
        """8 degrees under ``weak``, 4.5 under saturation, both interior.

        This is the sentence ADR 0022 is for, and the first time `run()`
        produces it rather than a script. The day gains **+6.18 %** at its own
        optimum here against the ADR's +6.4 %, and the difference is the same
        30 m as everywhere else in this class.
        """
        table = {
            (float(row[self.MASK_PATH]), ScintillationRegime(row[self.REGIME_PATH])): row[
                "daily.finite_bits"
            ]
            for row in mask_regime_sweep.to_records()
        }
        for regime, expected_best in (
            (ScintillationRegime.WEAK, 8.0),
            (self.SATURATED, 4.5),
        ):
            column = {mask: table[(mask, regime)] for mask in MASK_SWEEP_DEG}
            best = max(column, key=lambda mask: column[mask])
            assert best == expected_best
            assert column[best] > column[MASK_SWEEP_DEG[0]]
            assert column[best] > column[MASK_SWEEP_DEG[-1]]
        gain = table[(4.5, self.SATURATED)] / table[(8.0, ScintillationRegime.WEAK)] - 1.0
        assert gain == pytest.approx(0.0618, abs=5e-4)

    def test_the_gain_is_monotone_in_how_low_the_mask_is(
        self, mask_regime_sweep: SweepResult
    ) -> None:
        """+11.8 % at 2 degrees down to +1.0 % at 20: the effect is the low samples."""
        table = {
            (float(row[self.MASK_PATH]), ScintillationRegime(row[self.REGIME_PATH])): row[
                "daily.finite_bits"
            ]
            for row in mask_regime_sweep.to_records()
        }
        gains = [
            table[(mask, self.SATURATED)] / table[(mask, ScintillationRegime.WEAK)] - 1.0
            for mask in MASK_SWEEP_DEG
        ]
        assert gains == sorted(gains, reverse=True)
        assert gains[0] == pytest.approx(0.1184, abs=5e-4)
        assert gains[-1] == pytest.approx(0.0099, abs=5e-4)


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
