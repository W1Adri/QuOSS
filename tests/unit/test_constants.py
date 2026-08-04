"""Tests for the physical and geodetic constants.

A constant cannot be "tested" against anything but its source. What *can* be
tested, and is worth testing, is internal consistency: derived values must follow
from the defining ones, the two Earth gravity models must stay distinct, and the
orders of magnitude must reproduce figures a reader already knows. A typo in a
mantissa is exactly the kind of error that survives every other test in the suite
while quietly biasing a paper.
"""

import numpy as np
import pytest

from quoss.core import constants as c


class TestExactSIConstants:
    """The 2019 SI defining constants. Exact, so checkable digit by digit."""

    def test_speed_of_light(self) -> None:
        assert c.SPEED_OF_LIGHT_M_S == 299_792_458.0

    def test_planck(self) -> None:
        assert c.PLANCK_J_S == 6.62607015e-34

    def test_boltzmann(self) -> None:
        assert c.BOLTZMANN_J_K == 1.380649e-23

    def test_elementary_charge(self) -> None:
        assert c.ELEMENTARY_CHARGE_C == 1.602176634e-19

    def test_stefan_boltzmann_follows_from_the_exact_constants(self) -> None:
        """Relation: 2 pi^5 k^4 / (15 h^3 c^2). Derived, so it must be consistent."""
        derived = (
            2.0 * np.pi**5 * c.BOLTZMANN_J_K**4 / (15.0 * c.PLANCK_J_S**3 * c.SPEED_OF_LIGHT_M_S**2)
        )
        assert c.STEFAN_BOLTZMANN_W_M2_K4 == pytest.approx(derived, rel=1e-9)

    def test_photon_energy_at_1550_nm(self) -> None:
        """Energy hc/lambda is ~0.8 eV at telecom wavelength. Sanity of h and c."""
        energy_j = c.PLANCK_J_S * c.SPEED_OF_LIGHT_M_S / 1.55e-6
        energy_ev = energy_j / c.ELEMENTARY_CHARGE_C
        assert energy_ev == pytest.approx(0.7999, rel=1e-3)


class TestWGS84Ellipsoid:
    """Derived ellipsoid parameters must follow from the defining a and f."""

    def test_polar_radius_follows_from_flattening(self) -> None:
        expected = c.WGS84_RADIUS_EQUATORIAL_KM * (1.0 - c.WGS84_FLATTENING)
        assert c.WGS84_RADIUS_POLAR_KM == pytest.approx(expected, rel=1e-15)

    def test_polar_radius_matches_the_published_value(self) -> None:
        """NIMA TR8350.2 quotes the semi-minor axis as 6356.752314245 km."""
        assert c.WGS84_RADIUS_POLAR_KM == pytest.approx(6356.752314245, abs=1e-6)

    def test_eccentricity_squared_follows_from_flattening(self) -> None:
        expected = c.WGS84_FLATTENING * (2.0 - c.WGS84_FLATTENING)
        assert c.WGS84_ECCENTRICITY_SQ == pytest.approx(expected, rel=1e-15)

    def test_eccentricity_matches_the_published_value(self) -> None:
        """NIMA TR8350.2 quotes the first eccentricity as 8.1819190842622e-2."""
        assert c.WGS84_ECCENTRICITY == pytest.approx(8.1819190842622e-2, rel=1e-11)

    def test_earth_is_nearly_spherical(self) -> None:
        """Flattening is ~1/298: the poles sit ~21 km closer than the equator."""
        assert 20.0 < c.WGS84_RADIUS_EQUATORIAL_KM - c.WGS84_RADIUS_POLAR_KM < 22.0


class TestGravityModelsStayDistinct:
    """EGM96 for physics, WGS-72 for SGP4. Conflating them is a silent bias."""

    def test_the_two_models_are_not_the_same_numbers(self) -> None:
        """If these ever became equal, someone deleted the distinction by accident."""
        assert c.EGM96_MU_KM3_S2 != c.WGS72_MU_KM3_S2
        assert c.WGS84_RADIUS_EQUATORIAL_KM != c.WGS72_RADIUS_EQUATORIAL_KM
        assert c.EGM96_J2 != c.WGS72_J2

    def test_the_two_models_agree_to_the_expected_precision(self) -> None:
        """They describe the same planet: WGS-72 is less accurate, not different."""
        assert c.WGS72_MU_KM3_S2 == pytest.approx(c.EGM96_MU_KM3_S2, rel=1e-6)
        assert c.WGS72_RADIUS_EQUATORIAL_KM == pytest.approx(c.WGS84_RADIUS_EQUATORIAL_KM, rel=1e-6)
        assert c.WGS72_J2 == pytest.approx(c.EGM96_J2, rel=1e-4)

    def test_the_three_reference_radii_are_three_different_numbers(self) -> None:
        """Geodesy WGS-84, gravity EGM96, SGP4 WGS-72 — three radii, three jobs.

        A harmonic means nothing without the radius its expansion used, so
        collapsing any two of these would silently redefine every J_n that
        multiplies (R/r)^n.
        """
        radii = {
            c.WGS84_RADIUS_EQUATORIAL_KM,
            c.EGM96_RADIUS_EQUATORIAL_KM,
            c.WGS72_RADIUS_EQUATORIAL_KM,
        }
        assert len(radii) == 3

    def test_the_egm96_radius_is_within_a_metre_of_the_wgs84_one(self) -> None:
        """0.7 m apart: the same planet, measured twice.

        Worth 2.2e-7 relative in a J2 term — negligible against that model's own
        truncation, which is why the distinction is about meaning rather than
        accuracy.
        """
        gap_m = abs(c.EGM96_RADIUS_EQUATORIAL_KM - c.WGS84_RADIUS_EQUATORIAL_KM) * 1e3
        assert 0.5 < gap_m < 1.0

    def test_zonal_harmonic_hierarchy(self) -> None:
        """J2 dominates J3 and J4 by ~3 orders of magnitude; J3 and J4 are negative."""
        assert c.EGM96_J2 > 0.0
        assert c.EGM96_J3 < 0.0
        assert c.EGM96_J4 < 0.0
        assert abs(c.EGM96_J2) > 100.0 * abs(c.EGM96_J3)
        assert abs(c.EGM96_J2) > 100.0 * abs(c.EGM96_J4)

    def test_wgs72_zonal_harmonic_hierarchy(self) -> None:
        assert c.WGS72_J2 > 0.0
        assert c.WGS72_J3 < 0.0
        assert c.WGS72_J4 < 0.0


class TestOrbitalSanity:
    """The constants must reproduce orbital periods a reader already knows."""

    def test_iss_orbital_period(self) -> None:
        """Period 2 pi sqrt(a^3/mu): at 420 km altitude the ISS takes ~92.8 min."""
        a_km = c.WGS84_RADIUS_EQUATORIAL_KM + 420.0
        period_s = 2.0 * np.pi * np.sqrt(a_km**3 / c.EGM96_MU_KM3_S2)
        assert period_s / 60.0 == pytest.approx(92.8, abs=0.2)

    def test_typical_qkd_satellite_period(self) -> None:
        """At 550 km, the sun-synchronous regime QuOSS targets: ~95.6 min."""
        a_km = c.WGS84_RADIUS_EQUATORIAL_KM + 550.0
        period_s = 2.0 * np.pi * np.sqrt(a_km**3 / c.EGM96_MU_KM3_S2)
        assert period_s / 60.0 == pytest.approx(95.6, abs=0.2)

    def test_geostationary_radius(self) -> None:
        """A sidereal-day orbit has a = 42164 km. Ties mu to the rotation rate."""
        a_km = (c.EGM96_MU_KM3_S2 * (c.MEAN_SIDEREAL_DAY_S / (2.0 * np.pi)) ** 2) ** (1.0 / 3.0)
        assert a_km == pytest.approx(42164.0, abs=1.0)


class TestTimeAndRotation:
    """Time scales and their relations."""

    def test_mean_sidereal_day_is_23h56m04s(self) -> None:
        """The familiar tabulated form, itself quoted to 0.1 ms."""
        assert c.MEAN_SIDEREAL_DAY_S == pytest.approx(23 * 3600 + 56 * 60 + 4.0905, abs=1e-4)

    def test_mean_sidereal_day_is_close_to_but_not_equal_to_two_pi_over_omega(self) -> None:
        """Guards a mantissa typo without pretending the two are the same quantity.

        ``2 pi / omega`` is a rotation against an inertial direction; the mean
        sidereal day is against the precessing equinox. They agree to ~1.2e-7
        relative, so this catches a wrong digit while documenting the gap. See the
        note on MEAN_SIDEREAL_DAY_S for why neither is derived from the other.
        """
        inertial_period_s = 2.0 * np.pi / c.EARTH_ROTATION_RAD_S
        assert c.MEAN_SIDEREAL_DAY_S == pytest.approx(inertial_period_s, rel=2e-7)
        assert c.MEAN_SIDEREAL_DAY_S != inertial_period_s

    def test_mean_sidereal_day_is_shorter_than_the_solar_day(self) -> None:
        """By ~3 min 56 s: the well-known figure, and a check on both constants."""
        assert c.SECONDS_PER_DAY - c.MEAN_SIDEREAL_DAY_S == pytest.approx(235.9, abs=0.5)

    def test_seconds_per_day(self) -> None:
        assert c.SECONDS_PER_DAY == 86_400.0

    def test_j2000_epoch(self) -> None:
        assert c.JD_J2000 == 2_451_545.0

    def test_mjd_offset(self) -> None:
        """Subtracting the offset from JD(J2000) must give MJD 51544.5."""
        assert c.JD_J2000 - c.MJD_OFFSET_JD == pytest.approx(51544.5)

    def test_unix_epoch_is_thirty_years_before_j2000(self) -> None:
        """From 1970-01-01 to 2000-01-01 is 10957.5 days, including the noon offset."""
        assert c.JD_J2000 - c.JD_UNIX_EPOCH == pytest.approx(10_957.5)

    def test_equatorial_surface_speed(self) -> None:
        """Rotation gives ~465 m/s at the equator: the ground-station Doppler term."""
        speed_m_s = c.EARTH_ROTATION_RAD_S * c.WGS84_RADIUS_EQUATORIAL_KM * 1e3
        assert speed_m_s == pytest.approx(465.1, abs=0.5)


def test_all_exported_names_exist() -> None:
    """__all__ must not advertise a name the module does not define."""
    for name in c.__all__:
        assert hasattr(c, name), f"constants.__all__ lists undefined name {name!r}"


def test_every_constant_is_documented() -> None:
    """Each exported constant carries a docstring stating its unit and source.

    The autogenerated physics manual reads these; an undocumented constant would
    appear in the manual as a bare number.
    """
    import ast
    import pathlib

    source = pathlib.Path(c.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    documented: set[str] = set()
    body = tree.body
    for i, node in enumerate(body):
        if not isinstance(node, ast.AnnAssign | ast.Assign):
            continue
        following = body[i + 1] if i + 1 < len(body) else None
        has_doc = (
            isinstance(following, ast.Expr)
            and isinstance(following.value, ast.Constant)
            and isinstance(following.value.value, str)
        )
        if not has_doc:
            continue
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0]
        if isinstance(target, ast.Name):
            documented.add(target.id)

    undocumented = [n for n in c.__all__ if n not in documented]
    assert not undocumented, f"constants without a docstring: {undocumented}"
