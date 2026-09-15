"""``python -m quoss.validation`` — recompute the table and print or write it.

Why this module exists as its own file
--------------------------------------
:data:`~quoss.validation.base.REGENERATE_COMMAND` is quoted inside the generated
``docs/validation.md`` as the one command that rewrites it, and a generated file
that names a command nobody can run is a worse instruction than none: a reader
who tries it and gets ``No module named quoss.validation.__main__`` has to guess
whether the file is stale, wrong, or fine. So the command is a module.

It is deliberately thin. Everything it does is
:func:`~quoss.validation.base.run_all` followed by
:func:`~quoss.validation.base.render_markdown`; the only decisions here are
where the text goes and what the exit status means.

What the exit status means, which is the one design choice
----------------------------------------------------------
**Zero, unless the run could not be made.** A table containing
``not reproduced`` rows is a *correct* table — the whole point of deriving the
status instead of declaring it is that a disagreement gets published rather
than hidden — so a disagreement is not a failure of this command. What fails
here is only being unable to compute the table (a physics function refusing its
inputs, a case whose declared status its own numbers do not produce, two cases
sharing an identifier), which surfaces as the exception ``run_all`` raises.

The gate that *does* fail on an unexpected disagreement is
``tests/validation/test_base.py``, against
:data:`~quoss.validation.base.EXPECTED_DISAGREEMENTS`. Keeping the two apart
means a person can regenerate the document on a branch where something
disagrees, see it in the diff, and decide; CI still refuses to let it through
unexplained.

Examples
--------
Print the table to standard output:

.. code-block:: bash

    uv run python -m quoss.validation

Rewrite the committed document:

.. code-block:: bash

    uv run python -m quoss.validation --write docs/validation.md
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from quoss.validation.base import REGENERATE_COMMAND, render_markdown, run_all


def main(argv: Sequence[str] | None = None) -> int:
    """Recompute every validation case and emit the Markdown table.

    Parameters
    ----------
    argv : sequence of str, optional
        Command-line arguments without the program name. ``None`` (default)
        reads ``sys.argv[1:]``.

    Returns
    -------
    int
        ``0``. A failure to compute the table raises instead of returning; see
        the module docstring on why a disagreement is not a failure.

    Examples
    --------
    >>> main(["--quiet"])
    0
    """
    parser = argparse.ArgumentParser(
        prog="python -m quoss.validation",
        description=(
            "Recompute every validation case and render docs/validation.md. "
            f"The canonical invocation is: {REGENERATE_COMMAND}"
        ),
    )
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        metavar="PATH",
        help="write the table to PATH instead of standard output.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="compute the table and emit nothing; for checking that the run succeeds.",
    )
    args = parser.parse_args(argv)

    text = render_markdown(run_all())
    if args.write is not None:
        args.write.parent.mkdir(parents=True, exist_ok=True)
        args.write.write_text(text, encoding="utf-8")
    elif not args.quiet:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess in tests
    raise SystemExit(main())
