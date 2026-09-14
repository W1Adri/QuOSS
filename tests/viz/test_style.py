"""Tests for `quoss.viz.style`.

- ``TestWithoutMatplotlib`` — the package imports without the extra; using it
  says which extra to install.
- ``TestPublicationStyle`` — every key is a real ``rcParams`` name, the context
  applies and restores, the font is the bundled one, the sizes are IEEE's.
- ``TestPaletteIsColourBlindSafe`` — the palette checks of the dataviz method,
  recomputed here from the validator's own transforms rather than quoted.
- ``TestTheVocabulary`` — the labels that carry meaning, verbatim.
- ``TestNoGlobalPlottingState`` — no module of the package imports ``pyplot``.
"""

from __future__ import annotations

import ast
import importlib
import math
import sys
from itertools import combinations, pairwise
from pathlib import Path
from typing import Any, cast

import matplotlib
import pytest
from matplotlib import font_manager

from quoss.core.errors import ConfigurationError
from quoss.viz import style
from quoss.viz.style import (
    ASYMPTOTIC_COLOR,
    ASYMPTOTIC_HATCH,
    ASYMPTOTIC_LABEL,
    COLUMN_WIDTH_IN,
    DOUBLE_COLUMN_WIDTH_IN,
    FINITE_COLOR,
    FINITE_LABEL,
    FONT_SIZE_PT,
    MAX_HEIGHT_IN,
    PALETTE,
    PNG_DPI,
    SECONDARY_COLOR,
    SMALL_FONT_SIZE_PT,
    SURFACE,
    publication_style,
    require_matplotlib,
    use_publication_style,
)

from .builders import hide_matplotlib

VIZ_SOURCE = Path(style.__file__).resolve().parent


class TestWithoutMatplotlib:
    def test_require_matplotlib_names_the_extra(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hide_matplotlib(monkeypatch)
        with pytest.raises(ConfigurationError, match=r"quoss\[viz\]"):
            require_matplotlib()

    def test_the_style_context_refuses_without_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hide_matplotlib(monkeypatch)
        with pytest.raises(ConfigurationError), use_publication_style():
            pass  # pragma: no cover - the context never enters

    @pytest.mark.parametrize("module", ["quoss.viz.style", "quoss.viz.plots", "quoss.viz.figures"])
    def test_every_module_imports_without_it(
        self, monkeypatch: pytest.MonkeyPatch, module: str
    ) -> None:
        hide_matplotlib(monkeypatch)
        for name in ("quoss.viz.style", "quoss.viz.plots", "quoss.viz.figures"):
            if name in sys.modules:
                monkeypatch.delitem(sys.modules, name)
        fresh = importlib.import_module(module)
        assert fresh.__all__

    def test_the_style_dict_needs_no_matplotlib(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hide_matplotlib(monkeypatch)
        assert publication_style()["font.size"] == FONT_SIZE_PT


def rc(key: str) -> Any:
    """Return ``matplotlib.rcParams[key]`` for a key known only at runtime.

    ``RcParams`` is annotated with a ``Literal`` of every key matplotlib knows,
    which is the right annotation for a hand-written ``rcParams["font.size"]``
    and the wrong one here: this test's whole job is to walk the keys the style
    dict hands it, so the key is a plain ``str`` and the value is whatever the
    validator made of it.
    """
    return cast("dict[str, Any]", matplotlib.rcParams)[key]


class TestPublicationStyle:
    def test_every_key_is_a_real_rcparam(self) -> None:
        # rc_context validates each key and value; an unknown key raises KeyError.
        with matplotlib.rc_context(cast("Any", publication_style())):
            for key, value in publication_style().items():
                if key == "axes.prop_cycle":
                    colours = rc(key).by_key()["color"]
                    assert tuple(colours) == PALETTE
                elif key == "font.family":
                    # matplotlib's validator wraps a bare family name in a list, so
                    # the round trip is "serif" -> ["serif"] and not an equality.
                    assert list(rc(key)) == [value]
                elif key in ("font.serif",):
                    assert list(rc(key)) == value
                elif key == "figure.figsize":
                    assert tuple(rc(key)) == value
                else:
                    assert rc(key) == value, key

    def test_the_context_restores_the_previous_settings(self) -> None:
        before = matplotlib.rcParams["font.size"]
        with use_publication_style():
            assert matplotlib.rcParams["font.size"] == FONT_SIZE_PT
        assert matplotlib.rcParams["font.size"] == before

    def test_the_context_restores_after_an_exception(self) -> None:
        before = dict(matplotlib.rcParams)
        with pytest.raises(RuntimeError), use_publication_style():
            raise RuntimeError("inside")
        assert dict(matplotlib.rcParams) == before

    def test_the_font_is_the_one_bundled_with_matplotlib(self) -> None:
        """No dependency on system fonts: the file sits in matplotlib's own data directory."""
        found = font_manager.findfont(
            font_manager.FontProperties(family=publication_style()["font.serif"]),
            fallback_to_default=False,
        )
        assert Path(found).name == "STIXGeneral.ttf"
        assert Path(found).resolve().is_relative_to(Path(matplotlib.get_data_path()).resolve())

    def test_ieee_sizes(self) -> None:
        # IEEE author centre, "Resolution and Size" / "File Formatting" (module docstring).
        assert (COLUMN_WIDTH_IN, DOUBLE_COLUMN_WIDTH_IN, MAX_HEIGHT_IN) == (3.5, 7.16, 8.8)
        assert PNG_DPI >= 600
        assert publication_style()["figure.figsize"][0] == COLUMN_WIDTH_IN

    def test_type_sizes_are_approximately_9_to_10_pt(self) -> None:
        """Labels at the guide's 9 pt; small text one step down, never below 8 pt."""
        s = publication_style()
        assert s["axes.labelsize"] == FONT_SIZE_PT == 9.0
        assert {s["xtick.labelsize"], s["ytick.labelsize"], s["legend.fontsize"]} == {
            SMALL_FONT_SIZE_PT
        }
        assert SMALL_FONT_SIZE_PT == 8.0

    def test_fonts_are_embedded_not_type3(self) -> None:
        s = publication_style()
        assert (s["pdf.fonttype"], s["ps.fonttype"], s["svg.fonttype"]) == (42, 42, "path")

    def test_gridlines_are_solid_hairlines(self) -> None:
        s = publication_style()
        assert s["grid.linestyle"] == "-"
        assert s["grid.linewidth"] < s["lines.linewidth"]


# --------------------------------------------------------------------------- #
# Colour science, copied from the dataviz skill's validate_palette.py so the
# palette numbers in the style docstring are recomputed by a test that runs.
# OKLab: Ottosson 2020 matrices. CVD: Machado, Oliveira & Fernandes 2009,
# severity 1.0, applied in linear RGB. Delta E = 100 x Euclidean OKLab distance.
# --------------------------------------------------------------------------- #
MACHADO = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
}
LIGHT_BAND = (0.43, 0.77)
CHROMA_FLOOR = 0.10
CVD_TARGET = 8.0
NORMAL_FLOOR = 15.0
PRINTED_ONE_DECIMAL = 0.05
"""The validator prints Delta E to one decimal, so agreement is within half a unit of it."""
PRINTED_TWO_DECIMALS = 0.005


def _linear(hex_colour: str) -> tuple[float, float, float]:
    def channel(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    return channel(r), channel(g), channel(b)


def _oklab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    lc = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    mc = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    sc = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * lc + 0.7936177850 * mc - 0.0040720468 * sc,
        1.9779984951 * lc - 2.4285922050 * mc + 0.4505937099 * sc,
        0.0259040371 * lc + 0.7827717662 * mc - 0.8086757660 * sc,
    )


def _simulate(rgb: tuple[float, float, float], kind: str) -> tuple[float, float, float]:
    m = MACHADO[kind]
    out = [sum(m[i][j] * rgb[j] for j in range(3)) for i in range(3)]
    return (min(1.0, max(0.0, out[0])), min(1.0, max(0.0, out[1])), min(1.0, max(0.0, out[2])))


def delta_e(a: str, b: str, kind: str | None = None) -> float:
    la, lb = _linear(a), _linear(b)
    if kind is not None:
        la, lb = _simulate(la, kind), _simulate(lb, kind)
    return 100.0 * math.dist(_oklab(la), _oklab(lb))


def luminance(hex_colour: str) -> float:
    r, g, b = _linear(hex_colour)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: str, b: str) -> float:
    high, low = sorted((luminance(a), luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


def worst_cvd(pairs: list[tuple[str, str]]) -> float:
    return min(delta_e(a, b, kind) for a, b in pairs for kind in ("protan", "deutan"))


def worst_normal(pairs: list[tuple[str, str]]) -> float:
    return min(delta_e(a, b) for a, b in pairs)


class TestPaletteIsColourBlindSafe:
    def test_at_most_six_distinct_colours_in_the_documented_order(self) -> None:
        assert len(PALETTE) <= 6
        assert len(set(PALETTE)) == len(PALETTE)
        assert (FINITE_COLOR, ASYMPTOTIC_COLOR, SECONDARY_COLOR) == PALETTE[:3]

    def test_the_colour_science_reproduces_a_known_value(self) -> None:
        """Guard for the transcription: white is OKLab L = 1, a = b = 0 (to 1e-4)."""
        l_white, a_white, b_white = _oklab(_linear("#ffffff"))
        assert l_white == pytest.approx(1.0, abs=1e-4)
        assert abs(a_white) < 1e-4
        assert abs(b_white) < 1e-4

    def test_lightness_band_and_chroma_floor(self) -> None:
        for colour in PALETTE:
            lightness, a, b = _oklab(_linear(colour))
            assert LIGHT_BAND[0] <= lightness <= LIGHT_BAND[1], colour
            assert math.hypot(a, b) >= CHROMA_FLOOR, colour

    def test_adjacent_pairs_of_all_six(self) -> None:
        pairs = list(pairwise(PALETTE))
        assert worst_cvd(pairs) >= CVD_TARGET
        assert worst_normal(pairs) >= NORMAL_FLOOR
        assert worst_cvd(pairs) == pytest.approx(9.1, abs=PRINTED_ONE_DECIMAL)
        assert worst_normal(pairs) == pytest.approx(19.6, abs=PRINTED_ONE_DECIMAL)

    def test_all_pairs_of_the_three_the_plots_assign(self) -> None:
        pairs = list(combinations(PALETTE[:3], 2))
        assert worst_cvd(pairs) >= CVD_TARGET
        assert worst_normal(pairs) >= NORMAL_FLOOR
        assert worst_cvd(pairs) == pytest.approx(9.2, abs=PRINTED_ONE_DECIMAL)
        assert worst_normal(pairs) == pytest.approx(24.0, abs=PRINTED_ONE_DECIMAL)

    def test_the_low_contrast_colours_are_the_ones_the_docstring_names(self) -> None:
        low = {c: round(contrast(c, SURFACE), 2) for c in PALETTE if contrast(c, SURFACE) < 3.0}
        assert low == pytest.approx(
            {"#1baf7a": 2.82, "#eda100": 2.17, "#e87ba4": 2.69}, abs=PRINTED_TWO_DECIMALS
        )

    def test_blue_and_orange_nearly_merge_in_greyscale(self) -> None:
        """Why colour cannot be the only thing separating finite from asymptotic key."""
        blue, orange = luminance(FINITE_COLOR), luminance(ASYMPTOTIC_COLOR)
        assert blue == pytest.approx(0.188, abs=0.0005)
        assert orange == pytest.approx(0.278, abs=0.0005)
        assert orange - blue < 0.1


class TestTheVocabulary:
    def test_the_asymptotic_label_says_not_certified(self) -> None:
        assert ASYMPTOTIC_LABEL == "asymptotic (not certified)"

    def test_the_finite_label(self) -> None:
        assert FINITE_LABEL == "finite key"

    def test_the_hatch_is_a_real_hatch(self) -> None:
        assert ASYMPTOTIC_HATCH
        assert set(ASYMPTOTIC_HATCH) <= set("/\\|-+xoO.*")


class TestNoGlobalPlottingState:
    @pytest.mark.parametrize("name", ["style.py", "plots.py", "figures.py", "__init__.py"])
    def test_no_pyplot(self, name: str) -> None:
        tree = ast.parse((VIZ_SOURCE / name).read_text(encoding="utf-8"))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
                imported.extend(f"{node.module}.{a.name}" for a in node.names)
            elif isinstance(node, ast.Import):
                imported.extend(a.name for a in node.names)
        assert not [m for m in imported if "pyplot" in m]

    @pytest.mark.parametrize("name", ["style.py", "plots.py", "figures.py"])
    def test_no_io_import(self, name: str) -> None:
        """``io/`` stays unimported by viz (BRIEF wave 2): data arrives in the result."""
        source = (VIZ_SOURCE / name).read_text(encoding="utf-8")
        assert "quoss.io" not in source
