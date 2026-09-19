"""Wall-clock seconds per pipeline stage, measured where they are spent.

What this is, for someone arriving new
--------------------------------------
A run of :func:`quoss.engine.pipeline.run` goes through named *stages* — orbit,
geometry, passes, channel, key, series, and the optional ones. This module
times each of them with :func:`time.perf_counter` and hands the numbers to
:class:`~quoss.scenario.result.StageTimings`, which travels inside the result.
``notes/archive/GUIA_REIMPLEMENTACION-v3.md`` §5 asks for exactly that ("tiempos por etapa
del pipeline dentro del propio resultado. Optimizar con datos, no con
intuición"): a slow run should say where it was slow without anybody attaching
a profiler.

Why ``perf_counter`` and not ``time.time``
------------------------------------------
``time.time`` is the wall clock, which an NTP correction can move backwards in
the middle of a stage and turn a duration negative;
:class:`~quoss.scenario.result.StageTimings` refuses a negative duration, so a
clock adjustment would crash a run that computed everything correctly.
``perf_counter`` is monotonic and has the highest resolution the platform
offers, which is what an *interval* needs.

Why durations accumulate under one name
---------------------------------------
Several stages run once per station. Timing each call under its own key
(``channel[castelldefels]``) would make the table's shape depend on the
scenario; summing under ``channel`` keeps one row per stage, and the per-station
split is recoverable by running one station. With worker processes the sum is
of **worker** seconds, not elapsed seconds — two stations that take one second
each in parallel report ``channel = 2 s`` over a wall time near one — and the
pipeline says so in its docstring.

Examples
--------
>>> timer = StageTimer()
>>> with timer.stage("orbit"):
...     _ = sum(range(1000))
>>> with timer.stage("orbit"):
...     _ = sum(range(1000))
>>> timings = timer.timings()
>>> list(timings.seconds)
['orbit']
>>> timings.total_s >= 0.0
True
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from types import TracebackType

from quoss.core.errors import DomainError
from quoss.scenario.result import StageTimings

__all__ = ["StageTimer", "Timer"]


class Timer:
    """A context manager that measures the seconds its block took.

    The elapsed time is available as :attr:`elapsed_s` once the block exits,
    including when it exits by an exception — a stage that failed still took
    the time it took, and a caller reporting the failure may want it.

    Examples
    --------
    >>> with Timer() as timer:
    ...     _ = sum(range(100))
    >>> timer.elapsed_s >= 0.0
    True

    Reading it before the block has finished is refused rather than answered
    with a partial number:

    >>> Timer().elapsed_s
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: Timer has not finished: elapsed_s exists only after the with-block exits.
    """

    __slots__ = ("_elapsed_s", "_start")

    def __init__(self) -> None:
        self._start: float | None = None
        self._elapsed_s: float | None = None

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        self._elapsed_s = None
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        assert self._start is not None  # __enter__ always runs first
        self._elapsed_s = time.perf_counter() - self._start

    @property
    def elapsed_s(self) -> float:
        """Seconds between entering and leaving the block.

        Raises
        ------
        DomainError
            If the block has not exited yet.
        """
        if self._elapsed_s is None:
            raise DomainError(
                "Timer has not finished: elapsed_s exists only after the with-block exits."
            )
        return self._elapsed_s


class StageTimer:
    """Collect seconds per named stage, in first-seen order, summing repeats.

    Examples
    --------
    Durations from elsewhere — a worker process — are merged with :meth:`add`:

    >>> timer = StageTimer()
    >>> timer.add("channel", 0.25)
    >>> timer.merge({"channel": 0.5, "key": 0.125})
    >>> timer.timings().to_dict()
    {'channel': 0.75, 'key': 0.125}
    """

    __slots__ = ("_seconds",)

    def __init__(self) -> None:
        self._seconds: dict[str, float] = {}

    @contextmanager
    def stage(self, name: str) -> Iterator[None]:
        """Time the enclosed block and add it to ``name``.

        Parameters
        ----------
        name : str
            Stage name. Repeated names accumulate.

        Yields
        ------
        None
            Control to the timed block.
        """
        with Timer() as timer:
            yield
        self.add(name, timer.elapsed_s)

    def add(self, name: str, seconds: float) -> None:
        """Add ``seconds`` to stage ``name``.

        Parameters
        ----------
        name : str
            Stage name.
        seconds : float
            Non-negative, finite duration.

        Raises
        ------
        DomainError
            If ``seconds`` is negative or not finite; a duration measured by a
            monotonic clock cannot be either, so one that is came from a bug.
        """
        value = float(seconds)
        if not (value >= 0.0 and value != float("inf")):
            raise DomainError(f"stage {name!r} was given a duration of {seconds!r} s.")
        self._seconds[name] = self._seconds.get(name, 0.0) + value

    def merge(self, seconds: Mapping[str, float]) -> None:
        """Add every entry of a ``{stage: seconds}`` mapping, in its order.

        Parameters
        ----------
        seconds : Mapping[str, float]
            Durations to add, typically returned by a worker.
        """
        for name, value in seconds.items():
            self.add(name, value)

    def to_dict(self) -> dict[str, float]:
        """Return a plain copy of the accumulated seconds."""
        return dict(self._seconds)

    def timings(self) -> StageTimings:
        """Return the accumulated seconds as a frozen :class:`~quoss.scenario.result.StageTimings`."""
        return StageTimings(dict(self._seconds))
