"""Shared pytest fixtures.

Kept deliberately thin at this stage: only path anchors. The RNG fixture lands
here once `quoss.core.rng` exists, so that every stochastic test draws from a
single seeded generator.
"""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    """Directory holding read-only static data and offline snapshots."""
    return PROJECT_ROOT / "data"
