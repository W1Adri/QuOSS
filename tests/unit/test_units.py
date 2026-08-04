"""Tests for the unit convention.

The interesting cases are not the arithmetic — they are the two decibel sign
conventions, the boundary values (zero transmittance, unit transmittance) and
the refusal to convert something meaningless.
"""

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from quoss.core.errors import UnitConversionError
from quoss.core.units import (
    M_PER_KM,
    NM_PER_M,
    db_to_linear,
    dbm_to_w,
    deg_to_rad,
    km_to_m,
    linear_to_db,
    loss_db_to_transmittance,
    m_to_km,
    m_to_nm,
    nm_to_m,
    rad_to_deg,
    transmittance_to_loss_db,
    w_to_dbm,
)

# Finite, well-scaled floats. Excludes nan/inf so that a round-trip identity is
# a meaningful assertion rather than a tautology about nan.
finite_db = st.floats(min_value=-200.0, max_value=200.0, allow_nan=False, allow_infinity=False)
positive_ratio = st.floats(min_value=1e-30, max_value=1e30, allow_nan=False, allow_infinity=False)
unit_interval = st.floats(min_value=1e-30, max_value=1.0, allow_nan=False, allow_infinity=False)


class TestSignConventions:
    """The distinction that motivates having two decibel pairs at all."""

    def test_loss_and_gain_conventions_are_reciprocal(self) -> None:
        """A positive dB is a gain as a ratio, an attenuation as a loss."""
        assert db_to_linear(45.0) == pytest.approx(1.0 / loss_db_to_transmittance(45.0))

    def test_a_loss_yields_a_transmittance_below_one(self) -> None:
        """The bug this API exists to prevent: 45 dB of loss is not a gain of 3e4."""
        eta = loss_db_to_transmittance(45.0)
        assert 0.0 < eta < 1.0
        assert eta == pytest.approx(3.1622776601683795e-05)

    def test_zero_db_is_transparent_in_both_conventions(self) -> None:
        assert db_to_linear(0.0) == 1.0
        assert loss_db_to_transmittance(0.0) == 1.0

    def test_lossless_link_reports_positive_zero(self) -> None:
        """Not -0.0, which would read as a gain in a table of losses."""
        loss_db = transmittance_to_loss_db(1.0)
        assert loss_db == 0.0
        assert np.signbit(loss_db) is np.False_ or not np.signbit(loss_db)


class TestBoundaryValues:
    """Zero and one are the values a link budget actually hits."""

    def test_zero_transmittance_is_infinite_loss(self) -> None:
        """A satellite below the horizon: the answer is +inf dB, not an error."""
        assert transmittance_to_loss_db(0.0) == np.inf

    def test_zero_ratio_is_minus_infinity_db(self) -> None:
        assert linear_to_db(0.0) == -np.inf

    def test_zero_power_is_minus_infinity_dbm(self) -> None:
        assert w_to_dbm(0.0) == -np.inf

    def test_boundary_values_emit_no_warning(self) -> None:
        """`filterwarnings = ["error"]` would turn a stray RuntimeWarning into a failure.

        This test is the guard: log10(0) is a legitimate -inf here, and the
        suppression must be scoped tightly enough that nothing else leaks.
        """
        eta = np.array([0.0, 0.5, 1.0])
        loss_db = transmittance_to_loss_db(eta)
        assert np.array_equal(np.isinf(loss_db), np.array([True, False, False]))


class TestRejections:
    """Meaningless conversions raise rather than returning nan."""

    def test_negative_ratio_to_db_raises(self) -> None:
        with pytest.raises(UnitConversionError, match="negative power ratio"):
            linear_to_db(-1.0)

    def test_negative_transmittance_raises(self) -> None:
        with pytest.raises(UnitConversionError, match="negative transmittance"):
            transmittance_to_loss_db(-1e-9)

    def test_transmittance_above_one_raises(self) -> None:
        """Energy creation is a bug upstream, and must not be laundered into dB."""
        with pytest.raises(UnitConversionError, match="above one"):
            transmittance_to_loss_db(1.5)

    def test_transmittance_at_rounding_tolerance_is_accepted(self) -> None:
        """1 + 1e-16 is floating point, not amplification."""
        assert transmittance_to_loss_db(1.0 + 1e-16) == pytest.approx(0.0, abs=1e-12)

    def test_negative_power_raises(self) -> None:
        with pytest.raises(UnitConversionError, match="negative power"):
            w_to_dbm(-1.0)

    def test_one_bad_element_rejects_the_whole_array(self) -> None:
        """Vectorised inputs are validated as a whole; a single bad sample raises."""
        with pytest.raises(UnitConversionError):
            transmittance_to_loss_db(np.array([0.5, 0.9, 2.0]))


class TestScalarShapePreservation:
    """A float in gives a float out, so results stay JSON/YAML-serialisable."""

    @pytest.mark.parametrize(
        "func",
        [
            deg_to_rad,
            rad_to_deg,
            km_to_m,
            m_to_km,
            nm_to_m,
            m_to_nm,
            db_to_linear,
            linear_to_db,
            loss_db_to_transmittance,
            transmittance_to_loss_db,
            dbm_to_w,
            w_to_dbm,
        ],
    )
    def test_scalar_input_returns_builtin_float(self, func) -> None:
        result = func(0.5)
        assert type(result) is float, f"{func.__name__} leaked {type(result).__name__}"

    @pytest.mark.parametrize(
        "func",
        [deg_to_rad, km_to_m, nm_to_m, db_to_linear, loss_db_to_transmittance, dbm_to_w],
    )
    def test_array_input_returns_array_of_same_shape(self, func) -> None:
        x = np.linspace(0.1, 0.9, 7)
        result = func(x)
        assert isinstance(result, np.ndarray)
        assert result.shape == x.shape

    def test_scalar_result_is_json_serialisable(self) -> None:
        """The concrete reason scalars are coerced: np.float64 breaks json/yaml."""
        import json

        assert json.dumps({"loss_db": transmittance_to_loss_db(1e-3)}) == '{"loss_db": 30.0}'


class TestRoundTrips:
    """Property-based: every pair must invert its partner."""

    @given(finite_db)
    def test_db_ratio_round_trip(self, x_db: float) -> None:
        assert linear_to_db(db_to_linear(x_db)) == pytest.approx(x_db, abs=1e-9)

    @given(finite_db)
    def test_loss_round_trip(self, loss_db: float) -> None:
        eta = loss_db_to_transmittance(loss_db)
        # A loss above 0 dB is the physical case; the negative-dB half of the
        # range means gain, which transmittance_to_loss_db rejects by design.
        if eta <= 1.0:
            assert transmittance_to_loss_db(eta) == pytest.approx(loss_db, abs=1e-9)

    @given(unit_interval)
    def test_transmittance_round_trip(self, eta: float) -> None:
        assert loss_db_to_transmittance(transmittance_to_loss_db(eta)) == pytest.approx(
            eta, rel=1e-12
        )

    @given(finite_db)
    def test_dbm_round_trip(self, p_dbm: float) -> None:
        assert w_to_dbm(dbm_to_w(p_dbm)) == pytest.approx(p_dbm, abs=1e-9)

    @given(st.floats(min_value=-360.0, max_value=360.0, allow_nan=False))
    def test_angle_round_trip(self, x_deg: float) -> None:
        assert rad_to_deg(deg_to_rad(x_deg)) == pytest.approx(x_deg, abs=1e-12)

    @given(st.floats(min_value=1e-6, max_value=1e6, allow_nan=False))
    def test_length_round_trips_are_within_one_ulp(self, x: float) -> None:
        """Each direction is one correctly-rounded op, so the pair loses <= 1 ulp.

        Not bit-exact in general — 15/1e9*1e9 is 14.999999999999998 — but it is
        exact for the wavelengths a scenario actually states, which is what
        TestKnownValues pins down.
        """
        assert m_to_km(km_to_m(x)) == pytest.approx(x, rel=1e-15)
        assert m_to_nm(nm_to_m(x)) == pytest.approx(x, rel=1e-15)


class TestMonotonicity:
    """Direction of each conversion, stated so a sign flip cannot pass review."""

    @given(positive_ratio, positive_ratio)
    def test_more_loss_means_less_transmittance(self, a: float, b: float) -> None:
        loss_a, loss_b = min(a, b), max(a, b)
        assert loss_db_to_transmittance(loss_a) >= loss_db_to_transmittance(loss_b)

    @given(positive_ratio, positive_ratio)
    def test_db_ratio_is_increasing(self, a: float, b: float) -> None:
        lo, hi = min(a, b), max(a, b)
        assert linear_to_db(lo) <= linear_to_db(hi)


class TestKnownValues:
    """Values a reader can check by hand."""

    @pytest.mark.parametrize(
        ("loss_db", "eta"),
        [(0.0, 1.0), (10.0, 0.1), (20.0, 0.01), (30.0, 0.001), (3.0, 0.5011872336272722)],
    )
    def test_decade_losses(self, loss_db: float, eta: float) -> None:
        assert loss_db_to_transmittance(loss_db) == pytest.approx(eta)

    @pytest.mark.parametrize(
        ("p_dbm", "p_w"), [(30.0, 1.0), (0.0, 1e-3), (-30.0, 1e-6), (20.0, 0.1)]
    )
    def test_dbm_reference_points(self, p_dbm: float, p_w: float) -> None:
        assert dbm_to_w(p_dbm) == pytest.approx(p_w)

    @pytest.mark.parametrize(("nm", "m"), [(1550.0, 1.55e-6), (810.0, 8.1e-7), (785.0, 7.85e-7)])
    def test_telecom_and_free_space_wavelengths(self, nm: float, m: float) -> None:
        assert nm_to_m(nm) == m

    def test_leo_slant_range_crosses_to_metres(self) -> None:
        """The one internal km->m boundary, at a representative LEO value."""
        assert km_to_m(1200.0) == 1_200_000.0

    def test_scale_factors_are_exact_powers_of_ten(self) -> None:
        assert M_PER_KM == 1e3
        assert NM_PER_M == 1e9

    def test_quarter_turn(self) -> None:
        assert deg_to_rad(90.0) == np.pi / 2
