"""The single source of randomness, injectable and recordable.

Three rules, and each one exists because breaking it costs a retracted figure:

1. **One generator, injected.** Nothing in QuOSS calls ``np.random.normal`` or
   the legacy global functions. A function that needs randomness takes a
   ``numpy.random.Generator`` as an argument. The global state of the legacy API
   is shared, order-dependent and invisible in a call signature; a Monte Carlo
   run whose result depends on what ran before it is not reproducible.

2. **The seed is always known.** ``seed=None`` does not mean "unseeded", it means
   "draw one from the OS and *tell me which*". :attr:`RandomSource.seed` is
   always an integer that reproduces the run, and it is what goes into the
   result provenance.

3. **Parallel streams are spawned, never derived by arithmetic.**
   ``seed + worker_index`` produces streams whose correlation is unquantified.
   :meth:`RandomSource.spawn` uses ``SeedSequence.spawn``, which is designed to
   give statistically independent children. Independence matters here: the
   ensemble spread of a Monte Carlo *is* the result, so correlated workers would
   understate the uncertainty the simulator exists to quantify.

Examples
--------
>>> src = RandomSource.from_seed(20260731)
>>> src.seed
20260731
>>> a = RandomSource.from_seed(20260731).generator.normal(size=3)
>>> b = RandomSource.from_seed(20260731).generator.normal(size=3)
>>> bool((a == b).all())
True

Workers get independent streams that still reproduce from the parent seed:

>>> workers = RandomSource.from_seed(7).spawn(4)
>>> len({w.generator.integers(0, 2**62) for w in workers})
4
"""

from __future__ import annotations

from typing import Any

import numpy as np

__all__ = ["RandomSource"]

_MAX_SEED = 2**64
"""Seeds are reduced into ``[0, 2**64)`` so they round-trip through JSON/YAML."""


class RandomSource:
    """A seeded generator plus the seed that reproduces it.

    Immutable. Construct with :meth:`from_seed` rather than calling the
    initialiser, so that the recorded seed and the generator cannot disagree.

    The generator itself is of course stateful — that is what a generator is.
    What is immutable is the *identity* of this source: its seed and its position
    in the spawn tree. Drawing from :attr:`generator` advances it, so a source is
    not reusable for two independent draws; spawn a child instead.

    Parameters
    ----------
    seed : int
        The entropy that reproduces this source. Recorded in result provenance.
    seed_sequence : numpy.random.SeedSequence
        The sequence built from ``seed``, kept so children can be spawned from
        it rather than from arithmetic on the seed.
    """

    __slots__ = ("_generator", "_seed", "_seed_sequence")

    def __init__(self, seed: int, seed_sequence: np.random.SeedSequence) -> None:
        self._seed = int(seed)
        self._seed_sequence = seed_sequence
        self._generator = np.random.default_rng(seed_sequence)

    # -- construction ------------------------------------------------------- #
    @classmethod
    def from_seed(cls, seed: int | None = None) -> RandomSource:
        """Build a source from a seed, drawing one from the OS if none is given.

        Parameters
        ----------
        seed : int, optional
            Seed to reproduce. If ``None``, entropy is drawn from the operating
            system and reduced to an integer that is then recorded in
            :attr:`seed` — so a run started without a seed is still reproducible
            after the fact.

        Returns
        -------
        RandomSource
            A source whose :attr:`seed` reproduces it exactly.

        Raises
        ------
        ValueError
            If ``seed`` is negative.
        """
        if seed is None:
            # SeedSequence() with no argument pulls fresh OS entropy; reading it
            # back is what turns "unseeded" into "seeded with a value we logged".
            drawn = np.random.SeedSequence()
            entropy: Any = drawn.entropy
            seed = int(np.asarray(entropy, dtype=object).sum()) % _MAX_SEED
        if seed < 0:
            raise ValueError(f"seed must be non-negative, got {seed}.")
        return cls(seed=seed, seed_sequence=np.random.SeedSequence(seed))

    # -- accessors ---------------------------------------------------------- #
    @property
    def seed(self) -> int:
        """The seed that reproduces this source. Goes into result provenance."""
        return self._seed

    @property
    def generator(self) -> np.random.Generator:
        """The generator to draw from. Pass this into physics functions."""
        return self._generator

    @property
    def seed_sequence(self) -> np.random.SeedSequence:
        """The underlying sequence. Needed only to spawn children."""
        return self._seed_sequence

    # -- parallelism -------------------------------------------------------- #
    def spawn(self, n: int) -> tuple[RandomSource, ...]:
        """Create ``n`` statistically independent child sources.

        The intended way to parallelise: one child per worker, per pass, or per
        Monte Carlo realisation. The children depend only on this source's seed
        and their index, so the whole ensemble reproduces from the parent seed
        regardless of how many workers happened to run, or in what order they
        finished.

        Parameters
        ----------
        n : int
            Number of children. Must be positive.

        Returns
        -------
        tuple[RandomSource, ...]
            Children in index order. Each child's :attr:`seed` is the parent seed
            — the seed identifies the *ensemble*, and the child's position in the
            spawn order identifies the stream within it.

        Raises
        ------
        ValueError
            If ``n`` is not positive.

        Notes
        -----
        Repeated calls on the same parent keep spawning *new* children:
        ``SeedSequence`` tracks how many it has produced. Two calls of
        ``spawn(2)`` therefore give four distinct streams, not two pairs of
        duplicates.
        """
        if n <= 0:
            raise ValueError(f"n must be positive, got {n}.")
        return tuple(
            RandomSource(seed=self._seed, seed_sequence=child)
            for child in self._seed_sequence.spawn(n)
        )

    def __repr__(self) -> str:
        spawn_key = self._seed_sequence.spawn_key
        path = f", spawn_key={spawn_key}" if spawn_key else ""
        return f"RandomSource(seed={self._seed}{path})"
