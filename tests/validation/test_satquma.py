"""Tests for `quoss.validation.satquma`: the two identities, and the two gaps.

These node ids are not chosen here. `quoss/validation/satquma.py` already names
them in each case's ``test`` field, which is how a row of ``docs/validation.md``
stays traceable to an assertion somebody can run — and they named a file that
did not exist. `tests/validation/test_base.py::TestTheTableRuns::
test_every_case_names_a_test_file_that_exists` now fails if that happens again.

- ``TestLikeForLike`` — the two places SatQuMA and this project are computing
  the same object, and what agreement there does and does not buy.
- ``TestNotLikeForLike`` — the two gaps, asserted as gaps, including the part
  that is easy to get wrong: a gap is a claim too, and it has to stay false.
"""

from __future__ import annotations

import math

import pytest

from quoss.channel.background import background_counts_per_gate
from quoss.qkd.finite_key import SecurityParameters
from quoss.validation.base import ValidationCase, ValidationStatus
from quoss.validation.satquma import (
    SATQUMA_BACKGROUND_RATE_FLOOR_CPS,
    SATQUMA_COINCIDENCE_WINDOW_S,
    SATQUMA_CORRECTNESS,
    SATQUMA_EXTRANEOUS_COUNT_PROBABILITY,
    SATQUMA_SECRECY,
    cases,
)


def case(identifier: str) -> ValidationCase:
    """Return the one case with this identifier, or fail saying it is gone."""
    matches = [c for c in cases() if c.identifier == identifier]
    assert len(matches) == 1, f"{identifier!r} is not one of {[c.identifier for c in cases()]}"
    return matches[0]


class TestLikeForLike:
    def test_the_extraneous_count_floor_is_the_caption_arithmetic(self) -> None:
        """Their `p_ec` floor is a rate times a window, and so is our count per gate.

        Table I's caption reads: "A reported background count rate 500 - 2000 cps
        per detector (Moon position dependent) lower bounds p_ec by 5 x 10^-7,
        assuming a 1 ns coincidence window". That is 500 x 1e-9, and
        `background_counts_per_gate` is the same product — which is the point:
        the two projects mean the same object by "noise per detection window",
        so a later disagreement in key length cannot be blamed on the noise
        convention.

        The tolerance is float rounding and nothing else, because both sides are
        one multiplication.
        """
        computed = float(
            background_counts_per_gate(
                SATQUMA_BACKGROUND_RATE_FLOOR_CPS, gate_duration_s=SATQUMA_COINCIDENCE_WINDOW_S
            )
        )
        assert computed == pytest.approx(SATQUMA_EXTRANEOUS_COUNT_PROBABILITY, rel=1e-12)
        assert case("satquma2021.extraneous-count-floor").status is ValidationStatus.REPRODUCED

    def test_a_mean_is_not_a_probability_but_here_the_difference_is_unresolvable(self) -> None:
        """The case note makes a quantitative claim; this is it, checked.

        `background_counts_per_gate` returns a *mean* count, and `p_ec` is used
        as a probability. They differ by the higher terms of the Poisson tail,
        relative order `mu/2`. At 5e-7 that is 2.5e-7 relative — six orders
        below the 1 % scale any row of this table resolves — so reading one as
        the other is safe *here* and would not be at daylight background, which
        is exactly what `quoss.qkd.base` refuses to let happen silently.
        """
        mean = SATQUMA_EXTRANEOUS_COUNT_PROBABILITY
        probability = -math.expm1(-mean)
        assert (mean - probability) / mean == pytest.approx(0.5 * mean, rel=1e-6)
        assert (mean - probability) / mean < 1e-6

    def test_eq4_charges_the_same_fixed_cost_as_lim_eq1(self) -> None:
        """Identifies the bound family; it does not validate the bound.

        Sidhu et al.'s Eq. (4) subtracts `6 log2(21/eps_s) + log2(2/eps_c)`,
        which is Lim et al. 2014 Eq. (1) — their own Ref. [32] — so
        `SecurityParameters.penalty_bits` must reproduce it exactly at their
        epsilons. What that buys is negative and useful: every remaining
        difference in key length is in the terms the two do *not* share (the
        Chernoff tail bound, the Eq. (9) leakage, the basis bias), and not in
        the per-block constant.
        """
        published = 6.0 * math.log2(21.0 / SATQUMA_SECRECY) + math.log2(2.0 / SATQUMA_CORRECTNESS)
        computed = SecurityParameters(
            correctness=SATQUMA_CORRECTNESS, secrecy=SATQUMA_SECRECY
        ).penalty_bits
        assert computed == pytest.approx(published, rel=1e-12)
        assert case("satquma2021.finite-key-fixed-cost").status is ValidationStatus.REPRODUCED

    def test_the_fixed_cost_is_a_cost_and_does_not_scale_with_the_block(self) -> None:
        """Why it is worth a row at all: it is what kills a short block.

        At their epsilons the constant is ~271 bits, charged once per block
        whatever the link does. A pass certifying a few hundred bits is
        therefore decided by this term and not by the channel — the mechanism
        behind the two zero passes of ADR 0011 §2.
        """
        penalty = SecurityParameters(
            correctness=SATQUMA_CORRECTNESS, secrecy=SATQUMA_SECRECY
        ).penalty_bits
        assert 250.0 < penalty < 300.0
        tighter = SecurityParameters(correctness=1e-20, secrecy=1e-20).penalty_bits
        assert tighter > penalty, "a stricter epsilon must cost more, not less"


class TestNotLikeForLike:
    def test_the_key_lengths_are_figure_only_and_the_bound_differs(self) -> None:
        """A gap is a claim, and the claim is that nothing here is comparable.

        Two independent reasons, both in `satquma.py`'s note: every secret key
        length Sidhu et al. report is in a figure (Figs. 2-7), and a value read
        off a log-scale plot is not a published number (ADR 0009); and even if
        one were printed it would not be like-for-like — multiplicative
        Chernoff against Hoeffding, efficient BB84 at `p_X = 0.889/0.9` against
        the symmetric 0.5, a binomial-leakage estimate against `f n h(Q)`, a
        channel digitised from Micius's measured curve against a computed
        budget, and per-pass optimisation against fixed scenario parameters.

        Asserted as a gap with **nothing computed**, because the failure mode
        this guards is somebody quietly filling in a number read off Fig. 2.
        """
        row = case("satquma2021.single-pass-secret-key-length")
        assert row.status is ValidationStatus.GAP
        assert row.published is None and row.computed is None
        assert row.tolerance is None

    def test_the_link_curve_is_an_input_not_a_result(self) -> None:
        """Their 27 dB has a published side and no computable side, and that is the gap.

        The zenith anchor is printed, so `published` is 27 dB; but the curve it
        anchors is digitised from Micius Extended Data Fig. 3b and shown only as
        a plot, and the 27 dB is stated as an assumption about "the improved
        Micius system using a 1.2 m diameter OGS receiver at Delingha", not
        derived from printed system parameters. There is no physics of theirs to
        recompute, so `computed` stays None and the row stays a gap.
        """
        row = case("satquma2021.link-efficiency-curve")
        assert row.status is ValidationStatus.GAP
        assert row.published == 27.0
        assert row.computed is None

    def test_no_satquma_case_claims_to_be_an_independent_implementation_of_a_key_length(
        self,
    ) -> None:
        """The whole module's honest summary, asserted so it cannot drift.

        SatQuMA is the natural V3 oracle for this project's finite-key stack and
        it is **not one yet**: nothing here is installed, run or compared
        against. The two reproduced rows are V2 transcriptions of printed
        arithmetic; the two V3-shaped rows are gaps. If a fifth case ever
        arrives claiming V3 with a number in it, that is a real oracle and this
        test should be the thing that makes someone say so out loud.
        """
        reproduced = [c for c in cases() if c.status is ValidationStatus.REPRODUCED]
        assert {c.level for c in reproduced} == {"V2"}
        computed_v3 = [c for c in cases() if c.level == "V3" and c.computed is not None]
        assert not computed_v3
