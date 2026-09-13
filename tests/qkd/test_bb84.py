"""Tests for `quoss.qkd.bb84`.

Organised by the claim each block defends, not by the function it calls.

- ``TestTheSimulatedObservables`` — **V1**. The forward model, checked against
  its own definition by an independent path: the closed-form gain is compared
  against an explicit Poisson series over the per-photon-number yields, term by
  term, which is the thing the closed form is a summation of. Plus the two limits
  that make the QBER readable (a perfect link gives the optics' error, a dead
  link gives a coin flip) and the vacuum state, which must reproduce Ma et al.
  2005 Eq. (33) exactly rather than approximately.
- ``TestTheApproximationThisModuleDeclines`` — the measurement behind decision 1
  of the module docstring. The published gain ``Y_0 + 1 - e^(-eta mu)`` is
  evaluated beside the exact one, and the point where it returns a probability
  above one is found with a root finder rather than transcribed.
- ``TestTheDecoyBoundIsABound`` — **V1 and V3**, and the most important block
  here. A bound that is not a bound is the failure mode with no symptom: the rate
  stays plausible and the security claim is void. Three checks. That the bound
  never exceeds the truth it bounds, over a sweep of five decades of loss. That
  it agrees with the optimum of the **linear programme it is a closed form of**,
  solved by ``scipy.optimize.linprog`` — an implementation sharing no line of
  code with Ma et al.'s algebra. And that it tightens towards the truth as the
  decoy intensity falls, which is the paper's own statement about its own bound.
- ``TestWhereTheBoundCertifiesNothing`` — the uncertified and clamped branches,
  including the measurement that corrects the intuitive but wrong answer: loss
  alone never breaks the bound; an over-bright signal state does.
- ``TestTheOptimalIntensity`` — **V2**. Ma et al. 2005 Eq. (12) gives the
  analytic optimum ``mu`` in the loss-dominated limit. It is solved here from the
  published equation and compared against numerically maximising *this module's*
  full rate, with a tolerance that is the size of the terms Eq. (12) drops rather
  than a number chosen to pass.
- ``TestTheKeyRate`` — the assembled rate: the ordering chain over a wide sweep,
  the monotonicities that must hold, and the three ways the GLLP asymmetry shows
  up (error correction is paid on everything, privacy amplification only on the
  certified single-photon part).
- ``TestTheConfigurationIsRejectedWhenImpossible`` — every ``DomainError``.
- ``TestNtanos2021`` — the named constructor, and the arithmetic disagreement in
  the source sentence turned from a prose claim into a test that runs.
- ``TestTheRegistryAndModuleSurface`` — that the name resolves after import, and
  the negative control that no finite-key parameter has leaked into an asymptotic
  module.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest
from scipy.optimize import brentq, linprog, minimize_scalar
from scipy.stats import poisson

from quoss.core.errors import ConfigurationError, DegradationLog, DomainError
from quoss.core.types import FloatArray, FloatLike
from quoss.qkd.base import (
    NTANOS_SOURCE_PULSE_RATE_HZ,
    PROTOCOLS,
    KeyRegime,
    LinkConditions,
    QkdProtocol,
    binary_entropy,
)
from quoss.qkd.bb84 import (
    NTANOS_DECOY_INTENSITY,
    NTANOS_ERROR_CORRECTION_EFFICIENCY,
    NTANOS_INTERFEROMETER_VISIBILITY,
    NTANOS_SIGNAL_INTENSITY,
    NTANOS_STATE_COUNTS,
    VACUUM_ERROR_RATE,
    Bb84DecoyProtocol,
    IntensityObservables,
    SinglePhotonBounds,
    simulate_intensity,
    single_photon_bounds,
)

# The reference downlink of `channel/link_budget.py`: 0.75 m telescope, zenith,
# 28.541 dB end to end, and the night noise its own noise budget returns. The
# same two numbers `tests/qkd/test_base.py` uses, so the two files describe one
# link.
REFERENCE_TRANSMITTANCE = 1.3993e-03
REFERENCE_NIGHT_NOISE_PER_GATE = 7.8797e-07
REFERENCE_MISALIGNMENT = 0.01

# Five decades of loss, from a link that barely attenuates to one deep below the
# reference pass. Used wherever a claim has to hold over a range rather than at
# a point.
LOSS_SWEEP = (1.0, 1e-01, 1e-02, REFERENCE_TRANSMITTANCE, 1e-04, 1e-05, 1e-06, 1e-08)
NOISE_SWEEP = (0.0, 1e-08, REFERENCE_NIGHT_NOISE_PER_GATE, 1e-05, 1e-03, 7.519554e-03, 0.5, 3.42)


def conditions(
    *,
    transmittance: FloatLike = REFERENCE_TRANSMITTANCE,
    noise_counts_per_gate: FloatLike = REFERENCE_NIGHT_NOISE_PER_GATE,
    misalignment_error: FloatLike = REFERENCE_MISALIGNMENT,
) -> LinkConditions:
    """Build reference conditions with one thing changed."""
    return LinkConditions(
        transmittance=transmittance,
        noise_counts_per_gate=noise_counts_per_gate,
        misalignment_error=misalignment_error,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=1e-09,
    )


def bounds_for(
    link: LinkConditions,
    *,
    signal_intensity: float = NTANOS_SIGNAL_INTENSITY,
    decoy_intensity: float = NTANOS_DECOY_INTENSITY,
    log: DegradationLog | None = None,
) -> SinglePhotonBounds:
    """Run the decoy analysis on a link, the way the protocol does."""
    return single_photon_bounds(
        signal=simulate_intensity(link, intensity=signal_intensity),
        decoy=simulate_intensity(link, intensity=decoy_intensity),
        background_yield=link.background_yield,
        degradations=log if log is not None else DegradationLog(),
    )


def true_single_photon_yield(transmittance: float, background_yield: float) -> float:
    """``Y_1`` as the model actually is, Ma et al. 2005 Eq. (7) first line.

    The truth the decoy bound is a bound on. A single-photon pulse clicks if the
    photon survives, or if the background fires, or both:
    ``1 - (1 - Y_0)(1 - eta)``.
    """
    return background_yield + transmittance * (1.0 - background_yield)


def true_single_photon_qber(
    transmittance: float, background_yield: float, misalignment: float
) -> float:
    """``e_1`` as the model actually is: Ma et al. 2005 Eq. (9) at ``n = 1``."""
    detected = transmittance * (1.0 - background_yield)
    return (VACUUM_ERROR_RATE * background_yield + misalignment * detected) / (
        true_single_photon_yield(transmittance, background_yield)
    )


def reference_protocol(**overrides: float) -> Bb84DecoyProtocol:
    """Ntanos et al.'s configuration with one field changed."""
    signal, decoy, vacuum = NTANOS_STATE_COUNTS
    total = float(signal + decoy + vacuum)
    fields: dict[str, float] = {
        "signal_intensity": NTANOS_SIGNAL_INTENSITY,
        "decoy_intensity": NTANOS_DECOY_INTENSITY,
        "signal_probability": signal / total,
        "decoy_probability": decoy / total,
        "vacuum_probability": vacuum / total,
        "error_correction_efficiency": NTANOS_ERROR_CORRECTION_EFFICIENCY,
    }
    fields.update(overrides)
    return Bb84DecoyProtocol(**fields)


class TestTheSimulatedObservables:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    @pytest.mark.parametrize("intensity", [0.0, 0.11, 0.56, 1.0, 3.0])
    def test_the_gain_is_the_poisson_series_it_claims_to_be(
        self, transmittance: float, intensity: float
    ) -> None:
        """V1, by an independent path.

        `simulate_intensity` returns a closed form, ``1 - (1 - Y_0) e^(-eta mu)``.
        What that closed form *is* is the sum over photon number of "Alice sent n
        photons" times "an n-photon pulse clicks", Ma et al. 2005 Eqs. (7), (8)
        and (10). Summing the series term by term uses none of the algebra that
        collapsed it, so it catches a wrong exponent or a misplaced ``1 - Y_0``
        that a self-comparison would not.
        """
        link = conditions(transmittance=transmittance)
        y0 = float(link.background_yield)
        photons = np.arange(0, 200)
        # Y_n = 1 - (1 - Y_0)(1 - eta)^n: the background fires, or at least one
        # of the n photons survives. Evaluated through `log1p`/`expm1` because
        # written literally it is a difference of two numbers that agree to
        # sixteen digits whenever Y_0 and eta are both around 1e-07 -- which is
        # the reference night link, so the naive spelling would make *this test*
        # the least accurate thing in the comparison.
        if transmittance == 1.0:
            # A perfect link: every pulse carrying at least one photon clicks,
            # and the empty ones are left to the background. The logarithmic
            # form reaches the same answer through log1p(-1) = -inf, which is
            # the right limit arrived at by a route this suite turns into an
            # error (`filterwarnings = ["error"]`).
            per_photon_yield = np.where(photons == 0, y0, 1.0)
        else:
            per_photon_yield = -np.expm1(np.log1p(-y0) + photons * np.log1p(-transmittance))
        series = float(np.sum(poisson.pmf(photons, intensity) * per_photon_yield))

        gain = float(simulate_intensity(link, intensity=intensity).gain)
        assert gain == pytest.approx(series, rel=1e-12, abs=0.0)

    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    @pytest.mark.parametrize("noise", NOISE_SWEEP)
    def test_the_qber_is_the_published_mixture(self, transmittance: float, noise: float) -> None:
        """V1. The QBER against Ma et al. 2005 Eq. (11), rearranged.

        The module spells it as a mixture, ``e_0 + (e_mis - e_0)(Q - Y_0)/Q``;
        the paper spells it as a quotient, ``(e_0 Y_0 + e_mis (Q - Y_0))/Q``. The
        two are the same algebra and this is the check that the rearrangement did
        not lose a term — evaluated independently here, not by calling the module
        twice.
        """
        link = conditions(transmittance=transmittance, noise_counts_per_gate=noise)
        y0 = float(link.background_yield)
        observed = simulate_intensity(link, intensity=NTANOS_SIGNAL_INTENSITY)
        gain = float(observed.gain)
        published = (VACUUM_ERROR_RATE * y0 + REFERENCE_MISALIGNMENT * (gain - y0)) / gain
        assert float(observed.qber) == pytest.approx(published, rel=1e-12)

    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    @pytest.mark.parametrize("noise", NOISE_SWEEP)
    @pytest.mark.parametrize("misalignment", [0.0, 0.01, 0.25, 0.5])
    def test_the_qber_never_leaves_the_bracket_its_two_causes_set(
        self, transmittance: float, noise: float, misalignment: float
    ) -> None:
        """The QBER is between the optics and a coin flip, always.

        Not a range check for tidiness: `KeyRate` raises on a QBER above one half
        — above one half is an inverted bit convention, not a worse link — so an
        expression that can exceed it by one bit of rounding turns a good link
        into a traceback. The mixture spelling makes the bracket hold in floating
        point, and this is the sweep that says so, including the two endpoints
        (``e_mis = 0`` and ``e_mis = 1/2``) where the bracket is tightest.
        """
        link = conditions(
            transmittance=transmittance,
            noise_counts_per_gate=noise,
            misalignment_error=misalignment,
        )
        qber = float(simulate_intensity(link, intensity=NTANOS_SIGNAL_INTENSITY).qber)
        assert misalignment <= qber <= VACUUM_ERROR_RATE

    def test_the_vacuum_state_reproduces_the_published_special_case_exactly(self) -> None:
        """V2. Ma et al. 2005 Eq. (33): ``Q_vacuum = Y_0`` and ``E_vacuum = 1/2``.

        Exactly, not approximately, and not by a branch on ``intensity == 0``:
        the general expression has to give it. A model that needed a special case
        here would be one whose vacuum decoy state measures something other than
        what the bound assumes it measures.
        """
        link = conditions()
        vacuum = simulate_intensity(link, intensity=0.0)
        assert float(vacuum.gain) == float(link.background_yield)
        assert float(vacuum.qber) == VACUUM_ERROR_RATE

    def test_a_perfect_link_leaves_only_the_optics(self) -> None:
        """The bright limit: every click is a signal click, so ``E -> e_mis``."""
        link = conditions(transmittance=1.0, noise_counts_per_gate=0.0)
        observed = simulate_intensity(link, intensity=20.0)
        assert float(observed.gain) == pytest.approx(1.0, abs=1e-08)
        assert float(observed.qber) == pytest.approx(REFERENCE_MISALIGNMENT, rel=1e-08)

    def test_a_dead_link_leaves_only_the_coin_flip(self) -> None:
        """The dark limit: every click is background, so ``E -> 1/2``."""
        link = conditions(transmittance=1e-12, noise_counts_per_gate=1e-03)
        assert float(simulate_intensity(link, intensity=0.56).qber) == pytest.approx(
            VACUUM_ERROR_RATE, rel=1e-08
        )

    @pytest.mark.physics
    def test_the_gain_rises_with_the_intensity_and_with_the_link(self) -> None:
        """Two monotonicities, because a sign error passes every limit test."""
        link = conditions()
        gains = [float(simulate_intensity(link, intensity=mu).gain) for mu in (0.0, 0.1, 0.5, 1.0)]
        assert gains == sorted(gains)
        assert len(set(gains)) == len(gains)

        by_link = [
            float(simulate_intensity(conditions(transmittance=eta), intensity=0.56).gain)
            for eta in sorted(LOSS_SWEEP)
        ]
        assert by_link == sorted(by_link)

    def test_a_link_where_nothing_can_click_still_answers(self) -> None:
        """The one case where the QBER's denominator is zero.

        A vacuum pulse on a link with no background produces no clicks at all,
        so the fraction of the clicks that came from the signal is ``0/0``. The
        answer is the vacuum's one half — there are no sifted bits behind it
        either way — and the point of the test is that it is an answer and not
        a ``RuntimeWarning``, which this suite turns into an error.
        """
        dark = conditions(transmittance=1e-06, noise_counts_per_gate=0.0)
        silent = simulate_intensity(dark, intensity=0.0)
        assert float(silent.gain) == 0.0
        assert float(silent.qber) == VACUUM_ERROR_RATE

    def test_an_empty_pass_gives_empty_observables(self) -> None:
        """A pass segmented before its first visible sample is empty and legal."""
        link = conditions(transmittance=np.array([]))
        observed = simulate_intensity(link, intensity=0.56)
        assert observed.shape == (0,)
        assert observed.gain.size == 0

    def test_the_stored_arrays_cannot_be_moved_afterwards(self) -> None:
        observed = simulate_intensity(
            conditions(transmittance=np.array([1e-03, 1e-04])), intensity=0.5
        )
        with pytest.raises(ValueError, match="read-only"):
            observed.gain[0] = 1.0

    @pytest.mark.parametrize("bad", [-1e-09, -1.0, float("nan"), float("inf")])
    def test_a_negative_or_infinite_intensity_is_refused(self, bad: float) -> None:
        with pytest.raises(DomainError, match="mean photon number"):
            simulate_intensity(conditions(), intensity=bad)


class TestTheApproximationThisModuleDeclines:
    """Decision 1 of the module docstring, measured rather than asserted."""

    @staticmethod
    def _published_gain(transmittance: float, noise: float, intensity: float) -> float:
        """Ma et al. 2005 Eq. (10) / Ntanos et al. 2021 Eq. (A4), as printed."""
        return float(-np.expm1(-noise)) + 1.0 - float(np.exp(-transmittance * intensity))

    @pytest.mark.parametrize(
        ("noise", "expected_percent"),
        [
            (REFERENCE_NIGHT_NOISE_PER_GATE, 7.8718e-05),
            (7.519554e-03, 0.070965),
            (7.0712e-02, 0.077502),
        ],
    )
    def test_the_size_of_the_difference_at_three_operating_points(
        self, noise: float, expected_percent: float
    ) -> None:
        """The three numbers the module docstring cites, computed here.

        Night, clear-sky daylight on the 0.75 m telescope, and the same daylight
        on the 2.3 m one. The published form is high in every case, because what
        it double-counts is the gates where the sky and the signal both fire.
        """
        link = conditions(noise_counts_per_gate=noise)
        exact = float(simulate_intensity(link, intensity=NTANOS_SIGNAL_INTENSITY).gain)
        published = self._published_gain(REFERENCE_TRANSMITTANCE, noise, NTANOS_SIGNAL_INTENSITY)
        assert published > exact
        assert 100.0 * (published / exact - 1.0) == pytest.approx(expected_percent, rel=1e-04)

    def test_the_published_form_returns_a_probability_above_one(self) -> None:
        """The failure that is not a matter of degree.

        A gain above one is not a slightly wrong gain; `KeyRate` rejects it, and
        it is the same conflation of a mean with a probability that
        `quoss.channel.background` found in Ntanos et al. Eq. (20). The crossing
        point is found with a root finder rather than transcribed, so it cannot
        rot: what is asserted is that a crossing exists inside the range of sky
        brightness this project models, and that the exact form has none.
        """
        crossing = brentq(
            lambda noise: (
                self._published_gain(REFERENCE_TRANSMITTANCE, noise, NTANOS_SIGNAL_INTENSITY) - 1.0
            ),
            0.1,
            50.0,
        )
        assert crossing == pytest.approx(7.152, abs=1e-03)
        # Above it the published form is not a probability; the exact one still is.
        assert self._published_gain(REFERENCE_TRANSMITTANCE, 10.0, NTANOS_SIGNAL_INTENSITY) > 1.0
        exact = simulate_intensity(
            conditions(noise_counts_per_gate=10.0), intensity=NTANOS_SIGNAL_INTENSITY
        )
        assert float(exact.gain) < 1.0

    def test_keeping_the_published_error_numerator_would_break_one_half(self) -> None:
        """Decision 2: why the QBER is a mixture and not the printed quotient.

        Ma et al.'s numerator is ``e_0 Y_0 + e_mis (1 - e^(-eta mu))``. Combined
        with the *exact* gain — which is what this module computes — it gives a
        QBER above one half above a measurable sky brightness, and the ITU
        bright-sunshine case this project already models sits 12.6 % below that
        point rather than comfortably away from it.
        """

        def mixed_qber(noise: float) -> float:
            link = conditions(noise_counts_per_gate=noise)
            gain = float(simulate_intensity(link, intensity=NTANOS_SIGNAL_INTENSITY).gain)
            y0 = float(link.background_yield)
            signal = 1.0 - float(np.exp(-REFERENCE_TRANSMITTANCE * NTANOS_SIGNAL_INTENSITY))
            return (VACUUM_ERROR_RATE * y0 + REFERENCE_MISALIGNMENT * signal) / gain

        crossing = brentq(lambda noise: mixed_qber(noise) - VACUUM_ERROR_RATE, 1.0, 10.0)
        assert crossing == pytest.approx(3.912, abs=1e-03)
        assert 3.42 / crossing == pytest.approx(0.874, abs=1e-03)
        # The mixture spelling stays inside the bracket at the same point.
        assert mixed_qber(5.0) > VACUUM_ERROR_RATE
        beyond = simulate_intensity(
            conditions(noise_counts_per_gate=5.0), intensity=NTANOS_SIGNAL_INTENSITY
        )
        assert float(beyond.qber) <= VACUUM_ERROR_RATE


class TestTheDecoyBoundIsABound:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_it_never_exceeds_the_truth_it_bounds(self, transmittance: float) -> None:
        """V1, and the check with no symptom if it fails.

        ``Y_1`` is bounded from below and ``e_1`` from above. If either crosses
        the true value the rate is still a plausible number and the security
        claim is void — nothing downstream can detect it, because downstream only
        sees the bound. The true values come from the same model the observables
        came from, evaluated at ``n = 1`` by a separate expression.
        """
        link = conditions(transmittance=transmittance)
        y0 = float(link.background_yield)
        bounds = bounds_for(link)

        truth = true_single_photon_yield(transmittance, y0)
        assert 0.0 < float(bounds.single_photon_yield) <= truth
        assert float(bounds.single_photon_qber) >= true_single_photon_qber(
            transmittance, y0, REFERENCE_MISALIGNMENT
        )

    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_the_certified_gain_never_exceeds_the_total_gain(self, transmittance: float) -> None:
        """``Q_1 <= Q_mu``, which is what makes the rate orderable.

        `KeyRate` refuses a secret rate above the sifted one. That ordering is
        inherited from this inequality, so it is checked where it is created
        rather than only where it is enforced.
        """
        link = conditions(transmittance=transmittance)
        bounds = bounds_for(link)
        signal_gain = float(simulate_intensity(link, intensity=NTANOS_SIGNAL_INTENSITY).gain)
        assert float(bounds.single_photon_gain) <= signal_gain

    @pytest.mark.reference
    @pytest.mark.parametrize("transmittance", [1e-02, REFERENCE_TRANSMITTANCE, 1e-04, 1e-06])
    def test_it_agrees_with_the_linear_programme_it_is_a_closed_form_of(
        self, transmittance: float
    ) -> None:
        """V3. The published algebra against a general-purpose LP solver.

        Ma et al.'s Eq. (34) is the analytic solution of a small optimisation:
        over all yield sequences ``Y_0, Y_1, Y_2, ...`` in ``[0, 1]`` that
        reproduce the two measured gains and the measured ``Y_0``, minimise
        ``Y_1``. Handing that programme to ``scipy.optimize.linprog`` shares no
        line of reasoning with their derivation, so agreement is evidence about
        the formula and not about the transcription of it.

        The series is truncated at 40 photons, where the Poisson tail of a
        ``mu = 0.56`` source is below 1e-40 — far under the tolerance asserted,
        so the truncation cannot be what makes the two agree.
        """
        link = conditions(transmittance=transmittance)
        mu, nu = NTANOS_SIGNAL_INTENSITY, NTANOS_DECOY_INTENSITY
        y0 = float(link.background_yield)
        signal_gain = float(simulate_intensity(link, intensity=mu).gain)
        decoy_gain = float(simulate_intensity(link, intensity=nu).gain)

        photons = np.arange(0, 41)
        objective = np.zeros(photons.size)
        objective[1] = 1.0
        equalities = np.vstack(
            [poisson.pmf(photons, mu), poisson.pmf(photons, nu), np.eye(photons.size)[0]]
        )
        targets = np.array([signal_gain, decoy_gain, y0])
        solved = linprog(
            objective, A_eq=equalities, b_eq=targets, bounds=(0.0, 1.0), method="highs"
        )
        assert solved.status == 0

        assert float(bounds_for(link).single_photon_yield) == pytest.approx(
            float(solved.fun), rel=1e-09
        )

    @pytest.mark.physics
    def test_it_tightens_as_the_decoy_state_weakens(self) -> None:
        """The paper's own statement about its own bound, checked.

        Ma et al.'s deviation ``beta_Y1`` is first order in ``nu``, so a weaker
        decoy state certifies more of the true yield. That the ratio rises
        monotonically towards one is the sign that the bound is the right shape
        and not merely a number in the right range — and it is also the reason
        this module is asymptotic-only: what stops ``nu`` going to zero in an
        experiment is counting statistics, which is `finite_key.py`.
        """
        link = conditions()
        truth = true_single_photon_yield(REFERENCE_TRANSMITTANCE, float(link.background_yield))
        ratios = [
            float(bounds_for(link, decoy_intensity=nu).single_photon_yield) / truth
            for nu in (0.3, 0.2, 0.11, 0.05, 0.01, 0.001)
        ]
        assert ratios == sorted(ratios)
        assert ratios[-1] == pytest.approx(1.0, abs=1e-03)

    def test_the_reference_point_certifies_the_measured_fraction(self) -> None:
        """The two numbers the module docstring cites for the reference link."""
        link = conditions()
        y0 = float(link.background_yield)
        bounds = bounds_for(link)
        certified_fraction = float(bounds.single_photon_yield) / true_single_photon_yield(
            REFERENCE_TRANSMITTANCE, y0
        )
        assert 100.0 * certified_fraction == pytest.approx(96.13, abs=5e-03)
        inflation = float(bounds.single_photon_qber) / true_single_photon_qber(
            REFERENCE_TRANSMITTANCE, y0, REFERENCE_MISALIGNMENT
        )
        assert inflation == pytest.approx(1.1595, abs=5e-05)

    def test_the_two_published_prefactors_agree(self) -> None:
        """``Q_1 = Y_1 mu e^-mu``: Eq. (35) is Eq. (34) times the Poisson weight.

        They are written out separately so a reader can match the paper line for
        line, which is exactly the arrangement in which a typo in one of them
        goes unnoticed.
        """
        bounds = bounds_for(conditions())
        weight = NTANOS_SIGNAL_INTENSITY * float(np.exp(-NTANOS_SIGNAL_INTENSITY))
        assert float(bounds.single_photon_gain) == pytest.approx(
            float(bounds.single_photon_yield) * weight, rel=1e-12
        )

    def test_a_pass_is_the_same_call_with_arrays(self) -> None:
        link = conditions(transmittance=np.array([1e-05, 1e-04, REFERENCE_TRANSMITTANCE]))
        bounds = bounds_for(link)
        assert bounds.shape == (3,)
        assert bool(np.all(np.diff(bounds.single_photon_yield) > 0.0))

    def test_an_empty_pass_certifies_nothing_and_warns_about_nothing(self) -> None:
        log = DegradationLog()
        bounds = bounds_for(conditions(transmittance=np.array([])), log=log)
        assert bounds.shape == (0,)
        assert len(log) == 0


class TestWhereTheBoundCertifiesNothing:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_loss_alone_never_breaks_it(self, transmittance: float) -> None:
        """The intuitive answer, measured and found wrong.

        One expects the decoy analysis to give up on a dark link. It does not:
        with asymptotically exact data the bound stays positive across every
        decade tested and settles onto ``Y_0``, because a link with no signal
        left still certifies that a single photon would have clicked as often as
        the background does. This test exists because the module docstring
        originally claimed the opposite, and a wrong "when does this fail"
        sentence is worse than no sentence.
        """
        log = DegradationLog()
        bounds = bounds_for(conditions(transmittance=transmittance), log=log)
        assert bool(bounds.certified)
        assert not [entry for entry in log.entries if "uncertified" in entry.code]

    def test_the_bound_settles_onto_the_background_in_the_dark(self) -> None:
        """What the bound converges to when the signal is gone, and how closely.

        With no transmittance left, the only thing that can still make a
        single-photon pulse click is the background, so the true ``Y_1`` is
        ``Y_0``. The bound does not quite reach it: it keeps its own slack, the
        first-order-in-``nu`` deviation Ma et al. call ``beta_Y1``, which is
        **1.221 %** at Ntanos et al.'s intensities and vanishes as the decoy
        state weakens. Asserting equality here would have meant asserting the
        slack away.
        """
        link = conditions(transmittance=1e-12)
        y0 = float(link.background_yield)
        assert float(bounds_for(link).single_photon_yield) / y0 == pytest.approx(0.98779, abs=1e-05)
        assert float(
            bounds_for(link, decoy_intensity=1e-04).single_photon_yield
        ) / y0 == pytest.approx(1.0, abs=1e-04)

    @pytest.mark.physics
    def test_an_over_bright_signal_state_is_what_breaks_it(self) -> None:
        """What does break it, with the threshold found rather than transcribed.

        A bright signal state is mostly multi-photon, and the decoy data can no
        longer rule out that all of the gain came from there. The crossing is
        located with a root finder so that the number in the module docstring is
        one this test produced.
        """

        def certified_yield(intensity: float) -> float:
            link = conditions(transmittance=1e-03)
            bounds = single_photon_bounds(
                signal=simulate_intensity(link, intensity=intensity),
                decoy=simulate_intensity(link, intensity=0.1),
                background_yield=link.background_yield,
                degradations=DegradationLog(),
            )
            # Below the crossing the module clamps to zero, so the root finder is
            # given the raw ordering through the `certified` flag instead.
            return float(bounds.single_photon_yield) if bool(bounds.certified) else -1.0

        assert certified_yield(3.0) > 0.0
        assert certified_yield(5.0) < 0.0
        crossing = brentq(certified_yield, 3.0, 5.0, xtol=1e-04)
        assert crossing == pytest.approx(3.72, abs=1e-02)

    def test_an_uncertified_sample_reports_no_information_rather_than_none_needed(self) -> None:
        """The substitution that matters: ``e_1 = 1/2``, never ``e_1 = 0``.

        Zero would be a *perfect* single-photon error rate drawn exactly where
        the analysis failed — the most flattering possible number in the place
        where the least is known. One half is the value that carries no
        information: ``h(1/2) = 1``, and the single-photon term of the rate
        vanishes.
        """
        log = DegradationLog()
        link = conditions(transmittance=1e-03)
        bounds = single_photon_bounds(
            signal=simulate_intensity(link, intensity=5.0),
            decoy=simulate_intensity(link, intensity=0.1),
            background_yield=link.background_yield,
            degradations=log,
        )
        assert not bool(bounds.certified)
        assert float(bounds.single_photon_yield) == 0.0
        assert float(bounds.single_photon_gain) == 0.0
        assert float(bounds.single_photon_qber) == VACUUM_ERROR_RATE
        assert float(binary_entropy(bounds.single_photon_qber)) == 1.0

        entry = log.entries[0]
        assert entry.code == "bb84.single-photon-yield-uncertified"
        assert entry.details["uncertified_samples"] == 1
        assert entry.details["signal_intensity"] == 5.0

    def test_the_log_counts_the_samples_and_not_the_calls(self) -> None:
        """One entry per call, carrying how many of the pass it is about."""
        log = DegradationLog()
        link = conditions(transmittance=np.array([1e-03] * 4))
        single_photon_bounds(
            signal=simulate_intensity(link, intensity=5.0),
            decoy=simulate_intensity(link, intensity=0.1),
            background_yield=link.background_yield,
            degradations=log,
        )
        assert len(log) == 1
        assert log.entries[0].details["uncertified_samples"] == 4
        assert log.entries[0].details["total_samples"] == 4

    def test_an_unconstrained_error_rate_is_clamped_and_recorded(self) -> None:
        """The other branch: ``e_1`` bounded above one half is bounded by nothing.

        Carrying it on would give ``h(e_1) > 1`` and a negative single-photon
        term — privacy amplification removing more than the whole key. Clamped,
        the term is exactly zero, which is what an unconstrained error rate is
        worth.
        """
        log = DegradationLog()
        bounds = bounds_for(conditions(transmittance=1e-08), log=log)
        assert bool(bounds.certified)
        assert float(bounds.single_photon_qber) == VACUUM_ERROR_RATE
        assert log.entries[0].code == "bb84.single-photon-qber-clamped"
        assert log.entries[0].details["worst_bound"] > VACUUM_ERROR_RATE

    @pytest.mark.parametrize(("signal", "decoy"), [(0.56, 0.56), (0.11, 0.56), (0.56, 0.0)])
    def test_a_decoy_that_is_not_weaker_is_refused(self, signal: float, decoy: float) -> None:
        """``0 < nu < mu`` is not a convention: outside it the bound inverts."""
        link = conditions()
        with pytest.raises(DomainError, match="0 < nu < mu"):
            single_photon_bounds(
                signal=simulate_intensity(link, intensity=signal),
                decoy=simulate_intensity(link, intensity=decoy),
                background_yield=link.background_yield,
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize("bad", [-1e-09, 1.5, float("nan")])
    def test_a_background_yield_that_is_not_a_probability_is_refused(self, bad: float) -> None:
        """The mean-versus-probability trap, at the one seam it can still enter."""
        link = conditions()
        with pytest.raises(DomainError):
            single_photon_bounds(
                signal=simulate_intensity(link, intensity=0.56),
                decoy=simulate_intensity(link, intensity=0.11),
                background_yield=bad,
                degradations=DegradationLog(),
            )

    def test_shapes_that_do_not_broadcast_are_refused(self) -> None:
        signal = simulate_intensity(
            conditions(transmittance=np.array([1e-3, 1e-4, 1e-5])), intensity=0.56
        )
        decoy = simulate_intensity(conditions(transmittance=np.array([1e-3, 1e-4])), intensity=0.11)
        with pytest.raises(DomainError, match="broadcast"):
            single_photon_bounds(
                signal=signal,
                decoy=decoy,
                background_yield=0.0,
                degradations=DegradationLog(),
            )


class TestTheOptimalIntensity:
    """V2: the analytic optimum of Ma et al. 2005 Eq. (12)."""

    @staticmethod
    def _published_optimum(misalignment: float, efficiency: float) -> float:
        """Solve ``(1 - mu) e^-mu = f(e) h(e) / (1 - h(e))``, Ma et al. Eq. (12).

        Their derivation drops ``Y_0`` entirely and takes the decoy estimate to
        be perfect, so the number it returns is the optimum of the *idealised*
        rate. That is exactly what makes it a useful check: it is arrived at by
        an argument this module does not make.
        """
        entropy = float(binary_entropy(misalignment))
        target = efficiency * entropy / (1.0 - entropy)
        return float(brentq(lambda mu: (1.0 - mu) * np.exp(-mu) - target, 1e-06, 0.999))

    @pytest.mark.reference
    @pytest.mark.parametrize("transmittance", [1e-02, REFERENCE_TRANSMITTANCE, 1e-04])
    def test_maximising_this_modules_rate_finds_the_published_optimum(
        self, transmittance: float
    ) -> None:
        """The intensity that maximises the full rate, against the published one.

        The tolerance is **derived, not chosen**: Eq. (12) neglects the
        background (an error of order ``Y_0 / (eta mu)``) and a non-zero decoy
        intensity (an error of order ``nu / mu``), so the two may differ by about
        the size of what was dropped and no more. Below ``eta ~ 1e-05`` the first
        term stops being small for this receiver and the comparison stops being
        one — which is a property of Eq. (12), not of this module, and is why the
        sweep stops where it does.
        """
        decoy_intensity = 1e-03
        published = self._published_optimum(
            REFERENCE_MISALIGNMENT, NTANOS_ERROR_CORRECTION_EFFICIENCY
        )
        link = conditions(transmittance=transmittance)

        def negative_rate(intensity: float) -> float:
            protocol = reference_protocol(
                signal_intensity=intensity, decoy_intensity=decoy_intensity
            )
            return -float(protocol.key_rate(link, degradations=DegradationLog()).secure_per_pulse)

        found = float(
            minimize_scalar(
                negative_rate, bounds=(0.05, 2.0), method="bounded", options={"xatol": 1e-08}
            ).x
        )
        neglected = float(link.background_yield) / (transmittance * published) + 2.0 * (
            decoy_intensity / published
        )
        assert abs(found / published - 1.0) <= neglected

    def test_the_optimum_is_where_the_two_terms_of_the_rate_balance(self) -> None:
        """Why an optimum exists at all, in one assertion.

        Raising ``mu`` raises the gain, so the error-correction cost rises
        linearly; but the *fraction* of pulses carrying exactly one photon,
        ``mu e^-mu``, turns over at ``mu = 1``. The rate is therefore not
        monotone, which is the whole reason a decoy protocol has an intensity to
        choose. A model where brighter were always better would have a sign error
        in the GLLP term.
        """
        link = conditions()
        rates = [
            float(
                reference_protocol(signal_intensity=mu, decoy_intensity=1e-03)
                .key_rate(link, degradations=DegradationLog())
                .secure_per_pulse
            )
            for mu in (0.1, 0.4, 0.77, 1.5, 3.0)
        ]
        assert rates[2] == max(rates)
        assert rates[-1] < rates[0]


class TestTheKeyRate:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    @pytest.mark.parametrize("noise", NOISE_SWEEP)
    def test_the_ordering_chain_holds_everywhere(self, transmittance: float, noise: float) -> None:
        """``gain >= sifted >= secure >= 0``, over 64 operating points.

        `KeyRate` raises on a violation, so what this sweep really asserts is
        that no reachable link turns a legitimate configuration into a traceback.
        The corners matter: zero background, a sky of 3.42 counts per gate, and a
        transmittance of one.
        """
        rate = reference_protocol().key_rate(
            conditions(transmittance=transmittance, noise_counts_per_gate=noise),
            degradations=DegradationLog(),
        )
        gain = float(rate.gain)
        assert gain >= float(rate.sifted_per_pulse) >= float(rate.secure_per_pulse) >= 0.0
        assert 0.0 <= float(rate.qber) <= VACUUM_ERROR_RATE

    def test_the_sifted_rate_is_the_gain_times_the_protocol_efficiency(self) -> None:
        """Sifting discards; it does not create. And the decoys are paid for."""
        protocol = reference_protocol()
        rate = protocol.key_rate(conditions(), degradations=DegradationLog())
        assert float(rate.sifted_per_pulse) == pytest.approx(
            protocol.protocol_efficiency * float(rate.gain), rel=1e-12
        )
        assert protocol.protocol_efficiency < 0.5

    def test_the_reference_link_at_zenith(self) -> None:
        """V4 — a snapshot of this module's own output, and nothing more.

        The number is not traceable to a published one: Ntanos et al. report a
        maximum normalised rate of 3.9e-04 bit per pulse over their whole study,
        for a telescope and an elevation they do not pin down, and their own loss
        budget carries a 0.906 dB residual this project could not account for
        (`tests/channel/test_link_budget.py`). So this asserts that a refactor did
        not move the number, and `test_it_stays_under_the_best_case_of_the_source`
        asserts the one thing that *is* derivable about the comparison.
        """
        rate = reference_protocol().key_rate(conditions(), degradations=DegradationLog())
        assert float(rate.secure_per_pulse) == pytest.approx(1.180893e-04, rel=1e-06)
        assert float(rate.secure_bit_s) == pytest.approx(11808.93, rel=1e-06)
        assert float(rate.qber) == pytest.approx(1.049243e-02, rel=1e-06)
        assert rate.regime is KeyRegime.ASYMPTOTIC
        assert rate.protocol == "bb84-decoy"

    def test_it_stays_above_the_best_case_of_the_source(self) -> None:
        """The one-sided comparison that is derivable, stated as such.

        Ntanos et al.'s 3.9e-04 bit per pulse is a maximum over passes whose
        elevations are not all zenith, computed with a loss budget 0.906 dB
        heavier than the one this project reconstructs. A zenith rate on their
        largest telescope must therefore come out *above* it, and that is all the
        comparison supports — a two-sided tolerance here would be a number chosen
        to pass rather than derived. The aperture scaling is the collecting-area
        ratio only, which is why this is a bound and not a reproduction.
        """
        area_ratio = (2.3 / 0.75) ** 2
        rate = reference_protocol().key_rate(
            conditions(transmittance=REFERENCE_TRANSMITTANCE * area_ratio),
            degradations=DegradationLog(),
        )
        assert float(rate.secure_per_pulse) > 3.9e-04

    @pytest.mark.physics
    def test_the_rate_rises_with_the_link_and_falls_with_the_sky(self) -> None:
        by_link = [
            float(
                reference_protocol()
                .key_rate(conditions(transmittance=eta), degradations=DegradationLog())
                .secure_per_pulse
            )
            for eta in sorted(LOSS_SWEEP)
        ]
        assert by_link == sorted(by_link)

        by_sky = [
            float(
                reference_protocol()
                .key_rate(conditions(noise_counts_per_gate=noise), degradations=DegradationLog())
                .secure_per_pulse
            )
            for noise in sorted(NOISE_SWEEP)
        ]
        assert by_sky == sorted(by_sky, reverse=True)

    def test_error_correction_is_a_cost_and_only_a_cost(self) -> None:
        """Larger ``f`` can never give more key, and at the Shannon limit it gives most."""
        link = conditions()
        rates = [
            float(
                reference_protocol(error_correction_efficiency=f)
                .key_rate(link, degradations=DegradationLog())
                .secure_per_pulse
            )
            for f in (1.0, 1.16, 1.22, 2.0, 5.0)
        ]
        assert rates == sorted(rates, reverse=True)

    def test_the_rate_is_zero_where_nothing_is_certified(self) -> None:
        """No certified single-photon part, no key — and no negative one either."""
        link = conditions(transmittance=1e-03)
        protocol = reference_protocol(signal_intensity=5.0, decoy_intensity=0.1)
        log = DegradationLog()
        rate = protocol.key_rate(link, degradations=log)
        assert float(rate.secure_per_pulse) == 0.0
        assert not bool(rate.has_key)
        assert log.entries[0].code == "bb84.single-photon-yield-uncertified"

    def test_the_gllp_asymmetry_is_visible_in_the_rate(self) -> None:
        """Error correction is paid on everything; secrecy is bought only on ``Q_1``.

        The test is the one configuration where the two can be separated: raise
        the signal intensity so that the gain rises while the single-photon
        fraction ``mu e^-mu`` falls. A model that priced privacy amplification on
        the whole gain would reward that; GLLP punishes it, and the sifted rate
        going up while the secret rate goes down is the visible signature.
        """
        link = conditions()
        dim = reference_protocol(signal_intensity=0.56).key_rate(
            link, degradations=DegradationLog()
        )
        bright = reference_protocol(signal_intensity=2.5).key_rate(
            link, degradations=DegradationLog()
        )
        assert float(bright.sifted_per_pulse) > float(dim.sifted_per_pulse)
        assert float(bright.secure_per_pulse) < float(dim.secure_per_pulse)

    def test_spending_fewer_pulses_on_decoys_scales_the_rate_exactly(self) -> None:
        """In the asymptotic limit the decoy fractions are pure cost.

        The bound they buy is already exact however few of them are sent, so the
        rate is strictly proportional to the signal fraction. That proportionality
        is the sharpest possible statement of what this module cannot see, and the
        reason its results are labelled `ASYMPTOTIC`.
        """
        link = conditions()
        generous = reference_protocol(
            signal_probability=0.98, decoy_probability=0.01, vacuum_probability=0.01
        ).key_rate(link, degradations=DegradationLog())
        frugal = reference_protocol().key_rate(link, degradations=DegradationLog())
        expected = 0.98 / reference_protocol().signal_probability
        assert float(generous.secure_per_pulse) / float(frugal.secure_per_pulse) == pytest.approx(
            expected, rel=1e-12
        )

    def test_a_pass_comes_back_with_the_shape_it_went_in_with(self) -> None:
        link = conditions(transmittance=np.array([1e-05, 3.06e-04, REFERENCE_TRANSMITTANCE]))
        rate = reference_protocol().key_rate(link, degradations=DegradationLog())
        assert rate.shape == (3,)
        assert rate.pulse_rate_hz == NTANOS_SOURCE_PULSE_RATE_HZ

    def test_an_empty_pass_gives_an_empty_rate(self) -> None:
        rate = reference_protocol().key_rate(
            conditions(transmittance=np.array([])), degradations=DegradationLog()
        )
        assert rate.shape == (0,)
        assert rate.secure_bit_s.size == 0


class TestTheConfigurationIsRejectedWhenImpossible:
    @pytest.mark.parametrize(
        ("signal", "decoy"),
        [(0.56, 0.56), (0.11, 0.56), (0.56, 0.0), (0.56, -0.1), (float("inf"), 0.1)],
    )
    def test_intensities_that_invert_the_bound(self, signal: float, decoy: float) -> None:
        with pytest.raises(DomainError):
            reference_protocol(signal_intensity=signal, decoy_intensity=decoy)

    @pytest.mark.parametrize(
        "field", ["signal_probability", "decoy_probability", "vacuum_probability"]
    )
    @pytest.mark.parametrize("bad", [0.0, 1.0, -0.1, 1.5])
    def test_a_state_that_is_never_sent_is_a_different_protocol(
        self, field: str, bad: float
    ) -> None:
        """A zero probability is not "skip that state": the bound is different."""
        with pytest.raises(DomainError, match="in \\(0, 1\\)"):
            reference_protocol(**{field: bad})

    @pytest.mark.parametrize("total", [0.9, 1.1, 0.5])
    def test_probabilities_that_do_not_sum_to_one(self, total: float) -> None:
        with pytest.raises(DomainError, match="sum to 1"):
            reference_protocol(
                signal_probability=0.8 * total,
                decoy_probability=0.1 * total,
                vacuum_probability=0.1 * total,
            )

    def test_rounded_decimals_are_allowed_to_be_rounded(self) -> None:
        """0.76 + 0.05 + 0.19 is what a person types, and it must be accepted."""
        protocol = reference_protocol(
            signal_probability=0.76, decoy_probability=0.05, vacuum_probability=0.19
        )
        assert protocol.protocol_efficiency == pytest.approx(0.38)

    @pytest.mark.parametrize("bad", [0.999, 0.5, 0.0, -1.0, float("nan")])
    def test_error_correction_below_the_shannon_limit(self, bad: float) -> None:
        with pytest.raises(DomainError, match="Shannon"):
            reference_protocol(error_correction_efficiency=bad)

    def test_the_configuration_cannot_be_edited_after_construction(self) -> None:
        protocol = reference_protocol()
        with pytest.raises(AttributeError):
            protocol.signal_intensity = 1.0  # type: ignore[misc]


class TestNtanos2021:
    def test_the_named_constructor_is_their_parameter_set(self) -> None:
        protocol = Bb84DecoyProtocol.ntanos_2021()
        assert protocol.signal_intensity == NTANOS_SIGNAL_INTENSITY == 0.56
        assert protocol.decoy_intensity == NTANOS_DECOY_INTENSITY == 0.11
        assert protocol.error_correction_efficiency == 1.22
        assert protocol.protocol_efficiency == pytest.approx(0.380952, abs=1e-06)

    def test_the_state_ratio_printed_in_the_source_does_not_give_the_q_printed_beside_it(
        self,
    ) -> None:
        """The arithmetic disagreement of `NTANOS_STATE_COUNTS`, as a test.

        Their §4.1 says "signal:decoy:vacuum ratio = 4:1:16" and "about q = 2/5"
        in one sentence. Put into their own Eq. (A1) the printed order gives
        0.0952, a factor 4.2 away from 2/5; the reversed order gives 0.3810,
        which is what "about 2/5" means. The claim is in the constant's docstring
        and this is the arithmetic behind it, so that the claim cannot quietly
        become false.
        """

        def efficiency(counts: tuple[int, int, int]) -> float:
            signal, decoy, vacuum = counts
            return 0.5 * signal / (signal + decoy + vacuum)

        as_printed = efficiency((4, 1, 16))
        reversed_order = efficiency((16, 1, 4))
        assert as_printed == pytest.approx(0.0952, abs=1e-04)
        assert 0.4 / as_printed == pytest.approx(4.2, abs=0.05)
        assert reversed_order == pytest.approx(0.3810, abs=1e-04)
        assert NTANOS_STATE_COUNTS == (16, 1, 4)
        assert efficiency(NTANOS_STATE_COUNTS) == reversed_order

    def test_the_visibility_gives_the_misalignment_error_the_tests_use(self) -> None:
        """``e_mis = (1 - V)/2``, stated below their Eq. (A5)."""
        assert (1.0 - NTANOS_INTERFEROMETER_VISIBILITY) / 2.0 == pytest.approx(
            REFERENCE_MISALIGNMENT
        )


class TestTheRegistryAndModuleSurface:
    def test_the_name_resolves_once_this_module_is_imported(self) -> None:
        assert "bb84-decoy" in PROTOCOLS
        assert PROTOCOLS.resolve("BB84-Decoy ") is Bb84DecoyProtocol

    def test_what_the_registry_hands_back_is_the_class(self) -> None:
        """A protocol carries parameters, and choosing them is the caller's job."""
        resolved = PROTOCOLS.resolve("bb84-decoy")
        assert isinstance(resolved, type)
        assert issubclass(resolved, QkdProtocol)

    def test_registering_twice_is_refused(self) -> None:
        """Import order must not decide which class answers to a name."""
        with pytest.raises(ConfigurationError, match="already registered"):
            PROTOCOLS.register(Bb84DecoyProtocol)

    def test_all_is_complete_and_ordered_by_the_project_convention(self) -> None:
        """Constants, then classes, then functions, each block sorted."""
        from quoss.qkd import bb84

        for name in bb84.__all__:
            assert hasattr(bb84, name)
        constants = [n for n in bb84.__all__ if n.isupper()]
        classes = [n for n in bb84.__all__ if not n.isupper() and n[0].isupper()]
        functions = [n for n in bb84.__all__ if n[0].islower()]
        assert bb84.__all__ == sorted(constants) + sorted(classes) + sorted(functions)

    def test_no_finite_key_parameter_has_leaked_into_an_asymptotic_module(self) -> None:
        """The negative control for what this module is.

        A block length or a security parameter is a statement about a *finite*
        sample. One appearing in a public signature here would mean the finite-key
        bound had started growing a second home, which is the way two
        implementations of one formula are born.
        """
        from quoss.qkd import bb84

        forbidden = ("block", "epsilon", "security", "failure_probability", "samples")
        for name in bb84.__all__:
            attribute = getattr(bb84, name)
            if not callable(attribute):
                continue
            parameters = list(inspect.signature(attribute).parameters)
            for field in getattr(attribute, "__dataclass_fields__", {}):
                parameters.append(field)
            for parameter in parameters:
                assert not any(word in parameter.lower() for word in forbidden), (
                    f"{name} takes {parameter!r}"
                )

    def test_every_rate_this_module_returns_says_it_is_asymptotic(self) -> None:
        for transmittance in LOSS_SWEEP:
            rate = reference_protocol().key_rate(
                conditions(transmittance=transmittance), degradations=DegradationLog()
            )
            assert rate.regime is KeyRegime.ASYMPTOTIC


class TestTheContainersRefuseImpossibleContents:
    @pytest.mark.parametrize(
        ("field", "value"),
        [("gain", -0.1), ("gain", 1.5), ("qber", -0.1), ("qber", 0.6), ("gain", np.nan)],
    )
    def test_intensity_observables_out_of_range(self, field: str, value: float) -> None:
        fields: dict[str, FloatArray] = {"gain": np.array(0.5), "qber": np.array(0.1)}
        fields[field] = np.array(value)
        with pytest.raises(DomainError):
            IntensityObservables(intensity=0.56, **fields)

    def test_intensity_observables_that_do_not_broadcast(self) -> None:
        with pytest.raises(DomainError, match="broadcast"):
            IntensityObservables(intensity=0.5, gain=np.zeros(3), qber=np.zeros(2))

    @pytest.mark.parametrize("bad", [-1.0, float("nan")])
    def test_intensity_observables_with_an_impossible_intensity(self, bad: float) -> None:
        with pytest.raises(DomainError, match="mean photon number"):
            IntensityObservables(intensity=bad, gain=np.array(0.5), qber=np.array(0.1))

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("single_photon_yield", -0.1),
            ("single_photon_yield", 1.5),
            ("single_photon_gain", -0.1),
            ("single_photon_qber", 0.6),
            ("single_photon_qber", np.inf),
        ],
    )
    def test_single_photon_bounds_out_of_range(self, field: str, value: float) -> None:
        fields: dict[str, FloatArray] = {
            "single_photon_yield": np.array(0.5),
            "single_photon_gain": np.array(0.2),
            "single_photon_qber": np.array(0.1),
        }
        fields[field] = np.array(value)
        with pytest.raises(DomainError):
            SinglePhotonBounds(certified=np.array(True), **fields)

    def test_single_photon_bounds_that_do_not_broadcast(self) -> None:
        with pytest.raises(DomainError, match="broadcast"):
            SinglePhotonBounds(
                single_photon_yield=np.zeros(3),
                single_photon_gain=np.zeros(2),
                single_photon_qber=np.zeros(3),
                certified=np.zeros(3, dtype=np.bool_),
            )

    def test_the_bounds_cannot_be_edited_afterwards(self) -> None:
        bounds = bounds_for(conditions(transmittance=np.array([1e-03, 1e-04])))
        with pytest.raises(ValueError, match="read-only"):
            bounds.single_photon_yield[0] = 1.0
        with pytest.raises(ValueError, match="read-only"):
            bounds.certified[0] = False

    def test_the_repr_of_each_container_survives_an_empty_pass(self) -> None:
        """`repr` is what a reader sees first, and `np.min` of nothing raises."""
        link = conditions(transmittance=np.array([]))
        assert "empty" in repr(simulate_intensity(link, intensity=0.56))
        assert "empty" in repr(bounds_for(link))

    def test_the_repr_says_how_much_of_the_pass_is_certified(self) -> None:
        link = conditions(transmittance=np.array([1e-03] * 3))
        assert "certified=3/3" in repr(bounds_for(link))
