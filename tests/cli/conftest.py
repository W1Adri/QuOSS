"""Fixtures the CLI tests share: the two committed scenarios and one that degrades."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from quoss.scenario.defaults import ge1_two_terminals
from quoss.scenario.io import dump_scenario, loads_scenario
from quoss.scenario.models import AnyScenario


@pytest.fixture(scope="session")
def downlink_file(scenarios_dir: Path) -> Path:
    return scenarios_dir / "reference_castelldefels.yaml"


@pytest.fixture(scope="session")
def horizontal_file(scenarios_dir: Path) -> Path:
    return scenarios_dir / "ge1_1km.yaml"


@pytest.fixture(scope="session")
def sweep_spec_file(scenarios_dir: Path) -> Path:
    return scenarios_dir / "sweeps" / "ge1_distance.yaml"


def _degrading(expected: tuple[str, ...]) -> AnyScenario:
    """Return a horizontal scenario whose run records exactly one DEGRADED.

    900 nm is inside the 530-1500 nm range ITU-R P.1621-2 Table 1 covers and is
    not one of its five tabulated points, so a ``condition`` background has to be
    interpolated and ``background.sky-radiance-interpolated`` is recorded at
    DEGRADED. Horizontal rather than downlink because it runs in milliseconds and
    the severity is what is under test, not the geometry.
    """
    data = ge1_two_terminals().model_dump(mode="json")
    data["transmitter"]["wavelength_nm"] = 900.0
    data["background"] = {"condition": "overcast", "sky_radiance_w_m2_um_sr": None}
    data["expected_degradations"] = list(expected)
    return loads_scenario(json.dumps(data), format="json")


@pytest.fixture
def undeclared_degradation_file(tmp_path: Path) -> Path:
    path = tmp_path / "degrades_undeclared.yaml"
    dump_scenario(_degrading(()), path)
    return path


@pytest.fixture
def declared_degradation_file(tmp_path: Path) -> Path:
    path = tmp_path / "degrades_declared.yaml"
    dump_scenario(_degrading(("background.sky-radiance-interpolated",)), path)
    return path
