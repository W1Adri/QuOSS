"""Shared pytest fixtures.

Path anchors, plus the seeded randomness every stochastic test must draw from.
Physics fixtures (a reference scenario, a canned pass geometry) arrive with the
modules that need them.
"""

from pathlib import Path

import numpy as np
import pytest

from quoss.core.errors import DegradationLog
from quoss.core.rng import RandomSource
from quoss.core.types import TimeGrid

PROJECT_ROOT = Path(__file__).resolve().parents[1]

TEST_SEED = 20_260_731
"""Fixed seed for the whole suite.

A test that draws from an unseeded generator is a test that fails once a month
for no reason anybody can reproduce. Fixing the seed here means a failure is
always replayable; a test that genuinely needs a different stream spawns a child
rather than reseeding.
"""

TEST_EPOCH_JD = 2_460_676.5
"""2025-01-01 00:00 UTC. Arbitrary, but the same everywhere in the suite."""


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Absolute path to the repository root."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def scenarios_dir() -> Path:
    """Directory holding the versioned reference scenarios."""
    return PROJECT_ROOT / "scenarios"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    """Directory holding read-only static data and offline snapshots.

    Anchored on the *source tree* rather than on :data:`quoss.data.DATA_ROOT`
    on purpose. A test that compares the package's default path against the
    package's own constant compares a name with itself and passes whatever the
    constant says; going through the repository layout is what keeps it an
    assertion about where the data actually is.
    """
    return PROJECT_ROOT / "src" / "quoss" / "data"


@pytest.fixture
def random_source() -> RandomSource:
    """Return a freshly seeded :class:`RandomSource`, identical in every test.

    Function-scoped on purpose. A session-scoped generator would carry state
    between tests, so a test's numbers would depend on which tests ran before it
    — the exact non-determinism the injected-generator rule exists to remove.
    """
    return RandomSource.from_seed(TEST_SEED)


@pytest.fixture
def rng(random_source: RandomSource) -> np.random.Generator:
    """Return the generator to hand to a physics function under test."""
    return random_source.generator


@pytest.fixture
def degradations() -> DegradationLog:
    """Return an empty log, for asserting on what a function recorded.

    A physics test should assert on this as well as on the numbers: a function
    that returns the right value while quietly recording a substitution has still
    told the caller something they need to know.
    """
    return DegradationLog()


@pytest.fixture
def short_pass_grid() -> TimeGrid:
    """Return a 10-minute axis at 1 s spacing: the length of a LEO pass.

    The default time axis for channel and QKD tests, so that "does this scale to
    a real pass" is answered by construction rather than by a 3-sample toy.
    """
    return TimeGrid.uniform(epoch_jd=TEST_EPOCH_JD, duration_s=600.0, step_s=1.0)
