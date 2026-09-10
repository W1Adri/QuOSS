"""Tests for `quoss.channel.detector`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestAgainstLimEtAl`` — **V2**. The detection-rate and afterpulse formulas of
  Lim et al. 2014's Evaluation section, transcribed here from the paper and
  compared against the module over four fibre lengths. They agree to better
  than 3e-7 relative, which is a **derived** bound rather than a chosen one: the
  published form truncates the two-detector dark-count union at first order, and
  the truncation is ``p_dc^2 / (eta_sys k + 2 p_dc) <= p_dc / 2``.
- ``TestAgainstNtanosEtAl`` — **V2**, including one published claim that
  *reproduces*: their §4.2 argument that link attenuation keeps their detectors
  out of dead-time saturation is right by two orders of magnitude, and the class
  measures by how much rather than agreeing with it.
- ``TestTheEfficiencyChainAppliesToPhotonsOnly`` — the trap the module is shaped
  around, measured: the sky background is attenuated by the receiver chain and
  the dark counts are not, and folding the dark counts into the background loses
  0.94 dB of noise.
- ``TestGatingCannotTouchAfterpulsing`` — the second finding, and the one that
  ties this module to ``channel/background.py``: narrowing the gate tenfold buys
  10 dB with a nanowire and 0.22 dB with the published InGaAs diode, so
  "narrow the gate" is a conditional statement and the condition is the
  detector.
- ``TestTheThreeLinearisations`` — **V2 in conflict with itself**. Three
  published expressions (Lim's ``1 - 2 p_dc``, Lim's ``1 + p_ap``, Ntanos et
  al.'s ``Y_0 = P_dc + P_noise``) are first-order truncations of the module's
  composition rule, each excellent at its own operating point and each returning
  something above one somewhere inside this project's parameter sweeps. Both
  derived thresholds are re-derived here with a root finder.
- ``TestDeadTime`` / ``TestGatedDeadTime`` — **V1**. Both dead-time laws checked
  against Monte Carlo simulations of the processes they are derived from, plus
  the non-injectivity of the paralysable model exhibited with two explicit
  incident rates that report the same reading.
- ``TestScalingLaws`` — **V1**. The proportionalities that make a noise budget
  reviewable by hand, and shape preservation over the time axis.
- ``TestRejectsBadInput`` / ``TestModuleSurface``.

Not reproduced, and declared:

- **Any typical-detector table.** Gap 5 of ``docs/adr/0009-citation-policy.md``
  is still open. The two parameter sets tested here are two instruments from two
  papers, and nothing is interpolated between them; a test asserts that the
  constants carry their source in their names.
- **A dark-count rate for the InGaAs diode.** Lim et al. publish a probability
  per gate and state no gate width anywhere in the paper, so every rate for that
  detector in this file carries the gate it assumed.
- **The QBER contributions.** Lim et al.'s ``e_k = p_dc + e_mis [1 -
  exp(-eta_ch k)] + p_ap D_k / 2`` is a protocol quantity for ``qkd/``; what is
  tested here is the crossover it implies (afterpulsing overtakes dark counts
  below 42 dB of loss), which is a statement about the detector.
- **Afterpulse timing.** Whether an afterpulse can itself afterpulse is not
  settled by any verified source, so the module returns the published
  one-per-click form and warns above the 5 % point; the test asserts the
  *warning*, not a preferred model.
"""

from __future__ import annotations

import inspect
from itertools import pairwise

import numpy as np
import pytest
from scipy.optimize import brentq

from quoss.channel.background import (
    background_counts_per_gate,
    background_photon_rate_cps,
    background_power_w,
)
from quoss.channel.detector import (
    AFTERPULSE_CASCADE_LIMIT,
    DEAD_TIME_MODEL_DIVERGENCE_LIMIT,
    LIM_INGAAS_AFTERPULSE_PROBABILITY,
    LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
    LIM_INGAAS_EFFICIENCY,
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_DEAD_TIME_S,
    NTANOS_SNSPD_EFFICIENCY,
    NTANOS_SNSPD_GATE_DURATION_S,
    NTANOS_SNSPD_TIMING_JITTER_FWHM_S,
    afterpulsed_counts_per_gate,
    click_probability,
    dark_count_rate_from_probability_cps,
    dark_counts_per_gate,
    gates_blocked_per_click,
    incident_count_rate_cps,
    live_gate_fraction,
    observed_count_rate_cps,
    receiver_efficiency,
    saturation_count_rate_cps,
)
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.core.units import linear_to_db, transmittance_to_loss_db

# --------------------------------------------------------------------------- #
# The two published receivers
# --------------------------------------------------------------------------- #

RECEIVER_CHAIN_DB = NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB
"""5.65 dB: the 0.2 nm filter's 3 dB of insertion loss plus 2.65 dB of receiver.

Ntanos et al. 2021 §4.1. Their 0.3 dB polarisation decoherence loss is *not*
here: the same sentence calls it a loss "of the link", it applies to the signal
and not to unpolarised background light, and it belongs to ``link_budget.py``.
"""

ETA_NTANOS = 0.85 * 10.0 ** (-5.65 / 10.0)
"""The reference chain, computed here from the published numbers rather than
imported, so that :func:`receiver_efficiency` is compared against arithmetic
written out independently of it."""

NIGHT_BACKGROUND_PER_GATE = 7.6386e-6
"""Sky background at the 2.3 m aperture in a 1 ns gate, counts.

From ``channel/background.py``: the study nighttime radiance of Ntanos et al.
§4.2.2 (1.5e-4 W/m^2/um/sr) through their 100 urad field of view and 0.2 nm
filter at 1550 nm. Recomputed from that module in
``test_the_background_handoff_is_at_the_aperture`` rather than trusted as a
literal, so that a change there fails here.
"""

SOURCE_REPETITION_HZ = 100e6
"""Quantum signal repetition rate, Ntanos et al. §4.2, verbatim: "a quantum
signal repetition rate of 100 MHz"."""

BEST_CASE_LINK_LOSS_DB = 20.0
"""Ntanos et al. §4.2.1: the total downlink loss "can get as low as 20 dB in
total" with their largest telescope. Used as the best case for the dead-time
argument, because the best case is where saturation would appear first."""


def _lim_detection_probability(
    intensity: float, *, system_efficiency: float, dark_count_probability: float
) -> float:
    """Lim et al. 2014 Evaluation, transcribed: ``D_k = 1-(1-2 p_dc) exp(-eta_sys k)``.

    Written out here rather than imported so that the comparison is against the
    equation as printed. Verbatim from the paper: "the expected detection rate
    (excluding after-pulse contributions) is ``D_k = 1 - (1 - 2 p_dc)
    exp(-eta_sys k)``, where ``eta_sys = eta_ch eta_Bob``".
    """
    return 1.0 - (1.0 - 2.0 * dark_count_probability) * np.exp(-system_efficiency * intensity)


def _lim_afterpulsed_rate(detection_probability: float, *, afterpulse_probability: float) -> float:
    """Lim et al. 2014, transcribed: ``R_k = D_k (1 + p_ap)``."""
    return detection_probability * (1.0 + afterpulse_probability)


def _module_detection_probability(
    intensity: float,
    *,
    channel_transmittance: float,
    receiver_efficiency_: float,
    dark_count_probability: float,
    detector_count: int = 2,
) -> float:
    """Return the same quantity through the module, in its own vocabulary.

    Lim et al.'s ``k`` is the intensity at Alice and their ``eta_sys`` bundles
    the channel with the receiver; this module splits them at the aperture, so
    the photons per gate are ``eta_ch k`` and the efficiency is ``eta_Bob``.

    Note what the dark-count conversion does **not** need: a gate width. It goes
    from a probability to a rate and back through the same ``gate_duration_s``,
    which cancels — which is why this reproduction is possible at all, since Lim
    et al. never state a gate.
    """
    any_gate_s = 1e-9
    rate_cps = dark_count_rate_from_probability_cps(
        dark_count_probability, gate_duration_s=any_gate_s
    )
    dark = dark_counts_per_gate(rate_cps, gate_duration_s=any_gate_s, detector_count=detector_count)
    return float(
        click_probability(
            channel_transmittance * intensity,
            efficiency=receiver_efficiency_,
            dark_counts_per_gate=dark,
        )
    )


@pytest.mark.reference
class TestAgainstLimEtAl:
    """Lim et al. 2014, *Phys. Rev. A* 89, 022307, Evaluation section."""

    def test_the_published_parameters_are_transcribed(self) -> None:
        """Verbatim: "eta_Bob = 10%, p_dc = 6 x 10^-7, p_ap = 4 x 10^-2"."""
        assert LIM_INGAAS_EFFICIENCY == 0.10
        assert LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE == 6e-7
        assert LIM_INGAAS_AFTERPULSE_PROBABILITY == 4e-2

    @pytest.mark.parametrize(
        ("fibre_km", "published"),
        [
            (0.0, 4.877172e-2),
            (50.0, 4.988715e-3),
            (100.0, 5.010744e-4),
            (200.0, 6.199982e-6),
        ],
    )
    def test_the_detection_rate_reproduces_over_four_fibre_lengths(
        self, fibre_km: float, published: float
    ) -> None:
        """``D_k`` from the module against ``D_k`` as printed, at ``mu = 0.5``.

        The channel is theirs too: "the fibers have an attenuation coefficient
        of 0.2 dB/km. That is, their transmittance is eta_ch = 10^-0.2L/10".

        The tolerance is derived, not tuned. The module computes the exact
        two-detector union ``(1 - p_dc)^2`` and the paper prints its first order
        ``1 - 2 p_dc``, so the published value is larger by ``p_dc^2 exp(-x)``,
        which relative to ``D_k`` is at most ``p_dc / 2 = 3e-7`` — reached only
        in the limit where the dark counts are the whole of the detection rate.
        """
        intensity = 0.5
        channel = 10.0 ** (-0.2 * fibre_km / 10.0)
        transcribed = _lim_detection_probability(
            intensity,
            system_efficiency=channel * LIM_INGAAS_EFFICIENCY,
            dark_count_probability=LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
        )
        computed = _module_detection_probability(
            intensity,
            channel_transmittance=channel,
            receiver_efficiency_=LIM_INGAAS_EFFICIENCY,
            dark_count_probability=LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
        )

        assert transcribed == pytest.approx(published, rel=1e-6)
        assert computed == pytest.approx(transcribed, rel=3e-7)
        assert computed == pytest.approx(published, rel=1e-6)

    def test_the_truncation_error_grows_as_the_dark_counts_take_over(self) -> None:
        """Where the first-order union costs anything, and in which direction.

        The published form always reads *high*, because ``1 - 2 p_dc`` is
        smaller than ``(1 - p_dc)^2``, so it subtracts less. The size of the
        overshoot is ``p_dc^2 / (eta_sys k + 2 p_dc)``: negligible while the
        signal dominates, and approaching ``p_dc / 2`` when the dark counts do.
        Measured across their own figure's range it grows monotonically by four
        orders of magnitude and never reaches 1e-7.
        """
        intensity = 0.5
        overshoots: list[float] = []
        for fibre_km in (0.0, 50.0, 100.0, 200.0):
            channel = 10.0 ** (-0.2 * fibre_km / 10.0)
            transcribed = _lim_detection_probability(
                intensity,
                system_efficiency=channel * LIM_INGAAS_EFFICIENCY,
                dark_count_probability=LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
            )
            computed = _module_detection_probability(
                intensity,
                channel_transmittance=channel,
                receiver_efficiency_=LIM_INGAAS_EFFICIENCY,
                dark_count_probability=LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
            )
            overshoots.append(transcribed / computed - 1.0)

        assert all(low < high for low, high in pairwise(overshoots))
        assert overshoots[0] == pytest.approx(7.0e-12, rel=0.2)
        assert overshoots[-1] == pytest.approx(5.8e-8, rel=0.05)
        assert max(overshoots) < 0.5 * LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE

    def test_the_afterpulsed_rate_reproduces(self) -> None:
        """``R_k = D_k (1 + p_ap)``, which is what the module returns."""
        detection = 5.010744e-4
        transcribed = _lim_afterpulsed_rate(
            detection, afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY
        )
        computed = afterpulsed_counts_per_gate(
            detection,
            afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY,
            degradations=DegradationLog(),
        )
        assert float(computed) == pytest.approx(transcribed, rel=1e-15)
        assert float(computed) == pytest.approx(5.211174e-4, rel=1e-6)

    def test_the_afterpulse_error_term_overtakes_the_dark_counts_below_42_db(self) -> None:
        """The crossover that makes ``p_ap`` the important constant of the pair.

        In their own error model the two noise contributions are ``p_dc`` and
        ``p_ap D_k / 2``, so afterpulsing dominates once
        ``D_k > 2 p_dc / p_ap = 3e-5``. With ``mu = 0.5`` that is a total system
        efficiency of 6e-5, i.e. **42.2 dB** — and published satellite downlink
        budgets sit at 20 to 40 dB, so afterpulsing is the larger term across
        the whole useful range of a link that uses this detector.

        The QBER expression itself is not implemented here; it is a protocol
        quantity for ``qkd/``. What is asserted is the crossover, which is a
        property of the detector's two constants.
        """
        crossover_detection = (
            2.0 * LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE / LIM_INGAAS_AFTERPULSE_PROBABILITY
        )
        assert crossover_detection == pytest.approx(3e-5, rel=1e-12)

        intensity = 0.5
        crossover_efficiency = crossover_detection / intensity
        assert float(transmittance_to_loss_db(crossover_efficiency)) == pytest.approx(
            42.22, abs=0.01
        )

        # And on the two sides of it, computed rather than asserted by fiat.
        for detection, dominant in ((1e-6, "dark"), (1e-3, "afterpulse")):
            dark_term = LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE
            afterpulse_term = 0.5 * LIM_INGAAS_AFTERPULSE_PROBABILITY * detection
            assert (afterpulse_term > dark_term) == (dominant == "afterpulse")


@pytest.mark.reference
class TestAgainstNtanosEtAl:
    """Ntanos et al. 2021 §4.1 and §4.2, and one claim of theirs that holds."""

    def test_the_published_parameters_are_transcribed(self) -> None:
        """The §4.1 sentence, transcribed.

        Verbatim: "we assumed SNSPDs with quantum efficiencies of 85% at
        1550 nm, dark count rates of 300 counts per second (cps), timing jitter
        of 50 ps, dead time of 30 ns, and no after-pulsing effect. The
        detector's gate duration time was set to 1 ns".
        """
        assert NTANOS_SNSPD_EFFICIENCY == 0.85
        assert NTANOS_SNSPD_DARK_COUNT_RATE_CPS == 300.0
        assert NTANOS_SNSPD_TIMING_JITTER_FWHM_S == 50e-12
        assert NTANOS_SNSPD_DEAD_TIME_S == 30e-9
        assert NTANOS_SNSPD_AFTERPULSE_PROBABILITY == 0.0
        assert NTANOS_SNSPD_GATE_DURATION_S == 1e-9
        assert NTANOS_FILTER_INSERTION_LOSS_DB == 3.0
        assert NTANOS_RECEIVER_LOSS_DB == 2.65

    def test_the_receiver_chain_is_6_36_db(self) -> None:
        """The three published losses multiplied, and the detector's share of them.

        Worth stating because the intuition is backwards: the exotic part of the
        receiver is the cheapest. 85 % efficiency is 0.71 dB, while the filter
        and the rest of the optics cost 5.65 dB between them — so 11 % of the
        chain is the detector and 89 % is glass.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        assert eta == pytest.approx(ETA_NTANOS, rel=1e-15)
        assert eta == pytest.approx(0.2314296, rel=1e-6)

        total_db = float(transmittance_to_loss_db(eta))
        detector_db = float(transmittance_to_loss_db(NTANOS_SNSPD_EFFICIENCY))
        assert total_db == pytest.approx(6.3558, abs=1e-3)
        assert detector_db == pytest.approx(0.7058, abs=1e-3)
        assert detector_db / total_db == pytest.approx(0.111, abs=0.001)

    def test_the_two_detectors_in_the_published_gate(self) -> None:
        """300 cps each, two of them, 1 ns: 6e-7 counts per gate."""
        mu = dark_counts_per_gate(
            NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
            detector_count=2,
        )
        assert float(mu) == pytest.approx(6e-7, rel=1e-12)

    def test_the_equality_with_lims_dark_count_probability_is_a_coincidence(self) -> None:
        """Two papers, two technologies, the same 6e-7 — and it means nothing.

        Ntanos et al.'s two nanowires at 300 cps in their own 1 ns gate give
        exactly the 6e-7 per gate that Lim et al. publish for one InGaAs diode.
        Read per detector, which is the only way the two are comparable, they
        differ by a factor of two; and the agreement exists only at a gate width
        Lim et al. never state. The test exists so that nobody later reads the
        coincidence as two independent sources corroborating each other.
        """
        per_detector = dark_counts_per_gate(
            NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S
        )
        both = dark_counts_per_gate(
            NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
            detector_count=2,
        )
        assert float(both) == pytest.approx(LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE, rel=1e-12)
        assert float(per_detector) == pytest.approx(
            0.5 * LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE, rel=1e-12
        )

        # Change the assumed gate and the "agreement" moves by the same factor,
        # which is the proof that it is about the gate and not about the diodes.
        at_ten_ns = dark_count_rate_from_probability_cps(
            LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE, gate_duration_s=10e-9
        )
        at_one_ns = dark_count_rate_from_probability_cps(
            LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE, gate_duration_s=1e-9
        )
        assert float(at_one_ns) == pytest.approx(600.0, rel=1e-6)
        assert float(at_ten_ns) == pytest.approx(60.0, rel=1e-6)
        assert float(at_ten_ns) < NTANOS_SNSPD_DARK_COUNT_RATE_CPS < float(at_one_ns)

    def test_no_afterpulsing_means_exactly_the_identity(self) -> None:
        """A zero, not a small number: "and no after-pulsing effect".

        A nanowire has no avalanche and so no trapped carriers to release. The
        consequence is the whole of the gating argument in
        ``channel/background.py``: with this detector, narrowing the gate really
        does remove noise in proportion, because every noise term left scales
        with the gate.
        """
        log = DegradationLog()
        for counts in (0.0, 1e-6, 1e-3, 3.42):
            unchanged = afterpulsed_counts_per_gate(
                counts,
                afterpulse_probability=NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
                degradations=log,
            )
            assert float(unchanged) == pytest.approx(counts, rel=1e-15, abs=0.0)
        assert len(log) == 0

    def test_their_dead_time_claim_reproduces(self) -> None:
        """§4.2: link attenuation keeps their detectors out of saturation. It does.

        Verbatim: "despite the fast repetition rate at Alice station, the photon
        loss due to link attenuation is also high. This combination prevents the
        detectors of Bob station to be saturated due to their dead time".

        Quantified with their own numbers — 100 MHz, 30 ns, ``mu = 0.5`` and
        their best-case 20 dB total loss, which is where saturation would show
        up first: 500 kcps into a detector whose non-paralysable ceiling is
        33.3 Mcps, for a loss of 1.5 % continuous or 1.0 % gated. At their more
        typical 30 dB it is 0.15 %. The claim is not merely true, it is true
        with two orders of magnitude of margin, which is worth recording in a
        file whose other published claims mostly did not close.
        """
        intensity = 0.5
        click_per_gate = intensity * 10.0 ** (-BEST_CASE_LINK_LOSS_DB / 10.0)
        detected_cps = click_per_gate * SOURCE_REPETITION_HZ
        assert detected_cps == pytest.approx(500e3, rel=1e-12)

        log = DegradationLog()
        observed = observed_count_rate_cps(
            detected_cps, dead_time_s=NTANOS_SNSPD_DEAD_TIME_S, degradations=log
        )
        continuous_loss = 1.0 - float(observed) / detected_cps
        assert continuous_loss == pytest.approx(0.01478, rel=1e-3)
        assert len(log) == 0

        blocked = gates_blocked_per_click(
            NTANOS_SNSPD_DEAD_TIME_S, gate_period_s=1.0 / SOURCE_REPETITION_HZ
        )
        gated_loss = 1.0 - float(
            live_gate_fraction(click_per_gate, gates_blocked_per_click=blocked)
        )
        assert blocked == 2
        assert gated_loss == pytest.approx(0.00990, rel=1e-3)

        # The margin, which is the part of the claim worth quantifying.
        ceiling = saturation_count_rate_cps(NTANOS_SNSPD_DEAD_TIME_S)
        assert ceiling / detected_cps == pytest.approx(66.7, rel=1e-2)

    def test_the_gated_loss_is_smaller_than_the_continuous_one(self) -> None:
        """And why: 30 ns of dead time at 100 MHz costs 20 ns of gates, not 30.

        A gated receiver loses whole gates. The last third of a 30 ns dead time
        expires between two 10 ns gates and costs nothing, so the effective dead
        time is ``b T_rep = 20 ns``. The ratio of the two losses is therefore
        ``20 / 30`` to first order, and that is what this measures.
        """
        click_per_gate = 5e-3
        detected_cps = click_per_gate * SOURCE_REPETITION_HZ
        observed = observed_count_rate_cps(
            detected_cps, dead_time_s=NTANOS_SNSPD_DEAD_TIME_S, degradations=DegradationLog()
        )
        continuous_loss = 1.0 - float(observed) / detected_cps
        blocked = gates_blocked_per_click(NTANOS_SNSPD_DEAD_TIME_S, gate_period_s=10e-9)
        gated_loss = 1.0 - float(
            live_gate_fraction(click_per_gate, gates_blocked_per_click=blocked)
        )
        assert gated_loss < continuous_loss
        assert gated_loss / continuous_loss == pytest.approx(2.0 / 3.0, rel=0.01)

    def test_their_yield_is_a_sum_where_the_union_is_available(self) -> None:
        """Equation (A6): ``Y_0 = P_dc + P_noise``, and where a sum stops working.

        At night the two forms agree to 1.2e-6 relative, and that number is
        not a tolerance but the answer: the sum overestimates the union by
        ``mu / 2``, the second term of ``1 - exp(-mu)``, and the night mean is
        ``mu = 2.37e-6``. So the paper's arithmetic is fine to six digits at its
        own operating point.

        But the module reaches the same number by adding *means* and
        exponentiating once, and that route keeps working where the sum does
        not: with the daylight background their own receiver collects — 3.42
        counts per gate, from ``channel/background.py`` — the sum returns 3.42
        and the union returns 0.967.
        """
        dark = float(
            dark_counts_per_gate(
                NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
                gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
                detector_count=2,
            )
        )
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)

        night_sum = eta * NIGHT_BACKGROUND_PER_GATE + dark
        night_union = float(
            click_probability(
                0.0,
                efficiency=eta,
                background_photons_per_gate=NIGHT_BACKGROUND_PER_GATE,
                dark_counts_per_gate=dark,
            )
        )
        assert night_union == pytest.approx(night_sum, rel=2e-6)
        assert 1.0 - night_union / night_sum == pytest.approx(0.5 * night_sum, rel=1e-3)
        assert night_union == pytest.approx(2.3678e-6, rel=1e-4)

        daylight_counts_per_gate = 3.415341
        as_a_sum = daylight_counts_per_gate + dark
        as_a_union = float(
            click_probability(
                0.0,
                efficiency=1.0,
                background_photons_per_gate=daylight_counts_per_gate,
                dark_counts_per_gate=dark,
            )
        )
        assert as_a_sum > 1.0
        assert as_a_union == pytest.approx(0.967135, abs=1e-6)
        assert as_a_union < 1.0

    def test_the_background_handoff_is_at_the_aperture(self) -> None:
        """The literal used throughout this file, recomputed from ``background.py``.

        Two modules have to agree about where the boundary is: ``background.py``
        returns counts *at the aperture* and applies no optical chain, and this
        module applies the chain. If either side ever moves, this is the test
        that fails rather than a link budget that quietly shifts by 6.36 dB.
        """
        power_w = background_power_w(
            1.5e-4,
            field_of_view_full_angle_rad=100e-6,
            receive_aperture_m=2.3,
            filter_bandwidth_m=0.2e-9,
        )
        rate_cps = background_photon_rate_cps(power_w, wavelength_m=1.55e-6)
        at_aperture = background_counts_per_gate(
            rate_cps, gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S
        )
        assert float(at_aperture) == pytest.approx(NIGHT_BACKGROUND_PER_GATE, rel=1e-4)


@pytest.mark.physics
class TestTheEfficiencyChainAppliesToPhotonsOnly:
    """The trap: background photons are attenuated, dark counts are not."""

    def test_folding_the_dark_counts_into_the_background_loses_0_94_db(self) -> None:
        """The mistake, and its exact size at the reference receiver.

        "Apply the receiver efficiency to the noise" is the natural sentence and
        it is wrong for a quarter of the noise: a dark count is generated behind
        the optics, so nothing in front of them attenuates it. The size is not a
        rounding error — the noise comes out 1.242 times too small, and a QBER
        computed from it is correspondingly optimistic.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        dark = 6e-7

        correct = float(
            click_probability(
                0.0,
                efficiency=eta,
                background_photons_per_gate=NIGHT_BACKGROUND_PER_GATE,
                dark_counts_per_gate=dark,
            )
        )
        folded = float(
            click_probability(
                0.0,
                efficiency=eta,
                background_photons_per_gate=NIGHT_BACKGROUND_PER_GATE + dark,
            )
        )
        assert correct / folded == pytest.approx(1.2419, rel=1e-3)
        assert float(linear_to_db(correct / folded)) == pytest.approx(0.94, abs=0.01)

        # And the algebraic identity behind the number, so the 1.2419 is not a
        # frozen output: the ratio is (eta mu_bg + mu_dc) / (eta (mu_bg + mu_dc)).
        predicted = (eta * NIGHT_BACKGROUND_PER_GATE + dark) / (
            eta * (NIGHT_BACKGROUND_PER_GATE + dark)
        )
        assert correct / folded == pytest.approx(predicted, rel=1e-6)

    def test_the_chain_moves_the_dark_count_share_from_7_to_25_per_cent(self) -> None:
        """Which term dominates the night noise depends on which side of the optics.

        At the aperture the sky is 12.7 times the dark counts and it is
        tempting to ignore them. After a 6.36 dB chain it is 2.9 times, and the
        dark counts are a quarter of the noise budget. Same receiver, same
        night, different accounting point.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        dark = 6e-7

        at_aperture = dark / (NIGHT_BACKGROUND_PER_GATE + dark)
        after_chain = dark / (eta * NIGHT_BACKGROUND_PER_GATE + dark)
        assert at_aperture == pytest.approx(0.0728, abs=1e-4)
        assert after_chain == pytest.approx(0.2534, abs=1e-4)
        assert NIGHT_BACKGROUND_PER_GATE / dark == pytest.approx(12.73, rel=1e-3)
        assert eta * NIGHT_BACKGROUND_PER_GATE / dark == pytest.approx(2.946, rel=1e-3)

    def test_a_smaller_telescope_is_dark_count_limited(self) -> None:
        """The consequence for the three published stations.

        Background scales with the collecting area and dark counts do not, so
        the 0.75 m station sits below its own detectors: 1.9e-7 counts per gate
        of sky against 6e-7 of dark. Which is the reason
        ``channel/background.py`` reports the night-radiance disagreement
        between its two sources as costing 1.24x at 0.75 m and 2.83x at 2.3 m —
        the small telescope's noise is mostly not sky at all.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        dark = 6e-7
        small = NIGHT_BACKGROUND_PER_GATE * (0.75 / 2.3) ** 2
        assert eta * small == pytest.approx(1.88e-7, rel=1e-2)
        assert eta * small < dark
        assert eta * NIGHT_BACKGROUND_PER_GATE > dark


@pytest.mark.physics
class TestGatingCannotTouchAfterpulsing:
    """The second finding, and the condition it puts on ``background.py``."""

    def test_narrowing_the_gate_tenfold_buys_10_db_or_0_22_db(self) -> None:
        """The same receiver, the same link, two detectors, two conclusions.

        ``channel/background.py`` prices the gate: 1 ns to 100 ps removes 10 dB
        of sky for 0.08 dB of signal. That holds exactly for a nanowire, whose
        remaining noise term (dark counts) also scales with the gate. With the
        published InGaAs diode the afterpulse term does not move at all, and it
        is the largest of the three, so the same ten-fold narrowing is worth
        0.22 dB.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        click_per_gate = 1e-3
        totals: dict[tuple[str, float], float] = {}

        for gate_s in (1e-9, 100e-12):
            scale = gate_s / NTANOS_SNSPD_GATE_DURATION_S
            sky = eta * NIGHT_BACKGROUND_PER_GATE * scale
            dark = float(
                dark_counts_per_gate(
                    NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=gate_s, detector_count=2
                )
            )
            for name, p_ap in (
                ("nanowire", NTANOS_SNSPD_AFTERPULSE_PROBABILITY),
                ("ingaas", LIM_INGAAS_AFTERPULSE_PROBABILITY),
            ):
                noise = (
                    float(
                        afterpulsed_counts_per_gate(
                            sky + dark, afterpulse_probability=p_ap, degradations=DegradationLog()
                        )
                    )
                    + p_ap * click_per_gate
                )
                totals[(name, gate_s)] = noise

        nanowire_gain = totals[("nanowire", 1e-9)] / totals[("nanowire", 100e-12)]
        ingaas_gain = totals[("ingaas", 1e-9)] / totals[("ingaas", 100e-12)]
        assert float(linear_to_db(nanowire_gain)) == pytest.approx(10.0, abs=0.01)
        assert float(linear_to_db(ingaas_gain)) == pytest.approx(0.22, abs=0.02)

        # The documented table, to four figures.
        assert totals[("ingaas", 1e-9)] == pytest.approx(4.24e-5, rel=1e-2)
        assert totals[("ingaas", 100e-12)] == pytest.approx(4.02e-5, rel=1e-2)

    def test_the_afterpulse_term_is_the_only_one_independent_of_the_gate(self) -> None:
        """The structural statement behind the number, checked term by term."""
        gates = np.array([1e-9, 500e-12, 100e-12, 50e-12])
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)

        sky = eta * NIGHT_BACKGROUND_PER_GATE * gates / NTANOS_SNSPD_GATE_DURATION_S
        dark = (
            dark_counts_per_gate(
                NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=1.0, detector_count=2
            )
            * gates
        )
        afterpulse = np.full_like(gates, LIM_INGAAS_AFTERPULSE_PROBABILITY * 1e-3)

        # Sky and dark counts are strictly proportional to the gate; the
        # afterpulse term is constant to the last bit.
        assert np.allclose(sky / gates, sky[0] / gates[0], rtol=1e-12)
        assert np.allclose(dark / gates, dark[0] / gates[0], rtol=1e-12)
        assert np.all(afterpulse == afterpulse[0])

    def test_at_which_click_rate_afterpulsing_overtakes_the_sky(self) -> None:
        """The crossover, in the units a link budget speaks.

        Afterpulses scale with the click probability and the sky does not, so
        there is a click probability above which the detector is its own
        dominant noise source. With the published InGaAs afterpulse probability
        and the reference night sky in a 1 ns gate, that is 4.4e-5 clicks per
        gate — a 40 dB link at ``mu = 0.5``, which is the *worst* case of the
        published budgets. Every better link is afterpulse-limited.
        """
        eta = receiver_efficiency(NTANOS_SNSPD_EFFICIENCY, optical_loss_db=RECEIVER_CHAIN_DB)
        sky_and_dark = eta * NIGHT_BACKGROUND_PER_GATE + 6e-7
        crossover = sky_and_dark / LIM_INGAAS_AFTERPULSE_PROBABILITY
        assert crossover == pytest.approx(5.92e-5, rel=1e-2)

        loss_db = float(transmittance_to_loss_db(crossover / 0.5))
        assert loss_db == pytest.approx(39.3, abs=0.2)


@pytest.mark.physics
class TestTheThreeLinearisations:
    """Three published first-order forms, and what each costs off its operating point."""

    def test_the_two_detector_union_exceeds_one_above_half(self) -> None:
        """``1 - 2 p_dc`` goes negative, and the "probability" goes above 1.

        The daylight case is not hypothetical: 0.967 is what
        ``background.background_click_probability`` returns for Ntanos et al.'s
        own receiver under ITU-R's tabulated bright sunshine at 850 nm. Feeding
        it to Lim et al.'s printed form as a per-detector noise probability
        gives 1.93.
        """
        daylight_probability = 0.967135
        printed = _lim_detection_probability(
            0.0, system_efficiency=0.0, dark_count_probability=daylight_probability
        )
        assert printed == pytest.approx(1.93427, rel=1e-5)
        assert printed > 1.0

        exact = 1.0 - (1.0 - daylight_probability) ** 2
        assert exact == pytest.approx(0.99892, rel=1e-4)
        assert exact < 1.0

        # And the module cannot be made to return either of those, because it
        # never forms a probability until the means have been summed.
        mean = -np.log1p(-daylight_probability)
        through_module = float(
            click_probability(0.0, efficiency=1.0, dark_counts_per_gate=2 * mean)
        )
        assert through_module == pytest.approx(exact, rel=1e-12)

    def test_where_the_union_linearisation_reaches_five_per_cent(self) -> None:
        """A root, re-derived, not a remembered number: ``p_dc = 0.1791``."""
        root = brentq(lambda p: (1.0 - p) ** 2 / (1.0 - 2.0 * p) - 1.05, 1e-9, 0.49)
        assert root == pytest.approx(0.17913, abs=1e-5)
        # Below it the printed form is fine, above it the two are different physics.
        assert (1.0 - 0.1) ** 2 / (1.0 - 0.2) == pytest.approx(1.0125, rel=1e-3)

    def test_the_afterpulse_cascade_limit_is_a_closed_form(self) -> None:
        """``sqrt(1/21)``, re-derived with a root finder and checked against the constant.

        The two candidate models differ by ``1 / (1 - p_ap^2)``, so the 5 %
        crossing is where ``p_ap^2 = 1/21``. The constant in the module is that
        square root, and this test is what would notice if it were ever rounded
        to 0.22.
        """
        root = brentq(lambda p: 1.0 / (1.0 - p**2) - 1.05, 1e-9, 0.99)
        assert root == pytest.approx(AFTERPULSE_CASCADE_LIMIT, rel=1e-10)
        assert AFTERPULSE_CASCADE_LIMIT == pytest.approx(float(np.sqrt(1.0 / 21.0)), rel=1e-12)
        assert AFTERPULSE_CASCADE_LIMIT != 0.22

    def test_the_published_afterpulse_factor_is_0_16_per_cent_from_the_cascade(self) -> None:
        """At 4e-2 the model ambiguity is invisible; at 0.3 it is 10 %."""
        published = 1.0 + LIM_INGAAS_AFTERPULSE_PROBABILITY
        cascade = 1.0 / (1.0 - LIM_INGAAS_AFTERPULSE_PROBABILITY)
        assert cascade / published - 1.0 == pytest.approx(0.0016, abs=1e-4)

        noisy = DegradationLog()
        _ = afterpulsed_counts_per_gate(1e-3, afterpulse_probability=0.3, degradations=noisy)
        assert noisy.entries[0].code == "detector.afterpulse-cascade-unresolved"
        assert noisy.entries[0].severity is Severity.WARNING
        assert noisy.entries[0].details["cascade_factor"] == pytest.approx(1.0 / 0.7, rel=1e-9)
        assert noisy.entries[0].details["published_factor"] == pytest.approx(1.3, rel=1e-9)

    def test_the_afterpulse_warning_fires_only_above_the_limit(self) -> None:
        """The threshold is the 5 % point and nothing else."""
        below = DegradationLog()
        _ = afterpulsed_counts_per_gate(
            1e-3,
            afterpulse_probability=AFTERPULSE_CASCADE_LIMIT * (1.0 - 1e-9),
            degradations=below,
        )
        assert len(below) == 0

        above = DegradationLog()
        _ = afterpulsed_counts_per_gate(
            1e-3,
            afterpulse_probability=AFTERPULSE_CASCADE_LIMIT * (1.0 + 1e-9),
            degradations=above,
        )
        assert len(above) == 1

    def test_the_cascade_factor_is_reported_as_infinite_at_certainty(self) -> None:
        """``p_ap = 1`` is a detector that never stops, and the log says so.

        The published form returns a finite factor of 2 there, which is the
        clearest possible illustration of what the truncation drops: a detector
        whose every click is followed by another has an unbounded count rate,
        and only the cascading model can say that.
        """
        log = DegradationLog()
        total = afterpulsed_counts_per_gate(1e-3, afterpulse_probability=1.0, degradations=log)
        assert float(total) == pytest.approx(2e-3, rel=1e-12)
        assert log.entries[0].details["cascade_factor"] == float("inf")


@pytest.mark.physics
class TestDeadTime:
    """Both models, against the processes they are derived from."""

    def test_the_non_paralysable_law_is_the_live_time_identity(self) -> None:
        """``m = R / (1 + R tau)`` is ``m = 1 / (tau + 1 / R)`` rearranged.

        An independent derivation of the same formula: each recorded count costs
        ``tau`` of dead time plus, on average, ``1 / R`` of live waiting for the
        next arrival, so the counts per second is the reciprocal of that sum. If
        the module's algebra were wrong, this would not match.
        """
        tau = NTANOS_SNSPD_DEAD_TIME_S
        for rate in (1e3, 1e5, 1e6, 1e7):
            through_module = float(
                observed_count_rate_cps(rate, dead_time_s=tau, degradations=DegradationLog())
            )
            from_live_time = 1.0 / (tau + 1.0 / rate)
            assert through_module == pytest.approx(from_live_time, rel=1e-12)

    @pytest.mark.parametrize("rate_times_dead_time", [0.05, 0.3])
    def test_the_non_paralysable_law_matches_a_simulated_detector(
        self, rate_times_dead_time: float
    ) -> None:
        """**V1**: exponential arrivals, a 30 ns blind window, and counting.

        The module derives the law analytically; this simulates the process it
        was derived from — Poisson arrivals, each recorded count blocking the
        next ``tau`` — and counts what comes out. The tolerance is three
        standard errors of the estimate, ``3 / sqrt(counts)``, derived from the
        sample size rather than tuned.
        """
        tau = NTANOS_SNSPD_DEAD_TIME_S
        rate = rate_times_dead_time / tau
        source = RandomSource.from_seed(20260912)
        arrivals = np.cumsum(source.generator.exponential(1.0 / rate, size=200_000))

        counted = 0
        last_count = -np.inf
        for arrival in arrivals:
            if arrival - last_count >= tau:
                counted += 1
                last_count = arrival
        measured = counted / float(arrivals[-1])

        predicted = float(
            observed_count_rate_cps(rate, dead_time_s=tau, degradations=DegradationLog())
        )
        standard_error = predicted / np.sqrt(counted)
        assert abs(measured - predicted) < 3.0 * standard_error

    def test_the_paralysable_law_matches_a_simulated_extending_detector(self) -> None:
        """**V1**: the same arrivals, with *every* arrival restarting the window.

        The difference from the test above is one line — the window restarts on
        arrivals rather than on counts — and that one line is the whole
        distinction between the two models, so simulating both from the same
        generator is what shows the module's two branches are the two processes
        and not two formulas.
        """
        tau = NTANOS_SNSPD_DEAD_TIME_S
        rate = 0.3 / tau
        source = RandomSource.from_seed(20260913)
        gaps = source.generator.exponential(1.0 / rate, size=200_000)
        arrivals = np.cumsum(gaps)

        # An arrival is recorded only if the previous *arrival* was at least tau
        # ago, which is exactly the extending-dead-time condition.
        recorded = int(np.count_nonzero(gaps >= tau))
        measured = recorded / float(arrivals[-1])

        predicted = float(
            observed_count_rate_cps(
                rate, dead_time_s=tau, paralysable=True, degradations=DegradationLog()
            )
        )
        standard_error = predicted / np.sqrt(recorded)
        assert abs(measured - predicted) < 3.0 * standard_error

    def test_the_two_saturation_ceilings(self) -> None:
        """``1 / tau`` and ``1 / (e tau)``, a factor of ``e`` apart."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        assert saturation_count_rate_cps(tau) == pytest.approx(33.333e6, rel=1e-4)
        assert saturation_count_rate_cps(tau, paralysable=True) == pytest.approx(12.263e6, rel=1e-4)
        assert saturation_count_rate_cps(tau) / saturation_count_rate_cps(
            tau, paralysable=True
        ) == pytest.approx(float(np.e), rel=1e-12)

    def test_the_paralysable_maximum_is_where_the_derivative_vanishes(self) -> None:
        """A maximum, re-derived: ``d/dR [R exp(-R tau)] = 0`` at ``R = 1 / tau``."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        log = DegradationLog()
        rates = np.array([0.5, 0.9, 1.0, 1.1, 2.0]) / tau
        observed = observed_count_rate_cps(
            rates, dead_time_s=tau, paralysable=True, degradations=log
        )
        assert float(np.argmax(observed)) == 2.0
        assert float(observed[2]) == pytest.approx(saturation_count_rate_cps(tau, paralysable=True))

    def test_the_paralysable_model_maps_two_rates_to_one_reading(self) -> None:
        """Why there is no paralysable inverse: the function is not injective.

        Two incident rates, 16.3 and 59.4 Mcps, that a paralysable detector with
        a 30 ns dead time reports identically as 10 Mcps. A function that
        inverted this would have to pick one, and picking silently is the
        failure mode this project forbids — so the ambiguity is a missing
        function instead.
        """
        tau = NTANOS_SNSPD_DEAD_TIME_S
        log = DegradationLog()
        low = 16_313_407.57
        high = 59_377_900.78
        reported_low = float(
            observed_count_rate_cps(low, dead_time_s=tau, paralysable=True, degradations=log)
        )
        reported_high = float(
            observed_count_rate_cps(high, dead_time_s=tau, paralysable=True, degradations=log)
        )
        assert reported_low == pytest.approx(10e6, rel=1e-6)
        assert reported_high == pytest.approx(10e6, rel=1e-6)
        assert high / low == pytest.approx(3.64, rel=1e-2)

        # And there is genuinely no such function to call.
        from quoss.channel import detector

        assert "paralysable" not in inspect.signature(detector.incident_count_rate_cps).parameters

    def test_the_non_paralysable_inverse_round_trips(self) -> None:
        """``R = m / (1 - m tau)`` against ``m = R / (1 + R tau)``, both directions."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        for rate in (1e3, 1e5, 1e6, 1e7, 2e7):
            observed = observed_count_rate_cps(rate, dead_time_s=tau, degradations=DegradationLog())
            recovered = incident_count_rate_cps(observed, dead_time_s=tau)
            assert float(recovered) == pytest.approx(rate, rel=1e-9)

    def test_a_reading_at_the_ceiling_is_refused(self) -> None:
        """No non-paralysable detector can report ``1 / tau``, so there is no answer."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        with pytest.raises(DomainError, match="ceiling of a non-paralysable"):
            incident_count_rate_cps(1.0 / tau, dead_time_s=tau)
        with pytest.raises(DomainError, match="ceiling of a non-paralysable"):
            incident_count_rate_cps(1.5 / tau, dead_time_s=tau)

    def test_the_divergence_limit_is_re_derived(self) -> None:
        """``(1 + x) exp(-x) = 0.95`` at ``x = 0.35536``, and 11.8 Mcps at 30 ns."""
        root = brentq(lambda x: (1.0 + x) * np.exp(-x) - 0.95, 1e-9, 3.0)
        assert root == pytest.approx(DEAD_TIME_MODEL_DIVERGENCE_LIMIT, rel=1e-10)
        assert DEAD_TIME_MODEL_DIVERGENCE_LIMIT / NTANOS_SNSPD_DEAD_TIME_S == pytest.approx(
            11.845e6, rel=1e-3
        )

    def test_the_model_warning_fires_on_the_loudest_sample_of_a_pass(self) -> None:
        """A time series is judged by its worst point, like the background warning."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        quiet = DegradationLog()
        _ = observed_count_rate_cps(np.array([1e5, 1e6, 5e6]), dead_time_s=tau, degradations=quiet)
        assert len(quiet) == 0

        loud = DegradationLog()
        _ = observed_count_rate_cps(np.array([1e5, 1e6, 20e6]), dead_time_s=tau, degradations=loud)
        assert loud.entries[0].code == "detector.dead-time-model-ambiguous"
        assert loud.entries[0].severity is Severity.WARNING
        assert loud.entries[0].details["rate_times_dead_time"] == pytest.approx(0.6, rel=1e-9)
        assert loud.entries[0].details["non_paralysable_cps"] == pytest.approx(12.5e6, rel=1e-6)
        assert loud.entries[0].details["paralysable_cps"] == pytest.approx(10.976e6, rel=1e-4)

    def test_the_paralysable_past_maximum_warning(self) -> None:
        """Past ``R tau = 1`` a paralysable reading cannot be inverted at all."""
        tau = NTANOS_SNSPD_DEAD_TIME_S
        log = DegradationLog()
        _ = observed_count_rate_cps(2.0 / tau, dead_time_s=tau, paralysable=True, degradations=log)
        codes = [entry.code for entry in log.entries]
        assert codes == [
            "detector.dead-time-model-ambiguous",
            "detector.paralysable-past-maximum",
        ]

        # The non-paralysable branch never records that second one, however loud.
        non_paralysable = DegradationLog()
        _ = observed_count_rate_cps(100.0 / tau, dead_time_s=tau, degradations=non_paralysable)
        assert [entry.code for entry in non_paralysable.entries] == [
            "detector.dead-time-model-ambiguous"
        ]

    def test_an_empty_time_series_records_nothing_and_returns_empty(self) -> None:
        """The degenerate array, which the ``np.max`` of the warning would break on."""
        log = DegradationLog()
        empty = observed_count_rate_cps(
            np.array([]), dead_time_s=NTANOS_SNSPD_DEAD_TIME_S, degradations=log
        )
        assert empty.shape == (0,)
        assert len(log) == 0


@pytest.mark.physics
class TestGatedDeadTime:
    """The integer form, which is what a gated QKD receiver actually loses."""

    @pytest.mark.parametrize(
        ("dead_time_s", "gate_period_s", "expected"),
        [
            (30e-9, 10e-9, 2),
            (30e-9, 9e-9, 3),
            (30e-9, 1e-9, 29),
            (30e-9, 20e-9, 1),
            (30e-9, 30e-9, 0),
            (30e-9, 50e-9, 0),
        ],
    )
    def test_the_blocked_count_against_an_explicit_count(
        self, dead_time_s: float, gate_period_s: float, expected: int
    ) -> None:
        """``ceil(tau / T) - 1`` against counting the gate openings one by one.

        The closed form is an arithmetic shortcut for "how many integers ``j >=
        1`` satisfy ``j T < tau``", and the boundary case is the one worth
        pinning: three periods of dead time blocks two gates, because the third
        gate opens at the instant the detector recovers.
        """
        by_counting = sum(1 for j in range(1, 1000) if j * gate_period_s < dead_time_s)
        computed = gates_blocked_per_click(dead_time_s, gate_period_s=gate_period_s)
        assert computed == by_counting
        assert computed == expected

    @pytest.mark.parametrize(
        ("click_probability_per_gate", "blocked"), [(0.01, 29), (0.1, 2), (0.001, 29)]
    )
    def test_the_live_fraction_matches_a_simulated_gated_receiver(
        self, click_probability_per_gate: float, blocked: int
    ) -> None:
        """**V1**: gate-by-gate simulation against ``f = 1 / (1 + b p)``.

        The formula's derivation assumes the blocked windows never overlap, and
        that is not an approximation — a click can only occur in a live gate, so
        two clicks are at least ``b + 1`` gates apart by construction. This
        simulates the receiver gate by gate and measures the live fraction.

        The tolerance is three standard errors, and the standard error is
        derived from the process rather than assumed binomial: the live count is
        ``n - b * clicks``, so its scatter is ``b`` times the Poisson scatter of
        the click count, ``b sqrt(n f p) / n``. Reading it as a binomial on the
        live fraction instead understates it by a factor of five at ``b = 29``,
        which is exactly the kind of tolerance that would fail once a year for
        no reason.
        """
        source = RandomSource.from_seed(20260914)
        gates = 200_000
        draws = source.generator.random(gates)

        live = 0
        blocked_until = -1
        for index in range(gates):
            if index > blocked_until:
                live += 1
                if draws[index] < click_probability_per_gate:
                    blocked_until = index + blocked
        measured = live / gates

        predicted = float(
            live_gate_fraction(click_probability_per_gate, gates_blocked_per_click=blocked)
        )
        expected_clicks = gates * predicted * click_probability_per_gate
        standard_error = blocked * np.sqrt(expected_clicks) / gates
        assert abs(measured - predicted) < 3.0 * standard_error

    def test_the_documented_table(self) -> None:
        """The six numbers in the docstring, and the 1.1 dB at 1 GHz."""
        expected = {
            (1e-3, 2): 0.998004,
            (1e-3, 29): 0.971817,
            (1e-2, 2): 0.980392,
            (1e-2, 29): 0.775194,
            (1e-1, 2): 0.833333,
            (1e-1, 29): 0.256410,
        }
        for (probability, blocked), fraction in expected.items():
            computed = live_gate_fraction(probability, gates_blocked_per_click=blocked)
            assert float(computed) == pytest.approx(fraction, abs=1e-6)

        at_a_gigahertz = live_gate_fraction(1e-2, gates_blocked_per_click=29)
        assert float(transmittance_to_loss_db(at_a_gigahertz)) == pytest.approx(1.106, abs=1e-3)

    def test_a_detector_that_recovers_between_gates_loses_nothing(self) -> None:
        """Exactly 1, for any click probability, with no floating-point residue."""
        fraction = live_gate_fraction(np.array([0.0, 1e-6, 0.5, 1.0]), gates_blocked_per_click=0)
        assert np.all(fraction == 1.0)

    def test_the_reported_clicks_per_gate_saturate(self) -> None:
        """What the receiver reports is ``f p``, which has a ceiling of ``1 / b``.

        The useful reading of the formula: however bright the signal, a gated
        detector that blocks ``b`` gates per click cannot report more than one
        click every ``b + 1`` gates. At 1 GHz with a 30 ns dead time that is
        33.3 Mcps — the same ceiling as the continuous form, arrived at by
        counting gates instead of seconds, which is the check that the two
        formulations are one model.
        """
        blocked = 29
        probabilities = np.array([0.01, 0.1, 0.5, 1.0])
        reported = probabilities * live_gate_fraction(
            probabilities, gates_blocked_per_click=blocked
        )
        assert np.all(np.diff(reported) > 0.0)
        assert float(reported[-1]) == pytest.approx(1.0 / (1 + blocked), rel=1e-12)

        gate_period_s = 1e-9
        assert float(reported[-1]) / gate_period_s == pytest.approx(
            saturation_count_rate_cps(30e-9), rel=1e-9
        )


@pytest.mark.physics
class TestScalingLaws:
    """The proportionalities that make the noise budget reviewable by hand."""

    def test_dark_counts_scale_with_the_gate_and_the_detector_count(self) -> None:
        """Both linear, and the linearity is what keeps gating worth doing."""
        base = float(dark_counts_per_gate(NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=1e-9))
        assert float(
            dark_counts_per_gate(NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=1e-10)
        ) == pytest.approx(0.1 * base, rel=1e-12)
        assert float(
            dark_counts_per_gate(
                NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=1e-9, detector_count=4
            )
        ) == pytest.approx(4.0 * base, rel=1e-12)
        assert float(
            dark_counts_per_gate(2.0 * NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=1e-9)
        ) == pytest.approx(2.0 * base, rel=1e-12)

    def test_the_click_probability_is_linear_in_the_signal_when_it_is_small(self) -> None:
        """``1 - exp(-eta mu) -> eta mu``, which is the regime every budget is in."""
        eta = 0.2314
        for photons in (1e-9, 1e-6, 1e-4):
            probability = float(click_probability(photons, efficiency=eta))
            assert probability == pytest.approx(eta * photons, rel=1e-4)

    def test_the_click_probability_saturates_instead_of_exceeding_one(self) -> None:
        """Whatever the sky does, the answer stays a probability.

        The contrast with ``TestTheThreeLinearisations`` is the point: fed the
        same means, every published linear form passes 1 and keeps going, while
        this rises monotonically towards it and stops there. At a mean of a
        thousand counts per gate the answer is exactly 1.0 — the float64 limit
        of ``-expm1`` — and never 1.0000001.
        """
        probability = click_probability(
            np.array([1.0, 5.0, 20.0]),
            efficiency=1.0,
            background_photons_per_gate=np.array([3.42, 3.42, 3.42]),
            dark_counts_per_gate=6e-7,
        )
        assert np.all(probability < 1.0)
        assert np.all(np.diff(probability) > 0.0)
        assert float(probability[0]) == pytest.approx(0.98797, rel=1e-4)

        drowned = click_probability(1e3, efficiency=1.0, background_photons_per_gate=3.42)
        assert float(drowned) == 1.0

    def test_the_efficiency_chain_is_multiplicative_in_db(self) -> None:
        """Two losses applied together equal their sum in dB, as a chain must."""
        together = receiver_efficiency(0.85, optical_loss_db=3.0 + 2.65)
        stepwise = receiver_efficiency(0.85, optical_loss_db=3.0) * float(10.0 ** (-2.65 / 10.0))
        assert together == pytest.approx(stepwise, rel=1e-12)

    def test_shapes_are_preserved_over_the_time_axis(self) -> None:
        """Every array-valued entry point keeps the shape it was given."""
        eta = 0.2314
        pass_shape = (7,)
        signal = np.full(pass_shape, 1e-4)

        assert click_probability(signal, efficiency=eta).shape == pass_shape
        assert (
            click_probability(
                signal,
                efficiency=eta,
                background_photons_per_gate=np.full(pass_shape, 7.6e-6),
                dark_counts_per_gate=np.full(pass_shape, 6e-7),
            ).shape
            == pass_shape
        )
        assert dark_counts_per_gate(np.full(pass_shape, 300.0), gate_duration_s=1e-9).shape == (
            pass_shape
        )
        assert (
            afterpulsed_counts_per_gate(
                signal, afterpulse_probability=4e-2, degradations=DegradationLog()
            ).shape
            == pass_shape
        )
        assert (
            observed_count_rate_cps(
                np.full(pass_shape, 1e5), dead_time_s=30e-9, degradations=DegradationLog()
            ).shape
            == pass_shape
        )
        assert incident_count_rate_cps(np.full(pass_shape, 1e5), dead_time_s=30e-9).shape == (
            pass_shape
        )
        assert (
            live_gate_fraction(np.full(pass_shape, 1e-3), gates_blocked_per_click=2).shape
            == pass_shape
        )
        assert (
            dark_count_rate_from_probability_cps(
                np.full(pass_shape, 6e-7), gate_duration_s=1e-9
            ).shape
            == pass_shape
        )

    def test_the_dark_count_round_trip_is_exact_in_both_directions(self) -> None:
        """Rate to probability to rate, through the Poisson relation."""
        for rate in (1.0, 300.0, 6000.0, 1e6):
            per_gate = dark_counts_per_gate(rate, gate_duration_s=1e-9)
            probability = -np.expm1(-per_gate)
            recovered = dark_count_rate_from_probability_cps(probability, gate_duration_s=1e-9)
            assert float(recovered) == pytest.approx(rate, rel=1e-9)

    def test_the_poisson_and_linear_readings_of_a_dark_probability_agree_at_1e_minus_7(
        self,
    ) -> None:
        """Why the exact form costs nothing to use, and where it starts to matter."""
        exact = float(
            dark_count_rate_from_probability_cps(
                LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE, gate_duration_s=1e-9
            )
        )
        linear = LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE / 1e-9
        assert exact / linear - 1.0 == pytest.approx(3e-7, rel=0.1)

        # At a daylight-swamped probability the two are 3.4x apart, and only the
        # exact one diverges as the probability approaches certainty.
        swamped = float(dark_count_rate_from_probability_cps(0.967135, gate_duration_s=1e-9))
        assert swamped / (0.967135 / 1e-9) == pytest.approx(3.53, rel=1e-2)
        assert (
            float(dark_count_rate_from_probability_cps(1.0 - 1e-12, gate_duration_s=1e-9)) > 2.7e10
        )


class TestRejectsBadInput:
    def test_an_efficiency_in_per_cent_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="not a percentage"):
            receiver_efficiency(85.0)

    def test_a_negative_efficiency_is_rejected(self) -> None:
        with pytest.raises(DomainError, match=r"must be finite and in \[0, 1\]"):
            receiver_efficiency(-0.1)

    def test_a_negative_optical_loss_is_rejected(self) -> None:
        """A negative loss is a gain, and a receiver that emits photons."""
        with pytest.raises(DomainError, match="emits photons"):
            receiver_efficiency(0.85, optical_loss_db=-3.0)

    def test_a_non_finite_efficiency_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="quantum_efficiency"):
            receiver_efficiency(float("nan"))
        with pytest.raises(DomainError, match="optical_loss_db"):
            receiver_efficiency(0.85, optical_loss_db=float("inf"))

    @pytest.mark.parametrize("gate_s", [0.0, -1e-9, float("nan")])
    def test_a_non_positive_gate_is_rejected(self, gate_s: float) -> None:
        with pytest.raises(DomainError, match="must be finite and positive"):
            dark_counts_per_gate(300.0, gate_duration_s=gate_s)

    def test_the_duration_message_names_the_nanosecond_convention(self) -> None:
        """The message is the documentation at the point of failure."""
        with pytest.raises(DomainError) as info:
            dark_counts_per_gate(300.0, gate_duration_s=1.0e0 * 0.0)
        assert "1 nanosecond gate is 1e-9" in str(info.value)

        with pytest.raises(DomainError) as dead:
            observed_count_rate_cps(1e5, dead_time_s=0.0, degradations=DegradationLog())
        assert "30 nanosecond dead time is 30e-9" in str(dead.value)

        with pytest.raises(DomainError) as period:
            gates_blocked_per_click(30e-9, gate_period_s=0.0)
        assert "100 MHz is 10e-9" in str(period.value)

    def test_a_negative_dark_count_rate_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="must be non-negative"):
            dark_counts_per_gate(-1.0, gate_duration_s=1e-9)

    def test_the_rate_message_names_the_other_convention(self) -> None:
        """Because 6e-7 is the number a reader is most likely to pass here."""
        with pytest.raises(DomainError) as info:
            dark_counts_per_gate(-6e-7, gate_duration_s=1e-9)
        assert "dark_count_rate_from_probability_cps" in str(info.value)

    @pytest.mark.parametrize("count", [0, -1])
    def test_a_non_positive_detector_count_is_rejected(self, count: int) -> None:
        with pytest.raises(DomainError, match="detector_count must be at least 1"):
            dark_counts_per_gate(300.0, gate_duration_s=1e-9, detector_count=count)

    @pytest.mark.parametrize("count", [2.0, 0.85, True, "2"])
    def test_a_non_integer_detector_count_is_rejected(self, count: object) -> None:
        """Including ``True``, which is an ``int`` in Python and not a detector."""
        with pytest.raises(DomainError, match="detector_count must be an int"):
            dark_counts_per_gate(300.0, gate_duration_s=1e-9, detector_count=count)  # type: ignore[arg-type]

    def test_a_dark_count_probability_above_one_is_rejected(self) -> None:
        with pytest.raises(DomainError, match=r"must lie in \[0, 1\]"):
            dark_count_rate_from_probability_cps(1.5, gate_duration_s=1e-9)

    def test_a_dark_count_probability_of_exactly_one_is_rejected(self) -> None:
        """It implies an infinite rate, so there is no number to return."""
        with pytest.raises(DomainError, match="infinite rate"):
            dark_count_rate_from_probability_cps(1.0, gate_duration_s=1e-9)

    def test_the_probability_message_points_at_the_counts_converter(self) -> None:
        with pytest.raises(DomainError) as info:
            live_gate_fraction(3.42, gates_blocked_per_click=2)
        assert "click_probability" in str(info.value)

    def test_negative_counts_per_gate_are_rejected_everywhere(self) -> None:
        for call in (
            lambda: click_probability(-1e-6, efficiency=0.5),
            lambda: click_probability(0.0, efficiency=0.5, background_photons_per_gate=-1e-6),
            lambda: click_probability(0.0, efficiency=0.5, dark_counts_per_gate=-1e-6),
            lambda: afterpulsed_counts_per_gate(
                -1e-6, afterpulse_probability=0.04, degradations=DegradationLog()
            ),
        ):
            with pytest.raises(DomainError, match="must be non-negative"):
                call()

    def test_counts_above_one_are_accepted_because_they_are_means(self) -> None:
        """The daylight operating point is a real one and must not raise."""
        assert float(
            click_probability(0.0, efficiency=1.0, background_photons_per_gate=3.42)
        ) == pytest.approx(0.96733, rel=1e-4)
        assert float(
            afterpulsed_counts_per_gate(
                3.42, afterpulse_probability=0.04, degradations=DegradationLog()
            )
        ) == pytest.approx(3.5568, rel=1e-4)

    def test_a_non_finite_input_is_rejected_everywhere(self) -> None:
        for call in (
            lambda: click_probability(float("nan"), efficiency=0.5),
            lambda: dark_counts_per_gate(float("inf"), gate_duration_s=1e-9),
            lambda: dark_count_rate_from_probability_cps(float("nan"), gate_duration_s=1e-9),
            lambda: observed_count_rate_cps(
                float("nan"), dead_time_s=30e-9, degradations=DegradationLog()
            ),
            lambda: incident_count_rate_cps(float("nan"), dead_time_s=30e-9),
            lambda: live_gate_fraction(float("nan"), gates_blocked_per_click=2),
        ):
            with pytest.raises(DomainError, match="non-finite"):
                call()

    def test_an_afterpulse_probability_above_one_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="nanowire is exactly 0"):
            afterpulsed_counts_per_gate(
                1e-3, afterpulse_probability=1.5, degradations=DegradationLog()
            )

    def test_a_non_integer_blocked_count_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="must be an int"):
            live_gate_fraction(1e-3, gates_blocked_per_click=30e-9)  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="must be non-negative"):
            live_gate_fraction(1e-3, gates_blocked_per_click=-1)

    def test_a_negative_observed_rate_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="must be non-negative"):
            incident_count_rate_cps(-1.0, dead_time_s=30e-9)


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import detector

        assert detector.__all__ == sorted(detector.__all__)
        for name in detector.__all__:
            assert hasattr(detector, name)

    def test_every_published_constant_names_its_source(self) -> None:
        """Gap 5 of ADR 0009 is open, so no constant here may look generic.

        There is no verified table of typical detector parameters, so every
        number is one instrument from one paper. Naming the paper in the
        identifier is what stops ``DARK_COUNT_RATE_CPS`` from being read as "the"
        dark count rate — and the two sets differ by 10 dB in efficiency and a
        factor of infinity in afterpulsing.
        """
        from quoss.channel import detector

        for name in detector.__all__:
            if name.isupper() and not name.startswith(("AFTERPULSE_", "DEAD_TIME_")):
                assert name.startswith(("NTANOS_", "LIM_")), name

    def test_the_module_documents_both_sources(self) -> None:
        from quoss.channel import detector

        assert detector.__doc__ is not None
        assert "Ntanos" in detector.__doc__
        assert "Lim" in detector.__doc__
        assert "022307" in detector.__doc__

    def test_the_module_declares_what_it_leaves_out(self) -> None:
        """Each omission named with where it goes instead, or why there is nowhere."""
        from quoss.channel import detector

        assert detector.__doc__ is not None
        for absent in (
            "gate_signal_fraction",
            "quoss.qkd",
            "double-click",
            "0009",
            "Non-Poisson dark counts",
            "latching",
        ):
            assert absent in detector.__doc__

    def test_no_function_here_takes_a_wavelength_or_an_elevation(self) -> None:
        """The negative control for the two gaps easiest to fill by accident.

        A detector's efficiency and dark rate *are* wavelength dependent — 85 %
        is quoted "at 1550 nm" — and its dark rate is temperature dependent. No
        verified source gives either curve (gap 5 of ADR 0009), so the
        efficiency is an argument and the module models neither dependence. An
        elevation would be worse: nothing inside a receiver knows where the
        telescope points.
        """
        from quoss.channel import detector

        for name in detector.__all__:
            attribute = getattr(detector, name)
            if not callable(attribute) or isinstance(attribute, type):
                continue
            parameters = inspect.signature(attribute).parameters
            for forbidden in ("wavelength", "elevation", "zenith", "temperature"):
                assert not any(forbidden in parameter for parameter in parameters), name

    def test_there_is_no_random_generator_in_this_module(self) -> None:
        """Same rule as the rest of ``channel/``: randomness lives in ``core/rng.py``."""
        import ast

        from quoss.channel import detector

        tree = ast.parse(inspect.getsource(detector))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any("rng" in name or "random" in name for name in imported)
        assert hasattr(RandomSource, "from_seed")

    def test_the_gate_law_is_not_duplicated_here(self) -> None:
        """The jitter constant lives here; the ``erf`` law lives in ``background``.

        Asserted by absence, because the tempting thing is to add a
        ``gate_signal_fraction`` next to the jitter constant and end up with two
        of them. The gate trades signal against background, and both halves of a
        trade belong in one place.
        """
        from quoss.channel import background, detector

        assert not hasattr(detector, "gate_signal_fraction")
        assert hasattr(background, "gate_signal_fraction")
        assert detector.NTANOS_SNSPD_TIMING_JITTER_FWHM_S == 50e-12
