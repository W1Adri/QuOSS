"""Tests for `quoss.viz.plots`.

Every figure is built with ``matplotlib.figure.Figure`` (no GUI, no pyplot) and
rendered once with ``draw_without_rendering`` so that errors that only appear at
draw time — a mathtext typo, a bad layout — fail here.

- ``TestWithoutMatplotlib`` — every public function says which extra is missing.
- ``TestDegradedFootnote`` — a result with a substituted model is marked; one
  without is not; codes merge; the layout makes room.
- ``TestPassKeyVolume`` — the bars are the result's numbers; finite solid,
  asymptotic hatched and labelled "asymptotic (not certified)"; zeros marked;
  Monte Carlo whiskers are the quantiles.
- ``TestElevationAndRate``, ``TestDailyKey``, ``TestSweep``, ``TestSkyTrack``,
  ``TestMultiStation``, ``TestRelay`` — each plot's data, labels and refusals.
- ``TestSaveFigure`` — reproducible bytes, resolution, embedded fonts, refusals.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.layout_engine import ConstrainedLayoutEngine
from matplotlib.text import Text

from quoss.core.errors import ConfigurationError, DomainError
from quoss.core.units import rad_to_deg
from quoss.scenario.result import SimulationResult
from quoss.viz.plots import (
    DEGRADED_GID,
    DEGRADED_PREFIX,
    ZERO_KEY_GID,
    degraded_codes,
    mark_degradations,
    plot_daily_key,
    plot_elevation_and_rate,
    plot_multi_station,
    plot_pass_key_volume,
    plot_relay,
    plot_sky_track,
    plot_sweep,
    save_figure,
)
from quoss.viz.style import (
    ASYMPTOTIC_HATCH,
    ASYMPTOTIC_LABEL,
    FINITE_COLOR,
    FINITE_LABEL,
    use_publication_style,
)

from .builders import (
    ASYMPTOTIC_BITS,
    DEGRADED_WARNING,
    FINITE_BITS,
    INFO_WARNING,
    QUANTILE_BITS,
    hide_matplotlib,
    make_result,
    xdata,
    ydata,
)

STATION = "castelldefels"


def all_text(fig: Any) -> list[str]:
    fig.draw_without_rendering()
    return [t.get_text() for t in fig.findobj(Text)]


def footnotes(fig: Any) -> list[str]:
    return [t.get_text() for t in fig.texts if t.get_gid() == DEGRADED_GID]


def containers(fig: Any, label: str) -> list[Any]:
    return [c for ax in fig.axes for c in ax.containers if c.get_label() == label]


def legend_of(ax: Any) -> Any:
    legend = ax.get_legend()
    assert legend is not None
    return legend


def tight_bottom(ax: Any, renderer: Any) -> float:
    box = ax.get_tightbbox(renderer)
    assert box is not None
    return float(box.y0)


def anchor_x(annotation: Any) -> float:
    """Return the x of the point an annotation points at (``Annotation.xy``, not on ``Text``)."""
    return float(annotation.xy[0])


def sweep_records() -> list[dict[str, Any]]:
    # Shape of ADR 0011 §5 (fixture values, not a measurement here).
    rows = [
        (10.0, 432_985.0, 3_776_681.0),
        (2.0, 408_946.0, 3_876_492.0),
        (8.0, 434_938.0, 3_844_682.0),
    ]
    return [
        {
            "passes.minimum_elevation_deg": m,
            "daily.finite_bits": f,
            "daily.asymptotic_bits": a,
            "scenario_hash": "0" * 64,
        }
        for m, f, a in rows
    ]


PLOTS_OF_A_RESULT: list[tuple[str, Callable[[SimulationResult], Any]]] = [
    ("elevation_and_rate", lambda r: plot_elevation_and_rate(r, STATION)),
    ("pass_key_volume", lambda r: plot_pass_key_volume(r)),
    ("daily_key", lambda r: plot_daily_key(r)),
    ("sky_track", lambda r: plot_sky_track(r, STATION)),
    ("multi_station", lambda r: plot_multi_station(r)),
    ("relay", lambda r: plot_relay(r)),
]


class TestWithoutMatplotlib:
    @pytest.mark.parametrize(("name", "plot"), PLOTS_OF_A_RESULT)
    def test_every_plot_names_the_extra(
        self, monkeypatch: pytest.MonkeyPatch, name: str, plot: Callable[[SimulationResult], Any]
    ) -> None:
        result = make_result(multi_station=True, relay=True)
        hide_matplotlib(monkeypatch)
        with pytest.raises(ConfigurationError, match=r"quoss\[viz\]"):
            plot(result)

    def test_sweep_and_save(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        fig = Figure()
        hide_matplotlib(monkeypatch)
        with pytest.raises(ConfigurationError):
            plot_sweep(sweep_records(), x="passes.minimum_elevation_deg", y="daily.finite_bits")
        with pytest.raises(ConfigurationError):
            save_figure(fig, tmp_path / "f")


class TestDegradedFootnote:
    @pytest.mark.parametrize(("name", "plot"), PLOTS_OF_A_RESULT)
    def test_every_plot_marks_a_degraded_result(
        self, name: str, plot: Callable[[SimulationResult], Any]
    ) -> None:
        result = make_result(
            multi_station=True, relay=True, warnings=[INFO_WARNING, DEGRADED_WARNING]
        )
        fig = plot(result)
        assert footnotes(fig) == [DEGRADED_PREFIX + "channel.background-interpolated"]
        assert DEGRADED_PREFIX + "channel.background-interpolated" in all_text(fig)

    @pytest.mark.parametrize(("name", "plot"), PLOTS_OF_A_RESULT)
    def test_info_and_warning_entries_do_not_mark(
        self, name: str, plot: Callable[[SimulationResult], Any]
    ) -> None:
        warning = {**INFO_WARNING, "severity": "warning", "code": "pcflos.no-elevation-dependence"}
        fig = plot(make_result(multi_station=True, relay=True, warnings=[INFO_WARNING, warning]))
        assert footnotes(fig) == []
        assert not [t for t in all_text(fig) if t.startswith("DEGRADED")]

    def test_codes_from_two_plots_merge_into_one_footnote(self) -> None:
        fig = Figure(layout="constrained")
        left, right = fig.subplots(1, 2)
        other = {**DEGRADED_WARNING, "code": "atmosphere.profile-extrapolated"}
        plot_pass_key_volume(make_result(warnings=[DEGRADED_WARNING]), ax=left)
        plot_daily_key(make_result(warnings=[other, DEGRADED_WARNING]), ax=right)
        assert footnotes(fig) == [
            DEGRADED_PREFIX + "atmosphere.profile-extrapolated, channel.background-interpolated"
        ]

    def test_the_constrained_layout_leaves_room_at_the_foot(self) -> None:
        fig = plot_pass_key_volume(make_result(warnings=[DEGRADED_WARNING]))
        engine = fig.get_layout_engine()
        assert isinstance(engine, ConstrainedLayoutEngine)
        assert engine.get()["rect"] == pytest.approx((0.0, 0.07, 1.0, 0.93))
        fig.draw_without_rendering()
        note = next(t for t in fig.texts if t.get_gid() == DEGRADED_GID)
        renderer = FigureCanvasAgg(fig).get_renderer()
        note_top = note.get_window_extent(renderer).y1
        axes_bottom = min(tight_bottom(ax, renderer) for ax in fig.axes)
        assert note_top <= axes_bottom

    def test_a_figure_without_a_layout_engine_still_gets_the_footnote(self) -> None:
        fig = Figure()
        mark_degradations(fig, [DEGRADED_WARNING])
        assert fig.get_layout_engine() is None
        assert footnotes(fig) == [DEGRADED_PREFIX + "channel.background-interpolated"]

    def test_nothing_degraded_leaves_the_figure_untouched(self) -> None:
        fig = Figure()
        mark_degradations(fig, [INFO_WARNING])
        assert fig.texts == []

    def test_codes_ignore_entries_without_severity(self) -> None:
        assert degraded_codes([{"code": "x"}, DEGRADED_WARNING]) == (
            "channel.background-interpolated",
        )


class TestPassKeyVolume:
    def test_the_bars_are_the_results_numbers(self) -> None:
        fig = plot_pass_key_volume(make_result())
        (finite,) = containers(fig, FINITE_LABEL)
        (asymptotic,) = containers(fig, ASYMPTOTIC_LABEL)
        assert [p.get_height() for p in finite] == list(FINITE_BITS)
        assert [p.get_height() for p in asymptotic] == list(ASYMPTOTIC_BITS)

    def test_finite_is_solid_and_asymptotic_is_hatched_and_not_certified(self) -> None:
        fig = plot_pass_key_volume(make_result())
        (finite,) = containers(fig, FINITE_LABEL)
        (asymptotic,) = containers(fig, ASYMPTOTIC_LABEL)
        assert all(not p.get_hatch() for p in finite)
        assert all(p.get_fill() for p in finite)
        assert all(p.get_hatch() == ASYMPTOTIC_HATCH for p in asymptotic)
        legend = [t.get_text() for t in legend_of(fig.axes[0]).get_texts()]
        assert "asymptotic (not certified)" in legend
        assert FINITE_LABEL in legend

    def test_passes_with_zero_finite_key_are_marked_0(self) -> None:
        fig = plot_pass_key_volume(make_result())
        zeros = [t for t in fig.axes[0].texts if t.get_gid() == ZERO_KEY_GID]
        assert [z.get_text() for z in zeros] == ["0", "0"]
        (finite,) = containers(fig, FINITE_LABEL)
        centres = [p.get_x() + p.get_width() / 2.0 for p in finite]
        assert [anchor_x(z) for z in zeros] == pytest.approx([centres[1], centres[3]])

    def test_tick_labels_give_the_pass_and_its_utc_start(self) -> None:
        fig = plot_pass_key_volume(make_result(truncated_end=(False, False, False, True)))
        labels = [t.get_text() for t in fig.axes[0].get_xticklabels()]
        # 20 040 s after 00:00 UTC is 05:34.
        assert labels == ["1\n05:34", "2\n07:15", "3\n16:41", "4 (cut)\n18:22"]

    def test_several_stations_name_the_station(self) -> None:
        fig = plot_pass_key_volume(make_result(second_station="tenerife"))
        labels = [t.get_text().split("\n")[0] for t in fig.axes[0].get_xticklabels()]
        assert labels == ["castelldefels 1", "tenerife 1", "castelldefels 2", "tenerife 2"]

    def test_monte_carlo_whiskers_span_the_extreme_quantiles(self) -> None:
        fig = plot_pass_key_volume(make_result(monte_carlo=True))
        ax = fig.axes[0]
        (whiskers,) = [
            c
            for c in ax.collections
            if isinstance(c, LineCollection) and c.get_label() == "Monte Carlo P5-P95"
        ]
        (finite,) = containers(fig, FINITE_LABEL)
        centres = [p.get_x() + p.get_width() / 2.0 for p in finite]
        segments = whiskers.get_segments()
        assert [s[0][0] for s in segments] == pytest.approx(centres)
        assert [s[0][1] for s in segments] == list(QUANTILE_BITS[0])
        assert [s[1][1] for s in segments] == list(QUANTILE_BITS[2])
        (median,) = [line for line in ax.lines if line.get_label() == "Monte Carlo P50"]
        assert list(ydata(median)) == list(QUANTILE_BITS[1])

    def test_only_a_median_draws_no_whisker(self) -> None:
        fig = plot_pass_key_volume(make_result(monte_carlo=True, quantiles=(0.5,)))
        ax = fig.axes[0]
        assert not [c for c in ax.collections if str(c.get_label()).startswith("Monte Carlo P")]
        assert [line.get_label() for line in ax.lines] == ["Monte Carlo P50"]

    def test_no_median_draws_no_ring(self) -> None:
        fig = plot_pass_key_volume(make_result(monte_carlo=True, quantiles=(0.05, 0.95)))
        assert [line.get_label() for line in fig.axes[0].lines] == []

    def test_hiding_the_asymptotic_bars_centres_the_finite_ones(self) -> None:
        fig = plot_pass_key_volume(make_result(), show_asymptotic=False)
        assert containers(fig, ASYMPTOTIC_LABEL) == []
        (finite,) = containers(fig, FINITE_LABEL)
        assert [p.get_x() + p.get_width() / 2.0 for p in finite] == pytest.approx([0, 1, 2, 3])

    def test_no_passes(self) -> None:
        fig = plot_pass_key_volume(make_result(no_passes=True, warnings=[DEGRADED_WARNING]))
        assert "no pass above the mask" in all_text(fig)
        assert footnotes(fig)

    def test_draws_into_a_given_axes(self) -> None:
        fig = Figure()
        ax = fig.add_subplot()
        assert plot_pass_key_volume(make_result(), ax=ax) is fig

    def test_refuses_a_polar_axes(self) -> None:
        ax = Figure().add_subplot(projection="polar")
        with pytest.raises(DomainError, match="Cartesian"):
            plot_pass_key_volume(make_result(), ax=ax)

    def test_renders_under_the_publication_style(self) -> None:
        with use_publication_style():
            fig = plot_pass_key_volume(make_result(monte_carlo=True))
            texts = all_text(fig)
        assert "asymptotic (not certified)" in texts


class TestElevationAndRate:
    def test_two_panels_with_the_results_series(self) -> None:
        result = make_result()
        fig = plot_elevation_and_rate(result, STATION)
        elevation, rate = fig.axes
        series = result.series_for(STATION)
        np.testing.assert_array_equal(
            elevation.lines[0].get_ydata(), rad_to_deg(series.elevation_rad.values)
        )
        np.testing.assert_array_equal(
            rate.lines[0].get_ydata(), series.asymptotic_secure_bit_s.values
        )
        assert elevation.get_ylim() == (0.0, 90.0)
        assert rate.get_title(loc="left") == ASYMPTOTIC_LABEL
        assert rate.get_shared_x_axes().joined(elevation, rate)

    def test_the_mask_and_the_pass_windows(self) -> None:
        fig = plot_elevation_and_rate(make_result(), STATION)
        elevation, rate = fig.axes
        mask = [line for line in elevation.lines if list(ydata(line)) == [10.0, 10.0]]
        assert len(mask) == 1
        assert "mask 10°" in all_text(fig)
        for panel in (elevation, rate):
            assert len(panel.patches) == 4

    def test_the_rate_area_is_hatched(self) -> None:
        fig = plot_elevation_and_rate(make_result(), STATION)
        (area,) = fig.axes[1].collections
        assert area.get_hatch() == ASYMPTOTIC_HATCH

    def test_only_the_stations_own_passes_are_shaded(self) -> None:
        fig = plot_elevation_and_rate(make_result(second_station="tenerife"), "tenerife")
        assert len(fig.axes[0].patches) == 2

    def test_splits_a_given_grid_axes(self) -> None:
        fig = Figure(layout="constrained")
        left, right = fig.subplots(1, 2)
        assert plot_elevation_and_rate(make_result(), STATION, ax=right) is fig
        assert left in fig.axes
        assert right not in fig.axes
        assert len(fig.axes) == 3
        all_text(fig)

    def test_refuses_an_axes_outside_a_grid(self) -> None:
        fig = Figure()
        ax = fig.add_axes((0.1, 0.1, 0.8, 0.8))
        with pytest.raises(DomainError, match="grid"):
            plot_elevation_and_rate(make_result(), STATION, ax=ax)

    def test_refuses_an_unknown_station(self) -> None:
        with pytest.raises(DomainError, match="calar_alto"):
            plot_elevation_and_rate(make_result(), "calar_alto")


class TestDailyKey:
    def test_bars_dates_and_composed_security(self) -> None:
        result = make_result()
        fig = plot_daily_key(result)
        ax = fig.axes[0]
        (finite,) = containers(fig, FINITE_LABEL)
        (asymptotic,) = containers(fig, ASYMPTOTIC_LABEL)
        assert [p.get_height() for p in finite] == [sum(FINITE_BITS)]
        assert [p.get_height() for p in asymptotic] == [pytest.approx(sum(ASYMPTOTIC_BITS))]
        assert [t.get_text() for t in ax.get_xticklabels()] == ["2025-01-01"]
        assert "4e-10" in ax.get_title(loc="right")
        all_text(fig)

    def test_no_composition_no_title(self) -> None:
        fig = plot_daily_key(make_result(composed=False))
        assert fig.axes[0].get_title(loc="right") == ""

    def test_a_day_with_zero_key_is_marked(self) -> None:
        fig = plot_daily_key(make_result(finite_bits=(0.0, 0.0, 0.0, 0.0)))
        assert [t.get_text() for t in fig.axes[0].texts if t.get_gid() == ZERO_KEY_GID] == ["0"]

    def test_no_days(self) -> None:
        fig = plot_daily_key(make_result(no_passes=True, no_days=True))
        assert "no day in this result" in all_text(fig)


class TestSweep:
    X = "passes.minimum_elevation_deg"

    def test_points_are_drawn_in_order_of_the_parameter(self) -> None:
        fig = plot_sweep(sweep_records(), x=self.X, y="daily.finite_bits")
        (line,) = fig.axes[0].lines
        assert list(xdata(line)) == [2.0, 8.0, 10.0]
        assert list(ydata(line)) == [408_946.0, 434_938.0, 432_985.0]
        assert line.get_label() == FINITE_LABEL
        assert line.get_color() == FINITE_COLOR
        assert fig.axes[0].get_xlabel() == self.X

    def test_an_asymptotic_metric_uses_the_asymptotic_vocabulary(self) -> None:
        fig = plot_sweep(
            sweep_records(), x=self.X, y="daily.asymptotic_bits", log_y=True, ylabel="key"
        )
        (line,) = fig.axes[0].lines
        assert line.get_label() == "asymptotic (not certified)"
        assert line.get_linestyle() == "--"
        assert fig.axes[0].get_yscale() == "log"
        assert fig.axes[0].get_ylabel() == "key"

    @pytest.mark.parametrize(
        ("records", "match"),
        [
            ([], "at least one"),
            ([{"passes.minimum_elevation_deg": 2.0}], "no 'daily.finite_bits'"),
            ([{"passes.minimum_elevation_deg": "low", "daily.finite_bits": 1.0}], "not a number"),
            ([{"passes.minimum_elevation_deg": None, "daily.finite_bits": 1.0}], "not a number"),
            ([{"passes.minimum_elevation_deg": 2.0, "daily.finite_bits": float("nan")}], "finite"),
            (
                [
                    {"passes.minimum_elevation_deg": 2.0, "daily.finite_bits": 1.0},
                    {"passes.minimum_elevation_deg": 2.0, "daily.finite_bits": 2.0},
                ],
                "share a value",
            ),
        ],
    )
    def test_refusals(self, records: list[dict[str, Any]], match: str) -> None:
        with pytest.raises(DomainError, match=match):
            plot_sweep(records, x=self.X, y="daily.finite_bits")

    def test_a_log_axis_refuses_a_zero_it_would_drop(self) -> None:
        records = [
            {self.X: 2.0, "daily.finite_bits": 0.0},
            {self.X: 5.0, "daily.finite_bits": 10.0},
        ]
        with pytest.raises(DomainError, match="drop"):
            plot_sweep(records, x=self.X, y="daily.finite_bits", log_y=True)


class TestSkyTrack:
    def test_one_track_per_pass_at_the_zenith_angle(self) -> None:
        result = make_result()
        fig = plot_sky_track(result, STATION)
        ax = fig.axes[0]
        assert ax.name == "polar"
        series = result.series_for(STATION)
        t = series.grid.t_s
        tracks = [line for line in ax.lines if line.get_marker() in ("None", None, "")]
        mask, *passes = tracks
        assert list(ydata(mask))[:1] == [80.0]
        assert len(passes) == 4
        inside = (t >= result.passes.start_s[0]) & (t <= result.passes.end_s[0])
        np.testing.assert_allclose(
            ydata(passes[0]),
            90.0 - np.asarray(rad_to_deg(series.elevation_rad.values[inside])),
        )
        np.testing.assert_array_equal(xdata(passes[0]), series.azimuth_rad.values[inside])
        assert {"1", "2", "3", "4", "mask 10°"} <= set(all_text(fig)) | {
            line.get_label() for line in ax.lines
        }
        # The radius is the zenith angle and the label is the elevation, so they run
        # the opposite way: r = 30 deg from the centre is 60 deg above the horizon.
        # Only three of the four requested rings are drawn — matplotlib's polar
        # RadialLocator drops the tick that sits exactly on the origin, which here is
        # r = 0, the zenith — and the labels stay paired with the rings that remain.
        assert [
            (tick.get_loc(), tick.label1.get_text()) for tick in ax.yaxis.get_major_ticks()
        ] == [
            (30.0, "60°"),
            (60.0, "30°"),
            (90.0, "0°"),
        ]

    def test_a_pass_between_grid_samples_is_skipped(self) -> None:
        result = make_result()
        # A pass narrower than the 60 s grid step contains no sample.
        passes = result.passes
        narrow = type(passes)(
            **{
                **{f: getattr(passes, f) for f in passes.__dataclass_fields__},
                "start_s": passes.start_s + np.array([0.0, 0.0, 0.0, 1.0]),
                "end_s": np.array([*passes.end_s[:3], passes.start_s[3] + 2.0]),
            }
        )
        fig = plot_sky_track(
            SimulationResult(
                **{
                    **{f: getattr(result, f) for f in result.__dataclass_fields__},
                    "passes": narrow,
                }
            ),
            STATION,
        )
        assert "4" not in [t.get_text() for t in fig.axes[0].texts]

    def test_no_passes(self) -> None:
        fig = plot_sky_track(make_result(no_passes=True), STATION)
        assert "no pass above the mask" in all_text(fig)

    def test_refuses_a_cartesian_axes(self) -> None:
        with pytest.raises(DomainError, match="polar"):
            plot_sky_track(make_result(), STATION, ax=Figure().add_subplot())

    def test_draws_into_a_given_polar_axes(self) -> None:
        fig = Figure()
        assert plot_sky_track(make_result(), STATION, ax=fig.add_subplot(projection="polar")) is fig


class TestMultiStation:
    def test_bars_counts_and_policy(self) -> None:
        fig = plot_multi_station(make_result(multi_station=True))
        ax = fig.axes[0]
        (bars,) = containers(fig, FINITE_LABEL)
        assert [p.get_height() for p in bars] == [432_985.0, 0.0, 562_697.0]
        texts = [t.get_text() for t in ax.texts]
        assert texts.count("0") == 1
        assert {"2 passes", "0 passes", "1 pass"} <= set(texts)
        assert ax.get_title(loc="left") == "policy: best_available"
        assert ax.get_ylabel() == "finite key, 1 day"
        all_text(fig)

    def test_refuses_a_result_without_the_section(self) -> None:
        with pytest.raises(DomainError, match="multi_station"):
            plot_multi_station(make_result())


class TestRelay:
    def test_delivered_stranded_and_latency(self) -> None:
        fig = plot_relay(make_result(relay=True))
        ax = fig.axes[0]
        (delivered,) = containers(fig, "delivered end to end")
        (stranded,) = containers(fig, "stranded on board")
        assert [p.get_height() for p in delivered] == [432_985.0, 0.0]
        assert [p.get_height() for p in stranded] == [129_712.0, 0.0]
        labels = [t.get_text() for t in ax.get_xticklabels()]
        # 15 199 s is 4.22 h.
        assert labels == [
            "castelldefels → ogs_tenerife\nmean latency 4.2 h",
            "castelldefels → calar_alto\nno delivery",
        ]
        values = [t.get_text() for t in ax.texts if t.get_gid() != ZERO_KEY_GID]
        assert values[0].startswith("129.712") and values[0].endswith("kbit")
        assert [t.get_text() for t in ax.texts if t.get_gid() == ZERO_KEY_GID] == ["0"]
        all_text(fig)

    def test_refuses_a_result_without_the_section(self) -> None:
        with pytest.raises(DomainError, match="relay"):
            plot_relay(make_result())


class TestSaveFigure:
    def test_writes_one_file_per_format(self, tmp_path: Path) -> None:
        fig = plot_pass_key_volume(make_result())
        written = save_figure(fig, tmp_path / "nested" / "fig.pdf")
        assert written == (tmp_path / "nested" / "fig.pdf", tmp_path / "nested" / "fig.png")
        assert all(p.stat().st_size > 0 for p in written)

    def test_saving_twice_gives_identical_bytes(self, tmp_path: Path) -> None:
        """PNG, SVG and PDF alike: no timestamp, no random SVG identifiers."""
        with use_publication_style():
            fig = plot_pass_key_volume(make_result(monte_carlo=True, warnings=[DEGRADED_WARNING]))
        first = save_figure(fig, tmp_path / "a", formats=("png", "svg", "pdf"))
        second = save_figure(fig, tmp_path / "b", formats=("png", "svg", "pdf"))
        for one, two in zip(first, second, strict=True):
            assert one.read_bytes() == two.read_bytes(), one.suffix

    def test_two_separately_built_figures_give_identical_bytes(self, tmp_path: Path) -> None:
        with use_publication_style():
            one = save_figure(
                plot_daily_key(make_result()), tmp_path / "one", formats=("svg", "pdf")
            )
            two = save_figure(
                plot_daily_key(make_result()), tmp_path / "two", formats=("svg", "pdf")
            )
        for a, b in zip(one, two, strict=True):
            assert a.read_bytes() == b.read_bytes(), a.suffix

    def test_the_png_is_at_the_requested_resolution(self, tmp_path: Path) -> None:
        fig = Figure(figsize=(3.5, 2.0))
        (png,) = save_figure(fig, tmp_path / "f", formats=("png",))
        header = png.read_bytes()
        # IHDR: width and height are big-endian uint32 at bytes 16-24.
        assert int.from_bytes(header[16:20], "big") == 3.5 * 600
        assert int.from_bytes(header[20:24], "big") == 2.0 * 600

    def test_fonts_are_embedded_truetype_and_svg_text_is_paths(self, tmp_path: Path) -> None:
        fig = plot_pass_key_volume(make_result())  # built outside the style on purpose
        pdf, svg = save_figure(fig, tmp_path / "f", formats=("pdf", "svg"))
        pdf_bytes = pdf.read_bytes()
        assert b"/FontFile2" in pdf_bytes
        assert b"/Type3" not in pdf_bytes
        assert b"<text" not in svg.read_bytes()

    @pytest.mark.parametrize(
        ("formats", "dpi"),
        [((), 600.0), (("jpg",), 600.0), (("png", "png"), 600.0), (("png",), 0.0)],
    )
    def test_refusals(self, tmp_path: Path, formats: tuple[str, ...], dpi: float) -> None:
        with pytest.raises(DomainError):
            save_figure(Figure(), tmp_path / "f", formats=formats, dpi=dpi)
