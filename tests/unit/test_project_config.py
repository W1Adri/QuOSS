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
