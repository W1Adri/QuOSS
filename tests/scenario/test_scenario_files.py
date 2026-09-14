"""Tests for the versioned files under ``scenarios/``.

Every file loads offline, round-trips through its own dump, and the ones that
mirror a builder in :mod:`quoss.scenario.defaults` equal it exactly — so the
file a user copies and the object a test measures cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quoss.orbits.tle import parse_tle
from quoss.scenario.defaults import ntanos_2021, reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import dumps_scenario, load_scenario, loads_scenario

EXPECTED_FILES = {
    "reference_castelldefels.yaml",
    "ntanos2021_075m.yaml",
    "ntanos2021_130m.yaml",
    "ntanos2021_230m.yaml",
    "tle_example.yaml",
}


def scenario_files(scenarios_dir: Path) -> list[Path]:
    return sorted(scenarios_dir.glob("*.yaml"))


class TestEveryFile:
    def test_the_expected_files_are_present(self, scenarios_dir: Path) -> None:
        assert {p.name for p in scenario_files(scenarios_dir)} >= EXPECTED_FILES

    def test_every_file_loads_and_round_trips(self, scenarios_dir: Path) -> None:
        files = scenario_files(scenarios_dir)
        assert files, "no scenario files found"
        for path in files:
            scenario = load_scenario(path)
            back = loads_scenario(dumps_scenario(scenario))
            assert back == scenario, path.name
            assert scenario_hash(back) == scenario_hash(scenario), path.name

    def test_every_file_starts_with_a_comment_saying_what_it_is(self, scenarios_dir: Path) -> None:
        for path in scenario_files(scenarios_dir):
            assert path.read_text(encoding="utf-8").startswith("# "), path.name


class TestFilesEqualTheirBuilders:
    def test_reference_castelldefels(self, scenarios_dir: Path) -> None:
        assert (
            load_scenario(scenarios_dir / "reference_castelldefels.yaml")
            == reference_castelldefels()
        )

    @pytest.mark.parametrize(("file", "aperture_m"), [("075m", 0.75), ("130m", 1.3), ("230m", 2.3)])
    def test_ntanos_2021(self, scenarios_dir: Path, file: str, aperture_m: float) -> None:
        assert load_scenario(scenarios_dir / f"ntanos2021_{file}.yaml") == ntanos_2021(aperture_m)


class TestTleExample:
    def test_the_tle_passes_the_checksum_and_is_the_iss(self, scenarios_dir: Path) -> None:
        scenario = load_scenario(scenarios_dir / "tle_example.yaml")
        tle = scenario.orbit.tle
        assert tle is not None
        satrec = parse_tle(tle.line1, tle.line2)
        assert satrec.satnum == 25544
        assert tle.name == "ISS (ZARYA)"

    def test_the_window_starts_at_the_tle_epoch(self, scenarios_dir: Path) -> None:
        """The file's comment claims the epoch is 2026-09-13T04:12:47.9Z; the window starts within a second of it."""
        scenario = load_scenario(scenarios_dir / "tle_example.yaml")
        tle = scenario.orbit.tle
        assert tle is not None
        assert abs(scenario.time.epoch_jd - tle.epoch_jd) * 86_400.0 < 1.0

    def test_every_optional_stage_is_present(self, scenarios_dir: Path) -> None:
        """The TLE file doubles as the schema's worked example, so all three options are on."""
        scenario = load_scenario(scenarios_dir / "tle_example.yaml")
        assert scenario.monte_carlo is not None and scenario.monte_carlo.realisations == 200
        assert scenario.multi_station is not None
        assert scenario.relay is not None and scenario.relay.pairs == [
            ("castelldefels", "skinakas")
        ]
        assert scenario.station_names == ("castelldefels", "skinakas")
