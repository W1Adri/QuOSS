"""Read-only data that ships **inside** the package, and the root that finds it.

What this directory is
----------------------
Two things the simulator needs that are not code and not a scenario: the
optical-ground-station catalogue (``ogs.yaml``) and the offline snapshots of
external services (``snapshots/tle/``, ``snapshots/cloud_cover/``). They are
**package data**: they live under ``src/quoss/`` and travel in the wheel, next
to the modules that read them.

Why they live here and not at the repository root
-------------------------------------------------
They used to live in ``<repo>/data/``, and ``stations.py`` and ``snapshots.py``
found them by walking three directories up from their own ``__file__``. That
works for a checkout and for ``uv run``, and it is wrong for an installed
package in a way that is worth spelling out, because the wrongness is not a
crash in the physics -- it is a promise the project had been making since
stage 0 and could not keep.

``pyproject.toml`` declares a console script, ``quoss``. Anyone can therefore
``pip install quoss`` and run it. Measured on 2026-09-19 with the wheel
installed into a clean ``.venv`` **outside** the checkout: three walks up from
``<venv>/lib/python3.13/site-packages/quoss/io/stations.py`` lands on
``<venv>/lib/python3.13/``, so the default catalogue path came out as
``<venv>/lib/python3.13/data/ogs.yaml`` -- one level *above* ``site-packages``,
a directory that belongs to the interpreter and has nothing to do with QuOSS.
``load_station_catalogue()`` raised ``DataError: Station catalogue not found``.

Loud, not silent, which is the project's rule working as intended -- and still
a broken promise, because there was no path the user could have taken to make
it work: the file was not in the wheel at all. The 90 entries of the wheel were
``quoss/**/*.py`` and the ``dist-info``, and nothing else.
(``notes/INCONSISTENCIAS.md`` #18, ADR 0027 "Lo que esto mide" defect 2.)

Moving the two data sets under ``src/quoss/`` fixes both halves at once: the
build backend ships anything inside the package directory, and the anchor
becomes one directory up from this file instead of three up from a module --
which is the same directory in a checkout and in an installation, because it is
*inside* the thing that gets copied.

The limitation that remains, stated rather than discovered
-----------------------------------------------------------
:data:`DATA_ROOT` is a real filesystem path derived from ``__file__``. That
holds for a wheel installed the ordinary way, where the package is unpacked
into ``site-packages`` as ordinary files, and it does **not** hold for a
zipimported package (``python app.pyz``), where ``__file__`` names an entry
inside an archive and no directory exists to open. QuOSS is not distributed
that way -- ADR 0027 lists the four levels and none of them zips the package --
and the two readers both take an explicit ``root`` / ``path`` argument for any
caller who needs to put the data somewhere else.

Examples
--------
>>> from quoss.data import DATA_ROOT
>>> DATA_ROOT.is_dir()
True
>>> sorted(p.name for p in DATA_ROOT.iterdir() if not p.name.startswith("_"))
['ogs.yaml', 'snapshots']
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["DATA_ROOT"]

DATA_ROOT = Path(__file__).resolve().parent
"""The directory holding ``ogs.yaml`` and ``snapshots/``, wherever the package is.

One directory, resolved once, so that the two readers agree by construction
rather than by two copies of the same expression staying in step.
"""
