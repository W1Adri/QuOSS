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
(``docs/adr/0018-validation-is-a-table-not-a-badge.md``).

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
satquma
    Sidhu et al. 2021 (SatQuMA): what is like-for-like with this project's
    finite-key stack and what is not.
micius
    Liao et al. 2017: the only measured satellite QKD data in the table.

What is **not** here yet, and it is the row that matters most
--------------------------------------------------------------
``ntanos2021`` — Ntanos et al. 2021, the reference link's own source, together
with the two protocol papers the link is evaluated with (Ma et al. 2005, Lim
et al. 2014). It is stage 8.1 of ``notes/ROADMAP.md`` and it is **not written**.

This paragraph replaces one that listed it among the modules as though it
existed. That was not only a docstring being optimistic: the name was in
:data:`~quoss.validation.base.CASE_MODULES`, so :func:`~quoss.validation.base.run_all`
— the one entry point of the package — raised ``ModuleNotFoundError`` on every
call. **The table that existed to stop "validated" from being a badge could not
be produced at all.** The six disagreements that module will carry are kept, and
kept reachable, in :data:`~quoss.validation.base.PENDING_DISAGREEMENTS`.

So what ``run_all()`` returns today is 22 cases from three sources, and the
honest reading of it is: the channel recommendations and the two external
systems are covered; **the paper this project's reference link is built on is
not in the table yet**. Anything reported as validated against Ntanos et al.
traces to the assertions in ``tests/channel/`` and ``tests/qkd/``, not to a row
here.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
