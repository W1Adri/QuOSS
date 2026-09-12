"""Tests for `quoss.channel.background`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestTheTwoPublishedEquationsAreOne`` — **V2**. ITU-R P.1621-2 equation (1)
  and Ntanos et al. 2021 equation (19) are transcribed here independently, from
  two documents, and shown to be the same equation. The same class prices the
  two ways of misreading the field of view they disagree about the units of:
  6.02 dB for half-angle against full angle, 41.05 dB for handing the angle to
  the formula that wants steradians.
- ``TestAgainstTheTable`` — **V2**. The fifteen numbers of Table 1, plus the
  structural facts about them a reader would want checked before interpolating:
  which column dominates which, where the spectrum steepens, and the
  non-monotone entry that any smooth fit gets wrong.
- ``TestTheNightSourcesDisagree`` — **V2 in conflict**, which is the honest
  category for this one. Two openable sources give the nighttime radiance a
  factor of ten apart; the test asserts the disagreement, and measures what it
  costs against the dark-count rate of the same paper's detectors, so the
  conflict is a number rather than a caveat.
- ``TestTheFullMoonClaim`` — a published claim that is **not reproducible** from
  the parameters published beside it, asserted as such.
- ``TestAMeanIsNotAProbability`` — the trap the module is shaped around: with
  ITU-R's own daylight radiance and the reference receiver, equation (20) as
  printed returns a probability of 3.42.
- ``TestTheInterpolationGap`` — what gap 4 of ADR 0009 costs, measured by
  leave-one-out on the table's own points rather than asserted.
- ``TestTemporalGating`` — **V1**. The ``erf`` law against a Monte Carlo draw
  from the Gaussian jitter it comes from, and the ``S/sqrt(B)`` optimum
  re-derived with a root finder instead of trusting the module's constant.
- ``TestScalingLaws`` — **V1**. The four proportionalities that make a link
  budget reviewable by hand, and the shape preservation over the time axis.
- ``TestRejectsBadInput`` / ``TestModuleSurface``.

Not reproduced, and declared:

- **Ntanos et al.'s "10 kcps in the photon counter at most" for a full moon.**
  Their equation (19) with their own parameters gives 8.1, 24.4 or 76.4 kcps
  depending on which of their three telescopes the sentence means, and the
  sentence does not say. See ``TestTheFullMoonClaim``.
- **Sky radiance at 785 and 810 nm**, gap 4 of
  ``docs/adr/0009-citation-policy.md``. Table 1 has no entry between 530 and
  850 nm, so the interpolation error there cannot be measured *at* those
  wavelengths at all — only bounded by analogy with the brackets that do
  contain an interior point, which is what ``TestTheInterpolationGap`` does.
- **Earth radiance.** Table 1 is titled "of the sky and Earth" and prints only
  sky columns, so there is no uplink background here and no test for one.
- **Any elevation, azimuth or sun-angle dependence of the radiance.** Neither
  source publishes one. ``TestModuleSurface`` asserts the *absence* — that no
  function in the module accepts an elevation — because a plausible air-mass
  scaling would be 4.66 dB at 20 degrees and would look like physics.
"""

from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.special import erf

from quoss.channel.background import (
    GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS,
    ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR,
    ITU_SKY_RADIANCE_W_M2_UM_SR,
    ITU_SKY_RADIANCE_WAVELENGTHS_M,
    LINEAR_CLICK_PROBABILITY_LIMIT,
    NTANOS_DAYLIGHT_RADIANCE_RANGE_W_M2_UM_SR,
    NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR,
    NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR,
    NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    SkyCondition,
    background_click_probability,
    background_counts_per_gate,
    background_photon_rate_cps,
    background_power_w,
    gate_signal_fraction,
    gate_width_maximising_snr_s,
    interpolated_sky_radiance_w_m2_um_sr,
    receiver_solid_angle_sr,
    tabulated_sky_radiance_w_m2_um_sr,
)
from quoss.core.constants import PLANCK_J_S, SPEED_OF_LIGHT_M_S
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.rng import RandomSource
from quoss.core.units import linear_to_db

# --------------------------------------------------------------------------- #
# The reference receiver, and the published parameters that fix it
# --------------------------------------------------------------------------- #

WAVELENGTH_M = 1.55e-6
FIELD_OF_VIEW_RAD = 100e-6
FILTER_BANDWIDTH_M = 0.2e-9
GATE_S = 1e-9
JITTER_FWHM_S = 50e-12
DARK_COUNT_CPS = 300.0
"""Ntanos et al. 2021 §4.1, verbatim: "in order to minimize the effects of strong
daylight radiance, we assumed a narrow FOV of 100 urad and a narrow band-pass
filter of 0.2 nm with an insertion loss of 3 dB [...] SNSPDs with quantum
efficiencies of 85% at 1550 nm, dark count rates of 300 counts per second (cps),
timing jitter of 50 ps, dead time of 30 ns [...] The detector's gate duration
time was set to 1 ns."

The insertion loss, the quantum efficiency and the dead time are deliberately
absent from every test here: they attenuate background and signal by the same
factors, so they belong to ``channel/detector.py`` and ``channel/link_budget.py``
and applying them here as well would be the double-counting mistake
``channel/pointing.py`` exists to prevent.
"""

CHOLOMONDAS_M = 0.75
SKINAKAS_M = 1.3
HELMOS_M = 2.3
"""The three ground stations of Ntanos et al. §4.1, by telescope diameter.

Kept as three named values rather than one, because several of the findings in
this file are *only* visible as a function of aperture: the two published night
radiances differ by 1.24x in total noise at 0.75 m and 2.83x at 2.3 m, and the
paper's full-moon claim reproduces at one of the three and not the others.
"""


def _rate_cps(
    radiance_w_m2_um_sr: float,
    aperture_m: float,
    *,
    wavelength_m: float = WAVELENGTH_M,
    field_of_view_rad: float = FIELD_OF_VIEW_RAD,
    filter_bandwidth_m: float = FILTER_BANDWIDTH_M,
) -> float:
    """Return the background count rate for the reference receiver, cps."""
    power_w = background_power_w(
        radiance_w_m2_um_sr,
        field_of_view_full_angle_rad=field_of_view_rad,
        receive_aperture_m=aperture_m,
        filter_bandwidth_m=filter_bandwidth_m,
    )
    return float(background_photon_rate_cps(power_w, wavelength_m=wavelength_m))


def _itu_equation_1_power_w(
    radiance_w_m2_um_sr: float,
    *,
    field_of_view_rad: float,
    aperture_m: float,
    filter_bandwidth_um: float,
) -> float:
    """ITU-R P.1621-2 equation (1), transcribed from the rendered page.

    ``P_back = pi theta_r^2 A_r dlambda H / 4``, with ``theta_r`` the field of
    view in radians, ``A_r`` the receiver area in m^2, ``dlambda`` the receiver
    bandwidth in micrometres and ``H`` the radiance in W/m^2/um/sr.

    Written out rather than imported so that the comparison is against the
    equation as printed, not against a rearrangement of the module's own code.
    Read off the page image: the extracted text layer of this recommendation
    renders the numerator as ``2r Ar H``, dropping the pi, the theta and the
    delta, which is exactly the kind of transcription this project cannot
    afford to do from text.
    """
    area_m2 = np.pi * (0.5 * aperture_m) ** 2
    return float(
        np.pi * field_of_view_rad**2 * area_m2 * filter_bandwidth_um * radiance_w_m2_um_sr / 4.0
    )


def _ntanos_equation_19_power_w(
    radiance_w_m2_um_sr: float,
    *,
    solid_angle_sr: float,
    aperture_m: float,
    filter_bandwidth_um: float,
) -> float:
    """Ntanos et al. 2021 equation (19), transcribed: ``P = H Omega A_r dlambda``.

    Same quantity as :func:`_itu_equation_1_power_w`, from a different document,
    and taking the field of view as a **solid angle** where ITU-R takes it as an
    angle. That difference is the reason both are written out here.
    """
    area_m2 = np.pi * (0.5 * aperture_m) ** 2
    return float(radiance_w_m2_um_sr * solid_angle_sr * area_m2 * filter_bandwidth_um)


@pytest.mark.reference
class TestTheTwoPublishedEquationsAreOne:
    """ITU-R equation (1) and Ntanos et al. equation (19), from two documents."""

    def test_the_module_reproduces_itu_equation_1(self) -> None:
        """The published closed form, at the reference receiver and radiance."""
        published = _itu_equation_1_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            field_of_view_rad=FIELD_OF_VIEW_RAD,
            aperture_m=HELMOS_M,
            filter_bandwidth_um=FILTER_BANDWIDTH_M * 1e6,
        )
        computed = background_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
            receive_aperture_m=HELMOS_M,
            filter_bandwidth_m=FILTER_BANDWIDTH_M,
        )

        # The tolerance is the size of the only difference between the two: the
        # module uses the exact cone solid angle where equation (1) uses its
        # small-angle limit, which at 100 urad is 6.1e-9 relative. Anything
        # larger than that would be a real disagreement, so the bound is
        # derived from the approximation rather than chosen to pass.
        assert float(computed) == pytest.approx(published, rel=1e-8)
        assert float(computed) == pytest.approx(9.789413805835627e-16, rel=1e-12)

    def test_equation_19_is_equation_1_with_the_solid_angle_substituted(self) -> None:
        """The two published forms agree once the FOV is converted, not before."""
        solid_angle_sr = receiver_solid_angle_sr(FIELD_OF_VIEW_RAD)
        itu = _itu_equation_1_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            field_of_view_rad=FIELD_OF_VIEW_RAD,
            aperture_m=HELMOS_M,
            filter_bandwidth_um=FILTER_BANDWIDTH_M * 1e6,
        )
        ntanos = _ntanos_equation_19_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            solid_angle_sr=solid_angle_sr,
            aperture_m=HELMOS_M,
            filter_bandwidth_um=FILTER_BANDWIDTH_M * 1e6,
        )
        assert ntanos == pytest.approx(itu, rel=1e-8)

    def test_the_exact_solid_angle_matches_the_itu_small_angle_form(self) -> None:
        """At any real instrument field of view the choice is invisible."""
        for field_of_view_rad in (10e-6, 100e-6, 1e-3, 1e-2):
            exact = receiver_solid_angle_sr(field_of_view_rad)
            small_angle = np.pi * field_of_view_rad**2 / 4.0
            assert exact == pytest.approx(small_angle, rel=1e-4)

        # And the size of the departure at the reference field of view, stated
        # rather than absorbed into a tolerance.
        exact_100 = receiver_solid_angle_sr(100e-6)
        assert (np.pi * 100e-6**2 / 4.0) / exact_100 - 1.0 == pytest.approx(6.08e-9, rel=1e-2)

    def test_the_small_angle_form_reports_more_than_a_whole_sphere(self) -> None:
        """Why the exact form is used: the published one has no ceiling.

        This is the same argument ``beam.geometric_transmittance`` makes about
        the published gain product, and the same shape of failure: a formula
        that grows without bound where the physical quantity saturates. Nothing
        in the channel has a 40-degree field of view today, but a parameter
        sweep costs nothing and a formula that answers "31 steradians" costs a
        figure.
        """
        assert receiver_solid_angle_sr(2.0 * np.pi) == pytest.approx(4.0 * np.pi, rel=1e-12)
        assert np.pi * (2.0 * np.pi) ** 2 / 4.0 == pytest.approx(31.0063, rel=1e-4)
        assert np.pi * (2.0 * np.pi) ** 2 / 4.0 > 4.0 * np.pi

        # One per cent apart at 39.8 degrees of full angle, monotonically worse
        # after that.
        one_per_cent = brentq(
            lambda t: (np.pi * t**2 / 4.0) / receiver_solid_angle_sr(t) - 1.01, 1e-3, 3.0
        )
        assert np.degrees(one_per_cent) == pytest.approx(39.58, abs=0.05)

    def test_reading_the_field_of_view_as_a_half_angle_costs_6_02_db(self) -> None:
        """The fork neither source resolves, priced.

        ITU-R equation (1) fixes the convention by its own arithmetic: ``pi
        theta^2 / 4`` is the small-angle solid angle of a cone of half-angle
        ``theta / 2``, so their ``theta_r`` is the full angle. Ntanos et al.
        declare "a narrow FOV of 100 urad" and give no such handle. Whoever
        reads that as a half-angle collects four times the background.
        """
        full_angle = _rate_cps(NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR, HELMOS_M)
        as_half_angle = _rate_cps(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR, HELMOS_M, field_of_view_rad=2.0 * 100e-6
        )
        assert as_half_angle / full_angle == pytest.approx(4.0, rel=1e-6)
        assert float(linear_to_db(as_half_angle / full_angle)) == pytest.approx(6.02, abs=0.01)

    def test_handing_the_angle_to_the_steradian_formula_costs_41_db(self) -> None:
        """The unit trap between the two published forms of the same equation."""
        solid_angle_sr = receiver_solid_angle_sr(FIELD_OF_VIEW_RAD)
        correct = _ntanos_equation_19_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            solid_angle_sr=solid_angle_sr,
            aperture_m=HELMOS_M,
            filter_bandwidth_um=FILTER_BANDWIDTH_M * 1e6,
        )
        angle_as_steradians = _ntanos_equation_19_power_w(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            solid_angle_sr=FIELD_OF_VIEW_RAD,
            aperture_m=HELMOS_M,
            filter_bandwidth_um=FILTER_BANDWIDTH_M * 1e6,
        )
        assert angle_as_steradians / correct == pytest.approx(1.2732e4, rel=1e-3)
        assert float(linear_to_db(angle_as_steradians / correct)) == pytest.approx(41.05, abs=0.01)

        # And the module cannot be made to do it: a solid angle passed as an
        # angle is not silently accepted, because 1e-4 rad is a legal field of
        # view but 1e-4 sr is not the same thing. The guard that catches the
        # gross case is the 2 pi ceiling.
        with pytest.raises(DomainError, match="full cone angle"):
            receiver_solid_angle_sr(12.57)

    def test_one_photon_per_second_is_128_zeptowatts(self) -> None:
        """The photon-energy division, against the SI-exact constants.

        Not a citation but an identity, and worth pinning because it is the one
        place a factor of ``h`` or a wavelength in nanometres would turn every
        count rate in the project into a plausible wrong number.
        """
        energy_j = PLANCK_J_S * SPEED_OF_LIGHT_M_S / WAVELENGTH_M
        assert energy_j == pytest.approx(1.281578e-19, rel=1e-6)
        assert float(background_photon_rate_cps(energy_j, wavelength_m=WAVELENGTH_M)) == (
            pytest.approx(1.0, rel=1e-12)
        )


@pytest.mark.reference
class TestAgainstTheTable:
    """ITU-R P.1621-2 Table 1: the values, and the structure of the values."""

    def test_the_five_wavelengths_are_the_published_ones(self) -> None:
        assert ITU_SKY_RADIANCE_WAVELENGTHS_M == (0.530e-6, 0.850e-6, 0.965e-6, 1.06e-6, 1.50e-6)
        assert list(ITU_SKY_RADIANCE_WAVELENGTHS_M) == sorted(ITU_SKY_RADIANCE_WAVELENGTHS_M)

    def test_the_frequencies_printed_beside_them_agree(self) -> None:
        """Table 1 prints both columns, so it checks itself.

        566.0, 352.9, 310.9, 283.0 and 200.0 THz against 0.530, 0.850, 0.965,
        1.06 and 1.50 um. The recommendation rounds the frequencies to four
        significant figures, so the tolerance is the rounding and not a fudge:
        1e-3 relative covers 566.0 against c/0.530 um = 565.6 THz.
        """
        printed_thz = (566.0, 352.9, 310.9, 283.0, 200.0)
        for wavelength_m, frequency_thz in zip(
            ITU_SKY_RADIANCE_WAVELENGTHS_M, printed_thz, strict=True
        ):
            assert SPEED_OF_LIGHT_M_S / wavelength_m / 1e12 == pytest.approx(
                frequency_thz, rel=1e-3
            )

    def test_the_lookup_returns_the_printed_values(self) -> None:
        assert tabulated_sky_radiance_w_m2_um_sr(
            530e-9, condition=SkyCondition.BRIGHT_SUNSHINE
        ) == pytest.approx(303.4)
        assert tabulated_sky_radiance_w_m2_um_sr(
            850e-9, condition=SkyCondition.NORMAL_SUNSHINE
        ) == pytest.approx(42.58)
        assert tabulated_sky_radiance_w_m2_um_sr(
            1.5e-6, condition=SkyCondition.OVERCAST
        ) == pytest.approx(4.44)

    def test_the_wavelength_may_be_written_either_way(self) -> None:
        """``530e-9`` and ``0.53e-6`` differ in the last bit and are one wavelength."""
        assert tabulated_sky_radiance_w_m2_um_sr(
            530e-9, condition=SkyCondition.OVERCAST
        ) == tabulated_sky_radiance_w_m2_um_sr(0.53e-6, condition=SkyCondition.OVERCAST)

    def test_bright_dominates_normal_dominates_overcast(self) -> None:
        """At every wavelength, which is not something the table is sorted by."""
        for index in range(len(ITU_SKY_RADIANCE_WAVELENGTHS_M)):
            bright = ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.BRIGHT_SUNSHINE][index]
            normal = ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.NORMAL_SUNSHINE][index]
            overcast = ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.OVERCAST][index]
            assert bright > normal > overcast

    def test_the_normal_sunshine_column_is_not_monotone(self) -> None:
        """25.12 at 965 nm and 25.32 at 1060 nm — the entry no smooth fit gets right.

        A negative control for the transcription: this is the one place where
        the published table rises with wavelength, and a reader who "fixed" it
        into a monotone sequence would break this test rather than quietly
        improve the interpolation. It is also the concrete reason the module
        records a degradation instead of trusting a fit.
        """
        normal = ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.NORMAL_SUNSHINE]
        assert normal[2] == 25.12
        assert normal[3] == 25.32
        assert normal[3] > normal[2]

        # Every other column, and every other adjacent pair, does fall.
        for condition in (SkyCondition.BRIGHT_SUNSHINE, SkyCondition.OVERCAST):
            values = ITU_SKY_RADIANCE_W_M2_UM_SR[condition]
            assert all(later < earlier for earlier, later in pairwise(values))

    def test_the_spectrum_steepens_after_850_nm(self) -> None:
        """The 940 nm water-vapour band, visible in the table's own slopes.

        Local log-log slope -1.92 from 530 to 850 nm, -5.03 from 850 to 965 nm.
        This is the measurement behind two separate claims in the module: that a
        power law is a defensible interpolant *inside* the 530-850 nm bracket
        where 785 and 810 nm live, and that no smooth rule can be trusted across
        the whole grid.
        """
        wavelengths = np.asarray(ITU_SKY_RADIANCE_WAVELENGTHS_M)
        values = np.asarray(ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.BRIGHT_SUNSHINE])
        slopes = np.diff(np.log(values)) / np.diff(np.log(wavelengths))
        assert slopes[0] == pytest.approx(-1.9235, abs=1e-3)
        assert slopes[1] == pytest.approx(-5.0275, abs=1e-3)
        assert slopes[1] < 2.0 * slopes[0]

    def test_the_two_sources_agree_about_daylight_at_1_5_microns(self) -> None:
        """Ntanos et al.'s bracket contains ITU-R's normal and overcast values.

        The strongest cross-source statement this module can make, and worth
        contrasting with the night, where the same two sources are a factor of
        ten apart: ITU-R Table 1 at 1500 nm gives 6.00 (normal) and 4.44
        (overcast), and Ntanos et al. §4.2.2 put clear-sky daylight at 1550 nm
        between 0.1 and 6. Their bright-sunshine value, 13.01, sits 2.17x above
        the bracket, which is consistent rather than contradictory: a bracket of
        "typical" values need not contain the worst tabulated case.
        """
        low, high = NTANOS_DAYLIGHT_RADIANCE_RANGE_W_M2_UM_SR
        normal = tabulated_sky_radiance_w_m2_um_sr(1.5e-6, condition=SkyCondition.NORMAL_SUNSHINE)
        overcast = tabulated_sky_radiance_w_m2_um_sr(1.5e-6, condition=SkyCondition.OVERCAST)
        bright = tabulated_sky_radiance_w_m2_um_sr(1.5e-6, condition=SkyCondition.BRIGHT_SUNSHINE)

        assert low <= overcast <= high
        assert low <= normal <= high
        assert bright / high == pytest.approx(2.168, rel=1e-3)

    def test_the_table_cannot_be_mutated(self) -> None:
        """A published table that a caller can edit in place is not a citation."""
        with pytest.raises(TypeError):
            ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.OVERCAST] = (0.0,) * 5  # type: ignore[index]


@pytest.mark.reference
class TestTheNightSourcesDisagree:
    """Two openable sources, one quantity, a factor of ten."""

    def test_the_disagreement_is_a_factor_of_ten(self) -> None:
        itu_low, itu_high = ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR
        assert (itu_low, itu_high) == (1.0e-6, 2.0e-6)
        assert NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR / itu_high == pytest.approx(7.5)
        assert NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR / itu_low == pytest.approx(15.0)

    def test_what_the_disagreement_costs_depends_on_the_telescope(self) -> None:
        """The measurement that turns the conflict into a decision.

        Against the 300 cps dark-count rate of the same paper's detectors, the
        two candidate night radiances are indistinguishable on the small
        telescope and a factor of 2.8 apart on the large one. So the
        disagreement does not need resolving to design a 0.75 m station, and
        does need resolving to trust a 2.3 m one — which is exactly the station
        the paper reports its best budget for.
        """
        itu_mid = float(np.mean(ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR))
        expected = {CHOLOMONDAS_M: 1.237, SKINAKAS_M: 1.677, HELMOS_M: 2.827}
        for aperture_m, factor in expected.items():
            with_itu = _rate_cps(itu_mid, aperture_m) + DARK_COUNT_CPS
            with_ntanos = (
                _rate_cps(NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR, aperture_m) + DARK_COUNT_CPS
            )
            assert with_ntanos / with_itu == pytest.approx(factor, rel=2e-3)

        # The sky is below the detector's own noise on the small telescope and
        # above it on the large one, which is the mechanism behind those ratios.
        assert _rate_cps(itu_mid, CHOLOMONDAS_M) < DARK_COUNT_CPS
        assert _rate_cps(NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR, HELMOS_M) > DARK_COUNT_CPS

    def test_the_published_night_bracket_spans_a_factor_of_one_hundred(self) -> None:
        """Moonless to full moon, and the study value sits at its geometric mean."""
        ratio = NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR / NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR
        assert ratio == pytest.approx(100.0)
        geometric_mean = np.sqrt(
            NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR * NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR
        )
        assert NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR == pytest.approx(geometric_mean, rel=1e-12)


@pytest.mark.reference
class TestTheFullMoonClaim:
    """The full-moon count rate Ntanos et al. §4.2.2 prints, and cannot mean.

    Verbatim: "Even in the case of full moon, the background radiance
    corresponds to 10 kcps in the photon counter at most."

    A published, checkable consequence of their own equation (19), and it does
    not check out unless the sentence means their *smallest* telescope, which
    "at most" argues against. Recorded as a gap rather than reproduced, and the
    three candidate answers asserted so that a future reader can see which
    reading the sentence would need.
    """

    def test_the_three_telescopes_give_three_different_answers(self) -> None:
        rates = {
            aperture_m: _rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, aperture_m)
            for aperture_m in (CHOLOMONDAS_M, SKINAKAS_M, HELMOS_M)
        }
        assert rates[CHOLOMONDAS_M] == pytest.approx(8122.3, rel=1e-4)
        assert rates[SKINAKAS_M] == pytest.approx(24403.0, rel=1e-4)
        assert rates[HELMOS_M] == pytest.approx(76385.6, rel=1e-4)

    def test_only_the_smallest_telescope_reproduces_the_printed_10_kcps(self) -> None:
        claim_cps = 10e3
        assert _rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, CHOLOMONDAS_M) < claim_cps
        assert _rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, SKINAKAS_M) > claim_cps
        assert _rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, HELMOS_M) / claim_cps == (
            pytest.approx(7.64, rel=1e-2)
        )

    def test_the_optical_chain_does_not_close_the_gap_either(self) -> None:
        """The obvious rescue, tried and reported.

        If the 10 kcps were meant *after* the losses the same section declares —
        3 dB of filter insertion, 2.65 dB of receiver loss, 85 % detector
        efficiency — the 2.3 m station would give 17.7 kcps, still 1.8x above
        the claim. So no reading of the sentence recovers it for the telescope
        the paper's own best result uses, and the honest conclusion is that the
        sentence is unreproducible rather than that this module is wrong.
        """
        chain = 10.0 ** (-3.0 / 10.0) * 10.0 ** (-2.65 / 10.0) * 0.85
        detected = _rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, HELMOS_M) * chain
        assert detected == pytest.approx(17678.0, rel=1e-3)
        assert detected / 10e3 == pytest.approx(1.77, rel=1e-2)


@pytest.mark.physics
class TestAMeanIsNotAProbability:
    """Equation (20)'s linear reading, and where it stops being one."""

    def test_the_published_form_returns_a_probability_above_one(self) -> None:
        """From published parameters only, with no step that looks wrong.

        ITU-R's tabulated bright sunshine at 850 nm — the nearest tabulated
        wavelength to the 780-810 nm band — with Ntanos et al.'s receiver and
        their 1 ns gate.
        """
        radiance = tabulated_sky_radiance_w_m2_um_sr(850e-9, condition=SkyCondition.BRIGHT_SUNSHINE)
        rate_cps = _rate_cps(radiance, HELMOS_M, wavelength_m=850e-9)
        mean = float(background_counts_per_gate(rate_cps, gate_duration_s=GATE_S))

        assert rate_cps == pytest.approx(3.415341e9, rel=1e-5)
        assert mean == pytest.approx(3.4153, rel=1e-4)
        assert mean > 1.0

        # The middle telescope crosses unity too, so it is not an artefact of
        # taking the largest one.
        middle = float(
            background_counts_per_gate(
                _rate_cps(radiance, SKINAKAS_M, wavelength_m=850e-9), gate_duration_s=GATE_S
            )
        )
        assert middle == pytest.approx(1.0911, rel=1e-3)
        assert middle > 1.0

    def test_the_poisson_form_saturates_where_the_linear_one_does_not(self) -> None:
        log = DegradationLog()
        radiance = tabulated_sky_radiance_w_m2_um_sr(850e-9, condition=SkyCondition.BRIGHT_SUNSHINE)
        rate_cps = _rate_cps(radiance, HELMOS_M, wavelength_m=850e-9)
        probability = float(
            background_click_probability(rate_cps, gate_duration_s=GATE_S, degradations=log)
        )
        assert probability == pytest.approx(0.967135, rel=1e-5)
        assert probability < 1.0

        # Arbitrarily bright sky, still a probability.
        blinding = float(
            background_click_probability(1e18, gate_duration_s=GATE_S, degradations=log)
        )
        assert blinding == pytest.approx(1.0)
        assert blinding <= 1.0

    def test_the_warning_threshold_is_where_the_overshoot_reaches_five_per_cent(self) -> None:
        """The constant is derived, not chosen.

        ``mu / (1 - exp(-mu))`` is the factor by which reading the mean as a
        probability overshoots. It reaches 1.05 at ``mu = 0.0984``, and the
        module's threshold is that root rounded to one digit — which is a
        threshold whose defence is a number rather than a habit.
        """
        five_per_cent = brentq(lambda m: m / -np.expm1(-m) - 1.05, 1e-9, 1.0)
        assert five_per_cent == pytest.approx(0.0984, abs=1e-4)
        assert LINEAR_CLICK_PROBABILITY_LIMIT == pytest.approx(0.1)

        overshoot_at_limit = LINEAR_CLICK_PROBABILITY_LIMIT / float(
            -np.expm1(-LINEAR_CLICK_PROBABILITY_LIMIT)
        )
        assert overshoot_at_limit == pytest.approx(1.0508, rel=1e-3)

    @pytest.mark.parametrize(
        ("mean", "overshoot"),
        [(1e-3, 1.0005), (1e-2, 1.0050), (0.1, 1.0508), (1.0, 1.5820), (3.4153, 3.5314)],
    )
    def test_the_published_table_of_overshoots(self, mean: float, overshoot: float) -> None:
        """The five rows of the table in the function's docstring."""
        rate_cps = mean / GATE_S
        probability = float(
            background_click_probability(
                rate_cps, gate_duration_s=GATE_S, degradations=DegradationLog()
            )
        )
        assert mean / probability == pytest.approx(overshoot, rel=1e-3)

    def test_the_warning_fires_only_above_the_threshold(self) -> None:
        quiet = DegradationLog()
        background_click_probability(0.09 / GATE_S, gate_duration_s=GATE_S, degradations=quiet)
        assert len(quiet) == 0

        loud = DegradationLog()
        background_click_probability(0.11 / GATE_S, gate_duration_s=GATE_S, degradations=loud)
        assert len(loud) == 1
        assert loud.entries[0].code == "background.counts-per-gate-not-small"

    def test_the_warning_is_a_warning_and_not_a_degradation(self) -> None:
        """Nothing was substituted: the returned probability is the exact one.

        The severity matters because ``has_degraded`` is the single flag a
        result consumer reads to decide whether the numbers are those of the
        requested model. They are — the noisy operating point is a fact about
        the link, not a fallback in the code.
        """
        log = DegradationLog()
        background_click_probability(1.0 / GATE_S, gate_duration_s=GATE_S, degradations=log)
        assert log.entries[0].severity is Severity.WARNING
        assert not log.has_degraded
        assert log.entries[0].details["counts_per_gate"] == pytest.approx(1.0)
        assert log.entries[0].details["poisson_probability"] == pytest.approx(0.632121, rel=1e-5)

    def test_the_warning_fires_on_the_worst_sample_of_a_pass(self) -> None:
        """A vector input warns if *any* instant crosses, not just the last one."""
        log = DegradationLog()
        rates = np.array([1e6, 1e7, 1e9])
        background_click_probability(rates, gate_duration_s=GATE_S, degradations=log)
        assert len(log) == 1
        assert log.entries[0].details["counts_per_gate"] == pytest.approx(1.0)

    def test_the_probability_matches_a_poisson_draw(self) -> None:
        """**V1**: ``1 - exp(-mu)`` against counting Poisson arrivals.

        An independent route to the same number: the module derives it from the
        Poisson distribution analytically, and this draws from the distribution
        and counts. The tolerance is three standard errors of the estimate,
        ``3 sqrt(p (1-p) / n)``, which is derived from the sample size rather
        than tuned — at 200 000 draws and ``p`` near 0.18 that is 0.26 %.
        """
        source = RandomSource.from_seed(20260910)
        draws = 200_000
        mean = 0.2
        counts = source.generator.poisson(mean, size=draws)
        measured = float(np.count_nonzero(counts >= 1) / draws)

        predicted = float(
            background_click_probability(
                mean / GATE_S, gate_duration_s=GATE_S, degradations=DegradationLog()
            )
        )
        standard_error = np.sqrt(predicted * (1.0 - predicted) / draws)
        assert abs(measured - predicted) < 3.0 * standard_error

    def test_the_stable_form_keeps_its_digits_at_the_nighttime_mean(self) -> None:
        """``-expm1(-mu)`` rather than ``1 - exp(-mu)``, and why it is not pedantry.

        At the reference nighttime mean of 7.6e-06 counts per gate, the naive
        difference cancels the leading digits of two numbers that agree to six
        decimals. The stable form agrees with the exact series ``mu - mu^2/2``
        to fourteen digits; the naive one loses about ten bits.
        """
        mean = 7.638562785e-6
        exact = mean - mean**2 / 2.0 + mean**3 / 6.0
        stable = float(
            background_click_probability(
                mean / GATE_S, gate_duration_s=GATE_S, degradations=DegradationLog()
            )
        )
        naive = 1.0 - np.exp(-mean)
        assert stable == pytest.approx(exact, rel=1e-14)
        assert abs(naive - exact) > 100.0 * abs(stable - exact)


@pytest.mark.reference
class TestTheInterpolationGap:
    """Gap 4 of ADR 0009, measured rather than asserted away."""

    def test_a_tabulated_wavelength_records_nothing(self) -> None:
        """Because there the value *is* published, and saying otherwise dilutes the flag."""
        log = DegradationLog()
        for index, wavelength_m in enumerate(ITU_SKY_RADIANCE_WAVELENGTHS_M):
            value = interpolated_sky_radiance_w_m2_um_sr(
                wavelength_m, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
            )
            assert value == ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.BRIGHT_SUNSHINE][index]
        assert len(log) == 0

    def test_785_nm_is_interpolated_and_says_so(self) -> None:
        log = DegradationLog()
        value = interpolated_sky_radiance_w_m2_um_sr(
            785e-9, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
        )
        assert value == pytest.approx(142.5218, rel=1e-5)
        assert log.has_degraded
        entry = log.entries[0]
        assert entry.code == "background.sky-radiance-interpolated"
        assert entry.severity is Severity.DEGRADED
        assert entry.details["linear_alternative_w_m2_um_sr"] == pytest.approx(159.0859, rel=1e-5)
        assert entry.details["rule_spread_db"] == pytest.approx(0.4775, abs=1e-3)
        assert entry.details["bracket_nm"] == pytest.approx((530.0, 850.0))
        assert "0009" in entry.message

    def test_the_two_candidate_rules_disagree_by_half_a_decibel(self) -> None:
        """0.48 dB at 785 nm and 0.33 dB at 810 nm, for all three conditions.

        The spread is what a caller can see. It is *not* the uncertainty — see
        the leave-one-out test below, which is worse — and the point of
        measuring both is that the smaller number is the tempting one to quote.
        """
        expected_db = {785e-9: 0.4775, 810e-9: 0.3349}
        for wavelength_m, spread_db in expected_db.items():
            log = DegradationLog()
            interpolated_sky_radiance_w_m2_um_sr(
                wavelength_m, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
            )
            assert log.entries[0].details["rule_spread_db"] == pytest.approx(spread_db, abs=1e-3)

        for condition in SkyCondition:
            log = DegradationLog()
            interpolated_sky_radiance_w_m2_um_sr(785e-9, condition=condition, degradations=log)
            assert log.entries[0].details["rule_spread_db"] == pytest.approx(0.45, abs=0.03)

    def test_the_power_law_rule_is_the_conservative_one(self) -> None:
        """Inside the 530-850 nm bracket the power law reads lower than linear.

        Which is worth stating in a direction: an interpolated radiance from
        this module *understates* the background relative to the linear
        alternative, by up to 0.48 dB. A link budget built on it is optimistic
        by that much, and the degradation record carries the other number so the
        pessimistic reading is one field away.
        """
        for wavelength_m in (600e-9, 700e-9, 785e-9, 810e-9, 840e-9):
            log = DegradationLog()
            power_law = interpolated_sky_radiance_w_m2_um_sr(
                wavelength_m, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
            )
            assert power_law < log.entries[0].details["linear_alternative_w_m2_um_sr"]

    def test_leave_one_out_on_the_tables_own_points(self) -> None:
        """The measurement that makes the gap a gap.

        Drop one interior tabulated point, predict it from its two neighbours
        with each rule, and compare against what the table prints. The rule this
        module uses misses by 16 % to 27 %; the linear alternative by 2 % to
        32 %. Both are larger than the 0.48 dB (11.6 %) spread between the rules
        at 785 nm, which is why the module reports a decibel of unquantified
        error rather than the spread.

        Two caveats stated rather than hidden. The brackets tested here are
        wider than the one 785 nm sits in, and every one of them contains the
        940 nm water-vapour band, which is the worst case in the grid. So this
        bounds the interpolation error by analogy — the table has no interior
        point between 530 and 850 nm, so the error *there* cannot be measured at
        all, and pretending otherwise would be the second-order version of the
        same mistake ADR 0009 forbids.
        """
        wavelengths = np.asarray(ITU_SKY_RADIANCE_WAVELENGTHS_M)
        power_law_errors: list[float] = []
        linear_errors: list[float] = []
        for condition in SkyCondition:
            values = np.asarray(ITU_SKY_RADIANCE_W_M2_UM_SR[condition])
            for index in (1, 2, 3):
                left, right = index - 1, index + 1
                slope = np.log(values[right] / values[left]) / np.log(
                    wavelengths[right] / wavelengths[left]
                )
                power_law = values[left] * (wavelengths[index] / wavelengths[left]) ** slope
                linear = values[left] + (values[right] - values[left]) * (
                    (wavelengths[index] - wavelengths[left])
                    / (wavelengths[right] - wavelengths[left])
                )
                power_law_errors.append(abs(power_law / values[index] - 1.0))
                linear_errors.append(abs(linear / values[index] - 1.0))

        assert min(power_law_errors) == pytest.approx(0.156, abs=0.01)
        assert max(power_law_errors) == pytest.approx(0.269, abs=0.01)
        assert min(linear_errors) == pytest.approx(0.019, abs=0.01)
        assert max(linear_errors) == pytest.approx(0.319, abs=0.01)

        # Every miss of the rule in use exceeds the spread between the rules,
        # which is the specific claim the module docstring makes.
        spread_at_785 = 10.0 ** (0.4775 / 10.0) - 1.0
        assert min(power_law_errors) > spread_at_785

    def test_extrapolation_is_refused_rather_than_clamped(self) -> None:
        """``numpy.interp`` would return the end value in silence."""
        log = DegradationLog()
        with pytest.raises(DomainError, match="outside the range"):
            interpolated_sky_radiance_w_m2_um_sr(
                400e-9, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
            )
        with pytest.raises(DomainError, match="outside the range"):
            interpolated_sky_radiance_w_m2_um_sr(
                1.55e-6, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
            )
        assert len(log) == 0

        # What the clamped answer would have been, and why it is the unsafe
        # direction: the solar spectrum peaks near 500 nm, so the true 400 nm
        # radiance is above the 530 nm entry, not equal to it.
        clamped = float(
            np.interp(
                400e-9,
                np.asarray(ITU_SKY_RADIANCE_WAVELENGTHS_M),
                np.asarray(ITU_SKY_RADIANCE_W_M2_UM_SR[SkyCondition.BRIGHT_SUNSHINE]),
            )
        )
        assert clamped == 303.4

    def test_the_strict_lookup_refuses_1550_nm_and_names_the_alternative(self) -> None:
        """The wavelength of the whole reference paper is not in the table."""
        with pytest.raises(DomainError) as excinfo:
            tabulated_sky_radiance_w_m2_um_sr(1.55e-6, condition=SkyCondition.NORMAL_SUNSHINE)
        message = str(excinfo.value)
        assert "1550.0 nm" in message
        assert "530.0, 850.0, 965.0, 1060.0, 1500.0" in message
        assert "interpolated_sky_radiance_w_m2_um_sr" in message

    def test_1500_and_1550_nm_are_not_the_same_wavelength(self) -> None:
        """The tolerance on the lookup is 1e-9 relative, not "about right".

        50 nm is 3 % in wavelength and a factor of 2.2 in tabulated radiance
        between the bright-sunshine entries at 1060 and 1500 nm, so a lookup
        that rounded to the nearest entry would be a silent substitution.
        """
        assert tabulated_sky_radiance_w_m2_um_sr(
            1.5e-6, condition=SkyCondition.NORMAL_SUNSHINE
        ) == pytest.approx(6.00)
        with pytest.raises(DomainError):
            tabulated_sky_radiance_w_m2_um_sr(1.501e-6, condition=SkyCondition.NORMAL_SUNSHINE)


@pytest.mark.physics
class TestTemporalGating:
    """The one free parameter in the noise budget, and what it is worth."""

    def test_the_erf_law_matches_a_draw_from_the_jitter(self) -> None:
        """**V1**: the closed form against the Gaussian it was derived from.

        Draw arrival times from ``N(0, sigma)`` with ``sigma = FWHM / 2.3548``,
        count how many land inside the gate, and compare with ``erf``. The
        tolerance is three standard errors of a binomial estimate at 200 000
        draws, derived from the sample size.
        """
        source = RandomSource.from_seed(20260911)
        draws = 200_000
        sigma_s = JITTER_FWHM_S / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        arrivals = source.generator.normal(0.0, sigma_s, size=draws)

        for gate_s in (50e-12, 100e-12, 25e-12):
            measured = float(np.count_nonzero(np.abs(arrivals) < 0.5 * gate_s) / draws)
            predicted = float(gate_signal_fraction(gate_s, timing_jitter_fwhm_s=JITTER_FWHM_S))
            standard_error = np.sqrt(predicted * (1.0 - predicted) / draws)
            assert abs(measured - predicted) < 3.0 * standard_error

    def test_the_published_gate_keeps_everything_and_pays_for_it(self) -> None:
        """The 1 ns gate on the 50 ps detector: 0 dB of signal lost, 10 dB of noise kept."""
        kept_1ns = float(gate_signal_fraction(GATE_S, timing_jitter_fwhm_s=JITTER_FWHM_S))
        kept_100ps = float(gate_signal_fraction(100e-12, timing_jitter_fwhm_s=JITTER_FWHM_S))

        assert kept_1ns == pytest.approx(1.0, abs=1e-12)
        assert kept_100ps == pytest.approx(0.981468, rel=1e-5)
        assert float(linear_to_db(kept_1ns / kept_100ps)) == pytest.approx(0.0812, abs=1e-3)
        assert float(linear_to_db(GATE_S / 100e-12)) == pytest.approx(10.0, abs=1e-6)

    def test_the_documented_table_of_gate_widths(self) -> None:
        expected = {
            1e-9: 1.0,
            100e-12: 0.981468,
            59.45e-12: 0.838469,
            50e-12: 0.760968,
            25e-12: 0.443941,
        }
        for gate_s, kept in expected.items():
            assert float(
                gate_signal_fraction(gate_s, timing_jitter_fwhm_s=JITTER_FWHM_S)
            ) == pytest.approx(kept, rel=1e-5)

    def test_reading_the_fwhm_as_a_sigma_costs_2_7_db(self) -> None:
        """The unit trap in the jitter, priced.

        Datasheets quote timing jitter as a FWHM, and the model needs a standard
        deviation; the two differ by 2.3548. At the optimal gate the confusion
        understates the kept signal by 2.7 dB — in the *pessimistic* direction,
        which is why it would survive review: a link budget that is too
        conservative looks careful.
        """
        gate_s = gate_width_maximising_snr_s(JITTER_FWHM_S)
        correct = float(gate_signal_fraction(gate_s, timing_jitter_fwhm_s=JITTER_FWHM_S))
        as_sigma = float(erf(gate_s / (2.0 * np.sqrt(2.0) * JITTER_FWHM_S)))
        assert correct == pytest.approx(0.838482, rel=1e-5)
        assert as_sigma == pytest.approx(0.447835, rel=1e-4)
        assert float(linear_to_db(correct / as_sigma)) == pytest.approx(2.72, abs=0.02)

    def test_the_optimum_is_rederived_with_a_root_finder(self) -> None:
        """**V1**: the module's constant against an independent solve.

        The module states ``2 sqrt(2) x*`` with ``x*`` the root of
        ``(4/sqrt(pi)) x exp(-x^2) = erf(x)``. This solves it with ``brentq``
        and, separately, finds the argmax of the merit function on a grid, so
        neither the algebra nor the constant is taken on trust.
        """
        root = brentq(
            lambda x: (4.0 / np.sqrt(np.pi)) * x * np.exp(-(x**2)) - erf(x),
            0.1,
            5.0,
            xtol=1e-15,
            rtol=8.9e-16,
        )
        assert 2.0 * np.sqrt(2.0) * root == pytest.approx(
            GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS, rel=1e-11
        )

        grid = np.linspace(1e-4, 5.0, 200_001)
        merit = erf(grid) / np.sqrt(grid)
        assert grid[int(np.argmax(merit))] == pytest.approx(root, abs=1e-4)

    def test_the_optimum_is_not_exactly_2_8_sigma(self) -> None:
        """A near-round number, flagged so nobody turns it into an identity.

        2.799970553756 against 2.8 is a coincidence of decimal notation. Left
        unremarked it is the sort of thing that becomes "the optimal gate is
        2.8 sigma exactly" in a later docstring, and then a derivation nobody
        can reproduce.
        """
        assert GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS != 2.8
        assert abs(GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS - 2.8) == pytest.approx(2.945e-5, rel=1e-2)

    def test_the_optimum_in_seconds_scales_with_the_jitter_and_nothing_else(self) -> None:
        assert gate_width_maximising_snr_s(JITTER_FWHM_S) == pytest.approx(59.4519e-12, rel=1e-5)
        assert gate_width_maximising_snr_s(10.0 * JITTER_FWHM_S) == pytest.approx(
            10.0 * gate_width_maximising_snr_s(JITTER_FWHM_S), rel=1e-12
        )

    def test_the_background_level_does_not_move_the_optimum(self) -> None:
        """Including the dark counts, which scale with the gate the same way.

        The reason the optimum is a property of the detector alone: both noise
        terms are proportional to the gate width, so multiplying them by any
        constant leaves the argmax where it was. A test rather than a remark,
        because "the optimum does not depend on the sky" is exactly the kind of
        claim that is obvious and wrong when the noise has a constant term.
        """
        sigma_s = JITTER_FWHM_S / (2.0 * np.sqrt(2.0 * np.log(2.0)))
        gates_s = np.linspace(5e-12, 500e-12, 20_001)
        kept = gate_signal_fraction(gates_s, timing_jitter_fwhm_s=JITTER_FWHM_S)
        for background_cps in (1e3, 1e6, 1e9):
            noise_counts = (background_cps + DARK_COUNT_CPS) * gates_s
            merit = kept / np.sqrt(noise_counts)
            best_s = float(gates_s[int(np.argmax(merit))])
            assert best_s / sigma_s == pytest.approx(GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS, rel=2e-3)

    def test_the_optimum_is_broad(self) -> None:
        """0.55 dB across a factor of three in gate width.

        Measured because the module claims it, and because a sharp optimum
        would make the number a specification and a broad one makes it a
        guideline.
        """
        sigma_s = JITTER_FWHM_S / (2.0 * np.sqrt(2.0 * np.log(2.0)))

        def merit(gate_s: float) -> float:
            kept = float(gate_signal_fraction(gate_s, timing_jitter_fwhm_s=JITTER_FWHM_S))
            return kept / np.sqrt(gate_s)

        best = merit(gate_width_maximising_snr_s(JITTER_FWHM_S))
        for multiple in (1.5, 2.0, 4.0, 5.0):
            penalty_db = float(linear_to_db(best / merit(multiple * sigma_s)))
            assert 0.0 <= penalty_db <= 0.55

        # And the published 1 ns gate, which is 47 sigma, is well outside that.
        assert GATE_S / sigma_s == pytest.approx(47.1, rel=1e-2)
        assert float(linear_to_db(best / merit(GATE_S))) == pytest.approx(5.36, abs=0.02)

    def test_narrowing_the_gate_always_improves_the_noise_to_signal_ratio(self) -> None:
        """The statement that survives any figure of merit.

        ``x / erf(x)`` is monotone increasing, so there is no interior optimum
        for the background-to-signal ratio at all: narrowing always helps the
        QBER and always costs raw rate. The trade-off is a protocol question,
        which is why this module stops here and ``qkd/`` decides.
        """
        gates_s = np.geomspace(1e-13, 1e-8, 500)
        kept = gate_signal_fraction(gates_s, timing_jitter_fwhm_s=JITTER_FWHM_S)
        noise_to_signal = gates_s / kept
        assert np.all(np.diff(noise_to_signal) > 0.0)


@pytest.mark.physics
class TestScalingLaws:
    """The four proportionalities that let a reviewer check a budget by hand."""

    def test_power_scales_with_the_collecting_area(self) -> None:
        small = float(
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=1.0,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        )
        large = float(
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=2.0,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        )
        assert large / small == pytest.approx(4.0, rel=1e-12)

    def test_power_scales_with_the_filter_width(self) -> None:
        narrow = float(
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=0.1e-9,
            )
        )
        wide = float(
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=1.0e-9,
            )
        )
        assert wide / narrow == pytest.approx(10.0, rel=1e-12)

    def test_power_scales_with_the_radiance_and_vanishes_with_it(self) -> None:
        doubled = float(
            background_power_w(
                2.0 * NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        )
        single = float(
            background_power_w(
                NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        )
        assert doubled / single == pytest.approx(2.0, rel=1e-12)

        # A perfectly dark sky is the exact no-background limit, not an error.
        assert (
            float(
                background_power_w(
                    0.0,
                    field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                    receive_aperture_m=HELMOS_M,
                    filter_bandwidth_m=FILTER_BANDWIDTH_M,
                )
            )
            == 0.0
        )

    def test_the_count_rate_scales_with_the_wavelength(self) -> None:
        """Same power, more counts at longer wavelength: photons are cheaper there.

        A factor the eye does not catch in a table of decibels, because it is
        not a loss — it is the conversion from watts to counts, and it is
        linear in ``lambda``.
        """
        at_1550 = float(background_photon_rate_cps(1e-15, wavelength_m=1.55e-6))
        at_775 = float(background_photon_rate_cps(1e-15, wavelength_m=0.775e-6))
        assert at_1550 / at_775 == pytest.approx(2.0, rel=1e-12)

    def test_counts_per_gate_scale_with_the_gate(self) -> None:
        rate_cps = _rate_cps(NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR, HELMOS_M)
        one_ns = float(background_counts_per_gate(rate_cps, gate_duration_s=1e-9))
        ten_ns = float(background_counts_per_gate(rate_cps, gate_duration_s=10e-9))
        assert ten_ns / one_ns == pytest.approx(10.0, rel=1e-12)
        assert one_ns == pytest.approx(7.638563e-6, rel=1e-5)

    def test_shapes_are_preserved_over_the_time_axis(self) -> None:
        """The radiance is the array-valued input, because it is the one that varies."""
        radiances = np.geomspace(
            NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR, NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, 7
        )
        power_w = background_power_w(
            radiances,
            field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
            receive_aperture_m=HELMOS_M,
            filter_bandwidth_m=FILTER_BANDWIDTH_M,
        )
        rate_cps = background_photon_rate_cps(power_w, wavelength_m=WAVELENGTH_M)
        counts = background_counts_per_gate(rate_cps, gate_duration_s=GATE_S)
        probability = background_click_probability(
            rate_cps, gate_duration_s=GATE_S, degradations=DegradationLog()
        )

        assert power_w.shape == radiances.shape
        assert rate_cps.shape == radiances.shape
        assert counts.shape == radiances.shape
        assert probability.shape == radiances.shape
        assert np.all(np.diff(rate_cps) > 0.0)

        # A 2-D input survives too, which is what a sweep over stations crossed
        # with a time axis looks like.
        grid = background_power_w(
            radiances.reshape(7, 1) * np.ones((1, 3)),
            field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
            receive_aperture_m=HELMOS_M,
            filter_bandwidth_m=FILTER_BANDWIDTH_M,
        )
        assert grid.shape == (7, 3)


class TestRejectsBadInput:
    def test_a_negative_radiance_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            background_power_w(
                -1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )

    def test_a_non_finite_radiance_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            background_power_w(
                np.array([1.0, np.nan]),
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )

    def test_the_radiance_message_names_the_per_micrometre_convention(self) -> None:
        """The unit trap worth a sentence: per um, not per nm, a factor of 1000."""
        with pytest.raises(DomainError) as excinfo:
            background_power_w(
                -1e-6,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        assert "per micrometre" in str(excinfo.value)

    @pytest.mark.parametrize("field_of_view_rad", [0.0, -1e-4, np.nan, np.inf])
    def test_a_non_positive_field_of_view_is_rejected(self, field_of_view_rad: float) -> None:
        with pytest.raises(DomainError, match="finite and positive"):
            receiver_solid_angle_sr(field_of_view_rad)

    def test_a_field_of_view_beyond_a_full_sphere_is_rejected(self) -> None:
        """And the message says what a caller who passed steradians did wrong."""
        with pytest.raises(DomainError) as excinfo:
            receiver_solid_angle_sr(7.0)
        message = str(excinfo.value)
        assert "2 pi" in message
        assert "solid angle" in message

    def test_the_aperture_and_bandwidth_guards_carry_their_own_units(self) -> None:
        with pytest.raises(DomainError, match="receive_aperture_m"):
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=0.0,
                filter_bandwidth_m=FILTER_BANDWIDTH_M,
            )
        with pytest.raises(DomainError) as excinfo:
            background_power_w(
                1.0,
                field_of_view_full_angle_rad=FIELD_OF_VIEW_RAD,
                receive_aperture_m=HELMOS_M,
                filter_bandwidth_m=-1.0,
            )
        assert "0.2e-9" in str(excinfo.value)

    def test_a_negative_power_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            background_photon_rate_cps(-1e-15, wavelength_m=WAVELENGTH_M)
        with pytest.raises(DomainError, match="non-finite"):
            background_photon_rate_cps(np.array([np.inf]), wavelength_m=WAVELENGTH_M)

    def test_a_negative_rate_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-negative"):
            background_counts_per_gate(-1.0, gate_duration_s=GATE_S)
        with pytest.raises(DomainError, match="non-finite"):
            background_click_probability(
                np.array([np.nan]), gate_duration_s=GATE_S, degradations=DegradationLog()
            )

    @pytest.mark.parametrize("gate_s", [0.0, -1e-9, np.nan])
    def test_a_non_positive_gate_is_rejected(self, gate_s: float) -> None:
        with pytest.raises(DomainError, match="gate_duration_s"):
            background_counts_per_gate(1e3, gate_duration_s=gate_s)
        with pytest.raises(DomainError, match="gate_duration_s"):
            gate_signal_fraction(gate_s, timing_jitter_fwhm_s=JITTER_FWHM_S)

    def test_a_non_positive_jitter_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="timing_jitter_fwhm_s"):
            gate_signal_fraction(GATE_S, timing_jitter_fwhm_s=0.0)
        with pytest.raises(DomainError, match="timing_jitter_fwhm_s"):
            gate_width_maximising_snr_s(-50e-12)

    def test_the_wavelength_guard_of_validation_is_not_bypassed(self) -> None:
        with pytest.raises(DomainError, match="wavelength_m"):
            background_photon_rate_cps(1e-15, wavelength_m=0.0)
        with pytest.raises(DomainError, match="wavelength_m"):
            tabulated_sky_radiance_w_m2_um_sr(-1.0, condition=SkyCondition.OVERCAST)


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import background

        assert background.__all__ == sorted(background.__all__)
        for name in background.__all__:
            assert hasattr(background, name)

    def test_the_module_documents_both_sources(self) -> None:
        from quoss.channel import background

        assert background.__doc__ is not None
        assert "P.1621-2" in background.__doc__
        assert "Ntanos" in background.__doc__

    def test_the_module_declares_what_it_leaves_out(self) -> None:
        """Each omission named with where it goes instead, or why there is nowhere."""
        from quoss.channel import background

        assert background.__doc__ is not None
        for absent in (
            "zenith",
            "Uplink background",
            "Moonlight as a function of phase",
            "city lights",
            "detector",
            "link_budget",
            "0009",
        ):
            assert absent in background.__doc__

    def test_no_function_here_takes_an_elevation(self) -> None:
        """The negative control for the gap that would be easiest to fill wrongly.

        Sky radiance certainly depends on where the telescope points — the
        scattering path at 20 degrees is 2.92 air masses against 1 at zenith,
        which would be 4.66 dB if the radiance simply followed it. Neither
        source publishes that dependence, so the module takes the radiance as a
        given and no signature offers a place to put an elevation. If one ever
        appears, it should arrive with a citation and this test should be the
        thing that notices.
        """
        import inspect

        from quoss.channel import background

        for name in background.__all__:
            attribute = getattr(background, name)
            if not callable(attribute) or isinstance(attribute, type):
                continue
            parameters = inspect.signature(attribute).parameters
            assert not any("elevation" in parameter for parameter in parameters)
            assert not any("zenith" in parameter for parameter in parameters)

    def test_there_is_no_random_generator_in_this_module(self) -> None:
        """Same rule as ``channel/pointing.py``: randomness lives in ``core/rng.py``."""
        import ast
        import inspect

        from quoss.channel import background

        tree = ast.parse(inspect.getsource(background))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any("rng" in name or "random" in name for name in imported)
        assert hasattr(RandomSource, "from_seed")

    def test_the_sky_condition_enum_has_no_night_member(self) -> None:
        """Because the night value has a different pedigree: prose, not a table.

        A ``SkyCondition.NIGHT`` would make ``tabulated_sky_radiance`` return a
        number that is not in Table 1 through the same call that returns numbers
        that are, and the two published night values differ by a factor of ten.
        Keeping them as separate constants is what makes a caller choose.
        """
        assert {member.value for member in SkyCondition} == {
            "bright_sunshine",
            "normal_sunshine",
            "overcast",
        }
        assert not hasattr(SkyCondition, "NIGHT")
