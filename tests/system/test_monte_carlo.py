"""Tests for `quoss.system.monte_carlo`.

Organised by the claim each block defends, not by the function it calls.

- ``TestWhatTheDesignNumberUnderReports`` — **the headline measurement.** The
  432 985 bits the project reports today are the key at the 1 % fade quantile
  held for the whole pass; at the mean transmittance the same calculation gives
  758 707, the ensemble's median day sits there, and the two dead passes are
  dead in every realisation.
- ``TestReproducesTheDeterministicVolume`` — **V1, bit for bit.** One
  realisation with its fade factor put through `pass_key_volume` gives the same
  bits as the ensemble's row; a factor of exactly one gives the mean-transmittance
  volume exactly; the P50 with counts at expectation is the deterministic key.
- ``TestWhatCorrelationChanges`` — the honest finding: the P5-P95 band from
  fading alone against the correlation time, crossing 1 % of the median only
  when ``tau`` reaches the grid step, and the counting noise that dwarfs it at
  the physical ``tau``.
- ``TestTheRealisationCount`` — the criterion, not the taste: the order-
  statistic formula against a bootstrap on the ensemble actually drawn, and
  the standard error of the P5 at 1000 realisations.
- ``TestComposingADay`` — quantiles of sums, not sums of quantiles; the
  composed ``eps``.
- ``TestReproducibility`` — the seed reproduces the ensemble regardless of
  the chunk size; a different seed does not.
- ``TestTheLogSaysWhatHappened`` — every degradation entry.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
- ``TestRuntime`` — a thousand realisations over the reference day in seconds,
  measured rather than promised.
"""

from __future__ import annotations

import time

import numpy as np
import pytest

from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.qkd.finite_key import FiniteKeyResult, SecurityParameters
from quoss.system.correlated_fading import FadingParameters, sample_fade_factors
from quoss.system.key_volume import (
    PassKeyVolume,
    asymptotic_pass_key_volume,
    daily_key_volume,
    pass_key_volume,
)
from quoss.system.monte_carlo import (
    MonteCarloDailyKeyVolume,
    MonteCarloKeyVolume,
    MonteCarloOptions,
    monte_carlo_daily_key_volume,
    monte_carlo_pass_key_volume,
    quantile_standard_error,
    realisations_for_quantile,
)
from quoss.system.passes import PassSamples

from .reference import (
    REFERENCE_DAY_NUMBER,
    REFERENCE_FINITE_BITS,
    REFERENCE_FINITE_DAY_BITS,
    Link,
    link,
    reference_protocol,
    reference_security,
)
from .reference_fading import (
    REFERENCE_FADING,
    REFERENCE_SEED,
    FadingInputs,
    fading_inputs,
    fading_inputs_of,
    run_monte_carlo,
)

EXPECTED_BITS_AT_MEAN = (346_063.0, 0.0, 412_644.0, 0.0)
EXPECTED_DAY_BITS_AT_MEAN = 758_707.0
"""The deterministic key at the mean transmittance, measured by the headline test below."""


@pytest.fixture(scope="module")
def reference_link() -> Link:
    return link()


@pytest.fixture(scope="module")
def reference_inputs() -> FadingInputs:
    return fading_inputs()


@pytest.fixture(scope="module")
def reference_ensemble(reference_link: Link) -> MonteCarloKeyVolume:
    """Return a thousand realisations at the physical correlation times, counts sampled."""
    return run_monte_carlo(reference_link, realisations=1000)


def spread(volume: MonteCarloKeyVolume | MonteCarloDailyKeyVolume, column: int) -> float:
    """P5-P95 as a fraction of the P50, for the default quantiles."""
    q = volume.quantile_bits
    return float((q[2, column] - q[0, column]) / q[1, column])


def with_transmittance(conditions: LinkConditions, transmittance: np.ndarray) -> LinkConditions:
    return LinkConditions(
        transmittance=transmittance,
        noise_counts_per_gate=conditions.noise_counts_per_gate,
        misalignment_error=conditions.misalignment_error,
        pulse_rate_hz=conditions.pulse_rate_hz,
        gate_duration_s=conditions.gate_duration_s,
    )


class TestWhatTheDesignNumberUnderReports:
    """The headline measurement of the stage, regenerated rather than cited."""

    @pytest.mark.physics
    def test_the_design_number_is_todays_number(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        assert reference_ensemble.design_bits.tolist() == list(REFERENCE_FINITE_BITS)
        assert reference_ensemble.design.total_bits == REFERENCE_FINITE_DAY_BITS

    @pytest.mark.physics
    def test_the_key_at_the_mean_transmittance_is_seventy_five_percent_higher(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        """The fade allowance taken back out, the pointing factor at its mean.

        1.08-3.90 dB of allowance minus 0.22 dB of mean pointing loss, held for
        the whole pass, is the difference between 432 985 and 758 707 bits: the
        design number under-reports the typical day by 43 %.
        """
        assert reference_ensemble.expected_bits.tolist() == list(EXPECTED_BITS_AT_MEAN)
        assert reference_ensemble.expected.total_bits == EXPECTED_DAY_BITS_AT_MEAN
        ratio = reference_ensemble.expected.total_bits / reference_ensemble.design.total_bits
        assert ratio == pytest.approx(1.752, abs=2e-3)
        assert 1.0 - 1.0 / ratio == pytest.approx(0.43, abs=0.01)

    @pytest.mark.physics
    def test_the_median_day_sits_at_the_mean_transmittance_key(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        """Fading at the physical tau moves the median by less than the bootstrap error."""
        daily = monte_carlo_daily_key_volume(reference_ensemble, degradations=DegradationLog())
        median = float(daily.quantile_bits[1, 0])
        error = float(
            quantile_standard_error(daily.key_bits, 0.5, rng=RandomSource.from_seed(3).generator)[0]
        )
        assert abs(median - EXPECTED_DAY_BITS_AT_MEAN) < 4.0 * error
        assert median / reference_ensemble.design.total_bits == pytest.approx(1.75, abs=0.02)

    @pytest.mark.physics
    def test_the_two_dead_passes_are_dead_in_every_realisation(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        """ADR 0011's finding survives the fade allowance: it is the block, not the margin.

        And the mechanism moves. At the design transmittance the dead passes die
        at the phase-error cap (``phi`` 0.459 and 0.5). At the mean transmittance
        ``phi`` is 0.197 and 0.315, and what kills them is error correction
        outrunning the certified single-photon term — by 2.2 and 8.7 times — so
        that the most favourable of a thousand fading realisations still reaches
        only 58 % and 20 % of its own leakage.
        """
        assert reference_ensemble.outage_probability.tolist() == [0.0, 1.0, 0.0, 1.0]
        assert np.all(reference_ensemble.key_bits[:, [1, 3]] == 0.0)
        assert reference_ensemble.expected.has_key.tolist() == [True, False, True, False]
        design = reference_ensemble.design.finite
        expected = reference_ensemble.expected.finite
        assert design is not None and expected is not None
        assert np.allclose(design.phase_error_rate[[1, 3]], [0.459, 0.5], atol=1e-3)
        assert np.allclose(expected.phase_error_rate[[1, 3]], [0.197, 0.315], atol=1e-3)
        from quoss.qkd.base import binary_entropy

        term = expected.single_photon_events * (1.0 - binary_entropy(expected.phase_error_rate))
        ratio = expected.leakage_bits[[1, 3]] / term[[1, 3]]
        assert np.allclose(ratio, [2.19, 8.66], rtol=0.02)
        ensemble = reference_ensemble.finite
        best = (
            ensemble.single_photon_events
            * (1.0 - binary_entropy(ensemble.phase_error_rate))
            / ensemble.leakage_bits
        ).max(axis=0)
        assert np.allclose(best[[1, 3]], [0.58, 0.20], atol=0.02)
        assert np.all(ensemble.phase_error_rate[:, [1, 3]] < 0.5)

    @pytest.mark.physics
    def test_the_design_number_is_below_the_p5_of_every_live_pass(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        live = [0, 2]
        p5 = reference_ensemble.quantile_bits[0, live]
        assert np.all(p5 > reference_ensemble.design_bits[live])
        # By a wide margin: the P5 is itself 1.6-1.7 times the design figure.
        assert np.all(p5 / reference_ensemble.design_bits[live] > 1.6)

    @pytest.mark.physics
    def test_the_headline_quantiles(self, reference_ensemble: MonteCarloKeyVolume) -> None:
        """The numbers quoted in the module docstring, at the reference seed."""
        q = reference_ensemble.quantile_bits
        assert q[:, 0].tolist() == pytest.approx([329_229.0, 345_658.0, 361_865.0], abs=1.0)
        assert q[:, 2].tolist() == pytest.approx([395_324.0, 412_512.0, 429_023.0], abs=1.0)
        daily = monte_carlo_daily_key_volume(reference_ensemble, degradations=DegradationLog())
        assert daily.quantile_bits[:, 0].tolist() == pytest.approx(
            [735_329.0, 758_314.0, 782_391.0], abs=1.0
        )
        assert reference_ensemble.seed == REFERENCE_SEED
        assert reference_ensemble.fading == REFERENCE_FADING


class TestReproducesTheDeterministicVolume:
    """**V1, bit for bit.** The ensemble is `pass_key_volume` applied to each realisation."""

    @pytest.mark.physics
    def test_one_realisation_through_pass_key_volume_gives_the_same_bits(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """Rebuild realisation 0's transmittance from the same spawned stream.

        The per-pass child of the seed reproduces the fades exactly; putting
        the resulting per-sample transmittance through `pass_key_volume` must
        give the same key to the last bit, which is what the index-ordered
        pooling exists for.
        """
        realisations = 3
        volume = run_monte_carlo(reference_link, realisations=realisations, sample_counts=False)
        samples = reference_link.samples
        eta_free = np.asarray(reference_link.conditions.transmittance) * 10.0 ** (
            reference_inputs.fade_db / 10.0
        )
        children = RandomSource.from_seed(REFERENCE_SEED).spawn(samples.table.n_passes)
        transmittance = np.empty((realisations, samples.size))
        for index in range(samples.table.n_passes):
            rows = samples.pass_index == index
            fades = sample_fade_factors(
                reference_inputs.t_s[rows],
                realisations=realisations,
                log_irradiance_variance_np2=reference_inputs.log_irradiance_variance_np2[rows],
                beam_to_jitter_ratio=reference_inputs.beam_to_jitter_ratio[rows],
                parameters=REFERENCE_FADING,
                rng=children[index].generator,
                degradations=DegradationLog(),
                dwell_s=np.asarray(samples.dwell_s)[rows],
            )
            transmittance[:, rows] = eta_free[rows] * fades.factor
        for r in range(realisations):
            deterministic = pass_key_volume(
                with_transmittance(reference_link.conditions, transmittance[r]),
                samples=samples,
                protocol=reference_protocol(),
                security=reference_security(),
                degradations=DegradationLog(),
            )
            assert deterministic.key_bits.tolist() == volume.key_bits[r].tolist()

    @pytest.mark.physics
    def test_a_factor_of_exactly_one_reproduces_the_mean_transmittance_volume(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """No turbulence, a beam a hundred million jitters wide, no memory: ``F == 1``.

        ``sigma^2 = 0`` makes the scintillation factor exactly one; ``gamma =
        1e8`` makes the mean pointing factor exactly one in float64 and the
        shrunk factor round to one; the ensemble is then `pass_key_volume` at
        ``eta_free`` bit for bit, and `expected_bits` is the same number.
        """
        volume = monte_carlo_pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            nominal_fade_db=reference_inputs.fade_db,
            log_irradiance_variance_np2=0.0,
            beam_to_jitter_ratio=1e8,
            protocol=reference_protocol(),
            security=reference_security(),
            fading=FadingParameters(
                scintillation_correlation_time_s=1e-9, pointing_correlation_time_s=1e-9
            ),
            options=MonteCarloOptions(realisations=2, sample_counts=False),
            random_source=RandomSource.from_seed(1),
            degradations=DegradationLog(),
        )
        eta_free = np.asarray(reference_link.conditions.transmittance) * 10.0 ** (
            reference_inputs.fade_db / 10.0
        )
        deterministic = pass_key_volume(
            with_transmittance(reference_link.conditions, eta_free),
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=reference_security(),
            degradations=DegradationLog(),
        )
        assert volume.key_bits[0].tolist() == deterministic.key_bits.tolist()
        assert volume.key_bits[1].tolist() == deterministic.key_bits.tolist()
        assert volume.expected_bits.tolist() == deterministic.key_bits.tolist()
        assert volume.quantile_bits[1].tolist() == deterministic.key_bits.tolist()
        assert volume.mean_bits.tolist() == deterministic.key_bits.tolist()

    @pytest.mark.physics
    def test_the_bits_are_whole_numbers_in_the_finite_regime(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        assert np.all(reference_ensemble.key_bits == np.floor(reference_ensemble.key_bits))
        assert reference_ensemble.regime is KeyRegime.FINITE
        assert reference_ensemble.finite.regime is KeyRegime.FINITE
        assert reference_ensemble.security == reference_security()

    @pytest.mark.physics
    def test_the_poisson_draw_keeps_errors_inside_detections(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        """The binomial thinning, seen through the observed error rate."""
        observed = reference_ensemble.finite.observed_error_rate[:, [0, 2]]
        assert np.all(observed >= 0.0)
        assert np.all(observed <= 1.0)
        # Around the expected QBER of the live passes, 1.24-1.26 %, and scattered.
        assert np.all(np.abs(observed - 0.0125) < 0.001)
        assert float(observed.std()) > 0.0

    @pytest.mark.physics
    def test_the_click_probability_bounds_the_poisson_approximation(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """The ``1 - Q`` the module docstring quotes: below 1e-3 on this link."""
        eta_free = np.asarray(reference_link.conditions.transmittance) * 10.0 ** (
            reference_inputs.fade_db / 10.0
        )
        click = 1.0 - np.exp(-(eta_free * reference_protocol().signal_intensity))
        assert float(click.max()) < 1e-3


SWEEP_TAUS = (1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0)


@pytest.fixture(scope="module")
def sweep(reference_link: Link) -> dict[float, MonteCarloKeyVolume]:
    """Return fading-only ensembles (counts at expectation) at six correlation times."""
    return {
        tau: run_monte_carlo(
            reference_link,
            fading=FadingParameters(
                scintillation_correlation_time_s=tau, pointing_correlation_time_s=tau
            ),
            realisations=400,
            sample_counts=False,
        )
        for tau in SWEEP_TAUS
    }


class TestWhatCorrelationChanges:
    """The finding the stage has to state honestly, measured on the reference link."""

    TAUS = SWEEP_TAUS

    @pytest.mark.physics
    def test_the_spread_from_fading_grows_as_the_square_root_of_tau(
        self, sweep: dict[float, MonteCarloKeyVolume]
    ) -> None:
        """The module docstring's table: 0.11 % at 1 ms to 30 % at 100 s on pass 1.

        Each decade of ``tau`` multiplies the band by ``sqrt(10)``, because the
        dwell reduction is ``2 tau / T`` and the number of independent stretches
        in a pass goes as ``1 / tau``.
        """
        bands = np.array([spread(sweep[tau], 0) for tau in self.TAUS])
        expected = np.array([0.00106, 0.00332, 0.0104, 0.0360, 0.109, 0.304])
        # 400 realisations: the P5 and P95 each carry ~7 % relative error at this size.
        assert np.allclose(bands, expected, rtol=0.15)
        ratios = bands[1:] / bands[:-1]
        assert np.allclose(ratios[:-1], np.sqrt(10.0), rtol=0.2)

    @pytest.mark.physics
    def test_the_band_crosses_one_percent_between_ten_and_a_hundred_milliseconds(
        self, sweep: dict[float, MonteCarloKeyVolume]
    ) -> None:
        """Two orders of magnitude above the physical estimate of `FadingParameters`."""
        for tau in (1e-3, 1e-2):
            assert spread(sweep[tau], 0) < 0.01
            assert spread(sweep[tau], 2) < 0.01
        for tau in (1.0, 10.0, 100.0):
            assert spread(sweep[tau], 0) > 0.01
            assert spread(sweep[tau], 2) > 0.01
        daily = {
            tau: monte_carlo_daily_key_volume(sweep[tau], degradations=DegradationLog())
            for tau in (1e-3, 1.0, 100.0)
        }
        assert spread(daily[1e-3], 0) == pytest.approx(0.00071, rel=0.2)
        assert spread(daily[1.0], 0) == pytest.approx(0.022, rel=0.2)
        assert spread(daily[100.0], 0) == pytest.approx(0.20, rel=0.2)

    @pytest.mark.physics
    def test_the_median_does_not_move_with_tau(
        self, sweep: dict[float, MonteCarloKeyVolume]
    ) -> None:
        """Correlation widens the distribution; it does not shift it."""
        for tau in self.TAUS:
            median = sweep[tau].quantile_bits[1, [0, 2]]
            assert np.allclose(median, EXPECTED_BITS_AT_MEAN[0::2], rtol=0.01)

    @pytest.mark.physics
    def test_counting_noise_dwarfs_fading_at_the_physical_tau(
        self, reference_link: Link, sweep: dict[float, MonteCarloKeyVolume]
    ) -> None:
        """Nine per cent from counting against a tenth of a per cent from fading.

        The block pools millions of detections, whose Poisson noise alone is a
        few hundredths of a per cent — but the finite-key bound infers the
        single-photon yield from the small decoy and vacuum counts, and that
        inference amplifies their scatter into a 9 % band on the key. Fading at
        millisecond correlation times adds nothing visible on top.
        """
        counting_only = run_monte_carlo(
            reference_link,
            fading=FadingParameters(
                scintillation_correlation_time_s=1e-9, pointing_correlation_time_s=1e-9
            ),
            realisations=400,
            sample_counts=True,
        )
        both = run_monte_carlo(reference_link, realisations=400, sample_counts=True)
        assert spread(counting_only, 0) == pytest.approx(0.090, rel=0.2)
        assert spread(sweep[1e-3], 0) < 0.02 * spread(counting_only, 0)
        assert spread(both, 0) == pytest.approx(spread(counting_only, 0), rel=0.15)
        # And the mechanism: the certified single-photon events scatter far
        # more than the block size does.
        block_scatter = float(
            counting_only.finite.block_size[:, 0].std()
            / counting_only.finite.block_size[:, 0].mean()
        )
        events_scatter = float(
            counting_only.finite.single_photon_events[:, 0].std()
            / counting_only.finite.single_photon_events[:, 0].mean()
        )
        assert block_scatter < 1e-3
        assert events_scatter > 5.0 * block_scatter

    @pytest.mark.physics
    def test_the_mean_is_pulled_below_the_median_only_near_the_cliff(
        self, sweep: dict[float, MonteCarloKeyVolume]
    ) -> None:
        """Far from the cliff the distribution is symmetric; the two agree to the bootstrap."""
        volume = sweep[1.0]
        for column in (0, 2):
            error = float(
                quantile_standard_error(
                    volume.key_bits, 0.5, rng=RandomSource.from_seed(5).generator
                )[column]
            )
            assert (
                abs(float(volume.mean_bits[column] - volume.quantile_bits[1, column])) < 4.0 * error
            )


class TestTheRealisationCount:
    """A criterion, not a taste."""

    @pytest.mark.physics
    def test_the_formula_agrees_with_the_bootstrap(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        """The order-statistic standard error under a normal approximation, against a bootstrap.

        At 1000 realisations the bootstrapped standard error of the P5 is 0.2 %
        of the P50 on both live passes; the formula, fed the measured relative
        spread, predicts the same to within 25 % — the normal approximation's
        worth near, but not at, the finite-key cliff.
        """
        bits = reference_ensemble.key_bits
        bootstrap = quantile_standard_error(bits, 0.05, rng=RandomSource.from_seed(7).generator)
        for column in (0, 2):
            median = float(reference_ensemble.quantile_bits[1, column])
            relative_spread = float(bits[:, column].std(ddof=1)) / median
            z = -1.6449
            density = np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)
            formula = relative_spread * np.sqrt(0.05 * 0.95 / bits.shape[0]) / density
            assert float(bootstrap[column]) / median == pytest.approx(formula, rel=0.25)
            assert float(bootstrap[column]) / median < 0.01
            # Which is what the sizing function returns for that target.
            required = realisations_for_quantile(
                relative_spread, probability=0.05, relative_precision=0.01
            )
            assert required < bits.shape[0]
            assert required == pytest.approx(37, abs=10)

    def test_the_sizing_function_is_the_inverted_formula(self) -> None:
        assert realisations_for_quantile(0.1, probability=0.05, relative_precision=0.01) == 447
        assert realisations_for_quantile(0.1, probability=0.5, relative_precision=0.01) == 158
        assert realisations_for_quantile(0.02, probability=0.05, relative_precision=0.01) == 18
        assert realisations_for_quantile(1e-6, probability=0.5, relative_precision=1.0) == 2

    def test_the_bootstrap_of_a_constant_column_is_zero(self) -> None:
        bits = np.zeros((50, 2))
        bits[:, 1] = np.arange(50.0)
        error = quantile_standard_error(bits, 0.5, rng=RandomSource.from_seed(1).generator)
        assert float(error[0]) == 0.0
        assert float(error[1]) > 0.0


class TestComposingADay:
    """Quantiles of sums, and the composed claim."""

    @pytest.mark.physics
    def test_the_p5_of_the_sum_exceeds_the_sum_of_the_p5s(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        daily = monte_carlo_daily_key_volume(reference_ensemble, degradations=DegradationLog())
        assert daily.day_number.tolist() == [REFERENCE_DAY_NUMBER]
        assert daily.key_bits.shape == (1000, 1)
        assert float(daily.quantile_bits[0, 0]) > float(reference_ensemble.quantile_bits[0].sum())
        assert float(daily.quantile_bits[2, 0]) < float(reference_ensemble.quantile_bits[2].sum())
        assert np.allclose(daily.key_bits[:, 0], reference_ensemble.key_bits.sum(axis=1))
        assert daily.pass_count.tolist() == [4]
        assert daily.outage_probability.tolist() == [0.0]
        assert float(daily.mean_bits[0]) == pytest.approx(
            float(reference_ensemble.mean_bits.sum()), abs=1e-6
        )

    @pytest.mark.physics
    def test_the_day_composes_the_security_claim(
        self, reference_ensemble: MonteCarloKeyVolume
    ) -> None:
        log = DegradationLog()
        daily = monte_carlo_daily_key_volume(reference_ensemble, degradations=log)
        assert daily.security.secrecy == pytest.approx(4e-10, rel=1e-12)
        assert daily.regime is KeyRegime.FINITE
        assert daily.realisations == 1000
        assert daily.n_days == 1
        assert daily.seed == REFERENCE_SEED
        assert daily.protocol == "bb84-decoy"
        assert "n_days=1" in repr(daily)
        entry = next(e for e in log if e.code == "monte_carlo.day-composes-blocks")
        assert entry.details["blocks"] == 4
        # The companions travel with the day, summed.
        assert float(daily.design_bits[0]) == REFERENCE_FINITE_DAY_BITS
        assert float(daily.expected_bits[0]) == EXPECTED_DAY_BITS_AT_MEAN

    @pytest.mark.physics
    def test_a_two_day_window_gives_two_columns(self) -> None:
        two_days = link(step_s=2.0, duration_s=172_800.0)
        volume = run_monte_carlo(two_days, realisations=20, inputs=fading_inputs_of(two_days))
        daily = monte_carlo_daily_key_volume(volume, degradations=DegradationLog())
        assert daily.n_days == 2
        assert daily.day_number.tolist() == [REFERENCE_DAY_NUMBER, REFERENCE_DAY_NUMBER + 1]
        assert int(daily.pass_count.sum()) == two_days.table.n_passes
        reference = daily_key_volume(volume.design, degradations=DegradationLog())
        assert daily.design_bits.tolist() == reference.key_bits.tolist()

    def test_daily_refuses_a_non_volume(self) -> None:
        with pytest.raises(DomainError, match="volume must be a MonteCarloKeyVolume"):
            monte_carlo_daily_key_volume("a day", degradations=DegradationLog())  # type: ignore[arg-type]


class TestReproducibility:
    """The ensemble is a function of the seed and the pass table, and of nothing else."""

    @pytest.mark.physics
    def test_the_chunk_size_does_not_change_a_bit(self, reference_link: Link) -> None:
        fine = run_monte_carlo(reference_link, realisations=50, chunk_elements=1000)
        coarse = run_monte_carlo(reference_link, realisations=50, chunk_elements=10**8)
        assert np.array_equal(fine.key_bits, coarse.key_bits)
        assert np.array_equal(fine.finite.block_size, coarse.finite.block_size)

    @pytest.mark.physics
    def test_the_same_seed_reproduces_and_a_different_one_does_not(
        self, reference_link: Link
    ) -> None:
        a = run_monte_carlo(reference_link, realisations=20, seed=100)
        b = run_monte_carlo(reference_link, realisations=20, seed=100)
        c = run_monte_carlo(reference_link, realisations=20, seed=101)
        assert np.array_equal(a.key_bits, b.key_bits)
        assert not np.array_equal(a.key_bits, c.key_bits)
        assert a.seed == 100 and c.seed == 101

    @pytest.mark.physics
    def test_the_repr_names_the_ensemble(self, reference_ensemble: MonteCarloKeyVolume) -> None:
        text = repr(reference_ensemble)
        assert "realisations=1000" in text
        assert "n_passes=4" in text
        assert f"seed={REFERENCE_SEED}" in text
        assert reference_ensemble.realisations == 1000
        assert reference_ensemble.n_passes == 4
        assert reference_ensemble.key_bits.flags.writeable is False


class TestTheLogSaysWhatHappened:
    """Every degradation entry, and the two that need a synthetic link to fire."""

    @pytest.mark.physics
    def test_the_summary_entry(self, reference_link: Link) -> None:
        log = DegradationLog()
        run_monte_carlo(reference_link, realisations=20, degradations=log)
        entry = next(e for e in log if e.code == "monte_carlo.ensemble-summary")
        assert entry.severity is Severity.INFO
        assert entry.details["realisations"] == 20
        assert entry.details["design_bits"] == list(REFERENCE_FINITE_BITS)
        assert entry.details["expected_bits"] == list(EXPECTED_BITS_AT_MEAN)
        assert entry.details["seed"] == REFERENCE_SEED
        assert "Poisson-sampled" in entry.message
        assert not any(e.code == "monte_carlo.passes-not-independent" for e in log)
        assert not any(e.code == "monte_carlo.transmittance-clipped" for e in log)
        assert not any(e.code == "correlated_fading.samples-independent" for e in log)

    @pytest.mark.physics
    def test_a_correlation_time_comparable_to_the_gap_between_passes_is_flagged(
        self, reference_link: Link
    ) -> None:
        """5363 s between passes 1 and 2; at tau = 1000 s the dropped correlation is 4.6e-3."""
        log = DegradationLog()
        run_monte_carlo(
            reference_link,
            realisations=5,
            fading=FadingParameters(
                scintillation_correlation_time_s=1000.0, pointing_correlation_time_s=1e-3
            ),
            degradations=log,
            sample_counts=False,
        )
        entry = next(e for e in log if e.code == "monte_carlo.passes-not-independent")
        assert entry.severity is Severity.WARNING
        assert entry.details["shortest_gap_s"] == pytest.approx(5363.1, abs=0.5)
        assert entry.details["dropped_correlation"] == pytest.approx(
            np.exp(-5363.15 / 1000.0), rel=1e-3
        )

    @pytest.mark.physics
    def test_a_transmittance_above_one_after_fading_is_clipped_and_flagged(
        self, reference_link: Link
    ) -> None:
        """A synthetic near-lossless link with strong, slow scintillation."""
        samples = reference_link.samples
        bright = LinkConditions(
            transmittance=0.9,
            noise_counts_per_gate=1e-6,
            misalignment_error=0.01,
            pulse_rate_hz=reference_link.conditions.pulse_rate_hz,
            gate_duration_s=reference_link.conditions.gate_duration_s,
        )
        conditions = with_transmittance(bright, np.full(samples.size, 0.9))
        log = DegradationLog()
        volume = monte_carlo_pass_key_volume(
            conditions,
            samples=samples,
            nominal_fade_db=0.4,
            log_irradiance_variance_np2=0.5,
            beam_to_jitter_ratio=4.4,
            protocol=reference_protocol(),
            security=reference_security(),
            fading=FadingParameters(
                scintillation_correlation_time_s=100.0, pointing_correlation_time_s=100.0
            ),
            options=MonteCarloOptions(realisations=3, sample_counts=False),
            random_source=RandomSource.from_seed(2),
            degradations=log,
        )
        entry = next(e for e in log if e.code == "monte_carlo.transmittance-clipped")
        assert entry.severity is Severity.WARNING
        assert entry.details["clipped"] > 0
        assert entry.details["evaluations"] == 3 * samples.size
        assert volume.realisations == 3

    @pytest.mark.physics
    def test_a_link_with_no_noise_samples_zero_vacuum_counts(self, reference_link: Link) -> None:
        """The guarded division of the binomial rate: zero detections, zero errors."""
        samples = reference_link.samples
        quiet = with_transmittance(
            LinkConditions(
                transmittance=np.asarray(reference_link.conditions.transmittance),
                noise_counts_per_gate=0.0,
                misalignment_error=0.01,
                pulse_rate_hz=reference_link.conditions.pulse_rate_hz,
                gate_duration_s=reference_link.conditions.gate_duration_s,
            ),
            np.asarray(reference_link.conditions.transmittance),
        )
        volume = monte_carlo_pass_key_volume(
            quiet,
            samples=samples,
            nominal_fade_db=fading_inputs().fade_db,
            log_irradiance_variance_np2=fading_inputs().log_irradiance_variance_np2,
            beam_to_jitter_ratio=fading_inputs().beam_to_jitter_ratio,
            protocol=reference_protocol(),
            security=reference_security(),
            fading=REFERENCE_FADING,
            options=MonteCarloOptions(realisations=3),
            random_source=RandomSource.from_seed(2),
            degradations=DegradationLog(),
        )
        assert np.all(volume.finite.vacuum_events == 0.0)

    @pytest.mark.physics
    def test_a_single_pass_table_skips_the_gap_check(self, reference_link: Link) -> None:
        keep = np.array([True, False, False, False])
        table = reference_link.table.select(keep)
        samples = table.samples()
        rows = reference_link.samples.pass_index == 0
        inputs = fading_inputs()
        log = DegradationLog()
        one_pass = LinkConditions(
            transmittance=np.asarray(reference_link.conditions.transmittance)[rows],
            noise_counts_per_gate=np.asarray(reference_link.conditions.noise_counts_per_gate)[rows],
            misalignment_error=np.asarray(reference_link.conditions.misalignment_error)[rows],
            pulse_rate_hz=reference_link.conditions.pulse_rate_hz,
            gate_duration_s=reference_link.conditions.gate_duration_s,
        )
        volume = monte_carlo_pass_key_volume(
            one_pass,
            samples=samples,
            nominal_fade_db=inputs.fade_db[rows],
            log_irradiance_variance_np2=inputs.log_irradiance_variance_np2[rows],
            beam_to_jitter_ratio=inputs.beam_to_jitter_ratio[rows],
            protocol=reference_protocol(),
            security=reference_security(),
            fading=FadingParameters(
                scintillation_correlation_time_s=1e6, pointing_correlation_time_s=1e6
            ),
            options=MonteCarloOptions(realisations=3, sample_counts=False),
            random_source=RandomSource.from_seed(2),
            degradations=log,
        )
        assert volume.n_passes == 1
        assert not any(e.code == "monte_carlo.passes-not-independent" for e in log)


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError``."""

    def test_options_reject_bad_values(self) -> None:
        with pytest.raises(DomainError, match="realisations must be at least 1"):
            MonteCarloOptions(realisations=0)
        with pytest.raises(DomainError, match="quantiles must be strictly increasing"):
            MonteCarloOptions(realisations=1, quantiles=())
        with pytest.raises(DomainError, match="quantiles must be strictly increasing"):
            MonteCarloOptions(realisations=1, quantiles=(0.1, 1.5))
        with pytest.raises(DomainError, match="quantiles must be strictly increasing"):
            MonteCarloOptions(realisations=1, quantiles=(0.5, 0.5))
        with pytest.raises(DomainError, match="chunk_elements must be at least 1"):
            MonteCarloOptions(realisations=1, chunk_elements=0)
        assert MonteCarloOptions(realisations=3, sample_counts=0).sample_counts is False  # type: ignore[arg-type]

    def test_the_sizing_and_bootstrap_helpers_reject_bad_arguments(self) -> None:
        with pytest.raises(DomainError, match="relative_spread must be finite"):
            realisations_for_quantile(0.0, probability=0.5, relative_precision=0.01)
        with pytest.raises(DomainError, match=r"probability must lie in \(0, 1\)"):
            realisations_for_quantile(0.1, probability=1.0, relative_precision=0.01)
        with pytest.raises(DomainError, match="relative_precision must be finite"):
            realisations_for_quantile(0.1, probability=0.5, relative_precision=0.0)
        rng = RandomSource.from_seed(1).generator
        with pytest.raises(DomainError, match="key_bits must be 2-D"):
            quantile_standard_error(np.zeros(5), 0.5, rng=rng)
        with pytest.raises(DomainError, match=r"probability must lie in \[0, 1\]"):
            quantile_standard_error(np.zeros((5, 1)), 1.5, rng=rng)
        with pytest.raises(DomainError, match="resamples must be at least 2"):
            quantile_standard_error(np.zeros((5, 1)), 0.5, rng=rng, resamples=1)
        with pytest.raises(DomainError, match="rng must be a numpy"):
            quantile_standard_error(np.zeros((5, 1)), 0.5, rng=1)  # type: ignore[arg-type]

    def test_the_entry_point_rejects_bad_arguments(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        def run(**overrides: object) -> MonteCarloKeyVolume:
            arguments: dict[str, object] = {
                "samples": reference_link.samples,
                "nominal_fade_db": reference_inputs.fade_db,
                "log_irradiance_variance_np2": reference_inputs.log_irradiance_variance_np2,
                "beam_to_jitter_ratio": reference_inputs.beam_to_jitter_ratio,
                "protocol": reference_protocol(),
                "security": reference_security(),
                "fading": REFERENCE_FADING,
                "options": MonteCarloOptions(realisations=2),
                "random_source": RandomSource.from_seed(1),
                "degradations": DegradationLog(),
            }
            conditions = overrides.pop("conditions", reference_link.conditions)
            arguments.update(overrides)
            return monte_carlo_pass_key_volume(conditions, **arguments)  # type: ignore[arg-type]

        with pytest.raises(DomainError, match="samples must be a PassSamples"):
            run(samples=reference_link.table)
        with pytest.raises(DomainError, match="conditions must be a LinkConditions"):
            run(conditions=np.zeros(1800))
        with pytest.raises(DomainError, match="part of the contract"):
            run(
                conditions=LinkConditions(
                    transmittance=1e-3,
                    noise_counts_per_gate=1e-6,
                    misalignment_error=0.01,
                    pulse_rate_hz=1e8,
                    gate_duration_s=1e-9,
                )
            )
        empty = reference_link.table.select(np.zeros(4, dtype=bool)).samples()
        with pytest.raises(DomainError, match="samples is empty"):
            run(
                samples=empty,
                conditions=LinkConditions(
                    transmittance=np.zeros(0) + 1e-3,
                    noise_counts_per_gate=np.zeros(0),
                    misalignment_error=np.zeros(0),
                    pulse_rate_hz=1e8,
                    gate_duration_s=1e-9,
                ),
            )
        with pytest.raises(DomainError, match="must be a Bb84DecoyProtocol"):
            run(protocol="bb84")
        with pytest.raises(DomainError, match="security must be a SecurityParameters"):
            run(security=1e-10)
        with pytest.raises(DomainError, match="fading must be a FadingParameters"):
            run(fading=(1e-3, 1e-2))
        with pytest.raises(DomainError, match="options must be a MonteCarloOptions"):
            run(options=100)
        with pytest.raises(DomainError, match="random_source must be a RandomSource"):
            run(random_source=RandomSource.from_seed(1).generator)
        with pytest.raises(DomainError, match="nominal_fade_db contains non-finite"):
            run(nominal_fade_db=np.nan)
        with pytest.raises(DomainError, match="log_irradiance_variance_np2 must be at least 0"):
            run(log_irradiance_variance_np2=-0.1)
        with pytest.raises(DomainError, match="beam_to_jitter_ratio must be strictly above 0"):
            run(beam_to_jitter_ratio=0.0)
        with pytest.raises(DomainError, match="must broadcast to"):
            run(beam_to_jitter_ratio=np.ones(7))
        with pytest.raises(DomainError, match="gives a transmittance above 1"):
            run(
                conditions=with_transmittance(reference_link.conditions, np.full(1800, 0.9)),
                nominal_fade_db=1.0,
            )

    def test_the_volume_container_rejects_inconsistent_contents(self, reference_link: Link) -> None:
        good = run_monte_carlo(reference_link, realisations=3)

        def fields(**overrides: object) -> dict[str, object]:
            base: dict[str, object] = {
                "samples": good.samples,
                "key_bits": np.array(good.key_bits),
                "quantiles": good.quantiles,
                "quantile_bits": np.array(good.quantile_bits),
                "outage_probability": np.array(good.outage_probability),
                "mean_bits": np.array(good.mean_bits),
                "design": good.design,
                "expected": good.expected,
                "finite": good.finite,
                "seed": good.seed,
                "fading": good.fading,
                "sample_counts": True,
                "protocol": good.protocol,
            }
            base.update(overrides)
            return base

        def build(**overrides: object) -> MonteCarloKeyVolume:
            return MonteCarloKeyVolume(**fields(**overrides))  # type: ignore[arg-type]

        with pytest.raises(DomainError, match="samples must be a PassSamples"):
            build(samples=good.samples.table)
        with pytest.raises(DomainError, match="key_bits must have shape"):
            build(key_bits=np.zeros((3, 2)))
        with pytest.raises(DomainError, match="key_bits must be finite and non-negative"):
            build(key_bits=-np.ones((3, 4)))
        with pytest.raises(DomainError, match="quantile_bits has shape"):
            build(quantile_bits=np.zeros((2, 4)))
        with pytest.raises(DomainError, match="quantile_bits must be finite and non-negative"):
            build(quantile_bits=-np.ones((3, 4)))
        with pytest.raises(DomainError, match="must be non-decreasing down the quantile axis"):
            build(
                quantile_bits=np.array(good.quantile_bits)[::-1] + np.array([[0.0], [1.0], [2.0]])
            )
        with pytest.raises(DomainError, match="outage_probability has shape"):
            build(outage_probability=np.zeros(3))
        with pytest.raises(DomainError, match="outage_probability must be finite and non-negative"):
            build(outage_probability=-np.ones(4))
        with pytest.raises(DomainError, match="outage_probability must not exceed 1"):
            build(outage_probability=np.full(4, 2.0))
        with pytest.raises(DomainError, match="design must be a PassKeyVolume"):
            build(design=None)
        upper = asymptotic_pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            degradations=DegradationLog(),
        )
        with pytest.raises(DomainError, match="expected must be a FINITE volume"):
            build(expected=upper)
        with pytest.raises(DomainError, match="finite must be the FiniteKeyResult"):
            build(finite=good.design.finite)
        with pytest.raises(DomainError, match="fading must be a FadingParameters"):
            build(fading=None)
        with pytest.raises(DomainError, match="protocol must be a non-empty name"):
            build(protocol="")
        assert isinstance(good.design, PassKeyVolume)
        assert isinstance(good.finite, FiniteKeyResult)
        assert isinstance(good.samples, PassSamples)

    def test_the_daily_container_rejects_inconsistent_contents(self, reference_link: Link) -> None:
        good = monte_carlo_daily_key_volume(
            run_monte_carlo(reference_link, realisations=3), degradations=DegradationLog()
        )

        def build(**overrides: object) -> MonteCarloDailyKeyVolume:
            base: dict[str, object] = {
                "day_number": np.array(good.day_number),
                "key_bits": np.array(good.key_bits),
                "quantiles": good.quantiles,
                "quantile_bits": np.array(good.quantile_bits),
                "outage_probability": np.array(good.outage_probability),
                "mean_bits": np.array(good.mean_bits),
                "expected_bits": np.array(good.expected_bits),
                "design_bits": np.array(good.design_bits),
                "pass_count": np.array(good.pass_count),
                "security": good.security,
                "seed": good.seed,
                "protocol": good.protocol,
            }
            base.update(overrides)
            return MonteCarloDailyKeyVolume(**base)  # type: ignore[arg-type]

        with pytest.raises(DomainError, match="strictly ascending"):
            build(day_number=np.array([[1]]))
        with pytest.raises(DomainError, match="strictly ascending"):
            build(
                day_number=np.array([2, 1]),
                key_bits=np.zeros((3, 2)),
                quantile_bits=np.zeros((3, 2)),
                outage_probability=np.zeros(2),
                mean_bits=np.zeros(2),
                expected_bits=np.zeros(2),
                design_bits=np.zeros(2),
                pass_count=np.array([1, 1]),
            )
        with pytest.raises(DomainError, match="key_bits must have shape"):
            build(key_bits=np.zeros((3, 2)))
        with pytest.raises(DomainError, match="key_bits must be finite and non-negative"):
            build(key_bits=np.full((3, 1), np.inf))
        with pytest.raises(DomainError, match="quantile_bits has shape"):
            build(quantile_bits=np.zeros((3, 2)))
        with pytest.raises(DomainError, match="mean_bits must be finite"):
            build(mean_bits=np.array([-1.0]))
        with pytest.raises(DomainError, match="outage_probability must not exceed 1"):
            build(outage_probability=np.array([1.5]))
        with pytest.raises(DomainError, match="pass_count must have shape"):
            build(pass_count=np.array([0]))
        with pytest.raises(DomainError, match="security must be a SecurityParameters"):
            build(security=None)
        with pytest.raises(DomainError, match="protocol must be a non-empty name"):
            build(protocol="")
        assert isinstance(good.security, SecurityParameters)


class TestRuntime:
    """Measured, not promised: the number the module docstring quotes."""

    @pytest.mark.physics
    def test_a_thousand_realisations_over_the_day_take_seconds(self, reference_link: Link) -> None:
        """1.8 million link evaluations plus four thousand blocks; about a second here.

        The bound is an order of magnitude above the measurement so that a slow
        CI runner does not fail it; the number itself is in the report.
        """
        started = time.perf_counter()
        volume = run_monte_carlo(reference_link, realisations=1000, seed=77)
        elapsed = time.perf_counter() - started
        assert volume.key_bits.shape == (1000, 4)
        assert elapsed < 30.0
