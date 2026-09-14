"""Results addressed by what produced them, so that re-running a figure is free.

What the cache is, for someone arriving new
-------------------------------------------
A run is a pure function of three things: the scenario's physics, the code that
evaluated it, and — for a Monte Carlo — the seed. :class:`ResultCache` stores a
:class:`~quoss.scenario.result.SimulationResult` under a key built from exactly
those three, and hands it back when the same three come again.
``notes/GUIA_REIMPLEMENTACION.md`` §2.2 asks for this third cache level
("caché de resultados *content-addressed* por hash de escenario. Re-ejecutar
una figura debe ser gratis").

The key, part by part, and what each part protects against
-----------------------------------------------------------
``<scenario_hash>-<quoss version>[-seed<seed>]``, one directory per key.

- :func:`~quoss.scenario.hash.scenario_hash` excludes ``name`` and
  ``description``, so two files with the same physics share an entry, and
  includes every other field, so changing a mask by a hundredth of a degree is
  a different entry.
- ``quoss.__version__``: a result is a claim about what *this* code computes.
  A fixed bug that changed a number must not be answered from before the fix.
  The version is coarser than the commit, deliberately: a commit that touches
  a docstring would otherwise throw every entry away. The price is that a
  development checkout keeps serving entries across physics changes until the
  version moves; ``--cache`` is off by default in the CLI for that reason.
- The seed, for a Monte Carlo scenario: the ensemble is a function of the seed
  (``docs/adr/0012-correlated-fading-and-monte-carlo.md`` §6), so seed 7 and
  seed 8 are two results.

**An unseeded Monte Carlo is never cached.** ``seed: null`` means "draw one and
record it" (:mod:`quoss.core.rng`), so every run of that file records a
different seed and produces a different ensemble. Storing one would put an
entry on disk that no later run of the same file can ever hit — it would draw
another seed — while tempting a future change to key on the scenario alone and
serve one random ensemble as if it were *the* answer. To cache an ensemble,
write its seed into the scenario, which also makes the file reproduce it.

Layout and atomicity
--------------------
``<directory>/<key>/manifest.json`` and ``arrays.npz``, from
:meth:`~quoss.scenario.result.SimulationResult.to_manifest_and_arrays`. An
entry is written into a temporary sibling directory and moved into place with
one ``rename``, which POSIX makes atomic: a reader sees the old entry, the new
one, or none, never half of one. A crash mid-write leaves a ``.tmp-*``
directory that no key names.

A damaged entry is a miss, not an error
---------------------------------------
If an entry cannot be read back — truncated ``.npz``, invalid JSON, a manifest
from another schema, a stored hash that is not the key's — :meth:`ResultCache.get`
records a ``WARNING`` ``engine.cache-corrupt`` and returns ``None``, and the
next :meth:`ResultCache.put` replaces it. Not a
:class:`~quoss.core.errors.DataError`, because a cache holds nothing that
cannot be recomputed: the scenario is intact, and refusing to run it because a
derived copy was damaged would turn a disk hiccup into a failed simulation. A
``DataError`` is for external data that cannot be regenerated. The warning
exists so that repeated corruption is visible rather than silently paid for in
run time.

Examples
--------
>>> import tempfile
>>> from pathlib import Path
>>> from quoss.core.errors import DegradationLog
>>> from quoss.scenario.defaults import reference_castelldefels
>>> cache = ResultCache(Path(tempfile.mkdtemp()))
>>> scenario = reference_castelldefels()
>>> cache.key(
...     scenario, seed=None
... ) == f"{__import__('quoss.scenario.hash', fromlist=['x']).scenario_hash(scenario)}-{__import__('quoss').__version__}"
True
>>> cache.get(scenario, seed=None, degradations=DegradationLog()) is None
True
"""

from __future__ import annotations

import json
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Any

import numpy as np

import quoss
from quoss.core.errors import Degradation, DegradationLog, DomainError, Severity
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import Scenario
from quoss.scenario.result import SimulationResult

__all__ = ["ARRAYS_NAME", "MANIFEST_NAME", "ResultCache"]

MANIFEST_NAME = "manifest.json"
ARRAYS_NAME = "arrays.npz"
_WHERE = "quoss.engine.cache.ResultCache"


def _json_default(value: Any) -> Any:
    """Serialise NumPy scalars and arrays that degradation details may carry.

    Physics code records the numbers it substituted, and those numbers arrive as
    NumPy objects: ``degradations.degrade("channel.x", ..., fraction=eta)`` with
    ``eta`` a ``np.float64`` is the normal shape of a warning, and ``json.dumps``
    refuses it. Dropping the detail would leave a warning nobody can act on, so
    it is converted.

    The two branches are not equally travelled.
    :meth:`~quoss.scenario.result.SimulationResult.to_manifest_and_arrays` walks
    the whole manifest — warnings included — and lifts **every** ``ndarray`` into
    the ``.npz`` behind a ``{"$array": key}`` marker, through dicts, lists and
    tuples alike. So an array does not normally reach JSON at all; the array
    branch here is the guard for a detail shaped in a way that walk does not
    recurse into, and it converts rather than raising because a cache must never
    be the reason a run that computed everything correctly fails. Anything else
    does raise: storing ``"<object at 0x7f…>"`` and calling it a record of what
    happened would be worse than refusing.
    """
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"{type(value).__name__} is not JSON serialisable")


class ResultCache:
    """A directory of results keyed by scenario hash, code version and seed.

    Parameters
    ----------
    directory : Path
        Where entries live. Created on first write.

    Examples
    --------
    >>> import tempfile
    >>> from pathlib import Path
    >>> ResultCache(Path(tempfile.mkdtemp())).directory.is_dir()
    True
    """

    __slots__ = ("_directory",)

    def __init__(self, directory: Path | str) -> None:
        self._directory = Path(directory)

    @property
    def directory(self) -> Path:
        """The cache directory."""
        return self._directory

    # -- keys --------------------------------------------------------------- #
    @staticmethod
    def is_cacheable(scenario: Scenario) -> bool:
        """Whether results of this scenario may be cached.

        Everything except a Monte Carlo scenario whose seed is ``None``; see the
        module docstring for why.

        Parameters
        ----------
        scenario : Scenario
            The inputs.

        Returns
        -------
        bool
            ``True`` unless the scenario draws an unrecorded seed per run.
        """
        return scenario.monte_carlo is None or scenario.monte_carlo.seed is not None

    def key(self, scenario: Scenario, *, seed: int | None) -> str:
        """Return the entry name of a scenario run with a seed.

        Parameters
        ----------
        scenario : Scenario
            The inputs.
        seed : int or None
            The seed the run used; ignored for a scenario without Monte Carlo,
            which draws nothing.

        Returns
        -------
        str
            ``<scenario_hash>-<version>`` plus ``-seed<seed>`` for an ensemble.

        Raises
        ------
        DomainError
            If the scenario has a Monte Carlo and ``seed`` is ``None``.
        """
        base = f"{scenario_hash(scenario)}-{quoss.__version__}"
        if scenario.monte_carlo is None:
            return base
        if seed is None:
            raise DomainError(
                "a Monte Carlo result is a function of its seed; a cache key without one would "
                "serve one ensemble for all of them."
            )
        return f"{base}-seed{int(seed)}"

    def path(self, scenario: Scenario, *, seed: int | None) -> Path:
        """Return the directory an entry lives in (whether or not it exists)."""
        return self._directory / self.key(scenario, seed=seed)

    # -- reading ------------------------------------------------------------ #
    def get(
        self, scenario: Scenario, *, seed: int | None, degradations: DegradationLog
    ) -> SimulationResult | None:
        """Return the stored result of a scenario and seed, or ``None``.

        On a hit the stored run's warnings are appended to ``degradations`` —
        they still describe the numbers being returned — followed by an
        ``INFO`` ``engine.cache-hit``, and the returned result's ``warnings``
        are those same entries.

        Parameters
        ----------
        scenario : Scenario
            The inputs.
        seed : int or None
            The seed the run would use; ``None`` for a scenario with no Monte
            Carlo.
        degradations : DegradationLog
            Receives the replayed warnings and the hit, or the corruption warning.

        Returns
        -------
        SimulationResult or None
            The stored result, or ``None`` on a miss, an uncacheable scenario or
            a damaged entry.
        """
        if not self.is_cacheable(scenario):
            return None
        entry = self.path(scenario, seed=seed)
        manifest_path, arrays_path = entry / MANIFEST_NAME, entry / ARRAYS_NAME
        if not entry.exists():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            # The file is opened here and not by ``np.load`` because a truncated
            # archive makes ``np.load`` raise *after* it has opened the path and
            # *before* it returns the object whose ``close`` would release it: the
            # descriptor then survives until the garbage collector runs. One
            # damaged entry leaking one descriptor is harmless; a cache directory
            # damaged by a full disk, read on every run of a sweep, is not.
            with arrays_path.open("rb") as handle, np.load(handle, allow_pickle=False) as stored:
                arrays = {name: stored[name] for name in stored.files}
            result = SimulationResult.from_manifest_and_arrays(manifest, arrays)
            expected = scenario_hash(scenario)
            if (
                result.provenance.scenario_hash != expected
                or result.provenance.code_version != quoss.__version__
                or (scenario.monte_carlo is not None and result.provenance.seed != seed)
            ):
                raise DomainError(
                    f"entry records hash {result.provenance.scenario_hash!r}, version "
                    f"{result.provenance.code_version!r}, seed {result.provenance.seed!r}; the "
                    f"key names hash {expected!r}, version {quoss.__version__!r}, seed {seed!r}."
                )
        except Exception as error:  # every way a derived copy can be unreadable is a miss
            degradations.warn(
                "engine.cache-corrupt",
                f"the cache entry {entry.name} could not be read back ({type(error).__name__}: "
                f"{error}); it is treated as a miss and will be overwritten by this run.",
                where=f"{_WHERE}.get",
                entry=str(entry),
                error=type(error).__name__,
            )
            return None
        for stored_entry in result.warnings:
            degradations.add(
                Degradation(
                    code=str(stored_entry["code"]),
                    message=str(stored_entry["message"]),
                    severity=Severity(stored_entry["severity"]),
                    where=str(stored_entry["where"]),
                    details=dict(stored_entry["details"]),
                )
            )
        degradations.info(
            "engine.cache-hit",
            f"result served from the cache entry {entry.name}, computed at "
            f"{result.provenance.created_utc}; the warnings before this entry are that run's.",
            where=f"{_WHERE}.get",
            entry=str(entry),
            created_utc=result.provenance.created_utc,
        )
        return SimulationResult(
            scenario=result.scenario,
            provenance=result.provenance,
            series=result.series,
            passes=result.passes,
            daily=result.daily,
            monte_carlo=result.monte_carlo,
            multi_station=result.multi_station,
            relay=result.relay,
            warnings=[*result.warnings, degradations.entries[-1].to_dict()],
            timings=result.timings,
        )

    # -- writing ------------------------------------------------------------ #
    def put(self, result: SimulationResult, *, degradations: DegradationLog) -> Path | None:
        """Store a result atomically, replacing any entry under its key.

        Parameters
        ----------
        result : SimulationResult
            The result; its key comes from its scenario and its provenance seed.
        degradations : DegradationLog
            Receives an ``INFO`` ``engine.cache-not-stored`` when the scenario
            is not cacheable.

        Returns
        -------
        Path or None
            The entry directory, or ``None`` when nothing was stored.
        """
        scenario = result.scenario
        if not self.is_cacheable(scenario):
            degradations.info(
                "engine.cache-not-stored",
                "the scenario's Monte Carlo has seed null, so this run drew a seed of its own "
                f"({result.provenance.seed}) that no later run of the same scenario will draw; "
                "the result is not cached. Write the seed into the scenario to cache it.",
                where=f"{_WHERE}.put",
                seed=result.provenance.seed,
            )
            return None
        final = self.path(scenario, seed=result.provenance.seed)
        self._directory.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix=".tmp-", dir=self._directory))
        try:
            manifest, arrays = result.to_manifest_and_arrays()
            (staging / MANIFEST_NAME).write_text(
                json.dumps(manifest, default=_json_default, allow_nan=False), encoding="utf-8"
            )
            # Through Any: NumPy's stub types **kwds against its own allow_pickle flag.
            savez: Any = np.savez
            with (staging / ARRAYS_NAME).open("wb") as handle:
                savez(handle, **arrays)
            if final.exists():
                trash = self._directory / f".trash-{uuid.uuid4().hex}"
                final.rename(trash)
                shutil.rmtree(trash)
            staging.rename(final)
        except BaseException:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return final
