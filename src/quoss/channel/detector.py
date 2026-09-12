"""The detector: what it loses, what it invents, and when it is not listening.

What this module is for
-----------------------
Everything so far in :mod:`quoss.channel` happens *outside* the receiver: the
atmosphere attenuates, the beam spreads, the sky adds photons. This module is
what happens from the aperture inwards, and a single-photon detector does three
different things to a link, which is why one module holds all three:

1. **It loses real photons.** Not every photon that enters the telescope
   produces a count. The optics absorb some, the filter absorbs some, and the
   detector itself converts only a fraction of what reaches it. That fraction
   chain is :func:`receiver_efficiency`.
2. **It invents counts that were never photons.** A *dark count* is a click with
   no light: in a semiconductor avalanche photodiode a carrier tunnels or is
   thermally freed and starts the same avalanche a photon would; in a
   superconducting nanowire it is a thermal fluctuation. An *afterpulse* is a
   click caused by the previous click — carriers trapped during one avalanche
   escape a moment later and start another. Neither is distinguishable from a
   signal count once it is out of the detector.
3. **It goes blind after every count.** *Dead time* is the interval after a
   click during which the detector cannot produce another, because the avalanche
   has to be quenched or the nanowire has to cool back below its critical
   current. That makes the reported count rate a saturating function of the real
   one.

The first is a loss like any other in the budget. The second and third are not:
one adds noise that no amount of optical filtering removes, and the other makes
the instrument nonlinear in exactly the regime a high-rate link wants to work
in.

The composition rule, in one line
---------------------------------
**Means add; the exponential happens once, at the end.**

That sentence is the whole design of this module, and it exists because all
three of the published forms it reproduces break the rule in the same way.
A *mean* — the expected number of counts in a gate, written ``mu`` throughout —
is a non-negative number with no upper bound. A *probability* is a number in
``[0, 1]``. Independent Poisson processes have additive means, so signal,
background and dark counts are combined as means and converted once:

    p_click = 1 - exp(-(eta (mu_signal + mu_background) + mu_dark))

Every published expression below is the small-``mu`` linearisation of that, and
each one returns something above 1 somewhere inside the parameter space this
project sweeps. See "The three linearisations" below for what each costs.

**The trap this module is shaped to avoid: the efficiency chain applies to
everything that came through the aperture and to nothing that was born inside
the detector.** Background photons are photons — the optics and the quantum
efficiency attenuate them exactly as they attenuate signal, which is why
:mod:`quoss.channel.background` deliberately stops at the aperture and defers
the chain to here. Dark counts are not photons. They originate *after* the
optics, so multiplying them by the chain is not a modelling choice, it is a
missing term. Measured with the receiver of Ntanos et al. 2021 §4.1 (85 %
detectors, 3 dB filter, 2.65 dB receiver, so a 6.36 dB chain), the 2.3 m
telescope on their study night:

======================================  ==================  ================
Quantity                                Counts per gate     Share of noise
======================================  ==================  ================
Sky background at the aperture          7.64e-06            92.7 %
Sky background after the 6.36 dB chain  1.77e-06            74.7 %
Dark counts, two detectors at 300 cps   6.00e-07            25.3 %
======================================  ==================  ================

The chain moves the dark counts from 7 % of the noise to 25 % of it. Applying
the chain to the dark counts as well — the natural mistake, because it looks
like "apply the receiver efficiency to the noise" — understates the total noise
by a factor of 1.242, which is **0.94 dB** of noise that quietly disappears.
Nothing in the result looks wrong; the QBER comes out a little better than it
is.

The second finding: gating cannot touch afterpulsing
----------------------------------------------------
:mod:`quoss.channel.background` shows that narrowing the detection gate is the
cheapest decibels in the channel — from 1 ns to 100 ps costs 0.08 dB of signal
and removes 10 dB of sky. Dark counts scale linearly with the gate too, so they
do not rob it. **Afterpulses do not scale with the gate at all**, because an
afterpulse is triggered by a previous *click*, not by a duration: its rate is
proportional to the count rate, and the count rate is what the link produces.

Measured, with Lim et al. 2014's ``p_ap = 4e-2`` and a click probability of
1e-3 per gate (the middle of the published operating range — a 30 dB link with
``mu = 0.5``):

========  ==============  ==============  ==============  =============
Gate      Sky background  Dark counts     Afterpulses     Total
========  ==============  ==============  ==============  =============
1 ns      1.77e-06        6.00e-07        4.00e-05        4.24e-05
100 ps    1.77e-07        6.00e-08        4.00e-05        4.02e-05
========  ==============  ==============  ==============  =============

Ten times narrower buys **0.22 dB**, where the sky-only calculation promises 10.
So the two published detector sets *disagree about whether gating is worth
anything*, and the disagreement is a fact about the technology rather than about
the model: Ntanos et al. §4.1 write "and no after-pulsing effect" for their
superconducting nanowires, verbatim, because a nanowire has no trapped carriers
to release, while Lim et al.'s InGaAs avalanche photodiodes have
``p_ap = 4e-2``. Any statement of the form "narrow the gate" is conditional on
which detector is in the receiver, and this module is where that condition is
written down.

The three linearisations, priced
--------------------------------
All three published forms are first-order truncations of the composition rule,
and all three are excellent at the operating points their authors used. They are
written out here because a parameter sweep does not stay at the operating point.

**1. Two detectors' dark counts, added instead of unioned.** Lim et al. 2014
write the detection probability of a pulse of intensity ``k`` as::

    D_k = 1 - (1 - 2 p_dc) exp(-eta_sys k)

The ``2 p_dc`` is the union of two detectors' dark counts to first order; the
exact union is ``(1 - p_dc)^2``, which is what the additive-means rule gives
because ``exp(-2 mu_dc) = (1 - p_dc)^2`` when ``mu_dc = -ln(1 - p_dc)``. At
their ``p_dc = 6e-7`` the two agree to 7e-12 relative — this is not a
correction anyone needed. But ``1 - 2 p_dc`` goes negative above
``p_dc = 0.5``, and a "detection probability" then exceeds one: with the
daylight background probability of 0.967 that
:func:`quoss.channel.background.background_click_probability` returns for their
own receiver, the published form gives **1.93** where the exact one gives 0.999.
The two are 5 % apart at ``p_dc = 0.179``.

**2. Afterpulses counted once instead of cascading.** Lim et al. give the rate
including afterpulses as ``R_k = D_k (1 + p_ap)``: every primary click may be
followed by one afterpulse. If an afterpulse can itself afterpulse — it is a
real avalanche and traps real carriers — the geometric sum is ``1 / (1 - p_ap)``
instead. At ``p_ap = 4e-2`` the two differ by **0.16 %**; they reach 5 % at
``p_ap = sqrt(1/21) = 0.2182``, which is :data:`AFTERPULSE_CASCADE_LIMIT`.
Which of the two is right is not settled by any source verified here, so
:func:`afterpulsed_counts_per_gate` returns the published one and records a
warning carrying the other above that limit. Note also that Lim et al. apply
``(1 + p_ap)`` to ``D_k``, which is a probability, and call the result a rate:
at their operating point the distinction is invisible, and in the daylight case
it returns 1.006. This module applies afterpulsing to **counts** for that
reason.

**3. Two noise sources, added instead of unioned.** Ntanos et al. equation (A6)
writes the background yield as ``Y_0 = P_dc + P_noise``, a sum of two
probabilities where the union is ``1 - (1 - P_dc)(1 - P_noise)``. Same shape,
same conclusion: fine at 1e-6, above one in daylight, and unnecessary, because
the two means were available before either was exponentiated.

Dead time, and a published claim that does reproduce
----------------------------------------------------
Two models, and the difference is a hardware property, not an approximation:

- **Non-paralysable** — the dead time is a fixed window after each *recorded*
  count, and photons arriving inside it are lost without extending it. The usual
  behaviour of a quenched avalanche photodiode and of an SNSPD. The reported
  rate is ``m = R / (1 + R tau)``, which saturates at ``1 / tau``:
  **33.3 Mcps** for the 30 ns dead time of Ntanos et al. §4.1.
- **Paralysable** (extending) — every arrival restarts the dead time, whether or
  not it was recorded. ``m = R exp(-R tau)``, which *peaks* at ``1 / (e tau)``
  = 12.3 Mcps and then falls back towards zero.

The reason to carry both is that they disagree about the direction of failure.
Past its peak the paralysable model maps two incident rates to the same reported
one, so a measured rate cannot be corrected without knowing which side of the
peak it is on; the non-paralysable one is invertible everywhere below ``1 /
tau``, which is why :func:`incident_count_rate_cps` exists only for it. The two
agree to first order and part company at ``R tau = 0.3554``
(:data:`DEAD_TIME_MODEL_DIVERGENCE_LIMIT`), which is 11.8 Mcps at 30 ns.

And here is a published claim that **does** reproduce, which is worth recording
in a project whose notes are mostly full of ones that do not. Ntanos et al. §4.2
argue that "the photon loss due to link attenuation [...] prevents the detectors
of Bob station to be saturated due to their dead time, since only a limited
number of photons go to reach OGSs' detectors". With their 100 MHz source, their
30 ns dead time, ``mu = 0.5`` and their own best-case 20 dB total link loss, the
detected rate is 500 kcps and the dead-time loss is **1.5 %** (0.043 dB in the
gated form, where a 30 ns dead time blocks two of their 10 ns gate periods). At
30 dB it is 0.15 %. The claim is correct, and it is correct by two orders of
magnitude rather than narrowly.

What is deliberately not in here
--------------------------------
**The timing jitter's effect on the gate.** ``sigma_t`` is a detector property
and :data:`NTANOS_SNSPD_TIMING_JITTER_FWHM_S` lives here, but the law that turns
it into a kept fraction of the signal — ``erf(T / 2 sqrt(2) sigma)`` — is
:func:`quoss.channel.background.gate_signal_fraction`. The gate is where jitter
becomes a number, and the gate is the background module's only free parameter, so
the law belongs beside the term it trades against. Splitting a two-term trade
across two modules is how one of the terms gets forgotten.

**Yields, QBER and anything per basis.** The error rate an afterpulse causes is
``p_ap D_k / 2`` in Lim et al.'s own model — the factor of two because an
afterpulse carries no information about the bit, so half of them land on the
wrong detector — and the ``1 - (1 - Y_0)(1 - eta)^n`` yield of an ``n``-photon
state is the same kind of statement. Both are protocol quantities and live in
:mod:`quoss.qkd`. What this module hands over is a click probability and the
means behind it.

**The double-click outcome.** Lim et al. name four measurement outcomes,
``{0, 1, empty, both}``; a click in both detectors of a basis is a real event
with a protocol-level treatment (discard, or assign at random). Counting it
needs to know which detector belongs to which bit value, which is a protocol
fact.

**Datasheet values.** Gap 5 of ``docs/adr/0009-citation-policy.md`` is still
open: no free authoritative table of typical SPAD parameters was located, so the
constants here are the two *published and verified* parameter sets — Ntanos et
al. §4.1 for a superconducting nanowire and Lim et al. for an InGaAs avalanche
photodiode — and nothing is interpolated between them or averaged. They are not
a range of "typical" values; they are two instruments.

**Any conversion between a dark-count rate and a dark-count probability that
invents a gate.** The two sources publish the quantity in different units: 300
counts per second (Ntanos) and 6e-7 per gate (Lim). Converting between them
needs the gate width, and **Lim et al. state no gate width anywhere**, so
:func:`dark_count_rate_from_probability_cps` takes it as an argument and the
caller owns the assumption. Read at Ntanos's 1 ns gate, Lim's number implies 600
cps, twice the nanowire's 300 — plausible for a cooled InGaAs diode and not
something either paper says.

**Non-Poisson dark counts.** Afterpulsing makes a real detector's dark counts
*bunched* rather than Poisson, so the variance is larger than the mean even
though the mean is right. That matters for a finite-key statistical bound, not
for the mean rates here, and correcting it needs a measured afterpulse time
distribution, which no verified source supplies.

**Temperature, bias, latching, crosstalk, and recovery transients.** A real
SNSPD's efficiency depends on bias current; a real APD's dark rate roughly
doubles every 10 K; both can latch. All of them are datasheet-level effects and
gap 5 covers them.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``eta_q``                               detector quantum efficiency (-)
``eta``                                 full receiver efficiency chain (-)
``D``                                   dark count rate (counts/s)
``mu_dc``                               expected dark counts per gate (-)
``p_dc``                                dark count probability per gate (-)
``p_ap``                                afterpulse probability per click (-)
``tau``                                 detector dead time (s)
``R``                                   incident (true) count rate (counts/s)
``m``                                   observed (reported) count rate
                                        (counts/s)
``t_gate``                              detection gate width (s)
``T_rep``                               gate repetition period (s)
======================================  ====================================

References
----------
A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
§4.1 (the SNSPD parameters, the filter and receiver losses, the 1 ns gate), §4.2
(the 100 MHz repetition rate and the dead-time argument) and Appendix A
(equations (A4)-(A6), the yield and QBER model this module feeds).

C. C. W. Lim, M. Curty, N. Walenta, F. Xu and H. Zbinden, "Concise security
bounds for practical decoy-state quantum key distribution", *Phys. Rev. A*
**89**, 022307, 2014, Evaluation section: the InGaAs parameters
(``eta_Bob = 10 %``, ``p_dc = 6e-7``, ``p_ap = 4e-2``), the detection rate
``D_k = 1 - (1 - 2 p_dc) exp(-eta_sys k)``, the afterpulsed rate
``R_k = D_k (1 + p_ap)`` and the error model
``e_k = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2``.
"""

from __future__ import annotations

from typing import Final

import numpy as np

from quoss.channel._validation import validated_duration_s
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray
from quoss.core.units import loss_db_to_transmittance

__all__ = [
    "AFTERPULSE_CASCADE_LIMIT",
    "DEAD_TIME_MODEL_DIVERGENCE_LIMIT",
    "LIM_INGAAS_AFTERPULSE_PROBABILITY",
    "LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE",
    "LIM_INGAAS_EFFICIENCY",
    "NTANOS_FILTER_INSERTION_LOSS_DB",
    "NTANOS_RECEIVER_LOSS_DB",
    "NTANOS_SNSPD_AFTERPULSE_PROBABILITY",
    "NTANOS_SNSPD_DARK_COUNT_RATE_CPS",
    "NTANOS_SNSPD_DEAD_TIME_S",
    "NTANOS_SNSPD_EFFICIENCY",
    "NTANOS_SNSPD_GATE_DURATION_S",
    "NTANOS_SNSPD_TIMING_JITTER_FWHM_S",
    "afterpulsed_counts_per_gate",
    "click_probability",
    "dark_count_rate_from_probability_cps",
    "dark_counts_per_gate",
    "gates_blocked_per_click",
    "incident_count_rate_cps",
    "live_gate_fraction",
    "observed_count_rate_cps",
    "receiver_efficiency",
    "saturation_count_rate_cps",
]

# --------------------------------------------------------------------------- #
# The two published parameter sets. Gap 5 of ADR 0009: these are not "typical
# values", they are two instruments, each transcribed from a document that was
# opened.
# --------------------------------------------------------------------------- #

NTANOS_SNSPD_EFFICIENCY: Final[float] = 0.85
"""Quantum efficiency of the reference superconducting nanowire, at 1550 nm.

Ntanos et al. 2021 §4.1, verbatim: "we assumed SNSPDs with quantum efficiencies
of 85% at 1550 nm, dark count rates of 300 counts per second (cps), timing
jitter of 50 ps, dead time of 30 ns, and no after-pulsing effect."

Dimensionless fraction, not a percentage. 0.85 is 0.71 dB of loss, which is the
*smallest* term in the receiver chain: the 0.2 nm filter costs 3 dB and the rest
of the receiver 2.65 dB, so the detector is responsible for 11 % of the 6.36 dB
that :func:`receiver_efficiency` returns for this instrument.
"""

NTANOS_SNSPD_DARK_COUNT_RATE_CPS: Final[float] = 300.0
"""Dark count rate of the reference superconducting nanowire, counts/s.

Ntanos et al. 2021 §4.1. A **rate**, which is the convention this module treats
as primary because it is a property of the detector alone; the per-gate
probability depends on the gate and is therefore a property of the
detector *and* the design (see :func:`dark_counts_per_gate`).

In their own 1 ns gate this is 3e-7 counts per gate per detector, so 6e-7 for
the two detectors they use — numerically equal to
:data:`LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE`, which is *per detector* for
a different technology in a different paper. **That equality is a coincidence
and is recorded here so that nobody reads it as corroboration**: the two agree
only under a gate width that one of the two papers never states, and per
detector they differ by a factor of two.
"""

NTANOS_SNSPD_TIMING_JITTER_FWHM_S: Final[float] = 50e-12
"""Timing jitter of the reference superconducting nanowire, s, as a FWHM.

Ntanos et al. 2021 §4.1. Full width at half maximum, which is how datasheets
quote it and a factor of 2.3548 away from the standard deviation the Gaussian
model wants — reading one as the other costs 2.7 dB of signal at the optimal
gate.

The constant lives here because jitter is a detector property; the law that
turns it into a kept signal fraction is
:func:`quoss.channel.background.gate_signal_fraction`, because the gate is what
it trades against. See the module docstring on why that split is deliberate.
"""

NTANOS_SNSPD_DEAD_TIME_S: Final[float] = 30e-9
"""Dead time of the reference superconducting nanowire, s.

Ntanos et al. 2021 §4.1. Caps the reported count rate at 33.3 Mcps if the
detector is non-paralysable, and at 12.3 Mcps if it is paralysable
(:func:`saturation_count_rate_cps`). Neither cap is anywhere near the rates
their own link produces — 500 kcps at their best-case 20 dB loss — which is the
argument their §4.2 makes and this module reproduces.
"""

NTANOS_SNSPD_AFTERPULSE_PROBABILITY: Final[float] = 0.0
"""Afterpulse probability of the reference superconducting nanowire.

Ntanos et al. 2021 §4.1, verbatim: "and no after-pulsing effect". Exactly zero,
and it is a constant rather than an omission because it is the single parameter
that decides whether narrowing the detection gate is worth anything (see the
module docstring). A superconducting nanowire has no avalanche and therefore no
trapped carriers to release; the number is a property of the physics, not a
simplification the paper made.
"""

NTANOS_SNSPD_GATE_DURATION_S: Final[float] = 1e-9
"""Detection gate width of the reference receiver, s.

Ntanos et al. 2021 §4.1, verbatim: "The detector's gate duration time was set to
1 ns." A design choice rather than a detector property, and it is 20 times the
50 ps jitter of the same detector — 5.36 dB of ``S/sqrt(B)`` away from the
optimum that :func:`quoss.channel.background.gate_width_maximising_snr_s`
derives. Kept here as the published operating point, because every number in
this module and in :mod:`quoss.channel.background` that is quoted "per gate" is
quoted per *this* gate.
"""

NTANOS_FILTER_INSERTION_LOSS_DB: Final[float] = 3.0
"""Insertion loss of the reference receiver's 0.2 nm optical filter, dB.

Ntanos et al. 2021 §4.1: "a narrow band-pass filter of 0.2 nm with an insertion
loss of 3 dB". Half the light, and the trade it buys is in
:mod:`quoss.channel.background`: the filter width multiplies the sky background
linearly, so 0.2 nm instead of 1 nm removes 7 dB of noise for this 3 dB of
signal.
"""

NTANOS_RECEIVER_LOSS_DB: Final[float] = 2.65
"""Optical loss of the reference receiver, excluding the filter, dB.

Ntanos et al. 2021 §4.1: "the Bob's receiver loss was set to 2.65 dB". Covers
the telescope, the fibre coupling and the analyser optics as one number; the
paper does not break it down.

Deliberately **not** including their 0.3 dB polarisation decoherence loss, which
the same section lists separately as a property of the *link* ("the polarization
decoherence loss of the link was set to 0.3 dB"). It belongs to
``channel/link_budget.py``, and putting it in the receiver chain would apply it
to the sky background as well — which is wrong, because unpolarised background
light is not decohered by the channel.
"""

LIM_INGAAS_EFFICIENCY: Final[float] = 0.10
"""Detection efficiency of the reference InGaAs avalanche photodiode.

Lim et al. 2014, Evaluation, verbatim: "Bob uses an active measurement setup
with two single-photon detectors (InGaAs APDs): they have a detection efficiency
of eta_Bob = 10%, a dark count probability of p_dc = 6 x 10^-7 and an
after-pulse probability of p_ap = 4 x 10^-2."

10 dB of loss against the nanowire's 0.71 dB, which is the price of not needing
liquid helium. Their ``eta_Bob`` is the receiver-side efficiency as a whole, so
it is what :func:`receiver_efficiency` returns rather than what it takes: there
is no separate filter or optics term to add on top of it in that paper.
"""

LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE: Final[float] = 6e-7
"""Dark count probability per gate, per detector, of the reference InGaAs APD.

Lim et al. 2014, Evaluation. A **probability per gate**, which is the other of
the two conventions in the literature, and the paper states no gate width or
repetition period anywhere — so it cannot be converted into a rate without an
assumption the caller has to make and own (see
:func:`dark_count_rate_from_probability_cps`). At Ntanos et al.'s 1 ns gate it
would be 600 cps.

Their equation for the detection probability enters it as ``1 - 2 p_dc``, the
first-order union over their two detectors; the exact union is ``(1 - p_dc)^2``,
and at this value the two agree to 7e-12. See the module docstring for where
that stops being true.
"""

LIM_INGAAS_AFTERPULSE_PROBABILITY: Final[float] = 4e-2
"""Afterpulse probability per click of the reference InGaAs APD.

Lim et al. 2014, Evaluation. Four clicks in a hundred are followed by a
spurious one, and the reason that number matters out of proportion to its size
is in the module docstring: afterpulses are the one noise term that does not
scale with the detection gate, so they are what is left when gating has removed
everything it can. At a click probability of 1e-3 per gate they are 67 times the
dark counts of the same detector.

In the same paper's error model the afterpulse contribution to the error rate is
``p_ap D_k / 2``, which overtakes the dark-count contribution ``p_dc`` for any
detection probability above ``2 p_dc / p_ap = 3e-5`` — that is, for any link
loss below 42 dB at ``mu = 0.5``. The QBER term itself belongs to
:mod:`quoss.qkd`; the crossover is quoted here because it is what makes this
constant the important one.
"""

DEAD_TIME_MODEL_DIVERGENCE_LIMIT: Final[float] = 0.355361510699
"""``R tau`` above which the two dead-time models differ by more than 5 %.

The paralysable and non-paralysable models agree to first order in ``R tau``
and their ratio is ``(1 + R tau) exp(-R tau)``, which falls monotonically from
1. Setting it to 0.95 gives the root above, ``R tau = 0.3554``: at 30 ns of dead
time that is an incident rate of **11.8 Mcps**.

A **derived** threshold, not a chosen one, and re-derived by a root finder in
``tests/channel/test_detector.py`` rather than trusted from here. Below it the
choice of model is a detail; above it the two answers are different physics and
:func:`observed_count_rate_cps` says so in the log.
"""

AFTERPULSE_CASCADE_LIMIT: Final[float] = 0.218217890236
"""``p_ap`` above which counting afterpulses once instead of cascading matters.

Lim et al. 2014 multiply the detection rate by ``1 + p_ap``: one afterpulse per
primary click. If an afterpulse can itself afterpulse the factor is the
geometric sum ``1 / (1 - p_ap)``. Their ratio is ``1 / (1 - p_ap^2)``, so the
two models differ by 5 % at ``p_ap = sqrt(1/21) = 0.21822`` — a closed form, and
the value above is it.

At Lim et al.'s own ``p_ap = 4e-2`` the two differ by 0.16 %, which is why the
published form is the one returned. Above this limit
:func:`afterpulsed_counts_per_gate` records a warning carrying both values,
because no source verified here settles which model is right.
"""

_FIVE_PER_CENT: Final[float] = 0.05
"""The tolerance both derived limits above are the 5 % crossing of.

Named once so that the two constants and the tests that re-derive them cannot
drift apart, and because 5 % is the same criterion
:data:`quoss.channel.background.LINEAR_CLICK_PROBABILITY_LIMIT` uses — one
threshold convention across the noise budget rather than one per module.
"""


def _validated_fraction(name: str, value: float, *, hint: str = "") -> float:
    """Return a scalar in ``[0, 1]``, or raise naming the argument and the trap.

    Used for efficiencies and per-click probabilities, where the characteristic
    way of arriving wrong is as a percentage: an efficiency of 85 is as finite
    and non-negative as 0.85, and it would multiply a link budget by a hundred.
    """
    fraction = float(value)
    if not np.isfinite(fraction) or fraction < 0.0 or fraction > 1.0:
        message = (
            f"{name} must be finite and in [0, 1], got {fraction}. It is a dimensionless "
            "fraction, not a percentage: an efficiency of 85 % is 0.85, and 85 would multiply "
            "the link budget by a hundred."
        )
        raise DomainError(f"{message} {hint}".strip())
    return fraction


def _validated_counts_per_gate(name: str, value: FloatArray | float) -> FloatArray:
    """Return non-negative expected counts per gate as an array.

    Unbounded above on purpose: these are means, not probabilities, and the
    whole composition rule of this module depends on not confusing the two. A
    mean of 3.42 counts per gate is a real operating point — it is what the
    reference receiver collects from a bright daylight sky — and rejecting it
    here would be rejecting the case the module exists to get right.
    """
    counts = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(counts)):
        raise DomainError(f"{name} contains non-finite values.")
    if np.any(counts < 0.0):
        raise DomainError(
            f"{name} must be non-negative, got a minimum of {float(np.min(counts))}. These are "
            "expected counts per gate — a Poisson mean, dimensionless and unbounded above, not "
            "a probability. Values above 1 are accepted because a bright daylight sky really "
            "does deliver 3.4 background counts per nanosecond gate."
        )
    return counts


def _validated_probability(name: str, value: FloatArray | float) -> FloatArray:
    """Return an array of probabilities in ``[0, 1]``, rejecting anything else.

    The counterpart of :func:`_validated_counts_per_gate`, and the reason the two
    are separate functions rather than one with a flag: the whole point is that
    the bound applies to one of them and not to the other, so the two checks
    must not share a code path that could be given the wrong bound.
    """
    probability = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(probability)):
        raise DomainError(f"{name} contains non-finite values.")
    if np.any(probability < 0.0) or np.any(probability > 1.0):
        raise DomainError(
            f"{name} must lie in [0, 1], got the range [{float(np.min(probability))}, "
            f"{float(np.max(probability))}]. This argument is a probability, not a count: if "
            "what you have is an expected number of counts per gate, convert it with "
            "quoss.channel.detector.click_probability, which is where the one exponential of "
            "the noise budget belongs."
        )
    return probability


def _validated_rate_cps(name: str, value: FloatArray | float) -> FloatArray:
    """Return a non-negative count rate in counts per second, as an array."""
    rate = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(rate)):
        raise DomainError(f"{name} contains non-finite values.")
    if np.any(rate < 0.0):
        raise DomainError(
            f"{name} must be non-negative, got a minimum of {float(np.min(rate))}. The unit is "
            "counts per second: a 300 cps dark count rate is 300.0, and a dark count "
            "probability per gate of 6e-7 is not a rate — convert it with "
            "quoss.channel.detector.dark_count_rate_from_probability_cps, which needs the gate "
            "width to do it."
        )
    return rate


def receiver_efficiency(
    quantum_efficiency: float,
    *,
    optical_loss_db: float = 0.0,
) -> float:
    """Return the fraction of aperture photons that produce a count.

    The whole chain from aperture to click, as one number::

        eta = eta_q * 10 ** (-L / 10)

    with ``eta_q`` the detector's quantum efficiency and ``L`` every optical
    loss between the aperture and the detector, summed in dB. For the reference
    receiver of Ntanos et al. §4.1 that sum is the 3 dB filter insertion loss
    plus the 2.65 dB receiver loss, and the product with 85 % is 0.2314, i.e.
    **6.36 dB**.

    **This factor applies to signal and to sky background alike, and to dark
    counts not at all.** Background photons come through the same optics and hit
    the same detector, so :mod:`quoss.channel.background` deliberately reports
    counts *at the aperture* and leaves this multiplication to
    :func:`click_probability`, which applies it to both and to nothing else. See
    the module docstring for the 0.94 dB of noise that goes missing if the chain
    is applied to the dark counts too.

    **It is a scalar, and that is deliberate.** Everything in it is a property
    of the instrument: the coatings, the filter, the detector bias. Nothing here
    varies along a pass, so unlike the transmittances of
    :mod:`quoss.channel.beam` this one has no time axis, and giving it one would
    invite a caller to put an elevation-dependent term in it — which would be a
    real term, and would belong to the atmosphere.

    Parameters
    ----------
    quantum_efficiency
        Detector efficiency, a dimensionless fraction in ``[0, 1]``. Note that
        Lim et al.'s ``eta_Bob = 10 %`` is already a whole-receiver number, so
        for that instrument this is the only term and ``optical_loss_db`` stays
        zero.
    optical_loss_db
        Every optical loss between the aperture and the detector, summed, dB,
        non-negative. Zero by default, which is the "detector efficiency only"
        case.

    Returns
    -------
    float
        Efficiency in ``[0, 1]``.

    Raises
    ------
    DomainError
        If the efficiency is not in ``[0, 1]``, or the loss is not finite and
        non-negative.

    Examples
    --------
    The reference receiver, and the chain read as a loss:

    >>> from quoss.core.units import transmittance_to_loss_db
    >>> eta = receiver_efficiency(
    ...     NTANOS_SNSPD_EFFICIENCY,
    ...     optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    ... )
    >>> round(eta, 6)
    0.23143
    >>> round(float(transmittance_to_loss_db(eta)), 3)
    6.356

    The detector is the smallest of the three terms: 85 % is 0.71 dB against
    5.65 dB of optics.

    >>> round(float(transmittance_to_loss_db(NTANOS_SNSPD_EFFICIENCY)), 3)
    0.706

    And the InGaAs receiver, where the published efficiency is already the whole
    chain:

    >>> receiver_efficiency(LIM_INGAAS_EFFICIENCY)
    0.1
    """
    efficiency = _validated_fraction("quantum_efficiency", quantum_efficiency)
    loss_db = float(optical_loss_db)
    if not np.isfinite(loss_db) or loss_db < 0.0:
        raise DomainError(
            f"optical_loss_db must be finite and non-negative, got {loss_db}. The sign "
            "convention is a loss: 3 dB of filter insertion loss is +3.0, and passing -3.0 "
            "would return an efficiency of 2, which is a receiver that emits photons."
        )
    return efficiency * float(loss_db_to_transmittance(loss_db))


def dark_counts_per_gate(
    dark_count_rate_cps: FloatArray | float,
    *,
    gate_duration_s: float,
    detector_count: int = 1,
) -> FloatArray:
    """Return the expected dark counts in one gate, summed over the detectors.

    A dark count is a click with no photon: a thermally generated or
    tunnelling carrier starting the same avalanche a photon would, or a thermal
    fluctuation driving a nanowire normal. It is Poisson — the events are
    independent — so the expected number in a window is a rate times a
    duration::

        mu_dc = n * D * t_gate

    with ``n`` the number of detectors whose clicks the receiver counts as one
    detection event.

    **The linear scaling with the gate is the reason this term does not rob
    gating of its value.** :mod:`quoss.channel.background` shows that narrowing
    the gate removes sky background proportionally while costing almost no
    signal; dark counts obey the same proportionality, so the whole
    non-afterpulse noise budget scales together. What does *not* scale is
    afterpulsing (:func:`afterpulsed_counts_per_gate`), and that asymmetry is the
    finding in the module docstring.

    **Why the detector count multiplies here rather than in the protocol.** A
    receiver that measures one basis with two detectors registers a detection if
    *either* fires, so the dark-count process it sees is the superposition of
    two independent Poisson processes, whose mean is the sum. Doing it as a sum
    of means rather than as a union of probabilities is what makes the exact
    two-detector union ``(1 - p_dc)^2`` come out of the single exponential in
    :func:`click_probability`, instead of the ``1 - 2 p_dc`` of Lim et al.'s
    printed form.

    Parameters
    ----------
    dark_count_rate_cps
        Dark count rate **per detector**, counts per second, non-negative. Any
        shape: a real detector's dark rate drifts with temperature over hours,
        so this is the array-valued argument, matching the shape of
        :func:`quoss.channel.background.background_counts_per_gate`.
    gate_duration_s
        Gate width, s, strictly positive.
    detector_count
        Number of detectors summed into one detection event. A positive integer;
        1 by default, 2 for both of the reference receivers.

    Returns
    -------
    FloatArray
        Expected dark counts per gate, dimensionless, shaped like the rate.

    Raises
    ------
    DomainError
        If the rate is negative or non-finite, the gate is not finite and
        positive, or the detector count is not a positive integer.

    Examples
    --------
    The reference nanowires: 300 cps each, two of them, in a 1 ns gate.

    >>> mu = dark_counts_per_gate(
    ...     NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    ...     gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
    ...     detector_count=2,
    ... )
    >>> f"{float(mu):.4e}"
    '6.0000e-07'

    Narrowing the gate to 100 ps takes them down with it, exactly in proportion:

    >>> narrow = dark_counts_per_gate(
    ...     NTANOS_SNSPD_DARK_COUNT_RATE_CPS, gate_duration_s=100e-12, detector_count=2
    ... )
    >>> f"{float(narrow):.4e}"
    '6.0000e-08'

    Vectorised over a drifting dark rate:

    >>> import numpy as np
    >>> drifting = dark_counts_per_gate(
    ...     np.array([300.0, 450.0, 900.0]), gate_duration_s=1e-09, detector_count=2
    ... )
    >>> drifting.shape
    (3,)
    """
    rate = _validated_rate_cps("dark_count_rate_cps", dark_count_rate_cps)
    gate_s = validated_duration_s("gate_duration_s", gate_duration_s)
    count = _validated_detector_count(detector_count)
    counts: FloatArray = count * rate * gate_s
    return counts


def _validated_detector_count(detector_count: int) -> int:
    """Return a positive integer number of detectors.

    An integer rather than a float because "1.5 detectors" is not a receiver
    that exists, and because the intended abuse — passing a *detection
    efficiency* here, or the two-detector union probability — is caught by the
    same check.
    """
    if isinstance(detector_count, bool) or not isinstance(detector_count, (int, np.integer)):
        raise DomainError(
            f"detector_count must be an int, got {type(detector_count).__name__}. It counts "
            "physical detectors whose clicks are pooled into one detection event: 1, or 2 for "
            "both of the reference receivers. An efficiency does not belong here."
        )
    count = int(detector_count)
    if count < 1:
        raise DomainError(
            f"detector_count must be at least 1, got {count}. A receiver with no detector has "
            "no dark counts and no signal either, which is not a link budget worth computing."
        )
    return count


def dark_count_rate_from_probability_cps(
    dark_count_probability_per_gate: FloatArray | float,
    *,
    gate_duration_s: float,
) -> FloatArray:
    """Return the dark count rate implied by a published per-gate probability.

    The inverse of :func:`dark_counts_per_gate` for a single detector, through
    the Poisson relation rather than through the linear one::

        mu_dc = -ln(1 - p_dc)        D = mu_dc / t_gate

    ``-ln(1 - p)`` rather than ``p`` because a probability per gate is the
    probability of *at least one* dark count, and the rate is set by the mean.
    At the published 6e-7 the two readings differ by 3e-7 relative — utterly
    invisible — and the exact form is used anyway, for the same reason the exact
    cone solid angle is used in :mod:`quoss.channel.background`: the linear one
    has no ceiling. It diverges as ``p`` approaches 1, where the correct answer
    is that a detector clicking in every gate has an unbounded dark rate, and
    that is the one place where a wrong answer would be silent rather than
    obviously wrong.

    **The gate width is an argument because the sources disagree about which
    quantity is primary.** Ntanos et al. publish a rate (300 cps) and Lim et al.
    publish a probability (6e-7 per gate) — and Lim et al. state no gate width
    anywhere in the paper, so this conversion cannot be done from their numbers
    alone. Anyone who wants their detector as a rate has to supply a gate, and
    that assumption is the caller's, which is why it is a required keyword and
    not a default.

    Parameters
    ----------
    dark_count_probability_per_gate
        Probability that one detector produces at least one dark count in one
        gate, in ``[0, 1]``. Any shape.
    gate_duration_s
        The gate width the probability was quoted for, s, strictly positive.

    Returns
    -------
    FloatArray
        Dark count rate per detector, counts per second, shaped like the input.

    Raises
    ------
    DomainError
        If the probability is outside ``[0, 1]`` or non-finite, or the gate is
        not finite and positive. A probability of exactly 1 raises, because the
        implied rate is infinite.

    Examples
    --------
    Lim et al.'s InGaAs diode, read at Ntanos et al.'s 1 ns gate — an assumption
    that is the reader's, since Lim et al. never state a gate:

    >>> rate = dark_count_rate_from_probability_cps(
    ...     LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE,
    ...     gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
    ... )
    >>> round(float(rate), 3)
    600.0

    Twice the nanowire's 300 cps. Read at a 10 ns gate instead it would be 60,
    which is *below* it — the factor between the two published detectors is
    entirely an artefact of the gate the reader assumes:

    >>> round(float(dark_count_rate_from_probability_cps(6e-07, gate_duration_s=10e-09)), 3)
    60.0

    And the round trip closes:

    >>> back = dark_counts_per_gate(rate, gate_duration_s=1e-09)
    >>> f"{float(back):.4e}"
    '6.0000e-07'
    """
    probability = _validated_probability(
        "dark_count_probability_per_gate", dark_count_probability_per_gate
    )
    gate_s = validated_duration_s("gate_duration_s", gate_duration_s)
    if np.any(probability >= 1.0):
        raise DomainError(
            "dark_count_probability_per_gate must be below 1, got a maximum of "
            f"{float(np.max(probability))}. A detector that dark-counts in every single gate "
            "implies an infinite rate, so there is no number to return; the published values "
            "are of order 1e-7."
        )
    rate_cps: FloatArray = -np.log1p(-probability) / gate_s
    return rate_cps


def click_probability(
    signal_photons_per_gate: FloatArray | float,
    *,
    efficiency: float,
    background_photons_per_gate: FloatArray | float = 0.0,
    dark_counts_per_gate: FloatArray | float = 0.0,
) -> FloatArray:
    """Return the probability that the receiver registers a click in one gate.

    The composition rule of the module, in code::

        p = 1 - exp(-(eta * (mu_signal + mu_background) + mu_dark))

    Three independent Poisson processes: signal photons at the aperture,
    background photons at the aperture, and dark counts inside the detector.
    Independent Poisson means add, so they are summed and exponentiated **once**.

    **The efficiency multiplies the first two and not the third**, which is the
    one asymmetry in the expression and the reason it is a single function
    instead of three. Signal and background photons both arrive through the
    aperture and are attenuated identically by the optics and the quantum
    efficiency — that identity is why :mod:`quoss.channel.background` stops at
    the aperture and why nothing there applies an optical chain. Dark counts are
    generated *behind* the optics, so they enter at full strength. Applying the
    chain to them as well understates the reference receiver's night noise by
    0.94 dB (module docstring).

    **This reproduces Lim et al. 2014's detection rate exactly.** Their form is::

        D_k = 1 - (1 - 2 p_dc) exp(-eta_sys k)

    and with ``mu_dark = 2 * (-ln(1 - p_dc))`` this function returns
    ``1 - (1 - p_dc)^2 exp(-eta_sys k)``, of which theirs is the first order in
    ``p_dc``. At their 6e-7 the two agree to 7e-12; the printed one exceeds 1
    above ``p_dc = 0.5``, which the daylight background of the same receiver
    reaches.

    **What the exponential assumes about the source.** ``1 - exp(-eta mu)`` is
    the detection probability of a *Poissonian* pulse — a weak coherent state,
    which is what every decoy-state BB84 source is, and what Lim et al.'s
    ``exp(-eta_sys k)`` assumes. For a heralded single-photon source the
    probability is ``eta mu`` instead, and for the ``n``-photon yields a
    protocol needs it is ``1 - (1 - Y_0)(1 - eta)^n``. Those are protocol
    statements and they live in :mod:`quoss.qkd`; what crosses the boundary from
    here is this probability and the means behind it.

    Parameters
    ----------
    signal_photons_per_gate
        Mean signal photons arriving at the aperture in one gate — the source's
        mean photon number times the channel transmittance. Non-negative, any
        shape: this is the quantity that sweeps over a pass, so it is the
        primary array argument.
    efficiency
        Receiver efficiency from aperture to click, from
        :func:`receiver_efficiency`.
    background_photons_per_gate
        Mean sky-background photons at the aperture in one gate, from
        :func:`quoss.channel.background.background_counts_per_gate`.
        Non-negative, any broadcastable shape. Zero by default.
    dark_counts_per_gate
        Mean dark counts per gate, already summed over the detectors, from
        :func:`dark_counts_per_gate`. Non-negative, any broadcastable shape.
        Zero by default. **Not** multiplied by ``efficiency``.

    Returns
    -------
    FloatArray
        Probability in ``[0, 1)``, broadcast over the inputs.

    Raises
    ------
    DomainError
        If any mean is negative or non-finite, or the efficiency is outside
        ``[0, 1]``.

    Examples
    --------
    Lim et al.'s 100 km fibre case reproduced — 20 dB of channel, ``mu = 0.5``,
    so 5e-3 photons per gate at the receiver, and their two 6e-7 detectors:

    >>> import numpy as np
    >>> dark = 2.0 * float(-np.log1p(-LIM_INGAAS_DARK_COUNT_PROBABILITY_PER_GATE))
    >>> p = click_probability(5e-03, efficiency=LIM_INGAAS_EFFICIENCY, dark_counts_per_gate=dark)
    >>> f"{float(p):.6e}"
    '5.010744e-04'

    The reference downlink at night: the sky delivers 7.64e-6 photons per gate
    at the 2.3 m aperture, the chain keeps 23 % of them, and the two nanowires
    add 6e-7 of their own.

    >>> eta = receiver_efficiency(0.85, optical_loss_db=5.65)
    >>> noise = click_probability(
    ...     0.0,
    ...     efficiency=eta,
    ...     background_photons_per_gate=7.6386e-06,
    ...     dark_counts_per_gate=6e-07,
    ... )
    >>> f"{float(noise):.4e}"
    '2.3678e-06'

    Applying the chain to the dark counts as well — the mistake this signature
    exists to make impossible — loses a quarter of that noise:

    >>> wrong = click_probability(
    ...     0.0, efficiency=eta, background_photons_per_gate=7.6386e-06 + 6e-07
    ... )
    >>> round(float(noise / wrong), 4)
    1.2419

    Vectorised over a pass, with the signal rising and falling:

    >>> over_a_pass = click_probability(
    ...     np.array([1e-05, 1e-03, 1e-05]),
    ...     efficiency=eta,
    ...     background_photons_per_gate=7.6386e-06,
    ...     dark_counts_per_gate=6e-07,
    ... )
    >>> np.round(over_a_pass * 1e6, 3)
    array([  4.682, 233.77 ,   4.682])
    """
    signal = _validated_counts_per_gate("signal_photons_per_gate", signal_photons_per_gate)
    background = _validated_counts_per_gate(
        "background_photons_per_gate", background_photons_per_gate
    )
    dark = _validated_counts_per_gate("dark_counts_per_gate", dark_counts_per_gate)
    eta = _validated_fraction("efficiency", efficiency)
    # One exponential, at the end, on the sum of the means. -expm1(-mu) rather
    # than 1 - exp(-mu) for the same reason as in background.py: at the
    # reference night mean of 2.4e-06 the naive form cancels the leading digits
    # of two numbers that agree to six decimals.
    probability: FloatArray = -np.expm1(-(eta * (signal + background) + dark))
    return probability


def afterpulsed_counts_per_gate(
    primary_counts_per_gate: FloatArray | float,
    *,
    afterpulse_probability: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the counts per gate including afterpulses, Lim et al.'s form.

    An afterpulse is a click caused by the previous click: carriers trapped in
    the semiconductor during one avalanche escape microseconds later and start
    another. Lim et al. 2014 model it as one possible afterpulse per primary
    click::

        R = D * (1 + p_ap)

    which is what this returns. The alternative — an afterpulse that can itself
    afterpulse, summing the geometric series — is ``D / (1 - p_ap)``, and the
    two differ by ``1 / (1 - p_ap^2)``: **0.16 % at the published 4e-2**, 5 % at
    :data:`AFTERPULSE_CASCADE_LIMIT`, above which a warning carries both. No
    source verified in ``docs/adr/0009-citation-policy.md`` settles which is
    right, so the published one is returned and the disagreement is recorded
    rather than averaged away.

    **Why this takes counts and not a probability.** Lim et al. multiply ``D_k``,
    which is a probability, by ``(1 + p_ap)`` and call the result a rate. At
    their operating point (``D_k`` of order 1e-3) that is invisible; with the
    0.967 daylight click probability of the reference receiver it returns 1.006,
    a probability above one, which is the same conflation
    :mod:`quoss.channel.background` found in Ntanos et al. equation (20). So
    afterpulsing is applied here to **means**, where a factor above one is
    meaningful, and the conversion to a probability happens in
    :func:`click_probability` and nowhere else.

    **Why afterpulsing is the term that matters out of proportion to its size.**
    It is the only noise source in the receiver that does not scale with the
    detection gate — it scales with the *click rate*, which is what the link
    produces. Narrowing the gate from 1 ns to 100 ps removes 10 dB of sky and
    10 dB of dark counts and **0 dB** of afterpulsing; at a click probability of
    1e-3 that turns a promised 10 dB of noise reduction into 0.22 dB. And with
    Lim et al.'s numbers the afterpulse contribution overtakes the dark-count
    contribution at a detection probability of ``2 p_dc / p_ap = 3e-5``, i.e.
    for any link loss below 42 dB.

    Parameters
    ----------
    primary_counts_per_gate
        Expected counts per gate from everything else — signal, background and
        dark counts, before afterpulsing. Non-negative, any shape.
    afterpulse_probability
        Probability that a click is followed by an afterpulse, in ``[0, 1]``.
        Zero for a superconducting nanowire, which has no avalanche and
        therefore no trapped carriers (see
        :data:`NTANOS_SNSPD_AFTERPULSE_PROBABILITY`).
    degradations
        Log that receives a warning where the cascading model would differ from
        the published one by more than 5 %.

    Returns
    -------
    FloatArray
        Counts per gate including afterpulses, shaped like the input.

    Raises
    ------
    DomainError
        If the counts are negative or non-finite, or the probability is outside
        ``[0, 1]``.

    Examples
    --------
    The published InGaAs diode, at a click probability in the middle of the
    published operating range. Nothing is recorded, because at 4e-2 the model
    ambiguity is 0.16 %:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> total = afterpulsed_counts_per_gate(
    ...     1e-03, afterpulse_probability=LIM_INGAAS_AFTERPULSE_PROBABILITY, degradations=log
    ... )
    >>> f"{float(total):.6e}"
    '1.040000e-03'
    >>> len(log)
    0

    The afterpulse part alone, 4e-5 per gate, against the same detector's
    6e-7 of dark counts — 67 times larger, and immune to the gate:

    >>> round(float(total) - 1e-03, 9)
    4e-05

    A nanowire has none of it, exactly:

    >>> nanowire = afterpulsed_counts_per_gate(
    ...     1e-03,
    ...     afterpulse_probability=NTANOS_SNSPD_AFTERPULSE_PROBABILITY,
    ...     degradations=log,
    ... )
    >>> float(nanowire)
    0.001

    A detector bad enough for the two models to part company says so:

    >>> noisy = DegradationLog()
    >>> _ = afterpulsed_counts_per_gate(1e-03, afterpulse_probability=0.3, degradations=noisy)
    >>> noisy.entries[0].code
    'detector.afterpulse-cascade-unresolved'
    >>> round(noisy.entries[0].details["cascade_factor"], 6)
    1.428571
    """
    counts = _validated_counts_per_gate("primary_counts_per_gate", primary_counts_per_gate)
    probability = _validated_fraction(
        "afterpulse_probability",
        afterpulse_probability,
        hint="It is a probability per click, not a rate and not a percentage: the published "
        "InGaAs value is 4e-2 and a superconducting nanowire is exactly 0.",
    )
    if probability > AFTERPULSE_CASCADE_LIMIT:
        published_factor = 1.0 + probability
        cascade_factor = 1.0 / (1.0 - probability) if probability < 1.0 else float("inf")
        degradations.warn(
            "detector.afterpulse-cascade-unresolved",
            f"An afterpulse probability of {probability:.4g} is above the "
            f"{AFTERPULSE_CASCADE_LIMIT:.4g} where the two defensible afterpulse models differ "
            f"by more than 5 %: Lim et al. 2014's one-afterpulse-per-click form multiplies the "
            f"counts by {published_factor:.6g}, while letting afterpulses cascade multiplies "
            f"them by {cascade_factor:.6g}. The value returned is the published one. No source "
            "verified in docs/adr/0009-citation-policy.md settles which model is right, so this "
            "is a model uncertainty of "
            f"{100.0 * (cascade_factor / published_factor - 1.0):.1f} % on the noise, not a "
            "numerical one.",
            where="quoss.channel.detector.afterpulsed_counts_per_gate",
            afterpulse_probability=probability,
            published_factor=published_factor,
            cascade_factor=cascade_factor,
            cascade_limit=AFTERPULSE_CASCADE_LIMIT,
        )
    total: FloatArray = counts * (1.0 + probability)
    return total


def saturation_count_rate_cps(dead_time_s: float, *, paralysable: bool = False) -> float:
    """Return the highest count rate a detector of this dead time can report.

    Two answers, because the two dead-time models fail differently:

    - **Non-paralysable** (the default): the reported rate ``R / (1 + R tau)``
      rises monotonically to ``1 / tau`` and stays there. Every gap between
      counts is at least ``tau`` long, so ``1 / tau`` counts per second is the
      arithmetic ceiling — **33.3 Mcps** at the 30 ns of Ntanos et al. §4.1.
    - **Paralysable**: ``R exp(-R tau)`` has an interior maximum at
      ``R = 1 / tau``, where it equals ``1 / (e tau)`` = **12.3 Mcps**, and then
      *decreases*. A paralysable detector in a bright field reports fewer counts
      the more light it gets, and a rate below the maximum is consistent with
      two incident rates — which is why :func:`incident_count_rate_cps` refuses
      to invert this model.

    Neither ceiling is near the rates a satellite QKD downlink produces: with
    the reference source and the paper's own best-case 20 dB link, 500 kcps is
    1.5 % of the non-paralysable ceiling. The number matters for the *design*
    question rather than the budget — it is what caps the usable source
    repetition rate — and for recognising a saturated measurement when one shows
    up.

    Parameters
    ----------
    dead_time_s
        Detector dead time, s, strictly positive.
    paralysable
        ``False`` (default) for a fixed dead time after each recorded count;
        ``True`` for an extending one, restarted by every arrival.

    Returns
    -------
    float
        Maximum reportable count rate, counts per second.

    Raises
    ------
    DomainError
        If the dead time is not finite and positive.

    Examples
    --------
    >>> round(saturation_count_rate_cps(NTANOS_SNSPD_DEAD_TIME_S) / 1e6, 3)
    33.333
    >>> round(saturation_count_rate_cps(NTANOS_SNSPD_DEAD_TIME_S, paralysable=True) / 1e6, 3)
    12.263

    The paralysable ceiling is lower by a factor of ``e``, which is the whole
    difference between the two models expressed as one number:

    >>> import numpy as np
    >>> ratio = saturation_count_rate_cps(30e-09) / saturation_count_rate_cps(
    ...     30e-09, paralysable=True
    ... )
    >>> round(ratio - float(np.e), 12)
    0.0
    """
    dead_time = validated_duration_s(
        "dead_time_s",
        dead_time_s,
        hint="A 30 nanosecond dead time is 30e-9.",
    )
    if paralysable:
        return 1.0 / (np.e * dead_time)
    return 1.0 / dead_time


def observed_count_rate_cps(
    incident_rate_cps: FloatArray | float,
    *,
    dead_time_s: float,
    paralysable: bool = False,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the count rate a detector of this dead time reports.

    The two standard models, and the choice between them is a hardware fact:

    - **Non-paralysable**, the default: after each *recorded* count the detector
      is blind for ``tau``, and photons arriving inside that window are lost
      without extending it. ``m = R / (1 + R tau)``. This is how a quenched
      avalanche photodiode and an SNSPD behave.
    - **Paralysable** (extending): *every* arrival restarts the blind window,
      whether or not it was recorded. ``m = R exp(-R tau)``.

    Both are exact consequences of their assumption, not fits: for the
    non-paralysable case, each recorded count occupies ``tau`` of dead time plus
    ``1 / R`` of live waiting on average, so ``m = 1 / (tau + 1 / R)``, which is
    the formula rearranged.

    The models agree to first order and part company at ``R tau = 0.3554``
    (:data:`DEAD_TIME_MODEL_DIVERGENCE_LIMIT`), where a warning is recorded
    carrying both answers. A second warning fires when a paralysable detector is
    past its maximum at ``R tau = 1``, because there the reported rate *falls*
    with increasing light and no measurement can be corrected without knowing
    which branch it is on.

    **For a gated receiver, prefer** :func:`live_gate_fraction`. This function
    is the continuous-time form, appropriate for a free-running detector. A
    gated system loses whole gates rather than fractions of a second, and the
    difference is not negligible in the direction that matters: with a 30 ns
    dead time and 10 ns gate periods, a click blocks two gates, i.e. 20 ns of
    the 30, because the tail of the dead time ends between two gates and costs
    nothing. At the reference 20 dB link the continuous form gives 1.5 % of loss
    and the gated one 1.0 %.

    Parameters
    ----------
    incident_rate_cps
        True count rate arriving at the detector — what it would report with no
        dead time. Counts per second, non-negative, any shape: this is the
        quantity that varies over a pass.
    dead_time_s
        Dead time, s, strictly positive.
    paralysable
        Whether the dead time is extending. ``False`` by default, which is the
        behaviour of both reference detectors.
    degradations
        Log that receives a warning where the two models disagree by more than
        5 %, and a second one where a paralysable detector is past its maximum.

    Returns
    -------
    FloatArray
        Reported count rate, counts per second, shaped like the input.

    Raises
    ------
    DomainError
        If the rate is negative or non-finite, or the dead time is not finite
        and positive.

    Examples
    --------
    The reference downlink at night — 2.4 kcps of noise on the 2.3 m telescope —
    is nowhere near dead time, and nothing is recorded:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> m = observed_count_rate_cps(2367.8, dead_time_s=30e-09, degradations=log)
    >>> round(float(m), 3)
    2367.632
    >>> round(float(1.0 - m / 2367.8), 8)
    7.103e-05
    >>> len(log)
    0

    Their best-case 20 dB link at 100 MHz puts 500 kcps into the detector, which
    costs 1.5 %:

    >>> half_a_megacount = observed_count_rate_cps(500e03, dead_time_s=30e-09, degradations=log)
    >>> round(float(1.0 - half_a_megacount / 500e03), 6)
    0.014778

    Ten megacounts per second is where the choice of model becomes the dominant
    uncertainty, and the log says so:

    >>> loud = DegradationLog()
    >>> non_paralysable = observed_count_rate_cps(20e06, dead_time_s=30e-09, degradations=loud)
    >>> paralysable = observed_count_rate_cps(
    ...     20e06, dead_time_s=30e-09, paralysable=True, degradations=loud
    ... )
    >>> round(float(non_paralysable) / 1e6, 3)
    12.5
    >>> round(float(paralysable) / 1e6, 3)
    10.976
    >>> loud.entries[0].code
    'detector.dead-time-model-ambiguous'
    """
    rate = _validated_rate_cps("incident_rate_cps", incident_rate_cps)
    dead_time = validated_duration_s(
        "dead_time_s",
        dead_time_s,
        hint="A 30 nanosecond dead time is 30e-9.",
    )
    product = rate * dead_time
    worst = float(np.max(product)) if product.size else 0.0
    if worst > DEAD_TIME_MODEL_DIVERGENCE_LIMIT:
        non_paralysable = float(np.max(rate)) / (1.0 + worst)
        paralysable_value = float(np.max(rate)) * float(np.exp(-worst))
        degradations.warn(
            "detector.dead-time-model-ambiguous",
            f"The detector sees R tau = {worst:.4g}, above the "
            f"{DEAD_TIME_MODEL_DIVERGENCE_LIMIT:.4g} where the paralysable and non-paralysable "
            f"models differ by more than 5 %: at the loudest sample they report "
            f"{non_paralysable:.4g} and {paralysable_value:.4g} counts per second respectively. "
            "The model used here is the "
            f"{'paralysable' if paralysable else 'non-paralysable'} one. Which is right is a "
            "property of the hardware, not of the link, so it has to come from the detector's "
            "datasheet — gap 5 of docs/adr/0009-citation-policy.md.",
            where="quoss.channel.detector.observed_count_rate_cps",
            rate_times_dead_time=worst,
            non_paralysable_cps=non_paralysable,
            paralysable_cps=paralysable_value,
            divergence_limit=DEAD_TIME_MODEL_DIVERGENCE_LIMIT,
        )
    if paralysable and worst > 1.0:
        degradations.warn(
            "detector.paralysable-past-maximum",
            f"A paralysable detector at R tau = {worst:.4g} is past its maximum at 1, so the "
            "reported rate falls as the light rises and two incident rates give the same "
            "reading. Nothing can be inverted from a measurement in this regime, and a real "
            "detector here is more likely to be latched than to be following this model.",
            where="quoss.channel.detector.observed_count_rate_cps",
            rate_times_dead_time=worst,
            maximum_reportable_cps=1.0 / (np.e * dead_time),
        )
    if paralysable:
        observed: FloatArray = rate * np.exp(-product)
        return observed
    observed = rate / (1.0 + product)
    return observed


def incident_count_rate_cps(
    observed_rate_cps: FloatArray | float,
    *,
    dead_time_s: float,
) -> FloatArray:
    """Return the true count rate behind a reported one, non-paralysable only.

    The inverse of :func:`observed_count_rate_cps` in its non-paralysable
    form::

        R = m / (1 - m tau)

    which is the correction an experimentalist applies to a counter reading. It
    diverges as ``m`` approaches ``1 / tau``, which is right: a non-paralysable
    detector cannot report more than ``1 / tau``, so a reading at the ceiling is
    consistent with any amount of light.

    **There is no paralysable version, and that is the point of having this as a
    separate function.** ``m = R exp(-R tau)`` is not injective: it peaks at
    ``R = 1 / tau`` and falls afterwards, so every reported rate below the peak
    of ``1 / (e tau)`` corresponds to **two** incident rates — one below the peak
    and one above. Inverting it needs external knowledge of which branch the
    measurement is on, and a function that quietly picked the lower branch would
    be exactly the silent degradation this project forbids. So the ambiguity is
    a missing function rather than a hidden assumption.

    Parameters
    ----------
    observed_rate_cps
        Reported count rate, counts per second, non-negative, any shape.
    dead_time_s
        Dead time, s, strictly positive.

    Returns
    -------
    FloatArray
        True incident rate, counts per second, shaped like the input.

    Raises
    ------
    DomainError
        If the rate is negative or non-finite, the dead time is not finite and
        positive, or the reported rate is at or above ``1 / tau``, which no
        non-paralysable detector can produce.

    Examples
    --------
    A counter reading corrected back, and the round trip:

    >>> from quoss.core.errors import DegradationLog
    >>> true_rate = incident_count_rate_cps(1e06, dead_time_s=30e-09)
    >>> round(float(true_rate), 3)
    1030927.835
    >>> back = observed_count_rate_cps(true_rate, dead_time_s=30e-09, degradations=DegradationLog())
    >>> round(float(back), 6)
    1000000.0

    At a tenth of the ceiling the correction is 3 %; at nine tenths of it, a
    factor of ten. Which is why a counter near saturation measures the dead time
    rather than the light:

    >>> round(float(incident_count_rate_cps(3.3333e06, dead_time_s=30e-09)) / 3.3333e06, 4)
    1.1111
    >>> round(float(incident_count_rate_cps(30e06, dead_time_s=30e-09)) / 30e06, 4)
    10.0
    """
    observed = _validated_rate_cps("observed_rate_cps", observed_rate_cps)
    dead_time = validated_duration_s(
        "dead_time_s",
        dead_time_s,
        hint="A 30 nanosecond dead time is 30e-9.",
    )
    product = observed * dead_time
    if np.any(product >= 1.0):
        raise DomainError(
            f"observed_rate_cps reaches {float(np.max(observed))} counts per second, which is "
            f"at or above the 1 / tau = {1.0 / dead_time:.6g} ceiling of a non-paralysable "
            f"detector with a {dead_time} s dead time. No such detector can report that, so "
            "there is no incident rate to return: either the dead time is wrong, or the "
            "detector is not non-paralysable, or the reading is not a count rate."
        )
    incident: FloatArray = observed / (1.0 - product)
    return incident


def gates_blocked_per_click(dead_time_s: float, *, gate_period_s: float) -> int:
    """Return how many following gates one click blocks in a gated receiver.

    A gated receiver does not lose seconds of dead time, it loses whole gates: a
    gate that opens while the detector is recovering produces nothing, and one
    that opens after it has recovered is fully live. So the cost of dead time is
    an integer::

        blocked = ceil(tau / T_rep) - 1

    which counts the gate openings strictly inside the dead window — the
    integers ``j >= 1`` with ``j T_rep < tau``.

    **Two conventions are baked into that, and both are stated rather than
    hidden.** The dead time is measured from the *opening* of the gate that
    clicked, not from the click itself, which can be up to one gate width later;
    with the reference numbers that is 1 ns of slack on a 30 ns dead time, a 3 %
    effect, and it makes this estimate the conservative one. And a gate opening
    at exactly the recovery instant counts as live, which is what makes a dead
    time of exactly three periods block two gates rather than three.

    The integer is why gating is cheaper than the continuous formula suggests:
    30 ns of dead time at 100 MHz blocks 20 ns worth of gates, not 30, because
    the last third of the dead time expires between two gates and costs nothing.

    Parameters
    ----------
    dead_time_s
        Dead time, s, strictly positive.
    gate_period_s
        Interval between gate openings, s, strictly positive. The reciprocal of
        the source repetition rate: 100 MHz is ``10e-9``.

    Returns
    -------
    int
        Number of subsequent gates lost per click. Zero when the dead time is
        shorter than one period, which is the regime a slow source is in.

    Raises
    ------
    DomainError
        If either duration is not finite and positive.

    Examples
    --------
    Ntanos et al.'s 30 ns dead time at their 100 MHz repetition rate:

    >>> gates_blocked_per_click(NTANOS_SNSPD_DEAD_TIME_S, gate_period_s=10e-09)
    2

    Push the same detector to 1 GHz and it costs 29 gates per click, which is
    the trade their §4.2 names — a faster source buys raw rate until the dead
    time eats it:

    >>> gates_blocked_per_click(30e-09, gate_period_s=1e-09)
    29

    A source slow enough that the detector always recovers in time loses
    nothing:

    >>> gates_blocked_per_click(30e-09, gate_period_s=50e-09)
    0

    Exactly three periods of dead time blocks two gates, not three: the third
    gate opens at the instant the detector is live again.

    >>> gates_blocked_per_click(30e-09, gate_period_s=10e-09)
    2
    """
    dead_time = validated_duration_s(
        "dead_time_s",
        dead_time_s,
        hint="A 30 nanosecond dead time is 30e-9.",
    )
    period = validated_duration_s(
        "gate_period_s",
        gate_period_s,
        hint="It is the reciprocal of the source repetition rate, so 100 MHz is 10e-9 and not "
        "100e6.",
    )
    return int(np.ceil(dead_time / period)) - 1


def live_gate_fraction(
    click_probability_per_gate: FloatArray | float,
    *,
    gates_blocked_per_click: int,
) -> FloatArray:
    """Return the fraction of gates a gated detector is available for.

    The gated counterpart of :func:`observed_count_rate_cps`, and it is exact
    rather than approximate::

        f = 1 / (1 + b p)

    with ``b`` the gates blocked per click (:func:`gates_blocked_per_click`) and
    ``p`` the click probability of a *live* gate.

    The derivation is one line and worth following, because the usual objection
    to it — that two clicks close together would have overlapping dead windows
    and be double-counted — does not apply. Over ``N`` gates, a fraction ``f``
    are live, so ``N f p`` clicks occur, each blocking ``b`` gates:
    ``f = 1 - f p b``, hence the formula. The windows cannot overlap, because a
    click can only happen in a live gate and the ``b`` gates after a click are
    all blocked — so consecutive clicks are at least ``b + 1`` gates apart by
    construction.

    What the receiver actually reports is ``f p`` clicks per gate, which is the
    quantity a key rate integrates. Measured with the reference 30 ns dead time:

    ==========================  ==============  ==============
    Click probability per gate   100 MHz (b=2)   1 GHz (b=29)
    ==========================  ==============  ==============
    1e-3                        0.9980          0.9718
    1e-2                        0.9804          0.7752
    1e-1                        0.8333          0.2564
    ==========================  ==============  ==============

    The right-hand column is the reason a satellite link does not simply buy
    rate by raising the repetition frequency: at 1 GHz and a per-gate click
    probability of 1 %, a 30 ns detector throws away 1.1 dB of what the source
    produces.

    Parameters
    ----------
    click_probability_per_gate
        Probability that a live gate produces a click, in ``[0, 1]``, from
        :func:`click_probability`. Any shape.
    gates_blocked_per_click
        Gates lost per click, a non-negative integer, from
        :func:`gates_blocked_per_click`. Zero means the detector always recovers
        between gates, and the fraction is exactly 1.

    Returns
    -------
    FloatArray
        Fraction of gates that are live, in ``(0, 1]``, shaped like the input.

    Raises
    ------
    DomainError
        If the probability is outside ``[0, 1]`` or non-finite, or the blocked
        count is not a non-negative integer.

    Examples
    --------
    The reference receiver at 100 MHz, at the click probability of a 30 dB link:

    >>> round(float(live_gate_fraction(5e-04, gates_blocked_per_click=2)), 6)
    0.999001

    The same detector and link at 1 GHz, where the dead time starts to be the
    limit rather than the sky:

    >>> from quoss.core.units import transmittance_to_loss_db
    >>> live = live_gate_fraction(1e-02, gates_blocked_per_click=29)
    >>> round(float(live), 6)
    0.775194
    >>> round(float(transmittance_to_loss_db(live)), 4)
    1.1059

    A detector that recovers between gates loses nothing, for any signal:

    >>> import numpy as np
    >>> live_gate_fraction(np.array([1e-04, 1e-02, 0.5]), gates_blocked_per_click=0)
    array([1., 1., 1.])
    """
    probability = _validated_probability("click_probability_per_gate", click_probability_per_gate)
    blocked = gates_blocked_per_click
    if isinstance(blocked, bool) or not isinstance(blocked, (int, np.integer)):
        raise DomainError(
            f"gates_blocked_per_click must be an int, got {type(blocked).__name__}. It is a "
            "count of gates, from quoss.channel.detector.gates_blocked_per_click; a dead time "
            "in seconds does not belong here."
        )
    if int(blocked) < 0:
        raise DomainError(
            f"gates_blocked_per_click must be non-negative, got {int(blocked)}. Zero is the "
            "legitimate value for a detector that recovers within one gate period, and it "
            "returns a live fraction of exactly 1."
        )
    fraction: FloatArray = 1.0 / (1.0 + float(int(blocked)) * probability)
    return fraction
