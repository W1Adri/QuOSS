"""The finite-key bound: what a block of finite length actually yields.

What this module computes
-------------------------
:mod:`quoss.qkd.bb84` answers "what fraction of the pulses becomes key" as
though Alice and Bob had forever. This module answers the question a pass
actually poses: *they had eleven minutes and 6.6e10 pulses — how many bits of
key can they claim, and with what probability is the claim wrong?* In goes a
block of accumulated counts (:class:`DecoyBlockCounts`) and a pair of failure
probabilities (:class:`SecurityParameters`); out comes a number of **bits**
(:class:`FiniteKeyResult`), not a rate.

This is the block-level entry point :mod:`quoss.qkd.base` names and declines to
host: :meth:`~quoss.qkd.base.QkdProtocol.key_rate` maps instants to instants,
and a finite-key statement is about a *block*, which is an integral over a pass.
The integral itself is ``system/key_volume.py``, one stage later; what lives here
is the bound that integral feeds.

The vocabulary, assuming none of it
-----------------------------------
**Why "finite" changes anything.** Every number in the asymptotic rate is a
probability, and Alice and Bob never observe a probability. They observe a
count: 412 detections out of 3.7e8 pulses at the decoy intensity. A count
divided by a trial number is an *estimate* of the probability, and an estimate
can be unlucky. The decoy bound is built by subtracting one measured gain from
another, so a fluctuation of the wrong sign in either one makes the certified
single-photon yield too large — and a yield certified too large is a key that
Eve knows part of. The finite-key analysis replaces every measured count by the
worst value consistent with it at a stated confidence, and prices the difference.

**Composable security, and why the word matters.** A key is not "secure" or
"insecure"; it is ``epsilon``-secure, meaning it differs from an ideal uniform
key unknown to Eve by at most ``epsilon`` in a distance that behaves properly
under composition. *Composable* is the load-bearing word: it guarantees that
using the key inside another protocol — encrypting with it, authenticating with
it — degrades that protocol's security by at most ``epsilon`` too. A
non-composable bound can be perfectly true and still say nothing about the
system the key is used in. Lim et al.'s bound is composable, which is why it is
the one implemented; :class:`SecurityParameters` carries the two halves of it.

**The two halves.** ``epsilon_cor`` (correctness) is the probability that Alice
and Bob end up with *different* keys and do not notice. ``epsilon_sec``
(secrecy) is the probability that the key they share is not private. The
protocol is ``epsilon_cor + epsilon_sec``-secure. A typical experiment takes
both at 1e-10 or smaller; Lim et al.'s own evaluation uses 1e-15.

**Phase error, and why it is not the QBER.** Privacy amplification prices what
Eve knows, and what Eve knows is bounded by the error rate Alice and Bob *would
have seen* had they measured in the conjugate basis — the **phase** error rate.
They did not measure it, because those bits were used for key. So it has to be
inferred from the basis they did measure, and the inference is a random-sampling
argument with its own failure probability: that is the ``gamma`` term of
:func:`random_sampling_deviation`, and it is the price of not having measured
the thing being bounded.

The protocol this bound is for
------------------------------
Lim et al. 2014 analyse a specific protocol, and it is **not** the one
:mod:`quoss.qkd.bb84` implements. The differences are not cosmetic, so they are
listed before anything else:

======================  ===============================  ==========================
Feature                 ``bb84.py`` (asymptotic)         here (Lim et al. 2014)
======================  ===============================  ==========================
Basis choice            symmetric, ``q = 1/2``           biased, ``q_x`` free
Key comes from          signal pulses only               **all three intensities**
Error estimation        the same sifted bits             the **other** basis
Third intensity         exactly vacuum                   ``mu_3 >= 0``
Vacuum detections       worth nothing                    **counted as key**
Result                  a rate per pulse                 a **length** in bits
======================  ===============================  ==========================

The last two deserve a sentence each. Lim et al. credit the vacuum events
``s_0`` as key in full: a detection in a gate where Alice sent no photon is a
dark count, and a dark count carries no information about anything, so Eve knows
nothing about the bit Bob assigned to it. That is a real and slightly
counter-intuitive gain — noise that produces key — and it is why the bound stays
positive at losses where the asymptotic GLLP rate has already died. And a length
rather than a rate is not a presentation choice: ``6 log2(21/epsilon_sec)`` bits
are subtracted **once per block**, so the same link yields a different number of
bits per pulse depending on how long the block is.

Because the protocols differ, a finite-key result from this module is **not**
``bb84.py``'s rate times a correction factor, and the two are not comparable
term by term. What *is* comparable, and is checked in the tests, is the decoy
algebra underneath: with ``mu_3 = 0`` and the deviation terms switched off,
Lim et al.'s Eq. (3) is Ma et al.'s Eq. (34) written in counts instead of
probabilities. Two papers, two transcriptions, one number.

The five formulas
-----------------
Lim et al. state the whole bound in five equations, and this module is those
five equations with their guards. ``K = {mu_1, mu_2, mu_3}`` are the
intensities, ``p_k`` their probabilities, ``X`` the key basis and ``Z`` the
check basis, ``n_{X,k}`` the detections and ``m_{X,k}`` the bit errors::

    tau_n = sum_k e^(-mu_k) mu_k^n p_k / n!            probability Alice sends n photons

    n^pm_{X,k} = (e^mu_k / p_k) [n_{X,k} pm delta]     Hoeffding-corrected counts
    delta      = sqrt((n_X / 2) ln(21 / eps_sec))

    s_{X,0} >= tau_0 (mu_2 n^-_{X,mu_3} - mu_3 n^+_{X,mu_2}) / (mu_2 - mu_3)          (2)

    s_{X,1} >= tau_1 mu_1 [n^-_{X,mu_2} - n^+_{X,mu_3}
               - (mu_2^2 - mu_3^2)/mu_1^2 (n^+_{X,mu_1} - s_{X,0}/tau_0)]
               / (mu_1 (mu_2 - mu_3) - mu_2^2 + mu_3^2)                               (3)

    v_{Z,1} <= tau_1 (m^+_{Z,mu_2} - m^-_{Z,mu_3}) / (mu_2 - mu_3)                    (4)

    phi_X   <= v_{Z,1}/s_{Z,1} + gamma(eps_sec, v_{Z,1}/s_{Z,1}, s_{Z,1}, s_{X,1})    (5)

    l = floor[ s_{X,0} + s_{X,1} (1 - h(phi_X)) - leak_EC
               - 6 log2(21/eps_sec) - log2(2/eps_cor) ]                               (1)

Every ``21`` in there is one number: Lim et al.'s security analysis composes
**twenty-one** individual failure events (their supplementary Eq. (14):
``eps_sec = 2[2 alpha_1 + alpha_2 + alpha_3] + nu + 10 eps_1 + 2 eps_2``, with
every term set to a common ``eps``), so each single event is allowed
``eps_sec/21``. It is :data:`LIM_ERROR_TERM_COUNT`, spelled once.

Three things this module is shaped around
-----------------------------------------
**1. The deviation term is shared across intensities, and that is not a
rounding.** ``delta`` depends on the **total** ``n_X``, not on ``n_{X,k}``:
Hoeffding is applied to the assignment of the ``n_X`` detections among the three
intensities, which is a single random experiment. So the *rarest* intensity
carries the same absolute uncertainty as the commonest one, and after the
``1/p_k`` in ``n^pm`` it carries a far larger *relative* one. That is the
mechanism that makes decoy fractions a real trade-off instead of the pure cost
they are in :attr:`~quoss.qkd.bb84.Bb84DecoyProtocol.protocol_efficiency`, and
it is the reason this module exists rather than a correction factor.

**2. Where nothing is certified, the answer is zero bits and a logged reason.**
Eqs. (2), (3) and (4) are subtractions of noisy quantities and go negative when
the statistics are too thin, exactly as Ma et al.'s Eq. (34) does. A negative
number of events is not a small key: it is the absence of a certificate. Every
such branch clamps at zero, records a :class:`~quoss.core.errors.Degradation`
and produces ``length_bits = 0``, never a negative length and never a silent
substitution.

**3. A phase error rate of one half is the honest failure.** Where the sampling
argument certifies nothing, ``phi_X`` is set to ``1/2`` and not to zero, for the
reason :func:`~quoss.qkd.bb84.single_photon_bounds` sets ``e_1 = 1/2``:
``h(1/2) = 1``, the single-photon term vanishes, and the key falls back to the
vacuum events alone. Zero would draw a perfect channel where the analysis failed.

What this module does not do
----------------------------
**Choose parameters for you.** Lim et al. optimise ``{q_x, p_1, p_2, mu_1,
mu_2}`` numerically for every link, and the optimum moves with the block size —
that is their Fig. 1. Nothing here has a default, and nothing here optimises.
The search belongs to a sweep, which is ``engine/sweep.py``.

**Integrate over a pass.** :func:`expected_block_counts` turns link conditions
plus a pulse budget into counts, and :meth:`DecoyBlockCounts.pooled` adds them
up, but *how many pulses each sample stands for* is a question about a time
grid. That is ``system/key_volume.py``.

**Model detectors, sources or the sky.** The counts arrive already made. In an
experiment they are counted; in a simulation they come from
:func:`expected_block_counts`, which is the only function here that knows what a
transmittance is.

**Sample the counts.** :func:`expected_block_counts` returns **expectations**,
not draws from a multinomial. A simulated pass therefore prices the statistical
*estimation* penalty — which is what the bound is about — without also adding a
statistical *realisation*. Monte Carlo over realisations is
``system/monte_carlo.py``, and it is a different question: this one asks what a
typical block certifies, that one asks how the answer scatters.

=================================  ==========================================
Symbol                             Meaning
=================================  ==========================================
``eps_cor``, ``eps_sec``           correctness and secrecy failure
                                   probabilities (-)
``mu_1 > mu_2 + mu_3``             the three intensities (photons per pulse)
``p_k``                            probability of choosing intensity ``k`` (-)
``q_x``                            probability of choosing the key basis (-)
``n_X``, ``m_X``                   detections and bit errors, key basis
``n_Z``, ``m_Z``                   detections and bit errors, check basis
``tau_n``                          probability Alice sends ``n`` photons (-)
``s_{X,0}``, ``s_{X,1}``           certified vacuum and single-photon events
``v_{Z,1}``                        certified single-photon bit errors, check
``phi_X``                          certified phase error rate (-)
``leak_EC``                        bits revealed by error correction
``l``                              secret key length (bits)
=================================  ==========================================

References
----------
C. C. W. Lim, M. Curty, N. Walenta, F. Xu and H. Zbinden, "Concise security
bounds for practical decoy-state quantum key distribution", *Phys. Rev. A*
**89**, 022307, 2014 (preprint arXiv:1311.7129). Equations (1)-(5) of the main
text are the whole of this module; the supplementary material's Eqs. (1)-(14)
are the derivation, and its Eq. (14) is where the ``21`` comes from. Their
evaluation section fixes the parameter set reproduced in
``tests/qkd/test_finite_key.py``.

M. Tomamichel, C. C. W. Lim, N. Gisin and R. Renner, "Tight finite-key analysis
for quantum cryptography", *Nature Communications* **3**, 634, 2012, and
M. Tomamichel and R. Renner, *Phys. Rev. Lett.* **106**, 110506, 2011: the
entropic uncertainty relation Lim et al.'s secrecy analysis is built on.
``notes/ROADMAP.md`` named Tomamichel for this entry; the bound implemented is
Lim et al.'s because theirs is the one that covers **decoy states with weak
coherent pulses**, which is the protocol this project has. Tomamichel et al.'s
own protocol assumes a single-photon source, so applying it here would require
either a source QuOSS does not model or an extra tagging argument on top — and
their work is not bypassed by the choice: it is the proof technique underneath
Lim et al.'s Eq. (1).

C.-H. F. Fung, X. Ma and H. F. Chau, *Phys. Rev. A* **81**, 012318, 2010: the
random-sampling result behind Eq. (5), cited by Lim et al. as their Ref. [29].

X. Ma, B. Qi, Y. Zhao and H.-K. Lo, "Practical decoy state for quantum key
distribution", *Phys. Rev. A* **72**, 012326, 2005: the asymptotic decoy
analysis this one extends, implemented in :mod:`quoss.qkd.bb84`.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import factorial
from typing import Final

import numpy as np

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, FloatLike, frozen_view
from quoss.qkd.base import KeyRegime, LinkConditions, binary_entropy
from quoss.qkd.bb84 import VACUUM_ERROR_RATE, simulate_intensity

__all__ = [
    "LIM_CORRECTNESS",
    "LIM_ERROR_CORRECTION_EFFICIENCY",
    "LIM_ERROR_TERM_COUNT",
    "LIM_FIBER_ATTENUATION_DB_PER_KM",
    "LIM_KEY_LENGTH_PENALTY_TERMS",
    "LIM_MISALIGNMENT_ERROR",
    "LIM_SECURITY_CONSTANT",
    "LIM_WEAKEST_INTENSITY",
    "BasisCounts",
    "CertifiedEvents",
    "DecoyBlockCounts",
    "DecoySettings",
    "FiniteKeyResult",
    "SecurityParameters",
    "certified_events",
    "error_correction_leakage",
    "expected_block_counts",
    "hoeffding_deviation",
    "phase_error_rate",
    "random_sampling_deviation",
    "secret_key_length",
    "single_photon_errors",
]


LIM_ERROR_TERM_COUNT: Final[int] = 21
"""The ``21`` in every ``21/eps_sec`` of Lim et al. 2014. Dimensionless.

Their secrecy is composed of twenty-one individual failure events — supplementary
Eq. (14) reads ``eps_sec = 2[2 alpha_1 + alpha_2 + alpha_3] + nu + 10 eps_1 +
2 eps_2``, and the main text sets every term to a common ``eps``, giving
``eps_sec = 21 eps``. So each Hoeffding interval and each sampling argument is
run at confidence ``eps_sec/21``, and the penalty in Eq. (1) is
``6 log2(21/eps_sec)``.

Spelled once, as a name, because it appears in four formulas and a
transcription error in any one of them would move the key length by a few bits
per block — far too small to notice and exactly the wrong direction to be safe.
"""

LIM_KEY_LENGTH_PENALTY_TERMS: Final[int] = 6
"""The ``6`` multiplying ``log2(21/eps_sec)`` in Lim et al. 2014 Eq. (1).

Not the same number as :data:`LIM_ERROR_TERM_COUNT` and not derived from it.
It comes from their supplementary Eq. (13), where the key length carries
``-log2(2/(eps_cor beta))`` with ``beta = (alpha_2 alpha_3 nu)^2``: six factors
of ``eps`` inside a base-2 logarithm, hence six times ``log2(1/eps)``. At
``eps_sec = eps_cor = 1e-10`` the two penalties together are **260 bits**
(225.7 + 34.2) — negligible against a pass and decisive against a demonstration
block of a few hundred.
"""

LIM_SECURITY_CONSTANT: Final[float] = 1e-15
"""``kappa`` of Lim et al. 2014's evaluation: secrecy leakage per key bit.

Their Fig. 1 and Fig. 2 do not fix ``eps_sec``; they fix ``eps_sec = kappa l``,
so a longer key is allowed a proportionally larger absolute failure probability
and the *rate* of secrecy leakage is what stays constant. That makes the bound
implicit in its own answer — ``l`` appears on both sides — and the fixed point is
resolved by iteration in the tests rather than inside this module, because it is
a choice about how to report security and not part of the bound.
"""

LIM_CORRECTNESS: Final[float] = 1e-15
"""``eps_cor`` of Lim et al. 2014's evaluation. Dimensionless probability."""

LIM_MISALIGNMENT_ERROR: Final[float] = 5e-3
"""``e_mis`` of Lim et al. 2014's evaluation: 0.5 % optical error.

Half the 1 % this project's reference downlink inherits from Ntanos et al.'s
98 % interferometer visibility — a fibre system on a bench against a satellite
link through the atmosphere.
"""

LIM_ERROR_CORRECTION_EFFICIENCY: Final[float] = 1.16
"""``f_EC`` of Lim et al. 2014's evaluation. Dimensionless, ``>= 1``.

Lower than the 1.22 of CASCADE that Ntanos et al. assume, and the difference is
real: 1.16 is what modern LDPC codes achieve on this error range.
"""

LIM_WEAKEST_INTENSITY: Final[float] = 2e-4
"""``mu_3`` of Lim et al. 2014's evaluation, photons per pulse.

**Not zero**, and that is the point of the constant. Their analysis allows
``mu_3 >= 0``, and they still take 2e-4: an intensity modulator has a finite
extinction ratio, so the "vacuum" state of a real transmitter leaks a little
light. The formulas in this module never divide by ``mu_3``, so zero is legal
here; what the constant records is that the published evaluation did not use it.
"""

LIM_FIBER_ATTENUATION_DB_PER_KM: Final[float] = 0.2
"""Fibre attenuation of Lim et al. 2014's evaluation, dB/km.

Standard single-mode fibre at 1550 nm. Kept beside the other evaluation
parameters because the V2 test reproduces their Fig. 1, and a fibre link is the
only channel in this project that is not a satellite one.
"""

_NATS_PER_BIT: Final[float] = float(np.log(2.0))
"""``ln 2``, 0.693147. The ``log 2`` in the denominator of Lim et al.'s ``gamma``.

Their ``gamma`` mixes both logarithms in one expression — ``cd log 2`` is the
natural logarithm of two, ``log2(...)`` is a base-two logarithm — which is what
converts the entropic quantity underneath from nats to bits. Named rather than
written as ``np.log(2)`` inline so that the two never get swapped: reading that
``log 2`` as a base-two logarithm makes it ``1`` instead of ``0.693``, which
scales ``gamma`` by ``sqrt(ln 2) = 0.833`` — a **17 % underestimate** of the
sampling penalty, in the direction that flatters the key.
"""

_PROBABILITY_SUM_SLACK: Final[float] = 1e-9
"""Slack on the three intensity probabilities summing to one. See
:class:`DecoySettings`; the same tolerance and the same reasoning as
:class:`~quoss.qkd.bb84.Bb84DecoyProtocol`.
"""

_COUNT_ORDER_SLACK: Final[float] = 1e-9
"""Relative slack on ``errors <= detections`` and ``detections <= pulses``.

Not a tolerance on physics: both are counts of subsets of the same events, so a
violation beyond a part in a billion is an argument in the wrong slot, while the
last bit of it is what summing expectations in floating point does.
"""


def _range_of(value: FloatArray) -> str:
    """Format the range of an array for a message, surviving the empty case.

    Same helper and same reason as in :mod:`quoss.qkd.base`: an empty block is
    legal and ``np.min`` of an empty array raises, which would replace a message
    about one problem with a traceback about another.
    """
    if value.size == 0:
        return "empty"
    return f"{float(np.min(value)):.6g}, {float(np.max(value)):.6g}"


def _as_counts(value: FloatLike, *, name: str) -> FloatArray:
    """Validate one array of counts: finite and non-negative.

    Counts are floats rather than integers throughout this module. In an
    experiment they are integers; in a simulation they are **expectations**, and
    rounding an expectation of 0.4 detections to zero would quietly delete the
    whole low-elevation end of a pass. Every formula here is continuous in them.
    """
    counts = np.array(value, dtype=np.float64)
    if not np.all(np.isfinite(counts)):
        raise DomainError(f"{name} contains non-finite values.")
    if np.any(counts < 0.0):
        raise DomainError(
            f"{name} must be non-negative, got range [{_range_of(counts)}]. These are counts of "
            "events -- detections or errors -- accumulated over a block, not rates and not "
            "probabilities."
        )
    return counts


@dataclass(frozen=True, slots=True, kw_only=True)
class SecurityParameters:
    """How often the key is allowed to be wrong, and in which of the two ways.

    A finite-key statement is meaningless without these two numbers, which is
    why neither has a default. They are not tuning knobs: they are the claim.
    Halving them costs a handful of bits per block and is almost always the
    right trade, but *choosing* them is the experimenter's, since what is
    acceptable depends on what the key will be used for.

    Attributes
    ----------
    correctness : float
        ``eps_cor``: probability that Alice and Bob end up with different keys
        and the error-verification step does not catch it. In ``(0, 1)``.
    secrecy : float
        ``eps_sec``: probability that the key they do share is not private, in
        the composable sense — the trace distance from an ideal key, uniform and
        independent of everything Eve holds, exceeds this with probability at
        most this. In ``(0, 1)``.

    Raises
    ------
    DomainError
        If either value is not finite and strictly inside ``(0, 1)``. Zero is
        excluded because no protocol achieves it and the bound divides by it;
        one is excluded because a key that may always be insecure is not a key.

    Examples
    --------
    The pair a satellite experiment would quote, and what the two of them cost
    in bits before any statistics are even looked at:

    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> round(security.total, 12)
    2e-10
    >>> round(security.penalty_bits, 3)
    259.889

    Lim et al.'s own evaluation is far stricter, and costs 111 bits more:

    >>> strict = SecurityParameters(correctness=LIM_CORRECTNESS, secrecy=1e-15)
    >>> round(strict.penalty_bits - security.penalty_bits, 3)
    116.267

    The per-interval confidence is not ``eps_sec`` itself — it is that divided
    among the twenty-one failure events the proof composes:

    >>> f"{security.interval_confidence:.6e}"
    '4.761905e-12'
    """

    correctness: float
    secrecy: float

    def __post_init__(self) -> None:
        """Validate that both are probabilities a bound can be stated at."""
        for label in ("correctness", "secrecy"):
            value = float(getattr(self, label))
            if not np.isfinite(value) or not 0.0 < value < 1.0:
                raise DomainError(
                    f"{label} must be finite and in (0, 1), got {value}. It is a failure "
                    "probability: a typical experiment quotes 1e-10, and Lim et al. 2014 "
                    "evaluate at 1e-15. Zero is not achievable by any protocol and the bound "
                    "takes its logarithm; one is a key with no claim attached."
                )
            object.__setattr__(self, label, value)

    @property
    def total(self) -> float:
        """``eps_cor + eps_sec``: the protocol is secure to this.

        The two halves add, because a protocol fails if it is either incorrect
        or non-private, and a union bound is what composability licenses.
        """
        return self.correctness + self.secrecy

    @property
    def interval_confidence(self) -> float:
        """``eps_sec / 21``: the failure probability of a single interval.

        Each Hoeffding interval and the random-sampling argument are run at this
        confidence, so that the twenty-one of them compose to ``eps_sec``. See
        :data:`LIM_ERROR_TERM_COUNT`.
        """
        return self.secrecy / LIM_ERROR_TERM_COUNT

    @property
    def penalty_bits(self) -> float:
        """``6 log2(21/eps_sec) + log2(2/eps_cor)``: bits subtracted per block.

        The fixed cost of Lim et al. 2014 Eq. (1), independent of the link, the
        counts and the intensities. It is why a finite-key rate is a *length*
        divided by a pulse count and not a rate in its own right: a block ten
        times longer pays this once, not ten times.
        """
        secrecy = LIM_KEY_LENGTH_PENALTY_TERMS * float(np.log2(LIM_ERROR_TERM_COUNT / self.secrecy))
        correctness = float(np.log2(2.0 / self.correctness))
        return secrecy + correctness

    def __repr__(self) -> str:
        return (
            f"SecurityParameters(correctness={self.correctness:.3e}, "
            f"secrecy={self.secrecy:.3e}, penalty_bits={self.penalty_bits:.1f})"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecoySettings:
    """The three intensities Alice randomises over, and how often she sends each.

    Source configuration, not link behaviour — the same split as between
    :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` and
    :class:`~quoss.qkd.base.LinkConditions`. Frozen and validated, so every
    formula downstream may divide by ``mu_2 - mu_3`` without checking.

    The ordering constraint ``mu_1 > mu_2 + mu_3`` is **not** a convention. It is
    what makes Lim et al.'s step bounding the multi-photon tail valid: their
    supplementary derivation uses ``mu_2^n - mu_3^n <= (mu_2^2 - mu_3^2)
    mu_1^(n-2)`` for all ``n >= 2``, which needs ``mu_2 + mu_3 <= mu_1``.
    Violating it does not loosen the bound, it invalidates it — the resulting
    number is not a lower bound on anything.

    Attributes
    ----------
    signal_intensity : float
        ``mu_1``, mean photons per pulse of the strongest state.
    decoy_intensity : float
        ``mu_2``, the decoy. Strictly between ``mu_3`` and ``mu_1 - mu_3``.
    vacuum_intensity : float
        ``mu_3``, the weakest state. May be exactly zero — genuine vacuum — or
        the small residue a real intensity modulator leaks; Lim et al. evaluate
        at :data:`LIM_WEAKEST_INTENSITY`.
    signal_probability, decoy_probability, vacuum_probability : float
        ``p_1``, ``p_2``, ``p_3``: the fractions of pulses sent at each
        intensity. All strictly positive and summing to one.

    Raises
    ------
    DomainError
        If the intensities do not satisfy ``mu_1 > mu_2 + mu_3`` and
        ``mu_2 > mu_3 >= 0``, if any probability is outside ``(0, 1)``, or if
        the three do not sum to one.

    Examples
    --------
    The configuration this project's reference protocol uses — Ntanos et al.'s
    two intensities with genuine vacuum, split 16:1:4:

    >>> settings = DecoySettings(
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     vacuum_intensity=0.0,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ... )

    ``tau_n`` is the probability that a pulse — whichever intensity it was sent
    at — carried exactly ``n`` photons. The 4/21 of pulses sent as vacuum
    contribute 0.190 to ``tau_0`` outright; the rest of it is the two bright
    states coming up empty, which a mean of 0.56 photons does 57 % of the time:

    >>> round(settings.tau(0), 6)
    0.668342
    >>> round(settings.tau(1), 6)
    0.248408

    They are a probability distribution over photon number, so they sum to one
    over all ``n``, and the first two already account for 92 % of it:

    >>> round(sum(settings.tau(n) for n in range(30)), 12)
    1.0
    """

    signal_intensity: float
    decoy_intensity: float
    vacuum_intensity: float
    signal_probability: float
    decoy_probability: float
    vacuum_probability: float

    def __post_init__(self) -> None:
        """Validate the ordering the bound's derivation depends on."""
        names = ("signal_intensity", "decoy_intensity", "vacuum_intensity")
        intensities = []
        for label in names:
            value = float(getattr(self, label))
            if not np.isfinite(value) or value < 0.0:
                raise DomainError(
                    f"{label} must be finite and non-negative, got {value}. It is a mean photon "
                    "number per pulse."
                )
            object.__setattr__(self, label, value)
            intensities.append(value)
        mu_1, mu_2, mu_3 = intensities
        if not mu_2 > mu_3:
            raise DomainError(
                f"the intensities must satisfy decoy_intensity > vacuum_intensity, got "
                f"{mu_2} and {mu_3}. Lim et al. 2014 Eqs. (2) and (4) divide by "
                "mu_2 - mu_3, which is zero if the two are equal and negative if they are "
                "swapped -- and a bound with an inverted denominator is not a looser bound, it "
                "is an upper bound presented as a lower one."
            )
        if not mu_1 > mu_2 + mu_3:
            raise DomainError(
                f"the intensities must satisfy signal_intensity > decoy_intensity + "
                f"vacuum_intensity, got {mu_1} against {mu_2} + {mu_3} = {mu_2 + mu_3}. This is "
                "not a convention: Lim et al.'s supplementary derivation bounds the multi-photon "
                "tail with mu_2^n - mu_3^n <= (mu_2^2 - mu_3^2) mu_1^(n-2), which holds for all "
                "n >= 2 only when mu_2 + mu_3 <= mu_1. Outside it the formula still returns a "
                "number and that number certifies nothing."
            )

        probabilities = {
            "signal_probability": float(self.signal_probability),
            "decoy_probability": float(self.decoy_probability),
            "vacuum_probability": float(self.vacuum_probability),
        }
        for label, value in probabilities.items():
            if not np.isfinite(value) or not 0.0 < value < 1.0:
                raise DomainError(
                    f"{label} must be finite and in (0, 1), got {value}. All three intensities "
                    "are sent: a probability of zero is a two-state protocol, whose bound is a "
                    "different formula, and it would divide by zero in the 1/p_k of Lim et al.'s "
                    "corrected counts."
                )
            object.__setattr__(self, label, value)
        total = sum(probabilities.values())
        if abs(total - 1.0) > _PROBABILITY_SUM_SLACK:
            raise DomainError(
                "signal_probability, decoy_probability and vacuum_probability must sum to 1, got "
                f"{total}. They are the fractions of the emitted pulses sent at each intensity, "
                "and tau_n is a probability distribution built from them."
            )

    @property
    def intensities(self) -> tuple[float, float, float]:
        """``(mu_1, mu_2, mu_3)`` in the order every count triple uses."""
        return (self.signal_intensity, self.decoy_intensity, self.vacuum_intensity)

    @property
    def probabilities(self) -> tuple[float, float, float]:
        """``(p_1, p_2, p_3)``, matching :attr:`intensities` position by position."""
        return (self.signal_probability, self.decoy_probability, self.vacuum_probability)

    def tau(self, photons: int) -> float:
        """Return ``tau_n``: the probability that a pulse carried ``n`` photons.

        ``tau_n = sum_k e^(-mu_k) mu_k^n p_k / n!`` — the Poisson distribution of
        each intensity, averaged over the intensity Alice chose. Lim et al. 2014
        define it just after their Eq. (2).

        It is what converts between "events" and "events per pulse": the number
        of pulses in a block of ``N`` that carried exactly one photon is
        ``N tau_1``, whatever the channel then did to them. Eqs. (2), (3) and (4)
        are the only places it appears, and in each one it is the factor that
        turns a bound on a *rate* into a bound on a *count*.

        Parameters
        ----------
        photons : int
            ``n >= 0``. Only ``0`` and ``1`` are used by the bound; the rest
            exist so that a test can check the distribution sums to one.

        Returns
        -------
        float
            Probability in ``[0, 1]``.

        Raises
        ------
        DomainError
            If ``photons`` is negative.
        """
        if photons < 0:
            raise DomainError(
                f"photons must be non-negative, got {photons}. tau_n is a probability over "
                "photon number, and there is no such thing as a pulse of -1 photons."
            )
        terms = (
            np.exp(-mu) * mu**photons * p / factorial(photons)
            for mu, p in zip(self.intensities, self.probabilities, strict=True)
        )
        return float(sum(terms))


@dataclass(frozen=True, slots=True, kw_only=True)
class BasisCounts:
    """What one basis recorded: detections and bit errors, per intensity.

    The observables of the whole analysis. In an experiment these are six
    integers read off a counter after a run; in a simulation they come from
    :func:`expected_block_counts`. Nothing downstream looks at the channel
    again — the bound is a function of these numbers and the source settings.

    Six separate fields rather than two triples, and keyword-only, because the
    single most damaging mistake available here is silent: putting the decoy
    counts where the signal counts go produces a bound that is a perfectly
    ordinary positive number and certifies nothing. There is no arrangement of
    the arithmetic that catches it, so the names do the work.

    Attributes
    ----------
    signal_detections, decoy_detections, vacuum_detections : FloatArray
        Number of Bob's detections in this basis for pulses Alice sent at
        ``mu_1``, ``mu_2`` and ``mu_3`` — ``n_{X,k}`` in Lim et al.'s notation.
        Floats, not integers: a simulated block holds expectations, and rounding
        0.4 detections to zero deletes the low-elevation end of a pass.
    signal_errors, decoy_errors, vacuum_errors : FloatArray
        Number of those detections on which Alice's and Bob's bits disagree,
        ``m_{X,k}``. Each at most the matching detection count.

    Raises
    ------
    DomainError
        If any array is non-finite or negative, if an error count exceeds its
        detection count, or if the six do not broadcast to a common shape.

    Examples
    --------
    A block from one intensity triple, with a 1 % error rate on the two bright
    states and the coin flip that vacuum detections are:

    >>> counts = BasisCounts(
    ...     signal_detections=8.0e5,
    ...     decoy_detections=1.0e4,
    ...     vacuum_detections=2.0e2,
    ...     signal_errors=8.0e3,
    ...     decoy_errors=1.1e2,
    ...     vacuum_errors=1.0e2,
    ... )
    >>> float(counts.total_detections)
    810200.0
    >>> round(float(counts.observed_error_rate), 6)
    0.010133

    The error rate the key basis publishes is the one error correction is
    charged on, and it is *not* the phase error rate privacy amplification is
    charged on — see :func:`phase_error_rate` for the difference.

    Counts add over samples, which is what a pass is:

    >>> import numpy as np
    >>> a_pass = BasisCounts(
    ...     signal_detections=np.array([1.0e5, 8.0e5, 1.0e5]),
    ...     decoy_detections=np.array([1.2e3, 1.0e4, 1.2e3]),
    ...     vacuum_detections=np.array([2.0e2, 2.0e2, 2.0e2]),
    ...     signal_errors=np.array([2.0e3, 8.0e3, 2.0e3]),
    ...     decoy_errors=np.array([3.0e1, 1.1e2, 3.0e1]),
    ...     vacuum_errors=np.array([1.0e2, 1.0e2, 1.0e2]),
    ... )
    >>> a_pass.shape
    (3,)
    >>> block = a_pass.pooled()
    >>> block.shape, float(block.total_detections)
    ((), 1013000.0)
    """

    signal_detections: FloatArray
    decoy_detections: FloatArray
    vacuum_detections: FloatArray
    signal_errors: FloatArray
    decoy_errors: FloatArray
    vacuum_errors: FloatArray

    _FIELDS = (
        ("signal_detections", "signal_errors"),
        ("decoy_detections", "decoy_errors"),
        ("vacuum_detections", "vacuum_errors"),
    )

    def __post_init__(self) -> None:
        """Validate what every formula downstream is allowed to assume."""
        values = {}
        for detections_name, errors_name in self._FIELDS:
            for name in (detections_name, errors_name):
                values[name] = _as_counts(getattr(self, name), name=name)
        try:
            broadcast = np.broadcast_arrays(*values.values())
        except ValueError as exc:
            raise DomainError(
                "the six count arrays must broadcast to a common shape, got "
                f"{ {name: value.shape for name, value in values.items()} }. A trailing axis of "
                "length one against a full one silently makes an outer product rather than a "
                "block."
            ) from exc
        values = dict(zip(values.keys(), broadcast, strict=True))

        for detections_name, errors_name in self._FIELDS:
            detections, errors = values[detections_name], values[errors_name]
            if np.any(errors > detections * (1.0 + _COUNT_ORDER_SLACK)):
                raise DomainError(
                    f"{errors_name} exceeds {detections_name}: an error is a detection whose bit "
                    f"disagreed, so it is a subset. Ranges: errors [{_range_of(errors)}], "
                    f"detections [{_range_of(detections)}]. An error rate above one half is "
                    "legal here and happens at every vacuum state worth the name; an error "
                    "*count* above the detection count is two different quantities in one call."
                )
        for name, value in values.items():
            object.__setattr__(self, name, frozen_view(value))

    @property
    def detections(self) -> tuple[FloatArray, FloatArray, FloatArray]:
        """``(n_1, n_2, n_3)``, ordered as :attr:`DecoySettings.intensities`."""
        return (self.signal_detections, self.decoy_detections, self.vacuum_detections)

    @property
    def errors(self) -> tuple[FloatArray, FloatArray, FloatArray]:
        """``(m_1, m_2, m_3)``, ordered as :attr:`DecoySettings.intensities`."""
        return (self.signal_errors, self.decoy_errors, self.vacuum_errors)

    @property
    def total_detections(self) -> FloatArray:
        """``n_X``: detections summed over the three intensities."""
        total: FloatArray = self.signal_detections + self.decoy_detections + self.vacuum_detections
        return total

    @property
    def total_errors(self) -> FloatArray:
        """``m_X``: bit errors summed over the three intensities."""
        total: FloatArray = self.signal_errors + self.decoy_errors + self.vacuum_errors
        return total

    @property
    def observed_error_rate(self) -> FloatArray:
        """``m_X / n_X``: the error rate error correction is charged on.

        Zero where there were no detections at all. That is not an error rate of
        zero in any physical sense — it is the answer with no bits behind it,
        and the block it belongs to certifies no key anyway, so the value only
        has to be finite and harmless.
        """
        detections = self.total_detections
        safe = np.where(detections > 0.0, detections, 1.0)
        rate: FloatArray = np.where(detections > 0.0, self.total_errors / safe, 0.0)
        return rate

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the six arrays. ``()`` for a single block."""
        return self.signal_detections.shape

    def pooled(self, axis: int | tuple[int, ...] | None = None) -> BasisCounts:
        """Return the counts added up along ``axis``: many samples, one block.

        The operation that turns a per-instant simulation into the block a
        finite-key bound is about. It is a plain sum because counts are counts:
        the detections of a pass are the detections of its samples added.

        Parameters
        ----------
        axis : int or tuple of int or None
            Axis to sum over, as :func:`numpy.sum` takes it. ``None``, the
            default, sums everything and returns a single block.

        Returns
        -------
        BasisCounts
            Same six fields, summed.
        """
        summed = {
            name: np.sum(getattr(self, name), axis=axis) for pair in self._FIELDS for name in pair
        }
        return BasisCounts(**summed)

    def __repr__(self) -> str:
        return (
            f"BasisCounts(shape={self.shape}, "
            f"detections=[{_range_of(self.total_detections)}], "
            f"error_rate=[{_range_of(self.observed_error_rate)}])"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class DecoyBlockCounts:
    """Everything a block published: both bases, and how many pulses it took.

    The complete input to :func:`secret_key_length`, and the object
    ``system/key_volume.py`` will assemble from a pass.

    Attributes
    ----------
    key_basis : BasisCounts
        The basis the key is extracted from — ``X`` in Lim et al.'s notation.
        Its detections become key and its error rate is what error correction
        costs.
    check_basis : BasisCounts
        The basis kept for estimating what Eve knows — ``Z``. Its single-photon
        error rate is what privacy amplification is charged on, through
        :func:`phase_error_rate`. None of its bits become key.
    pulses : FloatArray
        ``N``: pulses Alice emitted for this block, including every pulse that
        was lost, sifted away or sent in the other basis. It appears nowhere in
        the bound itself and only in :attr:`FiniteKeyResult.key_per_pulse`,
        which is the quantity a rate plot shows.

    Raises
    ------
    DomainError
        If the two bases do not have the same shape, if ``pulses`` is negative
        or does not broadcast against them, or if the detections of the two
        bases together exceed the pulses that were sent.

    Examples
    --------
    >>> block = DecoyBlockCounts(
    ...     key_basis=BasisCounts(
    ...         signal_detections=8.0e5,
    ...         decoy_detections=1.0e4,
    ...         vacuum_detections=2.0e2,
    ...         signal_errors=8.0e3,
    ...         decoy_errors=1.1e2,
    ...         vacuum_errors=1.0e2,
    ...     ),
    ...     check_basis=BasisCounts(
    ...         signal_detections=9.0e4,
    ...         decoy_detections=1.1e3,
    ...         vacuum_detections=2.2e1,
    ...         signal_errors=9.0e2,
    ...         decoy_errors=1.2e1,
    ...         vacuum_errors=1.1e1,
    ...     ),
    ...     pulses=1.0e9,
    ... )
    >>> block.shape
    ()
    >>> float(block.key_basis.total_detections)
    810200.0

    Detections are a tiny fraction of the pulses, which is what a lossy link
    means — here 0.09 % of them survive into the key basis:

    >>> round(float(block.key_basis.total_detections / block.pulses) * 100, 4)
    0.081
    """

    key_basis: BasisCounts
    check_basis: BasisCounts
    pulses: FloatArray

    def __post_init__(self) -> None:
        """Validate that the two bases and the pulse budget describe one block."""
        for name in ("key_basis", "check_basis"):
            if not isinstance(getattr(self, name), BasisCounts):
                raise DomainError(
                    f"{name} must be a BasisCounts, got {type(getattr(self, name)).__name__}."
                )
        pulses = _as_counts(self.pulses, name="pulses")
        try:
            shape = np.broadcast_shapes(self.key_basis.shape, self.check_basis.shape, pulses.shape)
        except ValueError as exc:
            raise DomainError(
                f"key_basis {self.key_basis.shape}, check_basis {self.check_basis.shape} and "
                f"pulses {pulses.shape} must broadcast to a common shape."
            ) from exc
        if self.key_basis.shape != self.check_basis.shape:
            raise DomainError(
                f"key_basis and check_basis must have the same shape, got "
                f"{self.key_basis.shape} and {self.check_basis.shape}. The two are the same "
                "pulses sorted by basis, so a shape mismatch is two different runs in one "
                "object."
            )
        detected = self.key_basis.total_detections + self.check_basis.total_detections
        if np.any(detected > np.broadcast_to(pulses, shape) * (1.0 + _COUNT_ORDER_SLACK)):
            raise DomainError(
                f"the detections of the two bases together, [{_range_of(detected)}], exceed the "
                f"pulses sent, [{_range_of(pulses)}]. Every detection is a pulse that was sent, "
                "so pulses is the budget both bases are drawn from -- not the number of pulses "
                "in the key basis, and not the number of sifted bits."
            )
        object.__setattr__(self, "pulses", frozen_view(np.broadcast_to(pulses, shape).copy()))

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape. ``()`` for a single block."""
        return self.key_basis.shape

    def pooled(self, axis: int | tuple[int, ...] | None = None) -> DecoyBlockCounts:
        """Return the block obtained by adding up ``axis``: a pass, from samples.

        Parameters
        ----------
        axis : int or tuple of int or None
            Axis to sum over. ``None`` sums everything into one block.

        Returns
        -------
        DecoyBlockCounts
            Both bases and the pulse budget, summed.
        """
        return DecoyBlockCounts(
            key_basis=self.key_basis.pooled(axis),
            check_basis=self.check_basis.pooled(axis),
            pulses=np.asarray(np.sum(self.pulses, axis=axis), dtype=np.float64),
        )

    def __repr__(self) -> str:
        return (
            f"DecoyBlockCounts(shape={self.shape}, pulses=[{_range_of(self.pulses)}], "
            f"key_basis={self.key_basis!r}, check_basis={self.check_basis!r})"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class CertifiedEvents:
    """How many of a basis's detections are certified vacuum and single-photon.

    The output of Lim et al. 2014 Eqs. (2) and (3), and the finite-size analogue
    of :class:`~quoss.qkd.bb84.SinglePhotonBounds`: there the quantities are
    probabilities per pulse, here they are counts in a block, and the difference
    between the two is the whole subject of this module.

    Attributes
    ----------
    vacuum : FloatArray
        ``s_0``, lower bound: detections in gates where Alice sent no photon.
        Counted as key **in full** — a dark count tells Eve nothing about the
        bit Bob wrote down.
    single_photon : FloatArray
        ``s_1``, lower bound: detections from pulses that carried exactly one
        photon. The only detections privacy amplification can turn into secrecy.
    certified : BoolArray
        True where ``single_photon`` came out strictly positive. False is the
        honest answer for a block too thin to rule out that every single-photon
        pulse was blocked, not an error.

    Raises
    ------
    DomainError
        If any array is non-finite or negative, or if the three do not broadcast.
    """

    vacuum: FloatArray
    single_photon: FloatArray
    certified: BoolArray

    def __post_init__(self) -> None:
        """Validate that both counts are counts."""
        vacuum = _as_counts(self.vacuum, name="vacuum")
        single_photon = _as_counts(self.single_photon, name="single_photon")
        certified = np.array(self.certified, dtype=np.bool_)
        try:
            broadcast = np.broadcast_arrays(vacuum, single_photon, certified)
        except ValueError as exc:
            raise DomainError(
                f"vacuum {vacuum.shape}, single_photon {single_photon.shape} and certified "
                f"{certified.shape} must broadcast to a common shape."
            ) from exc
        object.__setattr__(self, "vacuum", frozen_view(np.asarray(broadcast[0], dtype=np.float64)))
        object.__setattr__(
            self, "single_photon", frozen_view(np.asarray(broadcast[1], dtype=np.float64))
        )
        frozen = np.asarray(broadcast[2], dtype=np.bool_).copy()
        frozen.flags.writeable = False
        object.__setattr__(self, "certified", frozen)

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the arrays."""
        return self.vacuum.shape

    def __repr__(self) -> str:
        certified = int(np.count_nonzero(self.certified))
        return (
            f"CertifiedEvents(shape={self.shape}, vacuum=[{_range_of(self.vacuum)}], "
            f"single_photon=[{_range_of(self.single_photon)}], "
            f"certified={certified}/{self.vacuum.size})"
        )


def hoeffding_deviation(sample_size: FloatLike, *, security: SecurityParameters) -> FloatArray:
    """Return ``delta``: how far a count may stray from its expectation.

    What it is
    ----------
    Alice sent ``n_X`` detected pulses spread over three intensities, and she
    chose each pulse's intensity at random. The number that ended up at
    intensity ``k`` is therefore a random variable, and the decoy analysis needs
    to know how far from its expectation it can be. Hoeffding's inequality
    answers that for any sum of bounded independent terms: the deviation exceeds
    ``delta = sqrt((n/2) ln(1/eps))`` with probability at most ``2 eps``.

    Lim et al. run every one of these intervals at ``eps = eps_sec/21``
    (:data:`LIM_ERROR_TERM_COUNT`), so ``delta = sqrt((n/2) ln(21/eps_sec))``,
    which is what this returns. It is their unnumbered display between Eqs. (2)
    and (3), and again between (4) and (5).

    Why one deviation for all three intensities
    -------------------------------------------
    ``delta`` depends on the **total** ``n_X``, not on the count at each
    intensity — the random experiment is the assignment of the whole block, and
    Hoeffding bounds it once. That has a consequence worth seeing before reading
    any result: after the ``1/p_k`` that converts a count to a per-pulse
    quantity, the same absolute ``delta`` becomes a *relative* uncertainty
    twenty times larger for an intensity sent 1/21 of the time than for one sent
    16/21 of the time. Sending fewer decoys costs nothing asymptotically and
    costs the square root of everything here.

    Why the square root, and what it means for a pass
    -------------------------------------------------
    ``delta`` grows like ``sqrt(n)`` while the counts themselves grow like
    ``n``, so the *relative* penalty falls like ``1/sqrt(n)``. Doubling a pass
    does not double the finite-key penalty, it multiplies it by 1.41 while
    doubling the key — which is the reason a longer block is always better and
    the reason the improvement saturates.

    Parameters
    ----------
    sample_size : float or FloatArray
        ``n``: the total number of events the interval is about — detections for
        Eqs. (2) and (3), bit errors for Eq. (4). Non-negative.
    security : SecurityParameters
        Supplies ``eps_sec``. Only :attr:`SecurityParameters.secrecy` is used.

    Returns
    -------
    FloatArray
        ``delta``, in events, of the shape of ``sample_size``.

    Raises
    ------
    DomainError
        If ``sample_size`` is negative or non-finite.

    Examples
    --------
    A block of a million detections, at a secrecy of 1e-10:

    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> round(float(hoeffding_deviation(1e6, security=security)), 3)
    3610.427

    Three and a half parts in a thousand of the block — and the same absolute
    figure applies to the 48 000 detections of an intensity sent 1/21 of the
    time, where it is 7.5 %:

    >>> round(float(hoeffding_deviation(1e6, security=security)) / (1e6 / 21) * 100, 2)
    7.58

    Four decades more detections shrink it by two decades, no more:

    >>> round(float(hoeffding_deviation(1e10, security=security)), 1)
    361042.7
    >>> round(float(hoeffding_deviation(1e10, security=security)) / 1e10 * 100, 5)
    0.00361

    Tightening the secrecy by five decades costs only 20 % more deviation — and
    that is not the same as costing 20 % of the key. On the reference block of
    ``tests/qkd/test_finite_key.py`` those same five decades cost **72 %** of
    it, because a deviation 20 % larger moves the phase error rate the whole
    length of the ``h`` curve. Cheap here, expensive there:

    >>> strict = SecurityParameters(correctness=1e-10, secrecy=1e-15)
    >>> round(
    ...     float(hoeffding_deviation(1e6, security=strict))
    ...     / float(hoeffding_deviation(1e6, security=security))
    ...     - 1,
    ...     4,
    ... )
    0.2007
    """
    events = _as_counts(sample_size, name="sample_size")
    deviation: FloatArray = np.sqrt(0.5 * events * np.log(LIM_ERROR_TERM_COUNT / security.secrecy))
    return deviation


def _corrected_counts(
    counts: FloatArray,
    deviation: FloatArray,
    *,
    intensity: float,
    probability: float,
    sign: float,
) -> FloatArray:
    """Return ``n^pm_k``: a count corrected for the statistics and the Poisson tail.

    ``(e^mu_k / p_k) (n_k +- delta)``, the unnumbered display of Lim et al. 2014
    between their Eqs. (2) and (3). Two separate corrections in one expression,
    and it is worth keeping them apart when reading a number:

    * ``1/p_k`` turns "detections among the pulses sent at this intensity" into
      "detections per pulse sent at any intensity", so that the three
      intensities can be compared;
    * ``e^mu_k`` removes the Poisson weighting, because the yields ``Y_n`` the
      decoy method solves for are properties of the channel and not of how often
      Alice chose to illuminate it.

    ``sign`` is ``+1`` for the upper end of the interval and ``-1`` for the
    lower. The result may be negative at the lower end when the block is smaller
    than its own deviation; it is **not** clamped here, because the published
    formula is not, and every place it feeds into clamps its own output.
    """
    corrected: FloatArray = np.exp(intensity) / probability * (counts + sign * deviation)
    return corrected


def certified_events(
    counts: BasisCounts,
    *,
    settings: DecoySettings,
    security: SecurityParameters,
    degradations: DegradationLog,
) -> CertifiedEvents:
    """Bound the vacuum and single-photon detections of one basis, from below.

    What it is
    ----------
    Lim et al. 2014 Eqs. (2) and (3). Bob announced how many times he clicked
    for each of Alice's three intensities; this returns how many of those clicks
    are *certifiably* from pulses that carried no photon and from pulses that
    carried exactly one. Both are lower bounds, because a lower bound is what a
    security proof can spend: claiming fewer single-photon events than there
    really were wastes key, claiming more gives it away.

    Why this is Ma et al.'s bound with statistics in it
    ---------------------------------------------------
    Set ``mu_3 = 0`` and let the block grow until ``delta`` is negligible, and
    Eq. (3) becomes, term for term, the ``Y_1`` bound of Ma et al. 2005 Eq. (34)
    that :func:`~quoss.qkd.bb84.single_photon_bounds` implements — with counts
    where that has probabilities. Everything that separates the two modules is
    therefore ``delta``, and the tests check the identity rather than describing
    it.

    The subtlety in Eq. (3): why clamping ``s_0`` first is safe
    -----------------------------------------------------------
    Eq. (3) contains ``+ (mu_2^2 - mu_3^2)/mu_1^2 * s_0/tau_0``, so a larger
    ``s_0`` gives a **larger** ``s_1``, and a reader checking for conservatism
    will stop here: clamping a negative ``s_0`` up to zero makes the
    single-photon bound bigger, and bigger is the unsafe direction.

    It is safe, and the reason is worth stating because it is not obvious.
    Eq. (3) is derived with the *true* number of vacuum events in that slot, and
    it is monotone increasing in it. So substituting any valid lower bound on
    the true ``s_0`` yields a valid lower bound on ``s_1``. Zero is a valid
    lower bound on a count of events — that is what a count is — and it is a
    *tighter* one than a negative number. Clamping therefore keeps the guarantee
    and improves the result, which is the opposite of the usual trade.

    Parameters
    ----------
    counts : BasisCounts
        Detections per intensity in one basis. The error counts are not used.
    settings : DecoySettings
        The three intensities and their probabilities.
    security : SecurityParameters
        Supplies ``eps_sec`` for the Hoeffding intervals.
    degradations : DegradationLog
        Receives a record wherever a bound had to be clamped at zero. Required,
        not optional: a log that can be omitted is one that will be.

    Returns
    -------
    CertifiedEvents
        ``s_0``, ``s_1`` and the mask of where ``s_1`` is positive.

    Examples
    --------
    Take a block of 1e10 pulses on this project's reference downlink at zenith
    and split it the way Ntanos et al. split their intensities. Just under a
    third of the 1.51e6 detections are certified single-photon events:

    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> from quoss.core.errors import DegradationLog
    >>> conditions = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> settings = DecoySettings(
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     vacuum_intensity=0.0,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ... )
    >>> block = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e10
    ... )
    >>> log = DegradationLog()
    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> events = certified_events(
    ...     block.key_basis, settings=settings, security=security, degradations=log
    ... )
    >>> round(float(events.single_photon))
    476496
    >>> round(float(events.single_photon / block.key_basis.total_detections), 4)
    0.3151

    And the certified vacuum count is **zero**, on a night link that produces
    375 vacuum detections. That is not a defect: the Hoeffding deviation of this
    block is 4440 detections, so 375 is far inside the noise of the assignment
    and nothing about them is certified. Eq. (2) goes negative, is clamped, and
    logs it — the free key from dark counts is a daylight effect, not a
    night-time one.

    >>> float(events.vacuum), log.entries[0].code
    (0.0, 'finite-key.vacuum-events-uncertified')

    Shrink the same link to a block of 1e6 pulses and the statistics no longer
    rule anything out: the bound goes negative, is clamped, and says so.

    >>> small = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e6
    ... )
    >>> log = DegradationLog()
    >>> events = certified_events(
    ...     small.key_basis, settings=settings, security=security, degradations=log
    ... )
    >>> bool(events.certified), float(events.single_photon)
    (False, 0.0)
    >>> [entry.code for entry in log.entries]
    ['finite-key.vacuum-events-uncertified', 'finite-key.single-photon-events-uncertified']
    """
    mu_1, mu_2, mu_3 = settings.intensities
    tau_0 = settings.tau(0)
    tau_1 = settings.tau(1)

    detections = counts.detections
    deviation = hoeffding_deviation(counts.total_detections, security=security)
    upper = tuple(
        _corrected_counts(n, deviation, intensity=mu, probability=p, sign=+1.0)
        for n, mu, p in zip(detections, settings.intensities, settings.probabilities, strict=True)
    )
    lower = tuple(
        _corrected_counts(n, deviation, intensity=mu, probability=p, sign=-1.0)
        for n, mu, p in zip(detections, settings.intensities, settings.probabilities, strict=True)
    )

    # Lim et al. 2014 Eq. (2), in their spelling: the vacuum yield read off the
    # two weakest intensities. `mu_2 - mu_3` is positive by DecoySettings.
    raw_vacuum = tau_0 * (mu_2 * lower[2] - mu_3 * upper[1]) / (mu_2 - mu_3)
    vacuum = np.maximum(raw_vacuum, 0.0)

    # Lim et al. 2014 Eq. (3). The denominator is positive whenever
    # mu_1 > mu_2 + mu_3, which DecoySettings requires; `vacuum` is the clamped
    # bound above, for the reason in the docstring.
    denominator = mu_1 * (mu_2 - mu_3) - mu_2**2 + mu_3**2
    bracket = lower[1] - upper[2] - (mu_2**2 - mu_3**2) / mu_1**2 * (upper[0] - vacuum / tau_0)
    raw_single = tau_1 * mu_1 * bracket / denominator
    single_photon = np.maximum(raw_single, 0.0)
    certified = raw_single > 0.0

    clamped_vacuum = int(np.count_nonzero(raw_vacuum < 0.0))
    if clamped_vacuum:
        degradations.warn(
            "finite-key.vacuum-events-uncertified",
            f"The vacuum bound of Lim et al. 2014 Eq. (2) is negative at {clamped_vacuum} of "
            f"{np.asarray(raw_vacuum).size} blocks and has been clamped to zero. The Hoeffding "
            "deviation is larger than the detection counts it is subtracted from, so the block "
            "is consistent with none of the detections being vacuum events; zero is a valid "
            "lower bound on a count, and the single-photon bound is computed from the clamped "
            "value, which keeps its guarantee and tightens it.",
            where="quoss.qkd.finite_key.certified_events",
            clamped_blocks=clamped_vacuum,
            total_blocks=int(np.asarray(raw_vacuum).size),
        )
    uncertified = int(np.count_nonzero(~certified))
    if uncertified:
        degradations.warn(
            "finite-key.single-photon-events-uncertified",
            f"The single-photon bound of Lim et al. 2014 Eq. (3) is non-positive at "
            f"{uncertified} of {certified.size} blocks: with this block size the statistics do "
            "not rule out that every single-photon pulse was blocked, so nothing is certified "
            "and the secret key length is zero. This is a statement about the block, not about "
            "the link -- the same link with more pulses may certify a key. Read "
            "CertifiedEvents.certified for which blocks.",
            where="quoss.qkd.finite_key.certified_events",
            uncertified_blocks=uncertified,
            total_blocks=int(certified.size),
            secrecy=security.secrecy,
        )

    return CertifiedEvents(vacuum=vacuum, single_photon=single_photon, certified=certified)


def single_photon_errors(
    counts: BasisCounts,
    *,
    settings: DecoySettings,
    security: SecurityParameters,
    degradations: DegradationLog,
) -> FloatArray:
    """Bound from above the bit errors that came from single-photon pulses.

    What it is
    ----------
    Lim et al. 2014 Eq. (4), ``v_1 <= tau_1 (m^+_2 - m^-_3)/(mu_2 - mu_3)``. Of
    the errors Bob recorded in this basis, how many can have come from pulses
    carrying exactly one photon? Upper bound, because this number is a cost: it
    is what privacy amplification will be charged for.

    The shape is the same subtraction as Eq. (2) — the two weakest intensities
    against each other — and for the same reason. A one-photon pulse is
    ``mu`` times more likely at intensity ``mu`` than at zero intensity to
    leading order, so the *difference* between two error counts, each weighted
    by ``e^mu/p``, isolates the single-photon contribution and cancels the
    vacuum one. Applied to the check basis, this is the numerator of
    :func:`~quoss.qkd.bb84.single_photon_bounds`'s Eq. (37) with counts in place
    of probabilities.

    Note which counts feed it: the **errors**, and their own Hoeffding deviation
    built from the total error count ``m_Z``, not from the detection count. A
    block with a million detections and forty errors has a deviation set by the
    forty.

    Parameters
    ----------
    counts : BasisCounts
        Counts of the basis the phase error is estimated from — the check basis
        in Lim et al.'s protocol. Only the error counts are used.
    settings : DecoySettings
        The three intensities and their probabilities.
    security : SecurityParameters
        Supplies ``eps_sec``.
    degradations : DegradationLog
        Receives a record where the bound is clamped at zero.

    Returns
    -------
    FloatArray
        ``v_1``, in events, of the counts' shape. Non-negative.

    Examples
    --------
    The reference downlink again, a block of 1e10 pulses, the check basis of a
    symmetric protocol. The bound comes out at 39 630 single-photon errors — out
    of 16 088 errors of every kind that the basis actually recorded:

    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> from quoss.core.errors import DegradationLog
    >>> conditions = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> settings = DecoySettings(
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     vacuum_intensity=0.0,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ... )
    >>> block = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e10
    ... )
    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> log = DegradationLog()
    >>> errors = single_photon_errors(
    ...     block.check_basis, settings=settings, security=security, degradations=log
    ... )
    >>> round(float(errors))
    39630
    >>> round(float(block.check_basis.total_errors))
    16088

    An upper bound above the total is still an upper bound, and it is what this
    configuration deserves: the decoy state gets 1/21 of the pulses, so it
    recorded 230 errors, while the deviation shared across the three intensities
    is 458. The estimate is dominated by its own uncertainty, and the ``1/p_2``
    that converts it to a per-pulse quantity multiplies that uncertainty by 21.
    A block that spends more of its pulses on decoys buys a tighter number here,
    which is the trade-off the asymptotic module cannot see —
    :attr:`~quoss.qkd.bb84.Bb84DecoyProtocol.protocol_efficiency` counts decoy
    pulses as pure cost.
    """
    mu_2, mu_3 = settings.decoy_intensity, settings.vacuum_intensity
    p_2, p_3 = settings.decoy_probability, settings.vacuum_probability
    tau_1 = settings.tau(1)

    deviation = hoeffding_deviation(counts.total_errors, security=security)
    upper_decoy = _corrected_counts(
        counts.decoy_errors, deviation, intensity=mu_2, probability=p_2, sign=+1.0
    )
    lower_vacuum = _corrected_counts(
        counts.vacuum_errors, deviation, intensity=mu_3, probability=p_3, sign=-1.0
    )
    raw = tau_1 * (upper_decoy - lower_vacuum) / (mu_2 - mu_3)
    bounded: FloatArray = np.maximum(raw, 0.0)

    clamped = int(np.count_nonzero(raw < 0.0))
    if clamped:
        degradations.warn(
            "finite-key.single-photon-errors-clamped",
            f"The single-photon error bound of Lim et al. 2014 Eq. (4) is negative at {clamped} "
            f"of {np.asarray(raw).size} blocks and has been clamped to zero. The difference of "
            "the two weakest intensities' error counts came out below their Hoeffding "
            "deviation, which says the data are consistent with no single-photon errors at all. "
            "Zero is the tightest value an upper bound on a count of events may take.",
            where="quoss.qkd.finite_key.single_photon_errors",
            clamped_blocks=clamped,
            total_blocks=int(np.asarray(raw).size),
        )
    return bounded


def random_sampling_deviation(
    *,
    error_rate: FloatLike,
    check_events: FloatLike,
    key_events: FloatLike,
    security: SecurityParameters,
    degradations: DegradationLog,
) -> FloatArray:
    """Return ``gamma``: the price of not having measured the phase error rate.

    What it is
    ----------
    The correction term of Lim et al. 2014 Eq. (5), from Fung, Ma and Chau 2010
    (their Ref. [29])::

        gamma(a, b, c, d) = sqrt( (c+d)(1-b)b / (c d ln2)
                                  * log2( (c+d)/(c d (1-b) b) * (21/a)^2 ) )

    with ``a = eps_sec``, ``b`` the error rate measured in the check basis,
    ``c`` the single-photon events *in* the check basis and ``d`` the
    single-photon events in the key basis.

    Why it has to exist
    -------------------
    Privacy amplification is priced on the **phase** error rate of the key
    basis: how often Alice and Bob would have disagreed had they measured those
    same single photons in the conjugate basis. They did not, because those
    bits became key. So the rate has to be transferred from the bits they did
    sacrifice, and the transfer is a sampling argument: ``c`` observed items and
    ``d`` unobserved ones, drawn from one pool without replacement. ``gamma`` is
    how far the unobserved half may sit above the observed half at confidence
    ``eps_sec/21``.

    Reading the formula
    -------------------
    Three behaviours are worth having in mind before looking at a number:

    * it falls like ``1/sqrt(c)`` when the check basis is the small one, which
      is the usual case — measuring more check bits is the direct way to buy a
      tighter phase error rate, and it is what a basis bias ``q_x`` trades
      against;
    * it vanishes as ``b -> 0``: the prefactor carries a factor ``b``, and
      ``b log2(1/b) -> 0``. A channel with no errors has no phase error either,
      and there is nothing left to sample;
    * it is symmetric in swapping ``c`` and ``d`` only through ``c+d``, so an
      enormous key basis does *not* make up for a thin check basis.

    Parameters
    ----------
    error_rate : float or FloatArray
        ``b``: the single-photon error rate of the check basis, ``v_1/s_{Z,1}``.
        In ``[0, 1]``. At exactly zero or one the formula's limit, zero, is
        returned rather than a ``0 * inf``.
    check_events : float or FloatArray
        ``c``: certified single-photon events in the check basis. Strictly
        positive.
    key_events : float or FloatArray
        ``d``: certified single-photon events in the key basis. Strictly
        positive.
    security : SecurityParameters
        Supplies ``eps_sec``.
    degradations : DegradationLog
        Receives a record if the logarithm's argument falls below one, where the
        published expression has no real value.

    Returns
    -------
    FloatArray
        ``gamma``, a deviation in error rate (dimensionless), non-negative.

    Raises
    ------
    DomainError
        If ``error_rate`` is outside ``[0, 1]``, or if either event count is not
        strictly positive. Zero events is not a small sample, it is no sample:
        the caller decides what to do about it, and :func:`phase_error_rate`
        does so by declaring the phase error rate unconstrained.

    Examples
    --------
    A pass-sized block with a 1 % single-photon error rate in the check basis,
    and about four hundred thousand certified single-photon events on each side:

    >>> from quoss.core.errors import DegradationLog
    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> log = DegradationLog()
    >>> round(
    ...     float(
    ...         random_sampling_deviation(
    ...             error_rate=0.01,
    ...             check_events=4.2e5,
    ...             key_events=4.2e5,
    ...             security=security,
    ...             degradations=log,
    ...         )
    ...     ),
    ...     6,
    ... )
    0.00209

    A fifth of the measured error rate, added on top of it. Shrink the check
    basis a hundredfold and the penalty grows by 7.4 — short of the tenfold of
    ``1/sqrt(c)``, because ``c + d`` barely moves when ``d`` is the large one:

    >>> round(
    ...     float(
    ...         random_sampling_deviation(
    ...             error_rate=0.01,
    ...             check_events=4.2e3,
    ...             key_events=4.2e5,
    ...             security=security,
    ...             degradations=log,
    ...         )
    ...     ),
    ...     6,
    ... )
    0.01549

    And a channel with no errors pays nothing, which is the limit rather than a
    special case:

    >>> float(
    ...     random_sampling_deviation(
    ...         error_rate=0.0,
    ...         check_events=4.2e5,
    ...         key_events=4.2e5,
    ...         security=security,
    ...         degradations=log,
    ...     )
    ... )
    0.0
    """
    b = np.asarray(error_rate, dtype=np.float64)
    c = np.asarray(check_events, dtype=np.float64)
    d = np.asarray(key_events, dtype=np.float64)
    if not np.all(np.isfinite(b)) or np.any(b < 0.0) or np.any(b > 1.0):
        raise DomainError(
            f"error_rate must be finite and in [0, 1], got range [{_range_of(b)}]. It is the "
            "single-photon error rate of the check basis, a fraction."
        )
    for name, value in (("check_events", c), ("key_events", d)):
        if not np.all(np.isfinite(value)) or np.any(value <= 0.0):
            raise DomainError(
                f"{name} must be finite and strictly positive, got range [{_range_of(value)}]. "
                "The sampling argument divides by both counts; zero certified events is not a "
                "small sample but no sample, and the phase error rate is then unconstrained "
                "rather than large."
            )

    # `np.where` evaluates both branches and this project runs with
    # filterwarnings = ["error"], so the degenerate endpoints are substituted
    # *before* the arithmetic rather than masked after it.
    interior = (b > 0.0) & (b < 1.0)
    safe_b = np.where(interior, b, 0.5)
    variance = (c + d) * (1.0 - safe_b) * safe_b / (c * d * _NATS_PER_BIT)
    argument = (
        (c + d) / (c * d * (1.0 - safe_b) * safe_b) * (LIM_ERROR_TERM_COUNT / security.secrecy) ** 2
    )
    degenerate = argument < 1.0
    logarithm = np.log2(np.maximum(argument, 1.0))
    gamma: FloatArray = np.where(interior, np.sqrt(variance * logarithm), 0.0)

    below_one = int(np.count_nonzero(degenerate & interior))
    if below_one:
        degradations.warn(
            "finite-key.sampling-argument-degenerate",
            f"The logarithm in the random-sampling term of Lim et al. 2014 Eq. (5) has an "
            f"argument below one at {below_one} of {np.asarray(argument).size} blocks, where "
            "the published expression has no real value, and gamma has been set to zero there. "
            "That happens only when the certified single-photon counts are enormous against the "
            "confidence demanded: with equal counts in the two bases and an error rate of one "
            "half it takes 8 (21/eps_sec)^2 events, which is 3.5e23 at a secrecy of 1e-10 and "
            "1.4e4 at a secrecy of 0.5. Zero is the limit being approached there, not a "
            "substitution for a missing model.",
            where="quoss.qkd.finite_key.random_sampling_deviation",
            degenerate_blocks=below_one,
            total_blocks=int(np.asarray(argument).size),
        )
    return gamma


def phase_error_rate(
    *,
    certified_errors: FloatLike,
    check_events: FloatLike,
    key_events: FloatLike,
    security: SecurityParameters,
    degradations: DegradationLog,
) -> FloatArray:
    """Return ``phi_X``: the error rate privacy amplification is charged on.

    What it is
    ----------
    Lim et al. 2014 Eq. (5): the single-photon error rate measured in the check
    basis, plus the sampling penalty of :func:`random_sampling_deviation` for
    transferring it to the key basis, capped at one half.

    Why it is not the QBER
    ----------------------
    The QBER — :attr:`BasisCounts.observed_error_rate` — is what Alice and Bob
    disagree on, and it prices *error correction*. The phase error rate is what
    they would have disagreed on in the conjugate basis, and it prices *privacy
    amplification*, because the uncertainty relation that underlies the proof
    says an eavesdropper's information about the key bits is bounded by the
    disturbance visible in the conjugate ones. Two different numbers, two
    different terms of Eq. (1), and confusing them is a full-strength security
    error in both directions: charging privacy amplification on the QBER would
    understate the cost on a link whose check statistics are thin, and charging
    error correction on the phase error rate would overstate it everywhere.

    The cap at one half, and why it is not zero
    -------------------------------------------
    ``h(1/2) = 1``, so a phase error rate of one half makes the single-photon
    term of Eq. (1) vanish exactly: the certified single photons produce no key
    and the block falls back to its vacuum events. That is the correct answer
    for "nothing is known about the phase errors", and it is why one half rather
    than zero is what this returns where the estimate fails —
    :func:`~quoss.qkd.bb84.single_photon_bounds` makes the same choice for the
    same reason.

    Parameters
    ----------
    certified_errors : float or FloatArray
        ``v_1``: the upper bound on single-photon bit errors in the check basis,
        from :func:`single_photon_errors`.
    check_events : float or FloatArray
        ``s_{Z,1}``: certified single-photon events in the check basis. Zero or
        negative means the estimate has no sample and the result is one half.
    key_events : float or FloatArray
        ``s_{X,1}``: certified single-photon events in the key basis. Same
        treatment.
    security : SecurityParameters
        Supplies ``eps_sec``.
    degradations : DegradationLog
        Receives a record wherever the rate had to be set to one half.

    Returns
    -------
    FloatArray
        ``phi_X`` in ``[0, 1/2]``, of the broadcast shape of the inputs.

    Examples
    --------
    The reference downlink's block from :func:`single_photon_errors`, with about
    420 000 certified single-photon events in each basis:

    >>> from quoss.core.errors import DegradationLog
    >>> security = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> log = DegradationLog()
    >>> phi = phase_error_rate(
    ...     certified_errors=3.963e4,
    ...     check_events=4.765e5,
    ...     key_events=4.765e5,
    ...     security=security,
    ...     degradations=log,
    ... )
    >>> round(float(phi), 6)
    0.088479

    Eight and a half per cent, against a key-basis QBER of 1.06 % on the same
    block: the finite-size analysis of a link whose optics are 1 % accurate
    charges privacy amplification at eight times that rate. Almost all of the
    gap is in ``v_1`` — see :func:`single_photon_errors`, which bounds 39 630
    single-photon errors where the basis recorded 16 088 of every kind — and
    only 0.0053 of it is the sampling term added here.

    Where nothing is certified, the answer is the coin flip and the log says so
    rather than the result quietly reading as a perfect channel:

    >>> log = DegradationLog()
    >>> float(
    ...     phase_error_rate(
    ...         certified_errors=0.0,
    ...         check_events=0.0,
    ...         key_events=4.2e5,
    ...         security=security,
    ...         degradations=log,
    ...     )
    ... )
    0.5
    >>> log.entries[0].code
    'finite-key.phase-error-unconstrained'
    """
    v = np.asarray(certified_errors, dtype=np.float64)
    c = np.asarray(check_events, dtype=np.float64)
    d = np.asarray(key_events, dtype=np.float64)
    for name, value in (
        ("certified_errors", v),
        ("check_events", c),
        ("key_events", d),
    ):
        if not np.all(np.isfinite(value)):
            raise DomainError(f"{name} contains non-finite values.")
    if np.any(v < 0.0):
        raise DomainError(
            f"certified_errors must be non-negative, got range [{_range_of(v)}]. It is a bound "
            "on a count of errors, already clamped by single_photon_errors."
        )

    usable = (c > 0.0) & (d > 0.0)
    safe_c = np.where(usable, c, 1.0)
    safe_d = np.where(usable, d, 1.0)
    ratio = np.minimum(np.where(usable, v / safe_c, VACUUM_ERROR_RATE), 1.0)
    gamma = random_sampling_deviation(
        error_rate=ratio,
        check_events=safe_c,
        key_events=safe_d,
        security=security,
        degradations=degradations,
    )
    rate: FloatArray = np.where(
        usable, np.minimum(ratio + gamma, VACUUM_ERROR_RATE), VACUUM_ERROR_RATE
    )

    unconstrained = int(np.count_nonzero(~usable))
    if unconstrained:
        degradations.warn(
            "finite-key.phase-error-unconstrained",
            f"No single-photon events are certified in one of the two bases at {unconstrained} "
            f"of {np.asarray(usable).size} blocks, so the sampling argument of Lim et al. 2014 "
            f"Eq. (5) has nothing to sample and the phase error rate is set to "
            f"{VACUUM_ERROR_RATE}. That is the value carrying no information -- h(1/2) = 1, so "
            "the single-photon term of Eq. (1) vanishes and only the vacuum events remain -- "
            "and not a zero error rate, which would price a perfect channel exactly where the "
            "estimate failed.",
            where="quoss.qkd.finite_key.phase_error_rate",
            unconstrained_blocks=unconstrained,
            total_blocks=int(np.asarray(usable).size),
        )
    capped = int(np.count_nonzero(usable & (ratio + gamma > VACUUM_ERROR_RATE)))
    if capped:
        degradations.warn(
            "finite-key.phase-error-capped",
            f"The phase error rate of Lim et al. 2014 Eq. (5) exceeds one half at {capped} of "
            f"{np.asarray(usable).size} blocks and has been capped there. Above one half the "
            "bound carries no information -- h > 1 would make the single-photon term negative, "
            "which is privacy amplification removing more than the key it is applied to -- and "
            "at exactly one half that term is zero, which is what an unconstrained phase error "
            "rate is worth.",
            where="quoss.qkd.finite_key.phase_error_rate",
            capped_blocks=capped,
            total_blocks=int(np.asarray(usable).size),
        )
    return rate


def error_correction_leakage(
    *,
    block_size: FloatLike,
    observed_error_rate: FloatLike,
    efficiency: float,
) -> FloatArray:
    """Return ``leak_EC``: bits revealed while correcting the errors.

    What it is
    ----------
    ``leak_EC = f_EC * n_X * h(E)``. Alice and Bob hold two strings that differ
    in a fraction ``E`` of their positions; reconciling them costs public
    discussion, and everything said publicly is heard by Eve, so it comes off
    the key one bit for one bit. Shannon's limit for that discussion is ``h(E)``
    bits per sifted bit, and a real code exceeds it by ``f_EC``: 1.16 for the
    LDPC codes of Lim et al.'s evaluation, 1.22 for CASCADE.

    Lim et al. set it exactly this way in their evaluation section, and note
    what it is: a model. In a real run ``leak_EC`` is *measured* — it is the
    length of the messages the two sides actually exchanged — and a protocol
    that reports it from this formula while the code performed worse has
    overcounted its key.

    Why this is charged on everything
    ---------------------------------
    The block size here is the **whole** key basis, ``n_X``, not the certified
    single-photon part of it. Error correction happens before anyone knows which
    detections came from single photons — nobody ever knows — so it is paid on
    every sifted bit, including the multi-photon ones that will contribute no
    secrecy at all. That asymmetry against the single-photon-only privacy term
    is the shape of Eq. (1), and it is why the rate dies at a QBER far below the
    one where privacy amplification alone would fail.

    Parameters
    ----------
    block_size : float or FloatArray
        ``n_X``: sifted bits being reconciled. Non-negative.
    observed_error_rate : float or FloatArray
        ``E``: the fraction of them that disagree, in ``[0, 1]``.
    efficiency : float
        ``f_EC >= 1``. One is Shannon's limit, which no code attains.

    Returns
    -------
    FloatArray
        Bits, non-negative, of the broadcast shape of the two arrays.

    Raises
    ------
    DomainError
        If the block size is negative, if the error rate leaves ``[0, 1]``, or
        if the efficiency is below one.

    Examples
    --------
    A block of 810 200 sifted bits at a 1 % error rate, corrected by a code 16 %
    off Shannon:

    >>> round(
    ...     float(
    ...         error_correction_leakage(
    ...             block_size=810200.0,
    ...             observed_error_rate=0.01,
    ...             efficiency=1.16,
    ...         )
    ...     )
    ... )
    75932

    Nine per cent of the block, spent before any of the security analysis
    begins. At a QBER of 11 % — BB84's asymptotic threshold — it is more than
    half:

    >>> round(
    ...     float(
    ...         error_correction_leakage(
    ...             block_size=810200.0,
    ...             observed_error_rate=0.11,
    ...             efficiency=1.16,
    ...         )
    ...     )
    ...     / 810200.0,
    ...     4,
    ... )
    0.5799
    """
    size = _as_counts(block_size, name="block_size")
    rate = np.asarray(observed_error_rate, dtype=np.float64)
    factor = float(efficiency)
    if not np.isfinite(factor) or factor < 1.0:
        raise DomainError(
            f"efficiency must be finite and at least 1, got {factor}. It is the factor by which "
            "a real reconciliation code exceeds Shannon's limit -- 1.16 for the LDPC codes of "
            "Lim et al. 2014, 1.22 for CASCADE -- and below one it claims a code that reveals "
            "less than the entropy it removes."
        )
    leakage: FloatArray = factor * size * binary_entropy(rate)
    return leakage


@dataclass(frozen=True, slots=True, kw_only=True)
class FiniteKeyResult:
    """The bits a block yields, and every term that decided the number.

    Frozen and self-consistent: the length is a function of the other fields, so
    editing one afterwards would leave a result that no longer implies itself —
    the reason :class:`~quoss.qkd.base.KeyRate` is frozen too.

    The parts are kept because the total is uninformative on its own. "Zero
    bits" has at least four causes — nothing certified, the phase estimate
    failed, error correction outran the key, or the fixed ``eps`` penalty did —
    and they call for different responses: a longer block, a larger check basis,
    a better code, or nothing at all.

    Attributes
    ----------
    length_bits : FloatArray
        ``l``: secret key length, in bits. A whole number (Eq. (1) floors it)
        and never negative.
    vacuum_events : FloatArray
        ``s_{X,0}``, the certified vacuum detections, which enter the key in
        full.
    single_photon_events : FloatArray
        ``s_{X,1}``, the certified single-photon detections.
    phase_error_rate : FloatArray
        ``phi_X``, what privacy amplification was charged on, in ``[0, 1/2]``.
    observed_error_rate : FloatArray
        ``E``, the key basis QBER, what error correction was charged on.
    leakage_bits : FloatArray
        ``leak_EC``, bits revealed during reconciliation.
    block_size : FloatArray
        ``n_X``, detections in the key basis.
    pulses : FloatArray
        ``N``, pulses emitted for the block.
    security : SecurityParameters
        The pair the length is a claim under. Carried because a key length
        without its failure probabilities is not a security statement.

    Raises
    ------
    DomainError
        If any array is non-finite, if the length is negative, if the phase
        error rate leaves ``[0, 1/2]``, if the observed error rate leaves
        ``[0, 1]``, or if the arrays do not broadcast to a common shape.
    """

    length_bits: FloatArray
    vacuum_events: FloatArray
    single_photon_events: FloatArray
    phase_error_rate: FloatArray
    observed_error_rate: FloatArray
    leakage_bits: FloatArray
    block_size: FloatArray
    pulses: FloatArray
    security: SecurityParameters

    _ARRAYS = (
        "length_bits",
        "vacuum_events",
        "single_photon_events",
        "phase_error_rate",
        "observed_error_rate",
        "leakage_bits",
        "block_size",
        "pulses",
    )

    def __post_init__(self) -> None:
        """Validate the invariants a consumer may skip re-checking."""
        if not isinstance(self.security, SecurityParameters):
            raise DomainError(
                f"security must be a SecurityParameters, got {type(self.security).__name__}. A "
                "key length without the failure probabilities it is claimed under is a number, "
                "not a security statement."
            )
        values = {name: np.array(getattr(self, name), dtype=np.float64) for name in self._ARRAYS}
        for name, value in values.items():
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
        try:
            broadcast = np.broadcast_arrays(*values.values())
        except ValueError as exc:
            raise DomainError(
                "the result arrays must broadcast to a common shape, got "
                f"{ {name: value.shape for name, value in values.items()} }."
            ) from exc
        values = dict(zip(values.keys(), broadcast, strict=True))

        if np.any(values["length_bits"] < 0.0):
            raise DomainError(
                f"length_bits must be non-negative, got range [{_range_of(values['length_bits'])}]"
                ". Where Eq. (1) goes negative there is no key at all, so it is clamped at zero "
                "and has_key says which blocks; a negative length integrates into a negative "
                "key volume over a pass."
            )
        phase = values["phase_error_rate"]
        if np.any(phase < 0.0) or np.any(phase > VACUUM_ERROR_RATE):
            raise DomainError(
                f"phase_error_rate must lie in [0, 0.5], got range [{_range_of(phase)}]. Above "
                "one half it carries no information and is capped there, which makes the "
                "single-photon term exactly zero."
            )
        observed = values["observed_error_rate"]
        if np.any(observed < 0.0) or np.any(observed > 1.0):
            raise DomainError(
                f"observed_error_rate must lie in [0, 1], got range [{_range_of(observed)}]."
            )
        for name, value in values.items():
            object.__setattr__(self, name, frozen_view(value))

    @property
    def regime(self) -> KeyRegime:
        """Always :attr:`~quoss.qkd.base.KeyRegime.FINITE`.

        A property rather than a field because it is not a choice: everything
        this module computes is a finite-block statement, and a result that
        could be labelled otherwise would be a result that could be mislabelled.
        """
        return KeyRegime.FINITE

    @property
    def key_per_pulse(self) -> FloatArray:
        """``l / N``: the quantity Lim et al. plot as the secret key rate.

        Zero where no pulses were sent, which is the empty block. Not a rate per
        second: multiplying by the source pulse rate is
        :attr:`~quoss.qkd.base.LinkConditions.pulse_rate_hz`'s job and belongs
        where the time axis is.
        """
        safe = np.where(self.pulses > 0.0, self.pulses, 1.0)
        rate: FloatArray = np.where(self.pulses > 0.0, self.length_bits / safe, 0.0)
        return rate

    @property
    def secret_fraction(self) -> FloatArray:
        """``l / n_X``: bits of key per sifted bit of the key basis.

        The quantity that makes two different links comparable after the loss
        has been divided out, and the one that shows what the finite-size
        penalty costs: it falls towards zero as the block shrinks even though
        the link has not changed.
        """
        safe = np.where(self.block_size > 0.0, self.block_size, 1.0)
        fraction: FloatArray = np.where(self.block_size > 0.0, self.length_bits / safe, 0.0)
        return fraction

    @property
    def has_key(self) -> BoolArray:
        """True where the block yields at least one bit."""
        positive: BoolArray = self.length_bits > 0.0
        return positive

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the arrays."""
        return self.length_bits.shape

    def __repr__(self) -> str:
        return (
            f"FiniteKeyResult(shape={self.shape}, length_bits=[{_range_of(self.length_bits)}], "
            f"phase_error_rate=[{_range_of(self.phase_error_rate)}], {self.security!r})"
        )


def secret_key_length(
    counts: DecoyBlockCounts,
    *,
    settings: DecoySettings,
    security: SecurityParameters,
    error_correction_efficiency: float,
    degradations: DegradationLog,
) -> FiniteKeyResult:
    """Return how many secret bits a block of counts certifies. Lim et al. Eq. (1).

    What it does
    ------------
    Assembles the other four formulas::

        l = floor[ s_{X,0} + s_{X,1} (1 - h(phi_X)) - leak_EC
                   - 6 log2(21/eps_sec) - log2(2/eps_cor) ]

    and clamps the result at zero. Each term is computed by the function that
    owns it — :func:`certified_events` for the two counts,
    :func:`single_photon_errors` and :func:`phase_error_rate` for ``phi_X``,
    :func:`error_correction_leakage` for the reconciliation cost — and all five
    are returned inside the :class:`FiniteKeyResult` so that a zero can be
    explained rather than only reported.

    The four terms, and what each one is buying
    -------------------------------------------
    * ``s_{X,0}``: **free key from noise.** Detections in gates where Alice sent
      nothing. Eve cannot know a bit that was decided by a dark count, so these
      enter at full value with no entropy charged against them. They are what
      keeps the bound alive at losses where the single-photon term has died.
    * ``s_{X,1} (1 - h(phi_X))``: the single-photon key, after privacy
      amplification. Multi-photon detections appear nowhere: GLLP assumes Eve
      has them.
    * ``leak_EC``: charged on the **whole** key basis, single-photon or not.
    * the two logarithms: a fixed toll of
      :attr:`SecurityParameters.penalty_bits`, paid once per block whatever the
      link does.

    Parameters
    ----------
    counts : DecoyBlockCounts
        Both bases and the pulse budget.
    settings : DecoySettings
        The intensities and their probabilities. Must be the ones the counts
        were taken with; nothing can check that, which is why they travel
        together through every call.
    security : SecurityParameters
        The failure probabilities the result is a claim under.
    error_correction_efficiency : float
        ``f_EC >= 1``. Required, with no default, for the same reason
        :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` requires it: it is a property
        of the code the experiment actually ran.
    degradations : DegradationLog
        Receives every clamp and every failed certificate.

    Returns
    -------
    FiniteKeyResult
        The length and the terms behind it.

    Examples
    --------
    This project's reference downlink at zenith, a block of 1e10 pulses — a
    hundred seconds of a 100 MHz source — with Ntanos et al.'s intensities and a
    symmetric basis choice:

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> conditions = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> settings = DecoySettings(
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     vacuum_intensity=0.0,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ... )
    >>> block = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e10
    ... )
    >>> log = DegradationLog()
    >>> result = secret_key_length(
    ...     block,
    ...     settings=settings,
    ...     security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
    ...     error_correction_efficiency=1.22,
    ...     degradations=log,
    ... )
    >>> float(result.length_bits)
    113870.0
    >>> result.regime
    <KeyRegime.FINITE: 'finite'>

    A hundred and fourteen kilobits out of a hundred seconds of pass — 1.14 kbit
    per second — and the label matters: this is what the block certifies, not
    what an infinitely long one would. The parts say where it came from and what
    it cost:

    >>> round(float(result.vacuum_events)), round(float(result.single_photon_events))
    (0, 476496)
    >>> round(float(result.phase_error_rate), 4), round(float(result.leakage_bits))
    (0.0885, 156816)

    Read that as a budget. The 476 496 certified single-photon detections lose
    43 % of themselves to privacy amplification (``h(0.0885) = 0.4314``), which
    leaves 270 946 bits; error correction takes 156 816 of those, and the fixed
    security penalty 260 more. The certified vacuum events contribute nothing
    here — on a night link there are only 375 of them, far inside the block's
    own Hoeffding deviation. The same link with a hundred times more pulses is
    almost five times better **per pulse**, because neither the fixed cost nor
    the square-root one grows with the block:

    >>> longer = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e12
    ... )
    >>> long_result = secret_key_length(
    ...     longer,
    ...     settings=settings,
    ...     security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
    ...     error_correction_efficiency=1.22,
    ...     degradations=DegradationLog(),
    ... )
    >>> round(float(long_result.key_per_pulse / result.key_per_pulse), 3)
    4.8
    """
    key_events = certified_events(
        counts.key_basis, settings=settings, security=security, degradations=degradations
    )
    check = certified_events(
        counts.check_basis, settings=settings, security=security, degradations=degradations
    )
    certified_error_count = single_photon_errors(
        counts.check_basis, settings=settings, security=security, degradations=degradations
    )
    phase = phase_error_rate(
        certified_errors=certified_error_count,
        check_events=check.single_photon,
        key_events=key_events.single_photon,
        security=security,
        degradations=degradations,
    )
    block_size = counts.key_basis.total_detections
    observed = counts.key_basis.observed_error_rate
    leakage = error_correction_leakage(
        block_size=block_size,
        observed_error_rate=observed,
        efficiency=error_correction_efficiency,
    )

    raw = (
        key_events.vacuum
        + key_events.single_photon * (1.0 - binary_entropy(phase))
        - leakage
        - security.penalty_bits
    )
    length: FloatArray = np.maximum(np.floor(raw), 0.0)

    exhausted = int(np.count_nonzero((raw <= 0.0) & key_events.certified))
    if exhausted:
        degradations.warn(
            "finite-key.block-too-short",
            f"Single-photon events are certified at {exhausted} of {np.asarray(raw).size} "
            "blocks and the key length is still zero: what the certificate bought was spent on "
            f"error correction and on the {security.penalty_bits:.0f} bits of fixed security "
            "penalty. This is a statement about the block length, not about the link -- the "
            "penalty is paid once per block, so pooling more pulses into one block is the "
            "response, and shortening the block is what makes it worse.",
            where="quoss.qkd.finite_key.secret_key_length",
            exhausted_blocks=exhausted,
            total_blocks=int(np.asarray(raw).size),
            penalty_bits=security.penalty_bits,
        )

    return FiniteKeyResult(
        length_bits=length,
        vacuum_events=key_events.vacuum,
        single_photon_events=key_events.single_photon,
        phase_error_rate=phase,
        observed_error_rate=observed,
        leakage_bits=leakage,
        block_size=block_size,
        pulses=counts.pulses,
        security=security,
    )


def expected_block_counts(
    conditions: LinkConditions,
    *,
    settings: DecoySettings,
    key_basis_probability: float,
    pulses: FloatLike,
) -> DecoyBlockCounts:
    """Turn link conditions and a pulse budget into the counts a block would hold.

    What it is
    ----------
    The simulation-side bridge, and the only function in this module that knows
    what a transmittance is. In an experiment the counts are *counted*; in a
    study they have to come from the channel model, and this is where
    :mod:`quoss.channel` meets the finite-key bound. It calls
    :func:`~quoss.qkd.bb84.simulate_intensity` once per intensity — the same
    forward model :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` uses, so the two
    modules cannot disagree about what the link does — and multiplies the
    resulting gains and error rates by how many pulses went where::

        n_{X,k} = N p_k q_x^2 Q_k          m_{X,k} = n_{X,k} E_k
        n_{Z,k} = N p_k (1-q_x)^2 Q_k      m_{Z,k} = n_{Z,k} E_k

    ``q_x^2`` and ``(1-q_x)^2`` are the sifting: Alice and Bob choose bases
    independently, and a detection is kept only where the two happened to agree.
    The pulses where they disagree — a fraction ``2 q_x (1-q_x)``, which is half
    of them at ``q_x = 1/2`` — are discarded and appear in neither basis. This
    is where a biased basis choice pays for itself: at ``q_x = 0.9``, 81 % of
    the detections reach the key basis instead of 25 %, and the check basis
    keeps 1 %, which is exactly the trade :func:`random_sampling_deviation`
    prices.

    These are **expectations**, not draws
    -------------------------------------
    Every count returned is a mean. That is deliberate and it is what makes the
    result a statement about a typical block: the finite-key bound prices the
    *estimation* uncertainty that remains even when the counts land exactly on
    their expectations, which is what ``delta`` and ``gamma`` are. Adding a
    multinomial draw on top would answer a different question — how much the
    answer scatters between passes — and that is ``system/monte_carlo.py``.

    A consequence worth stating: expected counts are not integers, and nothing
    here rounds them. A sample contributing 0.4 detections contributes 0.4.

    Two assumptions inherited from Lim et al.'s protocol
    ----------------------------------------------------
    **Detection probability does not depend on the basis.** Lim et al. require
    it explicitly in their concluding remarks — it is what lets the check basis
    speak for the key basis — and it is why the same ``Q_k`` multiplies both
    lines above. A receiver whose two bases have different efficiencies
    violates the proof, not merely this function.

    **The two bases have the same error rate.** The channel model of
    :mod:`quoss.channel` has one misalignment error and no basis-dependent
    term, so ``E_k`` is the same in both. A real polarisation receiver need not
    be that symmetric, and a measured asymmetry belongs in the counts, which is
    why :class:`BasisCounts` takes both bases' errors separately rather than
    deriving one from the other.

    Parameters
    ----------
    conditions : LinkConditions
        What the channel delivers at each sample: transmittance, noise mean and
        misalignment error.
    settings : DecoySettings
        Alice's three intensities and how often she sends each.
    key_basis_probability : float
        ``q_x`` in ``(0, 1)``: the probability that either party chooses the key
        basis. ``0.5`` is the symmetric BB84 of :mod:`quoss.qkd.bb84`.
    pulses : float or FloatArray
        ``N``: pulses emitted per sample, broadcasting against the conditions.
        For a pass this is the source pulse rate times the sample's dwell time,
        which is a question about a time grid and therefore the caller's —
        ``system/key_volume.py`` in this project.

    Returns
    -------
    DecoyBlockCounts
        Per-sample expected counts. Call :meth:`DecoyBlockCounts.pooled` to add
        the samples of a pass into the single block the bound is about.

    Raises
    ------
    DomainError
        If ``key_basis_probability`` is outside ``(0, 1)``, if ``pulses`` is
        negative, or if ``pulses`` does not broadcast against the conditions.

    Examples
    --------
    The reference downlink at zenith, a hundred seconds of a 100 MHz source:

    >>> from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ, LinkConditions
    >>> conditions = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> settings = DecoySettings(
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     vacuum_intensity=0.0,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ... )
    >>> block = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.5, pulses=1e10
    ... )
    >>> round(float(block.key_basis.signal_detections))
    1493502
    >>> round(float(block.key_basis.observed_error_rate), 6)
    0.010638

    Higher than the 1.0492 % that
    :func:`~quoss.qkd.bb84.simulate_intensity` returns for the signal state
    alone, because this block pools all three intensities and a vacuum
    detection is wrong half the time by construction.

    A quarter of the pulses reach the key basis and a quarter the check basis,
    so the two bases hold the same counts at ``q_x = 1/2``:

    >>> bool(
    ...     np.isclose(
    ...         float(block.key_basis.total_detections),
    ...         float(block.check_basis.total_detections),
    ...     )
    ... )
    True

    Biasing the basis moves detections from the check basis to the key basis
    without changing the link at all:

    >>> biased = expected_block_counts(
    ...     conditions, settings=settings, key_basis_probability=0.9, pulses=1e10
    ... )
    >>> round(float(biased.key_basis.total_detections / block.key_basis.total_detections), 3)
    3.24

    A pass is the same call with arrays, one pulse budget per sample, pooled
    into the block the bound is about:

    >>> a_pass = LinkConditions(
    ...     transmittance=np.array([3.06e-04, 1.3993e-03, 3.06e-04]),
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> samples = expected_block_counts(
    ...     a_pass, settings=settings, key_basis_probability=0.5, pulses=1e10
    ... )
    >>> samples.shape, samples.pooled().shape
    ((3,), ())
    >>> round(float(samples.pooled().pulses))
    30000000000
    """
    bias = float(key_basis_probability)
    if not np.isfinite(bias) or not 0.0 < bias < 1.0:
        raise DomainError(
            f"key_basis_probability must be finite and in (0, 1), got {bias}. It is the "
            "probability that a party picks the key basis: 0.5 is symmetric BB84, and at 0 or 1 "
            "one of the two bases is never measured -- with no check basis there is no phase "
            "error estimate and no key, and with no key basis there is no key either."
        )
    budget = _as_counts(pulses, name="pulses")
    try:
        np.broadcast_shapes(conditions.shape, budget.shape)
    except ValueError as exc:
        raise DomainError(
            f"pulses {budget.shape} must broadcast against the conditions {conditions.shape}. "
            "One pulse budget per sample, or one for all of them."
        ) from exc

    key_sifting = bias**2
    check_sifting = (1.0 - bias) ** 2
    key_detections: list[FloatArray] = []
    key_errors: list[FloatArray] = []
    check_detections: list[FloatArray] = []
    check_errors: list[FloatArray] = []
    for intensity, probability in zip(settings.intensities, settings.probabilities, strict=True):
        observables = simulate_intensity(conditions, intensity=intensity)
        sent = budget * probability
        for detections, errors, sifting in (
            (key_detections, key_errors, key_sifting),
            (check_detections, check_errors, check_sifting),
        ):
            detected = sent * sifting * observables.gain
            detections.append(detected)
            errors.append(detected * observables.qber)

    return DecoyBlockCounts(
        key_basis=BasisCounts(
            signal_detections=key_detections[0],
            decoy_detections=key_detections[1],
            vacuum_detections=key_detections[2],
            signal_errors=key_errors[0],
            decoy_errors=key_errors[1],
            vacuum_errors=key_errors[2],
        ),
        check_basis=BasisCounts(
            signal_detections=check_detections[0],
            decoy_detections=check_detections[1],
            vacuum_detections=check_detections[2],
            signal_errors=check_errors[0],
            decoy_errors=check_errors[1],
            vacuum_errors=check_errors[2],
        ),
        pulses=np.broadcast_to(budget, np.broadcast_shapes(conditions.shape, budget.shape)).copy(),
    )
