"""Architecture and convention guards.

The units decision and the dependency rule are only worth anything if they are
*enforced*. A convention that lives in a document erodes one pull request at a
time; these tests turn it into a property CI checks.

They are deliberately cheap and syntactic — an AST scan over ``src/quoss``, no
imports, no physics. Right now most of them pass trivially because the physics
modules do not exist yet. That is the point: they are being written *before* the
30 modules of stage 2, when retrofitting them would mean auditing all 30 by hand.

Each guard carries an allowlist. When a new legitimate exception appears, the
right move is to add it there with a comment saying why — that turns a silent
drift into a reviewed decision.
"""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "quoss"

# --------------------------------------------------------------------------- #
# Where conversions are allowed to live
# --------------------------------------------------------------------------- #
CONVERSION_ALLOWLIST = frozenset(
    {
        # Defines the conversions. Obviously allowed to perform them.
        "core/units.py",
        # The user-facing frontier: degrees and decibels are translated here.
        # (Created in stage 4; listed now so the rule is complete from the start.)
        "scenario/io.py",
    }
)

# numpy angle helpers. Their presence outside the allowlist means someone
# converted an angle inline instead of at the boundary.
ANGLE_CONVERTERS = frozenset({"deg2rad", "rad2deg", "degrees", "radians"})


def _python_files() -> list[Path]:
    """Return every Python file under src/quoss, excluding caches."""
    return sorted(p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts)


def _relative(path: Path) -> str:
    """Return a path relative to the package root, with forward slashes."""
    return path.relative_to(SRC).as_posix()


def _parse(path: Path) -> ast.Module:
    """Parse a source file into an AST."""
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.Module) -> list[tuple[int, str]]:
    """Return ``(lineno, module_name)`` for every import in a parsed module.

    Flattens ``import a.b`` and ``from a.b import c`` into the same shape, so the
    dependency guards only have to reason about the module being reached for.
    """
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                found.append((node.lineno, node.module))
        elif isinstance(node, ast.Import):
            found.extend((node.lineno, alias.name) for alias in node.names)
    return found


def test_there_are_files_to_check() -> None:
    """Guard against the guards silently passing because the glob broke."""
    assert len(_python_files()) >= 7


class TestUnitConventionIsEnforced:
    """Conversions happen at the boundary, not scattered through the physics."""

    def test_angle_conversion_only_at_the_boundary(self) -> None:
        """np.deg2rad outside units.py and scenario/io.py means degrees leaked in.

        The canonical internal angle is the radian. A ``deg2rad`` in the middle of
        a channel model is evidence that a caller passed degrees, which is the
        failure mode the suffix convention exists to prevent.
        """
        offenders: list[str] = []
        for path in _python_files():
            rel = _relative(path)
            if rel in CONVERSION_ALLOWLIST:
                continue
            for node in ast.walk(_parse(path)):
                if isinstance(node, ast.Attribute) and node.attr in ANGLE_CONVERTERS:
                    offenders.append(f"{rel}:{node.lineno} uses np.{node.attr}")
        assert not offenders, (
            "Angle conversion outside the boundary:\n  "
            + "\n  ".join(offenders)
            + f"\nConvert in one of {sorted(CONVERSION_ALLOWLIST)}, or import the "
            "helper from quoss.core.units."
        )

    def test_no_hardcoded_kilometre_scale_factors(self) -> None:
        """A bare 1e3 crossing km<->m must go through km_to_m/m_to_km instead.

        This is the one internal unit boundary in the project, so it is the place
        a stray factor is most likely to appear and least likely to be noticed.
        Naming it makes every crossing greppable.
        """
        offenders: list[str] = []
        for path in _python_files():
            rel = _relative(path)
            if rel in CONVERSION_ALLOWLIST:
                continue
            for node in ast.walk(_parse(path)):
                if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Mult | ast.Div):
                    continue
                for side in (node.left, node.right):
                    if (
                        isinstance(side, ast.Constant)
                        and isinstance(side.value, float)
                        and side.value in (1e3, 1e-3)
                    ):
                        offenders.append(f"{rel}:{node.lineno} scales by {side.value!r}")
        assert not offenders, (
            "Hardcoded km<->m factor:\n  "
            + "\n  ".join(offenders)
            + "\nUse quoss.core.units.km_to_m / m_to_km so the boundary is auditable."
        )

    def test_no_hardcoded_speed_of_light(self) -> None:
        """A literal 3e8 is both imprecise and unsearchable. constants.py exists for it."""
        offenders: list[str] = []
        approximations = {3e8, 2.998e8, 2.9979e8, 299792458.0}
        for path in _python_files():
            rel = _relative(path)
            if rel == "core/constants.py":
                continue
            for node in ast.walk(_parse(path)):
                if (
                    isinstance(node, ast.Constant)
                    and isinstance(node.value, float | int)
                    and not isinstance(node.value, bool)
                    and float(node.value) in approximations
                ):
                    offenders.append(f"{rel}:{node.lineno}")
        assert not offenders, (
            "Hardcoded speed of light at:\n  "
            + "\n  ".join(offenders)
            + "\nImport SPEED_OF_LIGHT_M_S from quoss.core.constants."
        )


class TestDependencyRule:
    """Enforces ``core <- physics <- system <- engine <- {cli, api, viz}``.

    A lightweight stand-in for import-linter, using only the standard library so
    the guard has no dependency of its own. Layer-by-layer rather than
    module-by-module, which is the granularity the design document states.
    """

    # Lower index = deeper layer. A module may import its own layer or deeper.
    LAYERS = (
        ("core",),
        ("orbits", "channel", "qkd"),
        ("system",),
        ("scenario",),
        ("engine",),
        ("cli", "api", "viz"),
    )
    # Consumed by injection, so they sit outside the ladder and may be reached
    # from anywhere that receives them as an argument.
    INJECTED = frozenset({"kernels", "io"})

    def _layer_of(self, package: str) -> int | None:
        for index, names in enumerate(self.LAYERS):
            if package in names:
                return index
        return None

    def test_no_import_points_the_wrong_way(self) -> None:
        offenders: list[str] = []
        for path in _python_files():
            rel = _relative(path)
            own_layer = self._layer_of(rel.split("/")[0])
            if own_layer is None:
                continue
            for lineno, name in _imports(_parse(path)):
                parts = name.split(".")
                if len(parts) < 2 or parts[0] != "quoss":
                    continue
                target = parts[1]
                if target in self.INJECTED:
                    continue
                target_layer = self._layer_of(target)
                if target_layer is not None and target_layer > own_layer:
                    offenders.append(
                        f"{rel}:{lineno} imports quoss.{target} "
                        f"(layer {target_layer}) from layer {own_layer}"
                    )
        assert not offenders, "Dependency rule violated:\n  " + "\n  ".join(offenders)

    def test_core_imports_nothing_from_quoss_but_core(self) -> None:
        """The foundation of the whole rule, worth asserting on its own."""
        offenders = [
            f"{_relative(path)}:{lineno} imports {name}"
            for path in _python_files()
            if _relative(path).startswith("core/")
            for lineno, name in _imports(_parse(path))
            if name.startswith("quoss.") and not name.startswith("quoss.core")
        ]
        assert not offenders, "core/ reached outside itself:\n  " + "\n  ".join(offenders)

    def test_no_module_outside_api_imports_a_web_framework(self) -> None:
        """Nothing outside api/ may import FastAPI. The core installs without it."""
        forbidden = {"fastapi", "starlette", "uvicorn", "pydantic_settings"}
        offenders = [
            f"{_relative(path)}:{lineno} imports {name}"
            for path in _python_files()
            if not _relative(path).startswith("api/")
            for lineno, name in _imports(_parse(path))
            if name.split(".")[0] in forbidden
        ]
        assert not offenders, "Web dependency in the core:\n  " + "\n  ".join(offenders)


class TestNoSilentDegradation:
    """Makes the "never degrade the physics in silence" rule checkable."""

    PHYSICS_PACKAGES = ("orbits", "channel", "qkd", "system")

    def test_no_bare_or_broad_except_in_the_physics_layer(self) -> None:
        """A bare ``except:`` or ``except Exception:`` is how a wrong number gets in.

        The diagnosis of SimulCTTC named this exactly: an ``except`` that returned
        "no scintillation" without saying so. In QuOSS a physics module must either
        re-raise as a QuossError or record a Degradation. Catching a *specific*
        exception and doing one of those two things is fine, which is why only the
        broad forms are flagged.
        """
        offenders: list[str] = []
        for path in _python_files():
            rel = _relative(path)
            if not rel.startswith(self.PHYSICS_PACKAGES):
                continue
            for node in ast.walk(_parse(path)):
                if not isinstance(node, ast.ExceptHandler):
                    continue
                if node.type is None:
                    offenders.append(f"{rel}:{node.lineno} bare except")
                elif isinstance(node.type, ast.Name) and node.type.id in (
                    "Exception",
                    "BaseException",
                ):
                    offenders.append(f"{rel}:{node.lineno} except {node.type.id}")
        assert not offenders, (
            "Broad exception handler in the physics layer:\n  "
            + "\n  ".join(offenders)
            + "\nCatch the specific exception, then re-raise as a QuossError or "
            "record it in a DegradationLog."
        )


class TestDocstringDiscipline:
    """The docstrings are the physics manual, so they cannot be optional."""

    def test_every_module_has_a_docstring(self) -> None:
        missing = [_relative(p) for p in _python_files() if ast.get_docstring(_parse(p)) is None]
        assert not missing, f"Modules without a docstring: {missing}"

    @pytest.mark.parametrize("module", ["core/units.py", "core/constants.py", "core/errors.py"])
    def test_key_modules_document_their_rationale_at_length(self, module: str) -> None:
        """These three encode decisions, not just code, so a one-liner is not enough.

        Judged by length rather than content, which is crude, but it does stop the
        module docstring being trimmed to "Units." during a refactor.
        """
        docstring = ast.get_docstring(_parse(SRC / module))
        assert docstring is not None
        assert len(docstring) > 500, f"{module} docstring is too short to explain why"
