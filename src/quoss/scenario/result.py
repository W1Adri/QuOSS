"""The result schema: what a run returns, and the two ways it is written down.

What a result is, for someone arriving new
------------------------------------------
A :class:`SimulationResult` is everything the engine produced for one
scenario: the time series it evaluated per station, the table of passes, the
daily totals, the optional Monte Carlo, multi-station and relay outputs, the
list of every degradation the physics recorded, how long each stage took, and
a :class:`Provenance` block saying which scenario (by hash), which code (by
version and git commit) and which seed made it. A result that lacks any of
those is a number without a pedigree, which is what a figure caption cannot
cite.

Why frozen dataclasses over arrays, not Pydantic
------------------------------------------------
The scenario is Pydantic because its content is scalars a person writes and a
validator checks field by field. A result is mostly arrays — 86 401 elevations
per station, ``(realisations, passes)`` Monte Carlo blocks — and Pydantic would
either copy them through Python lists on every validation or need custom
types to avoid it. The containers here are ``frozen=True, slots=True``
dataclasses storing read-only arrays (:func:`~quoss.core.types.frozen_copy`),
the same convention as every physics container, with the shape checks a
consumer relies on done once at construction.

Two serialisations, and why both
--------------------------------
* :meth:`SimulationResult.to_dict` / :meth:`~SimulationResult.from_dict`: one
  JSON-serialisable dict, arrays as lists. Portable, greppable, and what an
  API or a small test wants. NaN — the value a series holds outside a pass,
  where the channel was never evaluated — is written as ``null`` and read back
  as NaN, so the output is strict JSON (``allow_nan=False`` passes) rather
  than Python's non-standard ``NaN`` token.
* :meth:`SimulationResult.to_manifest_and_arrays` /
  :meth:`~SimulationResult.from_manifest_and_arrays`: the same tree with every
  array pulled out into a flat ``{"dotted.key": np.ndarray}`` mapping and a
  marker left in its place. The manifest is small JSON; the arrays go to an
  ``.npz`` (``engine/cache.py``, ``io/export.py``) with their dtype and NaNs
  intact and without a detour through text. A day of series for one station
  is ~4 MB as arrays and ~20 MB as JSON lists; the cache is why the second
  form exists.

Both round-trip exactly, including a result with no Monte Carlo and one with
quantile arrays (``tests/scenario/test_result.py::TestRoundTrip``).

What this module does not import
--------------------------------
``system/monte_carlo.py``, ``system/multi_ogs.py`` and ``system/relay.py`` are
written in the same stage as this file, so the containers for their outputs
(:class:`MonteCarloResults`, :class:`MultiStationResults`, :class:`RelayResults`)
are defined here as plain arrays with the shapes the cross-stage contract
fixes, and the engine fills them. Nothing here depends on how those modules
compute; only on what they promise to return.

Examples
--------
>>> from quoss.scenario.defaults import reference_castelldefels
>>> provenance = Provenance.collect(reference_castelldefels(), seed=7, data_versions={})
>>> provenance.code_version == __import__("quoss").__version__
True
>>> provenance.seed
7
"""

from __future__ import annotations

import copy
import dataclasses
import datetime as dt
import math
import platform
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from importlib.metadata import version as _package_version
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

import quoss
from quoss.core.errors import DomainError
from quoss.core.types import BoolArray, FloatArray, IntArray, TimeGrid, TimeSeries, frozen_copy
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import HorizontalScenario, Scenario

__all__ = [
    "ARRAY_MARKER",
    "AnyResult",
    "DailyResults",
    "HorizontalBudgetResults",
    "HorizontalResult",
    "HorizontalSessionResults",
    "MonteCarloResults",
    "MultiStationResults",
    "PassRecord",
    "PassResults",
    "Provenance",
    "RelayResults",
    "SeriesResults",
    "SimulationResult",
    "StageTimings",
    "git_commit",
]

ARRAY_MARKER = "$array"
"""Key of the placeholder a manifest holds where an array was pulled out."""

_GIT_TIMEOUT_S = 5.0


# --------------------------------------------------------------------------- #
# Array helpers
# --------------------------------------------------------------------------- #
def _nan_for_none(node: Any) -> Any:
    """Recursively map ``None`` to NaN in a (nested) list read back from JSON."""
    if isinstance(node, list):
        return [_nan_for_none(v) for v in node]
    return np.nan if node is None else node


def _none_for_nan(node: Any) -> Any:
    """Recursively map NaN to ``None`` in a (nested) list bound for JSON."""
    if isinstance(node, list):
        return [_none_for_nan(v) for v in node]
    return None if isinstance(node, float) and np.isnan(node) else node


def _frozen(value: Any, dtype: type[np.generic]) -> Any:
    """Return a read-only array of ``dtype`` from a list (``None`` -> NaN) or an array."""
    source = _nan_for_none(value) if dtype is np.float64 and isinstance(value, list) else value
    if dtype is np.float64:
        return frozen_copy(np.array(source, dtype=np.float64))
    out = np.array(source, dtype=dtype)
    out.flags.writeable = False
    return out


def _listify(node: Any) -> Any:
    """Recursively turn arrays into lists, float NaN into ``None``."""
    if isinstance(node, np.ndarray):
        return _none_for_nan(node.tolist()) if node.dtype.kind == "f" else node.tolist()
    if isinstance(node, dict):
        return {k: _listify(v) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [_listify(v) for v in node]
    return node


def _split(node: Any, prefix: str, arrays: dict[str, np.ndarray[Any, Any]]) -> Any:
    """Recursively replace arrays with markers, collecting them under dotted keys."""
    if isinstance(node, np.ndarray):
        arrays[prefix] = node
        return {ARRAY_MARKER: prefix}
    if isinstance(node, dict):
        return {k: _split(v, f"{prefix}.{k}" if prefix else k, arrays) for k, v in node.items()}
    if isinstance(node, list | tuple):
        return [_split(v, f"{prefix}.{i}", arrays) for i, v in enumerate(node)]
    return node


def _merge(node: Any, arrays: Mapping[str, np.ndarray[Any, Any]]) -> Any:
    """Recursively put arrays back where :func:`_split` left markers."""
    if isinstance(node, dict):
        if set(node) == {ARRAY_MARKER}:
            key = node[ARRAY_MARKER]
            if key not in arrays:
                raise DomainError(f"manifest references array {key!r} that was not supplied.")
            return arrays[key]
        return {k: _merge(v, arrays) for k, v in node.items()}
    if isinstance(node, list):
        return [_merge(v, arrays) for v in node]
    return node


def _grid_tree(grid: TimeGrid) -> dict[str, Any]:
    return {"epoch_jd": grid.epoch_jd, "t_s": grid.t_s}


def _grid_from(node: Mapping[str, Any]) -> TimeGrid:
    return TimeGrid(epoch_jd=float(node["epoch_jd"]), t_s=_frozen(node["t_s"], np.float64))


def _series_tree(series: TimeSeries) -> dict[str, Any]:
    return {"name": series.name, "unit": series.unit, "values": series.values}


def _series_from(node: Mapping[str, Any], grid: TimeGrid) -> TimeSeries:
    return TimeSeries(
        grid, _frozen(node["values"], np.float64), name=str(node["name"]), unit=str(node["unit"])
    )


# --------------------------------------------------------------------------- #
# Provenance and timings
# --------------------------------------------------------------------------- #
def git_commit(directory: Path | None = None) -> str | None:
    """Return the HEAD commit of the repository containing ``directory``, or ``None``.

    ``None`` — never an exception — when ``git`` is not installed, the
    directory is not inside a repository, or the command hangs past
    ``_GIT_TIMEOUT_S``. Provenance must not be the reason a run fails; an
    installed wheel has no repository and its results are still results.

    Parameters
    ----------
    directory : Path, optional
        Where to run ``git``; defaults to the installed ``quoss`` package
        directory, so that a source checkout reports its own commit.

    Returns
    -------
    str or None
        The 40-character hex commit, or ``None``.
    """
    where = directory if directory is not None else Path(quoss.__file__).resolve().parent
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=where,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    commit = completed.stdout.strip()
    return commit or None


@dataclass(frozen=True, slots=True)
class Provenance:
    """Where a result came from: inputs, code, environment, seed, time.

    Parameters
    ----------
    scenario_hash : str
        :func:`~quoss.scenario.hash.scenario_hash` of the inputs.
    scenario_name : str
        The scenario's label, for humans (it is not in the hash).
    code_version : str
        ``quoss.__version__``.
    git_commit : str or None
        HEAD of the source checkout, ``None`` for an installed package.
    python_version, numpy_version, scipy_version : str
        The interpreter and the two numeric libraries.
    data_versions : Mapping[str, str]
        Version tags of any external data used (TLE snapshot, cloud archive),
        keyed by data kind. Empty when none.
    seed : int or None
        The seed of the run's :class:`~quoss.core.rng.RandomSource`, ``None``
        for a run that drew no random numbers.
    created_utc : str
        ISO-8601 UTC timestamp of the run.
    """

    scenario_hash: str
    scenario_name: str
    code_version: str
    git_commit: str | None
    python_version: str
    numpy_version: str
    scipy_version: str
    data_versions: Mapping[str, str]
    seed: int | None
    created_utc: str

    def __post_init__(self) -> None:
        """Freeze the data-version mapping."""
        object.__setattr__(self, "data_versions", MappingProxyType(dict(self.data_versions)))

    @classmethod
    def collect(
        cls,
        scenario: Scenario | HorizontalScenario,
        *,
        seed: int | None,
        data_versions: Mapping[str, str],
    ) -> Provenance:
        """Fill every field from the environment at the moment of the call.

        Parameters
        ----------
        scenario : Scenario or HorizontalScenario
            The inputs of the run, of either geometry.
        seed : int or None
            The recorded seed.
        data_versions : Mapping[str, str]
            External data version tags.

        Returns
        -------
        Provenance
            The record.
        """
        return cls(
            scenario_hash=scenario_hash(scenario),
            scenario_name=scenario.name,
            code_version=quoss.__version__,
            git_commit=git_commit(),
            python_version=platform.python_version(),
            numpy_version=np.__version__,
            scipy_version=_package_version("scipy"),
            data_versions=dict(data_versions),
            seed=seed,
            created_utc=dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict."""
        return {
            "scenario_hash": self.scenario_hash,
            "scenario_name": self.scenario_name,
            "code_version": self.code_version,
            "git_commit": self.git_commit,
            "python_version": self.python_version,
            "numpy_version": self.numpy_version,
            "scipy_version": self.scipy_version,
            "data_versions": dict(self.data_versions),
            "seed": self.seed,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Provenance:
        """Rebuild from :meth:`to_dict`."""
        return cls(
            scenario_hash=str(data["scenario_hash"]),
            scenario_name=str(data["scenario_name"]),
            code_version=str(data["code_version"]),
            git_commit=None if data["git_commit"] is None else str(data["git_commit"]),
            python_version=str(data["python_version"]),
            numpy_version=str(data["numpy_version"]),
            scipy_version=str(data["scipy_version"]),
            data_versions={str(k): str(v) for k, v in dict(data["data_versions"]).items()},
            seed=None if data["seed"] is None else int(data["seed"]),
            created_utc=str(data["created_utc"]),
        )


@dataclass(frozen=True, slots=True)
class StageTimings:
    """Wall-clock seconds per pipeline stage, in the order the stages ran.

    Parameters
    ----------
    seconds : Mapping[str, float]
        Stage name to elapsed seconds. Insertion order is the run order.

    Examples
    --------
    >>> timings = StageTimings({"orbit": 0.5, "channel": 1.25})
    >>> timings.total_s
    1.75
    """

    seconds: Mapping[str, float] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Freeze the mapping; refuse negative durations."""
        frozen = {str(k): float(v) for k, v in dict(self.seconds).items()}
        for name, value in frozen.items():
            if not np.isfinite(value) or value < 0.0:
                raise DomainError(
                    f"stage {name!r} has a non-finite or negative duration {value!r}."
                )
        object.__setattr__(self, "seconds", MappingProxyType(frozen))

    @property
    def total_s(self) -> float:
        """Sum over stages, s."""
        return float(sum(self.seconds.values()))

    def to_dict(self) -> dict[str, float]:
        """Return a plain dict."""
        return dict(self.seconds)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StageTimings:
        """Rebuild from :meth:`to_dict`."""
        return cls(dict(data))


# --------------------------------------------------------------------------- #
# Passes and days
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class PassRecord:
    """One pass as a row of scalars, for a table or a JSON line.

    Built by :meth:`SimulationResult.pass_records`; a view, not a store.

    Parameters
    ----------
    station : str
        The station the pass is over.
    pass_index : int
        Row in :class:`PassResults`.
    satellite_index : int
        Which satellite of the trajectory stack.
    start_jd, end_jd, culmination_jd : float
        Refined crossing and culmination instants, Julian date UTC.
    duration_s : float
        ``end - start``, s.
    culmination_elevation_rad : float
        Peak elevation, rad.
    peak_one_sided_doppler_hz : float
        Largest ``|Doppler shift|`` over the pass's samples, Hz. **One side**
        of the sweep, not the width of it.
    doppler_excursion_hz : float
        ``max(shift) - min(shift)`` over the pass's samples, Hz. The **full
        width** the receiver traverses, and the one a capture range is sized
        against. Very nearly twice the field above, never exactly.
    peak_doppler_slew_hz_s : float
        Largest ``|d(Doppler)/dt|`` over the pass's samples, Hz/s. A rate, and
        a separate specification from either width above.
    max_point_ahead_angle_rad, min_point_ahead_angle_rad : float
        Widest and narrowest point-ahead lead over the pass, rad.
    finite_bits, asymptotic_bits : float
        Key under the finite bound and under the asymptotic rate.
    has_key : bool
        ``finite_bits > 0``.
    truncated : bool
        Whether either edge was cut by the grid.
    monte_carlo_quantile_bits : tuple[float, ...] or None
        Ensemble quantiles of the finite key, in the scenario's quantile
        order, when a Monte Carlo ran.
    """

    station: str
    pass_index: int
    satellite_index: int
    start_jd: float
    end_jd: float
    culmination_jd: float
    duration_s: float
    culmination_elevation_rad: float
    peak_one_sided_doppler_hz: float
    doppler_excursion_hz: float
    peak_doppler_slew_hz_s: float
    max_point_ahead_angle_rad: float
    min_point_ahead_angle_rad: float
    finite_bits: float
    asymptotic_bits: float
    has_key: bool
    truncated: bool
    monte_carlo_quantile_bits: tuple[float, ...] | None


@dataclass(frozen=True, slots=True)
class PassResults:
    """Every pass of the run, as parallel arrays over the pass axis.

    Instants are elapsed seconds from ``epoch_jd`` so that they line up with
    the series; :attr:`start_jd` and friends convert.

    Parameters
    ----------
    epoch_jd : float
        Julian date of ``t = 0``.
    station : tuple[str, ...]
        Station name per pass.
    satellite_index : IntArray
        Satellite per pass.
    start_s, end_s, culmination_s : FloatArray
        Refined instants, s.
    culmination_elevation_rad : FloatArray
        Peak elevation per pass, rad.
    peak_one_sided_doppler_hz : FloatArray
        Largest ``|Doppler shift|`` of each pass, Hz. The **amplitude of one
        side** of the sweep: how far from the nominal carrier the signal gets.
        Sizing a capture range off this alone under-specifies it by a factor
        very close to two — that is what the next column is for.
    doppler_excursion_hz : FloatArray
        ``max(shift) - min(shift)`` of each pass, Hz. The **full span** from
        the approaching extreme to the receding one, which is what a receiver's
        **capture or search range** has to cover. Measured, not doubled: the
        two extremes of a real pass are not equal, so this runs 1.977 to 1.999
        times the column above on the reference day rather than exactly twice.
    peak_doppler_slew_hz_s : FloatArray
        Largest ``|d(Doppler)/dt|`` of each pass, Hz/s — the rate its
        **tracking loop** has to follow. A capture range and a tracking rate
        are **two separate requirements**: a wide slow receiver loses lock at
        the horizon, a fast narrow one never acquires.
    max_point_ahead_angle_rad, min_point_ahead_angle_rad : FloatArray
        Widest and narrowest point-ahead lead of each pass, rad. The *span*
        between them is what a fine-steering mirror is sized by.
    finite_bits, asymptotic_bits : FloatArray
        Key per pass under each regime.

    Note on the five acquisition columns: each is reduced over the grid samples
    **inside** the pass, and a pass begins and ends between samples, so each is
    a bound rather than the exact extremum of the continuous pass — a lower
    bound for the three maxima and for the excursion, an upper bound for the
    minimum. The size of
    that gap is a property of the grid and is measured at
    :meth:`~quoss.system.passes.PassSamples.segment_max`.
    truncated_start, truncated_end : BoolArray
        Whether the grid cut the pass at either edge.
    day_number : IntArray
        Julian day number each pass starts in.

    Raises
    ------
    DomainError
        If any array does not have one entry per pass.
    """

    epoch_jd: float
    station: tuple[str, ...]
    satellite_index: IntArray
    start_s: FloatArray
    end_s: FloatArray
    culmination_s: FloatArray
    culmination_elevation_rad: FloatArray
    peak_one_sided_doppler_hz: FloatArray
    doppler_excursion_hz: FloatArray
    peak_doppler_slew_hz_s: FloatArray
    max_point_ahead_angle_rad: FloatArray
    min_point_ahead_angle_rad: FloatArray
    finite_bits: FloatArray
    asymptotic_bits: FloatArray
    truncated_start: BoolArray
    truncated_end: BoolArray
    day_number: IntArray

    def __post_init__(self) -> None:
        """Freeze every array and check the pass axis."""
        object.__setattr__(self, "station", tuple(str(s) for s in self.station))
        n = len(self.station)
        for name, dtype in _PASS_FIELDS:
            value = _frozen(getattr(self, name), dtype)
            if value.ndim != 1 or value.shape[0] != n:
                raise DomainError(
                    f"PassResults.{name} must have one entry per pass ({n}), got shape {value.shape}."
                )
            object.__setattr__(self, name, value)

    @property
    def n_passes(self) -> int:
        """Number of passes."""
        return len(self.station)

    @property
    def duration_s(self) -> FloatArray:
        """``end_s - start_s`` per pass."""
        return self.end_s - self.start_s

    @property
    def has_key(self) -> BoolArray:
        """``finite_bits > 0`` per pass."""
        return self.finite_bits > 0.0

    @property
    def start_jd(self) -> FloatArray:
        """Start instants as Julian dates."""
        return self.epoch_jd + self.start_s / _SECONDS_PER_DAY

    @property
    def end_jd(self) -> FloatArray:
        """End instants as Julian dates."""
        return self.epoch_jd + self.end_s / _SECONDS_PER_DAY

    @property
    def culmination_jd(self) -> FloatArray:
        """Culmination instants as Julian dates."""
        return self.epoch_jd + self.culmination_s / _SECONDS_PER_DAY

    def _tree(self) -> dict[str, Any]:
        tree: dict[str, Any] = {"epoch_jd": self.epoch_jd, "station": list(self.station)}
        for name, _ in _PASS_FIELDS:
            tree[name] = getattr(self, name)
        return tree

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> PassResults:
        return cls(
            epoch_jd=float(node["epoch_jd"]),
            station=tuple(node["station"]),
            **{name: _frozen(node[name], dtype) for name, dtype in _PASS_FIELDS},
        )


_SECONDS_PER_DAY = 86_400.0
_PASS_FIELDS: tuple[tuple[str, type[np.generic]], ...] = (
    ("satellite_index", np.int64),
    ("start_s", np.float64),
    ("end_s", np.float64),
    ("culmination_s", np.float64),
    ("culmination_elevation_rad", np.float64),
    ("peak_one_sided_doppler_hz", np.float64),
    ("doppler_excursion_hz", np.float64),
    ("peak_doppler_slew_hz_s", np.float64),
    ("max_point_ahead_angle_rad", np.float64),
    ("min_point_ahead_angle_rad", np.float64),
    ("finite_bits", np.float64),
    ("asymptotic_bits", np.float64),
    ("truncated_start", np.bool_),
    ("truncated_end", np.bool_),
    ("day_number", np.int64),
)


@dataclass(frozen=True, slots=True)
class DailyResults:
    """Key per UTC day, both regimes, with the composed security of the finite one.

    Parameters
    ----------
    day_number : IntArray
        Julian day number per row.
    finite_bits, asymptotic_bits : FloatArray
        Sum over the day's passes under each regime.
    pass_count, passes_with_key : IntArray
        Passes in the day, and those with ``finite_bits > 0``.
    seconds : FloatArray
        Seconds above the mask in the day.
    composed_correctness, composed_secrecy : float or None
        ``n * eps`` over the whole table when the scenario asked for daily
        composition (``docs/adr/0011-the-block-is-the-pass.md`` §6), else
        ``None``. One statement for the table, not one per row, for the
        reason that ADR gives.
    protocol : str
        Registered protocol name.

    Raises
    ------
    DomainError
        If any array does not have one entry per day.
    """

    day_number: IntArray
    finite_bits: FloatArray
    asymptotic_bits: FloatArray
    pass_count: IntArray
    passes_with_key: IntArray
    seconds: FloatArray
    composed_correctness: float | None
    composed_secrecy: float | None
    protocol: str

    def __post_init__(self) -> None:
        """Freeze every array and check the day axis."""
        days = _frozen(self.day_number, np.int64)
        object.__setattr__(self, "day_number", days)
        n = days.shape[0] if days.ndim == 1 else -1
        for name, dtype in _DAILY_FIELDS:
            value = _frozen(getattr(self, name), dtype)
            if value.ndim != 1 or value.shape[0] != n:
                raise DomainError(
                    f"DailyResults.{name} must have one entry per day ({n}), got shape {value.shape}."
                )
            object.__setattr__(self, name, value)

    @property
    def n_days(self) -> int:
        """Number of days."""
        return int(self.day_number.shape[0])

    def _tree(self) -> dict[str, Any]:
        tree: dict[str, Any] = {"day_number": self.day_number}
        for name, _ in _DAILY_FIELDS:
            tree[name] = getattr(self, name)
        tree["composed_correctness"] = self.composed_correctness
        tree["composed_secrecy"] = self.composed_secrecy
        tree["protocol"] = self.protocol
        return tree

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> DailyResults:
        return cls(
            day_number=_frozen(node["day_number"], np.int64),
            **{name: _frozen(node[name], dtype) for name, dtype in _DAILY_FIELDS},
            composed_correctness=_optional_float(node["composed_correctness"]),
            composed_secrecy=_optional_float(node["composed_secrecy"]),
            protocol=str(node["protocol"]),
        )


_DAILY_FIELDS: tuple[tuple[str, type[np.generic]], ...] = (
    ("finite_bits", np.float64),
    ("asymptotic_bits", np.float64),
    ("pass_count", np.int64),
    ("passes_with_key", np.int64),
    ("seconds", np.float64),
)


def _optional_float(value: Any) -> float | None:
    return None if value is None else float(value)


# --------------------------------------------------------------------------- #
# Series
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SeriesResults:
    """The per-station time series of the run, on one shared grid.

    Outside a pass the channel is not evaluated, so ``transmittance``,
    ``loss_total_db``, ``noise_per_gate`` and ``asymptotic_secure_bit_s`` hold
    NaN there. **Everything geometric is defined everywhere** — the look angles,
    the range-rate, the Doppler pair and the point-ahead angle — because the
    satellite has a position whether or not the link is worth evaluating, and
    an acquisition question is asked precisely about the part of the sky the
    key stage refuses to score.

    Why the Doppler is here at all, when the range-rate already is
    --------------------------------------------------------------
    ``doppler_shift_hz`` is ``range_rate_km_s`` times a constant, so one of the
    two is redundant — deliberately. They answer to different people. The
    range-rate is the geometry and carries no assumption; the Doppler is that
    geometry **committed to a carrier**, and it is the number a transceiver's
    capture range is written in. Carrying only the first would leave every
    reader to multiply, each choosing their own speed of light and their own
    reading of the sign; carrying only the second would bury the carrier
    assumption inside a column nobody can undo.

    The carrier is the scenario's own ``transmitter.wavelength_nm``, through
    ``f0 = c / lambda``. A system with a separate classical downlink at another
    wavelength has a second carrier and this series is not it.

    Parameters
    ----------
    station : str
        Station name.
    grid : TimeGrid
        The axis every series is on.
    elevation_rad, azimuth_rad, range_km : TimeSeries
        Look angles.
    range_rate_km_s : TimeSeries
        Rate of change of slant range, km/s. Positive while receding.
    doppler_shift_hz : TimeSeries
        First-order Doppler shift of the scenario's carrier, Hz. Negative — a
        redshift — while receding, so it runs opposite to the range-rate.
    doppler_rate_hz_s : TimeSeries
        How fast that shift is sweeping, Hz/s: the receiver's *tracking rate*
        requirement, as distinct from its capture range.
    point_ahead_angle_rad : TimeSeries
        Angle a monostatic terminal must lead its transmit beam by, radians.
    transmittance, loss_total_db, noise_per_gate, asymptotic_secure_bit_s : TimeSeries
        Channel and rate.

    Raises
    ------
    DomainError
        If any series is on a different axis than ``grid``.
    """

    station: str
    grid: TimeGrid
    elevation_rad: TimeSeries
    azimuth_rad: TimeSeries
    range_km: TimeSeries
    range_rate_km_s: TimeSeries
    doppler_shift_hz: TimeSeries
    doppler_rate_hz_s: TimeSeries
    point_ahead_angle_rad: TimeSeries
    transmittance: TimeSeries
    loss_total_db: TimeSeries
    noise_per_gate: TimeSeries
    asymptotic_secure_bit_s: TimeSeries

    def __post_init__(self) -> None:
        """Every series shares the axis."""
        for name in _SERIES_FIELDS:
            series: TimeSeries = getattr(self, name)
            if series.grid.n != self.grid.n or series.grid.epoch_jd != self.grid.epoch_jd:
                raise DomainError(
                    f"SeriesResults.{name} for {self.station!r} is on a different axis "
                    f"({series.grid!r}) than the result grid ({self.grid!r})."
                )

    def _tree(self) -> dict[str, Any]:
        tree: dict[str, Any] = {"station": self.station, "grid": _grid_tree(self.grid)}
        for name in _SERIES_FIELDS:
            tree[name] = _series_tree(getattr(self, name))
        return tree

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> SeriesResults:
        grid = _grid_from(node["grid"])
        return cls(
            station=str(node["station"]),
            grid=grid,
            **{name: _series_from(node[name], grid) for name in _SERIES_FIELDS},
        )


_SERIES_FIELDS: tuple[str, ...] = (
    "elevation_rad",
    "azimuth_rad",
    "range_km",
    "range_rate_km_s",
    "doppler_shift_hz",
    "doppler_rate_hz_s",
    "point_ahead_angle_rad",
    "transmittance",
    "loss_total_db",
    "noise_per_gate",
    "asymptotic_secure_bit_s",
)


# --------------------------------------------------------------------------- #
# Optional stages
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class MonteCarloResults:
    """The ensemble spread of the finite key per pass.

    Parameters
    ----------
    quantiles : tuple[float, ...]
        The probabilities of the rows of ``quantile_bits``.
    quantile_bits : FloatArray
        Shape ``(len(quantiles), n_passes)``: the finite key at each quantile.
    outage_probability : FloatArray
        Per pass, the fraction of realisations that certified zero key.
    mean_bits : FloatArray
        Per pass, the ensemble mean of the finite key.
    realisations : int
        Ensemble size.
    seed : int
        The seed that reproduces the ensemble.

    Raises
    ------
    DomainError
        On any shape that does not match ``(quantiles, passes)``.
    """

    quantiles: tuple[float, ...]
    quantile_bits: FloatArray
    outage_probability: FloatArray
    mean_bits: FloatArray
    realisations: int
    seed: int

    def __post_init__(self) -> None:
        """Freeze and check the ``(quantiles, passes)`` shapes."""
        object.__setattr__(self, "quantiles", tuple(float(q) for q in self.quantiles))
        bits = _frozen(self.quantile_bits, np.float64)
        if bits.ndim != 2 or bits.shape[0] != len(self.quantiles):
            raise DomainError(
                f"MonteCarloResults.quantile_bits must have shape (len(quantiles)="
                f"{len(self.quantiles)}, n_passes), got {bits.shape}."
            )
        object.__setattr__(self, "quantile_bits", bits)
        n = bits.shape[1]
        for name in ("outage_probability", "mean_bits"):
            value = _frozen(getattr(self, name), np.float64)
            if value.shape != (n,):
                raise DomainError(
                    f"MonteCarloResults.{name} must have one entry per pass ({n}), got shape {value.shape}."
                )
            object.__setattr__(self, name, value)
        if self.realisations < 1:
            raise DomainError(f"realisations must be positive, got {self.realisations}.")

    @property
    def n_passes(self) -> int:
        """Number of passes."""
        return int(self.quantile_bits.shape[1])

    def _tree(self) -> dict[str, Any]:
        return {
            "quantiles": list(self.quantiles),
            "quantile_bits": self.quantile_bits,
            "outage_probability": self.outage_probability,
            "mean_bits": self.mean_bits,
            "realisations": self.realisations,
            "seed": self.seed,
        }

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> MonteCarloResults:
        return cls(
            quantiles=tuple(node["quantiles"]),
            quantile_bits=_frozen(node["quantile_bits"], np.float64),
            outage_probability=_frozen(node["outage_probability"], np.float64),
            mean_bits=_frozen(node["mean_bits"], np.float64),
            realisations=int(node["realisations"]),
            seed=int(node["seed"]),
        )


@dataclass(frozen=True, slots=True)
class MultiStationResults:
    """What several stations harvest together, per day.

    Parameters
    ----------
    station_names : tuple[str, ...]
        Row order of ``bits_per_station_day``.
    bits_per_station_day : FloatArray
        Shape ``(n_stations, n_days)``: key credited to each station per day
        under the policy.
    scheduled_pass_count : IntArray
        Per station, passes kept after conflict resolution.
    policy : str
        The aggregation policy name.

    Raises
    ------
    DomainError
        On a shape that does not match the station count.
    """

    station_names: tuple[str, ...]
    bits_per_station_day: FloatArray
    scheduled_pass_count: IntArray
    policy: str

    def __post_init__(self) -> None:
        """Freeze and check the station axis."""
        object.__setattr__(self, "station_names", tuple(str(s) for s in self.station_names))
        n = len(self.station_names)
        bits = _frozen(self.bits_per_station_day, np.float64)
        if bits.ndim != 2 or bits.shape[0] != n:
            raise DomainError(
                f"MultiStationResults.bits_per_station_day must have shape (n_stations={n}, "
                f"n_days), got {bits.shape}."
            )
        object.__setattr__(self, "bits_per_station_day", bits)
        count = _frozen(self.scheduled_pass_count, np.int64)
        if count.shape != (n,):
            raise DomainError(
                f"MultiStationResults.scheduled_pass_count must have one entry per station ({n}), "
                f"got shape {count.shape}."
            )
        object.__setattr__(self, "scheduled_pass_count", count)

    def _tree(self) -> dict[str, Any]:
        return {
            "station_names": list(self.station_names),
            "bits_per_station_day": self.bits_per_station_day,
            "scheduled_pass_count": self.scheduled_pass_count,
            "policy": self.policy,
        }

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> MultiStationResults:
        return cls(
            station_names=tuple(node["station_names"]),
            bits_per_station_day=_frozen(node["bits_per_station_day"], np.float64),
            scheduled_pass_count=_frozen(node["scheduled_pass_count"], np.int64),
            policy=str(node["policy"]),
        )


@dataclass(frozen=True, slots=True)
class RelayResults:
    """End-to-end key between station pairs through the satellite, per day.

    Parameters
    ----------
    pairs : tuple[tuple[str, str], ...]
        Row order of the arrays.
    delivered_bits_per_day : FloatArray
        Shape ``(n_pairs, n_days)``.
    mean_latency_s : FloatArray
        Per pair, mean time from the pass that generated a key to the pass
        that delivered it, s.
    residuals : FloatArray
        Per pair, key still stored on board and undelivered at the end.

    Raises
    ------
    DomainError
        On a shape that does not match the pair count.
    """

    pairs: tuple[tuple[str, str], ...]
    delivered_bits_per_day: FloatArray
    mean_latency_s: FloatArray
    residuals: FloatArray

    def __post_init__(self) -> None:
        """Freeze and check the pair axis."""
        object.__setattr__(self, "pairs", tuple((str(a), str(b)) for a, b in self.pairs))
        n = len(self.pairs)
        bits = _frozen(self.delivered_bits_per_day, np.float64)
        if bits.ndim != 2 or bits.shape[0] != n:
            raise DomainError(
                f"RelayResults.delivered_bits_per_day must have shape (n_pairs={n}, n_days), "
                f"got {bits.shape}."
            )
        object.__setattr__(self, "delivered_bits_per_day", bits)
        for name in ("mean_latency_s", "residuals"):
            value = _frozen(getattr(self, name), np.float64)
            if value.shape != (n,):
                raise DomainError(
                    f"RelayResults.{name} must have one entry per pair ({n}), got shape {value.shape}."
                )
            object.__setattr__(self, name, value)

    def _tree(self) -> dict[str, Any]:
        return {
            "pairs": [list(pair) for pair in self.pairs],
            "delivered_bits_per_day": self.delivered_bits_per_day,
            "mean_latency_s": self.mean_latency_s,
            "residuals": self.residuals,
        }

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> RelayResults:
        return cls(
            pairs=tuple((a, b) for a, b in node["pairs"]),
            delivered_bits_per_day=_frozen(node["delivered_bits_per_day"], np.float64),
            mean_latency_s=_frozen(node["mean_latency_s"], np.float64),
            residuals=_frozen(node["residuals"], np.float64),
        )


# --------------------------------------------------------------------------- #
# The result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Everything one run produced, with its provenance.

    Parameters
    ----------
    scenario : Scenario
        The inputs, verbatim.
    provenance : Provenance
        Hash, versions, seed, timestamp.
    series : Sequence[SeriesResults]
        One per station, in scenario order.
    passes : PassResults
        The pass table over every station.
    daily : DailyResults
        Per-day totals.
    monte_carlo, multi_station, relay : optional
        Outputs of the optional stages, ``None`` when the scenario did not
        ask for them.
    warnings : Sequence[Mapping[str, Any]]
        :meth:`~quoss.core.errors.DegradationLog.to_dicts` of the run's log.
    timings : StageTimings
        Seconds per stage.

    Raises
    ------
    DomainError
        If a Monte Carlo block does not have one column per pass, or the
        series do not cover the scenario's stations.
    """

    scenario: Scenario
    provenance: Provenance
    series: Sequence[SeriesResults]
    passes: PassResults
    daily: DailyResults
    monte_carlo: MonteCarloResults | None
    multi_station: MultiStationResults | None
    relay: RelayResults | None
    warnings: Sequence[Mapping[str, Any]]
    timings: StageTimings

    def __post_init__(self) -> None:
        """Freeze the sequences and check the cross-container shapes."""
        object.__setattr__(self, "series", tuple(self.series))
        object.__setattr__(self, "warnings", tuple(copy.deepcopy(dict(w)) for w in self.warnings))
        stations = tuple(s.station for s in self.series)
        if stations != self.scenario.station_names:
            raise DomainError(
                f"series cover stations {stations}, scenario declares {self.scenario.station_names}."
            )
        if self.monte_carlo is not None and self.monte_carlo.n_passes != self.passes.n_passes:
            raise DomainError(
                f"monte_carlo has {self.monte_carlo.n_passes} passes, the pass table has "
                f"{self.passes.n_passes}."
            )

    # -- views -------------------------------------------------------------- #
    def pass_records(self) -> Iterator[PassRecord]:
        """Yield one :class:`PassRecord` per pass, Monte Carlo quantiles attached if any."""
        p = self.passes
        for i in range(p.n_passes):
            quantiles = (
                None
                if self.monte_carlo is None
                else tuple(float(v) for v in self.monte_carlo.quantile_bits[:, i])
            )
            yield PassRecord(
                station=p.station[i],
                pass_index=i,
                satellite_index=int(p.satellite_index[i]),
                start_jd=float(p.start_jd[i]),
                end_jd=float(p.end_jd[i]),
                culmination_jd=float(p.culmination_jd[i]),
                duration_s=float(p.duration_s[i]),
                culmination_elevation_rad=float(p.culmination_elevation_rad[i]),
                peak_one_sided_doppler_hz=float(p.peak_one_sided_doppler_hz[i]),
                doppler_excursion_hz=float(p.doppler_excursion_hz[i]),
                peak_doppler_slew_hz_s=float(p.peak_doppler_slew_hz_s[i]),
                max_point_ahead_angle_rad=float(p.max_point_ahead_angle_rad[i]),
                min_point_ahead_angle_rad=float(p.min_point_ahead_angle_rad[i]),
                finite_bits=float(p.finite_bits[i]),
                asymptotic_bits=float(p.asymptotic_bits[i]),
                has_key=bool(p.has_key[i]),
                truncated=bool(p.truncated_start[i] or p.truncated_end[i]),
                monte_carlo_quantile_bits=quantiles,
            )

    def series_for(self, station: str) -> SeriesResults:
        """Return the series of one station.

        Raises
        ------
        KeyError
            If no station of that name has series.
        """
        for s in self.series:
            if s.station == station:
                return s
        raise KeyError(f"no series for station {station!r}.")

    # -- serialisation ------------------------------------------------------ #
    def _tree(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.model_dump(mode="json"),
            "provenance": self.provenance.to_dict(),
            "series": [s._tree() for s in self.series],
            "passes": self.passes._tree(),
            "daily": self.daily._tree(),
            "monte_carlo": None if self.monte_carlo is None else self.monte_carlo._tree(),
            "multi_station": None if self.multi_station is None else self.multi_station._tree(),
            "relay": None if self.relay is None else self.relay._tree(),
            "warnings": [copy.deepcopy(dict(w)) for w in self.warnings],
            "timings": self.timings.to_dict(),
        }

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> SimulationResult:
        return cls(
            scenario=Scenario.model_validate(node["scenario"]),
            provenance=Provenance.from_dict(node["provenance"]),
            series=tuple(SeriesResults._from_tree(s) for s in node["series"]),
            passes=PassResults._from_tree(node["passes"]),
            daily=DailyResults._from_tree(node["daily"]),
            monte_carlo=(
                None
                if node["monte_carlo"] is None
                else MonteCarloResults._from_tree(node["monte_carlo"])
            ),
            multi_station=(
                None
                if node["multi_station"] is None
                else MultiStationResults._from_tree(node["multi_station"])
            ),
            relay=None if node["relay"] is None else RelayResults._from_tree(node["relay"]),
            warnings=tuple(node["warnings"]),
            timings=StageTimings.from_dict(node["timings"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return one JSON-serialisable dict, arrays as lists and NaN as ``null``."""
        out: dict[str, Any] = _listify(self._tree())
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> SimulationResult:
        """Rebuild from :meth:`to_dict`."""
        return cls._from_tree(data)

    def to_manifest_and_arrays(self) -> tuple[dict[str, Any], dict[str, np.ndarray[Any, Any]]]:
        """Return a small JSON manifest and a flat mapping of every array.

        The manifest is :meth:`to_dict`'s structure with each array replaced by
        ``{"$array": "dotted.key"}``; the arrays keep their dtype, shape and
        NaNs. ``np.savez(path, **arrays)`` stores them.

        Returns
        -------
        tuple[dict, dict[str, np.ndarray]]
            ``(manifest, arrays)``.
        """
        arrays: dict[str, np.ndarray[Any, Any]] = {}
        manifest: dict[str, Any] = _split(self._tree(), "", arrays)
        return manifest, arrays

    @classmethod
    def from_manifest_and_arrays(
        cls, manifest: Mapping[str, Any], arrays: Mapping[str, np.ndarray[Any, Any]]
    ) -> SimulationResult:
        """Rebuild from :meth:`to_manifest_and_arrays`.

        Raises
        ------
        DomainError
            If the manifest references an array that ``arrays`` lacks.
        """
        return cls._from_tree(_merge(dict(manifest), arrays))


# --------------------------------------------------------------------------- #
# The horizontal result
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class HorizontalBudgetResults:
    """Every term of a horizontal loss budget, one number each.

    The same decomposition :class:`~quoss.channel.link_budget.LossBudget` carries
    and in the same units, flattened from arrays to scalars because a horizontal
    link has one geometry and not a time series of them. A consumer reading
    ``geometric_db`` here and ``SeriesResults.loss_total_db`` there is reading the
    same quantity from the same assembler
    (:func:`quoss.channel.link_budget._assembled_loss_budget`); what differs is
    that one of them has an axis.

    Parameters
    ----------
    geometric_db : float
        Diffraction and the transmitter's truncation, dB.
    atmospheric_db : float
        ``extinction_db_per_km`` times the path length, dB.
    pointing_db, scintillation_db : float
        The two fade allowances at ``outage_probability``, each on its own, dB.
    fade_db : float
        The two combined, as ``fade_combination`` says. **Not** their sum unless
        that is what was asked for.
    receiver_chain_db, static_db : float
        The receiver's efficiency and the declared static loss, dB.
    total_db : float
        Everything, dB.
    transmittance : float
        ``10^(-total_db/10)``, linear.
    extinction_db_per_km : float
        What the scenario declared or the model resolved, dB/km. Carried because
        the two ways of declaring it are indistinguishable downstream, and a
        result that did not say which number the run used would make a modelled
        extinction untraceable.
    log_irradiance_variance_np2 : float
        The aperture-averaged scintillation variance, Np^2.
    rytov_variance_np2 : float
        The plane-wave Rytov variance of the path, Np^2. It is here and not
        derivable from the previous field because it is what says whether the
        weak theory applied at all: above 1 it did not.
    beam_to_jitter_ratio : float
        ``gamma``, the beam radius measured in pointing jitters.

    Raises
    ------
    DomainError
        If any field is not finite, or a decibel term is negative.
    """

    geometric_db: float
    atmospheric_db: float
    pointing_db: float
    scintillation_db: float
    fade_db: float
    receiver_chain_db: float
    static_db: float
    total_db: float
    transmittance: float
    extinction_db_per_km: float
    log_irradiance_variance_np2: float
    rytov_variance_np2: float
    beam_to_jitter_ratio: float

    def __post_init__(self) -> None:
        """Check every term is a finite number and the losses are losses."""
        for field_ in dataclasses.fields(self):
            value = float(getattr(self, field_.name))
            object.__setattr__(self, field_.name, value)
            if not math.isfinite(value) and field_.name != "beam_to_jitter_ratio":
                raise DomainError(
                    f"HorizontalBudgetResults.{field_.name} must be finite, got {value}."
                )
            if field_.name.endswith("_db") and value < 0.0:
                raise DomainError(
                    f"HorizontalBudgetResults.{field_.name} is a loss in dB and must be "
                    f"non-negative, got {value}. A negative loss would be gain."
                )

    def _tree(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> HorizontalBudgetResults:
        return cls(**{f.name: float(node[f.name]) for f in dataclasses.fields(cls)})


@dataclass(frozen=True, slots=True)
class HorizontalSessionResults:
    """What one measurement session certifies, and what it would have without the bound.

    Parameters
    ----------
    duration_s : float
        The declared session length. **This is the finite-key block**; see
        :class:`~quoss.scenario.models.SessionSpec` and ADR 0024 for who is
        responsible for it being a legitimate one.
    pulses : float
        Pulses emitted in the session, ``pulse_rate_hz * duration_s``. Not
        rounded: the bound is sensitive to the block size, not to the
        integrality of a pulse count.
    finite_bits : float
        Secret bits the session certifies under Lim et al. 2014 equation (1).
        ``floor`` of a real number, so a whole number.
    asymptotic_bits : float
        What the same session would yield if the block were infinite. Reported
        beside the finite figure and never instead of it, for the reason ADR
        0011 gives: on the reference day two passes out of four differ by "some
        bits" against "none at all".
    qber : float
        Quantum bit error rate in the key basis, linear.
    phase_error_rate : float
        The inferred error rate in the conjugate basis. The field that says
        *why* a session certifies nothing when it does: at 0.5 the single-photon
        term vanishes entirely.
    noise_counts_per_gate : float
        Background, dark counts and afterpulsing, per detection gate.
    correctness, secrecy : float
        The per-block failure probabilities the figure is quoted under. Per
        **this** block: concatenating ``n`` sessions composes them to ``n eps``,
        which is :func:`~quoss.system.key_volume.composed_security`'s rule and
        is not applied here, because nothing in one session's result knows how
        many sessions an experiment will run.

    Raises
    ------
    DomainError
        On a non-finite field, a negative bit count or duration, or a rate
        outside ``[0, 1]``.
    """

    duration_s: float
    pulses: float
    finite_bits: float
    asymptotic_bits: float
    qber: float
    phase_error_rate: float
    noise_counts_per_gate: float
    correctness: float
    secrecy: float

    def __post_init__(self) -> None:
        """Check the counts are counts and the probabilities are probabilities."""
        for field_ in dataclasses.fields(self):
            value = float(getattr(self, field_.name))
            object.__setattr__(self, field_.name, value)
            if not math.isfinite(value):
                raise DomainError(
                    f"HorizontalSessionResults.{field_.name} must be finite, got {value}."
                )
            if value < 0.0:
                raise DomainError(
                    f"HorizontalSessionResults.{field_.name} must be non-negative, got {value}."
                )
        for name in ("qber", "phase_error_rate", "correctness", "secrecy"):
            value = float(getattr(self, name))
            if value > 1.0:
                raise DomainError(
                    f"HorizontalSessionResults.{name} is a probability and must be at most 1, "
                    f"got {value}."
                )

    @property
    def has_key(self) -> bool:
        """True when the session certifies at least one bit."""
        return self.finite_bits > 0.0

    @property
    def finite_bit_s(self) -> float:
        """Certified secret bits per second of the session."""
        return self.finite_bits / self.duration_s

    @property
    def asymptotic_bit_s(self) -> float:
        """Asymptotic secret bits per second. Never the number to report on its own."""
        return self.asymptotic_bits / self.duration_s

    def _tree(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> HorizontalSessionResults:
        return cls(**{f.name: float(node[f.name]) for f in dataclasses.fields(cls)})


@dataclass(frozen=True, slots=True)
class HorizontalResult:
    """Everything one horizontal run produced, with its provenance.

    Why this is a container of its own and not ``SimulationResult`` with holes
    ---------------------------------------------------------------------------
    :class:`SimulationResult` is five containers about a satellite:
    ``series`` (one per station, over a time grid), ``passes`` (a table of
    passes), ``daily`` (per-day totals), and the optional ``monte_carlo``,
    ``multi_station`` and ``relay``. A horizontal run has **none** of those
    things -- no station, no pass, no day -- and the two ways of expressing
    that inside the existing container are both worse than a new one:

    * **``None`` where arrays are.** ``passes.finite_bits`` is typed
      ``FloatArray``, and every consumer -- ``io/export.py``, ``viz/plots.py``,
      ``engine/sweep.py``'s metric resolver -- indexes it without asking. Making
      it optional pushes an ``if`` into every one of them, and the ``if`` that
      somebody forgets is an ``AttributeError`` in a plotting routine, which is
      the good case; the bad case is a silent zero.
    * **Zero-length arrays.** They type-check and they are worse: a sum over an
      empty axis is ``0.0``, so ``daily.finite_bits.sum()`` would report **a
      horizontal link that certified 448 kbit as zero bits per day**, with no
      error anywhere. That is exactly the "plausible and wrong number" this
      project exists to refuse, and no consumer could tell it from a link that
      genuinely closed nothing.

    What the two results *do* share is the part that is about the run rather
    than the geometry: ``scenario``, ``provenance``, ``warnings`` and
    ``timings``, with the same names and the same types, so anything that reads
    only those -- the cache, the CLI's warning printer, a provenance check --
    works on both without knowing which it has. ADR 0024 records the choice.

    Parameters
    ----------
    scenario : HorizontalScenario
        The inputs, verbatim.
    provenance : Provenance
        Hash, versions, seed, timestamp -- the same record a downlink carries,
        because the hash is over the canonical form of either member of the
        union.
    budget : HorizontalBudgetResults
        The loss budget, term by term.
    session : HorizontalSessionResults
        What the measurement session certifies.
    warnings : Sequence[Mapping[str, Any]]
        :meth:`~quoss.core.errors.DegradationLog.to_dicts` of the run's log.
    timings : StageTimings
        Seconds per stage.
    """

    scenario: HorizontalScenario
    provenance: Provenance
    budget: HorizontalBudgetResults
    session: HorizontalSessionResults
    warnings: Sequence[Mapping[str, Any]]
    timings: StageTimings

    def __post_init__(self) -> None:
        """Freeze the warning list, deep-copying each entry as ``SimulationResult`` does."""
        object.__setattr__(self, "warnings", tuple(copy.deepcopy(dict(w)) for w in self.warnings))

    # -- serialisation ------------------------------------------------------ #
    def _tree(self) -> dict[str, Any]:
        return {
            "scenario": self.scenario.model_dump(mode="json"),
            "provenance": self.provenance.to_dict(),
            "budget": self.budget._tree(),
            "session": self.session._tree(),
            "warnings": [copy.deepcopy(dict(w)) for w in self.warnings],
            "timings": self.timings.to_dict(),
        }

    @classmethod
    def _from_tree(cls, node: Mapping[str, Any]) -> HorizontalResult:
        return cls(
            scenario=HorizontalScenario.model_validate(node["scenario"]),
            provenance=Provenance.from_dict(node["provenance"]),
            budget=HorizontalBudgetResults._from_tree(node["budget"]),
            session=HorizontalSessionResults._from_tree(node["session"]),
            warnings=tuple(node["warnings"]),
            timings=StageTimings.from_dict(node["timings"]),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return one JSON-serialisable dict.

        No array splitting counterpart (``to_manifest_and_arrays``), and that is
        not an omission: this result holds no arrays. The whole of it is a few
        dozen floats, so the JSON *is* the archive format.
        """
        out: dict[str, Any] = _listify(self._tree())
        return out

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> HorizontalResult:
        """Rebuild from :meth:`to_dict`."""
        return cls._from_tree(data)


AnyResult = SimulationResult | HorizontalResult
"""What :func:`quoss.engine.pipeline.run` returns, for either member of ``link``.

A plain union and not a base class. The two results share four fields
(``scenario``, ``provenance``, ``warnings``, ``timings``) and nothing else, and
a base class carrying four fields would invite a consumer to write against it
and then reach for ``passes`` behind an ``isinstance``. The union makes the
narrowing explicit at the one place it matters -- ``isinstance(result,
SimulationResult)`` -- and a type checker enforces it.
"""
