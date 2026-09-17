"""The scenario's identity: a canonical JSON form and its SHA-256.

What the hash is for
--------------------
Two consumers need to answer "is this the same simulation?" without running
it: the result cache (``engine/cache.py`` keys on it) and the provenance record
(:class:`quoss.scenario.result.Provenance` carries it, so a figure can be traced
to the exact inputs that produced it). Both need a function of the scenario's
*content* that does not depend on how the scenario was written down — key
order in a YAML file, ``1`` versus ``1.0``, whether the file went through JSON
first. That is what "canonical" means here: one byte string per physics.

What goes in, and what is left out
----------------------------------
``name`` and ``description`` are **excluded**. They are labels for humans; two
scenarios that differ only in them describe the same run and must share a
cache entry, otherwise renaming a file would re-run a day of Monte Carlo.
Everything else is included, options too: a scenario with 200 realisations is
a different computation from one with 2000, and ``schema_version`` is
included because the same numbers under a different schema mean different
things.

Why floats hash by ``repr``
---------------------------
``json.dumps`` writes a float with ``float.__repr__``, the shortest decimal
that round-trips to the same double. That makes the canonical form a faithful
image of the value in memory, with two consequences worth stating:

* ``0.1 + 0.2`` is ``0.30000000000000004`` and ``0.3`` is ``0.3``. They are
  different doubles, so they are different scenarios and hash differently.
  Rounding to "reasonable" digits before hashing would make two runs that
  produce different numbers share a cache entry — the wrong direction to err.
* ``1`` and ``1.0`` hash the **same**, because the schema coerces an integer
  written into a float field to ``1.0`` before anything is dumped. The YAML
  author's spelling is not part of the physics.

Both are tests (``tests/scenario/test_hash.py::TestFloatsHashByRepr``).

Why one value of the reference hash is pinned
---------------------------------------------
``tests/scenario/test_hash.py`` pins the hex digest of
:func:`~quoss.scenario.defaults.reference_castelldefels`. That is a V4-style
guard (``tests/golden/README.md``: a snapshot of our own output, proving
nothing about physics) and it is the right tool *here*, because what it guards
is a serialisation contract, not a model: if the canonical form changes — a
field renamed, an enum serialised by name instead of value, a datetime format
— every cached result silently becomes unreachable and every provenance record
stops matching its scenario. A pinned digest turns that into a failing test
with a diff, and the fix is a deliberate schema-version bump.

Examples
--------
>>> from quoss.scenario.defaults import reference_castelldefels
>>> scenario = reference_castelldefels()
>>> canonical_json(scenario)[:40]
'{"background":{"condition":null,"sky_rad'
>>> len(scenario_hash(scenario))
64
>>> scenario_hash(scenario.model_copy(update={"name": "renamed"})) == scenario_hash(scenario)
True
"""

from __future__ import annotations

import hashlib
import json

from quoss.scenario.models import AnyScenario

__all__ = ["HASH_EXCLUDED_FIELDS", "canonical_json", "scenario_hash"]

HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset({"name", "description"})
"""Top-level fields that are labels, not physics, and stay out of the digest."""


def canonical_json(scenario: AnyScenario) -> str:
    """Return the one JSON text that represents this scenario's physics.

    Keys sorted at every level, no whitespace, ASCII only, floats by ``repr``,
    enums by value, the epoch as ISO-8601 UTC with ``Z``, and the label fields
    of :data:`HASH_EXCLUDED_FIELDS` removed. ``allow_nan=False`` is belt and
    braces: the schema already refuses non-finite values, and a NaN that
    somehow got here would otherwise serialise as a token that is not JSON.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        A validated scenario of either geometry.

    Returns
    -------
    str
        The canonical text.

    Examples
    --------
    >>> from quoss.scenario.defaults import reference_castelldefels
    >>> text = canonical_json(reference_castelldefels())
    >>> '"epoch_utc":"2025-01-01T00:00:00Z"' in text
    True
    >>> text.startswith('{"background":')
    True
    >>> "reference_castelldefels" in text
    False
    """
    payload = scenario.physics_dict()
    return json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    )


def scenario_hash(scenario: AnyScenario) -> str:
    """Return the SHA-256 hex digest of :func:`canonical_json`.

    Parameters
    ----------
    scenario : Scenario or HorizontalScenario
        A validated scenario of either geometry.

    Returns
    -------
    str
        64 lowercase hexadecimal characters.
    """
    return hashlib.sha256(canonical_json(scenario).encode("ascii")).hexdigest()
