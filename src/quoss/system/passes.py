r"""Which stretches of a time grid are a pass, and how long each sample speaks for.

What a "pass" is, for a reader who has not met the word
-------------------------------------------------------
A satellite in low Earth orbit is not a geostationary relay parked over a city:
it rises, crosses the sky in ten minutes or less, and sets. A **pass** is one
such crossing — the contiguous stretch of time during which a particular ground
station can use a particular satellite. Everything a mission reports per night
is reported per pass, because a pass is the unit of work: the telescope slews to
it, tracks it, and stops.

"Can use" is not "can see", and that distinction is this module's first job.
A satellite one degree above the horizon is geometrically visible and
practically worthless: the beam crosses thirty times as much atmosphere as at
the zenith, the ground telescope is looking through the hottest, most turbulent,
most light-polluted air available, and the slant range — and with it the
geometric loss, which goes as range squared — is at its worst. So a pass is
defined against an **elevation mask**: a threshold angle below which the link is
declared unusable. Twenty degrees is the floor of the Ntanos et al. 2021 study
(:data:`~quoss.channel.link_budget.NTANOS_MINIMUM_ELEVATION_RAD`); ten is a
common operational compromise.

Why the mask is an argument here and not a constant anywhere
--------------------------------------------------------------
:func:`~quoss.orbits.geometry.look_angles` deliberately reports negative
elevations without filtering, and its docstring names this module as the owner
of the threshold. That division is not bureaucratic. The mask is a **design
variable**, and ``key_volume.py`` measures that it has an interior optimum
which the asymptotic key rate cannot see: lowering it below about 8 degrees on
the reference link *destroys* key, because the extra low-elevation samples add
errors that error correction pays for across the whole block while contributing
almost no certified single-photon detections. A number with an optimum in it
cannot be a constant, and a module that hard-coded one would have hidden a
6 % effect.

Four things a naive implementation gets wrong, each measured
-------------------------------------------------------------
**1. The boundaries are not on the grid.** A pass begins when the elevation
crosses the mask, and that instant falls *between* two samples. Taking the
first sample at or above the mask as the start throws away the fraction of a
step before it, at both ends. On the reference day — 1 s grid, four passes
totalling 1799.79 s — the unrefined answer is 1796.00 s: **3.79 s, or 0.21 %,
simply absent**. :func:`find_passes` therefore refines both crossings by linear
interpolation between the bracketing samples, and :attr:`PassTable.start_s` and
:attr:`PassTable.end_s` are those refined instants, not grid samples.

Linear interpolation is the right shape of approximation here and the reason is
worth one sentence: elevation against time is most nearly linear exactly at the
horizon, where it is changing fastest, and most strongly curved at culmination,
where it turns over. The crossings are at the horizon end. Curvature is dealt
with separately where it matters, which is point 3.

**2. The dwell time of a sample is not the grid step.** The samples of a pass
are not all worth the same number of seconds: the first and last own only the
part of their step that lies inside the refined window. :meth:`PassTable.samples`
returns a **dwell time per sample** under the midpoint rule — each sample owns
the interval from its midpoint with the previous sample to its midpoint with the
next, clipped to ``[start_s, end_s]`` — so that the dwell times of a pass sum to
its refined duration *exactly*, which the trapezoid rule on the raw samples does
not. That exactness is what lets ``key_volume.py`` use one weight vector for
both the asymptotic integral and the finite-key pulse budget, so that comparing
the two regimes measures the bound and not the quadrature.

**3. The highest sample is not the culmination.** The maximum elevation of a
pass sets its minimum slant range and therefore its best transmittance, so it
is the number a planner reads first, and reading it off the samples biases it
**low** by an amount that grows as the square of the grid step. Measured on the
reference day: on a 10 s grid the discrete maximum of the best pass is
**0.029 degrees** below the truth, on a 30 s grid **0.51 degrees**. Fitting a
parabola through the maximal sample and its two neighbours — the standard
three-point vertex, written here for unequal spacing so that a non-uniform grid
is handled exactly — reduces those to **0.0006** and **0.081** degrees, a factor
of 6 to 50. :attr:`PassTable.culmination_elevation_rad` is the refined value and
:attr:`PassTable.culmination_s` the refined instant.

**4. A pass clipped by the end of the grid is not a pass.** If the satellite is
already above the mask at the first sample, or still above it at the last, what
the grid holds is a *fragment*: its duration, its culmination and every bit of
key integrated over it are lower bounds on the real pass, and nothing in the
numbers says so. :attr:`PassTable.truncated_start` and
:attr:`PassTable.truncated_end` say so, and :func:`find_passes` records a
warning in the :class:`~quoss.core.errors.DegradationLog` naming how many
fragments it found — the "never degrade silently" rule of the README, applied to
the one degradation that looks exactly like an ordinary short pass.

Why the grid resolution is checked, and why on the sample count
----------------------------------------------------------------
A coarse grid does not merely blur the answer, it **inflates** it. Integrating
the reference day's key with progressively coarser grids, against the 1 s
answer of 432 985 bits:

==================  ===================  ==========
Step                Samples in shortest  Bias
==================  ===================  ==========
1 s                 303                  0.0000 %
10 s                30                   +0.026 %
25 s                12                   +0.120 %
45 s                7                    +1.319 %
60 s                5                    +2.018 %
120 s               2                    +8.586 %
==================  ===================  ==========

Two things about that table. The sign is positive — a planner who coarsens the
grid to save time is handed a *larger* key, which is the plausible-and-wrong
failure mode this project is built to refuse. And the bias is **not monotone**
in the step: it depends on where the samples happen to fall relative to
culmination, so 48 s lands at +0.003 % by accident while its neighbours at 45
and 60 s are at +1.3 % and +2.0 %. That is precisely why
:data:`MINIMUM_SAMPLES_PER_PASS` guards the *sample count* rather than an
estimated error: an error estimate computed from one coarse run can be small by
coincidence, while "this pass has four samples in it" cannot.

What this module deliberately does not do
-----------------------------------------
**It does not interpolate the trajectory.** A
:class:`~quoss.orbits.propagator.Trajectory` holds the samples it was asked for
and nothing between them, and ``notes/LAST_CHANGES.md`` left the choice of what
``passes.py`` should do about that open. The choice made here is: refine the
*boundaries* and the *culmination* from the samples that exist, by
interpolation in elevation, and never fabricate a state vector. A caller who
needs fine resolution inside a pass asks for a finer grid — which
:class:`~quoss.core.types.TimeGrid` allows to be non-uniform, so refining only
around the passes is a second propagation, not a special case here.

**It does not decide whether a pass yields key.** A pass with zero key is still
a pass, and which passes those are is the most interesting output of
``key_volume.py``. Folding a key threshold into pass detection would hide it.

**It does not choose between stations.** :func:`~quoss.orbits.geometry.look_angles`
takes one station, so a :class:`PassTable` is one station's view. Selecting or
aggregating across stations is ``system/multi_ogs.py``.

**It does not know about cloud.** A cloud-free line of sight is a probability
that the pass existed at all, not a shorter pass, and it is ``system/pcflos.py``.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``theta``                               elevation above the local horizon (rad)
``theta_min``                           the elevation mask (rad)
``t_start``, ``t_end``                  refined mask crossings (s from epoch)
``t_c``                                 culmination instant (s from epoch)
``w_i``                                 dwell time of sample ``i`` (s)
``P``                                   number of passes in a table
======================================  ====================================
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from quoss.core.constants import SECONDS_PER_DAY
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, IntArray, TimeGrid, frozen_view
from quoss.core.units import deg_to_rad, rad_to_deg
from quoss.orbits.geometry import LookAngles

__all__ = [
    "MINIMUM_SAMPLES_PER_PASS",
    "PassSamples",
    "PassTable",
    "find_passes",
]

MINIMUM_SAMPLES_PER_PASS: Final[int] = 12
"""Samples a pass must hold before :func:`find_passes` stops complaining.

**Derived from the table in the module docstring, not chosen to let something
pass.** It is the coarsest grid at which the reference day's integrated key
stays within 0.15 % of its 1 s value: 12 samples in the shortest pass gives
+0.120 %, and the next coarser point measured, 7 samples, gives +1.319 %.
``tests/system/test_passes.py::TestTheGridResolutionGuard`` regenerates that
table rather than trusting these digits.

The guard counts samples rather than estimating the error because the error is
not monotone in the step — see the module docstring — so a small error estimate
from a single coarse run is not evidence of a fine enough grid.
"""

_MIN_SAMPLES_FOR_PARABOLA: Final[int] = 3
"""Samples a three-point vertex fit needs. Below this the discrete peak stands."""

_JULIAN_DAY_NUMBER_OFFSET: Final[float] = 0.5
"""Added to a Julian date before flooring, to get the calendar day's JDN.

A Julian date rolls over at **noon** UTC, which is an astronomer's convention and
not a calendar day. ``floor(jd + 0.5)`` is the Julian Day Number of the UTC
calendar day the instant falls in, which is the grouping a "bits per night"
figure means. See :attr:`PassTable.day_number`.
"""


def _validated_mask(minimum_elevation_rad: float) -> float:
    """Return the elevation mask, rejecting anything that is not a usable angle."""
    mask = float(minimum_elevation_rad)
    if not np.isfinite(mask) or not 0.0 < mask < 0.5 * np.pi:
        raise DomainError(
            f"minimum_elevation_rad must be finite and in (0, pi/2), got {mask}. It is an angle "
            "in radians, so a 10 degree mask is 0.1745 and not 10. Zero is excluded because the "
            "whole channel carries a sec(zenith) or a 1/sin(theta) that diverges at the horizon, "
            "and pi/2 because a mask at the zenith admits nothing."
        )
    return mask


@dataclass(frozen=True, eq=False, slots=True)
class PassSamples:
    """Which grid samples belong to which pass, and how many seconds each owns.

    A **flat** record, not a ragged one: passes have different lengths, so the
    natural ``(n_passes, n_samples_in_pass)`` array does not exist. Instead every
    ``(pass, sample)`` pair is one entry, and the four arrays share one length.
    That shape is what lets ``key_volume.py`` evaluate the channel and the
    protocol **once** over every in-pass instant of a whole day in a single
    vectorised call, and then collapse the result per pass with a segment sum —
    rather than looping over passes, which is what a ragged container forces.

    The entries are ordered by pass and, within a pass, by increasing sample
    index, which is what makes :attr:`pass_index` sorted and a segment sum legal.

    Attributes
    ----------
    pass_index : IntArray
        Which row of the :class:`PassTable` this entry belongs to, in
        ``[0, n_passes)``. Sorted, non-decreasing.
    satellite_index : IntArray
        Which satellite, i.e. which row of the
        :class:`~quoss.orbits.geometry.LookAngles` arrays.
    sample_index : IntArray
        Which sample of the :class:`~quoss.core.types.TimeGrid`.
    dwell_s : FloatArray
        Seconds this sample speaks for, under the midpoint rule clipped to the
        refined pass boundaries. Strictly positive, and summing per pass to that
        pass's :attr:`PassTable.duration_s` exactly — see the module docstring
        for why exactly matters.
    table : PassTable
        The passes these entries index into. Carried so that a consumer cannot
        be handed samples and a table that describe different runs.

    Raises
    ------
    DomainError
        If the four arrays are not one-dimensional and of equal length, if any
        dwell time is not positive and finite, or if ``pass_index`` is not
        sorted within ``[0, table.n_passes)``.

    Examples
    --------
    >>> import numpy as np
    >>> samples = _reference_samples()
    >>> samples.size == samples.dwell_s.size
    True
    >>> bool(np.all(np.diff(samples.pass_index) >= 0))
    True
    """

    pass_index: IntArray
    satellite_index: IntArray
    sample_index: IntArray
    dwell_s: FloatArray
    table: PassTable

    def __post_init__(self) -> None:
        """Validate the shape contract a segment sum depends on, then freeze."""
        if not isinstance(self.table, PassTable):
            raise DomainError(f"table must be a PassTable, got {type(self.table).__name__}.")
        lengths = {
            name: np.asarray(getattr(self, name)).shape
            for name in ("pass_index", "satellite_index", "sample_index", "dwell_s")
        }
        if any(shape != lengths["pass_index"] for shape in lengths.values()):
            raise DomainError(
                f"the four arrays must have the same shape, got {lengths}. They are columns of "
                "one table of (pass, sample) entries."
            )
        if len(lengths["pass_index"]) != 1:
            raise DomainError(
                f"the arrays must be 1-D, got shape {lengths['pass_index']}. This container is "
                "flat on purpose: passes have different lengths, so a 2-D form would be ragged."
            )
        dwell = np.asarray(self.dwell_s, dtype=np.float64)
        if not np.all(np.isfinite(dwell)) or np.any(dwell <= 0.0):
            raise DomainError(
                f"dwell_s must be finite and strictly positive, got range "
                f"[{float(np.min(dwell)) if dwell.size else float('nan')}, "
                f"{float(np.max(dwell)) if dwell.size else float('nan')}]. A sample that speaks "
                "for no time is a sample that should not be in the table."
            )
        labels = np.asarray(self.pass_index, dtype=np.int64)
        if labels.size and (int(labels.min()) < 0 or int(labels.max()) >= self.table.n_passes):
            raise DomainError(
                f"pass_index must index the table's {self.table.n_passes} passes, got range "
                f"[{int(labels.min())}, {int(labels.max())}]."
            )
        if labels.size and not np.all(np.diff(labels) >= 0):
            raise DomainError(
                "pass_index must be non-decreasing: a segment sum over the passes is only "
                "correct if the entries of a pass are contiguous."
            )
        object.__setattr__(self, "pass_index", labels)
        object.__setattr__(
            self, "satellite_index", np.asarray(self.satellite_index, dtype=np.int64)
        )
        object.__setattr__(self, "sample_index", np.asarray(self.sample_index, dtype=np.int64))
        object.__setattr__(self, "dwell_s", frozen_view(dwell))

    @property
    def size(self) -> int:
        """Number of ``(pass, sample)`` entries."""
        return int(self.pass_index.size)

    @property
    def shape(self) -> tuple[int, ...]:
        """``(size,)``: the shape a consumer's per-entry arrays must have."""
        return (self.size,)

    def segment_sum(self, values: FloatArray) -> FloatArray:
        """Add ``values`` up per pass, returning one number per row of the table.

        The operation that turns a per-instant quantity into a per-pass one. It
        is :func:`numpy.bincount` rather than a loop, and it returns a zero for a
        pass with no entries, which cannot happen for a table built by
        :func:`find_passes` but is the harmless answer if it ever did.

        Parameters
        ----------
        values : FloatArray
            One value per entry, shape :attr:`shape`.

        Returns
        -------
        FloatArray
            Shape ``(table.n_passes,)``.

        Raises
        ------
        DomainError
            If ``values`` does not have one entry per ``(pass, sample)`` pair.

        Examples
        --------
        Summing the dwell times recovers each pass's duration, which is the
        identity the midpoint rule was chosen for:

        >>> import numpy as np
        >>> samples = _reference_samples()
        >>> recovered = samples.segment_sum(samples.dwell_s)
        >>> bool(np.allclose(recovered, samples.table.duration_s, rtol=0, atol=1e-9))
        True
        """
        array = np.asarray(values, dtype=np.float64)
        if array.shape != self.shape:
            raise DomainError(
                f"values has shape {array.shape}, but there are {self.size} (pass, sample) "
                "entries. A segment sum needs one value per entry."
            )
        summed: FloatArray = np.asarray(
            np.bincount(self.pass_index, weights=array, minlength=self.table.n_passes),
            dtype=np.float64,
        )
        return summed

    def __repr__(self) -> str:
        return (
            f"PassSamples(size={self.size}, n_passes={self.table.n_passes}, "
            f"dwell_s=[{float(np.min(self.dwell_s)):.3f}, {float(np.max(self.dwell_s)):.3f}])"
        )


@dataclass(frozen=True, eq=False, slots=True)
class PassTable:
    """Every pass found, one row each, with its refined boundaries and culmination.

    A columnar table rather than a list of objects: a day of a sixty-satellite
    constellation is a few hundred passes, and every downstream question
    ("longest", "highest", "group by night", "which yielded key") is an array
    operation over a column. Frozen and with read-only arrays, because a pass
    whose start can be edited after the fact is one whose duration no longer
    follows from its boundaries.

    Attributes
    ----------
    satellite_index : IntArray
        Row of the :class:`~quoss.orbits.geometry.LookAngles` arrays this pass
        belongs to, shape ``(P,)``.
    first_index, last_index : IntArray
        First and last grid sample **at or above the mask**, inclusive. These are
        the samples; the pass itself starts and ends between samples, which is
        what :attr:`start_s` and :attr:`end_s` are for.
    start_s, end_s : FloatArray
        Refined mask crossings, seconds from :attr:`grid`'s epoch. For a
        truncated pass the corresponding end is the grid boundary itself, since
        there is no sample outside to interpolate against.
    culmination_s : FloatArray
        Refined instant of maximum elevation, seconds from epoch.
    culmination_elevation_rad : FloatArray
        Refined maximum elevation, radians. At or above the sampled maximum, and
        the number that sets the pass's best slant range.
    sampled_culmination_elevation_rad : FloatArray
        The largest elevation actually *in* the grid, radians. Kept beside the
        refined value rather than replaced by it, because the difference between
        the two is how much the grid is costing — the module docstring measures
        it at 0.51 degrees on a 30 s grid — and a single field would hide it.
    truncated_start, truncated_end : BoolArray
        True where the pass runs off the start or the end of the grid. Every
        quantity of a truncated pass is a **lower bound**.
    minimum_elevation_rad : float
        The mask these passes were found against. Carried because a pass table
        without its mask cannot be compared with another one.
    grid : TimeGrid
        The time axis the indices index into.

    Raises
    ------
    DomainError
        If the columns disagree in shape or are not one-dimensional, if any
        index falls outside the grid, if ``last_index < first_index``, if a pass
        is not strictly later than its predecessor for the same satellite, or if
        ``start_s`` is not strictly below ``end_s``.

    Examples
    --------
    The reference day over Castelldefels — a 700 km sun-synchronous satellite, a
    10 degree mask — holds four passes, two of them good ones:

    >>> import numpy as np
    >>> table = _reference_table()
    >>> table.n_passes
    4
    >>> np.round(table.duration_s, 1)
    array([562.2, 376.6, 558.4, 302.7])
    >>> np.round(rad_to_deg(table.culmination_elevation_rad), 2)
    array([52.92, 17.65, 58.79, 14.22])

    None of them is clipped by the ends of the day:

    >>> bool(np.any(table.is_truncated))
    False
    """

    satellite_index: IntArray
    first_index: IntArray
    last_index: IntArray
    start_s: FloatArray
    end_s: FloatArray
    culmination_s: FloatArray
    culmination_elevation_rad: FloatArray
    sampled_culmination_elevation_rad: FloatArray
    truncated_start: BoolArray
    truncated_end: BoolArray
    minimum_elevation_rad: float
    grid: TimeGrid

    _INT_COLUMNS = ("satellite_index", "first_index", "last_index")
    _FLOAT_COLUMNS = (
        "start_s",
        "end_s",
        "culmination_s",
        "culmination_elevation_rad",
        "sampled_culmination_elevation_rad",
    )
    _BOOL_COLUMNS = ("truncated_start", "truncated_end")

    def __post_init__(self) -> None:
        """Validate that the columns describe passes of one grid, then freeze."""
        if not isinstance(self.grid, TimeGrid):
            raise DomainError(f"grid must be a TimeGrid, got {type(self.grid).__name__}.")
        object.__setattr__(
            self, "minimum_elevation_rad", _validated_mask(self.minimum_elevation_rad)
        )

        columns: dict[str, np.ndarray] = {}
        for name in self._INT_COLUMNS:
            columns[name] = np.asarray(getattr(self, name), dtype=np.int64)
        for name in self._FLOAT_COLUMNS:
            columns[name] = np.asarray(getattr(self, name), dtype=np.float64)
        for name in self._BOOL_COLUMNS:
            columns[name] = np.asarray(getattr(self, name), dtype=np.bool_)

        shape = columns["satellite_index"].shape
        if len(shape) != 1:
            raise DomainError(
                f"the columns must be 1-D, got shape {shape}. One row is one pass; a second axis "
                "would be a ragged container in disguise."
            )
        for name, value in columns.items():
            if value.shape != shape:
                raise DomainError(
                    f"column {name} has shape {value.shape}, but satellite_index has {shape}; "
                    "every column describes the same passes."
                )
            if value.dtype.kind == "f" and not np.all(np.isfinite(value)):
                raise DomainError(f"column {name} contains non-finite values.")

        n_samples = self.grid.n
        for name in ("first_index", "last_index"):
            value = columns[name]
            if value.size and (int(value.min()) < 0 or int(value.max()) >= n_samples):
                raise DomainError(
                    f"{name} must index the grid's {n_samples} samples, got range "
                    f"[{int(value.min())}, {int(value.max())}]."
                )
        if np.any(columns["last_index"] < columns["first_index"]):
            raise DomainError(
                "last_index must be at least first_index: a pass covers the inclusive sample "
                "range between them, so an empty range is not a short pass but no pass."
            )
        if np.any(columns["end_s"] <= columns["start_s"]):
            raise DomainError(
                "end_s must be strictly above start_s. A pass of zero duration integrates to "
                "zero key and would divide by zero in every per-second figure."
            )
        same_satellite = np.diff(columns["satellite_index"]) == 0
        if np.any(same_satellite & (np.diff(columns["first_index"]) <= 0)):
            raise DomainError(
                "the passes of one satellite must be in strictly increasing time order and must "
                "not overlap: one satellite cannot be above the mask twice at once, so an "
                "overlap means two tables were concatenated or a run was split wrongly."
            )

        for name, value in columns.items():
            object.__setattr__(self, name, frozen_view(value) if value.dtype.kind == "f" else value)

    # -- shape and derived geometry ------------------------------------------ #
    @property
    def n_passes(self) -> int:
        """Number of passes, ``P``. The length of every column."""
        return int(self.satellite_index.size)

    def __len__(self) -> int:
        return self.n_passes

    @property
    def duration_s(self) -> FloatArray:
        """``end_s - start_s``: usable seconds, from the refined crossings.

        Not ``t[last] - t[first]``, which is short by up to one grid step at each
        end — 0.21 % of the reference day, per the module docstring.
        """
        duration: FloatArray = self.end_s - self.start_s
        return duration

    @property
    def n_samples(self) -> IntArray:
        """How many grid samples each pass holds, ``last_index - first_index + 1``."""
        count: IntArray = self.last_index - self.first_index + 1
        return count

    @property
    def is_truncated(self) -> BoolArray:
        """True where either end of the pass runs off the grid."""
        clipped: BoolArray = self.truncated_start | self.truncated_end
        return clipped

    @property
    def start_jd(self) -> FloatArray:
        """Absolute Julian date of :attr:`start_s`, days."""
        jd: FloatArray = self.grid.epoch_jd + self.start_s / SECONDS_PER_DAY
        return jd

    @property
    def end_jd(self) -> FloatArray:
        """Absolute Julian date of :attr:`end_s`, days."""
        jd: FloatArray = self.grid.epoch_jd + self.end_s / SECONDS_PER_DAY
        return jd

    @property
    def day_number(self) -> IntArray:
        """Julian Day Number of the UTC calendar day each pass **starts** in.

        ``floor(start_jd + 0.5)``, per :data:`_JULIAN_DAY_NUMBER_OFFSET`: a
        Julian date rolls over at noon, a night's report does not.

        **The convention is "the day it starts in", and it is a convention, not
        a fact.** A pass that straddles midnight UTC is counted whole in the
        earlier day. For this project's geometry that happens to about one pass
        in a hundred and forty — four passes a day, each under ten minutes, so
        ``4 x 600 / 86400 = 2.8 %`` of days have one — and the alternative,
        splitting its block at midnight, would be strictly worse: it would pay
        the fixed finite-key penalty twice and estimate the statistics from two
        half-length blocks, which is the granularity mistake
        ``key_volume.py`` measures at a total loss of all key.
        """
        number: IntArray = np.floor(self.start_jd + _JULIAN_DAY_NUMBER_OFFSET).astype(np.int64)
        return number

    # -- selection ----------------------------------------------------------- #
    def select(self, keep: BoolArray) -> PassTable:
        """Return the table restricted to the rows where ``keep`` is True.

        Parameters
        ----------
        keep : BoolArray
            Boolean mask of length :attr:`n_passes`.

        Returns
        -------
        PassTable
            Same mask and grid, fewer rows.

        Raises
        ------
        DomainError
            If ``keep`` is not a boolean mask of the right length.

        Examples
        --------
        >>> import numpy as np
        >>> table = _reference_table()
        >>> good = table.select(table.culmination_elevation_rad > deg_to_rad(30.0))
        >>> good.n_passes
        2
        """
        mask = np.asarray(keep)
        if mask.dtype != np.bool_ or mask.shape != (self.n_passes,):
            raise DomainError(
                f"keep must be a boolean mask of shape ({self.n_passes},), got dtype "
                f"{mask.dtype} and shape {mask.shape}."
            )
        fields = {
            name: getattr(self, name)[mask]
            for name in self._INT_COLUMNS + self._FLOAT_COLUMNS + self._BOOL_COLUMNS
        }
        return PassTable(
            minimum_elevation_rad=self.minimum_elevation_rad,
            grid=self.grid,
            **fields,
        )

    # -- the bridge to an integral ------------------------------------------- #
    def samples(self) -> PassSamples:
        r"""Return every ``(pass, sample)`` pair with the seconds that sample owns.

        What it computes
        ----------------
        The **midpoint rule** weights, clipped to the refined pass boundaries.
        Sample ``i`` of a pass owns

        .. math::

            w_i = \min(t_\text{end}, \tfrac{t_i + t_{i+1}}{2})
                - \max(t_\text{start}, \tfrac{t_{i-1} + t_i}{2})

        with the first sample's lower edge taken as ``t_start`` and the last
        sample's upper edge as ``t_end``. The weights of a pass therefore sum to
        its duration exactly, for a uniform grid and a non-uniform one alike.

        Why the midpoint rule and not the trapezoid rule
        ------------------------------------------------
        Both are second-order accurate, so accuracy does not decide it. Two
        other things do.

        First, **the trapezoid rule cannot represent the refined boundaries.**
        Its weights are built from the samples, so the interval it integrates
        over is ``[t_first, t_last]`` — it cannot be told that the pass actually
        began 0.4 s earlier, and on the reference day it silently drops 3.79 s,
        0.21 % of the usable time. The midpoint weights take the boundary as an
        input.

        Second, and this is the one that matters for the finite-key bound,
        **these weights are multiplied by a pulse rate to get a pulse count.**
        A weight is therefore "how many pulses were emitted while the link was
        best described by this sample", which is a physical quantity that must
        be positive and must sum to exactly the pulses the pass emitted. The
        midpoint rule gives that by construction. The trapezoid rule's end
        weights are half-steps regardless of where the pass ends, so the sum is
        whatever it is.

        Returns
        -------
        PassSamples
            Flat ``(pass, sample)`` entries with their dwell times.

        Examples
        --------
        The dwell times of the reference day's first pass sum to its duration,
        and the interior ones are the grid step:

        >>> import numpy as np
        >>> table = _reference_table()
        >>> samples = table.samples()
        >>> first = samples.pass_index == 0
        >>> float(np.round(samples.dwell_s[first].sum(), 9)) == float(
        ...     np.round(table.duration_s[0], 9)
        ... )
        True
        >>> float(np.round(np.median(samples.dwell_s[first]), 9))
        1.0

        The total over every pass is the day's usable time, 1799.79 s, against
        the 1796.00 s the raw samples would have reported:

        >>> float(np.round(samples.dwell_s.sum(), 2))
        1799.79
        >>> float(
        ...     np.round(
        ...         (table.grid.t_s[table.last_index] - table.grid.t_s[table.first_index]).sum(), 2
        ...     )
        ... )
        1796.0
        """
        lengths = self.n_samples
        total = int(lengths.sum())
        pass_index = np.repeat(np.arange(self.n_passes, dtype=np.int64), lengths)
        satellite_index = np.repeat(self.satellite_index, lengths)
        # Offsets of each pass inside the flat arrays, so that the running
        # position within a pass is `arange(total) - repeat(offsets, lengths)`.
        offsets = np.concatenate(([0], np.cumsum(lengths)))[:-1].astype(np.int64)
        within = np.arange(total, dtype=np.int64) - np.repeat(offsets, lengths)
        sample_index = np.repeat(self.first_index, lengths) + within

        t = self.grid.t_s
        t_here = t[sample_index]
        is_first = within == 0
        is_last = within == np.repeat(lengths - 1, lengths)
        # The midpoint with the neighbour inside the same pass. For the edges the
        # neighbour does not exist, so the value is overwritten below; computing
        # it with a clipped index first keeps the expression branch-free.
        previous = t[np.maximum(sample_index - 1, 0)]
        following = t[np.minimum(sample_index + 1, self.grid.n - 1)]
        lower = np.where(is_first, np.repeat(self.start_s, lengths), 0.5 * (previous + t_here))
        upper = np.where(is_last, np.repeat(self.end_s, lengths), 0.5 * (t_here + following))
        dwell = upper - lower

        return PassSamples(
            pass_index=pass_index,
            satellite_index=satellite_index,
            sample_index=sample_index,
            dwell_s=np.asarray(dwell, dtype=np.float64),
            table=self,
        )

    def __repr__(self) -> str:
        if self.n_passes == 0:
            return (
                f"PassTable(n_passes=0, mask={rad_to_deg(self.minimum_elevation_rad):.2f} deg, "
                f"grid={self.grid!r})"
            )
        return (
            f"PassTable(n_passes={self.n_passes}, "
            f"mask={rad_to_deg(self.minimum_elevation_rad):.2f} deg, "
            f"duration_s=[{float(self.duration_s.min()):.1f}, {float(self.duration_s.max()):.1f}], "
            f"culmination_deg=[{float(rad_to_deg(self.culmination_elevation_rad.min())):.1f}, "
            f"{float(rad_to_deg(self.culmination_elevation_rad.max())):.1f}], "
            f"truncated={int(self.is_truncated.sum())})"
        )


def _runs_above(mask: BoolArray) -> tuple[IntArray, IntArray, IntArray]:
    """Return ``(satellite, first, last)`` of every contiguous True run of a 2-D mask.

    Padding with a False column on each side turns "the run starts here" into a
    local difference, so the whole ``(S, n)`` grid is segmented in two
    :func:`numpy.nonzero` calls and no loop over satellites or samples. The two
    nonzero results pair up row by row because :func:`numpy.nonzero` returns
    indices in row-major order and every run contributes exactly one rise and
    one fall.
    """
    n_satellites, n_samples = mask.shape
    padded = np.zeros((n_satellites, n_samples + 2), dtype=np.int8)
    padded[:, 1:-1] = mask
    difference = np.diff(padded, axis=1)
    satellite, rise = np.nonzero(difference == 1)
    _, fall = np.nonzero(difference == -1)
    return (
        satellite.astype(np.int64),
        rise.astype(np.int64),
        (fall - 1).astype(np.int64),
    )


def _refined_crossings(
    elevation: FloatArray,
    t_s: FloatArray,
    satellite: IntArray,
    first: IntArray,
    last: IntArray,
    mask_rad: float,
) -> tuple[FloatArray, FloatArray]:
    """Interpolate the two mask crossings of every pass linearly in elevation.

    At the rising edge the bracketing pair is ``(first - 1, first)``, whose
    elevations straddle the mask strictly — the earlier one is below it by
    definition of where the run started, the later at or above — so the
    denominator cannot vanish. Symmetrically at the falling edge. Where a
    bracketing sample does not exist the pass is truncated and the grid boundary
    is the best statement available; :func:`find_passes` flags those rows.
    """
    n_samples = t_s.size
    has_before = first > 0
    before = np.maximum(first - 1, 0)
    elevation_before = elevation[satellite, before]
    elevation_first = elevation[satellite, first]
    fraction_in = np.where(
        has_before,
        (mask_rad - elevation_before)
        / np.where(has_before, elevation_first - elevation_before, 1.0),
        0.0,
    )
    start_s = np.where(
        has_before, t_s[before] + fraction_in * (t_s[first] - t_s[before]), t_s[first]
    )

    has_after = last < n_samples - 1
    after = np.minimum(last + 1, n_samples - 1)
    elevation_last = elevation[satellite, last]
    elevation_after = elevation[satellite, after]
    fraction_out = np.where(
        has_after,
        (mask_rad - elevation_last) / np.where(has_after, elevation_after - elevation_last, 1.0),
        0.0,
    )
    end_s = np.where(has_after, t_s[last] + fraction_out * (t_s[after] - t_s[last]), t_s[last])
    return (
        np.asarray(start_s, dtype=np.float64),
        np.asarray(end_s, dtype=np.float64),
    )


def _culmination(
    elevation: FloatArray,
    t_s: FloatArray,
    samples: PassSamples,
    start_s: FloatArray,
    end_s: FloatArray,
) -> tuple[FloatArray, FloatArray, FloatArray]:
    r"""Return ``(t_c, theta_c, theta_sampled)``: the culmination, refined and raw.

    The refinement is the vertex of the parabola through the maximal sample and
    its two grid neighbours, written for **unequal** spacing so that a
    non-uniform :class:`~quoss.core.types.TimeGrid` is handled exactly rather
    than approximately. In Newton form,

    .. math::

        b_1 = \frac{y_1 - y_0}{x_1 - x_0}, \quad
        b_2 = \frac{\frac{y_2-y_1}{x_2-x_1} - b_1}{x_2 - x_0}, \quad
        x^* = \frac{x_0 + x_1}{2} - \frac{b_1}{2 b_2}

    which reduces to the familiar ``x_1 + h(y_0-y_2)/(2(y_0-2y_1+y_2))`` when
    the two steps are equal. ``b_2 < 0`` is the statement that the three points
    really do bracket a maximum.

    The fit is **accepted only if** ``b_2 < 0``, the pass maximum is attained at a
    single sample, and the vertex lands inside both the three-point bracket and
    the refined pass window. Otherwise the discrete
    maximum stands. That is not defensive padding: a pass whose highest sample is
    its first or last one — a fragment clipped by the grid, or a grazing pass
    whose peak is a single sample — has no interior maximum to refine, and
    extrapolating a parabola past the data there would invent an elevation the
    satellite never reached.
    """
    n_passes = samples.table.n_passes
    n_samples = t_s.size
    values = elevation[samples.satellite_index, samples.sample_index]
    # `find_passes` returns before calling this when there are no passes, so the
    # empty case is unreachable here and is deliberately not special-cased:
    # `reduceat` would reject the empty index list, and a guard for a branch no
    # caller can take is a branch no test can cover.
    lengths = samples.table.n_samples
    sampled_peak = np.maximum.reduceat(
        values, np.concatenate(([0], np.cumsum(lengths)))[:-1].astype(np.int64)
    )
    # First entry of each pass that attains the pass maximum. `pass_index` is
    # sorted, so `np.unique(..., return_index=True)` gives first occurrences.
    at_peak = np.flatnonzero(values == np.repeat(sampled_peak, lengths))
    peak_labels = samples.pass_index[at_peak]
    unique_labels, first_occurrence, tie_count = np.unique(
        peak_labels, return_index=True, return_counts=True
    )
    peak_entry = at_peak[first_occurrence]
    # A maximum attained at more than one sample is a plateau at grid
    # resolution, and a parabola fitted to an asymmetric bracket around one end
    # of it overshoots the data: through (20, 30, 30) the vertex is 31.25, an
    # elevation no sample saw. With a tie the grid has not resolved the peak, so
    # the sample stands -- which is both honest and the conservative direction.
    resolved = np.zeros(n_passes, dtype=np.bool_)
    resolved[unique_labels] = tie_count == 1
    peak_sample = samples.sample_index[peak_entry]
    peak_satellite = samples.satellite_index[peak_entry]

    t_peak = t_s[peak_sample]
    interior = (peak_sample > 0) & (peak_sample < n_samples - 1)
    left = np.maximum(peak_sample - 1, 0)
    right = np.minimum(peak_sample + 1, n_samples - 1)
    x0, x1, x2 = t_s[left], t_peak, t_s[right]
    y0 = elevation[peak_satellite, left]
    y1 = elevation[peak_satellite, peak_sample]
    y2 = elevation[peak_satellite, right]

    with np.errstate(divide="ignore", invalid="ignore"):
        b1 = (y1 - y0) / (x1 - x0)
        b2 = ((y2 - y1) / (x2 - x1) - b1) / (x2 - x0)
        vertex = 0.5 * (x0 + x1) - b1 / (2.0 * b2)
        value = y0 + b1 * (vertex - x0) + b2 * (vertex - x0) * (vertex - x1)
    usable = (
        interior
        & resolved
        & np.isfinite(vertex)
        & np.isfinite(value)
        & (b2 < 0.0)
        & (vertex >= x0)
        & (vertex <= x2)
        & (vertex >= start_s)
        & (vertex <= end_s)
    )
    culmination_s = np.where(usable, vertex, t_peak)
    # The vertex of a downward parabola through three points is never below the
    # middle one; the maximum is float-noise insurance, not a correction.
    culmination_elevation = np.maximum(np.where(usable, value, y1), y1)
    return (
        np.asarray(culmination_s, dtype=np.float64),
        np.asarray(culmination_elevation, dtype=np.float64),
        np.asarray(y1, dtype=np.float64),
    )


def find_passes(
    angles: LookAngles,
    *,
    grid: TimeGrid,
    minimum_elevation_rad: float,
    degradations: DegradationLog,
    minimum_duration_s: float = 0.0,
) -> PassTable:
    """Segment a time grid into the passes above an elevation mask.

    The entry point of the module. Takes what
    :func:`~quoss.orbits.geometry.look_angles` reports — elevation at every
    sample, for every satellite, unfiltered and including negative values — and
    returns one row per contiguous stretch above the mask, with the boundaries
    and the culmination refined off the grid as the module docstring derives.

    Vectorised over the whole ``(satellite, sample)`` grid: a day of sixty
    satellites at 1 s is 5.2 million elevations and is segmented without a
    Python loop over either axis.

    Parameters
    ----------
    angles : LookAngles
        Look angles from one ground station, shape ``(n_satellites, n_samples)``.
        Only :attr:`~quoss.orbits.geometry.LookAngles.elevation_rad` is read;
        the range and the rates belong to the channel, not to the segmentation.
    grid : TimeGrid
        The axis ``angles`` was computed on. Passed separately because
        :class:`~quoss.orbits.geometry.LookAngles` does not carry one — it is
        derived from a :class:`~quoss.orbits.propagator.Trajectory`, which does —
        and checked against it, since a mismatch would put every pass at the
        wrong time while every duration stayed plausible.
    minimum_elevation_rad : float
        The mask, radians, in ``(0, pi/2)``. **Required, with no default**: it is
        a design variable with a measured interior optimum (see
        ``system/key_volume.py``), and a default would make that choice
        invisible. 20 degrees is
        :data:`~quoss.channel.link_budget.NTANOS_MINIMUM_ELEVATION_RAD`.
    degradations : DegradationLog
        Receives a warning for every truncated pass, for every pass dropped by
        ``minimum_duration_s``, and when the grid is too coarse to integrate a
        pass (see :data:`MINIMUM_SAMPLES_PER_PASS`).
    minimum_duration_s : float, optional
        Drop passes shorter than this, seconds. Defaults to ``0.0``, which drops
        nothing: a two-second pass is a real geometric fact, and whether it is
        worth slewing to is an operations question this module does not own.
        Whatever it drops, it says so in ``degradations``.

    Returns
    -------
    PassTable
        One row per pass, possibly empty.

    Raises
    ------
    DomainError
        If ``grid`` does not match ``angles`` in length, if the mask is outside
        ``(0, pi/2)``, or if ``minimum_duration_s`` is negative or non-finite.

    Examples
    --------
    A day over Castelldefels with a 700 km sun-synchronous satellite, 10 degree
    mask, on a 1 s grid. Four passes, of which two reach above 50 degrees:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> angles, grid = _reference_geometry()
    >>> log = DegradationLog()
    >>> table = find_passes(
    ...     angles,
    ...     grid=grid,
    ...     minimum_elevation_rad=deg_to_rad(10.0),
    ...     degradations=log,
    ... )
    >>> table.n_passes
    4
    >>> np.round(rad_to_deg(table.culmination_elevation_rad), 2)
    array([52.92, 17.65, 58.79, 14.22])
    >>> len(log)
    0

    The same day with the Ntanos et al. 20 degree floor keeps two passes and
    about 42 % of the usable seconds:

    >>> strict = find_passes(
    ...     angles,
    ...     grid=grid,
    ...     minimum_elevation_rad=deg_to_rad(20.0),
    ...     degradations=log,
    ... )
    >>> strict.n_passes
    2
    >>> float(np.round(strict.duration_s.sum() / table.duration_s.sum(), 3))
    0.422

    A window that opens in the middle of a pass reports a fragment and says so,
    both in the column and in the log:

    >>> clipped_grid, clipped_angles = _reference_window(25_900.0, 600.0)
    >>> log = DegradationLog()
    >>> fragment = find_passes(
    ...     clipped_angles,
    ...     grid=clipped_grid,
    ...     minimum_elevation_rad=deg_to_rad(10.0),
    ...     degradations=log,
    ... )
    >>> bool(fragment.truncated_start[0])
    True
    >>> [entry.code for entry in log]
    ['passes.truncated-by-grid']
    """
    if not isinstance(grid, TimeGrid):
        raise DomainError(f"grid must be a TimeGrid, got {type(grid).__name__}.")
    if grid.n != angles.n_samples:
        raise DomainError(
            f"grid holds {grid.n} samples but angles holds {angles.n_samples}. They must be the "
            "same axis: a mismatch would place every pass at the wrong absolute time while every "
            "duration stayed plausible, which is the failure mode with no symptom."
        )
    mask_rad = _validated_mask(minimum_elevation_rad)
    floor_s = float(minimum_duration_s)
    if not np.isfinite(floor_s) or floor_s < 0.0:
        raise DomainError(
            f"minimum_duration_s must be finite and non-negative, got {floor_s}. The unit is "
            "seconds, and 'keep everything' is 0.0."
        )

    elevation = np.asarray(angles.elevation_rad, dtype=np.float64)
    above = elevation >= mask_rad
    satellite, first, last = _runs_above(above)

    if satellite.size == 0:
        degradations.info(
            "passes.none-found",
            f"No sample of the grid reaches the {rad_to_deg(mask_rad):.2f} degree mask, so the "
            "table is empty. The satellite may never rise over this station, or the window may "
            "fall between passes.",
            where="quoss.system.passes.find_passes",
            minimum_elevation_deg=float(rad_to_deg(mask_rad)),
            maximum_elevation_deg=float(rad_to_deg(elevation.max())) if elevation.size else None,
        )
        return PassTable(
            satellite_index=satellite,
            first_index=first,
            last_index=last,
            start_s=np.zeros(0),
            end_s=np.zeros(0),
            culmination_s=np.zeros(0),
            culmination_elevation_rad=np.zeros(0),
            sampled_culmination_elevation_rad=np.zeros(0),
            truncated_start=np.zeros(0, dtype=np.bool_),
            truncated_end=np.zeros(0, dtype=np.bool_),
            minimum_elevation_rad=mask_rad,
            grid=grid,
        )

    start_s, end_s = _refined_crossings(elevation, grid.t_s, satellite, first, last, mask_rad)
    truncated_start = first == 0
    truncated_end = last == grid.n - 1

    # The culmination fit needs the (pass, sample) expansion, which PassTable
    # owns. Build a provisional table for it, then rebuild with the result: the
    # expansion depends only on the indices and the boundaries, both already final.
    provisional = PassTable(
        satellite_index=satellite,
        first_index=first,
        last_index=last,
        start_s=start_s,
        end_s=end_s,
        culmination_s=start_s,
        culmination_elevation_rad=elevation[satellite, first],
        sampled_culmination_elevation_rad=elevation[satellite, first],
        truncated_start=truncated_start,
        truncated_end=truncated_end,
        minimum_elevation_rad=mask_rad,
        grid=grid,
    )
    culmination_s, culmination_elevation, sampled_elevation = _culmination(
        elevation, grid.t_s, provisional.samples(), start_s, end_s
    )

    table = PassTable(
        satellite_index=satellite,
        first_index=first,
        last_index=last,
        start_s=start_s,
        end_s=end_s,
        culmination_s=culmination_s,
        culmination_elevation_rad=culmination_elevation,
        sampled_culmination_elevation_rad=sampled_elevation,
        truncated_start=truncated_start,
        truncated_end=truncated_end,
        minimum_elevation_rad=mask_rad,
        grid=grid,
    )

    if floor_s > 0.0:
        keep = table.duration_s >= floor_s
        dropped = int((~keep).sum())
        if dropped:
            degradations.warn(
                "passes.below-minimum-duration",
                f"{dropped} of {table.n_passes} passes are shorter than the "
                f"{floor_s} s floor and were dropped; the shortest kept is "
                f"{float(table.duration_s[keep].min()) if keep.any() else float('nan')} s. Their "
                "key is not counted anywhere, so a 'bits per day' computed from what remains is "
                "a statement about the passes that survived this filter.",
                where="quoss.system.passes.find_passes",
                dropped=dropped,
                minimum_duration_s=floor_s,
                dropped_durations_s=[float(value) for value in table.duration_s[~keep]],
            )
            table = table.select(keep)
        if table.n_passes == 0:
            return table

    clipped = int(table.is_truncated.sum())
    if clipped:
        degradations.warn(
            "passes.truncated-by-grid",
            f"{clipped} of {table.n_passes} passes run off the end of the time grid. Their "
            "duration, culmination elevation and any key integrated over them are LOWER BOUNDS "
            "on the real pass, not estimates of it. Extend the grid to close them.",
            where="quoss.system.passes.find_passes",
            truncated=clipped,
            truncated_at_start=int(table.truncated_start.sum()),
            truncated_at_end=int(table.truncated_end.sum()),
        )

    shortest = int(table.n_samples.min())
    if shortest < MINIMUM_SAMPLES_PER_PASS:
        degradations.warn(
            "passes.grid-too-coarse",
            f"the shortest pass holds {shortest} samples, below the {MINIMUM_SAMPLES_PER_PASS} "
            "needed for the dwell-time quadrature to be trustworthy. A coarse grid does not blur "
            "the integrated key, it INFLATES it: 5 samples per pass overstates this project's "
            "reference day by 2.0 % and 2 samples by 8.6 %. Use a finer step.",
            where="quoss.system.passes.find_passes",
            shortest_pass_samples=shortest,
            required_samples=MINIMUM_SAMPLES_PER_PASS,
        )
    return table


# --------------------------------------------------------------------------- #
# Reference geometry for the doctests above.
#
# A private helper rather than a fixture, because the examples in this module's
# docstrings are run by pytest (`--doctest-modules`) and are the only executable
# statement of what the numbers in the prose mean. Keeping the construction in
# one place is what stops eight docstrings from each building a slightly
# different satellite and quietly disagreeing.
# --------------------------------------------------------------------------- #
def _reference_geometry() -> tuple[LookAngles, TimeGrid]:
    """Return one UTC day of look angles over Castelldefels for a 700 km SSO.

    2025-01-01, 1 s grid, a near-circular sun-synchronous orbit at 700 km with
    its node at 30 degrees east, seen from CTTC's own station (41.2750 N,
    1.9875 E, 30 m). Two-body motion: this module reads only the *shape* of the
    elevation curve, and J2 changes which passes occur on a given day without
    changing anything about how one is segmented.

    Examples
    --------
    >>> angles, grid = _reference_geometry()
    >>> angles.elevation_rad.shape
    (1, 86401)
    """
    from quoss.orbits.constellations import sun_synchronous_inclination_rad
    from quoss.orbits.geometry import look_angles
    from quoss.orbits.kepler import ClassicalElements
    from quoss.orbits.propagator import PropagationMethod, propagate

    semi_major_axis_km = 6378.137 + 700.0
    inclination = sun_synchronous_inclination_rad(
        semi_major_axis_km=semi_major_axis_km, eccentricity=0.001
    )
    elements = ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=semi_major_axis_km,
        eccentricity=0.001,
        inclination_rad=float(np.ravel(inclination)[0]),
        raan_rad=float(deg_to_rad(30.0)),
        argp_rad=0.0,
        true_anomaly_rad=0.0,
    )
    grid = TimeGrid.uniform(epoch_jd=2_460_676.5, duration_s=SECONDS_PER_DAY, step_s=1.0)
    trajectory = propagate(elements, grid, method=PropagationMethod.TWO_BODY)
    angles = look_angles(
        trajectory,
        station_latitude_rad=float(deg_to_rad(41.2750)),
        station_longitude_rad=float(deg_to_rad(1.9875)),
        station_altitude_km=0.030,
    )
    return angles, grid


def _reference_window(offset_s: float, duration_s: float) -> tuple[TimeGrid, LookAngles]:
    """Return a sub-window of :func:`_reference_geometry`, for the truncated case.

    Examples
    --------
    >>> grid, angles = _reference_window(25_900.0, 600.0)
    >>> grid.n
    601
    """
    from quoss.orbits.geometry import LookAngles as _LookAngles

    angles, grid = _reference_geometry()
    start = int(np.searchsorted(grid.t_s, offset_s))
    stop = int(np.searchsorted(grid.t_s, offset_s + duration_s)) + 1
    window = TimeGrid(epoch_jd=grid.epoch_jd, t_s=np.array(grid.t_s[start:stop], dtype=np.float64))
    clipped = _LookAngles(
        elevation_rad=np.array(angles.elevation_rad[:, start:stop]),
        azimuth_rad=np.array(angles.azimuth_rad[:, start:stop]),
        range_km=np.array(angles.range_km[:, start:stop]),
        range_rate_km_s=np.array(angles.range_rate_km_s[:, start:stop]),
        point_ahead_angle_rad=np.array(angles.point_ahead_angle_rad[:, start:stop]),
    )
    return window, clipped


def _reference_table() -> PassTable:
    """Return the reference day segmented at a 10 degree mask.

    Examples
    --------
    >>> _reference_table().n_passes
    4
    """
    angles, grid = _reference_geometry()
    return find_passes(
        angles,
        grid=grid,
        minimum_elevation_rad=float(deg_to_rad(10.0)),
        degradations=DegradationLog(),
    )


def _reference_samples() -> PassSamples:
    """Return the reference table's ``(pass, sample)`` expansion.

    Examples
    --------
    >>> _reference_samples().size
    1800
    """
    return _reference_table().samples()
