r"""The distribution of a pass's key: P5/P50/P95 and outage, from an ensemble of fading links.

What the project reports today, and what that number is
-------------------------------------------------------
:func:`~quoss.system.key_volume.pass_key_volume` is the project's answer to
"how many bits does this pass certify". It feeds
:func:`~quoss.qkd.finite_key.expected_block_counts` — expectations, not draws —
with :attr:`~quoss.qkd.base.LinkConditions.transmittance`, which is
:attr:`~quoss.channel.link_budget.LossBudget.transmittance` and **includes the
fade allowance** ``fade_db``: the loss that pointing jitter and scintillation
together exceed only 1 % of the time. So the number the project reports today
is the key of a pass in which the link sits at its 1 % fade quantile **for the
entire pass**, as though the worst hundredth of a second were every second.

That is neither the mean of the key over the fade distribution nor any
quantile of the distribution of per-pass keys. It is a design figure: a
budget carries its fade allowance so that the link works 99 % of the time,
and a key computed from it is what the 1 % moments would give if they were
permanent. Measured on the reference day
(``tests/system/test_monte_carlo.py::TestWhatTheDesignNumberUnderReports``):
the design figure is **432 985** bits; the same deterministic calculation at
the **mean** transmittance — the fade allowance taken back out, the pointing
factor at its mean ``gamma^2 / (gamma^2 + 1)`` — is **758 707** bits, so the
design number under-reports the typical day by **43 %**. The two dead passes
stay dead: pass 2 and pass 4 certify nothing at the mean transmittance either,
so the finding of `ADR 0011 <../../docs/adr/0011-the-block-is-the-pass.md>`_
that two of four passes yield nothing is not an artefact of the allowance.

This module replaces that single figure with a **distribution**: draw the
fades as correlated processes in time (:mod:`quoss.system.correlated_fading`),
push every realisation of the link through the same counts model and the same
finite-key bound, and report where the P5, the P50 and the P95 of the key per
pass sit, and how often a pass yields nothing at all.

What a quantile is, and what outage means here
----------------------------------------------
The **P5** of a quantity is the value it falls below 5 % of the time; the P50
is the median, the P95 the value exceeded 5 % of the time. Between P5 and P95
lie nine passes in ten. Reporting the three together says what a pass
*typically* gives and how far a bad or a good one departs from it, which is
the answer a mission needs to size a key store. **Outage** here is the
probability that a pass certifies **zero** bits — not that the link is
below a loss threshold, which is what the same word means in
:mod:`quoss.channel.link_budget`. The two are related and not the same: a
pass in outage by this module's definition is one whose whole block, fades
and all, fell on the wrong side of the finite-key cliff.

Where the ensemble fluctuates around, and why it is not the design transmittance
------------------------------------------------------------------------------
Each realisation ``r`` multiplies a **fade-free** transmittance by a fade
factor::

    eta_free_i = conditions.transmittance_i * 10^(fade_db_i / 10)
    eta_{r,i}  = eta_free_i * F_{r,i}

``eta_free`` is the budget with the fade allowance taken back out — geometry,
atmosphere, truncation and the receiver chain only. ``F`` is the product of
the scintillation factor, whose mean is 1, and the pointing factor, whose mean
is ``gamma^2 / (gamma^2 + 1)``; so the ensemble's mean transmittance is
``eta_free * gamma^2 / (gamma^2 + 1)``, and that is where
:attr:`MonteCarloKeyVolume.expected` is evaluated. The design transmittance is
below it by ``fade_db`` minus the mean pointing loss, 1.08-3.90 dB less
0.22 dB across the reference day's samples.

Why the factor is dwell-averaged, and what correlation then changes
-------------------------------------------------------------------
A sample of the grid speaks for its dwell time of pulses, and those pulses see
the *average* of the fade over the dwell, not one value of it. With
millisecond fades and a 1 s grid, the average is over hundreds of independent
fades and its variance is hundreds of times smaller than the marginal's.
:func:`~quoss.system.correlated_fading.sample_fade_factors` is therefore
called with the dwell times, and the consequence is the module's honest
finding, measured in ``TestWhatCorrelationChanges`` on the reference link with
both correlation times set equal:

===========  ====================  ====================  ===================
``tau``      pass 1, P5-P95 (%)    pass 3, P5-P95 (%)    day, P5-P95 (%)
===========  ====================  ====================  ===================
1 ms         0.11                  0.09                  0.07
10 ms        0.33                  0.27                  0.22
100 ms       1.04                  0.89                  0.68
1 s          3.6                   3.0                   2.2
10 s         10.9                  9.9                   7.4
100 s        30.4                  28.8                  20.0
===========  ====================  ====================  ===================

Each decade of ``tau`` widens the band by ``sqrt(10)``, because the dwell
reduction is ``2 tau / T`` and a pass holds ``duration / (2 tau)`` independent
stretches. The band crosses one per cent of the median between 10 and 100 ms
on this link — two orders of magnitude above the physical estimate of
:class:`~quoss.system.correlated_fading.FadingParameters` — and the median
itself does not move with ``tau`` at all.

**And at the physical ``tau`` the fading is not what sets the spread.** With
the block counts Poisson-sampled and no fading (``tau -> 0``), the P5-P95 band
of pass 1 is **9.0 %** of the median; with fading at the physical correlation
times on top it is 9.4 %. Ninety times the fading contribution, from counting
alone — not from the millions of detections in the block, whose own Poisson
scatter is 0.03 %, but from the small decoy and vacuum counts the finite-key
bound infers the single-photon yield from, whose scatter it amplifies. That
is measured in ``TestWhatCorrelationChanges::test_counting_noise_dwarfs_fading_at_the_physical_tau``,
and it is the number a study of "the effect of fading on the key" would have
to compare itself against first.

A study that drew one independent fade per 1 s sample instead would report a
fading band ``sqrt(1/w)`` — ten to twenty times — wider than the true one, and
the module does not compute that number: the instantaneous factors exist for
fade-duration statistics, and
:func:`~quoss.system.correlated_fading.sample_fade_factors` warns when they
are drawn on a grid coarser than the correlation time.

What correlated fading *does* change on this grid is then two things: the
low quantiles by exactly the variance the correlation adds once ``tau`` is
comparable to the dwell, and the fade-duration statistics of
:func:`~quoss.system.correlated_fading.fade_duration_statistics`, which an
i.i.d. model gets wrong by the ratio of the grid step to the correlation time
and which this module does not need but the synchronisation layer will.

Counting noise, and why Poisson on the pooled block is the exact model
----------------------------------------------------------------------
Even at a fixed transmittance Alice and Bob count, they do not observe an
expectation. With ``sample_counts=True`` (the default) every pooled block
count is drawn from a Poisson distribution with the expected count as its
mean, and each error count from a binomial on the drawn detections at the
expected error rate — the thinning of a Poisson process, which keeps errors
inside detections by construction. This is exact for a Poisson process with
piecewise-constant rate, which is what a block of gates with a per-sample
transmittance is once the fade realisation is fixed; the Bernoulli-per-gate
truth differs from it by a factor ``1 - Q`` in the variance, with ``Q`` the
click probability per gate, below ``1e-3`` on the reference link. The
pulse budget is not sampled: the source clock is not random.

Choosing the number of realisations, by a criterion and not by taste
--------------------------------------------------------------------
The P5 is an order statistic and its standard error is
``sqrt(p (1 - p) / R) / f(q_p)`` with ``f`` the density at the quantile.
Under a normal approximation to the key's distribution that is
``(SD / phi(z_p)) sqrt(p (1 - p) / R)``, and :func:`realisations_for_quantile`
inverts it: for a target standard error of 1 % of the median at ``p = 0.05``,
``R = 445 (SD / median)^2 / 0.01^2``, i.e. 445 realisations for a 10 % relative
spread and 18 for a 2 % one. :func:`quantile_standard_error` bootstraps the
same quantity from the ensemble actually drawn, which is how
``TestTheRealisationCount`` checks that the formula is not optimistic.

What is deliberately not in here
--------------------------------
**No channel.** Like ``key_volume.py``, this module takes the conditions and
the three per-sample fade inputs already evaluated, and the reason is the
same: the dependency order ``core <- physics <- system``. **No optimisation of
the block.** Every realisation uses the pass as its block, per ADR 0011. **No
cloud.** A cloudy pass is a pass that did not happen, ``system/pcflos.py``.
**No parallelism.** The ensemble is vectorised over realisations in chunks
and takes a few seconds for a day at a thousand realisations; ``engine/`` may
split passes across workers, and the per-pass spawned streams below are what
make that split invisible to the result.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``R``                                   number of realisations
``P``                                   number of passes
``eta_free``                            transmittance with the fade allowance removed
``F``                                   relative fade factor of a realisation
``p``                                   a quantile probability
``q_p``                                 the ``p`` quantile of the key
======================================  ====================================
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import pairwise
from typing import Final

import numpy as np
from scipy.special import ndtri

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.rng import RandomSource
from quoss.core.types import FloatArray, IntArray, frozen_view
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import (
    BasisCounts,
    DecoyBlockCounts,
    FiniteKeyResult,
    SecurityParameters,
    expected_block_counts,
    secret_key_length,
)
from quoss.system.correlated_fading import FadingParameters, sample_fade_factors
from quoss.system.key_volume import (
    SYMMETRIC_KEY_BASIS_PROBABILITY,
    PassKeyVolume,
    composed_security,
    decoy_settings_from_protocol,
    pass_key_volume,
)
from quoss.system.passes import PassSamples

__all__ = [
    "MonteCarloDailyKeyVolume",
    "MonteCarloKeyVolume",
    "MonteCarloOptions",
    "monte_carlo_daily_key_volume",
    "monte_carlo_pass_key_volume",
    "quantile_standard_error",
    "realisations_for_quantile",
]

DEFAULT_QUANTILES: Final[tuple[float, ...]] = (0.05, 0.5, 0.95)
"""P5, P50 and P95: the band nine passes in ten fall inside, and its middle."""

DEFAULT_CHUNK_ELEMENTS: Final[int] = 2_000_000
"""Link evaluations per chunk of the ensemble.

Two million ``(realisation, sample)`` pairs is about twenty arrays of 16 MB
alive at once inside :func:`~quoss.qkd.finite_key.expected_block_counts`,
which keeps a thousand-realisation day under half a gigabyte. Chunking changes
nothing about the result — the streams are spawned per pass and consumed
before the counts are evaluated — and ``TestReproducibility`` checks that a
different chunk size gives the same bits.
"""

_COUNT_PAIRS: Final[tuple[tuple[str, str], ...]] = (
    ("signal_detections", "signal_errors"),
    ("decoy_detections", "decoy_errors"),
    ("vacuum_detections", "vacuum_errors"),
)
"""The six columns of a :class:`~quoss.qkd.finite_key.BasisCounts`, paired for sampling.

Errors are a subset of detections, so the pairs are what the Poisson-then-
binomial draw needs; the same spelling-out as ``key_volume._BASIS_COUNT_FIELDS``
and for the same reason.
"""


# --------------------------------------------------------------------------- #
# Options
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class MonteCarloOptions:
    """How large the ensemble is and what is reported from it.

    Attributes
    ----------
    realisations : int
        Number of independent fade realisations per pass, ``R``, at least 1.
        Choose it with :func:`realisations_for_quantile`; 1000 covers a
        relative spread up to 15 % at a 1 % standard error on the P5.
    sample_counts : bool
        Draw the pooled block counts from their Poisson law (default) or use
        their expectations. ``False`` isolates the fading contribution to the
        spread, which is what ``TestWhatCorrelationChanges`` needs.
    quantiles : tuple of float
        Probabilities to report, each in ``[0, 1]``, strictly increasing so
        that the ordering of :attr:`MonteCarloKeyVolume.quantile_bits` is an
        invariant and not a convention. Default P5/P50/P95.
    chunk_elements : int
        Link evaluations per chunk; see :data:`DEFAULT_CHUNK_ELEMENTS`. Has no
        effect on the result.

    Raises
    ------
    DomainError
        If any field is outside its domain.

    Examples
    --------
    >>> MonteCarloOptions(realisations=1000)
    MonteCarloOptions(realisations=1000, sample_counts=True, quantiles=(0.05, 0.5, 0.95), chunk_elements=2000000)
    >>> MonteCarloOptions(realisations=1000, quantiles=(0.5, 0.05))
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: quantiles must be strictly increasing probabilities in [0, 1], got (0.5, 0.05). ...
    """

    realisations: int
    sample_counts: bool = True
    quantiles: tuple[float, ...] = DEFAULT_QUANTILES
    chunk_elements: int = DEFAULT_CHUNK_ELEMENTS

    def __post_init__(self) -> None:
        """Validate the ensemble size, the quantiles and the chunking."""
        count = int(self.realisations)
        if count < 1:
            raise DomainError(
                f"realisations must be at least 1, got {count}. An ensemble of none has no "
                "quantiles."
            )
        object.__setattr__(self, "realisations", count)
        object.__setattr__(self, "sample_counts", bool(self.sample_counts))
        probabilities = tuple(float(value) for value in self.quantiles)
        if (
            not probabilities
            or any(not np.isfinite(value) or not 0.0 <= value <= 1.0 for value in probabilities)
            or any(b <= a for a, b in pairwise(probabilities))
        ):
            raise DomainError(
                "quantiles must be strictly increasing probabilities in [0, 1], got "
                f"{self.quantiles}. Increasing, so that quantile_bits is ordered by "
                "construction; probabilities, so 5 % is 0.05 and not 5."
            )
        object.__setattr__(self, "quantiles", probabilities)
        chunk = int(self.chunk_elements)
        if chunk < 1:
            raise DomainError(f"chunk_elements must be at least 1, got {chunk}.")
        object.__setattr__(self, "chunk_elements", chunk)


# --------------------------------------------------------------------------- #
# Results
# --------------------------------------------------------------------------- #
def _validated_quantile_columns(
    quantiles: tuple[float, ...], quantile_bits: FloatArray, columns: int, label: str
) -> tuple[tuple[float, ...], FloatArray]:
    """Check that the quantile table has one row per probability and one column per unit."""
    probabilities = tuple(float(value) for value in quantiles)
    table = np.asarray(quantile_bits, dtype=np.float64)
    if table.shape != (len(probabilities), columns):
        raise DomainError(
            f"quantile_bits has shape {table.shape}, but there are {len(probabilities)} "
            f"quantiles and {columns} {label}."
        )
    if not np.all(np.isfinite(table)) or np.any(table < 0.0):
        raise DomainError("quantile_bits must be finite and non-negative.")
    if np.any(np.diff(table, axis=0) < 0.0):
        raise DomainError(
            "quantile_bits must be non-decreasing down the quantile axis: a P5 above a P95 is "
            "not a distribution."
        )
    return probabilities, frozen_view(table)


def _validated_per_unit(name: str, value: FloatArray, columns: int, label: str) -> FloatArray:
    """Return a finite non-negative ``(columns,)`` array, frozen."""
    array = np.asarray(value, dtype=np.float64)
    if array.shape != (columns,):
        raise DomainError(f"{name} has shape {array.shape}, but there are {columns} {label}.")
    if not np.all(np.isfinite(array)) or np.any(array < 0.0):
        raise DomainError(f"{name} must be finite and non-negative.")
    return frozen_view(array)


@dataclass(frozen=True, eq=False, slots=True)
class MonteCarloKeyVolume:
    """The ensemble of per-pass keys, its quantiles, and the two deterministic companions.

    Attributes
    ----------
    samples : PassSamples
        The ``(pass, sample)`` entries the ensemble was integrated over.
    key_bits : FloatArray
        Secret bits of every realisation of every pass, shape
        ``(realisations, n_passes)``. Whole numbers, never negative.
    quantiles : tuple of float
        The probabilities reported, increasing.
    quantile_bits : FloatArray
        The key at each probability, shape ``(len(quantiles), n_passes)``.
        Non-decreasing down the first axis.
    outage_probability : FloatArray
        Fraction of realisations in which each pass certified nothing, shape
        ``(n_passes,)``.
    mean_bits : FloatArray
        Mean over realisations per pass. Reported beside the median because the
        finite-key cliff makes the distribution skewed near it: a pass whose
        median is positive can have a mean pulled down by its outages.
    design : PassKeyVolume
        Today's number: :func:`~quoss.system.key_volume.pass_key_volume` at
        the design transmittance, the 1 % fade quantile held for the pass.
    expected : PassKeyVolume
        The same deterministic calculation at the **mean** transmittance. Not
        the mean of :attr:`key_bits` — the bound is not linear — but the
        number to compare the median against to see what fluctuation costs.
    finite : FiniteKeyResult
        Every term of the bound for every realisation and pass, shape
        ``(realisations, n_passes)``, so that an outage can be attributed.
    seed : int
        The seed that reproduces the ensemble.
    fading : FadingParameters
        The correlation times it was drawn with.
    sample_counts : bool
        Whether the block counts were Poisson-sampled.
    protocol : str
        Name of the protocol.

    Raises
    ------
    DomainError
        If the shapes disagree, any bits are negative or non-finite, the
        quantile table is not ordered, the outage is not a probability, or the
        companions are not finite-regime volumes over the same passes.
    """

    samples: PassSamples
    key_bits: FloatArray
    quantiles: tuple[float, ...]
    quantile_bits: FloatArray
    outage_probability: FloatArray
    mean_bits: FloatArray
    design: PassKeyVolume
    expected: PassKeyVolume
    finite: FiniteKeyResult
    seed: int
    fading: FadingParameters
    sample_counts: bool
    protocol: str

    def __post_init__(self) -> None:
        """Validate the shape contract, then freeze."""
        if not isinstance(self.samples, PassSamples):
            raise DomainError(f"samples must be a PassSamples, got {type(self.samples).__name__}.")
        n_passes = self.samples.table.n_passes
        bits = np.asarray(self.key_bits, dtype=np.float64)
        if bits.ndim != 2 or bits.shape[1] != n_passes:
            raise DomainError(
                f"key_bits must have shape (realisations, {n_passes}), got {bits.shape}."
            )
        if not np.all(np.isfinite(bits)) or np.any(bits < 0.0):
            raise DomainError("key_bits must be finite and non-negative.")
        object.__setattr__(self, "key_bits", frozen_view(bits))
        probabilities, table = _validated_quantile_columns(
            self.quantiles, self.quantile_bits, n_passes, "passes"
        )
        object.__setattr__(self, "quantiles", probabilities)
        object.__setattr__(self, "quantile_bits", table)
        outage = _validated_per_unit(
            "outage_probability", self.outage_probability, n_passes, "passes"
        )
        if np.any(outage > 1.0):
            raise DomainError("outage_probability must not exceed 1: it is a probability.")
        object.__setattr__(self, "outage_probability", outage)
        object.__setattr__(
            self, "mean_bits", _validated_per_unit("mean_bits", self.mean_bits, n_passes, "passes")
        )
        for name in ("design", "expected"):
            companion = getattr(self, name)
            if not isinstance(companion, PassKeyVolume):
                raise DomainError(
                    f"{name} must be a PassKeyVolume, got {type(companion).__name__}."
                )
            if companion.regime is not KeyRegime.FINITE or companion.n_passes != n_passes:
                raise DomainError(
                    f"{name} must be a FINITE volume over the same {n_passes} passes, got "
                    f"{companion!r}. The comparison the companions exist for is between the "
                    "same bound on the same blocks."
                )
        if not isinstance(self.finite, FiniteKeyResult) or self.finite.shape != bits.shape:
            raise DomainError(
                "finite must be the FiniteKeyResult of shape (realisations, n_passes) the bits "
                "came from."
            )
        if not isinstance(self.fading, FadingParameters):
            raise DomainError(
                f"fading must be a FadingParameters, got {type(self.fading).__name__}."
            )
        if not isinstance(self.protocol, str) or not self.protocol:
            raise DomainError(f"protocol must be a non-empty name, got {self.protocol!r}.")
        object.__setattr__(self, "seed", int(self.seed))
        object.__setattr__(self, "sample_counts", bool(self.sample_counts))

    @property
    def realisations(self) -> int:
        """``R``, the number of realisations."""
        return int(self.key_bits.shape[0])

    @property
    def n_passes(self) -> int:
        """``P``, the number of passes."""
        return int(self.key_bits.shape[1])

    @property
    def regime(self) -> KeyRegime:
        """Always :attr:`~quoss.qkd.base.KeyRegime.FINITE`: every realisation is a block."""
        return KeyRegime.FINITE

    @property
    def security(self) -> SecurityParameters:
        """The per-block failure probabilities every realisation is a claim under."""
        return self.finite.security

    @property
    def design_bits(self) -> FloatArray:
        """Today's number per pass: the key at the 1 % fade quantile held for the pass."""
        return self.design.key_bits

    @property
    def expected_bits(self) -> FloatArray:
        """The deterministic key at the mean transmittance, per pass."""
        return self.expected.key_bits

    def __repr__(self) -> str:
        return (
            f"MonteCarloKeyVolume({self.protocol!r}, realisations={self.realisations}, "
            f"n_passes={self.n_passes}, median_total={float(np.median(self.key_bits.sum(axis=1))):.3e}, "
            f"seed={self.seed})"
        )


@dataclass(frozen=True, eq=False, slots=True)
class MonteCarloDailyKeyVolume:
    """The ensemble of daily keys, with the composed security claim of a day.

    Attributes
    ----------
    day_number : IntArray
        Julian Day Number of each day holding a pass, ascending.
    key_bits : FloatArray
        Daily key of every realisation, shape ``(realisations, n_days)``: the
        passes of a day summed within each realisation, so that the day's
        quantiles are quantiles of a **sum** and not sums of quantiles — a P5
        of a sum is above the sum of the P5s whenever the passes are not
        perfectly correlated, and the difference is measured in
        ``TestComposingADay``.
    quantiles, quantile_bits, outage_probability, mean_bits
        As in :class:`MonteCarloKeyVolume`, per day. Outage is the fraction of
        realisations in which the whole day certified nothing.
    expected_bits, design_bits : FloatArray
        The two deterministic companions summed per day.
    pass_count : IntArray
        Passes in each day.
    security : SecurityParameters
        The composed failure probabilities of the busiest day, from
        :func:`~quoss.system.key_volume.composed_security`, for the reason
        :class:`~quoss.system.key_volume.DailyKeyVolume` gives.
    seed, protocol
        Inherited.

    Raises
    ------
    DomainError
        If the shapes disagree or any column is outside its domain.
    """

    day_number: IntArray
    key_bits: FloatArray
    quantiles: tuple[float, ...]
    quantile_bits: FloatArray
    outage_probability: FloatArray
    mean_bits: FloatArray
    expected_bits: FloatArray
    design_bits: FloatArray
    pass_count: IntArray
    security: SecurityParameters
    seed: int
    protocol: str

    def __post_init__(self) -> None:
        """Validate the columns, then freeze."""
        days = np.asarray(self.day_number, dtype=np.int64)
        if days.ndim != 1 or (days.size and not np.all(np.diff(days) > 0)):
            raise DomainError("day_number must be a 1-D strictly ascending array.")
        object.__setattr__(self, "day_number", days)
        n_days = int(days.size)
        bits = np.asarray(self.key_bits, dtype=np.float64)
        if bits.ndim != 2 or bits.shape[1] != n_days:
            raise DomainError(
                f"key_bits must have shape (realisations, {n_days}), got {bits.shape}."
            )
        if not np.all(np.isfinite(bits)) or np.any(bits < 0.0):
            raise DomainError("key_bits must be finite and non-negative.")
        object.__setattr__(self, "key_bits", frozen_view(bits))
        probabilities, table = _validated_quantile_columns(
            self.quantiles, self.quantile_bits, n_days, "days"
        )
        object.__setattr__(self, "quantiles", probabilities)
        object.__setattr__(self, "quantile_bits", table)
        for name in ("outage_probability", "mean_bits", "expected_bits", "design_bits"):
            object.__setattr__(
                self, name, _validated_per_unit(name, getattr(self, name), n_days, "days")
            )
        if np.any(self.outage_probability > 1.0):
            raise DomainError("outage_probability must not exceed 1: it is a probability.")
        counts = np.asarray(self.pass_count, dtype=np.int64)
        if counts.shape != (n_days,) or np.any(counts < 1):
            raise DomainError(
                f"pass_count must have shape ({n_days},) with at least one pass per day: a day "
                "with no pass does not appear in the table."
            )
        object.__setattr__(self, "pass_count", counts)
        if not isinstance(self.security, SecurityParameters):
            raise DomainError(
                f"security must be a SecurityParameters, got {type(self.security).__name__}. A "
                "day's key is a concatenation of blocks and travels with its composed eps."
            )
        if not isinstance(self.protocol, str) or not self.protocol:
            raise DomainError(f"protocol must be a non-empty name, got {self.protocol!r}.")
        object.__setattr__(self, "seed", int(self.seed))

    @property
    def realisations(self) -> int:
        """``R``."""
        return int(self.key_bits.shape[0])

    @property
    def n_days(self) -> int:
        """Number of days with at least one pass."""
        return int(self.day_number.size)

    @property
    def regime(self) -> KeyRegime:
        """Always :attr:`~quoss.qkd.base.KeyRegime.FINITE`."""
        return KeyRegime.FINITE

    def __repr__(self) -> str:
        return (
            f"MonteCarloDailyKeyVolume({self.protocol!r}, realisations={self.realisations}, "
            f"n_days={self.n_days}, seed={self.seed})"
        )


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _validated_samples(samples: PassSamples, conditions: LinkConditions) -> None:
    """Check the contract of ``key_volume.py``: conditions in sample order, one per entry."""
    if not isinstance(samples, PassSamples):
        raise DomainError(f"samples must be a PassSamples, got {type(samples).__name__}.")
    if not isinstance(conditions, LinkConditions):
        raise DomainError(f"conditions must be a LinkConditions, got {type(conditions).__name__}.")
    if conditions.shape != samples.shape:
        raise DomainError(
            f"conditions has shape {conditions.shape} but there are {samples.size} (pass, "
            f"sample) entries. As in key_volume.pass_key_volume, the caller evaluates the "
            "channel at samples.satellite_index and samples.sample_index, in that order; the "
            "order is part of the contract because a matching length in a different order is "
            "undetectable."
        )
    if samples.size == 0:
        raise DomainError("samples is empty: there are no passes to draw an ensemble over.")


def _per_sample(
    name: str, value: FloatArray | float, n: int, *, minimum: float, strict: bool
) -> FloatArray:
    """Broadcast a per-sample fade input to ``(n,)`` and check its range."""
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise DomainError(f"{name} contains non-finite values.")
    if (strict and np.any(array <= minimum)) or (not strict and np.any(array < minimum)):
        bound = "strictly above" if strict else "at least"
        raise DomainError(f"{name} must be {bound} {minimum}, got a value below that.")
    try:
        return np.broadcast_to(array, (n,)).astype(np.float64)
    except ValueError as exc:
        raise DomainError(
            f"{name} has shape {array.shape} and must broadcast to ({n},): one value per "
            "(pass, sample) entry, evaluated at the same instants as the conditions, or one "
            "for all of them."
        ) from exc


def _with_transmittance(conditions: LinkConditions, transmittance: FloatArray) -> LinkConditions:
    """Return the same link with another transmittance array."""
    return LinkConditions(
        transmittance=transmittance,
        noise_counts_per_gate=conditions.noise_counts_per_gate,
        misalignment_error=conditions.misalignment_error,
        pulse_rate_hz=conditions.pulse_rate_hz,
        gate_duration_s=conditions.gate_duration_s,
    )


def _row_sums(values: FloatArray) -> FloatArray:
    """Sum each row of a ``(rows, n)`` array in the order ``key_volume`` sums a pass.

    :func:`numpy.bincount` rather than :meth:`numpy.ndarray.sum`, because the
    latter is pairwise and the former accumulates in index order — which is what
    :meth:`~quoss.system.passes.PassSamples.segment_sum` does for a pass, so
    that a realisation whose fade factor is exactly one reproduces
    :func:`~quoss.system.key_volume.pass_key_volume` **bit for bit** rather than
    to rounding. ``TestReproducesTheDeterministicVolume`` asserts equality, not
    closeness, and this is why it can.
    """
    rows, n = values.shape
    labels = np.repeat(np.arange(rows, dtype=np.int64), n)
    summed: FloatArray = np.asarray(
        np.bincount(labels, weights=values.ravel(), minlength=rows), dtype=np.float64
    )
    return summed


def _sample_counts(
    rng: np.random.Generator, detections: FloatArray, errors: FloatArray
) -> tuple[FloatArray, FloatArray]:
    """Draw ``Poisson(detections)`` and ``Binomial(drawn, errors / detections)``."""
    drawn = rng.poisson(detections)
    rate = np.where(detections > 0.0, errors / np.where(detections > 0.0, detections, 1.0), 0.0)
    wrong = rng.binomial(drawn, np.clip(rate, 0.0, 1.0))
    return drawn.astype(np.float64), wrong.astype(np.float64)


def realisations_for_quantile(
    relative_spread: float, *, probability: float, relative_precision: float
) -> int:
    r"""Return the ensemble size that pins a quantile to a target standard error.

    The order-statistic standard error under a normal approximation,
    ``SE(q_p) = (SD / phi(z_p)) sqrt(p (1 - p) / R)``, solved for ``R`` with
    both sides divided by the median::

        R = p(1 - p)(spread / precision) ^ 2 / phi(z_p) ^ 2

    where ``spread`` is ``SD / median``, ``precision`` the target ``SE /
    median``, ``z_p`` the standard normal quantile and ``phi`` its density.
    It is a criterion rather than a taste: run a pilot, read the spread, and
    the size follows. The normal approximation is the weak point — a key
    distribution near the finite-key cliff is skewed — which is why
    :func:`quantile_standard_error` exists to check the answer by bootstrap on
    the ensemble actually drawn.

    Parameters
    ----------
    relative_spread : float
        Standard deviation of the key over the median, strictly positive.
    probability : float
        The quantile, in ``(0, 1)``.
    relative_precision : float
        Target standard error of the quantile over the median, strictly
        positive.

    Returns
    -------
    int
        The smallest ``R`` meeting the target, at least 2.

    Raises
    ------
    DomainError
        If any argument is outside its domain.

    Examples
    --------
    A 10 % relative spread pinned to a 1 % standard error on the P5:

    >>> realisations_for_quantile(0.10, probability=0.05, relative_precision=0.01)
    447

    The median is cheaper than the tails, and a tighter distribution needs far
    fewer draws — the size goes as the square of the spread:

    >>> realisations_for_quantile(0.10, probability=0.5, relative_precision=0.01)
    158
    >>> realisations_for_quantile(0.02, probability=0.05, relative_precision=0.01)
    18
    """
    spread = float(relative_spread)
    p = float(probability)
    precision = float(relative_precision)
    if not np.isfinite(spread) or spread <= 0.0:
        raise DomainError(f"relative_spread must be finite and strictly positive, got {spread}.")
    if not np.isfinite(p) or not 0.0 < p < 1.0:
        raise DomainError(
            f"probability must lie in (0, 1), got {p}: the extremes have no finite standard "
            "error under this formula."
        )
    if not np.isfinite(precision) or precision <= 0.0:
        raise DomainError(
            f"relative_precision must be finite and strictly positive, got {precision}."
        )
    z = float(ndtri(p))
    density = float(np.exp(-0.5 * z * z) / np.sqrt(2.0 * np.pi))
    required = p * (1.0 - p) * (spread / precision) ** 2 / density**2
    return max(2, int(np.ceil(required)))


def quantile_standard_error(
    key_bits: FloatArray, probability: float, *, rng: np.random.Generator, resamples: int = 200
) -> FloatArray:
    """Return the bootstrap standard error of a quantile of each column of ``key_bits``.

    Resample the realisation axis with replacement ``resamples`` times, take the
    quantile of each resample, and report the standard deviation across
    resamples. The estimate a study should print beside a P5, and the check on
    :func:`realisations_for_quantile`'s normal approximation.

    Parameters
    ----------
    key_bits : FloatArray
        Shape ``(realisations, columns)``; :attr:`MonteCarloKeyVolume.key_bits`
        or :attr:`MonteCarloDailyKeyVolume.key_bits`.
    probability : float
        The quantile, in ``[0, 1]``.
    rng : numpy.random.Generator
        Injected generator for the resampling.
    resamples : int
        Bootstrap resamples, at least 2.

    Returns
    -------
    FloatArray
        One standard error per column.

    Raises
    ------
    DomainError
        If the shape is not 2-D, the probability is outside ``[0, 1]``, or
        ``resamples`` is below 2.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.rng import RandomSource
    >>> draws = RandomSource.from_seed(1).generator.normal(1000.0, 100.0, size=(400, 1))
    >>> se = quantile_standard_error(draws, 0.05, rng=RandomSource.from_seed(2).generator)
    >>> bool(5.0 < float(se[0]) < 20.0)
    True
    """
    bits = np.asarray(key_bits, dtype=np.float64)
    if bits.ndim != 2:
        raise DomainError(f"key_bits must be 2-D, (realisations, columns), got shape {bits.shape}.")
    p = float(probability)
    if not np.isfinite(p) or not 0.0 <= p <= 1.0:
        raise DomainError(f"probability must lie in [0, 1], got {p}.")
    count = int(resamples)
    if count < 2:
        raise DomainError(f"resamples must be at least 2, got {count}.")
    if not isinstance(rng, np.random.Generator):
        raise DomainError(f"rng must be a numpy.random.Generator, got {type(rng).__name__}.")
    realisations = bits.shape[0]
    picks = rng.integers(0, realisations, size=(count, realisations))
    resampled = np.quantile(bits[picks], p, axis=1)
    error: FloatArray = np.std(resampled, axis=0, ddof=1)
    return error


# --------------------------------------------------------------------------- #
# The ensemble
# --------------------------------------------------------------------------- #
def monte_carlo_pass_key_volume(
    conditions: LinkConditions,
    *,
    samples: PassSamples,
    nominal_fade_db: FloatArray | float,
    log_irradiance_variance_np2: FloatArray | float,
    beam_to_jitter_ratio: FloatArray | float,
    protocol: Bb84DecoyProtocol,
    security: SecurityParameters,
    fading: FadingParameters,
    options: MonteCarloOptions,
    random_source: RandomSource,
    degradations: DegradationLog,
    key_basis_probability: float = SYMMETRIC_KEY_BASIS_PROBABILITY,
) -> MonteCarloKeyVolume:
    r"""Draw an ensemble of fading passes and return the distribution of their keys.

    How it works
    ------------
    1. **Take the fade allowance back out.** ``eta_free = transmittance *
       10^(fade_db / 10)`` per sample. The design number and the deterministic
       key at the mean transmittance are computed here as companions, with
       :func:`~quoss.system.key_volume.pass_key_volume` unchanged.
    2. **Per pass, one spawned stream.** ``random_source.spawn(P)`` gives each
       pass an independent child; its generator draws that pass's fade
       realisations (:func:`~quoss.system.correlated_fading.sample_fade_factors`
       with the dwell times, one call over all realisations) and, if asked,
       the Poisson counts. The chunking of the counts evaluation between the
       two consumes no randomness, so the ensemble is a function of the seed
       and the pass table alone.
    3. **Counts per realisation and sample**, from
       :func:`~quoss.qkd.finite_key.expected_block_counts` over a
       ``(chunk, n_pass)`` :class:`~quoss.qkd.base.LinkConditions`; pooled per
       pass with the same index-ordered sum ``key_volume.py`` uses.
    4. **One block per realisation and pass**, then
       :func:`~quoss.qkd.finite_key.secret_key_length` once over the whole
       ``(R, P)`` array.
    5. Quantiles along the realisation axis, the outage as the fraction of
       zeros, the mean.

    The process is restarted at every pass. The gap between passes is hours,
    and ``exp(-gap / tau)`` is below ``1e-15`` for any ``tau`` under a
    thirty-fifth of the gap; when it is not, the log says so.

    Parameters
    ----------
    conditions : LinkConditions
        The design conditions at each ``(pass, sample)`` entry, shape
        ``(samples.size,)``, in ``samples`` order — exactly what
        :func:`~quoss.system.key_volume.pass_key_volume` takes. Its
        transmittance **includes** the fade allowance.
    samples : PassSamples
        From :meth:`~quoss.system.passes.PassTable.samples`.
    nominal_fade_db : FloatArray or float
        :attr:`~quoss.channel.link_budget.LossBudget.fade_db` at the same
        entries: the allowance to remove. Shape ``(samples.size,)`` or scalar.
    log_irradiance_variance_np2 : FloatArray or float
        ``sigma^2`` at the same entries, Np^2, non-negative.
    beam_to_jitter_ratio : FloatArray or float
        ``gamma`` at the same entries, strictly positive.
    protocol : Bb84DecoyProtocol
        Drives the counts and the bound, as in ``key_volume.py``.
    security : SecurityParameters
        Per-block failure probabilities, per pass.
    fading : FadingParameters
        The two correlation times.
    options : MonteCarloOptions
        Ensemble size, count sampling, quantiles, chunking.
    random_source : RandomSource
        The seeded source; its seed goes into the result.
    degradations : DegradationLog
        Receives the bound's own clamps, a summary of the ensemble against
        its two companions, and warnings if any realisation's transmittance
        had to be clipped at one or the correlation times are not short
        against the gaps between passes.
    key_basis_probability : float, optional
        ``q_x``, as in ``key_volume.py``.

    Returns
    -------
    MonteCarloKeyVolume
        The ensemble.

    Raises
    ------
    DomainError
        If any argument fails its guard, or if removing the allowance would
        put a transmittance above one — which means the allowance and the
        conditions did not come from the same budget.

    Examples
    --------
    The reference day, two hundred realisations at millisecond correlation
    times:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.rng import RandomSource
    >>> from quoss.qkd.bb84 import Bb84DecoyProtocol
    >>> from quoss.qkd.finite_key import SecurityParameters
    >>> from quoss.system.correlated_fading import FadingParameters
    >>> samples, conditions, fade_db, variance, gamma = _reference_fading_inputs()
    >>> volume = monte_carlo_pass_key_volume(
    ...     conditions,
    ...     samples=samples,
    ...     nominal_fade_db=fade_db,
    ...     log_irradiance_variance_np2=variance,
    ...     beam_to_jitter_ratio=gamma,
    ...     protocol=Bb84DecoyProtocol.ntanos_2021(),
    ...     security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
    ...     fading=FadingParameters(
    ...         scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=0.02
    ...     ),
    ...     options=MonteCarloOptions(realisations=200),
    ...     random_source=RandomSource.from_seed(20260913),
    ...     degradations=DegradationLog(),
    ... )
    >>> volume.key_bits.shape
    (200, 4)
    >>> volume.design_bits
    array([190581.,      0., 242404.,      0.])
    >>> volume.expected_bits
    array([346063.,      0., 412644.,      0.])

    The design number sits far below the P5 of the two live passes, and the
    two dead passes are dead in every realisation:

    >>> bool(np.all(volume.quantile_bits[0, [0, 2]] > volume.design_bits[[0, 2]]))
    True
    >>> volume.outage_probability
    array([0., 1., 0., 1.])
    """
    _validated_samples(samples, conditions)
    settings = decoy_settings_from_protocol(protocol)
    if not isinstance(security, SecurityParameters):
        raise DomainError(f"security must be a SecurityParameters, got {type(security).__name__}.")
    if not isinstance(fading, FadingParameters):
        raise DomainError(f"fading must be a FadingParameters, got {type(fading).__name__}.")
    if not isinstance(options, MonteCarloOptions):
        raise DomainError(f"options must be a MonteCarloOptions, got {type(options).__name__}.")
    if not isinstance(random_source, RandomSource):
        raise DomainError(
            f"random_source must be a RandomSource, got {type(random_source).__name__}. The "
            "seed is part of the result's provenance, and only the source carries it."
        )
    n = samples.size
    n_passes = samples.table.n_passes
    fade_db = _per_sample("nominal_fade_db", nominal_fade_db, n, minimum=-np.inf, strict=True)
    variance = _per_sample(
        "log_irradiance_variance_np2", log_irradiance_variance_np2, n, minimum=0.0, strict=False
    )
    gamma = _per_sample("beam_to_jitter_ratio", beam_to_jitter_ratio, n, minimum=0.0, strict=True)

    eta_free = np.asarray(conditions.transmittance) * 10.0 ** (fade_db / 10.0)
    if np.any(eta_free > 1.0):
        raise DomainError(
            "removing nominal_fade_db from conditions.transmittance gives a transmittance above "
            f"1 (largest {float(eta_free.max()):.4g}). The allowance and the conditions must "
            "come from the same LossBudget: fade_db is inside LossBudget.transmittance, and "
            "taking out more than was put in is not a fade-free link but a different one."
        )
    mean_pointing = gamma**2 / (gamma**2 + 1.0)
    q_x = float(key_basis_probability)

    design = pass_key_volume(
        conditions,
        samples=samples,
        protocol=protocol,
        security=security,
        degradations=DegradationLog(),
        key_basis_probability=q_x,
    )
    expected = pass_key_volume(
        _with_transmittance(conditions, eta_free * mean_pointing),
        samples=samples,
        protocol=protocol,
        security=security,
        degradations=DegradationLog(),
        key_basis_probability=q_x,
    )

    realisations = options.realisations
    dwell = np.asarray(samples.dwell_s, dtype=np.float64)
    pulses = conditions.pulse_rate_hz * dwell
    t_s = np.asarray(samples.table.grid.t_s, dtype=np.float64)[samples.sample_index]
    noise = np.asarray(conditions.noise_counts_per_gate)
    misalignment = np.asarray(conditions.misalignment_error)
    boundaries = np.searchsorted(samples.pass_index, np.arange(n_passes + 1))
    children = random_source.spawn(n_passes)

    columns: dict[tuple[str, str], FloatArray] = {
        (basis, column): np.empty((realisations, n_passes), dtype=np.float64)
        for basis in ("key_basis", "check_basis")
        for pair in _COUNT_PAIRS
        for column in pair
    }
    clipped = 0
    for index in range(n_passes):
        start, stop = int(boundaries[index]), int(boundaries[index + 1])
        rows = slice(start, stop)
        n_pass = stop - start
        generator = children[index].generator
        fades = sample_fade_factors(
            t_s[rows],
            realisations=realisations,
            log_irradiance_variance_np2=variance[rows],
            beam_to_jitter_ratio=gamma[rows],
            parameters=fading,
            rng=generator,
            degradations=degradations,
            dwell_s=dwell[rows],
        )
        eta = eta_free[rows] * fades.factor
        clipped += int(np.count_nonzero(eta > 1.0))
        eta = np.minimum(eta, 1.0)

        chunk = max(1, options.chunk_elements // n_pass)
        for first in range(0, realisations, chunk):
            last = min(first + chunk, realisations)
            block = expected_block_counts(
                LinkConditions(
                    transmittance=eta[first:last],
                    noise_counts_per_gate=noise[rows],
                    misalignment_error=misalignment[rows],
                    pulse_rate_hz=conditions.pulse_rate_hz,
                    gate_duration_s=conditions.gate_duration_s,
                ),
                settings=settings,
                key_basis_probability=q_x,
                pulses=pulses[rows],
            )
            for basis in ("key_basis", "check_basis"):
                counts = getattr(block, basis)
                for pair in _COUNT_PAIRS:
                    for column in pair:
                        columns[(basis, column)][first:last, index] = _row_sums(
                            np.asarray(getattr(counts, column), dtype=np.float64)
                        )
        if options.sample_counts:
            for basis in ("key_basis", "check_basis"):
                for detections_name, errors_name in _COUNT_PAIRS:
                    drawn, wrong = _sample_counts(
                        generator,
                        columns[(basis, detections_name)][:, index],
                        columns[(basis, errors_name)][:, index],
                    )
                    columns[(basis, detections_name)][:, index] = drawn
                    columns[(basis, errors_name)][:, index] = wrong

    pooled_pulses = np.broadcast_to(samples.segment_sum(pulses), (realisations, n_passes))
    block = DecoyBlockCounts(
        key_basis=BasisCounts(
            **{column: columns[("key_basis", column)] for pair in _COUNT_PAIRS for column in pair}
        ),
        check_basis=BasisCounts(
            **{column: columns[("check_basis", column)] for pair in _COUNT_PAIRS for column in pair}
        ),
        pulses=np.array(pooled_pulses, dtype=np.float64),
    )
    result = secret_key_length(
        block,
        settings=settings,
        security=security,
        error_correction_efficiency=protocol.error_correction_efficiency,
        degradations=degradations,
    )
    key_bits = np.asarray(result.length_bits, dtype=np.float64)
    quantile_bits = np.quantile(key_bits, options.quantiles, axis=0)
    outage = np.mean(key_bits == 0.0, axis=0)
    mean_bits = np.mean(key_bits, axis=0)

    if clipped:
        degradations.warn(
            "monte_carlo.transmittance-clipped",
            f"{clipped} of {realisations * n} (realisation, sample) transmittances exceeded 1 "
            "after the fade factor was applied and were clipped to 1. A scintillation boost "
            "cannot deliver more than the source sent; if this is more than a handful the "
            "fade-free transmittance is close to one and this link is not the one this model "
            "was built for.",
            where="quoss.system.monte_carlo.monte_carlo_pass_key_volume",
            clipped=clipped,
            evaluations=realisations * n,
        )
    table = samples.table
    if n_passes > 1:
        order = np.argsort(table.start_s)
        gaps = table.start_s[order][1:] - table.end_s[order][:-1]
        shortest_gap = float(gaps.min())
        longest_tau = max(
            fading.scintillation_correlation_time_s, fading.pointing_correlation_time_s
        )
        survival = float(np.exp(-shortest_gap / longest_tau))
        if survival > 1e-6:
            degradations.warn(
                "monte_carlo.passes-not-independent",
                f"the fade process is restarted at every pass, but the longest correlation "
                f"time ({longest_tau:g} s) is not short against the shortest gap between "
                f"passes ({shortest_gap:.0f} s): a correlation of {survival:.2e} between the "
                "end of one pass and the start of the next was dropped. The per-pass "
                "quantiles are unaffected; the day's are slightly too narrow.",
                where="quoss.system.monte_carlo.monte_carlo_pass_key_volume",
                shortest_gap_s=shortest_gap,
                longest_correlation_time_s=longest_tau,
                dropped_correlation=survival,
            )
    median = np.quantile(key_bits, 0.5, axis=0)
    degradations.info(
        "monte_carlo.ensemble-summary",
        f"{realisations} realisations over {n_passes} passes at correlation times "
        f"{fading.scintillation_correlation_time_s:g} s (scintillation) and "
        f"{fading.pointing_correlation_time_s:g} s (pointing), counts "
        f"{'Poisson-sampled' if options.sample_counts else 'at expectation'}. Median total "
        f"{float(np.median(key_bits.sum(axis=1))):.0f} bits against {design.total_bits:.0f} at "
        f"the design (1 % fade) transmittance and {expected.total_bits:.0f} at the mean "
        f"transmittance; {int(np.count_nonzero(outage == 1.0))} passes certify nothing in "
        "every realisation.",
        where="quoss.system.monte_carlo.monte_carlo_pass_key_volume",
        realisations=realisations,
        median_bits=[float(value) for value in median],
        outage_probability=[float(value) for value in outage],
        design_bits=[float(value) for value in design.key_bits],
        expected_bits=[float(value) for value in expected.key_bits],
        seed=random_source.seed,
    )
    return MonteCarloKeyVolume(
        samples=samples,
        key_bits=key_bits,
        quantiles=options.quantiles,
        quantile_bits=np.asarray(quantile_bits, dtype=np.float64),
        outage_probability=np.asarray(outage, dtype=np.float64),
        mean_bits=np.asarray(mean_bits, dtype=np.float64),
        design=design,
        expected=expected,
        finite=result,
        seed=random_source.seed,
        fading=fading,
        sample_counts=options.sample_counts,
        protocol=protocol.name,
    )


def monte_carlo_daily_key_volume(
    volume: MonteCarloKeyVolume, *, degradations: DegradationLog
) -> MonteCarloDailyKeyVolume:
    """Sum each realisation's passes by UTC day, then take the day's quantiles.

    **Quantiles of sums, not sums of quantiles.** The P5 of a day is the P5 of
    the distribution of ``sum over passes`` within a realisation; adding the
    per-pass P5s instead assumes every pass has its bad night on the same
    night, which is a lower bound and a loose one. The difference is measured
    in ``TestComposingADay``.

    The day of a pass and the composed security claim follow
    :func:`~quoss.system.key_volume.daily_key_volume` exactly, for the reasons
    given there.

    Parameters
    ----------
    volume : MonteCarloKeyVolume
        The per-pass ensemble.
    degradations : DegradationLog
        Receives the composed ``eps``.

    Returns
    -------
    MonteCarloDailyKeyVolume
        One column per UTC day with at least one pass.

    Raises
    ------
    DomainError
        If ``volume`` is not a :class:`MonteCarloKeyVolume`, or the composition
        would make the failure probability reach one.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> volume = _reference_monte_carlo()
    >>> daily = monte_carlo_daily_key_volume(volume, degradations=DegradationLog())
    >>> daily.day_number, daily.key_bits.shape
    (array([2460677]), (200, 1))
    >>> float(daily.design_bits[0]), float(daily.expected_bits[0])
    (432985.0, 758707.0)
    >>> f"{daily.security.secrecy:.1e}"
    '4.0e-10'
    """
    if not isinstance(volume, MonteCarloKeyVolume):
        raise DomainError(f"volume must be a MonteCarloKeyVolume, got {type(volume).__name__}.")
    day_of_pass = volume.samples.table.day_number
    days, inverse = np.unique(day_of_pass, return_inverse=True)
    n_days = int(days.size)
    indicator = np.zeros((volume.n_passes, n_days), dtype=np.float64)
    indicator[np.arange(volume.n_passes), inverse] = 1.0
    key_bits = volume.key_bits @ indicator
    pass_count = np.bincount(inverse, minlength=n_days).astype(np.int64)
    security = composed_security(volume.security, int(pass_count.max()))
    degradations.info(
        "monte_carlo.day-composes-blocks",
        f"each day's key is the concatenation of up to {int(pass_count.max())} blocks, so the "
        f"failure probabilities compose to eps_sec = {security.secrecy:.3e}, "
        f"eps_cor = {security.correctness:.3e}; the day's quantiles are quantiles of the "
        "per-realisation sum, not sums of per-pass quantiles.",
        where="quoss.system.monte_carlo.monte_carlo_daily_key_volume",
        blocks=int(pass_count.max()),
        composed_secrecy=security.secrecy,
    )
    return MonteCarloDailyKeyVolume(
        day_number=days.astype(np.int64),
        key_bits=key_bits,
        quantiles=volume.quantiles,
        quantile_bits=np.asarray(np.quantile(key_bits, volume.quantiles, axis=0), dtype=np.float64),
        outage_probability=np.asarray(np.mean(key_bits == 0.0, axis=0), dtype=np.float64),
        mean_bits=np.asarray(np.mean(key_bits, axis=0), dtype=np.float64),
        expected_bits=volume.expected_bits @ indicator,
        design_bits=volume.design_bits @ indicator,
        pass_count=pass_count,
        security=security,
        seed=volume.seed,
        protocol=volume.protocol,
    )


# --------------------------------------------------------------------------- #
# Reference link for the doctests above, built on key_volume's helper so that
# there is one reference satellite and station in this package.
# --------------------------------------------------------------------------- #
def _reference_fading_inputs() -> tuple[
    PassSamples, LinkConditions, FloatArray, FloatArray, FloatArray
]:
    """Return the reference day's samples, conditions, fade allowance, sigma^2 and gamma.

    Examples
    --------
    >>> samples, conditions, fade_db, variance, gamma = _reference_fading_inputs()
    >>> fade_db.shape == variance.shape == gamma.shape == conditions.shape
    True
    """
    from quoss.channel.detector import (
        NTANOS_FILTER_INSERTION_LOSS_DB,
        NTANOS_RECEIVER_LOSS_DB,
        NTANOS_SNSPD_EFFICIENCY,
        receiver_efficiency,
    )
    from quoss.channel.link_budget import (
        NTANOS_POINTING_JITTER_RAD,
        NTANOS_TRANSMIT_APERTURE_M,
        downlink_loss_budget,
    )
    from quoss.channel.pointing import beam_to_jitter_ratio
    from quoss.channel.turbulence import downlink_log_irradiance_variance
    from quoss.system.key_volume import _reference_conditions
    from quoss.system.passes import _reference_geometry

    wavelength_m = 1.55e-6
    aperture_m = 0.75
    samples, conditions = _reference_conditions()
    angles, _ = _reference_geometry()
    rows = (samples.satellite_index, samples.sample_index)
    elevation = np.asarray(angles.elevation_rad)[rows]
    slant_range = np.asarray(angles.range_km)[rows]
    log = DegradationLog()
    chain = receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )
    loss = downlink_loss_budget(
        elevation,
        range_km=slant_range,
        wavelength_m=wavelength_m,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=aperture_m,
        zenith_transmittance=1.0,
        pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
        receiver_efficiency=chain,
        degradations=log,
    )
    variance = downlink_log_irradiance_variance(
        elevation, aperture_diameter_m=aperture_m, wavelength_m=wavelength_m, degradations=log
    )
    gamma = beam_to_jitter_ratio(
        slant_range,
        jitter_rad=NTANOS_POINTING_JITTER_RAD,
        wavelength_m=wavelength_m,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=aperture_m,
        degradations=log,
    )
    return (
        samples,
        conditions,
        np.asarray(loss.fade_db, dtype=np.float64),
        np.asarray(variance, dtype=np.float64),
        np.asarray(gamma, dtype=np.float64),
    )


def _reference_monte_carlo() -> MonteCarloKeyVolume:
    """Return the reference day's ensemble at 200 realisations.

    Examples
    --------
    >>> _reference_monte_carlo().realisations
    200
    """
    samples, conditions, fade_db, variance, gamma = _reference_fading_inputs()
    return monte_carlo_pass_key_volume(
        conditions,
        samples=samples,
        nominal_fade_db=fade_db,
        log_irradiance_variance_np2=variance,
        beam_to_jitter_ratio=gamma,
        protocol=Bb84DecoyProtocol.ntanos_2021(),
        security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
        fading=FadingParameters(
            scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=0.02
        ),
        options=MonteCarloOptions(realisations=200),
        random_source=RandomSource.from_seed(20260913),
        degradations=DegradationLog(),
    )
