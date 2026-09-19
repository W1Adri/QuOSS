"""The publication style: sizes, type, colours and the visual vocabulary of a QuOSS figure.

What this module is for, for someone arriving new
-------------------------------------------------
``docs/adr/0026-the-language-ladder.md`` ("Alternativas descartadas") gives
MATLAB exactly one real advantage over Python — the typographic quality of its
figures — and says it is recovered with ``matplotlib`` plus a publication
*style sheet*, naming this module as where. A style sheet is a set of
``matplotlib`` settings (``rcParams``: font, sizes, line widths, colours) that
every figure is drawn under, so that forty figures in a paper look like one
system rather than forty defaults. This module is that sheet, plus the few
visual conventions that carry *meaning* in this project and therefore must not
be left to whoever draws the next plot.

The sizes, and where they come from
-----------------------------------
IEEE's author centre ("Create Graphics for Your Article", subpages *Resolution
and Size* and *File Formatting*, opened on 2026-09-13 through WebFetch, whose
summariser quoted them; re-check against the page before citing in print):

* one column **3.5 in** (88.9 mm, 21 pc), two columns **7.16 in** (182 mm,
  43 pc), and nothing larger than 7.16 x 8.8 in —
  :data:`COLUMN_WIDTH_IN`, :data:`DOUBLE_COLUMN_WIDTH_IN`, :data:`MAX_HEIGHT_IN`;
* raster graphics ">300dpi" for colour and greyscale, ">600dpi" for black and
  white line art — :data:`PNG_DPI` is 600, because these figures are line art
  with a few flat fills, and the PDF (vector, resolution-free) is the file a
  submission uses; the PNG is for slides and previews;
* type "approximately 9-10 point when viewed at full size", consistent across
  graphics, with Helvetica, Times New Roman, Arial, Cambria and Symbol
  recommended; fonts in PDF/EPS embedded or outlined.

A figure here is drawn **at its printed size** (3.5 in wide, not 8 in shrunk
by LaTeX), so a 9 pt label in the file is a 9 pt label on the page. Drawing
large and scaling down is the usual reason paper figures have unreadable 5 pt
ticks.

The typeface, chosen and defended
---------------------------------
**STIX General**, a serif designed to match Times. Two reasons, in order:

1. *It matches the page.* IEEE body text is Times, and a figure whose labels
   use the body face reads as part of the paper; Times New Roman is on the
   guide's recommended list and STIX is its metric-compatible twin.
2. *It ships inside matplotlib* (``mpl-data/fonts/ttf/STIXGeneral.ttf``). A
   style that names "Times New Roman" resolves to whatever a machine happens to
   have — Times on a Mac, Liberation Serif or DejaVu Sans on a Linux CI runner
   — so the same code would lay out text differently and write different bytes
   on two machines. With a bundled font, :func:`quoss.viz.plots.save_figure`
   is byte-reproducible (measured in ``tests/viz/test_plots.py::TestSaveFigure``)
   and the maths (``mathtext.fontset = "stix"``) uses the same face.

The cost: STIX is not literally on IEEE's list. It is recommended type, not
required type, and a journal that insists gets ``font.serif`` overridden in one
line. The dataviz method this package follows puts everything in a system sans;
that rule is for screens and dashboards, and the destination here is a printed
column of Times.

Sizes: 9 pt for labels and titles (the guide's lower bound), 8 pt for tick
labels, legends and the degradation footnote — one step down so the hierarchy
reads, and still within "approximately 9-10".

The colours, and why there are only six
----------------------------------------
:data:`PALETTE` is the first six slots of the dataviz skill's validated
categorical order (blue, orange, aqua, yellow, magenta, green), unchanged.
Validated with the skill's ``validate_palette`` on a white surface (2026-09-13):
all six inside the OKLCH lightness band and above the chroma floor; worst
*adjacent* colour-vision-deficiency separation ΔE 9.1 (protanopia, yellow/aqua)
and worst normal-vision ΔE 19.6, against targets of 8 and 15. The first three —
the only ones the plots in this package assign — pass the stricter *all-pairs*
test too (worst CVD ΔE 9.2, normal 24.0). ΔE is the distance between two
colours in the OKLab space times 100; CVD simulated with Machado, Oliveira &
Fernandes (2009) at full severity. The same numbers are recomputed by
``tests/viz/test_style.py::TestPaletteIsColourBlindSafe`` from the transforms
copied out of the validator, so they are measured in this repo and not quoted.

Aqua (2.82:1), yellow (2.17:1) and magenta (2.69:1) are below 3:1 contrast on
white; the validator's rule is that such a colour needs visible labels, which
is why every plot here that uses aqua writes the value on the mark.

**Colour never carries a meaning on its own**, because a paper is printed in
greyscale and read by the one reviewer in twelve with a colour deficiency.
Blue and orange differ by only 0.09 in relative luminance (0.188 against 0.278,
``test_blue_and_orange_nearly_merge_in_greyscale``), so in greyscale they are
two similar greys. What separates them is the *encoding*: finite key is a solid
fill, asymptotic key an outline with a hatch (:data:`ASYMPTOTIC_HATCH`), and
the Monte Carlo spread is black ink. That redundancy is a rule, not a style.

The vocabulary that is part of the physics
------------------------------------------
:data:`ASYMPTOTIC_LABEL` is ``"asymptotic (not certified)"``. The asymptotic
key rate is what infinitely long blocks would give; a pass is a short block
and the finite-key bound certifies far less — on the reference day 432 985 bits
against 3.78 Mbit, with two of four passes at exactly zero
(``docs/adr/0011-the-block-is-the-pass.md``). The project refuses to report the
asymptotic number as available key, and a legend is where a reader decides what
a bar means, so the refusal is written into the label and tested.

What it deliberately leaves out
-------------------------------
A dark theme (print has no dark mode), LaTeX text rendering (needs a TeX
installation and makes output depend on it), and journal presets other than
IEEE: a second journal is a second dict, added when a paper needs it.

Examples
--------
>>> style = publication_style()
>>> style["font.size"], style["pdf.fonttype"]
(9.0, 42)
>>> COLUMN_WIDTH_IN, DOUBLE_COLUMN_WIDTH_IN
(3.5, 7.16)
"""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from types import ModuleType
from typing import Any

from quoss.core.errors import ConfigurationError

__all__ = [
    "ASYMPTOTIC_COLOR",
    "ASYMPTOTIC_HATCH",
    "ASYMPTOTIC_LABEL",
    "BASELINE",
    "COLUMN_WIDTH_IN",
    "DOUBLE_COLUMN_WIDTH_IN",
    "FINITE_COLOR",
    "FINITE_LABEL",
    "FONT_SIZE_PT",
    "GRID",
    "INK",
    "MAX_HEIGHT_IN",
    "MUTED",
    "PALETTE",
    "PNG_DPI",
    "SECONDARY_COLOR",
    "SECONDARY_INK",
    "SMALL_FONT_SIZE_PT",
    "SURFACE",
    "publication_style",
    "require_matplotlib",
    "use_publication_style",
]

COLUMN_WIDTH_IN = 3.5
"""IEEE one-column figure width, in (88.9 mm, 21 pc). IEEE author centre, *Resolution and Size*."""

DOUBLE_COLUMN_WIDTH_IN = 7.16
"""IEEE two-column figure width, in (182 mm, 43 pc). Same page."""

MAX_HEIGHT_IN = 8.8
"""IEEE largest figure height, in ("no larger than 7.16 x 8.8 inches"). *File Formatting*."""

PNG_DPI = 600
"""Raster resolution for PNG output: IEEE asks >600 dpi for line art, >300 dpi for colour."""

FONT_SIZE_PT = 9.0
"""Label and title size, pt: the lower end of IEEE's "approximately 9-10 point"."""

SMALL_FONT_SIZE_PT = 8.0
"""Tick labels, legends, footnotes, pt: one step below :data:`FONT_SIZE_PT`."""

# -- colours ------------------------------------------------------------------ #
SURFACE = "#ffffff"
"""Figure and axes background: the paper."""

INK = "#0b0b0b"
"""Primary text and the Monte Carlo whiskers."""

SECONDARY_INK = "#52514e"
"""Axis spines, ticks and secondary text."""

MUTED = "#898781"
"""Thresholds (the elevation mask) and annotations that must recede."""

GRID = "#e1e0d9"
"""Gridlines and the pass-window shading: one step off the surface."""

BASELINE = "#c3c2b7"
"""Hairlines that separate without carrying data."""

PALETTE: tuple[str, ...] = ("#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300")
"""The categorical slots, in the fixed validated order. Assigned in order, never cycled."""

FINITE_COLOR = PALETTE[0]
"""Finite (certified) key: slot 1, always a solid fill."""

ASYMPTOTIC_COLOR = PALETTE[1]
"""Asymptotic (uncertified) key: slot 2, always an outline with :data:`ASYMPTOTIC_HATCH`."""

SECONDARY_COLOR = PALETTE[2]
"""A third quantity beside finite key (stranded relay key): slot 3, always value-labelled."""

ASYMPTOTIC_HATCH = "////"
"""The hatch that makes asymptotic bars distinguishable from finite ones without colour."""

ASYMPTOTIC_LABEL = "asymptotic (not certified)"
"""Legend text of every asymptotic mark. Part of the ADR 0011 refusal; tested verbatim."""

FINITE_LABEL = "finite key"
"""Legend text of every finite-key mark."""

_HATCH_LINEWIDTH_PT = 0.6
_LINE_WIDTH_PT = 1.0
_AXES_LINEWIDTH_PT = 0.6
_GRID_LINEWIDTH_PT = 0.4
_MARKER_SIZE_PT = 4.0
_DEFAULT_HEIGHT_IN = 2.4
_SVG_HASH_SALT = "quoss"


def require_matplotlib() -> ModuleType:
    """Return the ``matplotlib`` module, or say how to install it.

    ``matplotlib`` is the optional extra ``quoss[viz]``: the physics installs
    without it, so every function in :mod:`quoss.viz` imports it lazily through
    here. A bare ``ImportError`` would tell the user that a module is missing;
    this tells them which extra provides it.

    Returns
    -------
    ModuleType
        The imported ``matplotlib``.

    Raises
    ------
    ConfigurationError
        If ``matplotlib`` cannot be imported.
    """
    try:
        return importlib.import_module("matplotlib")
    except ImportError as exc:
        raise ConfigurationError(
            "quoss.viz needs matplotlib, which is not installed; install the extra with "
            "`pip install quoss[viz]` (or `uv sync --extra viz`)."
        ) from exc


def publication_style() -> dict[str, Any]:
    """Return the ``rcParams`` of a QuOSS publication figure, as a plain dict.

    A plain dict and not a ``matplotlib.RcParams``, so that it can be read,
    diffed and tested without importing ``matplotlib``; every key is a valid
    ``rcParams`` name (``tests/viz/test_style.py`` feeds it to
    ``matplotlib.rc_context``, which rejects unknown keys).

    The choices, each defended in the module docstring: STIX serif at 9/8 pt,
    figure 3.5 x 2.4 in, white surface, top and right spines off, a hairline
    horizontal grid, TrueType fonts embedded in PDF and PostScript
    (``pdf.fonttype = 42``; the default Type 3 fonts are the ones submission
    checkers reject), SVG text as paths and a fixed SVG hash salt so SVG output
    does not depend on installed fonts or on a random identifier.

    Returns
    -------
    dict[str, Any]
        ``rcParams`` name to value.

    Examples
    --------
    >>> style = publication_style()
    >>> style["font.family"], style["font.serif"]
    ('serif', ['STIXGeneral'])
    >>> style["figure.figsize"]
    (3.5, 2.4)
    """
    cycle = ", ".join(repr(c) for c in PALETTE)
    return {
        # type
        "font.family": "serif",
        "font.serif": ["STIXGeneral"],
        "mathtext.fontset": "stix",
        "font.size": FONT_SIZE_PT,
        "axes.titlesize": FONT_SIZE_PT,
        "axes.labelsize": FONT_SIZE_PT,
        "xtick.labelsize": SMALL_FONT_SIZE_PT,
        "ytick.labelsize": SMALL_FONT_SIZE_PT,
        "legend.fontsize": SMALL_FONT_SIZE_PT,
        "figure.titlesize": FONT_SIZE_PT,
        # geometry
        "figure.figsize": (COLUMN_WIDTH_IN, _DEFAULT_HEIGHT_IN),
        "figure.constrained_layout.use": True,
        # surfaces and ink
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "text.color": INK,
        "axes.labelcolor": INK,
        "axes.edgecolor": SECONDARY_INK,
        "xtick.color": SECONDARY_INK,
        "ytick.color": SECONDARY_INK,
        "axes.linewidth": _AXES_LINEWIDTH_PT,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.prop_cycle": f"cycler('color', [{cycle}])",
        # grid: hairline, solid, horizontal only, behind the data
        "axes.grid": True,
        "axes.grid.axis": "y",
        "axes.axisbelow": True,
        "grid.color": GRID,
        "grid.linewidth": _GRID_LINEWIDTH_PT,
        "grid.linestyle": "-",
        # marks
        "lines.linewidth": _LINE_WIDTH_PT,
        "lines.markersize": _MARKER_SIZE_PT,
        "hatch.linewidth": _HATCH_LINEWIDTH_PT,
        "legend.frameon": False,
        # output
        "savefig.dpi": PNG_DPI,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "path",
        "svg.hashsalt": _SVG_HASH_SALT,
    }


@contextmanager
def use_publication_style() -> Iterator[None]:
    """Draw everything inside the ``with`` block under :func:`publication_style`.

    A context manager over ``matplotlib.rc_context`` and not a call to
    ``matplotlib.rcParams.update``: the global ``rcParams`` are process state,
    and a function that changed them would restyle every figure drawn after it
    by any other code, the same non-reentrancy that makes
    :class:`~quoss.core.errors.DegradationLog` an argument rather than a
    global. On exit the previous settings are back, even after an exception.

    Settings are read when an artist is *created* (a label's size, a line's
    width), so the figure has to be built inside the block, not only saved.

    Yields
    ------
    None
        Nothing; the style is active for the duration of the block.

    Raises
    ------
    ConfigurationError
        If ``matplotlib`` is not installed.

    Examples
    --------
    >>> import matplotlib
    >>> with use_publication_style():
    ...     matplotlib.rcParams["font.size"]
    9.0
    """
    matplotlib = require_matplotlib()
    with matplotlib.rc_context(publication_style()):
        yield
