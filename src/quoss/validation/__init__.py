"""Validation: what this project reproduces from the literature, and what it does not.

Everything below this package is *verified* in one of four senses, and
``tests/golden/README.md`` is strict about which of them may be called
validation. V1 (invariants) proves a module does not contradict itself; V4
(regression) proves a refactor did not move a number. Neither says the number
is right. Only two levels do: **V2**, a value printed in a source somebody
opened, and **V3**, an independent implementation of the same physics. This
package is the one place where those two are collected, recomputed, and turned
into a table a reader can check against the papers without running anything.

The organising decision, and the reason this is a package and not a paragraph
in the README, is that **a validation claim is a computation, not a label**.
Every row of the table calls the same public physics function the test suite
calls, compares the result with the published value under a tolerance whose
origin is written next to it, and only then derives its status. A status typed
by hand cannot survive: :class:`~quoss.validation.base.ValidationCase` refuses
to be built with a status its own numbers do not produce. That is what stops
"validated" from becoming a badge that outlives the agreement it once described
(``docs/adr/0018-validation-is-a-table-not-a-badge.md``, which records the
four statuses, why ``compatible`` exists instead of a widened tolerance, and
why a published disagreement is exit 0 here and a red test there).

Modules
-------
base
    The case, its four statuses, the rule that derives the status, the list of
    known disagreements, and the Markdown renderer for ``docs/validation.md``.
__main__
    ``python -m quoss.validation`` — prints the table, or writes it to a file
    with ``--write``.
channel
    ITU-R P.1621-2 and P.1622, and the Farid & Hranilovic 2007 pointing model
    against Ntanos et al. 2021.
ntanos2021
    **The source of the reference link itself** — Ntanos et al. 2021 — together
    with the two protocol papers its link is evaluated with, Ma et al. 2005 and
    Lim et al. 2014.
satquma
    Sidhu et al. 2021 (SatQuMA): what is like-for-like with this project's
    finite-key stack and what is not.
micius
    Liao et al. 2017: the only measured satellite QKD data in the table.

What the table says today, and it is the honest headline of stage 8
--------------------------------------------------------------------
``run_all()`` returns **35 cases from eight sources**: 17 reproduced, 3
compatible, 8 not reproduced and 7 declared gaps.

The number worth reading is the 8. Seven of them are Ntanos et al. 2021, and
that is not a verdict on the paper — it is the source with the most fully
stated parameters this project has, so more of its printed consequences can be
checked at all. A vaguer source would produce a shorter list and a false sense
of agreement. What the eight disagreements are, each in one line, is
:data:`~quoss.validation.base.EXPECTED_DISAGREEMENTS`; what each one costs is in
the note of its row.

**This section replaces one that said the paper the reference link is built on
had no row here at all**, and that absence is worth remembering rather than
quietly deleting. ``ntanos2021`` was listed in
:data:`~quoss.validation.base.CASE_MODULES` before it was written, so
:func:`~quoss.validation.base.run_all` — the one entry point of the package —
raised ``ModuleNotFoundError`` on every call: the table that existed to stop
"validated" from being a badge could not be produced at all. It was then
removed from the tuple and the hole declared, which made the package work and
made the gap visible; stage 8.1 is where the gap closed.

One disagreement still has no row, on purpose:
:data:`~quoss.validation.base.PENDING_DISAGREEMENTS` holds
``lim2014.block-1e4-reach``, because computing it would mean carrying a second
implementation of Lim et al.'s Evaluation section. Its measurement is named
there.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
