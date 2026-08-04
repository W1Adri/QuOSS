"""Tests for the random source.

Two properties matter and both are load-bearing for the Monte Carlo layer:
a run must reproduce from its recorded seed, and parallel streams must be
independent — because the ensemble spread *is* the result.
"""

import numpy as np
import pytest

from quoss.core.rng import RandomSource


class TestReproducibility:
    """The same seed must give the same numbers, always."""

    def test_same_seed_gives_identical_draws(self) -> None:
        a = RandomSource.from_seed(20260731).generator.normal(size=1000)
        b = RandomSource.from_seed(20260731).generator.normal(size=1000)
        assert np.array_equal(a, b)

    def test_different_seeds_give_different_draws(self) -> None:
        a = RandomSource.from_seed(1).generator.normal(size=1000)
        b = RandomSource.from_seed(2).generator.normal(size=1000)
        assert not np.array_equal(a, b)

    def test_seed_is_recorded(self) -> None:
        """The seed goes into result provenance, so it must be readable back."""
        assert RandomSource.from_seed(42).seed == 42

    def test_unseeded_source_still_records_a_seed(self) -> None:
        """`seed=None` means "draw one and tell me which", never "unseeded"."""
        src = RandomSource.from_seed(None)
        assert isinstance(src.seed, int)
        assert src.seed >= 0

    def test_recorded_seed_reproduces_an_unseeded_run(self) -> None:
        """The property that makes an unseeded run publishable after the fact."""
        original = RandomSource.from_seed(None)
        drawn = original.generator.normal(size=100)
        replay = RandomSource.from_seed(original.seed).generator.normal(size=100)
        assert np.array_equal(drawn, replay)

    def test_two_unseeded_sources_differ(self) -> None:
        a = RandomSource.from_seed(None)
        b = RandomSource.from_seed(None)
        assert a.seed != b.seed

    def test_recorded_seed_is_json_and_yaml_friendly(self) -> None:
        """A numpy integer would break a plain YAML dump of the provenance block."""
        import json

        seed = RandomSource.from_seed(None).seed
        assert type(seed) is int
        assert json.loads(json.dumps({"seed": seed}))["seed"] == seed

    def test_negative_seed_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="non-negative"):
            RandomSource.from_seed(-1)


class TestSpawning:
    """Parallel streams: independent, and reproducible from the parent seed."""

    def test_children_are_distinct(self) -> None:
        children = RandomSource.from_seed(7).spawn(8)
        draws = [tuple(c.generator.normal(size=5)) for c in children]
        assert len(set(draws)) == 8

    def test_child_streams_are_uncorrelated(self) -> None:
        """Independence is the whole point: correlated workers understate spread.

        `seed + index` would fail a test like this; SeedSequence.spawn passes it.
        """
        children = RandomSource.from_seed(11).spawn(2)
        a = children[0].generator.normal(size=20_000)
        b = children[1].generator.normal(size=20_000)
        correlation = float(np.corrcoef(a, b)[0, 1])
        # For 20k independent samples the sample correlation is ~N(0, 1/sqrt(N)),
        # i.e. sigma ~ 0.007. A 0.05 bound is ~7 sigma: tight, but not flaky.
        assert abs(correlation) < 0.05

    def test_ensemble_reproduces_from_the_parent_seed(self) -> None:
        """Re-running with the same seed gives the same ensemble, worker by worker."""
        first = [c.generator.normal(size=10) for c in RandomSource.from_seed(3).spawn(4)]
        second = [c.generator.normal(size=10) for c in RandomSource.from_seed(3).spawn(4)]
        for a, b in zip(first, second, strict=True):
            assert np.array_equal(a, b)

    def test_ensemble_is_independent_of_worker_count(self) -> None:
        """Child k depends on the parent seed and k, not on how many siblings ran.

        This is what makes a Monte Carlo result independent of the machine's core
        count — otherwise a figure would change when run on a bigger laptop.
        """
        few = RandomSource.from_seed(5).spawn(2)
        many = RandomSource.from_seed(5).spawn(16)
        for i in range(2):
            assert np.array_equal(
                few[i].generator.normal(size=10), many[i].generator.normal(size=10)
            )

    def test_children_report_the_parent_seed(self) -> None:
        """The seed identifies the ensemble; spawn position identifies the stream."""
        parent = RandomSource.from_seed(99)
        assert all(child.seed == 99 for child in parent.spawn(3))

    def test_repeated_spawning_keeps_producing_new_streams(self) -> None:
        """Two calls of spawn(2) give four streams, not two duplicated pairs."""
        parent = RandomSource.from_seed(13)
        first = parent.spawn(2)
        second = parent.spawn(2)
        draws = [tuple(c.generator.normal(size=5)) for c in (*first, *second)]
        assert len(set(draws)) == 4

    def test_grandchildren_are_distinct(self) -> None:
        """Nesting works: passes within a scenario, realisations within a pass."""
        child = RandomSource.from_seed(17).spawn(1)[0]
        grandchildren = child.spawn(4)
        draws = [tuple(g.generator.normal(size=5)) for g in grandchildren]
        assert len(set(draws)) == 4

    @pytest.mark.parametrize("n", [0, -1])
    def test_non_positive_spawn_count_is_rejected(self, n: int) -> None:
        with pytest.raises(ValueError, match="positive"):
            RandomSource.from_seed(1).spawn(n)

    def test_spawn_returns_a_tuple_in_index_order(self) -> None:
        children = RandomSource.from_seed(1).spawn(3)
        assert isinstance(children, tuple)
        assert len(children) == 3


class TestGeneratorInterface:
    """What physics functions actually receive."""

    def test_generator_is_a_numpy_generator(self) -> None:
        assert isinstance(RandomSource.from_seed(1).generator, np.random.Generator)

    def test_generator_identity_is_stable(self) -> None:
        """Repeated access must not silently reset the stream."""
        src = RandomSource.from_seed(1)
        assert src.generator is src.generator

    def test_draws_advance_the_stream(self) -> None:
        src = RandomSource.from_seed(1)
        assert not np.array_equal(src.generator.normal(size=5), src.generator.normal(size=5))

    def test_repr_shows_the_seed(self) -> None:
        assert "123" in repr(RandomSource.from_seed(123))

    def test_child_repr_shows_its_spawn_position(self) -> None:
        """So a log line can identify which stream produced a number."""
        child = RandomSource.from_seed(1).spawn(2)[1]
        assert "spawn_key" in repr(child)


class TestStatisticalSanity:
    """A seeded generator must still be a correct generator."""

    def test_normal_draws_have_the_right_moments(self) -> None:
        x = RandomSource.from_seed(2024).generator.normal(loc=0.0, scale=1.0, size=200_000)
        assert float(np.mean(x)) == pytest.approx(0.0, abs=0.01)
        assert float(np.std(x)) == pytest.approx(1.0, abs=0.01)

    def test_uniform_draws_span_the_unit_interval(self) -> None:
        x = RandomSource.from_seed(2024).generator.uniform(size=100_000)
        assert 0.0 <= x.min() < 0.001
        assert 0.999 < x.max() <= 1.0
