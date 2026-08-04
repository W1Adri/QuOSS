"""Exception hierarchy and the explicit-degradation mechanism.

Two complementary ways for something to go wrong, and the choice between them is
never left to chance:

**Raise** when the caller asked for something impossible or meaningless — an
unphysical parameter, an unparseable TLE, a solver that will not converge. The
computation cannot continue and pretending otherwise would fabricate numbers.

**Degrade** when a *model* cannot be evaluated but the simulation still has a
defensible answer to give — a turbulence profile outside its validated altitude
range, a cloud dataset with a gap, a finite-key bound that falls back to the
asymptotic limit. The answer is still produced, but the result carries a
:class:`Degradation` record saying exactly what was substituted and why.

What is forbidden is the third option: catching an exception and quietly
returning a plausible number. That is how a paper ends up with figures that are
wrong in a way nobody can see. Every ``except`` in the physics layer must either
re-raise as a :class:`QuossError` or record a :class:`Degradation` in a
:class:`DegradationLog` that travels out with the result.

Examples
--------
>>> log = DegradationLog()
>>> log.degrade(
...     code="turbulence.scintillation-unavailable",
...     message="Cn2 profile undefined above 20 km; scintillation set to zero.",
...     where="quoss.channel.turbulence.rytov_variance",
...     altitude_km=25.0,
... )
>>> log.has_degraded
True
>>> log.entries[0].severity
<Severity.DEGRADED: 'degraded'>
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

__all__ = [
    "ConfigurationError",
    "ConvergenceError",
    "DataError",
    "Degradation",
    "DegradationLog",
    "DomainError",
    "PhysicsError",
    "QuossError",
    "ScenarioError",
    "Severity",
    "UnitConversionError",
]


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class QuossError(Exception):
    """Base class for every error raised by QuOSS.

    Catching this and nothing broader is what lets a caller distinguish "the
    simulator rejected my input" from "the simulator has a bug".
    """


class ScenarioError(QuossError):
    """The scenario is invalid, inconsistent, or cannot be loaded.

    Raised at the user-facing boundary: schema violations, contradictory
    parameters, unreadable files. Never raised from inside the physics layer.
    """


class ConfigurationError(QuossError):
    """The simulator itself is misconfigured.

    Distinct from :class:`ScenarioError`: the scenario is fine, the environment
    is not — a missing numeric backend, an unregistered protocol name.
    """


class DataError(QuossError):
    """External data is missing, malformed, or unusable.

    TLE that will not parse, a weather snapshot whose schema changed, a station
    catalogue with a duplicate identifier.
    """


class PhysicsError(QuossError):
    """A physical model was asked for something it cannot compute."""


class DomainError(PhysicsError):
    """An argument lies outside the domain where the model is defined.

    Use this for hard domain violations — a negative wavelength, a transmittance
    above one — not for "outside the range the model was validated on", which is
    a :class:`Degradation`.
    """


class ConvergenceError(PhysicsError):
    """An iterative solver failed to converge to the requested tolerance."""


class UnitConversionError(QuossError):
    """A unit conversion received a value its convention cannot represent.

    Typically a negative linear ratio handed to a decibel conversion, or a
    transmittance greater than one.
    """


# --------------------------------------------------------------------------- #
# Explicit degradation
# --------------------------------------------------------------------------- #
class Severity(StrEnum):
    """How badly a recorded event affects the trustworthiness of a result.

    Attributes
    ----------
    INFO
        Worth reporting, no effect on the numbers. A cache hit, a fallback that
        is exact rather than approximate.
    WARNING
        The numbers are still those of the requested model, but the caller is
        operating near an edge — extrapolating a fit, sampling coarsely.
    DEGRADED
        A model was **substituted**. The numbers are no longer those of the
        requested model, and any figure derived from them must say so.
    """

    INFO = "info"
    WARNING = "warning"
    DEGRADED = "degraded"


@dataclass(frozen=True, slots=True)
class Degradation:
    """A single recorded deviation from the nominal computation.

    Parameters
    ----------
    code : str
        Stable, machine-readable identifier, dotted and lowercase, e.g.
        ``"turbulence.scintillation-unavailable"``. Stable across versions so
        that downstream code and tests can assert on it; the ``message`` is free
        to be reworded, the ``code`` is not.
    message : str
        Human-readable explanation. States what was substituted, not just that
        something happened.
    severity : Severity
        See :class:`Severity`.
    where : str
        Fully qualified name of the function that recorded it, e.g.
        ``"quoss.channel.turbulence.rytov_variance"``. Makes a warning in a
        result traceable to one line of code.
    details : Mapping[str, Any]
        Structured context — the offending values, the substituted model. Must
        be JSON-serialisable: these travel into the result manifest.
    """

    code: str
    message: str
    severity: Severity
    where: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable view for the result manifest.

        Returns
        -------
        dict[str, Any]
            Keys ``code``, ``message``, ``severity``, ``where``, ``details``.
        """
        return {
            "code": self.code,
            "message": self.message,
            "severity": str(self.severity),
            "where": self.where,
            "details": dict(self.details),
        }

    def __str__(self) -> str:
        detail = f" {dict(self.details)}" if self.details else ""
        return f"[{self.severity}] {self.code} in {self.where}: {self.message}{detail}"


class DegradationLog:
    """Append-only collector of :class:`Degradation` records.

    Passed **explicitly** down the call chain — there is no module-level
    singleton, because a global would make the physics layer non-reentrant and
    unparallelisable. A function that can degrade takes a log as a required
    argument; that requirement is what makes the degradation impossible to drop
    on the floor.

    Not thread-safe by design. Give each worker its own log and
    :meth:`extend` them at the join point, the same way each worker gets its own
    ``Generator`` from :mod:`quoss.core.rng`.

    Examples
    --------
    >>> log = DegradationLog()
    >>> log.warn("beam.wide-divergence", "Divergence above fit range.", where="demo")
    >>> len(log)
    1
    >>> log.has_degraded
    False
    """

    __slots__ = ("_entries",)

    def __init__(self, entries: Iterable[Degradation] = ()) -> None:
        self._entries: list[Degradation] = list(entries)

    # -- recording ---------------------------------------------------------- #
    def add(self, entry: Degradation) -> None:
        """Append an already-built record.

        Parameters
        ----------
        entry : Degradation
            The record to append.
        """
        self._entries.append(entry)

    def info(self, code: str, message: str, *, where: str, **details: Any) -> None:
        """Record a :attr:`Severity.INFO` event.

        Parameters
        ----------
        code : str
            Stable identifier.
        message : str
            Human-readable explanation.
        where : str
            Fully qualified name of the recording function.
        **details : Any
            JSON-serialisable structured context.
        """
        self.add(Degradation(code, message, Severity.INFO, where, details))

    def warn(self, code: str, message: str, *, where: str, **details: Any) -> None:
        """Record a :attr:`Severity.WARNING` event.

        Parameters
        ----------
        code : str
            Stable identifier.
        message : str
            Human-readable explanation.
        where : str
            Fully qualified name of the recording function.
        **details : Any
            JSON-serialisable structured context.
        """
        self.add(Degradation(code, message, Severity.WARNING, where, details))

    def degrade(self, code: str, message: str, *, where: str, **details: Any) -> None:
        """Record a :attr:`Severity.DEGRADED` event: a model was substituted.

        Parameters
        ----------
        code : str
            Stable identifier.
        message : str
            What was substituted, and for what.
        where : str
            Fully qualified name of the recording function.
        **details : Any
            JSON-serialisable structured context.
        """
        self.add(Degradation(code, message, Severity.DEGRADED, where, details))

    def extend(self, other: DegradationLog | Iterable[Degradation]) -> None:
        """Merge records from another log, preserving order.

        Parameters
        ----------
        other : DegradationLog or Iterable[Degradation]
            Records to append. Used at parallel join points.
        """
        if isinstance(other, DegradationLog):
            self._entries.extend(other._entries)
        else:
            self._entries.extend(other)

    # -- inspection --------------------------------------------------------- #
    @property
    def entries(self) -> Sequence[Degradation]:
        """Immutable view of the records, in the order they were recorded."""
        return tuple(self._entries)

    @property
    def has_degraded(self) -> bool:
        """True if any record has :attr:`Severity.DEGRADED`.

        The single flag a result consumer needs to decide whether the numbers
        are those of the requested model.
        """
        return any(e.severity is Severity.DEGRADED for e in self._entries)

    def by_severity(self, severity: Severity) -> Sequence[Degradation]:
        """Return the records matching one severity.

        Parameters
        ----------
        severity : Severity
            Severity to filter on.

        Returns
        -------
        Sequence[Degradation]
            Matching records, in recording order.
        """
        return tuple(e for e in self._entries if e.severity is severity)

    def to_dicts(self) -> list[dict[str, Any]]:
        """Return every record as a JSON-serialisable dict.

        Returns
        -------
        list[dict[str, Any]]
            One :meth:`Degradation.to_dict` per record.
        """
        return [e.to_dict() for e in self._entries]

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self) -> Iterator[Degradation]:
        return iter(self._entries)

    def __bool__(self) -> bool:
        # An empty log is falsy: `if log:` reads as "did anything happen?".
        return bool(self._entries)

    def __repr__(self) -> str:
        counts = {s.value: len(self.by_severity(s)) for s in Severity}
        summary = ", ".join(f"{k}={v}" for k, v in counts.items() if v)
        return f"DegradationLog({summary or 'empty'})"
