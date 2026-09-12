"""Tests for `quoss.channel.turbulence`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestPublishedItuTable2`` — **V2**, and the strongest anchor the channel has
  so far: the eight log-irradiance variances ITU-R P.1622 Table 2 prints, at
  four wavelengths and two wind speeds, under conditions the recommendation
  fully specifies. Reproduced to the printed precision.
- ``TestPublishedClosedFormCoefficients`` — **V2**. Each quantity is printed
  twice by its recommendation, once as an integral with a wavenumber and once as
  a closed form with a numeric coefficient. Recomputing one from the other is
  what catches a mistyped digit.
- ``TestApertureAveragingInvariants`` — **V1**. Including the Fresnel-scale
  check that catches the metres-for-micrometres bug this module was written
  with.
- ``TestScalingInvariants`` — **V1**. The exponents, checked by scaling rather
  than by value.
- ``TestTheWeakFluctuationWarning`` — that the model says when it is out of
  range, from both sides.
- ``TestRejectsBadInput`` / ``TestModuleSurface``.

No V3: no independent implementation of these recommendations was located. The
gap is declared in ``tests/golden/README.md``.
"""

from __future__ import annotations

import numpy as np
import pytest

from quoss.channel.turbulence import (
    NEPER_SQ_TO_DB_SQ,
    WEAK_FLUCTUATION_VARIANCE_LIMIT,
    aperture_averaging_factor,
    cn2_path_moment,
    downlink_log_irradiance_variance,
    fried_parameter_m,
    isoplanatic_angle_rad,
    log_irradiance_variance,
    turbulence_scale_height_m,
    uplink_log_irradiance_variance,
)
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.units import deg_to_rad

# --------------------------------------------------------------------------- #
# The published table, transcribed with its citation
# --------------------------------------------------------------------------- #

ITU_P1622_TABLE_2_ELEVATION_DEG = 75.0
ITU_P1622_TABLE_2_STATION_HEIGHT_M = 5.5
ITU_P1622_TABLE_2 = {
    21.0: {0.532: 0.23, 0.850: 0.13, 1.064: 0.10, 1.55: 0.07},
    30.0: {0.532: 0.36, 0.850: 0.21, 1.064: 0.16, 1.55: 0.10},
}
"""ITU-R P.1622 Table 2, "Example scintillation statistics for C0 = 1.7e-14 m-2/3".

Keyed by r.m.s. wind speed (m/s), then by wavelength (micrometres), giving
``sigma^2_lnN`` in Np^2. The recommendation states every condition needed to
reproduce them: the Cn2 profile of ITU-R P.1621 §5.1.1, "an elevation angle of
75 degrees, earth station antenna is 5.5 m above the ground, and for r.m.s. wind
speed along the vertical path, vrms, of 21 m/s and 30 m/s", with "the aperture
size less than the atmospheric coherence length, r0" — which is why these are
point-aperture values with no aperture averaging applied.
"""


@pytest.mark.physics
class TestPublishedItuTable2:
    @pytest.mark.parametrize("wind_m_s", [21.0, 30.0])
    @pytest.mark.parametrize("wavelength_um", [0.532, 0.850, 1.064, 1.55])
    def test_reproduces_the_published_variance(
        self, wind_m_s: float, wavelength_um: float, degradations: DegradationLog
    ) -> None:
        """Reproduce each of the eight values Table 2 prints.

        The bound is half a unit in the last printed digit, which is all a table
        given to two decimals can license. At 1.55 um and 21 m/s that means the
        published 0.07 admits anything in [0.065, 0.075], and the model returns
        0.0659; the tightest case is 0.532 um and 30 m/s, where 0.36 admits
        [0.355, 0.365] and the model returns 0.3618.
        """
        published = ITU_P1622_TABLE_2[wind_m_s][wavelength_um]
        measured = float(
            log_irradiance_variance(
                deg_to_rad(ITU_P1622_TABLE_2_ELEVATION_DEG),
                wavelength_m=wavelength_um * 1e-6,
                station_height_m=ITU_P1622_TABLE_2_STATION_HEIGHT_M,
                rms_wind_speed_m_s=wind_m_s,
                degradations=degradations,
            )
        )
        assert measured == pytest.approx(published, abs=0.005)

    def test_the_published_table_is_internally_consistent_in_decibels(self) -> None:
        """Table 2's dB^2 column is its Np^2 column times (10/ln 10)^2.

        Equation (4c) says so, and checking it costs nothing: 0.23 Np^2 is
        printed beside 4.35 dB^2, and 0.23 * 18.861 = 4.338. The bound is the
        rounding of the Np^2 column, which at two decimals is +-0.005 Np^2 and
        so +-0.094 dB^2.
        """
        assert 0.23 * NEPER_SQ_TO_DB_SQ == pytest.approx(4.35, abs=0.1)
        assert 0.36 * NEPER_SQ_TO_DB_SQ == pytest.approx(6.84, abs=0.1)

    def test_the_table_conditions_really_do_leave_the_aperture_below_r0(self) -> None:
        """Table 2 assumes "the aperture size is less than r0", so check r0 is not tiny.

        This is what licenses comparing the table against the *point-aperture*
        variance rather than the aperture-averaged one. If r0 came out at a
        centimetre the comparison would be against the wrong quantity.
        """
        r0 = float(
            fried_parameter_m(
                deg_to_rad(ITU_P1622_TABLE_2_ELEVATION_DEG),
                wavelength_m=1.55e-6,
                station_height_m=ITU_P1622_TABLE_2_STATION_HEIGHT_M,
            )
        )
        assert r0 > 0.1


# --------------------------------------------------------------------------- #
# V2 — the closed forms against their own integral forms
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestPublishedClosedFormCoefficients:
    """Each recommendation prints its quantity twice; the two must agree.

    Recomputing the closed-form coefficient from the integral form is a
    transcription check that needs no external oracle: if either printed
    coefficient were mistyped here, or the wrong power of 2 pi used, these fail.
    The 1e-3 bound is the rounding of the four significant figures printed.
    """

    def test_the_fried_parameter_coefficient(self) -> None:
        """P.1621-2 (8a) -> (8b): [0.423 (2 pi)^2]^(-3/5) in micrometres = 1.1654e-8."""
        recomputed = (0.423 * (2.0 * np.pi) ** 2) ** (-0.6) * (1e-6) ** 1.2
        assert recomputed == pytest.approx(1.1654e-8, rel=1e-3)

    def test_the_isoplanatic_angle_coefficient(self) -> None:
        """P.1621-2 (14a) -> (14b): [2.914 (2 pi)^2]^(-3/5) in micrometres = 3.663e-9."""
        recomputed = (2.914 * (2.0 * np.pi) ** 2) ** (-0.6) * (1e-6) ** 1.2
        assert recomputed == pytest.approx(3.663e-9, rel=1e-3)

    def test_the_log_irradiance_coefficient(self) -> None:
        """P.1622 (4a) -> (4b): 2.253 (2 pi)^(7/6) in micrometres = 1.924e8."""
        recomputed = 2.253 * (2.0 * np.pi) ** (7.0 / 6.0) * (1e-6) ** (-7.0 / 6.0)
        assert recomputed == pytest.approx(1.924e8, rel=1e-3)

    def test_the_aperture_averaging_coefficient_absorbs_the_micrometre_conversion(
        self,
    ) -> None:
        """P.1622 (7): the familiar 1.1 becomes 1.1e7 because (1e6)^(7/6) = 1e7.

        Exactly, not approximately — the exponent 7/6 and the factor 1e6 are
        chosen so this is an identity, which is the whole reason the
        recommendation can print a round 1.1e7.
        """
        assert 1.1 * (1e6) ** (7.0 / 6.0) == pytest.approx(1.1e7, rel=1e-12)


# --------------------------------------------------------------------------- #
# V1 — aperture averaging, anchored to the Fresnel scale
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestApertureAveragingInvariants:
    def test_averaging_turns_on_at_the_fresnel_scale(self) -> None:
        """The physical anchor, and the test that catches the unit bug.

        Aperture averaging sets in when the aperture spans more than one speckle,
        and the speckle size on the ground is the Fresnel scale
        ``sqrt(lambda L)`` with ``L`` the effective path to the turbulence,
        ``z0 / sin(elevation)``. At 1550 nm and 75 degrees that is 11.1 cm.

        So an aperture at exactly the Fresnel scale should sit near half
        suppression, an aperture ten times smaller near none, and one ten times
        larger deep into suppression. Measured: 0.48, 0.996 and 0.0054.

        This is the assertion that would have caught passing the wavelength in
        metres to a coefficient written for micrometres: that bug returned
        5e-10 for the 1 m case and 2.5e-5 for the 1 cm case — both still inside
        [0, 1], both silently absurd.
        """
        elevation = deg_to_rad(75.0)
        wavelength_m = 1.55e-6
        path_m = turbulence_scale_height_m() / float(np.sin(elevation))
        fresnel_m = float(np.sqrt(wavelength_m * path_m))
        assert fresnel_m == pytest.approx(0.111, abs=0.005)

        def factor(diameter_m: float) -> float:
            return float(
                aperture_averaging_factor(
                    elevation, aperture_diameter_m=diameter_m, wavelength_m=wavelength_m
                )
            )

        assert factor(0.1 * fresnel_m) > 0.95
        assert 0.3 < factor(fresnel_m) < 0.7
        assert factor(10.0 * fresnel_m) < 0.02

    def test_the_factor_stays_inside_zero_and_one(self) -> None:
        elevation = deg_to_rad(np.linspace(5.0, 90.0, 40))
        for diameter in (0.001, 0.1, 1.0, 10.0):
            values = aperture_averaging_factor(
                elevation, aperture_diameter_m=diameter, wavelength_m=1.55e-6
            )
            assert np.all(values > 0.0)
            assert np.all(values <= 1.0)

    def test_a_bigger_aperture_always_averages_more(self) -> None:
        elevation = deg_to_rad(60.0)
        diameters = np.geomspace(0.01, 3.0, 25)
        factors = [
            float(
                aperture_averaging_factor(
                    elevation, aperture_diameter_m=float(d), wavelength_m=1.55e-6
                )
            )
            for d in diameters
        ]
        assert np.all(np.diff(factors) < 0.0)

    def test_the_downlink_is_the_point_variance_times_the_factor(
        self, degradations: DegradationLog
    ) -> None:
        """Equation (8) is exactly that product, so assert it exactly."""
        elevation = deg_to_rad(np.array([20.0, 45.0, 80.0]))
        point = log_irradiance_variance(elevation, wavelength_m=1.55e-6, degradations=degradations)
        factor = aperture_averaging_factor(elevation, aperture_diameter_m=0.8, wavelength_m=1.55e-6)
        combined = downlink_log_irradiance_variance(
            elevation,
            aperture_diameter_m=0.8,
            wavelength_m=1.55e-6,
            degradations=degradations,
        )
        assert np.array_equal(combined, factor * point)

    def test_the_uplink_gets_no_aperture_averaging_at_all(
        self, degradations: DegradationLog
    ) -> None:
        """P.1622 §4.1.1 equation (5): the uplink variance *is* the point variance.

        This is the asymmetry that catches implementations, so it is asserted as
        exact equality rather than left implicit. Applying the downlink formula
        to an uplink would remove a suppression that is not physically there:
        with a 0.8 m aperture the two differ by a factor of 34 at 20 degrees
        elevation and 114 at 80 degrees — the factor itself climbs with
        elevation, because the averaging factor carries a ``sin(theta)``.
        """
        elevation = deg_to_rad(np.array([20.0, 45.0, 80.0]))
        point = log_irradiance_variance(elevation, wavelength_m=1.55e-6, degradations=degradations)
        uplink = uplink_log_irradiance_variance(
            elevation, wavelength_m=1.55e-6, degradations=degradations
        )
        assert np.array_equal(uplink, point)

        downlink = downlink_log_irradiance_variance(
            elevation,
            aperture_diameter_m=0.8,
            wavelength_m=1.55e-6,
            degradations=degradations,
        )
        suppression = uplink / downlink
        assert np.all(suppression > 30.0)
        assert np.all(np.diff(suppression) > 0.0)

    def test_the_uplink_signature_has_nowhere_to_put_an_aperture(self) -> None:
        """A parameter that must not be used is better absent than defaulted.

        Same guard as ``secular_rates_j2`` having nowhere to accept a J3: the
        shape of the API is what stops the wrong physics being requested.
        """
        import inspect

        parameters = inspect.signature(uplink_log_irradiance_variance).parameters
        assert not any("aperture" in name for name in parameters)
        assert not any("diameter" in name for name in parameters)


# --------------------------------------------------------------------------- #
# V1 — the exponents, checked by scaling
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestScalingInvariants:
    def test_the_variance_goes_as_sine_to_the_minus_eleven_sixths(
        self, degradations: DegradationLog
    ) -> None:
        """Attribution of the elevation exponent, not a value check.

        Equation (4b) has ``sin(theta)^(-11/6)``, so the ratio of variances at
        two elevations is a pure power of the ratio of their sines with no
        dependence on the profile, the wavelength or the site. Getting the
        exponent wrong — 11/6 against, say, 6/5 — changes a low-elevation
        variance by tens of percent while leaving every high-elevation number
        looking fine.
        """
        high = deg_to_rad(80.0)
        low = deg_to_rad(15.0)
        ratio = float(
            log_irradiance_variance(low, wavelength_m=1.55e-6, degradations=degradations)
            / log_irradiance_variance(high, wavelength_m=1.55e-6, degradations=degradations)
        )
        expected = (np.sin(high) / np.sin(low)) ** (11.0 / 6.0)
        assert ratio == pytest.approx(float(expected), rel=1e-12)

    def test_the_variance_goes_as_wavelength_to_the_minus_seven_sixths(
        self, degradations: DegradationLog
    ) -> None:
        elevation = deg_to_rad(50.0)
        short = float(
            log_irradiance_variance(elevation, wavelength_m=5.32e-7, degradations=degradations)
        )
        long = float(
            log_irradiance_variance(elevation, wavelength_m=1.55e-6, degradations=degradations)
        )
        assert short / long == pytest.approx((1.55e-6 / 5.32e-7) ** (7.0 / 6.0), rel=1e-12)

    def test_the_fried_parameter_goes_as_wavelength_to_the_six_fifths(self) -> None:
        """r0 ~ lambda^1.2 is why infrared links suffer less than visible ones."""
        elevation = deg_to_rad(50.0)
        short = float(fried_parameter_m(elevation, wavelength_m=5.32e-7))
        long = float(fried_parameter_m(elevation, wavelength_m=1.55e-6))
        assert long / short == pytest.approx((1.55e-6 / 5.32e-7) ** 1.2, rel=1e-12)

    def test_the_isoplanatic_angle_falls_faster_with_elevation_than_r0(self) -> None:
        """sin^1.6 against sin^0.6 — the recommendation's "decreases rapidly" in algebra.

        P.1621-2 §5.1.3 says theta_0 "decreases rapidly with elevation angles
        below about 75 degrees" while §5.1.2 gives r0 a gentler exponent. The
        ratio of the two exponents is exactly 1.6 / 0.6.
        """
        high = deg_to_rad(85.0)
        low = deg_to_rad(25.0)
        r0_ratio = float(
            fried_parameter_m(high, wavelength_m=1.55e-6)
            / fried_parameter_m(low, wavelength_m=1.55e-6)
        )
        angle_ratio = float(
            isoplanatic_angle_rad(high, wavelength_m=1.55e-6)
            / isoplanatic_angle_rad(low, wavelength_m=1.55e-6)
        )
        assert np.log(angle_ratio) / np.log(r0_ratio) == pytest.approx(1.6 / 0.6, rel=1e-12)

    def test_the_isoplanatic_angle_lands_in_the_range_the_text_gives(self) -> None:
        """Stay inside the 1e-6 to 1e-4 rad range §5.1.3 says these angles occupy."""
        elevation = deg_to_rad(np.linspace(10.0, 90.0, 30))
        angles = isoplanatic_angle_rad(elevation, wavelength_m=1.55e-6)
        assert np.all(angles > 1e-6)
        assert np.all(angles < 1e-4)

    def test_higher_moments_weight_the_jet_stream_more(self) -> None:
        """The reason the module computes moments rather than one integral.

        Raising the height weighting must raise the effective altitude, so the
        ratio of successive moments grows. If ``cn2_path_moment`` ignored its
        power argument this would collapse.
        """
        zeroth = cn2_path_moment(0.0)
        five_sixths = cn2_path_moment(5.0 / 6.0)
        second = cn2_path_moment(2.0)
        assert five_sixths / zeroth < second / five_sixths

    def test_shapes_are_preserved_over_the_time_axis(self, degradations: DegradationLog) -> None:
        """A pass is (n_samples,); a stack of passes is (n_satellites, n_samples)."""
        elevation = deg_to_rad(np.linspace(10.0, 80.0, 12).reshape(3, 4))
        assert log_irradiance_variance(
            elevation, wavelength_m=1.55e-6, degradations=degradations
        ).shape == (3, 4)
        assert fried_parameter_m(elevation, wavelength_m=1.55e-6).shape == (3, 4)
        assert isoplanatic_angle_rad(elevation, wavelength_m=1.55e-6).shape == (3, 4)


# --------------------------------------------------------------------------- #
# The model saying when it is out of range
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheWeakFluctuationWarning:
    def test_nothing_is_recorded_inside_the_valid_range(self, degradations: DegradationLog) -> None:
        log_irradiance_variance(deg_to_rad(70.0), wavelength_m=1.55e-6, degradations=degradations)
        assert len(degradations) == 0

    def test_a_warning_is_recorded_once_the_theory_is_out_of_range(
        self, degradations: DegradationLog
    ) -> None:
        """Low elevation in visible light drives the variance past 1 Np^2.

        The point of the test is not the number but that the caller is told:
        the value returned is still equation (4a)'s, and equation (4a) has
        stopped being trustworthy, and nothing about the returned array says so.
        """
        variance = log_irradiance_variance(
            deg_to_rad(5.0), wavelength_m=5.32e-7, degradations=degradations
        )
        assert float(variance) > WEAK_FLUCTUATION_VARIANCE_LIMIT
        assert len(degradations) == 1
        entry = degradations.entries[0]
        assert entry.code == "turbulence.weak-fluctuation-limit-exceeded"
        assert entry.severity is Severity.WARNING
        assert entry.where == "quoss.channel.turbulence.log_irradiance_variance"
        assert entry.details["peak_variance_np2"] == pytest.approx(float(variance))

    def test_the_warning_is_a_warning_and_not_a_degradation(
        self, degradations: DegradationLog
    ) -> None:
        """Severity matters: nothing was substituted, so `has_degraded` stays false.

        ``core/errors.py`` reserves DEGRADED for "a model was substituted". Here
        the caller still gets the model they asked for, evaluated outside its
        range, which is precisely what WARNING is for.
        """
        log_irradiance_variance(deg_to_rad(5.0), wavelength_m=5.32e-7, degradations=degradations)
        assert not degradations.has_degraded


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestRejectsBadInput:
    def test_an_elevation_at_or_below_the_horizon_is_rejected(
        self, degradations: DegradationLog
    ) -> None:
        """Zero elevation is rejected, not clamped: sec(zenith) diverges there."""
        with pytest.raises(DomainError, match=r"\(0, pi/2\]"):
            log_irradiance_variance(0.0, wavelength_m=1.55e-6, degradations=degradations)
        with pytest.raises(DomainError, match=r"\(0, pi/2\]"):
            log_irradiance_variance(
                deg_to_rad(-3.0), wavelength_m=1.55e-6, degradations=degradations
            )

    def test_degrees_passed_as_radians_are_caught(self, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match="radians, not degrees"):
            log_irradiance_variance(45.0, wavelength_m=1.55e-6, degradations=degradations)

    def test_a_non_finite_elevation_is_rejected(self, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            log_irradiance_variance(
                np.array([deg_to_rad(30.0), np.nan]),
                wavelength_m=1.55e-6,
                degradations=degradations,
            )

    def test_a_non_positive_wavelength_is_rejected(self, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match="wavelength_m"):
            log_irradiance_variance(deg_to_rad(45.0), wavelength_m=0.0, degradations=degradations)
        with pytest.raises(DomainError, match="wavelength_m"):
            fried_parameter_m(deg_to_rad(45.0), wavelength_m=-1.0)
        with pytest.raises(DomainError, match="wavelength_m"):
            isoplanatic_angle_rad(deg_to_rad(45.0), wavelength_m=float("nan"))

    def test_a_non_positive_aperture_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="aperture_diameter_m"):
            aperture_averaging_factor(
                deg_to_rad(45.0), aperture_diameter_m=0.0, wavelength_m=1.55e-6
            )
        with pytest.raises(DomainError, match="aperture_diameter_m"):
            aperture_averaging_factor(
                deg_to_rad(45.0), aperture_diameter_m=float("inf"), wavelength_m=1.55e-6
            )

    def test_the_elevation_guard_fires_inside_aperture_averaging_too(self) -> None:
        with pytest.raises(DomainError, match=r"\(0, pi/2\]"):
            aperture_averaging_factor(0.0, aperture_diameter_m=1.0, wavelength_m=1.55e-6)

    def test_a_bad_moment_power_or_station_height_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="power"):
            cn2_path_moment(float("nan"))
        with pytest.raises(DomainError, match="non-negative"):
            cn2_path_moment(0.0, station_height_m=-1.0)
        with pytest.raises(DomainError, match="finite"):
            cn2_path_moment(0.0, station_height_m=float("inf"))
        with pytest.raises(DomainError, match="top of the turbulent atmosphere"):
            cn2_path_moment(0.0, station_height_m=25_000.0)


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import turbulence

        assert turbulence.__all__ == sorted(turbulence.__all__)
        for name in turbulence.__all__:
            assert hasattr(turbulence, name)

    def test_the_module_documents_both_recommendations(self) -> None:
        from quoss.channel import turbulence

        assert turbulence.__doc__ is not None
        assert "P.1622" in turbulence.__doc__
        assert "P.1621-2" in turbulence.__doc__
