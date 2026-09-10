"""Tests for `quoss.channel.atmosphere`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestPublishedItuValues`` — **V2**. The three numbers ITU-R P.1621-2 prints
  about its own model: that a 2.3 m/s ground wind gives 21 m/s r.m.s., that the
  top integration layer is about 1 km thick, and that the layers span about
  20 km. These are the only absolute-correctness anchors this module has.
- ``TestProfileShapeInvariants`` — **V1**. That each of the three terms of
  equation (6) dominates where the recommendation says it does, including the
  10 km bump it describes in words.
- ``TestRefractionInvariants`` — **V1**. Refraction against its own analytic
  small-angle law, which attributes the residual rather than just bounding it.
- ``TestIntegralInvariants`` — **V1**. Monotonicity and the quadrature.
- ``TestRejectsBadInput`` — every guard, from both sides where there are two.
- ``TestModuleSurface`` — ``__all__`` and the shape of the API.

There is no V3 here yet: no independent implementation of the ITU-R profile was
located. That gap is declared in ``tests/golden/README.md`` rather than papered
over with a comparison against our own output.
"""

from __future__ import annotations

import numpy as np
import pytest

from quoss.channel.atmosphere import (
    ITU_GROUND_CN2_M23,
    ITU_GROUND_WIND_SPEED_M_S,
    ITU_LAYER_COUNT,
    ITU_TURBULENCE_TOP_HEIGHT_M,
    air_refractive_index,
    bufton_rms_wind_speed_m_s,
    hufnagel_valley_cn2_m23,
    integrated_cn2_m13,
    itu_layer_heights_m,
    itu_layer_thicknesses_m,
    refracted_elevation_rad,
)
from quoss.core.errors import DomainError
from quoss.core.units import deg_to_rad

# --------------------------------------------------------------------------- #
# The published values, transcribed with their citation
# --------------------------------------------------------------------------- #

ITU_P1621_2_RMS_WIND_FOR_UNKNOWN_GROUND_WIND_M_S = 21.0
"""ITU-R P.1621-2 §5.1.1, step 1: "When the ground wind speed is unknown, a
value of vg = 2.3 m/s may be used as an approximation resulting in
vrms = 21 m/s"."""

ITU_P1621_2_TOP_LAYER_THICKNESS_M = 1000.0
"""ITU-R P.1621-2 §5.1.1, after equation (7): "noting that h139 ~ 1 000 m"."""

ITU_P1621_2_LAYER_SPAN_M = 20_000.0
"""ITU-R P.1621-2 §5.1.1, after equation (7): "sum of hi ~ 20 km"."""

TELECOM_WAVELENGTH_M = 1.55e-6


@pytest.mark.physics
class TestPublishedItuValues:
    def test_the_recommendations_own_wind_example(self) -> None:
        """ITU-R P.1621-2 prints "vrms = 21 m/s" for vg = 2.3 m/s.

        The bound is half a unit in the last printed digit: 21 is printed to
        two significant figures, so the recommendation licenses +-0.5 m/s and
        nothing tighter. Measured: 21.018.
        """
        measured = bufton_rms_wind_speed_m_s(ITU_GROUND_WIND_SPEED_M_S)
        assert measured == pytest.approx(ITU_P1621_2_RMS_WIND_FOR_UNKNOWN_GROUND_WIND_M_S, abs=0.5)

    def test_the_published_wind_value_satisfies_the_published_equation(self) -> None:
        """Independent of our implementation: put 21 m/s back into equation (5).

        If the transcription of the coefficients were wrong, this would catch it
        without consulting the code under test at all. Same pattern as
        ``test_kepler.py::test_the_published_answer_satisfies_keplers_equation``.
        """
        ground = ITU_GROUND_WIND_SPEED_M_S
        from_equation = np.sqrt(ground**2 + 33.11 * ground + 360.31)
        assert from_equation == pytest.approx(
            ITU_P1621_2_RMS_WIND_FOR_UNKNOWN_GROUND_WIND_M_S, abs=0.5
        )

    def test_the_layer_grid_reproduces_the_thickness_the_recommendation_prints(self) -> None:
        """Match the printed h139 of about 1 000 m, measured at 992.27.

        That is 0.8 % below the printed value. The bound is 1 %, from the tilde:
        the recommendation writes the figure as approximate, and 1 000 m is
        plainly a rounded statement of exp(6.9).
        """
        thicknesses = itu_layer_thicknesses_m()
        assert thicknesses.shape == (ITU_LAYER_COUNT,)
        assert thicknesses[-1] == pytest.approx(ITU_P1621_2_TOP_LAYER_THICKNESS_M, rel=0.01)

    def test_the_layer_grid_reproduces_the_span_the_recommendation_prints(self) -> None:
        """Match the printed layer span of about 20 km, measured at 20.326 km.

        That is 1.6 % above the printed value, and the bound is 2 %, again from
        the tilde the recommendation writes. This is the check that catches the
        off-by-one that would matter: a grid run from i = 0 to 138 instead of
        1 to 139 spans 19.3 km, which fails at 2 % but would pass at 5 %.
        """
        total = float(itu_layer_thicknesses_m().sum())
        assert total == pytest.approx(ITU_P1621_2_LAYER_SPAN_M, rel=0.02)

    def test_the_first_layer_is_the_one_millimetre_of_a_kilometre_stated(self) -> None:
        """Match the 0.001 km the recommendation gives for the lowest layer — exactly 1 m."""
        assert float(itu_layer_thicknesses_m()[0]) == pytest.approx(1.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# V1 — the shape of the profile, against what the recommendation says in words
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestProfileShapeInvariants:
    def test_at_ground_level_the_profile_is_exactly_the_two_non_wind_terms(self) -> None:
        """h = 0 kills the ``h^10`` factor exactly, leaving C_0 + 2.7e-16.

        Exact equality is legitimate here: every exponential is exp(0) = 1 and
        the wind term is multiplied by a literal zero, so no rounding enters.
        """
        value = float(hufnagel_valley_cn2_m23(0.0, ground_cn2_m23=ITU_GROUND_CN2_M23))
        assert value == ITU_GROUND_CN2_M23 + 2.7e-16

    def test_wind_does_not_move_the_ground_but_dominates_at_ten_kilometres(self) -> None:
        """The recommendation: wind "has the greatest impact at heights above about 1 km".

        Two assertions, because one alone would not separate "wind matters up
        high" from "wind matters everywhere".
        """
        calm = hufnagel_valley_cn2_m23(np.array([0.0, 10_000.0]), rms_wind_speed_m_s=10.0)
        windy = hufnagel_valley_cn2_m23(np.array([0.0, 10_000.0]), rms_wind_speed_m_s=30.0)
        assert float(windy[0]) == float(calm[0])
        assert float(windy[1]) / float(calm[1]) > 5.0

    def test_ground_turbulence_does_not_reach_ten_kilometres(self) -> None:
        """The mirror of the previous test: "Cn2 is most dependent on C0 at low heights".

        The surface term decays with a 100 m scale height, so by 10 km it has
        been suppressed by exp(-100) and cannot possibly contribute.
        """
        quiet = hufnagel_valley_cn2_m23(10_000.0, ground_cn2_m23=1.7e-15)
        noisy = hufnagel_valley_cn2_m23(10_000.0, ground_cn2_m23=1.7e-13)
        assert float(noisy) == pytest.approx(float(quiet), rel=1e-12)

    def test_the_high_altitude_term_peaks_at_exactly_ten_kilometres(self) -> None:
        """The location of the bump is analytic, not fitted, so assert the exact value.

        Differentiating ``h^10 exp(-h/1000)`` gives
        ``(10 h^9 - h^10 / 1000) exp(-h/1000)``, which vanishes at
        ``h = 10 * 1000 = 10 000`` m. That is where the "5/7" model puts the jet
        stream, and it falls straight out of the two constants in equation (6) —
        so a mistyped exponent or a mistyped scale height moves this peak and
        this test says by how much.

        The 1 m sampling below is what sets the bound: the peak is located to
        the grid, so agreeing to within one grid step is the whole claim.
        """
        heights = np.arange(1_000.0, 20_000.0, 1.0)
        wind_term = hufnagel_valley_cn2_m23(
            heights, rms_wind_speed_m_s=21.0, ground_cn2_m23=0.0
        ) - 2.7e-16 * np.exp(-heights / 1500.0)
        peak = float(heights[int(np.argmax(wind_term))])
        assert peak == pytest.approx(10_000.0, abs=1.0)

    def test_the_full_profile_has_the_bump_near_ten_kilometres_the_text_describes(self) -> None:
        """Reproduce the rise §5.1.1 describes at around 10 km above the ground.

        The recommendation puts it in words: "At around 10 km above the ground,
        Cn2 increases slightly but falls off steeply."

        This is the one qualitative claim in §5.1.1 that a monotonic profile
        would silently violate, and a dropped ``h^10`` term is exactly what
        would make the profile monotonic. Asserting that the rise exists, and
        where it turns over, is what catches that.

        The full profile turns over at 9 850 m rather than the 10 000 m of the
        wind term alone, because the background term is still decaying and drags
        the sum's maximum slightly downhill. The window below is set to hold
        that difference, not to accommodate an unknown.
        """
        heights = np.linspace(5_000.0, 20_000.0, 601)
        profile = hufnagel_valley_cn2_m23(heights)
        assert np.any(np.diff(profile) > 0.0), "no local rise: the high-altitude term is missing"
        turnover = float(heights[int(np.argmax(np.where(heights > 6_000.0, profile, 0.0)))])
        assert 9_000.0 < turnover < 10_000.0

    def test_the_profile_falls_by_four_orders_over_the_first_twenty_kilometres(self) -> None:
        ground = float(hufnagel_valley_cn2_m23(0.0))
        top = float(hufnagel_valley_cn2_m23(ITU_TURBULENCE_TOP_HEIGHT_M))
        assert 1e4 < ground / top < 1e5

    def test_the_profile_is_vectorised_and_shape_preserving(self) -> None:
        """A scalar in gives a 0-d array; an (n, m) grid keeps its shape.

        The channel is vectorised over the time axis from the first signature,
        and a profile that quietly flattened its input would force every caller
        to reshape.
        """
        grid = np.linspace(0.0, 20_000.0, 12).reshape(3, 4)
        assert hufnagel_valley_cn2_m23(grid).shape == (3, 4)
        assert hufnagel_valley_cn2_m23(np.array([1.0])).shape == (1,)


# --------------------------------------------------------------------------- #
# V1 — refraction, attributed rather than bounded
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestRefractionInvariants:
    def test_the_bend_is_first_order_in_the_refractive_excess(self) -> None:
        """Attribution, not a bound — the pattern of ``test_the_residual_is_proportional_to_j2``.

        For ``n = 1 + eps``, expanding ``arccos(cos(el) / (1 + eps))`` gives a
        bend of ``eps * cot(el)`` plus a term of order ``eps^2``. A plain
        tolerance cannot separate the two hypotheses that matter: that the
        formula is right and merely truncated, or that a coefficient is wrong.
        Scaling ``eps`` does separate them.

        If the formula is right, the *relative* residual against ``eps cot(el)``
        falls linearly with ``eps``; if a coefficient were wrong, the residual
        would be first order in ``eps`` inside a first-order quantity and would
        not move at all.

        Better still, the constant of proportionality is derivable, so this does
        not just assert linearity — it names the slope. Carrying both expansions
        to second order, ``1/(1 + eps) = 1 - eps + eps^2`` and
        ``arccos(cos(el) - d) = el + d/sin(el) + (d^2/2) cos(el)/sin^3(el)``,
        the relative residual works out to ``eps * (1 + cot^2(el)/2)``. At
        20 degrees that is 4.7743, and the four measurements below run
        4.7639 to 4.7730, approaching it from below as ``eps`` shrinks. The 1 %
        bound is set by the third-order term this stops at.
        """
        elevation = deg_to_rad(20.0)
        base_excess = air_refractive_index(TELECOM_WAVELENGTH_M) - 1.0
        cotangent = 1.0 / np.tan(elevation)
        analytic_slope = 1.0 + 0.5 * cotangent**2
        for factor in (1.0, 0.5, 0.25, 0.125):
            excess = base_excess * factor
            measured = float(refracted_elevation_rad(elevation, 1.0 + excess)) - float(elevation)
            predicted = excess * cotangent
            slope = abs(measured / predicted - 1.0) / excess
            assert slope == pytest.approx(analytic_slope, rel=0.01)

    def test_the_bend_matches_the_small_angle_law_where_the_expansion_is_good(self) -> None:
        """A bound, with the bound derived from the term the expansion drops.

        The neglected term is relatively ``(eps/2) cot^2(el)``. At 40 degrees
        and above with eps = 2.7e-4 that is below 2e-4, so 1e-3 is loose enough
        to be a statement about truncation and tight enough that a dropped
        factor of ``n`` — worth 2.7e-4 relative on the elevation itself, which
        is 300 times the bend — could not hide inside it.
        """
        index = air_refractive_index(TELECOM_WAVELENGTH_M)
        excess = index - 1.0
        elevation = deg_to_rad(np.array([40.0, 60.0, 80.0]))
        measured = refracted_elevation_rad(elevation, index) - elevation
        predicted = excess / np.tan(elevation)
        assert np.allclose(measured, predicted, rtol=1e-3)

    def test_the_apparent_elevation_is_never_below_the_true_one(self) -> None:
        index = air_refractive_index(TELECOM_WAVELENGTH_M)
        elevation = deg_to_rad(np.linspace(0.0, 90.0, 91))
        assert np.all(refracted_elevation_rad(elevation, index) >= elevation)

    def test_the_bend_grows_monotonically_towards_the_horizon(self) -> None:
        index = air_refractive_index(TELECOM_WAVELENGTH_M)
        elevation = deg_to_rad(np.linspace(5.0, 90.0, 86))
        bend = refracted_elevation_rad(elevation, index) - elevation
        assert np.all(np.diff(bend) < 0.0)

    def test_at_the_zenith_the_correction_is_exactly_zero(self) -> None:
        """Not approximately: cos(pi/2) is 0, so the ratio is 0 whatever n is."""
        index = air_refractive_index(TELECOM_WAVELENGTH_M)
        zenith = 0.5 * np.pi
        assert float(refracted_elevation_rad(zenith, index)) == zenith

    def test_an_index_of_exactly_one_bends_nothing(self) -> None:
        """The vacuum limit. A model that could not reproduce it would be wrong."""
        elevation = deg_to_rad(np.linspace(1.0, 89.0, 89))
        assert np.allclose(refracted_elevation_rad(elevation, 1.0), elevation, atol=1e-15)

    def test_shorter_wavelengths_bend_more(self) -> None:
        """Dispersion: this is why the function takes a wavelength at all.

        Blue light sees a denser atmosphere than infrared, so a model that
        ignored the wavelength would be indistinguishable from this one except
        through this comparison.
        """
        blue = air_refractive_index(450e-9)
        infrared = air_refractive_index(1.55e-6)
        assert blue > infrared

    def test_thinner_air_bends_less(self) -> None:
        sea_level = air_refractive_index(TELECOM_WAVELENGTH_M, pressure_hpa=1013.25)
        altitude = air_refractive_index(TELECOM_WAVELENGTH_M, pressure_hpa=500.0)
        assert 1.0 < altitude < sea_level

    def test_the_reference_conditions_inconsistency_is_the_size_documented(self) -> None:
        """Equation (3) is not a no-op at equation (2)'s own reference point.

        The module docstring records this as 140 ppm and justifies applying
        equation (3) regardless. If a future edit "fixed" it by normalising the
        scale factor, this test would fail and force the change to be argued
        rather than slipped in.
        """
        wavelength_um = TELECOM_WAVELENGTH_M * 1.0e6
        inverse_square = 1.0 / (wavelength_um * wavelength_um)
        equation_two_only = 1.0 + 1.0e-8 * (
            6432.8 + 2_949_810.0 / (146.0 - inverse_square) + 25_540.0 / (41.0 - inverse_square)
        )
        with_equation_three = air_refractive_index(TELECOM_WAVELENGTH_M)
        ratio = (with_equation_three - 1.0) / (equation_two_only - 1.0)
        assert ratio == pytest.approx(1.000140519, rel=1e-6)


# --------------------------------------------------------------------------- #
# V1 — the integral
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestIntegralInvariants:
    def test_layer_midpoints_are_strictly_increasing(self) -> None:
        heights = itu_layer_heights_m()
        assert heights.shape == (ITU_LAYER_COUNT,)
        assert np.all(np.diff(heights) > 0.0)

    def test_midpoints_sit_inside_their_own_layers(self) -> None:
        """Each midpoint is half a thickness below its layer's upper edge."""
        thicknesses = itu_layer_thicknesses_m()
        upper = np.cumsum(thicknesses)
        lower = upper - thicknesses
        heights = itu_layer_heights_m()
        assert np.all(heights > lower)
        assert np.all(heights < upper)

    def test_the_integral_never_rises_with_station_height(self) -> None:
        """Every excluded layer had a positive integrand, so the sum can only fall.

        Non-increasing rather than strictly decreasing, and the difference is a
        real property worth pinning: the grid is 139 discrete layers, and near
        the top they are a kilometre thick. Two station heights inside the same
        layer exclude the same layers and give a bit-for-bit identical integral.
        Asserting strict monotonicity here would be asserting a resolution the
        model does not have.
        """
        stations = np.linspace(0.0, 15_000.0, 40)
        totals = np.array([integrated_cn2_m13(station_height_m=float(h)) for h in stations])
        assert np.all(np.diff(totals) <= 0.0)
        assert totals[-1] < totals[0]

    def test_crossing_a_layer_boundary_does_change_the_integral(self) -> None:
        """The companion to the test above: the steps exist, they are just steps.

        Without this, a function that ignored ``station_height_m`` entirely
        would pass the non-increasing test.
        """
        heights = itu_layer_heights_m()
        below = float(heights[100]) - 1.0
        above = float(heights[100]) + 1.0
        assert integrated_cn2_m13(station_height_m=above) < integrated_cn2_m13(
            station_height_m=below
        )

    def test_the_integral_equals_a_direct_midpoint_sum(self) -> None:
        """The quadrature is the one the docstring claims, computed independently here.

        Exact equality, because both routes perform the same multiplication and
        sum in the same order; this pins the rule rather than measuring an error.
        """
        heights = itu_layer_heights_m()
        thicknesses = itu_layer_thicknesses_m()
        expected = float(np.sum(hufnagel_valley_cn2_m23(heights) * thicknesses))
        assert integrated_cn2_m13() == expected

    def test_scaling_the_ground_turbulence_moves_the_integral_by_the_surface_term_only(
        self,
    ) -> None:
        """Attribution, not a bound.

        The surface term integrates to C_0 * 100 m analytically (a decaying
        exponential with a 100 m scale height, over a path that starts at the
        ground). So doubling C_0 must raise the integral by exactly 1.7e-14 *
        100, to within the quadrature error of a grid whose first layer is 1 m.
        """
        base = integrated_cn2_m13(ground_cn2_m23=ITU_GROUND_CN2_M23)
        doubled = integrated_cn2_m13(ground_cn2_m23=2.0 * ITU_GROUND_CN2_M23)
        assert doubled - base == pytest.approx(ITU_GROUND_CN2_M23 * 100.0, rel=1e-3)

    def test_a_station_above_the_boundary_layer_sees_far_less_turbulence(self) -> None:
        sea_level = integrated_cn2_m13(station_height_m=0.0)
        mountain = integrated_cn2_m13(station_height_m=2500.0)
        assert sea_level / mountain > 5.0


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestRejectsBadInput:
    def test_negative_ground_wind_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            bufton_rms_wind_speed_m_s(-1.0)

    def test_non_finite_ground_wind_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="finite"):
            bufton_rms_wind_speed_m_s(float("nan"))

    def test_a_height_below_ground_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="cannot be negative"):
            hufnagel_valley_cn2_m23(-1.0)

    def test_the_kilometres_for_metres_mistake_is_caught(self) -> None:
        """Passing 700 km as if it were metres would be a satellite altitude.

        The guard exists because heights here are metres while every altitude
        arriving from ``quoss.orbits`` is kilometres, and the wrong one produces
        a plausible tiny number rather than a failure.
        """
        with pytest.raises(DomainError, match="Karman"):
            hufnagel_valley_cn2_m23(700_000.0)

    def test_non_finite_height_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            hufnagel_valley_cn2_m23(np.array([0.0, np.inf]))

    def test_negative_wind_and_ground_turbulence_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="rms_wind_speed_m_s"):
            hufnagel_valley_cn2_m23(0.0, rms_wind_speed_m_s=-1.0)
        with pytest.raises(DomainError, match="ground_cn2_m23"):
            hufnagel_valley_cn2_m23(0.0, ground_cn2_m23=-1.0)

    def test_a_station_above_the_atmosphere_leaves_nothing_to_integrate(self) -> None:
        with pytest.raises(DomainError, match="top of the turbulent atmosphere"):
            integrated_cn2_m13(station_height_m=ITU_TURBULENCE_TOP_HEIGHT_M)

    def test_a_negative_or_non_finite_station_height_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            integrated_cn2_m13(station_height_m=-1.0)
        with pytest.raises(DomainError, match="finite"):
            integrated_cn2_m13(station_height_m=float("nan"))

    def test_a_non_positive_wavelength_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="wavelength_m"):
            air_refractive_index(0.0)
        with pytest.raises(DomainError, match="wavelength_m"):
            air_refractive_index(-1.55e-6)

    def test_a_non_positive_pressure_and_non_finite_temperature_are_rejected(self) -> None:
        with pytest.raises(DomainError, match="pressure_hpa"):
            air_refractive_index(TELECOM_WAVELENGTH_M, pressure_hpa=0.0)
        with pytest.raises(DomainError, match="temperature_c"):
            air_refractive_index(TELECOM_WAVELENGTH_M, temperature_c=float("inf"))

    def test_degrees_passed_as_radians_are_caught(self) -> None:
        """10 degrees written as 10.0 is 573 degrees, far outside [0, pi/2]."""
        with pytest.raises(DomainError, match="radians, not degrees"):
            refracted_elevation_rad(10.0, 1.0002)

    def test_a_non_finite_elevation_is_rejected(self) -> None:
        """Checked before the range test, so a NaN cannot slip through a comparison.

        NaN compares false against everything, so ``elevation < 0`` would be
        false for it and the range guard alone would wave it through.
        """
        with pytest.raises(DomainError, match="non-finite"):
            refracted_elevation_rad(np.array([deg_to_rad(30.0), np.nan]), 1.0002)

    def test_an_elevation_below_the_horizon_is_rejected(self) -> None:
        with pytest.raises(DomainError, match=r"\[0, pi/2\]"):
            refracted_elevation_rad(deg_to_rad(-5.0), 1.0002)

    def test_a_refractive_index_below_one_is_rejected(self) -> None:
        """Below 1 the ray would bend the other way, which air does not do."""
        with pytest.raises(DomainError, match="at least 1"):
            refracted_elevation_rad(deg_to_rad(45.0), 0.9)


# --------------------------------------------------------------------------- #
# The module surface
# --------------------------------------------------------------------------- #


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import atmosphere

        assert atmosphere.__all__ == sorted(atmosphere.__all__)
        for name in atmosphere.__all__:
            assert hasattr(atmosphere, name)

    def test_the_module_documents_its_source(self) -> None:
        """ADR 0009: a citation is a document somebody opened.

        The module docstring must name the recommendation it transcribes, so
        that a reader can check the formulas without going through git history.
        """
        from quoss.channel import atmosphere

        assert atmosphere.__doc__ is not None
        assert "P.1621-2" in atmosphere.__doc__

    def test_the_wind_helper_takes_no_profile_argument(self) -> None:
        """The Bufton model summarises a whole wind profile into one number.

        Asserting the shape of the signature is what stops a future refactor
        from quietly accepting a per-layer wind here, which would be a different
        model wearing this one's name — the same guard
        ``test_perturbations.py`` puts on ``secular_rates_j2`` and J3.
        """
        import inspect

        parameters = inspect.signature(bufton_rms_wind_speed_m_s).parameters
        assert list(parameters) == ["ground_wind_speed_m_s"]
