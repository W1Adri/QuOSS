"""``quoss sweep``: the same rows ``run_sweep`` returns, and a spec that is a file."""

from __future__ import annotations

import csv
import inspect
import json
from pathlib import Path

import pytest

from quoss.cli.main import main
from quoss.cli.report import EXIT_ERROR, EXIT_OK
from quoss.cli.sweep import DEFAULT_METRICS, load_sweep_spec
from quoss.core.errors import DegradationLog, ScenarioError
from quoss.engine.sweep import run_sweep
from quoss.scenario.io import load_scenario


class TestTheCliAddsNothingToASweep:
    def test_the_printed_table_equals_run_sweep(
        self,
        horizontal_file: Path,
        sweep_spec_file: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        status = main(["sweep", str(horizontal_file), str(sweep_spec_file)])
        assert status == EXIT_OK
        rows = list(csv.DictReader(capsys.readouterr().out.splitlines()))

        spec, metrics = load_sweep_spec(sweep_spec_file)
        by_hand = run_sweep(
            load_scenario(horizontal_file), spec, metrics=metrics, degradations=DegradationLog()
        ).to_records()

        assert len(rows) == len(by_hand)
        for row, record in zip(rows, by_hand, strict=True):
            assert set(row) == set(record)
            for key, value in record.items():
                assert row[key] == str(value)

    def test_the_default_metric_is_the_engine_own(self) -> None:
        """Spelled in two places, so it is asserted that they agree.

        A CLI quietly supplying a different default would make
        ``quoss sweep spec-without-metrics`` and ``run_sweep(...)`` measure
        different things under the same name.
        """
        engine_default = inspect.signature(run_sweep).parameters["metrics"].default
        assert tuple(engine_default) == DEFAULT_METRICS

    def test_the_written_csv_is_the_printed_one(
        self,
        horizontal_file: Path,
        sweep_spec_file: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        main(["sweep", str(horizontal_file), str(sweep_spec_file), "--out", str(tmp_path / "s")])
        printed = capsys.readouterr().out
        assert (tmp_path / "s" / "sweep.csv").read_text(encoding="utf-8") == printed

    def test_the_written_json_carries_the_base_hash_and_the_spec(
        self, horizontal_file: Path, sweep_spec_file: Path, tmp_path: Path
    ) -> None:
        main(["sweep", str(horizontal_file), str(sweep_spec_file), "--out", str(tmp_path / "s")])
        document = json.loads((tmp_path / "s" / "sweep.json").read_text(encoding="utf-8"))
        spec, metrics = load_sweep_spec(sweep_spec_file)
        assert document["metrics"] == list(metrics)
        assert document["spec"]["mode"] == spec.mode
        assert set(document["spec"]["parameters"]) == set(spec.parameters)
        assert all("scenario_hash" in row for row in document["records"])


class TestTheSpecFileIsRefusedLoudly:
    def test_an_unknown_key_names_the_three_that_exist(self, tmp_path: Path) -> None:
        """A ``parameter:`` typo must not surface as "a sweep needs at least one parameter"."""
        path = tmp_path / "typo.yaml"
        path.write_text("parameter:\n  a.b: [1]\n", encoding="utf-8")
        with pytest.raises(ScenarioError, match="unknown keys"):
            load_sweep_spec(path)

    def test_a_wrong_suffix_is_refused_before_reading(self, tmp_path: Path) -> None:
        path = tmp_path / "spec.txt"
        path.write_text("parameters:\n  a.b: [1]\n", encoding="utf-8")
        with pytest.raises(ScenarioError, match="suffix"):
            load_sweep_spec(path)

    def test_a_missing_file_is_a_scenario_error_and_not_an_oserror(self, tmp_path: Path) -> None:
        with pytest.raises(ScenarioError, match="cannot read sweep spec"):
            load_sweep_spec(tmp_path / "absent.yaml")

    def test_unparseable_yaml_is_a_scenario_error_naming_the_file(self, tmp_path: Path) -> None:
        """A parser message about a colon, on its own, does not say which file."""
        path = tmp_path / "broken.yaml"
        path.write_text("parameters:\n  a.b: [1\n  bad: : :\n", encoding="utf-8")
        with pytest.raises(ScenarioError, match="is not valid YAML/JSON"):
            load_sweep_spec(path)

    @pytest.mark.parametrize(
        ("body", "match"),
        [
            ("- a\n- b\n", "must be a mapping"),
            ("mode: grid\n", "no 'parameters' key"),
            ("parameters: 3\n", "must be a mapping of dotted path"),
            ("parameters:\n  a.b: [1]\nmetrics: 5\n", "list of strings"),
        ],
    )
    def test_each_malformed_spec_says_what_is_wrong(
        self, tmp_path: Path, body: str, match: str
    ) -> None:
        path = tmp_path / "spec.yaml"
        path.write_text(body, encoding="utf-8")
        with pytest.raises(ScenarioError, match=match):
            load_sweep_spec(path)

    def test_a_metric_of_the_other_geometry_fails_before_the_first_point(
        self, horizontal_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = tmp_path / "spec.yaml"
        path.write_text(
            "parameters:\n  path.path_length_m: [200.0, 1000.0]\nmetrics: [daily.finite_bits]\n",
            encoding="utf-8",
        )
        status = main(["sweep", str(horizontal_file), str(path)])
        assert status == EXIT_ERROR
        err = capsys.readouterr().err
        assert "budget" in err and "session" in err


class TestTheCommittedSpec:
    def test_it_loads_and_names_horizontal_metrics(self, sweep_spec_file: Path) -> None:
        _, metrics = load_sweep_spec(sweep_spec_file)
        assert all(m.split(".")[0] in ("budget", "session") for m in metrics)

    def test_five_kilometres_certifies_nothing_while_the_asymptotic_does_not(
        self, horizontal_file: Path, sweep_spec_file: Path
    ) -> None:
        """The finding of LAST_CHANGES §40, reproduced through the CLI's own path.

        The point of the committed spec asking for both metrics is that the two
        columns disagree at the last row: a sizing done on the asymptotic figure
        would call 5 km a working link.
        """
        spec, metrics = load_sweep_spec(sweep_spec_file)
        records = run_sweep(
            load_scenario(horizontal_file), spec, metrics=metrics, degradations=DegradationLog()
        ).to_records()
        last = records[-1]
        assert last["path.path_length_m"] == 5000.0
        assert last["session.finite_bits"] == 0.0
        assert last["session.asymptotic_bits"] > 0.0
