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

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from quoss.scenario.defaults import reference_castelldefels
from quoss.scenario.hash import HASH_EXCLUDED_FIELDS, canonical_json, scenario_hash
from quoss.scenario.io import dumps_scenario, load_scenario, loads_scenario
from quoss.scenario.models import SCHEMA_VERSION, Scenario

REFERENCE_DIGEST = "64132c82cf6f3cd810f8c58c270acdd7c74be1afda2f259ef9f1a51638647348"
"""SHA-256 of ``canonical_json(reference_castelldefels())``. Its history is `DIGEST_HISTORY`.

If this changes, the canonical form changed: every cached result keyed on the
old digest is unreachable and every provenance record stops matching its
scenario.

**Two different things move this digest, and only one of them is a
``SCHEMA_VERSION`` matter.** This docstring used to say a change was allowed
"only with a ``SCHEMA_VERSION`` bump", which contradicts ``SCHEMA_VERSION``'s own
rule that "adding an optional field with a default does not bump it". Both
cannot be right, so they are separated here:

1. **A field changes meaning, unit, name, or how it serialises.** An old file
   would then be *misread* under the new code — the dangerous case. Bump
   ``SCHEMA_VERSION``, so the old file is refused instead of misread.
2. **A new optional field with a default appears.** An old file is still read
   correctly; the default fills in and every existing scenario means exactly
   what it did. No bump, per ``SCHEMA_VERSION``'s rule. But the canonical form
   has gained a key, so the digest moves anyway.

Case 2 costs a cache generation and stops *previously written results* from
matching a re-derived digest. It does not endanger reading an old scenario,
which is what ``SCHEMA_VERSION`` exists to protect.

How to repin without it reading as drift
-----------------------------------------
A repinned digest and a silently drifted one are the same diff — one hex string
replaced by another — so the difference has to be something a test can check,
not something a reviewer has to remember. It is `DIGEST_HISTORY`:

- **Every repin appends an entry**: the new digest, the date, which case it is,
  the dotted path of the field that moved it, and why ``SCHEMA_VERSION`` did or
  did not move.
- **A case-2 entry is proved, not asserted.**
  `TestTheDigestHistoryIsReproducible` deletes the named fields from today's
  canonical form, newest first, and requires the result to hash to each earlier
  digest in turn. A repin that names the wrong field, or a drift that names none
  (a float formatted differently, an enum written by name), cannot reproduce the
  previous digest and fails there.
- **A case-1 entry cannot be reproduced by deletion** — the old form had a field
  that meant something else — so what is checked for it is the bump itself.
"""


@dataclass(frozen=True, slots=True, kw_only=True)
class DigestRepin:
    """One value `REFERENCE_DIGEST` has had, and what moved it there."""

    digest: str
    date: str
    schema_version: int
    added_fields: tuple[str, ...]
    """Dotted paths of optional fields that entered the canonical form (case 2)."""
    bumped_schema: bool
    """True for case 1: a field changed meaning, and ``SCHEMA_VERSION`` moved."""
    why: str


DIGEST_HISTORY: tuple[DigestRepin, ...] = (
    DigestRepin(
        digest="feafee61257b303a9fdb838e66a981ea4c58c8fad94ec5dfeba7841d53a84227",
        date="2026-09-13",
        schema_version=1,
        added_fields=(),
        bumped_schema=False,
        why="First pin, with the scenario contract of stage 4 (ADR 0014).",
    ),
    DigestRepin(
        digest="64132c82cf6f3cd810f8c58c270acdd7c74be1afda2f259ef9f1a51638647348",
        date="2026-09-15",
        schema_version=1,
        added_fields=("receiver.doppler_capture_range_hz",),
        bumped_schema=False,
        why=(
            "Case 2. ReceiverSpec.doppler_capture_range_hz was added, optional and None by "
            "default (ADR 0020). Every scenarios/*.yaml loads unchanged and means what it did, "
            "so SCHEMA_VERSION stays at 1; the canonical form gained the key "
            '"doppler_capture_range_hz":null, and that is the whole difference.'
        ),
    ),
)
"""Every value the reference digest has had, oldest first. Append; never edit."""


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
            ("receiver.doppler_capture_range_hz", 1e10),
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


class TestTheDigestHistoryIsReproducible:
    """What turns a repin from a claim into a fact: each old digest, rebuilt from today's form."""

    def test_the_last_entry_is_the_pinned_digest(self) -> None:
        assert DIGEST_HISTORY[-1].digest == REFERENCE_DIGEST
        assert DIGEST_HISTORY[-1].schema_version == SCHEMA_VERSION

    def test_the_rebuild_uses_the_canonical_serialisation_and_nothing_else(self) -> None:
        """The deletion below re-serialises a dict; this checks it serialises the same way.

        Without this, a reproduction could fail because the test wrote JSON with
        other separators — or pass because it did. Re-dumping today's canonical
        text unchanged must give back the identical bytes.
        """
        text = canonical_json(reference_castelldefels())
        assert self._dump(json.loads(text)) == text

    def test_every_case_two_repin_is_exactly_its_named_fields(self) -> None:
        """Delete the fields each repin names, newest first; each older digest must reappear.

        The 2026-09-15 repin is the worked example: remove
        ``receiver.doppler_capture_range_hz`` — whose value in the reference
        scenario is ``null`` — from today's canonical form, and the SHA-256 is
        ``feafee61…``, the 2026-09-13 digest, to the last hex digit. A drift that
        changed anything else would leave a different hash, and so would a
        repin that named the wrong field.
        """
        payload = json.loads(canonical_json(reference_castelldefels()))
        for newer, older in zip(DIGEST_HISTORY[:0:-1], DIGEST_HISTORY[-2::-1], strict=True):
            if newer.bumped_schema:
                assert newer.schema_version == older.schema_version + 1, newer.why
                return
            assert newer.schema_version == older.schema_version, newer.why
            assert newer.added_fields, f"{newer.date}: a case-2 repin must name its fields"
            for dotted in newer.added_fields:
                *parents, leaf = dotted.split(".")
                node = payload
                for part in parents:
                    node = node[part]
                del node[leaf]
            rebuilt = hashlib.sha256(self._dump(payload).encode("ascii")).hexdigest()
            assert rebuilt == older.digest, (
                f"removing {newer.added_fields} does not give back the {older.date} digest: "
                f"the repin of {newer.date} moved something it does not name"
            )

    def test_a_drift_that_names_no_field_would_be_caught(self) -> None:
        """The negative control: a changed value is not a deleted key, and does not reproduce."""
        payload = json.loads(canonical_json(reference_castelldefels()))
        del payload["receiver"]["doppler_capture_range_hz"]
        payload["channel"]["zenith_transmittance"] = 0.999_999_999_999
        rebuilt = hashlib.sha256(self._dump(payload).encode("ascii")).hexdigest()
        assert rebuilt != DIGEST_HISTORY[-2].digest

    @staticmethod
    def _dump(payload: Any) -> str:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        )
