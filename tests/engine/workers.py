"""Work functions for `test_parallel.py`, at module level so a spawned worker can import them.

A worker started with the ``spawn`` method is a fresh interpreter: it receives
the *reference* ``engine.workers.square`` and imports it, rather than a copy of
a closure. A function defined inside a test — or inside a test class — has no
importable name, so pickling it fails before any work starts. That is the whole
reason this file exists.
"""

from __future__ import annotations

import os

from quoss.core.errors import DegradationLog


def square(item: int, degradations: DegradationLog) -> int:
    """Square a number, recording the item and the process that squared it."""
    degradations.info(
        "test.square",
        f"squared {item}",
        where="tests.engine.workers",
        item=item,
        pid=os.getpid(),
    )
    return item * item


def fail_on(item: int, degradations: DegradationLog) -> int:
    """Square every item except 3, which raises after having recorded a warning.

    The warning before the raise is the point: the contract is that the log of a
    failing item is *discarded*, and a function that recorded nothing could not
    tell a discarded log from an empty one.
    """
    degradations.warn(
        "test.about-to-work",
        f"working on {item}",
        where="tests.engine.workers",
        item=item,
    )
    if item == 3:
        raise ValueError("item 3 is not welcome")
    return item * item


def process_id(item: int, degradations: DegradationLog) -> int:
    """Return the process id that ran the item, so a test can count the processes."""
    del degradations
    del item
    return os.getpid()
