"""Tests for `quoss.engine.cache`.

- ``TestWhatMayBeCached`` — everything but a Monte Carlo with ``seed: null``,
  and the reason spelled out where it is enforced.
- ``TestTheKey`` — what each part of the key protects against: physics, code
  version, seed; and labels that are not physics.
- ``TestAMissIsSilent`` — an empty directory answers ``None`` and says nothing.
- ``TestARoundTrip`` — put then get returns the same numbers, and replays the
  stored run's warnings before the hit.
- ``TestADamagedEntryIsAMissAndNotAnError`` — five ways an entry can be
  unreadable, each a ``WARNING`` and a ``None``.
- ``TestWritingIsAtomic`` — the entry appears whole or not at all, and a failed
  write leaves no staging directory behind.
- ``TestTheCacheChangesNothingAboutTheAnswer`` — the property the cache exists
  to have: a hit and a fresh run carry the same numbers.
"""

from __future__ import annotations

import dataclasses
import json
import zipfile
from pathlib import Path
from typing import Any

import numpy as np
import pytest

import quoss
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.engine.cache import ARRAYS_NAME, MANIFEST_NAME, ResultCache, _json_default
from quoss.engine.pipeline import run as _run
from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import MonteCarloSpec, Scenario
from quoss.scenario.result import SimulationResult


def run(scenario: Scenario, **kwargs: Any) -> SimulationResult:
    """:func:`quoss.engine.pipeline.run` narrowed to the downlink result.

    ``run`` takes either member of the ``link`` union and returns the matching
    result, so its static type is ``SimulationResult | HorizontalResult``. Every
    call in this file passes a downlink scenario, and the narrow is written as an
    assertion rather than a ``cast`` so that a scenario of the wrong kind fails
    here, by name, instead of on the first attribute the test reaches for.
    """
    result = _run(scenario, **kwargs)
    assert isinstance(result, SimulationResult), f"expected a downlink result, got {type(result)}"
    return result


def with_monte_carlo(*, seed: int | None) -> Scenario:
    """Return the reference scenario plus a small ensemble, so a seed enters the key."""
    return reference_castelldefels().model_copy(
        update={
            "monte_carlo": MonteCarloSpec(
                realisations=8,
                seed=seed,
                scintillation_correlation_time_s=0.002,
                pointing_correlation_time_s=0.02,
            )
        }
    )


def assert_same_numbers(one: SimulationResult, two: SimulationResult) -> None:
    """Assert two results carry the same numbers, warnings aside.

    Two results cannot be compared with ``==``: they hold NumPy arrays, whose
    ``==`` is elementwise. The serialised form is the right comparison anyway —
    it is what the cache stores — with two adjustments. Warnings are dropped,
    because a hit appends one of its own; that is the behaviour under test, not
    a difference in the numbers. And the float arrays are compared with
    ``equal_nan=True``, because a series is NaN wherever there is no pass and
    ``nan == nan`` is false, so a plain comparison would call every correct
    round trip a failure.
    """
    one_manifest, one_arrays = one.to_manifest_and_arrays()
    two_manifest, two_arrays = two.to_manifest_and_arrays()
    assert {k: v for k, v in one_manifest.items() if k != "warnings"} == {
        k: v for k, v in two_manifest.items() if k != "warnings"
    }
    assert set(one_arrays) == set(two_arrays)
    for name, array in one_arrays.items():
        other = two_arrays[name]
        assert array.dtype == other.dtype, name
        floating = np.issubdtype(array.dtype, np.floating)
        assert np.array_equal(array, other, equal_nan=floating), name


@pytest.fixture
def cache(tmp_path: Path) -> ResultCache:
    return ResultCache(tmp_path / "results")


@pytest.fixture(scope="module")
def reference_result() -> SimulationResult:
    """One reference run, shared: it is read-only here and costs a tenth of a second."""
    return run(reference_castelldefels(), degradations=DegradationLog())


class TestWhatMayBeCached:
    def test_a_scenario_without_an_ensemble_is_cacheable(self) -> None:
        assert ResultCache.is_cacheable(reference_castelldefels())

    def test_an_ensemble_with_a_written_seed_is_cacheable(self) -> None:
        assert ResultCache.is_cacheable(with_monte_carlo(seed=7))

    def test_an_ensemble_with_seed_null_is_not(self) -> None:
        """Why: every run of that file draws a different seed.

        An entry stored under such a scenario could never be hit — the next run
        draws another seed and looks under another key — so it would be dead
        bytes that tempt a future change to key on the scenario alone and serve
        one arbitrary ensemble as if it were the answer.
        """
        assert not ResultCache.is_cacheable(with_monte_carlo(seed=None))

    def test_an_uncacheable_scenario_is_a_miss_and_stores_nothing(
        self, cache: ResultCache, tmp_path: Path
    ) -> None:
        scenario = with_monte_carlo(seed=None)
        log = DegradationLog()
        assert cache.get(scenario, seed=1234, degradations=log) is None
        assert list(log) == []

        result = run(scenario, degradations=DegradationLog())
        stored = cache.put(result, degradations=log)
        assert stored is None
        (entry,) = [e for e in log if e.code == "engine.cache-not-stored"]
        assert entry.severity is Severity.INFO
        assert entry.details["seed"] == result.provenance.seed
        assert not (tmp_path / "results").exists()


class TestTheKey:
    def test_the_key_is_the_physics_hash_and_the_code_version(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        assert cache.key(scenario, seed=None) == f"{scenario_hash(scenario)}-{quoss.__version__}"

    def test_a_label_is_not_physics_and_shares_the_entry(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        renamed = scenario.model_copy(update={"name": "another name"})
        assert cache.key(renamed, seed=None) == cache.key(scenario, seed=None)

    def test_a_hundredth_of_a_degree_of_mask_is_another_entry(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        nudged = scenario.model_copy(
            update={
                "passes": scenario.passes.model_copy(
                    update={"minimum_elevation_deg": scenario.passes.minimum_elevation_deg + 0.01}
                )
            }
        )
        assert cache.key(nudged, seed=None) != cache.key(scenario, seed=None)

    def test_two_seeds_are_two_entries(self, cache: ResultCache) -> None:
        scenario = with_monte_carlo(seed=7)
        assert cache.key(scenario, seed=7) != cache.key(scenario, seed=8)
        assert cache.key(scenario, seed=7).endswith("-seed7")

    def test_a_seed_is_ignored_when_the_scenario_draws_nothing(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        assert cache.key(scenario, seed=99) == cache.key(scenario, seed=None)

    def test_an_ensemble_without_a_seed_has_no_key(self, cache: ResultCache) -> None:
        with pytest.raises(DomainError, match="function of its seed"):
            cache.key(with_monte_carlo(seed=None), seed=None)

    def test_path_names_the_entry_whether_or_not_it_exists(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        entry = cache.path(scenario, seed=None)
        assert entry.parent == cache.directory
        assert entry.name == cache.key(scenario, seed=None)
        assert not entry.exists()


class TestAMissIsSilent:
    def test_an_empty_cache_answers_none_and_records_nothing(self, cache: ResultCache) -> None:
        log = DegradationLog()
        assert cache.get(reference_castelldefels(), seed=None, degradations=log) is None
        assert list(log) == []

    def test_a_miss_does_not_create_the_directory(self, cache: ResultCache) -> None:
        cache.get(reference_castelldefels(), seed=None, degradations=DegradationLog())
        assert not cache.directory.exists()


class TestARoundTrip:
    def test_put_then_get_returns_the_same_numbers(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        entry = cache.put(reference_result, degradations=DegradationLog())
        assert entry is not None
        assert (entry / MANIFEST_NAME).is_file()
        assert (entry / ARRAYS_NAME).is_file()

        hit = cache.get(reference_castelldefels(), seed=None, degradations=DegradationLog())
        assert hit is not None
        assert_same_numbers(hit, reference_result)

    def test_the_stored_runs_warnings_come_back_before_the_hit(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        """A hit replays the warnings of the run whose numbers it is returning.

        Not decoration: the reference run records nine entries, several of them
        substituted models. A cached answer that arrived without them would be a
        degraded result presented as a clean one — exactly the silent degrading
        the project forbids.
        """
        assert len(reference_result.warnings) >= 1
        cache.put(reference_result, degradations=DegradationLog())

        log = DegradationLog()
        hit = cache.get(reference_castelldefels(), seed=None, degradations=log)
        assert hit is not None
        codes = [entry.code for entry in log]
        assert codes == [str(w["code"]) for w in reference_result.warnings] + ["engine.cache-hit"]
        assert log.entries[-1].severity is Severity.INFO
        assert [str(w["code"]) for w in hit.warnings] == codes

    def test_the_hit_names_when_the_stored_run_happened(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        cache.put(reference_result, degradations=DegradationLog())
        log = DegradationLog()
        cache.get(reference_castelldefels(), seed=None, degradations=log)
        hit = log.entries[-1]
        assert hit.details["created_utc"] == reference_result.provenance.created_utc

    def test_an_ensemble_round_trips_under_its_seed(self, cache: ResultCache) -> None:
        scenario = with_monte_carlo(seed=7)
        result = run(scenario, degradations=DegradationLog())
        cache.put(result, degradations=DegradationLog())

        assert cache.get(scenario, seed=7, degradations=DegradationLog()) is not None
        assert cache.get(scenario, seed=8, degradations=DegradationLog()) is None

    def test_putting_twice_replaces_the_entry_rather_than_stacking(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        first = cache.put(reference_result, degradations=DegradationLog())
        second = cache.put(reference_result, degradations=DegradationLog())
        assert first == second
        assert sorted(p.name for p in cache.directory.iterdir()) == [first.name]  # type: ignore[union-attr]


class TestADamagedEntryIsAMissAndNotAnError:
    """Five ways an entry can be unreadable. Each is a ``WARNING`` and a ``None``.

    Why not a ``DataError``: a cache holds nothing that cannot be recomputed. The
    scenario is intact, so refusing to run it because a *derived copy* was
    damaged would turn a disk hiccup into a failed simulation. The warning is
    what keeps repeated corruption visible instead of silently paid for in time.
    """

    @pytest.fixture
    def entry(self, cache: ResultCache, reference_result: SimulationResult) -> Path:
        stored = cache.put(reference_result, degradations=DegradationLog())
        assert stored is not None
        return stored

    def assert_miss(self, cache: ResultCache) -> DegradationLog:
        log = DegradationLog()
        assert cache.get(reference_castelldefels(), seed=None, degradations=log) is None
        (corrupt,) = [e for e in log if e.code == "engine.cache-corrupt"]
        assert corrupt.severity is Severity.WARNING
        return log

    def test_an_absent_manifest(self, cache: ResultCache, entry: Path) -> None:
        (entry / MANIFEST_NAME).unlink()
        self.assert_miss(cache)

    def test_invalid_json(self, cache: ResultCache, entry: Path) -> None:
        (entry / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
        log = self.assert_miss(cache)
        assert log.entries[-1].details["error"] == "JSONDecodeError"

    def test_a_truncated_array_file(self, cache: ResultCache, entry: Path) -> None:
        arrays = entry / ARRAYS_NAME
        arrays.write_bytes(arrays.read_bytes()[: len(arrays.read_bytes()) // 2])
        self.assert_miss(cache)

    def test_a_manifest_from_another_schema(self, cache: ResultCache, entry: Path) -> None:
        manifest = json.loads((entry / MANIFEST_NAME).read_text(encoding="utf-8"))
        del manifest["provenance"]
        (entry / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_miss(cache)

    def test_a_stored_hash_that_is_not_the_keys(self, cache: ResultCache, entry: Path) -> None:
        """The entry parses but describes another scenario: still a miss.

        This is the check that matters most, because it is the only corruption a
        reader could not notice: the numbers would load, and be somebody else's.
        """
        manifest = json.loads((entry / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest["provenance"]["scenario_hash"] = "0" * 64
        (entry / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        log = self.assert_miss(cache)
        assert "the key names hash" in log.entries[-1].message

    def test_a_stored_code_version_that_is_not_this_one(
        self, cache: ResultCache, entry: Path
    ) -> None:
        manifest = json.loads((entry / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest["provenance"]["code_version"] = "0.0.0-not-this-one"
        (entry / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        self.assert_miss(cache)

    def test_a_stored_seed_that_is_not_the_keys(self, cache: ResultCache) -> None:
        scenario = with_monte_carlo(seed=7)
        result = run(scenario, degradations=DegradationLog())
        stored = cache.put(result, degradations=DegradationLog())
        assert stored is not None
        manifest = json.loads((stored / MANIFEST_NAME).read_text(encoding="utf-8"))
        manifest["provenance"]["seed"] = 8
        (stored / MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")

        log = DegradationLog()
        assert cache.get(scenario, seed=7, degradations=log) is None
        assert log.entries[-1].code == "engine.cache-corrupt"

    def test_the_next_put_replaces_the_damaged_entry(
        self, cache: ResultCache, entry: Path, reference_result: SimulationResult
    ) -> None:
        (entry / MANIFEST_NAME).write_text("{not json", encoding="utf-8")
        cache.put(reference_result, degradations=DegradationLog())
        assert cache.get(reference_castelldefels(), seed=None, degradations=DegradationLog())


class TestWritingIsAtomic:
    def test_a_finished_entry_leaves_no_staging_directory(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        cache.put(reference_result, degradations=DegradationLog())
        assert [p.name for p in cache.directory.iterdir() if p.name.startswith(".")] == []

    def test_a_failed_write_leaves_neither_a_staging_directory_nor_an_entry(
        self,
        cache: ResultCache,
        reference_result: SimulationResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A crash mid-write must not leave a directory that a key names.

        The entry is built in a ``.tmp-*`` sibling and moved into place with one
        ``rename``; a reader therefore sees the old entry, the new one, or none.
        The failure is injected at ``np.savez``, which is the last and largest
        write and so the most likely place to run out of disk.
        """

        def explode(*args: Any, **kwargs: Any) -> None:
            raise OSError("no space left on device")

        monkeypatch.setattr(np, "savez", explode)
        with pytest.raises(OSError, match="no space left"):
            cache.put(reference_result, degradations=DegradationLog())
        assert list(cache.directory.iterdir()) == []

    def test_a_failed_replacement_leaves_the_old_entry_readable(
        self,
        cache: ResultCache,
        reference_result: SimulationResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache.put(reference_result, degradations=DegradationLog())

        def explode(*args: Any, **kwargs: Any) -> None:
            raise OSError("no space left on device")

        monkeypatch.setattr(np, "savez", explode)
        with pytest.raises(OSError):
            cache.put(reference_result, degradations=DegradationLog())
        assert cache.get(reference_castelldefels(), seed=None, degradations=DegradationLog())

    def test_the_arrays_file_is_an_uncompressed_npz_without_pickles(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        """No pickle in the cache, asserted on the bytes rather than on the call.

        ``np.load(..., allow_pickle=False)`` in :meth:`ResultCache.get` is the
        guard; this checks the other half, that nothing written needs pickling,
        so the guard never has to refuse an entry this very module wrote.
        """
        entry = cache.put(reference_result, degradations=DegradationLog())
        assert entry is not None
        with zipfile.ZipFile(entry / ARRAYS_NAME) as archive:
            assert archive.namelist()
            assert all(name.endswith(".npy") for name in archive.namelist())
        with np.load(entry / ARRAYS_NAME, allow_pickle=False) as stored:
            assert stored.files


class TestTheCacheChangesNothingAboutTheAnswer:
    def test_a_hit_carries_the_numbers_a_fresh_run_would_have_computed(
        self, cache: ResultCache
    ) -> None:
        scenario = reference_castelldefels()
        first = run(scenario, cache=cache, degradations=DegradationLog())
        log = DegradationLog()
        second = run(scenario, cache=cache, degradations=log)

        assert_same_numbers(second, first)
        assert [entry.code for entry in log][-1] == "engine.cache-hit"

    def test_the_first_run_of_a_scenario_stores_it(self, cache: ResultCache) -> None:
        scenario = reference_castelldefels()
        log = DegradationLog()
        run(scenario, cache=cache, degradations=log)
        assert cache.path(scenario, seed=None).is_dir()
        assert "engine.cache-hit" not in [entry.code for entry in log]


class TestNumpyValuesInAWarningSurviveTheManifest:
    """A degradation's ``details`` may hold NumPy values; JSON does not know them.

    Physics code records what it substituted, and what it substituted is usually
    a number it just computed — a ``np.float64``, or a small array of the
    elevations it clipped. ``json.dumps`` refuses both. The cache converts them
    instead of dropping them, because a warning that lost its numbers is a
    warning nobody can act on.
    """

    def test_a_numpy_scalar_and_array_are_stored_and_read_back(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        """The scalar becomes a Python float; the array comes back an array.

        The two take different routes, and the difference is worth seeing.
        ``to_manifest_and_arrays`` lifts every ``ndarray`` out of the manifest
        into the ``.npz`` — including the ones inside a warning's details — so
        the array never meets JSON and returns with its dtype intact. A NumPy
        *scalar* is not an array, is not lifted, and so is the value
        :func:`_json_default` actually converts.
        """
        log = DegradationLog()
        log.degrade(
            "test.numpy-details",
            "a substituted model, with its numbers",
            where="tests.engine.test_cache",
            scalar=np.float64(0.25),
            count=np.int64(3),
            array=np.array([1.5, 2.5]),
        )
        result = dataclasses.replace(reference_result, warnings=log.to_dicts())
        cache.put(result, degradations=DegradationLog())

        hit = cache.get(reference_castelldefels(), seed=None, degradations=DegradationLog())
        assert hit is not None
        (stored,) = [w for w in hit.warnings if w["code"] == "test.numpy-details"]
        details = dict(stored["details"])
        assert details["scalar"] == 0.25
        assert isinstance(details["scalar"], float)
        assert details["count"] == 3
        assert isinstance(details["count"], int)
        np.testing.assert_array_equal(details["array"], np.array([1.5, 2.5]))

    def test_the_array_branch_converts_instead_of_raising(self) -> None:
        """Called directly, because ``put`` cannot reach it — and that is the point.

        Every array inside a manifest is lifted into the ``.npz`` before
        ``json.dumps`` runs, so this branch is a guard for a detail shaped in a
        way that walk does not recurse into. It is tested here rather than
        deleted because the alternative to converting is raising, and a cache
        that raises has turned a bookkeeping surprise into a failed simulation.
        """
        assert _json_default(np.array([1.5, 2.5])) == [1.5, 2.5]
        assert _json_default(np.float64(0.25)) == 0.25
        with pytest.raises(TypeError, match="not JSON serialisable"):
            _json_default(object())

    def test_something_json_cannot_hold_at_all_is_refused_rather_than_dropped(
        self, cache: ResultCache, reference_result: SimulationResult
    ) -> None:
        """An unconvertible detail raises at ``put``, where the caller can see it.

        The alternative — ``default=str`` — would store ``"<object at 0x7f…>"``
        and call it a record of what happened.
        """
        log = DegradationLog()
        log.degrade(
            "test.unserialisable",
            "holds something JSON cannot",
            where="tests.engine.test_cache",
            thing=object(),
        )
        result = dataclasses.replace(reference_result, warnings=log.to_dicts())
        with pytest.raises(TypeError, match="not JSON serialisable"):
            cache.put(result, degradations=DegradationLog())
        assert list(cache.directory.iterdir()) == []
