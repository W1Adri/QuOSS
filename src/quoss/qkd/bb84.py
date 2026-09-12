"""BB84 with weak coherent pulses and vacuum+weak decoy states.

What this module computes
-------------------------
It is the first and, for now, the only implementation of
:class:`~quoss.qkd.base.QkdProtocol`. In goes a
:class:`~quoss.qkd.base.LinkConditions` — a transmittance, a noise mean and a
misalignment error at every instant of a pass — and out comes a
:class:`~quoss.qkd.base.KeyRate`: a secret-key rate per pulse, a quantum bit
error rate, and the label saying which security claim they are.

Everything here is **asymptotic**: it assumes the block of detections is
infinitely long, so that every frequency Alice and Bob measure equals the
probability behind it. That is an upper bound on what a LEO pass delivers, and
:attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` says so in the result's own field.
The finite-key bound is ``finite_key.py``, and it needs a block length, which
needs the time axis this stage does not carry.

The vocabulary, assuming none of it
-----------------------------------
**Weak coherent pulse (WCP).** A true single-photon source is hard; every
satellite QKD transmitter to date uses a laser pulse attenuated until it carries
on average less than one photon. The photon number of such a pulse is Poisson
distributed: with a mean of ``mu = 0.56``, about 57 % of the pulses carry no
photon at all, 32 % carry exactly one, and 11 % carry two or more.

**The photon-number-splitting (PNS) attack, and why those 11 % are a problem.**
Whenever a pulse carries two or more photons, an eavesdropper can keep one and
forward the rest. She has then a perfect copy of the bit and has disturbed
nothing: no error appears, so the QBER does not see her. Worse, a satellite
downlink loses 28 dB, so Alice and Bob expect almost every pulse to vanish. Eve
can block every single-photon pulse, forward only the multi-photon ones through
a channel of her own with no loss, and match the gain Bob expects while knowing
the entire key.

**Tagging and GLLP.** The defence, from Gottesman, Lo, Lütkenhaus and Preskill,
is to assume the worst: every multi-photon pulse is *tagged*, meaning Eve knows
its bit for free. Only the clicks that came from **single-photon** pulses can
produce secrecy. So the rate is not "sifted bits minus error correction"; it is
"the single-photon part of the sifted bits, minus what it costs to hide it,
minus the error correction of *all* of it". That asymmetry — privacy
amplification prices only the single-photon part, error correction is paid on
everything — is the whole shape of :meth:`Bb84DecoyProtocol._key_rate`.

**The problem GLLP leaves open.** Bob's detector does not report which pulse its
click came from. Alice and Bob measure one number, the overall gain; they cannot
separate the single-photon part of it, and assuming the worst (that every click
came from a multi-photon pulse, and every loss fell on the single-photon ones)
gives zero key past a few dB.

**Decoy states, the trick that closes it.** Alice randomly varies the intensity
of her pulses between a signal value ``mu``, a weaker decoy value ``nu``, and
vacuum, and announces afterwards which pulse was which. Eve cannot tell them
apart while they are in flight — a ``mu`` pulse and a ``nu`` pulse carrying one
photon each are physically identical — so whatever she does to the channel, she
does to all three. The *yield* of an ``n``-photon pulse, ``Y_n``, is therefore
the same number in all three ensembles, and three measured gains constrain the
same unknowns. That is enough to bound ``Y_1`` from below and ``e_1`` from
above, which is exactly what GLLP needs.

**Vacuum+weak** is the particular choice implemented here: one weak decoy plus
genuine vacuum. Ma et al. 2005 prove it is the optimal two-decoy choice (their
§3.4, following the ``nu_2 -> 0`` argument at the end of their §3.3), and the
vacuum pulses measure ``Y_0`` — the probability of a click when nothing was
sent — directly.

The model, in four lines
------------------------
With ``eta`` the end-to-end transmittance, ``eta_n = 1 - (1 - eta)^n`` the
probability that at least one of ``n`` photons survives, ``Y_0`` the background
click probability and ``e_mis`` the misalignment error:

===========================  ============================================
``Y_n = Y_0 + eta_n - Y_0 eta_n``   yield of an ``n``-photon pulse (Ma Eq. 7)
``Q_n = Y_n mu^n e^-mu / n!``       gain of the ``n``-photon part (Ma Eq. 8)
``Q = 1 - (1 - Y_0) e^(-eta mu)``   overall gain, summed over ``n``
``E = e_0 + (e_mis - e_0) (Q - Y_0)/Q``  overall QBER, ``e_0 = 1/2``
===========================  ============================================

and the decoy bounds, Ma et al. Eqs. (34), (35) and (37), reproduced verbatim in
:func:`single_photon_bounds`. The rate is Ma et al. Eq. (1), which is Ntanos et
al. Eq. (1)::

    R = q { Q_1 [1 - h(e_1)] - Q_mu f h(E_mu) }

Four decisions, each with the number that justifies it
------------------------------------------------------
**1. The exact yield, not the published approximation.** Ma et al. write
``Y_n = Y_0 + eta_n - Y_0 eta_n`` and then, on the next line, ``~= Y_0 + eta_n``,
"assuming ``Y_0`` and ``eta`` are small". Summed over the Poisson distribution
the approximation gives their Eq. (10), ``Q = Y_0 + 1 - e^(-eta mu)``, which is
also Ntanos et al. Eq. (A4). This module uses the **first** line, whose sum is
``Q = 1 - (1 - Y_0) e^(-eta mu)`` — and that is
:func:`~quoss.channel.detector.click_probability` with the transmitted mean
``eta mu`` as signal and the noise mean as dark counts, so there is one Poisson
click law in the project and not a second copy of it.

The difference is the gates where the background *and* the signal both fire,
which the approximation counts twice. Measured at this project's reference
downlink (0.75 m telescope, zenith, ``mu = 0.56``): **0.0000787 %** at the night
noise of 7.88e-07 counts per gate, **0.070965 %** under the 6 W/(m^2 um sr)
daylight of Ntanos et al. on the same telescope, and **0.077502 %** on their
2.3 m one. Small — and then it stops being small in the only way that matters: above
**7.15 counts per gate** the published form returns a gain **above one**, 1.0007
at ten counts per gate. That is the same conflation of a mean with a probability
that :mod:`quoss.channel.background` found in Ntanos et al. Eq. (20), and
:class:`~quoss.qkd.base.KeyRate` rejects a gain above one, so the approximation
would not merely mislead here, it would raise.

**2. The QBER as a mixture, not as a quotient.** ``E`` above is written as a
weighted average of the background's coin flip ``e_0 = 1/2`` and the optics'
``e_mis``, weighted by the share of the clicks each produces. Algebraically that
is Ma et al. Eq. (11) with ``1 - e^(-eta mu)`` replaced by ``Q - Y_0``, which is
the same quantity once the gain is the exact one. The reason to spell it as a
mixture is that ``E <= 1/2`` then holds **in floating point**, not just in
algebra: every term is a convex combination of two numbers that are themselves
at most one half. Keeping Ma's numerator literally while using the exact gain
does not have that property — it returns ``E > 1/2`` above **3.91 counts per
gate**, and the ITU bright-sunshine case this project models sits at 3.42, 12.6 %
below it. A QBER above one half is not a worse key: it is an inverted bit
convention, and :class:`~quoss.qkd.base.KeyRate` raises on it.

**3. Where the decoy bound certifies nothing, it says so.** The lower bound on
``Y_1`` can come out **negative**, which is not a small yield but an empty
constraint set: the decoy gain is consistent with every single-photon pulse
having been blocked, so nothing is certified. Clamping it to zero is right, but
``e_1`` is then ``0/0``, and returning ``e_1 = 0`` there would draw a *perfect*
single-photon error rate exactly where the analysis failed. This module returns
``e_1 = 1/2`` — the value that carries no information, ``h(1/2) = 1``, zero key —
marks the sample in :attr:`SinglePhotonBounds.certified`, and records a
``bb84.single-photon-yield-uncertified`` degradation.

Worth knowing *when* that happens, because the intuitive answer is wrong. It is
not loss: swept from ``eta = 1`` down to ``1e-08`` at the reference night noise
with Ntanos et al.'s intensities, the bound stays positive the whole way and
converges onto ``Y_0`` — to within its own first-order-in-``nu`` slack, 1.221 %
at those intensities — because a link with no signal left still certifies that a
single photon would have clicked as often as the background does. What breaks it
is the **intensity choice**: at ``nu = 0.1`` the bound goes non-positive above
``mu = 3.72`` for ``eta = 1e-03`` and above ``mu = 3.97`` for ``eta = 0.1``,
because a bright signal state is mostly multi-photon and the decoy data can no
longer rule out that all of the gain came from there. In an experiment the third
cause is statistical fluctuation in the measured gains, which is exactly what an
asymptotic module cannot see and ``finite_key.py`` exists for.

**4. The protocol efficiency counts the pulses spent on decoys.** Ma et al. give
``q = 1/2`` for BB84: half the pulses are thrown away because Alice and Bob
chose different bases. Ntanos et al. Eq. (A1) extends it to
``q = (1/2) N_s/(N_s + N_1 + N_2)`` — the decoy and vacuum pulses are spent on
measuring the channel, not on making key. This module uses the second form, so
every rate it returns is **per emitted pulse**, decoys included, which is the
only denominator under which a source rate in hertz means anything.

Note on that reference. Ntanos et al. state "signal:decoy:vacuum ratio = 4:1:16"
and "q = about 2/5" in the same sentence, and the two do not agree: 4:1:16 put
into their own Eq. (A1) gives ``q = (1/2)(4/21) = 0.0952``, a factor 4.2 below
2/5. Reversing the order — 16:1:4 — gives ``(1/2)(16/21) = 0.3810``, which is
what "about 2/5" means. :data:`NTANOS_STATE_COUNTS` therefore holds ``(16, 1,
4)``, and the disagreement is written down here rather than averaged away.

What this module deliberately does not have
-------------------------------------------
**A finite-key bound.** See the module's first paragraph.

**One-decoy and three-plus-decoy variants.** The bound implemented here is the
vacuum+weak one and only that. A one-decoy protocol has a *different* bound, not
this one with a probability set to zero, which is why
:class:`Bb84DecoyProtocol` requires all three probabilities to be positive rather
than treating a zero as "skip that state".

**Optimisation of ``mu`` and ``nu``.** The intensities are arguments with no
defaults. Ntanos et al.'s 0.56 and 0.11 came from a numerical optimisation
against *their* link at *their* noise; a default would carry that optimisation
silently into a link it was not optimised for.
:meth:`Bb84DecoyProtocol.ntanos_2021` exists so that reproducing their
configuration is one named call rather than five remembered numbers.

**Asymmetric (efficient) BB84.** Biasing the basis choice pushes ``q`` towards 1
by making one basis rare, and the rare basis is then what the parameter estimate
is built from — which is a statement about a finite sample. Pricing it
asymptotically would be claiming the gain without the cost, so the sifting factor
here is one half and the biased variant waits for ``finite_key.py``.

**Double clicks.** :mod:`quoss.channel.detector` stops short of them and says
why; the treatment that assigns a random bit to a double click differs from what
is done here by ``O(Y_0 eta mu)`` — 6e-12 at the reference night point — and
belongs with a detector model that reports two outcomes, not one probability.

=================================  ==========================================
Symbol                             Meaning
=================================  ==========================================
``mu``                             mean photon number of a signal pulse (-)
``nu``                             mean photon number of a decoy pulse (-)
``eta``                            end-to-end transmittance (-)
``Y_0``                            click probability with nothing sent (-)
``Y_1``                            yield of a single-photon pulse (-)
``Q_mu``, ``Q_nu``                 gain of the signal, decoy intensity (-)
``Q_1``                            gain of the single-photon part of ``Q_mu``
``E_mu``, ``E_nu``                 QBER of the signal, decoy intensity (-)
``e_0``                            error rate of a background click, 1/2 (-)
``e_1``                            error rate of the single-photon part (-)
``e_mis``                          misalignment error probability (-)
``q``                              protocol efficiency: sifting times the
                                   signal-state fraction (-)
``f``                              error-correction efficiency, >= 1 (-)
=================================  ==========================================

References
----------
X. Ma, B. Qi, Y. Zhao and H.-K. Lo, "Practical decoy state for quantum key
distribution", *Phys. Rev. A* **72**, 012326, 2005 (arXiv:quant-ph/0503005).
Eq. (1) the key rate, Eqs. (6)-(11) the yield, gain and QBER model, Eq. (33) the
vacuum decoy state, Eqs. (34), (35) and (37) the vacuum+weak bounds implemented
in :func:`single_photon_bounds`.

A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021.
Eq. (1) and Appendix A, Eqs. (A1)-(A6): the same model, and §4.1 the parameter
set :meth:`Bb84DecoyProtocol.ntanos_2021` reproduces.

D. Gottesman, H.-K. Lo, N. Lütkenhaus and J. Preskill, "Security of quantum key
distribution with imperfect devices", *Quantum Inf. Comput.* **4**, 325, 2004:
the tagged/untagged split that makes ``Q_1`` and ``e_1`` the quantities to bound.
Cited for the idea, not by equation number — the form used here is Ma et al.'s
Eq. (1), which is the document that was opened (``docs/adr/0009-citation-policy.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Final

import numpy as np

from quoss.channel.detector import click_probability
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, FloatLike, frozen_view
from quoss.qkd.base import (
    PROTOCOLS,
    KeyRate,
    KeyRegime,
    LinkConditions,
    QkdProtocol,
    binary_entropy,
)

__all__ = [
    "NTANOS_DECOY_INTENSITY",
    "NTANOS_ERROR_CORRECTION_EFFICIENCY",
    "NTANOS_INTERFEROMETER_VISIBILITY",
    "NTANOS_SIGNAL_INTENSITY",
    "NTANOS_STATE_COUNTS",
    "VACUUM_ERROR_RATE",
    "Bb84DecoyProtocol",
    "IntensityObservables",
    "SinglePhotonBounds",
    "simulate_intensity",
    "single_photon_bounds",
]


VACUUM_ERROR_RATE: Final[float] = 0.5
"""``e_0``: the error rate of a click that carried no signal, one half.

A background count — sky photon, dark count, stray light — knows nothing about
the bit Alice sent, so it lands on the right outcome exactly as often as on the
wrong one. Ma et al. 2005 Eq. (33), ``E_vacuum = e_0 = 1/2``; Ntanos et al. 2021
say the same below their Eq. (A5).

Not a parameter. It is a consequence of the background being uncorrelated with
the signal, and a link where it is *not* one half is one where the noise has
structure, which is a different model and not a different number.
"""

NTANOS_SIGNAL_INTENSITY: Final[float] = 0.56
"""``mu`` of Ntanos et al. 2021 §4.1: mean photons per signal pulse.

From a numerical optimisation against their own link budget and noise, so it is
a number for *that* link. It is close to the ``mu ~ 0.5`` that Ma et al. 2005
Eq. (12) gives as the optimum in the loss-dominated limit, which is why it is a
reasonable starting point and not a universal one.
"""

NTANOS_DECOY_INTENSITY: Final[float] = 0.11
"""``nu`` of Ntanos et al. 2021 §4.1: mean photons per decoy pulse.

Ma et al. 2005 show the bound tightens as ``nu`` falls (their deviation
``beta_Y1`` is first order in ``nu``), so the optimum is "as weak as the
statistics allow" — and what the statistics allow is a finite-key question. In
the asymptotic limit implemented here a smaller ``nu`` is simply better, which is
the clearest sign that this module is not the whole story.
"""

NTANOS_INTERFEROMETER_VISIBILITY: Final[float] = 0.98
"""Receiver visibility ``V`` of Ntanos et al. 2021 §4.1.

Visibility is how cleanly the receiver can tell Alice's two states apart: 1 is
perfect, 0 is not telling them apart at all. It fixes the misalignment error
through ``e_mis = (1 - V)/2``, stated below their Eq. (A5), so their 98 % is
``e_mis = 0.01``.

It lives here rather than in :mod:`quoss.channel` because nothing in the channel
consumes it, and it is *not* a protocol parameter either: ``e_mis`` is a field of
:class:`~quoss.qkd.base.LinkConditions`, because it is a property of the optics
at both ends and not a choice the experimenter makes per run.

Examples
--------
>>> (1.0 - NTANOS_INTERFEROMETER_VISIBILITY) / 2.0
0.01
"""

NTANOS_ERROR_CORRECTION_EFFICIENCY: Final[float] = 1.22
"""``f`` of Ntanos et al. 2021 §4.1: the CASCADE error-correction efficiency.

Correcting an error rate ``E`` costs at least ``h(E)`` bits of public discussion
per sifted bit — that is Shannon's limit, ``f = 1``. A real code spends more, and
CASCADE spends 22 % more. Larger ``f`` means *less* key, so this number errs in
the safe direction; ``f < 1`` claims error correction below the Shannon limit and
is rejected by :class:`Bb84DecoyProtocol`.
"""

NTANOS_STATE_COUNTS: Final[tuple[int, int, int]] = (16, 1, 4)
"""Signal : decoy : vacuum pulse counts behind Ntanos et al. 2021's ``q = 2/5``.

Their §4.1 states the ratio as "4:1:16" and the protocol efficiency as "about
``q = 2/5``" in one sentence, and the two disagree. Their own Eq. (A1),
``q = (1/2) N_s/(N_s + N_1 + N_2)``, gives ``0.0952`` for 4:1:16 and ``0.3810``
for 16:1:4; only the second rounds to 2/5. The order is reversed in the paper,
and this constant holds the order that reproduces their stated ``q``.

Written down rather than quietly fixed, per the rule of
``docs/adr/0009-citation-policy.md``: a citation is a promise a reader can check,
and this one cannot be checked without being told which half of the sentence was
used.

Examples
--------
>>> signal, decoy, vacuum = NTANOS_STATE_COUNTS
>>> round(0.5 * signal / (signal + decoy + vacuum), 4)
0.381
"""

_UNCERTIFIED_QBER: Final[float] = VACUUM_ERROR_RATE
"""What ``e_1`` is reported as where the decoy bound certifies nothing.

One half, because ``h(1/2) = 1``: privacy amplification then removes the whole
single-photon contribution and the rate formula is left with only its
error-correction cost, which is the correct answer when nothing was certified.
Zero would be the dangerous substitution — it draws a perfect single-photon
channel exactly where the analysis failed.
"""

_PROBABILITY_SUM_SLACK: Final[float] = 1e-9
"""How far the three state probabilities may miss summing to one.

Not a tolerance on physics. Three numbers a person typed into a scenario file —
``0.76``, ``0.05``, ``0.19`` — must be allowed to be rounded decimals, while a
set that sums to 0.9 is a missing state and a set that sums to 1.5 is a
misunderstanding of what the fields mean. A part in a billion separates the two.
"""


def _frozen_bool(value: BoolArray) -> BoolArray:
    """Return a read-only view of a boolean array.

    :func:`~quoss.core.types.frozen_view` does the same for ``float64`` and is
    typed for it; a mask is the one array in this module that is not a float, and
    widening that helper's signature to make it accept one would weaken it
    everywhere else.
    """
    out = value.view()
    out.flags.writeable = False
    return out


def _range_of(value: FloatArray) -> str:
    """Format the range of an array for a message, surviving the empty case.

    Same helper and same reason as in :mod:`quoss.qkd.base`: an empty pass is
    legal, and ``np.min`` of an empty array raises, which would replace a message
    about one problem with a traceback about another.
    """
    if value.size == 0:
        return "empty"
    return f"{float(np.min(value)):.6g}, {float(np.max(value)):.6g}"


@dataclass(frozen=True, slots=True, kw_only=True)
class IntensityObservables:
    """What Alice and Bob publish about one source intensity: its gain and QBER.

    After a run they announce, for each intensity separately, how often Bob
    clicked and how often the two of them disagreed. Those two numbers per
    intensity are the *entire* input to the decoy analysis — everything
    :func:`single_photon_bounds` knows about the channel arrives through here.

    Keyword-only and frozen for the reasons
    :class:`~quoss.qkd.base.KeyRate` is: two float arrays of the same shape in a
    positional call are a swap waiting to happen, and a gain that can be edited
    after the bound was computed from it is a bound about nothing.

    Attributes
    ----------
    intensity : float
        Mean photon number of the pulses this describes, ``mu`` or ``nu`` or
        zero for vacuum. A property of the source, so a scalar even though the
        observables are arrays: Alice does not change her intensities during a
        pass.
    gain : FloatArray
        ``Q``: probability that a pulse of this intensity produced a click, from
        any cause. In ``[0, 1]``.
    qber : FloatArray
        ``E``: fraction of the sifted bits from this intensity that disagree. In
        ``[0, 1/2]``, and never below ``e_mis`` nor above one half, because it is
        a mixture of the two — see :func:`simulate_intensity`.

    Raises
    ------
    DomainError
        If the intensity is negative or non-finite, if either array holds
        non-finite values or leaves its range, or if the two do not broadcast to
        a common shape.
    """

    intensity: float
    gain: FloatArray
    qber: FloatArray

    def __post_init__(self) -> None:
        """Validate what :func:`single_photon_bounds` is allowed to assume."""
        intensity = float(self.intensity)
        if not np.isfinite(intensity) or intensity < 0.0:
            raise DomainError(
                f"intensity must be finite and non-negative, got {intensity}. It is a mean "
                "photon number per pulse, so a typical signal state is 0.5 and the vacuum "
                "state is exactly 0."
            )
        object.__setattr__(self, "intensity", intensity)

        gain = np.array(self.gain, dtype=np.float64)
        qber = np.array(self.qber, dtype=np.float64)
        for name, value in (("gain", gain), ("qber", qber)):
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
        if np.any(gain < 0.0) or np.any(gain > 1.0):
            raise DomainError(
                f"gain must lie in [0, 1], got range [{_range_of(gain)}]. It is a probability "
                "per pulse of this intensity, not a count rate."
            )
        if np.any(qber < 0.0) or np.any(qber > VACUUM_ERROR_RATE):
            raise DomainError(
                f"qber must lie in [0, 0.5], got range [{_range_of(qber)}]. It is a fraction of "
                "the sifted bits, and above one half it is an inverted bit convention rather "
                "than a worse link."
            )
        try:
            broadcast = np.broadcast_arrays(gain, qber)
        except ValueError as exc:
            raise DomainError(
                f"gain and qber must broadcast to a common shape, got {gain.shape} and "
                f"{qber.shape}."
            ) from exc
        object.__setattr__(self, "gain", frozen_view(broadcast[0]))
        object.__setattr__(self, "qber", frozen_view(broadcast[1]))

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the two arrays. ``()`` for a single instant."""
        return self.gain.shape

    def __repr__(self) -> str:
        return (
            f"IntensityObservables(intensity={self.intensity!r}, shape={self.shape}, "
            f"gain=[{_range_of(self.gain)}], qber=[{_range_of(self.qber)}])"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class SinglePhotonBounds:
    """What the decoy analysis certifies about the single-photon pulses.

    GLLP needs two numbers that nobody can measure directly: how many of Bob's
    clicks came from pulses that carried exactly one photon, and how often those
    particular clicks were wrong. The decoy method bounds them — the first from
    below, the second from above — and a bound in the safe direction is all a
    security proof needs. This is the pair, plus the mask saying where the bound
    exists at all.

    Attributes
    ----------
    single_photon_yield : FloatArray
        ``Y_1``, lower bound: probability that a single-photon pulse produced a
        click. Ma et al. 2005 Eq. (34), clamped at zero where it goes negative.
    single_photon_gain : FloatArray
        ``Q_1``, lower bound: the share of *all* pulses that both carried exactly
        one photon and clicked, ``Y_1 mu e^-mu``. Ma et al. 2005 Eq. (35). This
        is the quantity the rate formula multiplies, and it is smaller than
        ``Y_1`` by the Poisson factor because most pulses do not carry exactly
        one photon.
    single_photon_qber : FloatArray
        ``e_1``, upper bound: error rate of those clicks. Ma et al. 2005
        Eq. (37), clamped into ``[0, 1/2]``, and set to one half wherever
        ``certified`` is false.
    certified : BoolArray
        True where the bound on ``Y_1`` came out strictly positive, i.e. where
        the decoy data rule out the possibility that every single-photon pulse
        was blocked. False is not an error: it is the honest answer for a link
        too poor to certify anything, and the samples where it is false are the
        samples where ``single_photon_qber`` is a placeholder rather than a
        bound.

    Raises
    ------
    DomainError
        If any array holds non-finite values or leaves its range, or if the four
        do not broadcast to a common shape.
    """

    single_photon_yield: FloatArray
    single_photon_gain: FloatArray
    single_photon_qber: FloatArray
    certified: BoolArray

    def __post_init__(self) -> None:
        """Validate the ranges a rate formula is allowed to skip re-checking."""
        names = ("single_photon_yield", "single_photon_gain", "single_photon_qber")
        values = [np.array(getattr(self, name), dtype=np.float64) for name in names]
        for name, value in zip(names, values, strict=True):
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
        certified = np.array(self.certified, dtype=np.bool_)
        try:
            broadcast = np.broadcast_arrays(*values, certified)
        except ValueError as exc:
            raise DomainError(
                "single_photon_yield, single_photon_gain, single_photon_qber and certified must "
                f"broadcast to a common shape, got {[v.shape for v in values]} and "
                f"{certified.shape}."
            ) from exc
        yield_, gain, qber = broadcast[0], broadcast[1], broadcast[2]
        for name, value in (("single_photon_yield", yield_), ("single_photon_gain", gain)):
            if np.any(value < 0.0) or np.any(value > 1.0):
                raise DomainError(
                    f"{name} must lie in [0, 1], got range [{_range_of(value)}]. Where the decoy "
                    "bound goes negative there is nothing certified, which is zero and a false "
                    "entry in `certified`, not a negative probability."
                )
        if np.any(qber < 0.0) or np.any(qber > VACUUM_ERROR_RATE):
            raise DomainError(
                f"single_photon_qber must lie in [0, 0.5], got range [{_range_of(qber)}]. The "
                "upper bound is clamped at one half because that is where it stops carrying "
                "information: h(1/2) = 1 and the single-photon term vanishes."
            )
        for name, value in zip(names, broadcast[:3], strict=True):
            object.__setattr__(self, name, frozen_view(value))
        object.__setattr__(
            self, "certified", _frozen_bool(np.asarray(broadcast[3], dtype=np.bool_))
        )

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the arrays. ``()`` for a single instant."""
        return self.single_photon_yield.shape

    def __repr__(self) -> str:
        certified = int(np.count_nonzero(self.certified))
        return (
            f"SinglePhotonBounds(shape={self.shape}, "
            f"single_photon_yield=[{_range_of(self.single_photon_yield)}], "
            f"single_photon_qber=[{_range_of(self.single_photon_qber)}], "
            f"certified={certified}/{self.single_photon_yield.size})"
        )


def simulate_intensity(conditions: LinkConditions, *, intensity: float) -> IntensityObservables:
    """Return the gain and QBER a given source intensity would produce.

    What it is
    ----------
    The forward model: given what the channel does, what would Alice and Bob
    *measure* for pulses of mean photon number ``intensity``? In an experiment
    these two numbers are counted, not computed; in a simulation they have to
    come from somewhere, and this is the somewhere. Everything downstream —
    :func:`single_photon_bounds`, the rate formula — treats them as data and
    never looks at the transmittance again.

    The gain
    --------
    A pulse of mean photon number ``mu`` crossing a channel of transmittance
    ``eta`` delivers a Poisson mean of ``eta mu`` photons to the detector, and
    the background delivers its own mean on top. Independent Poisson means add,
    so one exponential at the end gives the probability of at least one count::

        Q = 1 - exp(-(eta mu + mu_noise)) = 1 - (1 - Y_0) exp(-eta mu)

    which is :func:`~quoss.channel.detector.click_probability` — the project's
    single Poisson click law, reused rather than re-derived. The efficiency
    argument is ``1.0`` because
    :attr:`~quoss.qkd.base.LinkConditions.transmittance` is already end-to-end
    with the receiver chain inside it; passing it twice is the 6.36 dB double
    count that :mod:`quoss.channel.link_budget` is shaped around.

    This is Ma et al. 2005 Eq. (7) **first line** summed over the Poisson photon
    distribution. Their Eq. (10) and Ntanos et al.'s Eq. (A4),
    ``Q = Y_0 + 1 - e^(-eta mu)``, is the second line — the small-``Y_0``
    approximation — and it differs by the gates where signal and background both
    fire. See decision 1 in the module docstring for the three places that
    difference was measured and the point at which it returns a probability
    above one.

    The QBER
    --------
    Two things put a wrong bit into the sifted key, and they behave differently.
    A background click is uncorrelated with what Alice sent, so it is wrong half
    the time — :data:`VACUUM_ERROR_RATE`. A signal photon that arrives through a
    misaligned polarisation reference is wrong with probability ``e_mis``, no
    matter how good the link gets. The QBER is those two mixed in proportion to
    how many clicks each produces::

        E = e_0 + (e_mis - e_0) * (Q - Y_0) / Q

    where ``(Q - Y_0)/Q`` is the fraction of the clicks that came from the
    signal. Written this way rather than as Ma et al.'s quotient, the answer is a
    convex combination of two numbers that are each at most one half, so
    ``e_mis <= E <= 1/2`` holds in floating point and not only in algebra — see
    decision 2 in the module docstring for the operating point where the other
    spelling breaks it.

    The two limits are worth reading off the formula. When the link is good the
    signal dominates, ``Q -> eta mu``, and ``E -> e_mis``: a link cannot be
    better than its optics. When the link is bad the background dominates,
    ``Q -> Y_0``, and ``E -> 1/2``: pure noise is a coin flip. The QBER of a
    satellite pass sweeps between those two ends, which is why it rises towards
    the horizon.

    Parameters
    ----------
    conditions : LinkConditions
        What the channel delivers. Supplies the transmittance, the background
        yield and the misalignment error.
    intensity : float
        Mean photon number per pulse, ``mu`` or ``nu``, or exactly ``0.0`` for
        the vacuum state. Non-negative and finite.

    Returns
    -------
    IntensityObservables
        Gain and QBER of the conditions' shape.

    Raises
    ------
    DomainError
        If the intensity is negative or non-finite.

    Examples
    --------
    This project's reference downlink at zenith on a clear night — 0.75 m
    telescope, 28.541 dB end to end — carrying Ntanos et al.'s signal intensity:

    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> night = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> signal = simulate_intensity(night, intensity=NTANOS_SIGNAL_INTENSITY)
    >>> f"{float(signal.gain):.6e}"
    '7.840884e-04'

    One pulse in 1275 clicks, and the QBER sits just above the 1 % of the optics
    because the night sky contributes almost nothing:

    >>> f"{float(signal.qber):.6e}"
    '1.049243e-02'

    The vacuum state is the sanity check the model has to pass exactly: sending
    nothing, the gain **is** the background yield and the error rate **is** one
    half. That is Ma et al. 2005 Eq. (33), reproduced rather than special-cased:

    >>> vacuum = simulate_intensity(night, intensity=0.0)
    >>> bool(vacuum.gain == night.background_yield), float(vacuum.qber)
    (True, 0.5)

    And the daylight limit, with the sky four orders of magnitude brighter: the
    background now dominates the clicks and the QBER walks towards the coin flip,
    far past anything a key could survive.

    >>> day = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.519554e-03,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> f"{float(simulate_intensity(day, intensity=0.56).qber):.4f}"
    '0.4539'

    Vectorised over a pass, one call for all of it:

    >>> pass_ = LinkConditions(
    ...     transmittance=np.array([3.06e-04, 1.3993e-03, 3.06e-04]),
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> simulate_intensity(pass_, intensity=0.56).shape
    (3,)
    """
    mean_photons = float(intensity)
    if not np.isfinite(mean_photons) or mean_photons < 0.0:
        raise DomainError(
            f"intensity must be finite and non-negative, got {mean_photons}. It is a mean "
            "photon number per pulse: Ntanos et al.'s signal state is 0.56, their decoy state "
            "is 0.11, and the vacuum state is exactly 0."
        )

    background = conditions.background_yield
    gain = click_probability(
        mean_photons * conditions.transmittance,
        efficiency=1.0,
        dark_counts_per_gate=conditions.noise_counts_per_gate,
    )
    # The share of the clicks that came from the signal rather than the sky. The
    # guard is for the one reachable case where nothing clicks at all: the vacuum
    # state on a link with no background. Every click is then a signal click by a
    # vacuous majority, so the share is zero and the QBER is the vacuum's one
    # half, which is the answer with no sifted bits behind it either way.
    safe_gain = np.where(gain > 0.0, gain, 1.0)
    signal_share = (gain - background) / safe_gain
    qber = VACUUM_ERROR_RATE + (conditions.misalignment_error - VACUUM_ERROR_RATE) * signal_share
    return IntensityObservables(intensity=mean_photons, gain=gain, qber=qber)


def single_photon_bounds(
    *,
    signal: IntensityObservables,
    decoy: IntensityObservables,
    background_yield: FloatLike,
    degradations: DegradationLog,
) -> SinglePhotonBounds:
    """Bound the single-photon yield from below and its error rate from above.

    What it is
    ----------
    Alice sent pulses at two non-zero intensities and at vacuum; Bob announced
    how often he clicked for each. From those three gains this returns the two
    quantities GLLP needs and nobody can measure: how much of the signal gain
    came from pulses carrying exactly one photon, and how wrong those clicks
    were.

    Why a bound and not a value
    ---------------------------
    The yields ``Y_0, Y_1, Y_2, ...`` are infinitely many unknowns and the
    measurement gives three equations, so they are not determined. But the
    security proof does not need them determined: it needs a *pessimistic*
    answer, and a linear programme over the unknowns has one. Ma et al. 2005
    solve it in closed form for the vacuum+weak choice, which is the three
    expressions below.

    The formulas, verbatim from Ma et al. 2005 Eqs. (34), (35) and (37)::

        Y_1 >= mu / (mu nu - nu^2) * B
        Q_1 >= mu^2 e^-mu / (mu nu - nu^2) * B
        e_1 <= (E_nu Q_nu e^nu - e_0 Y_0) / (Y_1 nu)

    with the shared bracket ``B = Q_nu e^nu - Q_mu e^mu nu^2/mu^2
    - (mu^2 - nu^2)/mu^2 Y_0``. They are kept in the published spelling, with the
    two prefactors written out separately even though ``Q_1 = Y_1 mu e^-mu``,
    because a reader with the paper open has to be able to match them line for
    line — that is what a citation is for in this project
    (``docs/adr/0009-citation-policy.md``).

    Why the bound survives the exact yield model
    --------------------------------------------
    :func:`simulate_intensity` does not use the small-``Y_0`` approximation the
    paper's own simulation section uses, so it is worth saying why the bound
    still holds. Its derivation uses only that the yields lie in ``[0, 1]`` and
    that Alice's photon number is Poisson — never a particular expression for
    ``Y_n``. Feeding it exact gains therefore gives a valid, and slightly
    tighter, bound. That is checkable rather than asserted: at the reference
    night link the bound certifies **96.13 %** of the true single-photon yield
    and **1.1595** times its true error rate, both in the safe direction, and the
    test that measures it computes the true values from the same model.

    Where it certifies nothing
    --------------------------
    ``B`` goes negative when the decoy gain is consistent with every
    single-photon pulse having been blocked and every click having come from a
    multi-photon one. That is not a small yield, it is an empty constraint set.
    Those samples come back with ``Y_1 = Q_1 = 0``, ``certified`` false, ``e_1``
    set to one half — the value that carries no information rather than the zero
    that would look like a perfect channel — and a
    ``bb84.single-photon-yield-uncertified`` entry in the log.

    Loss alone does not do it, which is worth stating because the opposite is the
    natural guess: with asymptotically exact data the bound stays positive at
    every transmittance from one down to ``1e-08``, converging onto ``Y_0`` up to
    its own slack. What does break it is an over-bright signal state — above
    ``mu = 3.72`` at ``eta = 1e-03`` with ``nu = 0.1`` — and, in an experiment
    rather than a simulation, statistical fluctuation in the measured gains. See
    decision 3 in the module docstring.

    Parameters
    ----------
    signal : IntensityObservables
        Gain and QBER of the signal intensity ``mu``. Its QBER is not used: the
        decoy bound is built from the *decoy* error rate, which is why Ma et al.
        remark that ``E_mu`` plays no part in estimating ``Y_1`` and ``e_1``.
    decoy : IntensityObservables
        Gain and QBER of the decoy intensity ``nu``. Must be strictly weaker than
        the signal.
    background_yield : float or FloatArray
        ``Y_0``, the vacuum gain — from
        :attr:`~quoss.qkd.base.LinkConditions.background_yield`, or equivalently
        from ``simulate_intensity(conditions, intensity=0.0).gain``. A
        probability, so the mean counts per gate must already have been through
        the exponential.
    degradations : DegradationLog
        Log that receives the uncertified and clamped samples. Required rather
        than optional, per :mod:`quoss.core.errors`.

    Returns
    -------
    SinglePhotonBounds
        The two bounds and the mask, of the broadcast shape of the inputs.

    Raises
    ------
    DomainError
        If the decoy intensity is not strictly between zero and the signal
        intensity, if ``background_yield`` is not a probability, or if the arrays
        do not broadcast to a common shape.

    Examples
    --------
    The reference night link again, with Ntanos et al.'s two intensities:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> night = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> log = DegradationLog()
    >>> bounds = single_photon_bounds(
    ...     signal=simulate_intensity(night, intensity=NTANOS_SIGNAL_INTENSITY),
    ...     decoy=simulate_intensity(night, intensity=NTANOS_DECOY_INTENSITY),
    ...     background_yield=night.background_yield,
    ...     degradations=log,
    ... )
    >>> f"{float(bounds.single_photon_yield):.6e}"
    '1.345875e-03'

    The certified yield is just under the transmittance, which is the check worth
    doing by hand: a single photon reaching the detector *is* the transmittance,
    so ``Y_1`` slightly below ``eta = 1.3993e-03`` is right and ``Y_1`` above it
    would be a broken bound.

    >>> float(bounds.single_photon_yield) < 1.3993e-03
    True
    >>> f"{float(bounds.single_photon_qber):.6e}"
    '1.191443e-02'
    >>> bool(bounds.certified), len(log)
    (True, 0)

    A signal state bright enough that most of its pulses carry two photons or
    more, and the analysis certifies nothing on the very same link — and says so,
    rather than returning a zero error rate that would plot as a perfect channel:

    >>> log = DegradationLog()
    >>> bounds = single_photon_bounds(
    ...     signal=simulate_intensity(night, intensity=5.0),
    ...     decoy=simulate_intensity(night, intensity=0.1),
    ...     background_yield=night.background_yield,
    ...     degradations=log,
    ... )
    >>> bool(bounds.certified), float(bounds.single_photon_gain)
    (False, 0.0)
    >>> float(bounds.single_photon_qber)
    0.5
    >>> log.entries[0].code
    'bb84.single-photon-yield-uncertified'

    The other end of the same failure: on a link so dark that nearly every click
    is background, the bound on ``e_1`` runs past one half. It is clamped there,
    because an error rate that is merely "unconstrained" is worth the same zero
    key whether the bound reads 0.5 or 5, and the clamp is recorded too:

    >>> log = DegradationLog()
    >>> dark = LinkConditions(
    ...     transmittance=1e-08,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> bounds = single_photon_bounds(
    ...     signal=simulate_intensity(dark, intensity=NTANOS_SIGNAL_INTENSITY),
    ...     decoy=simulate_intensity(dark, intensity=NTANOS_DECOY_INTENSITY),
    ...     background_yield=dark.background_yield,
    ...     degradations=log,
    ... )
    >>> bool(bounds.certified), float(bounds.single_photon_qber)
    (True, 0.5)
    >>> log.entries[0].code
    'bb84.single-photon-qber-clamped'
    """
    mu = signal.intensity
    nu = decoy.intensity
    if not 0.0 < nu < mu:
        raise DomainError(
            f"the decoy intensity must satisfy 0 < nu < mu, got nu={nu} and mu={mu}. The bound "
            "of Ma et al. 2005 Eq. (34) has mu*nu - nu^2 in its denominator, which is zero at "
            "nu = mu and negative above it, so equal or swapped intensities do not give a worse "
            "bound, they give an inverted one. A zero decoy intensity is the vacuum state, which "
            "is already the third state of this protocol and enters through background_yield."
        )

    y0 = np.asarray(background_yield, dtype=np.float64)
    if not np.all(np.isfinite(y0)):
        raise DomainError("background_yield contains non-finite values.")
    if np.any(y0 < 0.0) or np.any(y0 > 1.0):
        raise DomainError(
            f"background_yield must lie in [0, 1], got range [{_range_of(y0)}]. It is Y_0, the "
            "probability of a click with nothing sent, not the mean counts per gate: the "
            "conversion is LinkConditions.background_yield and happens once."
        )
    try:
        np.broadcast_shapes(signal.shape, decoy.shape, y0.shape)
    except ValueError as exc:
        raise DomainError(
            f"signal {signal.shape}, decoy {decoy.shape} and background_yield {y0.shape} must "
            "broadcast to a common shape. A trailing axis of length one against a full one "
            "silently makes an outer product rather than a pass."
        ) from exc

    # Ma et al. 2005 Eq. (34) and (35), sharing their bracket. Written in the
    # paper's spelling so a reader with it open can match term for term; the
    # cancellation inside the bracket is mild (a factor of 13 at Ntanos et al.'s
    # intensities, against the 16 digits of a float64) and rewriting it to avoid
    # cancellation would cost the correspondence to buy precision nothing needs.
    bracket = (
        decoy.gain * np.exp(nu)
        - signal.gain * np.exp(mu) * nu**2 / mu**2
        - (mu**2 - nu**2) / mu**2 * y0
    )
    raw_yield = mu / (mu * nu - nu**2) * bracket
    raw_gain = mu**2 * np.exp(-mu) / (mu * nu - nu**2) * bracket
    certified = raw_yield > 0.0

    # Ma et al. 2005 Eq. (37). The denominator is zero or negative exactly where
    # nothing is certified, so the division is done against a placeholder and the
    # result discarded there -- `np.where` evaluates both branches, and this
    # project runs with filterwarnings = ["error"], so a division by zero inside
    # the discarded branch would raise rather than be discarded.
    safe_yield = np.where(certified, raw_yield, 1.0)
    raw_qber = (decoy.qber * decoy.gain * np.exp(nu) - VACUUM_ERROR_RATE * y0) / (safe_yield * nu)

    single_photon_yield = np.where(certified, raw_yield, 0.0)
    single_photon_gain = np.where(certified, raw_gain, 0.0)
    single_photon_qber = np.where(
        certified, np.clip(raw_qber, 0.0, VACUUM_ERROR_RATE), _UNCERTIFIED_QBER
    )

    uncertified = int(np.count_nonzero(~certified))
    if uncertified:
        degradations.warn(
            "bb84.single-photon-yield-uncertified",
            f"The vacuum+weak decoy bound of Ma et al. 2005 Eq. (34) is non-positive at "
            f"{uncertified} of {certified.size} samples: the decoy gain there is consistent "
            "with every single-photon pulse having been blocked, so nothing about the "
            "single-photon yield is certified and the secret key rate is zero. Y_1 and Q_1 are "
            f"returned as zero and e_1 as {_UNCERTIFIED_QBER} -- the value that carries no "
            "information, h(1/2) = 1 -- rather than as a zero error rate, which would plot as a "
            "perfect single-photon channel exactly where the analysis failed. Read "
            "SinglePhotonBounds.certified for which samples.",
            where="quoss.qkd.bb84.single_photon_bounds",
            uncertified_samples=uncertified,
            total_samples=int(certified.size),
            signal_intensity=mu,
            decoy_intensity=nu,
        )
    clamped = int(np.count_nonzero(certified & (raw_qber > VACUUM_ERROR_RATE)))
    if clamped:
        degradations.warn(
            "bb84.single-photon-qber-clamped",
            f"The upper bound on e_1 of Ma et al. 2005 Eq. (37) exceeds one half at {clamped} of "
            f"{certified.size} samples and has been clamped to {VACUUM_ERROR_RATE}. A bound "
            "above one half says only that the single-photon error rate is unconstrained, and "
            "carrying it into the rate formula would give h(e_1) > 1 and a negative "
            "single-photon term -- privacy amplification removing more than the whole key. "
            "Clamped, the term is exactly zero, which is what an unconstrained error rate is "
            "worth.",
            where="quoss.qkd.bb84.single_photon_bounds",
            clamped_samples=clamped,
            total_samples=int(certified.size),
            worst_bound=float(np.max(raw_qber[certified])),
        )

    return SinglePhotonBounds(
        single_photon_yield=single_photon_yield,
        single_photon_gain=single_photon_gain,
        single_photon_qber=single_photon_qber,
        certified=certified,
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Bb84DecoyProtocol(QkdProtocol):
    """BB84 with weak coherent pulses and vacuum+weak decoy states, asymptotic.

    The object holds **only the experimenter's choices** — two intensities, how
    the pulses are split between the three states, and how good the error
    correction is. Everything the link does arrives in
    :class:`~quoss.qkd.base.LinkConditions`, and
    :meth:`~quoss.qkd.base.QkdProtocol.key_rate` is a pure function of the two.

    Every parameter is required. Ntanos et al.'s ``mu = 0.56`` came from
    optimising against their link and their noise; carried in as a default it
    would be an optimisation done for someone else's channel, applied silently to
    yours. :meth:`ntanos_2021` is the named way to ask for exactly their
    configuration.

    Attributes
    ----------
    signal_intensity : float
        ``mu``, mean photons per signal pulse. The pulses that make key.
    decoy_intensity : float
        ``nu``, mean photons per decoy pulse. Strictly between zero and ``mu``;
        the pulses that measure the channel.
    signal_probability : float
        Fraction of pulses sent at ``mu``. The only one of the three that reaches
        the rate, through ``q`` — see :attr:`protocol_efficiency`.
    decoy_probability : float
        Fraction sent at ``nu``.
    vacuum_probability : float
        Fraction sent empty. All three strictly positive and summing to one: a
        zero is not "skip that state", it is a *different* protocol with a
        different bound.
    error_correction_efficiency : float
        ``f >= 1``. One is Shannon's limit; CASCADE is
        :data:`NTANOS_ERROR_CORRECTION_EFFICIENCY`.

    Raises
    ------
    DomainError
        If the intensities are not ``0 < nu < mu``, if any probability is outside
        ``(0, 1)`` or the three do not sum to one, or if ``f < 1``.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> protocol = Bb84DecoyProtocol.ntanos_2021()
    >>> protocol.name
    'bb84-decoy'
    >>> round(protocol.protocol_efficiency, 6)
    0.380952

    Their configuration on this project's reference downlink, at zenith on a
    clear night:

    >>> night = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> log = DegradationLog()
    >>> rate = protocol.key_rate(night, degradations=log)
    >>> f"{float(rate.secure_per_pulse):.6e}"
    '1.180893e-04'
    >>> round(float(rate.secure_bit_s))
    11809
    >>> rate.regime
    <KeyRegime.ASYMPTOTIC: 'asymptotic'>

    Eleven kilobits a second, and that is an **upper** bound: the block of
    detections a real pass yields is a few minutes long, not infinite. For scale,
    Ntanos et al. report a maximum normalised rate of 3.9e-04 bit per pulse
    across their whole study — a different telescope at an elevation they do not
    state, so the two are compatible rather than one reproducing the other.

    A pass is the same call with arrays. The rate collapses towards the horizon
    because the transmittance does, and where the decoy bound stops certifying
    anything the answer is zero and the log says so:

    >>> a_pass = LinkConditions(
    ...     transmittance=np.array([1e-07, 3.06e-04, 1.3993e-03, 3.06e-04, 1e-07]),
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> log = DegradationLog()
    >>> rate = protocol.key_rate(a_pass, degradations=log)
    >>> rate.has_key
    array([False,  True,  True,  True, False])
    >>> np.round(rate.secure_bit_s)
    array([    0.,  2472., 11809.,  2472.,     0.])

    The QBER is what closes the two ends: 1.05 % at zenith, where the optics'
    1 % dominates, and 46.75 % at the ends, where the sky does.

    >>> np.round(rate.qber, 4)
    array([0.4675, 0.0122, 0.0105, 0.0122, 0.4675])
    """

    name: ClassVar[str] = "bb84-decoy"

    signal_intensity: float
    decoy_intensity: float
    signal_probability: float
    decoy_probability: float
    vacuum_probability: float
    error_correction_efficiency: float

    def __post_init__(self) -> None:
        """Validate the choices, so that a rate computed from them is answerable."""
        mu = float(self.signal_intensity)
        nu = float(self.decoy_intensity)
        for label, value in (("signal_intensity", mu), ("decoy_intensity", nu)):
            if not np.isfinite(value):
                raise DomainError(f"{label} must be finite, got {value}.")
        if not 0.0 < nu < mu:
            raise DomainError(
                f"the intensities must satisfy 0 < decoy_intensity < signal_intensity, got "
                f"decoy_intensity={nu} and signal_intensity={mu}. They are mean photon numbers "
                "per pulse, so Ntanos et al. 2021 §4.1 is 0.11 and 0.56; the decoy has to be the "
                "weaker of the two or the bound of Ma et al. 2005 Eq. (34) inverts."
            )
        object.__setattr__(self, "signal_intensity", mu)
        object.__setattr__(self, "decoy_intensity", nu)

        probabilities = {
            "signal_probability": float(self.signal_probability),
            "decoy_probability": float(self.decoy_probability),
            "vacuum_probability": float(self.vacuum_probability),
        }
        for label, value in probabilities.items():
            if not np.isfinite(value) or not 0.0 < value < 1.0:
                raise DomainError(
                    f"{label} must be finite and in (0, 1), got {value}. All three states are "
                    "sent: this is the vacuum+weak decoy protocol, and a probability of zero is "
                    "not that protocol with one state skipped but a different one, whose bound "
                    "is a different formula. It is a fraction, not a percentage."
                )
            object.__setattr__(self, label, value)
        total = sum(probabilities.values())
        if abs(total - 1.0) > _PROBABILITY_SUM_SLACK:
            raise DomainError(
                f"signal_probability, decoy_probability and vacuum_probability must sum to 1, "
                f"got {total}. They are the fractions of the emitted pulses sent at each "
                "intensity, and every rate this protocol returns is per emitted pulse, so a sum "
                "below one is a state that was forgotten and a sum above one is a "
                "double-counted denominator."
            )

        efficiency = float(self.error_correction_efficiency)
        if not np.isfinite(efficiency) or efficiency < 1.0:
            raise DomainError(
                f"error_correction_efficiency must be finite and at least 1, got {efficiency}. "
                "It is the factor by which a real code exceeds Shannon's limit -- CASCADE is "
                "1.22 -- and a value below one claims error correction that costs less than the "
                "entropy it removes."
            )
        object.__setattr__(self, "error_correction_efficiency", efficiency)

    @classmethod
    def ntanos_2021(cls) -> Bb84DecoyProtocol:
        """Return the configuration of Ntanos et al. 2021 §4.1.

        ``mu = 0.56``, ``nu = 0.11``, a 16:1:4 split of signal, decoy and vacuum
        pulses, and CASCADE's ``f = 1.22``. The split is
        :data:`NTANOS_STATE_COUNTS`, whose docstring records the arithmetic
        disagreement in the source sentence it comes from.

        A named constructor rather than a set of defaults on ``__init__``: asking
        for someone else's optimised configuration should look like asking for
        it.

        Returns
        -------
        Bb84DecoyProtocol
            Their parameter set.

        Examples
        --------
        >>> protocol = Bb84DecoyProtocol.ntanos_2021()
        >>> protocol.signal_intensity, protocol.decoy_intensity
        (0.56, 0.11)
        >>> round(protocol.signal_probability, 6)
        0.761905
        """
        signal, decoy, vacuum = NTANOS_STATE_COUNTS
        total = float(signal + decoy + vacuum)
        return cls(
            signal_intensity=NTANOS_SIGNAL_INTENSITY,
            decoy_intensity=NTANOS_DECOY_INTENSITY,
            signal_probability=signal / total,
            decoy_probability=decoy / total,
            vacuum_probability=vacuum / total,
            error_correction_efficiency=NTANOS_ERROR_CORRECTION_EFFICIENCY,
        )

    @property
    def protocol_efficiency(self) -> float:
        """``q``: the fraction of emitted pulses that can become sifted key bits.

        Ntanos et al. 2021 Eq. (A1), ``q = (1/2) N_s/(N_s + N_1 + N_2)``. Two
        losses, multiplied:

        * **one half**, because Alice and Bob choose their bases independently
          and keep only the pulses where the two happened to agree. This is
          symmetric BB84; the biased variant that pushes the factor towards one
          is deferred, for the reason in the module docstring.
        * **the signal fraction**, because the decoy and vacuum pulses are spent
          on measuring the channel. They buy the bound, not the key.

        In the asymptotic limit implemented here that second factor is the
        *only* place the decoy and vacuum probabilities appear: with an
        infinitely long block, the gains they measure are exact however few of
        them are sent, so they are pure cost. That is precisely the trade-off
        ``finite_key.py`` makes real, and a reason to read a rate from this
        module as the upper bound it is labelled.

        Returns
        -------
        float
            ``q``, in ``(0, 0.5)``.
        """
        return 0.5 * self.signal_probability

    def _key_rate(self, conditions: LinkConditions, *, degradations: DegradationLog) -> KeyRate:
        """Compute the asymptotic GLLP rate. Called by the checked public wrapper.

        The three steps, and the asymmetry that is the whole point:

        1. simulate what Alice and Bob would measure at each intensity;
        2. bound the single-photon part from those measurements;
        3. pay for it. **Privacy amplification is charged on the single-photon
           part only** — ``Q_1 [1 - h(e_1)]``, because a multi-photon pulse is
           assumed already known to Eve and cannot be made secret at any price —
           **while error correction is charged on everything**, ``Q_mu f
           h(E_mu)``, because Alice and Bob must reconcile every sifted bit they
           keep, including the ones they will end up throwing away.

        The difference of those two terms is Ma et al. 2005 Eq. (1), and it goes
        negative where the error correction costs more than the certified
        single-photon key is worth. Negative is clamped to zero, because a
        negative rate is not a small key but the absence of one, and
        :attr:`~quoss.qkd.base.KeyRate.has_key` is the field that says which.
        """
        signal = simulate_intensity(conditions, intensity=self.signal_intensity)
        decoy = simulate_intensity(conditions, intensity=self.decoy_intensity)
        bounds = single_photon_bounds(
            signal=signal,
            decoy=decoy,
            background_yield=conditions.background_yield,
            degradations=degradations,
        )

        q = self.protocol_efficiency
        privacy = bounds.single_photon_gain * (1.0 - binary_entropy(bounds.single_photon_qber))
        correction = signal.gain * self.error_correction_efficiency * binary_entropy(signal.qber)
        secure_per_pulse = np.maximum(q * (privacy - correction), 0.0)

        return KeyRate(
            protocol=self.name,
            regime=KeyRegime.ASYMPTOTIC,
            pulse_rate_hz=conditions.pulse_rate_hz,
            gain=signal.gain,
            qber=signal.qber,
            sifted_per_pulse=q * signal.gain,
            secure_per_pulse=secure_per_pulse,
        )


# Registered on import, which is the only way the name `bb84-decoy` resolves.
# `PROTOCOLS` is empty until a protocol module is imported, so anything resolving
# a name out of a scenario file has to import this module first. That is the
# scope rule of `quoss.qkd` rather than an oversight -- an absent name forces the
# question at the call site -- but it does mean `PROTOCOLS.resolve("bb84-decoy")`
# raises in a process that has never imported `quoss.qkd.bb84`.
PROTOCOLS.register(Bb84DecoyProtocol)
