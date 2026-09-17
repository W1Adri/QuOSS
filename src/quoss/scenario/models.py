"""The scenario schema: every input a simulation takes, as a validated datum.

What a scenario is, for someone arriving new
--------------------------------------------
A *scenario* is the complete description of one simulation run — which
satellite, which ground stations, what telescope and detector, which QKD
protocol at what intensities, over which day and at what time step. Nothing
about the run lives anywhere else: hand the same scenario to the engine twice
and it produces the same numbers (with the same seed), hand it to somebody else
and they reproduce your figure. It is written as a YAML or JSON file, and this
module is the contract that file has to satisfy.

That contract is the single most consequential file in the project, because it
decides what a user *can* say. A parameter the physics takes but the schema
cannot express is a parameter every user silently gets at its default; a
parameter the schema accepts but never validates is a plausible wrong number
waiting to happen. So the schema here expresses every knob the physics layer
exposes (``notes/ROADMAP.md`` stage 4: "ya sabes exactamente qué parámetros
existen"), and validates each against the same domain the physics enforces, so
that a scenario that validates always converts.

Why a datum and not a request
-----------------------------
The previous code base (SimulCTTC) took its inputs as the arguments of an HTTP
handler: a request, assembled at call time, with defaults filled in wherever
the caller was silent. Two things went wrong with that, and both are recorded
in ``notes/ROADMAP.md``. First, defaults are invisible: an epoch the caller did
not set "fell silently to the wall clock", so the same request run on two days
described two different skies. Second, a request cannot be hashed, versioned or
diffed, so nothing tied a figure to the inputs that produced it. A scenario is
the opposite: a complete, frozen, hashable value. It is *data*. The
:mod:`quoss.scenario.hash` module turns it into a cache key and a provenance
record, and :mod:`quoss.scenario.io` turns it into a file that can be committed
next to the figure it made.

Units at the boundary, and why the conversion happens here exactly once
------------------------------------------------------------------------
``docs/adr/0001-unit-conventions.md`` fixes radians, metres and linear
transmittance inside the physics, with degrees, nanometres and decibels allowed
**only at the user boundary**. This module is that boundary. Every field name
carries the user's unit — ``latitude_deg``, ``wavelength_nm``,
``pointing_jitter_urad``, ``gate_ns`` — and each model offers the converted
value under the physics name — :attr:`StationSpec.latitude_rad`,
:attr:`TransmitterSpec.wavelength_m`, :attr:`ReceiverSpec.gate_s`. The engine
calls those and never converts on its own, so there is exactly one place where
a degree becomes a radian and the AST guard in
``tests/unit/test_conventions.py`` can check that no other place does.

The converters are plain properties and methods, not Pydantic
``computed_field``s, and that is not a style choice: a computed field is
included by ``model_dump``, so a file written by :func:`~quoss.scenario.io.dump_scenario`
would carry ``latitude_rad`` next to ``latitude_deg``, and reading it back under
``extra="forbid"`` would then fail on its own output. Round-trip safety wins.

Four fields have no default, on purpose
---------------------------------------
Every other field with a defensible published value carries it as a default.
Four do not, and they are a test (``tests/scenario/test_models.py::
TestTheFieldsWithoutADefault``) so that adding one is a visible decision:

* **Extinction, declared one of two ways and never neither.**
  :attr:`ChannelSpec.zenith_transmittance` is the atmosphere's vertical
  clear-sky transmittance as a number, and :attr:`ChannelSpec.extinction` is the
  same thing as a model. ``docs/adr/0009-citation-policy.md`` gap 14: Ntanos et
  al. 2021 Eq. (7) publishes the scaling law and no openable source publishes
  the number it scales, so a default on either would be an invented number made
  authoritative by its position. The physics function
  :func:`quoss.channel.link_budget.atmospheric_transmittance` refuses a default
  for the same reason, and this schema mirrors it: whoever has no extinction
  writes ``zenith_transmittance: 1.0`` and has thereby declared it. See
  ``docs/adr/0023-traceable-extinction.md`` for what the model added and what it
  left open.
* :attr:`ExtinctionSpec.aerosol_scale_height_m` and
  :attr:`ExtinctionSpec.scaling_law`, inside that model, for reasons of their
  own: no openable source publishes a scale height (gap 22), and the two
  published wavelength exponents are 43 dB per kilometre apart in fog.
* :attr:`PassSpec.minimum_elevation_deg` — the elevation mask. ``docs/adr/0011-the-block-is-the-pass.md``
  §5 measured that the finite-key yield has an **interior optimum near 8°**
  (lowering the mask from 8° to 2° buys 71 % more seconds and destroys 6.0 % of
  the day's key). A quantity with an optimum is a design variable, not a
  constant, and a default would hide a 6 % effect behind a citation.

What this module deliberately does not do
-----------------------------------------
It does not compute anything physical. Conversion, yes; a loss budget, no.
It imports from ``core``, ``orbits``, ``channel`` and ``qkd`` only — never from
``system`` or ``engine`` — because the dependency ladder of
``notes/GUIA_REIMPLEMENTACION.md`` puts ``scenario`` above the physics and below
the engine, and a schema that imported the pipeline would be a schema the
pipeline could not import.

Examples
--------
The reference scenario of this project, built from the named defaults, converts
into exactly the physics inputs the ``tests/system`` reference link uses:

>>> from quoss.scenario.defaults import reference_castelldefels
>>> scenario = reference_castelldefels()
>>> scenario.stations[0].name
'castelldefels'
>>> round(scenario.transmitter.wavelength_m * 1e9)
1550
>>> scenario.time.epoch_jd
2460676.5
>>> scenario.time.grid().n
86401
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from itertools import pairwise
from typing import Annotated, Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)
from sgp4.api import Satrec

from quoss.channel.atmosphere import ITU_GROUND_CN2_M23
from quoss.channel.background import (
    ITU_SKY_RADIANCE_WAVELENGTHS_M,
    SkyCondition,
    interpolated_sky_radiance_w_m2_um_sr,
)
from quoss.channel.detector import receiver_efficiency
from quoss.channel.extinction import (
    VisibilityScalingLaw,
    specific_attenuation_at_altitude_db_per_km,
    zenith_transmittance_from_visibility,
)
from quoss.channel.link_budget import FadeCombination
from quoss.channel.turbulence import PathWave, ScintillationRegime
from quoss.core.constants import WGS84_RADIUS_EQUATORIAL_KM
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import TimeGrid
from quoss.core.units import deg_to_rad, m_to_km, nm_to_m
from quoss.orbits.constellations import sun_synchronous_inclination_rad
from quoss.orbits.frames import calendar_to_jd
from quoss.orbits.kepler import ClassicalElements
from quoss.orbits.propagator import PropagationMethod
from quoss.orbits.tle import parse_tle, tle_epoch_jd
from quoss.qkd.base import PROTOCOLS
from quoss.qkd.bb84 import Bb84DecoyProtocol
from quoss.qkd.finite_key import SecurityParameters

__all__ = [
    "HV57_RMS_WIND_SPEED_M_S",
    "SCHEMA_VERSION",
    "AggregationPolicyName",
    "AnyScenario",
    "BackgroundSpec",
    "ChannelSpec",
    "ExtinctionSpec",
    "HorizontalPathSpec",
    "HorizontalScenario",
    "KeplerOrbit",
    "LinkKind",
    "MonteCarloSpec",
    "MultiStationSpec",
    "OrbitSpec",
    "PassSpec",
    "ProtocolSpec",
    "ReceiverSpec",
    "RelaySpec",
    "Scenario",
    "SecuritySpec",
    "SessionSpec",
    "SpecModel",
    "StationSpec",
    "TimeSpec",
    "TleOrbit",
    "TransmitterSpec",
]

SCHEMA_VERSION: int = 1
"""The scenario schema version this code reads and writes.

A file states its version in ``schema_version`` and is refused if it does not
match, rather than being read under whatever field meanings this version
happens to have. Bumped when a field changes meaning or unit; adding an
optional field with a default does not bump it.
"""

_RAD_PER_URAD = 1e-6
_S_PER_NS = 1e-9
_S_PER_PS = 1e-12
_MICROSECONDS_PER_SECOND = 1e6
_MAX_SEED = 2**64
"""Same reduction as :mod:`quoss.core.rng`: seeds must round-trip through YAML."""

_PROBABILITY_SUM_SLACK = 1e-9
"""Mirrors the slack :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` allows on the sum.

Three probabilities written as decimals — ``16/21``, ``1/21``, ``4/21`` — cannot
sum to exactly one in binary; this is the float-error allowance, not a physics
tolerance, and it is the same number the protocol uses so that a scenario that
validates here cannot be refused there.
"""

_GRID_STEP_SLACK = 1e-9
"""Mirrors :meth:`quoss.core.types.TimeGrid.uniform`'s whole-multiple rule."""

HV57_RMS_WIND_SPEED_M_S = 21.0
"""The Hufnagel-Valley 5/7 r.m.s. wind, m/s: the default of every turbulence function.

Kept as a literal here because it is what the physics defaults to and what the
reference link uses; ``tests/scenario/test_models.py`` asserts it equals the
default of :func:`quoss.channel.turbulence.log_irradiance_variance`.
"""


class SpecModel(BaseModel):
    """Base of every scenario model: closed, frozen, and finite.

    ``extra="forbid"`` because a misspelled key (``wavelenght_nm``) that is
    silently ignored leaves the field at its default, which is the exact
    "plausible wrong number" failure the project exists to refuse.
    ``frozen=True`` because a scenario is a datum: its hash is its identity,
    and an editable scenario is one whose hash lies. ``allow_inf_nan=False``
    because no field here has a physical meaning at infinity, and a NaN would
    pass every ``gt``/``lt`` bound (comparisons with NaN are false) and then
    poison every array downstream.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


# --------------------------------------------------------------------------- #
# Orbit
# --------------------------------------------------------------------------- #
class KeplerOrbit(SpecModel):
    """An orbit declared by its classical elements at the scenario epoch.

    The elements are **osculating at the epoch** and are propagated by
    :func:`quoss.orbits.propagator.propagate` with the method named here. The
    altitude is the mean altitude over the WGS-84 equatorial radius, so the
    semi-major axis is ``6378.137 km + altitude_km``, which is the convention of
    the project's reference link (``tests/system/reference.py``).

    Exactly one of ``inclination_deg`` or ``sun_synchronous=True`` must be
    given. A sun-synchronous orbit is one whose plane turns with the Sun (one
    revolution per year) because the Earth's equatorial bulge drags the node;
    that fixes the inclination as a function of altitude and eccentricity
    (:func:`quoss.orbits.constellations.sun_synchronous_inclination_rad`), so
    asking for both an inclination and sun-synchronism is asking for two
    inclinations.

    Examples
    --------
    >>> orbit = KeplerOrbit(
    ...     altitude_km=700.0, eccentricity=0.001, sun_synchronous=True, raan_deg=30.0
    ... )
    >>> round(orbit.semi_major_axis_km, 3)
    7078.137
    >>> round(orbit.inclination_rad, 6)
    1.713703
    >>> bool(orbit.to_elements().is_circular)
    False
    """

    altitude_km: float = Field(
        gt=0.0,
        description="Mean altitude above the WGS-84 equatorial radius, km. "
        "Semi-major axis is 6378.137 km plus this.",
    )
    eccentricity: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Orbital eccentricity, dimensionless. Zero is circular; the periapsis "
        "must stay above the Earth's surface, checked against altitude_km.",
    )
    inclination_deg: float | None = Field(
        default=None,
        ge=0.0,
        le=180.0,
        description="Inclination in degrees, or null when sun_synchronous is true.",
    )
    sun_synchronous: bool = Field(
        default=False,
        description="Derive the inclination that makes the node precess once per year at "
        "this altitude and eccentricity. Mutually exclusive with inclination_deg.",
    )
    raan_deg: float = Field(
        ge=0.0,
        lt=360.0,
        description="Right ascension of the ascending node at the epoch, degrees, in the "
        "TEME frame. No default: it fixes when the plane passes over a station.",
    )
    argp_deg: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="Argument of periapsis at the epoch, degrees.",
    )
    true_anomaly_deg: float = Field(
        default=0.0,
        ge=0.0,
        lt=360.0,
        description="True anomaly at the epoch, degrees: where on the ellipse the satellite "
        "is at t = 0.",
    )
    method: Literal["two_body", "zonal_numeric"] = Field(
        default="two_body",
        description="Propagation model. 'two_body' is the unperturbed ellipse; "
        "'zonal_numeric' integrates J2-J4 numerically. SGP4 is only reachable "
        "through a TLE, because it takes mean elements this model does not have.",
    )

    @model_validator(mode="after")
    def _one_inclination(self) -> KeplerOrbit:
        """Exactly one source of inclination, and a periapsis above the ground."""
        if (self.inclination_deg is None) == (not self.sun_synchronous):
            raise ValueError(
                "give exactly one of inclination_deg or sun_synchronous=true. They are two "
                "ways of fixing the same angle: a sun-synchronous orbit at a given altitude "
                "has one inclination and no other."
            )
        limit = self.altitude_km / (WGS84_RADIUS_EQUATORIAL_KM + self.altitude_km)
        if self.eccentricity >= limit:
            raise ValueError(
                f"eccentricity={self.eccentricity} puts the periapsis below the Earth's "
                f"equatorial radius: at altitude_km={self.altitude_km} the periapsis stays "
                f"above ground only for eccentricity < {limit:.6f}."
            )
        if self.sun_synchronous:
            try:
                sun_synchronous_inclination_rad(
                    semi_major_axis_km=self.semi_major_axis_km, eccentricity=self.eccentricity
                )
            except DomainError as error:
                raise ValueError(str(error)) from error
        return self

    @property
    def semi_major_axis_km(self) -> float:
        """Semi-major axis, km: the WGS-84 equatorial radius plus the altitude."""
        return WGS84_RADIUS_EQUATORIAL_KM + self.altitude_km

    @property
    def inclination_rad(self) -> float:
        """Inclination in radians, derived when the orbit is sun-synchronous."""
        if self.inclination_deg is not None:
            return float(deg_to_rad(self.inclination_deg))
        derived = sun_synchronous_inclination_rad(
            semi_major_axis_km=self.semi_major_axis_km, eccentricity=self.eccentricity
        )
        return float(derived.reshape(-1)[0])

    @property
    def raan_rad(self) -> float:
        """Right ascension of the ascending node, radians."""
        return float(deg_to_rad(self.raan_deg))

    @property
    def argp_rad(self) -> float:
        """Argument of periapsis, radians."""
        return float(deg_to_rad(self.argp_deg))

    @property
    def true_anomaly_rad(self) -> float:
        """True anomaly at the epoch, radians."""
        return float(deg_to_rad(self.true_anomaly_deg))

    @property
    def propagation_method(self) -> PropagationMethod:
        """The :class:`~quoss.orbits.propagator.PropagationMethod` member named by ``method``."""
        return PropagationMethod(self.method)

    def to_elements(self) -> ClassicalElements:
        """Return the osculating :class:`~quoss.orbits.kepler.ClassicalElements` at the epoch.

        This is the one call through which a Kepler scenario enters the
        physics; every angle leaves here in radians.
        """
        return ClassicalElements.from_semi_major_axis(
            semi_major_axis_km=self.semi_major_axis_km,
            eccentricity=self.eccentricity,
            inclination_rad=self.inclination_rad,
            raan_rad=self.raan_rad,
            argp_rad=self.argp_rad,
            true_anomaly_rad=self.true_anomaly_rad,
        )


class TleOrbit(SpecModel):
    """An orbit declared by a two-line element set, propagated with SGP4.

    The two lines are validated at construction with
    :func:`quoss.orbits.tle.parse_tle`, which checks what the ``sgp4`` package
    does not: line length, line number, checksum, and the record's own error
    flag. A TLE carries its own epoch; the scenario's :class:`TimeSpec` still
    fixes the *window*, and the engine offsets the window from the TLE epoch
    (:func:`quoss.orbits.tle.propagate_tle` takes seconds from the TLE epoch,
    never from any other one — see that module's "The epoch is not a parameter").

    Examples
    --------
    >>> orbit = TleOrbit(
    ...     line1="1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996",
    ...     line2="2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781",
    ... )
    >>> orbit.to_satrec().satnum
    25544
    >>> round(orbit.epoch_jd, 5)
    2458878.41701
    """

    line1: str = Field(description="TLE line 1, 69 columns, checksum in column 69.")
    line2: str = Field(description="TLE line 2, 69 columns, checksum in column 69.")
    name: str | None = Field(
        default=None,
        description="Optional object name (the 'line 0' of a three-line set). Informational.",
    )

    @model_validator(mode="after")
    def _parses(self) -> TleOrbit:
        """Refuse at validation what SGP4 would refuse at propagation."""
        try:
            parse_tle(self.line1, self.line2)
        except DomainError as error:
            raise ValueError(str(error)) from error
        return self

    def to_satrec(self) -> Satrec:
        """Return the parsed ``sgp4`` record, initialised against WGS-72."""
        return parse_tle(self.line1, self.line2)

    @property
    def epoch_jd(self) -> float:
        """The TLE's own epoch as a Julian date (UTC)."""
        return tle_epoch_jd(self.to_satrec())


class OrbitSpec(SpecModel):
    """Exactly one of a Kepler orbit or a TLE.

    Two keys rather than a tagged union so that a file reads as ``orbit:
    kepler: ...`` or ``orbit: tle: ...`` and a reader knows the propagator from
    the key alone.

    Examples
    --------
    >>> OrbitSpec(kepler=KeplerOrbit(altitude_km=600.0, inclination_deg=97.4, raan_deg=0.0)).is_tle
    False
    """

    kepler: KeplerOrbit | None = Field(default=None, description="Classical elements at the epoch.")
    tle: TleOrbit | None = Field(default=None, description="Two-line element set for SGP4.")

    @model_validator(mode="after")
    def _exactly_one(self) -> OrbitSpec:
        """One orbit, one propagator."""
        if (self.kepler is None) == (self.tle is None):
            raise ValueError(
                "give exactly one of kepler or tle. They are propagated by different models "
                "(analytic/numeric on osculating elements versus SGP4 on TLE mean elements) "
                "and cannot describe the same satellite twice."
            )
        return self

    @property
    def is_tle(self) -> bool:
        """True when the orbit is a TLE."""
        return self.tle is not None


# --------------------------------------------------------------------------- #
# Ground segment
# --------------------------------------------------------------------------- #
class StationSpec(SpecModel):
    """One optical ground station: where it is, and what its site is like.

    The turbulence defaults are the HV 5/7 reference site the physics
    functions default to: ``ground_cn2_m23 = 1.7e-14`` (ITU-R P.1621-2 Eq. (6))
    and ``rms_wind_speed_m_s = 21.0``. The r.m.s. wind is the parameter the
    turbulence functions take, and it is carried as such rather than derived
    from a ground wind through the Bufton profile: ITU-R P.1621-2 Eq. (5) turns
    the 2.3 m/s ground wind into **21.018** m/s, not 21.0, and the 0.085 %
    difference moved the reference loss budget by 6.8e-5 relative (0.0028 dB
    at 10 deg, ``tests/scenario/test_models.py::TestUnitsConvertOnceAtTheBoundary::
    test_the_wind_default_is_the_hv57_value_not_the_bufton_conversion``) — enough
    to make the reference scenario fail to reproduce the reference link exactly.
    Whoever has a ground wind converts it with
    :func:`quoss.channel.atmosphere.bufton_rms_wind_speed_m_s` and writes the
    result here. ``cloud_fraction`` is the site's mean cloud cover for the
    pCFLOS model, ``null`` when clouds are not modelled.

    Examples
    --------
    >>> station = StationSpec(
    ...     name="castelldefels",
    ...     latitude_deg=41.2750,
    ...     longitude_deg=1.9875,
    ...     altitude_m=30.0,
    ...     receive_aperture_m=0.75,
    ... )
    >>> round(station.latitude_rad, 6)
    0.720385
    >>> station.altitude_km
    0.03
    >>> station.rms_wind_speed_m_s
    21.0
    """

    name: str = Field(min_length=1, description="Unique identifier within the scenario.")
    latitude_deg: float = Field(ge=-90.0, le=90.0, description="Geodetic latitude, degrees north.")
    longitude_deg: float = Field(
        ge=-180.0, le=180.0, description="Longitude, degrees east (negative west)."
    )
    altitude_m: float = Field(
        ge=-500.0,
        le=9000.0,
        description="Height above the WGS-84 ellipsoid, metres. Also the station height the "
        "turbulence profile starts from.",
    )
    receive_aperture_m: float = Field(gt=0.0, description="Receiver telescope diameter, m.")
    ground_cn2_m23: float = Field(
        default=ITU_GROUND_CN2_M23,
        gt=0.0,
        description="Refractive-index structure constant at the ground, m^(-2/3). Default is "
        "ITU-R P.1621-2 Eq. (6)'s 1.7e-14.",
    )
    rms_wind_speed_m_s: float = Field(
        default=HV57_RMS_WIND_SPEED_M_S,
        gt=0.0,
        description="R.m.s. wind speed of the Bufton profile, m/s, as the turbulence functions "
        "take it. Default 21.0 is the HV 5/7 value. A ground wind is converted with "
        "quoss.channel.atmosphere.bufton_rms_wind_speed_m_s (2.3 m/s gives 21.018).",
    )
    cloud_fraction: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Mean cloud cover fraction of the site, or null when clouds are not "
        "modelled. Used by the pCFLOS availability model only.",
    )

    @property
    def latitude_rad(self) -> float:
        """Geodetic latitude, radians."""
        return float(deg_to_rad(self.latitude_deg))

    @property
    def longitude_rad(self) -> float:
        """Longitude, radians east."""
        return float(deg_to_rad(self.longitude_deg))

    @property
    def altitude_km(self) -> float:
        """Height above the ellipsoid, km — the unit :func:`quoss.orbits.geometry.look_angles` takes."""
        return float(m_to_km(self.altitude_m))

    @property
    def station_height_m(self) -> float:
        """Height above the ellipsoid, m — the unit the turbulence functions take."""
        return self.altitude_m


# --------------------------------------------------------------------------- #
# Optical chain
# --------------------------------------------------------------------------- #
class TransmitterSpec(SpecModel):
    """The satellite's optical source and telescope.

    ``truncation_ratio`` is the aperture radius over the Gaussian beam waist,
    ``alpha`` of ``docs/adr/0009-citation-policy.md`` gap 15; ``1.0`` is the
    only value consistent with the beam radii :mod:`quoss.channel.beam`
    computes, and the loss it implies (3.35 dB) is applied by the link budget.

    Examples
    --------
    >>> tx = TransmitterSpec(
    ...     wavelength_nm=1550.0, aperture_m=0.15, pointing_jitter_urad=0.75, pulse_rate_hz=100e6
    ... )
    >>> tx.wavelength_m
    1.55e-06
    >>> tx.pointing_jitter_rad
    7.5e-07
    >>> tx.pulse_period_s
    1e-08
    """

    wavelength_nm: float = Field(gt=0.0, description="Source wavelength, nm.")
    aperture_m: float = Field(gt=0.0, description="Transmit telescope diameter, m.")
    truncation_ratio: float = Field(
        default=1.0,
        gt=0.0,
        description="Aperture radius over beam waist (alpha). 1.0 matches the beam module's "
        "convention; larger values mean a beam expander that under-fills the aperture.",
    )
    pointing_jitter_urad: float = Field(
        ge=0.0, description="R.m.s. pointing error per axis, microradians."
    )
    pulse_rate_hz: float = Field(gt=0.0, description="Source repetition rate, Hz.")

    @property
    def wavelength_m(self) -> float:
        """Wavelength, m."""
        return float(nm_to_m(self.wavelength_nm))

    @property
    def pointing_jitter_rad(self) -> float:
        """R.m.s. pointing error per axis, rad."""
        return self.pointing_jitter_urad * _RAD_PER_URAD

    @property
    def pulse_period_s(self) -> float:
        """Time between pulses, s: the widest a detection gate can be."""
        return 1.0 / self.pulse_rate_hz


class ExtinctionSpec(SpecModel):
    """Atmospheric extinction as a model instead of a number.

    The other way of declaring :attr:`ChannelSpec.zenith_transmittance`, and the
    one that can be traced: visibility, an aerosol scale height and a published
    scaling law, turned into a vertical transmittance by
    :func:`quoss.channel.extinction.zenith_transmittance_from_visibility`. See
    ``docs/adr/0023-traceable-extinction.md``, and the module docstring of
    :mod:`quoss.channel.extinction` for what the model covers (aerosol
    scattering) and what it does not (molecular absorption, gap 23).

    **Two fields here have no default and both are unusual enough to say why.**
    ``aerosol_scale_height_m`` has none because no openable source publishes one
    for a generic site and the values in use span 1.2 to 2 km, a factor 1.67 in
    optical depth (ADR 0009 gap 22). ``scaling_law`` has none because the two
    published exponents are different physics in fog -- 43 dB over a kilometre
    apart at 1550 nm -- and which is right is a hardware decision, not a
    preference.

    ``visibility_altitude_m`` is the altitude the visibility describes, and it is
    separate from the station's because nothing in a visibility figure says
    which it is. Set it to the station's altitude for a locally measured
    visibility, in which case the altitude cancels exactly; set it to 0.0 for a
    sea-level climatological figure, in which case a station at 2390 m keeps
    only ``exp(-2390/H)`` of the aerosol column -- 0.031 dB instead of 0.230 at
    23 km of visibility, 1550 nm and 1.2 km of scale height.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> spec = ExtinctionSpec(
    ...     visibility_km=23.0,
    ...     visibility_altitude_m=30.0,
    ...     aerosol_scale_height_m=1200.0,
    ...     scaling_law="kim-2001",
    ... )
    >>> round(
    ...     spec.zenith_transmittance(
    ...         wavelength_m=1.55e-6, station_altitude_m=30.0, degradations=DegradationLog()
    ...     ),
    ...     5,
    ... )
    0.94833
    """

    visibility_km: float = Field(
        gt=0.0,
        description="Visual range at visibility_altitude_m, km. ITU-R P.1817-1 §12's code "
        "table labels 23 km very clear air, 10 km clear, 2 km light mist and 0.05 km dense fog.",
    )
    visibility_altitude_m: float = Field(
        ge=-500.0,
        le=9000.0,
        description="Altitude the visibility describes, m above the WGS-84 ellipsoid. Equal to "
        "the station's for a locally measured visibility (the altitude then cancels exactly); "
        "0.0 for a sea-level climatological figure.",
    )
    aerosol_scale_height_m: float = Field(
        gt=0.0,
        description="Height over which aerosol extinction falls by a factor e, m. REQUIRED, no "
        "default: no openable source publishes one (ADR 0009 gap 22), and 1.2 to 2 km is a "
        "factor 1.67 in optical depth.",
    )
    scaling_law: VisibilityScalingLaw = Field(
        description="Which published wavelength exponent: 'itu-p1814' (ITU-R P.1814 Eqs. (4)-(5), "
        "which is Kruse's law) or 'kim-2001' (Kim et al. 2001 Eq. (9) below 6 km). REQUIRED, no "
        "default: in fog they differ by 43 dB per kilometre at 1550 nm.",
    )

    def zenith_transmittance(
        self,
        *,
        wavelength_m: float,
        station_altitude_m: float,
        degradations: DegradationLog,
    ) -> float:
        """Resolve ``L_zen`` for one wavelength and one station.

        The conversion from user units to physics units happens here, in the
        schema, as every other conversion in this module does. It needs two
        things that live on other models -- the transmitter's wavelength and the
        station's altitude -- so it is a method taking them rather than a
        property, and the engine is what brings the three together.

        Parameters
        ----------
        wavelength_m : float
            The transmitter wavelength, m.
        station_altitude_m : float
            The station's height above the ellipsoid, m
            (:attr:`StationSpec.altitude_m`).
        degradations : DegradationLog
            Receives the warnings of
            :func:`quoss.channel.extinction.aerosol_specific_attenuation_db_per_km`.

        Returns
        -------
        float
            Vertical transmittance in ``(0, 1]``.
        """
        return float(
            zenith_transmittance_from_visibility(
                self.visibility_km,
                wavelength_m=wavelength_m,
                aerosol_scale_height_m=self.aerosol_scale_height_m,
                station_altitude_m=station_altitude_m,
                visibility_altitude_m=self.visibility_altitude_m,
                law=self.scaling_law,
                degradations=degradations,
            )
        )


class ChannelSpec(SpecModel):
    """The atmospheric and static terms of the downlink budget.

    Extinction is declared **exactly one of two ways, and there is no third**:
    :attr:`zenith_transmittance`, a number the scenario author stands behind, or
    :attr:`extinction`, a model with its inputs. Neither has a default and
    declaring neither is refused, for the reason
    ``docs/adr/0009-citation-policy.md`` gap 14 gives: there is no value of this
    field that can quietly mean "I did not think about it". The two-ways shape
    is :class:`BackgroundSpec`'s, for the same reason -- a value and a model are
    two answers to one question, and taking both would leave a reader guessing
    which one the run used.

    ``outage_probability`` is the quantile at which both fades (pointing and
    scintillation) are budgeted; ``fade_combination`` says whether the two
    quantiles are combined exactly or summed as Ntanos et al. 2021 §4.1 do.

    The scintillation regime, and why it is a scenario field
    -------------------------------------------------------
    **Scintillation** is the twinkling of a star: pockets of air at different
    temperatures act as weak lenses, so the power reaching the detector
    fluctuates. The budget prices it as a *fade allowance* — how many decibels
    to hold back so that the link still closes at the stated
    ``outage_probability`` — and to do that it needs the variance of the
    logarithm of the received irradiance.

    There are two defensible ways to compute that variance and they are not the
    same number. First-order perturbation theory gives the **Rytov variance**,
    which is ITU-R P.1622 equation (4a) and grows without bound; real air
    **saturates** near a scintillation index of 1, because the beam breaks into
    many independent speckles and more turbulence adds more speckles rather than
    deeper ones. :attr:`scintillation_regime` says which of the two the run
    uses, and the reason it is here — in the scenario, hashed, rather than an
    argument somebody passes at a call site — is that it moves a design
    decision, not a decimal: on the reference day the interior optimum of the
    elevation mask moves from **8° to 4.5°**, the day gains **+3.66 %** of
    certified key at the scenario's own 10° mask and **+6.18 %** comparing each
    regime at its own optimum (ADR 0022, and
    ``tests/e2e/test_reference_scenarios.py``). A result that did not carry the
    choice in its provenance would be two different days under one hash.

    **There is no default, and that is a change from the schema this field
    arrived in.** It had one, ``WEAK``, defended with a measurement: flipping it
    to the saturated model would move six of the eight published cells of ITU-R
    P.1622 Table 2 outside half a printed digit, so the project would lose six
    of its eight strongest V2 anchors of the channel
    (``tests/channel/test_turbulence.py::test_what_the_default_would_cost_across_the_whole_published_table``).
    That measurement still holds and the flip is still refused. What stopped
    holding is the *other* half of the argument — that a default here is
    invisible only in theory, because every file in ``scenarios/`` writes the
    field anyway. A horizontal link (``HorizontalPathSpec``) writes it too, and
    for it the saturated model is not a refinement below 20 degrees of elevation
    but the ordinary case: with ``C_n^2 = 1e-14`` at 1550 nm the weak theory
    stops being citable at **2413 m**
    (:func:`quoss.channel.horizontal.weak_theory_path_limit_m`), which is inside
    the range GE-1 is being sized over. A default that is right for one member of
    a discriminated union and wrong for the other is exactly the invisible
    parameter ADR 0014 refuses.

    So the field is required here, and the ``WEAK`` default **moves to the seven
    physics signatures** rather than disappearing — see the annex of ADR 0022.
    There it keeps the six anchors, because those signatures are where the
    comparisons against P.1622 are made; here the scenario author chooses and the
    choice is in the hash. Choosing ``MODERATE_TO_STRONG`` is one line, and the
    channel records ``turbulence.weak-fluctuation-limit-exceeded`` naming it
    whenever ``WEAK`` is used past its own validity limit.

    Examples
    --------
    >>> ChannelSpec(zenith_transmittance=0.812, scintillation_regime="weak").fade_combination
    <FadeCombination.EXACT: 'exact'>
    >>> ChannelSpec(
    ...     zenith_transmittance=0.812, scintillation_regime="moderate-to-strong"
    ... ).scintillation_regime
    <ScintillationRegime.MODERATE_TO_STRONG: 'moderate-to-strong'>

    Leaving the regime out is refused rather than assumed:

    >>> ChannelSpec(zenith_transmittance=0.812)
    Traceback (most recent call last):
        ...
    pydantic_core._pydantic_core.ValidationError: 1 validation error for ChannelSpec
    scintillation_regime
      Field required...

    >>> ChannelSpec(zenith_transmittance=0.812, scintillation_regime="weak").models_extinction
    False
    >>> modelled = ChannelSpec(
    ...     scintillation_regime="weak",
    ...     extinction=ExtinctionSpec(
    ...         visibility_km=23.0,
    ...         visibility_altitude_m=30.0,
    ...         aerosol_scale_height_m=1200.0,
    ...         scaling_law="kim-2001",
    ...     ),
    ... )
    >>> modelled.models_extinction
    True
    """

    zenith_transmittance: float | None = Field(
        default=None,
        gt=0.0,
        le=1.0,
        description="Clear-sky vertical atmospheric transmittance, linear (0, 1]. One of the "
        "two ways to declare extinction; writing 1.0 here is how a scenario declares 'no "
        "extinction modelled' (ADR 0009 gap 14).",
    )
    extinction: ExtinctionSpec | None = Field(
        default=None,
        description="The other way: a visibility, a scale height and a published scaling law, "
        "resolved into a vertical transmittance per station and wavelength (ADR 0023).",
    )
    static_loss_db: float = Field(
        default=0.0,
        ge=0.0,
        description="Fixed losses not modelled elsewhere (polarisation decoherence, coupling), "
        "dB, positive means loss.",
    )
    outage_probability: float = Field(
        default=0.01,
        gt=0.0,
        lt=1.0,
        description="Probability at which the fade allowance is budgeted; 0.01 is Ntanos et "
        "al. 2021 §4.1's 1 %.",
    )
    fade_combination: FadeCombination = Field(
        default=FadeCombination.EXACT,
        description="'exact' takes the joint quantile of the two fades; 'additive' sums the "
        "two marginal quantiles as the published budgets do (it overstates the fade).",
    )
    scintillation_regime: ScintillationRegime = Field(
        description="Which scintillation model turns the Rytov variance into the fade. 'weak' is "
        "ITU-R P.1622 equation (4a) itself, the number every V2 anchor in this project is "
        "compared against; 'moderate-to-strong' saturates it with the large-scale/small-scale "
        "split of Gruneisen et al. (A8)-(A9), which is never larger and is 6.1 dB smaller at the "
        "reference day's worst sample. REQUIRED, no default: the two differ by +3.66 % of the "
        "reference day's certified key and move the optimal elevation mask from 8 to 4.5 degrees, "
        "and on a horizontal path the weak theory stops being citable past 2413 m. ADR 0022 "
        "measures both and says what each buys.",
    )

    @model_validator(mode="after")
    def _exactly_one_extinction(self) -> ChannelSpec:
        """Require a transmittance or a model, never both, never neither."""
        if (self.zenith_transmittance is None) == (self.extinction is None):
            raise ValueError(
                "give exactly one of zenith_transmittance or extinction. A number and a model "
                "are two answers to the same question, and giving neither would leave the "
                "atmosphere at whatever the code happened to default to — which is the thing "
                "docs/adr/0009-citation-policy.md gap 14 exists to prevent. A scenario that "
                "does not model extinction writes zenith_transmittance: 1.0 and has said so."
            )
        return self

    @property
    def models_extinction(self) -> bool:
        """True when the transmittance comes from a model rather than a number."""
        return self.extinction is not None

    def zenith_transmittance_at(
        self,
        *,
        wavelength_m: float,
        station_altitude_m: float,
        degradations: DegradationLog,
    ) -> float:
        """Resolve ``L_zen`` whichever way it was declared.

        A declared number does not depend on the wavelength or the station, and
        a model does — the same visibility is 0.192 dB/km at 1550 nm and
        0.465 at 785, and a station 2 km up sits above most of the aerosol. So
        the engine calls this once per station rather than reading a field, and
        a multi-station scenario gets a different atmosphere at each site from
        one declaration.

        Parameters
        ----------
        wavelength_m : float
            The transmitter wavelength, m.
        station_altitude_m : float
            The station's height above the ellipsoid, m.
        degradations : DegradationLog
            Receives whatever the extinction model records; untouched when the
            transmittance was declared as a number, because a number that was
            written down deliberately has nothing to report.

        Returns
        -------
        float
            Vertical transmittance in ``(0, 1]``.
        """
        if self.zenith_transmittance is not None:
            return self.zenith_transmittance
        assert self.extinction is not None  # narrowed by the model validator
        return self.extinction.zenith_transmittance(
            wavelength_m=wavelength_m,
            station_altitude_m=station_altitude_m,
            degradations=degradations,
        )


class ReceiverSpec(SpecModel):
    """The ground receiver: optics after the telescope, and the detector.

    ``detector_count`` is how many detectors share the dark-count budget (two
    for a passive-basis-choice BB84 receiver). ``optical_loss_db`` is every
    loss between the telescope and the detector, filter included, so the chain
    efficiency the physics takes is :attr:`chain_efficiency`.

    Examples
    --------
    >>> rx = ReceiverSpec(
    ...     detector_efficiency=0.85,
    ...     optical_loss_db=5.65,
    ...     dark_count_rate_cps=300.0,
    ...     dead_time_ns=30.0,
    ...     gate_ns=1.0,
    ...     timing_jitter_fwhm_ps=50.0,
    ...     field_of_view_urad=100.0,
    ...     filter_bandwidth_nm=0.2,
    ... )
    >>> rx.gate_s
    1e-09
    >>> round(rx.chain_efficiency, 6)
    0.23143
    """

    detector_efficiency: float = Field(
        gt=0.0, le=1.0, description="Detector quantum efficiency at the wavelength, linear."
    )
    optical_loss_db: float = Field(
        ge=0.0,
        description="Receiver optical losses between telescope and detector, dB, filter "
        "insertion loss included.",
    )
    dark_count_rate_cps: float = Field(
        ge=0.0, description="Dark count rate per detector, counts/s."
    )
    detector_count: int = Field(
        default=2, ge=1, description="Number of detectors whose dark counts add."
    )
    afterpulse_probability: float = Field(
        default=0.0,
        ge=0.0,
        lt=1.0,
        description="Probability that a click triggers a spurious afterpulse; 0 for SNSPDs.",
    )
    dead_time_ns: float = Field(ge=0.0, description="Detector dead time after a click, ns.")
    gate_ns: float = Field(
        gt=0.0,
        description="Detection gate width, ns. Must not exceed the pulse period (checked at "
        "scenario level).",
    )
    timing_jitter_fwhm_ps: float = Field(
        ge=0.0, description="Detector timing jitter, full width at half maximum, ps."
    )
    field_of_view_urad: float = Field(
        gt=0.0, description="Receiver field of view, full angle, microradians."
    )
    filter_bandwidth_nm: float = Field(gt=0.0, description="Optical band-pass filter width, nm.")
    doppler_capture_range_hz: float | None = Field(
        default=None,
        gt=0.0,
        description="Optional. Total width of the receiver's Doppler acceptance window, Hz — "
        "the full span it can search, NOT the +/- half-range. A window of +/-5 GHz is "
        "1e10 here. None (the default) means no transceiver has been chosen yet, and the "
        "run's Doppler figures are then reported against nothing.",
    )

    @property
    def doppler_capture_half_range_hz(self) -> float | None:
        """Half of :attr:`doppler_capture_range_hz`, i.e. the window written as ``+/- X``.

        Both readings exist by name, for the reason
        :class:`~quoss.engine.pipeline.Acquisition` gives at length about the
        two Doppler columns: a quantity that is "the other one, times two" gets
        multiplied by two in some call sites and not in others. Neither of these
        is the one somebody has to remember to halve.

        Returns
        -------
        float or None
            ``doppler_capture_range_hz / 2``, or ``None`` when no window is
            declared.

        Examples
        --------
        A transceiver quoted as "+/-5 GHz of capture" is a 10 GHz window:

        >>> rx = ReceiverSpec(
        ...     detector_efficiency=0.85,
        ...     optical_loss_db=5.65,
        ...     dark_count_rate_cps=300.0,
        ...     dead_time_ns=30.0,
        ...     gate_ns=1.0,
        ...     timing_jitter_fwhm_ps=50.0,
        ...     field_of_view_urad=100.0,
        ...     filter_bandwidth_nm=0.2,
        ...     doppler_capture_range_hz=1e10,
        ... )
        >>> rx.doppler_capture_half_range_hz
        5000000000.0
        """
        if self.doppler_capture_range_hz is None:
            return None
        return self.doppler_capture_range_hz / 2.0

    @property
    def gate_s(self) -> float:
        """Gate width, s."""
        return self.gate_ns * _S_PER_NS

    @property
    def dead_time_s(self) -> float:
        """Dead time, s."""
        return self.dead_time_ns * _S_PER_NS

    @property
    def timing_jitter_fwhm_s(self) -> float:
        """Timing jitter FWHM, s."""
        return self.timing_jitter_fwhm_ps * _S_PER_PS

    @property
    def field_of_view_rad(self) -> float:
        """Field of view, full angle, rad."""
        return self.field_of_view_urad * _RAD_PER_URAD

    @property
    def filter_bandwidth_m(self) -> float:
        """Filter width, m."""
        return float(nm_to_m(self.filter_bandwidth_nm))

    @property
    def chain_efficiency(self) -> float:
        """Detector efficiency times the receiver's optical transmittance, linear.

        The single number :func:`quoss.channel.link_budget.downlink_loss_budget`
        and :func:`~quoss.channel.link_budget.downlink_noise_budget` take as
        ``receiver_efficiency``.
        """
        return receiver_efficiency(self.detector_efficiency, optical_loss_db=self.optical_loss_db)


class BackgroundSpec(SpecModel):
    """The sky's radiance into the receiver: a number, or an ITU table column.

    Exactly one of ``sky_radiance_w_m2_um_sr`` (a value, typically one of the
    night-time constants of :mod:`quoss.channel.background`) or ``condition``
    (a column of ITU-R P.1621-2 Table 1, tabulated at 530-1500 nm; between
    grid points the value is interpolated and a ``DEGRADED`` record is logged,
    ADR 0009 gap 4). A ``condition`` at a wavelength outside the table is
    refused at scenario validation, because there is no published value to
    interpolate towards.

    Examples
    --------
    >>> BackgroundSpec(sky_radiance_w_m2_um_sr=1.5e-4).is_tabulated
    False
    >>> BackgroundSpec(condition="overcast").condition
    <SkyCondition.OVERCAST: 'overcast'>
    """

    sky_radiance_w_m2_um_sr: float | None = Field(
        default=None,
        ge=0.0,
        description="Sky spectral radiance, W/(m^2 um sr). Ntanos et al. 2021 §4.2.2 give "
        "1.5e-5 for a moonless night, 1.5e-4 for their study night, 1.5e-3 at full moon. Zero "
        "is legal and means a closed enclosure (a bench, ADR 0024) — a declaration, not an "
        "omission, which the exactly-one validator below is what prevents.",
    )
    condition: SkyCondition | None = Field(
        default=None,
        description="ITU-R P.1621-2 Table 1 column: bright_sunshine, normal_sunshine or "
        "overcast. Daylight only; there is no night column in the table.",
    )

    @model_validator(mode="after")
    def _exactly_one(self) -> BackgroundSpec:
        """Require a value or a table column, never both, never neither."""
        if (self.sky_radiance_w_m2_um_sr is None) == (self.condition is None):
            raise ValueError(
                "give exactly one of sky_radiance_w_m2_um_sr or condition. A value and a "
                "table column are two answers to the same question."
            )
        return self

    @property
    def is_tabulated(self) -> bool:
        """True when the radiance comes from the ITU table rather than a value."""
        return self.condition is not None

    def radiance_w_m2_um_sr(self, wavelength_m: float, *, degradations: DegradationLog) -> float:
        """Resolve the radiance at a wavelength, logging any interpolation.

        Parameters
        ----------
        wavelength_m : float
            The transmitter wavelength, m.
        degradations : DegradationLog
            Receives the ``DEGRADED`` record when a table column is
            interpolated between grid points.

        Returns
        -------
        float
            Radiance in W/(m^2 um sr).
        """
        if self.sky_radiance_w_m2_um_sr is not None:
            return self.sky_radiance_w_m2_um_sr
        assert self.condition is not None  # narrowed by the model validator
        return interpolated_sky_radiance_w_m2_um_sr(
            wavelength_m, condition=self.condition, degradations=degradations
        )


# --------------------------------------------------------------------------- #
# Protocol and security
# --------------------------------------------------------------------------- #
class ProtocolSpec(SpecModel):
    """The QKD protocol and its source settings.

    ``name`` must be registered in :data:`quoss.qkd.base.PROTOCOLS`; today that
    is ``"bb84-decoy"`` only, and asking for another name is refused with the
    list of what exists rather than silently run as BB84. The bounds mirror
    :class:`~quoss.qkd.bb84.Bb84DecoyProtocol`: ``0 < decoy < signal``, three
    probabilities in ``(0, 1)`` summing to one, efficiency at least 1.

    Examples
    --------
    >>> spec = ProtocolSpec(
    ...     name="bb84-decoy",
    ...     signal_intensity=0.56,
    ...     decoy_intensity=0.11,
    ...     signal_probability=16 / 21,
    ...     decoy_probability=1 / 21,
    ...     vacuum_probability=4 / 21,
    ...     error_correction_efficiency=1.22,
    ...     misalignment_error=0.01,
    ... )
    >>> spec.to_protocol() == Bb84DecoyProtocol.ntanos_2021()
    True
    """

    name: str = Field(description="Registered protocol name, e.g. 'bb84-decoy'.")
    signal_intensity: float = Field(gt=0.0, description="Mean photons per signal pulse, mu.")
    decoy_intensity: float = Field(
        gt=0.0, description="Mean photons per decoy pulse, nu. Must be below the signal."
    )
    signal_probability: float = Field(
        gt=0.0, lt=1.0, description="Fraction of pulses sent as signal."
    )
    decoy_probability: float = Field(
        gt=0.0, lt=1.0, description="Fraction of pulses sent as decoy."
    )
    vacuum_probability: float = Field(gt=0.0, lt=1.0, description="Fraction of pulses sent empty.")
    error_correction_efficiency: float = Field(
        ge=1.0,
        description="Factor over the Shannon limit of the error-correcting code; CASCADE is 1.22.",
    )
    misalignment_error: float = Field(
        ge=0.0,
        le=0.5,
        description="Intrinsic optical error probability of the receiver, a fraction (1 % is 0.01).",
    )
    key_basis_probability: float = Field(
        default=0.5,
        gt=0.0,
        lt=1.0,
        description="Probability that a pulse is prepared and measured in the key basis; "
        "0.5 is symmetric BB84.",
    )

    @field_validator("name")
    @classmethod
    def _registered(cls, value: str) -> str:
        """Refuse a protocol the package does not have, naming those it does."""
        available = PROTOCOLS.names()
        if value not in available:
            raise ValueError(
                f"no QKD protocol is registered as {value!r}. Available: {list(available)}."
            )
        return value

    @model_validator(mode="after")
    def _consistent(self) -> ProtocolSpec:
        """Decoy below signal, and the three fractions summing to one."""
        if not self.decoy_intensity < self.signal_intensity:
            raise ValueError(
                f"decoy_intensity={self.decoy_intensity} must be below "
                f"signal_intensity={self.signal_intensity}: the decoy is the weaker state, or "
                "the single-photon bound of Ma et al. 2005 Eq. (34) inverts."
            )
        total = self.signal_probability + self.decoy_probability + self.vacuum_probability
        if abs(total - 1.0) > _PROBABILITY_SUM_SLACK:
            raise ValueError(
                f"signal_probability + decoy_probability + vacuum_probability must equal 1, "
                f"got {total!r}. They are the fractions of emitted pulses at each intensity."
            )
        return self

    def to_protocol(self) -> Bb84DecoyProtocol:
        """Return the :class:`~quoss.qkd.bb84.Bb84DecoyProtocol` these settings describe.

        The registry has validated the name; the package has one protocol, so
        the constructor is called directly. When a second protocol registers,
        this method is where the name dispatches.
        """
        return Bb84DecoyProtocol(
            signal_intensity=self.signal_intensity,
            decoy_intensity=self.decoy_intensity,
            signal_probability=self.signal_probability,
            decoy_probability=self.decoy_probability,
            vacuum_probability=self.vacuum_probability,
            error_correction_efficiency=self.error_correction_efficiency,
        )


class SecuritySpec(SpecModel):
    """The finite-key failure probabilities, and whether a day composes them.

    ``compose_daily=True`` reports the day's key under ``n * eps`` (the union
    bound over ``n`` independent blocks, ``docs/adr/0011-the-block-is-the-pass.md``
    §6); ``False`` reports each pass at its own ``eps`` and no daily claim.

    Examples
    --------
    >>> SecuritySpec().to_security().total
    2e-10
    """

    correctness: float = Field(
        default=1e-10, gt=0.0, lt=1.0, description="eps_cor per block, in (0, 1)."
    )
    secrecy: float = Field(
        default=1e-10, gt=0.0, lt=1.0, description="eps_sec per block, in (0, 1)."
    )
    compose_daily: bool = Field(
        default=True,
        description="Report the day's key with the composed n*eps failure probability.",
    )

    def to_security(self) -> SecurityParameters:
        """Return the :class:`~quoss.qkd.finite_key.SecurityParameters` for one block."""
        return SecurityParameters(correctness=self.correctness, secrecy=self.secrecy)


# --------------------------------------------------------------------------- #
# Time, passes, options
# --------------------------------------------------------------------------- #
class TimeSpec(SpecModel):
    """The simulation window: an explicit UTC epoch, a duration and a step.

    ``epoch_utc`` must be timezone-aware and in UTC. A naive datetime is
    refused because it is exactly the SimulCTTC defect ``notes/ROADMAP.md``
    records — an epoch that "fell silently to the wall clock" — in a new
    costume: Python would read it in whatever zone the machine happens to run
    in, and the sky over a station is a function of the true instant.

    ``duration_s`` must be a whole multiple of ``step_s`` to within the same
    ``1e-9`` relative slack :meth:`quoss.core.types.TimeGrid.uniform` uses, so
    that :meth:`grid` cannot fail on a scenario that validated.

    Examples
    --------
    >>> import datetime as dt
    >>> time = TimeSpec(
    ...     epoch_utc=dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc), duration_s=600.0, step_s=1.0
    ... )
    >>> time.epoch_jd
    2460676.5
    >>> time.grid().n
    601
    """

    epoch_utc: dt.datetime = Field(
        description="Instant of t = 0, timezone-aware UTC (ISO-8601 with 'Z'). Naive "
        "datetimes are refused."
    )
    duration_s: float = Field(gt=0.0, description="Length of the window, s.")
    step_s: float = Field(gt=0.0, description="Sample spacing, s. Must divide duration_s.")

    @field_validator("epoch_utc")
    @classmethod
    def _utc(cls, value: dt.datetime) -> dt.datetime:
        """Aware, UTC, and within the years :func:`calendar_to_jd` accepts."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError(
                "epoch_utc must be timezone-aware UTC, e.g. 2025-01-01T00:00:00Z. A naive "
                "datetime would be read in the machine's local zone: the 'epoch fell to the "
                "wall clock' defect of SimulCTTC."
            )
        if value.utcoffset() != dt.timedelta(0):
            raise ValueError(
                f"epoch_utc must be in UTC, got offset {value.utcoffset()}. Convert before "
                "writing the scenario; the Julian date is defined against UTC."
            )
        try:
            calendar_to_jd(
                value.year,
                value.month,
                value.day,
                value.hour,
                value.minute,
                value.second + value.microsecond / _MICROSECONDS_PER_SECOND,
            )
        except DomainError as error:
            raise ValueError(str(error)) from error
        return value

    @model_validator(mode="after")
    def _whole_steps(self) -> TimeSpec:
        """Mirror the whole-multiple rule of :meth:`TimeGrid.uniform`."""
        count = self.duration_s / self.step_s
        if abs(count - round(count)) > _GRID_STEP_SLACK * max(1.0, count):
            raise ValueError(
                f"duration_s={self.duration_s} is not a whole multiple of step_s={self.step_s} "
                f"({count} steps). A fractional last step would silently shorten the window."
            )
        return self

    @property
    def epoch_jd(self) -> float:
        """The epoch as a Julian date, UTC."""
        return calendar_to_jd(
            self.epoch_utc.year,
            self.epoch_utc.month,
            self.epoch_utc.day,
            self.epoch_utc.hour,
            self.epoch_utc.minute,
            self.epoch_utc.second + self.epoch_utc.microsecond / _MICROSECONDS_PER_SECOND,
        )

    @property
    def n_samples(self) -> int:
        """Number of samples of the closed uniform grid, ``duration/step + 1``."""
        return round(self.duration_s / self.step_s) + 1

    def grid(self) -> TimeGrid:
        """Return the uniform :class:`~quoss.core.types.TimeGrid` of the window."""
        return TimeGrid.uniform(
            epoch_jd=self.epoch_jd, duration_s=self.duration_s, step_s=self.step_s
        )


class PassSpec(SpecModel):
    """What counts as a usable pass.

    :attr:`minimum_elevation_deg` has **no default**; see the module docstring
    and ``docs/adr/0011-the-block-is-the-pass.md`` §5.

    Examples
    --------
    >>> round(PassSpec(minimum_elevation_deg=10.0).minimum_elevation_rad, 6)
    0.174533
    """

    minimum_elevation_deg: float = Field(
        ge=0.0,
        lt=90.0,
        description="Elevation mask, degrees. REQUIRED, no default: the finite-key yield has "
        "an interior optimum near 8 deg (ADR 0011 §5), so it is a design variable.",
    )
    minimum_duration_s: float = Field(
        default=0.0, ge=0.0, description="Passes shorter than this are dropped, s."
    )

    @property
    def minimum_elevation_rad(self) -> float:
        """Elevation mask, rad."""
        return float(deg_to_rad(self.minimum_elevation_deg))


class MonteCarloSpec(SpecModel):
    """Options of the per-pass Monte Carlo over correlated fading.

    ``seed=None`` means "draw one from the OS and record it" — the run is still
    reproducible from the provenance, per :mod:`quoss.core.rng`. The two
    correlation times are the memory of the scintillation and pointing
    processes; ``quantiles`` are the ensemble quantiles reported per pass and
    must be strictly increasing so that a result column is unambiguous.

    Examples
    --------
    >>> MonteCarloSpec(
    ...     realisations=200,
    ...     scintillation_correlation_time_s=0.01,
    ...     pointing_correlation_time_s=0.1,
    ... ).quantiles
    (0.05, 0.5, 0.95)
    """

    realisations: int = Field(ge=1, description="Number of independent fading realisations.")
    seed: int | None = Field(
        default=None,
        ge=0,
        lt=_MAX_SEED,
        description="Seed of the random source, or null to draw one and record it.",
    )
    sample_counts: bool = Field(
        default=True,
        description="Draw Poisson counts per block as well as the fading (true), or use "
        "expected counts under the sampled fading (false).",
    )
    scintillation_correlation_time_s: float = Field(
        gt=0.0, description="Correlation time of the scintillation process, s."
    )
    pointing_correlation_time_s: float = Field(
        gt=0.0, description="Correlation time of the pointing jitter process, s."
    )
    quantiles: tuple[float, ...] = Field(
        default=(0.05, 0.5, 0.95),
        min_length=1,
        description="Ensemble quantiles reported per pass, each in (0, 1), strictly increasing.",
    )

    @field_validator("quantiles")
    @classmethod
    def _increasing(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        """Each in (0, 1) and strictly increasing."""
        for q in value:
            if not 0.0 < q < 1.0:
                raise ValueError(f"quantiles must lie in (0, 1), got {q!r}.")
        if any(b <= a for a, b in pairwise(value)):
            raise ValueError(
                f"quantiles must be strictly increasing, got {list(value)}. The order names the "
                "result columns."
            )
        return value


class AggregationPolicyName(StrEnum):
    """How several stations' harvests combine (``system/multi_ogs.py``).

    Defined here rather than imported because ``system/multi_ogs.py`` and this
    module are written in the same stage; the engine maps the name to that
    module's enum. The values are the contract.

    Attributes
    ----------
    SUM
        Independent harvests, one satellite terminal per station.
    BEST_AVAILABLE
        One satellite terminal: overlapping pass windows conflict and the one
        with more expected key is kept.
    """

    SUM = "sum"
    BEST_AVAILABLE = "best_available"


class MultiStationSpec(SpecModel):
    """Options of the multi-station aggregation and site-diversity model.

    Examples
    --------
    >>> MultiStationSpec().policy
    <AggregationPolicyName.BEST_AVAILABLE: 'best_available'>
    """

    policy: AggregationPolicyName = Field(
        default=AggregationPolicyName.BEST_AVAILABLE,
        description="'sum' for independent harvests, 'best_available' for one terminal.",
    )
    cloud_decorrelation_length_km: float | None = Field(
        default=None,
        gt=0.0,
        description="Decorrelation length of cloud cover between sites, km, for the joint "
        "cloud-free probability; null disables the joint model.",
    )


class RelaySpec(SpecModel):
    """Trusted-node relay pairs: end-to-end key between two stations via the satellite.

    Examples
    --------
    >>> RelaySpec(pairs=[("a", "b")]).pairs
    [('a', 'b')]
    """

    pairs: list[tuple[str, str]] = Field(
        min_length=1, description="Ordered (source, destination) station-name pairs."
    )

    @field_validator("pairs")
    @classmethod
    def _distinct(cls, value: list[tuple[str, str]]) -> list[tuple[str, str]]:
        """Refuse a pair whose two ends are the same station."""
        for a, b in value:
            if a == b:
                raise ValueError(
                    f"a relay pair must join two different stations, got ({a!r}, {b!r})."
                )
        return value


# --------------------------------------------------------------------------- #
# The horizontal link
# --------------------------------------------------------------------------- #
class LinkKind(StrEnum):
    """Which geometry a scenario describes. The discriminator of the ``link`` union.

    A scenario is one of exactly two things, and there is no third and no
    "either":

    ``DOWNLINK``
        A satellite over a ground station. Elevation changes every second, the
        turbulence is an integral of the Hufnagel-Valley profile along
        ``1 / sin(theta)``, and the run is organised into **passes**.
    ``HORIZONTAL``
        A bench or a link of a few hundred metres to a few kilometres, at one
        height. ``C_n^2`` is a constant of the path, there is **no elevation**,
        and the run is one stationary **measurement session**.

    Why this is a tag and not a pair of optional sections
    -----------------------------------------------------
    Because :class:`SpecModel` sets ``extra="forbid"``, and a tag turns that
    setting into the rule. A horizontal scenario cannot carry ``stations``,
    ``passes``, ``orbit`` or ``time`` -- not by a validator that would have to
    be written and kept correct, but because
    :class:`HorizontalScenario` has no such fields and the model refuses names
    it does not have. The absence-based assertion of
    ``docs/adr/0021-horizontal-path.md`` (no signature of
    :mod:`quoss.channel.horizontal` takes an elevation) is now also a schema
    rule: no *scenario* of this kind can hold one either.
    """

    DOWNLINK = "downlink"
    HORIZONTAL = "horizontal"


class HorizontalPathSpec(SpecModel):
    """The air, the geometry and the extinction of a horizontal link.

    What a horizontal path is, for someone arriving new
    ---------------------------------------------------
    Light going to a satellite leaves the atmosphere: what it crosses is a
    *column* whose turbulence changes with height, traversed at an angle that
    changes every second. Light crossing a laboratory bench, or a kilometre
    between two rooftops, does neither. It stays at one height, so the
    refractive-index structure parameter ``C_n^2`` -- the number saying how
    strongly the air bends light, in m^(-2/3) -- is **one constant of the
    path**, and there is no elevation to speak of.

    That is not the slant-path formulas with a small angle. ITU-R P.1622's
    integral at 0.1 degrees runs along 11 000 km of atmosphere and returns
    **2.1e4 times** the variance of one horizontal kilometre in the same ground
    air (``docs/adr/0021-horizontal-path.md``).

    The two ways of declaring extinction, which are ``ChannelSpec``'s two
    ------------------------------------------------------------------------
    Exactly one of :attr:`extinction_db_per_km` (a number in dB/km, the unit
    ITU-R P.1814 equation (3) uses) or :attr:`extinction` (an
    :class:`ExtinctionSpec`) -- never both, never neither. The shape is
    deliberately the same as :class:`ChannelSpec`'s, and so is the reason: ADR
    0009 gap 14 says there is no value of this field that can quietly mean "I
    did not think about it", and a link through perfectly clear air writes
    ``extinction_db_per_km: 0.0`` and has said so.

    **What the model is evaluated to is different, and that is the only
    difference.** A downlink needs a *vertical transmittance*: the whole column
    above the station, one dimensionless number, which is what
    :func:`~quoss.channel.extinction.zenith_transmittance_from_visibility`
    integrates. A horizontal link has no column -- it needs the extinction
    **coefficient at its own height**, a loss per kilometre, which is
    :func:`~quoss.channel.extinction.specific_attenuation_at_altitude_db_per_km`.
    Same :class:`ExtinctionSpec`, same profile, one integration step apart.

    ``altitude_m`` is the field the downlink does not have an equivalent of,
    and it is here rather than on a station because a horizontal scenario has
    no stations. It matters only through
    ``exp(-(altitude_m - extinction.visibility_altitude_m) / aerosol_scale_height_m)``,
    so for the ordinary case -- a visibility measured where the link runs -- it
    cancels exactly and the declared scale height has no effect on any number.
    It is still required, for the reason ``visibility_altitude_m`` is: nothing
    in a visibility figure says at what height it was taken, and reading a
    sea-level climatological figure on a 2 km plateau is a different
    atmosphere by a factor 5.3.

    Examples
    --------
    >>> path = HorizontalPathSpec(
    ...     path_length_m=1000.0,
    ...     cn2_m23=1e-14,
    ...     wave="spherical",
    ...     altitude_m=30.0,
    ...     receive_aperture_m=0.10,
    ...     extinction_db_per_km=0.2,
    ...     scintillation_regime="weak",
    ... )
    >>> path.path_length_km
    1.0
    >>> path.models_extinction
    False
    """

    path_length_m: float = Field(
        gt=0.0,
        description="Length of the link, m. The unit is metres: a 2 km link is 2000.0, and 2.0 "
        "would be a bench, whose Rytov variance is 3.2e5 times smaller.",
    )
    cn2_m23: float = Field(
        ge=0.0,
        description="Refractive-index structure parameter along the path, m^(-2/3), constant. "
        "ITU-R P.1814 Table 4 gives 1e-16 (low), 1e-14 (moderate) and 1e-13 (high) near the "
        "ground; 0.0 is still air and is exact.",
    )
    wave: PathWave = Field(
        description="Which closed form describes the beam at the receiver: 'plane' or "
        "'spherical'. REQUIRED, no default: the two differ by a factor 2.46 in the point "
        "variance, and which one applies depends on the transmitter's Rayleigh range, not on a "
        "preference (ADR 0021). The budget records a WARNING when the declared wave contradicts "
        "that range.",
    )
    altitude_m: float = Field(
        ge=-500.0,
        le=9000.0,
        description="Height the link runs at, m above the WGS-84 ellipsoid. Used only by the "
        "extinction model, and only through its difference with "
        "extinction.visibility_altitude_m, which cancels exactly when the two agree.",
    )
    receive_aperture_m: float = Field(
        gt=0.0,
        description="Receiving lens diameter, m. Here and not on a station because a horizontal "
        "scenario has none; the transmitting aperture is transmitter.aperture_m.",
    )
    extinction_db_per_km: float | None = Field(
        default=None,
        ge=0.0,
        description="Specific attenuation of the air, dB/km (ITU-R P.1814's gamma_atmo). One of "
        "the two ways to declare extinction; writing 0.0 here is how a scenario declares 'no "
        "extinction modelled' (ADR 0009 gap 14).",
    )
    extinction: ExtinctionSpec | None = Field(
        default=None,
        description="The other way: a visibility, a scale height and a published scaling law, "
        "evaluated at altitude_m as a specific attenuation rather than integrated into a "
        "vertical transmittance (ADR 0023, ADR 0024).",
    )
    scintillation_regime: ScintillationRegime = Field(
        description="Which scintillation model turns the Rytov variance into the fade: 'weak' "
        "(first-order theory, ITU-R P.1814 equation (8) itself) or 'moderate-to-strong' (the "
        "saturated split of Gruneisen et al. (A8)-(A9)). REQUIRED, no default: on this path the "
        "weak theory stops being citable at 2413 m for C_n^2 = 1e-14 at 1550 nm "
        "(weak_theory_path_limit_m), which is inside the range GE-1 is sized over.",
    )
    static_loss_db: float = Field(
        default=0.0,
        ge=0.0,
        description="Fixed losses not modelled elsewhere, dB, positive means loss.",
    )
    outage_probability: float = Field(
        default=0.01,
        gt=0.0,
        lt=1.0,
        description="Probability at which the fade allowance is budgeted; 0.01 is Ntanos et "
        "al. 2021 §4.1's 1 %.",
    )
    fade_combination: FadeCombination = Field(
        default=FadeCombination.EXACT,
        description="'exact' takes the joint quantile of the two fades; 'additive' sums the two "
        "marginal quantiles as the published budgets do (it overstates the fade).",
    )

    @model_validator(mode="after")
    def _exactly_one_extinction(self) -> HorizontalPathSpec:
        """Require a number or a model, never both, never neither."""
        if (self.extinction_db_per_km is None) == (self.extinction is None):
            raise ValueError(
                "give exactly one of extinction_db_per_km or extinction. A number and a model "
                "are two answers to the same question, and giving neither would leave the air "
                "at whatever the code happened to default to — which is what "
                "docs/adr/0009-citation-policy.md gap 14 exists to prevent. A link that does "
                "not model extinction writes extinction_db_per_km: 0.0 and has said so."
            )
        return self

    @property
    def path_length_km(self) -> float:
        """Path length, km."""
        return float(m_to_km(self.path_length_m))

    @property
    def models_extinction(self) -> bool:
        """True when the attenuation comes from a model rather than a number."""
        return self.extinction is not None

    def extinction_db_per_km_at(
        self, *, wavelength_m: float, degradations: DegradationLog
    ) -> float:
        """Resolve the specific attenuation whichever way it was declared.

        The counterpart of
        :meth:`ChannelSpec.zenith_transmittance_at`, and a method for the same
        reason: a declared number does not depend on the wavelength and a model
        does -- 23 km of visibility is 0.192 dB/km at 1550 nm and 0.465 at 785.
        The engine calls this rather than reading a field, so the two ways of
        declaring produce one number through one call.

        Parameters
        ----------
        wavelength_m : float
            The transmitter wavelength, m.
        degradations : DegradationLog
            Receives whatever the extinction model records; untouched when the
            attenuation was declared as a number, because a number written down
            deliberately has nothing to report.

        Returns
        -------
        float
            Specific attenuation, dB/km, non-negative.
        """
        if self.extinction_db_per_km is not None:
            return self.extinction_db_per_km
        assert self.extinction is not None  # narrowed by the model validator
        return float(
            specific_attenuation_at_altitude_db_per_km(
                self.extinction.visibility_km,
                wavelength_m=wavelength_m,
                aerosol_scale_height_m=self.extinction.aerosol_scale_height_m,
                altitude_m=self.altitude_m,
                visibility_altitude_m=self.extinction.visibility_altitude_m,
                law=self.extinction.scaling_law,
                degradations=degradations,
            )
        )


class SessionSpec(SpecModel):
    """How long the measurement runs. On a horizontal link this **is** the key block.

    Why one number needs its own model and this much prose
    ------------------------------------------------------
    ``docs/adr/0011-the-block-is-the-pass.md`` decided that the block a
    finite-key bound is evaluated over is **a pass**, and the argument was that
    the geometry fixes it: between two passes the satellite is below the
    horizon and no pulse is sent, so a pass is not a choice anybody makes, it is
    where the data stops.

    A horizontal link is stationary. Nothing stops the data. The block is
    whatever the operator decides to call one, and that changes **who is
    responsible for the bound being valid**: on a downlink the schema can
    refuse to let anyone get it wrong, and here it cannot. So the duration is a
    required field with no default, it is written in the scenario where it
    enters the hash and the provenance, and ``docs/adr/0024-the-horizontal-scenario.md``
    says what the operator is promising by writing it.

    What the promise is, concretely: every pulse counted into one block must
    have been sent under the conditions the block was priced at, and the
    security parameters are per block, so running ``n`` sessions and
    concatenating their keys composes the failure probabilities to ``n * eps``
    exactly as :func:`~quoss.system.key_volume.composed_security` does for
    passes. A session declared longer than the link was actually stable is not
    an approximation, it is a false security claim.

    Examples
    --------
    >>> SessionSpec(duration_s=60.0).duration_s
    60.0
    """

    duration_s: float = Field(
        gt=0.0,
        description="Length of one measurement session, s. This is the finite-key block. "
        "REQUIRED, no default: on a stationary link nothing fixes it but the operator "
        "(ADR 0024), unlike a pass, which the geometry fixes (ADR 0011).",
    )


class HorizontalScenario(SpecModel):
    """The whole input of one horizontal run: a bench, or a link a few kilometres long.

    The other member of the ``link`` discriminated union, and deliberately not a
    :class:`Scenario` with the orbital half left empty. What it does **not**
    have is the point: no ``orbit``, no ``stations``, no ``passes``, no
    ``time``, and therefore nowhere to write an elevation, an elevation mask, a
    ground wind speed or a station height. ``extra="forbid"`` turns each of
    those absences into an error message naming the field, which is what
    ``docs/adr/0021-horizontal-path.md``'s "asserted by absence" becomes once
    the path has a scenario of its own.

    What it shares with a downlink, and why sharing is right here
    -------------------------------------------------------------
    ``transmitter``, ``receiver``, ``background``, ``protocol`` and ``security``
    are the **same** models. They describe hardware and a protocol, and a
    photon does not know what geometry brought it: an SNSPD has the same dark
    count rate on a bench as under a satellite. Copying them into horizontal
    twins would have created two ways to say one thing and two places for them
    to drift apart.

    ``background`` on a closed bench is ``sky_radiance_w_m2_um_sr: 0.0``, which
    is a declaration and not a default.

    Examples
    --------
    >>> from quoss.scenario.defaults import ge1_two_terminals
    >>> scenario = ge1_two_terminals()
    >>> scenario.link
    <LinkKind.HORIZONTAL: 'horizontal'>
    >>> scenario.path.path_length_m
    1000.0
    >>> scenario.session.duration_s
    60.0
    """

    link: Literal[LinkKind.HORIZONTAL] = Field(
        description="The discriminator: 'horizontal'. REQUIRED, with one legal value, so that a "
        "file says which geometry it describes in its first line rather than by which sections "
        "it happens to carry."
    )
    name: str = Field(min_length=1, description="Label. Excluded from the hash.")
    description: str = Field(default="", description="Free text. Excluded from the hash.")
    schema_version: int = Field(
        default=SCHEMA_VERSION, description="Schema version this file was written for."
    )
    path: HorizontalPathSpec
    transmitter: TransmitterSpec
    receiver: ReceiverSpec
    background: BackgroundSpec
    protocol: ProtocolSpec
    security: SecuritySpec
    session: SessionSpec

    @field_validator("schema_version")
    @classmethod
    def _supported(cls, value: int) -> int:
        """Refuse a file written for another schema rather than misread it."""
        if value != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {value} is not supported; this code reads version "
                f"{SCHEMA_VERSION}. Field meanings may differ between versions."
            )
        return value

    @model_validator(mode="after")
    def _consistent(self) -> HorizontalScenario:
        """Enforce the rules that span two sub-models.

        The gate rule is :class:`Scenario`'s, verbatim and for the same reason:
        one gate per pulse, and a gate wider than the pulse period would have
        two pulses inside it. The tabulated-background rule is
        :class:`Scenario`'s too -- ITU-R P.1621-2 Table 1 covers a wavelength
        range whatever the geometry.
        """
        if self.receiver.gate_s > self.transmitter.pulse_period_s:
            raise ValueError(
                f"receiver.gate_ns={self.receiver.gate_ns} exceeds the pulse period "
                f"{self.transmitter.pulse_period_s * 1e9} ns at transmitter.pulse_rate_hz="
                f"{self.transmitter.pulse_rate_hz}. One gate per pulse; wider gates overlap."
            )
        if self.background.is_tabulated:
            lo, hi = min(ITU_SKY_RADIANCE_WAVELENGTHS_M), max(ITU_SKY_RADIANCE_WAVELENGTHS_M)
            wavelength = self.transmitter.wavelength_m
            if not lo <= wavelength <= hi:
                raise ValueError(
                    f"background.condition is tabulated only for wavelengths "
                    f"{lo * 1e9:.0f}-{hi * 1e9:.0f} nm (ITU-R P.1621-2 Table 1); the transmitter "
                    f"is at {self.transmitter.wavelength_nm} nm. Give sky_radiance_w_m2_um_sr "
                    "instead."
                )
        return self

    def physics_dict(self) -> dict[str, Any]:
        """Return the JSON-mode dump with the label fields removed.

        The payload :mod:`quoss.scenario.hash` canonicalises, and the reason both
        members of the union carry this method rather than the hash special-casing
        them: a third member would then need nothing but the method.
        """
        return self.model_dump(mode="json", exclude={"name", "description"})


# --------------------------------------------------------------------------- #
# The scenario
# --------------------------------------------------------------------------- #
class Scenario(SpecModel):
    """The whole input of one run.

    ``name`` and ``description`` are labels: :func:`quoss.scenario.hash.scenario_hash`
    excludes them, so two scenarios with the same physics and different names
    share a cache entry. Everything else is physics or options and enters the
    hash.

    Cross-model rules enforced here, because no single sub-model can see both
    sides: station names unique; relay pairs name existing stations; the
    detection gate no wider than the pulse period (the rule
    :class:`~quoss.qkd.base.LinkConditions` enforces); a tabulated background
    only at a wavelength ITU-R P.1621-2 Table 1 covers.

    Examples
    --------
    >>> from quoss.scenario.defaults import reference_castelldefels
    >>> scenario = reference_castelldefels()
    >>> scenario.station_names
    ('castelldefels',)
    >>> scenario.schema_version
    1
    """

    link: Literal[LinkKind.DOWNLINK] = Field(
        default=LinkKind.DOWNLINK,
        description="The discriminator of the link union: 'downlink'. It has a default, and the "
        "default is defensible where scintillation_regime's was not, because this Literal has "
        "exactly one legal value: there is no alternative for it to hide. Writing it is still "
        "how a file says in its first line which geometry it describes.",
    )
    name: str = Field(min_length=1, description="Label. Excluded from the hash.")
    description: str = Field(default="", description="Free text. Excluded from the hash.")
    schema_version: int = Field(
        default=SCHEMA_VERSION, description="Schema version this file was written for."
    )
    orbit: OrbitSpec
    stations: list[StationSpec] = Field(min_length=1, description="At least one station.")
    transmitter: TransmitterSpec
    channel: ChannelSpec
    receiver: ReceiverSpec
    background: BackgroundSpec
    protocol: ProtocolSpec
    security: SecuritySpec
    time: TimeSpec
    passes: PassSpec
    monte_carlo: MonteCarloSpec | None = Field(default=None, description="Optional ensemble.")
    multi_station: MultiStationSpec | None = Field(
        default=None, description="Optional aggregation options."
    )
    relay: RelaySpec | None = Field(default=None, description="Optional trusted-node relay.")

    @field_validator("schema_version")
    @classmethod
    def _supported(cls, value: int) -> int:
        """Refuse a file written for another schema rather than misread it."""
        if value != SCHEMA_VERSION:
            raise ValueError(
                f"schema_version {value} is not supported; this code reads version "
                f"{SCHEMA_VERSION}. Field meanings may differ between versions."
            )
        return value

    @model_validator(mode="after")
    def _consistent(self) -> Scenario:
        """Enforce the rules that span two sub-models."""
        names = [station.name for station in self.stations]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"station names must be unique, duplicated: {duplicates}.")
        if self.relay is not None:
            unknown = sorted({s for pair in self.relay.pairs for s in pair if s not in names})
            if unknown:
                raise ValueError(
                    f"relay.pairs name stations that do not exist: {unknown}. Stations: {names}."
                )
        if self.receiver.gate_s > self.transmitter.pulse_period_s:
            raise ValueError(
                f"receiver.gate_ns={self.receiver.gate_ns} exceeds the pulse period "
                f"{self.transmitter.pulse_period_s * 1e9} ns at transmitter.pulse_rate_hz="
                f"{self.transmitter.pulse_rate_hz}. One gate per pulse; wider gates overlap."
            )
        if self.background.is_tabulated:
            lo, hi = min(ITU_SKY_RADIANCE_WAVELENGTHS_M), max(ITU_SKY_RADIANCE_WAVELENGTHS_M)
            wavelength = self.transmitter.wavelength_m
            if not lo <= wavelength <= hi:
                raise ValueError(
                    f"background.condition is tabulated only for wavelengths "
                    f"{lo * 1e9:.0f}-{hi * 1e9:.0f} nm (ITU-R P.1621-2 Table 1); the transmitter "
                    f"is at {self.transmitter.wavelength_nm} nm. Give sky_radiance_w_m2_um_sr "
                    "instead."
                )
        return self

    @property
    def station_names(self) -> tuple[str, ...]:
        """Station names, in declaration order."""
        return tuple(station.name for station in self.stations)

    def station(self, name: str) -> StationSpec:
        """Return the station called ``name``.

        Raises
        ------
        KeyError
            If no station has that name.
        """
        for station in self.stations:
            if station.name == name:
                return station
        raise KeyError(f"no station named {name!r}; stations: {list(self.station_names)}.")

    def physics_dict(self) -> dict[str, Any]:
        """Return the JSON-mode dump with the label fields removed.

        The payload :mod:`quoss.scenario.hash` canonicalises: enums by value,
        the datetime as an ISO-8601 string, floats as floats.
        """
        return self.model_dump(mode="json", exclude={"name", "description"})


# --------------------------------------------------------------------------- #
# The union
# --------------------------------------------------------------------------- #
AnyScenario = Annotated[Scenario | HorizontalScenario, Field(discriminator="link")]
"""A scenario of either geometry, told apart by its ``link`` field.

What a discriminated union buys, over a union
---------------------------------------------
A plain ``Scenario | HorizontalScenario`` would make Pydantic try each member
and report the errors of both when neither validates -- so a downlink file with
one bad field would be refused with a message about ``path``, ``session`` and
``link`` as well, and the user would have to work out which half of the message
was about their file. With a discriminator, ``link`` picks the member first and
the errors are that member's only.

It also makes the tag **load-bearing rather than decorative**: the schema cannot
be entered without saying which geometry the file describes, so
``extra="forbid"`` is what refuses ``passes:`` in a horizontal file, by name,
before any physics runs.

Examples
--------
>>> from pydantic import TypeAdapter
>>> from quoss.scenario.defaults import ge1_two_terminals, reference_castelldefels
>>> adapter = TypeAdapter(AnyScenario)
>>> type(adapter.validate_python(reference_castelldefels().model_dump(mode="json"))).__name__
'Scenario'
>>> type(adapter.validate_python(ge1_two_terminals().model_dump(mode="json"))).__name__
'HorizontalScenario'

A horizontal file that carries a downlink section is refused by name:

>>> data = ge1_two_terminals().model_dump(mode="json")
>>> data["passes"] = {"minimum_elevation_deg": 10.0}
>>> adapter.validate_python(data)
Traceback (most recent call last):
    ...
pydantic_core._pydantic_core.ValidationError: 1 validation error for ...
horizontal.passes
  Extra inputs are not permitted...
"""
