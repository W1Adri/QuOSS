r"""Ground-station look angles: elevation, azimuth, slant range, Doppler, point-ahead.

This is where a satellite's position turns into what a telescope on the ground
actually points at. Everything above this module — :mod:`quoss.orbits.kepler`,
:mod:`quoss.orbits.perturbations`, :mod:`quoss.orbits.propagator`,
:mod:`quoss.orbits.tle` — answers "where is the satellite in space". This module
answers the question a ground station asks: *which way do I turn, how far is
it, and how fast is that distance changing.*

What "elevation" and "azimuth" mean, defended
-----------------------------------------------
A telescope has two axes: it turns left-right (**azimuth**, measured clockwise
from geographic north, 0-360 deg) and tilts up-down (**elevation**, 0 deg at
the horizon, 90 deg at the zenith). Both are defined against the **local
vertical** — the direction a plumb line hangs, which on an oblate Earth is not
the direction to the planet's centre. :func:`~quoss.orbits.frames.enu_from_itrf`
already builds exactly that local East-North-Up basis from the WGS-84 geodetic
normal; this module's whole job is to feed it the right vector (satellite minus
station, in a frame where both are expressed the same way) and read elevation,
azimuth and range off the three ENU components.

Why the satellite has to be rotated into ITRF first
-----------------------------------------------------
A :class:`~quoss.orbits.propagator.Trajectory` is expressed in
:attr:`~quoss.orbits.frames.Frame.TEME` — an inertial frame, fixed against the
stars. A ground station is fixed to the *rotating* Earth. Subtracting a
station's ITRF position from a satellite's TEME position would combine two
vectors from different frames and produce a number that means nothing — the
station would appear to sweep across the sky at the Earth's full rotation rate
even for a satellite sitting still, because the subtraction has smuggled the
planet's own spin into the result. :func:`~quoss.orbits.frames.teme_to_itrf_state`
is the one rotation, through GMST, that puts both vectors in the same
(Earth-fixed) frame before the subtraction happens; :func:`look_angles` does
this once per call and every quantity it returns — elevation, azimuth, range,
range-rate, point-ahead angle — comes from that single rotated vector, so
there is exactly one place a frame mistake could hide instead of five.

Why velocity-derived quantities use the *station's* rest frame
-----------------------------------------------------------------
Range-rate and the point-ahead angle both need a **relative** velocity. The
station's velocity in ITRF is exactly zero by construction — the whole point
of an Earth-fixed frame is that a point bolted to the ground does not move in
it — so "relative to the station" and "the satellite's ITRF velocity" are the
same vector, with no separate station-velocity term to add or forget. Doing
this in TEME instead would require explicitly adding back the station's
:math:`\omega \times r` term (the same one
:func:`~quoss.orbits.frames.teme_to_itrf_state` documents for the satellite),
which is exactly the kind of term a rushed implementation drops.

Doppler is deliberately *not* computed here
----------------------------------------------
This module stops at :attr:`LookAngles.range_rate_km_s` — a purely geometric
quantity, metres per second, that does not know what carrier wavelength a
terminal transmits on. :func:`doppler_shift_hz` turns a range-rate into a
frequency shift given a carrier frequency, and is kept as a separate one-line
function rather than a field on :class:`LookAngles`, for the same reason
:mod:`quoss.orbits.propagator` does not store a gravity model on
:class:`~quoss.orbits.propagator.Trajectory` (see that module's docstring):
the carrier frequency belongs to the optical terminal, a channel/system-layer
concept that does not exist yet in this package (``notes/ROADMAP.md`` stage
2.2), and folding it into an orbits-layer type would assert a dependency this
layer does not have.

The point-ahead angle, defended with the factor that is easy to get wrong
------------------------------------------------------------------------
Light takes a finite time :math:`\tau = R/c` to cross the slant range
:math:`R`. During that time the satellite moves, so a telescope that points at
the satellite's *apparent* (currently observed) position is not pointing where
the satellite will be when the transmitted beam arrives — nor is a beam
transmitted straight at that apparent position on course to be received back
along the same line by a co-located terminal, because *its* signal will have
moved too by the time it returns. The component of relative velocity that
matters is the one **transverse** to the line of sight — a purely radial
approach or recession does not change the pointing direction, only the range —
so the module projects the relative velocity onto the plane perpendicular to
the line of sight and keeps only that.

For a single one-way leg (ground telescope firing at a satellite that will
catch the photons after time :math:`\tau`), the target has moved
:math:`v_\perp \tau = v_\perp R / c`, an angle of :math:`v_\perp / c` as seen
from the source. This module reports **twice** that,
:math:`\text{PAA} = 2 v_\perp / c`, because a QKD ground segment is not a
one-way emitter: it is a monostatic terminal that must simultaneously transmit
along a lead-ahead path and receive along the line the light actually arrives
on, and those two paths diverge by the same angle in opposite senses — the
same doubling that appears in optical inter-satellite-link literature for a
bidirectional terminal. A caller building a one-way-only link (e.g. a beacon
the satellite only receives, never returns) uses ``point_ahead_angle_rad / 2``
and should say so at the call site; this module does not have enough
information about the link architecture to choose that for the caller, so it
picks the more common bidirectional case and names it.

Measured, not asserted: for a satellite reaching 67.1 deg elevation over
Castelldefels (CTTC's own station, 41.2750 deg N, 1.9875 deg E, 30 m) on a
700 km sun-synchronous orbit, ``tests/orbits/test_geometry.py::TestPointAheadAngle``
finds a point-ahead angle of **50.6 microradians** at that closest approach —
larger than the 35 microradian planning figure in ``notes/ROADMAP.md``,
because that figure did not carry the factor of 2 derived above. Both numbers
are bigger than the pointing jitter this project will eventually model, which
is the only claim the roadmap note was making.

Conventions in force
---------------------
Angles in radians, distances in km, velocities in km/s, absolute time a Julian
date in days (UTC), per ``docs/adr/0001-unit-conventions.md``. Every function
is vectorised over whatever axes a :class:`~quoss.orbits.propagator.Trajectory`
carries: :attr:`LookAngles` fields have shape ``(n_satellites, n_samples)``,
satellite-major, matching :attr:`~quoss.orbits.propagator.Trajectory.r_km`.

References
----------
.. [1] Vallado, *Fundamentals of Astrodynamics and Applications*, 4th ed.,
       2013, Section 4.4 ("Topocentric Coordinates"): elevation/azimuth from a
       range vector in a topocentric frame.
.. [2] Degnan, "Millimeter Accuracy Satellite Laser Ranging: A Review", in
       *Contributions of Space Geodesy to Geodynamics: Technology*, AGU
       Geodynamics Series vol. 25, 1993 — the point-ahead angle for a
       bidirectional optical terminal and its factor of 2.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quoss.core.constants import SPEED_OF_LIGHT_M_S
from quoss.core.errors import DomainError
from quoss.core.types import FloatArray, FloatLike, frozen_view
from quoss.core.units import km_to_m, m_to_km
from quoss.orbits._validation import as_1d
from quoss.orbits.frames import Frame, enu_from_itrf, geodetic_to_itrf, gmst_rad, teme_to_itrf_state
from quoss.orbits.propagator import Trajectory

__all__ = [
    "LookAngles",
    "doppler_shift_hz",
    "look_angles",
]

_TWO_PI = 2.0 * np.pi
_SPEED_OF_LIGHT_KM_S = m_to_km(SPEED_OF_LIGHT_M_S)
# Doubled for a monostatic (transmit + receive) terminal — see the module
# docstring's "point-ahead angle" section for the derivation and the measured
# example that motivates keeping it, rather than the single-leg v_perp / c.
_POINT_AHEAD_FACTOR = 2.0


@dataclass(frozen=True, eq=False, slots=True)
class LookAngles:
    """Topocentric look angles and their rates, one set per satellite per sample.

    What :func:`look_angles` returns. Every field has shape
    ``(n_satellites, n_samples)`` — satellite-major, the same convention
    :class:`~quoss.orbits.propagator.Trajectory` uses for its ``(S, n, 3)``
    position array with the vector axis dropped, since a look angle is already
    a scalar per satellite per sample rather than a 3-vector.

    Parameters
    ----------
    elevation_rad : FloatArray
        Angle above the local horizon, radians. Negative when the satellite is
        below the horizon — this module does not filter on visibility, that is
        ``system/passes.py`` (``notes/ROADMAP.md`` stage 3), a downstream
        decision about *which* elevations count as a usable pass.
    azimuth_rad : FloatArray
        Compass bearing to the satellite, radians, measured clockwise from
        geographic north and wrapped to ``[0, 2 pi)``. Degenerate (arbitrary)
        exactly at the zenith and nadir, where the horizontal displacement is
        zero; not treated as an error, since a satellite passing directly
        overhead is an ordinary case a caller must be able to receive a result
        for.
    range_km : FloatArray
        Straight-line (slant) distance from station to satellite, km. Always
        positive.
    range_rate_km_s : FloatArray
        Rate of change of ``range_km``, km/s. Positive when the satellite is
        receding, negative when approaching — the sign :func:`doppler_shift_hz`
        is written against.
    point_ahead_angle_rad : FloatArray
        Angle a monostatic terminal must lead its transmit beam by, radians.
        See the module docstring for the derivation and the factor of 2.

    Raises
    ------
    DomainError
        If the fields disagree in shape.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.types import TimeGrid
    >>> from quoss.orbits.kepler import ClassicalElements
    >>> from quoss.orbits.propagator import PropagationMethod, propagate
    >>> coe = ClassicalElements.from_semi_major_axis(
    ...     semi_major_axis_km=7078.137,
    ...     eccentricity=0.001,
    ...     inclination_rad=np.deg2rad(98.19),
    ...     raan_rad=np.deg2rad(30.0),
    ...     argp_rad=0.0,
    ...     true_anomaly_rad=np.deg2rad(275.0),
    ... )
    >>> grid = TimeGrid.uniform(epoch_jd=2460676.5, duration_s=60.0, step_s=60.0)
    >>> traj = propagate(coe, grid, method=PropagationMethod.TWO_BODY)
    >>> angles = look_angles(
    ...     traj,
    ...     station_latitude_rad=np.deg2rad(41.2750),
    ...     station_longitude_rad=np.deg2rad(1.9875),
    ...     station_altitude_km=0.030,
    ... )
    >>> angles.elevation_rad.shape
    (1, 2)
    """

    elevation_rad: FloatArray
    azimuth_rad: FloatArray
    range_km: FloatArray
    range_rate_km_s: FloatArray
    point_ahead_angle_rad: FloatArray

    def __post_init__(self) -> None:
        """Check every field against the first one, then freeze the arrays."""
        shape = self.elevation_rad.shape
        for name in ("azimuth_rad", "range_km", "range_rate_km_s", "point_ahead_angle_rad"):
            value = getattr(self, name)
            if value.shape != shape:
                raise DomainError(
                    f"LookAngles.{name} has shape {value.shape}, but elevation_rad has "
                    f"{shape}; every field describes the same (satellite, sample) grid."
                )
        for name in (
            "elevation_rad",
            "azimuth_rad",
            "range_km",
            "range_rate_km_s",
            "point_ahead_angle_rad",
        ):
            object.__setattr__(self, name, frozen_view(getattr(self, name)))

    @property
    def n_satellites(self) -> int:
        """Number of satellites, the leading axis of every field."""
        return int(self.elevation_rad.shape[0])

    @property
    def n_samples(self) -> int:
        """Number of time samples, the trailing axis of every field."""
        return int(self.elevation_rad.shape[1])

    def __repr__(self) -> str:
        return f"LookAngles(n_satellites={self.n_satellites}, n_samples={self.n_samples})"


def _teme_trajectory_to_itrf(trajectory: Trajectory) -> tuple[FloatArray, FloatArray]:
    """Rotate every state in ``trajectory`` from TEME into ITRF.

    Flattens the ``(S, n, 3)`` arrays to ``(S * n, 3)`` before calling
    :func:`~quoss.orbits.frames.teme_to_itrf_state`, which only knows about a
    single ``(n, 3)`` block, and tiles GMST — a function of time alone, not of
    which satellite — to match. Reshaping back afterwards is the only place
    the satellite axis re-appears; every function downstream of this one works
    on a plain ``(S, n, 3)`` array as if it had been rotated one satellite at a
    time, without the loop.
    """
    n_satellites, n_samples, _ = trajectory.r_km.shape
    theta_rad = gmst_rad(trajectory.grid.jd)
    theta_tiled = np.tile(theta_rad, n_satellites)
    r_flat = trajectory.r_km.reshape(n_satellites * n_samples, 3)
    v_flat = trajectory.v_km_s.reshape(n_satellites * n_samples, 3)
    r_itrf_flat, v_itrf_flat = teme_to_itrf_state(r_flat, v_flat, theta_tiled)
    r_itrf = r_itrf_flat.reshape(n_satellites, n_samples, 3)
    v_itrf = v_itrf_flat.reshape(n_satellites, n_samples, 3)
    return r_itrf, v_itrf


def look_angles(
    trajectory: Trajectory,
    station_latitude_rad: FloatLike,
    station_longitude_rad: FloatLike,
    station_altitude_km: FloatLike = 0.0,
) -> LookAngles:
    r"""Elevation, azimuth, range, range-rate and point-ahead angle from a station.

    Parameters
    ----------
    trajectory : Trajectory
        Satellite states, in :attr:`~quoss.orbits.frames.Frame.TEME` — what
        every propagator in this package (:func:`~quoss.orbits.propagator.propagate`
        and :func:`~quoss.orbits.tle.propagate_tle` alike) produces, per
        ``notes/ROADMAP.md`` 2.1.6's note that this module must not have to
        branch on where the trajectory came from.
    station_latitude_rad : float or FloatArray
        Station geodetic latitude, radians, in ``[-pi/2, pi/2]``. A scalar (or
        a length-1 array): one station per call, the same restriction
        :func:`~quoss.orbits.frames.geodetic_to_itrf` places on a single site.
        Selecting or aggregating several stations is
        ``system/multi_ogs.py`` (stage 3), not this module.
    station_longitude_rad : float or FloatArray
        Station longitude, radians, positive east.
    station_altitude_km : float or FloatArray, optional
        Height above the WGS-84 ellipsoid, km. Defaults to sea level.

    Returns
    -------
    LookAngles
        One elevation/azimuth/range/range-rate/point-ahead value per satellite
        per sample.

    Raises
    ------
    DomainError
        If ``trajectory.frame`` is not TEME, if the station coordinates are not
        scalar, or if any computed range is exactly zero (the satellite
        coincides with the station, which is not a physical ground-to-orbit
        geometry).

    Notes
    -----
    See the module docstring for why the TEME to ITRF rotation happens before
    anything else, why range-rate and the point-ahead angle need no separate
    station-velocity term, and for the derivation and factor of 2 in the
    point-ahead angle.

    Examples
    --------
    A satellite placed exactly on the station's zenith normal — the geodetic
    "up" direction, built here in ITRF where that direction is exact — reads
    elevation 90 deg:

    >>> import numpy as np
    >>> from quoss.core.types import TimeGrid
    >>> from quoss.orbits.frames import Frame, geodetic_to_itrf, gmst_rad, itrf_to_teme_state
    >>> from quoss.orbits.propagator import PropagationMethod, Trajectory
    >>> station_lat, station_lon = np.deg2rad(41.2750), np.deg2rad(1.9875)
    >>> up = np.array(
    ...     [
    ...         np.cos(station_lat) * np.cos(station_lon),
    ...         np.cos(station_lat) * np.sin(station_lon),
    ...         np.sin(station_lat),
    ...     ]
    ... )
    >>> station_r_itrf_km = geodetic_to_itrf(station_lat, station_lon, 0.030)[0]
    >>> r_itrf_km = station_r_itrf_km + 700.0 * up  # 700 km straight up
    >>> epoch_jd = 2460676.5
    >>> theta = gmst_rad(np.array([epoch_jd, epoch_jd]))
    >>> r_teme, v_teme = itrf_to_teme_state(np.tile(r_itrf_km, (2, 1)), np.zeros((2, 3)), theta)
    >>> grid = TimeGrid.uniform(epoch_jd=epoch_jd, duration_s=1.0, n=2)
    >>> traj = Trajectory(
    ...     r_km=r_teme[np.newaxis, :, :],
    ...     v_km_s=v_teme[np.newaxis, :, :],
    ...     grid=grid,
    ...     frame=Frame.TEME,
    ...     method=PropagationMethod.TWO_BODY,
    ... )
    >>> angles = look_angles(traj, station_lat, station_lon, 0.030)
    >>> float(np.round(np.rad2deg(angles.elevation_rad[0, 0]), 6))
    90.0
    """
    if trajectory.frame is not Frame.TEME:
        raise DomainError(
            f"look_angles received a trajectory in frame {trajectory.frame!r}, but every "
            f"propagator in this package produces TEME (see the module docstring for why "
            f"the rotation into ITRF happens inside this function). A trajectory in another "
            f"frame is not one this project's propagators can have produced."
        )
    lat = as_1d("station_latitude_rad", station_latitude_rad)
    lon = as_1d("station_longitude_rad", station_longitude_rad)
    alt = as_1d("station_altitude_km", station_altitude_km)
    for name, value in (
        ("station_latitude_rad", lat),
        ("station_longitude_rad", lon),
        ("station_altitude_km", alt),
    ):
        if value.size != 1:
            raise DomainError(
                f"{name} must be a single scalar: look_angles computes one station's view. "
                f"See system/multi_ogs.py (notes/ROADMAP.md stage 3) for several stations."
            )

    n_satellites, n_samples, _ = trajectory.r_km.shape
    r_itrf, v_itrf = _teme_trajectory_to_itrf(trajectory)

    station_r_itrf_km = geodetic_to_itrf(lat, lon, alt)[0]
    # Broadcasts (3,) against (S, n, 3): the station is one fixed point shared
    # by every satellite and every sample.
    vector_itrf_km = r_itrf - station_r_itrf_km
    range_km = np.linalg.norm(vector_itrf_km, axis=-1)
    if np.any(range_km <= 0.0):
        raise DomainError(
            "look_angles found a satellite coincident with the station (range = 0), "
            "which is not a physical ground-to-orbit geometry."
        )

    enu_km = enu_from_itrf(vector_itrf_km.reshape(n_satellites * n_samples, 3), lat, lon).reshape(
        n_satellites, n_samples, 3
    )
    east_km, north_km, up_km = enu_km[..., 0], enu_km[..., 1], enu_km[..., 2]
    horizontal_km = np.hypot(east_km, north_km)
    elevation_rad = np.arctan2(up_km, horizontal_km)
    azimuth_rad = np.mod(np.arctan2(east_km, north_km), _TWO_PI)

    # The satellite's ITRF velocity *is* the velocity relative to the station:
    # a point fixed on the ground has zero ITRF velocity by construction, so
    # there is no separate station-velocity term to add. See the module
    # docstring's "Why velocity-derived quantities use the station's rest
    # frame" section.
    unit_los = vector_itrf_km / range_km[..., np.newaxis]
    range_rate_km_s = np.sum(v_itrf * unit_los, axis=-1)
    transverse_velocity_km_s = v_itrf - range_rate_km_s[..., np.newaxis] * unit_los
    transverse_speed_km_s = np.linalg.norm(transverse_velocity_km_s, axis=-1)
    point_ahead_angle_rad = _POINT_AHEAD_FACTOR * transverse_speed_km_s / _SPEED_OF_LIGHT_KM_S

    return LookAngles(
        elevation_rad=np.asarray(elevation_rad, dtype=np.float64),
        azimuth_rad=np.asarray(azimuth_rad, dtype=np.float64),
        range_km=np.asarray(range_km, dtype=np.float64),
        range_rate_km_s=np.asarray(range_rate_km_s, dtype=np.float64),
        point_ahead_angle_rad=np.asarray(point_ahead_angle_rad, dtype=np.float64),
    )


def doppler_shift_hz(range_rate_km_s: FloatArray, carrier_frequency_hz: float) -> FloatArray:
    r"""First-order Doppler shift of a carrier, from a geometric range-rate.

    .. math::

        \Delta f = -f_0 \frac{\dot{R}}{c}

    Parameters
    ----------
    range_rate_km_s : FloatArray
        Rate of change of slant range, km/s — :attr:`LookAngles.range_rate_km_s`.
        Positive for a receding satellite.
    carrier_frequency_hz : float
        Nominal (unshifted) carrier frequency, Hz. A 1550 nm laser is about
        1.934e14 Hz; this function takes the frequency, not the wavelength,
        because the shift it returns is linear in frequency and a caller
        converting a wavelength first would need this module's speed-of-light
        constant to do it, duplicating what :mod:`quoss.core.constants`
        already provides.

    Returns
    -------
    FloatArray
        Frequency shift, Hz. Negative — a redshift, lower received frequency —
        for a receding satellite; positive for an approaching one.

    Raises
    ------
    DomainError
        If ``carrier_frequency_hz`` is not finite and positive.

    Notes
    -----
    First order in :math:`\dot{R}/c` only. At LEO range-rates (at most the
    orbital speed, ~7.8 km/s), :math:`\dot{R}/c \sim 2.6\times10^{-5}`, so the
    relativistic correction this drops is
    :math:`O((\dot{R}/c)^2) \sim 7\times10^{-10}` relative — for a 1550 nm
    carrier (1.934e14 Hz) that is under 0.15 Hz against a first-order shift of
    several GHz, negligible next to any oscillator's own stability.

    Examples
    --------
    A satellite receding at 1 km/s redshifts a 1550 nm carrier by about
    645 MHz:

    >>> import numpy as np
    >>> shift = doppler_shift_hz(np.array([1.0]), 1.934e14)
    >>> float(np.round(shift[0] / 1e6, 1))
    -645.1
    """
    if not (np.isfinite(carrier_frequency_hz) and carrier_frequency_hz > 0.0):
        raise DomainError(
            f"carrier_frequency_hz must be finite and positive, got {carrier_frequency_hz!r}."
        )
    range_rate_km_s = np.asarray(range_rate_km_s, dtype=np.float64)
    if not np.all(np.isfinite(range_rate_km_s)):
        raise DomainError("range_rate_km_s contains non-finite values.")
    range_rate_m_s = km_to_m(range_rate_km_s)
    return np.asarray(-range_rate_m_s / SPEED_OF_LIGHT_M_S * carrier_frequency_hz, dtype=np.float64)
