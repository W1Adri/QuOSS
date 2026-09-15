"""Tests for `quoss.channel.pointing`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestAgainstTheExactIntegral`` — **V2**, and the strongest anchor this
  module has. Farid & Hranilovic 2007 print both the exact collected fraction
  (their equation (8), a double integral) and the closed form the module uses
  (their equation (9)). The exact one is integrated numerically here with
  ``scipy.integrate.quad`` — a core dependency, so an in-process oracle that
  need not be frozen, the same argument as the DOP853 oracle in
  ``tests/orbits/test_perturbations.py`` — and the closed form is measured
  against it, including inside the regime the paper says it should not be used.
- ``TestTwoPublishedSourcesAgree`` — **V2**. The fading exponent is published
  independently by Farid & Hranilovic (as ``gamma^2``, lengths) and by Ntanos et
  al. (as ``beta_p``, angles). They agree to 1 %, and the residual is
  attributed rather than tolerated.
- ``TestTheDoubleCountingTrap`` — the 17.5 dB that the module's shape exists to
  prevent, asserted as a property of the API rather than trusted to a comment.
- ``TestTheFadingLaw`` — **V1**. The power law derived in the module docstring,
  checked against a Monte Carlo draw from the Rayleigh jitter it comes from, and
  the mean/quantile/CDF checked against each other for consistency.
- ``TestTheOutOfRangeWarning`` — that the model says when its published
  validity condition fails, from both sides, and that the condition really does
  fail for the reference system's largest telescope.
- ``TestRejectsBadInput`` / ``TestModuleSurface``.

Not reproduced, and declared: **Table I of Farid & Hranilovic**, which prints an
NMSE between equations (8) and (9) for six values of ``W/a``. The averaging
range and the normalisation of that NMSE are not stated, and no plausible
convention reproduces the printed values — the closest attempts land 100 to
1000 times lower, and their last two entries (0.159e-3 and 0.153e-3) barely
differ, which is what a numerical floor looks like rather than a trend. What is
reproduced instead is the *claim the table is there to support*: the
approximation degrades as ``W/a`` shrinks, monotonically, and the threshold the
authors state is where the error becomes visible.
"""

from __future__ import annotations

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import erf

from quoss.channel.beam import beam_radius_m, divergence_half_angle_rad, geometric_transmittance
from quoss.channel.pointing import (
    GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT,
    beam_to_jitter_ratio,
    equivalent_beam_radius_m,
    mean_pointing_transmittance,
    pointing_outage_probability,
    pointing_transmittance,
    pointing_transmittance_quantile,
)
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.core.units import km_to_m, transmittance_to_loss_db

# --------------------------------------------------------------------------- #
# The reference geometry, and the published parameters that fix it
# --------------------------------------------------------------------------- #

WAVELENGTH_M = 1.55e-6
TRANSMIT_APERTURE_M = 0.15
RECEIVE_APERTURE_M = 0.75
RANGE_KM = 600.0
JITTER_RAD = 0.75e-6
"""Ntanos et al. 2021 §4.1, the same declared system as ``tests/channel/test_beam.py``.

"The pointing error variance was set to 0.75 urad, and the pointing loss was
calculated for an outage probability of 1%." Read as a standard deviation per
axis rather than a variance: a variance in rad^2 would make the r.m.s. error
0.87 mrad, three orders of magnitude wider than the 13 urad beam the same
paragraph specifies, which would put the link permanently in outage. The paper's
own use of the number in its equation (9) — ``beta_p = w_0^2 / 4 sigma_p^2``,
which is dimensionally a ratio of two angles squared — confirms it.
"""

FARID_TABLE_1 = {2: 13.0e-3, 4: 2.25e-3, 6: 0.8158e-3, 8: 0.344e-3, 10: 0.159e-3, 12: 0.153e-3}
"""Farid & Hranilovic 2007 Table I, "NMSE between exact and approximate h_p expressions".

Keyed by ``w_z / a``. Transcribed for the record and **not** asserted against —
see the module docstring for why, and ``test_the_error_shrinks_monotonically_as_the_table_says``
for what is asserted instead.
"""


def _geometry(**overrides: float) -> dict[str, float]:
    """Return the reference geometry keywords, with any overridden."""
    base: dict[str, float] = {
        "wavelength_m": WAVELENGTH_M,
        "transmit_aperture_m": TRANSMIT_APERTURE_M,
        "receive_aperture_m": RECEIVE_APERTURE_M,
    }
    base.update(overrides)
    return base


def _exact_collected_fraction(
    displacement_m: float, *, aperture_radius_m: float, beam_m: float
) -> float:
    """Farid & Hranilovic equation (8), integrated numerically.

    The published exact expression is the double integral of the Gaussian beam
    of their equation (7) over a circular detector displaced by ``r``::

        h_p(r) = int_{-a}^{a} int_{-zeta}^{zeta} (2 / pi w^2)
                 exp(-2 ((x - r)^2 + y^2) / w^2) dy dx,   zeta = sqrt(a^2 - x^2)

    The inner integral is an error function in closed form, which turns this
    into one well-behaved quadrature rather than two: ``int exp(-2 y^2 / w^2) dy``
    over ``[-zeta, zeta]`` is ``(w sqrt(pi) / sqrt(2)) erf(sqrt(2) zeta / w)``.
    Doing that step by hand rather than calling ``dblquad`` is what keeps this
    oracle fast enough to run in the default suite.
    """

    def integrand(x: float) -> float:
        zeta = np.sqrt(max(aperture_radius_m**2 - x**2, 0.0))
        return float(
            np.exp(-2.0 * (x - displacement_m) ** 2 / beam_m**2) * erf(np.sqrt(2.0) * zeta / beam_m)
        )

    value, _ = quad(integrand, -aperture_radius_m, aperture_radius_m, limit=200)
    return float((2.0 / (np.pi * beam_m**2)) * (beam_m * np.sqrt(np.pi) / np.sqrt(2.0)) * value)


@pytest.mark.physics
class TestAgainstTheExactIntegral:
    """The closed form against the exact integral both printed in the same paper.

    This is what makes the module's central approximation checkable rather than
    inherited: equation (9) is a fit to equation (8), and equation (8) can be
    evaluated to machine precision.
    """

    def test_the_exact_integral_at_zero_offset_is_the_beam_module_formula(self) -> None:
        """Equation (8) at ``r = 0`` is analytically ``1 - exp(-2 a^2 / W^2)``.

        Which is exactly what ``beam.geometric_transmittance`` returns, so this
        is a second published source arriving at the same geometric coupling by
        a different route — Ntanos et al.'s product of gains was the first. The
        agreement is to eight digits, i.e. to the quadrature's own accuracy,
        because the two expressions are the same integral.
        """
        beam_m = float(
            beam_radius_m(
                RANGE_KM, wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
            )
        )
        numeric = _exact_collected_fraction(
            0.0, aperture_radius_m=0.5 * RECEIVE_APERTURE_M, beam_m=beam_m
        )
        from_beam_module = float(
            geometric_transmittance(
                RANGE_KM,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=TRANSMIT_APERTURE_M,
                receive_aperture_m=RECEIVE_APERTURE_M,
            )
        )
        assert numeric == pytest.approx(from_beam_module, rel=1e-8)

    def test_the_published_a0_agrees_with_the_exact_value_at_zero_offset(self) -> None:
        """``A_0 = erf(v)^2`` against the exact ``1 - exp(-2 a^2 / W^2)``.

        The paper's ``A_0`` is itself an approximation — chosen so that the
        pointing dependence collapses into a single Gaussian — and this is where
        ``beam.geometric_transmittance`` differs from it. Measured: **-4.2e-4**
        relative, which is 0.0018 dB, at the reference geometry. QuOSS keeps the
        exact value, so the two modules multiply to the exact coupling at zero
        offset rather than to the fit.
        """
        beam_m = float(
            beam_radius_m(
                RANGE_KM, wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
            )
        )
        aperture_radius_m = 0.5 * RECEIVE_APERTURE_M
        v = np.sqrt(np.pi) * aperture_radius_m / (np.sqrt(2.0) * beam_m)
        published_a0 = float(erf(v) ** 2)
        exact = 1.0 - np.exp(-2.0 * aperture_radius_m**2 / beam_m**2)
        assert published_a0 / exact - 1.0 == pytest.approx(-4.2e-4, rel=0.05)
        assert abs(10.0 * np.log10(published_a0 / exact)) < 0.01

    @pytest.mark.parametrize("receive_aperture_m", [0.75, 1.3, 2.3])
    def test_the_closed_form_tracks_the_exact_integral_where_the_jitter_puts_the_beam(
        self, receive_aperture_m: float, degradations: DegradationLog
    ) -> None:
        """Compare equations (8) and (9) over the displacements that actually occur.

        The right interval to compare over is not "all r" but "the r a Rayleigh
        jitter produces": beyond four standard deviations lies 3.4e-4 of the
        distribution, and beyond a full beam radius lies 1e-17 of it at the
        reference jitter. Measured over ``[0, 4 sigma_s]``, the closed form is
        within **0.04 %** for the 0.75 m telescope, 0.12 % for 1.3 m and
        **0.36 %** for 2.3 m — the last of which is *below* the paper's stated
        ``W/a > 6`` validity threshold and still fine here, which is why the
        module warns instead of refusing.
        """
        beam_m = float(
            beam_radius_m(
                RANGE_KM, wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
            )
        )
        aperture_radius_m = 0.5 * receive_aperture_m
        jitter_displacement_m = JITTER_RAD * km_to_m(RANGE_KM)
        offsets_rad = np.linspace(0.0, 4.0 * JITTER_RAD, 25)

        exact = np.array(
            [
                _exact_collected_fraction(
                    float(offset * km_to_m(RANGE_KM)),
                    aperture_radius_m=aperture_radius_m,
                    beam_m=beam_m,
                )
                for offset in offsets_rad
            ]
        )
        relative = pointing_transmittance(
            offsets_rad,
            range_km=RANGE_KM,
            degradations=degradations,
            **_geometry(receive_aperture_m=receive_aperture_m),
        )
        absolute = (
            float(
                geometric_transmittance(
                    RANGE_KM,
                    wavelength_m=WAVELENGTH_M,
                    transmit_aperture_m=TRANSMIT_APERTURE_M,
                    receive_aperture_m=receive_aperture_m,
                )
            )
            * relative
        )
        worst = float(np.max(np.abs(absolute / exact - 1.0)))
        assert worst < 0.005
        assert 4.0 * jitter_displacement_m < beam_m

    def test_the_error_shrinks_monotonically_as_the_table_says(
        self, degradations: DegradationLog
    ) -> None:
        """Table I's *claim*, since Table I's *numbers* are not reproducible.

        The paper's table asserts that the approximation improves as ``W/a``
        grows, and states ``W/a > 6`` as the point where it is good. That
        ordering is reproducible and is what this asserts, over the same six
        values of ``W/a`` the table uses, comparing out to two beam radii where
        the approximation is under stress. Measured: 46 % maximum relative error
        at ``W/a = 2`` falling to 0.2 % at ``W/a = 12``, strictly decreasing.

        The printed NMSE values themselves are transcribed in
        ``FARID_TABLE_1`` and deliberately not asserted — the module docstring
        says why.
        """
        beam_m = 1.0
        errors = []
        for ratio in FARID_TABLE_1:
            aperture_radius_m = beam_m / ratio
            v = np.sqrt(np.pi) * aperture_radius_m / (np.sqrt(2.0) * beam_m)
            a0 = float(erf(v) ** 2)
            equivalent_sq = beam_m**2 * np.sqrt(np.pi) * erf(v) / (2.0 * v * np.exp(-(v**2)))
            displacements = np.linspace(0.0, 2.0 * beam_m, 30)
            exact = np.array(
                [
                    _exact_collected_fraction(
                        float(r), aperture_radius_m=aperture_radius_m, beam_m=beam_m
                    )
                    for r in displacements
                ]
            )
            approximate = a0 * np.exp(-2.0 * displacements**2 / equivalent_sq)
            errors.append(float(np.max(np.abs(approximate / exact - 1.0))))

        assert np.all(np.diff(errors) < 0.0)
        assert errors[0] == pytest.approx(0.46, rel=0.1)
        assert errors[-1] < 0.01


# --------------------------------------------------------------------------- #
# V2 — two independent sources for the same exponent
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTwoPublishedSourcesAgree:
    def test_gamma_squared_matches_ntanos_beta_p(self, degradations: DegradationLog) -> None:
        """Farid & Hranilovic (11) against Ntanos et al. (9), same system.

        The two write the same ratio in different variables: ``gamma^2`` uses
        the equivalent beam radius and the jitter as displacements at the
        receiver plane, ``beta_p`` uses the divergence half-angle and the jitter
        as angles. Dividing the first by the range squared gives the second,
        except that Farid & Hranilovic's numerator carries the finite-aperture
        correction and Ntanos et al.'s does not.

        Measured: 19.42 against 19.23, a 1 % difference, which is **0.01 dB** in
        the 1-in-100 pointing loss (1.030 dB against 1.040 dB). The residual is
        the aperture correction, not slack: it equals ``(w_zeq / (theta_div z))^2``
        exactly, which this test asserts, so if either expression were mistyped
        the attribution would fail even though the 1 % agreement might survive.
        """
        gamma = float(
            beam_to_jitter_ratio(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            )
        )
        divergence = divergence_half_angle_rad(
            wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
        )
        beta_p = divergence**2 / (4.0 * JITTER_RAD**2)

        assert gamma**2 == pytest.approx(19.423, rel=1e-3)
        assert beta_p == pytest.approx(19.234, rel=1e-3)
        assert gamma**2 / beta_p == pytest.approx(1.0099, rel=1e-3)

        equivalent_m = float(
            equivalent_beam_radius_m(RANGE_KM, degradations=degradations, **_geometry())
        )
        attributed = (equivalent_m / (divergence * km_to_m(RANGE_KM))) ** 2
        assert gamma**2 / beta_p == pytest.approx(attributed, rel=1e-12)

    def test_the_one_percent_outage_loss_matches_ntanos_own_formula(
        self, degradations: DegradationLog
    ) -> None:
        """Ntanos et al. equation (10), ``L_pt = p_0^(1/beta_p)``, at their own 1 % outage.

        Their formula and their parameters give 1.040 dB; this module gives
        1.030 dB. The difference is the aperture correction attributed above,
        and it is asserted as a bound on the *decibel* difference because that
        is the quantity a link budget carries.
        """
        theirs = 0.01 ** (
            1.0
            / (
                divergence_half_angle_rad(
                    wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
                )
                ** 2
                / (4.0 * JITTER_RAD**2)
            )
        )
        ours = float(
            pointing_transmittance_quantile(
                0.01,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        )
        theirs_db = -10.0 * np.log10(theirs)
        ours_db = float(transmittance_to_loss_db(ours))
        assert theirs_db == pytest.approx(1.040, abs=0.002)
        assert ours_db == pytest.approx(1.030, abs=0.002)
        assert abs(theirs_db - ours_db) < 0.02

    def test_the_mean_matches_ntanos_published_mean(self, degradations: DegradationLog) -> None:
        """Ntanos et al. equation (8) prints the mean as ``beta_p / (beta_p + 1)``.

        Derived here from the power law instead, as ``gamma^2 / (gamma^2 + 1)``,
        which is the same expression once the exponents agree. Two sources for
        one formula, and the integral that produces it —
        ``int_0^1 x gamma^2 x^(gamma^2 - 1) dx`` — is checked numerically too,
        because a mean that agrees with a published closed form but not with its
        own distribution would mean the distribution is the broken one.
        """
        gamma = float(
            beam_to_jitter_ratio(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            )
        )
        exponent = gamma**2
        published = exponent / (exponent + 1.0)
        measured = float(
            mean_pointing_transmittance(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            )
        )
        assert measured == pytest.approx(published, rel=1e-12)

        integrated, _ = quad(lambda x: x * exponent * x ** (exponent - 1.0), 0.0, 1.0)
        assert measured == pytest.approx(integrated, rel=1e-9)


# --------------------------------------------------------------------------- #
# The 17.5 dB the module's shape exists to prevent
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheDoubleCountingTrap:
    def test_perfect_pointing_returns_exactly_one(self, degradations: DegradationLog) -> None:
        """The property that makes the factor safe to multiply, asserted exactly.

        If any function here returned the published ``h_p`` — which includes
        ``A_0`` — then multiplying it by ``beam.geometric_transmittance`` would
        apply the geometric coupling twice. Zero offset returning exactly 1.0,
        and an outage probability of 1 returning exactly 1.0, is what says it
        does not.
        """
        assert (
            float(
                pointing_transmittance(
                    0.0, range_km=RANGE_KM, degradations=degradations, **_geometry()
                )
            )
            == 1.0
        )
        assert (
            float(
                pointing_transmittance_quantile(
                    1.0,
                    range_km=RANGE_KM,
                    jitter_rad=JITTER_RAD,
                    degradations=degradations,
                    **_geometry(),
                )
            )
            == 1.0
        )

    def test_what_double_counting_would_cost(self, degradations: DegradationLog) -> None:
        """Measure the error the API shape prevents, so the docstring's 17.5 dB is real.

        Following the source literally — using ``h_p`` as "the pointing loss"
        next to a separate geometric loss — applies ``A_0`` twice. At the
        reference geometry ``A_0`` is 0.0179, so the double count is 17.5 dB of
        loss invented from nothing, and the wrong total (35 dB) is just as
        plausible-looking as the right one (17.5 dB).
        """
        coupling = float(
            geometric_transmittance(
                RANGE_KM,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=TRANSMIT_APERTURE_M,
                receive_aperture_m=RECEIVE_APERTURE_M,
            )
        )
        relative = float(
            pointing_transmittance(
                JITTER_RAD, range_km=RANGE_KM, degradations=degradations, **_geometry()
            )
        )
        correct_db = float(transmittance_to_loss_db(coupling * relative))
        double_counted_db = float(transmittance_to_loss_db(coupling * coupling * relative))
        assert double_counted_db - correct_db == pytest.approx(17.48, abs=0.01)
        assert correct_db == pytest.approx(17.587, abs=0.01)

    def test_no_function_here_returns_the_absolute_coupling(
        self, degradations: DegradationLog
    ) -> None:
        """Everything is in ``(0, 1]`` and near 1, not near ``A_0``.

        A crude guard on purpose: it is the property that would break first if
        someone folded ``A_0`` back in for convenience, and it does not depend
        on any particular number staying the same.
        """
        values = [
            pointing_transmittance(
                JITTER_RAD, range_km=RANGE_KM, degradations=degradations, **_geometry()
            ),
            pointing_transmittance_quantile(
                0.01,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            ),
            mean_pointing_transmittance(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            ),
        ]
        for value in values:
            assert 0.5 < float(value) <= 1.0


# --------------------------------------------------------------------------- #
# V1 — the fading law, against the jitter it is derived from
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheFadingLaw:
    def test_the_power_law_matches_a_draw_from_the_rayleigh_jitter(
        self, rng: np.random.Generator, degradations: DegradationLog
    ) -> None:
        """The derivation in the module docstring, checked by simulation.

        Draw two independent Gaussians for the two axes, form the radial error,
        push it through equation (9), and the resulting sample must follow
        ``F(x) = x^(gamma^2)``. This is the one test that would catch an error in
        the *derivation* rather than in the transcription: an exponent of
        ``gamma`` instead of ``gamma^2``, or a factor of 2 in the Rayleigh
        parameter, both leave every published check above intact.

        The seed is the suite's, so the agreement is replayable, and the
        tolerance is **derived rather than chosen**: an empirical frequency from
        ``n`` draws is a binomial mean, so its standard error is
        ``sqrt(p (1 - p) / n)``, and the assertion is four of those. That scales
        correctly across the five levels checked here, whose predicted
        probabilities span 4.9e-5 to 0.82 — a fixed tolerance would be either
        vacuous at the top or a coin flip at the bottom. The wrong exponent
        (``gamma`` instead of ``gamma^2``, a factor of 4.4) misses by hundreds of
        standard errors.
        """
        jitter_displacement_m = JITTER_RAD * km_to_m(RANGE_KM)
        samples = 200_000
        offsets_m = np.hypot(
            rng.normal(0.0, jitter_displacement_m, samples),
            rng.normal(0.0, jitter_displacement_m, samples),
        )
        equivalent_m = float(
            equivalent_beam_radius_m(RANGE_KM, degradations=degradations, **_geometry())
        )
        drawn = np.exp(-2.0 * offsets_m**2 / equivalent_m**2)

        for level in (0.6, 0.8, 0.9, 0.95, 0.99):
            empirical = float(np.mean(drawn < level))
            predicted = float(
                pointing_outage_probability(
                    level,
                    range_km=RANGE_KM,
                    jitter_rad=JITTER_RAD,
                    degradations=degradations,
                    **_geometry(),
                )
            )
            standard_error = np.sqrt(predicted * (1.0 - predicted) / samples)
            assert abs(empirical - predicted) < 4.0 * standard_error

    def test_the_mean_of_the_draw_matches_the_closed_form(
        self, rng: np.random.Generator, degradations: DegradationLog
    ) -> None:
        gamma = float(
            beam_to_jitter_ratio(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            )
        )
        jitter_displacement_m = JITTER_RAD * km_to_m(RANGE_KM)
        offsets_m = np.hypot(
            rng.normal(0.0, jitter_displacement_m, 200_000),
            rng.normal(0.0, jitter_displacement_m, 200_000),
        )
        equivalent_m = float(
            equivalent_beam_radius_m(RANGE_KM, degradations=degradations, **_geometry())
        )
        drawn_mean = float(np.mean(np.exp(-2.0 * offsets_m**2 / equivalent_m**2)))
        closed_form = gamma**2 / (gamma**2 + 1.0)
        assert drawn_mean == pytest.approx(closed_form, rel=2e-3)

    def test_the_quantile_and_the_cdf_are_inverses(self, degradations: DegradationLog) -> None:
        """Asserted as a round trip, which is the cheapest way to catch a flipped exponent."""
        for probability in (1e-4, 0.01, 0.5, 0.999):
            transmittance = pointing_transmittance_quantile(
                probability,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
            recovered = pointing_outage_probability(
                transmittance,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
            assert float(recovered) == pytest.approx(probability, rel=1e-12)

    def test_the_median_sits_between_the_mean_and_the_deep_quantiles(
        self, degradations: DegradationLog
    ) -> None:
        """The skew that makes the mean the wrong summary, as an ordering.

        The distribution piles up against its ceiling at 1 and trails off
        towards 0, so it is skewed to the *left* and the mean sits **below** the
        median: 0.951 against 0.965, i.e. 0.218 dB of loss against 0.155 dB.
        That ordering is the useful part. The mean is already more pessimistic
        than the typical moment, and it is still five times more optimistic than
        the 1-in-1000 moment (1.545 dB) a QKD link has to survive — so "worse
        than typical" is not the same as "conservative", and only the quantile
        is.
        """
        mean = float(
            mean_pointing_transmittance(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
            )
        )
        median = float(
            pointing_transmittance_quantile(
                0.5,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        )
        deep = float(
            pointing_transmittance_quantile(
                1e-3,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        )
        assert deep < mean < median < 1.0
        assert float(transmittance_to_loss_db(mean)) == pytest.approx(0.218, abs=0.002)
        assert float(transmittance_to_loss_db(median)) == pytest.approx(0.155, abs=0.002)

    def test_more_jitter_is_monotonically_worse_everywhere(
        self, degradations: DegradationLog
    ) -> None:
        jitters = np.geomspace(0.2e-6, 10e-6, 25)
        means = [
            float(
                mean_pointing_transmittance(
                    RANGE_KM, jitter_rad=float(j), degradations=degradations, **_geometry()
                )
            )
            for j in jitters
        ]
        quantiles = [
            float(
                pointing_transmittance_quantile(
                    0.01,
                    range_km=RANGE_KM,
                    jitter_rad=float(j),
                    degradations=degradations,
                    **_geometry(),
                )
            )
            for j in jitters
        ]
        assert np.all(np.diff(means) < 0.0)
        assert np.all(np.diff(quantiles) < 0.0)

    def test_the_tail_is_steeper_than_the_mean(self, degradations: DegradationLog) -> None:
        """The design conclusion of the module, as a measured ratio.

        At the reference jitter the 1-in-100 loss is 4.7 times the mean loss;
        doubling the jitter takes the mean from 0.22 dB to 1.35 dB but the
        1-in-100 from 1.03 dB to 7.32 dB. The tail is what a QKD link is
        designed against, and it moves faster.
        """

        def losses(jitter_rad: float) -> tuple[float, float]:
            mean_db = float(
                transmittance_to_loss_db(
                    mean_pointing_transmittance(
                        RANGE_KM,
                        jitter_rad=jitter_rad,
                        degradations=degradations,
                        **_geometry(),
                    )
                )
            )
            tail_db = float(
                transmittance_to_loss_db(
                    pointing_transmittance_quantile(
                        0.01,
                        range_km=RANGE_KM,
                        jitter_rad=jitter_rad,
                        degradations=degradations,
                        **_geometry(),
                    )
                )
            )
            return mean_db, tail_db

        mean_db, tail_db = losses(JITTER_RAD)
        assert mean_db == pytest.approx(0.218, abs=0.002)
        assert tail_db == pytest.approx(1.030, abs=0.002)
        assert tail_db / mean_db == pytest.approx(4.7, rel=0.05)

        worse_mean_db, worse_tail_db = losses(2.0e-6)
        assert worse_mean_db == pytest.approx(1.35, abs=0.01)
        assert worse_tail_db == pytest.approx(7.32, abs=0.01)
        assert worse_tail_db - tail_db > worse_mean_db - mean_db

    def test_gamma_is_almost_constant_over_a_pass(self, degradations: DegradationLog) -> None:
        """Unlike every other channel term, and the reason it is worth saying.

        Both the beam radius and the jitter displacement grow with range, so
        they cancel. What is left is the aperture correction inside ``w_zeq``,
        which is why the variation is 0.5 % over a factor of four in range
        rather than exactly zero.
        """
        ranges_km = np.array([600.0, 1200.0, 2400.0])
        gammas = beam_to_jitter_ratio(
            ranges_km, jitter_rad=JITTER_RAD, degradations=degradations, **_geometry()
        )
        spread = float(np.max(gammas) / np.min(gammas) - 1.0)
        assert spread < 0.01

        geometric = geometric_transmittance(
            ranges_km,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=TRANSMIT_APERTURE_M,
            receive_aperture_m=RECEIVE_APERTURE_M,
        )
        assert float(np.max(geometric) / np.min(geometric)) > 3.0

    def test_the_equivalent_radius_is_always_wider_than_the_beam(
        self, degradations: DegradationLog
    ) -> None:
        """The aperture always helps, so the correction has a sign.

        ``w_zeq >= W`` for every geometry, because a telescope with a size keeps
        catching the near edge of the beam as the far edge walks off it. If the
        ``erf`` correction were inverted this would fail while every value
        stayed positive and plausible.
        """
        ranges_km = np.geomspace(100.0, 4000.0, 20)
        beam = beam_radius_m(
            ranges_km, wavelength_m=WAVELENGTH_M, transmit_aperture_m=TRANSMIT_APERTURE_M
        )
        for receiver_m in (0.1, 0.75, 2.3):
            equivalent = equivalent_beam_radius_m(
                ranges_km, degradations=degradations, **_geometry(receive_aperture_m=receiver_m)
            )
            assert np.all(equivalent >= beam)

    def test_shapes_are_preserved_over_the_time_axis(self, degradations: DegradationLog) -> None:
        """A pass is (n_samples,); a stack of passes is (n_satellites, n_samples)."""
        ranges_km = np.linspace(600.0, 2000.0, 12).reshape(3, 4)
        assert equivalent_beam_radius_m(
            ranges_km, degradations=degradations, **_geometry()
        ).shape == (3, 4)
        assert pointing_transmittance_quantile(
            0.01,
            range_km=ranges_km,
            jitter_rad=JITTER_RAD,
            degradations=degradations,
            **_geometry(),
        ).shape == (3, 4)
        assert pointing_transmittance(
            np.zeros((3, 4)) + JITTER_RAD,
            range_km=ranges_km,
            degradations=degradations,
            **_geometry(),
        ).shape == (3, 4)


# --------------------------------------------------------------------------- #
# The model saying when its published validity condition fails
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheOutOfRangeWarning:
    def test_nothing_is_recorded_for_a_geometry_inside_the_published_range(
        self, degradations: DegradationLog
    ) -> None:
        equivalent_beam_radius_m(RANGE_KM, degradations=degradations, **_geometry())
        assert len(degradations) == 0

    def test_the_reference_systems_largest_telescope_is_out_of_range(
        self, degradations: DegradationLog
    ) -> None:
        """The warning is not decorative: Ntanos et al.'s 2.3 m station trips it.

        At 600 km the beam radius is 3.95 m and the aperture radius 1.15 m, so
        ``W/a = 3.43`` against the published limit of 6. This is the
        configuration the paper reports its best link budget for, so a model
        that stayed silent here would be silent exactly where it matters.
        """
        equivalent_beam_radius_m(
            RANGE_KM, degradations=degradations, **_geometry(receive_aperture_m=2.3)
        )
        assert len(degradations) == 1
        entry = degradations.entries[0]
        assert entry.code == "pointing.gaussian-approximation-out-of-published-range"
        assert entry.severity is Severity.WARNING
        assert entry.where == "quoss.channel.pointing.equivalent_beam_radius_m"
        assert entry.details["beam_to_aperture_radius_ratio"] == pytest.approx(3.43, abs=0.01)
        assert entry.details["limit"] == GAUSSIAN_POINTING_BEAM_TO_RADIUS_LIMIT
        assert entry.details["receive_aperture_m"] == 2.3

    def test_the_warning_fires_on_the_worst_sample_of_a_pass(
        self, degradations: DegradationLog
    ) -> None:
        """Short range is the bad case, because the beam has had less room to grow.

        A 1.3 m telescope is inside the range at 600 km and outside it at
        400 km, and it is the *minimum* ratio over the pass that decides — one
        entry for the array, keyed to the worst sample.
        """
        ranges_km = np.array([400.0, 600.0, 1200.0])
        equivalent_beam_radius_m(
            ranges_km, degradations=degradations, **_geometry(receive_aperture_m=1.3)
        )
        assert len(degradations) == 1
        assert degradations.entries[0].details["beam_to_aperture_radius_ratio"] == pytest.approx(
            4.05, abs=0.02
        )

    def test_the_warning_is_a_warning_and_not_a_degradation(
        self, degradations: DegradationLog
    ) -> None:
        """Nothing was substituted, so ``has_degraded`` stays false.

        The caller gets equation (9), evaluated outside the range its authors
        vouch for. That is what WARNING is for; DEGRADED would mean a different
        model was used instead, and none was.
        """
        equivalent_beam_radius_m(
            RANGE_KM, degradations=degradations, **_geometry(receive_aperture_m=2.3)
        )
        assert not degradations.has_degraded

    def test_every_public_function_propagates_the_warning(
        self, degradations: DegradationLog
    ) -> None:
        """No entry point can compute a pointing loss without the guard firing.

        All five reach ``equivalent_beam_radius_m``, so the condition cannot be
        bypassed by picking a different function — which is the only reason it is
        safe for the guard to live in one place.
        """
        out_of_range = _geometry(receive_aperture_m=2.3)
        calls = [
            lambda: equivalent_beam_radius_m(RANGE_KM, degradations=degradations, **out_of_range),
            lambda: pointing_transmittance(
                JITTER_RAD, range_km=RANGE_KM, degradations=degradations, **out_of_range
            ),
            lambda: beam_to_jitter_ratio(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **out_of_range
            ),
            lambda: pointing_transmittance_quantile(
                0.01,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **out_of_range,
            ),
            lambda: pointing_outage_probability(
                0.9,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **out_of_range,
            ),
            lambda: mean_pointing_transmittance(
                RANGE_KM, jitter_rad=JITTER_RAD, degradations=degradations, **out_of_range
            ),
        ]
        for index, call in enumerate(calls, start=1):
            call()
            assert len(degradations) == index


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestALensFarWiderThanTheBeam:
    """The bench geometry: a millimetre beam into a lens centimetres across.

    Equation (9) divides by ``exp(-v^2)``, and past ``v^2 = 708`` that is a
    division by an underflowed zero. Before `_EQUIVALENT_RADIUS_EXPONENT_LIMIT`
    a 2 mm transmitter two metres from a 20 cm lens raised
    ``RuntimeWarning: divide by zero`` — which this suite turns into an error —
    and a 1 cm one returned ``gamma = 7.9e137`` with no complaint beyond the
    range warning. The law's own limit is an infinite equivalent radius: a beam
    that small never leaves a lens that large, so there is no pointing fade.
    """

    @staticmethod
    def _ratio(transmit_m: float, receive_m: float, degradations: DegradationLog) -> float:
        return float(
            beam_to_jitter_ratio(
                0.002,
                jitter_rad=5e-6,
                wavelength_m=1.55e-06,
                transmit_aperture_m=transmit_m,
                receive_aperture_m=receive_m,
                degradations=degradations,
            )
        )

    def test_past_the_limit_the_radius_is_infinite_and_the_warning_says_so(
        self, degradations: DegradationLog
    ) -> None:
        assert self._ratio(0.002, 0.2, degradations) == np.inf
        (entry,) = degradations.entries
        assert entry.code == "pointing.gaussian-approximation-out-of-published-range"
        assert entry.details["equivalent_radius_is_infinite"] is True
        assert "+inf" in entry.message

    def test_below_the_limit_it_is_finite_and_the_flag_is_false(
        self, degradations: DegradationLog
    ) -> None:
        assert np.isfinite(self._ratio(0.01, 0.2, degradations))
        assert degradations.entries[0].details["equivalent_radius_is_infinite"] is False

    def test_the_radius_grows_monotonically_into_the_limit(self) -> None:
        """No jump at the threshold other than the one to infinity, which is the limit itself."""
        log = DegradationLog()
        receivers = np.linspace(0.01, 0.2, 40)
        radii = np.array(
            [
                float(
                    equivalent_beam_radius_m(
                        0.002,
                        wavelength_m=1.55e-06,
                        transmit_aperture_m=0.002,
                        receive_aperture_m=float(receive),
                        degradations=log,
                    )
                )
                for receive in receivers
            ]
        )
        finite = np.isfinite(radii)
        first_infinite = int(np.argmin(finite))
        assert np.isfinite(radii[0]) and np.isinf(radii[-1])
        assert np.all(finite[:first_infinite]) and not np.any(finite[first_infinite:])
        assert np.all(np.diff(radii[:first_infinite]) >= 0.0)


class TestRejectsBadInput:
    def test_a_non_positive_jitter_is_rejected(self, degradations: DegradationLog) -> None:
        """Zero jitter is rejected rather than treated as perfect pointing.

        The exponent ``gamma^2`` diverges there, and the answer a caller wants
        in that case is ``beam.geometric_transmittance``, which the message says.
        """
        with pytest.raises(DomainError, match="jitter_rad"):
            beam_to_jitter_ratio(RANGE_KM, jitter_rad=0.0, degradations=degradations, **_geometry())
        with pytest.raises(DomainError, match="geometric_transmittance"):
            mean_pointing_transmittance(
                RANGE_KM, jitter_rad=-1e-6, degradations=degradations, **_geometry()
            )
        with pytest.raises(DomainError, match="radians"):
            pointing_transmittance_quantile(
                0.01,
                range_km=RANGE_KM,
                jitter_rad=float("nan"),
                degradations=degradations,
                **_geometry(),
            )

    def test_an_outage_probability_outside_the_unit_interval_is_rejected(
        self, degradations: DegradationLog
    ) -> None:
        """Including the percentage mistake, which is the likely one."""
        with pytest.raises(DomainError, match=r"\(0, 1\]"):
            pointing_transmittance_quantile(
                0.0,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        with pytest.raises(DomainError, match=r"1 % is 0\.01"):
            pointing_transmittance_quantile(
                1.0,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            ) if False else pointing_transmittance_quantile(
                5.0,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        with pytest.raises(DomainError, match=r"\(0, 1\]"):
            pointing_transmittance_quantile(
                float("nan"),
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )

    def test_a_negative_offset_is_rejected(self, degradations: DegradationLog) -> None:
        """A radial distance has no sign, so a negative one means a component was passed."""
        with pytest.raises(DomainError, match="non-negative"):
            pointing_transmittance(
                -1e-6, range_km=RANGE_KM, degradations=degradations, **_geometry()
            )
        with pytest.raises(DomainError, match="non-finite"):
            pointing_transmittance(
                np.array([1e-6, np.inf]),
                range_km=RANGE_KM,
                degradations=degradations,
                **_geometry(),
            )

    def test_a_transmittance_outside_zero_and_one_is_rejected(
        self, degradations: DegradationLog
    ) -> None:
        """Above 1 is the interesting case: it means an absolute coupling was passed."""
        with pytest.raises(DomainError, match=r"\[0, 1\]"):
            pointing_outage_probability(
                1.5,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        with pytest.raises(DomainError, match="geometric_transmittance"):
            pointing_outage_probability(
                -0.1,
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )
        with pytest.raises(DomainError, match="non-finite"):
            pointing_outage_probability(
                np.array([0.5, np.nan]),
                range_km=RANGE_KM,
                jitter_rad=JITTER_RAD,
                degradations=degradations,
                **_geometry(),
            )

    def test_the_range_and_aperture_guards_of_beam_are_not_bypassed(
        self, degradations: DegradationLog
    ) -> None:
        with pytest.raises(DomainError, match="range_km must be strictly positive"):
            equivalent_beam_radius_m(0.0, degradations=degradations, **_geometry())
        with pytest.raises(DomainError, match="receive_aperture_m"):
            equivalent_beam_radius_m(
                RANGE_KM, degradations=degradations, **_geometry(receive_aperture_m=0.0)
            )
        with pytest.raises(DomainError, match="transmit_aperture_m"):
            equivalent_beam_radius_m(
                RANGE_KM, degradations=degradations, **_geometry(transmit_aperture_m=-1.0)
            )
        with pytest.raises(DomainError, match="wavelength_m"):
            equivalent_beam_radius_m(
                RANGE_KM, degradations=degradations, **_geometry(wavelength_m=0.0)
            )

    def test_the_aperture_message_says_it_must_match_the_beam_module(
        self, degradations: DegradationLog
    ) -> None:
        """Two different receiving apertures in the two modules is a silent error."""
        with pytest.raises(DomainError, match="the two must agree"):
            equivalent_beam_radius_m(
                RANGE_KM, degradations=degradations, **_geometry(receive_aperture_m=0.0)
            )


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import pointing

        assert pointing.__all__ == sorted(pointing.__all__)
        for name in pointing.__all__:
            assert hasattr(pointing, name)

    def test_the_module_documents_both_sources(self) -> None:
        from quoss.channel import pointing

        assert pointing.__doc__ is not None
        assert "Farid" in pointing.__doc__
        assert "Ntanos" in pointing.__doc__

    def test_the_module_declares_what_it_leaves_out(self) -> None:
        """Four omissions, each named with where it goes instead."""
        from quoss.channel import pointing

        assert pointing.__doc__ is not None
        for absent in ("boresight", "correlated_fading", "monte_carlo", "17.5 dB"):
            assert absent in pointing.__doc__

    def test_there_is_no_random_generator_in_this_module(self) -> None:
        """The quantile function is the sampler, so the RNG stays in one place.

        ``core/rng.py`` exists so that every stochastic result traces to one
        registered seed. A module that grew its own generator would be a second
        place for randomness to enter, which is what that rule forbids.

        Checked on the *imports* rather than on the source text, because the
        module docstring names ``RandomSource`` on purpose — to say where the
        randomness belongs — and a grep for the word would flag exactly the
        sentence that documents the rule.
        """
        import ast
        import inspect

        from quoss.channel import pointing

        tree = ast.parse(inspect.getsource(pointing))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any("rng" in name or "random" in name for name in imported)

        # And the sampler this module deliberately does not own is reachable
        # from the place that should own it, which is what makes the omission a
        # decision rather than a hole.
        assert hasattr(RandomSource, "from_seed")
