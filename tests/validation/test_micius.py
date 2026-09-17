"""Tests for `quoss.validation.micius`: the one measured source in the table.

The node ids here are named by `quoss/validation/micius.py` itself, in each
case's ``test`` field, so that a row of ``docs/validation.md`` is traceable to an
assertion. They named a file that did not exist; see the header of
`test_satquma.py` for the guard that now catches that.

Why this source is different from every other one in the table: Liao et al. 2017
report a **measurement**, not a model. A model paper's number is a point and its
precision is its printed digits; a measurement comes with a spread the paper
gives in words — "in the range of 3 dB to 8 dB", "less than 3 dB", "~1 kbit/s" —
so the tolerance of a Micius case is a published *range*, and the interesting
tests are the ones that say how wide the agreement really is.

- ``TestTheDiffractionLoss`` — the one expected disagreement in the whole table,
  and where it comes from.
- ``TestTheBudgetAgainstTheMeasuredRate`` — the reproduced row, plus how much of
  it is real and how much is the width of "~1 kbit/s".
- ``TestWhatThePaperDoesNotGive`` — the three gaps, each asserted as a gap.
"""

from __future__ import annotations

import math

import pytest

from quoss.channel.beam import geometric_transmittance
from quoss.core.errors import DomainError
from quoss.core.units import transmittance_to_loss_db
from quoss.scenario.models import ChannelSpec, PassSpec
from quoss.validation.base import (
    EXPECTED_DISAGREEMENTS,
    ValidationCase,
    ValidationStatus,
)
from quoss.validation.micius import (
    MICIUS_AVERAGE_QBER,
    MICIUS_DETECTIONS,
    MICIUS_DIFFRACTION_LOSS_DB,
    MICIUS_FINAL_KEY_BITS,
    MICIUS_RECEIVE_APERTURE_M,
    MICIUS_REFERENCE_RANGE_KM,
    MICIUS_SIFTED_BITS,
    MICIUS_TRANSMIT_APERTURE_M,
    MICIUS_UNPUBLISHED_SCENARIO_INPUTS,
    MICIUS_WAVELENGTH_M,
    cases,
    implied_link_loss_db,
    published_link_loss_range_db,
)


def case(identifier: str) -> ValidationCase:
    """Return the one case with this identifier, or fail saying it is gone."""
    matches = [c for c in cases() if c.identifier == identifier]
    assert len(matches) == 1, f"{identifier!r} is not one of {[c.identifier for c in cases()]}"
    return matches[0]


class TestTheDiffractionLoss:
    def test_the_printed_aperture_is_not_the_beam(self) -> None:
        """The table's one expected disagreement, and it is the paper's own arithmetic.

        Liao et al. print "The diffraction loss is estimated to be 22 dB at
        1200 km" in the same paragraph as a 300 mm transmitter and a 1 m
        receiver. Those two apertures, at 848.6 nm and 1200 km, give **9.95 dB**
        — 12 dB less. The disagreement is not in the loss law: it is that the
        beam they describe elsewhere in the paragraph, "~10 µrad" and "about
        10 m" at 1200 km, is far wider than a 300 mm aperture can diffract to.

        So the 22 dB is a property of the real beam and the printed aperture
        does not determine it. Closing this needs a measured beam profile, not
        a different aperture chosen until the number comes out.
        """
        computed = float(
            transmittance_to_loss_db(
                geometric_transmittance(
                    MICIUS_REFERENCE_RANGE_KM,
                    wavelength_m=MICIUS_WAVELENGTH_M,
                    transmit_aperture_m=MICIUS_TRANSMIT_APERTURE_M,
                    receive_aperture_m=MICIUS_RECEIVE_APERTURE_M,
                )
            )
        )
        assert computed == pytest.approx(9.95, abs=0.01)
        assert abs(computed - MICIUS_DIFFRACTION_LOSS_DB) > 0.5
        assert case("micius2017.diffraction-loss-1200km").status is (
            ValidationStatus.NOT_REPRODUCED
        )

    def test_the_beam_the_paper_describes_is_wider_than_that_aperture_allows(self) -> None:
        """The quantitative form of "the printed aperture is not the beam".

        A Gaussian of waist radius `a = D/2` has far-field half-angle
        `lambda / (pi a)`, so a 300 mm aperture at 848.6 nm diffracts to a full
        divergence of 3.60 µrad and a 4.33 m spot at 1200 km. The paper's own
        "~10 µrad" and "about 10 m" are **2.8 times** that. Asserted because it
        is the whole content of the disagreement: two numbers in one paragraph
        that cannot both describe the same optic.
        """
        waist_m = MICIUS_TRANSMIT_APERTURE_M / 2.0
        full_divergence_rad = 2.0 * MICIUS_WAVELENGTH_M / (math.pi * waist_m)
        spot_m = full_divergence_rad * MICIUS_REFERENCE_RANGE_KM * 1e3
        assert full_divergence_rad == pytest.approx(3.60e-6, rel=0.01)
        assert spot_m == pytest.approx(4.33, rel=0.01)
        assert 10e-6 / full_divergence_rad == pytest.approx(2.8, rel=0.02)

    def test_the_disagreement_is_declared_rather_than_tolerated(self) -> None:
        """It is the only `NOT_REPRODUCED` row in the table, and it is written down.

        A disagreement that is not in `EXPECTED_DISAGREEMENTS` fails CI
        (`test_base.py`), which is what stops "not reproduced" from becoming a
        status people stop reading.
        """
        assert "micius2017.diffraction-loss-1200km" in EXPECTED_DISAGREEMENTS


class TestTheBudgetAgainstTheMeasuredRate:
    def test_the_implied_loss_is_in_range(self) -> None:
        """The printed loss terms and the measured rate describe one link.

        Inverting the printed source — three intensities 0.8/0.1/0 sent
        50/25/25 % at 100 MHz, through the sifting fraction Micius *measured*
        that night (1 671 072 / 3 551 136 = 0.4706, not the textbook 0.5) —
        for the ~1 kbit/s sifted rate at 1200 km gives **43.01 dB**, inside the
        35.97-43.97 dB the paper's own terms add up to.

        What it establishes is the premise of the diffraction case above: the
        22 dB and the measured rate are talking about the same pass.
        """
        low_db, high_db = published_link_loss_range_db()
        implied = implied_link_loss_db(1000.0)
        assert (low_db, high_db) == pytest.approx((35.97, 43.97), abs=0.01)
        assert low_db <= implied <= high_db
        assert implied == pytest.approx(43.01, abs=0.01)
        assert case("micius2017.link-loss-1200km-from-sifted-rate").status is (
            ValidationStatus.REPRODUCED
        )

    def test_how_weak_the_agreement_is_measured_rather_than_asserted(self) -> None:
        """The row reproduces, and the note says it is weak. This is how weak.

        "~1 kbit/s" is **one significant figure**. Reading it as 0.5 to
        1.5 kbit/s moves the implied loss from **46.02 dB to 41.25 dB** — a
        4.8 dB window, wider than half the published budget's own 8 dB spread.
        So the agreement is real but it is an agreement between two intervals,
        and a reader who takes 43.01 dB as a measurement of anything has
        over-read it.

        Weak in the other direction too, and one-sidedly: the inversion counts
        no noise clicks, and every noise click counted as signal makes the link
        look better, so 43.01 dB is a **lower bound** on the true loss.
        """
        pessimistic = implied_link_loss_db(500.0)
        optimistic = implied_link_loss_db(1500.0)
        assert pessimistic == pytest.approx(46.02, abs=0.01)
        assert optimistic == pytest.approx(41.25, abs=0.01)
        assert pessimistic - optimistic == pytest.approx(4.77, abs=0.02)
        _, high_db = published_link_loss_range_db()
        assert pessimistic > high_db, "the pessimistic reading leaves the published budget"

    def test_the_sifting_fraction_is_the_measured_one_and_not_one_half(self) -> None:
        """A measured fraction already contains whatever their sifting discarded.

        Micius reports 3 551 136 detections and 1 671 072 sifted bits on the
        same night: 0.4706, not 0.5. Using the textbook one-half would credit
        the link with 6 % more sifted bits than were measured and shift the
        inverted loss by 0.26 dB — small, but in the direction that flatters,
        and invented where a measurement exists.
        """
        assert MICIUS_SIFTED_BITS / MICIUS_DETECTIONS == pytest.approx(0.4706, abs=1e-4)
        assert MICIUS_SIFTED_BITS / MICIUS_DETECTIONS < 0.5

    def test_more_loss_means_less_key_over_the_whole_inverted_range(self) -> None:
        """Monotonicity, so the root the inversion finds is the only one.

        `implied_link_loss_db` inverts a gain curve with `brentq`, which returns
        *a* root in the bracket. The curve `1 - exp(-eta mu)` is strictly
        increasing in `eta`, so the root is unique — asserted rather than
        assumed, because a non-monotone inversion returning a plausible number
        is precisely this project's characteristic failure mode.
        """
        losses = [implied_link_loss_db(rate) for rate in (250.0, 500.0, 1000.0, 2000.0, 4000.0)]
        assert losses == sorted(losses, reverse=True)


class TestWhatThePaperDoesNotGive:
    def test_the_qber_needs_an_unprinted_background(self) -> None:
        """A gap with a published side: 1.1 %, and no way to compute it.

        A QBER is optical misalignment plus noise clicks, over all clicks. The
        optical part is bounded by the printed polarisation contrast of 280:1,
        i.e. 1/281 = **0.36 %**; the rest of the 1.1 % is noise, and the noise is
        not printed — dark counts only as a bound ("<25 Hz"), background not at
        all ("city stray light" in the second half of the pass). So about two
        thirds of the published QBER would have to be invented, which is exactly
        what ADR 0009 forbids.
        """
        optical_bound = 1.0 / 281.0
        assert optical_bound == pytest.approx(0.00356, abs=1e-5)
        assert optical_bound < MICIUS_AVERAGE_QBER
        assert 1.0 - optical_bound / MICIUS_AVERAGE_QBER == pytest.approx(0.676, abs=0.01)
        row = case("micius2017.average-qber")
        assert row.status is ValidationStatus.GAP
        assert row.published == MICIUS_AVERAGE_QBER and row.computed is None

    def test_the_final_key_needs_unprinted_inputs(self) -> None:
        """300 939 bits is printed and not reachable, and the shortcut is refused.

        The finite key needs the gain and error rate of each intensity, the
        leakage of their Hamming code, and their finite-size method with its
        intensity-fluctuation allowance; the main text gives none, and the
        arXiv copy that was opened carries no Extended Data.

        The tempting shortcut is the ratio 300 939 / 1 671 072 = 0.18 of final
        to sifted key. It is printed arithmetic between two printed numbers, not
        a model output, so reproducing it would validate a division.
        """
        assert MICIUS_FINAL_KEY_BITS / MICIUS_SIFTED_BITS == pytest.approx(0.180, abs=0.001)
        row = case("micius2017.final-key-one-pass")
        assert row.status is ValidationStatus.GAP
        assert row.computed is None

    def test_every_missing_input_is_required(self) -> None:
        """The gap is structural: each listed field has no default to fall back on.

        This is the load-bearing half of the claim "a Micius scenario cannot be
        built from what is printed". If any of these fields had a default, the
        scenario *would* build — silently, on values nobody chose — and the gap
        would be a choice rather than a fact. Two of them are the project's
        declared no-default fields (`zenith_transmittance`, ADR 0009 gap 14, and
        `minimum_elevation_deg`, ADR 0011 §5); this asserts the first of those
        directly and checks the rest are named.
        """
        assert len(MICIUS_UNPUBLISHED_SCENARIO_INPUTS) == 8
        for field, why in MICIUS_UNPUBLISHED_SCENARIO_INPUTS:
            assert field and why.strip(), field
        with pytest.raises((DomainError, ValueError)):
            ChannelSpec()  # type: ignore[call-arg]
        with pytest.raises((DomainError, ValueError)):
            PassSpec()  # type: ignore[call-arg]
        row = case("micius2017.scenario-sifted-key-per-pass")
        assert row.status is ValidationStatus.GAP
        assert row.published == float(MICIUS_SIFTED_BITS)
        assert "zenith_transmittance" in row.note

    def test_no_micius_case_invents_a_number(self) -> None:
        """Every gap has `computed is None`; none is quietly filled in later."""
        for row in cases():
            if row.status is ValidationStatus.GAP:
                assert row.computed is None, f"{row.identifier} computed a value for a gap"
