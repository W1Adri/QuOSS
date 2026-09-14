"""Tests for `quoss.scenario.hash`.

- ``TestLabelsAreNotPhysics`` — same physics, different name or description,
  same digest.
- ``TestEveryPhysicalFieldMovesTheDigest`` — one field per section changed,
  digest changed; and turning an optional stage on changes it too.
- ``TestStableAcrossConstructionPaths`` — builder, YAML file, JSON text and a
  round trip all agree.
- ``TestFloatsHashByRepr`` — ``0.1 + 0.2`` is not ``0.3``; ``1`` is ``1.0``.
- ``TestCanonicalForm`` — sorted keys, no whitespace, ASCII, the ``Z`` epoch.
- ``TestThePinnedReferenceDigest`` — a V4-style guard on the serialisation
  contract (not on physics), and the test says why that is the right tool.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import HASH_EXCLUDED_FIELDS, canonical_json, scenario_hash
from quoss.scenario.io import dumps_scenario, load_scenario, loads_scenario
from quoss.scenario.models import Scenario

REFERENCE_DIGEST = "feafee61257b303a9fdb838e66a981ea4c58c8fad94ec5dfeba7841d53a84227"
"""SHA-256 of ``canonical_json(reference_castelldefels())`` on 2026-09-13.

If this changes, the canonical form changed: every cached result keyed on the
old digest is unreachable and every provenance record stops matching its
scenario. That is allowed only with a ``SCHEMA_VERSION`` bump and a note.
"""


def reference_dict() -> dict[str, Any]:
    return reference_castelldefels().model_dump(mode="json")


def rebuilt(path: str, value: Any) -> Scenario:
    """Return the reference scenario with one dotted path replaced."""
    data = reference_dict()
    node: Any = data
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if part.isdigit() else node[part]
    node[parts[-1]] = value
    return Scenario.model_validate(data)


class TestLabelsAreNotPhysics:
    def test_name_and_description_do_not_enter_the_digest(self) -> None:
        base = reference_castelldefels()
        renamed = base.model_copy(update={"name": "something else", "description": "and more"})
        assert renamed != base
        assert scenario_hash(renamed) == scenario_hash(base)
        assert HASH_EXCLUDED_FIELDS == {"name", "description"}

    def test_the_label_text_is_absent_from_the_canonical_form(self) -> None:
        text = canonical_json(reference_castelldefels())
        assert "reference_castelldefels" not in text
        assert "QuOSS reference downlink" not in text


class TestEveryPhysicalFieldMovesTheDigest:
    @pytest.mark.parametrize(
        ("path", "value"),
        [
            ("orbit.kepler.altitude_km", 701.0),
            ("orbit.kepler.raan_deg", 31.0),
            ("stations.0.latitude_deg", 41.0),
            ("stations.0.receive_aperture_m", 1.3),
            ("transmitter.wavelength_nm", 1551.0),
            ("transmitter.pointing_jitter_urad", 1.0),
            ("channel.zenith_transmittance", 0.9),
            ("channel.fade_combination", "additive"),
            ("receiver.gate_ns", 2.0),
            ("receiver.detector_count", 1),
            ("background.sky_radiance_w_m2_um_sr", 1.5e-5),
            ("protocol.signal_intensity", 0.5),
            ("protocol.key_basis_probability", 0.9),
            ("security.correctness", 1e-9),
            ("security.compose_daily", False),
            ("time.epoch_utc", "2025-01-02T00:00:00Z"),
            ("time.step_s", 2.0),
            ("passes.minimum_elevation_deg", 8.0),
            ("passes.minimum_duration_s", 60.0),
        ],
    )
    def test_one_field(self, path: str, value: Any) -> None:
        assert scenario_hash(rebuilt(path, value)) != scenario_hash(reference_castelldefels())

    def test_turning_an_optional_stage_on_changes_the_digest(self) -> None:
        """200 realisations is a different computation from none; the cache must not conflate them."""
        with_mc = rebuilt(
            "monte_carlo",
            {
                "realisations": 200,
                "scintillation_correlation_time_s": 0.01,
                "pointing_correlation_time_s": 0.1,
            },
        )
        assert scenario_hash(with_mc) != scenario_hash(reference_castelldefels())
        assert scenario_hash(
            rebuilt(
                "monte_carlo",
                {**with_mc.model_dump(mode="json")["monte_carlo"], "realisations": 2000},
            )
        ) != scenario_hash(with_mc)


class TestStableAcrossConstructionPaths:
    def test_builder_file_json_and_round_trip_agree(self, scenarios_dir: Path) -> None:
        built = reference_castelldefels()
        from_file = load_scenario(scenarios_dir / "reference_castelldefels.yaml")
        from_json = loads_scenario(dumps_scenario(built, format="json"), format="json")
        from_yaml = loads_scenario(dumps_scenario(built))
        digests = {scenario_hash(s) for s in (built, from_file, from_json, from_yaml)}
        assert digests == {REFERENCE_DIGEST}

    def test_key_order_in_the_source_does_not_matter(self) -> None:
        data = reference_dict()
        shuffled = dict(reversed(list(data.items())))
        shuffled["receiver"] = dict(reversed(list(data["receiver"].items())))
        assert scenario_hash(Scenario.model_validate(shuffled)) == REFERENCE_DIGEST


class TestFloatsHashByRepr:
    def test_a_rounding_error_is_a_different_scenario(self) -> None:
        """``0.1 + 0.2`` and ``0.3`` are different doubles and must not share a cache entry."""
        a = rebuilt("channel.zenith_transmittance", 0.1 + 0.2)
        b = rebuilt("channel.zenith_transmittance", 0.3)
        assert scenario_hash(a) != scenario_hash(b)
        assert '"zenith_transmittance":0.30000000000000004' in canonical_json(a)
        assert '"zenith_transmittance":0.3' in canonical_json(b)

    def test_an_integer_spelling_of_a_float_field_is_the_same_scenario(self) -> None:
        """YAML ``1`` and ``1.0`` coerce to the same double before anything is dumped."""
        text = dumps_scenario(reference_castelldefels())
        assert "zenith_transmittance: 1.0" in text
        as_int = loads_scenario(
            text.replace("zenith_transmittance: 1.0", "zenith_transmittance: 1")
        )
        assert as_int.channel.zenith_transmittance == 1.0
        assert isinstance(as_int.channel.zenith_transmittance, float)
        assert scenario_hash(as_int) == REFERENCE_DIGEST


class TestCanonicalForm:
    def test_sorted_keys_no_whitespace_ascii(self) -> None:
        text = canonical_json(reference_castelldefels())
        assert text == json.dumps(json.loads(text), sort_keys=True, separators=(",", ":"))
        assert " " not in text.replace('"bb84-decoy"', "")
        assert text.isascii()
        top = list(json.loads(text))
        assert top == sorted(top)
        assert top[0] == "background" and "name" not in top

    def test_the_epoch_is_iso_8601_utc_with_z(self) -> None:
        assert '"epoch_utc":"2025-01-01T00:00:00Z"' in canonical_json(reference_castelldefels())

    def test_enums_serialise_by_value(self) -> None:
        assert '"fade_combination":"exact"' in canonical_json(reference_castelldefels())

    def test_deterministic(self) -> None:
        assert canonical_json(reference_castelldefels()) == canonical_json(
            reference_castelldefels()
        )

    def test_the_digest_is_sha256_hex(self) -> None:
        digest = scenario_hash(reference_castelldefels())
        assert len(digest) == 64
        assert int(digest, 16) >= 0


class TestThePinnedReferenceDigest:
    def test_the_reference_digest_is_pinned(self) -> None:
        """V4-style, on purpose.

        ``tests/golden/README.md`` says a snapshot of our own output proves
        nothing about physics, and this one does not try to: it guards the
        *serialisation contract*. A renamed field, an enum written by name, a
        datetime in another format — each would silently invalidate every
        cached result and every provenance record without a single physics
        test noticing. This is the test that notices, and its failure message
        is an instruction to bump ``SCHEMA_VERSION``.
        """
        assert scenario_hash(reference_castelldefels()) == REFERENCE_DIGEST
