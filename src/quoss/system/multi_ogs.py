r"""Several ground stations: what they add up to, and what one satellite terminal can serve.

What this module is for, for a reader arriving from one station
---------------------------------------------------------------
Everything up to :mod:`quoss.system.key_volume` is one station's view: one set
of look angles, one pass table, one key volume. A mission has several stations,
for two different reasons that lead to two different arithmetics, and the
whole content of this module is keeping them apart.

**Reason one: more key.** Each station harvests its own key with the
satellite, the satellite stores all of them, and pairs them up later
(``relay.py``). The stations do not compete; the day's key is the **sum** over
stations. That is :attr:`AggregationPolicy.SUM`.

**Reason two: weather.** A second station 2000 km away sees different clouds,
so the mission keeps working when the first is under a front. But the
satellite has **one optical terminal**, so it can talk to one station at a
time: when two stations' passes overlap in time, only one of them can happen.
The day's key is then the best **non-overlapping** selection of passes. That is
:attr:`AggregationPolicy.BEST_AVAILABLE`, and it is a scheduling problem.

The two policies give different numbers from the same inputs, and on the
reference day the difference is measured below. A module that offered one
aggregation would have had to pick, and neither is "the" answer: SUM is what a
trusted-node relay consumes, BEST_AVAILABLE is what a single-terminal satellite
can deliver.

Availability is a multiplier on an expectation, not on a key
-----------------------------------------------------------
When a per-pass cloud-free probability is supplied (from
:func:`~quoss.system.pcflos.pass_availability`), every figure labelled
``expected`` is ``bits * availability``: the **expected** bits, over the
weather, of a pass that certifies ``bits`` when it happens. The finite-key
bound certifies each pass's bits; the cloud only decides whether the pass
happens. An expected figure is therefore a planning number for a season, not a
key anyone holds on a given night, and this module keeps the certified and
expected columns side by side rather than replacing one with the other.

The scheduler is exact, and here is why that costs nothing
----------------------------------------------------------
Selecting a non-overlapping subset of intervals with maximum total weight is
**weighted interval scheduling**, and it has an exact solution in
``O(n log n)``: sort the passes by end time, and for each pass ``j`` let
``p(j)`` be the last pass that ends before ``j`` starts (a binary search);
then

.. math::

    M_j = \max\bigl(M_{j-1},\; w_j + M_{p(j)}\bigr)

is the best total using the first ``j`` passes, and backtracking through the
``max`` recovers which ones. A day of a few hundred passes is a loop of a few
hundred steps, which is why this is the one place in ``system/`` with a Python
loop over passes and why that is fine: the loop is over passes, not over the
time axis, and it runs once.

The obvious alternative, **greedy by key** (take the richest pass, discard
whatever overlaps it, repeat), is not exact: a single rich pass in the middle
of two slightly poorer ones that do not overlap each other beats it. On the
reference day the two agree — the conflicts happen to be pairwise and the
richer pass wins each — and ``tests/system/test_multi_ogs.py::
TestTheSchedulerIsExact`` both measures that and builds the instance where
greedy loses, and checks the dynamic programme against a brute force over
every subset of small random instances with Hypothesis. The exact one costs
nothing more than the greedy one, so there was no trade to make.

**A slew gap.** A terminal that finishes one pass needs time to slew and
settle before the next. ``minimum_gap_s`` is that time, and two scheduled
passes must be separated by at least it. It defaults to ``0.0`` — no gap —
because the value is a terminal property this project has no source for, and
zero is the only value that is not a guess; the docstring of
:func:`aggregate_stations` says what it changes.

**One satellite terminal, and only that.** The conflict modelled is that a
satellite cannot serve two stations at once. The mirror constraint — a ground
station cannot track two satellites at once — is not modelled, because the
project's scope is one satellite (``notes/LAST_CHANGES.md``, decision of
2026-09-10). Inputs where that constraint would bind — two satellites over
one station at the same time — are refused with a ``DomainError`` rather than
scheduled wrongly.

Measured on the reference day
-----------------------------
Three stations: Castelldefels (the reference, 41.2750 N, 1.9875 E), Calar Alto
(37.2236 N, 2.5461 W, 2168 m, 596 km away) and the ESA optical ground station
on Tenerife (28.298 N, 16.5118 W, 2400 m, 2214 km away), each with the
reference receiver, on the reference day at a 10 degree mask. The finite key
per station and pass:

==============  =======  ==================================
Station         Passes   Bits per pass
==============  =======  ==================================
Castelldefels   4        190 581, 0, 242 404, 0
Calar Alto      4        47 108, 0, 9 817, 0
Tenerife OGS    2        228 851, 333 846
==============  =======  ==================================

Calar Alto's passes overlap Castelldefels' — the two stations are 596 km
apart and the same orbit crosses both — so under one terminal they conflict,
and the scheduler keeps Castelldefels' 190 581 over Calar Alto's 47 108 and
242 404 over 9 817. Tenerife's two passes overlap only the two dead passes of
the other stations, so they cost nothing to keep. The result:

==================  ==============  ===============
Policy              Bits            Passes kept
==================  ==============  ===============
SUM                 1 052 607       10 of 10
BEST_AVAILABLE      995 682         4 of 10
==================  ==============  ===============

Site diversity bought this mission 2.3 times Castelldefels' own 432 985 bits
under one terminal. The six passes it dropped — four of them dead passes that
overlapped a live one — were worth 56 925 bits, 5.4 % of the sum. All of it is
in
``tests/system/test_multi_ogs.py::TestOnTheReferenceDay``.

What this module deliberately does not do
-----------------------------------------
- **Compute look angles, passes or key.** The caller does that per station —
  :func:`~quoss.orbits.geometry.look_angles` takes one station, by design —
  and hands the volumes in. Doing it here would put every knob of three
  packages in one signature.
- **Compose a security claim across stations.** Each station's key is a
  separate key with a separate partner; concatenating them is meaningless
  until a relay pairs them, and that composition lives in ``relay.py``.
- **Model the ground terminal's own conflicts**, per the scope above.
- **Choose a decorrelation length.** The joint cloud probability is
  ``pcflos.py``; this module takes availabilities as given.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``N``                                   number of stations
``w_j``                                 weight of pass ``j`` (expected bits)
``p(j)``                                last pass compatible with ``j``
``M_j``                                 best total over the first ``j`` passes
``g``                                   minimum gap between scheduled passes (s)
======================================  ====================================
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

import numpy as np

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, IntArray, TimeGrid, frozen_copy
from quoss.qkd.base import KeyRegime
from quoss.system.key_volume import PassKeyVolume
from quoss.system.pcflos import station_separation_km

__all__ = [
    "AggregationPolicy",
    "MultiStationKeyVolume",
    "StationPassKeys",
    "StationSet",
    "aggregate_stations",
    "greedy_schedule_passes",
    "same_grid",
    "schedule_passes",
]


class AggregationPolicy(StrEnum):
    """How several stations' passes combine into one figure.

    Attributes
    ----------
    SUM
        Every station harvests its own key; the total is the sum. Valid when
        the satellite is a trusted node that stores each key and pairs them
        later, which is what ``relay.py`` consumes — and only then, because it
        ignores that one terminal cannot serve two stations at once.
    BEST_AVAILABLE
        One optical terminal on the satellite: passes whose windows overlap
        conflict, and the exact weighted-interval schedule keeps the
        non-overlapping subset with the most expected bits.
    """

    SUM = "sum"
    BEST_AVAILABLE = "best_available"


def same_grid(a: TimeGrid, b: TimeGrid) -> bool:
    """Return True if two grids are the same time axis.

    :class:`~quoss.core.types.TimeGrid` is ``eq=False`` — identity, not
    contents — because comparing million-sample axes on every dataclass
    equality would be a silent cost. Pass windows from different stations are
    compared here on their **contents**: same epoch, same samples. Two grids
    with different epochs would put every pass at a different absolute time
    while every window stayed plausible, which is the mismatch with no symptom.

    Parameters
    ----------
    a, b : TimeGrid
        The two axes.

    Returns
    -------
    bool
        Whether they describe the same instants.

    Examples
    --------
    >>> from quoss.core.types import TimeGrid
    >>> one = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, step_s=1.0)
    >>> two = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, step_s=1.0)
    >>> shifted = TimeGrid.uniform(epoch_jd=2460677.5, duration_s=10.0, step_s=1.0)
    >>> same_grid(one, two), same_grid(one, shifted)
    (True, False)
    """
    return a is b or (
        a.epoch_jd == b.epoch_jd and a.n == b.n and bool(np.array_equal(a.t_s, b.t_s))
    )


@dataclass(frozen=True, eq=False, slots=True)
class StationSet:
    """The ground stations of a mission: names and WGS-84 positions.

    A columnar record rather than a list of station objects, for the same
    reason :class:`~quoss.system.passes.PassTable` is: every question asked of
    it ("how far apart", "which index is Tenerife") is an array operation.

    Attributes
    ----------
    names : tuple[str, ...]
        Unique, non-empty names, one per station. The names are what
        ``scenario/`` and ``relay.py`` address stations by.
    latitude_rad : FloatArray
        Geodetic latitudes, radians, in ``[-pi/2, pi/2]``.
    longitude_rad : FloatArray
        Longitudes, radians, positive east.
    altitude_km : FloatArray
        Heights above the WGS-84 ellipsoid, km.

    Raises
    ------
    DomainError
        If the arrays are not one-dimensional and of the same length as
        ``names``, if a name repeats or is empty, if any coordinate is
        non-finite, or if a latitude is outside ``[-pi/2, pi/2]``.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.units import deg_to_rad
    >>> stations = StationSet(
    ...     names=("castelldefels", "tenerife_ogs"),
    ...     latitude_rad=np.asarray(deg_to_rad(np.array([41.2750, 28.298]))),
    ...     longitude_rad=np.asarray(deg_to_rad(np.array([1.9875, -16.5118]))),
    ...     altitude_km=np.array([0.030, 2.400]),
    ... )
    >>> stations.n
    2
    >>> stations.index("tenerife_ogs")
    1
    >>> np.round(stations.separation_km(), 1)
    array([[   0. , 2213.8],
           [2213.8,    0. ]])
    """

    names: tuple[str, ...]
    latitude_rad: FloatArray
    longitude_rad: FloatArray
    altitude_km: FloatArray

    def __post_init__(self) -> None:
        """Validate the columns, then freeze them."""
        names = tuple(self.names)
        if not names:
            raise DomainError("a StationSet needs at least one station.")
        if any(not isinstance(name, str) or not name for name in names):
            raise DomainError(f"every station name must be a non-empty string, got {names!r}.")
        if len(set(names)) != len(names):
            raise DomainError(
                f"station names must be unique, got {names!r}: a repeated name would make "
                "'the key of station X' ambiguous."
            )
        object.__setattr__(self, "names", names)
        for field in ("latitude_rad", "longitude_rad", "altitude_km"):
            value = np.asarray(getattr(self, field), dtype=np.float64)
            if value.shape != (len(names),):
                raise DomainError(
                    f"{field} has shape {value.shape}, but there are {len(names)} names. One "
                    "coordinate per station."
                )
            if not np.all(np.isfinite(value)):
                raise DomainError(f"{field} contains non-finite values.")
            object.__setattr__(self, field, frozen_copy(value))
        if np.any(np.abs(self.latitude_rad) > 0.5 * np.pi):
            raise DomainError(
                "latitude_rad must lie in [-pi/2, pi/2]. A value outside it is almost always "
                "degrees that were never converted."
            )

    @property
    def n(self) -> int:
        """Number of stations."""
        return len(self.names)

    def __len__(self) -> int:
        return self.n

    def index(self, name: str) -> int:
        """Return the position of ``name``, or raise.

        Parameters
        ----------
        name : str
            A station name.

        Returns
        -------
        int
            Its index in every column.

        Raises
        ------
        DomainError
            If no station has that name.
        """
        try:
            return self.names.index(name)
        except ValueError:
            raise DomainError(f"no station named {name!r}; known: {self.names!r}.") from None

    def separation_km(self) -> FloatArray:
        """Return the ``(N, N)`` matrix of surface separations, km.

        :func:`~quoss.system.pcflos.station_separation_km` on this set's
        coordinates: the chord through the WGS-84 ellipsoid as an arc on the
        mean sphere, zero on the diagonal.
        """
        return station_separation_km(self.latitude_rad, self.longitude_rad)

    def __repr__(self) -> str:
        return f"StationSet(n={self.n}, names={self.names!r})"


@dataclass(frozen=True, eq=False, slots=True)
class StationPassKeys:
    """One station's passes, key, availability, and which passes the policy kept.

    Attributes
    ----------
    station : str
        The station's name.
    volume : PassKeyVolume
        Its per-pass key, carrying the pass table and the mask.
    availability : FloatArray or None
        Per-pass cloud-free probability in ``[0, 1]``, or ``None`` when no
        cloud model was supplied — in which case every ``expected`` figure
        equals its certified counterpart.
    selected : BoolArray
        Which passes the aggregation policy kept: all of them under
        :attr:`AggregationPolicy.SUM`, the scheduled subset under
        :attr:`AggregationPolicy.BEST_AVAILABLE`.

    Raises
    ------
    DomainError
        If ``availability`` or ``selected`` does not have one entry per pass,
        or an availability lies outside ``[0, 1]``.
    """

    station: str
    volume: PassKeyVolume
    availability: FloatArray | None
    selected: BoolArray

    def __post_init__(self) -> None:
        """Validate the per-pass columns against the volume."""
        if not isinstance(self.volume, PassKeyVolume):
            raise DomainError(f"volume must be a PassKeyVolume, got {type(self.volume).__name__}.")
        n_passes = self.volume.n_passes
        if self.availability is not None:
            availability = np.asarray(self.availability, dtype=np.float64)
            if availability.shape != (n_passes,):
                raise DomainError(
                    f"availability for {self.station!r} has shape {availability.shape}, but the "
                    f"station has {n_passes} passes. One probability per pass, from "
                    "pcflos.pass_availability."
                )
            if not np.all(np.isfinite(availability)) or np.any(
                (availability < 0.0) | (availability > 1.0)
            ):
                raise DomainError(
                    f"availability for {self.station!r} must lie in [0, 1]: it is the "
                    "probability that the pass happens."
                )
            object.__setattr__(self, "availability", frozen_copy(availability))
        selected = np.asarray(self.selected)
        if selected.dtype != np.bool_ or selected.shape != (n_passes,):
            raise DomainError(
                f"selected for {self.station!r} must be a boolean mask of shape ({n_passes},), "
                f"got dtype {selected.dtype} and shape {selected.shape}."
            )
        object.__setattr__(self, "selected", selected.copy())

    @property
    def expected_bits(self) -> FloatArray:
        """``key_bits * availability`` per pass — an expectation over weather.

        Equal to ``key_bits`` when no availability was supplied. Not a key
        anyone holds: the finite-key bound certifies ``key_bits`` on the night
        the pass happens, and the cloud decides whether it does.
        """
        bits = np.asarray(self.volume.key_bits, dtype=np.float64)
        if self.availability is None:
            return bits
        expected: FloatArray = bits * self.availability
        return expected

    @property
    def scheduled_bits(self) -> float:
        """Certified bits summed over the passes the policy kept."""
        return float(np.sum(np.asarray(self.volume.key_bits)[self.selected]))

    @property
    def scheduled_expected_bits(self) -> float:
        """Expected bits summed over the passes the policy kept."""
        return float(np.sum(self.expected_bits[self.selected]))

    def __repr__(self) -> str:
        return (
            f"StationPassKeys({self.station!r}, n_passes={self.volume.n_passes}, "
            f"selected={int(self.selected.sum())}, scheduled_bits={self.scheduled_bits:.3e})"
        )


@dataclass(frozen=True, eq=False, slots=True)
class MultiStationKeyVolume:
    """Bits per station and per UTC day under one aggregation policy.

    Attributes
    ----------
    stations : StationSet
        The stations, in the order of every per-station column.
    policy : AggregationPolicy
        Which arithmetic produced the totals.
    per_station : tuple[StationPassKeys, ...]
        Each station's passes with the selection the policy made.
    station_bits : FloatArray
        Certified bits per station over its selected passes, shape ``(N,)``.
    station_expected_bits : FloatArray
        The same, weighted by availability. Equal to :attr:`station_bits`
        when no availability was given.
    day_number : IntArray
        Julian Day Numbers of the UTC days holding at least one selected pass,
        ascending.
    daily_bits, daily_expected_bits : FloatArray
        Totals over all stations per day, certified and expected.
    conflicts_dropped : int
        Passes not selected because they overlapped a richer one. Zero under
        :attr:`AggregationPolicy.SUM`.
    minimum_gap_s : float
        The slew gap the schedule respected.
    regime : KeyRegime
        Inherited from the volumes, which must agree.

    Raises
    ------
    DomainError
        If the per-station columns do not have one entry per station, or the
        daily columns disagree in length, or any figure is negative.

    Examples
    --------
    See :func:`aggregate_stations`.
    """

    stations: StationSet
    policy: AggregationPolicy
    per_station: tuple[StationPassKeys, ...]
    station_bits: FloatArray
    station_expected_bits: FloatArray
    day_number: IntArray
    daily_bits: FloatArray
    daily_expected_bits: FloatArray
    conflicts_dropped: int
    minimum_gap_s: float
    regime: KeyRegime

    def __post_init__(self) -> None:
        """Validate shapes and signs, then freeze."""
        if not isinstance(self.stations, StationSet):
            raise DomainError(f"stations must be a StationSet, got {type(self.stations).__name__}.")
        object.__setattr__(self, "policy", AggregationPolicy(self.policy))
        object.__setattr__(self, "regime", KeyRegime(self.regime))
        per_station = tuple(self.per_station)
        if len(per_station) != self.stations.n or any(
            not isinstance(item, StationPassKeys) for item in per_station
        ):
            raise DomainError(
                f"per_station must hold one StationPassKeys per station ({self.stations.n}), "
                f"got {len(per_station)} entries."
            )
        object.__setattr__(self, "per_station", per_station)
        for name in ("station_bits", "station_expected_bits"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (self.stations.n,):
                raise DomainError(
                    f"{name} has shape {value.shape}, but there are {self.stations.n} stations."
                )
            if not np.all(np.isfinite(value)) or np.any(value < 0.0):
                raise DomainError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, frozen_copy(value))
        days = np.asarray(self.day_number, dtype=np.int64)
        if days.ndim != 1 or (days.size > 1 and not np.all(np.diff(days) > 0)):
            raise DomainError("day_number must be a 1-D strictly ascending array.")
        object.__setattr__(self, "day_number", days)
        for name in ("daily_bits", "daily_expected_bits"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != days.shape:
                raise DomainError(
                    f"{name} has shape {value.shape}, but day_number has {days.shape}."
                )
            if not np.all(np.isfinite(value)) or np.any(value < 0.0):
                raise DomainError(f"{name} must be finite and non-negative.")
            object.__setattr__(self, name, frozen_copy(value))
        if int(self.conflicts_dropped) < 0:
            raise DomainError("conflicts_dropped cannot be negative.")
        object.__setattr__(self, "conflicts_dropped", int(self.conflicts_dropped))
        gap = float(self.minimum_gap_s)
        if not np.isfinite(gap) or gap < 0.0:
            raise DomainError(f"minimum_gap_s must be finite and non-negative, got {gap}.")
        object.__setattr__(self, "minimum_gap_s", gap)

    @property
    def total_bits(self) -> float:
        """Certified bits over every station's selected passes."""
        return float(np.sum(self.station_bits))

    @property
    def total_expected_bits(self) -> float:
        """Expected bits over every station's selected passes."""
        return float(np.sum(self.station_expected_bits))

    @property
    def passes_selected(self) -> int:
        """How many passes, over all stations, the policy kept."""
        return int(sum(int(item.selected.sum()) for item in self.per_station))

    def __repr__(self) -> str:
        return (
            f"MultiStationKeyVolume({self.policy}, n_stations={self.stations.n}, "
            f"total_bits={self.total_bits:.3e}, passes_selected={self.passes_selected}, "
            f"conflicts_dropped={self.conflicts_dropped})"
        )


def _validated_intervals(
    start_s: FloatArray, end_s: FloatArray, weight: FloatArray, minimum_gap_s: float
) -> tuple[FloatArray, FloatArray, FloatArray, float]:
    """Check the three interval columns and the gap, returning them as float arrays."""
    start = np.asarray(start_s, dtype=np.float64)
    end = np.asarray(end_s, dtype=np.float64)
    value = np.asarray(weight, dtype=np.float64)
    if start.ndim != 1 or end.shape != start.shape or value.shape != start.shape:
        raise DomainError(
            f"start_s, end_s and weight must be 1-D arrays of one length, got shapes "
            f"{start.shape}, {end.shape}, {value.shape}."
        )
    if not (np.all(np.isfinite(start)) and np.all(np.isfinite(end)) and np.all(np.isfinite(value))):
        raise DomainError("interval columns contain non-finite values.")
    if np.any(end <= start):
        raise DomainError("every interval must have end_s strictly above start_s.")
    if np.any(value < 0.0):
        raise DomainError(
            "weights must be non-negative: a pass is worth what it certifies, never less "
            "than nothing."
        )
    gap = float(minimum_gap_s)
    if not np.isfinite(gap) or gap < 0.0:
        raise DomainError(
            f"minimum_gap_s must be finite and non-negative, got {gap}. It is the slew and "
            "settle time between two passes, in seconds; 0.0 means none."
        )
    return start, end, value, gap


def schedule_passes(
    start_s: FloatArray,
    end_s: FloatArray,
    weight: FloatArray,
    *,
    minimum_gap_s: float = 0.0,
) -> BoolArray:
    r"""Return the maximum-weight set of pairwise compatible intervals. Exact.

    Two intervals are **compatible** when one ends at least ``minimum_gap_s``
    before the other starts. The answer is the standard weighted interval
    scheduling dynamic programme: sort by end time, binary-search each
    interval's latest compatible predecessor, and take

    .. math::

        M_j = \max\bigl(M_{j-1},\; w_j + M_{p(j)}\bigr),

    then backtrack. ``O(n log n)``; the loop is over passes and runs once, so
    a day of a few hundred passes is a few hundred steps.

    **Ties, and what "not selected" means.** The dynamic programme leaves out
    an interval that adds nothing, so on its own it would report a dead pass
    (zero key) as unscheduled even when it conflicts with nothing. A second
    step adds back, in end order, every unselected interval that is compatible
    with everything selected — which can only be a zero-weight one, since a
    positive-weight compatible interval would have raised the optimum. After
    it, an interval is unselected **if and only if it conflicts with a selected
    one**, which is what a "passes dropped by conflict" count needs, and the
    total is unchanged, which is what the brute-force test checks.

    Parameters
    ----------
    start_s, end_s : FloatArray
        Interval boundaries, seconds on one axis, ``end_s > start_s``.
    weight : FloatArray
        Non-negative value of each interval.
    minimum_gap_s : float, optional
        Slew and settle time two selected intervals must be separated by.
        Defaults to ``0.0``.

    Returns
    -------
    BoolArray
        Mask of the selected intervals, in the input order.

    Raises
    ------
    DomainError
        If the columns disagree in shape, an interval is empty, a weight is
        negative, or the gap is negative.

    Examples
    --------
    The instance where greedy-by-weight loses: a rich middle interval that
    overlaps two poorer ones which together are worth more.

    >>> import numpy as np
    >>> start = np.array([0.0, 4.0, 9.0])
    >>> end = np.array([5.0, 10.0, 14.0])
    >>> weight = np.array([4.0, 6.0, 4.0])
    >>> schedule_passes(start, end, weight)
    array([ True, False,  True])
    >>> greedy_schedule_passes(start, end, weight)
    array([False,  True, False])

    A slew gap makes two back-to-back passes incompatible:

    >>> schedule_passes(np.array([0.0, 5.5]), np.array([5.0, 9.0]), np.array([1.0, 1.0]))
    array([ True,  True])
    >>> schedule_passes(
    ...     np.array([0.0, 5.5]), np.array([5.0, 9.0]), np.array([1.0, 1.0]), minimum_gap_s=1.0
    ... )
    array([ True, False])
    """
    start, end, value, gap = _validated_intervals(start_s, end_s, weight, minimum_gap_s)
    n = int(start.size)
    selected = np.zeros(n, dtype=np.bool_)
    if n == 0:
        return selected
    order = np.argsort(end, kind="stable")
    start_sorted = start[order]
    end_sorted = end[order]
    value_sorted = value[order]
    # Latest interval (in end order) ending at or before start - gap; 0 means
    # none, and the DP tables are offset by one so that M[0] = 0.
    predecessor = np.searchsorted(end_sorted, start_sorted - gap, side="right")
    best = np.zeros(n + 1, dtype=np.float64)
    take = np.zeros(n + 1, dtype=np.bool_)
    for j in range(1, n + 1):
        with_j = value_sorted[j - 1] + best[predecessor[j - 1]]
        # Strict inequality: an interval that adds nothing is left out.
        if with_j > best[j - 1]:
            best[j] = with_j
            take[j] = True
        else:
            best[j] = best[j - 1]
    j = n
    while j > 0:
        if take[j]:
            selected[order[j - 1]] = True
            j = int(predecessor[j - 1])
        else:
            j -= 1
    # Completion: an unselected interval compatible with everything selected
    # is added, in end order. It can only be one of zero weight (a positive one
    # would have raised the optimum), so the total is unchanged, and afterwards
    # "unselected" means "conflicts with a selected interval" and nothing else.
    for candidate in order:
        if selected[candidate]:
            continue
        chosen_start = start[selected]
        chosen_end = end[selected]
        compatible = (chosen_end + gap <= start[candidate]) | (chosen_start >= end[candidate] + gap)
        if bool(np.all(compatible)):
            selected[candidate] = True
    return selected


def greedy_schedule_passes(
    start_s: FloatArray,
    end_s: FloatArray,
    weight: FloatArray,
    *,
    minimum_gap_s: float = 0.0,
) -> BoolArray:
    """Return the greedy-by-weight selection. **Not exact**; exists to be measured against.

    Take the heaviest interval, discard everything incompatible with it,
    repeat. It is what "keep the one with more key" means if read literally,
    and :func:`schedule_passes` beats it whenever a heavy interval sits between
    two lighter ones that together outweigh it — see that function's example.
    It is public so that the comparison in the tests and the module docstring
    is between two named functions rather than a claim about one.

    Parameters
    ----------
    start_s, end_s, weight, minimum_gap_s
        As in :func:`schedule_passes`.

    Returns
    -------
    BoolArray
        Mask of the selected intervals, in the input order.

    Raises
    ------
    DomainError
        As in :func:`schedule_passes`.
    """
    start, end, value, gap = _validated_intervals(start_s, end_s, weight, minimum_gap_s)
    n = int(start.size)
    selected = np.zeros(n, dtype=np.bool_)
    available = np.ones(n, dtype=np.bool_)
    for candidate in np.argsort(-value, kind="stable"):
        if not available[candidate]:
            continue
        selected[candidate] = True
        compatible = (end + gap <= start[candidate]) | (start >= end[candidate] + gap)
        available &= compatible
        available[candidate] = False
    return selected


def _validated_volumes(
    stations: StationSet,
    volumes: Sequence[PassKeyVolume],
    availability: Sequence[FloatArray] | None,
) -> tuple[tuple[PassKeyVolume, ...], TimeGrid, KeyRegime]:
    """Check that the volumes are one per station, on one grid, in one regime."""
    if not isinstance(stations, StationSet):
        raise DomainError(f"stations must be a StationSet, got {type(stations).__name__}.")
    items = tuple(volumes)
    if len(items) != stations.n:
        raise DomainError(
            f"volumes must hold one PassKeyVolume per station ({stations.n}), got {len(items)}. "
            "A station with no passes still needs an entry; the engine builds one per station."
        )
    for index, item in enumerate(items):
        if not isinstance(item, PassKeyVolume):
            raise DomainError(
                f"volumes[{index}] must be a PassKeyVolume, got {type(item).__name__}."
            )
    if availability is not None and len(availability) != stations.n:
        raise DomainError(
            f"availability must hold one array per station ({stations.n}), got "
            f"{len(availability)}; pass None for no cloud model at all rather than a partial list."
        )
    grid = items[0].samples.table.grid
    regime = items[0].regime
    for index, item in enumerate(items[1:], start=1):
        if not same_grid(item.samples.table.grid, grid):
            raise DomainError(
                f"volumes[{index}] ({stations.names[index]!r}) is on a different time grid from "
                f"volumes[0] ({stations.names[0]!r}). Pass windows are only comparable on one "
                "axis: a different epoch would put every pass at a different absolute time while "
                "every window stayed plausible."
            )
        if item.regime is not regime:
            raise DomainError(
                f"volumes[{index}] is {item.regime} but volumes[0] is {regime}. Summing an "
                "asymptotic upper bound with a finite-key length is not a total of anything."
            )
    return items, grid, regime


def aggregate_stations(
    stations: StationSet,
    volumes: Sequence[PassKeyVolume],
    *,
    availability: Sequence[FloatArray] | None,
    policy: AggregationPolicy,
    degradations: DegradationLog,
    minimum_gap_s: float = 0.0,
) -> MultiStationKeyVolume:
    """Combine several stations' pass key volumes under one policy.

    Parameters
    ----------
    stations : StationSet
        The stations, in the order of ``volumes``.
    volumes : Sequence[PassKeyVolume]
        One per station, all on the same time grid and in the same regime.
        The caller computed them: look angles, passes and key per station.
    availability : Sequence[FloatArray] or None
        Per station, a per-pass cloud-free probability (from
        :func:`~quoss.system.pcflos.pass_availability`), or ``None`` for no
        cloud model — in which case expected and certified figures coincide.
        **Required, with no default**, because "I have no cloud model" and "I
        forgot" must be different edits.
    policy : AggregationPolicy
        :attr:`AggregationPolicy.SUM` or :attr:`AggregationPolicy.BEST_AVAILABLE`.
        Required: the two answer different questions (see the module
        docstring) and differ by 5.4 % on the reference day.
    degradations : DegradationLog
        Receives an ``INFO`` entry when passes were dropped by conflict, and
        one when availability was given, saying that expected bits are an
        expectation over weather and not a certified key.
    minimum_gap_s : float, optional
        Slew and settle time two scheduled passes must be separated by, s.
        Defaults to ``0.0``: the value is a property of the terminal that no
        source verified for this project supplies, so zero — no gap — is the
        only non-invented value. Under ``SUM`` it is carried but unused, since
        the stations do not share a terminal in that policy. A positive gap can
        only remove passes from a ``BEST_AVAILABLE`` schedule.

    Returns
    -------
    MultiStationKeyVolume
        Per-station and per-day totals with the selection made.

    Raises
    ------
    DomainError
        If the volumes are not one per station on one grid in one regime, if
        an availability array is missing or out of range, if the gap is
        negative, or — under ``BEST_AVAILABLE`` — if two passes of different
        satellites overlap at one station, a conflict this module does not
        model (project scope: one satellite).

    Examples
    --------
    Two synthetic stations whose only passes overlap, so one terminal must
    choose. The volumes are built from the reference day's own passes, split
    so that both stations "see" the same two keyed passes:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.units import deg_to_rad
    >>> from quoss.system.key_volume import _reference_volume
    >>> volume = _reference_volume()
    >>> stations = StationSet(
    ...     names=("east", "west"),
    ...     latitude_rad=np.asarray(deg_to_rad(np.array([41.0, 41.0]))),
    ...     longitude_rad=np.asarray(deg_to_rad(np.array([2.0, 1.0]))),
    ...     altitude_km=np.zeros(2),
    ... )
    >>> log = DegradationLog()
    >>> summed = aggregate_stations(
    ...     stations,
    ...     [volume, volume],
    ...     availability=None,
    ...     policy=AggregationPolicy.SUM,
    ...     degradations=log,
    ... )
    >>> float(summed.total_bits)
    865970.0
    >>> best = aggregate_stations(
    ...     stations,
    ...     [volume, volume],
    ...     availability=None,
    ...     policy=AggregationPolicy.BEST_AVAILABLE,
    ...     degradations=log,
    ... )
    >>> float(best.total_bits), best.conflicts_dropped
    (432985.0, 4)
    >>> [entry.code for entry in log]
    ['multi_ogs.passes-dropped-by-conflict']
    """
    chosen = AggregationPolicy(policy)
    items, _grid, regime = _validated_volumes(stations, volumes, availability)
    gap = float(minimum_gap_s)

    records: list[StationPassKeys] = []
    for index, item in enumerate(items):
        per_pass = None if availability is None else availability[index]
        records.append(
            StationPassKeys(
                station=stations.names[index],
                volume=item,
                availability=per_pass,
                selected=np.ones(item.n_passes, dtype=np.bool_),
            )
        )

    conflicts = 0
    if chosen is AggregationPolicy.BEST_AVAILABLE:
        # Flatten every station's passes into one interval list, tagged by
        # station and satellite; one satellite terminal means passes of the
        # SAME satellite conflict, so each satellite is scheduled on its own.
        station_of = np.concatenate(
            [np.full(record.volume.n_passes, i, dtype=np.int64) for i, record in enumerate(records)]
        )
        satellite_of = np.concatenate(
            [record.volume.samples.table.satellite_index for record in records]
        )
        start = np.concatenate([record.volume.samples.table.start_s for record in records])
        end = np.concatenate([record.volume.samples.table.end_s for record in records])
        weight = np.concatenate([record.expected_bits for record in records])
        _refuse_ground_terminal_conflicts(stations, station_of, satellite_of, start, end)

        keep = np.zeros(start.size, dtype=np.bool_)
        for satellite in np.unique(satellite_of):
            rows = np.flatnonzero(satellite_of == satellite)
            keep[rows] = schedule_passes(start[rows], end[rows], weight[rows], minimum_gap_s=gap)
        offset = 0
        rescheduled: list[StationPassKeys] = []
        for record in records:
            count = record.volume.n_passes
            rescheduled.append(
                StationPassKeys(
                    station=record.station,
                    volume=record.volume,
                    availability=record.availability,
                    selected=keep[offset : offset + count],
                )
            )
            offset += count
        records = rescheduled
        conflicts = int((~keep).sum())
        if conflicts:
            dropped_bits = float(np.sum(weight[~keep]))
            degradations.info(
                "multi_ogs.passes-dropped-by-conflict",
                f"{conflicts} of {keep.size} passes were not scheduled because one satellite "
                "terminal cannot serve two stations at once (or the slew gap of "
                f"{gap:g} s kept them apart); the exact weighted-interval schedule dropped "
                f"{dropped_bits:.0f} expected bits. Under AggregationPolicy.SUM they would all "
                "be counted, which is valid only for a trusted node that pairs keys later.",
                where="quoss.system.multi_ogs.aggregate_stations",
                dropped=conflicts,
                n_passes=int(keep.size),
                dropped_expected_bits=dropped_bits,
                minimum_gap_s=gap,
            )

    if availability is not None:
        degradations.info(
            "multi_ogs.expected-bits-are-an-expectation",
            "availability was supplied, so every `expected` figure is bits x availability: the "
            "expected key over the weather, not a key anyone holds on a given night. The "
            "finite-key bound certifies each pass's bits; the cloud decides whether the pass "
            "happens. Read `station_bits` for what a clear night delivers and "
            "`station_expected_bits` for a season's planning figure.",
            where="quoss.system.multi_ogs.aggregate_stations",
            n_stations=stations.n,
        )

    station_bits = np.array([record.scheduled_bits for record in records], dtype=np.float64)
    station_expected = np.array(
        [record.scheduled_expected_bits for record in records], dtype=np.float64
    )

    day_of_pass = np.concatenate(
        [record.volume.samples.table.day_number[record.selected] for record in records]
    )
    bits_of_pass = np.concatenate(
        [np.asarray(record.volume.key_bits)[record.selected] for record in records]
    )
    expected_of_pass = np.concatenate([record.expected_bits[record.selected] for record in records])
    days, inverse = np.unique(day_of_pass, return_inverse=True)
    n_days = int(days.size)
    daily_bits = np.bincount(inverse, weights=bits_of_pass, minlength=n_days)
    daily_expected = np.bincount(inverse, weights=expected_of_pass, minlength=n_days)

    return MultiStationKeyVolume(
        stations=stations,
        policy=chosen,
        per_station=tuple(records),
        station_bits=station_bits,
        station_expected_bits=station_expected,
        day_number=days.astype(np.int64),
        daily_bits=np.asarray(daily_bits, dtype=np.float64),
        daily_expected_bits=np.asarray(daily_expected, dtype=np.float64),
        conflicts_dropped=conflicts,
        minimum_gap_s=gap,
        regime=regime,
    )


def _refuse_ground_terminal_conflicts(
    stations: StationSet,
    station_of: IntArray,
    satellite_of: IntArray,
    start: FloatArray,
    end: FloatArray,
) -> None:
    """Raise if two passes of different satellites overlap at one station.

    That conflict is the ground terminal's, not the satellite's, and this
    module models only the latter (project scope: one satellite). Scheduling
    it as if it did not exist would count two passes a station can only track
    one of, so it is refused with the pair named.
    """
    for station in np.unique(station_of):
        rows = np.flatnonzero(station_of == station)
        if rows.size < 2:
            continue
        order = rows[np.argsort(start[rows], kind="stable")]
        overlapping = start[order[1:]] < end[order[:-1]]
        crossed = overlapping & (satellite_of[order[1:]] != satellite_of[order[:-1]])
        if np.any(crossed):
            first = int(np.flatnonzero(crossed)[0])
            raise DomainError(
                f"station {stations.names[int(station)]!r} has passes of satellites "
                f"{int(satellite_of[order[first]])} and {int(satellite_of[order[first + 1]])} "
                "overlapping in time. That is a conflict at the GROUND terminal, which this "
                "module does not schedule: the project's scope is one satellite (decision of "
                "2026-09-10), and BEST_AVAILABLE models only the satellite's single terminal. "
                "Restrict the input to one satellite, or extend the scheduler."
            )
