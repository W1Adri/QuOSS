"""Publication figures: a style sheet, the standard plots, and the paper's figures.

A figure is the last place a number can be misread, so this package draws only
what a :class:`~quoss.scenario.result.SimulationResult` (or a sweep's records)
already contains and computes no physics of its own — one formula, one place
(``notes/GUIA_REIMPLEMENTACION.md`` §1). What it does add is the visual
vocabulary the project's rules need: finite key solid, asymptotic key hatched
and labelled "asymptotic (not certified)", and a visible ``DEGRADED`` footnote
on any figure whose result recorded a substituted model.

``matplotlib`` is the optional extra ``quoss[viz]`` and is imported lazily, so
importing any module here works without it; calling a plotting function
without it raises :class:`~quoss.core.errors.ConfigurationError`.

Modules
-------
style
    The IEEE-sized publication ``rcParams``, the validated colour-blind-safe
    palette, and the labels that carry meaning.
plots
    The standard plots, each ``plot_*(result, ..., ax=None) -> Figure``, and
    :func:`~quoss.viz.plots.save_figure`, which writes reproducible files.
figures
    The paper's figures, each built from a versioned scenario and returned
    together with the numbers it plotted.

No re-exports, deliberately — see :mod:`quoss.core` for the reasoning. Import
from the module that defines the name.
"""

from __future__ import annotations

__all__: list[str] = []
