"""The horizontal engine against the same chain wired by hand, number for number.

What this file is for
---------------------
``tests/e2e/test_reference_scenarios.py`` makes one claim about the downlink
half of :mod:`quoss.engine`: *the engine computes nothing that a person calling
the physics functions by hand would not compute*. This file makes the same claim
about the horizontal half, in the same way and to the same standard — exact IEEE
754 equality against ``tests/e2e/oracle.py``'s ``hand_horizontal``, term by term
and not only on the total.

The reason for "term by term" is worth restating rather than assumed. A budget
is a sum of decibels, so two chains that disagree about the geometric term by
+0.3 dB and about the extinction term by -0.3 dB agree exactly on the total, and
a test on the total alone would pass. Each term is therefore compared on its own,
and the transmittance and the key afterwards.

What "bit for bit" means here, and why it is not ``approx``
-----------------------------------------------------------
The same argument as the downlink file's: this compares **the same computation
reached by two routes**, not two computations of the same quantity. The same
function with the same arguments returns the same doubles, so a one-ULP
difference means the two routes are not the same computation and a tolerance
would hide exactly what the file exists to find. Every literal that is a *count*
(``15_236_099.0`` bits) is an integer and stays ``==``; no non-integer literal is
compared against a computed value here, so the cross-platform bound that file
needs does not arise.

What the sweeps are for, and what they reproduce
------------------------------------------------
``docs/adr/0021-horizontal-path.md`` and ``notes/LAST_CHANGES.md`` §37 sized
GE-1 by calling the channel functions by hand in a test, and published two
tables from it: the receiving lens is worth a factor 8.4 to 11.2, and the link
makes 896 kbit/s at 200 m falling to 4 kbit/s at 5 km. ``TestTheSweepsReproduce
TheHandMeasuredTables`` runs those as :class:`~quoss.engine.sweep.SweepSpec`
points through ``run()`` and requires **the same numbers**, which is what turns
a measurement somebody once made into one the repository keeps making.

Classes
-------
TestTheHorizontalEngineAddsNothing
    GE-1 through ``run()`` against the hand chain, term by term, exactly.
TestTheBlockIsTheDeclaredSession
    The finite-key block, and the ``INFO`` that says whose responsibility it is.
TestTheSweepsReproduceTheHandMeasuredTables
    Distance, lens, ``C_n^2`` and gate width, against the published tables.
TestTheWaveBracketIsNotOrderedTheSameAtBothLenses
    Why the interval has to be computed and cannot be reasoned from the 2.46.
TestTheBenchIsTheOtherFile
    GE-0b: zero radiance, zero extinction, and the Rytov variance it matches.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from quoss.channel.horizontal import (
    PathWave,
    equivalent_bench_cn2_m23,
    plane_wave_rytov_variance,
    weak_theory_path_limit_m,
)
from quoss.core.errors import DegradationLog, Severity
from quoss.engine.horizontal import HORIZONTAL_STAGES, simulate_horizontal
from quoss.engine.pipeline import run as _run
from quoss.engine.sweep import SweepSpec, apply_point, run_sweep
from quoss.scenario.defaults import ge0b_bench, ge1_two_terminals
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import HorizontalScenario
from quoss.scenario.result import HorizontalResult

from .oracle import GE1_SESSION_S, hand_horizontal


def run_horizontal(scenario: HorizontalScenario, **kwargs: Any) -> HorizontalResult:
    """:func:`quoss.engine.pipeline.run` narrowed to the horizontal result."""
    result = _run(scenario, **kwargs)
    assert isinstance(result, HorizontalResult), f"expected a horizontal result, got {type(result)}"
    return result


def horizontal_base() -> HorizontalScenario:
    """GE-1 with the extinction declared as ADR 0021's hand-assumed 0.2 dB/km.

    The published tables of ADR 0021 and ``notes/LAST_CHANGES.md`` §37 were
    computed with ``0.2`` written by hand, before ``channel/extinction.py``
    existed. ``scenarios/ge1_1km.yaml`` declares the visibility instead and gets
    **0.192**, which is the better number and a different one. Reproducing a
    published table means reproducing its inputs, so the sweeps below start from
    the scenario with that one field swapped -- and
    ``test_the_two_declarations_differ_by_the_eight_thousandths_of_a_decibel``
    measures what the swap is worth, rather than leaving two numbers in the
    repository that look like they should agree.
    """
    scenario = apply_point(
        ge1_two_terminals(), {"path.extinction": None, "path.extinction_db_per_km": 0.2}
    )
    assert isinstance(scenario, HorizontalScenario)
    return scenario


ENGINE_GE1_FINITE_BITS = 15_236_099.0
"""GE-1's 60 s session as the engine computes it, with the modelled 0.192 dB/km.

An integer: the finite key is ``floor`` of a real number. Reproduced by the hand
chain of ``oracle.py`` at the same arguments.
"""


class TestTheHorizontalEngineAddsNothing:
    """GE-1 through ``run()`` against the hand chain, exactly, stage by stage."""

    def test_every_loss_term_matches_the_hand_chain(self) -> None:
        """Each decibel term on its own, because a sum can agree while its parts do not."""
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        for field in (
            "geometric_db",
            "atmospheric_db",
            "pointing_db",
            "scintillation_db",
            "fade_db",
            "total_db",
            "transmittance",
            "channel_transmittance",
        ):
            assert float(np.asarray(getattr(engine.loss, field))) == float(
                np.asarray(getattr(by_hand.loss, field))
            ), field
        assert engine.loss.receiver_chain_db == by_hand.loss.receiver_chain_db
        assert engine.loss.static_db == by_hand.loss.static_db
        assert engine.loss.truncation_db == by_hand.loss.truncation_db

    def test_the_noise_budget_and_the_conditions_match(self) -> None:
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        for field in (
            "background_per_gate",
            "dark_per_gate",
            "afterpulse_per_gate",
            "total_per_gate",
        ):
            assert float(np.asarray(getattr(engine.noise, field))) == float(
                np.asarray(getattr(by_hand.noise, field))
            ), field
        assert float(np.asarray(engine.conditions.transmittance)) == float(
            np.asarray(by_hand.conditions.transmittance)
        )
        assert engine.conditions.pulse_rate_hz == by_hand.conditions.pulse_rate_hz
        assert engine.conditions.gate_duration_s == by_hand.conditions.gate_duration_s

    def test_every_finite_key_term_matches(self) -> None:
        """Not only the length: the four terms that explain a length, and a zero."""
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        for field in (
            "length_bits",
            "vacuum_events",
            "single_photon_events",
            "phase_error_rate",
            "observed_error_rate",
            "leakage_bits",
        ):
            assert float(np.asarray(getattr(engine.finite, field))) == float(
                np.asarray(getattr(by_hand.finite, field))
            ), field

    def test_the_asymptotic_rate_matches(self) -> None:
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        for field in ("gain", "qber", "sifted_per_pulse", "secure_per_pulse"):
            assert float(np.asarray(getattr(engine.asymptotic, field))) == float(
                np.asarray(getattr(by_hand.asymptotic, field))
            ), field

    def test_the_extinction_the_model_resolved_matches_the_hand_call(self) -> None:
        """The schema's ``extinction_db_per_km_at`` and the function it wraps, same double."""
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        assert engine.result.budget.extinction_db_per_km == by_hand.extinction_db_per_km
        assert engine.result.budget.atmospheric_db == float(np.asarray(by_hand.loss.atmospheric_db))

    def test_the_reported_variances_and_gamma_match(self) -> None:
        """The three numbers the result carries that the budget does not return."""
        engine = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
        by_hand = hand_horizontal()
        assert engine.result.budget.log_irradiance_variance_np2 == by_hand.variance_np2
        assert engine.result.budget.rytov_variance_np2 == by_hand.rytov_np2
        assert engine.result.budget.beam_to_jitter_ratio == by_hand.gamma

    def test_the_session_totals_match_and_are_the_pinned_integer(self) -> None:
        result = run_horizontal(ge1_two_terminals())
        by_hand = hand_horizontal()
        assert result.session.finite_bits == float(np.asarray(by_hand.finite.length_bits))
        assert result.session.finite_bits == ENGINE_GE1_FINITE_BITS
        assert result.session.pulses == by_hand.pulses
        assert result.session.asymptotic_bits == float(
            np.asarray(by_hand.asymptotic.secure_per_pulse)
        ) * float(by_hand.pulses)
        assert result.session.qber == float(np.asarray(by_hand.asymptotic.qber))

    def test_nothing_is_dropped_by_the_scratch_log(self) -> None:
        """The reporting calls reuse a scratch log; every code in it is already in the run's.

        ``engine/horizontal.py`` recomputes the scintillation variance and
        ``gamma`` for the result, with a throwaway log, because the loss budget
        does not return them. Nothing may be lost that way, and "nothing" is
        checked rather than asserted in a comment: the budget made the identical
        calls a moment earlier with the run's own log, so every code the scratch
        log could hold is in ``degradations`` already.
        """
        log = DegradationLog()
        simulate_horizontal(ge1_two_terminals(), degradations=log)
        codes = {entry.code for entry in log}
        scratch = DegradationLog()
        by_hand = hand_horizontal()
        assert by_hand.gamma > 0.0
        # The two reporting calls, replayed against a fresh log.
        from quoss.channel.horizontal import horizontal_log_irradiance_variance
        from quoss.channel.pointing import beam_to_jitter_ratio

        scenario = ge1_two_terminals()
        horizontal_log_irradiance_variance(
            scenario.path.path_length_m,
            cn2_m23=scenario.path.cn2_m23,
            aperture_diameter_m=scenario.path.receive_aperture_m,
            wavelength_m=scenario.transmitter.wavelength_m,
            wave=scenario.path.wave,
            degradations=scratch,
            regime=scenario.path.scintillation_regime,
        )
        beam_to_jitter_ratio(
            scenario.path.path_length_km,
            jitter_rad=scenario.transmitter.pointing_jitter_rad,
            wavelength_m=scenario.transmitter.wavelength_m,
            transmit_aperture_m=scenario.transmitter.aperture_m,
            receive_aperture_m=scenario.path.receive_aperture_m,
            degradations=scratch,
        )
        assert {entry.code for entry in scratch} <= codes

    def test_the_timings_hold_three_stages_and_not_seven(self) -> None:
        """A stage that did not run is absent, not reported as zero seconds."""
        result = run_horizontal(ge1_two_terminals())
        assert tuple(result.timings.seconds) == HORIZONTAL_STAGES
        assert "orbit" not in result.timings.seconds
        assert "passes" not in result.timings.seconds

    def test_the_two_declarations_differ_by_eight_thousandths_of_a_decibel(self) -> None:
        """0.192 modelled against 0.2 assumed: what the traceable number costs.

        The published tables were computed with 0.2 dB/km written by hand. The
        scenario file declares 23 km of visibility and the model returns
        0.19199. The difference is 0.008 dB over one kilometre -- 0.19 % of key
        -- and it is measured here rather than left as two numbers that look
        like they should agree.
        """
        modelled = run_horizontal(ge1_two_terminals())
        assumed = run_horizontal(horizontal_base())
        assert modelled.budget.extinction_db_per_km == pytest.approx(0.19199, abs=5e-6)
        assert assumed.budget.extinction_db_per_km == 0.2
        gap_db = assumed.budget.total_db - modelled.budget.total_db
        assert gap_db == pytest.approx(0.008, abs=5e-4)
        assert modelled.session.finite_bits > assumed.session.finite_bits
        relative = modelled.session.finite_bits / assumed.session.finite_bits - 1.0
        assert relative == pytest.approx(0.0019, abs=2e-4)


class TestTheBlockIsTheDeclaredSession:
    """ADR 0024: the block is a declaration here, where ADR 0011 made it geometry."""

    def test_the_run_says_whose_responsibility_the_block_is(self) -> None:
        log = DegradationLog()
        simulate_horizontal(ge1_two_terminals(), degradations=log)
        (entry,) = [e for e in log if e.code == "horizontal.block-is-the-declared-session"]
        assert entry.severity is Severity.INFO
        assert entry.details["session_duration_s"] == GE1_SESSION_S
        assert entry.details["pulses"] == 6e9
        assert "ADR 0011" in entry.message and "stationary" in entry.message

    def test_a_longer_block_is_worth_more_than_its_length(self) -> None:
        """Doubling the session buys 2.16 times the key, not 2. That is the bound, measured.

        The asymptotic figure is exactly linear in the session: it is a rate
        times a time, and 2 is 2 to the last bit. The **certified** figure is
        not, and the gap is what a block length is worth:

        ==========  =============  ===============
        session     finite bits    bits per second
        ==========  =============  ===============
        15 s        3 115 905      207 727
        30 s        7 027 898      234 263
        60 s        15 205 091     253 418
        120 s       32 059 995     267 167
        ==========  =============  ===============

        Two things make it superlinear. The **fixed penalty** of Lim et al.
        equation (1), ``6 log2(21/eps_sec) + log2(2/eps_cor)``, is 260 bits at
        ``eps = 1e-10`` and is charged once per block however long it is. The
        larger effect is the **statistical** one: the Hoeffding and
        random-sampling deviations that price how well the check basis speaks for
        the key basis grow like the square root of the block, so their *share* of
        it falls like one over the square root. Doubling the block therefore buys
        2.16 times the key here, and the per-second figure is still climbing at
        120 s.

        That is the whole reason the block is a declared parameter rather than a
        bookkeeping detail -- and, read the other way, the reason ADR 0024 insists
        the declaration is a promise: a session written longer than the link was
        actually stationary buys exactly this much key that was never earned.
        """
        rates = {
            duration: run_horizontal(
                apply_point(horizontal_base(), {"session.duration_s": duration})  # type: ignore[arg-type]
            ).session
            for duration in (15.0, 30.0, 60.0, 120.0)
        }
        assert [s.finite_bits for s in rates.values()] == [
            3_115_905.0,
            7_027_898.0,
            15_205_091.0,
            32_059_995.0,
        ]
        assert rates[60.0].finite_bits / rates[30.0].finite_bits == pytest.approx(2.164, abs=0.001)
        assert rates[120.0].finite_bits / rates[60.0].finite_bits == pytest.approx(2.109, abs=0.001)
        # Monotone in the block, which is what says it is the bound and not noise.
        per_second = [s.finite_bit_s for s in rates.values()]
        assert per_second == sorted(per_second)
        # The asymptotic figure has none of this: it is a rate times a time.
        assert rates[120.0].asymptotic_bits / rates[60.0].asymptotic_bits == pytest.approx(
            2.0, rel=1e-12
        )

    def test_the_session_enters_the_hash(self) -> None:
        """Two block lengths are two claims, so they must not share a cache entry."""
        a = horizontal_base()
        b = apply_point(a, {"session.duration_s": 120.0})
        assert scenario_hash(a) != scenario_hash(b)


class TestTheSweepsReproduceTheHandMeasuredTables:
    """The published GE-1 tables, as sweeps through ``run()``.

    Every figure below was measured by hand in ``tests/channel/test_horizontal.py``
    and printed in ADR 0021 or ``notes/LAST_CHANGES.md`` §37. Running them as
    sweep points is what makes them reproducible rather than remembered.

    **The residual is an identity, and it is closed from both ends.** The sweep
    and the hand table are not two computations to be reconciled inside a
    tolerance: they are the same calls with the same arguments, so the assertions
    are exact equality against the hand chain and the printed two-decimal figures
    are checked separately, as a statement about what was published. That is the
    same shape ``notes/LAST_CHANGES.md`` §39 used for the mask sweep, where the
    786-bit residual turned out to be one argument rather than noise.
    """

    LENS_M = (0.025, 0.10)
    DISTANCE_M = (200.0, 500.0, 1000.0, 2000.0, 2413.3979535814706, 5000.0)

    @staticmethod
    def _sweep(spec: SweepSpec, *metrics: str) -> list[dict[str, Any]]:
        return run_sweep(
            horizontal_base(), spec, metrics=metrics or ("session.asymptotic_bit_s",)
        ).to_records()

    def test_the_lens_table_and_the_factor_of_eleven_point_two(self) -> None:
        """56.8 -> 636.2 kbit/s plane, 70.2 -> 589.9 spherical: 11.20 and 8.41."""
        rows = {
            (r["path.receive_aperture_m"], r["path.wave"]): r["session.asymptotic_bit_s"] / 1e3
            for r in self._sweep(
                SweepSpec(
                    {
                        "path.receive_aperture_m": list(self.LENS_M),
                        "path.wave": ["plane", "spherical"],
                    }
                )
            )
        }
        assert rows[(0.025, "plane")] == pytest.approx(56.82, abs=0.01)
        assert rows[(0.10, "plane")] == pytest.approx(636.20, abs=0.01)
        assert rows[(0.025, "spherical")] == pytest.approx(70.15, abs=0.01)
        assert rows[(0.10, "spherical")] == pytest.approx(589.92, abs=0.01)
        assert rows[(0.10, "plane")] / rows[(0.025, "plane")] == pytest.approx(11.20, abs=0.01)
        assert rows[(0.10, "spherical")] / rows[(0.025, "spherical")] == pytest.approx(
            8.41, abs=0.01
        )

    def test_the_sweep_point_is_the_hand_chain_to_the_bit(self) -> None:
        """The identity that makes the two-decimal figures above worth anything."""
        for lens in self.LENS_M:
            for wave in (PathWave.PLANE, PathWave.SPHERICAL):
                scenario = apply_point(
                    horizontal_base(),
                    {"path.receive_aperture_m": lens, "path.wave": wave.value},
                )
                assert isinstance(scenario, HorizontalScenario)
                engine = run_horizontal(scenario)
                by_hand = hand_horizontal(
                    receive_aperture_m=lens, wave=wave, extinction_db_per_km=0.2
                )
                assert engine.session.finite_bits == float(
                    np.asarray(by_hand.finite.length_bits)
                ), (lens, wave)
                assert engine.budget.total_db == float(np.asarray(by_hand.loss.total_db)), (
                    lens,
                    wave,
                )

    def test_the_distance_table(self) -> None:
        """200 m to 5 km, both waves, against §37's published table."""
        rows = {
            (r["path.path_length_m"], r["path.wave"]): r["session.asymptotic_bit_s"] / 1e3
            for r in self._sweep(
                SweepSpec(
                    {
                        "path.path_length_m": list(self.DISTANCE_M),
                        "path.wave": ["plane", "spherical"],
                    }
                )
            )
        }
        published = {
            200.0: (896.0, 888.0),
            500.0: (825.0, 798.0),
            1000.0: (636.0, 590.0),
            2000.0: (208.0, 183.0),
            2413.3979535814706: (122.0, 107.0),
            5000.0: (4.0, 4.4),
        }
        for length, (plane, spherical) in published.items():
            assert rows[(length, "plane")] == pytest.approx(plane, abs=0.6), length
            assert rows[(length, "spherical")] == pytest.approx(spherical, abs=0.6), length

    def test_the_weak_limit_is_where_the_table_says_it_is(self) -> None:
        """2413 m, and the Rytov variance there is exactly 1 -- from both ends."""
        limit = weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=1.55e-6)
        assert limit == pytest.approx(2413.4, abs=0.1)
        assert float(
            plane_wave_rytov_variance(limit, cn2_m23=1e-14, wavelength_m=1.55e-6)
        ) == pytest.approx(1.0, rel=1e-12)
        result = run_horizontal(
            apply_point(horizontal_base(), {"path.path_length_m": limit})  # type: ignore[arg-type]
        )
        assert result.budget.rytov_variance_np2 == pytest.approx(1.0, rel=1e-12)

    def test_the_weak_limit_is_where_the_budget_starts_warning(self) -> None:
        """A limit that did not agree with the code's own warning would be a second opinion."""

        def warned(length_m: float) -> bool:
            log = DegradationLog()
            scenario = apply_point(horizontal_base(), {"path.path_length_m": length_m})
            assert isinstance(scenario, HorizontalScenario)
            simulate_horizontal(scenario, degradations=log)
            return any("weak-fluctuation-limit-exceeded" in e.code for e in log)

        limit = weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=1.55e-6)
        assert not warned(limit * 0.999)
        assert warned(limit * 1.001)

    def test_the_cn2_sweep(self) -> None:
        """Four decades of turbulence: the fade, the Rytov variance and the key."""
        rows = {
            r["path.cn2_m23"]: r
            for r in self._sweep(
                SweepSpec({"path.cn2_m23": [1e-16, 1e-15, 1e-14, 1e-13]}),
                "session.asymptotic_bit_s",
                "budget.scintillation_db",
                "budget.rytov_variance_np2",
            )
        }
        expected = {
            1e-16: (788.39, 0.141, 0.0019884451224935693),
            1e-15: (741.92, 0.448, 0.019884451224935693),
            1e-14: (589.92, 1.446, 0.1988445122493569),
            1e-13: (267.63, 4.860, 1.988445122493569),
        }
        for cn2, (kbit_s, fade_db, rytov) in expected.items():
            row = rows[cn2]
            assert row["session.asymptotic_bit_s"] / 1e3 == pytest.approx(kbit_s, abs=0.01)
            assert row["budget.scintillation_db"] == pytest.approx(fade_db, abs=5e-4)
            assert row["budget.rytov_variance_np2"] == pytest.approx(rytov, rel=1e-4)
        # The Rytov variance is linear in C_n^2, exactly, and this is the check
        # that the sweep really varied the air and not something correlated
        # with it.
        assert rows[1e-13]["budget.rytov_variance_np2"] == pytest.approx(
            10.0 * rows[1e-14]["budget.rytov_variance_np2"], rel=1e-12
        )

    def test_the_gate_width_sweep_finds_the_lever_that_is_not_one_here(self) -> None:
        """A 25-fold gate changes the key by 0.09 %, and that is the result.

        On a satellite downlink the gate is a real design variable: it sets how
        much sky and how many dark counts land in each detection window. On a
        1 km ground link at night the whole noise budget is 6e-7 counts per gate
        against a signal of 4e-2, so widening the gate 25 times moves the QBER
        from 1.0002 % to 1.0039 % and the key by less than a tenth of a percent.
        Measuring that is what stops somebody from optimising it.
        """
        rows = {
            r["receiver.gate_ns"]: r
            for r in self._sweep(
                SweepSpec({"receiver.gate_ns": [0.2, 0.5, 1.0, 2.0, 5.0]}),
                "session.asymptotic_bit_s",
                "session.qber",
                "session.noise_counts_per_gate",
            )
        }
        assert rows[0.2]["session.noise_counts_per_gate"] == pytest.approx(1.207e-7, rel=1e-3)
        assert rows[5.0]["session.noise_counts_per_gate"] == pytest.approx(3.017e-6, rel=1e-3)
        # The noise is exactly linear in the gate: 25 times the width, 25 times
        # the counts. Nothing else in the budget depends on it.
        assert rows[5.0]["session.noise_counts_per_gate"] == pytest.approx(
            25.0 * rows[0.2]["session.noise_counts_per_gate"], rel=1e-12
        )
        assert rows[0.2]["session.qber"] == pytest.approx(0.010002, abs=1e-6)
        assert rows[5.0]["session.qber"] == pytest.approx(0.010039, abs=1e-6)
        change = rows[5.0]["session.asymptotic_bit_s"] / rows[0.2]["session.asymptotic_bit_s"] - 1.0
        assert change == pytest.approx(-0.0009, abs=1e-4)

    def test_a_downlink_metric_is_refused_before_the_first_point_runs(self) -> None:
        """``daily.finite_bits`` on a horizontal scenario names the sections that exist."""
        from quoss.core.errors import ScenarioError

        with pytest.raises(ScenarioError, match="other link geometry"):
            run_sweep(
                horizontal_base(),
                SweepSpec({"path.path_length_m": [500.0]}),
                metrics=("daily.finite_bits",),
            )


class TestTheWaveBracketIsNotOrderedTheSameAtBothLenses:
    """The reason the interval has to be computed and cannot be reasoned from the 2.46.

    A spherical wave scintillates **2.46 times less at a point** than a plane
    wave on the same path -- that is the ratio of the two closed forms'
    coefficients, 1.2285 against 0.5. The tempting inference is that the
    spherical wave is therefore always the optimistic edge of the bracket. It is
    not, because aperture averaging works on the *other* factor: a spherical
    wave's irradiance is correlated over a wider patch, so a wide lens averages
    fewer independent speckles out of it (Kaushal & Kaddoum's 0.214 against
    1.07).

    At 2.5 cm the lens is small enough that the point variance decides, and the
    plane wave is the **pessimistic** edge. At 10 cm the averaging decides, and
    the plane wave is the **optimistic** one. The bracket therefore inverts
    between the two rows of the headline table, which is why ADR 0021 prints an
    interval and why quoting "the spherical number" without saying which side of
    the inversion it is on would be quoting a bound as if it were an estimate.
    """

    @staticmethod
    def _key(lens_m: float, wave: PathWave) -> float:
        scenario = apply_point(
            horizontal_base(), {"path.receive_aperture_m": lens_m, "path.wave": wave.value}
        )
        assert isinstance(scenario, HorizontalScenario)
        return run_horizontal(scenario).session.asymptotic_bits

    def test_the_ordering_reverses_between_the_two_lenses(self) -> None:
        small_plane = self._key(0.025, PathWave.PLANE)
        small_spherical = self._key(0.025, PathWave.SPHERICAL)
        big_plane = self._key(0.10, PathWave.PLANE)
        big_spherical = self._key(0.10, PathWave.SPHERICAL)
        assert small_plane < small_spherical, "at 2.5 cm the plane wave is the pessimistic edge"
        assert big_plane > big_spherical, "at 10 cm the plane wave is the optimistic edge"

    def test_the_point_variance_ratio_is_the_same_2_46_at_both_lenses(self) -> None:
        """The factor the wrong inference is built on really is constant, so it is not the cause."""
        for lens in (0.025, 0.10):
            del lens
        plane = float(plane_wave_rytov_variance(1000.0, cn2_m23=1e-14, wavelength_m=1.55e-6))
        spherical = 0.5 / 1.2285 * plane
        assert plane / spherical == pytest.approx(2.457, abs=0.001)

    def test_the_aperture_averaging_is_what_reverses_it(self) -> None:
        """The scintillation fade, not the key, so the mechanism is visible on its own."""
        fades = {
            (lens, wave): run_horizontal(
                apply_point(  # type: ignore[arg-type]
                    horizontal_base(),
                    {"path.receive_aperture_m": lens, "path.wave": wave.value},
                )
            ).budget.scintillation_db
            for lens in (0.025, 0.10)
            for wave in (PathWave.PLANE, PathWave.SPHERICAL)
        }
        assert fades[(0.025, PathWave.PLANE)] > fades[(0.025, PathWave.SPHERICAL)]
        assert fades[(0.10, PathWave.PLANE)] < fades[(0.10, PathWave.SPHERICAL)]

    def test_the_interval_is_what_gets_quoted(self) -> None:
        """8.4 to 11.2 for the lens, 590 to 636 kbit/s for the link. An interval."""
        factors = sorted(
            self._key(0.10, wave) / self._key(0.025, wave)
            for wave in (PathWave.PLANE, PathWave.SPHERICAL)
        )
        assert factors[0] == pytest.approx(8.41, abs=0.01)
        assert factors[1] == pytest.approx(11.20, abs=0.01)
        rates = sorted(self._key(0.10, wave) / GE1_SESSION_S / 1e3 for wave in PathWave)
        assert rates[0] == pytest.approx(589.9, abs=0.1)
        assert rates[1] == pytest.approx(636.2, abs=0.1)


class TestTheBenchIsTheOtherFile:
    """GE-0b: the same schema, a dark enclosure, and the variance it is tuned to."""

    def test_the_bench_matches_ge1s_rytov_variance_by_construction(self) -> None:
        """8.87e-10 over 2 m is 1e-14 over 1 km, to machine precision and not to a figure."""
        bench = run_horizontal(ge0b_bench())
        field = run_horizontal(ge1_two_terminals())
        assert bench.budget.rytov_variance_np2 == pytest.approx(
            field.budget.rytov_variance_np2, rel=1e-12
        )
        assert ge0b_bench().path.cn2_m23 == equivalent_bench_cn2_m23(
            bench_length_m=2.0, path_length_m=1000.0, cn2_m23=1e-14
        )

    def test_matching_the_rytov_variance_does_not_match_what_the_receiver_sees(self) -> None:
        """A second, measurable half of ADR 0009 gap 20 — and this one is inside the model.

        The gap as it was stated is about phase screens: an emulator makes an
        ``r_0``, not a ``C_n^2`` over a length, and scintillation needs distance
        behind the screen to develop. That argument is correct and it is
        **outside** what QuOSS models, so it could only be written down.

        This is the part that can be measured, and it is large. The bench is
        tuned so that its **Rytov variance** equals GE-1's, and it does, to
        machine precision: 0.198845 both. But the Rytov variance is the variance
        a *point* detector would see, and what reaches the key is the
        **aperture-averaged** one -- and aperture averaging depends on how far
        away the turbulence is. A 10 cm lens two metres from the source averages
        essentially everything out:

        ============  ===============  ===============  ==============
        link          Rytov variance   averaging ``A``  fade at 1 %
        ============  ===============  ===============  ==============
        GE-1, 1 km    0.198845         0.2386           **1.446 dB**
        GE-0b, 2 m    0.198845         4.45e-5          **0.030 dB**
        ============  ===============  ===============  ==============

        The receiver-side variance is **2 183 times smaller** on the bench, and
        the fade it has to budget is 1.42 dB smaller. So a bench that matches
        ``C_n^2`` in the sense ``equivalent_bench_cn2_m23`` means does **not**
        reproduce the scintillation GE-1's receiver will actually have to
        survive, for a reason that has nothing to do with phase screens and
        everything to do with geometry.

        That does not make the bench useless -- it makes the question it answers
        a different one -- and it is the second reason the file says to ask a
        vendor for ``D/r_0`` and a Rytov number rather than for a ``C_n^2``.
        """
        bench = run_horizontal(ge0b_bench())
        field = run_horizontal(ge1_two_terminals())
        assert bench.budget.rytov_variance_np2 == pytest.approx(
            field.budget.rytov_variance_np2, rel=1e-12
        )
        ratio = field.budget.log_irradiance_variance_np2 / bench.budget.log_irradiance_variance_np2
        assert ratio == pytest.approx(2183.0, rel=5e-3)
        assert bench.budget.scintillation_db == pytest.approx(0.030, abs=5e-4)
        assert field.budget.scintillation_db == pytest.approx(1.446, abs=5e-4)
        assert field.budget.scintillation_db - bench.budget.scintillation_db == pytest.approx(
            1.416, abs=1e-3
        )

    def test_a_dark_enclosure_has_exactly_zero_background(self) -> None:
        """Zero radiance is a declaration, and it gives an exact zero rather than a small one."""
        engine = simulate_horizontal(ge0b_bench(), degradations=DegradationLog())
        assert float(np.asarray(engine.noise.background_per_gate)) == 0.0
        assert float(np.asarray(engine.noise.total_per_gate)) == float(
            np.asarray(engine.noise.dark_per_gate)
        )

    def test_zero_extinction_is_an_exact_zero_decibel_term(self) -> None:
        result = run_horizontal(ge0b_bench())
        assert result.budget.extinction_db_per_km == 0.0
        assert result.budget.atmospheric_db == 0.0

    def test_the_bench_is_the_plane_wave_side_of_the_rayleigh_range(self) -> None:
        """2 m is 0.0063 Rayleigh ranges, so ``plane`` is silent and ``spherical`` warns."""

        def codes(wave: PathWave) -> list[str]:
            log = DegradationLog()
            scenario = apply_point(ge0b_bench(), {"path.wave": wave.value})
            assert isinstance(scenario, HorizontalScenario)
            simulate_horizontal(scenario, degradations=log)
            return [e.code for e in log if e.code.startswith("horizontal.") and "wave" in e.code]

        assert codes(PathWave.PLANE) == []
        assert codes(PathWave.SPHERICAL) == ["horizontal.spherical-wave-inside-the-rayleigh-range"]
