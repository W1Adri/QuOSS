"""The outside world, kept at arm's length: HTTP cache, data clients, snapshots, export.

Everything in this package touches something the physics must never depend on:
a network socket, a file on disk written by somebody else, a third-party
serialisation library. That is the reason the package exists as a separate unit
and the reason it arrives late in the roadmap (``notes/ROADMAP.md`` stage 6):
every module in ``core``, ``orbits``, ``channel``, ``qkd``, ``system`` and
``engine`` was written and verified with synthetic data or with files under
``data/``, and none of them imports ``quoss.io``. The dependency arrow points
one way only — ``io`` may import the layers below it, and results reach the
physics by *injection* (a TLE record handed to a scenario, a cloud series
handed to ``system/pcflos.py``), never by a physics function reaching out.

Two consequences follow, and both are tested rather than promised:

* **The test suite never opens a socket.** Every function that would fetch
  takes a ``fetch`` callable; the tests hand in a fake, and one test
  (``tests/io/test_cache.py::TestTheSuiteIsOffline``) breaks ``socket.socket``
  outright and shows that every code path in this package still runs.
* **A demo does not depend on wifi.** ``snapshots.py`` stores versioned copies
  of what CelesTrak and Open-Meteo answered on a stated date, with the hash of
  the payload in a manifest, so a run can say *which* TLE and *which* cloud
  series it used — and a snapshot that was never fetched says so in its
  manifest instead of pretending.

Modules
-------
cache
    On-disk HTTP cache keyed by the sha256 of the URL, with a TTL and an
    explicit, opt-in stale fallback.
celestrak
    A TLE from the CelesTrak GP API, validated through ``orbits.tle.parse_tle``
    before it is returned.
openmeteo
    Hourly total cloud cover from the Open-Meteo historical archive (ERA5
    family), as a ``TimeGrid`` plus a fraction in ``[0, 1]``.
snapshots
    Versioned offline copies of the above, content-addressed and verified on
    load.
export
    A ``SimulationResult`` written to a self-describing directory: manifest,
    CSV tables, ``.npz`` arrays, optional Parquet.
stations
    The optical-ground-station catalogue in ``data/ogs.yaml``, every entry with
    the source of its coordinates.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
