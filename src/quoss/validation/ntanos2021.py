"""Validation cases for the paper this project's reference link is built on, and its two protocols.

Para quien llegue nuevo: **this is the source of the reference link, not one
source among several.** Ntanos et al. 2021 supplies the receiver (the
superconducting-nanowire detectors, their dead time, their gate, their dark
count rate), the transmitter (the 0.15 m aperture and the 0.75 µrad pointing
jitter), the protocol parameters (the two decoy intensities and the state
ratio), the night-sky radiance the study uses, and the three Greek ground
stations. Almost every number in ``scenarios/reference_castelldefels.yaml``
that is not a coordinate of Castelldefels came from that paper.

That is exactly why this module has to exist, and why it was the last one
written. A table of validation cases that covers the ITU-R recommendations and
two external systems, and leaves out the paper the whole link is assembled
from, is a table that says "validated" about the parts nobody was worried
about. Until this module landed, anything reported as validated against Ntanos
et al. traced to assertions scattered through ``tests/channel/`` and
``tests/qkd/`` and not to a row a reader could check.

The three sources, and why they are one module
-----------------------------------------------
A **validation case module** collects the published numbers of one source. This
one collects three, because they are not independent: Ntanos et al. evaluate
their link with the decoy-state formulas of **Ma et al. 2005** (their Appendix
A is Ma's Eqs. (10)-(11) with different symbols) and this project charges the
finite block of a pass with the bound of **Lim et al. 2014**. Splitting them
into three files would put the same link's gain in three places and make the
reader chase which paper owns which equation. They are separated in the
rendered table by source, which is what a reader needs.

What "published" means in a row of this module
-----------------------------------------------
Two things, and the difference matters:

- A number **printed as a number**: the "10 kcps at most" of §4.2.2, the
  "about 13 µrad" of §4.1, the 20 dB of §4.2.1, the 3.33e-4 bits per pulse of
  §4.3.1, the four coordinates of §2.
- A number **printed as an equation**, evaluated here at the paper's own stated
  parameters. Ntanos et al.'s Eq. (5) and Eq. (18), Ma et al.'s Eq. (10) and
  Lim et al.'s ``D_k`` are transcribed into this file — written out rather than
  imported, so that the published side of a comparison is the paper and not
  this project's version of it — and evaluated at the parameters the same paper
  states. This is the pattern :mod:`quoss.validation.satquma` already uses for
  Sidhu et al.'s Eq. (4), and :mod:`quoss.validation.channel` for Farid &
  Hranilovic's Eq. (11).

The second kind is not weaker than the first. An equation printed with a
transposed factor is a published claim exactly as much as a printed number is,
and it is the kind this project has found most often.

The headline of the module, in one sentence
--------------------------------------------
**Of the eleven Ntanos et al. rows below, two reproduce, one is compatible
once an unstated extinction is accounted for, one is a declared gap, and
seven do not reproduce.** That is not a verdict on the paper: it is the most
carefully parameterised source this project has, which is precisely why so many
of its printed consequences can be checked at all. A source whose parameters
were vaguer would produce a shorter table and a false sense of agreement.

What each disagreement is, in one line each, is in the note of its row and in
the Ntanos caveat of ``docs/adr/0009-citation-policy.md``. The pattern behind
three of them is worth naming here because it is one mistake made three times
in two papers: **a mean is not a probability.** Ntanos et al.'s Eq. (20) calls
``t_gate x cps`` a probability, their Eq. (A6) writes a union of two
probabilities as a sum, and Ma et al.'s Eq. (10) writes the gain as
``Y_0 + (1 - e^{-eta mu})`` instead of the union of the two. All three are
first-order expansions that are excellent at night and leave ``[0, 1]`` in
daylight. This project's rule, in one line: **means add, and the exponential is
taken once, at the end.**

What is deliberately **not** here
----------------------------------
``lim2014.block-1e4-reach``. Lim et al. state that "even if we use a block size
of 1e4, cryptographic keys can still be distributed over a fiber length of
135 km", and this project does not reproduce it: with a block of 1e4 detections
in the key basis it certifies no key at any fibre length, and the curve that
does reach 135 km is the one a decade larger. That is measured and asserted, in
``tests/qkd/test_finite_key.py::TestLim2014Evaluation``, and it stays in
:data:`~quoss.validation.base.PENDING_DISAGREEMENTS` rather than becoming a row
here. The reason is a cost this module would pay in the wrong currency:
reaching their number needs their optimisation over five free parameters
(``q_x``, the two state probabilities and the two intensities), which is about
120 lines of transcription living beside that test. Moving it into ``src/`` to
buy one row would make this project carry **two** implementations of Lim et
al.'s Evaluation section, and one formula in two places is the defect
``docs/adr/0016`` exists to prevent. The honest position is a declared hole
with its measurement named, which is the same rule ADR 0009 applies to
citations.
"""

from __future__ import annotations

import math
from typing import Final

import numpy as np

from quoss.channel.background import (
    NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR,
    NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
    SkyCondition,
    background_click_probability,
    background_counts_per_gate,
    background_photon_rate_cps,
    background_power_w,
    tabulated_sky_radiance_w_m2_um_sr,
)
from quoss.channel.beam import divergence_half_angle_rad, geometric_transmittance
from quoss.channel.detector import (
    LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
    LIM_INGAAS_EFFICIENCY,
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
    click_probability,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    NTANOS_BEST_CASE_TOTAL_LOSS_DB,
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_MINIMUM_ELEVATION_RAD,
    NTANOS_ORBIT_HEIGHT_KM,
    NTANOS_OUTAGE_PROBABILITY,
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_POLARISATION_LOSS_DB,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    FadeCombination,
    downlink_loss_budget,
    downlink_noise_budget,
    scintillation_fade_db,
)
from quoss.channel.turbulence import downlink_log_irradiance_variance
from quoss.core.errors import DegradationLog
from quoss.core.units import km_to_m
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
from quoss.qkd.bb84 import (
    NTANOS_SIGNAL_INTENSITY,
    NTANOS_STATE_COUNTS,
    Bb84DecoyProtocol,
    simulate_intensity,
)

# The one import that reaches above the physics layer, and the reason it is
# right: the case that checks the printed station coordinates has to compare the
# paper's numbers with *the coordinates this project actually flies over*, which
# live in the scenario defaults. Retyping them here would compare the paper with
# a second transcription of the paper and could not fail. The dependency guard
# in tests/unit/test_conventions.py leaves quoss.validation outside the ladder
# for exactly this kind of consumer.
from quoss.scenario.defaults import NTANOS_STATIONS
from quoss.validation.base import AccountedTerm, Comparison, ValidationCase

__all__ = [
    "LIM_2014",
    "MA_2005",
    "NTANOS_2021",
    "NTANOS_APERTURE_RATIO_AS_PRINTED",
    "NTANOS_FULL_MOON_CLAIM_CPS",
    "NTANOS_PEAK_SECRET_BITS_PER_PULSE",
    "NTANOS_PRINTED_DIVERGENCE_URAD",
    "NTANOS_PRINTED_PROTOCOL_EFFICIENCY",
    "NTANOS_PRINTED_STATE_COUNTS",
    "NTANOS_WAVELENGTH_M",
    "cases",
]

NTANOS_2021: Final = (
    "A. Ntanos, N. K. Lyras, D. Zavitsanos, G. Giannoulis, A. D. Panagopoulos and H. Avramopoulos, "
    "LEO Satellites Constellation-to-Ground QKD Links: Greek Quantum Communication "
    "Infrastructure Paradigm, Photonics 8(12):544 (2021), open access at mdpi.com"
)
MA_2005: Final = (
    "X. Ma, B. Qi, Y. Zhao and H.-K. Lo, Practical decoy state for quantum key distribution, "
    "Phys. Rev. A 72, 012326 (2005), preprint arXiv:quant-ph/0503005v5 opened via "
    "export.arxiv.org; the source of Ntanos et al. 2021 Appendix A"
)
LIM_2014: Final = (
    "C. C. W. Lim, M. Curty, N. Walenta, F. Xu and H. Zbinden, Concise security bounds for "
    "practical decoy-state quantum key distribution, Phys. Rev. A 89, 022307 (2014), preprint "
    "arXiv:1311.7129v2 opened via export.arxiv.org; the finite-key bound this project charges"
)

NTANOS_WAVELENGTH_M: Final = 1550e-9
"""§4.1: "operating at the telecom C-band (1550 nm)". The wavelength of the whole link."""

NTANOS_PRINTED_DIVERGENCE_URAD: Final = 13.0
"""§4.1: "an aperture of 0.15 m [...] providing a small beam divergence of about 13 urad"."""

NTANOS_FULL_MOON_CLAIM_CPS: Final = 10e3
"""§4.2.2: "Even in the case of full moon, the background radiance corresponds to 10 kcps in
the photon counter at most"."""

NTANOS_PRINTED_STATE_COUNTS: Final = (4, 1, 16)
"""§4.1, the signal:decoy:vacuum ratio as printed. This project uses it reversed; see the case."""

NTANOS_PRINTED_PROTOCOL_EFFICIENCY: Final = 0.4
"""§4.1: "about q = 2/5", printed in the same sentence as the 4:1:16 above."""

NTANOS_PEAK_SECRET_BITS_PER_PULSE: Final = 3.33e-4
"""§4.3.1, the peak of the single-pass secret key rate curve, in secret bits per emitted pulse."""

NTANOS_APERTURE_RATIO_AS_PRINTED: Final = 4.0
"""§4.3.2: the Helmos (2.3 m) station yields "about four times" what Skinakas (1.3 m) does."""

# Ntanos et al.'s own reference geometry, all from §4.1 and §4.2.1, used by several cases.
_ZENITH_RAD: Final = 0.5 * math.pi
_HELMOS_APERTURE_M: Final = 2.3
_SKINAKAS_APERTURE_M: Final = 1.3
_CHOLOMONDAS_APERTURE_M: Final = 0.75
_GATE_S: Final = 1e-9
_MISALIGNMENT_ERROR: Final = 0.01

# ITU-R P.1621-2 Table 3's brightest tabulated sky, at the tabulated wavelength nearest the
# 780-810 nm band the Eq. (20) discussion is written for. Used only to put Eq. (20) somewhere
# it can be checked: at 1550 nm at night the two readings agree to seven digits and nothing
# is learnt.
_DAYLIGHT_WAVELENGTH_M: Final = 850e-9

# Lim et al.'s Evaluation section: mu = 0.5 over 100 km of 0.2 dB/km fibre.
_LIM_INTENSITY: Final = 0.5
_LIM_FIBRE_KM: Final = 100.0
_LIM_FIBRE_DB_PER_KM: Final = 0.2

_LINK_TEST: Final = "tests/channel/test_link_budget.py::TestAgainstNtanosEtAl::"
_BACKGROUND_TEST: Final = "tests/channel/test_background.py::"
_OWN_TEST: Final = "tests/validation/test_ntanos2021.py::"


def _codes(log: DegradationLog) -> tuple[str, ...]:
    """Sorted, de-duplicated degradation codes, for the case record."""
    return tuple(sorted({entry.code for entry in log}))


def _receiver_chain() -> float:
    """Return the 6.36 dB receiver chain of §4.1 as a linear factor.

    85 % nanowires behind 3 dB of filter insertion and 2.65 dB of receiver
    optics, which is the chain every count in this module passes through.
    """
    return receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )


def _background_rate_cps(
    radiance_w_m2_um_sr: float, aperture_m: float, *, wavelength_m: float = NTANOS_WAVELENGTH_M
) -> float:
    """Background photons per second at the aperture, their Eq. (19) through this project."""
    power_w = background_power_w(
        radiance_w_m2_um_sr,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        receive_aperture_m=aperture_m,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
    )
    return float(background_photon_rate_cps(power_w, wavelength_m=wavelength_m))


def _total_loss_db(aperture_m: float, elevation_rad: float, log: DegradationLog) -> float:
    """Their §4.2.1 budget through this project, at zero extinction as they state it."""
    return float(
        downlink_loss_budget(
            elevation_rad,
            range_km=NTANOS_ORBIT_HEIGHT_KM,
            wavelength_m=NTANOS_WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=aperture_m,
            zenith_transmittance=1.0,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=_receiver_chain(),
            outage_probability=NTANOS_OUTAGE_PROBABILITY,
            static_loss_db=NTANOS_POLARISATION_LOSS_DB,
            fade_combination=FadeCombination.ADDITIVE,
            degradations=log,
        ).total_db
    )


def _secret_bits_per_pulse(total_loss_db: float, log: DegradationLog) -> float:
    """Asymptotic secret bits per emitted pulse at a given total link loss.

    Their protocol (``Bb84DecoyProtocol.ntanos_2021``: mu = 0.56, nu = 0.11,
    f = 1.22) on their night noise and their 1 % misalignment, which is what
    their §4.3 curves plot against elevation.
    """
    transmittance = 10.0 ** (-total_loss_db / 10.0)
    conditions = LinkConditions(
        transmittance=np.asarray(transmittance, dtype=np.float64),
        noise_counts_per_gate=_night_noise_per_gate(),
        misalignment_error=_MISALIGNMENT_ERROR,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=_GATE_S,
    )
    rate = Bb84DecoyProtocol.ntanos_2021().key_rate(conditions, degradations=log)
    return float(np.ravel(rate.secure_per_pulse)[0])


def _night_noise_per_gate() -> float:
    """Noise counts per gate on the study night, at the reference 0.75 m station.

    Assembled by :func:`~quoss.channel.link_budget.downlink_noise_budget` from
    the paper's own radiance and its own nanowires, rather than copied from the
    ``7.8797e-7`` literal the rest of the suite writes, so the three key-rate
    cases below rest on the paper and not on a number somebody typed.

    The three terms and where each enters: the sky arrives through the aperture
    and is attenuated by the 6.36 dB chain, the two nanowires' dark counts are
    born behind the optics and are not, and the afterpulses are proportional to
    the clicks. Adding them as means and exponentiating once is the rule this
    module's headline names.
    """
    return float(
        downlink_noise_budget(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            wavelength_m=NTANOS_WAVELENGTH_M,
            receive_aperture_m=_CHOLOMONDAS_APERTURE_M,
            field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
            filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
            gate_duration_s=_GATE_S,
            receiver_efficiency=_receiver_chain(),
            dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            degradations=DegradationLog(),
            detector_count=2,
            afterpulse_probability=NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
        ).total_per_gate
    )


def _printed_eq5_transmittance(receive_aperture_m: float) -> float:
    """Ntanos et al. Eq. (5) **exactly as printed**, at their §4.1 geometry.

    Their equation is a product of three standard factors::

        eta_geo = G_t G_r L_fsl,  G_t = (8 / w_0)^2,  G_r = (pi D_r / lambda)^2,
        L_fsl = (lambda / (4 pi z))^2

    with ``w_0 = 2 lambda / (pi D_t)`` their Eq. (6) divergence *half angle*.
    The transmitter gain of a Gaussian beam is ``8 / w_0^2``, not ``(8 / w_0)^2``:
    the 8 belongs outside the square. Written out here rather than imported so
    that what this case calls "published" is the paper's expression and not this
    project's.
    """
    divergence = divergence_half_angle_rad(
        wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
    )
    transmit_gain = (8.0 / divergence) ** 2
    receive_gain = (math.pi * receive_aperture_m / NTANOS_WAVELENGTH_M) ** 2
    range_m = float(km_to_m(NTANOS_ORBIT_HEIGHT_KM))
    free_space_loss = (NTANOS_WAVELENGTH_M / (4.0 * math.pi * range_m)) ** 2
    return float(transmit_gain * receive_gain * free_space_loss)


def _printed_eq18_level_db(log_irradiance_variance_np2: float) -> float:
    """Ntanos et al. Eq. (18) **exactly as printed**, sign and rounded factor included.

    ``L_sci(dB) = 4.343 [erf^-1(2 p_0 - 1) sqrt(2 ln(sigma_I^2 + 1))
    - (1/2) ln(sigma_I^2 + 1)]``

    Two transcription details carry the whole of this case:

    - Their argument is the **scintillation index** ``sigma_I^2`` (the
      normalised variance of the irradiance itself), while this project's
      turbulence module returns ``sigma_lnI^2`` (the variance of its natural
      logarithm). The two are related by ``sigma_I^2 = exp(sigma_lnI^2) - 1``,
      so the conversion is inverted here and the two expressions are asked
      about one physical turbulence rather than two.
    - They print the neper-to-decibel factor as ``4.343`` where it is
      ``10 / ln 10 = 4.342944819``. That rounding is the entire residual of
      this case, and it is why its tolerance can be derived exactly.
    """
    from scipy.special import erfinv

    scintillation_index = math.expm1(log_irradiance_variance_np2)
    log_term = math.log1p(scintillation_index)
    return 4.343 * (
        float(erfinv(2.0 * NTANOS_OUTAGE_PROBABILITY - 1.0)) * math.sqrt(2.0 * log_term)
        - 0.5 * log_term
    )


def _printed_eq_a1_protocol_efficiency(counts: tuple[int, int, int]) -> float:
    """Ntanos et al. Eq. (A1): ``q = (1/2) N_signal / (N_signal + N_decoy + N_vacuum)``.

    The one-half is the sifting factor of symmetric BB84 (Alice and Bob pick the
    same basis half the time); the fraction is the share of pulses sent at the
    signal intensity, because only those become key.
    """
    signal, decoy, vacuum = counts
    return 0.5 * signal / (signal + decoy + vacuum)


def _printed_ma_eq10_gain(transmittance: float, noise_per_gate: float, intensity: float) -> float:
    """Ma et al. 2005 Eq. (10), which is Ntanos et al. Eq. (A4): ``Q_mu = Y_0 + 1 - e^{-eta mu}``.

    ``Y_0`` is the background yield — the probability that a gate with no signal
    photon clicks anyway — and ``1 - e^{-eta mu}`` is the probability that the
    signal fires. The printed form **adds** the two, which double-counts the
    gates where both fire; the union is ``1 - (1 - Y_0) e^{-eta mu}``. Written
    with ``Y_0 = 1 - e^{-mu_noise}`` so the noise enters as the mean it is.
    """
    background_yield = -math.expm1(-noise_per_gate)
    return background_yield + 1.0 - math.exp(-transmittance * intensity)


def _printed_lim_detection_rate(fibre_km: float, intensity: float) -> float:
    """Lim et al. 2014 Evaluation, ``D_k = 1 - (1 - 2 p_dc) e^{-eta_sys k}``, as printed.

    ``2 p_dc`` is the first order of the exact two-detector union
    ``1 - (1 - p_dc)^2``. Their channel is theirs too: "the fibers have an
    attenuation coefficient of 0.2 dB/km. That is, their transmittance is
    ``eta_ch = 10^{-0.2 L / 10}``".
    """
    channel = 10.0 ** (-_LIM_FIBRE_DB_PER_KM * fibre_km / 10.0)
    system = channel * LIM_INGAAS_EFFICIENCY
    return 1.0 - (1.0 - 2.0 * LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE) * math.exp(
        -system * intensity
    )


def _ntanos_cases() -> list[ValidationCase]:
    """Return the eleven rows of the paper the reference link is built on."""
    log = DegradationLog()

    divergence_urad = 2e6 * float(
        divergence_half_angle_rad(
            wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
        )
    )

    printed_eq5 = _printed_eq5_transmittance(_HELMOS_APERTURE_M)
    exact_eq5 = float(
        geometric_transmittance(
            NTANOS_ORBIT_HEIGHT_KM,
            wavelength_m=NTANOS_WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=_HELMOS_APERTURE_M,
        )
    )

    variance_np2 = float(
        downlink_log_irradiance_variance(
            NTANOS_MINIMUM_ELEVATION_RAD,
            aperture_diameter_m=_CHOLOMONDAS_APERTURE_M,
            wavelength_m=NTANOS_WAVELENGTH_M,
            degradations=log,
        )
    )
    printed_eq18 = _printed_eq18_level_db(variance_np2)
    our_level_db = -float(scintillation_fade_db(variance_np2, outage_probability=0.01))

    budget_log = DegradationLog()
    best_case_db = _total_loss_db(_HELMOS_APERTURE_M, _ZENITH_RAD, budget_log)

    daylight_radiance = float(
        tabulated_sky_radiance_w_m2_um_sr(
            _DAYLIGHT_WAVELENGTH_M, condition=SkyCondition.BRIGHT_SUNSHINE
        )
    )
    daylight_rate_cps = _background_rate_cps(
        daylight_radiance, _HELMOS_APERTURE_M, wavelength_m=_DAYLIGHT_WAVELENGTH_M
    )
    printed_eq20 = float(background_counts_per_gate(daylight_rate_cps, gate_duration_s=_GATE_S))
    exact_click = float(
        background_click_probability(
            daylight_rate_cps, gate_duration_s=_GATE_S, degradations=DegradationLog()
        )
    )

    full_moon_cps = _background_rate_cps(NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR, _HELMOS_APERTURE_M)

    key_log = DegradationLog()
    helmos_bits = _secret_bits_per_pulse(best_case_db, key_log)
    skinakas_bits = _secret_bits_per_pulse(
        _total_loss_db(_SKINAKAS_APERTURE_M, _ZENITH_RAD, key_log), key_log
    )

    _, skinakas_latitude_deg, _, _ = NTANOS_STATIONS[_SKINAKAS_APERTURE_M]

    return [
        ValidationCase.evaluate(
            identifier="ntanos2021.divergence-full-angle",
            source=NTANOS_2021,
            locator=(
                "§4.1: 'an aperture of 0.15 m [...] providing a small beam divergence of about "
                "13 urad', with Eq. (6) w_0 = 2 lambda / (pi D_t) at 1550 nm"
            ),
            quantity="transmitter beam divergence, full angle",
            published=NTANOS_PRINTED_DIVERGENCE_URAD,
            computed=divergence_urad,
            unit="urad",
            tolerance=0.5,
            tolerance_basis=(
                "Half a unit in the last printed digit of 'about 13': the number is given to "
                "two significant figures with a hedge, which licenses +/- 0.5 urad."
            ),
            level="V2",
            note=(
                "13.157 urad, and the row exists for which angle it is. Their own Eq. (6) is a "
                "half angle and gives 6.578 urad, so the printed 13 is the full angle. Reading "
                "it as the half angle would halve every beam radius downstream and delete "
                "6 dB of geometric loss that is there — the largest single error a reader of "
                "§4.1 can make in one step."
            ),
            test=_LINK_TEST + "test_their_13_microradian_divergence_is_the_full_angle",
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.eq5-printed-gain-product",
            source=NTANOS_2021,
            locator=(
                "Eq. (5) as printed, G_t = (8/w_0)^2, at §4.1: 0.15 m transmitter, 2.3 m "
                "receiver, 600 km, 1550 nm"
            ),
            quantity="geometric transmittance of the downlink onto the largest station",
            published=printed_eq5,
            computed=exact_eq5,
            unit="1",
            tolerance=0.1 * printed_eq5,
            tolerance_basis=(
                "10 % of the published value, derived from the widest gap the *energy-conserving* "
                "reading of the same product form leaves against the Gaussian integral this "
                "project computes: 0.94 %, 2.8 % and 8.8 % at their 0.75, 1.3 and 2.3 m "
                "stations, because the product form linearises 1 - exp(-x) and uses the "
                "far-field radius w_0 z instead of the exact W(z). Ten per cent covers all "
                "three and is still eighty times narrower than the disagreement below."
            ),
            level="V2",
            note=(
                "A factor of exactly 8, so 9.03 dB optimistic, and the settling argument needs "
                "no appeal to this project at all: at their own largest telescope the printed "
                "form returns a transmittance of 1.358, a receiver collecting 36 % more light "
                "than the transmitter sent. The 8 belongs outside the square (G_t = 8/w_0^2), "
                "and with it the product form and the Gaussian integral agree to 0.94 % at "
                "0.75 m. Corroborated by their own §4.2.1 total: with the energy-conserving "
                "reading the geometric term is 8.07 dB and the declared terms reach 14.7 dB, "
                "leaving about 5 dB for the atmosphere; with the printed one the geometric term "
                "is a *gain* of -1.33 dB and no atmosphere closes the 15 dB that opens up."
            ),
            test=(
                "tests/channel/test_beam.py::TestPublishedGainProduct::"
                "test_the_printed_form_collects_more_power_than_was_transmitted"
            ),
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.eq18-scintillation-quantile",
            source=NTANOS_2021,
            locator=(
                "Eq. (18) at p_0 = 1 %, 20 deg elevation, 0.75 m station, 1550 nm "
                "(sigma_lnI^2 = 0.015276 Np^2 from ITU-R P.1622 Eq. (4b))"
            ),
            quantity="1 %-quantile irradiance level relative to the mean, scintillation only",
            published=printed_eq18,
            computed=our_level_db,
            unit="dB",
            tolerance=1.3e-5 * abs(printed_eq18),
            tolerance_basis=(
                "1.3e-5 relative, and it is an identity rather than a margin: the paper prints "
                "the neper-to-decibel factor as 4.343 where it is 10/ln(10) = 4.342944819, and "
                "4.343 / (10/ln 10) - 1 = 1.2706e-5 is the whole of the residual. Nothing else "
                "separates the two expressions."
            ),
            level="V2",
            note=(
                "Reproduced at -1.28190 dB against -1.28188 dB, and the row exists for the "
                "sign. Eq. (18) is 10 log10 of the p_0 quantile of the irradiance, so below the "
                "median it is **negative**: it is the signal *level* relative to the mean, not "
                "the drop from it, and the paper adds it to a budget of positive losses. Doing "
                "that leaves the total wrong by twice the fade, 2.564 dB here. "
                "quoss.channel.link_budget.scintillation_fade_db returns the negated form, "
                "which is why the computed column is negated to meet it."
            ),
            test=_LINK_TEST + "test_equation_18_reproduces_and_its_sign_is_a_gain",
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.best-case-total-loss",
            source=NTANOS_2021,
            locator=(
                "§4.2.1: 'the total link loss for a 600 km link distance can get as low as "
                "20 dB in total', at the §4.1 parameters with the 2.3 m station at zenith"
            ),
            quantity="total downlink loss, best case",
            published=NTANOS_BEST_CASE_TOTAL_LOSS_DB,
            computed=best_case_db,
            unit="dB",
            tolerance=0.5,
            tolerance_basis=(
                "Half a unit in the last printed digit: '20 dB' is given to the unit, which "
                "licenses +/- 0.5 dB and nothing tighter."
            ),
            level="V2",
            accounted=AccountedTerm(
                name="unstated atmospheric extinction",
                lower=0.0,
                upper=math.inf,
                basis=(
                    "One-sided by physics: an extinction is an attenuation, so it can only add "
                    "loss. The paper states no zenith transmittance anywhere, and their own "
                    "Eq. (7) needs one."
                ),
            ),
            note=(
                "19.094 dB from their own parameters, 0.906 dB short, and compatible rather "
                "than reproduced. The residual read through their Eq. (7) is L_zen = 0.812, an "
                "ordinary clear-sky zenith transmittance at 1550 nm — but a residual landing in "
                "a plausible range is not evidence that it *is* the thing it resembles, which "
                "is the whole reason 'compatible' is a separate status and not a widened "
                "tolerance. The term that made it plausible is this project's and not theirs: "
                "3.352 dB of Gaussian truncation for a transmitter that clips its beam at the "
                "waist radius. Without it the residual is 4.259 dB, needing L_zen = 0.375, an "
                "order of magnitude more extinction than anything credible at this wavelength. "
                "The missing decibels were in the transmitter, not in the atmosphere. This is "
                "the weakest form of compatibility the table has — a term unbounded above — and "
                "it is labelled as such."
            ),
            test=_LINK_TEST + "test_their_twenty_decibel_best_case_does_not_reproduce",
            degradations=_codes(budget_log),
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.zenith-transmittance",
            source=NTANOS_2021,
            locator=(
                "Eq. (7), L_a = L_zen^(1/cos zeta): the value of L_zen is never stated, in "
                "§4.1, §4.2.1 or anywhere else"
            ),
            quantity="clear-sky zenith atmospheric transmittance at 1550 nm",
            published=None,
            computed=None,
            unit="1",
            tolerance=None,
            tolerance_basis="None: the source prints no value, so there is nothing to compare.",
            level="V2",
            note=(
                "Gap, and it is the input the row above turns on. Their Eq. (7) raises a zenith "
                "transmittance to the air mass, which makes L_zen the single most load-bearing "
                "atmospheric number in their budget, and the paper never gives it. It cannot be "
                "read off ITU-R P.1621-2 Figures 1, 2 and 4 either: reading a value from a plot "
                "and calling it published is what ADR 0009 forbids, which is why "
                "quoss.validation.channel declines those figures and points here. What this "
                "project does instead is compute the extinction from a stated meteorological "
                "visibility (ADR 0023), so it never needs their number — and that is also why "
                "the 20 dB row above can only be compatible and never reproduced."
            ),
            test=_OWN_TEST + "TestTheDeclaredGap::test_no_zenith_transmittance_is_printed",
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.eq20-background-click-probability",
            source=NTANOS_2021,
            locator=(
                "Eq. (20), P_back = t_gate x R_back, at ITU-R P.1621-2 bright sunshine "
                "(850 nm, the nearest tabulated wavelength), 2.3 m station, 1 ns gate"
            ),
            quantity="probability that a gate contains a background click",
            published=printed_eq20,
            computed=exact_click,
            unit="1",
            tolerance=0.05 * printed_eq20,
            tolerance_basis=(
                "5 % of the published value, which is this project's own derived limit for "
                "accepting the linear reading at all: quoss.channel.background warns above "
                "LINEAR_CLICK_PROBABILITY_LIMIT = 0.1 counts per gate precisely because that is "
                "where t_gate x R_back overstates 1 - exp(-mu) by 5 %."
            ),
            level="V2",
            note=(
                "The printed form returns **3.42**, which is not a probability. Eq. (20) calls "
                "t_gate x R_back a probability when it is the expected *number* of counts in a "
                "gate; the two agree to seven digits at night and part company in daylight. "
                "Not an artefact of taking their largest telescope: the 1.3 m station crosses "
                "unity too, at 1.091. The exact form 1 - exp(-mu) returns 0.967 and stays a "
                "probability for arbitrarily bright sky. Same mistake as their Eq. (A6) and as "
                "Ma et al.'s Eq. (10) below; means add, and the exponential is taken once."
            ),
            test=_BACKGROUND_TEST
            + "TestAMeanIsNotAProbability::test_the_published_form_returns_a_probability_above_one",
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.full-moon-background",
            source=NTANOS_2021,
            locator=(
                "§4.2.2: 'Even in the case of full moon, the background radiance corresponds to "
                "10 kcps in the photon counter at most', through their Eq. (19) at 2.3 m"
            ),
            quantity="background count rate at the aperture, full moon",
            published=NTANOS_FULL_MOON_CLAIM_CPS,
            computed=full_moon_cps,
            unit="cps",
            comparison=Comparison.AT_MOST,
            tolerance=500.0,
            tolerance_basis=(
                "Half a unit in the last printed digit of '10 kcps', which is +/- 0.5 kcps. "
                "The claim is one-sided ('at most'), so the tolerance is applied on one side."
            ),
            level="V2",
            note=(
                "76.4 kcps at the station their own best result uses, 7.6 times the claim. The "
                "sentence is only reproducible for their *smallest* telescope — 8.1 kcps at "
                "0.75 m, 24.4 at 1.3 m — and 'at most' argues against that reading. The obvious "
                "rescue fails too: if the 10 kcps were meant after the 6.36 dB chain the same "
                "section declares, the 2.3 m station still gives 17.7 kcps, 1.8 times the "
                "claim. Reported as unreproducible rather than reinterpreted, because choosing "
                "the reading that makes the number come out is fitting the citation to the "
                "result."
            ),
            test=_BACKGROUND_TEST
            + "TestTheFullMoonClaim::test_only_the_smallest_telescope_reproduces_the_printed_10_kcps",
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.protocol-efficiency-as-printed",
            source=NTANOS_2021,
            locator=(
                "§4.1: a 'signal:decoy:vacuum ratio = 4:1:16' and 'about q = 2/5' in one "
                "sentence, through their own Eq. (A1)"
            ),
            quantity="protocol efficiency q, from the printed state ratio",
            published=NTANOS_PRINTED_PROTOCOL_EFFICIENCY,
            computed=_printed_eq_a1_protocol_efficiency(NTANOS_PRINTED_STATE_COUNTS),
            unit="1",
            tolerance=0.05,
            tolerance_basis=(
                "Half a unit in the last digit of 'about 2/5' read as 0.4, so +/- 0.05. A "
                "hedged fraction printed to one decimal licenses nothing tighter."
            ),
            level="V2",
            note=(
                "0.0952 against 0.4: the two halves of one sentence disagree by a factor of "
                "**4.2**, and the disagreement is internal to the paper rather than between the "
                "paper and this project. Eq. (A1) is q = (1/2) N_sig / (N_sig + N_dec + N_vac), "
                "so 4:1:16 gives 0.0952 and the reversed order 16:1:4 gives 0.3810, which is "
                "what 'about 2/5' means. This project sends the reversed order "
                f"(NTANOS_STATE_COUNTS = {NTANOS_STATE_COUNTS}) and says so where the constant "
                "is defined, because a decoy protocol that sent 16 vacua for every 4 signals "
                "would be throwing away four fifths of its key. Resolved by arithmetic, not by "
                "preference: only one of the two readings is consistent with the other half of "
                "the sentence."
            ),
            test=(
                "tests/qkd/test_bb84.py::TestNtanos2021::"
                "test_the_state_ratio_printed_in_the_source_does_not_give_the_q_printed_beside_it"
            ),
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.single-pass-peak-skr",
            source=NTANOS_2021,
            locator=(
                "§4.3.1, the peak of the single-pass secret key rate curve: 3.33e-4 secret bits "
                "per emitted pulse, 2.3 m station"
            ),
            quantity="peak asymptotic secret key rate of one pass",
            published=NTANOS_PEAK_SECRET_BITS_PER_PULSE,
            computed=helmos_bits,
            unit="bits per pulse",
            tolerance=5e-7,
            tolerance_basis=(
                "Half a unit in the last printed digit of 3.33e-4, which is 5e-7. Three "
                "significant figures licence nothing wider."
            ),
            level="V2",
            note=(
                "1.053e-3 against 3.33e-4: this project's peak is **3.16 times** theirs, at "
                "their own protocol, their own night noise and their own best-case geometry. "
                "The disagreement is a loss, and it can be quoted as one: landing on 3.33e-4 "
                "needs a total link loss of **24.07 dB**, which is 4.98 dB more than the "
                "19.09 dB their parameters give here and 4.07 dB more than the 20 dB their own "
                "§4.2.1 declares as the best case. So the two published claims — the 20 dB and "
                "the 3.33e-4 — are not consistent with each other under any decoy analysis that "
                "reproduces their Appendix A, whichever of the two this project is wrong about. "
                "Both are in the table; neither is used as an anchor."
            ),
            test=_OWN_TEST + "TestTheKeyRateClaims::test_the_peak_rate_needs_more_loss_than_20_db",
            degradations=_codes(key_log),
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.aperture-ratio-helmos-skinakas",
            source=NTANOS_2021,
            locator=(
                "§4.3.2: the 2.3 m Helmos station yields 'about four times' the key of the "
                "1.3 m Skinakas one, compared here at zenith"
            ),
            quantity="ratio of secret key rates, 2.3 m station over 1.3 m station",
            published=NTANOS_APERTURE_RATIO_AS_PRINTED,
            computed=helmos_bits / skinakas_bits,
            unit="1",
            tolerance=0.5,
            tolerance_basis=(
                "Half a unit in the last digit of 'about four', so +/- 0.5. The hedge is the "
                "paper's own and this is the widest reading of it."
            ),
            level="V2",
            note=(
                "3.056 at zenith, and the row records a correction to how this disagreement "
                "used to be written down. It was listed as '3.06 at every elevation tested', "
                "which is the zenith value and not a constant: measured across their own "
                "elevation range the ratio runs from 3.056 at 90 deg to **3.249** at their 20 "
                "deg floor, because the smaller aperture loses proportionally more to the "
                "longer slant path. The claim fails at every elevation in their range, but by "
                "between 19 % and 24 % rather than by one number. A bare aperture-area ratio "
                "would be (2.3/1.3)^2 = 3.13, which is the scale of the effect; 'four times' is "
                "above even that, and the key rate is sublinear in transmittance once the "
                "decoy bound bites, so four is not reachable from this geometry."
            ),
            test=_OWN_TEST + "TestTheKeyRateClaims::test_the_aperture_ratio_is_three_not_four",
            degradations=_codes(key_log),
        ),
        ValidationCase.evaluate(
            identifier="ntanos2021.skinakas-latitude-as-printed",
            source=NTANOS_2021,
            locator=(
                "§2, the Skinakas observatory: 'longitude: 35.2118 deg, latitude: 24.8981 deg'"
            ),
            quantity="latitude of the Skinakas ground station",
            published=24.8981,
            computed=skinakas_latitude_deg,
            unit="deg",
            tolerance=5e-5,
            tolerance_basis=(
                "Half a unit in the last printed digit: the coordinates are given to four "
                "decimals, which licenses +/- 0.00005 deg — about 5.5 m on the ground."
            ),
            level="V2",
            note=(
                "The printed labels are swapped, and geography settles it without appeal to any "
                "other source: Greece spans roughly 34-42 deg N and 19-29 deg E, Skinakas is on "
                "Crete, and 35.2 is a Greek latitude while 24.9 is a Greek longitude. All three "
                "stations are printed the same way, and all three fail the same band test — "
                "Cholomondas 40.3419/23.5060 and Helmos 37.9855/22.1984 — so it is a systematic "
                "label swap and not a typo in one row. This project stores them swapped back, "
                "in quoss.scenario.defaults.NTANOS_STATIONS, and the 10.3 deg in this row's "
                "deviation column is what taking the paper literally would cost: roughly "
                "1 150 km of ground displacement, which moves every pass this project would "
                "compute for those stations."
            ),
            test=(
                "tests/scenario/test_defaults.py::TestNtanos2021::"
                "test_the_printed_coordinate_labels_are_swapped"
            ),
        ),
    ]


def _protocol_cases() -> list[ValidationCase]:
    """Return the two rows of the protocol papers Ntanos et al.'s link is evaluated with."""
    noise_per_gate = float(
        background_counts_per_gate(
            _background_rate_cps(
                float(
                    tabulated_sky_radiance_w_m2_um_sr(
                        _DAYLIGHT_WAVELENGTH_M, condition=SkyCondition.BRIGHT_SUNSHINE
                    )
                ),
                _HELMOS_APERTURE_M,
                wavelength_m=_DAYLIGHT_WAVELENGTH_M,
            ),
            gate_duration_s=_GATE_S,
        )
    )
    # The transmittance the rest of the suite calls REFERENCE_TRANSMITTANCE: the reference
    # downlink at its median in-pass geometry. Any link would do here -- what the case is
    # about is the composition rule, not the channel -- and this one is the project's.
    transmittance = 1.3993e-3
    printed_gain = _printed_ma_eq10_gain(transmittance, noise_per_gate, NTANOS_SIGNAL_INTENSITY)
    exact_gain = float(
        simulate_intensity(
            LinkConditions(
                transmittance=np.asarray(transmittance, dtype=np.float64),
                noise_counts_per_gate=noise_per_gate,
                misalignment_error=_MISALIGNMENT_ERROR,
                pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
                gate_duration_s=_GATE_S,
            ),
            intensity=NTANOS_SIGNAL_INTENSITY,
        ).gain
    )
    # The term the printed form double-counts, computed exactly rather than bounded: the
    # gates in which the background and the signal both fire. Y_0 (1 - e^{-eta mu}).
    overlap = -math.expm1(-noise_per_gate) * (
        1.0 - math.exp(-transmittance * NTANOS_SIGNAL_INTENSITY)
    )

    printed_detection = _printed_lim_detection_rate(_LIM_FIBRE_KM, _LIM_INTENSITY)
    channel = 10.0 ** (-_LIM_FIBRE_DB_PER_KM * _LIM_FIBRE_KM / 10.0)
    dark_mean = 2.0 * float(-math.log1p(-LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE))
    exact_detection = float(
        click_probability(
            channel * _LIM_INTENSITY,
            efficiency=LIM_INGAAS_EFFICIENCY,
            dark_counts_per_gate=dark_mean,
        )
    )

    return [
        ValidationCase.evaluate(
            identifier="ma2005.eq10-gain-adds-instead-of-uniting",
            source=MA_2005,
            locator=(
                "Eq. (10), Q_mu = Y_0 + 1 - e^{-eta mu}, at mu = 0.56 and the reference "
                "downlink under ITU-R bright sunshine on the 2.3 m station (3.415 counts/gate)"
            ),
            quantity="gain: probability that a signal-intensity pulse produces a detection",
            published=printed_gain,
            computed=exact_gain,
            unit="1",
            tolerance=1e-12 * printed_gain,
            tolerance_basis=(
                "1e-12 relative: with the overlap below accounted for, the two expressions are "
                "the same closed form and only float rounding separates them. Measured residual "
                "against the accounted term, 4e-17 absolute."
            ),
            level="V2",
            accounted=AccountedTerm(
                name="double-counted overlap, Y_0 (1 - e^{-eta mu})",
                lower=overlap,
                upper=overlap,
                basis=(
                    "Computed exactly, not bounded: the printed sum and the exact union "
                    "1 - (1 - Y_0) e^{-eta mu} differ by precisely the product of the two "
                    "probabilities, which is the gates where the background and the signal "
                    "both fire."
                ),
            ),
            note=(
                "Compatible, and the interesting part is where it stops being so. At night the "
                "overlap is 6.2e-10 and nobody needed the correction — the two forms agree to "
                "eight digits. Under the sky modelled here the printed sum is 0.96792 against "
                "0.96716, high by 0.078 %, and it keeps climbing: above **7.152 background "
                "counts per gate** the printed gain exceeds one, which is not a slightly wrong "
                "gain but a probability that is not one, and quoss.qkd.base.KeyRate refuses it. "
                "The crossing is found with a root finder in the test rather than transcribed, "
                "so it cannot rot. Ntanos et al. reprint this as their Eq. (A4); it is the same "
                "mistake as their Eq. (20), one layer up."
            ),
            test=(
                "tests/qkd/test_bb84.py::TestTheApproximationThisModuleDeclines::"
                "test_the_published_form_returns_a_probability_above_one"
            ),
        ),
        ValidationCase.evaluate(
            identifier="lim2014.printed-detection-rate",
            source=LIM_2014,
            locator=(
                "Evaluation section, D_k = 1 - (1 - 2 p_dc) e^{-eta_sys k}, at their "
                "eta_Bob = 10 %, p_dc = 6e-7, k = 0.5 over 100 km of 0.2 dB/km fibre"
            ),
            quantity="detection rate per pulse at the signal intensity",
            published=printed_detection,
            computed=exact_detection,
            unit="1",
            tolerance=3e-7 * printed_detection,
            tolerance_basis=(
                "3e-7 relative, derived and not measured: this project computes the exact "
                "two-detector union (1 - p_dc)^2 and the paper prints its first order "
                "1 - 2 p_dc, so the published value is larger by p_dc^2 e^{-x}, which relative "
                "to D_k is at most p_dc / 2 = 3e-7 and reaches that only in the limit where the "
                "dark counts are the whole detection rate. Measured residual here: 7.2e-10."
            ),
            level="V2",
            note=(
                "Reproduced at 5.010744e-4, and this is the anchor that says the finite-key "
                "stack is being fed the channel its bound was published against. The row is "
                "also where the third instance of the module's headline lives: 1 - 2 p_dc goes "
                "**negative** above p_dc = 0.5, so the printed form returns 1.934 when handed "
                "the 0.967 daylight background that quoss.channel.background computes for "
                "Ntanos et al.'s own receiver. Nobody needed the correction at 6e-7 — the two "
                "agree to 7e-10 — and everybody needs it in daylight."
            ),
            test=(
                "tests/channel/test_detector.py::TestAgainstLimEtAl::"
                "test_the_detection_rate_reproduces_over_four_fibre_lengths"
            ),
        ),
    ]


def cases() -> tuple[ValidationCase, ...]:
    """Recompute every case of the reference link's own sources, in table order.

    Ntanos et al. first because they own the link, then the two protocol papers
    their Appendix A and this project's finite-key bound come from.

    Returns
    -------
    tuple of ValidationCase
        Eleven Ntanos et al. rows, then one Ma et al. row and one Lim et al. row.

    Examples
    --------
    >>> statuses = [case.status.value for case in cases()]
    >>> statuses.count("not_reproduced"), statuses.count("reproduced")
    (7, 3)
    >>> statuses.count("compatible"), statuses.count("gap")
    (2, 1)
    """
    return (*_ntanos_cases(), *_protocol_cases())
