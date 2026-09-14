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
channel
    ITU-R P.1621-2 and P.1622, and the Farid & Hranilovic 2007 pointing model
    against Ntanos et al. 2021.
ntanos2021
    Ntanos et al. 2021, the reference link's source, and the two protocol papers
    the link is evaluated with (Ma et al. 2005, Lim et al. 2014).
satquma
    Sidhu et al. 2021 (SatQuMA): what is like-for-like with this project's
    finite-key stack and what is not.
micius
    Liao et al. 2017: the only measured satellite QKD data in the table.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
