"""``quoss run``: the same result as calling ``run()`` by hand, in a directory.

The central assertion of this file is the one ADR 0016 makes about the engine,
one layer up: **the CLI adds nothing.** What it writes must rebuild into a
result equal, term by term, to :func:`quoss.engine.pipeline.run` called by hand
on the same file -- for both geometries, and without the test having to know
which geometry it is looking at.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from quoss.cli.main import main
from quoss.cli.report import EXIT_OK, EXIT_UNDECLARED_DEGRADATION
from quoss.core.errors import DegradationLog
from quoss.engine.pipeline import run as run_scenario
from quoss.scenario.io import load_scenario
from quoss.scenario.result import AnyResult, HorizontalResult, SimulationResult

#: Excluded from the comparison, and named rather than waved at. Both are
#: wall-clock readings: ``created_utc`` is the second the run started and
#: ``timings`` is how long each stage took. Two runs of the same scenario differ
#: in them by construction, so asserting on them would test the clock. Nothing
#: else is excluded -- every physical number, every warning, the hash and the
#: whole scenario are compared.
UNCOMPARABLE = ("provenance.created_utc", "timings")


def _rebuild(directory: Path) -> AnyResult:
    """Rebuild whatever result a directory holds, from ``result.json`` alone."""
    document = json.loads((directory / "result.json").read_text(encoding="utf-8"))
    manifest = document["manifest"]
    shape = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["export"]["shape"]
    if shape == "horizontal":
        assert document["arrays"] == {}
        return HorizontalResult.from_dict(manifest)
    arrays = {k: np.asarray(v["data"], dtype=v["dtype"]) for k, v in document["arrays"].items()}
    return SimulationResult.from_manifest_and_arrays(manifest, arrays)


def _comparable(result: AnyResult) -> dict[str, object]:
    """Return the result as a dict with the two wall-clock fields removed."""
    tree = result.to_dict()
    tree["provenance"] = {k: v for k, v in tree["provenance"].items() if k != "created_utc"}
    del tree["timings"]
    return tree


class TestTheCliAddsNothing:
    """What ``quoss run`` writes equals what ``run()`` returns, term by term."""

    @pytest.mark.parametrize("fixture", ["downlink_file", "horizontal_file"])
    def test_the_written_result_equals_the_hand_call(
        self, fixture: str, request: pytest.FixtureRequest, tmp_path: Path
    ) -> None:
        path: Path = request.getfixturevalue(fixture)
        out = tmp_path / fixture

        status = main(["run", str(path), "--out", str(out)])

        assert status == EXIT_OK
        by_hand = run_scenario(load_scenario(path), degradations=DegradationLog())
        assert _comparable(_rebuild(out)) == _comparable(by_hand)

    @pytest.mark.parametrize("fixture", ["downlink_file", "horizontal_file"])
    def test_the_rebuilt_result_is_the_same_class(
        self, fixture: str, request: pytest.FixtureRequest, tmp_path: Path
    ) -> None:
        """The directory reconstructs the *result*, not a look-alike dictionary.

        Equality of ``to_dict()`` would pass for two different containers holding
        the same numbers, and the whole point of ADR 0024's two containers is
        that a horizontal run must not come back as a downlink one with holes.
        """
        path: Path = request.getfixturevalue(fixture)
        out = tmp_path / fixture
        main(["run", str(path), "--out", str(out)])

        by_hand = run_scenario(load_scenario(path), degradations=DegradationLog())
        assert type(_rebuild(out)) is type(by_hand)

    def test_the_hash_written_is_the_hash_of_the_inputs(
        self, horizontal_file: Path, tmp_path: Path
    ) -> None:
        main(["run", str(horizontal_file), "--out", str(tmp_path / "out")])
        document = json.loads((tmp_path / "out" / "manifest.json").read_text(encoding="utf-8"))
        by_hand = run_scenario(load_scenario(horizontal_file), degradations=DegradationLog())
        assert document["result"]["provenance"]["scenario_hash"] == by_hand.provenance.scenario_hash


class TestTheShapeFollowsTheResultAndNotAFlag:
    """No ``--horizontal``: the file's ``link`` decides, end to end."""

    def test_a_horizontal_file_writes_the_horizontal_shape(
        self, horizontal_file: Path, tmp_path: Path
    ) -> None:
        main(["run", str(horizontal_file), "--out", str(tmp_path / "out")])
        written = {p.name for p in (tmp_path / "out").iterdir()}
        assert written == {
            "manifest.json",
            "README.txt",
            "result.json",
            "budget.csv",
            "session.csv",
        }

    def test_a_downlink_file_writes_the_downlink_shape(
        self, downlink_file: Path, tmp_path: Path
    ) -> None:
        main(["run", str(downlink_file), "--out", str(tmp_path / "out")])
        written = {p.name for p in (tmp_path / "out").iterdir()}
        assert {"passes.csv", "daily.csv", "arrays.npz"} <= written
        assert not any(name in written for name in ("budget.csv", "session.csv"))

    def test_the_two_shapes_share_no_data_file_name(
        self, downlink_file: Path, horizontal_file: Path, tmp_path: Path
    ) -> None:
        """Beyond the two self-describing files, the two directories cannot be confused.

        ``manifest.json``, ``README.txt`` and ``result.json`` are the envelope and
        exist in both. Everything else is disjoint, which is what makes "an
        absent ``passes.csv``" unambiguous rather than a reading the consumer has
        to guess at.
        """
        main(["run", str(downlink_file), "--out", str(tmp_path / "down")])
        main(["run", str(horizontal_file), "--out", str(tmp_path / "horiz")])
        envelope = {"manifest.json", "README.txt", "result.json"}
        down = {p.name for p in (tmp_path / "down").iterdir()} - envelope
        horiz = {p.name for p in (tmp_path / "horiz").iterdir()} - envelope
        assert down & horiz == set()


class TestTheWarningsAreNotSummarised:
    """Every field of every entry reaches the reader."""

    def test_every_recorded_entry_is_printed_whole(
        self, horizontal_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        main(["run", str(horizontal_file), "--out", str(tmp_path / "out")])
        err = capsys.readouterr().err

        by_hand = run_scenario(load_scenario(horizontal_file), degradations=DegradationLog())
        assert by_hand.warnings, "the fixture must record something for this to test anything"
        for entry in by_hand.warnings:
            assert str(entry["code"]) in err
            assert str(entry["where"]) in err
            assert str(entry["message"]) in err

    def test_the_export_entries_are_printed_too(
        self, horizontal_file: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``io.export-no-arrays`` is recorded after the result exists, so the result cannot carry it.

        Printing ``result.warnings`` instead of the log would drop exactly the
        line that explains why the directory has no ``arrays.npz``.
        """
        main(["run", str(horizontal_file), "--out", str(tmp_path / "out"), "--format", "npz"])
        assert "io.export-no-arrays" in capsys.readouterr().err


class TestTheExitStatusIsAboutUndeclaredSubstitutions:
    """A DEGRADED the file did not list fails; one it listed does not."""

    def test_an_undeclared_degradation_exits_non_zero(
        self, undeclared_degradation_file: Path, tmp_path: Path
    ) -> None:
        status = main(["run", str(undeclared_degradation_file), "--out", str(tmp_path / "out")])
        assert status == EXIT_UNDECLARED_DEGRADATION

    def test_the_files_are_still_written(
        self, undeclared_degradation_file: Path, tmp_path: Path
    ) -> None:
        """Non-zero is "not what you asked for", not "nothing happened".

        A run that substituted a model still computed something, and a reader who
        has to inspect the substitution needs the numbers it produced.
        """
        main(["run", str(undeclared_degradation_file), "--out", str(tmp_path / "out")])
        assert (tmp_path / "out" / "result.json").exists()

    def test_declaring_the_code_makes_it_zero(
        self, declared_degradation_file: Path, tmp_path: Path
    ) -> None:
        status = main(["run", str(declared_degradation_file), "--out", str(tmp_path / "out")])
        assert status == EXIT_OK

    def test_declaring_it_changes_nothing_the_run_computes(
        self,
        declared_degradation_file: Path,
        undeclared_degradation_file: Path,
        tmp_path: Path,
    ) -> None:
        """The field is about acceptance, which is why it is out of the hash.

        The two scenarios differ only in ``expected_degradations``, so every
        number, the warning list and the scenario hash must be identical; only
        the exit status differs.
        """
        declared = run_scenario(
            load_scenario(declared_degradation_file), degradations=DegradationLog()
        )
        undeclared = run_scenario(
            load_scenario(undeclared_degradation_file), degradations=DegradationLog()
        )
        assert isinstance(declared, HorizontalResult)
        assert isinstance(undeclared, HorizontalResult)
        assert declared.provenance.scenario_hash == undeclared.provenance.scenario_hash
        assert declared.budget == undeclared.budget
        assert declared.session == undeclared.session
        assert list(declared.warnings) == list(undeclared.warnings)
