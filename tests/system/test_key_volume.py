"""Tests for `quoss.system.key_volume`.

Organised by the claim each block defends, not by the function it calls.

- ``TestTheFiniteBoundIsTheDefault`` — the decision this module exists to close.
  The unqualified entry point returns ``FINITE``, there is no ``regime`` keyword
  to flip, and the asymptotic path announces itself in the log every time.
- ``TestWhatTheAsymptoticRateOverstates`` — **the headline measurement.** The
  per-pass and per-day table of the module docstring, regenerated: 11.5 % of the
  day, and two passes out of four that certify nothing where the asymptotic
  integral claims half a megabit. Plus *why* a low pass dies completely rather
  than a little.
- ``TestTheBlockIsThePass`` — **V1**, and the largest lever in the module. One
  block per sample yields zero bits from the whole day; one block per pass yields
  433 kbit. The bound is not additive over sub-blocks.
- ``TestAgainstHandPooledBlocks`` — **V3 within the project.** The vectorised
  segment sum is checked against ``DecoyBlockCounts.pooled()`` applied to one
  pass at a time, and the asymptotic integral against an explicit Python loop.
  Two implementations, one number.
- ``TestOneQuadratureAndOneConfiguration`` — that the two regimes differ by the
  bound and by nothing else: the same dwell times, the same protocol object.
- ``TestTheElevationMaskHasAnInteriorOptimum`` — the finding only this module can
  see. The asymptotic integral is monotone in the mask and the finite bound is
  not, and lowering the mask from 8 to 2 degrees buys 71 % more seconds and
  destroys 6.0 % of the day's key.
- ``TestWhatSaturatingTheScintillationDoesToTheMask`` — **the stage 1.2
  measurement**: the same day with the moderate-to-strong scintillation model
  instead of the weak one moves the interior optimum from 8 degrees to 4.5 and
  the day's key up 6.4 %.
- ``TestComposingADay`` — that ``n`` blocks at ``eps`` make a day at ``n eps``,
  what an honestly ``eps``-secure day costs (6.5 %), and the refusal when the
  composition is vacuous.
- ``TestTheGridResolutionGuard`` — regenerates the bias table that
  ``MINIMUM_SAMPLES_PER_PASS`` is derived from, including its sign and its
  non-monotonicity, which is why the guard counts samples.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
- ``TestTheModuleSurface`` — what the module refuses to do: compute the channel,
  accept conditions of the wrong shape, or attach an ``eps`` to an asymptotic day.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest

from quoss.channel.turbulence import ScintillationRegime
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.qkd.base import KeyRegime, LinkConditions
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import (
    DecoySettings,
    FiniteKeyResult,
    SecurityParameters,
    expected_block_counts,
    secret_key_length,
)
from quoss.system.key_volume import (
    SYMMETRIC_KEY_BASIS_PROBABILITY,
    DailyKeyVolume,
    PassKeyVolume,
    asymptotic_pass_key_volume,
    composed_security,
    daily_key_volume,
    decoy_settings_from_protocol,
    pass_key_volume,
)
from quoss.system.passes import MINIMUM_SAMPLES_PER_PASS, PassSamples, PassTable

from .reference import (
    REFERENCE_ASYMPTOTIC_BITS,
    REFERENCE_DAY_NUMBER,
    REFERENCE_FINITE_BITS,
    REFERENCE_FINITE_DAY_BITS,
    Link,
    link,
    reference_protocol,
    reference_security,
)


@pytest.fixture(scope="module")
def reference_link() -> Link:
    """Return the reference day at a 10 degree mask."""
    return link()


@pytest.fixture(scope="module")
def reference_table(reference_link: Link) -> PassTable:
    """Return the reference day's four passes."""
    return reference_link.table


def finite(
    target: Link,
    *,
    security: SecurityParameters | None = None,
    degradations: DegradationLog | None = None,
    key_basis_probability: float = SYMMETRIC_KEY_BASIS_PROBABILITY,
) -> PassKeyVolume:
    """Run the finite path on a wired link."""
    return pass_key_volume(
        target.conditions,
        samples=target.samples,
        protocol=reference_protocol(),
        security=security if security is not None else reference_security(),
        degradations=degradations if degradations is not None else DegradationLog(),
        key_basis_probability=key_basis_probability,
    )


def asymptotic(target: Link, *, degradations: DegradationLog | None = None) -> PassKeyVolume:
    """Run the asymptotic path on a wired link."""
    return asymptotic_pass_key_volume(
        target.conditions,
        samples=target.samples,
        protocol=reference_protocol(),
        degradations=degradations if degradations is not None else DegradationLog(),
    )


class TestTheFiniteBoundIsTheDefault:
    """The pending decision of `qkd/__init__.py`, closed structurally."""

    @pytest.mark.physics
    def test_the_unqualified_entry_point_is_finite(self, reference_link: Link) -> None:
        volume = finite(reference_link)
        assert volume.regime is KeyRegime.FINITE
        assert isinstance(volume.finite, FiniteKeyResult)

    def test_there_is_no_regime_argument_to_flip(self) -> None:
        """A default argument is a default somebody passes the other value to.

        The asymptotic answer is reachable only through a differently named
        function, so selecting it is a visible edit at the call site rather than a
        keyword buried in a call.
        """
        assert "regime" not in inspect.signature(pass_key_volume).parameters
        assert "regime" not in inspect.signature(asymptotic_pass_key_volume).parameters
        assert "asymptotic" in asymptotic_pass_key_volume.__name__

    @pytest.mark.physics
    def test_the_asymptotic_path_announces_itself_every_time(self, reference_link: Link) -> None:
        log = DegradationLog()
        asymptotic(reference_link, degradations=log)
        entry = next(e for e in log if e.code == "key_volume.asymptotic-upper-bound")
        assert entry.severity is Severity.WARNING
        assert "upper bound" in entry.message

    @pytest.mark.physics
    def test_an_asymptotic_volume_cannot_carry_a_finite_result(self, reference_link: Link) -> None:
        volume = asymptotic(reference_link)
        assert volume.finite is None
        with pytest.raises(DomainError, match="must not carry a FiniteKeyResult"):
            PassKeyVolume(
                samples=volume.samples,
                regime=KeyRegime.ASYMPTOTIC,
                key_bits=np.asarray(volume.key_bits),
                pulses=np.asarray(volume.pulses),
                seconds=np.asarray(volume.seconds),
                finite=finite(reference_link).finite,
                protocol=volume.protocol,
            )

    @pytest.mark.physics
    def test_a_finite_volume_cannot_omit_its_terms(self, reference_link: Link) -> None:
        volume = finite(reference_link)
        with pytest.raises(DomainError, match="must carry the FiniteKeyResult"):
            PassKeyVolume(
                samples=volume.samples,
                regime=KeyRegime.FINITE,
                key_bits=np.asarray(volume.key_bits),
                pulses=np.asarray(volume.pulses),
                seconds=np.asarray(volume.seconds),
                finite=None,
                protocol=volume.protocol,
            )


class TestWhatTheAsymptoticRateOverstates:
    """The headline measurement of stage 3, regenerated rather than cited."""

    @pytest.mark.physics
    def test_the_per_pass_table(self, reference_link: Link) -> None:
        """The module docstring's table, both columns."""
        lower = finite(reference_link)
        upper = asymptotic(reference_link)
        assert lower.key_bits.tolist() == list(REFERENCE_FINITE_BITS)
        assert np.allclose(upper.key_bits, REFERENCE_ASYMPTOTIC_BITS, rtol=1e-6)

    @pytest.mark.physics
    def test_the_day_ratio_is_eleven_percent(self, reference_link: Link) -> None:
        lower = finite(reference_link).total_bits
        upper = asymptotic(reference_link).total_bits
        assert lower == pytest.approx(REFERENCE_FINITE_DAY_BITS, abs=1.0)
        assert upper == pytest.approx(3_776_681.0, rel=1e-6)
        assert lower / upper == pytest.approx(0.1146, abs=5e-4)

    @pytest.mark.physics
    def test_two_of_four_passes_certify_nothing(self, reference_link: Link) -> None:
        """The part that matters more than the ratio: the error is unbounded, not 8.7x."""
        lower = finite(reference_link)
        upper = asymptotic(reference_link)
        assert lower.has_key.tolist() == [True, False, True, False]
        # The QBERs the "one block per day" argument rests on: pooling would carry
        # the dead passes' 787 000 detections into a block whose good passes sit
        # lower, and error correction is charged on every one of them.
        terms = lower.finite
        assert terms is not None
        dead_mask = ~lower.has_key
        assert float(terms.block_size[dead_mask].sum()) == pytest.approx(786_986.0, rel=1e-5)
        assert np.allclose(terms.observed_error_rate[dead_mask], [0.01762, 0.01943], atol=1e-5)
        assert np.allclose(terms.observed_error_rate[~dead_mask], [0.01262, 0.01237], atol=1e-5)
        # Every pass is positive asymptotically, so nothing in that column flags
        # the two that deliver no key at all.
        assert bool(np.all(upper.has_key))
        dead = ~lower.has_key
        assert float(upper.key_bits[dead].sum()) == pytest.approx(519_179.0, rel=1e-5)

    @pytest.mark.physics
    def test_the_dead_passes_are_reported_not_dropped(self, reference_link: Link) -> None:
        log = DegradationLog()
        finite(reference_link, degradations=log)
        entry = next(e for e in log if e.code == "key_volume.passes-without-key")
        assert entry.severity is Severity.INFO
        assert entry.details["passes_without_key"] == 2
        assert entry.details["n_passes"] == 4

    @pytest.mark.physics
    def test_a_low_pass_dies_by_phase_error_not_by_block_size(self, reference_link: Link) -> None:
        """Why it is a cliff and not a taper, which is the mechanism the docstring claims.

        Pass 4 collects 310 000 key-basis detections — not a small number — and
        certifies nothing, because the phase-error inference returns one half, at
        which ``1 - h(phi)`` is exactly zero and the single-photon term vanishes
        while error correction is still charged on every bit.
        """
        result = finite(reference_link).finite
        assert result is not None
        assert float(result.block_size[3]) > 3.0e5
        assert float(result.phase_error_rate[3]) == pytest.approx(0.5, abs=1e-12)
        assert float(result.leakage_bits[3]) > 0.0
        # The good passes sit an order of magnitude below the cap.
        assert float(result.phase_error_rate[0]) == pytest.approx(0.077, abs=1e-3)
        assert float(result.phase_error_rate[2]) == pytest.approx(0.072, abs=1e-3)

    @pytest.mark.physics
    def test_the_finite_bits_are_whole_numbers_and_the_asymptotic_ones_are_not(
        self, reference_link: Link
    ) -> None:
        """A block length is an integer; an integral of a rate is not.

        The distinction is not cosmetic: it is the difference between a quantity
        Eq. (1) floors and a quantity that was never a count of anything.
        """
        lower = finite(reference_link)
        upper = asymptotic(reference_link)
        assert np.all(lower.key_bits == np.floor(lower.key_bits))
        assert not np.all(upper.key_bits == np.floor(upper.key_bits))

    @pytest.mark.physics
    def test_daylight_kills_both_regimes_equally(self) -> None:
        """A sanity bound on the claim: the gap is the statistics, not the noise.

        Under the 0.1 W/(m^2 um sr) low end of Ntanos et al.'s daylight range the
        QBER reaches 22-38 % and neither regime certifies a bit, so no amount of
        block is the answer to a sunlit sky.
        """
        daylight = link(sky_radiance_w_m2_um_sr=0.1)
        assert finite(daylight).total_bits == 0.0
        assert asymptotic(daylight).total_bits == 0.0


class TestTheBlockIsThePass:
    """**V1.** The largest lever in the module, and both alternatives measured."""

    @pytest.mark.physics
    def test_one_block_per_sample_yields_nothing_at_all(self, reference_link: Link) -> None:
        """Treating the bound as a per-instant correction loses the entire day.

        Each of the 1800 samples holds a median of 1615 key-basis detections against
        a 260-bit fixed penalty and a phase-error inference with nothing to work on.
        The bound is not additive over sub-blocks.
        """
        protocol = reference_protocol()
        settings = decoy_settings_from_protocol(protocol)
        samples = reference_link.samples
        pulses = reference_link.conditions.pulse_rate_hz * np.asarray(samples.dwell_s)
        per_sample = expected_block_counts(
            reference_link.conditions,
            settings=settings,
            key_basis_probability=SYMMETRIC_KEY_BASIS_PROBABILITY,
            pulses=pulses,
        )
        sliced = secret_key_length(
            per_sample,
            settings=settings,
            security=reference_security(),
            error_correction_efficiency=protocol.error_correction_efficiency,
            degradations=DegradationLog(),
        )
        assert sliced.shape == (1800,)
        assert float(sliced.length_bits.sum()) == 0.0
        assert int(sliced.has_key.sum()) == 0
        # The block sizes the docstrings quote, measured rather than cited: these
        # are not tiny blocks, which is the point — 469 detections is already more
        # than the 260-bit penalty, and they still certify nothing.
        block = np.asarray(sliced.block_size)
        assert float(np.median(block)) == pytest.approx(1615.0, abs=2.0)
        assert float(block.min()) == pytest.approx(469.0, abs=1.0)
        assert float(block.max()) == pytest.approx(8917.0, abs=1.0)
        # And the same counts, pooled per pass, certify 433 kbit.
        assert finite(reference_link).total_bits == pytest.approx(
            REFERENCE_FINITE_DAY_BITS, abs=1.0
        )

    @pytest.mark.physics
    def test_pooling_the_whole_day_into_one_block_is_not_offered(self) -> None:
        """The opposite temptation, absent from the surface on purpose.

        There is no function here that takes a ``PassTable`` and returns one
        block: the four passes are separated by hours in which no pulse is sent,
        and pooling them would average the good passes' 1.24-1.26 % QBER against the
        dead ones' 1.9 %. ``daily_key_volume`` sums lengths, which is what
        composability licenses.
        """
        from quoss.system import key_volume as module

        assert "pooled" not in module.__all__
        assert all(not name.startswith("day_block") for name in module.__all__)
        signature = inspect.signature(daily_key_volume)
        assert list(signature.parameters) == ["volume", "degradations"]

    @pytest.mark.physics
    def test_a_longer_block_never_certifies_less(self, reference_link: Link) -> None:
        """Monotonicity in the block, which a pass-level bound must have.

        Doubling the pulse rate doubles every count at fixed conditions, and the
        bound can only improve: the fixed penalty is paid once either way.
        """
        base = finite(reference_link)
        faster = LinkConditions(
            transmittance=reference_link.conditions.transmittance,
            noise_counts_per_gate=reference_link.conditions.noise_counts_per_gate,
            misalignment_error=reference_link.conditions.misalignment_error,
            pulse_rate_hz=2.0 * reference_link.conditions.pulse_rate_hz,
            gate_duration_s=reference_link.conditions.gate_duration_s,
        )
        doubled = pass_key_volume(
            faster,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=reference_security(),
            degradations=DegradationLog(),
        )
        assert np.all(doubled.key_bits >= base.key_bits)
        assert doubled.total_bits > 2.0 * base.total_bits


class TestAgainstHandPooledBlocks:
    """**V3 within the project.** Two implementations of the same integral."""

    @pytest.mark.physics
    def test_the_segment_sum_reproduces_pooled_one_pass_at_a_time(
        self, reference_link: Link
    ) -> None:
        """The vectorised pooling, against `DecoyBlockCounts.pooled` per pass.

        ``pooled(None)`` is `finite_key.py`'s own summation, written without any
        notion of a pass; running it on one pass's slice and stacking the results
        is the independent route to the same blocks.
        """
        protocol = reference_protocol()
        settings = decoy_settings_from_protocol(protocol)
        samples = reference_link.samples
        dwell = np.asarray(samples.dwell_s)
        pulses = reference_link.conditions.pulse_rate_hz * dwell
        per_sample = expected_block_counts(
            reference_link.conditions,
            settings=settings,
            key_basis_probability=SYMMETRIC_KEY_BASIS_PROBABILITY,
            pulses=pulses,
        )
        expected: list[float] = []
        for index in range(samples.table.n_passes):
            rows = samples.pass_index == index
            one = LinkConditions(
                transmittance=np.asarray(reference_link.conditions.transmittance)[rows],
                noise_counts_per_gate=np.asarray(reference_link.conditions.noise_counts_per_gate)[
                    rows
                ],
                misalignment_error=np.asarray(reference_link.conditions.misalignment_error)[rows],
                pulse_rate_hz=reference_link.conditions.pulse_rate_hz,
                gate_duration_s=reference_link.conditions.gate_duration_s,
            )
            block = expected_block_counts(
                one,
                settings=settings,
                key_basis_probability=SYMMETRIC_KEY_BASIS_PROBABILITY,
                pulses=pulses[rows],
            ).pooled(None)
            expected.append(
                float(
                    secret_key_length(
                        block,
                        settings=settings,
                        security=reference_security(),
                        error_correction_efficiency=protocol.error_correction_efficiency,
                        degradations=DegradationLog(),
                    ).length_bits
                )
            )
        assert per_sample.shape == (samples.size,)
        assert finite(reference_link).key_bits.tolist() == expected

    @pytest.mark.physics
    def test_the_asymptotic_integral_reproduces_an_explicit_loop(
        self, reference_link: Link
    ) -> None:
        protocol = reference_protocol()
        rate = protocol.key_rate(reference_link.conditions, degradations=DegradationLog())
        samples = reference_link.samples
        expected = []
        for index in range(samples.table.n_passes):
            rows = samples.pass_index == index
            expected.append(
                float(
                    np.sum(np.asarray(rate.secure_bit_s)[rows] * np.asarray(samples.dwell_s)[rows])
                )
            )
        assert np.allclose(asymptotic(reference_link).key_bits, expected, rtol=1e-12, atol=0.0)


class TestOneQuadratureAndOneConfiguration:
    """That the two regimes differ by the bound and by nothing else."""

    @pytest.mark.physics
    def test_both_paths_report_the_same_seconds_and_pulses(self, reference_link: Link) -> None:
        lower, upper = finite(reference_link), asymptotic(reference_link)
        assert np.allclose(lower.seconds, upper.seconds, rtol=0.0, atol=1e-9)
        assert np.allclose(lower.pulses, upper.pulses, rtol=1e-12)
        assert np.allclose(lower.seconds, reference_link.table.duration_s, rtol=0.0, atol=1e-9)

    @pytest.mark.physics
    def test_the_pulses_are_the_rate_times_the_refined_duration(self, reference_link: Link) -> None:
        volume = finite(reference_link)
        expected = reference_link.conditions.pulse_rate_hz * reference_link.table.duration_s
        assert np.allclose(volume.pulses, expected, rtol=1e-12)

    def test_one_protocol_object_drives_both_regimes(self) -> None:
        """The derived settings carry the protocol's five choices unchanged."""
        protocol = Bb84DecoyProtocol.ntanos_2021()
        settings = decoy_settings_from_protocol(protocol)
        assert settings.signal_intensity == protocol.signal_intensity
        assert settings.decoy_intensity == protocol.decoy_intensity
        assert settings.vacuum_intensity == 0.0
        assert settings.signal_probability == protocol.signal_probability
        assert settings.decoy_probability == protocol.decoy_probability
        assert settings.vacuum_probability == protocol.vacuum_probability

    @pytest.mark.physics
    def test_changing_the_intensity_moves_both_regimes(self, reference_link: Link) -> None:
        """The check that the bridge is load-bearing, not decorative.

        If the finite path had its own hard-coded ``mu``, this would move one
        column and not the other, and the ratio between them would be a
        measurement of the configuration mismatch.
        """
        weaker = Bb84DecoyProtocol(
            signal_intensity=0.30,
            decoy_intensity=0.11,
            signal_probability=16 / 21,
            decoy_probability=1 / 21,
            vacuum_probability=4 / 21,
            error_correction_efficiency=1.22,
        )
        base_lower = finite(reference_link).total_bits
        base_upper = asymptotic(reference_link).total_bits
        moved_lower = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=weaker,
            security=reference_security(),
            degradations=DegradationLog(),
        ).total_bits
        moved_upper = asymptotic_pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=weaker,
            degradations=DegradationLog(),
        ).total_bits
        assert moved_lower != base_lower
        assert moved_upper != base_upper

    @pytest.mark.physics
    def test_an_asymmetric_basis_choice_is_honoured_and_warned_about(
        self, reference_link: Link
    ) -> None:
        """Allow it, and flag it, because the asymptotic protocol is symmetric.

        ``finite_key.py`` supports a biased basis, so refusing would be refusing
        a real protocol; but the asymptotic side of the comparison does not, so
        the pair stops being comparable and that has to be said out loud.
        """
        log = DegradationLog()
        biased = finite(reference_link, degradations=log, key_basis_probability=0.9)
        entry = next(e for e in log if e.code == "key_volume.asymmetric-basis-choice")
        assert entry.severity is Severity.WARNING
        assert entry.details["key_basis_probability"] == 0.9
        # And it is a real effect, not a cosmetic flag: biasing the basis changes
        # the answer by more than a rounding.
        assert biased.total_bits != finite(reference_link).total_bits

    @pytest.mark.physics
    def test_the_symmetric_value_warns_about_nothing(self, reference_link: Link) -> None:
        log = DegradationLog()
        finite(reference_link, degradations=log)
        assert not any(e.code == "key_volume.asymmetric-basis-choice" for e in log)
        assert SYMMETRIC_KEY_BASIS_PROBABILITY == 0.5

    @pytest.mark.physics
    def test_mean_bit_s_and_key_per_pulse_are_derived_not_stored(
        self, reference_link: Link
    ) -> None:
        volume = finite(reference_link)
        assert np.allclose(volume.mean_bit_s, volume.key_bits / volume.seconds)
        assert np.allclose(volume.key_per_pulse, volume.key_bits / volume.pulses)
        # The best pass averages a few hundred bits a second, a factor of 16 below
        # the peak instantaneous asymptotic rate, because most of a pass is near the
        # horizon and because the block pays for its own statistics. Both numbers
        # are quoted in `PassKeyVolume.mean_bit_s`, so both are measured here.
        assert float(volume.mean_bit_s[2]) == pytest.approx(434.0, abs=2.0)
        peak = float(
            np.max(
                reference_protocol()
                .key_rate(reference_link.conditions, degradations=DegradationLog())
                .secure_bit_s
            )
        )
        assert peak == pytest.approx(6896.0, abs=2.0)
        assert peak / float(volume.mean_bit_s[2]) == pytest.approx(15.9, abs=0.2)


class TestTheElevationMaskHasAnInteriorOptimum:
    """The finding only this module can see, and the clamp that explains it."""

    MASKS = (2.0, 5.0, 7.0, 8.0, 10.0, 20.0)

    @pytest.mark.reference
    def test_the_asymptotic_integral_is_monotone_in_the_mask(self) -> None:
        """A per-sample clamp at zero means a wider pass can never lose key."""
        totals = [asymptotic(link(mask)).total_bits for mask in self.MASKS]
        assert totals == sorted(totals, reverse=True)

    @pytest.mark.reference
    def test_the_asymptotic_integral_stops_moving_below_five_degrees(self) -> None:
        """Below 5 degrees the extra samples contribute *exactly* zero.

        So the mask is invisible to the asymptotic calculation precisely where it
        costs the finite bound the most.
        """
        assert asymptotic(link(2.0)).total_bits == pytest.approx(
            asymptotic(link(5.0)).total_bits, rel=1e-12
        )

    @pytest.mark.reference
    def test_the_finite_bound_is_not_monotone_and_peaks_near_eight_degrees(self) -> None:
        """The module docstring's table, regenerated."""
        totals = {mask: finite(link(mask)).total_bits for mask in self.MASKS}
        assert totals != dict(zip(self.MASKS, sorted(totals.values(), reverse=True), strict=True))
        best = max(totals, key=lambda mask: totals[mask])
        assert best == 8.0
        assert totals[8.0] == pytest.approx(434_938.0, abs=2.0)
        assert totals[2.0] == pytest.approx(408_946.0, abs=2.0)
        assert totals[20.0] == pytest.approx(360_978.0, abs=2.0)

    @pytest.mark.reference
    def test_widening_the_mask_buys_seconds_and_destroys_key(self) -> None:
        """71 % more usable time, 6.0 % less key. The number that makes the point."""
        wide, best = link(2.0), link(8.0)
        seconds_gained = float(wide.table.duration_s.sum() / best.table.duration_s.sum()) - 1.0
        key_lost = 1.0 - finite(wide).total_bits / finite(best).total_bits
        assert seconds_gained == pytest.approx(0.708, abs=0.01)
        assert key_lost == pytest.approx(0.0598, abs=1e-3)

    @pytest.mark.reference
    def test_the_mechanism_is_leakage_outrunning_certified_events(self) -> None:
        """Measured on one pass: +2.6 % single-photon events, +5.5 % leakage.

        Error correction is charged on every detection of the pooled block while
        privacy amplification pays only for the certified single-photon part, so
        a low-elevation sample that brings errors without bringing certificates is
        a net loss — something no per-sample formula can express.
        """
        tight = finite(link(10.0)).finite
        loose = finite(link(5.0)).finite
        assert tight is not None and loose is not None
        # Pass index 0 at a 5 degree mask is the same physical pass, widened.
        events_growth = float(loose.single_photon_events[0] / tight.single_photon_events[0]) - 1.0
        leakage_growth = float(loose.leakage_bits[0] / tight.leakage_bits[0]) - 1.0
        assert events_growth == pytest.approx(0.0264, abs=2e-3)
        assert leakage_growth == pytest.approx(0.0550, abs=2e-3)
        assert leakage_growth > events_growth


@pytest.mark.reference
class TestWhatSaturatingTheScintillationDoesToTheMask:
    """**The stage 1.2 measurement.** The interior optimum moves from 8 degrees to 4.5.

    What changed, in one sentence
    -----------------------------
    Nothing in this module. The only difference between the two columns below is
    that the channel was evaluated with
    :attr:`~quoss.channel.turbulence.ScintillationRegime.MODERATE_TO_STRONG`
    instead of ``WEAK`` — the log-irradiance variance of a sample whose Rytov
    variance exceeds 1 Np^2 is the saturated value of Gruneisen et al. equation
    (A8) rather than ITU-R P.1622 equation (4a)'s. The orbit, the pass table, the
    sample indices, the protocol and the security parameters are identical, which
    is what makes the comparison a comparison.

    The table
    ---------
    ============  ===============  ===================  ========
    mask (deg)    ``WEAK`` bits    saturated bits       change
    ============  ===============  ===================  ========
    2             408 946          458 862              +12.2 %
    4.5           424 448          **462 945**          +9.1 %
    5             426 988          462 936              +8.4 %
    8             **434 938**      457 663              +5.2 %
    10            432 985          449 514              +3.8 %
    20            360 978          364 740              +1.0 %
    ============  ===============  ===================  ========

    Why the optimum moves *down*
    ----------------------------
    The interior optimum exists because a low sample brings error-correction
    leakage faster than it brings certified single-photon events
    (``TestTheElevationMaskHasAnInteriorOptimum``). What makes a low sample
    expensive is its fade allowance, and the weak model charges it a fade that
    saturation says is not there: at the reference day's worst sample the
    variance falls from 1.48 to 0.63 Np^2, which is 6.1 dB off the 1 %-outage
    allowance. Samples that did not pay for themselves under the weak model do
    pay for themselves under the saturated one, so the mask that maximises the
    day's certified key drops from 8 degrees to 4.5, and the day gains 6.4 %.

    What this does **not** say
    --------------------------
    It does not say the reference day is worth 462 945 bits. Both columns are
    V4 — QuOSS's own output — and the saturated one rests on a heuristic fit
    whose only published anchor is a maximum scintillation index of 1.24
    (``tests/channel/test_turbulence.py``). What it says is that the choice of
    scintillation model is worth more than a decibel of margin: it moves a
    design decision, the elevation mask, by three and a half degrees. A margin
    that survives both columns is a margin; one that needs the saturated column
    is a bet on the heuristic.

    The split between channel and bound is in
    ``tests/e2e/test_reference_scenarios.py::TestWhatTheSaturatedModelIsWorth``,
    which is where the elasticity machinery of
    ``TestWhyTheHigherStationGainsLess`` gets used for the case it was written
    for.
    """

    SATURATED = ScintillationRegime.MODERATE_TO_STRONG
    MASKS = (2.0, 4.5, 5.0, 8.0, 10.0, 20.0)

    @staticmethod
    def _bits(mask_deg: float, regime: ScintillationRegime) -> float:
        return finite(link(mask_deg, regime=regime)).total_bits

    def test_the_two_regimes_see_the_same_passes_and_the_same_samples(self) -> None:
        """The control: the regime reaches the channel and nothing upstream of it."""
        weak, saturated = link(8.0), link(8.0, regime=self.SATURATED)
        assert weak.table.duration_s.tolist() == saturated.table.duration_s.tolist()
        assert weak.samples.sample_index.tolist() == saturated.samples.sample_index.tolist()
        assert np.any(
            np.asarray(weak.conditions.transmittance)
            != np.asarray(saturated.conditions.transmittance)
        )

    def test_the_saturated_optimum_is_at_four_and_a_half_degrees(self) -> None:
        """Still interior, and three and a half degrees lower."""
        totals = {mask: self._bits(mask, self.SATURATED) for mask in self.MASKS}
        best = max(totals, key=lambda mask: totals[mask])
        assert best == 4.5
        assert totals[4.5] > totals[2.0]
        assert totals[4.5] == pytest.approx(462_945.0, abs=2.0)

    def test_the_weak_optimum_is_still_at_eight(self) -> None:
        """Nothing about the default moved, which is what makes the shift attributable."""
        totals = {mask: self._bits(mask, ScintillationRegime.WEAK) for mask in self.MASKS}
        assert max(totals, key=lambda mask: totals[mask]) == 8.0
        assert totals[8.0] == pytest.approx(434_938.0, abs=2.0)

    def test_the_day_gains_six_per_cent_at_its_own_optimum(self) -> None:
        """434 938 bits at 8 degrees against 462 945 at 4.5: +6.44 %."""
        weak_best = self._bits(8.0, ScintillationRegime.WEAK)
        saturated_best = self._bits(4.5, self.SATURATED)
        assert saturated_best / weak_best - 1.0 == pytest.approx(0.0644, abs=5e-4)

    @pytest.mark.parametrize("mask_deg", MASKS)
    def test_saturating_never_costs_key_at_any_mask(self, mask_deg: float) -> None:
        """V1, and the only sign this effect is allowed to have.

        Saturation can only lower a variance
        (``TestTheSaturatedRegimeInvariants``), a lower variance can only lower a
        fade allowance, and a lower fade allowance can only raise a
        transmittance. If any mask reported less key with the saturated model,
        the plumbing would be wrong rather than the physics surprising.
        """
        assert self._bits(mask_deg, self.SATURATED) >= self._bits(
            mask_deg, ScintillationRegime.WEAK
        )

    def test_the_gain_is_largest_where_the_mask_is_lowest(self) -> None:
        """+12.2 % at 2 degrees against +1.0 % at 20: the effect is the low samples.

        A monotone gain is the signature of the mechanism. Saturation changes
        nothing above about 20 degrees, where the Rytov variance is 0.015 Np^2
        and the model is the identity to 0.6 %; everything it is worth comes
        from the samples a wide mask admits.
        """
        gains = [
            self._bits(mask, self.SATURATED) / self._bits(mask, ScintillationRegime.WEAK) - 1.0
            for mask in self.MASKS
        ]
        assert gains == sorted(gains, reverse=True)
        assert gains[0] == pytest.approx(0.1221, abs=1e-3)
        assert gains[-1] == pytest.approx(0.0104, abs=1e-3)


class TestComposingADay:
    """What a 'bits per day' figure owes its caption."""

    @pytest.mark.physics
    def test_the_day_is_the_sum_of_its_passes(self, reference_link: Link) -> None:
        volume = finite(reference_link)
        daily = daily_key_volume(volume, degradations=DegradationLog())
        assert daily.day_number.tolist() == [REFERENCE_DAY_NUMBER]
        assert float(daily.key_bits[0]) == pytest.approx(volume.total_bits, abs=1e-9)
        assert int(daily.pass_count[0]) == 4
        assert int(daily.passes_with_key[0]) == 2
        assert daily.n_days == 1
        assert len(daily) == 1

    @pytest.mark.physics
    def test_n_blocks_at_eps_make_a_day_at_n_eps(self, reference_link: Link) -> None:
        log = DegradationLog()
        daily = daily_key_volume(finite(reference_link), degradations=log)
        assert daily.security is not None
        assert daily.security.secrecy == pytest.approx(4e-10, rel=1e-12)
        assert daily.security.correctness == pytest.approx(4e-10, rel=1e-12)
        entry = next(e for e in log if e.code == "key_volume.day-composes-blocks")
        assert entry.details["blocks"] == 4

    @pytest.mark.physics
    def test_an_honestly_eps_secure_day_costs_six_and_a_half_percent(
        self, reference_link: Link
    ) -> None:
        """The other direction of the union bound, priced.

        To make the *day* 1e-10-secure rather than each pass, every block runs at
        1e-10/4. The claim is four times stronger and the key is 6.5 % smaller.
        """
        loose = finite(reference_link).total_bits
        tighter = finite(
            reference_link,
            security=SecurityParameters(correctness=1e-10 / 4, secrecy=1e-10 / 4),
        ).total_bits
        assert tighter < loose
        assert 1.0 - tighter / loose == pytest.approx(0.0651, abs=1e-3)
        # And the composed claim is then the one originally printed.
        daily = daily_key_volume(
            finite(
                reference_link,
                security=SecurityParameters(correctness=1e-10 / 4, secrecy=1e-10 / 4),
            ),
            degradations=DegradationLog(),
        )
        assert daily.security is not None
        assert daily.security.secrecy == pytest.approx(1e-10, rel=1e-12)

    def test_composing_is_a_union_bound(self) -> None:
        per_block = SecurityParameters(correctness=1e-12, secrecy=3e-11)
        for count in (1, 2, 17, 365 * 4):
            composed = composed_security(per_block, count)
            assert composed.correctness == pytest.approx(count * 1e-12, rel=1e-12)
            assert composed.secrecy == pytest.approx(count * 3e-11, rel=1e-12)

    def test_a_vacuous_composition_is_refused(self) -> None:
        """Enough blocks at a loose enough eps and the day has no claim at all."""
        with pytest.raises(DomainError, match="no security claim"):
            composed_security(SecurityParameters(correctness=1e-3, secrecy=1e-3), 1000)

    @pytest.mark.parametrize("blocks", [0, -1])
    def test_composing_fewer_than_one_block_is_refused(self, blocks: int) -> None:
        with pytest.raises(DomainError, match="blocks must be at least 1"):
            composed_security(reference_security(), blocks)

    def test_composing_refuses_a_non_security_object(self) -> None:
        with pytest.raises(DomainError, match="must be a SecurityParameters"):
            composed_security("1e-10", 4)  # type: ignore[arg-type]

    @pytest.mark.physics
    def test_an_asymptotic_day_carries_no_eps_and_says_so(self, reference_link: Link) -> None:
        log = DegradationLog()
        daily = daily_key_volume(asymptotic(reference_link), degradations=log)
        assert daily.security is None
        assert daily.regime is KeyRegime.ASYMPTOTIC
        entry = next(e for e in log if e.code == "key_volume.day-has-no-security-claim")
        assert entry.severity is Severity.WARNING

    @pytest.mark.physics
    def test_a_multi_day_window_splits_at_utc_midnight(self) -> None:
        """Two days of geometry give two rows, ascending, with no empty row between."""
        two_days = link(step_s=2.0, duration_s=172_800.0)
        daily = daily_key_volume(finite(two_days), degradations=DegradationLog())
        assert daily.n_days == 2
        assert daily.day_number.tolist() == [REFERENCE_DAY_NUMBER, REFERENCE_DAY_NUMBER + 1]
        assert np.all(np.diff(daily.day_number) == 1)
        assert int(daily.pass_count.sum()) == two_days.table.n_passes
        assert float(daily.key_bits.sum()) == pytest.approx(finite(two_days).total_bits, abs=1e-9)
        assert daily.total_bits == pytest.approx(float(daily.key_bits.sum()), abs=1e-9)

    @pytest.mark.physics
    def test_the_day_of_a_pass_is_where_it_starts(self, reference_link: Link) -> None:
        expected = np.floor(reference_link.table.start_jd + 0.5).astype(np.int64)
        assert reference_link.table.day_number.tolist() == expected.tolist()

    @pytest.mark.physics
    def test_mean_bit_s_is_per_usable_second(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        assert np.allclose(daily.mean_bit_s, daily.key_bits / daily.seconds)
        # 433 kbit over 1800 usable seconds, not over 86 400 seconds of day.
        assert float(daily.mean_bit_s[0]) == pytest.approx(240.6, abs=1.0)


class TestTheGridResolutionGuard:
    """The table `MINIMUM_SAMPLES_PER_PASS` is derived from, regenerated."""

    @pytest.mark.reference
    @pytest.mark.parametrize(
        ("step_s", "bias"),
        [
            (10.0, 0.000261),
            (25.0, 0.001201),
            (45.0, 0.013190),
            (60.0, 0.020179),
            (120.0, 0.085857),
        ],
    )
    def test_a_coarse_grid_inflates_the_day(self, step_s: float, bias: float) -> None:
        """Every one of these is **positive**: coarsening the grid hands out key.

        That sign is the reason the guard exists. A planner who halves the sample
        count to save runtime gets a larger number, with no symptom anywhere.
        """
        truth = finite(link(step_s=1.0)).total_bits
        coarse = finite(link(step_s=step_s)).total_bits
        assert coarse / truth - 1.0 == pytest.approx(bias, abs=2e-5)
        assert coarse > truth

    @pytest.mark.reference
    def test_the_bias_is_not_monotone_in_the_step(self) -> None:
        """Which is why the guard counts samples instead of estimating an error.

        48 s lands at +0.003 % by accident, between neighbours at +1.3 % and
        +2.0 %, because the bias depends on where the samples fall relative to
        culmination. An error estimate from a single coarse run can therefore be
        small by coincidence; a sample count cannot.
        """
        truth = finite(link(step_s=1.0)).total_bits
        bias = {
            step: finite(link(step_s=step)).total_bits / truth - 1.0 for step in (45.0, 48.0, 60.0)
        }
        assert bias[48.0] < bias[45.0]
        assert bias[48.0] < bias[60.0]
        assert abs(bias[48.0]) < 1e-4

    @pytest.mark.reference
    def test_the_threshold_is_where_the_bias_crosses_a_tenth_of_a_percent(self) -> None:
        """`MINIMUM_SAMPLES_PER_PASS` re-derived rather than trusted.

        At the constant's own sample count the bias is under 0.15 %; at the next
        coarser grid measured it is an order of magnitude worse.
        """
        truth = finite(link(step_s=1.0)).total_bits
        at_threshold = link(step_s=25.0)
        assert int(at_threshold.table.n_samples.min()) == MINIMUM_SAMPLES_PER_PASS
        assert abs(finite(at_threshold).total_bits / truth - 1.0) < 0.0015

        coarser = link(step_s=45.0)
        assert int(coarser.table.n_samples.min()) < MINIMUM_SAMPLES_PER_PASS
        assert abs(finite(coarser).total_bits / truth - 1.0) > 0.01


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError``, because a validator with no test is a comment."""

    @staticmethod
    def _volume_fields(volume: PassKeyVolume) -> dict[str, object]:
        return {
            "samples": volume.samples,
            "regime": volume.regime,
            "key_bits": np.array(volume.key_bits),
            "pulses": np.array(volume.pulses),
            "seconds": np.array(volume.seconds),
            "finite": volume.finite,
            "protocol": volume.protocol,
        }

    @staticmethod
    def _daily_fields(daily: DailyKeyVolume) -> dict[str, object]:
        return {
            "day_number": np.array(daily.day_number),
            "key_bits": np.array(daily.key_bits),
            "pass_count": np.array(daily.pass_count),
            "passes_with_key": np.array(daily.passes_with_key),
            "seconds": np.array(daily.seconds),
            "regime": daily.regime,
            "security": daily.security,
            "protocol": daily.protocol,
        }

    def test_conditions_of_the_wrong_length_are_refused(self, reference_link: Link) -> None:
        wrong = LinkConditions(
            transmittance=1e-3,
            noise_counts_per_gate=1e-6,
            misalignment_error=0.01,
            pulse_rate_hz=1e8,
            gate_duration_s=1e-9,
        )
        with pytest.raises(DomainError, match="part of the contract"):
            pass_key_volume(
                wrong,
                samples=reference_link.samples,
                protocol=reference_protocol(),
                security=reference_security(),
                degradations=DegradationLog(),
            )

    def test_a_non_linkconditions_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="conditions must be a LinkConditions"):
            pass_key_volume(
                np.zeros(reference_link.samples.size),  # type: ignore[arg-type]
                samples=reference_link.samples,
                protocol=reference_protocol(),
                security=reference_security(),
                degradations=DegradationLog(),
            )

    def test_a_non_passsamples_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="samples must be a PassSamples"):
            pass_key_volume(
                reference_link.conditions,
                samples=reference_link.table,  # type: ignore[arg-type]
                protocol=reference_protocol(),
                security=reference_security(),
                degradations=DegradationLog(),
            )

    def test_an_empty_sample_set_is_refused(self, reference_link: Link) -> None:
        """No passes is not a day with zero key; it is nothing to integrate over."""
        empty_table = reference_link.table.select(np.zeros(4, dtype=bool))
        empty = empty_table.samples()
        assert empty.size == 0
        conditions = LinkConditions(
            transmittance=np.zeros(0) + 1e-3,
            noise_counts_per_gate=np.zeros(0),
            misalignment_error=np.zeros(0),
            pulse_rate_hz=1e8,
            gate_duration_s=1e-9,
        )
        with pytest.raises(DomainError, match="no passes to integrate over"):
            pass_key_volume(
                conditions,
                samples=empty,
                protocol=reference_protocol(),
                security=reference_security(),
                degradations=DegradationLog(),
            )

    def test_a_non_protocol_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="must be a Bb84DecoyProtocol"):
            decoy_settings_from_protocol("bb84-decoy")  # type: ignore[arg-type]
        with pytest.raises(DomainError, match="must be a Bb84DecoyProtocol"):
            asymptotic_pass_key_volume(
                reference_link.conditions,
                samples=reference_link.samples,
                protocol=DecoySettings(  # type: ignore[arg-type]
                    signal_intensity=0.5,
                    decoy_intensity=0.1,
                    vacuum_intensity=0.0,
                    signal_probability=0.8,
                    decoy_probability=0.1,
                    vacuum_probability=0.1,
                ),
                degradations=DegradationLog(),
            )

    def test_a_non_security_object_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="security must be a SecurityParameters"):
            pass_key_volume(
                reference_link.conditions,
                samples=reference_link.samples,
                protocol=reference_protocol(),
                security=1e-10,  # type: ignore[arg-type]
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize("field", ["key_bits", "pulses", "seconds"])
    def test_a_volume_column_of_the_wrong_length_is_refused(
        self, reference_link: Link, field: str
    ) -> None:
        fields = self._volume_fields(finite(reference_link))
        fields[field] = np.zeros(3)
        with pytest.raises(DomainError, match="number per pass"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    @pytest.mark.parametrize("field", ["key_bits", "pulses", "seconds"])
    def test_a_negative_volume_column_is_refused(self, reference_link: Link, field: str) -> None:
        fields = self._volume_fields(finite(reference_link))
        broken = np.array(getattr(finite(reference_link), field))
        broken[0] = -1.0
        fields[field] = broken
        with pytest.raises(DomainError, match="must be non-negative"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_non_finite_volume_column_is_refused(self, reference_link: Link) -> None:
        fields = self._volume_fields(finite(reference_link))
        broken = np.array(finite(reference_link).key_bits)
        broken[0] = np.inf
        fields["key_bits"] = broken
        with pytest.raises(DomainError, match="non-finite"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_volume_without_a_protocol_name_is_refused(self, reference_link: Link) -> None:
        fields = self._volume_fields(finite(reference_link))
        fields["protocol"] = ""
        with pytest.raises(DomainError, match="protocol must be a non-empty name"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_volume_without_samples_is_refused(self, reference_link: Link) -> None:
        fields = self._volume_fields(finite(reference_link))
        fields["samples"] = reference_link.table
        with pytest.raises(DomainError, match="samples must be a PassSamples"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_finite_result_of_the_wrong_shape_is_refused(self, reference_link: Link) -> None:
        """One block per pass is the whole decision, so a mismatch is refused."""
        volume = finite(reference_link)
        assert volume.finite is not None
        fields = self._volume_fields(volume)
        one_block = FiniteKeyResult(
            length_bits=np.zeros(1),
            vacuum_events=np.zeros(1),
            single_photon_events=np.zeros(1),
            phase_error_rate=np.zeros(1),
            observed_error_rate=np.zeros(1),
            leakage_bits=np.zeros(1),
            block_size=np.zeros(1),
            pulses=np.ones(1),
            security=reference_security(),
        )
        fields["finite"] = one_block
        with pytest.raises(DomainError, match="One block per pass"):
            PassKeyVolume(**fields)  # type: ignore[arg-type]

    def test_daily_refuses_a_non_volume(self) -> None:
        with pytest.raises(DomainError, match="volume must be a PassKeyVolume"):
            daily_key_volume("a day", degradations=DegradationLog())  # type: ignore[arg-type]

    def test_a_repeated_day_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        for name in ("day_number", "key_bits", "pass_count", "passes_with_key", "seconds"):
            fields[name] = np.concatenate([np.asarray(fields[name]), np.asarray(fields[name])])
        with pytest.raises(DomainError, match="strictly ascending"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_daily_column_of_the_wrong_length_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        for name in ("key_bits", "seconds", "pass_count", "passes_with_key"):
            fields = self._daily_fields(daily)
            fields[name] = np.zeros(3, dtype=np.asarray(fields[name]).dtype)
            with pytest.raises(DomainError, match="but day_number has"):
                DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_two_dimensional_day_column_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields["day_number"] = np.zeros((2, 2), dtype=np.int64)
        with pytest.raises(DomainError, match="day_number must be 1-D"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    @pytest.mark.parametrize("name", ["key_bits", "seconds"])
    def test_a_negative_daily_length_is_refused(self, reference_link: Link, name: str) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields[name] = np.array([-1.0])
        with pytest.raises(DomainError, match="finite and non-negative"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    @pytest.mark.parametrize("name", ["pass_count", "passes_with_key"])
    def test_a_negative_daily_count_is_refused(self, reference_link: Link, name: str) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields[name] = np.array([-1], dtype=np.int64)
        with pytest.raises(DomainError, match="must be non-negative"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_more_keyed_passes_than_passes_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields["passes_with_key"] = np.array([99], dtype=np.int64)
        with pytest.raises(DomainError, match="cannot exceed pass_count"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_daily_volume_without_a_protocol_name_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields["protocol"] = ""
        with pytest.raises(DomainError, match="protocol must be a non-empty name"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_finite_day_without_security_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(finite(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields["security"] = None
        with pytest.raises(DomainError, match="must carry the composed SecurityParameters"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]

    def test_an_asymptotic_day_with_security_is_refused(self, reference_link: Link) -> None:
        daily = daily_key_volume(asymptotic(reference_link), degradations=DegradationLog())
        fields = self._daily_fields(daily)
        fields["security"] = reference_security()
        with pytest.raises(DomainError, match="must not carry SecurityParameters"):
            DailyKeyVolume(**fields)  # type: ignore[arg-type]


class TestTheModuleSurface:
    """What the module refuses to know, and what its repr says."""

    def test_it_does_not_compute_the_channel(self) -> None:
        """No loss-budget knob appears in any signature here.

        The contract is that the caller evaluates :mod:`quoss.channel` at the
        samples and hands back conditions; folding the budget in would put twelve
        optical arguments in this signature and make ``system`` depend on every
        knob of ``channel``.
        """
        forbidden = {
            "wavelength_m",
            "receive_aperture_m",
            "transmit_aperture_m",
            "zenith_transmittance",
            "pointing_jitter_rad",
            "sky_radiance_w_m2_um_sr",
        }
        for function in (pass_key_volume, asymptotic_pass_key_volume, daily_key_volume):
            assert forbidden.isdisjoint(inspect.signature(function).parameters)

    @pytest.mark.physics
    def test_the_reprs_name_the_regime(self, reference_link: Link) -> None:
        lower = finite(reference_link)
        upper = asymptotic(reference_link)
        assert "finite" in repr(lower)
        assert "asymptotic" in repr(upper)
        assert "bb84-decoy" in repr(lower)
        daily = daily_key_volume(lower, degradations=DegradationLog())
        assert "finite" in repr(daily)
        assert "n_days=1" in repr(daily)
        assert "n_passes=4" in repr(lower)

    @pytest.mark.physics
    def test_the_samples_travel_with_the_volume(self, reference_link: Link) -> None:
        """So a key volume can never be read without the mask it was computed at."""
        volume = finite(reference_link)
        assert isinstance(volume.samples, PassSamples)
        assert volume.samples.table.minimum_elevation_rad == pytest.approx(np.deg2rad(10.0))
        assert volume.n_passes == len(volume) == 4

    @pytest.mark.physics
    def test_key_per_pulse_is_zero_where_no_pulses_were_sent(self, reference_link: Link) -> None:
        """The guarded division, exercised on a volume with an empty pass."""
        volume = finite(reference_link)
        fields = {
            "samples": volume.samples,
            "regime": volume.regime,
            "key_bits": np.zeros(4),
            "pulses": np.zeros(4),
            "seconds": np.asarray(volume.seconds),
            "finite": volume.finite,
            "protocol": volume.protocol,
        }
        zeroed = PassKeyVolume(**fields)  # type: ignore[arg-type]
        assert zeroed.key_per_pulse.tolist() == [0.0, 0.0, 0.0, 0.0]
        assert zeroed.total_bits == 0.0
        assert not np.any(zeroed.has_key)
