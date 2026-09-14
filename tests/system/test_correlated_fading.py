"""Tests for `quoss.system.correlated_fading`.

Organised by the claim each block defends, not by the function it calls.

- ``TestTheProcess`` — **V1 and V3.** The exact AR(1) discretisation: the
  coefficients are in ``[0, 1)`` with a zero in front (hypothesis), the sampled
  process is stationary with unit variance, and its lag-``k`` autocorrelation is
  ``exp(-k dt / tau)`` to within the estimator's own standard error, on uniform
  and non-uniform grids alike.
- ``TestAgainstTheChannelsClosedForms`` — **V3 against `pointing.py` and
  `link_budget.py`.** A million instantaneous draws reproduce the pointing
  mean ``gamma^2 / (gamma^2 + 1)``, the 1 % pointing quantile ``p^(1/gamma^2)``,
  the pointing outage law, the unit mean of the scintillation factor and the 1 %
  scintillation fade in dB — each with a tolerance derived from the Monte Carlo
  standard error of that estimator.
- ``TestTheDwellAverage`` — **V3 against brute force.** The closed-form
  variance reduction against a fine-grid average of the process, and the
  integrated-OU construction against a fine-grid average of the *factors*:
  mean, per-window variance and pass-level variance, at ``T/tau`` of 0.1, 1
  and 10, with the second-order residual bounded and stated.
- ``TestFadeDurations`` — **V3 against the exact bivariate normal.** The
  down-crossing count per step against ``Phi(c) - Phi_2(c, c; phi)`` (scipy's
  bivariate normal is the independent implementation), the time fraction
  against the marginal outage, and the measurement that an i.i.d. model gets
  fade durations wrong by the ratio of the grid step to the correlation time.
- ``TestWhatCorrelationChangesOnTheGrid`` — the finding the module has to state
  honestly: on a 1 s grid with millisecond fades the dwell-averaged factor
  moves the pooled counts by a fraction of a percent, and an instantaneous draw
  per sample would overstate the fluctuation by ``sqrt(1/w)``, measured.
- ``TestChoosingACorrelationTime`` — the two kinematic helpers on the reference
  pass: the slew through the turbulence scale height against the wind, and the
  millisecond estimate that results with a Fresnel-scale width.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
- ``TestReproducibility`` — the same generator state gives the same ensemble;
  the stream consumed depends only on the shapes.
"""

from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.special import ndtr
from scipy.stats import multivariate_normal

from quoss.channel.link_budget import scintillation_fade_db
from quoss.channel.pointing import (
    mean_pointing_transmittance,
    pointing_outage_probability,
    pointing_transmittance_quantile,
)
from quoss.channel.turbulence import turbulence_scale_height_m
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.system.correlated_fading import (
    FadeDurationStatistics,
    FadeRealisations,
    FadingParameters,
    ar1_coefficients,
    dwell_averaged_variance_reduction,
    fade_duration_statistics,
    line_of_sight_angular_rate_rad_s,
    sample_fade_factors,
    slew_transverse_speed_m_s,
    taylor_correlation_time_s,
)

from .reference import Link, link
from .reference_fading import FadingInputs, fading_inputs

REFERENCE_VARIANCE_NP2 = 0.01528
"""The reference downlink's log-irradiance variance at 20 degrees, from `link_budget.py`."""

REFERENCE_GAMMA = 4.4072
"""``gamma`` at 600 km for Ntanos et al.'s jitter, from `pointing.py`."""

POINTING_GEOMETRY = {
    "range_km": 600.0,
    "jitter_rad": 0.75e-6,
    "wavelength_m": 1.55e-6,
    "transmit_aperture_m": 0.15,
    "receive_aperture_m": 0.75,
}
"""The geometry whose ``gamma`` is `REFERENCE_GAMMA`, for the closed-form oracles."""


@pytest.fixture(scope="module")
def reference_link() -> Link:
    return link()


@pytest.fixture(scope="module")
def reference_inputs() -> FadingInputs:
    return fading_inputs()


def parameters(tau_s: float, tau_p: float | None = None) -> FadingParameters:
    return FadingParameters(
        scintillation_correlation_time_s=tau_s,
        pointing_correlation_time_s=tau_s if tau_p is None else tau_p,
    )


def draw(
    t_s: np.ndarray,
    *,
    realisations: int,
    fading: FadingParameters,
    seed: int = 1,
    variance: float | np.ndarray = REFERENCE_VARIANCE_NP2,
    gamma: float | np.ndarray = REFERENCE_GAMMA,
    dwell_s: np.ndarray | None = None,
    degradations: DegradationLog | None = None,
) -> FadeRealisations:
    return sample_fade_factors(
        t_s,
        realisations=realisations,
        log_irradiance_variance_np2=variance,
        beam_to_jitter_ratio=gamma,
        parameters=fading,
        rng=RandomSource.from_seed(seed).generator,
        degradations=degradations if degradations is not None else DegradationLog(),
        dwell_s=dwell_s,
    )


def lag_autocorrelation(paths: np.ndarray, lag: int) -> tuple[float, float]:
    """Return the mean and standard error over realisations of the lag-``k`` estimate.

    Each realisation gives one estimate of ``E[x_i x_{i+k}]`` for a zero-mean,
    unit-variance process; the spread between realisations is the estimator's
    own uncertainty, so the tolerance is derived rather than chosen.
    """
    per_path = np.mean(paths[:, lag:] * paths[:, :-lag], axis=1)
    return float(per_path.mean()), float(per_path.std(ddof=1) / np.sqrt(per_path.size))


class TestTheProcess:
    """**V1 and V3.** The exact discretisation of an Ornstein-Uhlenbeck process."""

    @given(
        steps=st.lists(st.floats(min_value=0.0, max_value=1e3), min_size=1, max_size=20),
        tau=st.floats(min_value=1e-4, max_value=1e4),
    )
    @settings(max_examples=200, deadline=None)
    def test_coefficients_lie_in_the_unit_interval_with_no_memory_at_the_start(
        self, steps: list[float], tau: float
    ) -> None:
        t_s = np.concatenate([[0.0], np.cumsum(steps)])
        phi = ar1_coefficients(t_s, correlation_time_s=tau)
        assert phi[0] == 0.0
        assert np.all(phi >= 0.0)
        assert np.all(phi <= 1.0)
        # And it is exactly the exponential of the step on the axis, which is the
        # definition (the axis, not the list: cumsum-then-diff is not the identity
        # in floating point).
        assert np.array_equal(phi[1:], np.exp(-np.diff(t_s) / tau))

    def test_a_single_sample_has_a_single_zero_coefficient(self) -> None:
        assert ar1_coefficients(np.array([3.0]), correlation_time_s=1.0).tolist() == [0.0]

    @pytest.mark.physics
    def test_the_sampled_process_is_stationary_with_unit_variance(self) -> None:
        """Every sample has variance one, not only the late ones: no burn-in."""
        realisations = 20_000
        fading = parameters(1.0)
        paths = draw(np.arange(0.0, 5.0, 0.25), realisations=realisations, fading=fading)
        # Recover the Gaussian driver from the scintillation factor.
        sigma = np.sqrt(REFERENCE_VARIANCE_NP2)
        x = (np.log(paths.scintillation) + 0.5 * REFERENCE_VARIANCE_NP2) / sigma
        variance = x.var(axis=0, ddof=1)
        # SE of a sample variance from N normal draws is sqrt(2 / N).
        tolerance = 4.0 * np.sqrt(2.0 / realisations)
        assert np.all(np.abs(variance - 1.0) < tolerance)
        assert np.all(np.abs(x.mean(axis=0)) < 4.0 / np.sqrt(realisations))

    @pytest.mark.physics
    @pytest.mark.parametrize("lag", [1, 2, 5])
    def test_the_autocorrelation_is_the_exponential_of_the_lag(self, lag: int) -> None:
        """**V3**: ``exp(-k dt / tau)`` within four standard errors of the estimator."""
        dt, tau = 0.1, 0.5
        paths = draw(np.arange(0.0, 20.0, dt), realisations=4000, fading=parameters(tau))
        sigma = np.sqrt(REFERENCE_VARIANCE_NP2)
        x = (np.log(paths.scintillation) + 0.5 * REFERENCE_VARIANCE_NP2) / sigma
        estimate, error = lag_autocorrelation(x, lag)
        assert abs(estimate - np.exp(-lag * dt / tau)) < 4.0 * error

    @pytest.mark.physics
    def test_the_pointing_axes_are_independent_and_share_their_own_correlation_time(
        self,
    ) -> None:
        """The pointing factor decorrelates as ``exp(-2 dt / tau_p)``, the square of its drivers.

        ``E[x_t^2 x_s^2] - 1 = 2 rho^2``, so to first order in ``1/gamma^2`` the
        factor's autocorrelation is ``rho^2``; this is why the dwell reduction
        for pointing is taken at ``tau_p / 2``.
        """
        dt, tau_p = 0.1, 1.0
        paths = draw(
            np.arange(0.0, 20.0, dt),
            realisations=4000,
            fading=parameters(1e-3, tau_p),
            gamma=REFERENCE_GAMMA,
        )
        centred = paths.pointing - paths.pointing.mean()
        per_path = np.mean(centred[:, 1:] * centred[:, :-1], axis=1) / centred.var()
        estimate = float(per_path.mean())
        error = float(per_path.std(ddof=1) / np.sqrt(per_path.size))
        expected = np.exp(-2.0 * dt / tau_p)
        # First order in 1/gamma^2 = 0.05: the next term is of that relative size.
        assert abs(estimate - expected) < 4.0 * error + 0.05 * expected

    @pytest.mark.physics
    def test_a_non_uniform_grid_keeps_the_exact_autocorrelation(self) -> None:
        """Two spacings in one axis; each pair of neighbours has its own coefficient."""
        tau = 1.0
        t_s = np.concatenate([np.arange(0.0, 10.0, 0.5), np.arange(10.0, 30.0, 2.0)])
        paths = draw(t_s, realisations=4000, fading=parameters(tau))
        sigma = np.sqrt(REFERENCE_VARIANCE_NP2)
        x = (np.log(paths.scintillation) + 0.5 * REFERENCE_VARIANCE_NP2) / sigma
        fine, coarse = slice(0, 20), slice(20, 30)
        for block, dt in ((fine, 0.5), (coarse, 2.0)):
            estimate, error = lag_autocorrelation(x[:, block], 1)
            assert abs(estimate - np.exp(-dt / tau)) < 4.0 * error

    @pytest.mark.physics
    def test_the_three_drivers_are_independent(self) -> None:
        """Scintillation and pointing come from different air and different hardware."""
        paths = draw(np.arange(0.0, 50.0, 0.1), realisations=200, fading=parameters(1.0))
        s = paths.scintillation.ravel() - paths.scintillation.mean()
        p = paths.pointing.ravel() - paths.pointing.mean()
        correlation = float(np.mean(s * p) / np.sqrt(np.mean(s * s) * np.mean(p * p)))
        # Correlated samples: the effective count is about n / (2 tau / dt) per path.
        effective = 200 * 500 / 20.0
        assert abs(correlation) < 4.0 / np.sqrt(effective)


MARGINAL_REALISATIONS = 1_000_000


@pytest.fixture(scope="module")
def marginal() -> FadeRealisations:
    """Return one instant at a million realisations: the marginal law with no time in it."""
    return draw(
        np.array([0.0]),
        realisations=MARGINAL_REALISATIONS,
        fading=parameters(1e-3, 1e-2),
        seed=3,
    )


class TestAgainstTheChannelsClosedForms:
    """**V3.** A million instantaneous draws against `pointing.py` and `link_budget.py`."""

    @pytest.mark.physics
    def test_the_pointing_mean_is_the_published_one(self, marginal: FadeRealisations) -> None:
        expected = float(
            mean_pointing_transmittance(**POINTING_GEOMETRY, degradations=DegradationLog())
        )
        sample = marginal.pointing[:, 0]
        error = float(sample.std(ddof=1) / np.sqrt(sample.size))
        assert abs(float(sample.mean()) - expected) < 4.0 * error
        assert float(marginal.mean_pointing_factor[0]) == pytest.approx(expected, rel=1e-4)

    @pytest.mark.physics
    def test_the_one_percent_pointing_quantile_is_the_published_one(
        self, marginal: FadeRealisations
    ) -> None:
        """Ntanos et al. equation (10), from the sample side.

        The standard error of an empirical ``p`` quantile is
        ``sqrt(p (1 - p) / N) / f(q_p)`` with ``f`` the density, which for
        ``F(x) = x^(gamma^2)`` is ``gamma^2 p / q_p``.
        """
        expected = float(
            pointing_transmittance_quantile(
                0.01, **POINTING_GEOMETRY, degradations=DegradationLog()
            )
        )
        sample = marginal.pointing[:, 0]
        density = REFERENCE_GAMMA**2 * 0.01 / expected
        error = np.sqrt(0.01 * 0.99 / sample.size) / density
        assert abs(float(np.quantile(sample, 0.01)) - expected) < 4.0 * error

    @pytest.mark.physics
    def test_the_pointing_outage_law_is_a_power_law(self, marginal: FadeRealisations) -> None:
        """``P(F_p < x) = x^(gamma^2)`` at three levels, each within four binomial SEs."""
        sample = marginal.pointing[:, 0]
        for level in (0.7, 0.85, 0.95):
            expected = float(
                pointing_outage_probability(
                    level, **POINTING_GEOMETRY, degradations=DegradationLog()
                )
            )
            observed = float(np.mean(sample < level))
            error = np.sqrt(expected * (1.0 - expected) / sample.size)
            assert abs(observed - expected) < 4.0 * error

    @pytest.mark.physics
    def test_the_scintillation_factor_averages_to_one(self, marginal: FadeRealisations) -> None:
        """The ``-sigma^2 / 2`` in the exponent, checked rather than assumed."""
        sample = marginal.scintillation[:, 0]
        error = float(sample.std(ddof=1) / np.sqrt(sample.size))
        assert abs(float(sample.mean()) - 1.0) < 4.0 * error
        # And the log-variance is sigma^2, which is the other half of the convention.
        log_variance = float(np.log(sample).var(ddof=1))
        assert abs(log_variance - REFERENCE_VARIANCE_NP2) < 4.0 * REFERENCE_VARIANCE_NP2 * np.sqrt(
            2.0 / sample.size
        )

    @pytest.mark.physics
    def test_the_one_percent_scintillation_fade_is_link_budgets(
        self, marginal: FadeRealisations
    ) -> None:
        """Ntanos et al. equation (18), negated, from the sample side.

        The fade in dB is Gaussian with standard deviation ``4.343 sigma``, so
        the empirical 1 % quantile has standard error
        ``4.343 sigma sqrt(p (1 - p) / N) / phi(z_p)``.
        """
        expected = float(scintillation_fade_db(REFERENCE_VARIANCE_NP2, outage_probability=0.01))
        fade_db = -10.0 * np.log10(marginal.scintillation[:, 0])
        observed = float(np.quantile(fade_db, 0.99))
        sd_db = 4.3429 * np.sqrt(REFERENCE_VARIANCE_NP2)
        z = 2.3263
        density = np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi)
        error = sd_db * np.sqrt(0.01 * 0.99 / fade_db.size) / density
        assert abs(observed - expected) < 4.0 * error

    @pytest.mark.physics
    def test_the_factors_respect_their_bounds(self, marginal: FadeRealisations) -> None:
        assert np.all(marginal.pointing > 0.0)
        assert np.all(marginal.pointing <= 1.0)
        assert np.all(marginal.scintillation > 0.0)
        assert np.all(marginal.factor > 0.0)
        assert np.allclose(marginal.factor, marginal.scintillation * marginal.pointing)


class TestTheDwellAverage:
    """**V3 against brute force.** The reduction, and the construction that applies it."""

    @given(
        window=st.floats(min_value=0.0, max_value=1e6),
        tau=st.floats(min_value=1e-6, max_value=1e6),
    )
    @settings(max_examples=300, deadline=None)
    def test_the_reduction_lies_in_the_unit_interval(self, window: float, tau: float) -> None:
        w = float(dwell_averaged_variance_reduction(window, correlation_time_s=tau))
        assert 0.0 < w <= 1.0

    @pytest.mark.physics
    def test_the_reduction_is_monotone_and_has_both_limits(self) -> None:
        u = np.logspace(-6, 6, 200)
        w = dwell_averaged_variance_reduction(u, correlation_time_s=1.0)
        assert np.all(np.diff(w) < 0.0)
        # T << tau: 1 - u / 3 to second order.
        assert np.allclose(w[u < 1e-3], 1.0 - u[u < 1e-3] / 3.0, rtol=0.0, atol=1e-6)
        # T >> tau: 2 tau / T, with the -2 (tau/T)^2 correction.
        assert np.allclose(w[u > 1e3], 2.0 / u[u > 1e3], rtol=2e-3)

    def test_the_series_and_the_closed_form_agree_at_the_switch(self) -> None:
        """Either branch alone would be wrong somewhere; they must meet to machine precision."""
        u = np.array([0.999e-3, 1.001e-3])
        w = dwell_averaged_variance_reduction(u, correlation_time_s=1.0)
        exact = 2.0 * (np.expm1(-u) + u) / u**2
        series = 1.0 - u / 3.0 + u**2 / 12.0 - u**3 / 60.0 + u**4 / 360.0
        assert abs(float(w[0] - series[0])) == 0.0
        assert abs(float(w[1] - exact[1])) == 0.0
        assert abs(float(series[1] - exact[1])) < 1e-13

    @pytest.mark.physics
    def test_the_reduction_matches_a_brute_force_average_of_the_driver(self) -> None:
        """The closed form against the variance of a fine-grid mean of the process.

        A window holding 200 sub-steps of an exact OU path, averaged, over
        40 000 independent paths; the variance of a variance estimate from N
        draws is 2 / N, so the tolerance is four of those.
        """
        realisations, substeps, tau = 40_000, 200, 1.0
        for window in (0.1, 1.0, 10.0):
            paths = draw(
                np.arange(substeps) * (window / substeps),
                realisations=realisations,
                fading=parameters(tau),
                seed=11,
            )
            sigma = np.sqrt(REFERENCE_VARIANCE_NP2)
            x = (np.log(paths.scintillation) + 0.5 * REFERENCE_VARIANCE_NP2) / sigma
            observed = float(x.mean(axis=1).var(ddof=1))
            expected = float(dwell_averaged_variance_reduction(window, correlation_time_s=tau))
            # The fine grid averages the endpoints rather than the integral: a
            # relative bias of order (dt / tau) / 12 on the variance.
            bias = (window / substeps / tau) / 12.0
            assert abs(observed / expected - 1.0) < 4.0 * np.sqrt(2.0 / realisations) + bias

    @pytest.mark.physics
    @pytest.mark.parametrize("window", [0.1, 1.0, 10.0])
    def test_the_construction_matches_a_brute_force_average_of_the_factors(
        self, window: float
    ) -> None:
        """Mean, per-window variance and pass-level variance, against the true average.

        Brute force: four consecutive windows of 200 sub-steps each of the
        *instantaneous* factors, averaged within each window. Construction:
        `sample_fade_factors` with ``dwell_s`` on the four window centres.

        The tolerances: four standard errors of a variance estimate from
        20 000 paths is 5.7 % for a ratio of two independent ones; on top of
        that the construction is first-order in ``sigma^2`` and ``1/gamma^2``,
        and its measured residual at the reference values is under 1.5 % on
        every per-window variance and on the pass-level variance of the
        product, and 5 % on the pass-level variance of the pointing part at
        ``T = tau`` — the squared drivers' cross-window covariance, which is
        the known limitation the module docstring states.
        """
        realisations, substeps, windows, tau = 20_000, 200, 4, 1.0
        fading = parameters(tau)
        fine = draw(
            np.arange(windows * substeps) * (window / substeps),
            realisations=realisations,
            fading=fading,
            seed=5,
        )
        averaged = draw(
            (np.arange(windows) + 0.5) * window,
            realisations=realisations,
            fading=fading,
            seed=6,
            dwell_s=np.full(windows, window),
        )
        statistical = 4.0 * np.sqrt(2.0 / realisations) * np.sqrt(2.0)
        for name, budget in (("scintillation", 0.015), ("pointing", 0.015), ("factor", 0.015)):
            truth = getattr(fine, name).reshape(realisations, windows, substeps).mean(axis=2)
            built = getattr(averaged, name)
            mean_error = 4.0 * truth.std() / np.sqrt(truth.size)
            assert abs(float(built.mean() - truth.mean())) < mean_error + 1e-4
            variance_ratio = float(built.var(axis=0).mean() / truth.var(axis=0).mean())
            assert abs(variance_ratio - 1.0) < statistical + budget
            sum_ratio = float(built.sum(axis=1).var() / truth.sum(axis=1).var())
            pass_level_budget = 0.06 if name == "pointing" else budget
            assert abs(sum_ratio - 1.0) < statistical + pass_level_budget

    @pytest.mark.physics
    def test_the_averaged_factor_keeps_its_bounds_and_reports_its_reduction(self) -> None:
        realisations = 5000
        averaged = draw(
            np.arange(10.0),
            realisations=realisations,
            fading=parameters(1e-3, 1e-2),
            dwell_s=np.ones(10),
        )
        assert np.all(averaged.pointing > 0.0)
        assert np.all(averaged.pointing <= 1.0)
        assert np.all(averaged.scintillation > 0.0)
        assert np.allclose(
            averaged.scintillation_variance_reduction,
            dwell_averaged_variance_reduction(1.0, correlation_time_s=1e-3),
        )
        assert np.allclose(
            averaged.pointing_variance_reduction,
            dwell_averaged_variance_reduction(1.0, correlation_time_s=0.5e-2),
        )
        # A thousand fades per second: each averaged sample is within a few
        # tenths of a percent of its mean.
        assert float(averaged.scintillation.std()) < 0.01

    @pytest.mark.physics
    def test_a_zero_dwell_is_the_instantaneous_factor(self) -> None:
        """``dwell_s = 0`` must reduce exactly to no averaging, including the streams."""
        t_s = np.arange(0.0, 2.0, 0.1)
        instant = draw(t_s, realisations=300, fading=parameters(0.3), seed=9)
        zero = draw(t_s, realisations=300, fading=parameters(0.3), seed=9, dwell_s=np.zeros(20))
        assert np.all(zero.scintillation_variance_reduction == 1.0)
        assert np.all(zero.pointing_variance_reduction == 1.0)
        # Same marginal and same autocorrelation; the streams differ (three
        # normals per step instead of one), so equality is statistical.
        for name in ("scintillation", "pointing"):
            a, b = getattr(instant, name), getattr(zero, name)
            assert abs(float(a.mean() - b.mean())) < 4.0 * float(a.std()) / np.sqrt(a.size / 4.0)


class TestFadeDurations:
    """**V3 against the exact bivariate normal**, and what i.i.d. sampling gets wrong."""

    @pytest.mark.physics
    def test_the_down_crossing_count_per_step_is_the_bivariate_normal_probability(
        self,
    ) -> None:
        """``P(x_{i-1} >= c, x_i < c) = Phi(c) - Phi_2(c, c; phi)``, scipy as the oracle.

        The fade threshold on the scintillation factor maps to a level ``c`` on
        its Gaussian driver; the count of runs is the number of down-crossings
        plus the chance of starting below. Each realisation is an independent
        estimate, so the standard error is the spread between them.
        """
        dt, tau, threshold = 0.5, 1.0, 0.85
        realisations, n = 2000, 401
        t_s = np.arange(n, dtype=np.float64) * dt
        paths = draw(t_s, realisations=realisations, fading=parameters(tau), seed=13)
        stats = fade_duration_statistics(paths.scintillation, t_s, threshold=threshold)
        sigma = np.sqrt(REFERENCE_VARIANCE_NP2)
        c = (np.log(threshold) + 0.5 * REFERENCE_VARIANCE_NP2) / sigma
        phi = np.exp(-dt / tau)
        joint = float(
            multivariate_normal(mean=[0.0, 0.0], cov=[[1.0, phi], [phi, 1.0]]).cdf([c, c])
        )
        crossing = float(ndtr(c)) - joint
        expected_count = float(ndtr(c)) + (n - 1) * crossing
        error = float(stats.count.std(ddof=1) / np.sqrt(realisations))
        assert abs(float(stats.count.mean()) - expected_count) < 4.0 * error
        assert stats.steps == n - 1
        assert float(stats.total_time_s) == pytest.approx(n * dt)

    @pytest.mark.physics
    def test_the_time_fraction_is_the_marginal_outage(self) -> None:
        """Correlation changes durations, not the fraction of time below a level."""
        dt, tau_p, level = 0.02, 0.2, 0.85
        realisations = 1000
        t_s = np.arange(0.0, 20.0, dt)
        paths = draw(t_s, realisations=realisations, fading=parameters(1e-3, tau_p), seed=17)
        stats = fade_duration_statistics(paths.pointing, t_s, threshold=level)
        expected = float(
            pointing_outage_probability(level, **POINTING_GEOMETRY, degradations=DegradationLog())
        )
        error = float(stats.time_fraction.std(ddof=1) / np.sqrt(realisations))
        assert abs(float(stats.time_fraction.mean()) - expected) < 4.0 * error

    @pytest.mark.physics
    def test_an_iid_model_gets_fade_durations_wrong_by_the_step_to_tau_ratio(self) -> None:
        """The number no marginal can produce, and the divergence stated honestly.

        Independent draws at outage ``p`` give fades of mean length
        ``1 / (1 - p)`` steps whatever the grid, so their duration in seconds
        shrinks in proportion to the step. The correlated process gives fades
        of a physical length: measured on the pointing factor below 0.85 with
        ``tau_p = 0.2 s``, 47 ms at a 20 ms step, 22 ms at 5 ms and 14 ms at
        2 ms — 2.3, 4.5 and 7.0 steps against the i.i.d. model's 1.04. The
        duration is not grid-independent either, and that is the Rice
        divergence of the module docstring seen on a grid: the number of fades
        per second grows as ``dt^(-1/2)`` (0.90, 1.90, 2.97) while the fraction
        of time faded stays at the marginal 4.2 %. Both facts are asserted.
        """
        tau_p, level = 0.2, 0.85
        p = float(
            pointing_outage_probability(level, **POINTING_GEOMETRY, degradations=DegradationLog())
        )
        iid_steps = 1.0 / (1.0 - p)
        results: dict[float, tuple[float, float, float, float]] = {}
        for dt in (0.02, 0.002):
            t_s = np.arange(0.0, 40.0, dt)
            correlated = draw(t_s, realisations=400, fading=parameters(1e-3, tau_p), seed=19)
            # The same marginal with no memory at all: a correlation time far below the step.
            independent = draw(t_s, realisations=400, fading=parameters(1e-3, 1e-6), seed=19)
            with_memory = fade_duration_statistics(correlated.pointing, t_s, threshold=level)
            without = fade_duration_statistics(independent.pointing, t_s, threshold=level)
            mean_without = float(np.nanmean(without.mean_duration_s)) / dt
            mean_with = float(np.nanmean(with_memory.mean_duration_s)) / dt
            assert mean_without == pytest.approx(iid_steps, rel=0.1)
            # Same fraction of time faded, to within the estimators.
            assert abs(float(with_memory.time_fraction.mean() - without.time_fraction.mean())) < (
                4.0 * float(with_memory.time_fraction.std(ddof=1)) / np.sqrt(400)
            )
            assert float(with_memory.time_fraction.mean()) == pytest.approx(p, rel=0.05)
            results[dt] = (
                mean_with,
                float(np.nanmean(with_memory.mean_duration_s)),
                float(with_memory.count.mean()) / 40.0,
                float(without.count.mean()) / 40.0,
            )
        coarse, fine = results[0.02], results[0.002]
        assert coarse[0] == pytest.approx(2.3, rel=0.1)
        assert fine[0] == pytest.approx(7.0, rel=0.1)
        assert fine[0] > 5.0 * iid_steps
        assert coarse[1] == pytest.approx(0.047, rel=0.1)
        assert fine[1] == pytest.approx(0.014, rel=0.1)
        # The count per second of the correlated process grows as dt^(-1/2)
        # between the two grids, sqrt(10); the i.i.d. one grows as dt^(-1), ten.
        assert fine[2] / coarse[2] == pytest.approx(np.sqrt(10.0), rel=0.1)
        assert fine[3] / coarse[3] == pytest.approx(10.0, rel=0.1)

    def test_the_worked_example_and_the_no_fade_case(self) -> None:
        factor = np.array(
            [
                [1.0, 0.2, 1.0, 1.0, 0.3, 0.1, 1.0, 1.0],
                [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
                [0.1, 0.1, 1.0, 1.0, 1.0, 1.0, 1.0, 0.1],
            ]
        )
        stats = fade_duration_statistics(factor, np.arange(8.0), threshold=0.5)
        assert stats.count.tolist() == [2, 0, 2]
        assert np.isnan(stats.mean_duration_s[1])
        assert stats.mean_duration_s[0] == 1.5
        assert stats.mean_duration_s[2] == 1.5
        assert stats.time_fraction.tolist() == [0.375, 0.0, 0.375]
        assert np.allclose(stats.count_per_step, [2 / 7, 0.0, 2 / 7])
        assert isinstance(stats, FadeDurationStatistics)

    def test_a_one_dimensional_factor_is_one_realisation(self) -> None:
        stats = fade_duration_statistics(np.array([0.1, 1.0, 0.1]), np.arange(3.0), threshold=0.5)
        assert stats.count.tolist() == [2]

    def test_a_single_sample_axis_has_no_steps(self) -> None:
        stats = fade_duration_statistics(np.array([[0.1]]), np.array([0.0]), threshold=0.5)
        assert stats.steps == 0
        assert stats.total_time_s == 0.0
        assert stats.count.tolist() == [1]
        assert stats.time_fraction.tolist() == [0.0]
        assert stats.count_per_step.tolist() == [0.0]


class TestWhatCorrelationChangesOnTheGrid:
    """The honest finding: on a 1 s grid with millisecond fades, the block barely moves."""

    @pytest.mark.physics
    def test_an_instantaneous_draw_per_sample_overstates_the_pooled_fluctuation(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """The ``sqrt(1/w)`` of the module docstring, measured on pass 1.

        Pool ``pulses * eta_free * F`` over the pass with instantaneous factors
        and with dwell-averaged ones; the ratio of the standard deviations must
        be the ratio the marginal variances and their reductions predict.
        """
        samples = reference_link.samples
        rows = samples.pass_index == 0
        t_s = reference_inputs.t_s[rows]
        dwell = np.asarray(samples.dwell_s)[rows]
        weight = (
            np.asarray(reference_link.conditions.transmittance)[rows]
            * 10.0 ** (reference_inputs.fade_db[rows] / 10.0)
            * dwell
        )
        fading = parameters(1e-3, 1e-2)
        realisations = 4000
        log = DegradationLog()
        instant = draw(
            t_s,
            realisations=realisations,
            fading=fading,
            seed=23,
            variance=reference_inputs.log_irradiance_variance_np2[rows],
            gamma=reference_inputs.beam_to_jitter_ratio[rows],
            degradations=log,
        )
        averaged = draw(
            t_s,
            realisations=realisations,
            fading=fading,
            seed=23,
            variance=reference_inputs.log_irradiance_variance_np2[rows],
            gamma=reference_inputs.beam_to_jitter_ratio[rows],
            dwell_s=dwell,
        )
        # The instantaneous request on a 1 s grid says so in the log.
        entry = next(e for e in log if e.code == "correlated_fading.samples-independent")
        assert entry.severity is Severity.WARNING

        pooled_instant = (instant.factor * weight).sum(axis=1)
        pooled_averaged = (averaged.factor * weight).sum(axis=1)
        observed = float(pooled_instant.std() / pooled_averaged.std())
        # Predicted from the per-sample marginal variances and their reductions.
        var_s = instant.scintillation.var(axis=0)
        var_p = instant.pointing.var(axis=0)
        w_s = averaged.scintillation_variance_reduction
        w_p = averaged.pointing_variance_reduction
        predicted = float(
            np.sqrt(
                np.sum(weight**2 * (var_s + var_p))
                / np.sum(weight**2 * (var_s * w_s + var_p * w_p))
            )
        )
        # Two variance estimates from R draws each: 4 sqrt(2/R) sqrt(2) on the ratio.
        assert observed / predicted == pytest.approx(1.0, abs=4.0 * np.sqrt(2.0 / realisations) * 2)
        # Between the two components' own factors: sqrt(1/w) is 22.4 for the
        # millisecond scintillation and 10 for the ten-millisecond pointing (whose
        # factor decorrelates at tau_p / 2), and the mix lands between them.
        assert 10.0 < predicted < 22.4
        # And the dwell-averaged fluctuation of the pooled count is a fraction of a percent.
        assert float(pooled_averaged.std() / pooled_averaged.mean()) < 0.002

    @pytest.mark.physics
    def test_the_pooled_fluctuation_grows_as_the_square_root_of_tau(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """``w ~ 2 tau / T``, so the pooled standard deviation goes as ``sqrt(tau)``."""
        samples = reference_link.samples
        rows = samples.pass_index == 2
        t_s = reference_inputs.t_s[rows]
        dwell = np.asarray(samples.dwell_s)[rows]
        weight = (
            np.asarray(reference_link.conditions.transmittance)[rows]
            * 10.0 ** (reference_inputs.fade_db[rows] / 10.0)
            * dwell
        )
        spreads = []
        for tau in (1e-3, 1e-2, 1e-1):
            paths = draw(
                t_s,
                realisations=2000,
                fading=parameters(tau),
                seed=29,
                variance=reference_inputs.log_irradiance_variance_np2[rows],
                gamma=reference_inputs.beam_to_jitter_ratio[rows],
                dwell_s=dwell,
            )
            pooled = (paths.factor * weight).sum(axis=1)
            spreads.append(float(pooled.std() / pooled.mean()))
        ratios = np.array(spreads[1:]) / np.array(spreads[:-1])
        assert np.allclose(ratios, np.sqrt(10.0), rtol=0.15)
        assert spreads[0] < 1e-3


class TestChoosingACorrelationTime:
    """The kinematic helpers on the reference pass, and the estimate they give."""

    @pytest.mark.physics
    def test_the_slew_outruns_the_wind_by_an_order_of_magnitude(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """Through the ITU scale height the line of sight sweeps at 60-85 m/s on pass 3.

        Against the 2.3 m/s ground wind of ITU-R P.1621: the Taylor speed of a
        LEO downlink is the slew, and a correlation time taken from a wind
        speed would be thirty times too long.
        """
        rows = reference_link.samples.pass_index == 2
        elevation = reference_inputs.elevation_rad[rows]
        rate = line_of_sight_angular_rate_rad_s(
            elevation, reference_inputs.azimuth_rad[rows], reference_inputs.t_s[rows]
        )
        height = turbulence_scale_height_m()
        speed = slew_transverse_speed_m_s(elevation, angular_rate_rad_s=rate, layer_height_m=height)
        assert height == pytest.approx(7700.0, abs=1.0)
        assert float(rate.max()) == pytest.approx(0.00938, abs=2e-5)
        assert float(speed.min()) == pytest.approx(61.6, abs=0.5)
        assert float(speed.max()) == pytest.approx(84.5, abs=0.5)
        assert float(speed.min()) > 10.0 * 2.3

    @pytest.mark.physics
    def test_a_fresnel_width_gives_milliseconds(
        self, reference_link: Link, reference_inputs: FadingInputs
    ) -> None:
        """The order of magnitude `FadingParameters` asks the caller to own.

        With ``l = sqrt(lambda h)`` — a declared gap, not a published width —
        the reference pass lands between 1.3 and 1.8 ms; the same width over
        the ground wind alone would say 47 ms.
        """
        rows = reference_link.samples.pass_index == 2
        elevation = reference_inputs.elevation_rad[rows]
        rate = line_of_sight_angular_rate_rad_s(
            elevation, reference_inputs.azimuth_rad[rows], reference_inputs.t_s[rows]
        )
        height = turbulence_scale_height_m()
        speed = slew_transverse_speed_m_s(elevation, angular_rate_rad_s=rate, layer_height_m=height)
        width = float(np.sqrt(1.55e-6 * height))
        tau = taylor_correlation_time_s(width, speed)
        assert width == pytest.approx(0.109, abs=1e-3)
        assert float(tau.min()) == pytest.approx(1.29e-3, rel=0.02)
        assert float(tau.max()) == pytest.approx(1.77e-3, rel=0.02)
        assert float(taylor_correlation_time_s(width, 2.3)) == pytest.approx(0.0475, rel=0.01)

    def test_the_angular_rate_of_a_pure_elevation_ramp(self) -> None:
        t = np.arange(10.0)
        rate = line_of_sight_angular_rate_rad_s(np.deg2rad(30.0 + 0.5 * t), np.zeros(10), t)
        assert np.allclose(rate, np.deg2rad(0.5), rtol=1e-9)

    def test_the_angular_rate_unwraps_the_azimuth(self) -> None:
        """A pass through north must not register the 2 pi jump as a slew."""
        t = np.arange(5.0)
        azimuth = np.array([6.20, 6.25, 6.28, 0.03, 0.08])
        rate = line_of_sight_angular_rate_rad_s(np.full(5, 0.5), azimuth, t)
        assert np.all(rate < 0.1)


class TestReproducibility:
    """The same generator state gives the same ensemble, and the stream depends on shapes only."""

    def test_the_same_seed_reproduces_and_a_different_one_does_not(self) -> None:
        t_s = np.arange(0.0, 3.0, 0.5)
        a = draw(t_s, realisations=8, fading=parameters(0.4), seed=41)
        b = draw(t_s, realisations=8, fading=parameters(0.4), seed=41)
        c = draw(t_s, realisations=8, fading=parameters(0.4), seed=42)
        assert np.array_equal(a.factor, b.factor)
        assert not np.array_equal(a.factor, c.factor)

    def test_the_realisations_axis_is_first(self) -> None:
        paths = draw(np.arange(0.0, 3.0, 0.5), realisations=8, fading=parameters(0.4))
        assert paths.shape == (8, 6)
        assert paths.realisations == 8
        assert paths.n == 6
        assert "FadeRealisations(shape=(8, 6)" in repr(paths)
        assert paths.factor.flags.writeable is False

    def test_a_single_sample_axis_works_with_and_without_dwell(self) -> None:
        for dwell in (None, np.array([2.0])):
            paths = draw(np.array([1.0]), realisations=5, fading=parameters(0.4), dwell_s=dwell)
            assert paths.shape == (5, 1)


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError``, because a validator with no test is a comment."""

    @given(tau=st.floats(max_value=0.0) | st.just(float("nan")) | st.just(float("inf")))
    @settings(max_examples=50, deadline=None)
    def test_parameters_reject_non_positive_times(self, tau: float) -> None:
        with pytest.raises(DomainError, match="must be finite and strictly positive"):
            FadingParameters(scintillation_correlation_time_s=tau, pointing_correlation_time_s=1.0)
        with pytest.raises(DomainError, match="must be finite and strictly positive"):
            FadingParameters(scintillation_correlation_time_s=1.0, pointing_correlation_time_s=tau)

    def test_coefficients_reject_a_bad_axis(self) -> None:
        with pytest.raises(DomainError, match="must be 1-D"):
            ar1_coefficients(np.zeros((2, 2)), correlation_time_s=1.0)
        with pytest.raises(DomainError, match="non-finite"):
            ar1_coefficients(np.array([0.0, np.nan]), correlation_time_s=1.0)
        with pytest.raises(DomainError, match="non-decreasing"):
            ar1_coefficients(np.array([1.0, 0.0]), correlation_time_s=1.0)
        with pytest.raises(DomainError, match="correlation_time_s must be finite"):
            ar1_coefficients(np.array([0.0, 1.0]), correlation_time_s=0.0)

    def test_the_reduction_rejects_a_bad_window(self) -> None:
        with pytest.raises(DomainError, match="dwell_s must be finite and non-negative"):
            dwell_averaged_variance_reduction(-1.0, correlation_time_s=1.0)
        with pytest.raises(DomainError, match="dwell_s must be finite and non-negative"):
            dwell_averaged_variance_reduction(np.inf, correlation_time_s=1.0)
        with pytest.raises(DomainError, match="correlation_time_s must be finite"):
            dwell_averaged_variance_reduction(1.0, correlation_time_s=-1.0)

    def test_sampling_rejects_bad_arguments(self) -> None:
        t_s = np.arange(3.0)
        fading = parameters(1.0)
        rng = RandomSource.from_seed(1).generator
        log = DegradationLog()
        with pytest.raises(DomainError, match="realisations must be at least 1"):
            draw(t_s, realisations=0, fading=fading)
        with pytest.raises(DomainError, match="parameters must be a FadingParameters"):
            sample_fade_factors(
                t_s,
                realisations=2,
                log_irradiance_variance_np2=0.01,
                beam_to_jitter_ratio=4.0,
                parameters=(1.0, 1.0),  # type: ignore[arg-type]
                rng=rng,
                degradations=log,
            )
        with pytest.raises(DomainError, match="rng must be a numpy"):
            sample_fade_factors(
                t_s,
                realisations=2,
                log_irradiance_variance_np2=0.01,
                beam_to_jitter_ratio=4.0,
                parameters=fading,
                rng=7,  # type: ignore[arg-type]
                degradations=log,
            )
        with pytest.raises(DomainError, match="log_irradiance_variance_np2 must be finite"):
            draw(t_s, realisations=2, fading=fading, variance=-0.1)
        with pytest.raises(DomainError, match="beam_to_jitter_ratio must be finite"):
            draw(t_s, realisations=2, fading=fading, gamma=0.0)
        with pytest.raises(DomainError, match="must broadcast to the"):
            draw(t_s, realisations=2, fading=fading, variance=np.array([0.01, 0.02]))
        with pytest.raises(DomainError, match="dwell_s must have shape"):
            draw(t_s, realisations=2, fading=fading, dwell_s=np.ones(2))
        with pytest.raises(DomainError, match="dwell_s must be finite and non-negative"):
            draw(t_s, realisations=2, fading=fading, dwell_s=np.array([1.0, -1.0, 1.0]))

    def test_realisations_reject_inconsistent_contents(self) -> None:
        good = draw(np.arange(3.0), realisations=2, fading=parameters(1.0))

        def fields(**overrides: object) -> dict[str, object]:
            base: dict[str, object] = {
                "t_s": np.array(good.t_s),
                "factor": np.array(good.factor),
                "scintillation": np.array(good.scintillation),
                "pointing": np.array(good.pointing),
                "mean_pointing_factor": np.array(good.mean_pointing_factor),
                "scintillation_variance_reduction": np.array(good.scintillation_variance_reduction),
                "pointing_variance_reduction": np.array(good.pointing_variance_reduction),
                "parameters": good.parameters,
            }
            base.update(overrides)
            return base

        with pytest.raises(DomainError, match="parameters must be a FadingParameters"):
            FadeRealisations(**fields(parameters=None))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="t_s must be 1-D"):
            FadeRealisations(**fields(t_s=np.zeros((1, 3))))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="factor must have shape"):
            FadeRealisations(**fields(factor=np.ones((2, 4))))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="must be finite and non-negative"):
            FadeRealisations(**fields(scintillation=-np.ones((2, 3))))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="must share one shape"):
            FadeRealisations(**fields(pointing=np.ones((3, 3)) * 0.5))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="pointing must not exceed 1"):
            FadeRealisations(**fields(pointing=np.ones((2, 3)) * 1.5))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="mean_pointing_factor must have shape"):
            FadeRealisations(**fields(mean_pointing_factor=np.ones(2)))  # type: ignore[arg-type]
        with pytest.raises(DomainError, match=r"must lie in \(0, 1\]"):
            FadeRealisations(**fields(pointing_variance_reduction=np.zeros(3)))  # type: ignore[arg-type]

    def test_fade_statistics_reject_bad_arguments(self) -> None:
        with pytest.raises(DomainError, match="threshold must be finite and strictly positive"):
            fade_duration_statistics(np.ones((1, 3)), np.arange(3.0), threshold=0.0)
        with pytest.raises(DomainError, match="factor must have shape"):
            fade_duration_statistics(np.ones((1, 4)), np.arange(3.0), threshold=0.5)
        with pytest.raises(DomainError, match="factor must have shape"):
            fade_duration_statistics(np.ones((1, 1, 3)), np.arange(3.0), threshold=0.5)
        with pytest.raises(DomainError, match="non-finite"):
            fade_duration_statistics(np.array([[1.0, np.nan, 1.0]]), np.arange(3.0), threshold=0.5)

    def test_the_kinematic_helpers_reject_bad_arguments(self) -> None:
        with pytest.raises(DomainError, match="correlation_width_m must be finite"):
            taylor_correlation_time_s(0.0, 1.0)
        with pytest.raises(DomainError, match="transverse_speed_m_s must be finite"):
            taylor_correlation_time_s(1.0, 0.0)
        with pytest.raises(DomainError, match="must have the shape of t_s"):
            line_of_sight_angular_rate_rad_s(np.zeros(2), np.zeros(3), np.arange(3.0))
        with pytest.raises(DomainError, match="at least two strictly increasing"):
            line_of_sight_angular_rate_rad_s(np.zeros(1), np.zeros(1), np.zeros(1))
        with pytest.raises(DomainError, match="at least two strictly increasing"):
            line_of_sight_angular_rate_rad_s(np.zeros(2), np.zeros(2), np.zeros(2))
        with pytest.raises(DomainError, match=r"elevation_rad must lie in \(0, pi/2\]"):
            slew_transverse_speed_m_s(0.0, angular_rate_rad_s=0.01, layer_height_m=1000.0)
        with pytest.raises(DomainError, match="angular_rate_rad_s must be finite and non-negative"):
            slew_transverse_speed_m_s(0.5, angular_rate_rad_s=-0.01, layer_height_m=1000.0)
        with pytest.raises(
            DomainError, match="layer_height_m must be finite and strictly positive"
        ):
            slew_transverse_speed_m_s(0.5, angular_rate_rad_s=0.01, layer_height_m=0.0)
