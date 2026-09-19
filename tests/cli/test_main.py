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

import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from quoss.cli.main import PROG, build_parser, main
from quoss.cli.report import EXIT_ERROR, EXIT_OK, EXIT_USAGE


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
