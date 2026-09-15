"""Tests for `quoss.system.relay`.

Organised by the claim each block defends.

- ``TestTheStoreIdentity`` — **V1.** With an unbounded store the total delivered
  is exactly ``min(sum K_A, sum K_B)`` whatever the pass order; identical inputs
  return the whole total at zero latency; residuals are never both positive;
  every bit is paired or stored. Hypothesis over random pass sequences.
- ``TestAgainstAHandSimulatedStore`` — **V3 within the project**: the FIFO
  store, the latency of the oldest bit and the bit-weighted mean, re-simulated
  in plain Python on a small hand-written schedule where the answers can be
  read off.
- ``TestOnTheReferenceDay`` — the module docstring's table: Castelldefels to
  Tenerife (three deliveries, 6 114 / 33 780 / 5 703 s, 129 712 bits stranded)
  and to Calar Alto (59 s and then 39 822 s, because FIFO pairs the second
  delivery with the first pass's remainder).
- ``TestSecurityComposition`` — the union bound over the consumed blocks of both
  sides, ``None`` in the asymptotic regime and when nothing was delivered, and
  the refusal of a vacuous composition.
- ``TestTheScopeIsOneSatellite`` — a second satellite is refused with the
  decision named; no ISL stub exists.
- ``TestTheContainersRefuseImpossibleContents`` — every ``DomainError``.
"""

from __future__ import annotations

import inspect

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.types import TimeGrid
from quoss.qkd.base import KeyRegime
from quoss.qkd.finite_key import SecurityParameters
from quoss.system import relay as module
from quoss.system.key_volume import asymptotic_pass_key_volume, pass_key_volume
from quoss.system.relay import RelayKeyVolume, trusted_node_relay

from .reference import Link, conditions_at, link, reference_protocol
from .reference_stations import StationLink, station_link, synthetic_volume


@pytest.fixture(scope="module")
def reference_link() -> Link:
    return link()


@pytest.fixture(scope="module")
def castelldefels() -> StationLink:
    return station_link("castelldefels")


@pytest.fixture(scope="module")
def calar_alto() -> StationLink:
    return station_link("calar_alto")


@pytest.fixture(scope="module")
def tenerife() -> StationLink:
    return station_link("tenerife_ogs")


def schedule(
    windows_a: list[tuple[float, float]],
    bits_a: list[float],
    windows_b: list[tuple[float, float]],
    bits_b: list[float],
) -> RelayKeyVolume:
    """Relay two hand-written schedules on one satellite and one grid."""
    grid = TimeGrid.uniform(epoch_jd=2_460_676.5, duration_s=86_400.0, step_s=1.0)
    a = synthetic_volume([(s, e, 0) for s, e in windows_a], bits_a, grid=grid)
    b = synthetic_volume([(s, e, 0) for s, e in windows_b], bits_b, grid=grid)
    return trusted_node_relay(a, b, degradations=DegradationLog())


def hand_simulation(
    ends_a: list[float], bits_a: list[float], ends_b: list[float], bits_b: list[float]
) -> tuple[list[float], list[float], list[float]]:
    """Run a second FIFO store without arrays; return (delivered, oldest age, mean age)."""
    events = sorted(
        [(t, 0, k) for t, k in zip(ends_a, bits_a, strict=True) if k > 0]
        + [(t, 1, k) for t, k in zip(ends_b, bits_b, strict=True) if k > 0],
        key=lambda item: (item[0], item[1]),
    )
    stores: list[list[list[float]]] = [[], []]
    delivered, oldest, mean = [], [], []
    for t, side, k in events:
        other = stores[1 - side]
        left = k
        paired = 0.0
        ages: list[tuple[float, float]] = []
        while left > 0 and other:
            t0, stored = other[0]
            take = min(left, stored)
            ages.append((t - t0, take))
            left -= take
            paired += take
            if take == stored:
                other.pop(0)
            else:
                other[0][1] -= take
        if paired > 0:
            delivered.append(paired)
            oldest.append(max(age for age, _ in ages))
            mean.append(sum(age * w for age, w in ages) / paired)
        if left > 0:
            stores[side].append([t, left])
    return delivered, oldest, mean


class TestTheStoreIdentity:
    """**V1**: what an unbounded store guarantees regardless of order."""

    @pytest.mark.physics
    def test_identical_inputs_return_the_whole_total_at_zero_latency(
        self, reference_link: Link
    ) -> None:
        volume = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
            degradations=DegradationLog(),
        )
        result = trusted_node_relay(volume, volume, degradations=DegradationLog())
        assert result.total_bits == volume.total_bits
        assert result.delivered_bits.tolist() == [190_581.0, 242_404.0]
        assert result.latency_s.tolist() == [0.0, 0.0]
        assert result.mean_latency_s.tolist() == [0.0, 0.0]
        assert result.stranded_bits == 0.0
        assert result.n_deliveries == len(result) == 2
        # Ties in end time put A first, so B's pass is the one that delivers.
        assert result.delivering_side.tolist() == [1, 1]
        assert result.delivering_pass.tolist() == [0, 2]

    @pytest.mark.physics
    @given(
        bits_a=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=6),
        bits_b=st.lists(st.integers(min_value=0, max_value=1000), min_size=1, max_size=6),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=150, deadline=None)
    def test_the_total_is_the_minimum_of_the_two_sums_whatever_the_order(
        self, bits_a: list[float], bits_b: list[float], seed: int
    ) -> None:
        rng = np.random.default_rng(seed)
        # Disjoint by construction: every gap exceeds the 300 s window, so no two
        # windows overlap however they are split between the two sides. Drawing
        # starts independently on [0, 80000) does not give that — two of them can
        # land within 300 s of each other, and the result is two passes of *one*
        # satellite overlapping in time, which `PassTable` rejects as physically
        # impossible. It is right to reject it; the generator was wrong to build
        # it. Hypothesis found it at seed 275 with six windows, after the shape
        # had been in the suite long enough to look safe.
        gaps = rng.uniform(310.0, 6_000.0, size=len(bits_a) + len(bits_b))
        starts = np.cumsum(gaps)
        windows = [(float(s), float(s) + 300.0) for s in starts]
        rng.shuffle(windows)
        result = schedule(windows[: len(bits_a)], bits_a, windows[len(bits_a) :], bits_b)
        assert result.total_bits == pytest.approx(min(sum(bits_a), sum(bits_b)), abs=1e-6)
        assert result.total_bits == pytest.approx(result.upper_bound_bits, abs=1e-6)
        assert min(result.residual_a_bits, result.residual_b_bits) == 0.0
        assert result.total_bits + result.residual_a_bits == pytest.approx(sum(bits_a), abs=1e-6)
        assert result.total_bits + result.residual_b_bits == pytest.approx(sum(bits_b), abs=1e-6)
        assert np.all(result.delivered_bits > 0.0)
        assert np.all(result.latency_s >= 0.0)
        assert np.all(result.mean_latency_s <= result.latency_s + 1e-9)
        assert float(result.daily_bits.sum()) == pytest.approx(result.total_bits, abs=1e-6)

    @pytest.mark.physics
    def test_the_order_changes_when_and_not_how_much(self) -> None:
        """A then B delivers at B's end; B then A delivers at A's end; both deliver the same."""
        a_first = schedule([(1000.0, 1500.0)], [100.0], [(5000.0, 5500.0)], [70.0])
        b_first = schedule([(5000.0, 5500.0)], [100.0], [(1000.0, 1500.0)], [70.0])
        assert a_first.total_bits == b_first.total_bits == 70.0
        assert a_first.delivering_side.tolist() == [1]
        assert b_first.delivering_side.tolist() == [0]
        assert a_first.delivered_at_s.tolist() == b_first.delivered_at_s.tolist() == [5500.0]
        assert a_first.latency_s.tolist() == b_first.latency_s.tolist() == [4000.0]
        assert a_first.residual_a_bits == 30.0 and b_first.residual_a_bits == 30.0

    @pytest.mark.physics
    def test_a_dead_pass_is_not_an_event(self) -> None:
        result = schedule(
            [(1000.0, 1500.0), (3000.0, 3500.0)], [0.0, 10.0], [(5000.0, 5500.0)], [10.0]
        )
        assert result.n_deliveries == 1
        assert result.latency_s.tolist() == [2000.0]

    @pytest.mark.physics
    def test_nothing_delivered_is_a_valid_empty_result(self) -> None:
        """One side never yields: no events, no security claim, everything stranded."""
        result = schedule([(1000.0, 1500.0)], [100.0], [(5000.0, 5500.0)], [0.0])
        assert result.n_deliveries == 0
        assert result.total_bits == 0.0
        assert result.residual_a_bits == 100.0 and result.residual_b_bits == 0.0
        assert result.security is None
        assert result.day_number.shape == (0,)


class TestAgainstAHandSimulatedStore:
    """**V3 within the project**: two implementations of the FIFO store."""

    @pytest.mark.physics
    def test_a_schedule_whose_answers_can_be_read_off(self) -> None:
        """A: 100 @ 1000 s, 50 @ 6000 s.  B: 30 @ 2000 s, 150 @ 8000 s.

        Event 1 (B, 2000 s): pairs 30 of A's 100, age 1000 s. A keeps 70.
        Event 2 (B, 8000 s): pairs A's 70 (age 7000 s) and A's 50 (age 2000 s):
        120 delivered, oldest 7000 s, mean (70 x 7000 + 50 x 2000) / 120 = 4917 s.
        B keeps 30 stranded.
        """
        result = schedule(
            [(500.0, 1000.0), (5500.0, 6000.0)],
            [100.0, 50.0],
            [(1500.0, 2000.0), (7500.0, 8000.0)],
            [30.0, 150.0],
        )
        assert result.delivered_bits.tolist() == [30.0, 120.0]
        assert result.latency_s.tolist() == [1000.0, 7000.0]
        assert result.mean_latency_s.tolist() == pytest.approx(
            [1000.0, (70 * 7000 + 50 * 2000) / 120]
        )
        assert result.residual_b_bits == 30.0 and result.residual_a_bits == 0.0
        assert result.delivering_side.tolist() == [1, 1]
        assert result.delivering_pass.tolist() == [0, 1]

    @pytest.mark.physics
    @given(
        bits_a=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=5),
        bits_b=st.lists(st.integers(min_value=0, max_value=100), min_size=1, max_size=5),
        seed=st.integers(min_value=0, max_value=2**31 - 1),
    )
    @settings(max_examples=150, deadline=None)
    def test_the_vectorised_bookkeeping_matches_a_plain_python_store(
        self, bits_a: list[float], bits_b: list[float], seed: int
    ) -> None:
        rng = np.random.default_rng(seed)
        n = len(bits_a) + len(bits_b)
        starts = np.sort(rng.choice(np.arange(0, 80_000, 400), size=n, replace=False)).astype(float)
        windows = [(float(s), float(s) + 300.0) for s in starts]
        rng.shuffle(windows)
        windows_a, windows_b = windows[: len(bits_a)], windows[len(bits_a) :]
        result = schedule(windows_a, bits_a, windows_b, bits_b)
        # `synthetic_volume` sorts each side's passes by start, as a PassTable must.
        ends_a = sorted(e for _, e in windows_a)
        ends_b = sorted(e for _, e in windows_b)
        order_a = np.argsort([s for s, _ in windows_a])
        order_b = np.argsort([s for s, _ in windows_b])
        delivered, oldest, mean = hand_simulation(
            ends_a, [bits_a[i] for i in order_a], ends_b, [bits_b[i] for i in order_b]
        )
        assert result.delivered_bits.tolist() == pytest.approx(delivered, abs=1e-9)
        assert result.latency_s.tolist() == pytest.approx(oldest, abs=1e-9)
        assert result.mean_latency_s.tolist() == pytest.approx(mean, abs=1e-9)


class TestOnTheReferenceDay:
    """The module docstring's table, regenerated."""

    @pytest.mark.reference
    def test_castelldefels_to_tenerife(
        self, castelldefels: StationLink, tenerife: StationLink
    ) -> None:
        log = DegradationLog()
        result = trusted_node_relay(
            castelldefels.volume,
            tenerife.volume,
            degradations=log,
            names=("castelldefels", "tenerife_ogs"),
        )
        assert result.delivered_bits.tolist() == [190_581.0, 38_270.0, 204_134.0]
        assert result.delivering_side.tolist() == [1, 0, 1]
        assert result.delivering_pass.tolist() == [0, 2, 1]
        assert result.latency_s.tolist() == pytest.approx([6113.9, 33_779.9, 5703.5], abs=0.1)
        assert result.mean_latency_s.tolist() == pytest.approx(result.latency_s.tolist(), abs=1e-9)
        assert result.total_bits == 432_985.0
        assert result.upper_bound_bits == 432_985.0
        assert result.total_b_bits == 562_697.0
        assert result.residual_a_bits == 0.0
        assert result.residual_b_bits == 129_712.0
        assert result.stranded_bits == 129_712.0
        assert result.daily_bits.tolist() == [432_985.0]
        assert float(result.latency_s.min()) / 3600.0 == pytest.approx(1.58, abs=0.01)
        assert float(result.latency_s.max()) / 3600.0 == pytest.approx(9.38, abs=0.01)
        # Two blocks of each side were consumed: 4 x 1e-10.
        assert result.security is not None
        assert result.security.secrecy == pytest.approx(4e-10, rel=1e-12)
        codes = [e.code for e in log]
        assert codes == ["relay.trusted-node", "relay.key-stranded-on-board"]
        stranded = log.entries[1]
        assert stranded.severity is Severity.WARNING
        assert stranded.details["station"] == "tenerife_ogs"
        assert stranded.details["stranded_bits"] == 129_712.0
        assert "castelldefels" in repr(result) and "tenerife_ogs" in repr(result)

    @pytest.mark.reference
    def test_castelldefels_to_calar_alto_shows_the_fifo_latency(
        self, castelldefels: StationLink, calar_alto: StationLink
    ) -> None:
        """Fast and poor: 59 s for the first delivery, then 11 hours for the second."""
        result = trusted_node_relay(
            castelldefels.volume, calar_alto.volume, degradations=DegradationLog()
        )
        assert result.delivered_bits.tolist() == [47_108.0, 9_817.0]
        assert result.total_bits == 56_925.0 == result.upper_bound_bits
        assert result.latency_s.tolist() == pytest.approx([59.1, 39_822.0], abs=0.1)
        # Calar Alto's second live pass ends 72 s BEFORE Castelldefels' second one,
        # so it is paired with the remainder of Castelldefels' FIRST pass.
        a, c = castelldefels.table, calar_alto.table
        assert float(a.end_s[2] - c.end_s[2]) == pytest.approx(71.8, abs=0.1)
        assert result.residual_a_bits == 432_985.0 - 56_925.0

    @pytest.mark.reference
    def test_the_relay_is_symmetric_in_its_arguments_up_to_the_side_label(
        self, castelldefels: StationLink, tenerife: StationLink
    ) -> None:
        forward = trusted_node_relay(
            castelldefels.volume, tenerife.volume, degradations=DegradationLog()
        )
        backward = trusted_node_relay(
            tenerife.volume, castelldefels.volume, degradations=DegradationLog()
        )
        assert forward.delivered_bits.tolist() == backward.delivered_bits.tolist()
        assert forward.latency_s.tolist() == backward.latency_s.tolist()
        assert forward.delivering_side.tolist() == [
            1 - s for s in backward.delivering_side.tolist()
        ]
        assert forward.residual_b_bits == backward.residual_a_bits


class TestSecurityComposition:
    """The union bound over both sides' consumed blocks."""

    @pytest.mark.physics
    def test_only_consumed_blocks_count(self, reference_link: Link) -> None:
        """A relay that consumes one block of A and one of B is 2 eps, not 4 eps.

        B is the reference day restricted to its first pass, so A's first pass
        pairs with it at zero latency and A's second live pass is stranded: two
        blocks consumed, one per side, and the union bound counts exactly those.
        """
        security = SecurityParameters(correctness=1e-10, secrecy=3e-11)
        volume = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=security,
            degradations=DegradationLog(),
        )
        first_only = reference_link.table.select(np.array([True, False, False, False])).samples()
        one_pass = pass_key_volume(
            conditions_at(reference_link.angles, first_only),
            samples=first_only,
            protocol=reference_protocol(),
            security=security,
            degradations=DegradationLog(),
        )
        log = DegradationLog()
        result = trusted_node_relay(volume, one_pass, degradations=log)
        # At secrecy 3e-11 the blocks certify less than at the reference 1e-10
        # (178 672 for pass 1 against 190 581), which is the tighter claim's price.
        assert float(volume.key_bits[0]) == 178_672.0
        assert result.delivered_bits.tolist() == [float(volume.key_bits[0])]
        assert result.residual_a_bits == float(volume.key_bits[2])
        assert result.security is not None
        assert result.security.secrecy == pytest.approx(2 * 3e-11, rel=1e-12)
        assert result.security.correctness == pytest.approx(2e-10, rel=1e-12)
        entry = log.entries[0]
        assert entry.details["blocks_a"] == 1 and entry.details["blocks_b"] == 1
        assert "MUST BE TRUSTED" in entry.message
        # And the same day relayed to itself consumes all four: 4 eps.
        both = trusted_node_relay(volume, volume, degradations=DegradationLog())
        assert both.security is not None
        assert both.security.secrecy == pytest.approx(4 * 3e-11, rel=1e-12)

    @pytest.mark.physics
    def test_a_finite_relay_that_delivers_nothing_makes_no_claim(
        self, reference_link: Link
    ) -> None:
        """B is the reference day's dead second pass: finite regime, zero key, no deliveries."""
        dead_only = reference_link.table.select(np.array([False, True, False, False])).samples()
        dead = pass_key_volume(
            conditions_at(reference_link.angles, dead_only),
            samples=dead_only,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
            degradations=DegradationLog(),
        )
        assert dead.total_bits == 0.0 and dead.regime is KeyRegime.FINITE
        live = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
            degradations=DegradationLog(),
        )
        log = DegradationLog()
        result = trusted_node_relay(live, dead, degradations=log)
        assert result.n_deliveries == 0
        assert result.regime is KeyRegime.FINITE
        assert result.security is None
        assert result.residual_a_bits == live.total_bits
        entry = next(e for e in log if e.code == "relay.trusted-node")
        assert "Nothing was delivered" in entry.message
        assert entry.details["composed_secrecy"] is None

    @pytest.mark.physics
    def test_an_asymptotic_relay_carries_no_claim_and_says_so(self, reference_link: Link) -> None:
        upper = asymptotic_pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            degradations=DegradationLog(),
        )
        log = DegradationLog()
        result = trusted_node_relay(upper, upper, degradations=log)
        assert result.regime is KeyRegime.ASYMPTOTIC
        assert result.security is None
        assert result.total_bits == pytest.approx(upper.total_bits, rel=1e-12)
        entry = next(e for e in log if e.code == "relay.no-security-claim")
        assert entry.severity is Severity.WARNING

    @pytest.mark.physics
    def test_a_vacuous_composition_is_refused(self, reference_link: Link) -> None:
        """Two ways to reach one: within one side, or only once the two sides are added.

        One pass on each side at eps = 0.6: each side alone composes to 0.6, a
        probability, and the pair to 1.2, which is not. That is the relay's own
        refusal, distinct from ``composed_security`` refusing a single side
        (eps = 0.3 over four blocks, below). Only consumed blocks count, which
        is why one pass per side is the construction: a four-pass A paired with
        a one-pass B consumes one block of each and composes to 2 eps.
        """
        loose = SecurityParameters(correctness=0.6, secrecy=0.6)
        first_only = reference_link.table.select(np.array([True, False, False, False])).samples()
        one_pass = pass_key_volume(
            conditions_at(reference_link.angles, first_only),
            samples=first_only,
            protocol=reference_protocol(),
            security=loose,
            degradations=DegradationLog(),
        )
        assert one_pass.total_bits > 0.0
        with pytest.raises(DomainError, match=r"1 blocks of A and 1 of B gives eps_cor = 1\.2"):
            trusted_node_relay(one_pass, one_pass, degradations=DegradationLog())
        looser = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=0.3, secrecy=0.3),
            degradations=DegradationLog(),
        )
        with pytest.raises(DomainError, match="composing 4 blocks at correctness"):
            trusted_node_relay(looser, looser, degradations=DegradationLog())

    def test_the_composition_is_a_sum_and_the_docstring_says_why(self) -> None:
        assert module.__doc__ is not None
        assert "union bound" in module.__doc__
        assert "xor" in module.__doc__


class TestTheScopeIsOneSatellite:
    """No ISL, no stub, and the decision is named."""

    def test_a_second_satellite_is_refused(self) -> None:
        grid = TimeGrid.uniform(epoch_jd=2_460_676.5, duration_s=86_400.0, step_s=1.0)
        a = synthetic_volume([(1000.0, 1500.0, 0)], [10.0], grid=grid)
        b = synthetic_volume([(5000.0, 5500.0, 1)], [10.0], grid=grid)
        with pytest.raises(DomainError, match=r"OUT OF SCOPE.*2026-09-10"):
            trusted_node_relay(a, b, degradations=DegradationLog())

    def test_there_is_no_isl_anywhere_on_the_surface(self) -> None:
        assert not any("isl" in name.lower() for name in module.__all__)
        assert not any("isl" in p.lower() for p in inspect.signature(trusted_node_relay).parameters)
        assert module.__doc__ is not None and "Inter-satellite links" in module.__doc__


class TestTheContainersRefuseImpossibleContents:
    """Every ``DomainError`` of the relay and its container."""

    def test_a_non_volume_is_refused(self, reference_link: Link) -> None:
        with pytest.raises(DomainError, match="volume_b must be a PassKeyVolume"):
            trusted_node_relay(
                synthetic_volume([(1.0, 5.0, 0)], [1.0]),
                reference_link.table,  # type: ignore[arg-type]
                degradations=DegradationLog(),
            )

    def test_different_grids_are_refused(self) -> None:
        a = synthetic_volume([(1000.0, 1500.0, 0)], [10.0])
        b = synthetic_volume(
            [(1000.0, 1500.0, 0)],
            [10.0],
            grid=TimeGrid.uniform(epoch_jd=2_460_677.5, duration_s=86_400.0, step_s=1.0),
        )
        with pytest.raises(DomainError, match="different time grids"):
            trusted_node_relay(a, b, degradations=DegradationLog())

    def test_different_regimes_are_refused(self, reference_link: Link) -> None:
        finite = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
            degradations=DegradationLog(),
        )
        upper = synthetic_volume([(1000.0, 1500.0, 0)], [10.0], grid=reference_link.grid)
        with pytest.raises(DomainError, match="neither"):
            trusted_node_relay(finite, upper, degradations=DegradationLog())

    @pytest.fixture
    def result(self) -> RelayKeyVolume:
        return schedule(
            [(500.0, 1000.0), (5500.0, 6000.0)],
            [100.0, 50.0],
            [(1500.0, 2000.0), (7500.0, 8000.0)],
            [30.0, 150.0],
        )

    @staticmethod
    def _fields(result: RelayKeyVolume) -> dict[str, object]:
        return {
            "names": result.names,
            "delivered_bits": np.array(result.delivered_bits),
            "delivered_at_s": np.array(result.delivered_at_s),
            "delivering_side": np.array(result.delivering_side),
            "delivering_pass": np.array(result.delivering_pass),
            "latency_s": np.array(result.latency_s),
            "mean_latency_s": np.array(result.mean_latency_s),
            "day_number": np.array(result.day_number),
            "daily_bits": np.array(result.daily_bits),
            "total_a_bits": result.total_a_bits,
            "total_b_bits": result.total_b_bits,
            "residual_a_bits": result.residual_a_bits,
            "residual_b_bits": result.residual_b_bits,
            "security": result.security,
            "regime": result.regime,
            "protocols": result.protocols,
        }

    @pytest.mark.parametrize(
        ("field", "value", "message"),
        [
            ("names", ("A",), "two non-empty station names"),
            ("protocols", ("x", ""), "two non-empty names"),
            ("delivered_bits", np.zeros((2, 1)), "must be 1-D"),
            ("delivered_bits", np.array([0.0, 120.0]), "strictly positive"),
            ("delivered_at_s", np.zeros(3), "there are 2 events"),
            ("latency_s", np.array([np.nan, 1.0]), "non-finite"),
            ("latency_s", np.array([-1.0, 7000.0]), "cannot be negative"),
            ("mean_latency_s", np.array([2000.0, 7000.0]), "cannot exceed latency_s"),
            ("delivering_side", np.array([1, 2]), r"0 \(a pass over A\) or 1"),
            ("delivering_side", np.zeros(3, dtype=np.int64), "there are 2 events"),
            ("delivering_pass", np.array([-1, 0]), "must index a pass table"),
            ("day_number", np.array([5, 4]), "strictly ascending"),
            ("daily_bits", np.array([-1.0]), "one per day_number"),
            ("daily_bits", np.array([10.0]), "sum to the delivered total"),
            ("total_a_bits", -1.0, "finite and non-negative"),
            ("residual_a_bits", 5.0, "both residuals are positive"),
            ("total_b_bits", 999.0, "Every bit is either paired or stored"),
        ],
    )
    def test_invalid_results_are_refused(
        self, result: RelayKeyVolume, field: str, value: object, message: str
    ) -> None:
        fields = self._fields(result)
        fields[field] = value
        with pytest.raises(DomainError, match=message):
            RelayKeyVolume(**fields)  # type: ignore[arg-type]

    def test_a_finite_relay_that_delivered_must_carry_security(self, reference_link: Link) -> None:
        finite = pass_key_volume(
            reference_link.conditions,
            samples=reference_link.samples,
            protocol=reference_protocol(),
            security=SecurityParameters(correctness=1e-10, secrecy=1e-10),
            degradations=DegradationLog(),
        )
        result = trusted_node_relay(finite, finite, degradations=DegradationLog())
        fields = self._fields(result)
        fields["security"] = None
        with pytest.raises(DomainError, match="must carry the composed SecurityParameters"):
            RelayKeyVolume(**fields)  # type: ignore[arg-type]

    def test_an_asymptotic_relay_must_not_carry_security(self, result: RelayKeyVolume) -> None:
        fields = self._fields(result)
        fields["security"] = SecurityParameters(correctness=1e-10, secrecy=1e-10)
        with pytest.raises(DomainError, match="security must be None"):
            RelayKeyVolume(**fields)  # type: ignore[arg-type]
