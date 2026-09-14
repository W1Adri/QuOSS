"""One function over many items, in this process or in spawned workers, with identical output.

What this is, for someone arriving new
--------------------------------------
The engine has two loops whose iterations do not talk to each other: the
stations of one run (:func:`quoss.engine.pipeline.run`) and the points of a
sweep (:func:`quoss.engine.sweep.run_sweep`). :func:`map_workers` runs such a
loop either in the calling process (``workers=1``) or across worker
**processes**, and returns the same list either way.

Why processes and not threads
-----------------------------
Python's global interpreter lock lets one thread execute Python bytecode at a
time. The stages here are mostly NumPy calls that release it, but between
those calls sit Pydantic properties, dataclass validation and SGP4 bookkeeping
that do not, so threads would serialise exactly the part that is not already
vectorised. ``notes/GUIA_REIMPLEMENTACION.md`` §2.2 names the defect this
replaces: SimulCTTC's ``run_in_threadpool`` "sobre Python escalar no paraleliza
nada (GIL)".

Why the ``spawn`` start method
------------------------------
``fork`` copies the parent's memory, including any lock another thread held at
that instant and any OpenBLAS thread pool, into a child that has none of those
threads; the documented outcome is an occasional deadlock, and CPython 3.12
warns about forking a threaded process. ``spawn`` starts a clean interpreter
that imports the function by name. The price is start-up — every worker imports
NumPy, SciPy and :mod:`quoss` — and that price is measured in
``tests/engine/test_parallel.py::TestWhatWorkersCost``; it is why the default is
one worker.

Why results and logs are joined in input order
----------------------------------------------
Workers finish in whatever order the operating system schedules them. If the
join followed completion order, the pass table of a two-station run would list
the stations in a different order on different days, and the
:class:`~quoss.core.errors.DegradationLog` would interleave their warnings
differently — two results of one scenario that compare unequal for no physical
reason. Each item therefore gets **its own** log, built inside the worker, and
the logs are appended to the caller's in input order after the fact; the
function receives its randomness inside the item (a
:meth:`~quoss.core.rng.RandomSource.spawn` child chosen by the caller), never
from the worker's identity. The consequence is the property this module is
tested on: ``workers=2`` returns the same result as ``workers=1``, bit for bit
(``tests/engine/test_parallel.py::TestWorkersDoNotChangeTheResult``).

A failure in item ``k`` re-raises in the caller after the logs of items
``0 .. k-1`` have been joined and the log of item ``k`` discarded, in both
paths, so even the failure is independent of the worker count.

Examples
--------
>>> from quoss.core.errors import DegradationLog
>>> log = DegradationLog()
>>> map_workers(_demo_square, [1, 2, 3], workers=1, degradations=log)
[1, 4, 9]
>>> [entry.details["item"] for entry in log]
[1, 2, 3]
"""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Sequence
from concurrent.futures import Future, ProcessPoolExecutor
from typing import TypeVar

from quoss.core.errors import Degradation, DegradationLog, DomainError

__all__ = ["map_workers", "validated_workers"]

T = TypeVar("T")
R = TypeVar("R")


def validated_workers(workers: int) -> int:
    """Return ``workers`` as a positive ``int``, or refuse it.

    Parameters
    ----------
    workers : int
        Requested number of worker processes. ``1`` means in-process.

    Returns
    -------
    int
        The same number.

    Raises
    ------
    DomainError
        If ``workers`` is not an integer of at least one. ``True`` is refused
        although Python counts it as ``1``: a flag passed where a count was
        expected is a caller's mistake, not a request for one worker.

    Examples
    --------
    >>> validated_workers(4)
    4
    >>> validated_workers(0)
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: workers must be an integer >= 1, got 0.
    """
    if isinstance(workers, bool) or not isinstance(workers, int) or workers < 1:
        raise DomainError(f"workers must be an integer >= 1, got {workers!r}.")
    return workers


def _call(fn: Callable[[T, DegradationLog], R], item: T) -> tuple[R, tuple[Degradation, ...]]:
    """Run ``fn`` on one item with a fresh log; the unit both paths execute."""
    log = DegradationLog()
    value = fn(item, log)
    return value, tuple(log.entries)


def map_workers(
    fn: Callable[[T, DegradationLog], R],
    items: Sequence[T],
    *,
    workers: int,
    degradations: DegradationLog,
) -> list[R]:
    """Apply ``fn(item, log)`` to every item and return the values in input order.

    Parameters
    ----------
    fn : Callable[[T, DegradationLog], R]
        The work for one item. It receives a log of its own and must record
        into that one. With ``workers > 1`` it must be importable by name — a
        module-level function — and ``items`` and the return value must pickle.
    items : Sequence[T]
        The inputs. Each carries everything ``fn`` needs, including its own
        :class:`~quoss.core.rng.RandomSource` if it draws random numbers.
    workers : int
        ``1`` runs in this process. More starts at most ``min(workers,
        len(items))`` spawned processes; a single item never starts a pool,
        since there would be nothing to run beside it.
    degradations : DegradationLog
        Receives every item's log, appended in input order.

    Returns
    -------
    list[R]
        One value per item, in input order.

    Raises
    ------
    DomainError
        If ``workers`` is not a positive integer.
    Exception
        Whatever ``fn`` raised for the first failing item, after the logs of
        the items before it were joined.
    """
    count = validated_workers(workers)
    inputs = list(items)
    values: list[R] = []
    if count == 1 or len(inputs) <= 1:
        for item in inputs:
            value, entries = _call(fn, item)
            degradations.extend(entries)
            values.append(value)
        return values

    context = multiprocessing.get_context("spawn")
    pool = ProcessPoolExecutor(max_workers=min(count, len(inputs)), mp_context=context)
    try:
        futures: list[Future[tuple[R, tuple[Degradation, ...]]]] = [
            pool.submit(_call, fn, item) for item in inputs
        ]
        for future in futures:
            value, entries = future.result()
            degradations.extend(entries)
            values.append(value)
    finally:
        pool.shutdown(wait=True, cancel_futures=True)
    return values


def _demo_square(item: int, degradations: DegradationLog) -> int:
    """Square a number and log it: the module doctest's work function."""
    degradations.info("parallel.demo", "squared", where="quoss.engine.parallel", item=item)
    return item * item
