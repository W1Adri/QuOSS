"""The scenario as a datum: the schema, its files, its identity, and the result shape.

Everything a run takes lives in one validated, frozen, hashable value — a
:class:`~quoss.scenario.models.Scenario` — and everything a run returns lives
in one serialisable value — a :class:`~quoss.scenario.result.SimulationResult`.
This package defines both and nothing else: no physics, no orchestration.
``notes/ROADMAP.md`` calls it "el archivo más importante del proyecto — define
el contrato", and the contract is: a user speaks degrees, nanometres and
decibels in a YAML file; the engine receives radians, metres and linear
transmittance from the conversions here; and the numbers that come back carry
the hash of the inputs, the code version and the seed that made them.

Modules
-------
models
    The Pydantic schema. Field names carry the user's unit; properties carry
    the physics unit. Two fields have no default on purpose.
defaults
    Named builders: the project's reference link, and Ntanos et al. 2021's
    three stations.
io
    YAML/JSON in and out through ``yaml.safe_load``/``safe_dump``; every
    validation failure as one ``ScenarioError`` listing every bad field.
hash
    Canonical JSON and SHA-256: the cache key and the provenance identity.
    Labels excluded, floats by ``repr``.
result
    The result schema: frozen dataclasses over arrays, with a JSON-list form
    and a manifest-plus-arrays form.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
