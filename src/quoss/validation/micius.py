"""Validation cases for Micius: the only measured satellite QKD data in the table.

Para quien llegue nuevo: Micius is the Chinese quantum science satellite
(launched 2016, ~500 km sun-synchronous orbit). Liao et al., *Satellite-to-ground
quantum key distribution*, Nature 549, 43-47 (2017), arXiv:1707.00542, report
decoy-state BB84 from it to the Xinglong station: 850 nm, three intensities
(0.8, 0.1, 0) sent 50/25/25 %, a 300 mm transmitter, a 1 m receiving telescope,
and — the part that makes this source different from every other one in
``docs/validation.md`` — **measured** results: 3 551 136 detections and
1 671 072 sifted bits in 273 s on 19 December 2016, a sifted rate falling from
~12 kbit/s at 645 km to ~1 kbit/s at 1200 km, a 1.1 % average QBER, and 300 939
bits of final key.

Why measured data changes the comparison: a model paper's number is a point, and
its precision is its printed digits. A measurement comes with a spread the
paper describes in words ("in the range of 3 dB to 8 dB", "less than 3 dB",
"~16 %"), so the tolerance basis of a Micius case is the published range, not a
digit. And its system is not this project's reference link: comparing
end-to-end needs a Micius scenario, and a scenario needs inputs Liao et al. do
not print. This module refuses to fill them.

What is computed, at the physics level (``channel.beam``, ``qkd.bb84``):

1. **The 22 dB diffraction loss** they estimate at 1200 km — *not reproduced*:
   the printed 300 mm aperture, diffraction-limited, gives 9.95 dB, because
   the beam they describe ("~10 µrad", "about 10 m" at 1200 km) is 2.8 times
   wider than that aperture's diffraction limit. Sidhu et al. 2021 §II read the
   same numbers the same way.
2. **Their loss budget against their own measured rate** at 1200 km —
   *reproduced*: the printed terms add up to 35.97-43.97 dB, and the loss that
   turns the three printed intensities into the measured ~1 kbit/s sifted rate,
   through :func:`quoss.qkd.bb84.simulate_intensity`, is 43.01 dB.

What is a gap, and why: the average QBER (no background rate printed), the
final key (no per-intensity gains, no error-correction efficiency, the
finite-size analysis in Methods and Extended Data that the arXiv copy does not
carry), and the scenario-level key per pass (:data:`MICIUS_UNPUBLISHED_SCENARIO_INPUTS`
lists the required scenario fields the paper does not give).
"""

from __future__ import annotations

from typing import Final

from scipy.optimize import brentq

from quoss.channel.beam import geometric_transmittance
from quoss.core.errors import DegradationLog
from quoss.core.units import transmittance_to_loss_db
from quoss.qkd.base import LinkConditions
from quoss.qkd.bb84 import simulate_intensity
from quoss.validation.base import ValidationCase

__all__ = [
    "LIAO_2017",
    "MICIUS_ATMOSPHERE_LOSS_RANGE_DB",
    "MICIUS_AVERAGE_QBER",
    "MICIUS_COINCIDENCE_WINDOW_S",
    "MICIUS_DETECTIONS",
    "MICIUS_DETECTOR_EFFICIENCY",
    "MICIUS_DIFFRACTION_LOSS_DB",
    "MICIUS_FINAL_KEY_BITS",
    "MICIUS_GROUND_OPTICAL_EFFICIENCY",
    "MICIUS_INTENSITIES",
    "MICIUS_INTENSITY_PROBABILITIES",
    "MICIUS_POINTING_LOSS_MAX_DB",
    "MICIUS_PULSE_RATE_HZ",
    "MICIUS_RECEIVE_APERTURE_M",
    "MICIUS_REFERENCE_RANGE_KM",
    "MICIUS_SIFTED_BITS",
    "MICIUS_SIFTED_RATE_AT_1200_KM_BIT_S",
    "MICIUS_TRANSMIT_APERTURE_M",
    "MICIUS_UNPUBLISHED_SCENARIO_INPUTS",
    "MICIUS_WAVELENGTH_M",
    "cases",
    "implied_link_loss_db",
    "published_link_loss_range_db",
]

LIAO_2017: Final = (
    "S.-K. Liao et al., Satellite-to-ground quantum key distribution, Nature 549, 43-47 (2017); "
    "preprint arXiv:1707.00542 opened via export.arxiv.org (main text and captions; that copy "
    "carries no Extended Data tables)"
)

# "Experimental challenges and solutions"
MICIUS_TRANSMIT_APERTURE_M: Final = 0.300
""""we use a 300-mm aperture Cassegrain telescope in the satellite"."""
MICIUS_RECEIVE_APERTURE_M: Final = 1.0
""""a Ritchey-Chretien telescope with an aperture of 1 m"."""
MICIUS_REFERENCE_RANGE_KM: Final = 1200.0
MICIUS_DIFFRACTION_LOSS_DB: Final = 22.0
""""The diffraction loss is estimated to be 22 dB at 1200 km"."""
MICIUS_ATMOSPHERE_LOSS_RANGE_DB: Final = (3.0, 8.0)
""""at 1200 km the loss due to atmospheric absorption and turbulence is in the range of 3 dB to 8 dB"."""
MICIUS_POINTING_LOSS_MAX_DB: Final = 3.0
""""and the loss due to pointing error is less than 3 dB"."""
MICIUS_COINCIDENCE_WINDOW_S: Final = 2e-9
""""used to tag the received signal photons within a 2-ns time window"."""

# "Experimental procedure and results"
MICIUS_WAVELENGTH_M: Final = 848.6e-9
MICIUS_PULSE_RATE_HZ: Final = 100e6
""""emit laser pulses (848.6 nm, 100 MHz, 0.2 ns)"."""
MICIUS_INTENSITIES: Final = (0.8, 0.1, 0.0)
""""the average photon number in the output of the telescope: mu_s=0.8, mu_1=0.1, mu_2=0"."""
MICIUS_INTENSITY_PROBABILITIES: Final = (0.5, 0.25, 0.25)
""""sent with probabilities of 50%, 25%, and 25%, respectively"."""
MICIUS_DETECTOR_EFFICIENCY: Final = 0.50
""""four single-photon detectors (efficiency 50%, dark counts <25 Hz, timing jitter 350 ps)"."""
MICIUS_GROUND_OPTICAL_EFFICIENCY: Final = 0.16
""""The overall optical efficiency including the receiving telescope and the fiber coupling on the
ground station is ~16%" — optical, so the detector efficiency is a separate factor."""
MICIUS_DETECTIONS: Final = 3_551_136
MICIUS_SIFTED_BITS: Final = 1_671_072
""""the ground station collected 3,551,136 detection events, and thereof 1,671,072 bits of sifted
keys" (19 December 2016, 273 s)."""
MICIUS_SIFTED_RATE_AT_1200_KM_BIT_S: Final = 1000.0
""""The sifted key rate decrease from ~12 kbit/s at 645 km to ~1 kbit/s at 1200 km"."""
MICIUS_AVERAGE_QBER: Final = 0.011
""""the observed quantum bit error rate (QBER) with an average of 1.1%"."""
MICIUS_FINAL_KEY_BITS: Final = 300_939
""""we calculate secure final key of 300,939 bits when the statistical failure probability is set
to be 10-9"."""

MICIUS_UNPUBLISHED_SCENARIO_INPUTS: Final[tuple[tuple[str, str], ...]] = (
    (
        "channel.zenith_transmittance",
        "no vertical transmittance at 850 nm; only '3 dB to 8 dB' of absorption and "
        "turbulence together, at one range",
    ),
    ("receiver.field_of_view_urad", "the ground station's field of view is not printed"),
    ("receiver.filter_bandwidth_nm", "'a bandwidth filter', with no bandwidth"),
    ("receiver.dead_time_ns", "not printed for the four detectors"),
    ("background", "no sky radiance or background count rate; only 'city stray light'"),
    (
        "protocol.error_correction_efficiency",
        "'a hamming algorithm is used for error correction', with no efficiency",
    ),
    (
        "transmitter.pointing_jitter_urad",
        "'tracking accuracy of ~1.2 µrad' without saying per axis, radial, r.m.s. or peak",
    ),
    ("orbit.kepler.raan_deg", "only '~500 km' and sun-synchronous; no elements or epoch"),
)
"""Required fields of :class:`quoss.scenario.models.Scenario` that Liao et al. do not give.

Each is required (no default) in the scenario models — that is asserted in
``tests/validation/test_micius.py`` — so a Micius scenario could only be built by
inventing them. A declared gap beats a false V2 (ADR 0009), so none is built.
"""

_MEASURED_SIFTING_FRACTION: Final = MICIUS_SIFTED_BITS / MICIUS_DETECTIONS
_TEST: Final = "tests/validation/test_micius.py::"


def published_link_loss_range_db() -> tuple[float, float]:
    """Return the end-to-end loss at 1200 km implied by Liao et al.'s printed terms.

    The sum of diffraction (22 dB), atmosphere (3 to 8 dB), pointing (0 to
    3 dB), ground optics (~16 %) and detectors (50 %), at the two extremes of
    each range. An interval, because every term but the efficiencies is printed
    as one; and a *loss* in dB, so the terms add.

    Returns
    -------
    tuple of float
        ``(lowest, highest)`` total loss, dB.

    Examples
    --------
    >>> low, high = published_link_loss_range_db()
    >>> round(low, 2), round(high, 2)
    (35.97, 43.97)
    """
    receiver_db = float(
        transmittance_to_loss_db(MICIUS_GROUND_OPTICAL_EFFICIENCY * MICIUS_DETECTOR_EFFICIENCY)
    )
    low_atmosphere_db, high_atmosphere_db = MICIUS_ATMOSPHERE_LOSS_RANGE_DB
    return (
        MICIUS_DIFFRACTION_LOSS_DB + low_atmosphere_db + receiver_db,
        MICIUS_DIFFRACTION_LOSS_DB + high_atmosphere_db + MICIUS_POINTING_LOSS_MAX_DB + receiver_db,
    )


def implied_link_loss_db(sifted_rate_bit_s: float) -> float:
    """Return the end-to-end loss that turns Micius's source into a given sifted rate.

    What it computes: the transmittance ``eta`` (satellite exit aperture to a
    click, detectors included) at which the three printed intensities, sent with
    their printed probabilities at 100 MHz, produce ``sifted_rate_bit_s`` sifted
    bits per second, and that transmittance in dB. The gain of each intensity is
    :func:`quoss.qkd.bb84.simulate_intensity`, ``1 - exp(-eta mu)`` with no
    noise, and the sifting fraction is the one Micius *measured* on the same
    night, 1 671 072 / 3 551 136 = 0.4706 — not the textbook 0.5, because a
    measured fraction already contains whatever their sifting discarded.

    Why no noise: the dark counts are printed only as a bound (<25 Hz per
    detector) and the background not at all. Every noise click counted as
    signal makes the implied link look better, so the loss returned is a
    **lower bound** on the true one. At the bound, four detectors at 25 Hz in
    a 2 ns window are 2e-7 counts per gate, about 1 % of the clicks at 1200 km.

    Parameters
    ----------
    sifted_rate_bit_s : float
        Sifted key rate, bits per second.

    Returns
    -------
    float
        End-to-end loss, dB.

    Examples
    --------
    The ~1 kbit/s Liao et al. print at 1200 km:

    >>> round(implied_link_loss_db(1000.0), 2)
    43.01
    """

    def sifted(transmittance: float) -> float:
        link = LinkConditions(
            transmittance=transmittance,
            noise_counts_per_gate=0.0,
            misalignment_error=0.0,
            pulse_rate_hz=MICIUS_PULSE_RATE_HZ,
            gate_duration_s=MICIUS_COINCIDENCE_WINDOW_S,
        )
        gain = sum(
            probability * float(simulate_intensity(link, intensity=intensity).gain)
            for intensity, probability in zip(
                MICIUS_INTENSITIES, MICIUS_INTENSITY_PROBABILITIES, strict=True
            )
        )
        return MICIUS_PULSE_RATE_HZ * gain * _MEASURED_SIFTING_FRACTION - sifted_rate_bit_s

    transmittance = float(brentq(sifted, 1e-12, 1.0, xtol=1e-15, rtol=1e-12))
    return float(transmittance_to_loss_db(transmittance))


def cases() -> tuple[ValidationCase, ...]:
    """Recompute the Micius cases.

    Returns
    -------
    tuple of ValidationCase
        Diffraction loss, the budget against the measured rate, then three gaps.

    Examples
    --------
    >>> [case.status.value for case in cases()]
    ['not_reproduced', 'reproduced', 'gap', 'gap', 'gap']
    """
    diffraction_db = float(
        transmittance_to_loss_db(
            geometric_transmittance(
                MICIUS_REFERENCE_RANGE_KM,
                wavelength_m=MICIUS_WAVELENGTH_M,
                transmit_aperture_m=MICIUS_TRANSMIT_APERTURE_M,
                receive_aperture_m=MICIUS_RECEIVE_APERTURE_M,
            )
        )
    )
    low_db, high_db = published_link_loss_range_db()
    log = DegradationLog()
    implied_db = implied_link_loss_db(MICIUS_SIFTED_RATE_AT_1200_KM_BIT_S)
    missing = "; ".join(f"{field} ({why})" for field, why in MICIUS_UNPUBLISHED_SCENARIO_INPUTS)

    return (
        ValidationCase.evaluate(
            identifier="micius2017.diffraction-loss-1200km",
            source=LIAO_2017,
            locator=(
                "'Experimental challenges and solutions': 300 mm transmitter, 1 m receiver, "
                "'The diffraction loss is estimated to be 22 dB at 1200 km'"
            ),
            quantity="geometric (diffraction) loss at 1200 km",
            published=MICIUS_DIFFRACTION_LOSS_DB,
            computed=diffraction_db,
            unit="dB",
            tolerance=0.5,
            tolerance_basis="Printed to the unit, so ±0.5 dB.",
            level="V2",
            note=(
                "Not reproduced, and the reason is in the same paragraph. The printed 300 mm "
                "aperture at 848.6 nm has a diffraction-limited full divergence of 3.60 µrad "
                "and a beam diameter of 4.33 m at 1200 km, which collects 9.95 dB into 1 m. "
                "Liao et al. describe '~10 µrad' and 'about 10 m': a beam 2.8 times wider than "
                "the aperture allows, which Sidhu et al. 2021 §II also read as "
                "non-diffraction-limited spreading. The 22 dB belongs to the real beam, and "
                "the printed aperture does not determine it; closing this needs a measured "
                "beam profile, not a different aperture chosen to fit."
            ),
            test=_TEST + "TestTheDiffractionLoss::test_the_printed_aperture_is_not_the_beam",
        ),
        ValidationCase.evaluate(
            identifier="micius2017.link-loss-1200km-from-sifted-rate",
            source=LIAO_2017,
            locator=(
                "loss terms of 'Experimental challenges and solutions' and the ~1 kbit/s sifted "
                "rate at 1200 km of 'Experimental procedure and results' (19 Dec 2016 pass)"
            ),
            quantity="end-to-end link loss at 1200 km: printed budget against measured rate",
            published=0.5 * (low_db + high_db),
            computed=implied_db,
            unit="dB",
            tolerance=0.5 * (high_db - low_db),
            tolerance_basis=(
                "The published loss range, not a point: 22 dB + (3 to 8) dB + (0 to 3) dB + "
                "10.97 dB of ground optics and detectors = 35.97 to 43.97 dB, written as its "
                "midpoint ± its half-width."
            ),
            level="V2",
            note=(
                "Consistent: the loss that makes the printed source give the measured ~1 kbit/s "
                "is 43.01 dB, inside the budget and near its pessimistic end. Weak in both "
                "directions, and the numbers say how weak: '~1 kbit/s' is one significant "
                "figure, and 0.5 to 1.5 kbit/s spans 46.02 to 41.25 dB; and the noise-free "
                "inversion makes 43.01 dB a lower bound. What it does establish is that Liao "
                "et al.'s loss terms and their measured rate are the same link — the premise "
                "of the diffraction case above, where the 22 dB is taken as theirs."
            ),
            test=_TEST + "TestTheBudgetAgainstTheMeasuredRate::test_the_implied_loss_is_in_range",
            degradations=tuple(sorted({entry.code for entry in log})),
        ),
        ValidationCase.evaluate(
            identifier="micius2017.average-qber",
            source=LIAO_2017,
            locator="'Experimental procedure and results' and Fig. 3c: average QBER 1.1 %",
            quantity="average quantum bit error rate over the pass",
            published=MICIUS_AVERAGE_QBER,
            computed=None,
            unit="1",
            tolerance=None,
            tolerance_basis="None: nothing computed.",
            level="V2",
            note=(
                "Gap. A QBER is optical misalignment plus noise clicks over all clicks, and the "
                "noise is not printed: dark counts only as '<25 Hz', background not at all "
                "('city stray light' in the second half of the pass). The printed average "
                "polarisation contrast of 280:1 bounds the optical part at 1/281 = 0.36 %, so "
                "about two thirds of the 1.1 % is noise this project would have to invent."
            ),
            test=_TEST + "TestWhatThePaperDoesNotGive::test_the_qber_needs_an_unprinted_background",
        ),
        ValidationCase.evaluate(
            identifier="micius2017.final-key-one-pass",
            source=LIAO_2017,
            locator="'Experimental procedure and results': 300 939 bits at failure probability 1e-9",
            quantity="final secret key of the 19 December 2016 pass",
            published=float(MICIUS_FINAL_KEY_BITS),
            computed=None,
            unit="bits",
            tolerance=None,
            tolerance_basis="None: nothing computed.",
            level="V2",
            note=(
                "Gap. The finite key needs the gain and error rate of each intensity, the "
                "error-correction leakage of their Hamming code, and their finite-size method "
                "with its intensity-fluctuation allowance (<5 %); the main text gives none of "
                "them, and the arXiv copy that was opened has no Extended Data. The ratio "
                "300 939 / 1 671 072 = 0.18 of final to sifted key is printed arithmetic, not a "
                "model output, so it is not a validation number either."
            ),
            test=_TEST + "TestWhatThePaperDoesNotGive::test_the_final_key_needs_unprinted_inputs",
        ),
        ValidationCase.evaluate(
            identifier="micius2017.scenario-sifted-key-per-pass",
            source=LIAO_2017,
            locator="'Experimental procedure and results': 1 671 072 sifted bits in 273 s",
            quantity="sifted key of one pass, from an end-to-end Micius scenario",
            published=float(MICIUS_SIFTED_BITS),
            computed=None,
            unit="bits",
            tolerance=None,
            tolerance_basis="None: nothing computed.",
            level="V2",
            note=(
                "Gap: a scenario cannot be built from what is printed without inventing "
                f"required inputs — {missing}. None is filled (ADR 0009)."
            ),
            test=_TEST + "TestWhatThePaperDoesNotGive::test_every_missing_input_is_required",
        ),
    )
