"""Tests for `quoss.scenario.defaults`.

- ``TestReferenceCastelldefels`` — the builder converts into the physics
  inputs ``tests/system/reference.py`` builds by hand, compared numerically
  (elements, grid, every link-budget argument, and the budgets themselves).
- ``TestTheDefaultsAreTheNtanosConstants`` — every user-unit literal of the
  Ntanos receiver and transmitter converts back to its ``NTANOS_*`` constant.
- ``TestNtanos2021`` — the three stations, the corrected coordinate labels,
  and the printed inclination that is not the sun-synchronous one.
"""

from __future__ import annotations

import numpy as np
import pytest

from quoss.channel.background import NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_DEAD_TIME_S,
    NTANOS_SNSPD_EFFICIENCY,
    NTANOS_SNSPD_GATE_DURATION_S,
    NTANOS_SNSPD_TIMING_JITTER_FWHM_S,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_MINIMUM_ELEVATION_RAD,
    NTANOS_OGS_APERTURES_M,
    NTANOS_ORBIT_HEIGHT_KM,
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    downlink_loss_budget,
    downlink_noise_budget,
)
from quoss.core.errors import DegradationLog
from quoss.core.types import TimeGrid
from quoss.core.units import rad_to_deg
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.kepler import ClassicalElements
from quoss.qkd.base import NTANOS_SOURCE_PULSE_RATE_HZ
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import SecurityParameters
from quoss.scenario.defaults import (
    NTANOS_MINIMUM_ELEVATION_DEG,
    NTANOS_STATIONS,
    ntanos_2021,
    reference_castelldefels,
)

# One conversion is one multiplication by a power of ten: at most one rounding of
# 2^-53 on each side of the comparison. 2^-50 leaves a factor 8 for the arithmetic
# of the constant itself, and nothing more.
ONE_CONVERSION = 2**-50

# The reference module's own constants, retyped: it cannot be imported across test
# directories under importlib mode (brief), and a second transcription that drifts
# from ``tests/system/reference.py`` is exactly what this file would then catch.
STATION_LATITUDE_RAD = float(np.deg2rad(41.2750))
STATION_LONGITUDE_RAD = float(np.deg2rad(1.9875))
STATION_ALTITUDE_KM = 0.030
ORBIT_ALTITUDE_KM = 700.0
ORBIT_ECCENTRICITY = 0.001
ORBIT_RAAN_RAD = float(np.deg2rad(30.0))
EPOCH_JD = 2_460_676.5
WAVELENGTH_M = 1.55e-6
RECEIVE_APERTURE_M = 0.75
GATE_S = 1e-9
MISALIGNMENT_ERROR = 0.01
REFERENCE_MASK_DEG = 10.0


def reference_elements() -> ClassicalElements:
    """Build the elements of ``tests/system/reference.py::geometry`` its way."""
    a = 6378.137 + ORBIT_ALTITUDE_KM
    inclination = float(
        np.ravel(
            sun_synchronous_inclination_rad(semi_major_axis_km=a, eccentricity=ORBIT_ECCENTRICITY)
        )[0]
    )
    return ClassicalElements.from_semi_major_axis(
        semi_major_axis_km=a,
        eccentricity=ORBIT_ECCENTRICITY,
        inclination_rad=inclination,
        raan_rad=ORBIT_RAAN_RAD,
        argp_rad=0.0,
        true_anomaly_rad=0.0,
    )


class TestReferenceCastelldefels:
    def test_elements_match_the_reference_module(self) -> None:
        got = reference_castelldefels().orbit.kepler
        assert got is not None
        expected = reference_elements()
        actual = got.to_elements()
        for attr in (
            "semi_latus_rectum_km",
            "eccentricity",
            "inclination_rad",
            "raan_rad",
            "argp_rad",
            "true_anomaly_rad",
        ):
            assert float(np.ravel(getattr(actual, attr))[0]) == pytest.approx(
                float(np.ravel(getattr(expected, attr))[0]), rel=ONE_CONVERSION
            ), attr

    def test_grid_matches_the_reference_module(self) -> None:
        grid = reference_castelldefels().time.grid()
        expected = TimeGrid.uniform(epoch_jd=EPOCH_JD, duration_s=86_400.0, step_s=1.0)
        assert grid.epoch_jd == expected.epoch_jd
        assert np.array_equal(grid.t_s, expected.t_s)

    def test_station_matches_the_reference_module(self) -> None:
        station = reference_castelldefels().stations[0]
        assert station.latitude_rad == pytest.approx(STATION_LATITUDE_RAD, rel=ONE_CONVERSION)
        assert station.longitude_rad == pytest.approx(STATION_LONGITUDE_RAD, rel=ONE_CONVERSION)
        assert station.altitude_km == pytest.approx(STATION_ALTITUDE_KM, rel=ONE_CONVERSION)
        assert station.receive_aperture_m == RECEIVE_APERTURE_M

    def test_every_link_condition_input_matches_the_reference_module(self) -> None:
        """Scalar by scalar, the arguments ``conditions_at`` passes to the two budgets."""
        s = reference_castelldefels()
        chain = receiver_efficiency(
            NTANOS_SNSPD_EFFICIENCY,
            optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
        )
        assert s.transmitter.wavelength_m == pytest.approx(WAVELENGTH_M, rel=ONE_CONVERSION)
        assert s.transmitter.aperture_m == NTANOS_TRANSMIT_APERTURE_M
        assert s.transmitter.pointing_jitter_rad == pytest.approx(
            NTANOS_POINTING_JITTER_RAD, rel=ONE_CONVERSION
        )
        assert s.transmitter.pulse_rate_hz == NTANOS_SOURCE_PULSE_RATE_HZ
        assert s.channel.zenith_transmittance == 1.0
        assert s.channel.static_loss_db == 0.0
        assert s.channel.outage_probability == 0.01
        assert s.receiver.chain_efficiency == chain
        assert s.receiver.field_of_view_rad == pytest.approx(
            NTANOS_RECEIVER_FIELD_OF_VIEW_RAD, rel=ONE_CONVERSION
        )
        assert s.receiver.filter_bandwidth_m == pytest.approx(
            NTANOS_FILTER_BANDWIDTH_M, rel=ONE_CONVERSION
        )
        assert s.receiver.gate_s == pytest.approx(GATE_S, rel=ONE_CONVERSION)
        assert s.receiver.dark_count_rate_cps == NTANOS_SNSPD_DARK_COUNT_RATE_CPS
        assert s.receiver.detector_count == 2
        assert s.background.sky_radiance_w_m2_um_sr == NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR
        assert s.protocol.misalignment_error == MISALIGNMENT_ERROR
        assert s.protocol.to_protocol() == Bb84DecoyProtocol.ntanos_2021()
        assert s.security.to_security() == SecurityParameters(correctness=1e-10, secrecy=1e-10)
        assert s.passes.minimum_elevation_deg == REFERENCE_MASK_DEG

    def test_the_budgets_evaluate_identically_from_either_source(self) -> None:
        """The strongest form: run the two budgets with scenario-derived and hand-built arguments.

        Tolerance: the inputs agree to one conversion (2^-50); the loss budget is
        smooth in every argument with condition numbers of order ten (the
        pointing fade goes as the square of the beam-to-jitter ratio), so 1e-12
        relative is three orders above what the input disagreement can produce.
        """
        s = reference_castelldefels()
        station = s.stations[0]
        elevation = np.deg2rad(np.array([10.0, 30.0, 60.0, 89.0]))
        slant_range = np.array([2000.0, 1200.0, 800.0, 701.0])
        log_a, log_b = DegradationLog(), DegradationLog()
        from_scenario = downlink_loss_budget(
            elevation,
            range_km=slant_range,
            wavelength_m=s.transmitter.wavelength_m,
            transmit_aperture_m=s.transmitter.aperture_m,
            receive_aperture_m=station.receive_aperture_m,
            zenith_transmittance=s.channel.zenith_transmittance,
            pointing_jitter_rad=s.transmitter.pointing_jitter_rad,
            receiver_efficiency=s.receiver.chain_efficiency,
            outage_probability=s.channel.outage_probability,
            static_loss_db=s.channel.static_loss_db,
            transmit_truncation_ratio=s.transmitter.truncation_ratio,
            fade_combination=s.channel.fade_combination,
            station_height_m=station.station_height_m,
            rms_wind_speed_m_s=station.rms_wind_speed_m_s,
            ground_cn2_m23=station.ground_cn2_m23,
            degradations=log_a,
        )
        chain = receiver_efficiency(
            NTANOS_SNSPD_EFFICIENCY,
            optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
        )
        by_hand = downlink_loss_budget(
            elevation,
            range_km=slant_range,
            wavelength_m=WAVELENGTH_M,
            transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            receive_aperture_m=RECEIVE_APERTURE_M,
            zenith_transmittance=1.0,
            pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
            receiver_efficiency=chain,
            # Written out, because `reference.conditions_at` does NOT pass it: the
            # fixture leaves the turbulence at 0 m while the scenario starts it at
            # the station's 30 m. That single argument is the 457 bits between
            # 432 985 and 433 442 (ADR 0016, tests/e2e/test_reference_scenarios.py).
            station_height_m=30.0,
            degradations=log_b,
        )
        np.testing.assert_allclose(from_scenario.total_db, by_hand.total_db, rtol=1e-12)
        np.testing.assert_allclose(from_scenario.transmittance, by_hand.transmittance, rtol=1e-12)
        assert log_a.to_dicts() == log_b.to_dicts()

        noise_a = downlink_noise_budget(
            s.background.radiance_w_m2_um_sr(s.transmitter.wavelength_m, degradations=log_a),
            wavelength_m=s.transmitter.wavelength_m,
            receive_aperture_m=station.receive_aperture_m,
            field_of_view_full_angle_rad=s.receiver.field_of_view_rad,
            filter_bandwidth_m=s.receiver.filter_bandwidth_m,
            gate_duration_s=s.receiver.gate_s,
            receiver_efficiency=s.receiver.chain_efficiency,
            dark_count_rate_cps=s.receiver.dark_count_rate_cps,
            detector_count=s.receiver.detector_count,
            afterpulse_probability=s.receiver.afterpulse_probability,
            degradations=log_a,
        )
        noise_b = downlink_noise_budget(
            NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR,
            wavelength_m=WAVELENGTH_M,
            receive_aperture_m=RECEIVE_APERTURE_M,
            field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
            filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
            gate_duration_s=GATE_S,
            receiver_efficiency=chain,
            dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            detector_count=2,
            degradations=log_b,
        )
        np.testing.assert_allclose(noise_a.total_per_gate, noise_b.total_per_gate, rtol=1e-12)


class TestTheDefaultsAreTheNtanosConstants:
    """Each user-unit literal, converted back, is its SI constant to within one rounding."""

    def test_receiver_literals(self) -> None:
        rx = reference_castelldefels().receiver
        assert rx.dead_time_s == pytest.approx(NTANOS_SNSPD_DEAD_TIME_S, rel=ONE_CONVERSION)
        assert rx.gate_s == pytest.approx(NTANOS_SNSPD_GATE_DURATION_S, rel=ONE_CONVERSION)
        assert rx.timing_jitter_fwhm_s == pytest.approx(
            NTANOS_SNSPD_TIMING_JITTER_FWHM_S, rel=ONE_CONVERSION
        )
        assert rx.field_of_view_rad == pytest.approx(
            NTANOS_RECEIVER_FIELD_OF_VIEW_RAD, rel=ONE_CONVERSION
        )
        assert rx.filter_bandwidth_m == pytest.approx(NTANOS_FILTER_BANDWIDTH_M, rel=ONE_CONVERSION)

    def test_transmitter_literal(self) -> None:
        tx = reference_castelldefels().transmitter
        assert tx.pointing_jitter_rad == pytest.approx(
            NTANOS_POINTING_JITTER_RAD, rel=ONE_CONVERSION
        )

    def test_the_elevation_floor_literal(self) -> None:
        """20.0 deg written as a literal; ``rad_to_deg`` of the constant is 20.000000000000007."""
        assert NTANOS_MINIMUM_ELEVATION_DEG == 20.0
        assert float(rad_to_deg(NTANOS_MINIMUM_ELEVATION_RAD)) == pytest.approx(
            20.0, rel=ONE_CONVERSION
        )
        assert ntanos_2021(0.75).passes.minimum_elevation_rad == pytest.approx(
            NTANOS_MINIMUM_ELEVATION_RAD, rel=ONE_CONVERSION
        )


class TestNtanos2021:
    @pytest.mark.parametrize(
        ("aperture_m", "name"), [(0.75, "cholomondas"), (1.3, "skinakas"), (2.3, "helmos")]
    )
    def test_the_three_stations(self, aperture_m: float, name: str) -> None:
        scenario = ntanos_2021(aperture_m)
        assert scenario.stations[0].name == name
        assert scenario.stations[0].receive_aperture_m == aperture_m
        assert scenario.name == f"ntanos2021_{name}"
        kepler = scenario.orbit.kepler
        assert kepler is not None
        assert kepler.altitude_km == NTANOS_ORBIT_HEIGHT_KM
        assert kepler.inclination_deg == 97.4
        assert scenario.passes.minimum_elevation_deg == 20.0

    def test_the_apertures_are_the_published_three(self) -> None:
        assert tuple(NTANOS_STATIONS) == NTANOS_OGS_APERTURES_M

    def test_a_fourth_aperture_is_not_a_ntanos_scenario(self) -> None:
        with pytest.raises(ValueError, match=r"aperture_m must be one of \[0.75, 1.3, 2.3\]"):
            ntanos_2021(1.0)

    def test_the_printed_coordinate_labels_are_swapped(self) -> None:
        """Every printed 'longitude' lies in Greece's latitude band and vice versa.

        Greece spans roughly 34-42 N and 19-29 E. The paper's §2 prints
        "longitude: 35.2118°, latitude: 24.8981°" for Skinakas; 35.2 is a
        Greek latitude and 24.9 a Greek longitude, not the other way round.
        """
        for _, latitude_deg, longitude_deg, _ in NTANOS_STATIONS.values():
            assert 34.0 <= latitude_deg <= 42.0
            assert 19.0 <= longitude_deg <= 29.0
            assert not 19.0 <= latitude_deg <= 29.0  # so the labels as printed cannot be right

    def test_the_printed_inclination_is_not_the_sun_synchronous_one(self) -> None:
        """97.4 deg as printed; the SSO condition at 600 km circular gives 97.79 deg.

        Measured here: the difference is 0.39 deg. The scenario carries the
        printed value because it is the paper's parameter.
        """
        sso_deg = float(
            rad_to_deg(
                float(
                    np.ravel(
                        sun_synchronous_inclination_rad(
                            semi_major_axis_km=6378.137 + 600.0, eccentricity=0.0
                        )
                    )[0]
                )
            )
        )
        assert sso_deg == pytest.approx(97.79, abs=0.005)
        assert abs(sso_deg - 97.4) > 0.3
        kepler = ntanos_2021(2.3).orbit.kepler
        assert kepler is not None
        assert not kepler.sun_synchronous
