"""Tests for `quoss.qkd.finite_key`.

Organised by the claim each block defends, not by the function it calls.

- ``TestTheHoeffdingDeviation`` — **V3**. ``delta`` is checked against the
  inequality it is the solution of, solved numerically by a root finder rather
  than transcribed, plus the square-root scaling that decides how a longer pass
  pays off.
- ``TestTheCertifiedCountsAreBounds`` — **V1**, and the block with no symptom if
  it fails. A bound that is not a bound leaves the key length plausible and the
  security claim void. The truth it must not exceed is built from the same
  photon-number decomposition the forward model is a sum of, evaluated at
  ``n = 0`` and ``n = 1``.
- ``TestTheAsymptoticLimitIsMaEtAl`` — **V3 across sources**. With ``mu_3 = 0``
  and a block large enough for ``delta`` to vanish, Lim et al. 2014 Eq. (3) must
  reproduce Ma et al. 2005 Eq. (34) as implemented in :mod:`quoss.qkd.bb84` —
  two papers, two transcriptions, one number. Same for their Eqs. (4) and (37).
- ``TestWhatTheStatisticsCost`` — the measurements this module exists to make:
  how the penalty shrinks with the block, and the trade-off the asymptotic
  module cannot see, where spending more pulses on decoys buys a tighter bound.
- ``TestTheSinglePhotonErrors`` and ``TestTheRandomSamplingDeviation`` — the two
  halves of the phase error rate, including the negative control that
  distinguishes the natural logarithm in ``gamma`` from a base-two one.
- ``TestThePhaseErrorRate`` — that it is an upper bound, that it fails to one
  half rather than to zero, and that it is not the QBER.
- ``TestTheKeyLength`` — the assembled bound: never above the block it came
  from, a whole number, monotone in block size, and zero with a logged reason
  where the fixed costs win.
- ``TestTheVacuumCredit`` — Lim et al.'s free key from dark counts, measured
  where it matters and where it does not.
- ``TestLim2014Evaluation`` — **V2**, and the honest part of it. Their Fig. 1
  rests on a channel model whose printed error formula is internally
  inconsistent; the reading that reproduces their published block-size ratio is
  identified by measurement, and the block size at which their curve ends does
  **not** reproduce, which is recorded rather than fitted away.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
- ``TestTheExpectedCounts`` — the simulation bridge: the sifting fractions, the
  vacuum state, and pooling a pass into a block.
- ``TestTheModuleSurface`` — that a finite result cannot be labelled asymptotic,
  and that nothing here registered itself as a protocol.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
from scipy.optimize import brentq

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatLike
from quoss.qkd.base import (
    NTANOS_SOURCE_PULSE_RATE_HZ,
    PROTOCOLS,
    KeyRegime,
    LinkConditions,
    binary_entropy,
)
from quoss.qkd.bb84 import (
    NTANOS_DECOY_INTENSITY,
    NTANOS_SIGNAL_INTENSITY,
    VACUUM_ERROR_RATE,
    simulate_intensity,
    single_photon_bounds,
)
from quoss.qkd.finite_key import (
    LIM_CORRECTNESS,
    LIM_ERROR_CORRECTION_EFFICIENCY,
    LIM_ERROR_TERM_COUNT,
    LIM_KEY_LENGTH_PENALTY_TERMS,
    LIM_MISALIGNMENT_ERROR,
    LIM_SECURITY_CONSTANT,
    LIM_WEAKEST_INTENSITY,
    BasisCounts,
    CertifiedEvents,
    DecoyBlockCounts,
    DecoySettings,
    FiniteKeyResult,
    SecurityParameters,
    certified_events,
    error_correction_leakage,
    expected_block_counts,
    hoeffding_deviation,
    phase_error_rate,
    random_sampling_deviation,
    secret_key_length,
    single_photon_errors,
)

# The reference downlink of `channel/link_budget.py`, and the same two numbers
# `tests/qkd/test_bb84.py` uses, so the three files describe one link.
REFERENCE_TRANSMITTANCE = 1.3993e-03
REFERENCE_NIGHT_NOISE_PER_GATE = 7.8797e-07
REFERENCE_DAY_NOISE_PER_GATE = 7.519554e-03
REFERENCE_MISALIGNMENT = 0.01

# A hundred seconds of a 100 MHz source: the order of magnitude of a LEO pass.
REFERENCE_PULSES = 1e10

LOSS_SWEEP = (1e-01, 1e-02, REFERENCE_TRANSMITTANCE, 1e-04, 1e-05)
BLOCK_SWEEP = (1e8, 1e9, REFERENCE_PULSES, 1e11, 1e12)


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


def settings(
    *,
    signal_intensity: float = NTANOS_SIGNAL_INTENSITY,
    decoy_intensity: float = NTANOS_DECOY_INTENSITY,
    vacuum_intensity: float = 0.0,
    signal_probability: float = 16 / 21,
    decoy_probability: float = 1 / 21,
    vacuum_probability: float = 4 / 21,
) -> DecoySettings:
    """Ntanos et al.'s intensities with the 16:1:4 split, with one thing changed."""
    return DecoySettings(
        signal_intensity=signal_intensity,
        decoy_intensity=decoy_intensity,
        vacuum_intensity=vacuum_intensity,
        signal_probability=signal_probability,
        decoy_probability=decoy_probability,
        vacuum_probability=vacuum_probability,
    )


def security(*, correctness: float = 1e-10, secrecy: float = 1e-10) -> SecurityParameters:
    """Return the pair a satellite experiment would quote."""
    return SecurityParameters(correctness=correctness, secrecy=secrecy)


def block_for(
    link: LinkConditions,
    *,
    pulses: FloatLike = REFERENCE_PULSES,
    key_basis_probability: float = 0.5,
    source: DecoySettings | None = None,
) -> DecoyBlockCounts:
    """Return the expected counts of one block on a link."""
    return expected_block_counts(
        link,
        settings=source if source is not None else settings(),
        key_basis_probability=key_basis_probability,
        pulses=pulses,
    )


def basis_counts(
    *,
    signal_detections: FloatLike = 0.0,
    decoy_detections: FloatLike = 0.0,
    vacuum_detections: FloatLike = 0.0,
    signal_errors: FloatLike = 0.0,
    decoy_errors: FloatLike = 0.0,
    vacuum_errors: FloatLike = 0.0,
) -> BasisCounts:
    """Build a :class:`BasisCounts` from plain numbers.

    The container stores float arrays, so a test writing ``1e5`` has to say
    ``np.array(1e5)`` — the same wrapping ``tests/qkd/test_bb84.py`` does for
    :class:`~quoss.qkd.bb84.IntensityObservables`. Doing it once here keeps the
    six-field calls below readable.
    """
    return BasisCounts(
        signal_detections=np.asarray(signal_detections, dtype=np.float64),
        decoy_detections=np.asarray(decoy_detections, dtype=np.float64),
        vacuum_detections=np.asarray(vacuum_detections, dtype=np.float64),
        signal_errors=np.asarray(signal_errors, dtype=np.float64),
        decoy_errors=np.asarray(decoy_errors, dtype=np.float64),
        vacuum_errors=np.asarray(vacuum_errors, dtype=np.float64),
    )


def block_counts(
    *, key_basis: BasisCounts, check_basis: BasisCounts, pulses: FloatLike
) -> DecoyBlockCounts:
    """Build a :class:`DecoyBlockCounts` with a plain number of pulses."""
    return DecoyBlockCounts(
        key_basis=key_basis,
        check_basis=check_basis,
        pulses=np.asarray(pulses, dtype=np.float64),
    )


def certified(
    *, vacuum: FloatLike, single_photon: FloatLike, certified_mask: FloatLike | bool
) -> CertifiedEvents:
    """Build a :class:`CertifiedEvents` from plain numbers."""
    return CertifiedEvents(
        vacuum=np.asarray(vacuum, dtype=np.float64),
        single_photon=np.asarray(single_photon, dtype=np.float64),
        certified=np.asarray(certified_mask, dtype=np.bool_),
    )


def finite_result(
    *,
    length_bits: FloatLike = 0.0,
    vacuum_events: FloatLike = 0.0,
    single_photon_events: FloatLike = 0.0,
    phase_error_rate: FloatLike = 0.1,
    observed_error_rate: FloatLike = 0.01,
    leakage_bits: FloatLike = 0.0,
    block_size: FloatLike = 0.0,
    pulses: FloatLike = 1.0,
    security_parameters: SecurityParameters | None = None,
) -> FiniteKeyResult:
    """Build a :class:`FiniteKeyResult` from plain numbers."""
    return FiniteKeyResult(
        length_bits=np.asarray(length_bits, dtype=np.float64),
        vacuum_events=np.asarray(vacuum_events, dtype=np.float64),
        single_photon_events=np.asarray(single_photon_events, dtype=np.float64),
        phase_error_rate=np.asarray(phase_error_rate, dtype=np.float64),
        observed_error_rate=np.asarray(observed_error_rate, dtype=np.float64),
        leakage_bits=np.asarray(leakage_bits, dtype=np.float64),
        block_size=np.asarray(block_size, dtype=np.float64),
        pulses=np.asarray(pulses, dtype=np.float64),
        security=security_parameters if security_parameters is not None else security(),
    )


def true_yields(link: LinkConditions) -> tuple[float, float, float]:
    """Return ``(Y_0, Y_1, e_1)`` of the model the forward simulation is a sum of.

    The photon-number decomposition behind
    :func:`~quoss.qkd.bb84.simulate_intensity`, evaluated at ``n = 0`` and
    ``n = 1``: a single-photon pulse clicks if its photon survives, or the
    background fires, or both, and it is wrong when the background decided
    (half the time) or when the optics misaligned it.
    """
    y_0 = float(link.background_yield)
    eta = float(link.transmittance)
    y_1 = y_0 + eta * (1.0 - y_0)
    e_1 = (VACUUM_ERROR_RATE * y_0 + REFERENCE_MISALIGNMENT * eta * (1.0 - y_0)) / y_1
    return y_0, y_1, e_1


def true_events(
    link: LinkConditions,
    *,
    pulses: float,
    sifting: float,
    source: DecoySettings | None = None,
) -> tuple[float, float, float]:
    """Return the true ``(s_0, s_1, v_1)`` a block holds, before any bounding.

    ``s_n = N * sifting * tau_n * Y_n`` — the pulses that carried ``n`` photons,
    survived the sifting, and produced a click — and ``v_1 = s_1 e_1``. This is
    what the certified counts are bounds on, and it comes from the photon-number
    decomposition rather than from the module under test.
    """
    source = source if source is not None else settings()
    y_0, y_1, e_1 = true_yields(link)
    s_0 = pulses * sifting * source.tau(0) * y_0
    s_1 = pulses * sifting * source.tau(1) * y_1
    return s_0, s_1, s_1 * e_1


class TestTheHoeffdingDeviation:
    @pytest.mark.reference
    @pytest.mark.parametrize("sample_size", [1e2, 1e4, 1e6, 1e10])
    @pytest.mark.parametrize("secrecy", [1e-6, 1e-10, 1e-15])
    def test_it_solves_the_inequality_it_comes_from(
        self, sample_size: float, secrecy: float
    ) -> None:
        """V3. The closed form against the inequality, solved by a root finder.

        Hoeffding's bound for a sum of ``n`` terms in ``[0, 1]`` is
        ``Pr[|S - E S| >= t] <= 2 exp(-2 t^2 / n)``, and ``delta`` is the ``t``
        at which the right-hand side equals the failure probability the proof
        allows each interval, ``2 eps_sec/21``. Finding that ``t`` with
        ``brentq`` shares no algebra with the square root in the module, so
        agreement is evidence about the formula rather than about its
        transcription.
        """
        parameters = security(secrecy=secrecy)
        failure = 2.0 * parameters.interval_confidence

        def excess(t: float) -> float:
            return 2.0 * np.exp(-2.0 * t**2 / sample_size) - failure

        solved = brentq(excess, 0.0, 10.0 * np.sqrt(sample_size), xtol=1e-12, rtol=1e-15)
        assert float(hoeffding_deviation(sample_size, security=parameters)) == pytest.approx(
            solved, rel=1e-12
        )

    @pytest.mark.physics
    def test_it_grows_as_the_square_root_of_the_block(self) -> None:
        """Four times the events, twice the deviation — exactly, not approximately.

        This is the whole reason a longer pass helps: the deviation grows like
        ``sqrt(n)`` while the counts grow like ``n``, so the relative penalty
        falls like ``1/sqrt(n)`` and never reaches zero.
        """
        parameters = security()
        small = float(hoeffding_deviation(1e6, security=parameters))
        large = float(hoeffding_deviation(4e6, security=parameters))
        assert large / small == pytest.approx(2.0, rel=1e-12)

    @pytest.mark.physics
    def test_a_block_with_no_events_deviates_by_nothing(self) -> None:
        """An empty block is legal and its deviation is exactly zero, not a nan."""
        assert float(hoeffding_deviation(0.0, security=security())) == 0.0

    def test_it_is_vectorised_over_blocks(self) -> None:
        """One call for a sweep of block sizes, elementwise."""
        sizes = np.array([1e4, 1e6, 1e8])
        deviations = hoeffding_deviation(sizes, security=security())
        assert deviations.shape == (3,)
        assert np.all(np.diff(deviations) > 0.0)

    def test_a_negative_sample_size_is_rejected(self) -> None:
        """Counts are counts."""
        with pytest.raises(DomainError, match="non-negative"):
            hoeffding_deviation(-1.0, security=security())


class TestTheCertifiedCountsAreBounds:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    @pytest.mark.parametrize("pulses", [1e10, 1e12])
    def test_the_single_photon_count_never_exceeds_the_truth(
        self, transmittance: float, pulses: float
    ) -> None:
        """V1, and the check with no symptom if it fails.

        ``s_1`` is a lower bound on a quantity nobody can measure. If it ever
        exceeds the true number of single-photon detections, the key length is
        still an ordinary positive number and the security claim is void —
        nothing downstream can detect it, because downstream only sees the
        bound.
        """
        link = conditions(transmittance=transmittance)
        block = block_for(link, pulses=pulses)
        events = certified_events(
            block.key_basis,
            settings=settings(),
            security=security(),
            degradations=DegradationLog(),
        )
        _, truth, _ = true_events(link, pulses=pulses, sifting=0.25)
        assert float(events.single_photon) <= truth

    @pytest.mark.physics
    @pytest.mark.parametrize(
        "noise", [REFERENCE_NIGHT_NOISE_PER_GATE, 1e-4, REFERENCE_DAY_NOISE_PER_GATE]
    )
    def test_the_vacuum_count_never_exceeds_the_truth(self, noise: float) -> None:
        """``s_0`` is a lower bound too, and the one that matters in daylight."""
        link = conditions(noise_counts_per_gate=noise)
        block = block_for(link, pulses=1e12)
        events = certified_events(
            block.key_basis,
            settings=settings(),
            security=security(),
            degradations=DegradationLog(),
        )
        truth, _, _ = true_events(link, pulses=1e12, sifting=0.25)
        assert float(events.vacuum) <= truth

    @pytest.mark.physics
    @pytest.mark.parametrize("pulses", BLOCK_SWEEP)
    def test_the_certified_counts_never_exceed_the_detections(self, pulses: float) -> None:
        """``s_0 + s_1 <= n_X``: they are subsets of the same clicks.

        The ordering the key length inherits — ``l <= n_X`` — is created here,
        so it is checked where it is created and not only where it is used.
        """
        block = block_for(conditions(), pulses=pulses)
        events = certified_events(
            block.key_basis,
            settings=settings(),
            security=security(),
            degradations=DegradationLog(),
        )
        total = float(events.vacuum + events.single_photon)
        assert total <= float(block.key_basis.total_detections)

    @pytest.mark.physics
    def test_the_bound_tightens_towards_the_truth_as_the_block_grows(self) -> None:
        """The defining behaviour of a finite-size penalty.

        The ratio of certified to true single-photon events must never fall as
        the block grows, and must stay below one. Measured on the reference
        downlink at zenith, the sequence over 1e8 to 1e12 pulses is
        ``0, 0, 0.548, 0.830, 0.920``: below about 1e10 pulses — a hundred
        seconds of a 100 MHz source — this link certifies **nothing at all**,
        and past it the bound closes on the truth without ever reaching it.
        """
        link = conditions()
        fractions = []
        for pulses in BLOCK_SWEEP:
            block = block_for(link, pulses=pulses)
            events = certified_events(
                block.key_basis,
                settings=settings(),
                security=security(),
                degradations=DegradationLog(),
            )
            _, truth, _ = true_events(link, pulses=pulses, sifting=0.25)
            fractions.append(float(events.single_photon) / truth)
        assert np.all(np.diff(fractions) >= 0.0)
        assert fractions[-1] < 1.0
        assert fractions[0] == 0.0
        assert fractions[1] == 0.0
        assert fractions[2] == pytest.approx(0.548, abs=0.01)
        assert fractions[-1] == pytest.approx(0.920, abs=0.01)


class TestTheAsymptoticLimitIsMaEtAl:
    @pytest.mark.reference
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_the_single_photon_bound_becomes_ma_et_als(self, transmittance: float) -> None:
        """V3 across sources, and the strongest check in this file.

        Lim et al. 2014 Eq. (3) and Ma et al. 2005 Eq. (34) were transcribed
        from different papers into different modules, one in counts and one in
        probabilities. With ``mu_3 = 0`` and a block so large that the Hoeffding
        deviation is negligible, they must be the same number: ``s_1`` divided
        by the pulses that carried one photon and survived sifting,
        ``N q_x^2 tau_1``, is ``Y_1``.

        Agreement here is evidence about both transcriptions at once, which is
        what an independent implementation buys and a rewrite of the same
        algebra does not.
        """
        link = conditions(transmittance=transmittance)
        source = settings()
        pulses = 1e24
        block = block_for(link, pulses=pulses, source=source)
        events = certified_events(
            block.key_basis, settings=source, security=security(), degradations=DegradationLog()
        )
        finite_yield = float(events.single_photon) / (pulses * 0.25 * source.tau(1))

        ma = single_photon_bounds(
            signal=simulate_intensity(link, intensity=source.signal_intensity),
            decoy=simulate_intensity(link, intensity=source.decoy_intensity),
            background_yield=link.background_yield,
            degradations=DegradationLog(),
        )
        assert finite_yield == pytest.approx(float(ma.single_photon_yield), rel=1e-6)

    @pytest.mark.reference
    def test_the_residual_is_exactly_the_hoeffding_term(self) -> None:
        """The two bounds differ by ``delta`` and by nothing else.

        Agreement at one block size could be a coincidence of two errors. The
        *way* the disagreement shrinks cannot: ``delta`` grows like ``sqrt(N)``
        while the counts grow like ``N``, so the relative gap must fall like
        ``1/sqrt(N)``. Four decades of block size must divide it by exactly a
        hundred.

        Measured on the reference downlink: 4.33e-04 at 1e16 pulses, 4.33e-06 at
        1e20, 4.33e-08 at 1e24 — three points on a line of slope -1/2.
        """
        link = conditions()
        source = settings()
        ma = single_photon_bounds(
            signal=simulate_intensity(link, intensity=source.signal_intensity),
            decoy=simulate_intensity(link, intensity=source.decoy_intensity),
            background_yield=link.background_yield,
            degradations=DegradationLog(),
        )
        truth = float(ma.single_photon_yield)

        residuals = []
        for pulses in (1e16, 1e20, 1e24):
            block = block_for(link, pulses=pulses, source=source)
            events = certified_events(
                block.key_basis,
                settings=source,
                security=security(),
                degradations=DegradationLog(),
            )
            finite_yield = float(events.single_photon) / (pulses * 0.25 * source.tau(1))
            residuals.append(abs(finite_yield / truth - 1.0))

        assert residuals[0] / residuals[1] == pytest.approx(100.0, rel=1e-3)
        assert residuals[1] / residuals[2] == pytest.approx(100.0, rel=1e-3)
        assert residuals[0] == pytest.approx(4.33e-04, rel=1e-2)

    @pytest.mark.reference
    @pytest.mark.parametrize("transmittance", [1e-02, REFERENCE_TRANSMITTANCE, 1e-04])
    def test_the_single_photon_error_rate_becomes_ma_et_als(self, transmittance: float) -> None:
        """Lim et al. Eq. (4) over Eq. (3) is Ma et al. Eq. (37), in the limit.

        The ratio ``v_1 / s_1`` is the single-photon error rate, and it has to
        converge on the bound :func:`~quoss.qkd.bb84.single_photon_bounds`
        computes from the published closed form.
        """
        link = conditions(transmittance=transmittance)
        source = settings()
        pulses = 1e24
        block = block_for(link, pulses=pulses, source=source)
        events = certified_events(
            block.key_basis, settings=source, security=security(), degradations=DegradationLog()
        )
        errors = single_photon_errors(
            block.check_basis, settings=source, security=security(), degradations=DegradationLog()
        )
        finite_rate = float(errors) / float(events.single_photon)

        ma = single_photon_bounds(
            signal=simulate_intensity(link, intensity=source.signal_intensity),
            decoy=simulate_intensity(link, intensity=source.decoy_intensity),
            background_yield=link.background_yield,
            degradations=DegradationLog(),
        )
        assert finite_rate == pytest.approx(float(ma.single_photon_qber), rel=1e-5)

    @pytest.mark.reference
    def test_the_vacuum_count_becomes_the_background_yield(self) -> None:
        """Eq. (2) in the limit is ``Y_0``, which the channel already knows.

        With ``mu_3 = 0`` the vacuum state *is* a measurement of the background,
        so the bound has nothing to infer and must return the number
        :attr:`~quoss.qkd.base.LinkConditions.background_yield` computes from the
        noise mean.
        """
        link = conditions(noise_counts_per_gate=REFERENCE_DAY_NOISE_PER_GATE)
        source = settings()
        pulses = 1e24
        block = block_for(link, pulses=pulses, source=source)
        events = certified_events(
            block.key_basis, settings=source, security=security(), degradations=DegradationLog()
        )
        finite_yield = float(events.vacuum) / (pulses * 0.25 * source.tau(0))
        assert finite_yield == pytest.approx(float(link.background_yield), rel=1e-6)


class TestWhatTheStatisticsCost:
    @pytest.mark.physics
    def test_decoys_are_pure_cost_only_in_the_asymptotic_limit(self) -> None:
        """The measurement this module exists to make.

        :attr:`~quoss.qkd.bb84.Bb84DecoyProtocol.protocol_efficiency` says decoy
        pulses buy a bound that is already exact however few are sent, so they
        are pure cost and the optimum fraction is zero. That is true, and it is
        true only asymptotically.

        Measured here on the reference downlink at zenith, sweeping the decoy
        fraction with the vacuum fraction held at 5 %:

        * at 1e20 pulses the key per pulse **falls monotonically** with the
          decoy fraction — 7.11e-05 at 5 % down to 2.70e-05 at 90 %;
        * at 1e10 pulses — a hundred seconds of a 100 MHz source — it has an
          **interior maximum near 50 %**: 6.26e-06 at 10 %, 2.12e-05 at 50 %,
          1.69e-05 at 90 %. Spending half the pass on decoys is worth a factor
          3.4 over spending a tenth of it.

        Nothing in the asymptotic module can see that optimum, because the
        quantity it optimises does not depend on the decoy fraction at all.
        """
        link = conditions()
        fractions = (0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)
        rates: dict[float, list[float]] = {}
        for pulses in (1e10, 1e20):
            row = []
            for decoy in fractions:
                source = settings(
                    signal_probability=1.0 - 0.05 - decoy,
                    decoy_probability=decoy,
                    vacuum_probability=0.05,
                )
                result = secret_key_length(
                    block_for(link, pulses=pulses, source=source),
                    settings=source,
                    security=security(),
                    error_correction_efficiency=1.22,
                    degradations=DegradationLog(),
                )
                row.append(float(result.key_per_pulse))
            rates[pulses] = row

        asymptotic = np.array(rates[1e20])
        assert np.all(np.diff(asymptotic) < 0.0)

        finite = np.array(rates[1e10])
        best = int(np.argmax(finite))
        assert 0.0 < fractions[best] < 0.9
        assert fractions[best] == pytest.approx(0.5, abs=0.11)
        assert finite[best] / finite[fractions.index(0.1)] == pytest.approx(3.4, rel=0.1)

    @pytest.mark.physics
    def test_a_pass_length_block_yields_a_fifth_of_the_asymptotic_key(self) -> None:
        """The headline cost, measured rather than asserted qualitatively.

        Same link, same protocol, same intensities — only the block length
        changes. On the reference downlink at zenith with the 16:1:4 split, the
        key per pulse is 1.1387e-05 for a block of 1e10 pulses and 6.0239e-05
        in the limit: a hundred-second pass certifies **18.9 %** of what the
        asymptotic formula promises for the same conditions.

        Reading the asymptotic number as available key is therefore not a small
        optimism, and it gets worse as the block shrinks: at 1e9 pulses this
        link certifies nothing at all.
        """
        link = conditions()
        source = settings()
        rates = []
        for pulses in (1e9, REFERENCE_PULSES, 1e20):
            result = secret_key_length(
                block_for(link, pulses=pulses, source=source),
                settings=source,
                security=security(),
                error_correction_efficiency=1.22,
                degradations=DegradationLog(),
            )
            rates.append(float(result.key_per_pulse))

        assert rates[0] == 0.0
        assert rates[1] == pytest.approx(1.1387e-05, rel=1e-3)
        assert rates[2] == pytest.approx(6.0239e-05, rel=1e-3)
        assert rates[1] / rates[2] == pytest.approx(0.189, rel=1e-2)


class TestTheSinglePhotonErrors:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_it_never_falls_below_the_truth_it_bounds(self, transmittance: float) -> None:
        """V1. ``v_1`` is an upper bound, and the direction matters.

        Too small a bound understates what Eve could know and hands out key that
        is not secret. The truth comes from the photon-number decomposition,
        not from the module under test.
        """
        link = conditions(transmittance=transmittance)
        block = block_for(link, pulses=1e12)
        bound = float(
            single_photon_errors(
                block.check_basis,
                settings=settings(),
                security=security(),
                degradations=DegradationLog(),
            )
        )
        _, _, truth = true_events(link, pulses=1e12, sifting=0.25)
        assert bound >= truth

    @pytest.mark.physics
    def test_a_rare_decoy_state_makes_the_bound_exceed_the_total_errors(self) -> None:
        """The measurement behind the 1/21 decoy fraction, and it is not a defect.

        With Ntanos et al.'s 16:1:4 split, a block of 1e10 pulses gives the
        decoy state 230 errors in the check basis while the deviation shared
        across the three intensities is 458 — twice as large — and the ``1/p_2``
        that converts it to a per-pulse quantity multiplies that by 21. The
        bound on single-photon errors then comes out at 39 630 where the basis
        recorded 16 088 errors of every kind.

        An upper bound above the total is still an upper bound; what it says is
        that this configuration certifies almost nothing about where the errors
        came from, which is exactly why the finite-key optimum spends far more
        pulses on decoys than the asymptotic one.
        """
        block = block_for(conditions(), pulses=REFERENCE_PULSES)
        bound = float(
            single_photon_errors(
                block.check_basis,
                settings=settings(),
                security=security(),
                degradations=DegradationLog(),
            )
        )
        total = float(block.check_basis.total_errors)
        deviation = float(hoeffding_deviation(total, security=security()))

        assert float(block.check_basis.decoy_errors) == pytest.approx(230.1, rel=1e-2)
        assert deviation == pytest.approx(458.0, rel=1e-2)
        assert bound == pytest.approx(39630.0, rel=1e-3)
        assert total == pytest.approx(16088.0, rel=1e-3)
        assert bound > total

    def test_a_negative_bound_is_clamped_and_logged(self) -> None:
        """Real data can invert the subtraction; expectations cannot.

        Eq. (4) subtracts the vacuum state's errors from the decoy state's. In
        the forward model the decoy state always has the higher error rate per
        pulse — it has the signal errors on top of the same background — so this
        branch is unreachable from :func:`expected_block_counts` and is reached
        here with counts written by hand, which is what a fluctuating experiment
        can produce.
        """
        counts = basis_counts(
            signal_detections=1e5,
            decoy_detections=1e5,
            vacuum_detections=1e5,
            signal_errors=100.0,
            decoy_errors=10.0,
            vacuum_errors=1000.0,
        )
        source = settings(signal_probability=0.2, decoy_probability=0.4, vacuum_probability=0.4)
        log = DegradationLog()
        bound = single_photon_errors(counts, settings=source, security=security(), degradations=log)
        assert float(bound) == 0.0
        assert log.entries[0].code == "finite-key.single-photon-errors-clamped"
        assert log.entries[0].details["clamped_blocks"] == 1


class TestTheRandomSamplingDeviation:
    @pytest.mark.physics
    @pytest.mark.parametrize("error_rate", [0.0, 1.0])
    def test_it_vanishes_at_both_endpoints(self, error_rate: float) -> None:
        """``b log2(1/b) -> 0``, so the limit is zero and not a ``0 * inf``.

        A channel with no errors is not an edge case in this project: it is what
        a simulated link with no background and perfect optics has, and it is
        the first value a test reaches for. The endpoints are substituted before
        the arithmetic rather than masked after it, because the project runs
        with ``filterwarnings = ["error"]``.
        """
        assert (
            float(
                random_sampling_deviation(
                    error_rate=error_rate,
                    check_events=1e5,
                    key_events=1e5,
                    security=security(),
                    degradations=DegradationLog(),
                )
            )
            == 0.0
        )

    @pytest.mark.physics
    def test_it_is_symmetric_in_the_two_event_counts(self) -> None:
        """``gamma`` sees ``c`` and ``d`` only through ``1/c + 1/d``.

        Which of the two bases is the sampled one and which is the sampling one
        does not enter — a fact that is easy to assume and worth checking, since
        an implementation that swapped them would be wrong only where the two
        differ.
        """
        forward = float(
            random_sampling_deviation(
                error_rate=0.01,
                check_events=1e4,
                key_events=1e8,
                security=security(),
                degradations=DegradationLog(),
            )
        )
        backward = float(
            random_sampling_deviation(
                error_rate=0.01,
                check_events=1e8,
                key_events=1e4,
                security=security(),
                degradations=DegradationLog(),
            )
        )
        assert forward == backward

    @pytest.mark.physics
    def test_the_smaller_count_governs_it(self) -> None:
        """A huge key basis does not make up for a thin check basis.

        Measured: 1e4 against 1e4 gives 0.0141, and growing the key basis four
        decades to 1e8 only takes it to 0.0099 — while growing *both* to 1e8
        takes it to 0.00013, a hundredfold better. The harmonic sum is dominated
        by whichever count is smaller, which is the whole argument for spending
        pulses on the check basis.
        """
        both_small = float(
            random_sampling_deviation(
                error_rate=0.01,
                check_events=1e4,
                key_events=1e4,
                security=security(),
                degradations=DegradationLog(),
            )
        )
        one_large = float(
            random_sampling_deviation(
                error_rate=0.01,
                check_events=1e4,
                key_events=1e8,
                security=security(),
                degradations=DegradationLog(),
            )
        )
        both_large = float(
            random_sampling_deviation(
                error_rate=0.01,
                check_events=1e8,
                key_events=1e8,
                security=security(),
                degradations=DegradationLog(),
            )
        )
        assert both_small == pytest.approx(0.0141, rel=1e-2)
        assert one_large == pytest.approx(0.0099, rel=1e-2)
        assert both_large == pytest.approx(0.000127, rel=1e-2)
        assert one_large / both_large > 50.0

    @pytest.mark.physics
    def test_a_base_two_logarithm_would_understate_it_by_seventeen_per_cent(self) -> None:
        """Negative control for the one ambiguity in the published formula.

        Lim et al. write ``cd log 2`` in the denominator and ``log2(...)`` in
        the numerator of the same expression. Reading the first as a base-two
        logarithm makes it ``log2(2) = 1`` instead of ``ln 2 = 0.693``, which
        scales ``gamma`` by ``sqrt(ln 2) = 0.8326`` — a 17 % underestimate of
        the sampling penalty, in the direction that flatters the key and with no
        symptom anywhere else.
        """
        b, c, d, a = 0.01, 4.2e5, 4.2e5, 1e-10
        published = float(
            random_sampling_deviation(
                error_rate=b,
                check_events=c,
                key_events=d,
                security=security(secrecy=a),
                degradations=DegradationLog(),
            )
        )
        misread = float(
            np.sqrt(
                (c + d)
                * (1.0 - b)
                * b
                / (c * d * 1.0)
                * np.log2((c + d) / (c * d * (1.0 - b) * b) * (LIM_ERROR_TERM_COUNT / a) ** 2)
            )
        )
        assert misread / published == pytest.approx(float(np.sqrt(np.log(2.0))), rel=1e-12)
        assert misread / published == pytest.approx(0.8326, rel=1e-3)

    def test_a_degenerate_logarithm_is_clamped_and_logged(self) -> None:
        """Where the published expression has no real value, ``gamma`` is zero.

        The argument of the logarithm falls below one only when the certified
        counts are enormous relative to the confidence demanded — here a
        deliberately loose secrecy of 0.5 with a million events on each side.
        The limit being approached is zero, so zero is returned, but it is a
        place the published formula does not define and the log says so.
        """
        log = DegradationLog()
        value = random_sampling_deviation(
            error_rate=0.5,
            check_events=1e6,
            key_events=1e6,
            security=security(secrecy=0.5),
            degradations=log,
        )
        assert float(value) == 0.0
        assert log.entries[0].code == "finite-key.sampling-argument-degenerate"

    @pytest.mark.parametrize("error_rate", [-0.1, 1.5, np.nan])
    def test_an_impossible_error_rate_is_rejected(self, error_rate: float) -> None:
        with pytest.raises(DomainError, match="error_rate"):
            random_sampling_deviation(
                error_rate=error_rate,
                check_events=1e5,
                key_events=1e5,
                security=security(),
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize("name", ["check_events", "key_events"])
    def test_zero_events_are_rejected_rather_than_guessed(self, name: str) -> None:
        """No sample is not a small sample, and the caller decides what it means."""
        arguments = {"check_events": 1e5, "key_events": 1e5}
        arguments[name] = 0.0
        with pytest.raises(DomainError, match=name):
            random_sampling_deviation(
                error_rate=0.01,
                security=security(),
                degradations=DegradationLog(),
                **arguments,
            )


class TestThePhaseErrorRate:
    @pytest.mark.physics
    @pytest.mark.parametrize("transmittance", LOSS_SWEEP)
    def test_it_is_never_below_the_rate_it_was_measured_from(self, transmittance: float) -> None:
        """``phi = v_1/s_1 + gamma`` with ``gamma >= 0``: an upper bound, always.

        The sampling term can only add. A phase error rate below the measured
        check-basis rate would mean the transfer between bases had *improved*
        the estimate, which is the one thing a confidence interval cannot do.
        """
        link = conditions(transmittance=transmittance)
        block = block_for(link, pulses=1e12)
        source, parameters = settings(), security()
        key_events = certified_events(
            block.key_basis, settings=source, security=parameters, degradations=DegradationLog()
        )
        check = certified_events(
            block.check_basis, settings=source, security=parameters, degradations=DegradationLog()
        )
        errors = single_photon_errors(
            block.check_basis, settings=source, security=parameters, degradations=DegradationLog()
        )
        measured = float(errors) / float(check.single_photon)
        phase = float(
            phase_error_rate(
                certified_errors=errors,
                check_events=check.single_photon,
                key_events=key_events.single_photon,
                security=parameters,
                degradations=DegradationLog(),
            )
        )
        assert phase >= measured
        assert phase <= VACUUM_ERROR_RATE

    @pytest.mark.physics
    def test_it_is_not_the_qber_and_the_difference_is_large(self) -> None:
        """Two error rates, two terms of Eq. (1), and a factor of eight between them.

        On the reference block — 1e10 pulses, 16:1:4 — the key basis measures a
        QBER of 1.06 %, which is what error correction is charged on, while the
        phase error rate privacy amplification is charged on is 8.85 %. Charging
        privacy amplification at the QBER would inflate the single-photon term
        by 1.609 — a factor nothing downstream could detect, since downstream
        sees only the result.
        """
        block = block_for(conditions(), pulses=REFERENCE_PULSES)
        result = secret_key_length(
            block,
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert float(result.observed_error_rate) == pytest.approx(0.010638, rel=1e-3)
        assert float(result.phase_error_rate) == pytest.approx(0.088479, rel=1e-3)

        optimistic = float(result.single_photon_events) * (
            1.0 - float(binary_entropy(result.observed_error_rate))
        )
        honest = float(result.single_photon_events) * (
            1.0 - float(binary_entropy(result.phase_error_rate))
        )
        assert optimistic / honest == pytest.approx(1.609, rel=1e-3)

    def test_no_certified_events_gives_one_half_and_says_so(self) -> None:
        """The honest failure: unconstrained, not perfect."""
        log = DegradationLog()
        value = phase_error_rate(
            certified_errors=0.0,
            check_events=0.0,
            key_events=1e5,
            security=security(),
            degradations=log,
        )
        assert float(value) == VACUUM_ERROR_RATE
        assert log.entries[0].code == "finite-key.phase-error-unconstrained"

    def test_a_rate_above_one_half_is_capped_and_logged(self) -> None:
        """Above one half the bound stops carrying information rather than growing."""
        log = DegradationLog()
        value = phase_error_rate(
            certified_errors=4.9e4,
            check_events=1e5,
            key_events=1e5,
            security=security(),
            degradations=log,
        )
        assert float(value) == VACUUM_ERROR_RATE
        assert [entry.code for entry in log.entries] == ["finite-key.phase-error-capped"]

    def test_it_is_vectorised_and_mixes_the_two_outcomes(self) -> None:
        """One call over a pass where some samples certify and others do not."""
        log = DegradationLog()
        value = phase_error_rate(
            certified_errors=np.array([0.0, 1e3, 0.0]),
            check_events=np.array([0.0, 1e5, 1e5]),
            key_events=np.array([1e5, 1e5, 1e5]),
            security=security(),
            degradations=log,
        )
        assert value.shape == (3,)
        assert float(value[0]) == VACUUM_ERROR_RATE
        assert 0.0 < float(value[1]) < VACUUM_ERROR_RATE
        assert float(value[2]) == 0.0
        assert log.entries[0].details["unconstrained_blocks"] == 1

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("certified_errors", -1.0),
            ("certified_errors", np.nan),
            ("check_events", np.nan),
            ("key_events", np.inf),
        ],
    )
    def test_impossible_arguments_are_rejected(self, field: str, value: float) -> None:
        arguments: dict[str, FloatLike] = {
            "certified_errors": 1e3,
            "check_events": 1e5,
            "key_events": 1e5,
        }
        arguments[field] = value
        with pytest.raises(DomainError, match=field):
            phase_error_rate(security=security(), degradations=DegradationLog(), **arguments)


class TestTheErrorCorrectionLeakage:
    @pytest.mark.physics
    @pytest.mark.parametrize("error_rate", [0.0, 0.001, 0.01, 0.11, 0.5])
    def test_it_is_the_entropy_times_the_block_times_the_efficiency(
        self, error_rate: float
    ) -> None:
        """The formula against its three factors, evaluated separately."""
        leakage = float(
            error_correction_leakage(
                block_size=810200.0, observed_error_rate=error_rate, efficiency=1.16
            )
        )
        assert leakage == pytest.approx(1.16 * 810200.0 * float(binary_entropy(error_rate)))

    @pytest.mark.physics
    def test_a_perfect_channel_reveals_nothing(self) -> None:
        """``h(0) = 0``: there is nothing to reconcile and nothing is published."""
        assert (
            float(
                error_correction_leakage(block_size=1e6, observed_error_rate=0.0, efficiency=1.22)
            )
            == 0.0
        )

    @pytest.mark.physics
    def test_at_bb84s_asymptotic_threshold_it_takes_more_than_half_the_block(self) -> None:
        """11 % is where the asymptotic rate dies, and this is most of why.

        ``1.16 h(0.11) = 0.58``: at the error rate BB84's textbook threshold
        names, reconciliation alone publishes 58 % of the sifted bits, before
        any of the security analysis begins.
        """
        fraction = (
            float(
                error_correction_leakage(block_size=1e6, observed_error_rate=0.11, efficiency=1.16)
            )
            / 1e6
        )
        assert fraction == pytest.approx(0.5799, rel=1e-3)

    def test_an_efficiency_below_shannon_is_rejected(self) -> None:
        """A code cannot reveal less than the entropy it removes."""
        with pytest.raises(DomainError, match="at least 1"):
            error_correction_leakage(block_size=1e6, observed_error_rate=0.01, efficiency=0.9)

    def test_an_error_rate_outside_zero_to_one_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="error_rate"):
            error_correction_leakage(block_size=1e6, observed_error_rate=1.5, efficiency=1.16)


class TestTheKeyLength:
    @pytest.mark.physics
    @pytest.mark.parametrize("pulses", BLOCK_SWEEP)
    def test_it_never_exceeds_the_block_it_came_from(self, pulses: float) -> None:
        """``l <= n_X``: privacy amplification cannot create sifted bits.

        The ordering :class:`~quoss.qkd.base.KeyRate` enforces for the
        asymptotic rate, checked here for the length. It is inherited from
        ``s_0 + s_1 <= n_X`` and from the two subtractions, so a violation would
        mean one of those terms had the wrong sign.
        """
        block = block_for(conditions(), pulses=pulses)
        result = secret_key_length(
            block,
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert float(result.length_bits) <= float(block.key_basis.total_detections)

    @pytest.mark.physics
    def test_it_is_a_whole_number_of_bits(self) -> None:
        """Eq. (1) floors. A key is a string, and 0.4 of a bit is not a bit."""
        result = secret_key_length(
            block_for(conditions(), pulses=REFERENCE_PULSES),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        length = float(result.length_bits)
        assert length == float(int(length))
        assert length == 113870.0

    @pytest.mark.physics
    def test_more_pulses_are_never_worse_per_pulse(self) -> None:
        """Monotone in the block size, which is what makes pooling a pass sound.

        Both the fixed penalty and the square-root one are shared over a longer
        block, so the key per pulse can only improve. If it ever fell, pooling
        the samples of a pass into one block — what ``system/key_volume.py``
        will do — could destroy key rather than create it.

        Measured over 1e8 to 1e12 pulses on the reference downlink:
        ``0, 0, 1.139e-05, 4.338e-05, 5.466e-05`` bits per pulse. The two zeros
        are blocks too short to certify anything, and the sequence never falls.
        """
        rates = []
        for pulses in BLOCK_SWEEP:
            result = secret_key_length(
                block_for(conditions(), pulses=pulses),
                settings=settings(),
                security=security(),
                error_correction_efficiency=1.22,
                degradations=DegradationLog(),
            )
            rates.append(float(result.key_per_pulse))
        assert np.all(np.diff(rates) >= 0.0)
        assert rates[0] == 0.0
        assert np.all(np.diff(rates[2:]) > 0.0)

    @pytest.mark.physics
    def test_a_block_that_certifies_single_photons_can_still_yield_nothing(self) -> None:
        """The fourth way of getting zero, and the one with its own log entry.

        With a hundred times the night noise, a block of 1e12 pulses certifies
        8.6e7 single-photon events and still returns no key: the QBER is 8 %, so
        error correction publishes more than the certified part is worth. That is
        a statement about the link, and the log distinguishes it from the three
        failures that are statements about the block.
        """
        log = DegradationLog()
        result = secret_key_length(
            block_for(conditions(noise_counts_per_gate=1e-4), pulses=1e12),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=log,
        )
        assert float(result.length_bits) == 0.0
        assert float(result.single_photon_events) == pytest.approx(8.576e7, rel=1e-2)
        assert float(result.observed_error_rate) == pytest.approx(0.0796, rel=1e-2)
        assert "finite-key.block-too-short" in {entry.code for entry in log.entries}

    @pytest.mark.physics
    def test_the_fixed_penalty_is_the_two_published_logarithms(self) -> None:
        """``6 log2(21/eps_sec) + log2(2/eps_cor)``, against the constants it names.

        The two ``21``-shaped numbers in Eq. (1) come from different places —
        :data:`LIM_ERROR_TERM_COUNT` from how many failure events the proof
        composes, :data:`LIM_KEY_LENGTH_PENALTY_TERMS` from how many ``eps``
        factors sit inside one logarithm — and using either for the other is a
        mistake worth a few hundred bits per block.
        """
        parameters = security(correctness=1e-10, secrecy=1e-10)
        expected = LIM_KEY_LENGTH_PENALTY_TERMS * float(
            np.log2(LIM_ERROR_TERM_COUNT / parameters.secrecy)
        ) + float(np.log2(2.0 / parameters.correctness))
        assert parameters.penalty_bits == pytest.approx(expected, rel=1e-15)
        assert parameters.penalty_bits == pytest.approx(259.889, abs=1e-3)

    @pytest.mark.physics
    def test_a_stricter_secrecy_costs_key(self) -> None:
        """Monotone in ``eps_sec``, through both the penalty and the deviations.

        And the cost is **not** small, which is worth knowing before treating
        ``eps_sec`` as free. On the reference block of 1e10 pulses the key is
        254 541 bits at 1e-04, 113 870 at 1e-10 and 32 113 at 1e-15: six decades
        of extra secrecy cost 55 % of the key, and five more cost 72 % of what
        was left.

        The mechanism is not the fixed penalty — that is 260 bits out of a
        hundred thousand. It is that ``delta`` carries ``sqrt(ln(21/eps_sec))``,
        which grows by only 20 % over those six decades, and this block's decoy
        statistics are thin enough that 20 % more deviation moves the phase
        error rate from 5.4 % to 8.8 %. Cheap in the deviation, expensive in the
        key: exactly the sort of amplification a finite-key analysis exists to
        make visible.
        """
        block = block_for(conditions(), pulses=REFERENCE_PULSES)
        lengths = []
        for secrecy_value in (1e-4, 1e-10, 1e-15):
            result = secret_key_length(
                block,
                settings=settings(),
                security=security(secrecy=secrecy_value),
                error_correction_efficiency=1.22,
                degradations=DegradationLog(),
            )
            lengths.append(float(result.length_bits))
        assert lengths[0] > lengths[1] > lengths[2]
        assert lengths[0] == pytest.approx(254541.0, rel=1e-3)
        assert lengths[1] == pytest.approx(113870.0, rel=1e-3)
        assert lengths[2] == pytest.approx(32113.0, rel=1e-3)

    def test_it_is_vectorised_over_a_pass(self) -> None:
        """A sweep of blocks in one call, and the shape survives."""
        link = conditions(
            transmittance=np.array([1e-05, REFERENCE_TRANSMITTANCE, 1e-05]),
        )
        result = secret_key_length(
            block_for(link, pulses=REFERENCE_PULSES),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert result.shape == (3,)
        assert list(result.has_key) == [False, True, False]
        assert float(result.length_bits[1]) == 113870.0

    def test_pooling_a_pass_yields_more_than_treating_samples_separately(self) -> None:
        """Why a block is a pass and not an instant, in one comparison.

        The same 3e10 pulses either as three separate blocks of 1e10 or as one
        pooled block: pooled, they pay the fixed penalty once and share one
        Hoeffding deviation, and the key is **2.68 times larger** — 914 611 bits
        against 341 610. Treating each sample of a pass as its own block is the
        mistake this comparison exists to price, and the factor is not 3 because
        the pooled block's own deviation grows like the square root of it.
        """
        link = conditions(
            transmittance=np.array(
                [REFERENCE_TRANSMITTANCE, REFERENCE_TRANSMITTANCE, REFERENCE_TRANSMITTANCE]
            )
        )
        samples = block_for(link, pulses=REFERENCE_PULSES)
        separate = secret_key_length(
            samples,
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        pooled = secret_key_length(
            samples.pooled(),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert float(np.sum(separate.length_bits)) == pytest.approx(3.0 * 113870.0, rel=1e-6)
        assert float(pooled.length_bits) / float(np.sum(separate.length_bits)) == pytest.approx(
            2.677, rel=1e-3
        )


class TestTheVacuumCredit:
    @pytest.mark.physics
    def test_dark_counts_make_key_but_only_in_a_narrow_window(self) -> None:
        """Lim et al. credit ``s_{X,0}`` in full, and here is what that is worth.

        A detection in a gate where Alice sent nothing was decided by the
        detector, not by the channel, so Eve knows nothing about the bit Bob
        wrote down and the event enters the key at full value. It is a real
        effect and a narrow one, measured here on the reference link at 1e12
        pulses as the sky brightens:

        * at the night noise of 7.9e-07 counts per gate there are too few vacuum
          detections to certify any — ``s_0 = 0``;
        * at 1e-05 the credit is 1.5e+06 bits, **3.3 %** of the key;
        * at 1e-04 and above ``s_0`` is larger still (1.7e+07) and the key is
          **zero**, because error correction is charged on the whole block and
          the QBER those same dark counts produce has already eaten it.

        So "noise makes key" is true, bounded, and never a rescue: the term that
        grows with the background is always outrun by the term that pays for it.
        """
        credits = []
        for noise in (REFERENCE_NIGHT_NOISE_PER_GATE, 1e-5, 1e-4):
            result = secret_key_length(
                block_for(conditions(noise_counts_per_gate=noise), pulses=1e12),
                settings=settings(),
                security=security(),
                error_correction_efficiency=1.22,
                degradations=DegradationLog(),
            )
            credits.append((float(result.vacuum_events), float(result.length_bits)))

        assert credits[0][0] == 0.0
        assert credits[0][1] > 0.0
        assert credits[1][0] == pytest.approx(1.514e6, rel=1e-2)
        assert credits[1][0] / credits[1][1] == pytest.approx(0.033, rel=0.1)
        assert credits[2][0] == pytest.approx(1.654e7, rel=1e-2)
        assert credits[2][1] == 0.0


# --------------------------------------------------------------------------- #
# Lim et al. 2014's own evaluation, transcribed for the V2 block below.
#
# Their fibre system model, from the Evaluation section: a dedicated fibre at
# 0.2 dB/km, an InGaAs APD receiver, and the three intensities of their Fig. 1.
# It lives in the test and not in the module because it is *their channel*, and
# `quoss.channel` is this project's.
# --------------------------------------------------------------------------- #
LIM_DETECTOR_EFFICIENCY = 0.10
LIM_DARK_COUNT_PROBABILITY = 6e-7
LIM_AFTERPULSE_PROBABILITY = 4e-2


def lim_channel(length_km: float, intensity: float) -> tuple[float, float]:
    """Return ``(R_k, e_k)`` of Lim et al. 2014's Evaluation section.

    Transcribed from the paper::

        eta_ch  = 10^(-0.2 L / 10)
        eta_sys = eta_ch eta_Bob
        D_k     = 1 - (1 - 2 p_dc) exp(-eta_sys k)
        R_k     = D_k (1 + p_ap)
        e_k     = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2

    with one reading resolved by measurement. As printed, the misalignment term
    carries ``eta_ch`` — the fibre alone — while the detection rate beside it
    carries ``eta_sys = eta_ch eta_Bob``, ten times smaller. That term then
    contributes **3.9 points** of QBER at zero loss and 4.8 at 100 km on a system
    whose optics are specified at 0.5 %; and since it is the only term that does
    not scale with the detector efficiency while the detections beside it do, the
    optical error rate it implies goes like ``1/eta_Bob`` — a better detector
    would improve the optics. Read with ``eta_sys`` in both places — the form of
    Ma et al. 2005 Eq. (11), where the same transmittance multiplies signal
    errors and signal detections — it contributes 0.48 points at every distance,
    which is ``e_mis`` diluted by the afterpulses, as it should.

    The reading is not settled by preference. Of the four combinations of that
    choice with the choice of whether ``e_k`` counts errors per gate or per
    detection, only one reproduces the paper's own published ratio between block
    sizes, and it is this one — see
    :meth:`TestLim2014Evaluation.test_the_published_block_size_ratio`.
    """
    eta_ch = 10.0 ** (-0.2 * length_km / 10.0)
    eta_sys = eta_ch * LIM_DETECTOR_EFFICIENCY
    detection = 1.0 - (1.0 - 2.0 * LIM_DARK_COUNT_PROBABILITY) * np.exp(-eta_sys * intensity)
    rate = detection * (1.0 + LIM_AFTERPULSE_PROBABILITY)
    error = (
        LIM_DARK_COUNT_PROBABILITY
        + LIM_MISALIGNMENT_ERROR * (1.0 - np.exp(-eta_sys * intensity))
        + LIM_AFTERPULSE_PROBABILITY * detection / 2.0
    )
    return float(rate), float(error)


def lim_counts(
    length_km: float,
    block_size: float,
    *,
    source: DecoySettings,
    key_basis_probability: float,
) -> DecoyBlockCounts:
    """Build the block Lim et al.'s protocol would accumulate at this fibre length.

    They fix the post-processing block size ``n_X`` and let the number of pulses
    follow: Alice keeps sending until the key basis holds ``n_X`` detections, so
    ``N = n_X / (q_x^2 sum_k p_k R_k)``.
    """
    channels = [lim_channel(length_km, intensity) for intensity in source.intensities]
    per_pulse = sum(
        probability * key_basis_probability**2 * rate
        for (rate, _error), probability in zip(channels, source.probabilities, strict=True)
    )
    pulses = block_size / per_pulse

    def basis(sifting: float) -> BasisCounts:
        detections = [
            pulses * probability * sifting * rate
            for (rate, _error), probability in zip(channels, source.probabilities, strict=True)
        ]
        errors = [
            pulses * probability * sifting * error
            for (_rate, error), probability in zip(channels, source.probabilities, strict=True)
        ]
        return basis_counts(
            signal_detections=detections[0],
            decoy_detections=detections[1],
            vacuum_detections=detections[2],
            signal_errors=errors[0],
            decoy_errors=errors[1],
            vacuum_errors=errors[2],
        )

    return block_counts(
        key_basis=basis(key_basis_probability**2),
        check_basis=basis((1.0 - key_basis_probability) ** 2),
        pulses=pulses,
    )


def lim_key_rate(length_km: float, block_size: float, parameters: tuple[float, ...]) -> float:
    """Return ``R = l/N`` for one parameter set, with their ``eps_sec = kappa l``.

    Lim et al. do not fix the secrecy: they fix the secrecy *per key bit*,
    ``eps_sec = kappa l``, which puts the answer on both sides of the equation.
    The map ``l -> l(eps_sec(l))`` is increasing, so iterating it from the
    largest conceivable key converges downwards on the largest fixed point —
    which is the number they plot. The iteration is here rather than in the
    module because it is a choice about how to *report* security, not part of
    the bound.
    """
    key_basis_probability, signal_share, decoy_share, signal_mu, decoy_mu = parameters
    if not 0.01 < key_basis_probability < 0.999:
        return 0.0
    if not (0.001 < signal_share < 0.998 and 0.001 < decoy_share < 0.998):
        return 0.0
    if signal_share + decoy_share > 0.998:
        return 0.0
    if not (
        LIM_WEAKEST_INTENSITY < decoy_mu and decoy_mu + LIM_WEAKEST_INTENSITY < signal_mu < 1.0
    ):
        return 0.0

    source = DecoySettings(
        signal_intensity=signal_mu,
        decoy_intensity=decoy_mu,
        vacuum_intensity=LIM_WEAKEST_INTENSITY,
        signal_probability=signal_share,
        decoy_probability=decoy_share,
        vacuum_probability=1.0 - signal_share - decoy_share,
    )
    counts = lim_counts(
        length_km, block_size, source=source, key_basis_probability=key_basis_probability
    )
    length = block_size
    for _ in range(40):
        secrecy = min(max(LIM_SECURITY_CONSTANT * length, 1e-30), 0.1)
        result = secret_key_length(
            counts,
            settings=source,
            security=SecurityParameters(correctness=LIM_CORRECTNESS, secrecy=secrecy),
            error_correction_efficiency=LIM_ERROR_CORRECTION_EFFICIENCY,
            degradations=DegradationLog(),
        )
        updated = float(result.length_bits)
        if updated == 0.0 or abs(updated - length) <= 1e-9 * max(updated, 1.0):
            length = updated
            break
        length = updated
    return length / float(counts.pulses)


def lim_optimised_rate(length_km: float, block_size: float) -> float:
    """Maximise ``R`` over ``{q_x, p_1, p_2, mu_1, mu_2}``, as Lim et al. do.

    A coarse grid followed by Nelder-Mead from its best point. The grid is not
    decoration: over most of this domain the rate is exactly zero, so a local
    method started at random finds no gradient at all and reports zero.
    """
    from itertools import product

    from scipy.optimize import minimize

    grid = product(
        (0.5, 0.7, 0.9),
        (0.3, 0.5, 0.7),
        (0.1, 0.3, 0.4),
        (0.3, 0.4, 0.5),
        (0.05, 0.1, 0.2),
    )
    best_rate, best_point = 0.0, None
    for point in grid:
        rate = lim_key_rate(length_km, block_size, point)
        if rate > best_rate:
            best_rate, best_point = rate, point
    if best_point is None:
        return 0.0
    refined = minimize(
        lambda x: -lim_key_rate(length_km, block_size, tuple(x)),
        np.array(best_point),
        method="Nelder-Mead",
        options={"maxiter": 2000, "xatol": 1e-6, "fatol": 1e-18},
    )
    return max(best_rate, float(-refined.fun))


class TestTheLimChannelModelAmbiguity:
    """The measurement behind :func:`lim_channel`'s resolved reading.

    Fast, and kept out of the ``slow`` class below on purpose: it is the
    evidence for a modelling choice, and evidence should run in every loop.
    """

    @pytest.mark.physics
    @pytest.mark.parametrize(("length_km", "expected_ratio"), [(0.0, 8.07), (100.0, 9.98)])
    def test_the_printed_misalignment_term_is_too_large_by_one_over_eta_bob(
        self, length_km: float, expected_ratio: float
    ) -> None:
        """Their ``e_k`` mixes two transmittances, and the factor is measurable.

        The misalignment term of a QBER must tend to ``e_mis`` when the link is
        good: it is the fraction of *detected* signal photons that land in the
        wrong outcome, and no detector efficiency enters it. Their printed form
        puts ``eta_ch`` there while the detection rate beside it carries
        ``eta_sys``, so the implied optical error rate is inflated by
        ``1/eta_Bob`` — 8.07 at zero loss and 9.98 at 100 km, where the
        exponentials have linearised and the ratio is exactly ``1/0.1``.

        Measured against the specification the paper itself states, ``e_mis =
        0.5 %``: the consistent reading contributes 0.48 points of QBER at every
        distance — ``e_mis`` diluted by the afterpulse detections — and the
        printed one contributes 3.9 and 4.8.
        """
        intensity = 0.5
        eta_ch = 10.0 ** (-0.2 * length_km / 10.0)
        eta_sys = eta_ch * LIM_DETECTOR_EFFICIENCY
        detection = 1.0 - (1.0 - 2.0 * LIM_DARK_COUNT_PROBABILITY) * np.exp(-eta_sys * intensity)
        rate = detection * (1.0 + LIM_AFTERPULSE_PROBABILITY)

        printed = LIM_MISALIGNMENT_ERROR * (1.0 - np.exp(-eta_ch * intensity)) / rate
        consistent = LIM_MISALIGNMENT_ERROR * (1.0 - np.exp(-eta_sys * intensity)) / rate

        assert printed / consistent == pytest.approx(expected_ratio, rel=1e-2)
        assert consistent == pytest.approx(
            LIM_MISALIGNMENT_ERROR / (1.0 + LIM_AFTERPULSE_PROBABILITY), rel=0.02
        )
        assert printed > 10.0 * LIM_MISALIGNMENT_ERROR * 0.5


@pytest.mark.slow
@pytest.mark.reference
class TestLim2014Evaluation:
    def test_the_published_block_size_ratio(self) -> None:
        """V2, and the measurement that resolves their error model.

        Lim et al. write, of their Fig. 1: "at a fiber length of 100 km, the
        secret key rate obtained with ``n_X = 1e9`` is about 1.75 times the one
        based on ``n_X = 1e7``". That is a statement about the *finite-size
        scaling*, which is what this module implements, and it is the part of
        their evaluation that survives the ambiguity in their channel model.

        Reproduced here: **1.79**, against their 1.75, both with the same
        optimisation over ``{q_x, p_1, p_2, mu_1, mu_2}``.

        And the ratio is what identifies the reading of their ``e_k``. The four
        combinations of (``eta_ch`` or ``eta_sys`` in the misalignment term) and
        (errors per gate or per detection) give ratios of **1.79**, 2.73, 1.46
        and 1.47. Only the physically consistent one — ``eta_sys``, errors per
        gate — lands on their published figure, so that is the one
        :func:`lim_channel` implements, and the choice rests on their own number
        rather than on taste.
        """
        small = lim_optimised_rate(100.0, 1e7)
        large = lim_optimised_rate(100.0, 1e9)
        assert small > 0.0
        assert large / small == pytest.approx(1.79, rel=0.05)

    def test_a_block_of_1e5_reaches_135_km(self) -> None:
        """Their smallest curve's reach, at a block size one decade larger.

        Lim et al. state that "even if we use a block size of 1e4, cryptographic
        keys can still be distributed over a fiber length of 135 km", and their
        Fig. 1's leftmost curve ends just past that. Reproduced with a block of
        **1e5**: positive key at 135 km, dying between there and 150 km, which
        is the shape of the curve they draw.
        """
        assert lim_optimised_rate(135.0, 1e5) > 0.0
        assert lim_optimised_rate(150.0, 1e5) < lim_optimised_rate(135.0, 1e5)

    def test_their_1e4_block_does_not_reproduce_and_that_is_recorded(self) -> None:
        """The part of their evaluation this implementation does **not** reproduce.

        With a block of 1e4 detections in the key basis, this implementation
        certifies **no key at any fibre length** — not at 135 km, not at 100 km,
        not at zero loss, where the link is as good as it can be. Their Fig. 1
        shows that block size reaching 135 km.

        The disagreement is exactly one decade in block size: our 1e5 curve is
        their 1e4 curve, reaching 135 km and dying shortly after. The two
        candidate causes are a different convention for what ``n_X`` counts and
        a different resolution of the ``e_k`` ambiguity above; neither is
        settled by anything printed in the paper, so the discrepancy is recorded
        here rather than removed by fitting one of them.

        This test asserts the disagreement rather than the agreement. It is a
        V4 snapshot of a known gap, and its job is to fail loudly if a later
        change makes 1e4 blocks work — which would be good news needing this
        docstring rewritten, not a regression.
        """
        for length_km in (0.0, 100.0, 135.0):
            assert lim_optimised_rate(length_km, 1e4) == 0.0


class TestTheExpectedCounts:
    @pytest.mark.physics
    @pytest.mark.parametrize("bias", [0.1, 0.5, 0.9])
    def test_the_sifting_fractions_are_the_squares_of_the_bias(self, bias: float) -> None:
        """``q_x^2`` and ``(1-q_x)^2``, and the rest of the pulses are discarded.

        Alice and Bob choose bases independently, so a detection survives only
        where the two agree. At ``q_x = 0.5`` that keeps half the detections and
        throws away the other half; at 0.9 it keeps 82 % of them and gives the
        check basis 1 %, which is the trade
        :func:`random_sampling_deviation` prices.
        """
        link = conditions()
        block = block_for(link, pulses=1e12, key_basis_probability=bias)
        symmetric = block_for(link, pulses=1e12, key_basis_probability=0.5)
        assert float(block.key_basis.total_detections) == pytest.approx(
            float(symmetric.key_basis.total_detections) * (bias / 0.5) ** 2, rel=1e-12
        )
        assert float(block.check_basis.total_detections) == pytest.approx(
            float(symmetric.check_basis.total_detections) * ((1.0 - bias) / 0.5) ** 2, rel=1e-12
        )

    @pytest.mark.physics
    def test_the_vacuum_state_reproduces_the_background_and_the_coin_flip(self) -> None:
        """A pulse with no photons clicks at ``Y_0`` and is wrong half the time.

        Ma et al. 2005 Eq. (33) at the level of counts, and the check that the
        third intensity really is being treated as the vacuum it is set to.
        """
        link = conditions()
        source = settings()
        block = block_for(link, pulses=1e12, source=source)
        sent = 1e12 * source.vacuum_probability * 0.25
        assert float(block.key_basis.vacuum_detections) == pytest.approx(
            sent * float(link.background_yield), rel=1e-12
        )
        assert float(block.key_basis.vacuum_errors) == pytest.approx(
            float(block.key_basis.vacuum_detections) * VACUUM_ERROR_RATE, rel=1e-12
        )

    @pytest.mark.physics
    def test_the_detections_never_exceed_the_pulses_that_were_sent(self) -> None:
        """The invariant :class:`DecoyBlockCounts` refuses to be constructed without."""
        block = block_for(conditions(transmittance=1.0), pulses=1e6)
        detected = float(block.key_basis.total_detections + block.check_basis.total_detections)
        assert detected <= float(block.pulses)

    def test_pooling_a_pass_adds_the_samples(self) -> None:
        """Counts are counts: a pass is its samples summed, per field."""
        link = conditions(transmittance=np.array([1e-4, 1e-3, 1e-4]))
        samples = block_for(link, pulses=np.array([1e9, 2e9, 1e9]))
        pooled = samples.pooled()
        assert pooled.shape == ()
        assert float(pooled.pulses) == pytest.approx(4e9)
        assert float(pooled.key_basis.signal_detections) == pytest.approx(
            float(np.sum(samples.key_basis.signal_detections))
        )
        assert float(pooled.check_basis.total_errors) == pytest.approx(
            float(np.sum(samples.check_basis.total_errors))
        )

    def test_pooling_along_one_axis_keeps_the_others(self) -> None:
        """A sweep of passes pools each pass and keeps the sweep."""
        link = conditions(transmittance=np.full((2, 3), REFERENCE_TRANSMITTANCE))
        samples = block_for(link, pulses=1e9)
        pooled = samples.pooled(axis=1)
        assert pooled.shape == (2,)
        assert float(pooled.pulses[0]) == pytest.approx(3e9)

    @pytest.mark.parametrize("bias", [0.0, 1.0, -0.5, np.nan])
    def test_an_impossible_basis_bias_is_rejected(self, bias: float) -> None:
        """At zero or one, one of the two bases is never measured."""
        with pytest.raises(DomainError, match="key_basis_probability"):
            expected_block_counts(
                conditions(), settings=settings(), key_basis_probability=bias, pulses=1e9
            )

    def test_a_negative_pulse_budget_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="pulses"):
            expected_block_counts(
                conditions(), settings=settings(), key_basis_probability=0.5, pulses=-1.0
            )

    def test_a_pulse_budget_that_does_not_broadcast_is_rejected(self) -> None:
        """One budget per sample, or one for all of them — never an outer product."""
        link = conditions(transmittance=np.array([1e-4, 1e-3, 1e-4]))
        with pytest.raises(DomainError, match="broadcast"):
            expected_block_counts(
                link,
                settings=settings(),
                key_basis_probability=0.5,
                pulses=np.array([1e9, 2e9]),
            )

    def test_an_empty_pass_is_legal_and_stays_empty(self) -> None:
        """A pass segmented before its first visible sample has no counts.

        Legal for the same reason it is legal in :mod:`quoss.qkd.base`: four
        channel modules had to be fixed for it once, and an empty result is the
        honest answer rather than a traceback.
        """
        link = conditions(transmittance=np.array([]))
        block = block_for(link, pulses=np.array([]))
        assert block.shape == (0,)
        result = secret_key_length(
            block,
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert result.shape == (0,)
        assert result.length_bits.size == 0
        # And every container says so rather than raising on `np.min` of nothing,
        # which is the same guard `quoss.qkd.base` needed.
        assert "empty" in repr(block)
        assert "empty" in repr(block.key_basis)
        assert "empty" in repr(result)

    def test_the_two_count_triples_are_ordered_like_the_intensities(self) -> None:
        """``detections`` and ``errors`` line up with :attr:`DecoySettings.intensities`.

        The order is the one thing no arithmetic can check — putting the decoy
        counts where the signal counts go gives an ordinary positive bound that
        certifies nothing — so it is asserted where it is defined.
        """
        block = block_for(conditions(), pulses=1e12)
        basis = block.key_basis
        assert basis.detections == (
            basis.signal_detections,
            basis.decoy_detections,
            basis.vacuum_detections,
        )
        assert basis.errors == (basis.signal_errors, basis.decoy_errors, basis.vacuum_errors)
        # The signal state is the brightest, so per pulse sent it is the one that
        # clicks most often -- the ordering a swap would invert.
        source = settings()
        per_pulse = [
            float(count) / probability
            for count, probability in zip(basis.detections, source.probabilities, strict=True)
        ]
        assert per_pulse[0] > per_pulse[1] > per_pulse[2]


class TestTheContainersRefuseImpossibleContents:
    @pytest.mark.parametrize(("field", "value"), [("correctness", 0.0), ("secrecy", 1.0)])
    def test_a_security_parameter_outside_zero_to_one_is_rejected(
        self, field: str, value: float
    ) -> None:
        arguments = {"correctness": 1e-10, "secrecy": 1e-10}
        arguments[field] = value
        with pytest.raises(DomainError, match=field):
            SecurityParameters(**arguments)

    def test_the_security_total_is_the_sum_of_its_halves(self) -> None:
        assert security(correctness=1e-9, secrecy=3e-10).total == pytest.approx(1.3e-9)

    def test_a_decoy_ordering_that_inverts_the_denominator_is_rejected(self) -> None:
        """``mu_2 > mu_3`` is what keeps Eqs. (2) and (4) lower bounds."""
        with pytest.raises(DomainError, match="decoy_intensity > vacuum_intensity"):
            settings(decoy_intensity=0.05, vacuum_intensity=0.05)

    def test_an_intensity_ordering_that_breaks_the_derivation_is_rejected(self) -> None:
        """``mu_1 > mu_2 + mu_3`` is the inequality the multi-photon bound needs."""
        with pytest.raises(DomainError, match=r"signal_intensity > decoy_intensity"):
            settings(signal_intensity=0.2, decoy_intensity=0.15, vacuum_intensity=0.1)

    @pytest.mark.parametrize("intensity", [-0.1, np.inf])
    def test_an_impossible_intensity_is_rejected(self, intensity: float) -> None:
        with pytest.raises(DomainError, match="signal_intensity"):
            settings(signal_intensity=intensity)

    def test_a_zero_intensity_probability_is_rejected(self) -> None:
        """Not "skip that state": a different protocol, and a division by zero."""
        with pytest.raises(DomainError, match="decoy_probability"):
            settings(signal_probability=0.8, decoy_probability=0.0, vacuum_probability=0.2)

    def test_probabilities_that_do_not_sum_to_one_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="sum to 1"):
            settings(signal_probability=0.5, decoy_probability=0.2, vacuum_probability=0.2)

    def test_a_negative_photon_number_has_no_tau(self) -> None:
        with pytest.raises(DomainError, match="photons must be non-negative"):
            settings().tau(-1)

    def test_error_counts_above_detection_counts_are_rejected(self) -> None:
        """An error is a detection whose bit disagreed, so it is a subset."""
        with pytest.raises(DomainError, match="exceeds"):
            basis_counts(
                signal_detections=100.0,
                decoy_detections=10.0,
                vacuum_detections=1.0,
                signal_errors=200.0,
                decoy_errors=1.0,
                vacuum_errors=0.5,
            )

    def test_negative_counts_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            basis_counts(
                signal_detections=-1.0,
                decoy_detections=10.0,
                vacuum_detections=1.0,
                signal_errors=0.0,
                decoy_errors=1.0,
                vacuum_errors=0.5,
            )

    def test_non_finite_counts_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            basis_counts(
                signal_detections=np.inf,
                decoy_detections=10.0,
                vacuum_detections=1.0,
                signal_errors=0.0,
                decoy_errors=1.0,
                vacuum_errors=0.5,
            )

    def test_counts_that_do_not_broadcast_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="broadcast"):
            basis_counts(
                signal_detections=np.zeros(3),
                decoy_detections=np.zeros(4),
                vacuum_detections=1.0,
                signal_errors=0.0,
                decoy_errors=0.0,
                vacuum_errors=0.5,
            )

    def test_the_counts_are_frozen_after_construction(self) -> None:
        """Immutable includes the numbers, as everywhere else in this project."""
        counts = basis_counts(
            signal_detections=np.array([1.0, 2.0]),
            decoy_detections=0.0,
            vacuum_detections=0.0,
            signal_errors=0.0,
            decoy_errors=0.0,
            vacuum_errors=0.0,
        )
        with pytest.raises(ValueError, match="read-only"):
            counts.signal_detections[0] = 5.0

    def test_a_block_needs_two_bases_of_the_same_shape(self) -> None:
        with pytest.raises(DomainError, match="same shape"):
            block_counts(
                key_basis=basis_counts(
                    signal_detections=np.zeros(3),
                    decoy_detections=0.0,
                    vacuum_detections=0.0,
                    signal_errors=0.0,
                    decoy_errors=0.0,
                    vacuum_errors=0.0,
                ),
                check_basis=basis_counts(
                    signal_detections=0.0,
                    decoy_detections=0.0,
                    vacuum_detections=0.0,
                    signal_errors=0.0,
                    decoy_errors=0.0,
                    vacuum_errors=0.0,
                ),
                pulses=1e6,
            )

    def test_a_block_that_detected_more_than_it_sent_is_rejected(self) -> None:
        """Pulses is the budget both bases are drawn from."""
        basis = basis_counts(
            signal_detections=600.0,
            decoy_detections=0.0,
            vacuum_detections=0.0,
            signal_errors=0.0,
            decoy_errors=0.0,
            vacuum_errors=0.0,
        )
        with pytest.raises(DomainError, match="exceed the pulses"):
            block_counts(key_basis=basis, check_basis=basis, pulses=1000.0)

    def test_a_block_needs_basis_counts_and_not_something_shaped_like_them(self) -> None:
        with pytest.raises(DomainError, match="must be a BasisCounts"):
            DecoyBlockCounts(key_basis=object(), check_basis=object(), pulses=1.0)  # type: ignore[arg-type]

    def test_a_block_whose_pulses_do_not_broadcast_is_rejected(self) -> None:
        basis = basis_counts(
            signal_detections=np.zeros(3),
            decoy_detections=0.0,
            vacuum_detections=0.0,
            signal_errors=0.0,
            decoy_errors=0.0,
            vacuum_errors=0.0,
        )
        with pytest.raises(DomainError, match="broadcast"):
            block_counts(key_basis=basis, check_basis=basis, pulses=np.zeros(4))

    def test_certified_events_refuse_negative_counts(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            certified(vacuum=-1.0, single_photon=0.0, certified_mask=False)

    def test_certified_events_must_broadcast(self) -> None:
        with pytest.raises(DomainError, match="broadcast"):
            certified(
                vacuum=np.zeros(3),
                single_photon=np.zeros(4),
                certified_mask=np.zeros(3, dtype=bool),
            )

    def test_a_result_refuses_a_negative_length(self) -> None:
        with pytest.raises(DomainError, match="length_bits"):
            finite_result(
                length_bits=-1.0,
                vacuum_events=0.0,
                single_photon_events=0.0,
                phase_error_rate=0.1,
                observed_error_rate=0.01,
                leakage_bits=0.0,
                block_size=0.0,
                pulses=1.0,
                security_parameters=security(),
            )

    @pytest.mark.parametrize(
        ("field", "value"), [("phase_error_rate", 0.6), ("observed_error_rate", 1.5)]
    )
    def test_a_result_refuses_an_impossible_error_rate(self, field: str, value: float) -> None:
        arguments: dict[str, FloatLike] = {
            "length_bits": 0.0,
            "vacuum_events": 0.0,
            "single_photon_events": 0.0,
            "phase_error_rate": 0.1,
            "observed_error_rate": 0.01,
            "leakage_bits": 0.0,
            "block_size": 0.0,
            "pulses": 1.0,
        }
        arguments[field] = value
        with pytest.raises(DomainError, match=field):
            finite_result(security_parameters=security(), **arguments)

    def test_a_result_refuses_non_finite_numbers(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            finite_result(
                length_bits=np.nan,
                vacuum_events=0.0,
                single_photon_events=0.0,
                phase_error_rate=0.1,
                observed_error_rate=0.01,
                leakage_bits=0.0,
                block_size=0.0,
                pulses=1.0,
                security_parameters=security(),
            )

    def test_a_result_refuses_arrays_that_do_not_broadcast(self) -> None:
        with pytest.raises(DomainError, match="broadcast"):
            finite_result(
                length_bits=np.zeros(3),
                vacuum_events=np.zeros(4),
                single_photon_events=0.0,
                phase_error_rate=0.1,
                observed_error_rate=0.01,
                leakage_bits=0.0,
                block_size=0.0,
                pulses=1.0,
                security_parameters=security(),
            )

    def test_a_result_refuses_a_security_claim_that_is_not_one(self) -> None:
        """A key length without its failure probabilities is a number, not a claim."""
        with pytest.raises(DomainError, match="must be a SecurityParameters"):
            finite_result(
                length_bits=0.0,
                vacuum_events=0.0,
                single_photon_events=0.0,
                phase_error_rate=0.1,
                observed_error_rate=0.01,
                leakage_bits=0.0,
                block_size=0.0,
                pulses=1.0,
                security_parameters=1e-10,  # type: ignore[arg-type]
            )


class TestTheModuleSurface:
    def test_a_finite_result_cannot_be_labelled_asymptotic(self) -> None:
        """The regime is a property, not a field, so it cannot be set wrong."""
        result = secret_key_length(
            block_for(conditions(), pulses=REFERENCE_PULSES),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert result.regime is KeyRegime.FINITE
        assert not hasattr(type(result), "regime.setter")

    def test_no_protocol_was_registered_by_this_module(self) -> None:
        """A block-level bound is not a :class:`~quoss.qkd.base.QkdProtocol`.

        The interface maps instants to instants; this module maps a block to a
        length. Registering something here under a protocol name would let a
        scenario select it and then be handed an object with no ``key_rate``.
        """
        assert set(PROTOCOLS.names()) == {"bb84-decoy"}

    def test_the_per_pulse_and_per_sifted_bit_rates_are_zero_on_an_empty_block(self) -> None:
        """Both derived rates divide, and both survive a block with nothing in it."""
        result = finite_result(
            length_bits=0.0,
            vacuum_events=0.0,
            single_photon_events=0.0,
            phase_error_rate=0.5,
            observed_error_rate=0.0,
            leakage_bits=0.0,
            block_size=0.0,
            pulses=0.0,
            security_parameters=security(),
        )
        assert float(result.key_per_pulse) == 0.0
        assert float(result.secret_fraction) == 0.0
        assert not bool(result.has_key)

    def test_the_secret_fraction_is_key_over_sifted_bits(self) -> None:
        """The quantity that makes two links comparable once loss is divided out."""
        result = secret_key_length(
            block_for(conditions(), pulses=REFERENCE_PULSES),
            settings=settings(),
            security=security(),
            error_correction_efficiency=1.22,
            degradations=DegradationLog(),
        )
        assert float(result.secret_fraction) == pytest.approx(
            float(result.length_bits) / float(result.block_size), rel=1e-12
        )
        assert float(result.secret_fraction) == pytest.approx(0.0753, rel=1e-2)

    def test_the_observed_error_rate_of_an_empty_basis_is_zero(self) -> None:
        """No detections is not an error rate; it is the harmless value."""
        counts = basis_counts(
            signal_detections=0.0,
            decoy_detections=0.0,
            vacuum_detections=0.0,
            signal_errors=0.0,
            decoy_errors=0.0,
            vacuum_errors=0.0,
        )
        assert float(counts.observed_error_rate) == 0.0

    @pytest.mark.parametrize(
        "renderer",
        [
            lambda: repr(security()),
            lambda: repr(settings()),
            lambda: repr(block_for(conditions(), pulses=1e9)),
            lambda: repr(block_for(conditions(), pulses=1e9).key_basis),
            lambda: repr(
                certified_events(
                    block_for(conditions(), pulses=1e12).key_basis,
                    settings=settings(),
                    security=security(),
                    degradations=DegradationLog(),
                )
            ),
            lambda: repr(
                secret_key_length(
                    block_for(conditions(), pulses=1e12),
                    settings=settings(),
                    security=security(),
                    error_correction_efficiency=1.22,
                    degradations=DegradationLog(),
                )
            ),
        ],
    )
    def test_every_container_renders_without_raising(self, renderer: Callable[[], str]) -> None:
        """A repr that raises turns a debugging session into a second bug."""
        rendered = renderer()
        assert isinstance(rendered, str)
        assert rendered
