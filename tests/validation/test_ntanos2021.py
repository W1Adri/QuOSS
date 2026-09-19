"""Tests for `quoss.validation.ntanos2021`: the rows this module measures itself.

Most of the thirteen cases in that module point their `test` field at an
assertion that already existed somewhere in `tests/channel/`, `tests/qkd/` or
`tests/scenario/` — which is the point of the field: a row of
`docs/validation.md` is traceable to something that runs, and the physics is
asserted where the physics lives, not a second time here.

Three rows had nowhere to point, and this file is where they point:

- The **peak single-pass key rate** of §4.3.1 and the **aperture ratio** of
  §4.3.2. Neither had an assertion anywhere: they were carried as one-line
  entries in `PENDING_DISAGREEMENTS` for as long as this package existed,
  described but never measured. Measuring them is what let one of the two
  descriptions be corrected — the ratio was written down as "3.06 at every
  elevation tested" and it is 3.06 only at zenith.
- The **zenith transmittance gap**. A gap is a claim as much as a number is,
  and the way it goes stale is silently: somebody adds the number the source
  never printed, and the row keeps saying `gap`. So the gap is asserted, in the
  only way a gap can be — that nothing is computed and nothing is published.

`TestTheModuleSurface` covers what is true of the module as a whole: the status
mix that its own docstring claims, and that every identifier it produces is
either expected to disagree or agrees.
"""

from __future__ import annotations

import math
from collections import Counter

import pytest

from quoss.core.errors import DegradationLog
from quoss.core.units import deg_to_rad
from quoss.validation.base import (
    EXPECTED_DISAGREEMENTS,
    PENDING_DISAGREEMENTS,
    ValidationCase,
    ValidationStatus,
)
from quoss.validation.ntanos2021 import (
    NTANOS_APERTURE_RATIO_AS_PRINTED,
    NTANOS_PEAK_SECRET_BITS_PER_PULSE,
    _secret_bits_per_pulse,
    _total_loss_db,
    cases,
)

HELMOS_M = 2.3
SKINAKAS_M = 1.3
ZENITH_RAD = 0.5 * math.pi


def case(identifier: str) -> ValidationCase:
    """Return the one case with this identifier, or fail saying it is gone."""
    matches = [c for c in cases() if c.identifier == identifier]
    assert len(matches) == 1, f"{identifier!r} is not one of {[c.identifier for c in cases()]}"
    return matches[0]


@pytest.mark.reference
class TestTheKeyRateClaims:
    """The two §4.3 numbers, measured here because nothing else measured them."""

    def test_the_peak_rate_needs_more_loss_than_20_db(self) -> None:
        """**V2 that fails**, and the finding is that their two claims disagree with each other.

        §4.3.1 prints a peak single-pass secret key rate of 3.33e-4 secret bits
        per emitted pulse. With their protocol (mu = 0.56, nu = 0.11, f = 1.22),
        their study-night background and their own best-case geometry — the
        2.3 m station at zenith, 600 km — this project gets **1.053e-3**, which
        is 3.16 times as much.

        What makes that a finding about the paper rather than about this
        project is expressing the gap as a loss. Secret bits per pulse is
        monotone in the total link loss, so there is exactly one loss that
        lands on 3.33e-4, and it is **24.07 dB**. Their §4.2.1 declares the best
        case as 20 dB. So no total loss consistent with §4.2.1 produces the peak
        rate of §4.3.1: the two printed claims are 4.07 dB apart under any
        decoy analysis that reproduces their own Appendix A, and this project's
        19.09 dB budget sits on the optimistic side of both.

        The root is found rather than transcribed, so the 24.07 cannot rot.
        """
        from scipy.optimize import brentq

        log = DegradationLog()
        best_case_db = _total_loss_db(HELMOS_M, ZENITH_RAD, log)
        assert best_case_db == pytest.approx(19.094, abs=1e-3)

        ours = _secret_bits_per_pulse(best_case_db, log)
        assert ours == pytest.approx(1.0526e-3, rel=1e-3)
        assert ours / NTANOS_PEAK_SECRET_BITS_PER_PULSE == pytest.approx(3.16, abs=0.01)

        loss_db = brentq(
            lambda db: _secret_bits_per_pulse(db, log) - NTANOS_PEAK_SECRET_BITS_PER_PULSE,
            1.0,
            40.0,
        )
        assert loss_db == pytest.approx(24.074, abs=5e-3)
        assert loss_db - 20.0 == pytest.approx(4.074, abs=5e-3)
        assert loss_db > best_case_db

    def test_the_aperture_ratio_is_three_not_four(self) -> None:
        """§4.3.2's "about four times" is 3.06 at zenith, and not one number.

        The claim compares the 2.3 m Helmos station with the 1.3 m Skinakas one.
        Measured across their own elevation range — their §4.1 floor is 20° —
        the ratio is **3.056 at zenith and 3.249 at 20°**, rising as the link
        gets worse because the smaller aperture loses proportionally more to the
        longer slant path.

        Two things are asserted and the second is the reason this test exists.
        First, that the claim fails at every elevation in their range, by
        between 19 % and 24 %. Second, that the ratio is **not constant**: the
        disagreement was written down in `PENDING_DISAGREEMENTS` as "3.06 at
        every elevation tested", which is the zenith value read as if it were a
        plateau. A one-line description of a number nobody had measured is
        exactly how a plausible wrong number survives, which is the failure mode
        this project's citation policy exists for.

        The scale of the effect, for context: the bare aperture-area ratio is
        (2.3/1.3)^2 = 3.13, and the key rate is sublinear in transmittance once
        the decoy bound bites, so four is not reachable from this geometry at
        all.
        """
        log = DegradationLog()
        ratios = {}
        for elevation_deg in (20.0, 45.0, 90.0):
            elevation_rad = (
                ZENITH_RAD if elevation_deg == 90.0 else float(deg_to_rad(elevation_deg))
            )
            helmos = _secret_bits_per_pulse(_total_loss_db(HELMOS_M, elevation_rad, log), log)
            skinakas = _secret_bits_per_pulse(_total_loss_db(SKINAKAS_M, elevation_rad, log), log)
            ratios[elevation_deg] = helmos / skinakas

        assert ratios[90.0] == pytest.approx(3.056, abs=5e-3)
        assert ratios[45.0] == pytest.approx(3.088, abs=5e-3)
        assert ratios[20.0] == pytest.approx(3.249, abs=5e-3)

        # It fails everywhere in their range...
        for ratio in ratios.values():
            assert ratio < NTANOS_APERTURE_RATIO_AS_PRINTED - 0.5

        # ...and it is not the single number the pending entry described.
        assert ratios[20.0] > ratios[45.0] > ratios[90.0]
        assert ratios[20.0] - ratios[90.0] == pytest.approx(0.193, abs=5e-3)

        # The aperture-area ratio, which is the scale of the effect and still below four.
        assert (HELMOS_M / SKINAKAS_M) ** 2 == pytest.approx(3.130, abs=5e-3)


class TestTheDeclaredGap:
    """A gap is a claim, and this is the only way one can be asserted."""

    def test_no_zenith_transmittance_is_printed(self) -> None:
        """Their Eq. (7) needs `L_zen` and the paper never gives it.

        The assertion can only be about the shape of the row, because the
        content of the claim is an absence in a document: nothing published,
        nothing computed, no tolerance. What it protects against is the way a
        gap rots — somebody supplies the number the source never printed,
        `classify` starts returning something other than `GAP`, and the row goes
        on saying that the paper left it out.

        Why it matters here rather than being bookkeeping: `L_zen` is raised to
        the air mass in their Eq. (7), so it is the single most load-bearing
        atmospheric input of their budget, and its absence is exactly why
        `ntanos2021.best-case-total-loss` can only ever be *compatible*. This
        project does not need their number — it computes the extinction from a
        stated meteorological visibility (ADR 0023) — and that independence is
        what lets the gap stay declared instead of being filled with a guess.
        """
        gap = case("ntanos2021.zenith-transmittance")
        assert gap.status is ValidationStatus.GAP
        assert gap.published is None
        assert gap.computed is None
        assert gap.tolerance is None
        assert gap.deviation is None

        # And the row it explains is compatible and not reproduced, for that reason.
        assert case("ntanos2021.best-case-total-loss").status is ValidationStatus.COMPATIBLE


class TestTheModuleSurface:
    """What is true of the thirteen rows together."""

    def test_the_status_mix_is_the_one_the_docstring_claims(self) -> None:
        """The module headline is a claim about its own output, so it is asserted.

        Eleven Ntanos et al. rows — two reproduced, one compatible, one gap,
        seven not reproduced — plus one Ma et al. row and one Lim et al. one.
        """
        collected = cases()
        assert len(collected) == 13

        ntanos = [c for c in collected if c.identifier.startswith("ntanos2021.")]
        assert len(ntanos) == 11
        assert Counter(c.status for c in ntanos) == {
            ValidationStatus.NOT_REPRODUCED: 7,
            ValidationStatus.REPRODUCED: 2,
            ValidationStatus.COMPATIBLE: 1,
            ValidationStatus.GAP: 1,
        }

        assert [c.identifier for c in collected if not c.identifier.startswith("ntanos2021.")] == [
            "ma2005.eq10-gain-adds-instead-of-uniting",
            "lim2014.printed-detection-rate",
        ]

    def test_every_disagreement_this_module_produces_was_written_down(self) -> None:
        """The five that moved out of `PENDING_DISAGREEMENTS`, plus the two new ones.

        Five identifiers sat in `PENDING_DISAGREEMENTS` before this module
        existed, described but unreachable. All five are produced here. Two more
        disagreements appeared while writing it — Eq. (20)'s click probability
        and the swapped station coordinates — and both are listed too, because
        the mapping is enforced in both directions.
        """
        disagreeing = {c.identifier for c in cases() if c.status is ValidationStatus.NOT_REPRODUCED}
        assert disagreeing <= set(EXPECTED_DISAGREEMENTS)
        assert disagreeing >= {
            "ntanos2021.eq5-printed-gain-product",
            "ntanos2021.protocol-efficiency-as-printed",
            "ntanos2021.full-moon-background",
            "ntanos2021.single-pass-peak-skr",
            "ntanos2021.aperture-ratio-helmos-skinakas",
        }
        assert not disagreeing & set(PENDING_DISAGREEMENTS)

    def test_the_only_pending_identifier_left_is_the_one_with_a_reason(self) -> None:
        """`lim2014.block-1e4-reach`, and the module says why it is not a row.

        Not an oversight and not laziness: computing it needs Lim et al.'s
        optimisation over five free parameters, which lives beside the test that
        measures the disagreement. Lifting it into `src/` would leave two
        implementations of one published Evaluation section. The reason is in
        the module docstring and in `PENDING_DISAGREEMENTS`, and this asserts
        that the entry did not quietly grow company.
        """
        assert set(PENDING_DISAGREEMENTS) == {"lim2014.block-1e4-reach"}

    def test_every_row_that_agrees_rests_on_a_derived_tolerance(self) -> None:
        """No row in this module passes on a width somebody chose.

        The three that reproduce name where their width comes from: the paper's
        own printed precision ("about 13 urad" is two significant figures), the
        paper's rounding of 10/ln(10) to 4.343, and the first-order truncation
        `p_dc/2` of Lim et al.'s two-detector union. A tolerance picked so that
        today's number passes can never fail, so it proves nothing.
        """
        agreeing = [c for c in cases() if c.status is ValidationStatus.REPRODUCED]
        assert len(agreeing) == 3
        for c in agreeing:
            assert "tuned" not in c.tolerance_basis.lower()
            assert c.tolerance is not None and c.tolerance > 0.0
            assert len(c.tolerance_basis) > 60, (
                f"{c.identifier} does not say where its width is from"
            )
