"""Tests for `quoss.channel.horizontal`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestPublishedItuP1814Table4`` — **V2**: the six optical fade depths ITU-R
  P.1814 prints for a 1 km path, reproduced to their two decimals.
- ``TestThreeSourcesAgree`` — **between sources**: P.1814's coefficient against
  P.1622 equation (4a) integrated along a horizontal path and against Kaushal &
  Kaddoum (8); and Kaushal & Kaddoum's aperture averaging (20) against P.1622
  equations (6)-(7) on the same path, which is also what confirms the
  micrometre reading of P.1622's 1.1e7.
- ``TestApertureAveragingInvariants`` and ``TestScalingInvariants`` — **V1**.
- ``TestTheWeakFluctuationWarning`` and ``TestTheWaveModelWarning`` — the module
  says when it is outside its theory, with the size of what that costs.
- ``TestNoSignatureTakesAnElevation`` — by absence.
- ``TestTheLossBudget`` — composition, the bench, and why a slant path at a low
  angle is not a horizontal one.
- ``TestSizingTheGroundExperiments`` — the question this module exists to
  answer for GE-0b and GE-1, on declared assumptions. **V4** where it quotes a
  number: it is QuOSS's own output on inputs nobody published.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

import numpy as np
import pytest
from scipy.integrate import quad

from quoss.channel import horizontal
from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
from quoss.channel.beam import rayleigh_range_km
from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
    receiver_efficiency,
)
from quoss.channel.horizontal import (
    ITU_P1814_SCINTILLATION_COEFFICIENT_DB2,
    KAUSHAL_PLANE_APERTURE_AVERAGING_COEFFICIENT,
    KAUSHAL_PLANE_STRONG_TURBULENCE_COEFFICIENT,
    KAUSHAL_SPHERICAL_WAVE_COEFFICIENT,
    PLANE_WAVE_RYTOV_COEFFICIENT,
    PathWave,
    ScintillationRegime,
    equivalent_bench_cn2_m23,
    horizontal_aperture_averaging_factor,
    horizontal_log_irradiance_variance,
    horizontal_loss_budget,
    horizontal_point_log_irradiance_variance,
    plane_wave_rytov_variance,
    weak_theory_path_limit_m,
)
from quoss.channel.link_budget import (
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    FadeCombination,
    LossBudget,
    combined_fade_db,
    downlink_noise_budget,
)
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import (
    _APERTURE_AVERAGING_COEFFICIENT,
    NEPER_SQ_TO_DB_SQ,
    WEAK_FLUCTUATION_VARIANCE_LIMIT,
    log_irradiance_variance,
    saturated_log_irradiance_variance,
)
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.units import deg_to_rad
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, KeyRate, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol

# --------------------------------------------------------------------------- #
# The published table, transcribed with its citation
# --------------------------------------------------------------------------- #

ITU_P1814_TABLE_4_PATH_M = 1000.0
ITU_P1814_TABLE_4 = {
    0.98e-6: {1e-16: 0.51, 1e-14: 5.06, 1e-13: 16.00},
    1.55e-6: {1e-16: 0.39, 1e-14: 3.87, 1e-13: 12.25},
}
"""ITU-R P.1814 Table 4, "Table of scintillation fade depths expected for 1 km path length".

Keyed by wavelength (m), then by ``C_n^2`` (m^(-2/3)) — the "Low", "Moderate"
and "High" columns — giving the attenuation in dB. The text below equation (8)
defines that attenuation as ``2 sigma_chi``, with ``sigma_chi^2`` from equation
(8) in dB^2. Read from the PDF page image, not the text layer.
"""

HALF_PRINTED_DIGIT_DB = 0.005
"""Table 4 prints two decimals, so a printed value stands for anything within this."""

COEFFICIENT_RELATIVE_ROUNDING = 0.005 / ITU_P1814_SCINTILLATION_COEFFICIENT_DB2
"""23.17 printed to four figures: a table computed from a longer coefficient may differ by this.

In the variance; half of it in ``sigma``, which is what the table prints.
"""

WAVELENGTH_M = 1.55e-6


def point_variance(path_m: float, cn2: float, wave: PathWave = PathWave.PLANE) -> float:
    return float(
        horizontal_point_log_irradiance_variance(
            path_m, cn2_m23=cn2, wavelength_m=WAVELENGTH_M, wave=wave, degradations=DegradationLog()
        )
    )


@pytest.mark.reference
class TestPublishedItuP1814Table4:
    @pytest.mark.parametrize(
        ("wavelength_m", "cn2", "printed_db"),
        [
            (wavelength, cn2, printed)
            for wavelength, row in ITU_P1814_TABLE_4.items()
            for cn2, printed in row.items()
        ],
    )
    def test_the_fade_depth_is_twice_the_sigma_of_equation_8(
        self, wavelength_m: float, cn2: float, printed_db: float
    ) -> None:
        """All six optical cells, including the two the recommendation should not have printed.

        The tolerance is the printed rounding plus the rounding of the
        coefficient, both derived above; measured, the largest miss is
        0.0039 dB (0.51 printed, 0.5061 computed).
        """
        variance_np2 = plane_wave_rytov_variance(
            ITU_P1814_TABLE_4_PATH_M, cn2_m23=cn2, wavelength_m=wavelength_m
        )
        depth_db = 2.0 * float(np.sqrt(variance_np2 * NEPER_SQ_TO_DB_SQ))
        tolerance = HALF_PRINTED_DIGIT_DB + 0.5 * COEFFICIENT_RELATIVE_ROUNDING * printed_db
        assert depth_db == pytest.approx(printed_db, abs=tolerance)

    def test_the_high_column_is_outside_the_theory_that_printed_it(self) -> None:
        """P.1814 says the variance saturates in strong turbulence, and tabulates 1e-13 anyway.

        The plane-wave Rytov variance of its "High" column is 1.99 Np^2 at
        1550 nm and 3.39 at 980 nm — both above the limit of weak-fluctuation
        theory — so 12.25 and 16.00 dB are exactly the kind of number that is
        right to the printed digit and wrong about the air. The module warns on
        those two cells and on none of the other four.
        """
        for wavelength_m, row in ITU_P1814_TABLE_4.items():
            for cn2 in row:
                log = DegradationLog()
                horizontal_point_log_irradiance_variance(
                    ITU_P1814_TABLE_4_PATH_M,
                    cn2_m23=cn2,
                    wavelength_m=wavelength_m,
                    wave=PathWave.PLANE,
                    degradations=log,
                )
                assert (len(log) == 1) is (cn2 == 1e-13), (wavelength_m, cn2)
        assert plane_wave_rytov_variance(
            1000.0, cn2_m23=1e-13, wavelength_m=1.55e-6
        ) == pytest.approx(1.99, abs=0.005)
        assert plane_wave_rytov_variance(
            1000.0, cn2_m23=1e-13, wavelength_m=0.98e-6
        ) == pytest.approx(3.39, abs=0.005)


@pytest.mark.reference
class TestThreeSourcesAgree:
    def test_p1622_equation_4a_along_a_horizontal_path_is_p1814(self) -> None:
        """The slant-path integral this project already uses, laid flat.

        P.1622 (4a) is ``2.253 k^(7/6) sec(zeta)^(11/6) integral Cn2(h) h^(5/6) dh``.
        Write the height as the distance along the path, ``h = s cos(zeta)``:
        ``dh = cos(zeta) ds`` and ``h^(5/6) = s^(5/6) cos(zeta)^(5/6)``, and the
        ``sec^(11/6)`` cancels exactly, leaving
        ``2.253 k^(7/6) integral Cn2(s) s^(5/6) ds`` — an integral along the
        path from the receiver, which no longer knows where the path points. For
        a uniform path of length ``L`` that is ``2.253 (6/11) Cn2 k^(7/6) L^(11/6)``.

        Measured: 1.22891 against P.1814's 1.22845, 3.7e-4 apart. Derived bound:
        2.253 and 23.17 are each printed to four figures, 2.2e-4 of rounding
        each, 4.4e-4 together.
        """
        integral, _ = quad(lambda s: s ** (5.0 / 6.0), 0.0, 1.0)
        assert integral == pytest.approx(6.0 / 11.0, rel=1e-12)
        from_p1622 = 2.253 * integral
        bound = 0.0005 / 2.253 + 0.005 / ITU_P1814_SCINTILLATION_COEFFICIENT_DB2
        assert abs(from_p1622 / PLANE_WAVE_RYTOV_COEFFICIENT - 1.0) <= bound
        assert abs(from_p1622 / PLANE_WAVE_RYTOV_COEFFICIENT - 1.0) == pytest.approx(
            3.7e-4, abs=0.1e-4
        )

    def test_kaushal_and_kaddoum_print_the_textbook_1_23(self) -> None:
        """Their equation (8), to its three printed figures: 1.3e-3 apart, 4.1e-3 allowed."""
        assert abs(1.23 / PLANE_WAVE_RYTOV_COEFFICIENT - 1.0) <= 0.005 / 1.23

    def test_the_spherical_wave_is_the_0_4_their_equation_9_prints(self) -> None:
        """Equation (9) writes the same variance twice: ``0.4 sigma_R^2`` and ``0.5 Cn2 k^(7/6) L^(11/6)``."""
        ratio = KAUSHAL_SPHERICAL_WAVE_COEFFICIENT / PLANE_WAVE_RYTOV_COEFFICIENT
        assert ratio == pytest.approx(0.4, abs=0.05 / 1.0 * 0.4 + 0.005)
        assert point_variance(1000.0, 1e-14, PathWave.SPHERICAL) / point_variance(
            1000.0, 1e-14
        ) == pytest.approx(ratio, rel=1e-12)

    def test_p1622_aperture_averaging_along_a_horizontal_path_is_churnsides(self) -> None:
        """P.1622 (6)-(7) laid flat, against Kaushal & Kaddoum (20). And the unit it settles.

        The same substitution as above turns the scale height of (6) into a
        distance along the path, and for uniform turbulence
        ``z0 = [(L^3/3) / ((6/11) L^(11/6))]^(6/7) = (11/18)^(6/7) L``; in (7)
        ``sin(theta)`` cancels against the ``cos(zeta)`` of that substitution.
        So (7) becomes ``1 / (1 + 1.1e7 (D^2 / (lambda_um (11/18)^(6/7) L))^(7/6))``,
        whose coefficient in metres is ``1.1 * 18/11 = 1.8`` exactly. Churnside,
        as quoted in (20), is ``1.07 (pi/2)^(7/6) = 1.812``.

        0.67 % apart. Derived bound: P.1622 prints "1.1" — two figures, 4.5 % —
        and (20) prints 1.07, 0.47 %.

        It also settles, from a second source, the unit
        ``quoss.channel.turbulence`` had to settle by a Fresnel-scale argument:
        read with the wavelength in metres, 1.1e7 would be 1.8e7 here and
        disagree with Churnside by seven orders of magnitude.
        """
        for path_m in (2.0, 200.0, 1000.0, 5000.0):
            for diameter_m in (0.01, 0.05, 0.2):
                z0 = (11.0 / 18.0) ** (6.0 / 7.0) * path_m
                argument = diameter_m**2 / (WAVELENGTH_M * 1e6 * z0)
                itu_excess = _APERTURE_AVERAGING_COEFFICIENT * argument ** (7.0 / 6.0)
                kaushal = float(
                    horizontal_aperture_averaging_factor(
                        path_m,
                        aperture_diameter_m=diameter_m,
                        wavelength_m=WAVELENGTH_M,
                        wave=PathWave.PLANE,
                    )
                )
                kaushal_excess = 1.0 / kaushal - 1.0
                assert abs(itu_excess / kaushal_excess - 1.0) <= 0.05 / 1.1 + 0.005 / 1.07
                read_in_metres = 1.1e7 * (diameter_m**2 / (WAVELENGTH_M * z0)) ** (7.0 / 6.0)
                assert read_in_metres / kaushal_excess > 1e6
        coefficient = KAUSHAL_PLANE_APERTURE_AVERAGING_COEFFICIENT * (np.pi / 2.0) ** (7.0 / 6.0)
        assert 1.8 / coefficient == pytest.approx(0.9933, abs=1e-4)


@pytest.mark.physics
class TestApertureAveragingInvariants:
    @pytest.mark.parametrize("wave", list(PathWave))
    def test_between_zero_and_one_and_decreasing_in_the_aperture(self, wave: PathWave) -> None:
        diameters = np.geomspace(1e-4, 1.0, 60)
        factors = np.array(
            [
                float(
                    horizontal_aperture_averaging_factor(
                        1000.0, aperture_diameter_m=float(d), wavelength_m=WAVELENGTH_M, wave=wave
                    )
                )
                for d in diameters
            ]
        )
        assert np.all((factors > 0.0) & (factors <= 1.0))
        assert np.all(np.diff(factors) < 0.0)
        assert factors[0] > 0.999

    def test_a_longer_path_averages_less_with_the_same_lens(self) -> None:
        """Longer path, bigger speckles, fewer of them in the lens."""
        factors = horizontal_aperture_averaging_factor(
            np.array([100.0, 1000.0, 10000.0]),
            aperture_diameter_m=0.05,
            wavelength_m=WAVELENGTH_M,
            wave=PathWave.PLANE,
        )
        assert np.all(np.diff(factors) > 0.0)

    def test_the_spherical_wave_is_averaged_less(self) -> None:
        """0.214 against 1.07: its speckle is coarser at the receiver end."""
        kwargs = {"aperture_diameter_m": 0.05, "wavelength_m": WAVELENGTH_M}
        plane = horizontal_aperture_averaging_factor(1000.0, wave=PathWave.PLANE, **kwargs)
        spherical = horizontal_aperture_averaging_factor(1000.0, wave=PathWave.SPHERICAL, **kwargs)
        assert float(spherical) > float(plane)

    def test_at_the_fresnel_scale_the_factor_is_the_closed_form(self) -> None:
        """``D = sqrt(lambda L)`` makes ``k D^2 / 4L = pi / 2`` for any path."""
        for path_m in (10.0, 1000.0, 1e5):
            fresnel = float(np.sqrt(WAVELENGTH_M * path_m))
            factor = horizontal_aperture_averaging_factor(
                path_m, aperture_diameter_m=fresnel, wavelength_m=WAVELENGTH_M, wave=PathWave.PLANE
            )
            expected = 1.0 / (1.0 + 1.07 * (np.pi / 2.0) ** (7.0 / 6.0))
            assert float(factor) == pytest.approx(expected, rel=1e-12)


@pytest.mark.physics
class TestScalingInvariants:
    def test_the_exponents(self) -> None:
        base = point_variance(700.0, 3e-15)
        assert point_variance(700.0, 6e-15) / base == pytest.approx(2.0, rel=1e-12)
        assert point_variance(1400.0, 3e-15) / base == pytest.approx(2.0 ** (11.0 / 6.0), rel=1e-12)
        longer = plane_wave_rytov_variance(700.0, cn2_m23=3e-15, wavelength_m=2.0 * WAVELENGTH_M)
        assert float(longer) / base == pytest.approx(2.0 ** (-7.0 / 6.0), rel=1e-12)

    def test_still_air_does_not_scintillate(self) -> None:
        assert point_variance(1000.0, 0.0) == 0.0

    def test_it_broadcasts_length_against_turbulence(self) -> None:
        variance = plane_wave_rytov_variance(
            np.array([[100.0], [1000.0]]),
            cn2_m23=np.array([1e-15, 1e-14, 1e-13]),
            wavelength_m=WAVELENGTH_M,
        )
        assert variance.shape == (2, 3)


class TestTheWeakFluctuationWarning:
    def test_it_carries_the_strong_turbulence_asymptote_as_a_measure(self) -> None:
        """At P.1814's own High cell, the measure says the weak theory is 2.04 times too large."""
        log = DegradationLog()
        returned = horizontal_point_log_irradiance_variance(
            1000.0, cn2_m23=1e-13, wavelength_m=WAVELENGTH_M, wave=PathWave.PLANE, degradations=log
        )
        (entry,) = log.entries
        assert entry.code == "horizontal.weak-fluctuation-limit-exceeded"
        assert entry.severity is Severity.WARNING
        rytov = entry.details["peak_rytov_variance_np2"]
        strong = 1.0 + KAUSHAL_PLANE_STRONG_TURBULENCE_COEFFICIENT / rytov ** (2.0 / 5.0)
        assert entry.details["strong_turbulence_scintillation_index"] == pytest.approx(
            strong, rel=1e-12
        )
        assert entry.details["strong_turbulence_log_variance_np2"] == pytest.approx(
            np.log(1.0 + strong), rel=1e-12
        )
        assert entry.details["returned_variance_np2"] == float(returned)
        assert entry.details["limit_np2"] == WEAK_FLUCTUATION_VARIANCE_LIMIT
        assert float(returned) / entry.details[
            "strong_turbulence_log_variance_np2"
        ] == pytest.approx(2.04, abs=0.01)

    def test_the_regime_is_the_paths_whichever_wave_was_asked_for(self) -> None:
        """A spherical variance below 1 on a path whose Rytov variance is above 1 still warns."""
        cn2 = 1.2 / float(plane_wave_rytov_variance(1000.0, cn2_m23=1.0, wavelength_m=WAVELENGTH_M))
        assert point_variance(1000.0, cn2, PathWave.SPHERICAL) < 1.0
        log = DegradationLog()
        horizontal_point_log_irradiance_variance(
            1000.0,
            cn2_m23=cn2,
            wavelength_m=WAVELENGTH_M,
            wave=PathWave.SPHERICAL,
            degradations=log,
        )
        assert [e.code for e in log] == ["horizontal.weak-fluctuation-limit-exceeded"]
        assert log.entries[0].details["wave"] == "spherical"

    def test_below_the_limit_nothing_is_recorded(self) -> None:
        log = DegradationLog()
        horizontal_log_irradiance_variance(
            1000.0,
            cn2_m23=1e-14,
            aperture_diameter_m=0.1,
            wavelength_m=WAVELENGTH_M,
            wave=PathWave.PLANE,
            degradations=log,
        )
        assert len(log) == 0


class TestTheWaveModelWarning:
    """A 5 cm transmitter at 1550 nm has a 1 267 m Rayleigh range."""

    @staticmethod
    def _codes(path_m: float, wave: PathWave) -> list[str]:
        log = DegradationLog()
        horizontal_loss_budget(path_m, wave=wave, degradations=log, **GE1_BASE, cn2_m23=1e-15)
        return [e.code for e in log if e.code.startswith("horizontal.")]

    def test_the_rayleigh_range_of_the_example(self) -> None:
        assert rayleigh_range_km(
            wavelength_m=WAVELENGTH_M, transmit_aperture_m=0.05
        ) * 1000.0 == pytest.approx(1266.8, abs=0.1)

    def test_each_wave_is_silent_on_its_own_side_and_warns_on_the_other(self) -> None:
        assert self._codes(1000.0, PathWave.PLANE) == []
        assert self._codes(2000.0, PathWave.PLANE) == [
            "horizontal.plane-wave-beyond-the-rayleigh-range"
        ]
        assert self._codes(2000.0, PathWave.SPHERICAL) == []
        assert self._codes(1000.0, PathWave.SPHERICAL) == [
            "horizontal.spherical-wave-inside-the-rayleigh-range"
        ]

    def test_the_warning_carries_the_factor_the_choice_is_worth(self) -> None:
        log = DegradationLog()
        horizontal_loss_budget(
            2000.0, wave=PathWave.PLANE, degradations=log, **GE1_BASE, cn2_m23=1e-15
        )
        (entry,) = [e for e in log if e.code.startswith("horizontal.")]
        assert entry.details["path_to_rayleigh_range_ratio"] == pytest.approx(1.579, abs=0.001)
        assert entry.details["plane_to_spherical_variance_ratio"] == pytest.approx(2.457, abs=0.001)


class TestNoSignatureTakesAnElevation:
    def test_no_public_function_has_an_elevation_or_a_station_height(self) -> None:
        """A horizontal path has no elevation, and the API must not accept one.

        Nor a station height, nor a wind speed: those parametrise the
        Hufnagel-Valley profile, and a horizontal path does not integrate it.
        If one appears, it should arrive with a citation and this test should
        be what notices.
        """
        for name in horizontal.__all__:
            attribute = getattr(horizontal, name)
            if not callable(attribute) or isinstance(attribute, type):
                continue
            for parameter in inspect.signature(attribute).parameters:
                for forbidden in ("elevation", "zenith", "station_height", "wind"):
                    assert forbidden not in parameter, (name, parameter)

    def test_the_module_never_touches_an_elevation_or_the_profile(self) -> None:
        """By source: no name mentions an elevation, and `turbulence` lends only path-free things.

        The allowed list grew when stage 1.2 arrived, and what it is allowed to
        grow *with* is the point: two unit constants, the plane/spherical enum,
        the regime enum and the saturation model. None of the five knows about an
        elevation, a zenith angle or the Hufnagel-Valley profile, so none of them
        can smuggle a slant path into a horizontal one. An import of
        ``log_irradiance_variance`` or ``cn2_path_moment`` would fail here, which
        is what this test is for.
        """
        tree = ast.parse(inspect.getsource(horizontal))
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                assert "elevation" not in node.id
            if isinstance(node, ast.ImportFrom) and node.module == "quoss.channel.turbulence":
                assert {alias.name for alias in node.names} == {
                    "NEPER_SQ_TO_DB_SQ",
                    "WEAK_FLUCTUATION_VARIANCE_LIMIT",
                    "PathWave",
                    "ScintillationRegime",
                    "saturated_log_irradiance_variance",
                }
            if isinstance(node, ast.ImportFrom) and node.module == "quoss.channel.atmosphere":
                pytest.fail("the horizontal module must not import the vertical profile")

    def test_a_slant_path_at_a_low_angle_is_not_a_horizontal_path(self) -> None:
        """The reason the separate module exists, measured.

        The slant-path variance at 0.1 degrees elevation, with the ITU profile
        starting from its ground value of 1.727e-14, against a 1 km horizontal
        path in air of that same ground value: 7 103 Np^2 against 0.343, a
        factor of 2.1e4. The slant formula is integrating twenty kilometres of
        atmosphere along an 11 000 km line, and it warns — but the number a
        careless caller would take for "nearly horizontal" is not a horizontal
        link at all.
        """
        log = DegradationLog()
        slant = float(
            log_irradiance_variance(deg_to_rad(0.1), wavelength_m=WAVELENGTH_M, degradations=log)
        )
        flat = float(
            plane_wave_rytov_variance(1000.0, cn2_m23=1.727e-14, wavelength_m=WAVELENGTH_M)
        )
        assert slant / flat == pytest.approx(2.07e4, rel=0.01)
        assert [e.code for e in log] == ["turbulence.weak-fluctuation-limit-exceeded"]


# --------------------------------------------------------------------------- #
# The loss budget, and the sizing question it answers
# --------------------------------------------------------------------------- #

GE1_BASE: dict[str, Any] = {
    "wavelength_m": WAVELENGTH_M,
    "transmit_aperture_m": 0.05,
    "receive_aperture_m": 0.1,
    "extinction_db_per_km": 0.2,
    "pointing_jitter_rad": 5e-6,
    "receiver_efficiency": receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    ),
}
"""A horizontal link to size, **on declared assumptions and not published values**.

The receiver chain is the Ntanos et al. 2021 one the downlink uses. The rest is
this file's choice, written here so a reader can change it: 5 µrad of r.m.s.
jitter per axis, and 0.2 dB/km of clear-air extinction, which P.1814 does not
give a number for (its equation (3) is the form, not the value).
"""


@pytest.mark.physics
class TestTheLossBudget:
    def test_the_terms_add_up_to_the_total(self) -> None:
        budget = horizontal_loss_budget(
            np.array([200.0, 1000.0, 3000.0]),
            wave=PathWave.PLANE,
            cn2_m23=1e-14,
            degradations=DegradationLog(),
            **GE1_BASE,
        )
        assert isinstance(budget, LossBudget)
        total = (
            budget.geometric_db
            + budget.truncation_db
            + budget.atmospheric_db
            + budget.fade_db
            + budget.receiver_chain_db
            + budget.static_db
        )
        np.testing.assert_allclose(budget.total_db, total, rtol=0, atol=1e-12)
        np.testing.assert_allclose(budget.atmospheric_db, [0.04, 0.2, 0.6], rtol=0, atol=1e-15)

    def test_the_fade_is_the_shared_law_on_the_horizontal_inputs(self) -> None:
        """Same private assembler as the downlink: the fade is `combined_fade_db` of these inputs."""
        log = DegradationLog()
        budget = horizontal_loss_budget(
            1000.0, wave=PathWave.PLANE, cn2_m23=1e-14, degradations=log, **GE1_BASE
        )
        gamma = beam_to_jitter_ratio(
            1.0,
            jitter_rad=GE1_BASE["pointing_jitter_rad"],
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=0.05,
            receive_aperture_m=0.1,
            degradations=DegradationLog(),
        )
        variance = horizontal_log_irradiance_variance(
            1000.0,
            cn2_m23=1e-14,
            aperture_diameter_m=0.1,
            wavelength_m=WAVELENGTH_M,
            wave=PathWave.PLANE,
            degradations=DegradationLog(),
        )
        by_hand = combined_fade_db(
            beam_to_jitter_ratio_value=gamma,
            log_irradiance_variance_np2=variance,
            outage_probability=0.01,
        )
        assert float(budget.fade_db) == float(by_hand)
        assert budget.fade_combination is FadeCombination.EXACT

    def test_extinction_and_wave_have_no_default(self) -> None:
        """ADR 0009 gap 14's rule, carried over: nothing quietly means "not thought about"."""
        parameters = inspect.signature(horizontal_loss_budget).parameters
        for name in ("extinction_db_per_km", "wave", "cn2_m23", "pointing_jitter_rad"):
            assert parameters[name].default is inspect.Parameter.empty

    def test_a_bench_with_a_lens_far_wider_than_the_beam(self) -> None:
        """A 2 mm beam, two metres, into 20 cm: every term defined, pointing exactly zero.

        This geometry used to be a ``RuntimeWarning`` in the pointing law and,
        one step on, a silently wrong joint fade; see
        `tests/channel/test_pointing.py::TestALensFarWiderThanTheBeam` and
        `tests/channel/test_link_budget.py::TestTheJointFadeWhenPointingIsNegligible`.
        The geometric term saturates at zero decibels instead of promising more
        light than was sent, and what is left is the transmitter truncation and
        the receiver chain.
        """
        log = DegradationLog()
        bench = dict(
            GE1_BASE, transmit_aperture_m=0.002, receive_aperture_m=0.2, extinction_db_per_km=0.0
        )
        budget = horizontal_loss_budget(
            2.0, wave=PathWave.PLANE, cn2_m23=1e-10, degradations=log, **bench
        )
        assert float(budget.pointing_db) == 0.0
        assert float(budget.geometric_db) == pytest.approx(0.0, abs=1e-12)
        assert np.isfinite(float(budget.total_db))
        (entry,) = log.entries
        assert entry.details["equivalent_radius_is_infinite"] is True

    def test_zero_turbulence_leaves_only_the_pointing_fade(self) -> None:
        budget = horizontal_loss_budget(
            1000.0, wave=PathWave.PLANE, cn2_m23=0.0, degradations=DegradationLog(), **GE1_BASE
        )
        assert float(budget.scintillation_db) == 0.0
        assert float(budget.fade_db) == pytest.approx(float(budget.pointing_db), abs=1e-12)

    @pytest.mark.parametrize(
        ("field", "value", "match"),
        [
            ("extinction_db_per_km", -0.1, "extinction_db_per_km"),
            ("extinction_db_per_km", np.nan, "extinction_db_per_km"),
            ("receive_aperture_m", 0.0, "receive_aperture_m"),
            ("static_loss_db", -1.0, "static_loss_db"),
        ],
    )
    def test_bad_inputs_are_refused(self, field: str, value: float, match: str) -> None:
        kwargs = dict(GE1_BASE, **{field: value})
        with pytest.raises(DomainError, match=match):
            horizontal_loss_budget(
                1000.0, wave=PathWave.PLANE, cn2_m23=1e-14, degradations=DegradationLog(), **kwargs
            )

    @pytest.mark.parametrize("length", [0.0, -1.0, np.inf, np.nan])
    def test_a_path_length_that_is_not_a_length_is_refused(self, length: float) -> None:
        with pytest.raises(DomainError, match="path_length_m"):
            plane_wave_rytov_variance(length, cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)

    @pytest.mark.parametrize("cn2", [-1e-15, np.inf, np.nan])
    def test_a_structure_parameter_that_is_not_one_is_refused(self, cn2: float) -> None:
        with pytest.raises(DomainError, match="cn2_m23"):
            plane_wave_rytov_variance(1000.0, cn2_m23=cn2, wavelength_m=WAVELENGTH_M)


def ge1_key(
    path_m: float, receive_m: float, cn2: float, wave: PathWave
) -> tuple[LossBudget, KeyRate]:
    """Budget, noise and asymptotic BB84 key of one horizontal link, the recipe of the module."""
    log = DegradationLog()
    link = dict(GE1_BASE, transmit_aperture_m=0.025, receive_aperture_m=receive_m)
    budget = horizontal_loss_budget(path_m, wave=wave, cn2_m23=cn2, degradations=log, **link)
    noise = downlink_noise_budget(
        NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
        wavelength_m=WAVELENGTH_M,
        receive_aperture_m=receive_m,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
        gate_duration_s=1e-9,
        receiver_efficiency=float(GE1_BASE["receiver_efficiency"]),
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        detector_count=2,
        degradations=log,
    )
    conditions = LinkConditions(
        transmittance=budget.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=0.01,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=1e-9,
    )
    key = Bb84DecoyProtocol.ntanos_2021().key_rate(conditions, degradations=log)
    return budget, key


class TestTheHeadlineLensComparisonIsABracket:
    """The 2.5 cm to 10 cm comparison, with the regime of every row on the page.

    What was wrong with the way it was quoted
    ------------------------------------------
    ADR 0021 reported "56.8 to 636 kbit/s, a factor 11.2" for going from a
    2.5 cm receiving lens to a 10 cm one, and reported it as a number. Both rows
    were computed with ``PathWave.PLANE``, and both rows are at **3.16 Rayleigh
    ranges** of the 2.5 cm transmitter, where a plane wave is the wrong side of
    the idealisation — which the module's own
    ``horizontal.plane-wave-beyond-the-rayleigh-range`` warning said at the
    time, into a log nobody read.

    Note what the transmitter is doing here, because it is easy to misread the
    comparison as changing it: ``ge1_key`` holds the **transmitter** at 2.5 cm
    in both rows and varies the **receiving** lens. The Rayleigh range is a
    property of the transmitter alone, ``z_R = pi (D_T/2)^2 / lambda``, so it is
    316.7 m in both rows and ``L / z_R = 3.158`` in both. The two rows are the
    same regime, and it is not the regime they were computed in.

    What the honest version is
    --------------------------
    ============  =========  ==========  ============  ==============
    lens          `L/z_R`    plane       spherical     citable
    ============  =========  ==========  ============  ==============
    2.5 cm        3.158      56.8        **70.2**      spherical
    10 cm         3.158      636.2       **589.9**     spherical
    factor        —          11.20       **8.41**      8.41
    ============  =========  ==========  ============  ==============

    At 3.16 Rayleigh ranges the beam has spread to 3.3 times its waist, so the
    spherical column is the defensible one and the plane column is the other
    edge of the bracket. The true answer is the Gaussian beam wave, which is ADR
    0009 gap 18 and has no open source here, so what this module can say is: the
    lens is worth **a factor between 8.4 and 11.2**, and the 10 cm link makes
    **590 to 636 kbit/s**. An interval, not a number.

    Note also that the bracket is not ordered the way the point variances are.
    A spherical wave scintillates 2.46 times less at a point, but its irradiance
    correlation is wider, so a 10 cm lens averages it less well (Kaushal &
    Kaddoum's 0.214 against 1.07). At 2.5 cm the plane wave is the pessimistic
    edge and at 10 cm it is the optimistic one — which is exactly why a bracket
    has to be computed and cannot be reasoned about from the 2.46.
    """

    RAYLEIGH_RATIO = 3.158

    def test_the_rayleigh_range_is_the_transmitters_and_the_same_in_both_rows(self) -> None:
        """316.7 m for the 2.5 cm transmitter, so both rows sit at 3.16 z_R."""
        rayleigh_m = (
            rayleigh_range_km(wavelength_m=WAVELENGTH_M, transmit_aperture_m=0.025) * 1000.0
        )
        assert rayleigh_m == pytest.approx(316.7, abs=0.1)
        assert 1000.0 / rayleigh_m == pytest.approx(self.RAYLEIGH_RATIO, abs=0.001)

    def test_the_warning_fired_on_both_plane_rows_and_on_neither_spherical_one(self) -> None:
        """The module said so at the time, with the ratio in the details."""
        for receive_m in (0.025, 0.1):
            for wave, expected in ((PathWave.PLANE, 1), (PathWave.SPHERICAL, 0)):
                log = DegradationLog()
                horizontal_loss_budget(
                    1000.0,
                    wave=wave,
                    cn2_m23=1e-14,
                    degradations=log,
                    **dict(GE1_BASE, transmit_aperture_m=0.025, receive_aperture_m=receive_m),
                )
                codes = [entry.code for entry in log if entry.code.startswith("horizontal.")]
                assert len(codes) == expected, (receive_m, wave)
                if expected:
                    assert codes == ["horizontal.plane-wave-beyond-the-rayleigh-range"]
                    (entry,) = [e for e in log if e.code.startswith("horizontal.")]
                    assert entry.details["path_to_rayleigh_range_ratio"] == pytest.approx(
                        self.RAYLEIGH_RATIO, abs=0.001
                    )

    def test_the_lens_is_worth_a_factor_between_eight_and_eleven(self) -> None:
        """Both edges, and the statement that only the interval is citable."""
        rates = {
            (lens, wave): float(ge1_key(1000.0, lens, 1e-14, wave)[1].secure_bit_s)
            for lens in (0.025, 0.1)
            for wave in PathWave
        }
        assert rates[0.025, PathWave.PLANE] == pytest.approx(56_800.0, rel=1e-3)
        assert rates[0.025, PathWave.SPHERICAL] == pytest.approx(70_200.0, rel=1e-3)
        assert rates[0.1, PathWave.PLANE] == pytest.approx(636_200.0, rel=1e-3)
        assert rates[0.1, PathWave.SPHERICAL] == pytest.approx(589_900.0, rel=1e-3)
        plane = rates[0.1, PathWave.PLANE] / rates[0.025, PathWave.PLANE]
        spherical = rates[0.1, PathWave.SPHERICAL] / rates[0.025, PathWave.SPHERICAL]
        assert plane == pytest.approx(11.20, abs=0.02)
        assert spherical == pytest.approx(8.41, abs=0.02)

    def test_the_bracket_is_not_ordered_by_the_point_variance(self) -> None:
        """Plane is the worse edge at 2.5 cm and the better edge at 10 cm.

        The crossing is the whole reason the bracket has to be computed: a
        reader who knows only that a spherical wave scintillates 2.46 times less
        would predict the spherical column to be the optimistic one at both
        lenses, and would be wrong at one of them.
        """
        rates = {
            (lens, wave): float(ge1_key(1000.0, lens, 1e-14, wave)[1].secure_bit_s)
            for lens in (0.025, 0.1)
            for wave in PathWave
        }
        assert rates[0.025, PathWave.SPHERICAL] > rates[0.025, PathWave.PLANE]
        assert rates[0.1, PathWave.SPHERICAL] < rates[0.1, PathWave.PLANE]
        averaging = {
            wave: float(
                horizontal_aperture_averaging_factor(
                    1000.0, aperture_diameter_m=0.1, wavelength_m=WAVELENGTH_M, wave=wave
                )
            )
            for wave in PathWave
        }
        assert averaging[PathWave.SPHERICAL] > averaging[PathWave.PLANE]
        assert point_variance(1000.0, 1e-14, PathWave.SPHERICAL) < point_variance(1000.0, 1e-14)


class TestTheOperatingLimitsAreConstraintsAndNotNotes:
    """GE-1's two hard bounds, as functions with tests rather than sentences in an ADR."""

    def test_the_weak_theory_limit_is_the_crossing_it_claims(self) -> None:
        """V1 against the definition: the closed form and a root-find agree, 2413 m.

        The closed form inverts ``sigma_R^2 = 1.2285 C_n^2 k^(7/6) L^(11/6)``
        analytically; this checks it against the function it inverts, which is
        the only check that can catch a wrong exponent in the inverse.
        """
        limit_m = weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)
        assert limit_m == pytest.approx(2413.4, abs=0.1)
        assert float(
            plane_wave_rytov_variance(limit_m, cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)
        ) == pytest.approx(WEAK_FLUCTUATION_VARIANCE_LIMIT, rel=1e-12)

    def test_it_is_the_length_at_which_the_budget_starts_warning(self) -> None:
        """The constraint and the warning are the same boundary, checked from both sides.

        A limit that did not coincide with the code's own warning would be a
        second opinion, which is worse than no opinion: the number a design
        review quotes has to be the number the module enforces.
        """
        limit_m = weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)
        for length_m, warned in ((limit_m * 0.999, False), (limit_m * 1.001, True)):
            log = DegradationLog()
            horizontal_loss_budget(
                length_m,
                wave=PathWave.SPHERICAL,
                cn2_m23=1e-14,
                degradations=log,
                **dict(GE1_BASE, transmit_aperture_m=0.025),
            )
            codes = [e.code for e in log if e.code.endswith("weak-fluctuation-limit-exceeded")]
            assert bool(codes) is warned, length_m

    def test_quieter_air_buys_a_longer_path_only_as_the_six_elevenths(self) -> None:
        """A hundredfold drop in ``C_n^2`` buys a factor 12.3, not a factor 100.

        The design consequence, and the reason "pick a better site" is not an
        answer for a long horizontal link: the exponent that makes scintillation
        grow fast with distance is the same one that makes the usable distance
        grow slowly with site quality.
        """
        near = weak_theory_path_limit_m(cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)
        far = weak_theory_path_limit_m(cn2_m23=1e-16, wavelength_m=WAVELENGTH_M)
        assert far / near == pytest.approx(100.0 ** (6.0 / 11.0), rel=1e-12)
        assert far / near == pytest.approx(12.33, abs=0.01)

    def test_the_bench_equivalence_is_an_identity_and_not_an_estimate(self) -> None:
        """8.87e-10 over 2 m has exactly the Rytov variance of 1e-14 over 1 km."""
        required = equivalent_bench_cn2_m23(bench_length_m=2.0, path_length_m=1000.0, cn2_m23=1e-14)
        assert required == pytest.approx(8.874e-10, rel=1e-3)
        assert float(
            plane_wave_rytov_variance(2.0, cn2_m23=required, wavelength_m=WAVELENGTH_M)
        ) == pytest.approx(
            float(plane_wave_rytov_variance(1000.0, cn2_m23=1e-14, wavelength_m=WAVELENGTH_M)),
            rel=1e-12,
        )

    def test_folding_the_bench_is_the_only_cheap_lever(self) -> None:
        """Five times the bench length is 19.1 times less ``C_n^2`` needed.

        The number GE-0b's design turns on. Nothing else in the expression is
        available: ``C_n^2(path)`` is the experiment being stood in for and the
        exponent is the physics, so the length of the folded path is the whole
        design space.
        """
        two = equivalent_bench_cn2_m23(bench_length_m=2.0, path_length_m=1000.0, cn2_m23=1e-14)
        ten = equivalent_bench_cn2_m23(bench_length_m=10.0, path_length_m=1000.0, cn2_m23=1e-14)
        assert two / ten == pytest.approx(5.0 ** (11.0 / 6.0), rel=1e-12)
        assert two / ten == pytest.approx(19.12, abs=0.02)

    @pytest.mark.parametrize("cn2", [0.0, -1e-14, np.nan, np.inf])
    def test_a_path_limit_needs_turbulence_to_exist(self, cn2: float) -> None:
        with pytest.raises(DomainError, match="cn2_m23"):
            weak_theory_path_limit_m(cn2_m23=cn2, wavelength_m=WAVELENGTH_M)

    def test_neither_limit_broadcasts(self) -> None:
        """A limit is one number, and an array of them would be a table nobody asked for."""
        with pytest.raises(DomainError, match="take scalars"):
            equivalent_bench_cn2_m23(
                bench_length_m=2.0,
                path_length_m=1000.0,
                cn2_m23=np.array([1e-14, 1e-15]),  # type: ignore[arg-type]
            )


class TestTheSaturatedRegimeOnAHorizontalPath:
    """Stage 1.2 inherited here, and the two GE-1 figures it changes.

    The saturation model lives in :mod:`quoss.channel.turbulence` and is reached
    from both budgets through their own ``regime`` argument
    (``ScintillationRegime``). What it changes on a horizontal path is
    everything past ``weak_theory_path_limit_m`` — which for GE-1's design case
    is everything past 2.41 km.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG

    @staticmethod
    def _scintillation_db(path_m: float, wave: PathWave, regime: ScintillationRegime) -> float:
        budget = horizontal_loss_budget(
            path_m,
            wave=wave,
            cn2_m23=1e-14,
            degradations=DegradationLog(),
            regime=regime,
            **dict(GE1_BASE, transmit_aperture_m=0.025, receive_aperture_m=0.05),
        )
        return float(budget.scintillation_db)

    def test_the_default_is_weak_everywhere_it_is_offered(self) -> None:
        """Three signatures, one default, and it is the recommendation."""
        for function in (
            horizontal_point_log_irradiance_variance,
            horizontal_log_irradiance_variance,
            horizontal_loss_budget,
        ):
            assert (
                inspect.signature(function).parameters["regime"].default is ScintillationRegime.WEAK
            )

    def test_nothing_changes_below_the_weak_theory_limit(self) -> None:
        """At 1 km the two regimes agree to 0.16 dB, which is the model being the identity.

        The bound is not a tolerance: at ``sigma_R^2 = 0.199`` the saturated
        log-variance is 0.884 of the Rytov one, and a fade allowance goes as
        roughly ``sqrt(variance)``, so 6 % of 1.1 dB is what it has to be.
        """
        for wave in PathWave:
            weak = self._scintillation_db(1000.0, wave, ScintillationRegime.WEAK)
            saturated = self._scintillation_db(1000.0, wave, self.SATURATED)
            assert 0.0 < weak - saturated < 0.16, wave

    def test_the_wave_choice_at_five_kilometres_was_mostly_the_weak_model(self) -> None:
        """21.73 against 15.06 dB becomes 8.41 against 9.94, and the sign flips.

        ADR 0021 quotes the 6.67 dB spread as what the plane-against-spherical
        choice is worth, and it is the largest single number in that ADR. Under
        the saturated model the spread is 1.53 dB and the *other way round*: at
        5 km the plane wave's Rytov variance is 3.80 Np^2 and the spherical
        one's is 1.55, so saturation removes far more from the plane wave, and
        what is left is the aperture averaging, which favours the plane wave.

        So most of that 6.67 dB was the weak model being evaluated four times
        past its own limit, not a real cost of not knowing the beam. It does not
        make the Gaussian-beam gap (ADR 0009 gap 18) go away — 1.53 dB is still
        1.53 dB — but it does mean the gap was being quoted at four times its
        size.
        """
        weak = {
            wave: self._scintillation_db(5000.0, wave, ScintillationRegime.WEAK)
            for wave in PathWave
        }
        saturated = {
            wave: self._scintillation_db(5000.0, wave, self.SATURATED) for wave in PathWave
        }
        assert weak[PathWave.PLANE] == pytest.approx(21.73, abs=0.01)
        assert weak[PathWave.SPHERICAL] == pytest.approx(15.06, abs=0.01)
        assert saturated[PathWave.PLANE] == pytest.approx(8.41, abs=0.01)
        assert saturated[PathWave.SPHERICAL] == pytest.approx(9.94, abs=0.01)
        assert weak[PathWave.PLANE] - weak[PathWave.SPHERICAL] == pytest.approx(6.67, abs=0.02)
        assert saturated[PathWave.SPHERICAL] - saturated[PathWave.PLANE] == pytest.approx(
            1.53, abs=0.02
        )

    def test_the_two_cells_p1814_should_not_have_printed_are_five_decibels_out(self) -> None:
        """Its "High" column, measured against the saturated model instead of asserted.

        ``TestPublishedItuP1814Table4`` reproduces 12.25 and 16.00 dB from
        equation (8) and says in prose that the recommendation should not have
        printed them. This puts a number on "should not": the saturated model
        gives 7.19 and 7.57 dB for the same two cells, so the printed values are
        5.06 and 8.43 dB of fade that is not there. V4 against V2 — the
        published number is the one being doubted, so this cannot be a V2 check,
        and saying which is which is the point.
        """
        for wavelength_m, printed_db, saturated_db in (
            (1.55e-6, 12.25, 7.19),
            (0.98e-6, 16.00, 7.57),
        ):
            rytov = float(
                plane_wave_rytov_variance(1000.0, cn2_m23=1e-13, wavelength_m=wavelength_m)
            )
            variance = float(saturated_log_irradiance_variance(rytov, wave=PathWave.PLANE))
            depth_db = 2.0 * float(np.sqrt(variance * NEPER_SQ_TO_DB_SQ))
            assert depth_db == pytest.approx(saturated_db, abs=0.01)
            assert printed_db - depth_db > 5.0

    def test_the_saturated_branch_says_which_model_ran(self) -> None:
        """A different code from the weak branch's, carrying both values and the ratio."""
        log = DegradationLog()
        horizontal_loss_budget(
            5000.0,
            wave=PathWave.PLANE,
            cn2_m23=1e-14,
            degradations=log,
            regime=self.SATURATED,
            **dict(GE1_BASE, transmit_aperture_m=0.025),
        )
        codes = [entry.code for entry in log if entry.code.startswith("horizontal.")]
        assert "horizontal.scintillation-saturated" in codes
        assert "horizontal.weak-fluctuation-limit-exceeded" not in codes
        (entry,) = [e for e in log if e.code == "horizontal.scintillation-saturated"]
        assert entry.severity is Severity.WARNING
        assert entry.details["weak_variance_np2"] == pytest.approx(3.802, abs=1e-3)
        assert entry.details["peak_variance_np2"] == pytest.approx(0.7707, abs=1e-3)
        assert entry.details["wave"] == "plane"


class TestSizingTheGroundExperiments:
    """What to decide for GE-1 before buying anything, on `GE1_BASE` and a 2.5 cm transmitter.

    Every rate here is the **asymptotic** BB84 rate at the 1 %-outage
    transmittance — what the link delivers 99 % of the time, not its mean, and
    before the finite-key cost of a real block. Night sky, the Ntanos et al.
    receiver, 1 % misalignment.
    """

    def test_the_receiver_aperture_is_the_lever_at_one_kilometre(self) -> None:
        """At 1 km in moderate turbulence, 2.5 cm to 10 cm of lens is a factor 11 in key.

        Two effects at once, and the budget shows which is which: the geometric
        term falls from 7.78 to 0.24 dB because the beam fits, and the
        scintillation allowance from 3.80 to 1.12 dB because the lens averages
        seventeen times more speckle. V4.
        """
        small_budget, small = ge1_key(1000.0, 0.025, 1e-14, PathWave.PLANE)
        large_budget, large = ge1_key(1000.0, 0.1, 1e-14, PathWave.PLANE)
        assert float(small_budget.geometric_db) == pytest.approx(7.78, abs=0.01)
        assert float(large_budget.geometric_db) == pytest.approx(0.24, abs=0.01)
        assert float(small_budget.scintillation_db) == pytest.approx(3.80, abs=0.01)
        assert float(large_budget.scintillation_db) == pytest.approx(1.12, abs=0.01)
        assert float(large.secure_bit_s) / float(small.secure_bit_s) == pytest.approx(11.2, abs=0.1)

    def test_the_key_falls_with_distance_and_rises_with_aperture_everywhere(self) -> None:
        """V1 over the grid a design review would draw: 200 m to 5 km, 2.5 to 20 cm, three skies."""
        paths = (200.0, 500.0, 1000.0, 2000.0, 5000.0)
        lenses = (0.025, 0.05, 0.1, 0.2)
        for cn2 in (1e-15, 1e-14):
            rates = np.array(
                [
                    [
                        float(ge1_key(path, lens, cn2, PathWave.PLANE)[1].secure_bit_s)
                        for lens in lenses
                    ]
                    for path in paths
                ]
            )
            assert np.all(np.diff(rates, axis=0) <= 0.0)
            assert np.all(np.diff(rates, axis=1) >= 0.0)

    def test_the_qber_is_not_what_limits_this_link(self) -> None:
        """Wherever the link still makes 2 kbit/s, the QBER is below 1.2 %, against a 1 % floor.

        The floor is the misalignment; noise at night through a 100 µrad field
        of view is orders of magnitude below the signal. So the design variable
        is the loss — and its fade allowance — not the error rate, until the
        link is nearly lost. Measured over the grid, the worst such cell is
        5 km with a 10 cm lens in moderate turbulence: 4.0 kbit/s at 1.11 %. V4.
        """
        for cn2 in (1e-15, 1e-14, 1e-13):
            for path in (200.0, 500.0, 1000.0, 2000.0, 5000.0):
                for lens in (0.025, 0.05, 0.1, 0.2):
                    _, key = ge1_key(path, lens, cn2, PathWave.PLANE)
                    if float(key.secure_bit_s) > 2e3:
                        assert 0.01 <= float(key.qber) < 0.012, (cn2, path, lens)

    def test_where_moderate_turbulence_leaves_the_weak_theory(self) -> None:
        """At ``C_n^2 = 1e-14``, 1550 nm, the Rytov variance reaches 1 at 2.41 km.

        ``L* = 1000 (1 / 0.1988)^(6/11)`` m. Past it every number in the budget
        carries the weak-fluctuation warning, so a GE-1 longer than that is one
        this module can dimension only until stage 1.2 exists.
        """
        crossing_m = 1000.0 * (1.0 / point_variance(1000.0, 1e-14)) ** (6.0 / 11.0)
        assert crossing_m == pytest.approx(2414.0, abs=1.0)
        assert point_variance(crossing_m, 1e-14) == pytest.approx(1.0, rel=1e-9)

    def test_the_wave_choice_is_worth_several_decibels_at_five_kilometres(self) -> None:
        """Plane against spherical at 5 km, 5 cm lens, moderate sky: 21.7 against 15.1 dB of fade.

        The two idealisations bracket the Gaussian beam the transmitter really
        emits, and a design that closes only under the spherical one has not
        closed. V4, and outside the weak theory on both sides — which the
        warnings say.
        """
        plane, _ = ge1_key(5000.0, 0.05, 1e-14, PathWave.PLANE)
        spherical, _ = ge1_key(5000.0, 0.05, 1e-14, PathWave.SPHERICAL)
        assert float(plane.scintillation_db) == pytest.approx(21.73, abs=0.01)
        assert float(spherical.scintillation_db) == pytest.approx(15.06, abs=0.01)

    def test_what_a_bench_emulator_has_to_reach(self) -> None:
        """A two-metre emulator matching 1 km of moderate air needs ``C_n^2 = 8.9e-10``.

        ``(1000 / 2)^(11/6) = 8.87e4``: the Rytov variance of a path grows as
        its length to the 11/6, so the same variance over a path 500 times
        shorter needs air 88 700 times more turbulent — nine orders of magnitude
        above the ``1e-16`` of a quiet night, and the number an emulator's
        characterisation has to reach before GE-0b stands in for GE-1.
        """
        required = 1e-14 * (1000.0 / 2.0) ** (11.0 / 6.0)
        assert required == pytest.approx(8.87e-10, rel=1e-3)
        assert point_variance(2.0, required) == pytest.approx(
            point_variance(1000.0, 1e-14), rel=1e-12
        )
