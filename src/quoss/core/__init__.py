"""Core vocabulary: constants, units, types, errors, randomness, logging.

Everything else in QuOSS imports from here, and this package imports from
nothing but the standard library, numpy and scipy. That asymmetry is the
foundation of the dependency rule ``core <- physics <- system <- engine <-
{cli, api, viz}``.

Deliberately no re-exports. Import from the module that owns the name::

    from quoss.core.constants import EGM96_MU_KM3_S2
    from quoss.core.units import deg_to_rad, loss_db_to_transmittance
    from quoss.core.types import FloatArray, TimeGrid
    from quoss.core.errors import DegradationLog, DomainError
    from quoss.core.rng import RandomSource
    from quoss.core.logging import get_logger

Two import paths for one name means grep gives an incomplete answer, and the
audits this project relies on — where is a conversion done, who records a
degradation — are grep-shaped.

Modules
-------
constants
    Physical, geodetic and time constants, each with its source.
units
    The unit convention and the only sanctioned conversion helpers.
types
    Array aliases and the :class:`~quoss.core.types.TimeGrid` time axis.
errors
    Exception hierarchy and the explicit-degradation mechanism.
rng
    The single injectable random source, with reproducible parallel streams.
logging
    Structured logging for run diagnostics, never for physics validity.
"""

from __future__ import annotations

__all__: list[str] = []
