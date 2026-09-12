"""Shared type aliases and the time-axis containers every stage speaks.

The array contract
------------------
The whole pipeline is vectorised over time. A physics function takes arrays and
returns arrays; there is no scalar entry point that a caller might reach for.
The aliases here exist so that a signature states the shape and dtype it expects
instead of saying ``np.ndarray`` and leaving the reader to guess.

The time contract
-----------------
Time has two halves and both are needed:

* **Absolute** — a Julian date, because SGP4, GMST and every ephemeris are
  defined against one. Days, ``float64``.
* **Elapsed** — seconds from a stated epoch, because that is what the physics
  integrates over and what a plot's x-axis shows.

:class:`TimeGrid` carries the pair together. This is deliberate: if each module
tracked its own epoch, the first bug would be a silent one-day offset in a
Doppler curve. A function that needs absolute time asks the grid for
:attr:`TimeGrid.jd`; one that needs elapsed time uses :attr:`TimeGrid.t_s`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias

import numpy as np
import numpy.typing as npt

from quoss.core.constants import SECONDS_PER_DAY
from quoss.core.errors import DomainError

__all__ = [
    "BoolArray",
    "FloatArray",
    "FloatLike",
    "IntArray",
    "TimeGrid",
    "TimeSeries",
    "Vec3Array",
    "frozen_copy",
    "frozen_view",
]

# --------------------------------------------------------------------------- #
# Array aliases
# --------------------------------------------------------------------------- #
FloatArray: TypeAlias = npt.NDArray[np.float64]
"""Canonical floating array. ``float64`` everywhere, no exceptions.

``float32`` would halve memory but costs ~7 significant digits, and a
finite-key bound subtracts large nearly-equal terms. Not a trade worth making.
"""

IntArray: TypeAlias = npt.NDArray[np.int64]
"""Integer array: sample indices, pass identifiers, photon counts."""

BoolArray: TypeAlias = npt.NDArray[np.bool_]
"""Boolean mask over the time axis: visibility, gating, outage."""

Vec3Array: TypeAlias = npt.NDArray[np.float64]
"""Stack of 3-vectors, shape ``(n, 3)``.

Position and velocity in ECI/ECEF. Time is always the **first** axis, so
``r[i]`` is the vector at sample ``i`` and ``r[:, 0]`` is the x component.
Same runtime type as :data:`FloatArray`; distinct name because the shape
contract differs.
"""

FloatLike: TypeAlias = float | FloatArray
"""A float or an array of floats.

Only for genuinely shape-agnostic helpers — unit conversions, elementary
algebra. Physics functions take :data:`FloatArray`: accepting scalars there is
how the vectorisation contract erodes one signature at a time.
"""


# --------------------------------------------------------------------------- #
# Making "immutable" true
#
# Every container in this project that documents itself as immutable is a frozen
# dataclass or uses __slots__, and neither of those freezes an array's *contents*.
# The two helpers below are what a container calls before storing an array, so
# that the guarantee its docstring gives its consumers is one it actually holds.
# --------------------------------------------------------------------------- #
def frozen_copy(value: FloatArray) -> FloatArray:
    """Return an independent, read-only ``float64`` copy of ``value``.

    What a container stores when it documents itself as immutable and did **not**
    create the array it was handed. Two failures are closed at once, and both are
    silent:

    * **Mutation.** ``frozen=True`` freezes the *binding*, not the buffer, so
      ``grid.t_s[0] = 99.0`` used to succeed. That could put a :class:`TimeGrid`
      into a state its own constructor rejects — samples out of order — while
      :attr:`TimeGrid.duration_s` and :attr:`TimeGrid.is_uniform` kept answering
      as though nothing had happened, and while the class docstring went on
      telling consumers they need not re-check. Marking the array unwriteable
      turns that assignment into a ``ValueError`` at the line that makes the
      mistake.
    * **Aliasing.** A validator that returns its argument unchanged when it is
      already a 1-D ``float64`` array — which is the right call inside a physics
      function that goes on to build new arrays — means a container storing that
      return value shares the caller's buffer. The caller can then edit their own
      array and change the container underneath.

    The **copy** is what closes the aliasing; freezing alone would not, because
    the caller keeps a writeable reference to the same memory. Use
    :func:`frozen_view` when the array was just produced locally and no such
    second reference exists.

    Cost, so the choice is not made blind: the copy is of the array handed in, so
    it is ``n`` values for a time axis or a set of elements — irrelevant. It is
    the wrong tool for a ``(S, n, 3)`` trajectory.

    Parameters
    ----------
    value : FloatArray
        Array to copy. Any shape.

    Returns
    -------
    FloatArray
        A new, contiguous, read-only array with the same values.

    Examples
    --------
    >>> caller_owns = np.array([1.0, 2.0])
    >>> stored = frozen_copy(caller_owns)
    >>> caller_owns[0] = 99.0  # the caller edits their own array
    >>> float(stored[0])  # the stored copy is untouched
    1.0
    >>> bool(np.shares_memory(stored, caller_owns))
    False
    >>> stored.flags.writeable
    False
    """
    out = np.array(value, dtype=np.float64)
    out.flags.writeable = False
    return out


def frozen_view(value: FloatArray) -> FloatArray:
    """Return a read-only view sharing the buffer of ``value``.

    The zero-copy half of :func:`frozen_copy`, for arrays the calling module
    produced itself. A trajectory is the case: its ``(S, n, 3)`` positions and
    velocities are filled in by the propagator and never handed in from outside,
    so there is no second writeable reference to defend against, and copying would
    cost real memory — 24 MB per array for a million samples of one satellite — to
    defend against a reference that does not exist.

    A *view* rather than the argument itself, because ``writeable`` belongs to the
    array object and not to the buffer. Freezing the argument in place would make
    a caller's array read-only as a side effect of passing it, which is a surprise
    they did not ask for; freezing a view of it is invisible to them.

    Parameters
    ----------
    value : FloatArray
        Array to wrap. Any shape. Must already be ``float64``: this helper does
        not convert, because converting would copy and the whole point is not to.

    Returns
    -------
    FloatArray
        A read-only view. Shares memory with ``value``.

    Examples
    --------
    >>> produced_locally = np.zeros(3)
    >>> frozen = frozen_view(produced_locally)
    >>> bool(np.shares_memory(frozen, produced_locally))
    True
    >>> produced_locally.flags.writeable  # the argument is left alone
    True
    >>> frozen.flags.writeable
    False
    """
    out = value.view()
    out.flags.writeable = False
    return out


# --------------------------------------------------------------------------- #
# Time axis
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False, slots=True)
class TimeGrid:
    """The time axis of a simulation: an epoch plus elapsed seconds.

    Immutable and validated at construction, so any function receiving one may
    assume the samples are finite, one-dimensional and strictly increasing
    without re-checking. **Immutable includes the samples**: ``t_s`` is stored as
    an independent read-only copy, so neither ``grid.t_s[0] = ...`` nor an edit to
    the array the caller passed in can move the axis afterwards. Without that, the
    permission this docstring grants would not be one the class can keep — the
    reachable bad state is a grid whose samples are out of order, which
    :attr:`duration_s` and :attr:`is_uniform` would then answer about as if
    nothing were wrong.

    Parameters
    ----------
    epoch_jd : float
        Julian date of ``t_s == 0``, in days (UTC). Absolute anchor for SGP4,
        GMST and solar/lunar geometry.
    t_s : FloatArray
        Elapsed seconds from ``epoch_jd``. One-dimensional, finite, strictly
        increasing. Need not be uniformly spaced — adaptive grids around a pass
        are legitimate — but see :attr:`is_uniform`. Copied on construction; the
        caller keeps their array and may do as they like with it.

    Raises
    ------
    DomainError
        If ``t_s`` is not one-dimensional, is empty, contains non-finite values,
        or is not strictly increasing; or if ``epoch_jd`` is not finite.

    Examples
    --------
    >>> grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=600.0, step_s=1.0)
    >>> grid.n
    601
    >>> float(grid.duration_s)
    600.0

    The samples cannot be moved after the fact:

    >>> grid.t_s[0] = 99.0
    Traceback (most recent call last):
        ...
    ValueError: assignment destination is read-only
    """

    epoch_jd: float
    t_s: FloatArray

    def __post_init__(self) -> None:
        """Validate the invariants the rest of the pipeline relies on, then freeze.

        Validation happens on the array as handed in and the freezing after, so
        that a rejected grid is rejected for its own reason and not for a copy's.
        """
        if not np.isfinite(self.epoch_jd):
            raise DomainError(f"epoch_jd must be finite, got {self.epoch_jd!r}.")
        t = self.t_s
        if t.ndim != 1:
            raise DomainError(f"t_s must be 1-D, got shape {t.shape}.")
        if t.size == 0:
            raise DomainError("t_s must contain at least one sample.")
        if not np.all(np.isfinite(t)):
            raise DomainError("t_s contains non-finite values.")
        if t.size > 1 and not np.all(np.diff(t) > 0.0):
            raise DomainError(
                "t_s must be strictly increasing; duplicate or out-of-order samples "
                "break pass segmentation and temporal correlation."
            )
        # `object.__setattr__` because the dataclass is frozen: the assignment the
        # decorator blocks is exactly the one needed to make the freeze stick.
        object.__setattr__(self, "t_s", frozen_copy(t))

    # -- constructors ------------------------------------------------------- #
    @classmethod
    def uniform(
        cls,
        *,
        epoch_jd: float,
        duration_s: float,
        step_s: float | None = None,
        n: int | None = None,
    ) -> TimeGrid:
        """Build a uniformly spaced grid from a duration.

        Exactly one of ``step_s`` or ``n`` must be given.

        Parameters
        ----------
        epoch_jd : float
            Julian date of the first sample.
        duration_s : float
            Span from first to last sample, in seconds. Must be positive.
        step_s : float, optional
            Sample spacing in seconds. The grid is closed on both ends, so it
            holds ``duration_s / step_s + 1`` samples and ``duration_s`` must be
            an integer multiple of ``step_s``.
        n : int, optional
            Number of samples, at least 2, spanning ``duration_s`` inclusively.

        Returns
        -------
        TimeGrid
            The constructed grid.

        Raises
        ------
        DomainError
            If neither or both of ``step_s``/``n`` are given, if ``duration_s``
            is not positive, or if ``duration_s`` is not a whole multiple of
            ``step_s``.
        """
        if (step_s is None) == (n is None):
            raise DomainError("Provide exactly one of step_s or n.")
        if not (duration_s > 0.0 and np.isfinite(duration_s)):
            raise DomainError(f"duration_s must be finite and positive, got {duration_s!r}.")

        if step_s is not None:
            if not (step_s > 0.0 and np.isfinite(step_s)):
                raise DomainError(f"step_s must be finite and positive, got {step_s!r}.")
            count = duration_s / step_s
            n_steps = round(count)
            # A non-integer sample count silently truncates the last fraction of
            # a pass. Reject it rather than quietly shortening the window.
            if abs(count - n_steps) > 1e-9 * max(1.0, count):
                raise DomainError(
                    f"duration_s={duration_s} is not a whole multiple of step_s={step_s} "
                    f"({count} steps). Adjust one of them."
                )
            t_s = np.arange(n_steps + 1, dtype=np.float64) * step_s
        else:
            assert n is not None  # narrowed by the exclusivity check above
            if n < 2:
                raise DomainError(f"n must be at least 2, got {n}.")
            t_s = np.linspace(0.0, duration_s, n, dtype=np.float64)

        return cls(epoch_jd=float(epoch_jd), t_s=t_s)

    # -- geometry of the axis ----------------------------------------------- #
    @property
    def n(self) -> int:
        """Number of samples."""
        return int(self.t_s.size)

    @property
    def duration_s(self) -> float:
        """Span from first to last sample, in seconds. Zero for a single sample."""
        return float(self.t_s[-1] - self.t_s[0])

    @property
    def is_uniform(self) -> bool:
        """True if the spacing is constant to within floating-point tolerance.

        Several models (AR(1) fading, FFT-based scintillation spectra) are only
        defined on a uniform axis and must check this rather than assume it.
        """
        if self.n < 3:
            return True
        d = np.diff(self.t_s)
        return bool(np.allclose(d, d[0], rtol=1e-9, atol=0.0))

    @property
    def step_s(self) -> float:
        """Sample spacing in seconds.

        Returns
        -------
        float
            The common spacing.

        Raises
        ------
        DomainError
            If the grid is not uniform, or holds a single sample.
        """
        if self.n < 2:
            raise DomainError("A single-sample grid has no step.")
        if not self.is_uniform:
            raise DomainError("Grid is not uniform; step_s is undefined. Use t_s directly.")
        return float(self.t_s[1] - self.t_s[0])

    @property
    def jd(self) -> FloatArray:
        """Absolute Julian date of every sample, in days.

        Computed as ``epoch_jd + t_s / 86400``. Beware that ``float64`` holds a
        Julian date to about 20 microseconds; that is ample for link geometry but
        is the reason elapsed seconds, not JD, is the axis the physics integrates
        over.
        """
        return self.epoch_jd + self.t_s / SECONDS_PER_DAY

    def __len__(self) -> int:
        return self.n

    def __repr__(self) -> str:
        kind = "uniform" if self.is_uniform else "non-uniform"
        return (
            f"TimeGrid(epoch_jd={self.epoch_jd!r}, n={self.n}, "
            f"duration_s={self.duration_s!r}, {kind})"
        )


@dataclass(frozen=True, eq=False, slots=True)
class TimeSeries:
    """Values sampled on a :class:`TimeGrid`, carrying their own unit label.

    A minimal, dependency-free container for one quantity over time — the thing
    a physics function returns and a plot consumes. The unit travels with the
    values so an axis label cannot drift from the data.

    This is *not* the result schema. How a full result is serialised
    (``xarray.Dataset`` versus Parquet plus manifest) is decided in stage 4;
    this type is what the physics layer hands over in the meantime.

    Parameters
    ----------
    grid : TimeGrid
        The time axis.
    values : FloatArray
        Sample values. First axis must match ``grid.n``; trailing axes are
        allowed, so a stack of Monte Carlo realisations of shape ``(n, m)`` is
        a valid series.
    name : str
        Short identifier, e.g. ``"skr"``, ``"elevation"``.
    unit : str
        Unit string in the project convention, e.g. ``"bit/s"``, ``"rad"``,
        ``"km"``, or ``""`` for a dimensionless quantity such as transmittance.

    Raises
    ------
    DomainError
        If the leading axis of ``values`` does not match ``grid.n``.

    Examples
    --------
    >>> grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=10.0, n=11)
    >>> series = TimeSeries(grid, np.zeros(11), name="eta_total", unit="")
    >>> len(series)
    11
    """

    grid: TimeGrid
    values: FloatArray
    name: str
    unit: str = ""

    def __post_init__(self) -> None:
        """Check that the values line up with the time axis."""
        if self.values.ndim == 0 or self.values.shape[0] != self.grid.n:
            raise DomainError(
                f"TimeSeries {self.name!r}: leading axis of values has length "
                f"{None if self.values.ndim == 0 else self.values.shape[0]}, "
                f"but the grid has {self.grid.n} samples."
            )

    def __len__(self) -> int:
        return self.grid.n

    def __repr__(self) -> str:
        unit = f" [{self.unit}]" if self.unit else ""
        return f"TimeSeries({self.name!r}{unit}, shape={self.values.shape})"
