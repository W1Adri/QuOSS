"""The protocol boundary: what a key rate is computed from, and what comes back.

What this module is for
-----------------------
:mod:`quoss.channel` finishes with two numbers at every instant of a pass: the
fraction of the photons leaving the satellite that reach a detector, and the
mean number of counts per detection gate that are **not** signal. A QKD protocol
turns that pair into two more numbers: a secret key rate and an error rate. This
module is the seam between the two halves. It defines what crosses it
(:class:`LinkConditions`), what comes back (:class:`KeyRate`), the interface an
implementation fills in (:class:`QkdProtocol`), and the table that maps a name in
a scenario file to an implementation (:class:`ProtocolRegistry`).

There is no physics here. Every formula that says something about BB84 lives in
``bb84.py``; what lives here is the shape of the conversation and the three
mistakes that are easy to make while having it.

The vocabulary, assuming none of it
-----------------------------------
**QKD** is a way for two parties — Alice on the satellite, Bob on the ground —
to end up holding the same random bit string while being able to *bound* how
much of it an eavesdropper could know. Alice sends single photons (or dim laser
pulses standing in for them) prepared in one of several polarisation states; Bob
measures them. Quantum mechanics does the work: measuring an unknown photon
disturbs it, so eavesdropping shows up as errors.

- **Gate.** The short window in which the receiver is willing to believe a click
  came from the pulse Alice sent. One gate per pulse. Narrowing it throws away
  background light, which is why :mod:`quoss.channel.background` treats the gate
  as the noise budget's only free parameter.
- **Gain** (symbol ``Q``). The probability that a gate produces a click at all,
  from any cause. Dimensionless, in ``[0, 1]``, and per *pulse*, not per second.
- **Yield** (symbol ``Y``). The same idea conditioned on what Alice sent: the
  probability of a click given that she sent ``n`` photons. ``Y_0`` — the yield
  when she sent **nothing** — is the noise, and is the only yield this module
  computes, because it is the only one that follows from the channel alone.
- **Sifting.** Alice and Bob choose measurement bases at random and afterwards
  announce the choices, keeping only the pulses where they happened to agree.
  The kept fraction is the sifted key; for symmetric BB84 it is half.
- **QBER** — quantum bit error rate. The fraction of the sifted bits on which
  they disagree. It is a *fraction*, not a rate per second: 11 % is ``0.11``. Two
  things produce it, and they behave differently. A background count is
  uncorrelated with what Alice sent, so it lands on the wrong bit half the time.
  A misaligned polarisation reference corrupts the signal photons *themselves*,
  so it does not wash out as the link improves.
- **Secret key rate.** What survives after Alice and Bob spend part of the sifted
  key correcting their errors and the rest of it shrinking whatever the
  eavesdropper might know to nothing. That second step is *privacy
  amplification*, and :func:`binary_entropy` is the function that prices it.
- **Asymptotic** versus **finite-key**. The clean formulas assume an infinitely
  long key, so that measured frequencies equal probabilities. A LEO pass is a
  few minutes; the block is finite by construction and the statistics have
  confidence intervals. The asymptotic rate is therefore an **upper bound**, not
  a deliverable, and :class:`KeyRegime` makes every result say which one it is so
  that a plot legend cannot quietly promise the wrong one.

Three traps this seam exists to close
-------------------------------------
**1. A mean is not a probability.** :class:`~quoss.channel.link_budget.NoiseBudget`
reports counts per gate as a **mean**: means of independent Poisson processes
add, which is what lets background, dark counts and afterpulses be summed at
all. A protocol needs ``Y_0``, a *probability*, and the conversion is
``1 - exp(-mu)`` applied once, at the end. Reading the mean as the probability is
the error :mod:`quoss.channel.background` prices at 253 % for the ITU
bright-sunshine case, where the "probability" comes out as 3.42. Measured here,
in the ordinary case rather than the pathological one: under the 6 W/(m^2 um sr)
of clear-sky daylight that Ntanos et al. quote at 1550 nm, their 2.3 m telescope
collects a mean of 7.0712e-2 counts per gate whose true ``Y_0`` is 6.8270e-2, so
the linear reading overstates it by **3.58 %**; on the 0.75 m telescope of this
project's reference downlink the same reading is **0.38 %** high. Small, silent,
and in the direction that flatters the link. :attr:`LinkConditions.background_yield` is the only route from
one to the other, and it is :func:`~quoss.channel.detector.click_probability`
itself rather than a second copy of the same exponential.

**2. The transmittance already includes the receiver.**
:attr:`~quoss.channel.link_budget.LossBudget.transmittance` is end-to-end: optics,
filter and detector efficiency are inside it. Multiplying it by an efficiency
again is the 6.36 dB double count that :mod:`quoss.channel.link_budget` is shaped
around — a factor of 4.3 in key rate, with every intermediate number still
looking ordinary. :class:`LinkConditions` therefore has **one** transmittance
field and no efficiency field, so there is no pair to multiply.

**3. A per-pulse number is not a per-second number.** Every quantity a protocol
computes is per pulse; every quantity a paper plots is per second. The bridge is
the source pulse rate, one multiplication. :class:`KeyRate` stores only the
per-pulse form and *derives* the per-second one, so the two cannot disagree —
the same reason :class:`~quoss.channel.link_budget.LossBudget` is frozen.

Why the time axis is not here
-----------------------------
:class:`LinkConditions` holds arrays and no :class:`~quoss.core.types.TimeGrid`.
This matches :mod:`quoss.channel`, whose functions take an elevation array rather
than a grid, and it keeps a parameter sweep — a hundred transmittances that are
not a time series at all — from having to invent a time axis to be allowed
through. Integrating a rate over a pass to get bits per pass needs the axis and
is ``system/key_volume.py``, one stage later.

What this module deliberately does not have
-------------------------------------------
**Any protocol but BB84.** The registry is empty until ``bb84.py`` imports, and
it holds no name for E91, CV-QKD, MDI-QKD or TF-QKD, which are out of scope
rather than pending. This is the rule ``docs/adr/0005-propagation.md`` settled
for ``PropagationMethod``: an absent name forces a question at the call site, a
present and unimplemented one invites a scenario to select it. Adding a protocol
later means writing a class that implements :meth:`QkdProtocol._key_rate` and
registering its name; nothing outside this package would change, because what
crosses the boundary is :class:`LinkConditions` in and :class:`KeyRate` out.

**A block-level finite-key entry point.** :meth:`QkdProtocol.key_rate` maps
instants to instants. A finite-key bound is a statement about a *block* of
detections, and a block is an integral over a pass, which needs the time axis
this module does not carry. That entry point belongs beside the bound, in
``finite_key.py``, and takes accumulated counts rather than a rate. Until it
exists, every rate this interface returns is :attr:`KeyRegime.ASYMPTOTIC` and
says so in its own field.

**The decoy-state machinery.** Bounding ``Y_1`` and ``e_1`` from the observed
gains of several intensities is the content of BB84 with weak coherent pulses,
not of the boundary, and pushing it here would make the interface unimplementable
by anything else.

**Double clicks, dead time and afterpulse errors.** The first is a protocol
outcome with a protocol-level treatment (:mod:`quoss.channel.detector` says why
it stops short of it); the second and third are detector behaviour that
:mod:`quoss.channel.detector` already models and that reaches this seam folded
into the transmittance and the noise mean. A caller running a source fast enough
to saturate its own detectors is not warned here: the number that decides that is
:func:`~quoss.channel.detector.saturation_count_rate_cps`, and it takes a dead
time this module has no field for.

=================================  ==========================================
Symbol                             Meaning
=================================  ==========================================
``eta``                            end-to-end transmittance, satellite
                                   aperture to click (-)
``mu_noise``                       mean counts per gate that are not signal (-)
``Y_0``                            probability of a click with no signal
                                   photon sent (-)
``Q``                              gain: probability of a click per pulse (-)
``E``                              QBER: fraction of sifted bits in error (-)
``e_d``                            misalignment error probability (-)
``f_rep``                          source pulse rate (Hz)
``h(x)``                           binary entropy, in bits
=================================  ==========================================

References
----------
A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
§4.2 (the 100 MHz source pulse rate) and Appendix A, equations (A4)-(A6) (the
yield and QBER model that ``bb84.py`` implements against this interface).

C. C. W. Lim, M. Curty, N. Walenta, F. Xu and H. Zbinden, "Concise security
bounds for practical decoy-state quantum key distribution", *Phys. Rev. A*
**89**, 022307, 2014, Evaluation section: the error model
``e_k = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2``, which is where
:attr:`LinkConditions.misalignment_error` enters and why it is a property of the
link rather than of the protocol.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import ClassVar, Final

import numpy as np
from scipy.special import xlogy

from quoss.channel.detector import click_probability
from quoss.core.errors import ConfigurationError, DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, FloatLike, frozen_view

__all__ = [
    "NTANOS_SOURCE_PULSE_RATE_HZ",
    "PROTOCOLS",
    "KeyRate",
    "KeyRegime",
    "LinkConditions",
    "ProtocolRegistry",
    "QkdProtocol",
    "binary_entropy",
]


NTANOS_SOURCE_PULSE_RATE_HZ: Final[float] = 100.0e6
"""Source pulse rate of Ntanos et al. 2021 §4.2, Hz.

100 MHz, the only source repetition rate this project has from a verified
source. It is what makes their dead-time argument checkable — at that rate their
500 kcps of detections sit two orders of magnitude below the 33.3 Mcps ceiling of
a 30 ns dead time (:mod:`quoss.channel.detector`) — and it is the number that
turns every per-pulse quantity in this package into a per-second one.

Not a default anywhere: :class:`LinkConditions` requires the pulse rate because a
source that runs at a different rate makes every rate in the result different,
and a default would let that difference arrive unannounced.
"""

_BITS_PER_NAT: Final[float] = 1.0 / float(np.log(2.0))
"""Bits per nat, 1.442695. Converts the natural logarithm ``xlogy`` returns.

Spelled as the identity it is rather than as digits, for the same reason as
``link_budget.DB_PER_NEPER``: it is what makes :func:`binary_entropy` checkable
by hand against its own definition.
"""

_ORDERING_SLACK: Final[float] = 1e-12
"""Relative slack on the ``gain >= sifted >= secure`` chain of :class:`KeyRate`.

Not a tolerance on physics. The three are computed from one another, so a
violation of more than a part in a million million is an argument in the wrong
slot, while a violation of the last bit is floating-point rounding in an
expression that is mathematically an equality.
"""


def _range_of(value: FloatArray) -> str:
    """Format the range of an array for a message, surviving the empty case.

    An empty pass is legal (see :class:`LinkConditions`), and ``np.min`` of an
    empty array raises — which would turn a message about a *different* problem
    into a traceback about this one.
    """
    if value.size == 0:
        return "empty"
    return f"{float(np.min(value)):.6g}, {float(np.max(value)):.6g}"


def binary_entropy(error_rate: FloatLike) -> FloatArray:
    """Return the binary entropy ``h(x) = -x log2 x - (1-x) log2 (1-x)``, in bits.

    What it is
    ----------
    The number of bits of uncertainty in a single coin flip that comes up heads
    with probability ``x``. A fair coin (``x = 0.5``) carries exactly one bit; a
    coin that always lands the same way (``x = 0`` or ``x = 1``) carries none,
    because there is nothing to learn from watching it.

    Why a QKD module needs it
    -------------------------
    It prices both halves of what Alice and Bob must spend. Correcting an error
    rate ``E`` costs at least ``h(E)`` bits of public discussion per sifted bit,
    and shrinking the eavesdropper's knowledge of a bit she may have disturbed at
    rate ``e_1`` costs another ``h(e_1)``. Every secret-key formula in this
    package is a sifted rate multiplied by one minus a sum of these, which is why
    the function lives at the boundary rather than inside one protocol: the
    finite-key bound needs the same function as the asymptotic rate, and two
    copies of it would be two things to keep in step.

    Why ``xlogy`` and not ``x * log(x)``
    ------------------------------------
    At ``x = 0`` the product ``x log x`` is ``0 * -inf``, which numpy evaluates to
    ``nan`` **and** emits a warning for — and this project runs its tests with
    ``filterwarnings = ["error"]``, so the warning is not something one can decide
    to ignore later. Guarding with :func:`numpy.where` does not help: both
    branches are evaluated before the choice is made, so the warning still fires.
    ``scipy.special.xlogy`` defines ``xlogy(0, 0) = 0``, which is the limit
    ``lim_{x->0} x log x``, and computes it without ever forming the product. A
    zero error rate is not an edge case here: it is what a simulated link with no
    background and no misalignment has, and it is the value a test reaches for
    first.

    The sign of zero is fixed on the way out. ``-(0.0)/ln2`` is ``-0.0``, which
    compares equal to zero and breaks nothing, but prints as ``-0.`` in a result
    table where a negative entropy is exactly the kind of thing a reader should
    not have to decide to ignore. Adding ``0.0`` maps ``-0.0`` to ``0.0`` and
    leaves every other value untouched.

    Parameters
    ----------
    error_rate
        Probability, in ``[0, 1]``. Any shape. A QBER is a fraction: 11 % is
        ``0.11``.

    Returns
    -------
    FloatArray
        Entropy in bits, in ``[0, 1]``, same shape as the input.

    Raises
    ------
    DomainError
        If any value is non-finite or outside ``[0, 1]``.

    Examples
    --------
    The three values one can check by hand:

    >>> float(binary_entropy(0.0))
    0.0
    >>> float(binary_entropy(0.5))
    1.0
    >>> float(binary_entropy(1.0))
    0.0

    It is symmetric about one half and vectorised:

    >>> binary_entropy(np.array([0.0, 0.25, 0.5, 0.75, 1.0]))
    array([0.        , 0.81127812, 1.        , 0.81127812, 0.        ])

    And the number behind BB84's familiar 11 % asymptotic error threshold: the
    one-way rate ``1 - 2 h(E)`` reaches zero where ``h(E) = 0.5``.

    >>> round(float(binary_entropy(0.11)), 6)
    0.499916
    """
    x = np.asarray(error_rate, dtype=np.float64)
    if not np.all(np.isfinite(x)):
        raise DomainError("error_rate contains non-finite values.")
    if np.any(x < 0.0) or np.any(x > 1.0):
        raise DomainError(
            "error_rate must lie in [0, 1], got range "
            f"[{float(np.min(x))}, {float(np.max(x))}]. It is a fraction, not a percentage: "
            "an 11 % error rate is 0.11."
        )
    entropy: FloatArray = -_BITS_PER_NAT * (xlogy(x, x) + xlogy(1.0 - x, 1.0 - x)) + 0.0
    return entropy


class KeyRegime(StrEnum):
    """Which security statement a :class:`KeyRate` is making.

    The two differ by more than a correction term, so a result that does not say
    which one it is cannot be compared with anything.

    Attributes
    ----------
    ASYMPTOTIC
        Computed as though the block of detections were infinitely long, so that
        every observed frequency equals its probability. An **upper bound** on
        what a real pass delivers, and one that is loosest exactly where the link
        is worst. Legitimate for a sanity check or a comparison against a
        published asymptotic figure; never a number to report as available key.
    FINITE
        Computed for a block of stated length with a stated failure probability,
        so that the statistics carry confidence intervals. This is what a pass
        actually yields, and what QuOSS reports by default once ``finite_key.py``
        exists.
    """

    ASYMPTOTIC = "asymptotic"
    FINITE = "finite"


class LinkConditions:
    """What the channel delivers to a protocol at every instant of a pass.

    Immutable and validated at construction, so a protocol receiving one may
    assume the transmittances are in range, the noise means are non-negative and
    every field has a common shape, without re-checking. **Immutable includes the
    numbers**: each array is stored as an independent read-only copy, so neither
    ``conditions.transmittance[0] = ...`` nor a later edit to the array the caller
    passed in can move the link under a result that has already been computed.

    Scalars are accepted for any of the three physical quantities and broadcast
    against the others, so a single instant reads naturally and a pass reads the
    same way; what is *stored* is always a ``float64`` array of the common shape.
    Not a dataclass, for the reason
    :class:`~quoss.orbits.kepler.ClassicalElements` is not one: a generated
    ``__init__`` would have to declare one type for both roles, and widening the
    attributes to ``float | FloatArray`` would push a branch into every protocol
    for a case that cannot occur once ``__init__`` has returned.

    An **empty** set of conditions is legal and returns empty results. That is
    not a curiosity: a pass segmented before its first visible sample is empty,
    and four channel modules had to be fixed for it when
    :mod:`quoss.channel.link_budget` first called them in sequence.

    Parameters
    ----------
    transmittance : float or FloatArray
        End-to-end transmittance, satellite aperture to detector click, in
        ``(0, 1]`` — precisely
        :attr:`~quoss.channel.link_budget.LossBudget.transmittance`, receiver
        efficiency chain **included**. There is deliberately no efficiency
        argument beside it: see trap 2 in the module docstring for the 6.36 dB
        that the pair would invite. Zero is excluded for the same reason
        :mod:`quoss.channel.link_budget` excludes it — a link that transmits
        nothing has infinite loss, and it turns the decoy bounds into ``0/0``.
    noise_counts_per_gate : float or FloatArray
        Mean counts per gate that are not signal, from
        :attr:`~quoss.channel.link_budget.NoiseBudget.total_per_gate`. A
        **mean**, non-negative and with no upper bound; the conversion to a
        probability is :attr:`background_yield` and happens once.
    misalignment_error : float or FloatArray
        Probability that a signal photon which *was* detected lands in the wrong
        outcome because the polarisation reference of transmitter and receiver
        disagree — Lim et al.'s ``e_mis``. In ``[0, 0.5]``. Required, with no
        default, for the same reason ``zenith_transmittance`` is required in
        :mod:`quoss.channel.link_budget`: there is no value that quietly means "I
        did not think about this", and a silent ``0.0`` is a claim of perfect
        optics.
    pulse_rate_hz : float
        Source pulse rate, Hz. The only bridge between per-pulse and per-second,
        and the reason it lives beside the noise: the noise is quoted *per gate*
        and there is exactly one gate per pulse, so the two numbers describe the
        same clock and are checkable against each other here.
    gate_duration_s : float
        Detection gate width, s, the one the noise mean was integrated over. It
        enters no formula in this package — the noise arrives already integrated
        — and is required because it is the only thing that makes "per gate"
        mean anything, and because a gate wider than the pulse period is a
        receiver whose gates overlap, which is a configuration no result should
        be produced for.

    Raises
    ------
    DomainError
        If any array holds non-finite values, if a transmittance is outside
        ``(0, 1]``, if a noise mean is negative, if a misalignment error is
        outside ``[0, 0.5]``, if the pulse rate or gate duration is not finite
        and positive, if the gate is wider than the pulse period, or if the three
        arrays do not broadcast to a common shape.

    Examples
    --------
    This project's reference downlink at zenith — Ntanos et al.'s 600 km orbit,
    0.15 m transmitter, 0.75 m ground telescope, their SNSPD chain and their
    1 ns gate, on a night whose sky radiance is the value their numerical study
    uses:

    >>> conditions = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> conditions.shape
    ()
    >>> float(conditions.pulse_period_s)
    1e-08

    The noise mean and the probability it implies, which at night differ far
    below the precision of either:

    >>> f"{float(conditions.background_yield):.6e}"
    '7.879697e-07'

    In daylight they do not. Four orders of magnitude of extra sky, and the
    linear reading of the mean is 0.38 % high on this telescope — 3.58 % on the
    2.3 m one, which collects ten times the sky:

    >>> day = LinkConditions(
    ...     transmittance=1.3993e-03,
    ...     noise_counts_per_gate=7.519554e-03,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> round(float(7.519554e-03 / day.background_yield - 1.0) * 100.0, 2)
    0.38

    A pass is the same call with arrays, and the stored numbers cannot be moved
    afterwards:

    >>> pass_ = LinkConditions(
    ...     transmittance=np.array([3.06e-04, 1.40e-03, 3.06e-04]),
    ...     noise_counts_per_gate=7.8797e-07,
    ...     misalignment_error=0.01,
    ...     pulse_rate_hz=NTANOS_SOURCE_PULSE_RATE_HZ,
    ...     gate_duration_s=1e-09,
    ... )
    >>> pass_.shape
    (3,)
    >>> pass_.transmittance[0] = 1.0
    Traceback (most recent call last):
        ...
    ValueError: assignment destination is read-only
    """

    __slots__ = (
        "_gate_duration_s",
        "_misalignment_error",
        "_noise_counts_per_gate",
        "_pulse_rate_hz",
        "_transmittance",
    )

    def __init__(
        self,
        *,
        transmittance: FloatLike,
        noise_counts_per_gate: FloatLike,
        misalignment_error: FloatLike,
        pulse_rate_hz: float,
        gate_duration_s: float,
    ) -> None:
        eta = np.array(transmittance, dtype=np.float64)
        noise = np.array(noise_counts_per_gate, dtype=np.float64)
        misalignment = np.array(misalignment_error, dtype=np.float64)

        for name, value in (
            ("transmittance", eta),
            ("noise_counts_per_gate", noise),
            ("misalignment_error", misalignment),
        ):
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")

        if np.any(eta <= 0.0) or np.any(eta > 1.0):
            raise DomainError(
                "transmittance must lie in (0, 1]; it is a linear fraction, not a decibel "
                "figure and not a percentage, so a 30 dB link is 1e-3 and not 30. Range given: "
                f"[{_range_of(eta)}]. It is the end-to-end factor of "
                "LossBudget.transmittance, receiver chain included."
            )
        if np.any(noise < 0.0):
            raise DomainError(
                "noise_counts_per_gate must be non-negative. It is a mean number of counts per "
                f"gate, not a probability, so it has no upper bound. Range given: [{_range_of(noise)}]."
            )
        if np.any(misalignment < 0.0) or np.any(misalignment > 0.5):
            raise DomainError(
                "misalignment_error must lie in [0, 0.5]. It is a probability, so 1 % is 0.01; "
                "and a reference that is wrong more than half the time is not a worse link but "
                f"an inverted labelling, which is fixed by swapping two wires. Range given: [{_range_of(misalignment)}]."
            )

        rate = float(pulse_rate_hz)
        if not np.isfinite(rate) or rate <= 0.0:
            raise DomainError(
                f"pulse_rate_hz must be finite and positive, got {rate}. The unit is hertz: "
                "a 100 MHz source is 100e6."
            )
        gate = float(gate_duration_s)
        if not np.isfinite(gate) or gate <= 0.0:
            raise DomainError(
                f"gate_duration_s must be finite and positive, got {gate}. The unit is seconds: "
                "a 1 nanosecond gate is 1e-9."
            )
        if gate > 1.0 / rate:
            raise DomainError(
                f"gate_duration_s={gate} exceeds the pulse period 1/pulse_rate_hz="
                f"{1.0 / rate} s. There is one gate per pulse, so a gate wider than the period "
                "is a receiver whose gates overlap: every count would be attributed to two "
                "pulses and the noise mean handed in was integrated over a window that does "
                "not exist."
            )

        try:
            broadcast = np.broadcast_arrays(eta, noise, misalignment)
        except ValueError as exc:
            raise DomainError(
                "transmittance, noise_counts_per_gate and misalignment_error must broadcast to "
                f"a common shape, got {eta.shape}, {noise.shape} and {misalignment.shape}. A "
                "trailing axis of length one against a full one silently makes an outer product "
                "rather than a pass."
            ) from exc

        self._transmittance: FloatArray = frozen_view(broadcast[0])
        self._noise_counts_per_gate: FloatArray = frozen_view(broadcast[1])
        self._misalignment_error: FloatArray = frozen_view(broadcast[2])
        self._pulse_rate_hz: float = rate
        self._gate_duration_s: float = gate

    # -- what the channel measured ------------------------------------------ #
    @property
    def transmittance(self) -> FloatArray:
        """End-to-end transmittance, receiver chain included. Read-only."""
        return self._transmittance

    @property
    def noise_counts_per_gate(self) -> FloatArray:
        """Mean counts per gate that are not signal. A mean, not a probability."""
        return self._noise_counts_per_gate

    @property
    def misalignment_error(self) -> FloatArray:
        """Probability that a detected signal photon lands in the wrong outcome."""
        return self._misalignment_error

    @property
    def pulse_rate_hz(self) -> float:
        """Source pulse rate, Hz."""
        return self._pulse_rate_hz

    @property
    def gate_duration_s(self) -> float:
        """Detection gate width the noise mean was integrated over, s."""
        return self._gate_duration_s

    # -- what follows from it ----------------------------------------------- #
    @property
    def pulse_period_s(self) -> float:
        """Time between pulses, s. One gate fits in here, by construction."""
        return 1.0 / self._pulse_rate_hz

    @property
    def background_yield(self) -> FloatArray:
        """Probability of a click in a gate where no signal photon arrived, ``Y_0``.

        ``1 - exp(-mu_noise)``, and it is
        :func:`~quoss.channel.detector.click_probability` with no signal and no
        efficiency rather than a second copy of that exponential — one Poisson
        click law in the project, called from the two places that need it. The
        efficiency is ``1.0`` because the chain is already inside both numbers
        this object holds: the background in ``noise_counts_per_gate`` was
        attenuated by :func:`~quoss.channel.link_budget.downlink_noise_budget`
        and the dark counts were correctly *not* attenuated by it.

        Returns
        -------
        FloatArray
            Probability in ``[0, 1)``, the shape of the conditions.
        """
        return click_probability(
            0.0, efficiency=1.0, dark_counts_per_gate=self._noise_counts_per_gate
        )

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the three arrays. ``()`` for a single instant."""
        return self._transmittance.shape

    @property
    def size(self) -> int:
        """Number of instants. ``1`` for a single instant, ``0`` for an empty pass."""
        return int(self._transmittance.size)

    def __repr__(self) -> str:
        return (
            f"LinkConditions(shape={self.shape}, transmittance=[{_range_of(self._transmittance)}], "
            f"noise_counts_per_gate=[{_range_of(self._noise_counts_per_gate)}], "
            f"pulse_rate_hz={self._pulse_rate_hz!r})"
        )


@dataclass(frozen=True, slots=True, kw_only=True)
class KeyRate:
    """What a protocol returns: a rate, an error rate, and what they are claims about.

    Keyword-only, because five of its seven fields are float arrays of the same
    shape and a positional swap between two of them would produce a result that
    is wrong and ordinary-looking. Frozen, because a result whose parts can be
    edited afterwards is one whose parts no longer imply one another.

    Only the **per-pulse** rates are stored. The per-second ones every figure
    shows are properties derived from them and the pulse rate, so the pair cannot
    drift apart the way two stored copies would.

    Attributes
    ----------
    protocol : str
        :attr:`QkdProtocol.name` of whatever produced this. Carried because a
        rate without its protocol cannot be compared with another rate.
    regime : KeyRegime
        Asymptotic or finite-key. See :class:`KeyRegime`; the difference is a
        security statement, not a correction factor.
    pulse_rate_hz : float
        Source pulse rate, copied from the :class:`LinkConditions` this was
        computed from. :meth:`QkdProtocol.key_rate` checks that it was copied
        and not recomputed.
    gain : FloatArray
        ``Q``: probability that a pulse produces a click, from any cause.
    qber : FloatArray
        ``E``: fraction of the sifted bits that disagree, in ``[0, 0.5]``.
    sifted_per_pulse : FloatArray
        Sifted bits per pulse — clicks that survived basis reconciliation. At
        most ``gain``.
    secure_per_pulse : FloatArray
        Secret bits per pulse after error correction and privacy amplification,
        **clamped at zero**. Clamping is the protocol's job and is checked here:
        the formulas go negative where the link is too poor, and a negative
        number is not a small key but the absence of one — privacy amplification
        cannot remove more than all of the sifted key. :attr:`has_key` is the
        field to read for "was there any".
    """

    protocol: str
    regime: KeyRegime
    pulse_rate_hz: float
    gain: FloatArray
    qber: FloatArray
    sifted_per_pulse: FloatArray
    secure_per_pulse: FloatArray

    def __post_init__(self) -> None:
        """Validate the invariants a consumer is allowed to skip re-checking."""
        if not isinstance(self.protocol, str) or not self.protocol:
            raise DomainError(f"protocol must be a non-empty name, got {self.protocol!r}.")
        object.__setattr__(self, "regime", KeyRegime(self.regime))

        rate = float(self.pulse_rate_hz)
        if not np.isfinite(rate) or rate <= 0.0:
            raise DomainError(f"pulse_rate_hz must be finite and positive, got {rate}.")
        object.__setattr__(self, "pulse_rate_hz", rate)

        names = ("gain", "qber", "sifted_per_pulse", "secure_per_pulse")
        values = [np.array(getattr(self, name), dtype=np.float64) for name in names]
        for name, value in zip(names, values, strict=True):
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
        try:
            broadcast = np.broadcast_arrays(*values)
        except ValueError as exc:
            raise DomainError(
                "gain, qber, sifted_per_pulse and secure_per_pulse must broadcast to a common "
                f"shape, got {[v.shape for v in values]}."
            ) from exc
        gain, qber, sifted, secure = broadcast

        if np.any(gain < 0.0) or np.any(gain > 1.0):
            raise DomainError(
                f"gain must lie in [0, 1], got range [{_range_of(gain)}]. It is a probability "
                "per pulse, not a count rate: a 100 MHz source clicking 500 kcps has a gain of "
                "5e-3, not 5e5."
            )
        if np.any(qber < 0.0) or np.any(qber > 0.5):
            raise DomainError(
                f"qber must lie in [0, 0.5], got range [{_range_of(qber)}]. It is a fraction, "
                "so 11 % is 0.11; and above one half it is not a worse key but an inverted bit "
                "convention."
            )
        if np.any(sifted > gain * (1.0 + _ORDERING_SLACK)):
            raise DomainError(
                "sifted_per_pulse exceeds gain. Sifting discards clicks and creates none, so "
                f"the sifted rate is at most the gain. Ranges: sifted [{_range_of(sifted)}], "
                f"gain [{_range_of(gain)}]."
            )
        if np.any(secure < 0.0):
            raise DomainError(
                f"secure_per_pulse must be non-negative, got range [{_range_of(secure)}]. Where "
                "the rate formula goes negative there is no key at all, so the protocol clamps "
                "at zero and says so through has_key; a negative rate reported as a rate "
                "integrates into a negative key volume over a pass."
            )
        if np.any(secure > sifted * (1.0 + _ORDERING_SLACK)):
            raise DomainError(
                "secure_per_pulse exceeds sifted_per_pulse. Error correction and privacy "
                "amplification both shrink the sifted key, so the secret rate is at most the "
                f"sifted one. Ranges: secure [{_range_of(secure)}], sifted [{_range_of(sifted)}]."
            )

        for name, value in zip(names, broadcast, strict=True):
            object.__setattr__(self, name, frozen_view(value))

    @property
    def shape(self) -> tuple[int, ...]:
        """Common shape of the four arrays."""
        return self.gain.shape

    @property
    def sifted_bit_s(self) -> FloatArray:
        """Sifted bits per second: the per-pulse rate times the pulse rate."""
        sifted: FloatArray = self.sifted_per_pulse * self.pulse_rate_hz
        return sifted

    @property
    def secure_bit_s(self) -> FloatArray:
        """Secret bits per second. The quantity a figure of SKR(t) plots."""
        secure: FloatArray = self.secure_per_pulse * self.pulse_rate_hz
        return secure

    @property
    def has_key(self) -> BoolArray:
        """True where a secret key exists at all.

        Strictly positive, not "above a threshold": what a threshold would mean
        is a question about a pass, and a pass is ``system/key_volume.py``.
        """
        positive: BoolArray = self.secure_per_pulse > 0.0
        return positive

    def __repr__(self) -> str:
        return (
            f"KeyRate({self.protocol!r}, {self.regime}, shape={self.shape}, "
            f"secure_bit_s=[{_range_of(self.secure_bit_s)}], qber=[{_range_of(self.qber)}])"
        )


class QkdProtocol(ABC):
    """The interface every protocol implements: conditions in, rate and QBER out.

    A subclass is **configuration, not state**: a frozen object holding the
    choices an experimenter makes — intensities, basis bias, block length,
    security parameter — whose :meth:`key_rate` is a pure function of itself and
    its argument. Nothing here holds a result, opens a file or touches a global.
    The split between this object and :class:`LinkConditions` is exactly that
    one: the conditions are what the link *does*, the protocol is what the
    experimenter *chose*.

    Subclasses implement :meth:`_key_rate` and inherit :meth:`key_rate`, which
    checks the three things an implementation can get wrong without anything
    looking unusual. They are checks on plumbing, not on physics, and each is a
    mistake that has a plausible-looking result on the other side of it.

    Attributes
    ----------
    name : str
        Registry key, lowercase and without spaces, e.g. ``"bb84-decoy"``. The
        string a scenario file writes. Declared here and defined by the subclass.
    """

    name: ClassVar[str]

    def key_rate(self, conditions: LinkConditions, *, degradations: DegradationLog) -> KeyRate:
        """Return the key rate and QBER for these conditions, instant by instant.

        The wrapper every subclass inherits. It delegates to :meth:`_key_rate`
        and then checks that the result is about the question that was asked:

        * the **shape** matches the conditions — a protocol that broadcast two
          arrays the wrong way round returns an ``(n, n)`` result whose diagonal
          is right and whose plot is meaningless;
        * the **pulse rate** was copied rather than recomputed, because
          :attr:`KeyRate.secure_bit_s` is derived from it and a rate copied from
          somewhere else scales every figure in the paper;
        * the **name** is this protocol's, because a result is compared against
          other results by that string.

        Parameters
        ----------
        conditions : LinkConditions
            What the channel delivers. See trap 2 in the module docstring for
            why there is no efficiency argument beside it.
        degradations : DegradationLog
            Log that receives anything the protocol had to substitute. Required
            rather than optional, per :mod:`quoss.core.errors`: a log that can be
            omitted is one that will be.

        Returns
        -------
        KeyRate
            Per-pulse rates, QBER, and the regime they are claims about.

        Raises
        ------
        ConfigurationError
            If the implementation returned a result that does not answer for
            these conditions. This is a defect in the protocol class, not in the
            caller's scenario, which is why it is not a
            :class:`~quoss.core.errors.ScenarioError`.
        """
        result = self._key_rate(conditions, degradations=degradations)
        if result.protocol != self.name:
            raise ConfigurationError(
                f"{type(self).__name__}._key_rate returned a KeyRate labelled "
                f"{result.protocol!r}, but this protocol is named {self.name!r}. The label is "
                "how a result is identified once it is far from the call that made it."
            )
        if result.pulse_rate_hz != conditions.pulse_rate_hz:
            raise ConfigurationError(
                f"{type(self).__name__}._key_rate returned a KeyRate whose pulse_rate_hz is "
                f"{result.pulse_rate_hz}, but the conditions state {conditions.pulse_rate_hz}. "
                "It is copied, never recomputed: every per-second rate in the result is the "
                "per-pulse rate multiplied by it."
            )
        if result.shape != conditions.shape:
            raise ConfigurationError(
                f"{type(self).__name__}._key_rate returned a KeyRate of shape {result.shape} "
                f"for conditions of shape {conditions.shape}. A mismatch here is almost always "
                "two arrays broadcast against each other instead of elementwise."
            )
        return result

    @abstractmethod
    def _key_rate(self, conditions: LinkConditions, *, degradations: DegradationLog) -> KeyRate:
        """Compute the rate. Implemented by the subclass, called by :meth:`key_rate`.

        Private because there is one public entry point and it is the checked
        one: a subclass that exposed its own would let a caller bypass the three
        checks by accident.

        Parameters
        ----------
        conditions : LinkConditions
            What the channel delivers.
        degradations : DegradationLog
            Log for anything substituted.

        Returns
        -------
        KeyRate
            With ``protocol`` set to :attr:`name`, ``pulse_rate_hz`` copied from
            ``conditions``, and arrays of the conditions' shape.
        """


class ProtocolRegistry:
    """Maps the protocol name a scenario writes to the class that implements it.

    A scenario file says ``protocol: bb84-decoy``; something has to turn that
    string into code. This is that table, and it is an *object* rather than a
    module-level dict so that a test can build its own and register a stand-in
    without editing the table the rest of the process reads. The shared instance
    is :data:`PROTOCOLS`.

    Mutable global state is otherwise avoided in this project — see
    :class:`~quoss.core.errors.DegradationLog` for why the degradation log is
    passed explicitly rather than kept in a module singleton. A registry differs
    in the way that matters: it is written once per class at **import** time,
    never during a computation, so no physics function's result depends on when
    it ran relative to another's.

    What it hands back is the **class**, not an instance, because a protocol
    carries parameters and choosing them is the caller's job.

    Examples
    --------
    >>> registry = ProtocolRegistry()
    >>> len(registry)
    0
    >>> class Stub(QkdProtocol):
    ...     name = "stub"
    ...
    ...     def _key_rate(self, conditions, *, degradations):
    ...         raise NotImplementedError
    >>> registry.register(Stub) is Stub
    True
    >>> registry.names()
    ('stub',)
    >>> registry.resolve("STUB ") is Stub
    True
    >>> "bb84-decoy" in registry
    False
    """

    __slots__ = ("_by_name",)

    def __init__(self, protocols: Iterable[type[QkdProtocol]] = ()) -> None:
        self._by_name: dict[str, type[QkdProtocol]] = {}
        for protocol in protocols:
            self.register(protocol)

    def register(self, protocol: type[QkdProtocol]) -> type[QkdProtocol]:
        """Add a protocol class, and return it so this reads as a decorator.

        Parameters
        ----------
        protocol : type[QkdProtocol]
            The class to register. Its :attr:`QkdProtocol.name` is the key.

        Returns
        -------
        type[QkdProtocol]
            The same class, unchanged.

        Raises
        ------
        ConfigurationError
            If the class declares no usable name, if the name is not lowercase
            and free of whitespace, or if that name is already taken. The last
            one is the useful case: two classes answering to one string is a
            coin flip decided by import order.
        """
        if not isinstance(protocol, type) or not issubclass(protocol, QkdProtocol):
            raise ConfigurationError(
                f"{protocol!r} is not a QkdProtocol subclass. The registry stores classes, not "
                "instances: a protocol carries parameters, and choosing them is the caller's."
            )
        name = getattr(protocol, "name", None)
        if not isinstance(name, str) or not name:
            raise ConfigurationError(
                f"{protocol.__name__} must define a non-empty class attribute `name`; it is the "
                "string a scenario file writes to select the protocol."
            )
        if name != name.lower() or name.split() != [name]:
            raise ConfigurationError(
                f"Protocol name {name!r} must be lowercase and contain no whitespace, so that a "
                "scenario file, a CLI flag and a result label spell it the same way."
            )
        if name in self._by_name:
            raise ConfigurationError(
                f"Protocol name {name!r} is already registered to "
                f"{self._by_name[name].__name__}; {protocol.__name__} cannot take it. Which one "
                "won would otherwise be decided by import order."
            )
        self._by_name[name] = protocol
        return protocol

    def resolve(self, name: str) -> type[QkdProtocol]:
        """Return the class registered under ``name``.

        Permissive at the boundary and strict inside, the same discipline as
        :func:`~quoss.orbits.frames.resolve_frame`: the query is stripped and
        lowercased, because it arrives from YAML written by a person, while what
        is stored was checked when it was registered.

        Parameters
        ----------
        name : str
            Protocol name, e.g. ``"bb84-decoy"``.

        Returns
        -------
        type[QkdProtocol]
            The registered class.

        Raises
        ------
        ConfigurationError
            If nothing is registered under that name. The message lists what is,
            and says why a protocol that is not implemented is absent rather than
            present and raising.
        """
        key = str(name).strip().lower()
        try:
            return self._by_name[key]
        except KeyError:
            available = ", ".join(repr(n) for n in self.names()) or "nothing yet"
            raise ConfigurationError(
                f"No QKD protocol is registered as {name!r}. Registered: {available}. QuOSS "
                "implements BB84 with weak coherent pulses and decoy states and nothing else; "
                "E91, CV-QKD, MDI-QKD and TF-QKD are absent rather than present and raising, so "
                "that a scenario cannot select one and a reader cannot assume it exists (the "
                "rule of docs/adr/0005-propagation.md)."
            ) from None

    def names(self) -> tuple[str, ...]:
        """Return the registered names, sorted."""
        return tuple(sorted(self._by_name))

    def __contains__(self, name: object) -> bool:
        return isinstance(name, str) and name.strip().lower() in self._by_name

    def __iter__(self) -> Iterator[str]:
        return iter(self.names())

    def __len__(self) -> int:
        return len(self._by_name)

    def __repr__(self) -> str:
        return f"ProtocolRegistry({', '.join(self.names()) or 'empty'})"


PROTOCOLS: Final[ProtocolRegistry] = ProtocolRegistry()
"""The registry the rest of QuOSS reads.

Empty until a protocol module is imported; ``bb84.py`` registers itself on
import, and nothing else ever will while BB84 is the only implemented protocol.
"""
