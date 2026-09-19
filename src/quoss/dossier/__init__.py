"""The three experiment dossiers: the simulator stops being code and becomes an answer.

What this package is, for someone arriving new
----------------------------------------------
Everything else under ``quoss`` produces *numbers*: a result object, a CSV, a
row in a validation table. This package produces the three **documents** that
somebody outside the code reads in order to decide something -- whether to buy a
lens, whether to lend an optical bench, whether a mountain station is worth its
access road.

There are three, one per experiment, all committed under ``docs/experiments/``:

``GE-1.md``
    Two ground terminals a kilometre apart, one way. The field link: its
    architecture, its budget term by term, what a bigger receiving lens buys,
    and the distance past which the certified key is zero while the asymptotic
    calculation still claims kilobits.
``GE-0b.md``
    Two metres of optical bench with a turbulence emulator. What it rehearses
    of GE-1 and -- the part worth the document -- what it does not, with the
    question to put to a manufacturer written out to be pasted into an email.
``reference-link.md``
    The reference day: the satellite link every number in this project is
    measured on. Which passes certify nothing, where the elevation mask's
    interior optimum is and in which turbulence regime, what standing high is
    worth at three stations, and which of the two mutually inconsistent
    published reference links is in use.

The one rule
------------
**Nothing in these documents is transcribed by hand.** Every figure comes out
of a run the generator made, the documents are committed, and
``tests/dossier/test_docs.py`` re-renders them and fails when the committed
bytes differ. The reasoning is in :mod:`quoss.dossier.base`, and the short
version is that a number copied into a document that gets taken to a meeting is
the same defect this project has already had to fix twice in prose -- except
that this time the reader has no code in front of them to check it against.

The rule has a second half that is easy to miss: **a builder may run the engine
and may read a result, and may not evaluate physics of its own**. A figure the
result does not carry goes *up*, into the result, not down into the report.
Writing ``GE-1.md`` moved three that way.

Modules
-------
base
    What a dossier is, the cell formatters, the closing "what this cannot
    claim" section, and the registry.
ge1, ge0b, reference
    One builder each.
__main__
    ``python -m quoss.dossier`` regenerates all three.

No re-exports, deliberately -- see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
