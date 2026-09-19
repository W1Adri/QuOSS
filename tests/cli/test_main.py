"""The parser, the exit statuses, and the console script the installer writes.

The test that matters most in this file is
``TestTheInstalledCommandRuns::test_the_console_script_runs``, and it is the one
that looks least like a test of this project's code. ``[project.scripts]`` has
named ``quoss.cli.main:main`` since stage 0, and that module did not exist until
this PR, so **installing the package left a command that raised
``ModuleNotFoundError`` on every invocation**. Nothing caught it: importing
:mod:`quoss.cli.main` from a test would have been a plain import and could not
see a wrong entry-point string, a missing ``__init__.py``, a callable that is
not callable, or a console script the installer never wrote. Only running the
installed file as a subprocess sees any of those, so that is what this does.
"""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import numpy as np
import pytest

import quoss
from quoss.cli.main import NO_COMMIT, PROG, build_parser, main, version_report
from quoss.cli.report import EXIT_ERROR, EXIT_OK, EXIT_USAGE
from quoss.scenario.result import git_commit


def _console_script() -> Path:
    """Return the installed ``quoss`` next to the interpreter running the tests."""
    found = shutil.which(PROG, path=str(Path(sys.executable).parent))
    assert found is not None, (
        f"no {PROG!r} console script next to {sys.executable}. The environment this suite "
        f"runs in must have the project installed (`uv sync`), because the entry point is "
        f"what this test exists to exercise and an import cannot see it."
    )
    return Path(found)


class TestTheInstalledCommandRuns:
    """The entry point, as a subprocess, not as an import."""

    def test_the_console_script_runs(self) -> None:
        completed = subprocess.run(
            [str(_console_script()), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout.startswith(f"{PROG} ")


class TestWhatVersionAnswers:
    """``--version`` has to answer "which tree", not only "which release".

    ``0.1.0`` covers every commit made between two tags, so a figure somebody
    copied out of a run and labelled with the version alone cannot be traced
    back to the code that produced it. These tests are about the second half of
    the answer (ADR 0030).
    """

    def test_it_names_the_release_on_the_first_line(self) -> None:
        """First line stays ``<prog> <version>``, which is what a script parses."""
        assert version_report().splitlines()[0] == f"{PROG} {quoss.__version__}"

    def test_it_names_the_commit_the_provenance_of_a_result_would_name(self) -> None:
        """The command and a result file must not disagree about the tree.

        ``Provenance`` has carried the commit since stage 4; ``--version`` did
        not until ADR 0030. Asserting them equal is what keeps the two answers
        one answer: a reader holding an exported ``result.json`` and a terminal
        must not have to decide which to believe.
        """
        commit = git_commit()
        line = version_report().splitlines()[1]
        if commit is None:  # pragma: no cover - the suite runs inside the checkout
            assert line == NO_COMMIT
        else:
            assert line.split() == ["commit", commit]

    def test_a_tree_without_a_repository_says_so_instead_of_going_quiet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An installed wheel has no ``.git``, and the report must not shrink.

        Dropping the line would make "installed from PyPI" and "this build
        failed to record its commit" produce identical output, and those are
        very different things to tell somebody who is trying to reproduce a
        number.
        """
        monkeypatch.setattr("quoss.cli.main.git_commit", lambda: None)
        report = version_report()
        assert report.splitlines()[1] == NO_COMMIT
        assert len(report.splitlines()) == 4

    def test_it_names_the_numeric_stack(self) -> None:
        """numpy and scipy move results; the report says which ones ran."""
        report = version_report()
        assert platform.python_version() in report
        assert np.__version__ in report

    def test_the_lines_are_not_rewrapped_to_the_terminal(self) -> None:
        """The reason this is a custom action and not ``action="version"``.

        ``argparse``'s own version action runs the string through the help
        formatter, which re-wraps it: four lines come out as however many the
        window allows, broken wherever the width falls. Running the flag as a
        subprocess with no terminal at all is what catches that -- calling
        :func:`version_report` directly cannot, because the re-wrapping happens
        in argparse and not in the function.
        """
        completed = subprocess.run(
            [str(_console_script()), "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert completed.stdout == version_report() + "\n"

    def test_the_console_script_reaches_a_subcommand(self, tmp_path: Path) -> None:
        """``--version`` is handled by argparse; this proves the subcommand modules import.

        A broken import inside ``run.py`` or ``sweep.py`` would leave
        ``--version`` working and every real invocation dead, because
        :func:`~quoss.cli.main.build_parser` imports them at module scope.
        """
        completed = subprocess.run(
            [str(_console_script()), "validate", "--quiet"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert completed.returncode == EXIT_OK, completed.stderr

    def test_the_declared_entry_point_is_the_one_that_exists(self, project_root: Path) -> None:
        """``pyproject.toml`` names a module and an attribute that are really there.

        A second guard on the same defect from the other side: the subprocess
        test fails if the environment is stale, this one fails if the string is
        wrong, and the failure messages differ.
        """
        with (project_root / "pyproject.toml").open("rb") as handle:
            scripts = tomllib.load(handle)["project"]["scripts"]
        module, _, attribute = scripts[PROG].partition(":")
        imported = __import__(module, fromlist=[attribute])
        assert callable(getattr(imported, attribute))


class TestTheParser:
    def test_each_subcommand_is_registered(self) -> None:
        parser = build_parser()
        for command in ("run", "sweep", "validate"):
            args = parser.parse_args(
                {
                    "run": [command, "s.yaml", "--out", "o"],
                    "sweep": [command, "s.yaml", "spec.yaml"],
                    "validate": [command],
                }[command]
            )
            assert args.execute.__module__ == f"quoss.cli.{command}"

    def test_no_subcommand_prints_the_help_and_exits_on_usage(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status = main([])
        assert status == EXIT_USAGE
        assert "COMMAND" in capsys.readouterr().err

    def test_an_unknown_subcommand_is_argparse_own_exit(self) -> None:
        with pytest.raises(SystemExit) as raised:
            main(["nope"])
        assert raised.value.code == EXIT_USAGE


class TestAQuossErrorIsAMessageAndNotATraceback:
    def test_a_missing_scenario_file_exits_three(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        status = main(["run", str(tmp_path / "absent.yaml"), "--out", str(tmp_path / "out")])
        assert status == EXIT_ERROR
        err = capsys.readouterr().err
        assert "absent.yaml" in err
        assert "Traceback" not in err

    def test_an_invalid_scenario_keeps_the_field_path_in_the_message(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        bad = tmp_path / "bad.yaml"
        bad.write_text("link: downlink\nname: x\n", encoding="utf-8")
        status = main(["run", str(bad), "--out", str(tmp_path / "out")])
        assert status == EXIT_ERROR
        assert "ScenarioError" in capsys.readouterr().err
