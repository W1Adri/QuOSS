"""``quoss dossier``: the same text the generator produces, written where it was asked.

The CLI computes nothing, one layer further out
------------------------------------------------
`tests/cli/test_run.py` asserts that the `result.json` `quoss run` writes
rebuilds into a result equal term by term to `engine.pipeline.run` called by
hand. This file makes the same assertion about the dossier: the bytes this
subcommand writes are the bytes `quoss.dossier.base.render` produces, character
for character, so that the committed documents and the ones a user writes to
their own path cannot come from two different code paths.

That matters more here than it looks. `tests/dossier/test_docs.py` guards the
committed files against the *generator*; if the CLI reformatted, re-wrapped or
appended anything of its own, the file a user produced would differ from the
one CI checks, and the difference would only show up in the document somebody
carried into a meeting.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from quoss.cli.main import main
from quoss.cli.report import EXIT_ERROR, EXIT_OK
from quoss.dossier.base import dossier_for, dossiers, regenerate_command, render
from quoss.scenario.io import dump_scenario, load_scenario


@pytest.fixture(scope="module")
def ge1_path(project_root: Path) -> Path:
    return project_root / "scenarios" / "ge1_1km.yaml"


class TestTheSubcommandWritesWhatTheGeneratorProduces:
    def test_the_file_is_the_rendered_text_byte_for_byte(
        self, ge1_path: Path, tmp_path: Path
    ) -> None:
        target = tmp_path / "nested" / "GE-1.md"
        assert main(["dossier", str(ge1_path), "--out", str(target)]) == EXIT_OK
        scenario = load_scenario(ge1_path)
        expected = render(dossier_for(scenario), scenario).text
        assert target.read_text(encoding="utf-8") == expected

    def test_a_dash_sends_it_to_standard_output(
        self, ge1_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert main(["dossier", str(ge1_path), "--out", "-"]) == EXIT_OK
        scenario = load_scenario(ge1_path)
        assert capsys.readouterr().out == render(dossier_for(scenario), scenario).text

    def test_the_header_quotes_a_command_that_runs(
        self, ge1_path: Path, tmp_path: Path, project_root: Path
    ) -> None:
        """The regeneration command in each document has to be the real one.

        A generated file naming a command nobody can run is a worse instruction
        than none: a reader who tries it and gets a usage error has to guess
        whether the file is stale, wrong or fine. So the command is parsed back
        out of the header and executed, with `--out` redirected so the
        committed file is not touched.
        """
        spec = dossier_for(load_scenario(ge1_path))
        quoted = regenerate_command(spec)
        assert quoted.startswith("uv run quoss dossier ")
        argv = quoted.split()[3:]  # drop "uv run quoss"
        assert argv[0] == "dossier"
        target = tmp_path / "out.md"
        argv = [*argv[:-1], str(target)]
        argv[1] = str(project_root / argv[1])
        assert main(argv) == EXIT_OK
        assert target.is_file()

    def test_it_prints_the_warnings_whole_on_standard_error(
        self, ge1_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The rule of `quoss.cli.report` applies here as to every other subcommand.

        A dossier's runs record real substitutions -- the 5 km sweep point logs
        `horizontal.weak-fluctuation-limit-exceeded` -- and the person running
        the command is the one who can still do something about them.
        """
        main(["dossier", str(ge1_path), "--out", str(tmp_path / "x.md")])
        err = capsys.readouterr().err
        assert "warnings:" in err
        assert "horizontal.weak-fluctuation-limit-exceeded" in err


class TestWhatItRefuses:
    def test_a_scenario_with_no_registered_dossier_is_an_error_and_not_a_stub(
        self, tmp_path: Path, project_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """No generic fallback: an error that lists the registered scenarios.

        A confident-looking document generated for a scenario nobody wrote
        sections for would carry whichever figures a generic path could reach
        and be silent about everything it could not, and its omissions would be
        invisible to exactly the reader who cannot check them.
        """
        scenario = load_scenario(project_root / "scenarios" / "ge1_1km.yaml")
        renamed = scenario.model_copy(update={"name": "ge1_but_edited"})
        path = tmp_path / "renamed.yaml"
        dump_scenario(renamed, path)
        assert main(["dossier", str(path), "--out", str(tmp_path / "out.md")]) == EXIT_ERROR
        err = capsys.readouterr().err
        assert "no dossier is registered" in err
        for spec in dossiers():
            assert spec.scenario_name in err

    def test_out_is_required_so_that_looking_cannot_overwrite(self, ge1_path: Path) -> None:
        """`--out` has no default, and the default it does not have is the committed path.

        Defaulting it would make `quoss dossier scenarios/ge1_1km.yaml` rewrite
        a tracked document as the side effect of a command somebody ran to look
        at the output.
        """
        with pytest.raises(SystemExit) as exit_info:
            main(["dossier", str(ge1_path)])
        assert exit_info.value.code == 2


class TestItIsRegisteredOnTheParser:
    def test_the_subcommand_exists_and_dispatches_to_its_module(self) -> None:
        from quoss.cli.main import build_parser

        args = build_parser().parse_args(["dossier", "s.yaml", "--out", "o.md"])
        assert args.execute.__module__ == "quoss.cli.dossier"

    def test_the_help_names_every_registered_scenario(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A reader who does not know which scenarios have a dossier can ask the tool.

        The alternative is reading the registry, and the person most likely to
        need the answer is the one least likely to be reading source.
        """
        with pytest.raises(SystemExit):
            main(["dossier", "--help"])
        out = capsys.readouterr().out
        for spec in dossiers():
            assert spec.scenario_path in out
            assert spec.document_path in out
