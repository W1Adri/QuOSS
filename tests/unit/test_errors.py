"""Tests for the exception hierarchy and the explicit-degradation mechanism.

The point of these tests is the project's hardest rule: a substituted model must
be visible in the result. A DegradationLog that could be dropped, ignored or
silently emptied would make that rule advisory.
"""

import json

import pytest

from quoss.core.errors import (
    ConfigurationError,
    ConvergenceError,
    DataError,
    Degradation,
    DegradationLog,
    DomainError,
    PhysicsError,
    QuossError,
    ScenarioError,
    Severity,
    UnitConversionError,
)


class TestHierarchy:
    """Catching QuossError must catch everything QuOSS raises, and nothing else."""

    @pytest.mark.parametrize(
        "exc",
        [
            ScenarioError,
            ConfigurationError,
            DataError,
            PhysicsError,
            DomainError,
            ConvergenceError,
            UnitConversionError,
        ],
    )
    def test_every_error_derives_from_the_base(self, exc: type[Exception]) -> None:
        assert issubclass(exc, QuossError)

    def test_physics_errors_are_grouped(self) -> None:
        """A caller can catch PhysicsError to mean "the model refused"."""
        assert issubclass(DomainError, PhysicsError)
        assert issubclass(ConvergenceError, PhysicsError)

    def test_scenario_errors_are_not_physics_errors(self) -> None:
        """Bad input and an unevaluable model are different failures."""
        assert not issubclass(ScenarioError, PhysicsError)

    def test_base_is_an_exception_not_a_base_exception(self) -> None:
        assert issubclass(QuossError, Exception)


class TestDegradation:
    """A single record: stable code, human message, structured details."""

    def test_fields_round_trip_through_to_dict(self) -> None:
        entry = Degradation(
            code="turbulence.scintillation-unavailable",
            message="Cn2 profile undefined above 20 km; scintillation set to zero.",
            severity=Severity.DEGRADED,
            where="quoss.channel.turbulence.rytov_variance",
            details={"altitude_km": 25.0},
        )
        payload = entry.to_dict()
        assert payload["code"] == "turbulence.scintillation-unavailable"
        assert payload["severity"] == "degraded"
        assert payload["where"] == "quoss.channel.turbulence.rytov_variance"
        assert payload["details"] == {"altitude_km": 25.0}

    def test_is_json_serialisable(self) -> None:
        """Records travel into the result manifest, which is JSON."""
        entry = Degradation("a.b", "msg", Severity.WARNING, "where", {"x": 1})
        assert json.loads(json.dumps(entry.to_dict()))["details"]["x"] == 1

    def test_is_immutable(self) -> None:
        entry = Degradation("a.b", "msg", Severity.INFO, "where")
        with pytest.raises((AttributeError, TypeError)):
            entry.code = "other"  # type: ignore[misc]

    def test_str_includes_severity_code_and_location(self) -> None:
        text = str(Degradation("a.b", "msg", Severity.DEGRADED, "mod.fn", {"k": 2}))
        assert "degraded" in text
        assert "a.b" in text
        assert "mod.fn" in text
        assert "k" in text

    def test_details_default_to_empty(self) -> None:
        assert Degradation("a.b", "msg", Severity.INFO, "where").details == {}


class TestSeverity:
    """Three levels, and the string values are part of the serialised contract."""

    def test_values_are_stable_strings(self) -> None:
        assert Severity.INFO == "info"
        assert Severity.WARNING == "warning"
        assert Severity.DEGRADED == "degraded"

    def test_serialises_as_a_plain_string(self) -> None:
        assert json.dumps({"s": Severity.DEGRADED}) == '{"s": "degraded"}'


class TestDegradationLog:
    """The collector that travels with a result."""

    def test_starts_empty_and_falsy(self) -> None:
        log = DegradationLog()
        assert len(log) == 0
        assert not log
        assert not log.has_degraded

    def test_records_preserve_order(self) -> None:
        log = DegradationLog()
        log.info("a", "first", where="w")
        log.warn("b", "second", where="w")
        log.degrade("c", "third", where="w")
        assert [e.code for e in log.entries] == ["a", "b", "c"]

    def test_convenience_methods_set_the_right_severity(self) -> None:
        log = DegradationLog()
        log.info("a", "m", where="w")
        log.warn("b", "m", where="w")
        log.degrade("c", "m", where="w")
        assert [e.severity for e in log.entries] == [
            Severity.INFO,
            Severity.WARNING,
            Severity.DEGRADED,
        ]

    def test_keyword_arguments_become_details(self) -> None:
        log = DegradationLog()
        log.degrade("a", "m", where="w", altitude_km=25.0, model="HV5/7")
        assert log.entries[0].details == {"altitude_km": 25.0, "model": "HV5/7"}

    def test_has_degraded_only_reacts_to_substitution(self) -> None:
        """An INFO or WARNING must not flag a result as untrustworthy."""
        log = DegradationLog()
        log.info("a", "m", where="w")
        log.warn("b", "m", where="w")
        assert not log.has_degraded
        log.degrade("c", "m", where="w")
        assert log.has_degraded

    def test_by_severity_filters(self) -> None:
        log = DegradationLog()
        log.warn("a", "m", where="w")
        log.degrade("b", "m", where="w")
        log.warn("c", "m", where="w")
        assert [e.code for e in log.by_severity(Severity.WARNING)] == ["a", "c"]
        assert [e.code for e in log.by_severity(Severity.DEGRADED)] == ["b"]

    def test_entries_view_cannot_mutate_the_log(self) -> None:
        """A caller holding `entries` must not be able to erase a degradation."""
        log = DegradationLog()
        log.degrade("a", "m", where="w")
        entries = log.entries
        assert isinstance(entries, tuple)
        assert len(log) == 1

    def test_is_iterable(self) -> None:
        log = DegradationLog()
        log.warn("a", "m", where="w")
        assert [e.code for e in log] == ["a"]

    def test_to_dicts_is_json_serialisable(self) -> None:
        log = DegradationLog()
        log.degrade("a", "m", where="w", value=1.5)
        assert json.loads(json.dumps(log.to_dicts()))[0]["details"]["value"] == 1.5

    def test_repr_summarises_counts(self) -> None:
        log = DegradationLog()
        log.degrade("a", "m", where="w")
        log.warn("b", "m", where="w")
        text = repr(log)
        assert "degraded=1" in text
        assert "warning=1" in text

    def test_empty_repr_says_empty(self) -> None:
        assert "empty" in repr(DegradationLog())


class TestMerging:
    """Parallel workers each get a log; the join point merges them."""

    def test_extend_from_another_log_preserves_order(self) -> None:
        worker_a = DegradationLog()
        worker_a.warn("a", "m", where="w")
        worker_b = DegradationLog()
        worker_b.degrade("b", "m", where="w")

        merged = DegradationLog()
        merged.extend(worker_a)
        merged.extend(worker_b)
        assert [e.code for e in merged.entries] == ["a", "b"]
        assert merged.has_degraded

    def test_extend_from_a_plain_iterable(self) -> None:
        log = DegradationLog()
        log.extend([Degradation("a", "m", Severity.INFO, "w")])
        assert len(log) == 1

    def test_merging_does_not_mutate_the_source(self) -> None:
        source = DegradationLog()
        source.warn("a", "m", where="w")
        target = DegradationLog()
        target.extend(source)
        target.warn("b", "m", where="w")
        assert len(source) == 1

    def test_constructor_accepts_initial_entries(self) -> None:
        log = DegradationLog([Degradation("a", "m", Severity.DEGRADED, "w")])
        assert log.has_degraded
