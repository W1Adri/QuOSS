"""Tests for the versioned files under ``scenarios/``.

Every file loads offline, round-trips through its own dump, and the ones that
mirror a builder in :mod:`quoss.scenario.defaults` equal it exactly — so the
file a user copies and the object a test measures cannot drift apart.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quoss.orbits.tle import parse_tle
from quoss.scenario.defaults import (
    ge0b_bench,
    ge1_two_terminals,
    ntanos_2021,
    reference_castelldefels,
)
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import dumps_scenario, load_scenario, loads_scenario
from quoss.scenario.models import AnyScenario, Scenario


def as_downlink(scenario: AnyScenario) -> Scenario:
    """Narrow a loaded scenario to the downlink member, or fail the test saying so.

    :func:`~quoss.scenario.io.load_scenario` returns the member the file's
    ``link`` field names, so its static type is the union. A test that loads a
    downlink file and then reads ``scenario.time`` is not making an assumption
    worth hiding behind a ``cast``: it is asserting that the file is a downlink,
    and that assertion is worth running.
    """
    assert isinstance(scenario, Scenario), f"expected a downlink scenario, got {type(scenario)}"
    return scenario


EXPECTED_FILES = {
    "reference_castelldefels.yaml",
    "ntanos2021_075m.yaml",
    "ntanos2021_130m.yaml",
    "ntanos2021_230m.yaml",
    "tle_example.yaml",
    "ge0b_bench.yaml",
    "ge1_1km.yaml",
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

    def test_ge1_two_terminals(self, scenarios_dir: Path) -> None:
        assert load_scenario(scenarios_dir / "ge1_1km.yaml") == ge1_two_terminals()

    def test_ge0b_bench(self, scenarios_dir: Path) -> None:
        assert load_scenario(scenarios_dir / "ge0b_bench.yaml") == ge0b_bench()


class TestTheHorizontalFilesSayWhatTheyCannotAnswer:
    """The two things ``notes/LAST_CHANGES.md`` §37 measured and could not close, in the files.

    A gap that lives only in an ADR is a gap the person copying a scenario file
    never reads. Both of these decide what the file is worth, so both are in it.
    """

    def test_the_bench_file_asks_the_emulator_question_the_right_way_round(
        self, scenarios_dir: Path
    ) -> None:
        """ADR 0009 gap 20, in the file rather than only in the ADR.

        ``equivalent_bench_cn2_m23`` gives 8.87e-10 and that is a **necessary
        and not sufficient** condition: an emulator makes a phase screen with an
        ``r_0``, not a ``C_n^2`` over a length, and scintillation needs distance
        behind the screen to develop. The file has to carry the question to put
        to a vendor, because the number alone reads like a specification.
        """
        text = (scenarios_dir / "ge0b_bench.yaml").read_text(encoding="utf-8")
        assert "D/r_0" in text
        assert "how many screens" in text
        assert "NECESSARY and NOT a SUFFICIENT" in text
        assert "gap 20" in text
        assert "8.873841649388922e-10" in text

    def test_the_ge1_file_says_why_it_is_not_a_retroreflector(self, scenarios_dir: Path) -> None:
        """ADR 0025's recommendation, with the source marked as read in abstract only."""
        text = (scenarios_dir / "ge1_1km.yaml").read_text(encoding="utf-8")
        assert "Appl. Opt. 51(25):6147" in text
        assert "2012" in text
        assert "READ IN\n#   ABSTRACT ONLY" in text or "ABSTRACT ONLY" in text
        assert "SIGN" in text and "magnitude" in text

    def test_both_files_say_the_block_is_a_declaration(self, scenarios_dir: Path) -> None:
        """ADR 0024: on a stationary link the operator fixes the block, not the geometry."""
        for name in ("ge1_1km.yaml", "ge0b_bench.yaml"):
            text = (scenarios_dir / name).read_text(encoding="utf-8")
            assert "ADR 0024" in text
            assert "session" in text


class TestTleExample:
    def test_the_tle_passes_the_checksum_and_is_the_iss(self, scenarios_dir: Path) -> None:
        scenario = as_downlink(load_scenario(scenarios_dir / "tle_example.yaml"))
        tle = scenario.orbit.tle
        assert tle is not None
        satrec = parse_tle(tle.line1, tle.line2)
        assert satrec.satnum == 25544
        assert tle.name == "ISS (ZARYA)"

    def test_the_window_starts_at_the_tle_epoch(self, scenarios_dir: Path) -> None:
        """The file's comment claims the epoch is 2026-09-13T04:12:47.9Z; the window starts within a second of it."""
        scenario = as_downlink(load_scenario(scenarios_dir / "tle_example.yaml"))
        tle = scenario.orbit.tle
        assert tle is not None
        assert abs(scenario.time.epoch_jd - tle.epoch_jd) * 86_400.0 < 1.0

    def test_every_optional_stage_is_present(self, scenarios_dir: Path) -> None:
        """The TLE file doubles as the schema's worked example, so all three options are on."""
        scenario = as_downlink(load_scenario(scenarios_dir / "tle_example.yaml"))
        assert scenario.monte_carlo is not None and scenario.monte_carlo.realisations == 200
        assert scenario.multi_station is not None
        assert scenario.relay is not None and scenario.relay.pairs == [
            ("castelldefels", "skinakas")
        ]
        assert scenario.station_names == ("castelldefels", "skinakas")
