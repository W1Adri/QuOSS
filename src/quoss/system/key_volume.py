r"""The integral over a pass: bits per pass, bits per day, and the block that makes it finite.

What this module is for, and why it is not a multiplication
----------------------------------------------------------
:mod:`quoss.qkd` answers "what fraction of a pulse sent *right now* becomes
secret key". A mission asks "how many bits do we get tonight". Turning the first
into the second looks like multiplying a rate by a duration, and for the
asymptotic rate it very nearly is. For the number that a real system actually
delivers, it is not, and the gap is the whole content of this module.

The reason is that a **finite-key bound is a statement about a block, not about
an instant.** :mod:`quoss.qkd.finite_key` prices the fact that Alice and Bob
never observe a probability, only a count: 412 detections out of 3.7e8 pulses is
an *estimate* of a yield, and an estimate can have bad luck. The price of that
uncertainty depends on how many counts there are, so it depends on the size of
the block — and a block is an integral over a time axis. ``qkd/`` has no time
axis, which is why every rate leaving :mod:`quoss.qkd.base` is labelled
:attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` and says so in its own field, and
why ``finite_key.py`` could compute the bound but could not make it the default.

This module owns the time axis, so it can. :func:`pass_key_volume` — the
unqualified name, the one a caller reaches for — returns
:attr:`~quoss.qkd.base.KeyRegime.FINITE`. The asymptotic answer is available
only through :func:`asymptotic_pass_key_volume`, whose name says what it is.
That is the pending decision of ``qkd/__init__.py`` and
`ADR 0010 <../../docs/adr/0010-decoy-and-finite-key.md>`_, closed here, and it
is closed **structurally** rather than with a default argument: there is no
``regime=`` keyword to flip, because a keyword with a default is a keyword
somebody will pass the other value to by accident.

The headline: what the asymptotic rate overstates, measured
-----------------------------------------------------------
This project's reference downlink — a 0.75 m telescope at Castelldefels, a
700 km sun-synchronous satellite, a clear moonless night, Ntanos et al.'s 16:1:4
decoy split at ``mu = 0.56``, ``eps_cor = eps_sec = 1e-10``, a 10 degree
elevation mask, one UTC day:

=======  ==============  ==============  ======================
Pass     Asymptotic      Finite          Culmination elevation
=======  ==============  ==============  ======================
1        1 548 341 bit   **190 581** bit  52.9 deg
2        319 898 bit     **0** bit        17.6 deg
3        1 709 160 bit   **242 404** bit  58.8 deg
4        199 281 bit     **0** bit        14.2 deg
Day      3 776 681 bit   **432 985** bit  --
=======  ==============  ==============  ======================

The day's ratio is **11.5 %**, which already matters. The per-pass column
matters more: **two of the four passes yield literally nothing**, where the
asymptotic integral claims 320 and 199 kbit. So the error of reporting the
asymptotic figure is not "about nine times optimistic"; it is *unbounded* on the
passes whose blocks are too small for the statistics, and those are exactly the
low-elevation passes a scheduler would be deciding whether to take.

Why a low pass dies completely rather than yielding a little
-----------------------------------------------------------
The mechanism is worth spelling out, because "small block, small key" is the
wrong intuition. Pass 4 collects 309 867 detections in the key basis — not a
small number. What kills it is the **phase error rate**: the bound must infer,
from the basis Alice and Bob *did* measure, what the error rate would have been
in the conjugate basis, and that inference is a sampling argument whose width
grows as the counts shrink. At pass 4's block size the inference returns
``phi = 0.5``, the maximum possible, at which ``1 - h(phi) = 0`` and the entire
single-photon term vanishes. Meanwhile error correction is still charged on all
309 867 bits. The bound does not taper to zero; it falls off a cliff, and
:attr:`~quoss.qkd.finite_key.FiniteKeyResult.phase_error_rate` is the field that
says which cliff.

The finding only this module can see: the elevation mask has an interior optimum
-------------------------------------------------------------------------------
:mod:`quoss.system.passes` takes the mask as a required argument and says it is
a design variable. Here is why. Sweeping the mask over the reference day:

========  =======  =================  ================
Mask      Passes   Finite day (bit)   Asymptotic (bit)
========  =======  =================  ================
2 deg     6        408 946            3 876 492
5 deg     5        426 988            3 876 492
7 deg     4        433 771            3 862 432
**8 deg** 4        **434 938**        3 844 682
10 deg    4        432 985            3 776 681
20 deg    2        360 978            2 949 471
========  =======  =================  ================

Two separate things are visible and both are the point.

**The asymptotic column is monotone and the finite column is not.** Asymptotic
key per pulse is clamped at zero sample by sample, so adding a bad sample to a
pass can never subtract key — below 5 degrees the extra samples contribute
*exactly* zero and the column stops moving altogether. A block-level bound has
no such protection: the low-elevation samples at a pass's edges bring their
errors into the pooled block, where error correction is charged on **every**
detection, while contributing almost no certified single-photon events. Lowering
the mask from 8 to 2 degrees adds **71 %** more usable seconds and **destroys
6.0 % of the day's key**, and the asymptotic calculation cannot see it happen.

**So the optimum is interior, near 8 degrees**, and it is not where a geometric
argument would put it. Measured on pass 1 alone, going from a 10 to a 5 degree
mask: its certified single-photon events rise 2.6 % (718 970 to 737 975) and its
error-correction leakage rises **5.5 %** (246 574 to 260 144). The second
outruns the first, and the pass loses 1.7 % of its key while gaining 22 % of its
duration. This is the same shape of finding as the decoy-fraction optimum in
``finite_key.py``: a quantity the asymptotic formula is indifferent to turns out
to have a real optimum once the block is finite.

Why both regimes share one quadrature, and one configuration object
-------------------------------------------------------------------
A comparison between two numbers is worthless if they differ in more than the
thing being compared. Two precautions make the table above a measurement of the
*bound* and nothing else.

**One weight vector.** Both paths integrate over the dwell times of
:meth:`~quoss.system.passes.PassTable.samples` — the midpoint-rule seconds each
sample speaks for. The asymptotic path multiplies the per-second rate by them;
the finite path multiplies the pulse rate by them to get each sample's share of
the block's pulses. Neither path has a quadrature rule of its own, so neither
can be ahead or behind for a reason that is not the bound.

**One configuration object.** Both paths take the same
:class:`~quoss.qkd.bb84.Bb84DecoyProtocol`, and
:func:`decoy_settings_from_protocol` derives the
:class:`~quoss.qkd.finite_key.DecoySettings` the finite path needs from it. The
alternative — two objects, one per regime — would let the two describe different
experiments, and the failure mode is silent: a comparison between ``mu = 0.56``
asymptotic and ``mu = 0.5`` finite looks exactly like a comparison between two
bounds.

Adding up a day is not free, and this is where it is priced
----------------------------------------------------------
A day's key is the sum of its passes' keys, which is arithmetic. The **security
statement** is not, and this is the one place in the project where it can be
stated, because it is the only place that holds more than one block.

Each pass is an independent block, certified ``eps_sec``-secret and
``eps_cor``-correct *on its own*. Concatenating ``n`` such keys gives a key whose
failure probability is bounded by the union of the ``n`` failures:
``n * eps``, not ``eps``. At four passes and ``eps = 1e-10`` that is a harmless
``4e-10`` — but it is a different number from the one printed beside it, and at
a hundred passes of a constellation it is ``1e-8``. :func:`composed_security`
computes it and :attr:`DailyKeyVolume.security` carries it, so that a day's key
never travels without the ``eps`` it is actually secure under.

And the other direction is priced too. To make a **day** ``eps``-secure rather
than each pass, every block must run at ``eps / n``. Measured on the reference
day at ``eps = 1e-10`` and four passes: 404 780 bits instead of 432 985, so a
genuinely ``1e-10``-secure day costs **6.5 %** of the key. Cheap, and not zero,
and not something anybody would find by reading a rate plot.

Why one block per pass, and not per sample or per day
----------------------------------------------------
The choice of what constitutes a block is the single largest lever in this
module, and the two obvious alternatives both fail, in opposite directions and
by measurable amounts.

**One block per sample**, which is what treating the finite-key bound as a
per-instant correction would amount to, yields **zero bits from the entire
reference day** — 0 of 1800 samples certify a single bit. Each sample's block
holds a median of 1615 key-basis
detections (469 at the worst sample, 8917 at the best), against a fixed
:attr:`~quoss.qkd.finite_key.SecurityParameters.penalty_bits` toll of 260 bits
and a phase-error inference that has nothing to work with. The bound is not
additive over sub-blocks, and assuming it is loses everything.

**One block per day** — pooling all four passes into one — is the opposite
temptation: a bigger block pays the 260-bit toll once and has tighter
statistics. It is also wrong, and not by a little. Pooling requires the blocks
to come from one run of the protocol with one set of parameters, and the four
passes are separated by hours in which the satellite is below the horizon and no
pulses are sent at all. More concretely, it would pool the error rates: the two
dead passes contribute 787 000 detections at 1.8-1.9 % QBER into a block whose
good passes sit at 1.24-1.26 %, and error correction is charged on the lot. This
module does not offer it, and :func:`daily_key_volume` sums *lengths*, which is
the operation that is actually licensed.

What is deliberately not in here
--------------------------------
**The scatter between passes.** Every count in the block comes from
:func:`~quoss.qkd.finite_key.expected_block_counts`, which returns
**expectations**. The finite-key bound prices the estimation uncertainty that
remains *even when the counts land exactly on their means*; how much the answer
moves when they do not is a different question and is ``system/monte_carlo.py``.
So the numbers here are the key a *typical* pass certifies, not a quantile of a
distribution over passes, and they carry no P5/P95.

**Time-correlated fading.** The conditions at each sample are independent
marginal quantiles from :mod:`quoss.channel.link_budget`, whose docstring says
plainly that until ``system/correlated_fading.py`` exists "no statement in this
module about a key *per pass* follows from one about a key *per gate*". This
module makes exactly that statement, so the caveat transfers here and is
restated rather than dropped: a real link fades in millisecond bursts, so the
*number of consecutive gates lost* is not what independent sampling implies.
What that does to a block is an open question, and the honest summary is that
these figures assume the fade statistics of a pass are the marginal ones.

**Cloud.** A cloud-free line of sight is a probability that the pass happened at
all. Multiplying a key volume by it would turn "works on 70 % of nights" into
"delivers 70 % of the key every night", which are different systems.
``system/pcflos.py``.

**Parameter optimisation.** The intensities, the decoy split, the basis bias and
the mask all have optima that move with the block, and two of them are measured
above. Searching that space is ``engine/sweep.py``.

**Choosing between ground stations, and relays.** ``system/multi_ogs.py`` and
``system/relay.py``.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``l``                                   secret key length of a block (bit)
``N``                                   pulses emitted for a block
``w_i``                                 dwell time of sample ``i`` (s)
``q_x``                                 probability of choosing the key basis
``eps_sec``, ``eps_cor``                secrecy and correctness failure
                                        probabilities of one block
``n``                                   number of blocks composed into a day
======================================  ====================================

References
----------
C. C. W. Lim, M. Curty, N. Walenta, F. Xu and H. Zbinden, "Concise security
bounds for practical decoy-state quantum key distribution", *Physical Review A*
**89**, 022307 (2014). Eq. (1) is the block bound every number here rests on;
:mod:`quoss.qkd.finite_key` implements it and this module decides what the block
is.

A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021.
The reference link parameters and the decoy configuration of
:meth:`~quoss.qkd.bb84.Bb84DecoyProtocol.ntanos_2021`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, IntArray, frozen_view
from quoss.core.units import deg_to_rad
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import (
    BasisCounts,
    DecoyBlockCounts,
    DecoySettings,
    FiniteKeyResult,
    SecurityParameters,
    expected_block_counts,
    secret_key_length,
)
from quoss.system.passes import PassSamples

__all__ = [
    "SYMMETRIC_KEY_BASIS_PROBABILITY",
    "DailyKeyVolume",
    "PassKeyVolume",
    "asymptotic_pass_key_volume",
    "composed_security",
    "daily_key_volume",
    "decoy_settings_from_protocol",
    "pass_key_volume",
]

SYMMETRIC_KEY_BASIS_PROBABILITY: Final[float] = 0.5
"""``q_x`` for symmetric BB84: Alice and Bob pick either basis with equal odds.

Not a tunable default but the value that makes the two regimes the same
protocol. :attr:`~quoss.qkd.bb84.Bb84DecoyProtocol.protocol_efficiency` is
``0.5 * signal_probability``, and that leading one half **is** this number: it
is the fraction of pulses where the two independently chosen bases happen to
agree. Hand the finite path a different ``q_x`` and the asymptotic comparison
stops being a comparison — one side would be biasing the basis and the other
not — so :func:`pass_key_volume` accepts another value and records a warning
saying exactly that.
"""

_VACUUM_INTENSITY: Final[float] = 0.0
"""``mu_3`` implied by :class:`~quoss.qkd.bb84.Bb84DecoyProtocol`.

The asymptotic module's vacuum state is an exactly empty pulse — its
``background_yield`` is the click probability of a gate with nothing in it — so
deriving :class:`~quoss.qkd.finite_key.DecoySettings` from a protocol has to use
zero and not a small positive number. Lim et al.'s bound allows ``mu_3 >= 0``,
which is strictly more general; a run that uses a non-zero third intensity
builds its ``DecoySettings`` directly and has no asymptotic counterpart in this
package to compare against.
"""

_BASIS_COUNT_FIELDS: Final[tuple[str, ...]] = (
    "signal_detections",
    "decoy_detections",
    "vacuum_detections",
    "signal_errors",
    "decoy_errors",
    "vacuum_errors",
)
"""The six columns of a :class:`~quoss.qkd.finite_key.BasisCounts`, for pooling.

Spelled out rather than read off the class's private ``_FIELDS``: a segment sum
over passes has to touch every column, and naming them here means adding a
seventh count to that class breaks this module loudly instead of silently
dropping the new column out of every block.
"""


def decoy_settings_from_protocol(protocol: Bb84DecoyProtocol) -> DecoySettings:
    """Return the finite-key decoy settings that describe the same experiment.

    The bridge between the two regimes, and the reason they can be compared at
    all. :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` and
    :class:`~quoss.qkd.finite_key.DecoySettings` hold the same five choices —
    two intensities and three sending probabilities — with one difference: the
    asymptotic protocol does not carry a third intensity because its vacuum
    state is exactly empty, while Lim et al.'s bound allows ``mu_3 >= 0``. This
    function supplies the zero, and :data:`_VACUUM_INTENSITY` documents why it
    is zero and not a small number.

    **It exists so that there is no second place to type ``mu``.** Two objects
    configured independently would let the finite and asymptotic answers describe
    different links, and the failure has no symptom: the comparison still
    produces a ratio, and the ratio is wrong by whatever the two configurations
    disagreed about.

    Parameters
    ----------
    protocol : Bb84DecoyProtocol
        The asymptotic protocol configuration.

    Returns
    -------
    DecoySettings
        The same intensities and probabilities, with ``mu_3 = 0``.

    Raises
    ------
    DomainError
        If ``protocol`` is not a :class:`~quoss.qkd.bb84.Bb84DecoyProtocol`.

    Examples
    --------
    Ntanos et al.'s configuration, carried across unchanged:

    >>> from quoss.qkd.bb84 import Bb84DecoyProtocol
    >>> settings = decoy_settings_from_protocol(Bb84DecoyProtocol.ntanos_2021())
    >>> settings.intensities
    (0.56, 0.11, 0.0)
    >>> tuple(round(value, 6) for value in settings.probabilities)
    (0.761905, 0.047619, 0.190476)

    ``tau_0``, the probability that a pulse was empty, follows from the split and
    is what the vacuum certificate is normalised by:

    >>> round(settings.tau(0), 6)
    0.668342
    """
    if not isinstance(protocol, Bb84DecoyProtocol):
        raise DomainError(
            f"protocol must be a Bb84DecoyProtocol, got {type(protocol).__name__}. This function "
            "exists to keep one configuration driving both regimes; handing it something else "
            "would reintroduce the second place to type an intensity."
        )
    return DecoySettings(
        signal_intensity=protocol.signal_intensity,
        decoy_intensity=protocol.decoy_intensity,
        vacuum_intensity=_VACUUM_INTENSITY,
        signal_probability=protocol.signal_probability,
        decoy_probability=protocol.decoy_probability,
        vacuum_probability=protocol.vacuum_probability,
    )


def composed_security(security: SecurityParameters, blocks: int) -> SecurityParameters:
    """Return the failure probabilities a concatenation of ``blocks`` keys satisfies.

    What it computes, and why it is not the identity
    -----------------------------------------------
    ``n * eps_sec`` and ``n * eps_cor``. A union bound: the concatenated key
    fails if *any* of the blocks failed, and the bound a proof gives for each one
    is per block. Composability is precisely the property that licenses this
    addition — that is what the word means in "composable finite-key bound", and
    :class:`~quoss.qkd.finite_key.SecurityParameters` documents it for the
    ``eps_sec + eps_cor`` sum inside one block. The same argument applied across
    blocks is this function.

    **Why it needs saying at all.** Every figure in the satellite-QKD literature
    that reports "bits per day" is a sum of passes, and the ``eps`` printed in
    the caption is almost always the per-block one. The gap is small and it is
    real: four passes at ``1e-10`` give a day at ``4e-10``, a hundred passes of a
    constellation give ``1e-8``, and a year of four passes a day gives
    ``1.5e-7``. None of those is alarming; all of them are different from the
    number beside them, and the difference grows with exactly the quantity — more
    passes — that a mission is trying to maximise.

    Parameters
    ----------
    security : SecurityParameters
        The per-block failure probabilities.
    blocks : int
        How many blocks are concatenated. At least one.

    Returns
    -------
    SecurityParameters
        The composed pair.

    Raises
    ------
    DomainError
        If ``blocks`` is below one, or if the composed probability reaches one —
        at which point the concatenation carries no security claim at all, which
        is a result worth refusing to return rather than returning as a number.

    Examples
    --------
    Four passes at ``1e-10`` each:

    >>> per_block = SecurityParameters(correctness=1e-10, secrecy=1e-10)
    >>> day = composed_security(per_block, 4)
    >>> f"{day.secrecy:.1e}"
    '4.0e-10'

    And the other direction, which is what a mission wanting an ``eps``-secure
    *day* has to run each block at:

    >>> tighter = SecurityParameters(correctness=1e-10 / 4, secrecy=1e-10 / 4)
    >>> f"{composed_security(tighter, 4).secrecy:.1e}"
    '1.0e-10'

    Enough blocks at a loose enough ``eps`` and the claim is vacuous, which is
    refused rather than reported:

    >>> composed_security(SecurityParameters(correctness=0.5, secrecy=0.5), 4)
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: composing 4 blocks at correctness=5.000e-01 gives 2, which is not a failure probability: the concatenated key has no security claim. Run each block at a smaller eps, or report the passes separately.
    """
    if not isinstance(security, SecurityParameters):
        raise DomainError(f"security must be a SecurityParameters, got {type(security).__name__}.")
    count = int(blocks)
    if count < 1:
        raise DomainError(
            f"blocks must be at least 1, got {count}. Composing zero blocks is not a key with a "
            "trivial guarantee, it is the absence of a key, and nothing downstream can use the "
            "difference."
        )
    for label, value in (("correctness", security.correctness), ("secrecy", security.secrecy)):
        composed = count * value
        if composed >= 1.0:
            raise DomainError(
                f"composing {count} blocks at {label}={value:.3e} gives {composed:g}, which is "
                "not a failure probability: the concatenated key has no security claim. Run each "
                "block at a smaller eps, or report the passes separately."
            )
    return SecurityParameters(
        correctness=count * security.correctness,
        secrecy=count * security.secrecy,
    )


def _validated_samples(samples: PassSamples, conditions: LinkConditions) -> None:
    """Check that the conditions were evaluated at exactly these pass samples.

    The contract of this module: a caller evaluates :mod:`quoss.channel` at the
    ``(satellite, sample)`` pairs :meth:`~quoss.system.passes.PassTable.samples`
    lists, in that order, and hands back a :class:`~quoss.qkd.base.LinkConditions`
    of that one-dimensional shape. Checking it here is what makes the contract a
    contract: a conditions array of the right length but the wrong order would
    attribute every sample's transmittance to the wrong instant and produce a
    key volume that is wrong by an amount nothing downstream could notice.
    """
    if not isinstance(samples, PassSamples):
        raise DomainError(f"samples must be a PassSamples, got {type(samples).__name__}.")
    if not isinstance(conditions, LinkConditions):
        raise DomainError(f"conditions must be a LinkConditions, got {type(conditions).__name__}.")
    if conditions.shape != samples.shape:
        raise DomainError(
            f"conditions has shape {conditions.shape} but there are {samples.size} (pass, "
            f"sample) entries, so the expected shape is {samples.shape}. This module does not "
            "compute the channel: the caller evaluates it at samples.satellite_index and "
            "samples.sample_index, in that order, and hands the result back. A length mismatch "
            "is a different set of instants; a matching length in a different order would be "
            "undetectable, which is why the order is part of the contract and not a convention."
        )
    if samples.size == 0:
        raise DomainError(
            "samples is empty: there are no passes to integrate over. Check the elevation mask "
            "and the time window before asking for a key volume."
        )


def _pooled_block(
    per_sample: DecoyBlockCounts, samples: PassSamples, pulses: FloatArray
) -> DecoyBlockCounts:
    """Add the per-sample counts of each pass into that pass's single block.

    A segment sum, one per count column, via
    :meth:`~quoss.system.passes.PassSamples.segment_sum`. It is a plain addition
    because counts are counts: the detections of a pass are the detections of its
    samples added, which is what
    :meth:`~quoss.qkd.finite_key.DecoyBlockCounts.pooled` does for a whole array
    and what this does per pass.
    """

    def pool(basis: BasisCounts) -> BasisCounts:
        return BasisCounts(
            **{
                name: samples.segment_sum(np.asarray(getattr(basis, name), dtype=np.float64))
                for name in _BASIS_COUNT_FIELDS
            }
        )

    return DecoyBlockCounts(
        key_basis=pool(per_sample.key_basis),
        check_basis=pool(per_sample.check_basis),
        pulses=samples.segment_sum(pulses),
    )


@dataclass(frozen=True, eq=False, slots=True)
class PassKeyVolume:
    """Bits per pass, with the regime that claim is made in and the terms behind it.

    Attributes
    ----------
    samples : PassSamples
        The ``(pass, sample)`` entries integrated over. Carries the
        :class:`~quoss.system.passes.PassTable`, so a volume always travels with
        the passes and the elevation mask it is about.
    regime : KeyRegime
        :attr:`~quoss.qkd.base.KeyRegime.FINITE` from :func:`pass_key_volume`,
        :attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC` from
        :func:`asymptotic_pass_key_volume`. The two are not a correction factor
        apart — see the module docstring's table, where two passes differ by
        *everything* — so a volume that did not say which would be uncomparable.
    key_bits : FloatArray
        Secret bits from each pass, shape ``(P,)``. Never negative. A whole
        number in the finite regime, where it is a block length; a real number in
        the asymptotic regime, where it is an integral of a rate.
    pulses : FloatArray
        Pulses emitted during each pass, shape ``(P,)``.
    seconds : FloatArray
        Usable seconds of each pass — the dwell times summed, identical to
        :attr:`~quoss.system.passes.PassTable.duration_s`, carried so that
        :attr:`mean_bit_s` needs nothing else.
    finite : FiniteKeyResult or None
        Every term of Lim et al. Eq. (1) per pass in the finite regime — the
        certified counts, the phase error rate, the leakage — and ``None`` in the
        asymptotic one. Present because "zero bits" has four possible causes and
        they call for different fixes; see
        :class:`~quoss.qkd.finite_key.FiniteKeyResult`.
    protocol : str
        Name of the protocol that produced this.

    Raises
    ------
    DomainError
        If the arrays do not have one entry per pass, if any is negative or
        non-finite, if ``finite`` is present in the asymptotic regime or absent
        in the finite one, or if the finite result does not have one block per
        pass.

    Examples
    --------
    >>> import numpy as np
    >>> volume = _reference_volume()
    >>> volume.regime
    <KeyRegime.FINITE: 'finite'>
    >>> volume.key_bits
    array([190581.,      0., 242404.,      0.])
    >>> float(volume.total_bits)
    432985.0

    Two of the four passes certify nothing, and the reason is in the terms:

    >>> volume.has_key
    array([ True, False,  True, False])
    >>> np.round(volume.finite.phase_error_rate, 3)
    array([0.077, 0.459, 0.072, 0.5  ])
    """

    samples: PassSamples
    regime: KeyRegime
    key_bits: FloatArray
    pulses: FloatArray
    seconds: FloatArray
    finite: FiniteKeyResult | None
    protocol: str

    def __post_init__(self) -> None:
        """Validate that the columns describe these passes in this regime."""
        if not isinstance(self.samples, PassSamples):
            raise DomainError(f"samples must be a PassSamples, got {type(self.samples).__name__}.")
        object.__setattr__(self, "regime", KeyRegime(self.regime))
        if not isinstance(self.protocol, str) or not self.protocol:
            raise DomainError(f"protocol must be a non-empty name, got {self.protocol!r}.")

        n_passes = self.samples.table.n_passes
        for name in ("key_bits", "pulses", "seconds"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (n_passes,):
                raise DomainError(
                    f"{name} has shape {value.shape}, but there are {n_passes} passes. One "
                    "number per pass; a scalar would be a day's total wearing a pass's name."
                )
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
            if np.any(value < 0.0):
                raise DomainError(
                    f"{name} must be non-negative, got range [{float(value.min())}, "
                    f"{float(value.max())}]. A negative key volume is not a small key but the "
                    "absence of one, which has_key reports and a negative number would hide by "
                    "cancelling against a positive pass in the day's sum."
                )
            object.__setattr__(self, name, frozen_view(value))

        if self.regime is KeyRegime.FINITE:
            if not isinstance(self.finite, FiniteKeyResult):
                raise DomainError(
                    "a FINITE key volume must carry the FiniteKeyResult its length came from, "
                    f"got {type(self.finite).__name__}. Without it a zero cannot be explained, "
                    "and the four reasons a block yields nothing need different responses."
                )
            if self.finite.shape != (n_passes,):
                raise DomainError(
                    f"finite has shape {self.finite.shape}, but there are {n_passes} passes. One "
                    "block per pass is the whole decision of this module."
                )
        elif self.finite is not None:
            raise DomainError(
                "an ASYMPTOTIC key volume must not carry a FiniteKeyResult: it would claim a "
                "block-level statement for a number computed per instant and integrated."
            )

    @property
    def n_passes(self) -> int:
        """Number of passes, ``P``."""
        return int(self.key_bits.size)

    def __len__(self) -> int:
        return self.n_passes

    @property
    def total_bits(self) -> float:
        """Bits summed over every pass in the table.

        Adding **lengths**, which is the operation composability licenses. What
        it does *not* do is tighten the security parameter: see
        :func:`composed_security` and :attr:`DailyKeyVolume.security`.
        """
        return float(np.sum(self.key_bits))

    @property
    def has_key(self) -> BoolArray:
        """True for each pass that yields at least one bit."""
        positive: BoolArray = self.key_bits > 0.0
        return positive

    @property
    def mean_bit_s(self) -> FloatArray:
        """Bits per second averaged over each pass, ``key_bits / seconds``.

        The number a figure of "secret key rate over a pass" should be compared
        against, and not the same thing as the peak instantaneous rate: on the
        reference day's best pass it is 434 bit/s against a peak asymptotic rate
        of 6896 bit/s, because most of a pass is spent near the horizon and
        because the block pays for its own statistics.
        """
        rate: FloatArray = self.key_bits / self.seconds
        return rate

    @property
    def key_per_pulse(self) -> FloatArray:
        """``key_bits / pulses``: the quantity a rate plot of this project shows."""
        safe = np.where(self.pulses > 0.0, self.pulses, 1.0)
        per_pulse: FloatArray = np.where(self.pulses > 0.0, self.key_bits / safe, 0.0)
        return per_pulse

    def __repr__(self) -> str:
        return (
            f"PassKeyVolume({self.protocol!r}, {self.regime}, n_passes={self.n_passes}, "
            f"total_bits={self.total_bits:.3e}, with_key={int(self.has_key.sum())})"
        )


@dataclass(frozen=True, eq=False, slots=True)
class DailyKeyVolume:
    """Bits per UTC day, and the failure probability that sum is actually secure under.

    Attributes
    ----------
    day_number : IntArray
        Julian Day Number of each day, ascending and without gaps in the data —
        a day with no pass simply does not appear, which is the honest
        representation: "no key" and "no pass" are different facts and a zero row
        would conflate them.
    key_bits : FloatArray
        Bits summed over the passes that started in each day.
    pass_count : IntArray
        Passes that started in each day.
    passes_with_key : IntArray
        How many of them yielded at least one bit. Carried separately because the
        difference between this and :attr:`pass_count` is the single most
        informative number in the table — on the reference day it is 2 of 4.
    seconds : FloatArray
        Usable seconds summed over each day's passes.
    regime : KeyRegime
        Inherited from the :class:`PassKeyVolume` this came from.
    security : SecurityParameters or None
        The failure probabilities the **day's concatenated key** satisfies, from
        :func:`composed_security` applied to the largest number of blocks any one
        day holds. ``None`` in the asymptotic regime, which makes no ``eps``
        claim at all. See the module docstring: this field is why the class
        exists rather than being a two-line ``np.bincount`` at the call site.
    protocol : str
        Name of the protocol.

    Raises
    ------
    DomainError
        If the columns disagree in length, if ``day_number`` is not strictly
        ascending, if any count or length is negative, or if ``security`` is
        present in the asymptotic regime or absent in the finite one.

    Examples
    --------
    >>> daily = _reference_daily()
    >>> daily.day_number
    array([2460677])
    >>> float(daily.key_bits[0])
    432985.0
    >>> int(daily.passes_with_key[0]), int(daily.pass_count[0])
    (2, 4)

    And the part a caption usually gets wrong: four blocks at ``1e-10`` make a
    day at ``4e-10``.

    >>> f"{daily.security.secrecy:.1e}"
    '4.0e-10'
    """

    day_number: IntArray
    key_bits: FloatArray
    pass_count: IntArray
    passes_with_key: IntArray
    seconds: FloatArray
    regime: KeyRegime
    security: SecurityParameters | None
    protocol: str

    def __post_init__(self) -> None:
        """Validate the columns and the regime's security claim."""
        object.__setattr__(self, "regime", KeyRegime(self.regime))
        if not isinstance(self.protocol, str) or not self.protocol:
            raise DomainError(f"protocol must be a non-empty name, got {self.protocol!r}.")

        days = np.asarray(self.day_number, dtype=np.int64)
        if days.ndim != 1:
            raise DomainError(f"day_number must be 1-D, got shape {days.shape}.")
        if days.size and not np.all(np.diff(days) > 0):
            raise DomainError(
                "day_number must be strictly ascending with no repeats: a repeated day is two "
                "partial totals for one night, which would be read as two nights."
            )
        object.__setattr__(self, "day_number", days)

        for name in ("key_bits", "seconds"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != days.shape:
                raise DomainError(
                    f"{name} has shape {value.shape}, but day_number has {days.shape}."
                )
            if not np.all(np.isfinite(value)) or np.any(value < 0.0):
                raise DomainError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, frozen_view(value))
        for name in ("pass_count", "passes_with_key"):
            value = np.asarray(getattr(self, name), dtype=np.int64)
            if value.shape != days.shape:
                raise DomainError(
                    f"{name} has shape {value.shape}, but day_number has {days.shape}."
                )
            if np.any(value < 0):
                raise DomainError(f"{name} must be non-negative.")
            object.__setattr__(self, name, value)
        if np.any(self.passes_with_key > self.pass_count):
            raise DomainError(
                "passes_with_key cannot exceed pass_count: a pass that yielded key is one of the "
                "passes."
            )

        if self.regime is KeyRegime.FINITE:
            if not isinstance(self.security, SecurityParameters):
                raise DomainError(
                    "a FINITE daily volume must carry the composed SecurityParameters, got "
                    f"{type(self.security).__name__}. A day's key is a concatenation of blocks "
                    "and its failure probability is their union bound, not one block's eps."
                )
        elif self.security is not None:
            raise DomainError(
                "an ASYMPTOTIC daily volume must not carry SecurityParameters: the asymptotic "
                "rate makes no finite-block claim, so attaching an eps to it would be a security "
                "statement nothing computed."
            )

    @property
    def n_days(self) -> int:
        """Number of days with at least one pass."""
        return int(self.day_number.size)

    def __len__(self) -> int:
        return self.n_days

    @property
    def total_bits(self) -> float:
        """Bits summed over every day."""
        return float(np.sum(self.key_bits))

    @property
    def mean_bit_s(self) -> FloatArray:
        """Bits per usable second of each day — not per second of the day."""
        rate: FloatArray = self.key_bits / self.seconds
        return rate

    def __repr__(self) -> str:
        return (
            f"DailyKeyVolume({self.protocol!r}, {self.regime}, n_days={self.n_days}, "
            f"total_bits={self.total_bits:.3e})"
        )


def pass_key_volume(
    conditions: LinkConditions,
    *,
    samples: PassSamples,
    protocol: Bb84DecoyProtocol,
    security: SecurityParameters,
    degradations: DegradationLog,
    key_basis_probability: float = SYMMETRIC_KEY_BASIS_PROBABILITY,
) -> PassKeyVolume:
    """Return the secret bits each pass certifies. Finite-key, and there is no flag.

    **This is the default answer of the project.** It applies Lim et al. 2014
    Eq. (1) to the block a pass actually is, and there is deliberately no
    ``regime`` argument: the asymptotic number lives in
    :func:`asymptotic_pass_key_volume`, whose name says so. See the module
    docstring for what that costs — on the reference day, 88.5 % of the
    headline figure and two passes out of four entirely.

    How it works, in three vectorised steps
    ---------------------------------------
    1. **Pulses per sample.** Each sample's dwell time (the midpoint-rule seconds
       from :meth:`~quoss.system.passes.PassTable.samples`) times the source
       pulse rate. No rounding: a sample that emitted 1.4e8 pulses emitted 1.4e8,
       and the block size is what the bound is sensitive to, not the integrality
       of one sample's share.
    2. **Counts per sample**, from
       :func:`~quoss.qkd.finite_key.expected_block_counts` — one call over every
       in-pass instant of the whole window, the same forward model
       :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` uses, so the two regimes cannot
       disagree about what the link does.
    3. **One block per pass**, by segment-summing those counts, and then
       :func:`~quoss.qkd.finite_key.secret_key_length` once over the whole pass
       axis. Nothing loops over passes.

    Parameters
    ----------
    conditions : LinkConditions
        What the channel delivers at each in-pass instant, shape
        ``(samples.size,)`` — evaluated by the caller at
        ``samples.satellite_index`` and ``samples.sample_index``, **in that
        order**. This module does not compute the channel: that would make
        :mod:`quoss.system` depend on every knob of :mod:`quoss.channel` and put
        a twelve-argument budget in this signature. The order is checked only by
        length, which is why the contract is stated here rather than assumed.
    samples : PassSamples
        From :meth:`~quoss.system.passes.PassTable.samples`.
    protocol : Bb84DecoyProtocol
        The experimenter's choices. Drives **both** regimes, through
        :func:`decoy_settings_from_protocol`; its
        ``error_correction_efficiency`` is the ``f_EC`` the block is charged.
    security : SecurityParameters
        The per-block failure probabilities. Required, with no default, for the
        reason that class gives: they are the claim, not a tuning knob. Note that
        these are **per pass**; :func:`daily_key_volume` composes them.
    degradations : DegradationLog
        Receives every clamp from the bound itself, plus an entry naming how many
        passes certified nothing and a warning if ``key_basis_probability`` makes
        this incomparable with the asymptotic path.
    key_basis_probability : float, optional
        ``q_x`` in ``(0, 1)``. Defaults to
        :data:`SYMMETRIC_KEY_BASIS_PROBABILITY`, the only value for which this
        and :func:`asymptotic_pass_key_volume` describe the same protocol. Any
        other value is honoured and warned about.

    Returns
    -------
    PassKeyVolume
        One length per pass, in :attr:`~quoss.qkd.base.KeyRegime.FINITE`.

    Raises
    ------
    DomainError
        If ``conditions`` does not match ``samples`` in shape, if ``samples`` is
        empty, or if any argument is not of its declared type.

    Examples
    --------
    The reference day: four passes, two of which certify key.

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.qkd.bb84 import Bb84DecoyProtocol
    >>> from quoss.qkd.finite_key import SecurityParameters
    >>> samples, conditions = _reference_conditions()
    >>> log = DegradationLog()
    >>> volume = pass_key_volume(
    ...     conditions,
    ...     samples=samples,
    ...     protocol=Bb84DecoyProtocol.ntanos_2021(),
    ...     security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
    ...     degradations=log,
    ... )
    >>> volume.key_bits
    array([190581.,      0., 242404.,      0.])
    >>> volume.regime
    <KeyRegime.FINITE: 'finite'>

    The two dead passes are reported, not dropped:

    >>> [entry.code for entry in log if entry.code.startswith("key_volume")]
    ['key_volume.passes-without-key']

    And the bits are whole numbers, because a block length is:

    >>> bool(np.all(volume.key_bits == np.floor(volume.key_bits)))
    True
    """
    _validated_samples(samples, conditions)
    settings = decoy_settings_from_protocol(protocol)
    if not isinstance(security, SecurityParameters):
        raise DomainError(f"security must be a SecurityParameters, got {type(security).__name__}.")
    q_x = float(key_basis_probability)
    if q_x != SYMMETRIC_KEY_BASIS_PROBABILITY:
        degradations.warn(
            "key_volume.asymmetric-basis-choice",
            f"key_basis_probability={q_x} is not the symmetric {SYMMETRIC_KEY_BASIS_PROBABILITY} "
            "that Bb84DecoyProtocol.protocol_efficiency assumes, so this result is NOT comparable "
            "with asymptotic_pass_key_volume for the same protocol: one biases the basis and the "
            "other does not. The finite-key number itself is correct for the biased protocol.",
            where="quoss.system.key_volume.pass_key_volume",
            key_basis_probability=q_x,
            symmetric_value=SYMMETRIC_KEY_BASIS_PROBABILITY,
        )

    pulses_per_sample = conditions.pulse_rate_hz * np.asarray(samples.dwell_s, dtype=np.float64)
    per_sample = expected_block_counts(
        conditions,
        settings=settings,
        key_basis_probability=q_x,
        pulses=pulses_per_sample,
    )
    block = _pooled_block(per_sample, samples, pulses_per_sample)
    result = secret_key_length(
        block,
        settings=settings,
        security=security,
        error_correction_efficiency=protocol.error_correction_efficiency,
        degradations=degradations,
    )

    seconds = samples.segment_sum(np.asarray(samples.dwell_s, dtype=np.float64))
    volume = PassKeyVolume(
        samples=samples,
        regime=KeyRegime.FINITE,
        key_bits=np.asarray(result.length_bits, dtype=np.float64),
        pulses=np.asarray(block.pulses, dtype=np.float64),
        seconds=seconds,
        finite=result,
        protocol=protocol.name,
    )
    barren = int((~volume.has_key).sum())
    if barren:
        degradations.info(
            "key_volume.passes-without-key",
            f"{barren} of {volume.n_passes} passes certify no key at all. That is a result, not "
            "a failure: the asymptotic rate is positive over every one of them, so a study that "
            "reported the asymptotic figure would have counted them. FiniteKeyResult's "
            "phase_error_rate and leakage_bits say which of the four reasons applies to each.",
            where="quoss.system.key_volume.pass_key_volume",
            passes_without_key=barren,
            n_passes=volume.n_passes,
            phase_error_rate=[float(value) for value in result.phase_error_rate],
        )
    return volume


def asymptotic_pass_key_volume(
    conditions: LinkConditions,
    *,
    samples: PassSamples,
    protocol: Bb84DecoyProtocol,
    degradations: DegradationLog,
) -> PassKeyVolume:
    """Return the asymptotic key integral over each pass. An **upper bound**, named as one.

    The time integral of :attr:`~quoss.qkd.base.KeyRate.secure_bit_s` over each
    pass, using the same dwell times :func:`pass_key_volume` turns into pulses,
    so the two differ by the bound and not by the quadrature.

    **What it is for.** Three legitimate uses and no others: comparing against a
    published asymptotic figure, measuring what the finite-size penalty costs,
    and sanity-checking that the channel and protocol are wired up at all. It is
    not a number to report as available key — see the module docstring's table,
    where it exceeds the real answer by a factor of 8.7 over a day and by
    *everything* on two passes out of four.

    **Why it integrates a clamped rate, and what that hides.**
    :attr:`~quoss.qkd.base.KeyRate.secure_per_pulse` is clamped at zero sample by
    sample, so a sample where the asymptotic formula goes negative contributes
    nothing rather than subtracting. That makes this integral monotone in the
    elevation mask: widening a pass can never reduce it. The finite bound has no
    such protection, because its error correction is charged on the pooled block,
    and the module docstring measures the 6.0 % of a day that difference is
    worth. A reader comparing the two columns of that table is looking at the
    consequence of this clamp.

    Parameters
    ----------
    conditions : LinkConditions
        As in :func:`pass_key_volume`: shape ``(samples.size,)``, evaluated in
        ``samples`` order.
    samples : PassSamples
        From :meth:`~quoss.system.passes.PassTable.samples`.
    protocol : Bb84DecoyProtocol
        The same object :func:`pass_key_volume` takes.
    degradations : DegradationLog
        Receives everything the protocol records, plus the reminder that this
        number is an upper bound.

    Returns
    -------
    PassKeyVolume
        One integral per pass, in :attr:`~quoss.qkd.base.KeyRegime.ASYMPTOTIC`,
        with :attr:`PassKeyVolume.finite` set to ``None``.

    Raises
    ------
    DomainError
        If ``conditions`` does not match ``samples`` in shape or ``samples`` is
        empty.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.qkd.bb84 import Bb84DecoyProtocol
    >>> samples, conditions = _reference_conditions()
    >>> log = DegradationLog()
    >>> upper = asymptotic_pass_key_volume(
    ...     conditions,
    ...     samples=samples,
    ...     protocol=Bb84DecoyProtocol.ntanos_2021(),
    ...     degradations=log,
    ... )
    >>> np.round(upper.key_bits)
    array([1548341.,  319898., 1709160.,  199281.])
    >>> upper.regime
    <KeyRegime.ASYMPTOTIC: 'asymptotic'>
    >>> upper.finite is None
    True

    Every call says, in the log, that this is not the available key:

    >>> [entry.code for entry in log if entry.code.startswith("key_volume")]
    ['key_volume.asymptotic-upper-bound']
    """
    _validated_samples(samples, conditions)
    if not isinstance(protocol, Bb84DecoyProtocol):
        raise DomainError(f"protocol must be a Bb84DecoyProtocol, got {type(protocol).__name__}.")

    rate = protocol.key_rate(conditions, degradations=degradations)
    dwell = np.asarray(samples.dwell_s, dtype=np.float64)
    key_bits = samples.segment_sum(np.asarray(rate.secure_bit_s, dtype=np.float64) * dwell)
    pulses = samples.segment_sum(conditions.pulse_rate_hz * dwell)
    seconds = samples.segment_sum(dwell)

    degradations.warn(
        "key_volume.asymptotic-upper-bound",
        "this key volume is ASYMPTOTIC: it assumes each pass's block of detections is infinitely "
        "long, so it is an upper bound on what the pass delivers, and one that is loosest exactly "
        "where the link is worst. On this project's reference day it exceeds the finite-key "
        "answer by a factor of 8.7 over the day and certifies key on two passes that certify "
        "none. Use pass_key_volume for the available key.",
        where="quoss.system.key_volume.asymptotic_pass_key_volume",
        n_passes=samples.table.n_passes,
    )
    return PassKeyVolume(
        samples=samples,
        regime=KeyRegime.ASYMPTOTIC,
        key_bits=key_bits,
        pulses=pulses,
        seconds=seconds,
        finite=None,
        protocol=protocol.name,
    )


def daily_key_volume(volume: PassKeyVolume, *, degradations: DegradationLog) -> DailyKeyVolume:
    """Group a pass volume by UTC day and compose the security claim.

    Sums **lengths**, which composability licenses, and composes the failure
    probabilities, which is the part a "bits per day" figure usually leaves out.
    See :func:`composed_security` and the module docstring.

    The day of a pass is the UTC calendar day its refined start falls in
    (:attr:`~quoss.system.passes.PassTable.day_number`), and a pass straddling
    midnight is counted whole in the earlier day — a convention, stated there,
    and the only one that does not split a block.

    **Why the composed ``eps`` uses the busiest day and not each day's own
    count.** A :class:`DailyKeyVolume` carries one
    :class:`~quoss.qkd.finite_key.SecurityParameters`, so it has to be a
    statement every row satisfies. Taking the maximum pass count makes it the
    weakest claim in the table, which is the only one true of all of them; taking
    each day's own would be a per-row field that a reader summing the column
    would then compose a second time, by hand, wrongly.

    Parameters
    ----------
    volume : PassKeyVolume
        Per-pass bits, from either regime.
    degradations : DegradationLog
        Receives the composed ``eps`` and, in the asymptotic regime, the note
        that there is none.

    Returns
    -------
    DailyKeyVolume
        One row per UTC day that holds at least one pass.

    Raises
    ------
    DomainError
        If ``volume`` is not a :class:`PassKeyVolume`, or if the composition
        would make the day's failure probability reach one.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> volume = _reference_volume()
    >>> log = DegradationLog()
    >>> daily = daily_key_volume(volume, degradations=log)
    >>> daily.day_number, daily.key_bits
    (array([2460677]), array([432985.]))
    >>> int(daily.pass_count[0]), int(daily.passes_with_key[0])
    (4, 2)

    The day's key is a concatenation of four blocks, so its secrecy is four times
    one block's, and the log says so:

    >>> f"{daily.security.secrecy:.1e}"
    '4.0e-10'
    >>> [entry.code for entry in log]
    ['key_volume.day-composes-blocks']
    """
    if not isinstance(volume, PassKeyVolume):
        raise DomainError(f"volume must be a PassKeyVolume, got {type(volume).__name__}.")

    day_of_pass = volume.samples.table.day_number
    days, inverse = np.unique(day_of_pass, return_inverse=True)
    n_days = int(days.size)
    key_bits = np.bincount(inverse, weights=volume.key_bits, minlength=n_days)
    seconds = np.bincount(inverse, weights=volume.seconds, minlength=n_days)
    pass_count = np.bincount(inverse, minlength=n_days).astype(np.int64)
    with_key = np.bincount(
        inverse, weights=volume.has_key.astype(np.float64), minlength=n_days
    ).astype(np.int64)

    security: SecurityParameters | None = None
    if volume.regime is KeyRegime.FINITE:
        assert volume.finite is not None  # guaranteed by PassKeyVolume.__post_init__
        blocks = int(pass_count.max())
        security = composed_security(volume.finite.security, blocks)
        degradations.info(
            "key_volume.day-composes-blocks",
            f"each day's key is the concatenation of up to {blocks} independent blocks, so its "
            f"failure probabilities are the union bound: eps_sec = {security.secrecy:.3e} and "
            f"eps_cor = {security.correctness:.3e}, against "
            f"{volume.finite.security.secrecy:.3e} and "
            f"{volume.finite.security.correctness:.3e} per pass. To make the DAY secure at the "
            "per-pass eps, run every block at eps divided by the number of passes; on this "
            "project's reference day that costs 6.5 % of the key.",
            where="quoss.system.key_volume.daily_key_volume",
            blocks=blocks,
            per_block_secrecy=volume.finite.security.secrecy,
            composed_secrecy=security.secrecy,
        )
    else:
        degradations.warn(
            "key_volume.day-has-no-security-claim",
            "this daily total is ASYMPTOTIC, so it carries no failure probability: there is no "
            "eps to compose because no finite-block statement was made. Any 'bits per day at "
            "eps = ...' built on it would be attaching a claim nothing computed.",
            where="quoss.system.key_volume.daily_key_volume",
            n_days=n_days,
        )

    return DailyKeyVolume(
        day_number=days.astype(np.int64),
        key_bits=np.asarray(key_bits, dtype=np.float64),
        pass_count=pass_count,
        passes_with_key=with_key,
        seconds=np.asarray(seconds, dtype=np.float64),
        regime=volume.regime,
        security=security,
        protocol=volume.protocol,
    )


# --------------------------------------------------------------------------- #
# Reference link for the doctests above.
#
# The geometry comes from `quoss.system.passes`, so there is one reference
# satellite and one reference station in this package rather than two that drift.
# The channel parameters are the ones `tests/channel/test_link_budget.py` and
# `tests/qkd/test_finite_key.py` use, so that every number in the prose of this
# module traces to the same link as theirs.
# --------------------------------------------------------------------------- #
def _reference_conditions() -> tuple[PassSamples, LinkConditions]:
    """Return the reference day's in-pass samples and the link conditions there.

    A 0.75 m ground telescope, 1550 nm, a 1 ns gate, a clear moonless night, and
    a 10 degree elevation mask. Extinction is declared ignored
    (``zenith_transmittance=1.0``) rather than guessed, per
    ``docs/adr/0009-citation-policy.md``: no source verified for this project
    publishes a zenith transmittance, so the figures here are a clear-sky upper
    bound on the atmosphere as well as an exact statement about everything else.

    Examples
    --------
    >>> samples, conditions = _reference_conditions()
    >>> samples.size == conditions.shape[0]
    True
    >>> conditions.shape
    (1800,)
    """
    from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
    from quoss.channel.detector import (
        NTANOS_FILTER_INSERTION_LOSS_DB,
        NTANOS_RECEIVER_LOSS_DB,
        NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        NTANOS_SNSPD_EFFICIENCY,
        receiver_efficiency,
    )
    from quoss.channel.link_budget import (
        NTANOS_FILTER_BANDWIDTH_M,
        NTANOS_POINTING_JITTER_RAD,
        NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        NTANOS_TRANSMIT_APERTURE_M,
        downlink_loss_budget,
        downlink_noise_budget,
    )
    from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ
    from quoss.system.passes import _reference_geometry, find_passes

    wavelength_m = 1.55e-6
    aperture_m = 0.75
    gate_s = 1e-9
    misalignment = 0.01

    angles, grid = _reference_geometry()
    table = find_passes(
        angles,
        grid=grid,
        minimum_elevation_rad=float(deg_to_rad(10.0)),
        degradations=DegradationLog(),
    )
    samples = table.samples()
    log = DegradationLog()
    chain = receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )
    loss = downlink_loss_budget(
        np.asarray(angles.elevation_rad)[samples.satellite_index, samples.sample_index],
        range_km=np.asarray(angles.range_km)[samples.satellite_index, samples.sample_index],
        wavelength_m=wavelength_m,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=aperture_m,
        zenith_transmittance=1.0,
        pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
        receiver_efficiency=chain,
        degradations=log,
    )
    noise = downlink_noise_budget(
        NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
        wavelength_m=wavelength_m,
        receive_aperture_m=aperture_m,
        field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
        filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
        gate_duration_s=gate_s,
        receiver_efficiency=chain,
        dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
        detector_count=2,
        degradations=log,
    )
    conditions = LinkConditions(
        transmittance=loss.transmittance,
        noise_counts_per_gate=noise.total_per_gate,
        misalignment_error=misalignment,
        pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
        gate_duration_s=gate_s,
    )
    return samples, conditions


def _reference_volume() -> PassKeyVolume:
    """Return the reference day's finite-key volume.

    Examples
    --------
    >>> float(_reference_volume().total_bits)
    432985.0
    """
    samples, conditions = _reference_conditions()
    return pass_key_volume(
        conditions,
        samples=samples,
        protocol=Bb84DecoyProtocol.ntanos_2021(),
        security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
        degradations=DegradationLog(),
    )


def _reference_daily() -> DailyKeyVolume:
    """Return the reference day grouped by UTC day.

    Examples
    --------
    >>> _reference_daily().n_days
    1
    """
    return daily_key_volume(_reference_volume(), degradations=DegradationLog())
