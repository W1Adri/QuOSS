"""One well-formed validation case, and the knobs to bend it out of shape.

Every test in this directory that is about the *machinery* — the status rule,
the refusals, the renderer — needs a case that is valid except for the one thing
under test. Writing sixteen keyword arguments at each of those would bury the
one that matters, so this builds a valid case and takes overrides.

The values are deliberately not physics. A machinery test that used the real
ITU-R numbers would fail for two reasons at once the day the physics moved, and
the reader would have to work out which. The two places that do use the real
table are `test_base.py::TestTheTableRuns`, which is about the table and not
about the machinery, and `test_docs.py`, which compares the committed document
with a fresh render.
"""

from __future__ import annotations

from typing import Any

from quoss.validation.base import AccountedTerm, ValidationCase

VALID: dict[str, Any] = {
    "identifier": "source.quantity",
    "source": "A Source (2026), somewhere openable",
    "locator": "Eq. (1)",
    "quantity": "a quantity",
    "published": 10.0,
    "computed": 10.1,
    "unit": "dB",
    "tolerance": 0.5,
    "tolerance_basis": "printed to one decimal, so half of the last digit",
    "level": "V2",
    "note": "a note a reader can act on",
    "test": "tests/validation/test_base.py::TestSomething::test_something",
}
"""A case that passes every check: reproduced, 10.1 against 10.0 within 0.5."""

ACCOUNTED = AccountedTerm(
    name="a term the source omits",
    lower=0.0,
    upper=5.0,
    basis="bounded above by the thing it stands for",
)


def case(**overrides: Any) -> ValidationCase:
    """Return a case built by ``evaluate``, with ``overrides`` applied to :data:`VALID`."""
    return ValidationCase.evaluate(**{**VALID, **overrides})
