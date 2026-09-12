"""Tests for `quoss.channel.link_budget`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestAgainstNtanosEtAl`` — **V2**, and the least comfortable one in the
  package. Their equations (7) and (18) are transcribed here from the paper and
  reproduce exactly. Their §4.2.1 headline — "the total link loss for a 600 km
  link distance can get as low as 20 dB in total" — does **not**: every term
  they list, computed from the parameters they declare and combined the way they
  combine them, sums to 15.741 dB. The class measures the 4.259 dB residual and
  states what closing it would require, rather than adjusting anything until it
  agrees.
- ``TestTwoOnePerCentAllowancesAreNotOnePerCent`` — the module's headline, at
  three levels at once. **V1**: the closed-form joint quantile is checked
  against a Monte Carlo of the two physical processes — Gaussian jitter in two
  axes through the pointing law, lognormal irradiance through the fade law.
  **V3**: the exponentially modified Gaussian is inverted by bisection and
  verified by re-evaluating its own distribution function at the answer.
  **V2**: the additive convention is the published one, and the class prices it.
- ``TestTheFadeLawsAreClosedForm`` — **V1**. That the pointing fade in dB is
  exactly exponential and the scintillation fade in dB is exactly Gaussian is
  what makes the class above possible, so both are checked against the
  distributions the physics modules define rather than assumed.
- ``TestTheReceiverChainIsCountedOnce`` — the trap the module is shaped around,
  measured: the two transmittances differ by exactly the chain, the two routes
  to a detected count agree, and mixing them costs 6.36 dB.
- ``TestAirMass`` — **V3**. The secant of equation (7) against an independent
  spherical-shell geometry, and the 5 % limit re-solved with a root finder
  instead of trusted from the constant.
- ``TestNoiseBudget`` — **V1** against ``channel/detector.py``'s own published
  table, including the 0.94 dB the natural mistake hides, and the inversion
  between a sky-limited and a dark-count-limited receiver.
- ``TestScalingLaws`` / ``TestRejectsBadInput`` / ``TestModuleSurface``.

Not reproduced, and declared:

- **Atmospheric extinction.** No source verified for this project publishes a
  zenith transmittance at 1550 nm: ITU-R P.1621-2 gives absorption and
  scattering as Figures 1, 2 and 4 and as nothing else, and Ntanos et al. cite a
  reference for equation (7) without stating the number it scales. Every test
  here that needs one either passes ``1.0`` and says so or solves for the value
  a published claim would imply.
- **Uplink.** No uplink budget exists to test. Beam wander is a third fade with
  a different distribution, and gap 7 of ``docs/adr/0009-citation-policy.md``
  records that no verified source publishes the radiance of a sunlit Earth.
- **Anything per pass.** Both fades are marginal quantiles at an instant. The
  number of *consecutive* gates a fade costs needs the temporal correlation of
  ``system/correlated_fading.py``, and a test asserting a key per pass from
  these numbers would be asserting independence that nobody has established.
"""

from __future__ import annotations

import ast
import inspect
import re
from itertools import pairwise

import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.special import erfinv

from quoss.channel.background import (
    NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    SkyCondition,
    tabulated_sky_radiance_w_m2_um_sr,
)
from quoss.channel.beam import divergence_half_angle_rad, geometric_transmittance
from quoss.channel.detector import (
    LIM_INGAAS_AFTERPULSE_PROBABILITY,
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
    click_probability,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    DB_PER_NEPER,
    GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE,
    NTANOS_BEST_CASE_TOTAL_LOSS_DB,
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_MINIMUM_ELEVATION_RAD,
    NTANOS_OGS_APERTURES_M,
    NTANOS_ORBIT_HEIGHT_KM,
    NTANOS_OUTAGE_PROBABILITY,
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_POLARISATION_LOSS_DB,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    SECANT_AIRMASS_ELEVATION_LIMIT_RAD,
    FadeCombination,
    LossBudget,
    NoiseBudget,
    _spherical_shell_airmass,
    additive_fade_outage_probability,
    atmospheric_transmittance,
    combined_fade_db,
    downlink_loss_budget,
    downlink_noise_budget,
    gaussian_truncation_efficiency,
    pointing_fade_db,
    scintillation_fade_db,
    secant_airmass,
)
from quoss.channel.pointing import beam_to_jitter_ratio, pointing_transmittance
from quoss.channel.turbulence import downlink_log_irradiance_variance
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.core.units import deg_to_rad, transmittance_to_loss_db

WAVELENGTH_M = 1.55e-6
"""1550 nm, the wavelength of Ntanos et al. §4.1 and of this repo's reference link."""

GATE_S = 1e-9
"""The 1 ns detection gate of Ntanos et al. §4.1."""

REFERENCE_APERTURE_M = NTANOS_OGS_APERTURES_M[0]
"""The 0.75 m Cholomondas telescope: the smallest of the three, and the one the
module docstring's fade table is measured on."""


def chain_efficiency() -> float:
    """Return the 6.36 dB receiver chain of Ntanos et al. §4.1 as a linear factor."""
    return receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )


def reference_gamma(receive_aperture_m: float = REFERENCE_APERTURE_M) -> float:
    """Return the beam-to-jitter ratio of the reference downlink."""
    return float(
        beam_to_jitter_ratio(
            NTANOS_ORBIT_HEIGHT_KM,
            jitter_rad=NTANOS_POINTING_JITTER_RAD,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=receive_aperture_m,
            degradations=DegradationLog(),
        )
    )


def reference_variance(
    elevation_rad: float, receive_aperture_m: float = REFERENCE_APERTURE_M
) -> float:
    """Return the downlink log-irradiance variance of the reference geometry, Np^2."""
    return float(
        downlink_log_irradiance_variance(
            elevation_rad,
            aperture_diameter_m=receive_aperture_m,
            wavelength_m=WAVELENGTH_M,
            degradations=DegradationLog(),
        )
    )


def published_scintillation_level_db(
    scintillation_index: float, outage_probability: float
) -> float:
    """Ntanos et al. equation (18), transcribed from the paper exactly as printed.

    ``L_sci(dB) = 4.343 x [erf^-1(2 p_0 - 1) . [2 ln(sigma^2_I + 1)]^(1/2)
    - (1/2) ln(sigma^2_I + 1)]``

    Kept verbatim, sign and all, so that the module's departure from it is a
    difference between two expressions in this file rather than an assertion
    about one.
    """
    log_variance = np.log(scintillation_index + 1.0)
    return 4.343 * (
        erfinv(2.0 * outage_probability - 1.0) * np.sqrt(2.0 * log_variance) - 0.5 * log_variance
    )


class TestAgainstNtanosEtAl:
    """**V2** against Ntanos et al. 2021, *Photonics* 8(12):544."""

    def test_the_published_parameters_are_transcribed(self) -> None:
        assert NTANOS_TRANSMIT_APERTURE_M == 0.15
        assert NTANOS_OGS_APERTURES_M == (0.75, 1.3, 2.3)
        assert NTANOS_POINTING_JITTER_RAD == 0.75e-6
        assert NTANOS_OUTAGE_PROBABILITY == 0.01
        assert NTANOS_POLARISATION_LOSS_DB == 0.3
        assert NTANOS_RECEIVER_FIELD_OF_VIEW_RAD == 100e-6
        assert NTANOS_FILTER_BANDWIDTH_M == 0.2e-9
        assert NTANOS_ORBIT_HEIGHT_KM == 600.0
        assert NTANOS_BEST_CASE_TOTAL_LOSS_DB == 20.0
        assert np.degrees(NTANOS_MINIMUM_ELEVATION_RAD) == pytest.approx(20.0)

    def test_their_13_microradian_divergence_is_the_full_angle(self) -> None:
        """§4.1: "an aperture of 0.15 m [...] providing a small beam divergence of about 13 urad".

        Their equation (6) is ``w_0 = 2 lambda / (pi D_t)``, a half angle, which
        is 6.58 urad here. The 13 urad they quote is therefore the full angle,
        and reading it as the half angle would halve every beam radius in the
        budget — 6 dB of geometric loss that is not there.
        """
        half = divergence_half_angle_rad(
            wavelength_m=WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
        )
        assert half == pytest.approx(2.0 * WAVELENGTH_M / (np.pi * NTANOS_TRANSMIT_APERTURE_M))
        assert 2.0 * half * 1e6 == pytest.approx(13.0, abs=0.2)

    def test_equation_7_is_beer_lambert_in_the_exponent(self) -> None:
        """Their ``L_a = L_zen^(1/cos zeta)``, transcribed and compared term by term."""
        elevation = deg_to_rad(np.array([90.0, 60.0, 30.0, 20.0]))
        zenith = 0.8
        published = zenith ** (1.0 / np.cos(0.5 * np.pi - elevation))
        ours = atmospheric_transmittance(
            elevation, zenith_transmittance=zenith, degradations=DegradationLog()
        )
        assert ours == pytest.approx(published, rel=1e-15)

        # And the reason the exponent is where the elevation goes: in decibels
        # the law is exactly linear in air mass.
        loss = np.asarray(transmittance_to_loss_db(ours))
        assert loss == pytest.approx(
            float(transmittance_to_loss_db(zenith)) * np.asarray(secant_airmass(elevation)),
            rel=1e-12,
        )

    def test_equation_18_reproduces_and_its_sign_is_a_gain(self) -> None:
        """**V2**, and the sign is the finding.

        Equation (18) is ``10 log10`` of the ``p_0`` quantile of the irradiance,
        so for any outage below the median crossing it is negative: it is the
        signal *level* relative to the mean, not the drop from it. The module
        returns the drop, and the two are the same number negated.
        """
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        # The paper's argument is the scintillation index; ours is the
        # log-variance. Invert their conversion so the two expressions are
        # asked about the same physical turbulence.
        scintillation_index = np.expm1(variance)

        published = published_scintillation_level_db(scintillation_index, 0.01)
        ours = float(scintillation_fade_db(variance, outage_probability=0.01))

        assert published < 0.0
        assert ours == pytest.approx(-published, rel=2e-4)
        assert ours == pytest.approx(1.282, abs=5e-4)

    def test_adding_equation_18_as_printed_costs_twice_the_fade(self) -> None:
        """The cost of the sign, in the only unit that matters: total link loss."""
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        fade = float(scintillation_fade_db(variance, outage_probability=0.01))
        as_printed = published_scintillation_level_db(np.expm1(variance), 0.01)
        assert fade - as_printed == pytest.approx(2.0 * fade, rel=2e-4)

    def test_the_log_variance_is_not_a_scintillation_index(self) -> None:
        """Applying ``ln(sigma^2 + 1)`` to a quantity that is already a log-variance.

        ITU-R P.1622 equation (4b) computes ``sigma^2_lnI`` directly, so
        ``quoss.channel.turbulence`` returns it; equation (18) is written for the
        scintillation index and converts internally. Doing the conversion twice
        is invisible where this link operates and not invisible at the edge of
        the theory that produced the number.
        """
        reference = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        assert reference == pytest.approx(0.01528, abs=5e-6)

        correct = float(scintillation_fade_db(reference, outage_probability=0.01))
        twice_converted = float(scintillation_fade_db(np.log1p(reference), outage_probability=0.01))
        assert correct - twice_converted == pytest.approx(0.005, abs=5e-4)

        # At the weak-fluctuation limit of turbulence.WEAK_FLUCTUATION_VARIANCE_LIMIT.
        at_limit = float(scintillation_fade_db(1.0, outage_probability=0.01))
        at_limit_twice = float(scintillation_fade_db(np.log1p(1.0), outage_probability=0.01))
        assert at_limit - at_limit_twice == pytest.approx(2.36, abs=0.01)

    def test_their_twenty_decibel_best_case_does_not_reproduce(self) -> None:
        """**V2 that fails**, and the number by which.

        §4.2.1: "the total link loss for a 600 km link distance can get as low
        as 20 dB in total. To achieve this loss performance, a large enough
        telescope in the receiver is required." Built from their own §4.1
        parameters — 0.15 m transmitter, 2.3 m receiver, 600 km at zenith,
        0.75 urad jitter at 1 % outage, 85 % nanowires behind a 3 dB filter and
        2.65 dB of receiver optics, 0.3 dB polarisation — and combined their
        way, every term sums to 15.741 dB.

        Plus one term their equations do not have and this module does: the
        3.352 dB the untruncated Gaussian far field of ``beam.py`` overstates
        for a transmitter that clips its own beam at the waist radius. With it,
        19.094 dB.

        The residual is 0.906 dB, which read through their equation (7) is
        ``L_zen = 0.812`` — an ordinary clear-sky zenith transmittance at
        1550 nm. So the 20 dB is **consistent with** this budget plus an
        unstated extinction of a plausible size, and that is the whole claim: a
        residual landing in a plausible range is not evidence that it is the
        thing it resembles, and the paper states no extinction anywhere.

        Worth reading together with the assertion below it: without the
        truncation term the residual is 4.259 dB, which would need
        ``L_zen = 0.375``, an order of magnitude more extinction than anything
        credible at this wavelength. The missing decibels were in the
        transmitter, not in the atmosphere.
        """
        log = DegradationLog()
        budget = downlink_loss_budget(
            0.5 * np.pi,
            range_km=NTANOS_ORBIT_HEIGHT_KM,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=NTANOS_OGS_APERTURES_M[2],
            zenith_transmittance=1.0,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
            static_loss_db=NTANOS_POLARISATION_LOSS_DB,
            fade_combination=FadeCombination.ADDITIVE,
            degradations=log,
        )
        assert float(budget.total_db) == pytest.approx(19.094, abs=1e-3)
        assert budget.truncation_db == pytest.approx(3.352, abs=1e-3)

        residual = NTANOS_BEST_CASE_TOTAL_LOSS_DB - float(budget.total_db)
        assert residual == pytest.approx(0.906, abs=1e-3)
        implied_zenith_transmittance = 10.0 ** (-residual / 10.0)
        assert implied_zenith_transmittance == pytest.approx(0.812, abs=1e-3)

        # Without the transmitter term, the same residual would demand an
        # extinction nobody could defend. This is the assertion that says which
        # of the two findings is doing the work.
        without_truncation = float(budget.total_db) - budget.truncation_db
        assert without_truncation == pytest.approx(15.741, abs=1e-3)
        assert NTANOS_BEST_CASE_TOTAL_LOSS_DB - without_truncation == pytest.approx(4.259, abs=1e-3)
        assert 10.0 ** (-(NTANOS_BEST_CASE_TOTAL_LOSS_DB - without_truncation) / 10.0) == (
            pytest.approx(0.375, abs=1e-3)
        )

        # And the residual is not the fade convention: choosing the defensible
        # combination rule moves the total by less than a fifteenth of it.
        exact = downlink_loss_budget(
            0.5 * np.pi,
            range_km=NTANOS_ORBIT_HEIGHT_KM,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=NTANOS_OGS_APERTURES_M[2],
            zenith_transmittance=1.0,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            static_loss_db=NTANOS_POLARISATION_LOSS_DB,
            degradations=log,
        )
        # And the residual is not the fade convention: at zenith the two
        # combination rules differ by 0.067 dB, a thirteenth of it.
        convention = float(budget.total_db) - float(exact.total_db)
        assert convention == pytest.approx(0.067, abs=1e-3)
        assert convention < residual / 10.0

    def test_the_four_terms_of_their_budget_add_to_the_total(self) -> None:
        """A budget whose parts do not add up to its whole is not a budget."""
        log = DegradationLog()
        budget = downlink_loss_budget(
            NTANOS_MINIMUM_ELEVATION_RAD,
            range_km=1500.0,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            static_loss_db=NTANOS_POLARISATION_LOSS_DB,
            degradations=log,
        )
        parts = (
            float(budget.geometric_db)
            + budget.truncation_db
            + float(budget.atmospheric_db)
            + float(budget.fade_db)
            + budget.receiver_chain_db
            + budget.static_db
        )
        assert parts == pytest.approx(float(budget.total_db), rel=1e-14)
        # The two marginal fades are reported for review and are *not* in the sum.
        assert float(budget.pointing_db) + float(budget.scintillation_db) > float(budget.fade_db)

    def test_their_elevation_floor_is_where_the_secant_still_holds(self) -> None:
        """20 degrees: the flat-slab air mass is 0.50 % high there, so the gap costs nothing."""
        secant = float(secant_airmass(NTANOS_MINIMUM_ELEVATION_RAD))
        spherical = float(_spherical_shell_airmass(NTANOS_MINIMUM_ELEVATION_RAD))
        assert secant / spherical - 1.0 == pytest.approx(0.0050, abs=1e-4)
        assert NTANOS_MINIMUM_ELEVATION_RAD > SECANT_AIRMASS_ELEVATION_LIMIT_RAD


class TestTwoOnePerCentAllowancesAreNotOnePerCent:
    """The module's headline, checked against a simulation of the two processes."""

    @staticmethod
    def _sampled_fades(
        gamma: float, variance: float, size: int, seed: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return ``(pointing_db, scintillation_db)`` sampled from the physics, not the law.

        The pointing sample goes through
        :func:`quoss.channel.pointing.pointing_transmittance` from a radial
        offset built out of two independent Gaussian axes, which is the process
        the power law is derived from rather than the power law itself. The
        scintillation sample is the mean-normalised lognormal of Ntanos et al.
        equation (17).
        """
        source = RandomSource.from_seed(seed)
        jitter = NTANOS_POINTING_JITTER_RAD
        axes = source.generator.normal(0.0, jitter, size=(2, size))
        offset = np.hypot(axes[0], axes[1])
        kept = pointing_transmittance(
            offset,
            range_km=NTANOS_ORBIT_HEIGHT_KM,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            degradations=DegradationLog(),
        )
        irradiance = np.exp(source.generator.normal(-0.5 * variance, np.sqrt(variance), size=size))
        assert gamma > 0.0
        return -10.0 * np.log10(kept), -10.0 * np.log10(irradiance)

    def test_the_documented_table(self) -> None:
        """The six rows of the module docstring, at both outage probabilities."""
        gamma = reference_gamma()
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        expected = {
            0.01: (1.030, 1.282, 2.312, 1.668, 0.644, 6.59e-4),
            0.001: (1.545, 1.692, 3.237, 2.217, 1.020, 1.07e-5),
        }
        for outage, row in expected.items():
            point = float(pointing_fade_db(gamma, outage_probability=outage))
            scint = float(scintillation_fade_db(variance, outage_probability=outage))
            joint = float(
                combined_fade_db(
                    beam_to_jitter_ratio_value=gamma,
                    log_irradiance_variance_np2=variance,
                    outage_probability=outage,
                )
            )
            effective = float(
                additive_fade_outage_probability(
                    beam_to_jitter_ratio_value=gamma,
                    log_irradiance_variance_np2=variance,
                    outage_probability=outage,
                )
            )
            assert point == pytest.approx(row[0], abs=1e-3)
            assert scint == pytest.approx(row[1], abs=1e-3)
            assert point + scint == pytest.approx(row[2], abs=1e-3)
            assert joint == pytest.approx(row[3], abs=1e-3)
            assert point + scint - joint == pytest.approx(row[4], abs=1e-3)
            assert effective == pytest.approx(row[5], rel=1e-2)

    def test_the_one_per_cent_budget_is_really_a_fifteenth_of_a_per_cent(self) -> None:
        """The finding in the unit a design review uses."""
        effective = float(
            additive_fade_outage_probability(
                beam_to_jitter_ratio_value=reference_gamma(),
                log_irradiance_variance_np2=reference_variance(NTANOS_MINIMUM_ELEVATION_RAD),
                outage_probability=0.01,
            )
        )
        assert 0.01 / effective == pytest.approx(15.2, abs=0.1)

    @pytest.mark.physics
    def test_the_joint_quantile_matches_a_simulation_of_both_processes(self) -> None:
        """**V1**: 4e6 samples of jitter and turbulence, at two outage levels.

        The tolerance is derived, not chosen: the standard error of an empirical
        quantile is ``sqrt(p (1-p) / n) / f(q)``, and the density ``f`` at the
        1 % point is estimated here from the sample itself rather than from the
        model being tested.
        """
        gamma = reference_gamma()
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        size = 4_000_000
        point, scint = self._sampled_fades(gamma, variance, size, seed=20260912)
        total = point + scint

        for outage in (0.01, 0.001):
            predicted = float(
                combined_fade_db(
                    beam_to_jitter_ratio_value=gamma,
                    log_irradiance_variance_np2=variance,
                    outage_probability=outage,
                )
            )
            measured = float(np.quantile(total, 1.0 - outage))
            # Local density from the sample: how wide a window holds 1 % of the
            # points around the quantile.
            window = float(
                np.quantile(total, min(1.0 - outage + 0.005, 1.0))
                - np.quantile(total, 1.0 - outage - 0.005)
            )
            density = 0.01 / window
            standard_error = np.sqrt(outage * (1.0 - outage) / size) / density
            assert abs(measured - predicted) < 4.0 * standard_error

    @pytest.mark.physics
    def test_the_additive_allowance_is_exceeded_as_rarely_as_claimed(self) -> None:
        """**V1**: the 0.066 %, counted rather than computed."""
        gamma = reference_gamma()
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        size = 4_000_000
        point, scint = self._sampled_fades(gamma, variance, size, seed=20260913)
        allowance = float(pointing_fade_db(gamma, outage_probability=0.01)) + float(
            scintillation_fade_db(variance, outage_probability=0.01)
        )
        measured = float(np.mean(point + scint > allowance))
        predicted = float(
            additive_fade_outage_probability(
                beam_to_jitter_ratio_value=gamma,
                log_irradiance_variance_np2=variance,
                outage_probability=0.01,
            )
        )
        standard_error = np.sqrt(predicted * (1.0 - predicted) / size)
        assert abs(measured - predicted) < 4.0 * standard_error

    @pytest.mark.physics
    def test_adding_quantiles_is_conservative_everywhere(self) -> None:
        """A property, over a grid, because one measured case is an anecdote.

        Both fades are non-negative-tailed and independent, so the sum of the
        marginal quantiles always exceeds the quantile of the sum. Two special
        cases fall out of the same grid and are worth naming: with no turbulence
        the scintillation allowance vanishes and the two rules coincide, and the
        gap grows with the *smaller* of the two terms rather than with either
        one alone.
        """
        for gamma_sq in (5.0, 19.42, 60.0):
            for variance in (0.0, 1e-4, 0.0153, 0.3, 1.0):
                for outage in (0.2, 0.01, 1e-4):
                    gamma = np.sqrt(gamma_sq)
                    additive = float(pointing_fade_db(gamma, outage_probability=outage)) + float(
                        scintillation_fade_db(variance, outage_probability=outage)
                    )
                    joint = float(
                        combined_fade_db(
                            beam_to_jitter_ratio_value=gamma,
                            log_irradiance_variance_np2=variance,
                            outage_probability=outage,
                        )
                    )
                    if variance == 0.0:
                        assert additive == pytest.approx(joint, abs=1e-9)
                    else:
                        assert additive > joint

    def test_the_bisection_converges_to_its_own_definition(self) -> None:
        """**V3**: the returned level put back through the distribution function.

        Independent of the physics: whatever the module claims the joint
        quantile is, evaluating the exponentially modified Gaussian there must
        return ``1 - p``. This is the check that would catch a wrong bracket, a
        loop count too small, or a sign slip inside the exponent.
        """
        from quoss.channel.link_budget import _emg_cdf, _fade_distribution_parameters

        gamma = np.array([2.0, 4.407, 8.0])
        variance = np.array([1e-6, 0.0153, 0.5])
        mean, sd, rate = _fade_distribution_parameters(gamma, variance)
        for outage in (0.5, 0.01, 1e-6, 1e-12):
            level = combined_fade_db(
                beam_to_jitter_ratio_value=gamma,
                log_irradiance_variance_np2=variance,
                outage_probability=outage,
            )
            assert _emg_cdf(level, mean, sd, rate) == pytest.approx(1.0 - outage, abs=1e-12)


class TestTheFadeLawsAreClosedForm:
    """**V1**: the two distributions the closed form above depends on."""

    def test_the_pointing_fade_agrees_with_the_transmittance_quantile(self) -> None:
        """Same statement from the two sides of the ``-10 log10``."""
        from quoss.channel.pointing import pointing_transmittance_quantile

        log = DegradationLog()
        for outage in (0.5, 0.01, 1e-5):
            kept = pointing_transmittance_quantile(
                outage,
                range_km=NTANOS_ORBIT_HEIGHT_KM,
                jitter_rad=NTANOS_POINTING_JITTER_RAD,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=REFERENCE_APERTURE_M,
                receive_aperture_m=REFERENCE_APERTURE_M,
                degradations=log,
            )
            gamma = beam_to_jitter_ratio(
                NTANOS_ORBIT_HEIGHT_KM,
                jitter_rad=NTANOS_POINTING_JITTER_RAD,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=REFERENCE_APERTURE_M,
                receive_aperture_m=REFERENCE_APERTURE_M,
                degradations=log,
            )
            assert float(pointing_fade_db(gamma, outage_probability=outage)) == pytest.approx(
                float(transmittance_to_loss_db(kept)), rel=1e-12
            )

    def test_the_pointing_fade_in_decibels_is_exponential(self) -> None:
        """The defining property: the quantile is linear in ``log(1/p)``.

        Checked as a difference rather than a fit — equal ratios of outage must
        cost equal increments of decibel, at any starting point — because that
        is the statement :func:`combined_fade_db` relies on.
        """
        gamma = reference_gamma()
        decade = DB_PER_NEPER * np.log(10.0) / gamma**2
        for outage in (0.5, 0.01, 1e-6):
            here = float(pointing_fade_db(gamma, outage_probability=outage))
            there = float(pointing_fade_db(gamma, outage_probability=outage / 10.0))
            assert there - here == pytest.approx(decade, rel=1e-12)

    def test_the_scintillation_fade_in_decibels_is_gaussian(self) -> None:
        """Mean ``4.343 sigma^2/2``, standard deviation ``4.343 sigma``, both read off quantiles."""
        variance = 0.0153
        median = float(scintillation_fade_db(variance, outage_probability=0.5))
        assert median == pytest.approx(DB_PER_NEPER * 0.5 * variance, rel=1e-12)

        upper = float(scintillation_fade_db(variance, outage_probability=0.158_655_254))
        assert upper - median == pytest.approx(DB_PER_NEPER * np.sqrt(variance), rel=1e-6)

    @pytest.mark.physics
    def test_both_laws_match_samples_of_the_processes_they_describe(self) -> None:
        """**V1**: the marginals of the same simulation the joint test uses."""
        gamma = reference_gamma()
        variance = reference_variance(NTANOS_MINIMUM_ELEVATION_RAD)
        point, scint = TestTwoOnePerCentAllowancesAreNotOnePerCent._sampled_fades(
            gamma, variance, 2_000_000, seed=20260914
        )
        assert float(np.mean(point)) == pytest.approx(DB_PER_NEPER / gamma**2 * 1.0, rel=0.01)
        assert float(np.quantile(point, 0.99)) == pytest.approx(
            float(pointing_fade_db(gamma, outage_probability=0.01)), rel=0.02
        )
        assert float(np.quantile(scint, 0.99)) == pytest.approx(
            float(scintillation_fade_db(variance, outage_probability=0.01)), rel=0.02
        )

    def test_no_turbulence_means_no_allowance_at_any_outage(self) -> None:
        for outage in (0.5, 0.01, 1e-9):
            assert float(scintillation_fade_db(0.0, outage_probability=outage)) == 0.0


class TestTheReceiverChainIsCountedOnce:
    """The trap the module is shaped around, measured."""

    @staticmethod
    def _budget(fade: FadeCombination = FadeCombination.EXACT) -> LossBudget:
        return downlink_loss_budget(
            NTANOS_MINIMUM_ELEVATION_RAD,
            range_km=1500.0,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            static_loss_db=NTANOS_POLARISATION_LOSS_DB,
            fade_combination=fade,
            degradations=DegradationLog(),
        )

    def test_the_two_transmittances_differ_by_exactly_the_chain(self) -> None:
        budget = self._budget()
        ratio = float(budget.transmittance) / float(budget.channel_transmittance)
        assert ratio == pytest.approx(chain_efficiency(), rel=1e-12)
        assert float(transmittance_to_loss_db(ratio)) == pytest.approx(6.356, abs=1e-3)

    def test_the_two_routes_to_a_detected_count_agree(self) -> None:
        """The end-to-end factor with ``efficiency=1``, or the channel factor with the chain."""
        budget = self._budget()
        mean_photon_number = 0.56  # Ntanos et al. §4.1
        through = click_probability(
            mean_photon_number * float(budget.transmittance),
            efficiency=1.0,
        )
        apart = click_probability(
            mean_photon_number * float(budget.channel_transmittance),
            efficiency=chain_efficiency(),
        )
        assert float(through) == pytest.approx(float(apart), rel=1e-14)

    def test_mixing_them_loses_the_chain_twice(self) -> None:
        """6.36 dB, and a factor of 4.3 in the detected rate.

        The mistake has no symptom: every intermediate number stays in range and
        the key rate simply comes out low, which is the direction a cautious
        reviewer is least likely to challenge.
        """
        budget = self._budget()
        mean_photon_number = 0.56
        correct = mean_photon_number * float(budget.transmittance)
        doubled = correct * chain_efficiency()
        assert correct / doubled == pytest.approx(1.0 / chain_efficiency(), rel=1e-12)
        assert float(transmittance_to_loss_db(doubled / correct)) == pytest.approx(6.356, abs=1e-3)
        assert correct / doubled == pytest.approx(4.32, abs=0.01)

    def test_the_geometric_term_is_the_beam_module_unchanged(self) -> None:
        """No re-derivation: the budget calls the module, it does not restate it."""
        budget = self._budget()
        direct = geometric_transmittance(
            1500.0,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
        )
        assert float(budget.geometric_db) == pytest.approx(
            float(transmittance_to_loss_db(direct)), rel=1e-14
        )


class TestTheTransmitterClipsItsOwnBeam:
    """**V3**: the closed form against the diffraction integral it came from."""

    @staticmethod
    def _numerical_efficiency(alpha: float) -> float:
        """On-axis far-field intensity per unit launched power, by quadrature.

        Fraunhofer on axis is ``|integral E dA|^2 / (lambda L)^2`` — the
        amplitude integrates and the intensity is its square — so both integrals
        are done here directly over the aperture, with no algebra in common with
        the module. The untruncated case is the same integrals to 60 waists,
        which is where a Gaussian has nothing left.
        """
        from scipy.integrate import quad

        def amplitude(limit: float) -> float:
            return quad(lambda r: np.exp(-(r**2)) * 2.0 * np.pi * r, 0.0, limit)[0]

        def power(limit: float) -> float:
            return quad(lambda r: np.exp(-2.0 * r**2) * 2.0 * np.pi * r, 0.0, limit)[0]

        truncated = amplitude(alpha) ** 2 / power(alpha)
        untruncated = amplitude(60.0) ** 2 / power(60.0)
        return truncated / untruncated

    @pytest.mark.parametrize("alpha", [0.5, 1.0, 1.12, 1.5, 2.0, 3.0])
    def test_the_closed_form_is_the_diffraction_integral(self, alpha: float) -> None:
        assert gaussian_truncation_efficiency(alpha) == pytest.approx(
            self._numerical_efficiency(alpha), rel=1e-9
        )

    def test_the_three_numbers_and_which_one_this_is(self) -> None:
        """0.63, 3.35 and 3.98 dB are three answers to three different questions.

        The reference power is what separates them, and the module applies the
        middle one because a link budget's transmit power is the power that left
        the telescope. Asserting all three here is what stops the other two from
        being adopted by accident later — the golden README predicted this term
        at 0.63 dB before the module existed, which is the first of the three.
        """
        alpha = GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE
        clipped = -np.expm1(-2.0 * alpha**2)  # power that leaves the aperture
        applied = gaussian_truncation_efficiency(alpha)
        versus_laser = (-np.expm1(-(alpha**2))) ** 2

        assert float(transmittance_to_loss_db(clipped)) == pytest.approx(0.632, abs=1e-3)
        assert float(transmittance_to_loss_db(applied)) == pytest.approx(3.352, abs=1e-3)
        assert float(transmittance_to_loss_db(versus_laser)) == pytest.approx(3.984, abs=1e-3)
        # The three are one identity, not three measurements.
        assert applied * clipped == pytest.approx(versus_laser, rel=1e-14)

    def test_it_vanishes_once_the_aperture_outgrows_the_beam(self) -> None:
        """Which is what makes it a design variable and not a constant of nature."""
        losses = [
            float(transmittance_to_loss_db(gaussian_truncation_efficiency(alpha)))
            for alpha in (1.0, 1.5, 2.0, 3.0, 5.0)
        ]
        assert losses == pytest.approx([3.352, 0.919, 0.159, 0.001, 0.0], abs=1e-3)
        assert all(later < earlier for earlier, later in pairwise(losses))

    def test_it_is_the_beam_module_convention_that_fixes_the_default(self) -> None:
        """``alpha = 1`` is inherited, not chosen: ``beam.py`` puts the waist at ``D_T/2``.

        Asserted against the private constant of that module on purpose. If
        somebody changes the waist convention there, this budget's default term
        has to move with it, and a test that reads the constant is the only
        thing that notices.
        """
        from quoss.channel.beam import _WAIST_RADIUS_PER_DIAMETER

        aperture_radius_per_diameter = 0.5
        assert GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE == pytest.approx(
            aperture_radius_per_diameter / _WAIST_RADIUS_PER_DIAMETER
        )
        default = inspect.signature(downlink_loss_budget).parameters["transmit_truncation_ratio"]
        assert default.default == GAUSSIAN_TRUNCATION_RATIO_OF_THE_BEAM_MODULE

    def test_it_does_not_vary_over_a_pass(self) -> None:
        """A transmitter property, so a scalar — and a budget line of its own."""
        budget = downlink_loss_budget(
            deg_to_rad(np.linspace(20.0, 80.0, 16)),
            range_km=np.linspace(1500.0, 700.0, 16),
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            degradations=DegradationLog(),
        )
        assert isinstance(budget.truncation_db, float)

    @pytest.mark.parametrize("alpha", [0.0, -1.0, np.nan, np.inf])
    def test_a_truncation_ratio_outside_its_domain(self, alpha: float) -> None:
        with pytest.raises(DomainError, match="truncation_ratio"):
            gaussian_truncation_efficiency(alpha)


class TestAirMass:
    """**V3**: the flat-slab secant against an independent spherical geometry."""

    @pytest.mark.parametrize(
        ("elevation_deg", "excess"),
        [(30.0, 0.00199), (20.0, 0.00500), (10.0, 0.0210), (5.0, 0.0806)],
    )
    def test_the_documented_excess(self, elevation_deg: float, excess: float) -> None:
        elevation = deg_to_rad(elevation_deg)
        ratio = float(secant_airmass(elevation)) / float(_spherical_shell_airmass(elevation))
        assert ratio - 1.0 == pytest.approx(excess, rel=0.01)

    def test_overhead_both_models_are_one(self) -> None:
        assert float(secant_airmass(0.5 * np.pi)) == pytest.approx(1.0, rel=1e-15)
        assert float(_spherical_shell_airmass(0.5 * np.pi)) == pytest.approx(1.0, rel=1e-12)

    def test_at_the_horizon_one_diverges_and_the_other_does_not(self) -> None:
        """Which is the reason the constant below exists at all."""
        assert float(_spherical_shell_airmass(0.0)) == pytest.approx(38.73, abs=0.01)
        assert float(secant_airmass(1e-9)) > 1e8

    def test_the_five_per_cent_limit_is_re_solved(self) -> None:
        """**Derived, not chosen**: the constant re-found with a root finder."""
        root = brentq(
            lambda elevation: (
                float(secant_airmass(elevation)) / float(_spherical_shell_airmass(elevation)) - 1.05
            ),
            deg_to_rad(0.5),
            deg_to_rad(45.0),
            xtol=1e-14,
        )
        assert root == pytest.approx(SECANT_AIRMASS_ELEVATION_LIMIT_RAD, rel=1e-9)
        assert np.degrees(root) == pytest.approx(6.427, abs=1e-3)

    def test_the_warning_fires_below_the_limit_and_not_above(self) -> None:
        above = DegradationLog()
        atmospheric_transmittance(
            SECANT_AIRMASS_ELEVATION_LIMIT_RAD * 1.01,
            zenith_transmittance=0.9,
            degradations=above,
        )
        assert len(above) == 0

        below = DegradationLog()
        atmospheric_transmittance(
            SECANT_AIRMASS_ELEVATION_LIMIT_RAD * 0.5, zenith_transmittance=0.9, degradations=below
        )
        assert len(below) == 1
        entry = below.entries[0]
        assert entry.code == "link_budget.secant-airmass-out-of-range"
        assert entry.severity is Severity.WARNING
        assert entry.details["secant_airmass"] > entry.details["spherical_airmass"]

    def test_the_warning_is_about_the_worst_sample_of_a_pass(self) -> None:
        """One record per call, naming the lowest elevation, not one per sample."""
        log = DegradationLog()
        atmospheric_transmittance(
            deg_to_rad(np.array([40.0, 20.0, 3.0, 25.0])),
            zenith_transmittance=0.9,
            degradations=log,
        )
        assert len(log) == 1
        assert log.entries[0].details["min_elevation_rad"] == pytest.approx(deg_to_rad(3.0))

    def test_declaring_extinction_ignored_is_silent(self) -> None:
        """``1.0`` is a statement, not an omission, so it records nothing."""
        log = DegradationLog()
        result = atmospheric_transmittance(
            deg_to_rad(45.0), zenith_transmittance=1.0, degradations=log
        )
        assert float(result) == 1.0
        assert len(log) == 0


class TestNoiseBudget:
    """**V1** against the published table of ``channel/detector.py``."""

    @staticmethod
    def _noise(
        receive_aperture_m: float,
        *,
        afterpulse_probability: float = NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
        signal_counts_per_gate: float = 0.0,
        gate_duration_s: float = GATE_S,
        degradations: DegradationLog | None = None,
    ) -> NoiseBudget:
        return downlink_noise_budget(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            wavelength_m=WAVELENGTH_M,
            receive_aperture_m=receive_aperture_m,
            field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
            filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
            gate_duration_s=gate_duration_s,
            receiver_efficiency=chain_efficiency(),
            dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            detector_count=2,
            afterpulse_probability=afterpulse_probability,
            signal_counts_per_gate=signal_counts_per_gate,
            degradations=degradations if degradations is not None else DegradationLog(),
        )

    def test_the_detector_module_table_reproduces(self) -> None:
        """The 2.3 m rows of ``channel/detector.py``'s own docstring table."""
        noise = self._noise(NTANOS_OGS_APERTURES_M[2])
        assert float(noise.background_per_gate) == pytest.approx(1.77e-6, rel=0.01)
        assert float(noise.dark_per_gate) == pytest.approx(6.00e-7, rel=1e-12)
        assert float(noise.afterpulse_per_gate) == 0.0
        share = float(noise.dark_per_gate) / float(noise.total_per_gate)
        assert share == pytest.approx(0.253, abs=1e-3)

    @pytest.mark.parametrize(
        ("aperture_m", "hidden_db", "dark_share"),
        [(2.3, 0.941, 0.253), (0.75, 3.822, 0.761)],
    )
    def test_putting_the_chain_on_the_dark_counts_hides_noise(
        self, aperture_m: float, hidden_db: float, dark_share: float
    ) -> None:
        """The natural mistake — "apply the receiver efficiency to the noise" — priced.

        It is larger on the small telescope, which is the opposite of the
        intuition that a bigger receiver has more to lose: the sky term scales
        with collecting area and the dark counts do not, so the smaller the
        telescope the more of its noise is born behind the optics and the more a
        blanket efficiency removes that was never there.
        """
        noise = self._noise(aperture_m)
        correct = float(noise.total_per_gate)
        at_aperture = float(noise.background_per_gate) / chain_efficiency()
        wrong = (at_aperture + float(noise.dark_per_gate)) * chain_efficiency()
        assert 10.0 * np.log10(correct / wrong) == pytest.approx(hidden_db, abs=2e-3)
        assert float(noise.dark_per_gate) / correct == pytest.approx(dark_share, abs=1e-3)

    def test_the_receiver_inverts_between_the_two_telescopes(self) -> None:
        """Sky limited at 2.3 m, dark-count limited at 0.75 m, on the same night."""
        big = self._noise(NTANOS_OGS_APERTURES_M[2])
        small = self._noise(NTANOS_OGS_APERTURES_M[0])
        assert float(big.background_per_gate) > float(big.dark_per_gate)
        assert float(small.dark_per_gate) > float(small.background_per_gate)

    def test_narrowing_the_gate_does_not_touch_afterpulsing(self) -> None:
        """The condition ``channel/detector.py`` attaches to "narrow the gate".

        With the InGaAs afterpulse probability of Lim et al. and a realistic
        click load, a tenfold narrower gate removes ten times the sky and ten
        times the dark counts and none of the afterpulses.
        """
        signal = 1e-3
        wide = self._noise(
            NTANOS_OGS_APERTURES_M[2],
            afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY,
            signal_counts_per_gate=signal,
        )
        narrow = self._noise(
            NTANOS_OGS_APERTURES_M[2],
            afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY,
            signal_counts_per_gate=signal,
            gate_duration_s=GATE_S / 10.0,
        )
        assert float(narrow.background_per_gate) == pytest.approx(
            float(wide.background_per_gate) / 10.0,
            rel=1e-12,
        )
        assert float(narrow.dark_per_gate) == pytest.approx(
            float(wide.dark_per_gate) / 10.0,
            rel=1e-12,
        )
        gained = float(wide.afterpulse_per_gate) / float(narrow.afterpulse_per_gate)
        assert gained == pytest.approx(1.0, abs=0.01)

        bought_db = 10.0 * np.log10(float(wide.total_per_gate) / float(narrow.total_per_gate))
        assert bought_db == pytest.approx(0.22, abs=0.02)

    def test_the_afterpulse_term_counts_signal_clicks_too(self) -> None:
        """Afterpulses come from clicks, and most clicks on a working link are signal."""
        without = self._noise(
            NTANOS_OGS_APERTURES_M[2], afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY
        )
        with_signal = self._noise(
            NTANOS_OGS_APERTURES_M[2],
            afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY,
            signal_counts_per_gate=1e-3,
        )
        assert float(with_signal.afterpulse_per_gate) > 100.0 * float(without.afterpulse_per_gate)
        assert float(with_signal.afterpulse_per_gate) == pytest.approx(
            LIM_INGAAS_AFTERPULSE_PROBABILITY * 1e-3, rel=0.01
        )

    def test_the_total_is_a_mean_and_may_exceed_one(self) -> None:
        """The composition rule of ``channel/detector.py``, inherited here.

        A daylight sky can put more than one background photon in a gate. That
        is a legal mean and an illegal probability, and the point of returning
        means is that the exponential happens once, later, in
        ``click_probability``.
        """
        log = DegradationLog()
        noise = downlink_noise_budget(
            tabulated_sky_radiance_w_m2_um_sr(0.85e-6, condition=SkyCondition.BRIGHT_SUNSHINE),
            wavelength_m=0.85e-6,
            receive_aperture_m=NTANOS_OGS_APERTURES_M[2],
            field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
            filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
            gate_duration_s=GATE_S,
            receiver_efficiency=1.0,
            dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            detector_count=2,
            degradations=log,
        )
        assert float(noise.total_per_gate) > 1.0
        assert (
            float(
                click_probability(
                    0.0, efficiency=1.0, background_photons_per_gate=noise.total_per_gate
                )
            )
            < 1.0
        )


class TestScalingLaws:
    """**V1**: the proportionalities that make a budget reviewable by hand."""

    def test_the_budget_is_vectorised_over_the_time_axis(self) -> None:
        elevation = deg_to_rad(np.linspace(20.0, 89.0, 64))
        range_km = np.linspace(1500.0, 600.0, 64)
        budget = downlink_loss_budget(
            elevation,
            range_km=range_km,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            degradations=DegradationLog(),
        )
        for term in (
            budget.geometric_db,
            budget.atmospheric_db,
            budget.fade_db,
            budget.total_db,
            budget.transmittance,
        ):
            assert term.shape == (64,)
        # A pass gets better as the satellite rises, in every term at once.
        assert np.all(np.diff(budget.total_db) < 0.0)

    def test_a_pass_agrees_sample_by_sample_with_scalar_calls(self) -> None:
        """The check that catches a broadcast that silently reduced."""
        elevation = np.asarray(deg_to_rad(np.array([25.0, 50.0, 80.0])))
        range_km = np.array([1400.0, 900.0, 620.0])
        vectorised = downlink_loss_budget(
            elevation,
            range_km=range_km,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            degradations=DegradationLog(),
        )
        for index in range(3):
            one = downlink_loss_budget(
                float(elevation[index]),
                range_km=float(range_km[index]),
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
                receive_aperture_m=REFERENCE_APERTURE_M,
                zenith_transmittance=0.9,
                pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
                receiver_efficiency=chain_efficiency(),
                degradations=DegradationLog(),
            )
            assert float(vectorised.total_db[index]) == pytest.approx(
                float(one.total_db), rel=1e-13
            )

    def test_the_atmospheric_loss_in_decibels_is_linear_in_air_mass(self) -> None:
        elevation = deg_to_rad(np.array([90.0, 30.0, 20.0]))
        loss = np.asarray(
            transmittance_to_loss_db(
                atmospheric_transmittance(
                    elevation, zenith_transmittance=0.5, degradations=DegradationLog()
                )
            )
        )
        assert loss / loss[0] == pytest.approx(np.asarray(secant_airmass(elevation)), rel=1e-12)

    def test_the_noise_background_scales_with_collecting_area(self) -> None:
        small = TestNoiseBudget._noise(1.0)
        big = TestNoiseBudget._noise(2.0)
        assert float(big.background_per_gate) / float(small.background_per_gate) == pytest.approx(
            4.0, rel=1e-12
        )
        assert float(big.dark_per_gate) == float(small.dark_per_gate)

    def test_an_empty_pass_returns_empty_and_records_nothing(self) -> None:
        log = DegradationLog()
        budget = downlink_loss_budget(
            np.array([]),
            range_km=np.array([]),
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=REFERENCE_APERTURE_M,
            zenith_transmittance=0.9,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain_efficiency(),
            degradations=log,
        )
        assert budget.total_db.shape == (0,)
        assert len(log) == 0


class TestRejectsBadInput:
    """Every guard, with the wrong-unit case that motivates it."""

    @pytest.mark.parametrize("outage", [0.0, 1.0, 1.5, -0.1, np.nan, np.inf])
    def test_an_outage_outside_the_open_unit_interval(self, outage: float) -> None:
        with pytest.raises(DomainError, match="outage_probability"):
            pointing_fade_db(4.4, outage_probability=outage)

    def test_the_percentage_mistake_is_named_in_the_message(self) -> None:
        with pytest.raises(DomainError, match=re.escape("1 % is 0.01, not 1")):
            scintillation_fade_db(0.01, outage_probability=1.0)

    @pytest.mark.parametrize("zenith", [0.0, -0.1, 1.5, np.nan])
    def test_a_zenith_transmittance_outside_the_unit_interval(self, zenith: float) -> None:
        with pytest.raises(DomainError, match="zenith_transmittance"):
            atmospheric_transmittance(
                1.0, zenith_transmittance=zenith, degradations=DegradationLog()
            )

    def test_a_zenith_transmittance_given_in_decibels(self) -> None:
        """The characteristic mistake: passing 3 for "3 dB" instead of 0.501."""
        with pytest.raises(DomainError, match="not a decibel figure"):
            atmospheric_transmittance(1.0, zenith_transmittance=3.0, degradations=DegradationLog())

    def test_an_elevation_below_the_horizon(self) -> None:
        with pytest.raises(DomainError, match="elevation_rad"):
            secant_airmass(-0.1)

    def test_a_negative_log_irradiance_variance(self) -> None:
        with pytest.raises(DomainError, match="log_irradiance_variance_np2"):
            scintillation_fade_db(-1e-9, outage_probability=0.01)

    def test_a_beam_to_jitter_ratio_of_zero(self) -> None:
        with pytest.raises(DomainError, match="beam_to_jitter_ratio_value"):
            pointing_fade_db(0.0, outage_probability=0.01)

    def test_the_joint_quantile_guards_its_own_arguments(self) -> None:
        """``combined_fade_db`` does not reach the public guards, so it has its own.

        It takes both distribution parameters at once through a private helper,
        which is exactly the shape in which a validator gets forgotten: the two
        public functions each check one argument, and the function that consumes
        both would inherit neither.
        """
        with pytest.raises(DomainError, match="beam_to_jitter_ratio_value"):
            combined_fade_db(
                beam_to_jitter_ratio_value=-1.0,
                log_irradiance_variance_np2=0.01,
                outage_probability=0.01,
            )
        with pytest.raises(DomainError, match="log_irradiance_variance_np2"):
            combined_fade_db(
                beam_to_jitter_ratio_value=4.4,
                log_irradiance_variance_np2=-0.01,
                outage_probability=0.01,
            )

    def test_a_negative_static_loss(self) -> None:
        with pytest.raises(DomainError, match="static_loss_db"):
            downlink_loss_budget(
                1.0,
                range_km=600.0,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
                receive_aperture_m=REFERENCE_APERTURE_M,
                zenith_transmittance=1.0,
                pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
                receiver_efficiency=chain_efficiency(),
                static_loss_db=-1.0,
                degradations=DegradationLog(),
            )

    def test_a_negative_signal_count(self) -> None:
        with pytest.raises(DomainError, match="signal_counts_per_gate"):
            TestNoiseBudget._noise(1.0, signal_counts_per_gate=-1e-9)

    def test_an_unknown_fade_combination(self) -> None:
        with pytest.raises(ValueError, match="not a valid FadeCombination"):
            downlink_loss_budget(
                1.0,
                range_km=600.0,
                wavelength_m=WAVELENGTH_M,
                transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
                receive_aperture_m=REFERENCE_APERTURE_M,
                zenith_transmittance=1.0,
                pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
                receiver_efficiency=chain_efficiency(),
                fade_combination="average",  # type: ignore[arg-type]
                degradations=DegradationLog(),
            )


class TestModuleSurface:
    """Rules about what this module is allowed to be, asserted rather than intended."""

    def test_zenith_transmittance_has_no_default(self) -> None:
        """The declared gap, enforced by the signature.

        No source verified for this project publishes a vertical transmittance
        at 1550 nm, so there must be no argument value that quietly means "I did
        not think about this". A caller who wants no extinction writes ``1.0``
        in their own code and thereby says so.
        """
        for function in (atmospheric_transmittance, downlink_loss_budget):
            parameter = inspect.signature(function).parameters["zenith_transmittance"]
            assert parameter.default is inspect.Parameter.empty

    def test_no_uplink_function_exists(self) -> None:
        """Asserted by absence: a wrong uplink budget is worse than a missing one."""
        from quoss.channel import link_budget

        assert not any("uplink" in name.lower() for name in link_budget.__all__)
        assert any("downlink" in name for name in link_budget.__all__)

    def test_there_is_no_random_generator_in_this_module(self) -> None:
        """Same rule as the rest of ``channel/``: randomness lives in ``core/rng.py``.

        This module is the one most tempted to break it, because it summarises
        two distributions and a Monte Carlo would be the obvious way. It is a
        closed form instead, which is why the tests above can check it against a
        simulation rather than being one.
        """
        from quoss.channel import link_budget

        tree = ast.parse(inspect.getsource(link_budget))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any("rng" in name or "random" in name for name in imported)
        assert hasattr(RandomSource, "from_seed")

    def test_the_physics_is_not_restated_here(self) -> None:
        """An assembler that re-derives a term has two copies of it to keep in step.

        Checked by import rather than by reading: every physical quantity in the
        budget must come from the module that owns it.
        """
        from quoss.channel import link_budget

        source = inspect.getsource(link_budget)
        for owner in (
            "quoss.channel.beam",
            "quoss.channel.pointing",
            "quoss.channel.turbulence",
            "quoss.channel.background",
            "quoss.channel.detector",
        ):
            assert f"from {owner} import" in source

    def test_the_two_fade_combination_rules_are_both_named(self) -> None:
        """Neither is a default hidden in a boolean flag."""
        assert set(FadeCombination) == {FadeCombination.EXACT, FadeCombination.ADDITIVE}
        default = inspect.signature(downlink_loss_budget).parameters["fade_combination"].default
        assert default is FadeCombination.EXACT

    def test_the_budget_is_frozen(self) -> None:
        """Terms that can be edited after the fact stop adding up to the total."""
        budget = TestTheReceiverChainIsCountedOnce._budget()
        with pytest.raises(AttributeError):
            budget.total_db = np.array(0.0)  # type: ignore[misc]
