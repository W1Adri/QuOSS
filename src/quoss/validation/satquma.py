"""Validation cases for SatQuMA: what is like-for-like with this project, and what is not.

Para quien llegue nuevo: SatQuMA (Satellite Quantum Modelling & Analysis) is the
University of Strathclyde's open-source finite-key calculator for satellite QKD
(github.com/cnqo-qcomms/SatQuMA, MIT licence). Its physics is published in Sidhu
et al., *Finite key effects in satellite quantum key distribution*, npj Quantum
Information 8, 18 (2022), arXiv:2012.07829 — opened for this module. It is the
obvious candidate for an external oracle of this project's finite-key stack,
and the point of this module is to say exactly how far that holds.

What *is* like-for-like, read off the paper:

- The **protocol family**. Sidhu et al. use weak coherent pulses with three
  intensities ``mu_1 > mu_2 > mu_3 = 0`` — two decoys, one of them the vacuum —
  exactly the structure of :mod:`quoss.qkd.finite_key`. (Not one decoy: the
  paper and the SatQuMA v1.1 manual, arXiv:2109.01686, both say "two-decoy".)
- The **key-length equation**. Their Eq. (4) is Lim et al. 2014 Eq. (1) — their
  Ref. [32] — with the same fixed cost ``6 log2(21/eps_s) + log2(2/eps_c)``,
  which this module recomputes through
  :attr:`~quoss.qkd.finite_key.SecurityParameters.penalty_bits`.
- The **noise convention**. Their extraneous-count probability ``p_ec`` is dark
  plus background counts per pulse in a 1 ns coincidence window, the same
  object as this project's noise counts per gate; the caption arithmetic
  (500 cps x 1 ns = 5e-7) is recomputed below.

What is *not*, and why no key length of theirs can be a V3 oracle here:

1. **Tail bound.** "the tight multiplicative Chernoff bound [35]" (§III and
   Methods VI A) where Lim et al. and this project use Hoeffding's inequality.
   SatQuMA v1.1 can select Hoeffding, but running it is out of scope (no new
   dependency, no network in CI), and the paper's numbers are Chernoff.
2. **Basis bias.** Efficient BB84 with ``p_X = 0.889`` (transmitter) and 0.9
   (receiver), key from one basis only; :mod:`quoss.system.key_volume` defaults
   to the symmetric 0.5.
3. **Error-correction leakage.** Their Eq. (9) is a finite-size estimate built
   on an inverse binomial distribution; this project charges
   ``f n_X h(Q)`` with a fixed ``f``.
4. **Channel.** Their link efficiency versus elevation is Micius's measured
   curve (their Ref. [41], Extended Data Fig. 3b) scaled to a 27 dB zenith value,
   shown only in their Fig. 1(c); this project computes a physical budget.
5. **Operation.** Protocol parameters and the transmission window are optimised
   per pass; here they are fixed by the scenario. Security parameters
   ``eps_c = 1e-15``, ``eps_s = 1e-9`` against this project's 1e-10 each, and a
   500 km orbit.

And every secret key length the paper reports is in a figure (Figs. 2-7), so
even the quantities that would be comparable are not printed. Those are the
two ``GAP`` cases. SatQuMA itself is never installed or run by this project.
"""

from __future__ import annotations

import math
from typing import Final

from quoss.channel.background import background_counts_per_gate
from quoss.qkd.finite_key import SecurityParameters
from quoss.validation.base import ValidationCase

__all__ = [
    "SATQUMA_BACKGROUND_RATE_FLOOR_CPS",
    "SATQUMA_COINCIDENCE_WINDOW_S",
    "SATQUMA_CORRECTNESS",
    "SATQUMA_EXTRANEOUS_COUNT_PROBABILITY",
    "SATQUMA_SECRECY",
    "SIDHU_2021",
    "cases",
]

SIDHU_2021: Final = (
    "J. S. Sidhu, T. Brougham, D. McArthur, R. G. Pousa and D. K. L. Oi, Finite key effects in "
    "satellite quantum key distribution, npj Quantum Inf. 8, 18 (2022) — the SatQuMA paper; "
    "preprint arXiv:2012.07829v2 opened via export.arxiv.org"
)

SATQUMA_EXTRANEOUS_COUNT_PROBABILITY: Final = 5e-7
SATQUMA_BACKGROUND_RATE_FLOOR_CPS: Final = 500.0
SATQUMA_COINCIDENCE_WINDOW_S: Final = 1e-9
"""Table I and its caption: "A reported background count rate 500 − 2000 cps per detector
(Moon position dependent) lower bounds p_ec by 5 × 10−7 [51], assuming a 1 ns coincidence
window"."""

SATQUMA_CORRECTNESS: Final = 1e-15
SATQUMA_SECRECY: Final = 1e-9
"""Table I: "Correctness parameter eps_c 10−15", "Secrecy parameter eps_s 10−9"."""

_TABLE_I_TEST: Final = "tests/validation/test_satquma.py::TestLikeForLike::"
_GAP_TEST: Final = "tests/validation/test_satquma.py::TestNotLikeForLike::"


def cases() -> tuple[ValidationCase, ...]:
    """Recompute the SatQuMA cases: two like-for-like identities, two declared gaps.

    Returns
    -------
    tuple of ValidationCase
        The noise-convention and fixed-cost cases, then the key-length and
        link-efficiency gaps.

    Examples
    --------
    >>> [case.status.value for case in cases()]
    ['reproduced', 'reproduced', 'gap', 'gap']
    """
    # Their Eq. (4), the last two terms, transcribed from the rendered page:
    # l = floor(s_X0 + s_X1 (1 - h(phi_X)) - lambda_EC - 6 log2(21/eps_s) - log2(2/eps_c)).
    published_fixed_cost = 6.0 * math.log2(21.0 / SATQUMA_SECRECY) + math.log2(
        2.0 / SATQUMA_CORRECTNESS
    )
    fixed_cost = SecurityParameters(
        correctness=SATQUMA_CORRECTNESS, secrecy=SATQUMA_SECRECY
    ).penalty_bits

    extraneous = float(
        background_counts_per_gate(
            SATQUMA_BACKGROUND_RATE_FLOOR_CPS, gate_duration_s=SATQUMA_COINCIDENCE_WINDOW_S
        )
    )
    return (
        ValidationCase.evaluate(
            identifier="satquma2021.extraneous-count-floor",
            source=SIDHU_2021,
            locator="Table I and caption: 500 cps per detector in a 1 ns window gives p_ec = 5e-7",
            quantity="extraneous counts per pulse (dark + background), lower bound",
            published=SATQUMA_EXTRANEOUS_COUNT_PROBABILITY,
            computed=extraneous,
            unit="counts per gate",
            tolerance=1e-12 * SATQUMA_EXTRANEOUS_COUNT_PROBABILITY,
            tolerance_basis=(
                "1e-12 relative: the caption's arithmetic is exact (a rate times a window), so "
                "only float rounding may separate the two."
            ),
            level="V2",
            note=(
                "The noise convention is shared: their p_ec per pulse in a 1 ns window is this "
                "project's mean background count per gate. It is a mean, not a probability; at "
                "5e-7 the two differ by mu/2 = 2.5e-7 relative, below anything this table "
                "resolves. What this does not share is the elevation dependence — both hold "
                "the background constant over a pass, and both say so."
            ),
            test=_TABLE_I_TEST + "test_the_extraneous_count_floor_is_the_caption_arithmetic",
        ),
        ValidationCase.evaluate(
            identifier="satquma2021.finite-key-fixed-cost",
            source=SIDHU_2021,
            locator="Eq. (4), the terms 6 log2(21/eps_s) + log2(2/eps_c), at Table I eps values",
            quantity="bits charged once per block, independent of the link",
            published=published_fixed_cost,
            computed=fixed_cost,
            unit="bits",
            tolerance=1e-12 * published_fixed_cost,
            tolerance_basis="1e-12 relative: two transcriptions of one closed form, float rounding.",
            level="V2",
            note=(
                "Identifies the bound family rather than validating it: their Eq. (4) is Lim et "
                "al. 2014 Eq. (1), their Ref. [32], so agreement here says the two stacks charge "
                "the same fixed cost and moves every difference in key length to the terms that "
                "are not shared — the Chernoff tail bound, the Eq. (9) leakage, the basis bias."
            ),
            test=_TABLE_I_TEST + "test_eq4_charges_the_same_fixed_cost_as_lim_eq1",
        ),
        ValidationCase.evaluate(
            identifier="satquma2021.single-pass-secret-key-length",
            source=SIDHU_2021,
            locator="Figs. 2-3: optimised single-pass secret key length versus eta_link^sys",
            quantity="finite secret key length of one zenith overpass",
            published=None,
            computed=None,
            unit="bits",
            tolerance=None,
            tolerance_basis="None: nothing is printed to compare against.",
            level="V3",
            note=(
                "Gap, for two independent reasons. Figure-only: no key length is printed in "
                "the text or a table, and a value read off a log-scale plot is not a published "
                "number (ADR 0009). And not like-for-like even if it were: multiplicative "
                "Chernoff bound against Hoeffding, efficient BB84 with p_X = 0.889/0.9 against "
                "0.5, the Eq. (9) binomial leakage against f n h(Q), a channel taken from "
                "Micius's measured curve against a physical budget, and per-pass optimisation "
                "of intensities and window against fixed scenario parameters. Closing it means "
                "generating SatQuMA output with the Hoeffding option into a frozen file with a "
                "manifest (tests/golden/README.md, V3 rules), not running it here."
            ),
            test=_GAP_TEST + "test_the_key_lengths_are_figure_only_and_the_bound_differs",
        ),
        ValidationCase.evaluate(
            identifier="satquma2021.link-efficiency-curve",
            source=SIDHU_2021,
            locator="Fig. 1(c) and Table I: eta_link(theta) from Micius data, 27 dB at zenith",
            quantity="system link efficiency at zenith (the curve's anchor)",
            published=27.0,
            computed=None,
            unit="dB",
            tolerance=None,
            tolerance_basis="None: nothing computed.",
            level="V2",
            note=(
                "Gap. The 27 dB is an input of theirs, 'the improved Micius system using a "
                "1.2 m diameter OGS receiver at Delingha', and the elevation dependence is "
                "digitised from Micius Extended Data Fig. 3b and shown only as a plot. Neither "
                "is computable from printed system parameters, so there is no physics here to "
                "compare with; see quoss.validation.micius for the Micius numbers that are."
            ),
            test=_GAP_TEST + "test_the_link_curve_is_an_input_not_a_result",
        ),
    )
