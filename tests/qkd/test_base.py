"""Tests for `quoss.qkd.base`.

There is no physics in the module, so there is no V2 or V3 here: nothing in it
reproduces a published number. What it holds instead is a **boundary**, and the
tests are organised by the mistake each part of that boundary exists to stop.

- ``TestBinaryEntropy`` — **V1**. The one function in the module that computes
  anything, checked against its own definition evaluated by an independent path
  (the standard library's ``math.log2`` instead of ``scipy.special.xlogy``), plus
  the two properties that make it usable — symmetry about one half, and a finite
  answer with no warning at the endpoints, where the naive product is
  ``0 * -inf``.
- ``TestTheMeanIsNotAProbability`` — the first trap, **measured against the
  channel itself** rather than asserted: the noise budget of
  ``quoss.channel.link_budget`` is run for the reference receiver at night and in
  daylight, and the error made by reading its mean as a probability comes out at
  4e-5 % and 0.38 %, and at 3.58 % on the 2.3 m telescope.
- ``TestLinkConditions`` / ``TestLinkConditionsRejectsBadInput`` — the container
  and every way of building an impossible one, including the empty pass that
  four channel modules had to be fixed for.
- ``TestKeyRate`` / ``TestKeyRateRejectsBadInput`` — the result, and the ordering
  chain ``gain >= sifted >= secure >= 0`` that catches an argument in the wrong
  slot. The slack allowed on that chain is exercised from both sides.
- ``TestTheProtocolContract`` — the three plumbing checks
  ``QkdProtocol.key_rate`` makes, each with a deliberately broken implementation
  behind it, because a check nobody has seen fail is a check nobody knows works.
- ``TestProtocolRegistry`` — including the negative control that matters most
  here: no name for an unimplemented protocol is reachable, today or after any
  import.
- ``TestModuleSurface`` — that the boundary has not acquired protocol parameters,
  and that the module says what it leaves out.

The stand-in protocol used throughout is ``_Illustrative``. It is **not** a QKD
model and is not asked to be one; it exists so that the interface has something
to be exercised with. The real one is ``bb84.py``.
"""

from __future__ import annotations

import dataclasses
import inspect
import math

import numpy as np
import pytest

from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
    NTANOS_SNSPD_EFFICIENCY,
    NTANOS_SNSPD_GATE_DURATION_S,
    click_probability,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    NTANOS_FILTER_BANDWIDTH_M,
    NTANOS_OGS_APERTURES_M,
    NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
    downlink_noise_budget,
)
from quoss.core.errors import ConfigurationError, DegradationLog, DomainError
from quoss.core.types import FloatArray, FloatLike
from quoss.qkd.base import (
    NTANOS_SOURCE_PULSE_RATE_HZ,
    PROTOCOLS,
    KeyRate,
    KeyRegime,
    LinkConditions,
    ProtocolRegistry,
    QkdProtocol,
    binary_entropy,
)

# The reference downlink of `channel/link_budget.py`, zenith, 0.75 m telescope:
# 28.541 dB end to end, and the night noise its own noise budget returns.
REFERENCE_TRANSMITTANCE = 1.3993e-03
REFERENCE_NIGHT_NOISE_PER_GATE = 7.8797e-07


def conditions(
    *,
    transmittance: FloatLike = REFERENCE_TRANSMITTANCE,
    noise_counts_per_gate: FloatLike = REFERENCE_NIGHT_NOISE_PER_GATE,
    misalignment_error: FloatLike = 0.01,
    pulse_rate_hz: float = NTANOS_SOURCE_PULSE_RATE_HZ,
    gate_duration_s: float = NTANOS_SNSPD_GATE_DURATION_S,
) -> LinkConditions:
    """Build reference conditions with one thing changed."""
    return LinkConditions(
        transmittance=transmittance,
        noise_counts_per_gate=noise_counts_per_gate,
        misalignment_error=misalignment_error,
        pulse_rate_hz=pulse_rate_hz,
        gate_duration_s=gate_duration_s,
    )


class _Illustrative(QkdProtocol):
    """A stand-in, not a QKD model.

    Single-photon BB84 with no decoy machinery and no finite-key correction:
    enough structure that the interface is exercised on numbers with the right
    shape and the right ordering, and nothing that should be read as physics.
    """

    name = "test-illustrative"

    def _key_rate(self, conditions: LinkConditions, *, degradations: DegradationLog) -> KeyRate:
        noise = conditions.background_yield
        signal = conditions.transmittance
        gain = 1.0 - (1.0 - signal) * (1.0 - noise)
        # A background click is uncorrelated with the bit, so it is wrong half
        # the time; a misaligned reference corrupts the signal photon itself.
        qber = np.minimum(0.5, (0.5 * noise + conditions.misalignment_error * signal) / gain)
        sifted = 0.5 * gain
        secure = sifted * np.maximum(0.0, 1.0 - 2.0 * binary_entropy(qber))
        return KeyRate(
            protocol=self.name,
            regime=KeyRegime.ASYMPTOTIC,
            pulse_rate_hz=conditions.pulse_rate_hz,
            gain=gain,
            qber=qber,
            sifted_per_pulse=sifted,
            secure_per_pulse=secure,
        )


class TestBinaryEntropy:
    def test_the_three_values_that_can_be_checked_by_hand(self) -> None:
        assert float(binary_entropy(0.0)) == 0.0
        assert float(binary_entropy(1.0)) == 0.0
        assert float(binary_entropy(0.5)) == 1.0

    def test_it_matches_its_own_definition_by_an_independent_path(self) -> None:
        """``math.log2`` instead of ``scipy.special.xlogy``: same formula, other code.

        Not a reference value — the definition is the reference. What this
        catches is a wrong constant in the nat-to-bit conversion or a swapped
        argument in ``xlogy``, neither of which the endpoint values above would
        notice, because both are zero there.
        """
        for x in (1e-09, 1e-04, 0.011, 0.11, 0.25, 0.4999, 0.5, 0.9):
            expected = -x * math.log2(x) - (1.0 - x) * math.log2(1.0 - x)
            assert float(binary_entropy(x)) == pytest.approx(expected, rel=1e-12)

    def test_it_is_symmetric_about_one_half(self) -> None:
        x = np.linspace(0.0, 1.0, 101)
        assert binary_entropy(x) == pytest.approx(binary_entropy(1.0 - x), abs=1e-15)

    def test_one_bit_is_the_maximum_and_it_is_reached_only_at_one_half(self) -> None:
        x = np.linspace(0.0, 1.0, 1001)
        h = binary_entropy(x)
        assert float(np.max(h)) == 1.0
        assert np.argmax(h) == 500

    def test_the_endpoints_produce_no_warning_and_no_nan(self) -> None:
        """The reason ``xlogy`` is used at all.

        ``x * log(x)`` at zero is ``0 * -inf``: numpy returns ``nan`` and emits
        a RuntimeWarning, and this suite runs with ``filterwarnings = ["error"]``,
        so the warning is a failure and not a thing to ignore later. Guarding
        with ``np.where`` would not help — both branches are evaluated before the
        choice is made.
        """
        values = binary_entropy(np.array([0.0, 1.0, 1e-300, 1.0 - 1e-16]))
        assert np.all(np.isfinite(values))

    def test_zero_is_positive_zero(self) -> None:
        """``-0.0`` compares equal to zero and prints as a negative entropy."""
        assert math.copysign(1.0, float(binary_entropy(0.0))) == 1.0
        assert math.copysign(1.0, float(binary_entropy(1.0))) == 1.0

    def test_the_eleven_per_cent_threshold_is_solved_rather_than_quoted(self) -> None:
        """Where ``h(E) = 1/2``, which is where the one-way rate ``1 - 2h`` vanishes.

        The familiar BB84 asymptotic error threshold. Derived here with a root
        finder rather than transcribed, so that the number in the docstring is
        the number the function produces.
        """
        from scipy.optimize import brentq

        threshold = brentq(lambda e: 1.0 - 2.0 * float(binary_entropy(e)), 1e-12, 0.5)
        assert threshold == pytest.approx(0.1100278644, rel=1e-09)
        assert round(float(binary_entropy(0.11)), 6) == 0.499916

    def test_it_is_vectorised_and_shape_preserving(self) -> None:
        for shape in ((0,), (5,), (3, 4)):
            assert binary_entropy(np.full(shape, 0.25)).shape == shape

    @pytest.mark.parametrize("bad", [-1e-09, 1.0 + 1e-09, 11.0])
    def test_it_refuses_anything_outside_zero_to_one(self, bad: float) -> None:
        with pytest.raises(DomainError, match="a fraction, not a percentage"):
            binary_entropy(bad)

    def test_it_refuses_nan(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            binary_entropy(np.array([0.1, np.nan]))


class TestTheMeanIsNotAProbability:
    """The first trap, measured against the module that produces the mean."""

    @staticmethod
    def _noise_mean(*, radiance: float, aperture_m: float) -> float:
        chain = receiver_efficiency(
            NTANOS_SNSPD_EFFICIENCY,
            optical_loss_db=NTANOS_RECEIVER_LOSS_DB + NTANOS_FILTER_INSERTION_LOSS_DB,
        )
        budget = downlink_noise_budget(
            radiance,
            wavelength_m=1.55e-06,
            receive_aperture_m=aperture_m,
            field_of_view_full_angle_rad=NTANOS_RECEIVER_FIELD_OF_VIEW_RAD,
            filter_bandwidth_m=NTANOS_FILTER_BANDWIDTH_M,
            gate_duration_s=NTANOS_SNSPD_GATE_DURATION_S,
            receiver_efficiency=chain,
            dark_count_rate_cps=NTANOS_SNSPD_DARK_COUNT_RATE_CPS,
            detector_count=2,
            degradations=DegradationLog(),
        )
        return float(budget.total_per_gate)

    def test_the_night_mean_of_the_reference_receiver_is_what_this_file_assumes(
        self,
    ) -> None:
        """Ties ``REFERENCE_NIGHT_NOISE_PER_GATE`` to the channel that produces it."""
        mean = self._noise_mean(radiance=1.5e-04, aperture_m=NTANOS_OGS_APERTURES_M[0])
        assert mean == pytest.approx(REFERENCE_NIGHT_NOISE_PER_GATE, rel=1e-04)

    def test_at_night_the_two_readings_agree_to_four_parts_in_ten_million(self) -> None:
        mean = self._noise_mean(radiance=1.5e-04, aperture_m=NTANOS_OGS_APERTURES_M[0])
        yield_0 = float(conditions(noise_counts_per_gate=mean).background_yield)
        assert (mean - yield_0) / yield_0 == pytest.approx(3.94e-07, rel=0.05)

    def test_in_daylight_the_linear_reading_is_0_38_and_3_58_per_cent_high(self) -> None:
        """The measured cost of the confusion, on the two published telescopes.

        6 W/(m^2 um sr) is the top of the clear-sky daylight bracket Ntanos et
        al. quote at 1550 nm. Neither number is alarming on its own, which is the
        point: the mistake does not announce itself, and it flatters the link.
        """
        errors = {}
        for aperture in (NTANOS_OGS_APERTURES_M[0], NTANOS_OGS_APERTURES_M[2]):
            mean = self._noise_mean(radiance=6.0, aperture_m=aperture)
            yield_0 = float(conditions(noise_counts_per_gate=mean).background_yield)
            errors[aperture] = round((mean / yield_0 - 1.0) * 100.0, 2)
        assert errors == {0.75: 0.38, 2.3: 3.58}

    def test_the_yield_is_the_detectors_own_click_law(self) -> None:
        """One Poisson click law in the project, not two that can drift apart."""
        mean = np.array([0.0, 1e-06, 1e-03, 3.42])
        expected = click_probability(0.0, efficiency=1.0, dark_counts_per_gate=mean)
        assert conditions(noise_counts_per_gate=mean).background_yield == pytest.approx(
            expected, rel=0.0, abs=0.0
        )

    def test_the_yield_is_bounded_by_one_where_the_mean_is_not(self) -> None:
        """The ITU bright-sunshine case, whose "probability" is 3.42."""
        y0 = float(conditions(noise_counts_per_gate=3.42).background_yield)
        assert y0 == pytest.approx(float(-np.expm1(-3.42)), rel=0.0, abs=0.0)
        assert round(y0, 5) == 0.96729
        assert y0 < 1.0


class TestLinkConditions:
    def test_scalars_broadcast_against_arrays(self) -> None:
        c = conditions(transmittance=np.full(7, REFERENCE_TRANSMITTANCE))
        assert c.shape == (7,)
        assert c.size == 7
        assert c.noise_counts_per_gate.shape == (7,)
        assert c.misalignment_error.shape == (7,)

    def test_a_single_instant_is_zero_dimensional(self) -> None:
        c = conditions()
        assert c.shape == ()
        assert c.size == 1

    def test_the_stored_arrays_are_read_only(self) -> None:
        c = conditions(transmittance=np.full(3, 1e-03))
        for array in (c.transmittance, c.noise_counts_per_gate, c.misalignment_error):
            with pytest.raises(ValueError, match="read-only"):
                array[0] = 0.5

    def test_editing_the_callers_array_does_not_move_the_link(self) -> None:
        """Aliasing, which freezing alone would not close.

        A validator that returns its argument unchanged leaves the container
        sharing the caller's buffer, and the caller keeps a writeable reference
        to it. The copy is what closes that.
        """
        mine = np.full(3, 1e-03)
        c = conditions(transmittance=mine)
        mine[0] = 1.0
        assert float(c.transmittance[0]) == 1e-03
        assert not np.shares_memory(c.transmittance, mine)

    def test_an_empty_pass_is_legal_and_stays_empty(self) -> None:
        """A pass segmented before its first visible sample.

        Four channel modules raised ``zero-size array to reduction operation``
        on this, each in a ``np.max`` guarding a warning, and none of their own
        tests caught it because each was exercised with real samples. Anything
        downstream of them inherits the obligation.
        """
        c = conditions(transmittance=np.empty(0), noise_counts_per_gate=np.empty(0))
        assert c.shape == (0,)
        assert c.size == 0
        assert c.background_yield.shape == (0,)
        assert "empty" in repr(c)
        rate = _Illustrative().key_rate(c, degradations=DegradationLog())
        assert rate.shape == (0,)
        assert rate.secure_bit_s.shape == (0,)

    def test_the_pulse_period_is_the_reciprocal_of_the_rate(self) -> None:
        assert conditions().pulse_period_s == pytest.approx(1e-08, rel=1e-15)

    def test_the_repr_names_the_shape_the_ranges_and_the_clock(self) -> None:
        text = repr(conditions(transmittance=np.array([1e-04, 1e-03])))
        assert "shape=(2,)" in text
        assert "0.0001, 0.001" in text
        assert "100000000.0" in text


class TestLinkConditionsRejectsBadInput:
    @pytest.mark.parametrize("bad", [0.0, -1e-12, 1.0 + 1e-09, 30.0])
    def test_a_transmittance_outside_zero_to_one(self, bad: float) -> None:
        with pytest.raises(DomainError, match="not a decibel figure"):
            conditions(transmittance=bad)

    def test_a_negative_noise_mean(self) -> None:
        with pytest.raises(DomainError, match="not a probability"):
            conditions(noise_counts_per_gate=-1e-12)

    def test_a_noise_mean_above_one_is_accepted(self) -> None:
        """Because it is a mean. 3.42 counts per gate is a real operating point."""
        assert float(conditions(noise_counts_per_gate=3.42).noise_counts_per_gate) == 3.42

    @pytest.mark.parametrize("bad", [-1e-12, 0.5 + 1e-09, 1.0])
    def test_a_misalignment_outside_zero_to_a_half(self, bad: float) -> None:
        with pytest.raises(DomainError, match="inverted labelling"):
            conditions(misalignment_error=bad)

    @pytest.mark.parametrize("bad", [0.0, -1.0, float("inf"), float("nan")])
    def test_a_pulse_rate_that_is_not_a_rate(self, bad: float) -> None:
        with pytest.raises(DomainError, match="pulse_rate_hz"):
            conditions(pulse_rate_hz=bad)

    @pytest.mark.parametrize("bad", [0.0, -1e-09, float("nan")])
    def test_a_gate_that_is_not_a_duration(self, bad: float) -> None:
        with pytest.raises(DomainError, match="gate_duration_s must be finite"):
            conditions(gate_duration_s=bad)

    def test_a_gate_wider_than_the_pulse_period(self) -> None:
        """Gates that overlap: every count attributed to two pulses."""
        with pytest.raises(DomainError, match="gates overlap"):
            conditions(pulse_rate_hz=1e09, gate_duration_s=2.0 * NTANOS_SNSPD_GATE_DURATION_S)

    def test_a_gate_exactly_filling_the_period_is_allowed(self) -> None:
        """Continuous gating is a real receiver, and the boundary is not an error."""
        assert conditions(pulse_rate_hz=1e09, gate_duration_s=1e-09).gate_duration_s == 1e-09

    @pytest.mark.parametrize(
        "field", ["transmittance", "noise_counts_per_gate", "misalignment_error"]
    )
    def test_non_finite_values_anywhere(self, field: str) -> None:
        with pytest.raises(DomainError, match=f"{field} contains non-finite"):
            conditions(**{field: np.array([0.01, np.nan])})  # type: ignore[arg-type]

    def test_shapes_that_do_not_broadcast(self) -> None:
        with pytest.raises(DomainError, match="outer product"):
            conditions(transmittance=np.full(3, 1e-03), noise_counts_per_gate=np.zeros(4))


def key_rate(**overrides: object) -> KeyRate:
    """Build a well-formed result with one thing changed."""
    fields: dict[str, object] = {
        "protocol": "test-illustrative",
        "regime": KeyRegime.ASYMPTOTIC,
        "pulse_rate_hz": NTANOS_SOURCE_PULSE_RATE_HZ,
        "gain": np.array([1e-03, 1e-04]),
        "qber": np.array([0.01, 0.2]),
        "sifted_per_pulse": np.array([5e-04, 5e-05]),
        "secure_per_pulse": np.array([2e-04, 0.0]),
    }
    fields.update(overrides)
    return KeyRate(**fields)  # type: ignore[arg-type]


class TestKeyRate:
    def test_the_per_second_rates_are_derived_and_cannot_disagree(self) -> None:
        rate = key_rate()
        assert rate.secure_bit_s == pytest.approx(
            rate.secure_per_pulse * NTANOS_SOURCE_PULSE_RATE_HZ
        )
        assert rate.sifted_bit_s == pytest.approx(
            rate.sifted_per_pulse * NTANOS_SOURCE_PULSE_RATE_HZ
        )
        assert float(rate.secure_bit_s[0]) == pytest.approx(2e04)

    def test_has_key_is_strict_positivity(self) -> None:
        assert list(key_rate().has_key) == [True, False]

    def test_it_is_frozen_and_its_arrays_are_read_only(self) -> None:
        rate = key_rate()
        with pytest.raises(dataclasses.FrozenInstanceError):
            rate.pulse_rate_hz = 1.0  # type: ignore[misc]
        with pytest.raises(ValueError, match="read-only"):
            rate.secure_per_pulse[0] = 1.0

    def test_the_regime_accepts_its_own_string(self) -> None:
        """Because a scenario file writes ``finite``, not an enum member."""
        assert key_rate(regime="finite").regime is KeyRegime.FINITE

    def test_scalars_and_arrays_broadcast_to_one_shape(self) -> None:
        rate = key_rate(qber=0.01, secure_per_pulse=0.0)
        assert rate.shape == (2,)
        assert rate.qber.shape == (2,)

    def test_the_repr_names_the_protocol_the_regime_and_the_rate_in_bits(self) -> None:
        """A result far from the call that made it has to identify itself."""
        text = repr(key_rate())
        assert "'test-illustrative'" in text
        assert "asymptotic" in text
        assert "shape=(2,)" in text
        assert "secure_bit_s=[0, 20000]" in text


class TestKeyRateRejectsBadInput:
    def test_an_empty_protocol_name(self) -> None:
        with pytest.raises(DomainError, match="non-empty name"):
            key_rate(protocol="")

    def test_a_regime_that_names_nothing(self) -> None:
        with pytest.raises(ValueError, match="asymptotic-ish"):
            key_rate(regime="asymptotic-ish")

    def test_a_pulse_rate_that_is_not_a_rate(self) -> None:
        with pytest.raises(DomainError, match="pulse_rate_hz"):
            key_rate(pulse_rate_hz=0.0)

    def test_a_gain_above_one(self) -> None:
        """The characteristic slip: a count rate in a probability's slot."""
        with pytest.raises(DomainError, match="5e-3, not 5e5"):
            key_rate(gain=5e05, sifted_per_pulse=0.0, secure_per_pulse=0.0)

    def test_a_qber_above_one_half(self) -> None:
        with pytest.raises(DomainError, match="inverted bit convention"):
            key_rate(qber=0.6)

    def test_a_sifted_rate_above_the_gain(self) -> None:
        with pytest.raises(DomainError, match="Sifting discards clicks and creates none"):
            key_rate(sifted_per_pulse=np.array([2e-03, 1e-05]))

    def test_a_negative_secret_rate(self) -> None:
        """Where the formula goes negative there is no key; the protocol clamps."""
        with pytest.raises(DomainError, match="negative key volume"):
            key_rate(secure_per_pulse=np.array([-1e-09, 0.0]))

    def test_a_secret_rate_above_the_sifted_rate(self) -> None:
        with pytest.raises(DomainError, match="both shrink the sifted key"):
            key_rate(secure_per_pulse=np.array([6e-04, 0.0]))

    def test_the_ordering_slack_absorbs_rounding_and_nothing_more(self) -> None:
        """Both sides of the slack, so it is a threshold and not a licence.

        The three rates are computed from one another, so an equality can lose
        its last bit; a violation of a part in a million cannot come from that.
        """
        sifted = np.array([5e-04, 5e-05])
        key_rate(secure_per_pulse=sifted * (1.0 + 1e-13))
        with pytest.raises(DomainError, match="both shrink the sifted key"):
            key_rate(secure_per_pulse=sifted * (1.0 + 1e-06))

    @pytest.mark.parametrize("field", ["gain", "qber", "sifted_per_pulse", "secure_per_pulse"])
    def test_non_finite_values_anywhere(self, field: str) -> None:
        with pytest.raises(DomainError, match=f"{field} contains non-finite"):
            key_rate(**{field: np.array([np.nan, 0.0])})

    def test_shapes_that_do_not_broadcast(self) -> None:
        with pytest.raises(DomainError, match="must broadcast"):
            key_rate(qber=np.full(3, 0.01))


class TestTheProtocolContract:
    def test_the_interface_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError, match="abstract"):
            QkdProtocol()  # type: ignore[abstract]

    def test_a_conforming_protocol_returns_a_rate_of_the_right_shape(self) -> None:
        c = conditions(transmittance=np.geomspace(1e-05, 1e-02, 16))
        rate = _Illustrative().key_rate(c, degradations=DegradationLog())
        assert rate.shape == (16,)
        assert rate.protocol == "test-illustrative"
        assert rate.regime is KeyRegime.ASYMPTOTIC
        assert np.all(rate.secure_per_pulse <= rate.sifted_per_pulse)

    def test_the_illustrative_protocol_loses_the_key_as_the_link_closes(self) -> None:
        """Not a claim about BB84 — a check that the interface carries a trend.

        The noise is fixed, so as the transmittance falls the background takes
        over the clicks, the QBER rises to one half and the rate reaches zero
        and stays there rather than going negative.
        """
        c = conditions(transmittance=np.geomspace(1e-09, 1e-02, 64))
        rate = _Illustrative().key_rate(c, degradations=DegradationLog())
        assert bool(rate.has_key[-1])
        assert not bool(rate.has_key[0])
        assert float(rate.qber[0]) == pytest.approx(0.5, abs=1e-03)
        assert np.all(np.diff(rate.secure_per_pulse) >= 0.0)

    def test_the_degradation_log_reaches_the_implementation(self) -> None:
        class _Recording(_Illustrative):
            name = "test-recording"

            def _key_rate(
                self, conditions: LinkConditions, *, degradations: DegradationLog
            ) -> KeyRate:
                degradations.warn("test.noted", "Noted.", where="test")
                rate = super()._key_rate(conditions, degradations=degradations)
                return dataclasses.replace(rate, protocol=self.name)

        log = DegradationLog()
        _Recording().key_rate(conditions(), degradations=log)
        assert [entry.code for entry in log] == ["test.noted"]

    def test_a_result_labelled_with_another_protocols_name_is_refused(self) -> None:
        class _Mislabelled(_Illustrative):
            name = "test-mislabelled"

            def _key_rate(
                self, conditions: LinkConditions, *, degradations: DegradationLog
            ) -> KeyRate:
                # The label of the class this one was copied from, which is how
                # the mistake happens: a subclass that forgot to relabel.
                rate = super()._key_rate(conditions, degradations=degradations)
                return dataclasses.replace(rate, protocol=_Illustrative.name)

        with pytest.raises(ConfigurationError, match="labelled 'test-illustrative'"):
            _Mislabelled().key_rate(conditions(), degradations=DegradationLog())

    def test_a_result_that_recomputed_the_pulse_rate_is_refused(self) -> None:
        class _OwnClock(_Illustrative):
            name = "test-own-clock"

            def _key_rate(
                self, conditions: LinkConditions, *, degradations: DegradationLog
            ) -> KeyRate:
                rate = super()._key_rate(conditions, degradations=degradations)
                return dataclasses.replace(rate, protocol=self.name, pulse_rate_hz=1e06)

        with pytest.raises(ConfigurationError, match="copied, never recomputed"):
            _OwnClock().key_rate(conditions(), degradations=DegradationLog())

    def test_a_result_of_the_wrong_shape_is_refused(self) -> None:
        """The mistake that produces an ``(n, n)`` result with a correct diagonal."""

        class _Outer(_Illustrative):
            name = "test-outer"

            def _key_rate(
                self, conditions: LinkConditions, *, degradations: DegradationLog
            ) -> KeyRate:
                rate = super()._key_rate(conditions, degradations=degradations)
                column: FloatArray = rate.gain[:, None] * np.ones(rate.shape[0])
                return KeyRate(
                    protocol=self.name,
                    regime=rate.regime,
                    pulse_rate_hz=rate.pulse_rate_hz,
                    gain=column,
                    qber=rate.qber[:, None] * np.ones(rate.shape[0]),
                    sifted_per_pulse=0.5 * column,
                    secure_per_pulse=np.zeros_like(column),
                )

        c = conditions(transmittance=np.full(5, 1e-03))
        with pytest.raises(ConfigurationError, match=r"shape \(5, 5\) for conditions of shape"):
            _Outer().key_rate(c, degradations=DegradationLog())

    def test_the_interface_has_exactly_one_public_entry_point(self) -> None:
        """A subclass exposing its own would let a caller skip the three checks."""
        public = [name for name in dir(QkdProtocol) if not name.startswith("_")]
        assert public == ["key_rate"]


class TestProtocolRegistry:
    def test_register_returns_the_class_so_it_reads_as_a_decorator(self) -> None:
        registry = ProtocolRegistry()
        assert registry.register(_Illustrative) is _Illustrative
        assert registry.resolve("test-illustrative") is _Illustrative
        assert len(registry) == 1
        assert list(registry) == ["test-illustrative"]
        assert "test-illustrative" in registry
        assert "TEST-ILLUSTRATIVE " in registry
        assert 42 not in registry
        assert repr(registry) == "ProtocolRegistry(test-illustrative)"

    def test_an_empty_registry_says_so(self) -> None:
        assert repr(ProtocolRegistry()) == "ProtocolRegistry(empty)"
        assert ProtocolRegistry().names() == ()

    def test_it_can_be_built_from_an_iterable(self) -> None:
        assert ProtocolRegistry([_Illustrative]).names() == ("test-illustrative",)

    def test_a_name_is_resolved_the_way_a_person_writes_it(self) -> None:
        registry = ProtocolRegistry([_Illustrative])
        assert registry.resolve("  Test-Illustrative  ") is _Illustrative

    def test_two_classes_cannot_share_a_name(self) -> None:
        """Otherwise which one wins is decided by import order."""

        class _Twin(_Illustrative):
            pass

        registry = ProtocolRegistry([_Illustrative])
        with pytest.raises(ConfigurationError, match="already registered"):
            registry.register(_Twin)

    def test_only_protocol_classes_are_accepted(self) -> None:
        registry = ProtocolRegistry()
        with pytest.raises(ConfigurationError, match="stores classes, not"):
            registry.register(_Illustrative())  # type: ignore[arg-type]
        with pytest.raises(ConfigurationError, match="not a QkdProtocol subclass"):
            registry.register(int)  # type: ignore[arg-type]

    def test_a_class_without_a_name_is_refused(self) -> None:
        class _Anonymous(QkdProtocol):
            def _key_rate(
                self, conditions: LinkConditions, *, degradations: DegradationLog
            ) -> KeyRate:
                raise NotImplementedError

        with pytest.raises(ConfigurationError, match="must define a non-empty"):
            ProtocolRegistry().register(_Anonymous)

    @pytest.mark.parametrize("bad", ["BB84", "bb84 decoy", "bb84\t"])
    def test_a_name_that_a_yaml_file_could_not_reproduce(self, bad: str) -> None:
        class _Odd(_Illustrative):
            name = bad

        with pytest.raises(ConfigurationError, match="lowercase and contain no whitespace"):
            ProtocolRegistry().register(_Odd)

    def test_resolving_an_unknown_name_lists_what_exists(self) -> None:
        registry = ProtocolRegistry([_Illustrative])
        with pytest.raises(ConfigurationError) as excinfo:
            registry.resolve("e91")
        message = str(excinfo.value)
        assert "'test-illustrative'" in message
        assert "0005-propagation" in message

    def test_an_empty_registry_still_explains_itself(self) -> None:
        with pytest.raises(ConfigurationError, match="nothing yet"):
            ProtocolRegistry().resolve("bb84-decoy")

    @pytest.mark.parametrize(
        "absent", ["e91", "entanglement", "cv", "cv-qkd", "mdi", "mdi-qkd", "tf", "tf-qkd"]
    )
    def test_no_unimplemented_protocol_is_reachable_by_name(self, absent: str) -> None:
        """The negative control for the scope rule, on the registry the project reads.

        An absent name forces the question at the call site; a present and
        unimplemented one invites a scenario to select it. This holds however
        many protocol modules have been imported by the time it runs.
        """
        assert absent not in PROTOCOLS
        with pytest.raises(ConfigurationError):
            PROTOCOLS.resolve(absent)


class TestModuleSurface:
    def test_all_is_complete_and_ordered_by_the_project_convention(self) -> None:
        """Constants, then classes, then functions, each block sorted."""
        from quoss.qkd import base

        for name in base.__all__:
            assert hasattr(base, name)
        constants = [n for n in base.__all__ if n.isupper()]
        classes = [n for n in base.__all__ if not n.isupper() and n[0].isupper()]
        functions = [n for n in base.__all__ if n[0].islower()]
        assert base.__all__ == sorted(constants) + sorted(classes) + sorted(functions)

    def test_the_only_published_constant_names_its_source(self) -> None:
        from quoss.qkd import base

        assert [n for n in base.__all__ if n.isupper() and n != "PROTOCOLS"] == [
            "NTANOS_SOURCE_PULSE_RATE_HZ"
        ]
        assert NTANOS_SOURCE_PULSE_RATE_HZ == 100.0e06

    def test_no_protocol_parameter_has_leaked_into_the_boundary(self) -> None:
        """The negative control for what this module is.

        An intensity, a decoy level, a block length or a security parameter are
        choices an experimenter makes, so they belong to a protocol object. A
        boundary that accepted one would stop being implementable by anything
        else, and would be the place a second copy of the BB84 model grew.
        """
        from quoss.qkd import base

        forbidden = ("intensity", "decoy", "block", "epsilon", "mean_photon", "basis")
        for name in base.__all__:
            attribute = getattr(base, name)
            if not callable(attribute):
                continue
            parameters = inspect.signature(attribute).parameters
            for parameter in parameters:
                assert not any(word in parameter for word in forbidden), f"{name}.{parameter}"

    def test_the_link_conditions_offer_no_second_efficiency_to_multiply_by(self) -> None:
        """Trap 2, asserted by absence: there is one transmittance and no pair."""
        parameters = inspect.signature(LinkConditions).parameters
        assert "transmittance" in parameters
        for absent in ("efficiency", "receiver_efficiency", "channel_transmittance", "loss_db"):
            assert absent not in parameters

    def test_the_module_declares_what_it_leaves_out(self) -> None:
        from quoss.qkd import base

        assert base.__doc__ is not None
        for absent in (
            "E91",
            "CV-QKD",
            "MDI-QKD",
            "TF-QKD",
            "0005-propagation",
            "finite_key.py",
            "system/key_volume.py",
            "decoy-state machinery",
            "saturation_count_rate_cps",
        ):
            assert absent in base.__doc__

    def test_the_module_documents_both_sources(self) -> None:
        from quoss.qkd import base

        assert base.__doc__ is not None
        assert "Ntanos" in base.__doc__
        assert "Lim" in base.__doc__
        assert "022307" in base.__doc__

    def test_there_is_no_random_generator_in_this_module(self) -> None:
        """Same rule as ``channel/``: randomness lives in ``core/rng.py``."""
        import ast

        from quoss.qkd import base

        tree = ast.parse(inspect.getsource(base))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
            elif isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
        assert not any("rng" in name or "random" in name for name in imported)

    def test_the_package_re_exports_nothing(self) -> None:
        """The rule of ``quoss.core``: import from the module that defines the name."""
        import quoss.qkd

        assert quoss.qkd.__all__ == []
