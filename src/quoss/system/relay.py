r"""Trusted-node relay: key between two stations that never see each other.

What a trusted node is, for a reader who has not met the term
--------------------------------------------------------------
Quantum key distribution gives a key to the two ends of one optical link. A
satellite link's two ends are the satellite and a ground station, so what a
pass produces is a key ``K_A`` shared between the satellite and station A —
not between A and anybody else. To give two stations A and B a key they share
*with each other*, the satellite does something classical: on a pass over A it
gets ``K_A``, on a pass over B it gets ``K_B``, and then it announces, over any
public channel, the bitwise exclusive-or ``K_A xor K_B``. Station A knows
``K_A`` and reads ``K_B`` off the announcement; station B knows ``K_B`` and
reads ``K_A``. Either key now serves as the shared secret, of length
``min(|K_A|, |K_B|)`` since the shorter one bounds what the xor can carry.

The name says the cost: the satellite **holds both keys in the clear**, so
anyone who controls it controls the end-to-end key. The protocol is only as
secure as the satellite is trusted. That is not a flaw to be engineered away
in this module — it is the definition of the architecture the project's scope
fixes (one satellite, no inter-satellite links, decision of 2026-09-10) — and
every figure here is an end-to-end key *conditional on* that trust.

Why this is a simulation over time and not a formula
-----------------------------------------------------
Because the two stations are not visited at once. A pass over A ends with
``K_A`` on board and nothing to pair it with; the key waits in the on-board
store until a pass over B produces something to pair. The delivered key at
each B pass is ``min(stored A key, new B key)``, the surplus on either side
goes back into the store, and the pattern repeats in whichever order the
passes actually come. :func:`trusted_node_relay` walks the passes of both
stations in chronological order — the key of a pass exists when the pass
**ends**, because the block is the pass (``docs/adr/0011``) and a block is not
complete before its last sample — and keeps the two balances. A loop over
passes, a few hundred at most, and the one place in this module that is not
an array operation, because each step depends on the store the previous step
left.

**An identity worth knowing before reading any number.** With an unbounded
store the balances can never both be positive — whenever they would be, a
pairing happens — so at the end of the window one of them is zero, and then
the total delivered equals ``min(sum K_A, sum K_B)`` exactly, whatever the
order of the passes. The order does not change *how much*; it changes **when**
(the latency, and which UTC day the bits land in) and **how much is
stranded** in the store when the window closes. Those are the outputs that
carry information, and ``tests/system/test_relay.py::TestTheStoreIdentity``
asserts the identity so that nobody reads the total as if ordering had
earned it.

Latency, defined
----------------
Two numbers per delivery, both in seconds, both measured from the end of the
pass whose key was consumed to the end of the pass that delivered it:

- ``latency_s``: the age of the **oldest** bit delivered — the longest any of
  the delivered bits waited on board. The store is first-in-first-out, so a
  delivery may consume the tail of one stored pass and the head of the next,
  and this is the age of the tail.
- ``mean_latency_s``: the **bit-weighted mean** age of the delivered bits.

Both are zero for a delivery whose two passes end at the same instant, which
happens when the same pass is seen from two close stations.

Security composition: a sum, and why a sum is right
---------------------------------------------------
Each pass's key is ``eps``-secure on its own. The end-to-end key is a function
of *two* keys, one from each side, and it fails if either of them was not
what its proof promised. The probability of "either" is bounded by the sum of
the two probabilities — the union bound, the same argument
:func:`~quoss.system.key_volume.composed_security` makes for concatenating a
day's blocks — so the end-to-end key of a day that consumed ``n_A`` blocks of
A and ``n_B`` blocks of B is ``(n_A + n_B) eps``-secure, and
:attr:`RelayKeyVolume.security` carries that. The addition is not a
conservative approximation of something tighter: composable security is
exactly the property that licenses it, and no better bound is available
without assumptions about the failures being independent, which a proof does
not give.

Measured on the reference day
-----------------------------
Castelldefels (the reference, 432 985 bits in two live passes) relayed to the
ESA optical ground station on Tenerife (2214 km away, 562 697 bits in two live
passes), same satellite, same day. The passes interleave A, B, A, B and the
store never holds both sides at once:

=====  ==========  ===============  ==============  ============
Event  Delivered   Consumed from    Latency (s)     Residual
=====  ==========  ===============  ==============  ============
1      190 581     A pass 1         6 114           B: 38 270
2      38 270      B pass 1         33 780          A: 204 134
3      204 134     A pass 3         5 703           B: 129 712
=====  ==========  ===============  ==============  ============

Total 432 985 bits, which is ``min(432 985, 562 697)``: the identity above.
The 129 712 bits of Tenerife's last pass are stranded on board at midnight,
and the latency ranges from 1.6 hours to 9.4 — the second event waited across
the daytime gap in which neither station is visible.

Against Calar Alto (596 km away, whose passes end within a minute of
Castelldefels') the same relay delivers 56 925 bits — the near station is fast
and poor, the far one slow and rich — and the latency definition shows its
teeth: the first 47 108 bits arrive **59 s** after Castelldefels' first pass,
but the remaining 9 817 wait **39 822 s**, because Calar Alto's second live
pass ends 72 s *before* Castelldefels' second one and the first-in-first-out
store therefore pairs it with what was left of Castelldefels' *first* pass,
eleven hours old. ``tests/system/test_relay.py::TestOnTheReferenceDay``
regenerates both.

What this module deliberately does not do
-----------------------------------------
- **Inter-satellite links.** Out of scope by the project decision above. There
  is no stub, no flag and no placeholder: a second satellite in either volume
  is a ``DomainError`` naming the decision, because a relay through two
  satellites is a different store with a different security statement.
- **Bound the on-board store.** A real memory is finite; the residuals reported
  here say how much a bound would have to hold.
- **Choose which station to serve.** A relay consumes volumes computed under
  :attr:`~quoss.system.multi_ogs.AggregationPolicy.SUM`; whether both passes
  could physically happen is ``multi_ogs.py``'s question.
- **Model the classical channel.** The xor announcement is assumed delivered.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``K_A``, ``K_B``                        key of one pass over A, over B (bit)
``S_A``, ``S_B``                        on-board store of unpaired A, B key
``eps``                                 failure probability of one block
``n_A``, ``n_B``                        blocks of each side that were consumed
======================================  ====================================
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray, IntArray, frozen_copy
from quoss.qkd.base import KeyRegime
from quoss.qkd.finite_key import SecurityParameters
from quoss.system.key_volume import PassKeyVolume, composed_security
from quoss.system.multi_ogs import same_grid

__all__ = [
    "RelayKeyVolume",
    "trusted_node_relay",
]

_BIT_TOLERANCE = 1e-6
"""Absolute slack, in bits, for the store identities checked at construction.

The balances are sums and differences of block lengths — whole numbers in the
finite regime, reals in the asymptotic one — and the identities must hold to
rounding, not to a fraction of a bit.
"""


@dataclass(frozen=True, eq=False, slots=True)
class RelayKeyVolume:
    """End-to-end key between two stations through one trusted satellite.

    Attributes
    ----------
    names : tuple[str, str]
        The two stations, in the order ``(A, B)`` the volumes were given.
    delivered_bits : FloatArray
        Bits of end-to-end key each delivery produced, shape ``(E,)``, in
        chronological order. Strictly positive: a pass that paired nothing is
        not an event.
    delivered_at_s : FloatArray
        Instant of each delivery, seconds from the grid's epoch: the end of the
        delivering pass.
    delivering_side : IntArray
        ``0`` when a pass over A delivered (consuming stored B key), ``1`` when
        a pass over B did.
    delivering_pass : IntArray
        Row of the delivering side's pass table.
    latency_s : FloatArray
        Age of the oldest delivered bit, s. See the module docstring.
    mean_latency_s : FloatArray
        Bit-weighted mean age of the delivered bits, s.
    day_number : IntArray
        Julian Day Numbers of the UTC days in which a delivery happened,
        ascending, by the delivering pass's day.
    daily_bits : FloatArray
        End-to-end bits delivered per such day.
    total_a_bits, total_b_bits : float
        What each side generated over the window.
    residual_a_bits, residual_b_bits : float
        Unpaired key of each side still on board at the end of the window. At
        most one of them is non-zero.
    security : SecurityParameters or None
        The failure probabilities of the day's end-to-end key — the union
        bound over every consumed block of both sides. ``None`` in the
        asymptotic regime, which makes no ``eps`` claim, and when nothing was
        delivered.
    regime : KeyRegime
        Of both volumes, which must agree.
    protocols : tuple[str, str]
        Protocol names of the two links.

    Raises
    ------
    DomainError
        If the per-event columns disagree in length, a delivery is not
        positive, a latency is negative, a side is not 0 or 1, both residuals
        are positive, the totals do not satisfy ``delivered + residual =
        generated`` on each side, or the security field contradicts the
        regime.

    Examples
    --------
    See :func:`trusted_node_relay`.
    """

    names: tuple[str, str]
    delivered_bits: FloatArray
    delivered_at_s: FloatArray
    delivering_side: IntArray
    delivering_pass: IntArray
    latency_s: FloatArray
    mean_latency_s: FloatArray
    day_number: IntArray
    daily_bits: FloatArray
    total_a_bits: float
    total_b_bits: float
    residual_a_bits: float
    residual_b_bits: float
    security: SecurityParameters | None
    regime: KeyRegime
    protocols: tuple[str, str]

    def __post_init__(self) -> None:
        """Validate the store identities and the security claim, then freeze."""
        names = tuple(self.names)
        if len(names) != 2 or any(not isinstance(n, str) or not n for n in names):
            raise DomainError(f"names must be two non-empty station names, got {names!r}.")
        object.__setattr__(self, "names", names)
        protocols = tuple(self.protocols)
        if len(protocols) != 2 or any(not isinstance(p, str) or not p for p in protocols):
            raise DomainError(f"protocols must be two non-empty names, got {protocols!r}.")
        object.__setattr__(self, "protocols", protocols)
        object.__setattr__(self, "regime", KeyRegime(self.regime))

        delivered = np.asarray(self.delivered_bits, dtype=np.float64)
        if delivered.ndim != 1:
            raise DomainError(f"delivered_bits must be 1-D, got shape {delivered.shape}.")
        shape = delivered.shape
        if not np.all(np.isfinite(delivered)) or np.any(delivered <= 0.0):
            raise DomainError(
                "delivered_bits must be finite and strictly positive: a pass that paired "
                "nothing is not a delivery event."
            )
        object.__setattr__(self, "delivered_bits", frozen_copy(delivered))
        for name in ("delivered_at_s", "latency_s", "mean_latency_s"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != shape:
                raise DomainError(
                    f"{name} has shape {value.shape}, but there are {shape[0]} events."
                )
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{name} contains non-finite values.")
            object.__setattr__(self, name, frozen_copy(value))
        if np.any(self.latency_s < 0.0) or np.any(self.mean_latency_s < 0.0):
            raise DomainError("latencies cannot be negative: key is delivered after it exists.")
        if np.any(self.mean_latency_s > self.latency_s + _BIT_TOLERANCE):
            raise DomainError("mean_latency_s cannot exceed latency_s, the age of the oldest bit.")
        for name in ("delivering_side", "delivering_pass"):
            value = np.asarray(getattr(self, name), dtype=np.int64)
            if value.shape != shape:
                raise DomainError(
                    f"{name} has shape {value.shape}, but there are {shape[0]} events."
                )
            object.__setattr__(self, name, value)
        if np.any((self.delivering_side != 0) & (self.delivering_side != 1)):
            raise DomainError("delivering_side must be 0 (a pass over A) or 1 (a pass over B).")
        if np.any(self.delivering_pass < 0):
            raise DomainError("delivering_pass must index a pass table.")

        days = np.asarray(self.day_number, dtype=np.int64)
        if days.ndim != 1 or (days.size > 1 and not np.all(np.diff(days) > 0)):
            raise DomainError("day_number must be a 1-D strictly ascending array.")
        object.__setattr__(self, "day_number", days)
        daily = np.asarray(self.daily_bits, dtype=np.float64)
        if daily.shape != days.shape or not np.all(np.isfinite(daily)) or np.any(daily < 0.0):
            raise DomainError("daily_bits must be finite, non-negative and one per day_number.")
        object.__setattr__(self, "daily_bits", frozen_copy(daily))

        totals: dict[str, float] = {}
        for name in ("total_a_bits", "total_b_bits", "residual_a_bits", "residual_b_bits"):
            amount = float(getattr(self, name))
            if not np.isfinite(amount) or amount < 0.0:
                raise DomainError(f"{name} must be finite and non-negative, got {amount}.")
            object.__setattr__(self, name, amount)
            totals[name] = amount
        if min(totals["residual_a_bits"], totals["residual_b_bits"]) > _BIT_TOLERANCE:
            raise DomainError(
                "both residuals are positive, which an unbounded store never allows: whenever "
                "both sides hold key, a pairing happens."
            )
        delivered_total = float(np.sum(delivered))
        for side, total, residual in (
            ("A", totals["total_a_bits"], totals["residual_a_bits"]),
            ("B", totals["total_b_bits"], totals["residual_b_bits"]),
        ):
            if abs(delivered_total + residual - total) > _BIT_TOLERANCE * max(1.0, total):
                raise DomainError(
                    f"side {side}: delivered ({delivered_total:g}) + residual ({residual:g}) "
                    f"must equal generated ({total:g}). Every bit is either paired or stored."
                )
        if abs(float(np.sum(daily)) - delivered_total) > _BIT_TOLERANCE * max(1.0, delivered_total):
            raise DomainError("daily_bits must sum to the delivered total.")

        if self.regime is KeyRegime.FINITE and delivered.size:
            if not isinstance(self.security, SecurityParameters):
                raise DomainError(
                    "a FINITE relay that delivered key must carry the composed SecurityParameters "
                    "of the blocks it consumed: the end-to-end key fails if either side's block "
                    "did, and that union bound is the only claim it can make."
                )
        elif self.security is not None:
            raise DomainError(
                "security must be None for an ASYMPTOTIC relay (no eps claim exists) and for a "
                "relay that delivered nothing (there is no key to make a claim about)."
            )

    @property
    def n_deliveries(self) -> int:
        """Number of delivery events, ``E``."""
        return int(self.delivered_bits.size)

    def __len__(self) -> int:
        return self.n_deliveries

    @property
    def total_bits(self) -> float:
        """End-to-end bits delivered over the window."""
        return float(np.sum(self.delivered_bits))

    @property
    def upper_bound_bits(self) -> float:
        """``min(total_a_bits, total_b_bits)``, the order-independent ceiling.

        With an unbounded store it is also the total delivered — the identity
        of the module docstring — so the value of carrying it is that a bounded
        store, or a window cut short, would show the gap.
        """
        return float(min(self.total_a_bits, self.total_b_bits))

    @property
    def stranded_bits(self) -> float:
        """Key still on board when the window closed, ``residual_a + residual_b``."""
        return float(self.residual_a_bits + self.residual_b_bits)

    def __repr__(self) -> str:
        return (
            f"RelayKeyVolume({self.names[0]!r}<->{self.names[1]!r}, {self.regime}, "
            f"deliveries={self.n_deliveries}, total_bits={self.total_bits:.3e}, "
            f"stranded={self.stranded_bits:.3e})"
        )


def _validated_pair(volume_a: PassKeyVolume, volume_b: PassKeyVolume) -> None:
    """Check that the two volumes describe one satellite, one grid, one regime."""
    for label, volume in (("volume_a", volume_a), ("volume_b", volume_b)):
        if not isinstance(volume, PassKeyVolume):
            raise DomainError(f"{label} must be a PassKeyVolume, got {type(volume).__name__}.")
    if not same_grid(volume_a.samples.table.grid, volume_b.samples.table.grid):
        raise DomainError(
            "volume_a and volume_b are on different time grids. The relay orders the passes of "
            "the two stations on one axis; a different epoch would interleave them wrongly "
            "while every pass kept a plausible duration."
        )
    if volume_a.regime is not volume_b.regime:
        raise DomainError(
            f"volume_a is {volume_a.regime} but volume_b is {volume_b.regime}. Pairing an "
            "asymptotic upper bound with a finite-key length gives a number that is neither."
        )
    satellites = np.unique(
        np.concatenate(
            [volume_a.samples.table.satellite_index, volume_b.samples.table.satellite_index]
        )
    )
    if satellites.size > 1:
        raise DomainError(
            f"the two volumes involve {satellites.size} satellites ({satellites.tolist()}). A "
            "trusted-node relay is one satellite's on-board store; relaying through several "
            "needs inter-satellite links, which are OUT OF SCOPE by the project decision of "
            "2026-09-10 (one satellite) and are not stubbed here. Give each satellite its own "
            "pair of volumes."
        )


def trusted_node_relay(
    volume_a: PassKeyVolume,
    volume_b: PassKeyVolume,
    *,
    degradations: DegradationLog,
    names: tuple[str, str] = ("A", "B"),
) -> RelayKeyVolume:
    """Simulate the on-board key store and return the end-to-end key between A and B.

    Chronological store-and-forward, as the module docstring describes: the
    passes of both stations are ordered by their **end** instant (a block is
    complete when its pass ends), each live pass adds its key to its side's
    store, and whenever the opposite store is non-empty the two are paired
    first-in-first-out and the pairing is one delivery event.

    Parameters
    ----------
    volume_a, volume_b : PassKeyVolume
        Per-pass key of each station with the same satellite, on the same
        grid, in the same regime. Computed by the caller per station; under
        :attr:`~quoss.system.multi_ogs.AggregationPolicy.SUM`, since a relay
        needs both passes to have happened.
    degradations : DegradationLog
        Receives an ``INFO`` naming the trust assumption and the composed
        ``eps``, a ``WARNING`` when key is stranded on board at the end of the
        window, and a ``WARNING`` in the asymptotic regime that no security
        claim exists.
    names : tuple[str, str], optional
        Station names for the result. Defaults to ``("A", "B")``.

    Returns
    -------
    RelayKeyVolume
        Every delivery with its latency, the daily totals, the residual store
        and the composed security.

    Raises
    ------
    DomainError
        If the volumes are not on one grid, in one regime, or involve more
        than one satellite; or if the composed failure probability reaches one.

    Examples
    --------
    A station relayed to itself: every pass pairs with itself at zero latency
    and the whole day comes through.

    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.system.key_volume import _reference_volume
    >>> volume = _reference_volume()
    >>> log = DegradationLog()
    >>> relay = trusted_node_relay(volume, volume, degradations=log)
    >>> relay.delivered_bits
    array([190581., 242404.])
    >>> relay.latency_s
    array([0., 0.])
    >>> float(relay.total_bits) == float(volume.total_bits) == relay.upper_bound_bits
    True
    >>> relay.stranded_bits
    0.0

    Four blocks were consumed — two of each side — so the day's end-to-end key
    is ``4e-10``-secure, not ``1e-10``:

    >>> f"{relay.security.secrecy:.1e}"
    '4.0e-10'
    >>> [entry.code for entry in log]
    ['relay.trusted-node']
    """
    _validated_pair(volume_a, volume_b)
    station_names = (str(names[0]), str(names[1]))
    volumes = (volume_a, volume_b)

    # One merged, chronological list of live passes. A pass with no key neither
    # stores nor delivers, so it is not an event; ties in end time put A first,
    # which is a convention and changes nothing about how much is delivered.
    side = np.concatenate([np.full(v.n_passes, i, dtype=np.int64) for i, v in enumerate(volumes)])
    row = np.concatenate([np.arange(v.n_passes, dtype=np.int64) for v in volumes])
    end_s = np.concatenate([v.samples.table.end_s for v in volumes])
    bits = np.concatenate([np.asarray(v.key_bits, dtype=np.float64) for v in volumes])
    day = np.concatenate([v.samples.table.day_number for v in volumes])
    live = bits > 0.0
    order = np.lexsort((side[live], end_s[live]))
    side, row, end_s, bits, day = (
        side[live][order],
        row[live][order],
        end_s[live][order],
        bits[live][order],
        day[live][order],
    )

    stores: tuple[deque[tuple[float, float, int]], deque[tuple[float, float, int]]] = (
        deque(),
        deque(),
    )
    consumed: tuple[set[int], set[int]] = (set(), set())
    delivered: list[float] = []
    delivered_at: list[float] = []
    delivering_side: list[int] = []
    delivering_pass: list[int] = []
    latency: list[float] = []
    mean_latency: list[float] = []
    delivery_day: list[int] = []

    for this_side, this_row, this_end, this_bits, this_day in zip(
        side.tolist(), row.tolist(), end_s.tolist(), bits.tolist(), day.tolist(), strict=True
    ):
        other = stores[1 - this_side]
        remaining = float(this_bits)
        paired = 0.0
        oldest_age = 0.0
        age_weighted = 0.0
        while remaining > 0.0 and other:
            stored_end, stored_bits, stored_row = other[0]
            take = min(remaining, stored_bits)
            age = float(this_end) - stored_end
            oldest_age = max(oldest_age, age)
            age_weighted += take * age
            paired += take
            remaining -= take
            consumed[1 - this_side].add(stored_row)
            if take >= stored_bits:
                other.popleft()
            else:
                other[0] = (stored_end, stored_bits - take, stored_row)
        if paired > 0.0:
            consumed[this_side].add(this_row)
            delivered.append(paired)
            delivered_at.append(float(this_end))
            delivering_side.append(int(this_side))
            delivering_pass.append(int(this_row))
            latency.append(oldest_age)
            # A bit-weighted mean of ages cannot exceed the largest age; the
            # minimum removes only floating-point rounding, which is visible
            # when a block is a subnormal number of bits and nowhere else.
            mean_latency.append(min(age_weighted / paired, oldest_age))
            delivery_day.append(int(this_day))
        if remaining > 0.0:
            stores[this_side].append((float(this_end), remaining, int(this_row)))

    residual = tuple(float(sum(entry[1] for entry in store)) for store in stores)
    total = tuple(float(v.total_bits) for v in volumes)
    delivered_array = np.asarray(delivered, dtype=np.float64)
    days, inverse = np.unique(np.asarray(delivery_day, dtype=np.int64), return_inverse=True)
    daily = np.bincount(inverse, weights=delivered_array, minlength=int(days.size))

    security: SecurityParameters | None = None
    if volume_a.regime is KeyRegime.FINITE:
        assert volume_a.finite is not None and volume_b.finite is not None  # by PassKeyVolume
        if delivered_array.size:
            composed_a = composed_security(volume_a.finite.security, len(consumed[0]))
            composed_b = composed_security(volume_b.finite.security, len(consumed[1]))
            correctness = composed_a.correctness + composed_b.correctness
            secrecy = composed_a.secrecy + composed_b.secrecy
            if correctness >= 1.0 or secrecy >= 1.0:
                raise DomainError(
                    f"composing {len(consumed[0])} blocks of A and {len(consumed[1])} of B gives "
                    f"eps_cor = {correctness:g}, eps_sec = {secrecy:g}, which is not a failure "
                    "probability: the end-to-end key has no security claim."
                )
            security = SecurityParameters(correctness=correctness, secrecy=secrecy)
        degradations.info(
            "relay.trusted-node",
            f"the end-to-end key between {station_names[0]!r} and {station_names[1]!r} is "
            "delivered by the satellite announcing K_A xor K_B, so the satellite holds both keys "
            "in the clear and MUST BE TRUSTED: this figure is conditional on that. "
            + (
                f"It consumed {len(consumed[0])} blocks of A and {len(consumed[1])} of B, so its "
                f"failure probabilities are the union bound eps_sec = {security.secrecy:.3e}, "
                f"eps_cor = {security.correctness:.3e}."
                if security is not None
                else "Nothing was delivered, so there is no key to make a security claim about."
            ),
            where="quoss.system.relay.trusted_node_relay",
            blocks_a=len(consumed[0]),
            blocks_b=len(consumed[1]),
            composed_secrecy=None if security is None else security.secrecy,
        )
    else:
        degradations.warn(
            "relay.no-security-claim",
            "both volumes are ASYMPTOTIC, so the relayed key carries no failure probability: "
            "there is no eps to compose because no finite-block statement was made on either "
            "side. The bit count is an upper bound on what the relay delivers, as its inputs are.",
            where="quoss.system.relay.trusted_node_relay",
        )
    stranded = residual[0] + residual[1]
    if stranded > 0.0:
        which = station_names[0] if residual[0] > 0.0 else station_names[1]
        degradations.warn(
            "relay.key-stranded-on-board",
            f"{stranded:.0f} bits of {which!r} key are still in the on-board store at the end of "
            "the window, unpaired. They are not lost — the next pass over the other station "
            "would pair them — but they are not delivered inside this window, and a memory "
            "bound would have to hold at least this much.",
            where="quoss.system.relay.trusted_node_relay",
            stranded_bits=stranded,
            station=which,
        )

    return RelayKeyVolume(
        names=station_names,
        delivered_bits=delivered_array,
        delivered_at_s=np.asarray(delivered_at, dtype=np.float64),
        delivering_side=np.asarray(delivering_side, dtype=np.int64),
        delivering_pass=np.asarray(delivering_pass, dtype=np.int64),
        latency_s=np.asarray(latency, dtype=np.float64),
        mean_latency_s=np.asarray(mean_latency, dtype=np.float64),
        day_number=days.astype(np.int64),
        daily_bits=np.asarray(daily, dtype=np.float64),
        total_a_bits=total[0],
        total_b_bits=total[1],
        residual_a_bits=residual[0],
        residual_b_bits=residual[1],
        security=security,
        regime=volume_a.regime,
        protocols=(volume_a.protocol, volume_b.protocol),
    )
