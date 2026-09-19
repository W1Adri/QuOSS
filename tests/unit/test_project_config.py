"""Every mypy override in ``pyproject.toml`` names something that exists.

Why a test and not just the mypy flag
--------------------------------------
``warn_unused_configs`` was ``false`` from stage 0 to 2026-09-19, with a reason
that was true when written: the per-module sections were forward-looking, so
they named packages the roadmap had not created yet and mypy would have
complained about all of them. Stages 1-8 are written now, so the excuse expired
— and the moment the flag was turned on it named **three** dead sections
(``quoss.kernels.*`` in the strict list, ``numba.*`` and ``pyarrow.*`` in the
missing-imports list), which is what an expired excuse looks like.

The flag alone does not close the row, and the reason is the tolerance rule of
``CLAUDE.md``: mypy emits this as a ``note:`` and **still exits 0**. A check
that cannot fail does not test anything, so it would report the next dead
section into a CI log nobody reads. This module is the half that fails.

What each half covers
---------------------
Deliberately not the same thing, because the two lists mean different things.
A ``quoss.*`` pattern names a package of this repository and is checkable
against the tree with certainty. A third-party pattern says "this library has
no stubs, do not complain", and whether it is needed depends on what is
installed — so asserting it against the tree would fail in an environment
without the extras, which is the config being environment-dependent rather
than wrong. What is asserted for those is the weaker, still useful thing: the
distribution is one this project declares somewhere.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = PROJECT_ROOT / "pyproject.toml"
PACKAGE = PROJECT_ROOT / "src" / "quoss"

#: Modules that arrive with a declared dependency instead of being declared
#: themselves, named one by one rather than by loosening the assertion.
#: ``erfa`` is the import name of ``pyerfa``, which ``astropy`` pulls in; the
#: golden-data generators touch it through astropy and never list it, and
#: declaring a transitive dependency to satisfy a test would be the test
#: changing the project rather than checking it.
TRANSITIVE = {"erfa"}


def _config() -> dict:
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))


def _override_modules() -> list[str]:
    overrides = _config()["tool"]["mypy"]["overrides"]
    return [module for section in overrides for module in section["module"]]


def test_warn_unused_configs_is_on() -> None:
    """Turning it back off is a decision, and this is where it has to be argued.

    It was ``false`` for seven weeks with a reason that stopped being true and
    nothing to notice that. A row in the roadmap noticed, eventually.
    """
    assert _config()["tool"]["mypy"]["warn_unused_configs"] is True, (
        "warn_unused_configs is off again. It reports dead per-module sections, which is "
        "how three of them were found on 2026-09-19. If there is a reason to turn it off, "
        "the reason goes next to it in pyproject.toml."
    )


@pytest.mark.parametrize(
    "pattern", sorted(m for m in _override_modules() if m.startswith("quoss."))
)
def test_every_quoss_mypy_override_names_a_package_that_exists(pattern: str) -> None:
    """``quoss.kernels.*`` was strictness promised to a package that is not written.

    The failure is quiet by nature: a strict setting on a module that does not
    exist is indistinguishable, from the outside, from a strict setting that is
    doing its job. Nothing goes red, and the day the package *is* written
    nobody checks whether the entry still says what they want.
    """
    relative = pattern.removeprefix("quoss.").removesuffix(".*").replace(".", "/")
    target = PACKAGE / relative
    assert target.is_dir() or target.with_suffix(".py").is_file(), (
        f"pyproject.toml has a mypy override for {pattern}, and src/quoss/{relative} does not "
        f"exist. Either the package moved, or the override is aimed at a stage that is not "
        f"written -- in which case it goes in the day the stage does, not seven weeks early."
    )


@pytest.mark.parametrize(
    "pattern", sorted(m for m in _override_modules() if not m.startswith("quoss."))
)
def test_every_third_party_mypy_override_is_a_dependency_this_project_declares(
    pattern: str,
) -> None:
    """A missing-imports override for something the project does not depend on.

    ``numba.*`` and ``pyarrow.*`` were both here on 2026-09-19 and neither is
    imported anywhere mypy looks: numba belongs to the unwritten stage 2.4, and
    pyarrow is reached only through ``importlib.import_module`` so that Parquet
    stays an extra. The distribution is checked and not the import, because
    whether a stub override is *needed* depends on what is installed, and a
    test that depends on the extras is a test that reports its environment.
    """
    project = _config()["project"]
    declared = {
        requirement.split(">=")[0].split("==")[0].split("[")[0].strip().lower()
        for requirement in (
            list(project["dependencies"])
            + [r for group in project["optional-dependencies"].values() for r in group]
            + [r for group in _config()["dependency-groups"].values() for r in group]
        )
    }
    distribution = pattern.removesuffix(".*").split(".")[0].lower()
    assert distribution in declared | TRANSITIVE, (
        f"pyproject.toml has a mypy override for {pattern}, and {distribution} is not in "
        f"[project.dependencies], any extra, or any dependency group. An override for a "
        f"library the project does not pull in cannot be doing anything."
    )


def _per_file_ignore_patterns() -> list[str]:
    return list(_config()["tool"]["ruff"]["lint"]["per-file-ignores"])


@pytest.mark.parametrize("pattern", sorted(_per_file_ignore_patterns()))
def test_every_ruff_per_file_ignore_names_something_that_exists(pattern: str) -> None:
    """The same defect as a dead mypy override, one config further out.

    ``benchmarks/**`` and ``validation/**`` sat in this table from stage 0 until
    2026-09-19, aimed at two directories that held a ``.gitkeep`` and nothing
    else. A lint exception for a directory with no code in it cannot be doing
    anything, and — this is the part that makes it worth a test — **cannot be
    told apart from one that is**. ``ruff`` says nothing about it: unlike mypy's
    ``warn_unused_configs``, there is no flag that reports an ignore that never
    fires, not even as a note. So this assertion is the only thing that can.

    The root ``validation/**`` was the worse of the two, because it read as
    covering the validation code. It did not: that lives in
    ``src/quoss/validation/`` and is matched by no entry here, so the ignore
    would have had no effect even if the directory had ever been filled — the
    exception and the code it appeared to excuse were never in the same place.

    The pattern is resolved to the part before the first glob, which is all this
    can check without reimplementing ruff's matcher, and is exactly what catches
    a top-level directory that is not there.
    """
    prefix = pattern.split("*", 1)[0].rstrip("/")
    if not prefix:  # a pattern that is glob from the first character matches anywhere
        return
    target = PROJECT_ROOT / prefix
    assert target.exists(), (
        f"pyproject.toml has a ruff per-file-ignore for {pattern!r}, and {prefix} does not "
        f"exist. Either it moved, or the exception outlived the code it excused — and ruff "
        f"will never say so, because it has no equivalent of mypy's warn_unused_configs."
    )


# --------------------------------------------------------------------------- #
# The declared floors, and the job that builds them
# --------------------------------------------------------------------------- #
WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

#: Requirements whose floor is deliberately absent, each with its reason. They
#: are asserted *floorless* as well, so the day one gets a floor this list has
#: to shrink: an exception that can only grow is one that outlives its reason.
FLOORLESS = {
    "numba": "stage 2.4 is not written (ADR 0026), so nothing imports it and no job can pin it",
    "fastapi": "stage 9 is not written (ADR 0027), so nothing imports it and no job can pin it",
    "uvicorn": "stage 9 is not written (ADR 0027), so nothing imports it and no job can pin it",
    "pydantic-settings": "stage 9 is not written (ADR 0027), so nothing imports it",
}


def _distribution(requirement: str) -> str:
    for separator in (">=", "==", "["):
        requirement = requirement.split(separator)[0]
    return requirement.strip().lower()


def _shipped_requirements() -> dict[str, str]:
    """Return ``{distribution: requirement}`` for everything an installer resolves.

    The runtime dependencies and the extras — what `pip install quoss[viz]`
    pulls in. Not `[dependency-groups]`: those are tooling, never shipped, and
    their versions are the lock's business.
    """
    project = _config()["project"]
    requirements = list(project["dependencies"])
    for group in project["optional-dependencies"].values():
        requirements.extend(group)
    return {_distribution(r): r for r in requirements}


def _minimums_pins() -> dict[str, str]:
    """Return ``{distribution: pinned version}`` from the ``minimums`` CI job.

    Parsed out of the raw text rather than through a YAML round trip: the job's
    body is a folded scalar of shell, so YAML gives back one string either way,
    and a regex over it is honest about that instead of pretending to be
    structured.
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    body = text.split("  minimums:", 1)
    assert len(body) == 2, "ci.yml has no `minimums` job; the floors would be untested again"
    return {
        _distribution(match): match.split("==")[1]
        for match in re.findall(r'--with "([^"]+==[^"]+)"', body[1])
    }


@pytest.mark.parametrize("distribution", sorted(_shipped_requirements()))
def test_every_shipped_requirement_is_either_floored_and_pinned_or_neither(
    distribution: str,
) -> None:
    """A floor nobody builds is a hope published in the wheel's metadata.

    This is the rule the round of 2026-09-19 settled, and it is two-sided on
    purpose. A requirement may declare a floor **only if** the ``minimums`` job
    pins that exact version and runs the suite against it; a requirement no job
    can pin declares no floor and says why in ``FLOORLESS``. There is no third
    state, because the third state is what was there before: ``numpy>=1.26``
    and ``scipy>=1.11``, neither of which any environment ever constructed, and
    **both of which were false** — the repository uses ``np.trapezoid`` and
    numpy 2's scalar repr, and scipy 1.11 pins ``numpy<2`` besides being yanked
    from PyPI.

    Pinning the floor and asserting the pin here are two different jobs and both
    are needed: the CI job answers "does it work", and this answers "is it the
    version we promised". Without the second, the job could drift upwards one
    dependency at a time and go on being green while the metadata went on being
    a claim about something else.
    """
    requirement = _shipped_requirements()[distribution]
    pins = _minimums_pins()
    if distribution in FLOORLESS:
        assert ">=" not in requirement, (
            f"{requirement!r} declares a floor, and {distribution} is listed in FLOORLESS as "
            f"untestable ({FLOORLESS[distribution]}). If it can be pinned now, pin it in the "
            f"minimums job and take it out of FLOORLESS in the same commit."
        )
        assert distribution not in pins, (
            f"the minimums job pins {distribution}, which FLOORLESS says nothing can pin. "
            f"One of the two is out of date."
        )
        return
    assert ">=" in requirement, (
        f"{requirement!r} declares no floor and is not in FLOORLESS. Either give it one and "
        f"pin it in the minimums job, or add it to FLOORLESS with the reason no job can."
    )
    floor = requirement.split(">=", 1)[1].strip()
    assert distribution in pins, (
        f"pyproject.toml declares {requirement!r} and the minimums job of ci.yml does not pin "
        f"{distribution}. A floor no environment builds is not a floor."
    )
    pinned = pins[distribution]
    assert pinned.startswith(floor), (
        f"pyproject.toml declares {requirement!r} and the minimums job pins "
        f"{distribution}=={pinned}. The job has to build the floor the package promises, or "
        f"the promise is about a version nothing tests."
    )


@pytest.mark.parametrize("distribution", sorted(FLOORLESS))
def test_a_requirement_declared_floorless_is_still_shipped(distribution: str) -> None:
    """FLOORLESS may not outlive the requirement it excuses.

    Same shape as ``PATHS_DECLARED_ABSENT`` in ``tests/unit/test_notes.py``: an
    allowlist that can only grow is an exception nobody can date.
    """
    assert distribution in _shipped_requirements(), (
        f"FLOORLESS names {distribution}, which pyproject.toml no longer ships. Remove the row."
    )


# --------------------------------------------------------------------------- #
# The three places that name a version name the same one
# --------------------------------------------------------------------------- #
# ``src/quoss/__init__.py`` is the single source: hatch reads ``__version__``
# from it to build the wheel, and every result carries it as provenance. But
# ``CITATION.cff`` has to repeat it, because that is the file GitHub and Zenodo
# read and neither of them runs Python -- so there are two copies of one fact,
# and a second copy is a thing that drifts.
#
# It drifts in the worst possible direction, too. The failure is not a red
# build: it is a release whose citation metadata says 0.1.0 while the code says
# 0.2.0, published to a DOI that is permanent, in a file whose entire purpose is
# to let somebody else say which version they ran. So it is asserted, and
# asserted **before** the tag rather than noticed after it.
CITATION = PROJECT_ROOT / "CITATION.cff"


def _citation() -> dict:
    """Parse ``CITATION.cff``, which is YAML with a schema on top."""
    import yaml

    with CITATION.open(encoding="utf-8") as handle:
        parsed = yaml.safe_load(handle)
    assert isinstance(parsed, dict), "CITATION.cff must parse to a mapping"
    return parsed


def test_the_citation_file_names_the_version_the_package_reports() -> None:
    import quoss

    assert _citation()["version"] == quoss.__version__, (
        f"CITATION.cff says version {_citation()['version']!r} and the package reports "
        f"{quoss.__version__!r}. src/quoss/__init__.py is the source; CITATION.cff is the "
        f"copy GitHub and Zenodo read, and a release published from a wrong copy mints a "
        f"permanent DOI against the wrong version. CHANGELOG.md, step 1."
    )


def test_the_citation_file_names_the_authors_pyproject_names() -> None:
    """Same drift, other field, and this one has no build step to catch it.

    A wrong version at least produces a wheel somebody might notice; a wrong
    author list produces a correct-looking citation with the wrong name on it.
    """
    declared = {author["name"] for author in _config()["project"]["authors"]}
    cited = {
        f"{author['given-names']} {author['family-names']}" for author in _citation()["authors"]
    }
    assert declared == cited, (
        f"pyproject.toml declares {sorted(declared)} and CITATION.cff cites {sorted(cited)}."
    )


def test_the_citation_file_declares_the_licence_the_project_declares() -> None:
    assert _citation()["license"] == _config()["project"]["license"]


def test_the_citation_file_points_at_the_repository_pyproject_points_at() -> None:
    assert _citation()["repository-code"] == _config()["project"]["urls"]["Repository"]


def test_the_changelog_has_an_entry_for_the_version_the_package_reports() -> None:
    """A release with no changelog entry is a version nobody can find out about.

    Third copy of the same fact, and it earns its place for a different reason
    than ``CITATION.cff``: that file is metadata a machine reads, this one is
    the only place that says what the version *contains* and, more to the
    point, what it does **not** affirm. A tag pushed without it publishes a
    citable object with no statement of scope attached.
    """
    import quoss

    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{quoss.__version__}]" in changelog, (
        f"CHANGELOG.md has no `## [{quoss.__version__}]` heading. CHANGELOG.md, step 2: the "
        f"entry is written before the tag, because the tag is what mints the DOI."
    )
