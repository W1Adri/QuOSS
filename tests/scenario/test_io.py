"""Tests for `quoss.scenario.io`.

- ``TestRoundTrip`` — ``loads(dumps(s)) == s`` for the defaults, through files
  with each suffix, and for Hypothesis-generated valid scenarios: datetimes
  and enums survive the YAML text.
- ``TestEveryErrorIsAScenarioError`` — parser errors, non-mapping documents,
  unknown formats and suffixes, unreadable and unwritable paths.
- ``TestTheMessageListsEveryFailingField`` — two mistakes are reported as two
  dotted paths in one message.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any

import pytest
import yaml
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from quoss.channel.link_budget import FadeCombination
from quoss.core.errors import ScenarioError
from quoss.scenario.defaults import ntanos_2021, reference_castelldefels
from quoss.scenario.hash import scenario_hash
from quoss.scenario.io import (
    dump_scenario,
    dumps_scenario,
    format_for_path,
    load_scenario,
    loads_scenario,
)
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


def reference_dict() -> dict[str, Any]:
    return reference_castelldefels().model_dump(mode="json")


@st.composite
def valid_scenarios(draw: st.DrawFn) -> Scenario:
    """Draw the reference scenario with a handful of fields randomised inside their domains."""
    data = reference_dict()
    step_s = draw(st.sampled_from([1.0, 2.0, 5.0, 10.0, 30.0]))
    # Labels: any printable text except the one character YAML does not preserve
    # (NEL, U+0085, which PyYAML folds to a space — see
    # ``test_yaml_folds_the_nel_character_in_labels``). Physics fields never hold text.
    label = st.characters(exclude_categories=("Cc", "Cs"), exclude_characters="\x85")
    data["name"] = draw(st.text(alphabet=label, min_size=1, max_size=20))
    data["description"] = draw(st.text(alphabet=label, max_size=40))
    data["orbit"]["kepler"]["altitude_km"] = draw(st.floats(min_value=300.0, max_value=1500.0))
    data["orbit"]["kepler"]["raan_deg"] = draw(st.floats(min_value=0.0, max_value=359.9))
    data["channel"]["zenith_transmittance"] = draw(st.floats(min_value=0.05, max_value=1.0))
    data["channel"]["fade_combination"] = draw(st.sampled_from(["exact", "additive"]))
    data["passes"]["minimum_elevation_deg"] = draw(st.floats(min_value=0.0, max_value=80.0))
    data["time"]["step_s"] = step_s
    data["time"]["duration_s"] = step_s * draw(st.integers(min_value=1, max_value=5000))
    data["time"]["epoch_utc"] = draw(
        st.datetimes(
            min_value=dt.datetime(1950, 1, 1),
            max_value=dt.datetime(2050, 12, 31),
            timezones=st.just(dt.UTC),
        )
    ).isoformat()
    data["security"]["correctness"] = draw(st.floats(min_value=1e-15, max_value=1e-3))
    return Scenario.model_validate(data)


class TestRoundTrip:
    @pytest.mark.parametrize("format", ["yaml", "json"])
    def test_the_defaults(self, format: str) -> None:
        for scenario in (reference_castelldefels(), ntanos_2021(1.3)):
            text = dumps_scenario(scenario, format=format)  # type: ignore[arg-type]
            assert loads_scenario(text, format=format) == scenario  # type: ignore[arg-type]

    @pytest.mark.parametrize("suffix", [".yaml", ".yml", ".json"])
    def test_through_a_file(self, tmp_path: Path, suffix: str) -> None:
        scenario = reference_castelldefels()
        path = tmp_path / f"scenario{suffix}"
        dump_scenario(scenario, path)
        assert load_scenario(path) == scenario
        assert load_scenario(str(path)) == scenario

    @given(scenario=valid_scenarios())
    @settings(max_examples=40, deadline=None)
    def test_generated_scenarios(self, scenario: Scenario) -> None:
        """Property: text is a faithful image, and the hash survives the trip."""
        for format in ("yaml", "json"):
            back = loads_scenario(dumps_scenario(scenario, format=format), format=format)
            assert back == scenario
            assert scenario_hash(back) == scenario_hash(scenario)

    def test_yaml_folds_the_nel_character_in_labels(self) -> None:
        """The one round-trip limitation, stated: YAML 1.1 treats U+0085 as a line break.

        PyYAML folds it to a space on the way back, so a label containing it
        does not survive the YAML path (JSON preserves it). Labels are outside
        the hash, so no physics and no cache key is affected; a physics field
        never holds text.
        """
        scenario = reference_castelldefels().model_copy(update={"description": "a\x85b"})
        assert loads_scenario(dumps_scenario(scenario)).description == "a b"
        assert loads_scenario(dumps_scenario(scenario, format="json"), format="json") == scenario
        assert scenario_hash(loads_scenario(dumps_scenario(scenario))) == scenario_hash(scenario)

    def test_the_datetime_is_written_with_z_and_read_back_aware(self) -> None:
        text = dumps_scenario(reference_castelldefels())
        assert "epoch_utc: '2025-01-01T00:00:00Z'" in text
        assert as_downlink(loads_scenario(text)).time.epoch_utc == dt.datetime(
            2025, 1, 1, tzinfo=dt.UTC
        )

    def test_a_bare_yaml_timestamp_with_offset_loads(self) -> None:
        """PyYAML parses an unquoted ``...Z`` into an aware datetime; the schema accepts it."""
        text = dumps_scenario(reference_castelldefels()).replace(
            "'2025-01-01T00:00:00Z'", "2025-01-01T00:00:00Z"
        )
        assert isinstance(yaml.safe_load(text)["time"]["epoch_utc"], dt.datetime)
        assert loads_scenario(text) == reference_castelldefels()

    def test_a_bare_yaml_timestamp_without_offset_is_the_wall_clock_defect(self) -> None:
        text = dumps_scenario(reference_castelldefels()).replace(
            "'2025-01-01T00:00:00Z'", "2025-01-01 00:00:00"
        )
        with pytest.raises(ScenarioError, match=r"time\.epoch_utc: .*wall clock"):
            loads_scenario(text)

    def test_enums_are_written_by_value_and_read_back_as_members(self) -> None:
        text = dumps_scenario(reference_castelldefels())
        assert "fade_combination: exact" in text
        assert as_downlink(loads_scenario(text)).channel.fade_combination is FadeCombination.EXACT

    def test_json_output_ends_with_a_newline_and_is_indented(self) -> None:
        text = dumps_scenario(reference_castelldefels(), format="json")
        assert text.endswith("}\n")
        assert '\n  "name": "reference_castelldefels"' in text


class TestEveryErrorIsAScenarioError:
    def test_invalid_yaml(self) -> None:
        with pytest.raises(ScenarioError, match="not valid YAML"):
            loads_scenario("name: [unclosed")

    def test_invalid_json(self) -> None:
        with pytest.raises(ScenarioError, match="not valid JSON"):
            loads_scenario("{", format="json")

    def test_a_document_that_is_not_a_mapping(self) -> None:
        with pytest.raises(ScenarioError, match=r"must be a mapping.*got list"):
            loads_scenario("- a\n- b\n")

    def test_unknown_format_on_load_and_dump(self) -> None:
        with pytest.raises(ScenarioError, match="unknown scenario format 'toml'"):
            loads_scenario("a: 1", format="toml")  # type: ignore[arg-type]
        with pytest.raises(ScenarioError, match="unknown scenario format 'toml'"):
            dumps_scenario(reference_castelldefels(), format="toml")  # type: ignore[arg-type]

    def test_unknown_suffix(self, tmp_path: Path) -> None:
        with pytest.raises(ScenarioError, match=r"expected a \.yaml, \.yml or \.json suffix"):
            format_for_path(tmp_path / "scenario.toml")
        with pytest.raises(ScenarioError, match="suffix"):
            dump_scenario(reference_castelldefels(), tmp_path / "scenario.txt")

    def test_a_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(ScenarioError, match="cannot read scenario file"):
            load_scenario(tmp_path / "missing.yaml")

    def test_an_unwritable_path(self, tmp_path: Path) -> None:
        with pytest.raises(ScenarioError, match="cannot write scenario file"):
            dump_scenario(reference_castelldefels(), tmp_path / "no_such_dir" / "scenario.yaml")

    def test_the_validation_error_is_chained_as_the_cause(self) -> None:
        with pytest.raises(ScenarioError) as info:
            loads_scenario("name: x")
        assert isinstance(info.value.__cause__, ValidationError)


class TestTheMessageListsEveryFailingField:
    def test_two_errors_two_dotted_paths(self) -> None:
        data = reference_dict()
        data["protocol"]["name"] = "e91"
        data["channel"]["zenith_transmittance"] = 2.0
        with pytest.raises(ScenarioError) as info:
            loads_scenario(dumps_scenario_dict(data))
        message = str(info.value)
        assert "scenario has 2 invalid fields:" in message
        assert "\n  protocol.name: no QKD protocol is registered as 'e91'" in message
        assert (
            "\n  channel.zenith_transmittance: Input should be less than or equal to 1" in message
        )

    def test_one_error_is_singular(self) -> None:
        data = reference_dict()
        data["stations"][0]["latitude_deg"] = 95.0
        with pytest.raises(
            ScenarioError, match=r"scenario has 1 invalid field:\n  stations.0.latitude_deg:"
        ):
            loads_scenario(dumps_scenario_dict(data))

    def test_a_model_level_error_names_its_model(self) -> None:
        """A rule spanning two fields is reported at the model that owns it, without the 'Value error' prefix."""
        data = reference_dict()
        data["orbit"]["kepler"]["sun_synchronous"] = False
        with pytest.raises(
            ScenarioError, match=r"\n  orbit.kepler: give exactly one of inclination_deg"
        ):
            loads_scenario(dumps_scenario_dict(data))

    def test_a_root_level_error_is_labelled_root(self) -> None:
        data = reference_dict()
        data["stations"] = [data["stations"][0], data["stations"][0]]
        with pytest.raises(ScenarioError, match=r"\n  <root>: station names must be unique"):
            loads_scenario(dumps_scenario_dict(data))


def dumps_scenario_dict(data: dict[str, Any]) -> str:
    """YAML text of an unvalidated dict, for feeding deliberately broken input."""
    return yaml.safe_dump(data, sort_keys=False)
