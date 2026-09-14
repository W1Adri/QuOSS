"""Tests for `quoss.engine.parallel`.

- ``TestValidatedWorkers`` — what a worker count may be, and why ``True`` is not
  a count of one.
- ``TestWorkersDoNotChangeTheResult`` — the property the module exists for:
  ``workers=2`` returns what ``workers=1`` returns, values and log alike, in
  input order and not in completion order.
- ``TestOneItemNeverStartsAPool`` — a single item runs here, whatever the count.
- ``TestAFailureIsTheSameInBothPaths`` — the failing item's log is discarded and
  the earlier ones are kept, in-process and across processes.
- ``TestWorkersAreRealProcesses`` — the pool branch really does spawn, so the
  test above is not measuring the in-process path twice.
- ``TestWhatWorkersCost`` — the start-up price named in the module docstring,
  measured rather than asserted from memory.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from quoss.core.errors import DegradationLog, DomainError
from quoss.engine.parallel import map_workers, validated_workers

# A spawned worker is a fresh interpreter that imports the work function by name,
# so `engine.workers` has to be importable *there*. `multiprocessing.spawn` copies
# the parent's `sys.path` into the child's preparation data, so putting the tests
# directory on this process's path is what makes the child able to find it; pytest
# does not add it under `--import-mode=importlib`. Without this the pool branch
# fails with `ModuleNotFoundError: No module named 'engine'` and every test below
# that measures the difference between the two paths would be untestable.
_TESTS_ROOT = str(Path(__file__).resolve().parents[1])
if _TESTS_ROOT not in sys.path:
    sys.path.insert(0, _TESTS_ROOT)

from .workers import fail_on, process_id, square  # noqa: E402 — after the path fix above

ITEMS = [1, 2, 3, 4, 5, 6]


def entries_of(log: DegradationLog) -> list[tuple[str, int]]:
    """Return the ``(code, item)`` of every entry: what "in input order" means here."""
    return [(entry.code, int(entry.details["item"])) for entry in log]


class TestValidatedWorkers:
    @pytest.mark.parametrize("count", [1, 2, 4, 64])
    def test_a_positive_integer_is_returned_unchanged(self, count: int) -> None:
        assert validated_workers(count) == count

    @pytest.mark.parametrize("bad", [0, -1, -64])
    def test_fewer_than_one_worker_is_refused(self, bad: int) -> None:
        with pytest.raises(DomainError, match=r"workers must be an integer >= 1"):
            validated_workers(bad)

    @pytest.mark.parametrize("bad", [1.0, "2", None, 2.5])
    def test_a_non_integer_is_refused(self, bad: object) -> None:
        with pytest.raises(DomainError, match=r"workers must be an integer >= 1"):
            validated_workers(bad)  # type: ignore[arg-type]

    def test_true_is_refused_although_python_counts_it_as_one(self) -> None:
        """``True == 1`` in Python, so only an explicit check catches a flag here.

        A caller who writes ``workers=True`` meant "yes, use workers" and would
        silently get exactly one, which is the case that uses none.
        """
        flag = True
        assert flag == 1  # the premise of the test: Python counts True as one
        with pytest.raises(DomainError, match=r"got True"):
            validated_workers(True)


class TestWorkersDoNotChangeTheResult:
    def test_two_workers_return_what_one_returns(self) -> None:
        one, many = DegradationLog(), DegradationLog()
        assert map_workers(square, ITEMS, workers=1, degradations=one) == [
            1,
            4,
            9,
            16,
            25,
            36,
        ]
        assert map_workers(square, ITEMS, workers=2, degradations=many) == map_workers(
            square, ITEMS, workers=1, degradations=DegradationLog()
        )

    def test_the_log_is_in_input_order_and_not_in_completion_order(self) -> None:
        one, many = DegradationLog(), DegradationLog()
        map_workers(square, ITEMS, workers=1, degradations=one)
        map_workers(square, ITEMS, workers=4, degradations=many)
        assert entries_of(many) == entries_of(one)
        assert [item for _, item in entries_of(many)] == ITEMS

    def test_the_caller_log_keeps_what_it_already_held(self) -> None:
        log = DegradationLog()
        log.info("test.before", "already here", where="tests.engine.test_parallel", item=0)
        map_workers(square, [1, 2], workers=2, degradations=log)
        assert entries_of(log) == [("test.before", 0), ("test.square", 1), ("test.square", 2)]


class TestOneItemNeverStartsAPool:
    def test_a_single_item_runs_in_this_process(self) -> None:
        (pid,) = map_workers(process_id, [0], workers=8, degradations=DegradationLog())
        assert pid == os.getpid()

    def test_no_items_at_all_is_an_empty_list(self) -> None:
        assert map_workers(square, [], workers=8, degradations=DegradationLog()) == []


class TestAFailureIsTheSameInBothPaths:
    @pytest.mark.parametrize("workers", [1, 3])
    def test_the_failure_is_re_raised_and_the_failing_items_log_is_dropped(
        self, workers: int
    ) -> None:
        log = DegradationLog()
        with pytest.raises(ValueError, match="item 3 is not welcome"):
            map_workers(fail_on, [1, 2, 3, 4], workers=workers, degradations=log)
        # Items 1 and 2 joined; item 3's own warning went with its discarded log.
        assert entries_of(log) == [("test.about-to-work", 1), ("test.about-to-work", 2)]

    def test_the_two_paths_join_exactly_the_same_entries(self) -> None:
        here, there = DegradationLog(), DegradationLog()
        for log, workers in ((here, 1), (there, 3)):
            with pytest.raises(ValueError):
                map_workers(fail_on, [1, 2, 3, 4], workers=workers, degradations=log)
        assert entries_of(there) == entries_of(here)


@pytest.mark.slow
class TestWorkersAreRealProcesses:
    def test_more_than_one_item_and_more_than_one_worker_leaves_this_process(self) -> None:
        pids = map_workers(process_id, list(range(8)), workers=2, degradations=DegradationLog())
        assert os.getpid() not in pids
        assert 1 <= len(set(pids)) <= 2

    def test_the_pool_is_capped_by_the_number_of_items(self) -> None:
        pids = map_workers(process_id, [0, 1], workers=16, degradations=DegradationLog())
        assert len(set(pids)) <= 2


@pytest.mark.slow
class TestWhatWorkersCost:
    def test_spawning_costs_more_than_the_work_it_saves_on_small_items(self) -> None:
        """Why the default is one worker, measured instead of asserted.

        Squaring six numbers is free; starting two interpreters that each import
        NumPy, SciPy and :mod:`quoss` is not. The assertion is deliberately loose
        — a tenth of a second is far below any machine's spawn cost and far above
        six multiplications — because the point is the *sign* of the difference,
        not a number this suite could reproduce on another machine.
        """
        start = time.perf_counter()
        map_workers(square, ITEMS, workers=1, degradations=DegradationLog())
        here = time.perf_counter() - start

        start = time.perf_counter()
        map_workers(square, ITEMS, workers=2, degradations=DegradationLog())
        spawned = time.perf_counter() - start

        assert here < 0.1
        assert spawned > here
