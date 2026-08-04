"""Tests for the shared types, chiefly the TimeGrid invariants.

TimeGrid validates at construction so that no downstream function has to
re-check. These tests are what make that promise true.
"""

import numpy as np
import pytest

from quoss.core.constants import JD_J2000, SECONDS_PER_DAY
from quoss.core.errors import DomainError
from quoss.core.types import TimeGrid, TimeSeries

EPOCH = 2_460_676.5  # 2025-01-01 00:00 UTC, an arbitrary but concrete epoch.


class TestTimeGridConstruction:
    """The two documented ways to build a uniform axis."""

    def test_from_step(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=600.0, step_s=1.0)
        assert grid.n == 601  # closed on both ends
        assert grid.duration_s == 600.0
        assert grid.step_s == 1.0

    def test_from_sample_count(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=600.0, n=601)
        assert grid.n == 601
        assert grid.step_s == pytest.approx(1.0)

    def test_both_constructors_agree(self) -> None:
        by_step = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=300.0, step_s=0.5)
        by_count = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=300.0, n=601)
        assert np.allclose(by_step.t_s, by_count.t_s)

    def test_requires_exactly_one_of_step_or_n(self) -> None:
        with pytest.raises(DomainError, match="exactly one"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0)
        with pytest.raises(DomainError, match="exactly one"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, step_s=1.0, n=11)

    def test_non_integer_step_count_is_rejected(self) -> None:
        """Rounding 7/2 samples down would silently truncate the end of a pass."""
        with pytest.raises(DomainError, match="whole multiple"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, step_s=3.0)

    def test_rejects_non_positive_duration(self) -> None:
        with pytest.raises(DomainError, match="duration_s"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=0.0, step_s=1.0)
        with pytest.raises(DomainError, match="duration_s"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=-10.0, step_s=1.0)

    def test_rejects_non_positive_step(self) -> None:
        with pytest.raises(DomainError, match="step_s"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, step_s=0.0)

    def test_rejects_too_few_samples(self) -> None:
        with pytest.raises(DomainError, match="at least 2"):
            TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=1)


class TestTimeGridValidation:
    """Invariants every consumer is allowed to assume without checking."""

    def test_rejects_two_dimensional_axis(self) -> None:
        with pytest.raises(DomainError, match="1-D"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.zeros((3, 2)))

    def test_rejects_empty_axis(self) -> None:
        with pytest.raises(DomainError, match="at least one sample"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.array([]))

    def test_rejects_nan(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, np.nan, 2.0]))

    def test_rejects_infinity(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, np.inf]))

    def test_rejects_duplicated_samples(self) -> None:
        """Duplicates break pass segmentation and any AR(1) recursion."""
        with pytest.raises(DomainError, match="strictly increasing"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, 1.0, 1.0, 2.0]))

    def test_rejects_decreasing_samples(self) -> None:
        with pytest.raises(DomainError, match="strictly increasing"):
            TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, 2.0, 1.0]))

    def test_rejects_non_finite_epoch(self) -> None:
        with pytest.raises(DomainError, match="epoch_jd"):
            TimeGrid(epoch_jd=np.nan, t_s=np.array([0.0, 1.0]))

    def test_accepts_a_single_sample(self) -> None:
        """A one-shot evaluation is legitimate; it simply has no step."""
        grid = TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0]))
        assert grid.n == 1
        assert grid.duration_s == 0.0
        with pytest.raises(DomainError, match="no step"):
            _ = grid.step_s

    def test_is_immutable(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, step_s=1.0)
        with pytest.raises((AttributeError, TypeError)):
            grid.epoch_jd = 0.0  # type: ignore[misc]


class TestNonUniformGrids:
    """Adaptive axes are allowed, but must announce themselves."""

    def test_non_uniform_grid_is_accepted(self) -> None:
        grid = TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, 1.0, 3.0, 10.0]))
        assert not grid.is_uniform

    def test_step_of_a_non_uniform_grid_raises(self) -> None:
        """Models defined only on a uniform axis must not silently get a wrong dt."""
        grid = TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, 1.0, 3.0, 10.0]))
        with pytest.raises(DomainError, match="not uniform"):
            _ = grid.step_s

    def test_uniform_grid_is_recognised(self) -> None:
        assert TimeGrid.uniform(epoch_jd=EPOCH, duration_s=100.0, step_s=0.1).is_uniform

    def test_linspace_grid_is_recognised_as_uniform(self) -> None:
        """np.linspace spacing is not bit-identical; the tolerance must absorb that."""
        grid = TimeGrid(epoch_jd=EPOCH, t_s=np.linspace(0.0, 5400.0, 1000))
        assert grid.is_uniform


class TestAbsoluteTime:
    """The epoch/elapsed pairing is the whole reason TimeGrid exists."""

    def test_jd_starts_at_the_epoch(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=600.0, step_s=1.0)
        assert grid.jd[0] == EPOCH

    def test_jd_advances_in_days(self) -> None:
        """One day of elapsed seconds must advance the Julian date by exactly one."""
        grid = TimeGrid(epoch_jd=EPOCH, t_s=np.array([0.0, SECONDS_PER_DAY]))
        assert grid.jd[1] - grid.jd[0] == pytest.approx(1.0, abs=1e-12)

    def test_jd_has_the_same_length_as_the_axis(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=60.0, step_s=1.0)
        assert grid.jd.shape == grid.t_s.shape

    def test_j2000_epoch_round_trips(self) -> None:
        grid = TimeGrid(epoch_jd=JD_J2000, t_s=np.array([0.0]))
        assert grid.jd[0] == JD_J2000

    def test_len_matches_sample_count(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, step_s=1.0)
        assert len(grid) == grid.n == 11


class TestTimeSeries:
    """Values must line up with their axis, and carry their unit."""

    def test_accepts_matching_length(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=11)
        series = TimeSeries(grid, np.zeros(11), name="eta_total", unit="")
        assert len(series) == 11

    def test_rejects_mismatched_length(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=11)
        with pytest.raises(DomainError, match="11 samples"):
            TimeSeries(grid, np.zeros(10), name="skr", unit="bit/s")

    def test_accepts_monte_carlo_ensemble(self) -> None:
        """Trailing axes are allowed: (n, realisations) is a valid series."""
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=11)
        series = TimeSeries(grid, np.zeros((11, 500)), name="skr", unit="bit/s")
        assert series.values.shape == (11, 500)

    def test_rejects_scalar_values(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=11)
        with pytest.raises(DomainError):
            TimeSeries(grid, np.asarray(1.0), name="skr", unit="bit/s")

    def test_repr_shows_name_and_unit(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=EPOCH, duration_s=10.0, n=11)
        text = repr(TimeSeries(grid, np.zeros(11), name="skr", unit="bit/s"))
        assert "skr" in text
        assert "bit/s" in text
