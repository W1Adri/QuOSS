r"""The standard plots of a run, drawn from a result and nothing else.

What this module does, for someone arriving new
-----------------------------------------------
Each ``plot_*`` function takes a :class:`~quoss.scenario.result.SimulationResult`
(or, for :func:`plot_sweep`, the rows of ``SweepResult.to_records()``) and draws
one standard view of it: elevation and rate over the day, key per pass, key per
day, a parameter sweep, the sky track of the passes, the multi-station harvest
and the relay. :func:`save_figure` writes the result to files that are the same
bytes every time.

Four rules shape every function, and each is a rule of the project rather than
a matter of taste:

1. **No physics here.** Every number on a plot is a field of the result. The
   only arithmetic is presentation: radians to degrees through
   :func:`quoss.core.units.rad_to_deg` (the repo's AST guard forbids
   ``np.rad2deg`` outside ``core/units.py``), seconds to hours for an axis,
   ``90 deg - elevation`` as the radius of a sky plot, and the Julian day number
   to a calendar date through :func:`quoss.orbits.frames.jd_to_calendar`, the
   function ``io/export.py`` uses for the same column. A plot that re-derived a
   key or a quantile would be a second implementation that could disagree with
   the first without any test noticing.
2. **Finite and asymptotic key never look alike.** Finite key is a solid
   blue fill labelled "finite key"; asymptotic key is an orange *outline with a
   hatch* labelled "asymptotic (not certified)". The hatch is what survives
   greyscale printing, where the two colours are two similar greys
   (:mod:`quoss.viz.style`). A pass that certifies nothing gets a visible "0"
   at its base, because a zero-height bar is indistinguishable from a missing
   one — and on the reference day two of the four passes are exactly that.
3. **Degradations are visible.** If the result's ``warnings`` hold any entry of
   severity ``degraded`` — a model was substituted, so the numbers are not
   those of the requested model — the figure gets a footnote
   ``DEGRADED: <codes>``. Entries of severity ``info`` and ``warning`` do not
   mark the figure (the numbers are still those of the requested model); they
   stay in ``result.warnings``, which the CLI prints.
4. **No global state.** Figures are built with ``matplotlib.figure.Figure``,
   never ``pyplot``: ``pyplot`` keeps a process-wide "current figure", which is
   what makes plotting code non-reentrant and leaks figures in long runs. No
   GUI backend is ever touched, so the functions run the same in a test, a
   worker process and a notebook.

Every plot function takes ``ax=None``. With ``None`` it creates a one-column
figure; with an axes it draws into that axes (so a paper figure can compose
several plots in one grid) and returns the figure that axes belongs to.

The one plot with two quantities, and why it is two panels
----------------------------------------------------------
:func:`plot_elevation_and_rate` shows elevation (degrees, 0 to 90) and the
asymptotic secure rate (bit/s, 0 to thousands). The obvious drawing is one
panel with a second y-axis on the right. It is not done: with two scales on one
plot, where the curves cross is decided by how the two axes happen to be
ranged, so the figure shows a relationship that is a property of the axis
limits, not of the data. Two panels sharing the time axis show the same
alignment in time — which is the point, the rate lives only inside the shaded
pass windows — without that artefact. ``docs/adr/0017-publication-figures.md``
records the decision.

What it deliberately leaves out
-------------------------------
Coverage maps (they need a ground-track grid the result does not store),
interactive plots (the web frontend's job, ``notes/GUIA_REIMPLEMENTACION.md``
§4), and a daily Monte Carlo band: :class:`~quoss.scenario.result.MonteCarloResults`
keeps quantiles per *pass*, and the quantiles of a day are quantiles of the
per-realisation sum, which cannot be rebuilt from per-pass quantiles (on the
reference ensemble the day's P5 is 735 329 bits while the sum of the passes'
P5 is 724 553, ``notes`` §28). Summing them here would draw a band that no
ensemble produced.

Examples
--------
>>> from quoss.viz.plots import SAVE_FORMATS
>>> SAVE_FORMATS
('pdf', 'png', 'svg')
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from quoss.core.errors import DomainError, Severity
from quoss.core.types import FloatArray, IntArray
from quoss.core.units import rad_to_deg
from quoss.orbits.frames import jd_to_calendar
from quoss.scenario.result import SeriesResults, SimulationResult
from quoss.viz.style import (
    ASYMPTOTIC_COLOR,
    ASYMPTOTIC_HATCH,
    ASYMPTOTIC_LABEL,
    COLUMN_WIDTH_IN,
    FINITE_COLOR,
    FINITE_LABEL,
    GRID,
    INK,
    MUTED,
    PNG_DPI,
    SECONDARY_COLOR,
    SMALL_FONT_SIZE_PT,
    SURFACE,
    publication_style,
    require_matplotlib,
)

if TYPE_CHECKING:
    from matplotlib.axes import Axes
    from matplotlib.figure import Figure

__all__ = [
    "DEGRADED_GID",
    "DEGRADED_PREFIX",
    "SAVE_FORMATS",
    "SECONDS_PER_HOUR",
    "ZERO_KEY_GID",
    "degraded_codes",
    "mark_degradations",
    "plot_daily_key",
    "plot_elevation_and_rate",
    "plot_multi_station",
    "plot_pass_key_volume",
    "plot_relay",
    "plot_sky_track",
    "plot_sweep",
    "save_figure",
]

SECONDS_PER_HOUR = 3600.0
"""Seconds in an hour: the time axes are drawn in hours."""

SAVE_FORMATS: tuple[str, ...] = ("pdf", "png", "svg")
"""The file formats :func:`save_figure` writes."""

DEGRADED_PREFIX = "DEGRADED: "
"""Start of the footnote a figure carries when its result recorded a substituted model."""

DEGRADED_GID = "quoss-degraded"
"""``gid`` of that footnote's text artist, so it can be found and extended."""

ZERO_KEY_GID = "quoss-zero-key"
"""``gid`` of the "0" written at the base of a bar that certifies no key."""

_ONE_PANEL_HEIGHT_IN = 2.4
_TWO_PANEL_HEIGHT_IN = 3.6
_SKY_HEIGHT_IN = 3.2
_BAR_WIDTH = 0.38
_CAP_HALF_WIDTH = 0.08
_FOOTNOTE_MARGIN = 0.07
"""Fraction of the figure height kept free at the bottom for the DEGRADED footnote."""
_DAYS_TO_HALF = 0.5
"""A Julian day number names the civil day that starts at ``JDN - 0.5``."""
_RIGHT_ANGLE_DEG = 90.0
_MEDIAN = 0.5
_SAVE_TIME_KEYS = ("pdf.fonttype", "ps.fonttype", "svg.fonttype", "svg.hashsalt")
_METADATA: dict[str, dict[str, Any]] = {
    "pdf": {"CreationDate": None},
    "svg": {"Date": None},
    "png": {},
}


# --------------------------------------------------------------------------- #
# Shared pieces
# --------------------------------------------------------------------------- #
def degraded_codes(warnings: Iterable[Mapping[str, Any]]) -> tuple[str, ...]:
    """Return the sorted, distinct codes of the ``degraded`` entries of a warning list.

    Parameters
    ----------
    warnings : Iterable[Mapping[str, Any]]
        ``SimulationResult.warnings``: dicts from
        :meth:`~quoss.core.errors.DegradationLog.to_dicts`, each with at least
        ``code`` and ``severity``.

    Returns
    -------
    tuple[str, ...]
        Codes of severity :attr:`~quoss.core.errors.Severity.DEGRADED`, sorted
        and without repetition; empty when nothing was substituted.

    Examples
    --------
    >>> degraded_codes(
    ...     [
    ...         {"code": "b.cloud", "severity": "degraded"},
    ...         {"code": "engine.cache-hit", "severity": "info"},
    ...         {"code": "a.profile", "severity": "degraded"},
    ...         {"code": "b.cloud", "severity": "degraded"},
    ...     ]
    ... )
    ('a.profile', 'b.cloud')
    """
    return tuple(
        sorted(
            {str(w["code"]) for w in warnings if str(w.get("severity")) == Severity.DEGRADED.value}
        )
    )


def mark_degradations(fig: Figure, warnings: Iterable[Mapping[str, Any]]) -> None:
    """Write ``DEGRADED: <codes>`` at the foot of a figure whose result substituted a model.

    Does nothing when no entry is ``degraded``. When the figure already carries
    the footnote (two plots of the same figure, or of two results), the codes
    are merged into the one footnote instead of stacking a second. When the
    figure uses matplotlib's constrained layout (every figure this module
    creates does), the bottom :data:`_FOOTNOTE_MARGIN` of the figure is taken
    out of the layout so the footnote cannot sit on a tick label; a figure with
    another layout gets the text at the same place and keeps its own layout.

    Parameters
    ----------
    fig : Figure
        The figure to mark.
    warnings : Iterable[Mapping[str, Any]]
        The result's warning list.
    """
    codes = set(degraded_codes(warnings))
    if not codes:
        return
    existing = [t for t in fig.texts if t.get_gid() == DEGRADED_GID]
    if existing:
        note = existing[0]
        codes.update(note.get_text().removeprefix(DEGRADED_PREFIX).split(", "))
        note.set_text(DEGRADED_PREFIX + ", ".join(sorted(codes)))
        return
    fig.text(
        0.01,
        0.005,
        DEGRADED_PREFIX + ", ".join(sorted(codes)),
        ha="left",
        va="bottom",
        fontsize=SMALL_FONT_SIZE_PT,
        color=INK,
        gid=DEGRADED_GID,
    )
    from matplotlib.layout_engine import ConstrainedLayoutEngine

    engine = fig.get_layout_engine()
    if isinstance(engine, ConstrainedLayoutEngine):
        engine.set(rect=(0.0, _FOOTNOTE_MARGIN, 1.0, 1.0 - _FOOTNOTE_MARGIN))


def _new_figure(height_in: float) -> Figure:
    from matplotlib.figure import Figure

    return Figure(figsize=(COLUMN_WIDTH_IN, height_in), layout="constrained")


def _figure_and_axes(ax: Axes | None, *, height_in: float, polar: bool = False) -> tuple[Any, Any]:
    """Return ``(figure, axes)``: a new one-column figure, or the figure of ``ax``."""
    require_matplotlib()
    if ax is None:
        fig = _new_figure(height_in)
        return fig, fig.add_subplot(projection="polar" if polar else None)
    is_polar = ax.name == "polar"
    if polar != is_polar:
        wanted = "a polar axes (projection='polar')" if polar else "a Cartesian axes"
        raise DomainError(f"this plot needs {wanted}, got an axes of projection {ax.name!r}.")
    return ax.figure, ax


def _station_series(result: SimulationResult, station: str) -> SeriesResults:
    try:
        return result.series_for(station)
    except KeyError as exc:
        raise DomainError(
            f"station {station!r} is not in this result; it has {result.scenario.station_names}."
        ) from exc


def _station_passes(result: SimulationResult, station: str) -> IntArray:
    """Row indices of ``result.passes`` that belong to ``station``, in table order."""
    indices: IntArray = np.flatnonzero(np.asarray(result.passes.station, dtype=object) == station)
    return indices


def _clock(result: SimulationResult, t_s: float) -> str:
    """``HH:MM`` UTC of an elapsed time on the result's axis (for a tick label)."""
    instant = result.scenario.time.epoch_utc + dt.timedelta(seconds=float(t_s))
    return instant.strftime("%H:%M")


def _date_of_day_number(day_number: int) -> str:
    year, month, day, *_ = jd_to_calendar(float(day_number) - _DAYS_TO_HALF)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _engineering(ax: Any, unit: str) -> None:
    from matplotlib.ticker import EngFormatter

    ax.yaxis.set_major_formatter(EngFormatter(unit=unit))


def _mark_zero_key(ax: Any, x: FloatArray, bits: FloatArray) -> None:
    for xi in x[bits <= 0.0]:
        ax.annotate(
            "0",
            (float(xi), 0.0),
            xytext=(0.0, 2.0),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=SMALL_FONT_SIZE_PT,
            color=INK,
            gid=ZERO_KEY_GID,
        )


def _finite_and_asymptotic_bars(
    ax: Any, x: FloatArray, finite: FloatArray, asymptotic: FloatArray | None
) -> FloatArray:
    """Draw the finite bars (solid) and, if given, the asymptotic ones (hatched outline).

    Returns the x positions of the finite bars.
    """
    x_finite = x - _BAR_WIDTH / 2.0 if asymptotic is not None else x
    ax.bar(x_finite, finite, width=_BAR_WIDTH, color=FINITE_COLOR, label=FINITE_LABEL)
    if asymptotic is not None:
        ax.bar(
            x + _BAR_WIDTH / 2.0,
            asymptotic,
            width=_BAR_WIDTH,
            facecolor=SURFACE,
            edgecolor=ASYMPTOTIC_COLOR,
            hatch=ASYMPTOTIC_HATCH,
            linewidth=0.8,
            label=ASYMPTOTIC_LABEL,
        )
    _mark_zero_key(ax, x_finite, finite)
    return x_finite


def _legend_above(ax: Any) -> None:
    """Put the legend in a two-column band directly above the axes, as wide as the axes.

    The anchor is a *box* ``(x0, y0, width, height)`` in axes coordinates rather
    than a point, with ``mode="expand"``, which pins the legend to the axes width.
    That matters because constrained layout treats a legend outside the axes as
    part of the layout: anchored to a point, the legend takes its natural width,
    and a legend wider than a 3.5 in column (two entries as long as "asymptotic
    (not certified)" at the matplotlib default of 10 pt) makes the solver shrink
    the axes until it fits — 350 px of figure leaving 57 px of axes, and then the
    "axes sizes collapsed to zero" warning on the next draw. Pinned to the axes
    width, the same figure keeps 255 px of axes.

    The font size is set here instead of being read from ``rcParams`` so the band
    is the same height whether or not the caller is inside
    :func:`~quoss.viz.style.use_publication_style`, like every other piece of text
    this module places.
    """
    ax.legend(
        loc="lower left",
        bbox_to_anchor=(0.0, 1.0, 1.0, 0.0),
        mode="expand",
        ncols=2,
        borderaxespad=0.2,
        fontsize=SMALL_FONT_SIZE_PT,
    )


def _empty(ax: Any, message: str) -> None:
    ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes, color=MUTED)


# --------------------------------------------------------------------------- #
# Time series
# --------------------------------------------------------------------------- #
def plot_elevation_and_rate(
    result: SimulationResult, station: str, *, ax: Axes | None = None
) -> Figure:
    """Draw one station's elevation and asymptotic secure rate over the run, passes shaded.

    Two panels sharing the time axis (module docstring: why not a twin axis).
    Top: elevation in degrees, 0 to 90 (the part of the day below the horizon
    is outside the view, not removed from the data), with the scenario's
    elevation mask as a dashed threshold. Bottom: the asymptotic secure bit
    rate, which the result holds only inside passes (NaN elsewhere, so the curve
    is absent there rather than drawn at zero), as a hatched area titled
    "asymptotic (not certified)" — a rate per instant is an asymptotic
    quantity; the finite key of a pass is a property of the whole block and has
    no time series. Pass windows are shaded grey in both panels.

    Parameters
    ----------
    result : SimulationResult
        The run.
    station : str
        Which station's series.
    ax : Axes, optional
        An axes created from a grid (``fig.add_subplot``, ``fig.subplots``,
        a gridspec). Its slot is split into the two panels and the axes itself
        is removed. ``None`` creates a one-column figure.

    Returns
    -------
    Figure
        The figure holding the two panels.

    Raises
    ------
    DomainError
        If ``station`` has no series, or ``ax`` is not part of a grid.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    require_matplotlib()
    series = _station_series(result, station)
    if ax is None:
        fig: Any = _new_figure(_TWO_PANEL_HEIGHT_IN)
        slots = fig.add_gridspec(2, 1)
    else:
        spec = ax.get_subplotspec()
        if spec is None:
            raise DomainError(
                "plot_elevation_and_rate splits its axes into two panels, so the axes must "
                "come from a grid (add_subplot, subplots or a gridspec), not add_axes."
            )
        fig = ax.figure
        ax.remove()
        slots = spec.subgridspec(2, 1)
    ax_elevation = fig.add_subplot(slots[0])
    ax_rate = fig.add_subplot(slots[1], sharex=ax_elevation)

    hours = series.grid.t_s / SECONDS_PER_HOUR
    mask_deg = result.scenario.passes.minimum_elevation_deg
    for i in _station_passes(result, station):
        for panel in (ax_elevation, ax_rate):
            panel.axvspan(
                result.passes.start_s[i] / SECONDS_PER_HOUR,
                result.passes.end_s[i] / SECONDS_PER_HOUR,
                color=GRID,
                linewidth=0.0,
                zorder=0,
            )

    ax_elevation.plot(hours, rad_to_deg(series.elevation_rad.values), color=FINITE_COLOR)
    ax_elevation.axhline(mask_deg, color=MUTED, linestyle="--", linewidth=0.8)
    ax_elevation.annotate(
        f"mask {mask_deg:g}°",
        (1.0, mask_deg),
        xycoords=("axes fraction", "data"),
        xytext=(0.0, 2.0),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=SMALL_FONT_SIZE_PT,
        color=MUTED,
    )
    ax_elevation.set_ylim(0.0, _RIGHT_ANGLE_DEG)
    ax_elevation.set_ylabel("elevation [deg]")
    ax_elevation.tick_params(labelbottom=False)

    rate = series.asymptotic_secure_bit_s.values
    defined = np.isfinite(rate)
    ax_rate.fill_between(
        hours,
        0.0,
        np.where(defined, rate, 0.0),
        where=defined,
        facecolor=SURFACE,
        edgecolor=ASYMPTOTIC_COLOR,
        hatch=ASYMPTOTIC_HATCH,
        linewidth=0.0,
    )
    ax_rate.plot(hours, rate, color=ASYMPTOTIC_COLOR)
    ax_rate.set_title(ASYMPTOTIC_LABEL, loc="left")
    ax_rate.set_ylim(bottom=0.0)
    _engineering(ax_rate, "bit/s")
    ax_rate.set_ylabel("secure rate")
    epoch = result.scenario.time.epoch_utc.strftime("%Y-%m-%d %H:%M")
    ax_rate.set_xlabel(f"hours since {epoch} UTC — {station}")

    mark_degradations(fig, result.warnings)
    return fig


# --------------------------------------------------------------------------- #
# Key volume
# --------------------------------------------------------------------------- #
def plot_pass_key_volume(
    result: SimulationResult, *, ax: Axes | None = None, show_asymptotic: bool = True
) -> Figure:
    """Draw the key of every pass: finite solid, asymptotic hatched, Monte Carlo whiskers.

    One group per pass, in pass-table order, labelled with the pass number, its
    start time (UTC) and, when the result has several stations, the station.
    In each group:

    * the **finite** key (the certified block of the pass) as a solid bar,
      with a "0" at its base when the pass certifies nothing;
    * the **asymptotic** key as a hatched outline labelled
      "asymptotic (not certified)", unless ``show_asymptotic`` is false;
    * when the result has a Monte Carlo section, a black whisker from the
      lowest to the highest ensemble quantile (P5-P95 by default) and a ring
      at the median, drawn over the finite bar. The ensemble fluctuates around
      the **mean** transmittance while the bar is the **design** number held at
      the fade quantile for the whole pass, so on the reference link the whisker
      sits above the bar (758 314 bits median day against 432 985); that gap is
      a finding (``notes`` §28), not a drawing error, and it is why the two are
      not merged into one mark.

    A pass whose block was cut by the edge of the time grid gets "(cut)" in its
    label: its key is a lower bound (``docs/adr/0011-the-block-is-the-pass.md``
    §8).

    Parameters
    ----------
    result : SimulationResult
        The run.
    ax : Axes, optional
        Cartesian axes to draw into; ``None`` creates a one-column figure.
    show_asymptotic : bool
        Whether to draw the asymptotic bars. The Monte Carlo figure hides them
        so the spread is visible at the finite key's scale.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        If ``ax`` is polar.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    fig, axes = _figure_and_axes(ax, height_in=_ONE_PANEL_HEIGHT_IN)
    p = result.passes
    if p.n_passes == 0:
        _empty(axes, "no pass above the mask")
        mark_degradations(fig, result.warnings)
        return fig

    x = np.arange(p.n_passes, dtype=np.float64)
    x_finite = _finite_and_asymptotic_bars(
        axes, x, p.finite_bits, p.asymptotic_bits if show_asymptotic else None
    )

    mc = result.monte_carlo
    if mc is not None:
        probabilities = np.asarray(mc.quantiles, dtype=np.float64)
        low, high = int(np.argmin(probabilities)), int(np.argmax(probabilities))
        if probabilities[low] < probabilities[high]:
            lower, upper = mc.quantile_bits[low], mc.quantile_bits[high]
            axes.vlines(
                x_finite,
                lower,
                upper,
                color=INK,
                linewidth=0.9,
                label=f"Monte Carlo P{probabilities[low] * 100:g}-P{probabilities[high] * 100:g}",
            )
            for bound in (lower, upper):
                axes.hlines(
                    bound,
                    x_finite - _CAP_HALF_WIDTH,
                    x_finite + _CAP_HALF_WIDTH,
                    color=INK,
                    linewidth=0.9,
                )
        if _MEDIAN in mc.quantiles:
            axes.plot(
                x_finite,
                mc.quantile_bits[mc.quantiles.index(_MEDIAN)],
                linestyle="none",
                marker="o",
                markerfacecolor=SURFACE,
                markeredgecolor=INK,
                label="Monte Carlo P50",
            )

    several = len(set(p.station)) > 1
    labels: list[str] = []
    counters: dict[str, int] = {}
    for i in range(p.n_passes):
        station = p.station[i]
        counters[station] = counters.get(station, 0) + 1
        name = f"{station} {counters[station]}" if several else f"{counters[station]}"
        cut = " (cut)" if bool(p.truncated_start[i] or p.truncated_end[i]) else ""
        labels.append(f"{name}{cut}\n{_clock(result, float(p.start_s[i]))}")
    axes.set_xticks(x, labels)
    axes.set_xlabel("pass (start, UTC)")
    axes.set_ylim(bottom=0.0)
    _engineering(axes, "bit")
    axes.set_ylabel("key per pass")
    _legend_above(axes)
    mark_degradations(fig, result.warnings)
    return fig


def plot_daily_key(result: SimulationResult, *, ax: Axes | None = None) -> Figure:
    """Draw the key of every UTC day: finite solid, asymptotic hatched.

    One group per day of ``result.daily``, labelled with the calendar date. When
    the scenario composed the day's security (``docs/adr/0011-the-block-is-the-pass.md``
    §6), the composed failure probabilities are printed above the plot: a
    day's key is ``n`` blocks, each ``eps``-secure, so the day is
    ``n * eps``-secure, and a figure that showed the bits without that number
    would show a key without its guarantee.

    No Monte Carlo band: see the module docstring for why per-pass quantiles
    cannot be summed into a daily one.

    Parameters
    ----------
    result : SimulationResult
        The run.
    ax : Axes, optional
        Cartesian axes to draw into; ``None`` creates a one-column figure.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        If ``ax`` is polar.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    fig, axes = _figure_and_axes(ax, height_in=_ONE_PANEL_HEIGHT_IN)
    d = result.daily
    if d.n_days == 0:
        _empty(axes, "no day in this result")
        mark_degradations(fig, result.warnings)
        return fig
    x = np.arange(d.n_days, dtype=np.float64)
    _finite_and_asymptotic_bars(axes, x, d.finite_bits, d.asymptotic_bits)
    axes.set_xticks(x, [_date_of_day_number(int(n)) for n in d.day_number])
    axes.set_xlabel("UTC day")
    axes.set_ylim(bottom=0.0)
    _engineering(axes, "bit")
    axes.set_ylabel("key per day")
    _legend_above(axes)
    if d.composed_secrecy is not None and d.composed_correctness is not None:
        axes.set_title(
            rf"composed $\varepsilon_{{\rm sec}}$ = {d.composed_secrecy:.0e}, "
            rf"$\varepsilon_{{\rm cor}}$ = {d.composed_correctness:.0e}",
            loc="right",
            fontsize=SMALL_FONT_SIZE_PT,
        )
    mark_degradations(fig, result.warnings)
    return fig


# --------------------------------------------------------------------------- #
# Sweeps
# --------------------------------------------------------------------------- #
def plot_sweep(
    records: Sequence[Mapping[str, Any]],
    *,
    x: str,
    y: str,
    ax: Axes | None = None,
    log_y: bool = False,
    xlabel: str | None = None,
    ylabel: str | None = None,
) -> Figure:
    """Draw one metric of a parameter sweep against one swept parameter.

    ``records`` are the rows of ``SweepResult.to_records()``: plain dicts with
    the dotted parameter names (``passes.minimum_elevation_deg``) and the metric
    names (``daily.finite_bits``) as keys. The points are drawn sorted by ``x``,
    joined by a line, each with a marker so that the sampled values are visible
    and the line is not mistaken for a measured curve between them.

    A metric whose name contains ``asymptotic`` is drawn in the asymptotic
    vocabulary — orange, dashed, hollow markers, legend "asymptotic (not
    certified)" — and any other as a solid blue line with filled markers.

    It refuses, rather than draws something plausible:

    * a record without ``x`` or ``y``, or a value that is not a finite number;
    * two records with the same ``x`` — a grid sweep over two parameters, whose
      rows must be filtered to one value of the other parameter first, because
      a line through both would zig-zag between two curves;
    * ``log_y`` with a value that is not positive: matplotlib would silently
      drop the point (a pass with zero key is exactly the value a log axis
      loses), which is a degradation without a record.

    Parameters
    ----------
    records : Sequence[Mapping[str, Any]]
        Sweep rows.
    x, y : str
        Keys of the parameter and the metric.
    ax : Axes, optional
        Cartesian axes to draw into; ``None`` creates a one-column figure.
    log_y : bool
        Logarithmic y axis.
    xlabel, ylabel : str, optional
        Axis labels; default to ``x`` and ``y``.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        On any of the refusals above, or a polar ``ax``.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    rows = list(records)
    if not rows:
        raise DomainError("plot_sweep needs at least one record.")
    xs = _column(rows, x)
    ys = _column(rows, y)
    if np.unique(xs).size != xs.size:
        raise DomainError(
            f"several records share a value of {x!r}; a sweep over more than one parameter "
            "must be filtered to one value of the others before plotting against it."
        )
    if log_y and np.any(ys <= 0.0):
        raise DomainError(
            f"log_y with non-positive values of {y!r} ({ys[ys <= 0.0].tolist()}); a log axis "
            "would drop those points without saying so."
        )
    fig, axes = _figure_and_axes(ax, height_in=_ONE_PANEL_HEIGHT_IN)
    order = np.argsort(xs)
    if "asymptotic" in y:
        axes.plot(
            xs[order],
            ys[order],
            color=ASYMPTOTIC_COLOR,
            linestyle="--",
            marker="o",
            markerfacecolor=SURFACE,
            label=ASYMPTOTIC_LABEL,
        )
    else:
        axes.plot(xs[order], ys[order], color=FINITE_COLOR, marker="o", label=FINITE_LABEL)
    if log_y:
        axes.set_yscale("log")
    axes.set_xlabel(x if xlabel is None else xlabel)
    axes.set_ylabel(y if ylabel is None else ylabel)
    return fig


def _column(rows: Sequence[Mapping[str, Any]], key: str) -> FloatArray:
    values: list[float] = []
    for i, row in enumerate(rows):
        if key not in row:
            raise DomainError(f"sweep record {i} has no {key!r}; its keys are {sorted(row)}.")
        try:
            value = float(row[key])
        except (TypeError, ValueError) as exc:
            raise DomainError(f"sweep record {i}: {key!r} = {row[key]!r} is not a number.") from exc
        if not np.isfinite(value):
            raise DomainError(f"sweep record {i}: {key!r} = {value!r} is not finite.")
        values.append(value)
    return np.asarray(values, dtype=np.float64)


# --------------------------------------------------------------------------- #
# Geometry
# --------------------------------------------------------------------------- #
def plot_sky_track(result: SimulationResult, station: str, *, ax: Axes | None = None) -> Figure:
    """Draw where each pass crosses the station's sky, as seen looking up.

    A polar plot: the angle is the azimuth (north at the top, east to the
    right, clockwise as on a compass), the radius is the **zenith angle**
    ``90 deg - elevation``, so the zenith is the centre and the horizon the rim.
    That radius is chosen so that a high pass is a short track near the centre
    and a grazing one hugs the rim, the way the sky looks; plotting elevation
    as the radius would put the horizon at the centre. Only in-pass samples are
    drawn, one line per pass (so the track does not jump across the sky between
    passes), each numbered at its start. The elevation mask is the dashed
    circle.

    Parameters
    ----------
    result : SimulationResult
        The run.
    station : str
        Which station's sky.
    ax : Axes, optional
        A **polar** axes; ``None`` creates a figure with one.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        If ``station`` has no series or ``ax`` is not polar.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    series = _station_series(result, station)
    fig, axes = _figure_and_axes(ax, height_in=_SKY_HEIGHT_IN, polar=True)
    axes.set_theta_zero_location("N")
    axes.set_theta_direction(-1)
    axes.set_rlim(0.0, _RIGHT_ANGLE_DEG)
    # The radius is the zenith angle and the label is the elevation, hence the
    # reversed list. All four rings are asked for; matplotlib's polar RadialLocator
    # may drop the one that falls on the origin (r = 0, the zenith), and whether it
    # does has differed between versions. Either outcome is fine and neither is
    # worked around — a "90°" label at the very centre would sit on top of every
    # track that culminates near it — so the test asserts the invariant that holds
    # in both, that a ring at r is labelled `90 - r`, rather than the list of rings.
    axes.set_yticks([0.0, 30.0, 60.0, 90.0], ["90°", "60°", "30°", "0°"])
    axes.grid(True)

    mask_deg = result.scenario.passes.minimum_elevation_deg
    circle = np.linspace(0.0, 2.0 * np.pi, 361)
    axes.plot(
        circle,
        np.full_like(circle, _RIGHT_ANGLE_DEG - mask_deg),
        color=MUTED,
        linestyle="--",
        linewidth=0.8,
        label=f"mask {mask_deg:g}°",
    )

    t = series.grid.t_s
    azimuth = series.azimuth_rad.values
    zenith_deg: FloatArray = _RIGHT_ANGLE_DEG - np.asarray(
        rad_to_deg(series.elevation_rad.values), dtype=np.float64
    )
    passes = _station_passes(result, station)
    drawn = 0
    for number, i in enumerate(passes, start=1):
        inside = (t >= result.passes.start_s[i]) & (t <= result.passes.end_s[i])
        if not np.any(inside):
            continue
        axes.plot(azimuth[inside], zenith_deg[inside], color=FINITE_COLOR)
        first = int(np.flatnonzero(inside)[0])
        axes.plot(azimuth[first], zenith_deg[first], marker="o", color=FINITE_COLOR)
        axes.annotate(
            str(number),
            (azimuth[first], zenith_deg[first]),
            xytext=(3.0, 3.0),
            textcoords="offset points",
            fontsize=SMALL_FONT_SIZE_PT,
            color=INK,
        )
        drawn += 1
    if drawn == 0:
        _empty(axes, "no pass above the mask")
    axes.set_title(f"sky track — {station}", loc="left")
    mark_degradations(fig, result.warnings)
    return fig


# --------------------------------------------------------------------------- #
# Optional stages
# --------------------------------------------------------------------------- #
def plot_multi_station(result: SimulationResult, *, ax: Axes | None = None) -> Figure:
    """Draw the finite key each station contributes under the multi-station policy.

    One solid bar per station: its key over the run (the result's per-day rows
    added up), labelled with how many of its passes the policy kept. The policy
    is the title, because the same stations give different numbers under
    ``sum`` (independent harvests) and ``best_available`` (one satellite
    terminal, overlapping passes conflict) — on the reference day 1 052 607
    against 995 682 bits (``notes`` §30).

    Parameters
    ----------
    result : SimulationResult
        A run whose scenario asked for multi-station aggregation.
    ax : Axes, optional
        Cartesian axes to draw into; ``None`` creates a one-column figure.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        If the result has no multi-station section, or ``ax`` is polar.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    ms = result.multi_station
    if ms is None:
        raise DomainError(
            "this result has no multi_station section: the scenario did not ask for "
            "multi-station aggregation."
        )
    fig, axes = _figure_and_axes(ax, height_in=_ONE_PANEL_HEIGHT_IN)
    x = np.arange(len(ms.station_names), dtype=np.float64)
    totals = ms.bits_per_station_day.sum(axis=1)
    axes.bar(x, totals, width=2.0 * _BAR_WIDTH, color=FINITE_COLOR, label=FINITE_LABEL)
    _mark_zero_key(axes, x, totals)
    for xi, total, count in zip(x, totals, ms.scheduled_pass_count, strict=True):
        axes.annotate(
            f"{int(count)} pass{'es' if int(count) != 1 else ''}",
            (float(xi), float(total)),
            xytext=(0.0, 2.0),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=SMALL_FONT_SIZE_PT,
            color=INK,
        )
    n_days = ms.bits_per_station_day.shape[1]
    axes.set_xticks(x, list(ms.station_names))
    axes.set_ylim(bottom=0.0)
    _engineering(axes, "bit")
    axes.set_ylabel(f"finite key, {n_days} day{'s' if n_days != 1 else ''}")
    axes.set_title(f"policy: {ms.policy}", loc="left")
    mark_degradations(fig, result.warnings)
    return fig


def plot_relay(result: SimulationResult, *, ax: Axes | None = None) -> Figure:
    """Draw, per relayed station pair, the key delivered end to end and the key stranded.

    Two solid bars per pair: the key the satellite delivered (paired across the
    two stations and announced) and the key still stored on board, unpaired,
    when the run ended. Both are certified finite key, so neither is hatched;
    the stranded bar is aqua and carries its value as text (aqua is below 3:1
    contrast on white, :mod:`quoss.viz.style`). The pair label gives the mean
    latency in hours — the time a delivered bit waited on board. On the
    reference day, Castelldefels to OGS Tenerife delivers 432 985 bits and
    strands 129 712 (``notes`` §30).

    Parameters
    ----------
    result : SimulationResult
        A run whose scenario asked for a relay.
    ax : Axes, optional
        Cartesian axes to draw into; ``None`` creates a one-column figure.

    Returns
    -------
    Figure
        The figure ``ax`` belongs to.

    Raises
    ------
    DomainError
        If the result has no relay section, or ``ax`` is polar.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    relay = result.relay
    if relay is None:
        raise DomainError("this result has no relay section: the scenario did not ask for a relay.")
    fig, axes = _figure_and_axes(ax, height_in=_ONE_PANEL_HEIGHT_IN)
    from matplotlib.ticker import EngFormatter

    x = np.arange(len(relay.pairs), dtype=np.float64)
    delivered = relay.delivered_bits_per_day.sum(axis=1)
    axes.bar(
        x - _BAR_WIDTH / 2.0,
        delivered,
        width=_BAR_WIDTH,
        color=FINITE_COLOR,
        label="delivered end to end",
    )
    _mark_zero_key(axes, x - _BAR_WIDTH / 2.0, delivered)
    axes.bar(
        x + _BAR_WIDTH / 2.0,
        relay.residuals,
        width=_BAR_WIDTH,
        color=SECONDARY_COLOR,
        label="stranded on board",
    )
    formatter = EngFormatter(unit="bit")
    for xi, value in zip(x, relay.residuals, strict=True):
        axes.annotate(
            formatter.format_data(float(value)),
            (float(xi) + _BAR_WIDTH / 2.0, float(value)),
            xytext=(0.0, 2.0),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=SMALL_FONT_SIZE_PT,
            color=INK,
        )
    labels = []
    for (a, b), latency_s in zip(relay.pairs, relay.mean_latency_s, strict=True):
        latency = (
            "no delivery"
            if not np.isfinite(latency_s)
            else f"mean latency {latency_s / SECONDS_PER_HOUR:.1f} h"
        )
        labels.append(f"{a} → {b}\n{latency}")
    axes.set_xticks(x, labels)
    axes.set_ylim(bottom=0.0)
    axes.yaxis.set_major_formatter(formatter)
    axes.set_ylabel("key")
    _legend_above(axes)
    mark_degradations(fig, result.warnings)
    return fig


# --------------------------------------------------------------------------- #
# Output
# --------------------------------------------------------------------------- #
def save_figure(
    fig: Figure,
    path: str | Path,
    *,
    formats: Sequence[str] = ("pdf", "png"),
    dpi: float = PNG_DPI,
) -> tuple[Path, ...]:
    """Write a figure to one file per format, the same bytes every time.

    ``path`` is the file name without its extension (an extension that is one
    of :data:`SAVE_FORMATS` is dropped): ``save_figure(fig, "out/fig3")`` writes
    ``out/fig3.pdf`` and ``out/fig3.png``, creating ``out/`` if needed.

    Why reproducible bytes matter: a figure committed next to the paper, or
    produced in CI, should change only when its data or code changed. Two
    things make ordinary matplotlib output differ between saves, and both are
    removed here — the creation timestamp PDF and SVG embed
    (``metadata={"CreationDate": None}`` / ``{"Date": None}``), and the random
    identifiers SVG gives clip paths and hatches (a fixed ``svg.hashsalt``).
    PNG embeds no date. Text in SVG is written as paths and fonts in PDF are
    embedded TrueType, so neither depends on fonts installed where the file is
    opened. Measured in ``tests/viz/test_plots.py::TestSaveFigure``: saving the
    same figure twice gives identical PNG, SVG **and PDF** bytes. The PDF
    guarantee is weaker in one way: its bytes include the matplotlib version in
    the ``Producer`` field, so a different matplotlib gives a different file
    even for an identical drawing (the same holds for the PNG ``Software``
    field).

    The output-related settings (font embedding, SVG text and salt) are applied
    at save time whether or not the figure was built under
    :func:`~quoss.viz.style.use_publication_style`.

    One geometry for every format
    -----------------------------
    The layout is computed **once**, before the first file is written, and then
    frozen (``set_layout_engine("none")``, restored afterwards) so every format
    is written from the same axes rectangle.

    Why: the backends do not agree on the figure's resolution. The raster
    backend draws at the requested ``dpi`` (600 here), while the PDF and SVG
    backends force 72 dpi. Constrained layout runs inside each ``savefig`` and
    starts from the positions the *previous* save left behind, so a PDF written
    after a PNG is laid out from a rectangle solved at a different resolution.
    It does not merely differ: on a one-column figure with a legend band above
    the axes, matplotlib's own solver declares the result collapsed and warns
    "constrained_layout not applied because axes sizes collapsed to zero",
    leaving the PDF with a different plot area than the PNG beside it.

    Concretely, on ``plot_daily_key`` of the reference day: saving pdf, png, svg
    in that order raises the warning on the svg (and again on every repeat),
    while the same three formats saved from a frozen layout raise nothing and
    put the axes at the same rectangle in all three files. The check is
    ``tests/viz/test_plots.py::TestSaveFigure``, where the suite turns any
    warning into an error.

    The axes are then put back where they were on entry, so the call leaves the
    figure as it found it. That is what makes *repeated* saves identical rather
    than merely warning-free: the layout solver is iterative, so it lands one
    unit in the last place away from where it landed before when it starts from
    an already-solved rectangle instead of the declared one — enough to change
    the clip-path identifiers matplotlib derives from the geometry, and so the
    SVG bytes.

    Parameters
    ----------
    fig : Figure
        The figure.
    path : str or Path
        Target without extension.
    formats : Sequence[str]
        Any of :data:`SAVE_FORMATS`, each at most once.
    dpi : float
        Resolution of raster output; :data:`~quoss.viz.style.PNG_DPI` by default.

    Returns
    -------
    tuple[Path, ...]
        The files written, in ``formats`` order.

    Raises
    ------
    DomainError
        On an empty, unknown or repeated format, or a non-positive ``dpi``.
    ConfigurationError
        If ``matplotlib`` is not installed.
    """
    matplotlib = require_matplotlib()
    chosen = tuple(formats)
    unknown = [f for f in chosen if f not in SAVE_FORMATS]
    if not chosen or unknown or len(set(chosen)) != len(chosen):
        raise DomainError(
            f"formats must be a non-empty selection of {SAVE_FORMATS} without repetition, "
            f"got {chosen}."
        )
    if not dpi > 0.0:
        raise DomainError(f"dpi must be positive, got {dpi!r}.")
    target = Path(path)
    if target.suffix.lstrip(".") in SAVE_FORMATS:
        target = target.with_suffix("")
    target.parent.mkdir(parents=True, exist_ok=True)
    style = publication_style()
    written: list[Path] = []
    with matplotlib.rc_context({key: style[key] for key in _SAVE_TIME_KEYS}):
        engine = fig.get_layout_engine()
        placed = [(ax, ax.get_position().frozen(), ax.get_in_layout()) for ax in fig.axes]
        fig.draw_without_rendering()
        fig.set_layout_engine("none")
        try:
            for fmt in chosen:
                out = target.with_name(f"{target.name}.{fmt}")
                fig.savefig(out, format=fmt, dpi=dpi, metadata=_METADATA[fmt], facecolor=SURFACE)
                written.append(out)
        finally:
            fig.set_layout_engine(engine)
            for ax, position, in_layout in placed:
                # set_position takes an axes out of the layout hierarchy, because
                # it assumes a caller placing an axes by hand wants it left alone;
                # here the caller is the layout itself, so put it back.
                ax.set_position(position)
                ax.set_in_layout(in_layout)
    return tuple(written)
