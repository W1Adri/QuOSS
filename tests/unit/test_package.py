"""Smoke tests: the package imports and reports a sane version."""

import re

import quoss

SEMVER = re.compile(r"^\d+\.\d+\.\d+")


def test_package_imports() -> None:
    assert quoss is not None


def test_version_is_semver() -> None:
    assert SEMVER.match(quoss.__version__), quoss.__version__


def test_installed_metadata_matches_module_version() -> None:
    from importlib.metadata import version

    assert version("quoss") == quoss.__version__


def test_core_dependencies_are_importable() -> None:
    import numpy
    import pydantic
    import scipy

    assert numpy.__version__
    assert scipy.__version__
    assert pydantic.VERSION
