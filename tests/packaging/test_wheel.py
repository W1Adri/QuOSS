"""The wheel carries its data, checked from an installation and not from the tree.

What this module is for
-----------------------
Every other test in this suite runs against the *checkout*: ``uv run pytest``
puts ``src/`` on the path and the physics never notices whether the project was
installed or not. That is the right default for 3 875 tests, and it is blind to
one entire class of defect — the one where the code is fine, the tests are
green, and what ships is missing a file.

That defect was real and lived in the tree from stage 0 to 2026-09-19.
``pyproject.toml`` declares a console script, so ``pip install quoss`` is a
supported thing to do; the station catalogue and the offline snapshots lived in
``<repo>/data/`` and were found by walking three directories up from
``io/stations.py``. In a checkout that walk lands on the repository root. From
an installed wheel it lands on ``<venv>/lib/python3.13/``, one level *above*
``site-packages`` — and the file was not in the wheel anyway, so no path would
have worked. ``notes/INCONSISTENCIAS.md`` #18; ADR 0027, "Lo que esto mide".

**Why it has to install.** The failure is invisible from the source tree by
construction: in the tree the data *is* three directories up, so any assertion
written against the checkout passes both before and after the fix and proves
nothing. The only place the defect exists is an installation, so that is where
the test has to stand. This is the same argument that made the console-script
test run ``quoss`` as a subprocess rather than importing ``main``: an import
does not see a wrong entry-point string, and a checkout does not see a missing
wheel entry.

What it costs, measured
-----------------------
On this machine (Linux x86-64, CPython 3.13, warm uv cache): building the wheel
0.63 s, creating the venv and installing 0.22 s, and the three scenario runs
0.74 s (horizontal), 4.86 s (downlink) and 9.27 s (TLE) — **about 16 s in
total**, dominated entirely by the physics and not by the packaging. That is
cheap enough to run on every push in every job rather than in a job of its own,
and it is why there is no separate CI job for it.

The one thing that can make it skip is ``uv`` missing from ``PATH``, which
cannot happen under ``uv run pytest``. A skip that nobody sees is a test that
does not exist, so CI sets ``QUOSS_REQUIRE_PACKAGING_TESTS=1`` and the skip
becomes a failure there.

Checked against the defect, not only against the fix
-----------------------------------------------------
A packaging test that has only ever seen a working package is a photograph of
a working package. The defect was put back by hand — an ``exclude`` in
``[tool.hatch.build.targets.wheel]`` dropping ``quoss/data/`` from the wheel —
and **five of these eight tests failed**: the three data entries and the two
that read them from the installation.

The other three are the three scenario runs, and they **passed with the data
missing**. That is not a hole, it is the measurement that explains why the two
reader tests above have to exist: the shipped scenarios inline their stations
and their TLE, so ``quoss run`` never opens ``quoss/data/`` and cannot see the
file is gone. It is also exactly what INCONSISTENCIAS #18 reported on
2026-09-19 — "quoss run corre los tres escenarios … y sale 0", while
``load_station_catalogue()`` raised — reproduced here as a control.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

#: Horizontal, downlink and TLE — one scenario per code path through ``run``.
#: The same three INCONSISTENCIAS #18 was measured against, so the before and
#: the after are the same experiment.
SCENARIOS = ("ge1_1km", "reference_castelldefels", "tle_example")

#: Data files the wheel must carry. Named one by one: a count would pass while
#: a rename quietly swapped one file for another.
REQUIRED_WHEEL_DATA = (
    "quoss/data/ogs.yaml",
    "quoss/data/snapshots/tle/iss_zarya.json",
    "quoss/data/snapshots/cloud_cover/castelldefels_2025-01-01_02.json",
)


def _require_uv() -> str:
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - uv is how this suite is run
        message = "uv is not on PATH; the wheel cannot be built or installed"
        if os.environ.get("QUOSS_REQUIRE_PACKAGING_TESTS"):
            pytest.fail(message + " (QUOSS_REQUIRE_PACKAGING_TESTS is set)")
        pytest.skip(message)
    return uv


def _run(*argv: str | Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [str(a) for a in argv],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, (
        f"{argv[0]} exited {result.returncode}\n--- stdout ---\n{result.stdout}"
        f"\n--- stderr ---\n{result.stderr}"
    )
    return result


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build the wheel into a temporary directory and return its path.

    ``--out-dir`` is not decoration: the default is ``<repo>/dist``, and a test
    that writes into the checkout it is testing has changed the thing it is
    measuring.
    """
    uv = _require_uv()
    out = tmp_path_factory.mktemp("wheel")
    _run(uv, "build", "--wheel", "--out-dir", out, PROJECT_ROOT)
    wheels = sorted(out.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel in {out}, found {wheels}"
    return wheels[0]


@pytest.fixture(scope="session")
def installed_quoss(built_wheel: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Install the wheel into a clean venv **outside** the checkout; return its ``bin``.

    Outside is asserted rather than assumed. A venv created inside the
    repository would still have ``<repo>/data/`` three directories above
    ``site-packages`` on some layouts, and the test would go green for the
    reason it exists to rule out.
    """
    uv = _require_uv()
    venv = tmp_path_factory.mktemp("venv") / "v"
    assert PROJECT_ROOT not in venv.parents, (
        f"the venv at {venv} is inside the checkout at {PROJECT_ROOT}; this test only "
        f"means anything from outside it"
    )
    _run(uv, "venv", venv)
    env = {**os.environ, "VIRTUAL_ENV": str(venv)}
    env.pop("UV_LOCKED", None)  # the lock describes the dev env, not this install
    _run(uv, "pip", "install", built_wheel, env=env)
    bindir = venv / ("Scripts" if sys.platform == "win32" else "bin")
    assert bindir.is_dir()
    return bindir


@pytest.mark.parametrize("member", REQUIRED_WHEEL_DATA)
def test_the_wheel_carries_its_data(built_wheel: Path, member: str) -> None:
    """The catalogue and both snapshots are entries of the wheel.

    They were not, until this stage: the wheel held 90 entries, all of them
    ``quoss/**/*.py`` plus the ``dist-info``. It holds 95 now — the four files
    of ``quoss/data/`` (three data files and the ``__init__.py`` that anchors
    them) plus one directory entry — and 671 KB where it was 648 KB.
    """
    with zipfile.ZipFile(built_wheel) as archive:
        names = set(archive.namelist())
    assert member in names, (
        f"{member} is not in the wheel. Entries under quoss/data/: "
        f"{sorted(n for n in names if n.startswith('quoss/data/'))}"
    )


def test_the_installed_catalogue_resolves_inside_site_packages(installed_quoss: Path) -> None:
    """``load_station_catalogue()`` works from an installation, and reads the shipped file.

    Both halves matter. Before this stage the call raised
    ``DataError: Station catalogue not found at <venv>/lib/python3.13/data/ogs.yaml``
    — loud, which is the project's rule working, and still a promise the
    project could not keep. Asserting only "it does not raise" would also pass
    if the default path had been quietly repointed at the developer's checkout,
    which is the silent version of the same bug, so the path is asserted to
    live under ``site-packages``.
    """
    script = (
        "import json, pathlib\n"
        "from quoss.io.stations import DEFAULT_CATALOGUE_PATH, load_station_catalogue\n"
        "print(json.dumps({\n"
        "    'path': str(DEFAULT_CATALOGUE_PATH),\n"
        "    'names': [s.name for s in load_station_catalogue()],\n"
        "}))\n"
    )
    out = _run(installed_quoss / "python", "-c", script).stdout.strip().splitlines()[-1]
    import json

    payload = json.loads(out)
    assert payload["names"] == [
        "castelldefels_cttc",
        "esa_ogs_tenerife",
        "matera_mlro",
        "graz_lustbuehel",
    ]
    assert "site-packages" in payload["path"], payload["path"]
    assert str(PROJECT_ROOT) not in payload["path"], (
        f"the installed package is reading {payload['path']}, which is in the checkout. "
        f"An installation that only works next to a clone is not an installation."
    )


def test_the_installed_snapshots_load(installed_quoss: Path) -> None:
    """Both shipped snapshots parse from the installation, hash check included.

    ``load_snapshot`` verifies the payload's SHA-256 against the manifest, so
    this also rules out a wheel that carries the bytes mangled — a data file
    added to a build with the wrong newline handling is a real way to ship a
    file that exists and is wrong.
    """
    script = (
        "from quoss.core.errors import DegradationLog\n"
        "from quoss.io.snapshots import DEFAULT_SNAPSHOT_ROOT, snapshot_cloud_cover, snapshot_tle\n"
        "log = DegradationLog()\n"
        "tle = snapshot_tle('iss_zarya', degradations=log)\n"
        "cloud = snapshot_cloud_cover('castelldefels_2025-01-01_02', degradations=log)\n"
        "assert 'site-packages' in str(DEFAULT_SNAPSHOT_ROOT), DEFAULT_SNAPSHOT_ROOT\n"
        "print(tle.catalog_number, len(cloud.cloud_fraction))\n"
    )
    assert _run(installed_quoss / "python", "-c", script).stdout.split()[0] == "25544"


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_the_console_script_runs_a_scenario_from_the_installation(
    installed_quoss: Path, scenario: str, tmp_path: Path
) -> None:
    """``quoss run`` writes its directory, from the installed entry point.

    Run as a subprocess and not by importing ``main``: an ``import`` does not
    see a wrong ``[project.scripts]`` string, which is the defect this same
    pair of tests caught in stage 7.
    """
    out = tmp_path / scenario
    _run(
        installed_quoss / "quoss",
        "run",
        PROJECT_ROOT / "scenarios" / f"{scenario}.yaml",
        "--out",
        out,
    )
    assert (out / "manifest.json").is_file(), sorted(p.name for p in out.iterdir())
