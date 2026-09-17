"""Tests for `quoss.scenario.models`.

Organised by the claim each block defends.

- ``TestTheTwoFieldsWithoutADefault`` — the two decisions the schema inherits
  from ADR 0009 (gap 14) and ADR 0011 (§5): ``zenith_transmittance`` and
  ``minimum_elevation_deg`` are required, and a test is what keeps them so.
- ``TestUnitsConvertOnceAtTheBoundary`` — every user-unit field has a physics
  unit twin, and the twin is what ``core.units`` says it is.
- ``TestAValidScenarioAlwaysConverts`` — **V1 by property**: the schema's rules
  mirror the physics containers' rules, so what validates here builds a
  ``TimeGrid``, a ``ClassicalElements``, a protocol and a security object
  without ever raising downstream.
- ``TestKeplerOrbit`` / ``TestTleOrbit`` / ``TestOrbitSpec`` — exclusivity,
  feasibility and the SGP4 checksum.
- ``TestBackgroundSpec`` — value or table, and that resolving a table column
  logs the interpolation the physics logs.
- ``TestProtocolSpec`` — the registry decides the name; ``"e91"`` is refused
  with the list of what exists.
- ``TestTimeSpec`` — naive datetimes are the wall-clock defect and are refused;
  the whole-multiple rule mirrors ``TimeGrid.uniform``.
- ``TestScenario`` — the cross-model rules, ``extra="forbid"``, frozen, NaN.
- ``TestTheModuleSurface`` — layering (no ``system``/``engine`` import) and
  that every numeric field carries a bound.
"""

from __future__ import annotations

import ast
import datetime as dt
import inspect
import math
from collections.abc import Callable
from pathlib import Path
from types import NoneType, UnionType
from typing import Any, get_args

import numpy as np
import pytest
from annotated_types import Ge, Gt, Le, Lt
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import TypeAdapter, ValidationError

import quoss.scenario.models as models_module
from quoss.channel.atmosphere import bufton_rms_wind_speed_m_s
from quoss.channel.background import SkyCondition
from quoss.channel.detector import receiver_efficiency
from quoss.channel.horizontal import (
    horizontal_log_irradiance_variance,
    horizontal_loss_budget,
    horizontal_point_log_irradiance_variance,
)
from quoss.channel.link_budget import FadeCombination, downlink_loss_budget
from quoss.channel.turbulence import (
    ScintillationRegime,
    downlink_log_irradiance_variance,
    log_irradiance_variance,
    uplink_log_irradiance_variance,
)
from quoss.core.errors import DegradationLog, Severity
from quoss.core.types import TimeGrid
from quoss.core.units import deg_to_rad
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.frames import calendar_to_jd
from quoss.orbits.kepler import ClassicalElements
from quoss.orbits.propagator import PropagationMethod
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import SecurityParameters
from quoss.scenario.defaults import ge1_two_terminals, reference_castelldefels
from quoss.scenario.models import (
    HV57_RMS_WIND_SPEED_M_S,
    SCHEMA_VERSION,
    AggregationPolicyName,
    AnyScenario,
    BackgroundSpec,
    ChannelSpec,
    ExtinctionSpec,
    HorizontalPathSpec,
    HorizontalScenario,
    KeplerOrbit,
    LinkKind,
    MonteCarloSpec,
    MultiStationSpec,
    OrbitSpec,
    PassSpec,
    ProtocolSpec,
    ReceiverSpec,
    RelaySpec,
    Scenario,
    SecuritySpec,
    SessionSpec,
    SpecModel,
    StationSpec,
    TimeSpec,
    TleOrbit,
    TransmitterSpec,
)

ISS_LINE1 = "1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996"
ISS_LINE2 = "2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781"
"""The TLE of ``quoss.orbits.tle.parse_tle``'s own doctest."""

UTC = dt.UTC


def reference_dict() -> dict[str, Any]:
    """Return the reference scenario as the plain dict a file would give."""
    return reference_castelldefels().model_dump(mode="json")


def with_override(data: dict[str, Any], path: str, value: Any) -> dict[str, Any]:
    """Return a deep-ish copy of ``data`` with the dotted ``path`` set to ``value``."""
    out = dict(data)
    node: Any = out
    parts = path.split(".")
    for part in parts[:-1]:
        key: int | str = int(part) if part.isdigit() else part
        child = node[key]
        copied: Any = list(child) if isinstance(child, list) else dict(child)
        node[key] = copied
        node = copied
    last: int | str = int(parts[-1]) if parts[-1].isdigit() else parts[-1]
    node[last] = value
    return out


# --------------------------------------------------------------------------- #
class TestTheFieldsWithoutADefault:
    """Adding a default to any of these is a decision, and this is where it shows up."""

    def test_extinction_must_be_declared_one_of_the_two_ways(self) -> None:
        """ADR 0009 gap 14, now with a second way of answering it (ADR 0023).

        Neither ``zenith_transmittance`` nor ``extinction`` is individually
        required — either alone is a complete declaration — so what is asserted
        is the pair: a ``ChannelSpec`` with neither is refused, and so is one
        with both. A default on either would be an invented atmosphere made
        authoritative by sitting in a signature.
        """
        assert not ChannelSpec.model_fields["zenith_transmittance"].is_required()
        assert not ChannelSpec.model_fields["extinction"].is_required()
        with pytest.raises(ValidationError, match="exactly one of zenith_transmittance"):
            ChannelSpec(scintillation_regime="weak")
        with pytest.raises(ValidationError, match="exactly one of zenith_transmittance"):
            ChannelSpec(
                scintillation_regime="weak",
                zenith_transmittance=0.9,
                extinction=ExtinctionSpec(
                    visibility_km=23.0,
                    visibility_altitude_m=0.0,
                    aerosol_scale_height_m=1200.0,
                    scaling_law="kim-2001",
                ),
            )

    def test_the_two_fields_inside_the_extinction_model_are_required(self) -> None:
        """A scale height nobody published, and a law that is a physics choice."""
        assert ExtinctionSpec.model_fields["aerosol_scale_height_m"].is_required()
        assert ExtinctionSpec.model_fields["scaling_law"].is_required()
        assert ExtinctionSpec.model_fields["visibility_km"].is_required()
        assert ExtinctionSpec.model_fields["visibility_altitude_m"].is_required()
        with pytest.raises(ValidationError, match="aerosol_scale_height_m"):
            ExtinctionSpec(visibility_km=23.0, visibility_altitude_m=0.0, scaling_law="kim-2001")  # type: ignore[call-arg]

    def test_minimum_elevation_is_required(self) -> None:
        """ADR 0011 §5: interior optimum near 8 deg, so the mask is a design variable."""
        assert PassSpec.model_fields["minimum_elevation_deg"].is_required()
        with pytest.raises(ValidationError, match="minimum_elevation_deg"):
            PassSpec()  # type: ignore[call-arg]

    def test_the_descriptions_say_why(self) -> None:
        """A reader of the schema, not only of the tests, must see the reason."""
        assert "ADR 0009" in str(ChannelSpec.model_fields["zenith_transmittance"].description)
        assert "ADR 0023" in str(ChannelSpec.model_fields["extinction"].description)
        assert "ADR 0009 gap 22" in str(
            ExtinctionSpec.model_fields["aerosol_scale_height_m"].description
        )
        assert "ADR 0011" in str(PassSpec.model_fields["minimum_elevation_deg"].description)


# --------------------------------------------------------------------------- #
class TestExtinctionIsResolvedNotRead:
    """The two ways produce a transmittance through the same call.

    The engine never reads ``channel.zenith_transmittance``; it asks
    ``zenith_transmittance_at`` for one, with a wavelength and a station. That
    is what lets a single declaration give three stations three different
    atmospheres, and what makes a declared number bit-identical to what it was
    before the model existed.
    """

    @staticmethod
    def _modelled(**overrides: object) -> ChannelSpec:
        fields: dict[str, object] = {
            "visibility_km": 23.0,
            "visibility_altitude_m": 0.0,
            "aerosol_scale_height_m": 1200.0,
            "scaling_law": "kim-2001",
        }
        fields.update(overrides)
        return ChannelSpec(scintillation_regime="weak", extinction=ExtinctionSpec(**fields))

    def test_a_declared_number_comes_back_unchanged_and_logs_nothing(self) -> None:
        spec = ChannelSpec(zenith_transmittance=0.812, scintillation_regime="weak")
        log = DegradationLog()
        got = spec.zenith_transmittance_at(
            wavelength_m=1.55e-6, station_altitude_m=30.0, degradations=log
        )
        assert got == 0.812
        assert spec.models_extinction is False
        assert len(log) == 0

    def test_a_model_depends_on_the_wavelength(self) -> None:
        """0.192 dB/km at 1550 nm against 0.465 at 785, so ``L_zen`` differs."""
        spec = self._modelled()
        log = DegradationLog()
        infrared = spec.zenith_transmittance_at(
            wavelength_m=1.55e-6, station_altitude_m=0.0, degradations=log
        )
        near = spec.zenith_transmittance_at(
            wavelength_m=785e-9, station_altitude_m=0.0, degradations=log
        )
        assert infrared == pytest.approx(0.94833, abs=5e-6)
        assert near == pytest.approx(0.87945, abs=5e-6)
        assert spec.models_extinction is True

    def test_a_sea_level_visibility_gives_three_stations_three_atmospheres(self) -> None:
        """Castelldefels at 30 m, Calar Alto at 2168 m, Teide OGS at 2390 m."""
        spec = self._modelled()
        log = DegradationLog()
        got = [
            spec.zenith_transmittance_at(
                wavelength_m=1.55e-6, station_altitude_m=altitude_m, degradations=log
            )
            for altitude_m in (30.0, 2168.0, 2390.0)
        ]
        assert got == pytest.approx([0.94958, 0.99133, 0.99279], abs=5e-6)
        assert got[0] < got[1] < got[2]

    def test_a_locally_measured_visibility_makes_the_station_altitude_irrelevant(self) -> None:
        """The other reading, and it is the ordinary one for a site survey.

        A visibility measured where the station stands describes the bottom of
        the aerosol column above it, whatever altitude that bottom is at. So
        setting ``visibility_altitude_m`` equal to the station's altitude gives
        the same transmittance at 30 m and at 2390 m — and that identity is the
        reason the two altitudes are separate fields rather than one.
        """
        log = DegradationLog()
        got = [
            self._modelled(visibility_altitude_m=altitude_m).zenith_transmittance_at(
                wavelength_m=1.55e-6, station_altitude_m=altitude_m, degradations=log
            )
            for altitude_m in (30.0, 2168.0, 2390.0)
        ]
        assert got[0] == pytest.approx(got[1], rel=1e-15)
        assert got[0] == pytest.approx(got[2], rel=1e-15)
        assert got[0] == pytest.approx(math.exp(-0.053048), abs=5e-6)

    def test_the_models_warnings_reach_the_log_the_engine_passes(self) -> None:
        """A fog visibility under the disputed law has to surface in ``warnings[]``."""
        spec = self._modelled(visibility_km=0.05, scaling_law="itu-p1814")
        log = DegradationLog()
        spec.zenith_transmittance_at(wavelength_m=1.55e-6, station_altitude_m=0.0, degradations=log)
        assert [entry.code for entry in log] == [
            "extinction.kruse-exponent-below-the-fog-threshold"
        ]


# --------------------------------------------------------------------------- #
class TestUnitsConvertOnceAtTheBoundary:
    """The physics-unit twin of every user-unit field."""

    def test_station(self) -> None:
        station = StationSpec(
            name="s",
            latitude_deg=41.275,
            longitude_deg=1.9875,
            altitude_m=30.0,
            receive_aperture_m=0.75,
        )
        assert station.latitude_rad == deg_to_rad(41.275)
        assert station.longitude_rad == deg_to_rad(1.9875)
        assert station.altitude_km == 0.03
        assert station.station_height_m == 30.0
        assert station.rms_wind_speed_m_s == 21.0

    def test_the_schema_has_no_regime_default_and_the_physics_signatures_keep_theirs(
        self,
    ) -> None:
        """The default did not disappear, it moved — and this is where that is checked.

        Until PR #15 the schema and
        :func:`~quoss.channel.link_budget.downlink_loss_budget` both defaulted to
        ``WEAK``, and the test here was that the two agreed: a drift between them
        would have been invisible, every scenario quietly getting one model while
        every direct caller got the other.

        The schema's default is now **gone**, for the reason ADR 0022's annex
        gives: a horizontal path (:class:`HorizontalPathSpec`) is the other member
        of the ``link`` union, and on it the weak theory stops being citable at
        2413 m — so one default cannot be right for both members. The seven
        physics signatures keep ``WEAK``, because those are where the comparisons
        against ITU-R P.1622 Table 2 are made and flipping them would move six of
        its eight published cells outside half a printed digit.

        So what is asserted is the new arrangement, in both directions: required
        in the schema, ``WEAK`` in every physics signature, and the count of those
        signatures pinned so that a new one appearing without a default — or with
        the other one — is a red test rather than a silent asymmetry.
        """
        assert ChannelSpec.model_fields["scintillation_regime"].is_required()
        with pytest.raises(ValidationError, match="scintillation_regime"):
            ChannelSpec(zenith_transmittance=1.0)  # type: ignore[call-arg]

        signatures: list[Callable[..., Any]] = [
            downlink_loss_budget,
            log_irradiance_variance,
            downlink_log_irradiance_variance,
            uplink_log_irradiance_variance,
            horizontal_point_log_irradiance_variance,
            horizontal_log_irradiance_variance,
            horizontal_loss_budget,
        ]
        defaults = {
            f.__name__: inspect.signature(f).parameters["regime"].default for f in signatures
        }
        assert defaults == dict.fromkeys(defaults, ScintillationRegime.WEAK)
        assert len(defaults) == 7
        assert "REQUIRED, no default" in str(
            ChannelSpec.model_fields["scintillation_regime"].description
        )
        assert "moderate-to-strong" in str(
            ChannelSpec.model_fields["scintillation_regime"].description
        )

    def test_the_wind_default_is_the_hv57_value_not_the_bufton_conversion(self) -> None:
        """Bufton(2.3 m/s) is 21.018 m/s; HV 5/7 and the physics defaults use 21.0.

        Measured here: the two differ by 0.085 %, which moved the reference
        loss budget by 6.8e-5 relative (0.0028 dB at 10 deg) when the field was
        a ground wind. The schema carries the r.m.s. wind the physics takes.
        """
        assert bufton_rms_wind_speed_m_s(2.3) == pytest.approx(21.018, abs=5e-4)
        assert abs(bufton_rms_wind_speed_m_s(2.3) - 21.0) / 21.0 > 8e-4
        # The literal in the schema is the physics default, checked against the signature.
        default = (
            inspect.signature(log_irradiance_variance).parameters["rms_wind_speed_m_s"].default
        )
        assert HV57_RMS_WIND_SPEED_M_S == default == 21.0
        # What the 0.085 % would have cost: the reference loss budget at 10 deg and
        # 2000 km, once with each wind. Pinned to two significant digits as a
        # measurement, not a tolerance on physics.
        s = reference_castelldefels()
        budgets = [
            downlink_loss_budget(
                np.array([float(deg_to_rad(10.0))]),
                range_km=np.array([2000.0]),
                wavelength_m=s.transmitter.wavelength_m,
                transmit_aperture_m=s.transmitter.aperture_m,
                receive_aperture_m=s.stations[0].receive_aperture_m,
                zenith_transmittance=1.0,
                pointing_jitter_rad=s.transmitter.pointing_jitter_rad,
                receiver_efficiency=s.receiver.chain_efficiency,
                station_height_m=s.stations[0].station_height_m,
                rms_wind_speed_m_s=wind,
                degradations=DegradationLog(),
            ).total_db[0]
            for wind in (21.0, bufton_rms_wind_speed_m_s(2.3))
        ]
        difference_db = budgets[1] - budgets[0]
        assert difference_db == pytest.approx(0.0028, abs=0.0002)
        assert difference_db / budgets[0] == pytest.approx(6.8e-5, abs=0.2e-5)

    def test_transmitter(self) -> None:
        tx = TransmitterSpec(
            wavelength_nm=1550.0, aperture_m=0.15, pointing_jitter_urad=0.75, pulse_rate_hz=100e6
        )
        # One multiplication by a power of ten: at most one rounding, 2^-53 relative.
        assert tx.wavelength_m == pytest.approx(1.55e-6, rel=2**-52)
        assert tx.pointing_jitter_rad == pytest.approx(0.75e-6, rel=2**-52)
        assert tx.pulse_period_s == 1e-8

    def test_receiver(self) -> None:
        rx = ReceiverSpec(
            detector_efficiency=0.85,
            optical_loss_db=5.65,
            dark_count_rate_cps=300.0,
            dead_time_ns=30.0,
            gate_ns=1.0,
            timing_jitter_fwhm_ps=50.0,
            field_of_view_urad=100.0,
            filter_bandwidth_nm=0.2,
        )
        assert rx.gate_s == pytest.approx(1e-9, rel=2**-52)
        assert rx.dead_time_s == pytest.approx(30e-9, rel=2**-52)
        assert rx.timing_jitter_fwhm_s == pytest.approx(50e-12, rel=2**-52)
        assert rx.field_of_view_rad == pytest.approx(100e-6, rel=2**-52)
        assert rx.filter_bandwidth_m == pytest.approx(0.2e-9, rel=2**-52)
        assert rx.chain_efficiency == receiver_efficiency(0.85, optical_loss_db=5.65)

    def test_pass_and_security(self) -> None:
        assert PassSpec(minimum_elevation_deg=10.0).minimum_elevation_rad == deg_to_rad(10.0)
        assert SecuritySpec(correctness=1e-9, secrecy=2e-9).to_security() == SecurityParameters(
            correctness=1e-9, secrecy=2e-9
        )

    def test_time(self) -> None:
        time = TimeSpec(
            epoch_utc=dt.datetime(2025, 1, 1, 12, 30, 15, 500_000, tzinfo=UTC),
            duration_s=600.0,
            step_s=1.0,
        )
        assert time.epoch_jd == calendar_to_jd(2025, 1, 1, 12, 30, 15.5)
        grid = time.grid()
        expected = TimeGrid.uniform(epoch_jd=time.epoch_jd, duration_s=600.0, step_s=1.0)
        assert grid.epoch_jd == expected.epoch_jd
        assert np.array_equal(grid.t_s, expected.t_s)
        assert time.n_samples == grid.n == 601

    def test_kepler_elements_are_the_reference_elements(self) -> None:
        """Same construction as ``tests/system/reference.py``, angle by angle."""
        orbit = KeplerOrbit(
            altitude_km=700.0, eccentricity=0.001, sun_synchronous=True, raan_deg=30.0
        )
        a = 6378.137 + 700.0
        inclination = float(
            np.ravel(sun_synchronous_inclination_rad(semi_major_axis_km=a, eccentricity=0.001))[0]
        )
        expected = ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=a,
            eccentricity=0.001,
            inclination_rad=inclination,
            raan_rad=float(deg_to_rad(30.0)),
            argp_rad=0.0,
            true_anomaly_rad=0.0,
        )
        got = orbit.to_elements()
        for attr in (
            "semi_latus_rectum_km",
            "eccentricity",
            "inclination_rad",
            "raan_rad",
            "argp_rad",
            "true_anomaly_rad",
        ):
            assert np.array_equal(
                np.asarray(getattr(got, attr)), np.asarray(getattr(expected, attr))
            ), attr

    def test_explicit_inclination_is_used_as_given(self) -> None:
        orbit = KeplerOrbit(altitude_km=600.0, inclination_deg=97.4, raan_deg=0.0)
        assert orbit.inclination_rad == deg_to_rad(97.4)
        assert orbit.argp_rad == 0.0
        assert orbit.true_anomaly_rad == 0.0


# --------------------------------------------------------------------------- #
class TestAValidScenarioAlwaysConverts:
    """The schema's rules mirror the containers', so nothing raises downstream."""

    @given(
        step_s=st.sampled_from([0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]),
        steps=st.integers(min_value=1, max_value=20_000),
        second=st.integers(min_value=0, max_value=59),
    )
    @settings(max_examples=60, deadline=None)
    def test_whole_multiples_build_a_grid_of_the_promised_length(
        self, step_s: float, steps: int, second: int
    ) -> None:
        """``duration = k * step`` validates and yields ``k + 1`` samples, for any k."""
        time = TimeSpec(
            epoch_utc=dt.datetime(2025, 6, 1, 0, 0, second, tzinfo=UTC),
            duration_s=steps * step_s,
            step_s=step_s,
        )
        assert time.grid().n == steps + 1 == time.n_samples

    @given(
        altitude_km=st.floats(min_value=300.0, max_value=2000.0),
        eccentricity=st.floats(min_value=0.0, max_value=0.02),
    )
    @settings(max_examples=40, deadline=None)
    def test_sun_synchronous_leo_orbits_convert(
        self, altitude_km: float, eccentricity: float
    ) -> None:
        """Every LEO sun-synchronous orbit the validator accepts has elements."""
        orbit = KeplerOrbit(
            altitude_km=altitude_km, eccentricity=eccentricity, sun_synchronous=True, raan_deg=0.0
        )
        elements = orbit.to_elements()
        assert 0.0 < float(np.ravel(elements.inclination_rad)[0]) < np.pi

    def test_protocol_and_security_convert_to_the_physics_objects(self) -> None:
        scenario = reference_castelldefels()
        assert scenario.protocol.to_protocol() == Bb84DecoyProtocol.ntanos_2021()
        assert scenario.security.to_security() == SecurityParameters(
            correctness=1e-10, secrecy=1e-10
        )


# --------------------------------------------------------------------------- #
class TestKeplerOrbit:
    def test_neither_inclination_nor_sun_synchronous_is_refused(self) -> None:
        with pytest.raises(
            ValidationError, match="exactly one of inclination_deg or sun_synchronous"
        ):
            KeplerOrbit(altitude_km=700.0, raan_deg=0.0)

    def test_both_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of"):
            KeplerOrbit(altitude_km=700.0, inclination_deg=98.0, sun_synchronous=True, raan_deg=0.0)

    def test_periapsis_below_ground_is_refused(self) -> None:
        """700 km up, e >= 700 / 7078 = 0.0989 dips below the equatorial radius."""
        limit = 700.0 / (6378.137 + 700.0)
        with pytest.raises(ValidationError, match="periapsis below the Earth"):
            KeplerOrbit(altitude_km=700.0, eccentricity=limit, inclination_deg=98.0, raan_deg=0.0)
        KeplerOrbit(
            altitude_km=700.0, eccentricity=limit * 0.99, inclination_deg=98.0, raan_deg=0.0
        )

    def test_an_impossible_sun_synchronous_orbit_is_refused_at_validation(self) -> None:
        """At 20 000 km J2 cannot drive the node fast enough; the physics says so, so does the schema."""
        with pytest.raises(
            ValidationError, match="No inclination makes this orbit sun-synchronous"
        ):
            KeplerOrbit(altitude_km=20_000.0, sun_synchronous=True, raan_deg=0.0)

    def test_method_maps_to_the_propagator_enum(self) -> None:
        assert (
            KeplerOrbit(altitude_km=700.0, inclination_deg=98.0, raan_deg=0.0).propagation_method
            is PropagationMethod.TWO_BODY
        )
        assert (
            KeplerOrbit(
                altitude_km=700.0, inclination_deg=98.0, raan_deg=0.0, method="zonal_numeric"
            ).propagation_method
            is PropagationMethod.ZONAL_NUMERIC
        )

    def test_sgp4_is_not_a_kepler_method(self) -> None:
        """SGP4 takes mean elements a Kepler orbit does not have; only a TLE reaches it."""
        with pytest.raises(ValidationError, match="method"):
            KeplerOrbit.model_validate(
                {"altitude_km": 700.0, "inclination_deg": 98.0, "raan_deg": 0.0, "method": "sgp4"}
            )

    @pytest.mark.parametrize("field", ["raan_deg", "argp_deg", "true_anomaly_deg"])
    def test_angles_are_half_open_on_a_turn(self, field: str) -> None:
        with pytest.raises(ValidationError, match=field):
            KeplerOrbit(
                **{"altitude_km": 700.0, "inclination_deg": 98.0, "raan_deg": 0.0, field: 360.0}
            )


class TestTleOrbit:
    def test_a_valid_tle_parses_and_carries_its_epoch(self) -> None:
        orbit = TleOrbit(line1=ISS_LINE1, line2=ISS_LINE2, name="ISS (ZARYA)")
        assert orbit.to_satrec().satnum == 25544
        assert orbit.epoch_jd == pytest.approx(2458878.41700964, abs=1e-8)

    def test_a_corrupted_checksum_is_refused_at_validation(self) -> None:
        """The failure ``parse_tle`` finds and ``sgp4`` would not."""
        with pytest.raises(ValidationError, match="checksum"):
            TleOrbit(line1=ISS_LINE1[:-1] + "0", line2=ISS_LINE2)


class TestOrbitSpec:
    def test_neither_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of kepler or tle"):
            OrbitSpec()

    def test_both_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of kepler or tle"):
            OrbitSpec(
                kepler=KeplerOrbit(altitude_km=700.0, inclination_deg=98.0, raan_deg=0.0),
                tle=TleOrbit(line1=ISS_LINE1, line2=ISS_LINE2),
            )

    def test_is_tle(self) -> None:
        assert OrbitSpec(tle=TleOrbit(line1=ISS_LINE1, line2=ISS_LINE2)).is_tle
        assert not OrbitSpec(
            kepler=KeplerOrbit(altitude_km=700.0, inclination_deg=98.0, raan_deg=0.0)
        ).is_tle


# --------------------------------------------------------------------------- #
class TestBackgroundSpec:
    def test_exactly_one_source(self) -> None:
        with pytest.raises(ValidationError, match="exactly one of sky_radiance"):
            BackgroundSpec()
        with pytest.raises(ValidationError, match="exactly one of sky_radiance"):
            BackgroundSpec(sky_radiance_w_m2_um_sr=1e-5, condition="overcast")

    def test_a_value_resolves_to_itself_without_a_log_entry(
        self, degradations: DegradationLog
    ) -> None:
        spec = BackgroundSpec(sky_radiance_w_m2_um_sr=1.5e-4)
        assert not spec.is_tabulated
        assert spec.radiance_w_m2_um_sr(1.55e-6, degradations=degradations) == 1.5e-4
        assert len(degradations) == 0

    def test_a_table_column_at_a_grid_point_does_not_degrade(
        self, degradations: DegradationLog
    ) -> None:
        spec = BackgroundSpec(condition="overcast")
        assert spec.condition is SkyCondition.OVERCAST
        assert spec.radiance_w_m2_um_sr(1.5e-6, degradations=degradations) == 4.44
        assert len(degradations) == 0

    def test_a_table_column_between_grid_points_records_the_interpolation(
        self, degradations: DegradationLog
    ) -> None:
        """ADR 0009 gap 4: interpolating the ITU table is a substitution and is logged as one."""
        spec = BackgroundSpec(condition=SkyCondition.NORMAL_SUNSHINE)
        value = spec.radiance_w_m2_um_sr(1.0e-6, degradations=degradations)
        assert value > 0.0
        assert degradations.has_degraded
        assert degradations.entries[0].severity is Severity.DEGRADED


# --------------------------------------------------------------------------- #
class TestProtocolSpec:
    def base(self, **overrides: Any) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": "bb84-decoy",
            "signal_intensity": 0.56,
            "decoy_intensity": 0.11,
            "signal_probability": 16 / 21,
            "decoy_probability": 1 / 21,
            "vacuum_probability": 4 / 21,
            "error_correction_efficiency": 1.22,
            "misalignment_error": 0.01,
        }
        data.update(overrides)
        return data

    def test_an_unregistered_protocol_is_refused_naming_the_registered_ones(self) -> None:
        """The negative control: E91 is not implemented and must not silently run as BB84."""
        with pytest.raises(
            ValidationError, match=r"no QKD protocol is registered as 'e91'.*bb84-decoy"
        ):
            ProtocolSpec(**self.base(name="e91"))

    def test_decoy_must_be_weaker_than_signal(self) -> None:
        with pytest.raises(ValidationError, match="must be below"):
            ProtocolSpec(**self.base(decoy_intensity=0.56))

    def test_probabilities_must_sum_to_one(self) -> None:
        with pytest.raises(ValidationError, match="must equal 1"):
            ProtocolSpec(**self.base(vacuum_probability=0.2))

    def test_the_float_slack_on_the_sum_is_the_protocols_own(self) -> None:
        """16/21 + 1/21 + 4/21 is not 1.0 in binary and must still be accepted."""
        spec = ProtocolSpec(**self.base())
        assert spec.to_protocol() == Bb84DecoyProtocol.ntanos_2021()
        assert models_module._PROBABILITY_SUM_SLACK == 1e-9

    def test_misalignment_is_a_probability_below_one_half(self) -> None:
        with pytest.raises(ValidationError, match="misalignment_error"):
            ProtocolSpec(**self.base(misalignment_error=0.6))


# --------------------------------------------------------------------------- #
class TestTimeSpec:
    def test_a_naive_datetime_is_the_wall_clock_defect_and_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="wall clock"):
            TimeSpec(epoch_utc=dt.datetime(2025, 1, 1), duration_s=60.0, step_s=1.0)

    def test_a_non_utc_offset_is_refused(self) -> None:
        cest = dt.timezone(dt.timedelta(hours=2))
        with pytest.raises(ValidationError, match="must be in UTC"):
            TimeSpec(epoch_utc=dt.datetime(2025, 7, 1, tzinfo=cest), duration_s=60.0, step_s=1.0)

    def test_a_year_outside_the_julian_date_helpers_range_is_refused(self) -> None:
        """``calendar_to_jd`` refuses years outside [1900, 2100]; so must the schema."""
        with pytest.raises(ValidationError, match="year"):
            TimeSpec(epoch_utc=dt.datetime(1850, 1, 1, tzinfo=UTC), duration_s=60.0, step_s=1.0)

    def test_a_fractional_step_count_is_refused(self) -> None:
        with pytest.raises(ValidationError, match="not a whole multiple"):
            TimeSpec(epoch_utc=dt.datetime(2025, 1, 1, tzinfo=UTC), duration_s=10.0, step_s=3.0)

    def test_the_slack_is_the_grids_slack(self) -> None:
        """0.3 / 0.1 is 2.9999999999999996; ``TimeGrid.uniform`` accepts it, so does the schema."""
        time = TimeSpec(epoch_utc=dt.datetime(2025, 1, 1, tzinfo=UTC), duration_s=0.3, step_s=0.1)
        assert time.grid().n == 4
        assert models_module._GRID_STEP_SLACK == 1e-9

    def test_an_iso_string_with_z_parses_to_utc(self) -> None:
        time = TimeSpec.model_validate(
            {"epoch_utc": "2025-01-01T00:00:00Z", "duration_s": 60.0, "step_s": 1.0}
        )
        assert time.epoch_utc.tzinfo is not None
        assert time.epoch_jd == 2460676.5


# --------------------------------------------------------------------------- #
class TestOptionSpecs:
    def test_monte_carlo_quantiles_must_be_probabilities_in_increasing_order(self) -> None:
        base = {
            "realisations": 10,
            "scintillation_correlation_time_s": 0.01,
            "pointing_correlation_time_s": 0.1,
        }
        with pytest.raises(ValidationError, match=r"quantiles must lie in \(0, 1\)"):
            MonteCarloSpec(**base, quantiles=(0.0, 0.5))
        with pytest.raises(ValidationError, match="strictly increasing"):
            MonteCarloSpec(**base, quantiles=(0.5, 0.5))
        with pytest.raises(ValidationError, match="strictly increasing"):
            MonteCarloSpec(**base, quantiles=(0.9, 0.1))
        assert MonteCarloSpec(**base).quantiles == (0.05, 0.5, 0.95)

    def test_monte_carlo_seed_bounds_are_the_random_sources(self) -> None:
        base = {
            "realisations": 10,
            "scintillation_correlation_time_s": 0.01,
            "pointing_correlation_time_s": 0.1,
        }
        with pytest.raises(ValidationError, match="seed"):
            MonteCarloSpec(**base, seed=-1)
        with pytest.raises(ValidationError, match="seed"):
            MonteCarloSpec(**base, seed=2**64)
        assert MonteCarloSpec(**base, seed=None).seed is None

    def test_multi_station_policy_default(self) -> None:
        assert MultiStationSpec().policy is AggregationPolicyName.BEST_AVAILABLE
        assert MultiStationSpec(policy="sum").policy is AggregationPolicyName.SUM

    def test_relay_pairs(self) -> None:
        with pytest.raises(ValidationError, match="two different stations"):
            RelaySpec(pairs=[("a", "a")])
        with pytest.raises(ValidationError, match="pairs"):
            RelaySpec(pairs=[])
        assert RelaySpec.model_validate({"pairs": [["a", "b"]]}).pairs == [("a", "b")]


# --------------------------------------------------------------------------- #
class TestScenario:
    def test_a_misspelled_key_is_refused_not_ignored(self) -> None:
        data = with_override(
            reference_dict(),
            "transmitter",
            {**reference_dict()["transmitter"], "wavelenght_nm": 1.0},
        )
        with pytest.raises(ValidationError, match="wavelenght_nm"):
            Scenario.model_validate(data)

    def test_frozen(self) -> None:
        scenario = reference_castelldefels()
        with pytest.raises(ValidationError, match="frozen"):
            scenario.name = "other"  # type: ignore[misc]

    @pytest.mark.parametrize("bad", [float("nan"), float("inf")])
    def test_non_finite_values_are_refused(self, bad: float) -> None:
        with pytest.raises(ValidationError, match="altitude_km"):
            Scenario.model_validate(
                with_override(reference_dict(), "orbit.kepler.altitude_km", bad)
            )

    def test_duplicate_station_names(self) -> None:
        data = reference_dict()
        data["stations"] = [data["stations"][0], data["stations"][0]]
        with pytest.raises(ValidationError, match="station names must be unique"):
            Scenario.model_validate(data)

    def test_relay_pairs_must_name_stations(self) -> None:
        data = with_override(reference_dict(), "relay", {"pairs": [["castelldefels", "nowhere"]]})
        with pytest.raises(ValidationError, match=r"do not exist: \['nowhere'\]"):
            Scenario.model_validate(data)

    def test_gate_wider_than_the_pulse_period_is_refused(self) -> None:
        """The rule ``LinkConditions`` enforces, caught before any physics runs."""
        data = with_override(
            reference_dict(), "receiver.gate_ns", 11.0
        )  # period is 10 ns at 100 MHz
        with pytest.raises(ValidationError, match="exceeds the pulse period"):
            Scenario.model_validate(data)

    def test_a_tabulated_background_outside_the_itu_table_is_refused(self) -> None:
        """1550 nm is outside 530-1500 nm; the physics would raise, so the schema refuses first."""
        data = with_override(reference_dict(), "background", {"condition": "overcast"})
        with pytest.raises(ValidationError, match="tabulated only for wavelengths 530-1500 nm"):
            Scenario.model_validate(data)

    def test_a_tabulated_background_inside_the_table_is_accepted(self) -> None:
        data = with_override(reference_dict(), "background", {"condition": "overcast"})
        data = with_override(data, "transmitter.wavelength_nm", 850.0)
        assert Scenario.model_validate(data).background.condition is SkyCondition.OVERCAST

    def test_another_schema_version_is_refused(self) -> None:
        with pytest.raises(ValidationError, match=f"this code reads version {SCHEMA_VERSION}"):
            Scenario.model_validate(with_override(reference_dict(), "schema_version", 2))

    def test_station_lookup(self) -> None:
        scenario = reference_castelldefels()
        assert scenario.station_names == ("castelldefels",)
        assert scenario.station("castelldefels") is scenario.stations[0]
        with pytest.raises(KeyError, match="no station named 'x'"):
            scenario.station("x")

    def test_physics_dict_drops_the_labels(self) -> None:
        payload = reference_castelldefels().physics_dict()
        assert "name" not in payload and "description" not in payload
        assert payload["channel"]["fade_combination"] == "exact"
        assert payload["time"]["epoch_utc"] == "2025-01-01T00:00:00Z"

    def test_enums_accept_members_and_values(self) -> None:
        assert (
            ChannelSpec(
                zenith_transmittance=1.0, scintillation_regime="weak", fade_combination="additive"
            ).fade_combination
            is FadeCombination.ADDITIVE
        )


# --------------------------------------------------------------------------- #
class TestTheModuleSurface:
    def test_it_imports_nothing_from_system_or_engine(self) -> None:
        """Layering, checked on the AST: ``scenario`` sits above the physics and below the engine."""
        source = Path(str(models_module.__file__)).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
            elif isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
        forbidden = {name for name in imported if name.startswith(("quoss.system", "quoss.engine"))}
        assert forbidden == set()

    def test_every_numeric_field_carries_a_bound(self) -> None:
        """An unbounded float is a plausible wrong number the schema would wave through.

        ``schema_version`` is the one exception, on both members of the ``link``
        union: it is not a quantity but a label checked for equality by its own
        validator.
        """
        unbounded: list[str] = []
        for model in SpecModel.__subclasses__():
            for name, info in model.model_fields.items():
                annotation = info.annotation
                members = (
                    set(get_args(annotation)) if isinstance(annotation, UnionType) else {annotation}
                )
                members.discard(NoneType)
                if not members or not members <= {float, int}:
                    continue
                if name == "schema_version" and model in (Scenario, HorizontalScenario):
                    continue
                if not any(isinstance(m, Gt | Ge | Lt | Le) for m in info.metadata):
                    unbounded.append(f"{model.__name__}.{name}")
        assert unbounded == []


# --------------------------------------------------------------------------- #
class TestTheLinkUnion:
    """``link`` is the discriminator, and ``extra="forbid"`` is what it buys (ADR 0024)."""

    def test_a_horizontal_scenario_cannot_carry_a_downlink_section(self) -> None:
        """The rule of ADR 0021 -- no elevation anywhere -- now asserted by the schema.

        It was asserted by absence in the physics signatures and by an AST walk
        over the module. Here it is a validation error that names the field,
        which is the version a user of a YAML file sees.
        """
        data = ge1_two_terminals().model_dump(mode="json")
        for forbidden in ("passes", "stations", "orbit", "time", "channel", "multi_station"):
            polluted = dict(data)
            polluted[forbidden] = {}
            with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
                TypeAdapter(AnyScenario).validate_python(polluted)

    def test_a_downlink_scenario_cannot_carry_a_horizontal_section(self) -> None:
        data = reference_castelldefels().model_dump(mode="json")
        for forbidden in ("path", "session"):
            polluted = dict(data)
            polluted[forbidden] = {}
            with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
                TypeAdapter(AnyScenario).validate_python(polluted)

    def test_the_tag_picks_the_member_and_nothing_else_does(self) -> None:
        adapter: TypeAdapter[AnyScenario] = TypeAdapter(AnyScenario)
        assert isinstance(
            adapter.validate_python(reference_castelldefels().model_dump(mode="json")), Scenario
        )
        assert isinstance(
            adapter.validate_python(ge1_two_terminals().model_dump(mode="json")),
            HorizontalScenario,
        )

    def test_an_unknown_tag_is_refused_rather_than_guessed(self) -> None:
        data = ge1_two_terminals().model_dump(mode="json")
        data["link"] = "uplink"
        with pytest.raises(ValidationError):
            TypeAdapter(AnyScenario).validate_python(data)

    def test_the_downlink_default_is_a_literal_with_one_legal_value(self) -> None:
        """Why *this* default is defensible where ``scintillation_regime``'s was not.

        A default can only hide a choice somebody might have made differently.
        ``Scenario.link`` is a ``Literal`` with exactly one member, so there is
        no alternative for it to hide -- which is the whole of the argument, and
        is why the horizontal member's tag has no default at all: there the tag
        is what distinguishes it from something else.
        """
        assert not Scenario.model_fields["link"].is_required()
        assert Scenario.model_fields["link"].default is LinkKind.DOWNLINK
        assert get_args(Scenario.model_fields["link"].annotation) == (LinkKind.DOWNLINK,)
        assert HorizontalScenario.model_fields["link"].is_required()

    def test_every_scenarios_file_writes_the_tag_anyway(self, project_root: Path) -> None:
        for path in sorted((project_root / "scenarios").glob("*.yaml")):
            assert "\nlink: " in path.read_text(encoding="utf-8"), path.name


# --------------------------------------------------------------------------- #
class TestTheHorizontalSchema:
    @staticmethod
    def _path(**overrides: object) -> dict[str, object]:
        fields: dict[str, object] = {
            "path_length_m": 1000.0,
            "cn2_m23": 1e-14,
            "wave": "spherical",
            "altitude_m": 30.0,
            "receive_aperture_m": 0.1,
            "extinction_db_per_km": 0.2,
            "scintillation_regime": "weak",
        }
        fields.update(overrides)
        return fields

    def test_exactly_one_way_of_declaring_extinction(self) -> None:
        """``ChannelSpec``'s rule, for the same reason (ADR 0009 gap 14)."""
        assert HorizontalPathSpec(**self._path()).models_extinction is False
        with pytest.raises(ValidationError, match="exactly one of extinction_db_per_km"):
            HorizontalPathSpec(**self._path(extinction_db_per_km=None))
        with pytest.raises(ValidationError, match="exactly one of extinction_db_per_km"):
            HorizontalPathSpec(
                **self._path(
                    extinction=ExtinctionSpec(
                        visibility_km=23.0,
                        visibility_altitude_m=30.0,
                        aerosol_scale_height_m=1200.0,
                        scaling_law="kim-2001",
                    )
                )
            )

    def test_the_wave_and_the_regime_are_required(self) -> None:
        assert HorizontalPathSpec.model_fields["wave"].is_required()
        assert HorizontalPathSpec.model_fields["scintillation_regime"].is_required()
        assert "REQUIRED, no default" in str(HorizontalPathSpec.model_fields["wave"].description)
        assert "2413 m" in str(HorizontalPathSpec.model_fields["scintillation_regime"].description)

    def test_the_declared_number_and_the_model_go_through_one_call(self) -> None:
        """``extinction_db_per_km_at`` is the counterpart of ``zenith_transmittance_at``."""
        log = DegradationLog()
        declared = HorizontalPathSpec(**self._path())
        assert declared.extinction_db_per_km_at(wavelength_m=1.55e-6, degradations=log) == 0.2
        assert len(log) == 0
        modelled = HorizontalPathSpec(
            **self._path(
                extinction_db_per_km=None,
                extinction=ExtinctionSpec(
                    visibility_km=23.0,
                    visibility_altitude_m=30.0,
                    aerosol_scale_height_m=1200.0,
                    scaling_law="kim-2001",
                ),
            )
        )
        assert modelled.models_extinction is True
        assert modelled.extinction_db_per_km_at(
            wavelength_m=1.55e-6, degradations=log
        ) == pytest.approx(0.19199, abs=5e-6)

    def test_the_model_depends_on_the_wavelength_and_the_number_does_not(self) -> None:
        log = DegradationLog()
        modelled = HorizontalPathSpec(
            **self._path(
                extinction_db_per_km=None,
                extinction=ExtinctionSpec(
                    visibility_km=23.0,
                    visibility_altitude_m=30.0,
                    aerosol_scale_height_m=1200.0,
                    scaling_law="kim-2001",
                ),
            )
        )
        infrared = modelled.extinction_db_per_km_at(wavelength_m=1.55e-6, degradations=log)
        near = modelled.extinction_db_per_km_at(wavelength_m=785e-9, degradations=log)
        assert near > infrared
        assert near == pytest.approx(0.465, abs=5e-4)

    def test_the_scale_height_cancels_when_the_visibility_was_measured_at_the_link(self) -> None:
        """An identity, not an approximation: the exponent is exactly zero (ADR 0024)."""
        log = DegradationLog()

        def gamma(scale_height_m: float) -> float:
            spec = HorizontalPathSpec(
                **self._path(
                    extinction_db_per_km=None,
                    extinction=ExtinctionSpec(
                        visibility_km=23.0,
                        visibility_altitude_m=30.0,
                        aerosol_scale_height_m=scale_height_m,
                        scaling_law="kim-2001",
                    ),
                )
            )
            return spec.extinction_db_per_km_at(wavelength_m=1.55e-6, degradations=log)

        assert gamma(1200.0) == gamma(2000.0)

    def test_the_path_length_converts_once_in_the_schema(self) -> None:
        assert HorizontalPathSpec(**self._path()).path_length_km == 1.0

    def test_the_session_duration_is_required_and_says_why(self) -> None:
        assert SessionSpec.model_fields["duration_s"].is_required()
        assert "ADR 0024" in str(SessionSpec.model_fields["duration_s"].description)
        with pytest.raises(ValidationError, match="duration_s"):
            SessionSpec()  # type: ignore[call-arg]

    def test_the_gate_rule_is_the_downlinks_rule(self) -> None:
        """One gate per pulse, on either geometry, from the same sentence."""
        scenario = ge1_two_terminals()
        with pytest.raises(ValidationError, match="One gate per pulse"):
            scenario.model_copy(
                update={"receiver": scenario.receiver.model_copy(update={"gate_ns": 20.0})}
            ).model_validate(
                scenario.model_dump(mode="json")
                | {"receiver": scenario.receiver.model_dump(mode="json") | {"gate_ns": 20.0}}
            )

    def test_a_tabulated_background_outside_the_itu_table_is_refused(self) -> None:
        """ITU-R P.1621-2 Table 1 covers 530-1500 nm whatever brought the light.

        GE-1 is at 1550 nm, which is outside it; a daytime bench at 1064 nm is
        inside and passes. Both directions are checked, because a rule that only
        ever refuses is indistinguishable from one that always refuses.
        """
        data = ge1_two_terminals().model_dump(mode="json")
        data["background"] = {"sky_radiance_w_m2_um_sr": None, "condition": "overcast"}
        with pytest.raises(ValidationError, match="tabulated only for wavelengths"):
            HorizontalScenario.model_validate(data)
        inside = dict(data)
        inside["transmitter"] = dict(data["transmitter"]) | {"wavelength_nm": 1064.0}
        assert (
            HorizontalScenario.model_validate(inside).background.condition is SkyCondition.OVERCAST
        )

    def test_an_unsupported_schema_version_is_refused_rather_than_misread(self) -> None:
        data = ge1_two_terminals().model_dump(mode="json")
        data["schema_version"] = SCHEMA_VERSION + 1
        with pytest.raises(ValidationError, match="is not supported"):
            HorizontalScenario.model_validate(data)

    def test_the_labels_stay_out_of_the_physics_dict(self) -> None:
        payload = ge1_two_terminals().physics_dict()
        assert "name" not in payload and "description" not in payload
        assert payload["link"] == "horizontal"
