"""Tests for `quoss.engine.profiling`.

- ``TestTimer`` — a block's duration, including when the block raised, and the
  refusal to answer before the block has finished.
- ``TestTheClockIsMonotonic`` — why ``perf_counter`` and not ``time.time``: the
  wall clock can move backwards mid-stage, and a negative duration is refused
  further down, so it would crash a run that computed everything correctly.
- ``TestStageTimer`` — first-seen order, repeats summed, merge from a worker.
- ``TestAnImpossibleDurationIsRefused`` — negative, infinite and NaN.
- ``TestTheTimingsTravelInTheResult`` — the point of the module: a real run
  carries one row per stage.
"""

from __future__ import annotations

import math
import time

import pytest

from quoss.core.errors import DegradationLog, DomainError
from quoss.engine.pipeline import run
from quoss.engine.profiling import StageTimer, Timer
from quoss.scenario.defaults import reference_castelldefels


def busy(seconds: float) -> None:
    """Spin for a measurable interval without sleeping.

    ``time.sleep`` is the obvious way and the wrong one here: it is allowed to
    return early or late by the scheduler's granularity, so a test that asserted
    "at least 5 ms elapsed" after sleeping 5 ms would fail now and then on a
    loaded machine. A spin on the same clock the code reads cannot undershoot.
    """
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


class TestTimer:
    def test_a_block_takes_at_least_as_long_as_it_spun(self) -> None:
        with Timer() as timer:
            busy(0.005)
        assert timer.elapsed_s >= 0.005

    def test_a_block_that_raised_still_reports_its_time(self) -> None:
        timer = Timer()
        with pytest.raises(ValueError, match="stage failed"), timer:
            busy(0.005)
            raise ValueError("stage failed")
        assert timer.elapsed_s >= 0.005

    def test_reading_before_the_block_finished_is_refused(self) -> None:
        with pytest.raises(DomainError, match="exists only after the with-block exits"):
            _ = Timer().elapsed_s

    def test_re_entering_clears_the_previous_measurement(self) -> None:
        timer = Timer()
        with timer:
            busy(0.005)
        first = timer.elapsed_s
        with timer:
            pass
        assert timer.elapsed_s < first


class TestTheClockIsMonotonic:
    def test_two_readings_never_go_backwards(self) -> None:
        """The property ``StageTimer.add`` relies on, stated where it is relied upon.

        ``time.time`` carries no such promise: an NTP step during a stage can
        make the end earlier than the start, and :meth:`StageTimer.add` refuses a
        negative duration — so a correct run would fail on a clock correction.
        """
        readings = [time.perf_counter() for _ in range(100)]
        assert readings == sorted(readings)


class TestStageTimer:
    def test_stages_keep_first_seen_order_and_repeats_are_summed(self) -> None:
        timer = StageTimer()
        with timer.stage("orbit"):
            busy(0.002)
        with timer.stage("channel"):
            busy(0.002)
        with timer.stage("orbit"):
            busy(0.002)
        seconds = timer.to_dict()
        assert list(seconds) == ["orbit", "channel"]
        assert seconds["orbit"] >= 0.004
        assert seconds["channel"] >= 0.002

    def test_a_stage_that_raised_is_not_timed_because_the_block_never_returns(self) -> None:
        """The failure propagates and the stage is left out of the table.

        ``stage`` adds the duration *after* the ``yield`` returns, so an exception
        inside the block skips the ``add``. This is asserted rather than assumed
        because the reverse — a half-run stage counted as if it had finished —
        would put a plausible number in a table people read as a measurement.
        """
        timer = StageTimer()
        with pytest.raises(ValueError, match="boom"), timer.stage("orbit"):
            raise ValueError("boom")
        assert timer.to_dict() == {}

    def test_add_accumulates_and_merge_takes_a_mapping_in_its_order(self) -> None:
        timer = StageTimer()
        timer.add("channel", 0.25)
        timer.merge({"channel": 0.5, "key": 0.125})
        assert timer.to_dict() == {"channel": 0.75, "key": 0.125}
        assert timer.timings().to_dict() == {"channel": 0.75, "key": 0.125}

    def test_zero_is_a_legal_duration(self) -> None:
        timer = StageTimer()
        timer.add("result", 0.0)
        assert timer.to_dict() == {"result": 0.0}

    def test_to_dict_is_a_copy_and_not_the_live_mapping(self) -> None:
        timer = StageTimer()
        timer.add("orbit", 1.0)
        snapshot = timer.to_dict()
        timer.add("orbit", 1.0)
        assert snapshot == {"orbit": 1.0}
        assert timer.to_dict() == {"orbit": 2.0}


class TestAnImpossibleDurationIsRefused:
    @pytest.mark.parametrize("bad", [-1e-9, -1.0, math.inf, math.nan])
    def test_negative_infinite_and_nan_are_all_refused(self, bad: float) -> None:
        """A monotonic clock cannot produce any of these, so one that did is a bug.

        NaN is included because ``not (nan >= 0.0)`` is true: the condition is
        written as a positive test rather than as ``value < 0.0`` precisely so
        that NaN falls on the refusing side instead of sailing through and
        poisoning every later sum.
        """
        timer = StageTimer()
        with pytest.raises(DomainError, match=r"stage 'orbit' was given a duration"):
            timer.add("orbit", bad)
        assert timer.to_dict() == {}

    def test_merge_refuses_the_whole_mapping_at_the_first_bad_entry(self) -> None:
        timer = StageTimer()
        with pytest.raises(DomainError):
            timer.merge({"orbit": 1.0, "channel": -1.0, "key": 1.0})
        assert timer.to_dict() == {"orbit": 1.0}


class TestTheTimingsTravelInTheResult:
    def test_a_real_run_reports_one_row_per_stage(self) -> None:
        result = run(reference_castelldefels(), degradations=DegradationLog())
        stages = list(result.timings.seconds)
        assert stages == ["orbit", "geometry", "passes", "channel", "key", "series", "result"]
        assert all(value >= 0.0 for value in result.timings.seconds.values())
        assert result.timings.total_s == pytest.approx(sum(result.timings.seconds.values()))
