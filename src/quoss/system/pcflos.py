r"""Cloud: the probability that a pass happens at all, and what several sites buy.

What "pCFLOS" is, for a reader who has not met the acronym
-----------------------------------------------------------
An optical link needs a straight line from the telescope to the satellite with
no cloud on it. Cloud is not an attenuation term like the atmosphere of
:mod:`quoss.channel` — a thin cirrus costs tens of decibels and a cumulus costs
everything — so the honest model is binary: either the line of sight is clear
and the pass exists, or it is not and the pass does not. The **probability of a
cloud-free line of sight**, pCFLOS, is the probability of the first case. It is
a number in ``[0, 1]`` attached to a place, a time, and (in principle) a
direction.

Everything downstream should read it as **the probability that the pass
exists**, never as a factor on the key. Multiplying a key volume by 0.7 turns
"works on 70 % of nights" into "delivers 70 % of the key every night", and those
are different systems: the first stores key against dry spells, the second does
not need to. :mod:`quoss.system.key_volume` refuses to do that multiplication
and this module is where the probability lives instead.

Where the number comes from, and the one case where it is exact
---------------------------------------------------------------
The input this module takes is a **cloud fraction** ``f``: the fraction of the
sky, seen from above, that cloud covers. It is what a weather archive gives —
Open-Meteo's ERA5 ``cloud_cover`` is exactly this, in percent, one value per
hour per grid cell — and it is what a climatology table gives as a monthly
mean. For a *vertical* line of sight the conversion is not a model but a
definition: cover fraction is the fraction of the cell's area a vertical line
hits cloud in, so a random vertical line is clear with probability

.. math::

    p_\text{CFLOS}(\text{zenith}) = 1 - f .

:func:`cloud_free_probability` returns that, and nothing else.

The gap, declared: no elevation dependence
-------------------------------------------
A satellite is not at the zenith. At 10 degrees of elevation a line of sight
runs through a cloud layer for ``1 / sin(10 deg) = 5.8`` times the vertical
distance, so it crosses several times the horizontal extent of cloud that a
vertical line does, and the probability of threading between the cells is
lower. The classical measurement of that effect is Lund & Shanklin's, from
whole-sky photographs (I. A. Lund and M. D. Shanklin, "Photogrammetrically
determined cloud-free lines-of-sight through the atmosphere", *J. Appl.
Meteorol.* **11**, 773-782, 1972, and "Universal methods for estimating
probabilities of cloud-free lines-of-sight through the atmosphere", *J. Appl.
Meteorol.* **12**, 28-35, 1973). **Neither paper could be opened** when this
module was written — the publisher's pages refuse the request — so under the
citation policy of ``docs/adr/0009-citation-policy.md`` no number from them is
transcribed here, because a number recalled from memory and labelled with a
table number is exactly the failure that policy exists to prevent.

The consequence is structural rather than a comment: **no function in this
module accepts an elevation**, and ``tests/system/test_pcflos.py`` asserts that
by absence, the same negative control :mod:`quoss.channel.background` has for
its sky radiance. :func:`cloud_free_probability` records a warning on every
call saying that the value it returns is the zenith one, and in which direction
that is wrong: for a single cloud layer a slant line can only meet *more* cloud
than a vertical one, so ``1 - f`` is an **upper bound** on the true pCFLOS at
any elevation and exact only at the zenith.

What a geometric model would need, and why guessing is worse than not having
it: to turn ``f`` into a slant-path probability one needs the cloud **base
height** (how far the line travels inside the layer) and the **cell size** (how
far it travels between clouds), and the answer is sensitive to both — the same
``f = 0.5`` can be one continuous sheet, which a slant line meets with
probability 0.5 like a vertical one, or a field of small cumulus, which a line
at 10 degrees can hardly miss. Neither quantity is in a cloud-fraction archive.
A guessed pair would produce a plausible elevation curve with an error nobody
could bound, and the number that comes out would then be quoted with the
elevation attached, as if it were measured.

Availability of a pass: three readings of an hourly series
----------------------------------------------------------
A cloud archive is hourly; a pass is ten minutes. :func:`pass_availability`
interpolates the series **linearly** onto the pass grid — a modelling choice,
recorded in the log on every call, and the only one defensible without a
sub-hourly cloud model — and then has to say which value of the interpolant
"the pass" gets. Three candidates, each returned on request through
:class:`AvailabilityRule`:

- **the value at culmination**, a point estimate at the instant that matters
  most for the link;
- **the dwell-weighted mean over the window**, the expected fraction of the
  pass's instants that are clear;
- **the minimum over the window**, the pessimistic reading, which is what a
  pass needs if a single blocked minute aborts the block.

None of the three is "the" availability, because the true quantity — the
probability that the *whole* pass is clear — needs the space-time correlation
of the cloud field over ten minutes, which an hourly archive does not contain.
What the hourly resolution does guarantee is that the three cannot differ by
much: over a 10-minute window a linear interpolant of an hourly series moves by
at most a sixth of the hour-to-hour change. Measured in
``tests/system/test_pcflos.py::TestTheThreeReadingsOfAnHourlySeries`` on a
synthetic front (cover rising from 0.05 to 0.95 in three hours and falling
back, the reference day's four passes): the largest spread between any two of
the three readings over any pass is **0.023** in probability, against a
day-to-day range of 0.9, and the derived ceiling — the front's 0.3 per hour
times the longest pass, 562 s — is 0.047. The mean and the culmination value
agree to 1e-4; it is the minimum that sits apart, by the slope times half a
pass. The default is the mean, because it is the only one of
the three that is an expectation of something (the fraction of clear instants);
the spread against the other two travels in the log entry so that a caller who
wanted the minimum can see what the choice cost.

Site diversity: what a second station buys, and what is not known about it
---------------------------------------------------------------------------
Two stations far enough apart see different clouds, and the pass over the
second exists when the first is blocked. If the two were **independent**, the
probability that at least one is clear would be

.. math::

    P_\text{ind} = 1 - \prod_i (1 - p_i),

which is an **upper bound** on availability: real cloud fields are correlated
over hundreds of kilometres, and correlation only makes "both blocked" more
likely. The other extreme, **perfect correlation** (the same weather everywhere,
so the clearer station is clear whenever the cloudier one is), gives
``max_i p_i`` — a **lower bound** for any non-negative correlation, since the
union of events contains each of them.

Between the two, the usual parametrisation is a pairwise correlation that
decays with separation, ``rho_ij = exp(-d_ij / L)``. For **two** stations that
is enough: two Bernoulli variables with given marginals and given correlation
have exactly one joint law, and

.. math::

    P(\text{both cloudy}) = q_1 q_2 + \rho \sqrt{p_1 q_1 p_2 q_2},
    \qquad q_i = 1 - p_i,

so :func:`joint_cloud_free_probability` returns ``1`` minus that, exactly.
**Not every** ``rho`` is compatible with every pair of marginals: a Bernoulli
pair cannot be more correlated than ``sqrt(min(p_1 q_2, p_2 q_1) /
max(p_1 q_2, p_2 q_1))``, which is 1 when the marginals are equal and 0.22 when
they are 0.9 and 0.3. Two close stations with very different climatologies and
a correlation model that says 0.9 are therefore an inconsistent input, and the
function raises rather than clipping, because a clipped correlation is a
substituted model with no record.

For **three or more** stations the pairwise correlations do *not* determine
the joint law — there are ``2^N - 1`` free probabilities and only ``N(N-1)/2``
correlations — so no exact answer exists to compute. The function returns the
two bounds, names the gap in the log, and leaves ``exact`` as ``None``. A
Gaussian-copula construction would fill it with a specific choice; it is not
made here because nothing verified says it is the right one, and a filled gap
with no citation is a number that will be quoted.

The decorrelation length ``L`` has **no default**. It is the whole content of
the correlation model and no source verified for this project publishes a
value; a caller who has one writes it, and a caller who does not gets a
``TypeError`` instead of a plausible answer.

Distance between stations
-------------------------
:func:`station_separation_km` is the arc length on a sphere of the WGS-84 mean
radius, obtained from the **chord** between the two sites computed through
:func:`~quoss.orbits.frames.geodetic_to_itrf` — the same ellipsoid the rest of
the project puts its stations on — rather than from a spherical formula applied
to geodetic latitudes. The difference is of the order of the flattening,
``1/298``, which is far below anything a cloud correlation length could
resolve; the reason to go through the ellipsoid anyway is that it is the one
place a station's position is already defined, so there is no second
convention to disagree with the first. ``tests/system/test_pcflos.py::
TestStationSeparation`` checks it against the haversine formula as the
independent computation (V3), to within that flattening.

What this module deliberately does not do
-----------------------------------------
- **Read a weather archive.** Fetching Open-Meteo is ``io/openmeteo.py``, which
  is injected from above; this module takes arrays.
- **Convert a cloud fraction into an attenuation.** A cloud is not a loss term
  here; a partially transmitting thin cloud is a different, unmodelled regime.
- **Depend on elevation, azimuth, or season.** See the gap above.
- **Decide which station to use.** ``multi_ogs.py`` consumes these
  probabilities; this module produces them.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``f``                                   cloud cover fraction, in ``[0, 1]``
``p``                                   probability of a cloud-free line of
                                        sight, ``1 - f`` at the zenith
``q``                                   ``1 - p``, probability of cloud
``rho_ij``                              correlation of the clear/cloudy
                                        indicators of stations ``i`` and ``j``
``d_ij``                                separation of the stations (km)
``L``                                   decorrelation length (km)
======================================  ====================================

References
----------
I. A. Lund and M. D. Shanklin, "Photogrammetrically determined cloud-free
lines-of-sight through the atmosphere", *J. Appl. Meteorol.* **11**(5),
773-782, 1972; and "Universal methods for estimating probabilities of
cloud-free lines-of-sight through the atmosphere", *J. Appl. Meteorol.*
**12**(1), 28-35, 1973. **Cited as the source that would close the elevation
gap, not as a source of any number here: neither could be opened.**
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

import numpy as np

from quoss.core.constants import (
    SECONDS_PER_DAY,
    WGS84_RADIUS_EQUATORIAL_KM,
    WGS84_RADIUS_POLAR_KM,
)
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray, TimeGrid, frozen_copy
from quoss.orbits.frames import geodetic_to_itrf
from quoss.system.passes import PassTable

__all__ = [
    "WGS84_MEAN_RADIUS_KM",
    "AvailabilityRule",
    "JointCloudFreeProbability",
    "cloud_free_probability",
    "joint_cloud_free_probability",
    "pass_availability",
    "station_separation_km",
]

WGS84_MEAN_RADIUS_KM: Final[float] = (
    2.0 * WGS84_RADIUS_EQUATORIAL_KM + WGS84_RADIUS_POLAR_KM
) / 3.0
"""``(2a + b) / 3 = 6371.0088 km``, the mean radius of the WGS-84 ellipsoid.

The sphere on which :func:`station_separation_km` reports an arc. Derived from
the two axes in :mod:`quoss.core.constants` rather than typed, so that it can
only disagree with the ellipsoid the stations sit on by the definition of a
mean.
"""

_CORRELATION_FEASIBILITY_SLACK: Final[float] = 1e-12
"""Tolerance on the Fréchet bound of the two-station correlation.

The bound ``sqrt(min / max)`` is exactly 1 for equal marginals, and a caller who
passes the same ``p`` twice with ``rho = exp(-0 / L) = 1`` is asking for
precisely that edge; one unit in the last place of rounding must not turn a
legitimate call into a ``DomainError``.
"""


class AvailabilityRule(StrEnum):
    """Which value of the interpolated cloud series a pass is assigned.

    See the module docstring for why there are three and why none is "the"
    availability. A :class:`~enum.StrEnum` so that a scenario file can name one
    in plain text and the physics compares against a member.

    Attributes
    ----------
    MEAN
        Dwell-weighted mean of the cloud-free probability over the pass window,
        using the midpoint dwell times of
        :meth:`~quoss.system.passes.PassTable.samples`. The expected fraction of
        the pass's instants that are clear. The default of
        :func:`pass_availability`.
    CULMINATION
        The value at the refined culmination instant.
    MINIMUM
        The minimum over the window: the pessimistic reading, appropriate when
        one blocked minute aborts the block.
    """

    MEAN = "mean"
    CULMINATION = "culmination"
    MINIMUM = "minimum"


def _validated_cloud_fraction(name: str, value: FloatArray | float) -> FloatArray:
    """Return a cloud fraction as an array, rejecting anything outside ``[0, 1]``."""
    fraction = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(fraction)):
        raise DomainError(f"{name} contains non-finite values.")
    if fraction.size and (np.any(fraction < 0.0) or np.any(fraction > 1.0)):
        raise DomainError(
            f"{name} must lie in [0, 1], got range [{float(fraction.min())}, "
            f"{float(fraction.max())}]. It is a cover FRACTION: a weather archive that reports "
            "cloud cover in percent (Open-Meteo's ERA5 cloud_cover does) must be divided by "
            "100 before it gets here, and a value of 50 is that mistake, not a half-covered "
            "sky."
        )
    return fraction


def _validated_probability(name: str, value: FloatArray | float) -> FloatArray:
    """Return a probability array in ``[0, 1]``, or raise."""
    probability = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(probability)):
        raise DomainError(f"{name} contains non-finite values.")
    if probability.size and (np.any(probability < 0.0) or np.any(probability > 1.0)):
        raise DomainError(
            f"{name} must lie in [0, 1], got range [{float(probability.min())}, "
            f"{float(probability.max())}]. It is a probability of a cloud-free line of sight, "
            "which is what cloud_free_probability returns."
        )
    return probability


def cloud_free_probability(
    cloud_fraction: FloatArray | float, *, degradations: DegradationLog
) -> FloatArray:
    """Return the zenith probability of a cloud-free line of sight, ``1 - f``.

    Exact for a vertical line of sight, by the definition of cover fraction
    (see the module docstring), and an **upper bound** for any other direction:
    a slant line through a cloud layer meets at least as much cloud as a
    vertical one. That is the whole model, and its incompleteness is recorded
    rather than patched — there is no elevation argument because the published
    dependence (Lund & Shanklin 1972, 1973) could not be opened to transcribe,
    and a curve from memory would be a number with a citation it does not have.

    Parameters
    ----------
    cloud_fraction : FloatArray or float
        Cloud cover fraction ``f`` in ``[0, 1]``. Any shape: a scalar
        climatology, or a series over a time axis.
    degradations : DegradationLog
        Receives one ``WARNING`` per call, ``pcflos.no-elevation-dependence``,
        stating that the returned value is the zenith one and is optimistic at
        any lower elevation.

    Returns
    -------
    FloatArray
        ``1 - f``, shaped like the input.

    Raises
    ------
    DomainError
        If any value is non-finite or outside ``[0, 1]`` — in particular a
        percentage that was never divided by 100.

    Examples
    --------
    A sky four-tenths covered is clear along a vertical line six times in ten:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> float(cloud_free_probability(0.4, degradations=log))
    0.6
    >>> [entry.code for entry in log]
    ['pcflos.no-elevation-dependence']

    Vectorised over a series, one warning per call and not per sample:

    >>> import numpy as np
    >>> log = DegradationLog()
    >>> cloud_free_probability(np.array([0.0, 0.25, 1.0]), degradations=log)
    array([1.  , 0.75, 0.  ])
    >>> len(log)
    1

    A percentage is refused, because 50 is not a fraction of anything:

    >>> cloud_free_probability(50.0, degradations=log)
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: cloud_fraction must lie in [0, 1], got range [50.0, 50.0]. ...
    """
    fraction = _validated_cloud_fraction("cloud_fraction", cloud_fraction)
    degradations.warn(
        "pcflos.no-elevation-dependence",
        "the cloud-free probability returned is the ZENITH value 1 - f. It is exact for a "
        "vertical line of sight and an upper bound at any lower elevation, where a slant path "
        "crosses more cloud; the size of the overestimate is not modelled because the "
        "published elevation dependence (Lund & Shanklin 1972, 1973) could not be opened to "
        "transcribe, and a geometric model would need a cloud base height and a cell size "
        "that no cloud-fraction archive provides. Treat every availability built on this as "
        "optimistic on low passes.",
        where="quoss.system.pcflos.cloud_free_probability",
        n_values=int(fraction.size),
        max_cloud_fraction=float(fraction.max()) if fraction.size else None,
    )
    probability: FloatArray = 1.0 - fraction
    return probability


def _series_on_pass_axis(grid: TimeGrid, table: PassTable) -> FloatArray:
    """Return the cloud grid's instants as seconds from the pass grid's epoch.

    The two grids carry their own epochs, and a cloud series fetched for a
    calendar day starts at midnight while a pass grid starts wherever the
    scenario says. Reconciling them once here, through the absolute Julian
    dates both carry, is what makes "does the series cover the pass" a
    comparison of two numbers on the same axis.
    """
    offset_s = (grid.epoch_jd - table.grid.epoch_jd) * SECONDS_PER_DAY
    axis: FloatArray = np.asarray(grid.t_s, dtype=np.float64) + offset_s
    return axis


def pass_availability(
    cloud_fraction_series: FloatArray,
    *,
    grid: TimeGrid,
    table: PassTable,
    degradations: DegradationLog,
    rule: AvailabilityRule = AvailabilityRule.MEAN,
) -> FloatArray:
    """Return the cloud-free probability of each pass, from a cloud series.

    What it computes
    ----------------
    The cloud series lives on its own, usually hourly, grid. It is turned into
    a zenith cloud-free probability by :func:`cloud_free_probability`,
    interpolated **linearly** onto the pass grid's time axis, and read once per
    pass according to ``rule``: the dwell-weighted mean over the refined pass
    window, the value at culmination, or the minimum over the window. All three
    are computed on every call and the spread between them is written to the
    log, so the choice travels with its cost.

    Why linear interpolation, and why it is recorded
    ------------------------------------------------
    ERA5 is hourly and a pass is ten minutes, so *some* rule has to say what
    the cover was at 03:07 when the archive gives 03:00 and 04:00. Linear is
    the only rule that adds no structure the data does not have — a spline
    would invent a sub-hourly curve, a step would invent a discontinuity at the
    hour. It is still a modelling choice, so every call records it as an
    ``INFO`` entry (``pcflos.pass-availability-rule``) with the series step.

    Why the mean is the default
    ---------------------------
    It is the one reading of the three that is an expectation of something —
    the fraction of the pass's instants with a clear line of sight. The
    minimum is what a pass needs if one blocked minute aborts the whole block;
    the culmination value is the point estimate at the instant of best link.
    The module docstring measures how far apart they can be at hourly
    resolution: 0.023 at most across the reference day under a synthetic front.
    The dwell-weighted mean is the midpoint quadrature of
    :meth:`~quoss.system.passes.PassTable.samples`, which is *exact* for a
    linear function on every cell that does not straddle an hourly knot, so the
    quadrature error is confined to at most one cell per knot inside the pass.

    Parameters
    ----------
    cloud_fraction_series : FloatArray
        Cloud cover fraction at each sample of ``grid``, shape ``(grid.n,)``,
        in ``[0, 1]``.
    grid : TimeGrid
        The axis of the series. Its epoch may differ from the pass grid's; the
        two are reconciled through their Julian dates.
    table : PassTable
        The passes, from :func:`~quoss.system.passes.find_passes`.
    degradations : DegradationLog
        Receives the warning of :func:`cloud_free_probability` and the ``INFO``
        entry naming the rule, the interpolation and the spread.
    rule : AvailabilityRule, optional
        Which reading to return. Defaults to :attr:`AvailabilityRule.MEAN`.

    Returns
    -------
    FloatArray
        One probability per pass, shape ``(table.n_passes,)``, in ``[0, 1]``.

    Raises
    ------
    DomainError
        If the series does not have one value per sample of ``grid``, if any
        value is outside ``[0, 1]``, or if the series does not **cover** every
        pass window — extrapolating a cloud series would be inventing weather,
        and :func:`numpy.interp` would do it silently.

    Examples
    --------
    An hourly series that clears from a fully covered midnight to a clear
    afternoon, on the reference day. The four passes start at about 07:08,
    08:47, 18:13 and 19:53 UTC:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.types import TimeGrid
    >>> from quoss.system.passes import _reference_table
    >>> table = _reference_table()
    >>> hourly = TimeGrid.uniform(epoch_jd=table.grid.epoch_jd, duration_s=86_400.0, step_s=3600.0)
    >>> cover = np.clip(1.0 - hourly.t_s / 43_200.0, 0.0, 1.0)  # clear by noon
    >>> log = DegradationLog()
    >>> np.round(pass_availability(cover, grid=hourly, table=table, degradations=log), 3)
    array([0.602, 0.737, 1.   , 1.   ])
    >>> sorted({entry.code for entry in log})
    ['pcflos.no-elevation-dependence', 'pcflos.pass-availability-rule']

    A series that stops before the last pass is refused rather than extended:

    >>> short = TimeGrid.uniform(epoch_jd=table.grid.epoch_jd, duration_s=36_000.0, step_s=3600.0)
    >>> pass_availability(cover[:11], grid=short, table=table, degradations=log)
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: the cloud series covers [0.0, 36000.0] s of the pass grid, but the passes span [25714.4, 71922.2] s. ...
    """
    if not isinstance(grid, TimeGrid):
        raise DomainError(f"grid must be a TimeGrid, got {type(grid).__name__}.")
    if not isinstance(table, PassTable):
        raise DomainError(f"table must be a PassTable, got {type(table).__name__}.")
    chosen = AvailabilityRule(rule)
    fraction = _validated_cloud_fraction("cloud_fraction_series", cloud_fraction_series)
    if fraction.shape != (grid.n,):
        raise DomainError(
            f"cloud_fraction_series has shape {fraction.shape}, but grid holds {grid.n} samples. "
            "One cover fraction per sample of the series' own grid."
        )
    axis = _series_on_pass_axis(grid, table)
    if table.n_passes == 0:
        return np.zeros(0, dtype=np.float64)
    window_start = float(table.start_s.min())
    window_end = float(table.end_s.max())
    if axis[0] > window_start or axis[-1] < window_end:
        raise DomainError(
            f"the cloud series covers [{axis[0]:.1f}, {axis[-1]:.1f}] s of the pass grid, but "
            f"the passes span [{window_start:.1f}, {window_end:.1f}] s. A series that does not "
            "cover a pass cannot say whether it was cloudy, and np.interp would extend the end "
            "value silently, which is inventing weather. Fetch a series that covers the window."
        )

    probability = cloud_free_probability(fraction, degradations=degradations)
    fine_t = np.asarray(table.grid.t_s, dtype=np.float64)

    # Culmination: one interpolation per pass.
    at_culmination = np.interp(table.culmination_s, axis, probability)

    # Mean: the midpoint dwell times of the pass samples, which sum to the
    # refined duration exactly, weighting the interpolant at those samples.
    samples = table.samples()
    dwell = np.asarray(samples.dwell_s, dtype=np.float64)
    at_samples = np.interp(fine_t[samples.sample_index], axis, probability)
    mean = samples.segment_sum(at_samples * dwell) / samples.segment_sum(dwell)

    # Minimum: a piecewise-linear function attains its minimum over an interval
    # at an endpoint or at a knot inside it, so evaluate exactly those and
    # nothing else. Knots are gathered per pass with searchsorted and folded
    # with `np.minimum.at`, which handles passes with no interior knot.
    at_start = np.interp(table.start_s, axis, probability)
    at_end = np.interp(table.end_s, axis, probability)
    minimum = np.minimum(at_start, at_end)
    first_knot = np.searchsorted(axis, table.start_s, side="right")
    past_knot = np.searchsorted(axis, table.end_s, side="left")
    knot_count = np.maximum(past_knot - first_knot, 0)
    owner = np.repeat(np.arange(table.n_passes), knot_count)
    offsets = np.repeat(first_knot, knot_count)
    within = np.arange(int(knot_count.sum())) - np.repeat(
        np.concatenate(([0], np.cumsum(knot_count)))[:-1], knot_count
    )
    np.minimum.at(minimum, owner, probability[offsets + within])

    readings = {
        AvailabilityRule.MEAN: np.asarray(mean, dtype=np.float64),
        AvailabilityRule.CULMINATION: np.asarray(at_culmination, dtype=np.float64),
        AvailabilityRule.MINIMUM: np.asarray(minimum, dtype=np.float64),
    }
    spread = float(
        max(
            np.max(np.abs(readings[a] - readings[b]))
            for a in readings
            for b in readings
            if a is not b
        )
    )
    degradations.info(
        "pcflos.pass-availability-rule",
        f"each pass's availability is the {chosen.value} of the cloud-free probability over "
        "its window, from a cloud series interpolated LINEARLY between its samples "
        f"({'uniform' if grid.is_uniform else 'non-uniform'} series grid). Linear "
        "interpolation of an hourly archive is a modelling choice, not data; the three "
        "readings (mean, culmination, minimum) differ by at most "
        f"{spread:.4f} in probability across these passes.",
        where="quoss.system.pcflos.pass_availability",
        rule=chosen.value,
        interpolation="linear",
        series_step_s=grid.step_s if grid.is_uniform and grid.n > 1 else None,
        n_passes=table.n_passes,
        max_spread_between_rules=spread,
        mean=[float(value) for value in readings[AvailabilityRule.MEAN]],
        culmination=[float(value) for value in readings[AvailabilityRule.CULMINATION]],
        minimum=[float(value) for value in readings[AvailabilityRule.MINIMUM]],
    )
    return readings[chosen]


def station_separation_km(latitude_rad: FloatArray, longitude_rad: FloatArray) -> FloatArray:
    r"""Return the pairwise surface separation of a set of sites, km, shape ``(N, N)``.

    The chord between every pair of sites on the WGS-84 ellipsoid, through
    :func:`~quoss.orbits.frames.geodetic_to_itrf` at zero altitude, converted
    to an arc on the sphere of :data:`WGS84_MEAN_RADIUS_KM`:

    .. math::

        d = 2 R \arcsin\!\left(\frac{c}{2R}\right)

    Zero altitude on purpose: two stations 500 km apart and 2 km different in
    height are 500 km apart for a cloud field, and putting the altitude in
    would change the answer by the ratio of the two, which is nothing, while
    making the function depend on a quantity the correlation model does not.

    **Why not the haversine formula directly.** It would give the same number
    to one part in three hundred and take five lines. The reason to go through
    the ellipsoid is that it is where every station in this project already
    lives, so this distance and the station's elevation angles cannot disagree
    about where the station is. The haversine is used as the *independent*
    computation in the tests instead, which is the better place for it.

    Parameters
    ----------
    latitude_rad : FloatArray
        Geodetic latitudes, radians, shape ``(N,)``, in ``[-pi/2, pi/2]``.
    longitude_rad : FloatArray
        Longitudes, radians, shape ``(N,)``, positive east.

    Returns
    -------
    FloatArray
        Symmetric ``(N, N)`` matrix of separations, km, zero on the diagonal.

    Raises
    ------
    DomainError
        If the two arrays are not one-dimensional of the same length, or a
        latitude is outside ``[-pi/2, pi/2]`` (almost always degrees that were
        never converted).

    Examples
    --------
    Castelldefels to the ESA optical ground station on Tenerife, both by their
    published coordinates:

    >>> import numpy as np
    >>> from quoss.core.units import deg_to_rad
    >>> lat = np.asarray(deg_to_rad(np.array([41.2750, 28.298])))
    >>> lon = np.asarray(deg_to_rad(np.array([1.9875, -16.5118])))
    >>> np.round(station_separation_km(lat, lon), 1)
    array([[   0. , 2213.8],
           [2213.8,    0. ]])

    One degree of longitude on the equator is one three-hundred-and-sixtieth
    of the equator's circumference, to the flattening:

    >>> d = station_separation_km(np.zeros(2), np.asarray(deg_to_rad(np.array([0.0, 1.0]))))
    >>> round(float(d[0, 1]), 3)
    111.319
    """
    lat = np.asarray(latitude_rad, dtype=np.float64)
    lon = np.asarray(longitude_rad, dtype=np.float64)
    if lat.ndim != 1 or lon.shape != lat.shape:
        raise DomainError(
            f"latitude_rad and longitude_rad must be 1-D arrays of the same length, got shapes "
            f"{lat.shape} and {lon.shape}: one pair of coordinates per station."
        )
    if not (np.all(np.isfinite(lat)) and np.all(np.isfinite(lon))):
        raise DomainError("station coordinates contain non-finite values.")
    positions = geodetic_to_itrf(lat, lon, np.zeros_like(lat))
    difference = positions[:, np.newaxis, :] - positions[np.newaxis, :, :]
    chord = np.sqrt(np.sum(difference * difference, axis=-1))
    ratio = np.clip(chord / (2.0 * WGS84_MEAN_RADIUS_KM), 0.0, 1.0)
    arc: FloatArray = 2.0 * WGS84_MEAN_RADIUS_KM * np.arcsin(ratio)
    return arc


@dataclass(frozen=True, eq=False, slots=True)
class JointCloudFreeProbability:
    """The probability that at least one of several stations is cloud-free.

    Two bounds always, and the exact value when it exists. See the module
    docstring for why the exact value exists for two stations and not for
    three.

    Attributes
    ----------
    independent : FloatArray
        ``1 - prod(1 - p_i)``: the value if the stations' clouds were
        independent. An **upper bound** on availability for any non-negative
        correlation.
    comonotone : FloatArray
        ``max_i p_i``: the value under perfect correlation, and a **lower
        bound** for any joint law with these marginals, since "at least one
        clear" contains "the best one clear".
    exact : FloatArray or None
        The bivariate-Bernoulli value for exactly two stations (or the single
        station's own ``p`` for one), ``None`` for three or more, where the
        pairwise correlations do not determine a joint law.
    correlation : FloatArray
        ``exp(-d_ij / L)``, shape ``(N, N)``, the correlation model that was
        used.
    decorrelation_length_km : float
        ``L``.

    Raises
    ------
    DomainError
        If a bound is outside ``[0, 1]``, if ``comonotone`` exceeds
        ``independent`` anywhere, or if ``exact`` is present and falls outside
        the two bounds — any of which means the caller built the object by
        hand from inconsistent numbers.

    Examples
    --------
    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> joint = joint_cloud_free_probability(
    ...     np.array([0.6, 0.6]),
    ...     separation_km=np.array([[0.0, 500.0], [500.0, 0.0]]),
    ...     decorrelation_length_km=500.0,
    ...     degradations=DegradationLog(),
    ... )
    >>> (
    ...     round(float(joint.comonotone), 4),
    ...     round(float(joint.exact), 4),
    ...     round(float(joint.independent), 4),
    ... )
    (0.6, 0.7517, 0.84)
    """

    independent: FloatArray
    comonotone: FloatArray
    exact: FloatArray | None
    correlation: FloatArray
    decorrelation_length_km: float

    def __post_init__(self) -> None:
        """Validate the ordering the two bounds must satisfy, then freeze."""
        upper = _validated_probability("independent", self.independent)
        lower = _validated_probability("comonotone", self.comonotone)
        if lower.shape != upper.shape:
            raise DomainError(
                f"comonotone has shape {lower.shape} but independent has {upper.shape}; the two "
                "bounds describe the same instants."
            )
        if np.any(lower > upper + _CORRELATION_FEASIBILITY_SLACK):
            raise DomainError(
                "comonotone (the perfectly correlated case, max of the marginals) cannot "
                "exceed independent (1 - prod(1 - p)): the union of events is at least the "
                "largest of them. A violation means the two arrays came from different "
                "marginals."
            )
        object.__setattr__(self, "independent", frozen_copy(upper))
        object.__setattr__(self, "comonotone", frozen_copy(lower))
        if self.exact is not None:
            value = _validated_probability("exact", self.exact)
            if value.shape != upper.shape:
                raise DomainError(
                    f"exact has shape {value.shape} but the bounds have {upper.shape}."
                )
            if np.any(value < lower - _CORRELATION_FEASIBILITY_SLACK) or np.any(
                value > upper + _CORRELATION_FEASIBILITY_SLACK
            ):
                raise DomainError(
                    "exact must lie between comonotone and independent: those are the bounds "
                    "for every joint law with these marginals and a non-negative correlation."
                )
            object.__setattr__(self, "exact", frozen_copy(value))
        rho = np.asarray(self.correlation, dtype=np.float64)
        if rho.ndim != 2 or rho.shape[0] != rho.shape[1]:
            raise DomainError(f"correlation must be a square matrix, got shape {rho.shape}.")
        object.__setattr__(self, "correlation", frozen_copy(rho))
        length = float(self.decorrelation_length_km)
        if not np.isfinite(length) or length <= 0.0:
            raise DomainError(f"decorrelation_length_km must be finite and positive, got {length}.")
        object.__setattr__(self, "decorrelation_length_km", length)

    @property
    def n_stations(self) -> int:
        """Number of stations, the side of the correlation matrix."""
        return int(self.correlation.shape[0])

    @property
    def is_exact(self) -> bool:
        """True when :attr:`exact` is available, i.e. for at most two stations."""
        return self.exact is not None

    def __repr__(self) -> str:
        exact = "exact" if self.is_exact else "bounds only"
        return (
            f"JointCloudFreeProbability(n_stations={self.n_stations}, {exact}, "
            f"L={self.decorrelation_length_km:g} km)"
        )


def _validated_separation(separation_km: FloatArray, n_stations: int) -> FloatArray:
    """Return the separation matrix, checked to be a symmetric zero-diagonal distance."""
    distance = np.asarray(separation_km, dtype=np.float64)
    if distance.shape != (n_stations, n_stations):
        raise DomainError(
            f"separation_km has shape {distance.shape}, but p describes {n_stations} stations, "
            f"so the expected shape is ({n_stations}, {n_stations}). "
            "station_separation_km builds it."
        )
    if not np.all(np.isfinite(distance)) or np.any(distance < 0.0):
        raise DomainError("separation_km must be finite and non-negative.")
    if not np.allclose(distance, distance.T, rtol=0.0, atol=1e-9):
        raise DomainError("separation_km must be symmetric: d_ij is the same distance as d_ji.")
    if np.any(np.abs(np.diagonal(distance)) > 1e-9):
        raise DomainError("separation_km must be zero on the diagonal: a station is where it is.")
    return distance


def joint_cloud_free_probability(
    p: FloatArray,
    *,
    separation_km: FloatArray,
    decorrelation_length_km: float,
    degradations: DegradationLog,
) -> JointCloudFreeProbability:
    r"""Return the probability that at least one station has a clear line of sight.

    What it computes
    ----------------
    With ``rho_ij = exp(-d_ij / L)`` as the pairwise correlation of the
    clear/cloudy indicators:

    - **one station**: ``p`` itself, exactly;
    - **two stations**: the exact bivariate-Bernoulli answer
      ``1 - (q_1 q_2 + rho sqrt(p_1 q_1 p_2 q_2))``;
    - **three or more**: no exact answer exists from pairwise correlations,
      and the result carries the two bounds — independence above,
      ``max_i p_i`` below — with ``exact = None`` and a ``WARNING`` in the log.

    The bounds are returned in every case, so a consumer can always read what
    correlation is worth: on the reference pair of the module docstring
    (``p = 0.6`` twice, 500 km apart, ``L = 500 km``) the independent value is
    0.84, the exact one 0.75, and the perfectly correlated one 0.60.

    Why the feasibility bound is an error and not a clip
    ----------------------------------------------------
    Two Bernoulli variables with marginals ``p_1 <= p_2`` cannot be more
    correlated than ``sqrt(p_1 q_2 / (p_2 q_1))``: above that, "both clear"
    would have to be more probable than "station 1 clear" on its own. A
    correlation model that returns more than that for a pair of stations is
    inconsistent with the climatologies handed in. Clipping would substitute a
    different correlation with no record of which; raising says which pair and
    by how much, which is what a caller needs to fix either ``L`` or the
    marginals.

    Parameters
    ----------
    p : FloatArray
        Cloud-free probability per station, shape ``(N,)`` for a climatology or
        ``(N, T)`` for a series over ``T`` instants. The station axis is the
        first one.
    separation_km : FloatArray
        Pairwise separations, shape ``(N, N)``, symmetric with zero diagonal —
        :func:`station_separation_km` builds it.
    decorrelation_length_km : float
        ``L`` of the exponential model, km, finite and positive. **No
        default**: it is the whole content of the correlation model and no
        source verified for this project publishes a value.
    degradations : DegradationLog
        Receives a ``WARNING`` for three or more stations, where only bounds
        are returned.

    Returns
    -------
    JointCloudFreeProbability
        The bounds, the exact value where it exists, and the correlation
        matrix used.

    Raises
    ------
    DomainError
        If ``p`` is outside ``[0, 1]`` or has no station axis, if the
        separation matrix is not a symmetric zero-diagonal distance of the
        right shape, if ``L`` is not finite and positive, or if the two-station
        correlation is infeasible for the given marginals.

    Examples
    --------
    Two identical stations, from adjacent to far apart, at ``L = 500 km``:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> for d in (0.0, 500.0, 2000.0):
    ...     joint = joint_cloud_free_probability(
    ...         np.array([0.6, 0.6]),
    ...         separation_km=np.array([[0.0, d], [d, 0.0]]),
    ...         decorrelation_length_km=500.0,
    ...         degradations=log,
    ...     )
    ...     print(d, round(float(joint.exact), 4))
    0.0 0.6
    500.0 0.7517
    2000.0 0.8356
    >>> len(log)
    0

    Three stations: bounds only, and the log says why:

    >>> three = joint_cloud_free_probability(
    ...     np.array([0.6, 0.6, 0.6]),
    ...     separation_km=500.0 * (1.0 - np.eye(3)),
    ...     decorrelation_length_km=500.0,
    ...     degradations=log,
    ... )
    >>> three.exact is None, round(float(three.comonotone), 3), round(float(three.independent), 3)
    (True, 0.6, 0.936)
    >>> [entry.code for entry in log]
    ['pcflos.joint-law-not-unique']

    An inconsistent pair is refused:

    >>> joint_cloud_free_probability(
    ...     np.array([0.9, 0.3]),
    ...     separation_km=np.array([[0.0, 10.0], [10.0, 0.0]]),
    ...     decorrelation_length_km=500.0,
    ...     degradations=log,
    ... )
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: the correlation model gives rho = 0.9802 for stations 0 and 1, but two Bernoulli variables with cloud-free probabilities 0.9 and 0.3 can be correlated at most 0.2182. ...
    """
    probability = _validated_probability("p", p)
    if probability.ndim == 0:
        raise DomainError(
            "p must have a leading station axis, shape (N,) or (N, T); a scalar names no "
            "station. For one station, wrap it in a length-1 array."
        )
    n_stations = int(probability.shape[0])
    if n_stations == 0:
        raise DomainError("p has no stations: nothing to combine.")
    distance = _validated_separation(separation_km, n_stations)
    length = float(decorrelation_length_km)
    if not np.isfinite(length) or length <= 0.0:
        raise DomainError(
            f"decorrelation_length_km must be finite and positive, got {length}. It is the "
            "e-folding distance of the cloud correlation and has no default on purpose."
        )
    rho = np.exp(-distance / length)

    cloudy = 1.0 - probability
    independent = 1.0 - np.prod(cloudy, axis=0)
    comonotone = np.max(probability, axis=0)

    exact: FloatArray | None
    if n_stations == 1:
        exact = np.asarray(probability[0], dtype=np.float64)
    elif n_stations == 2:
        p1, p2 = probability[0], probability[1]
        q1, q2 = cloudy[0], cloudy[1]
        cross = np.sqrt(p1 * q1 * p2 * q2)
        # Fréchet bound: the largest correlation two Bernoulli variables with
        # these marginals admit. Where either marginal is 0 or 1 the variable
        # is constant, `cross` vanishes and rho has no effect, so no bound.
        lo = np.minimum(p1 * q2, p2 * q1)
        hi = np.maximum(p1 * q2, p2 * q1)
        with np.errstate(divide="ignore", invalid="ignore"):
            rho_max = np.where(hi > 0.0, np.sqrt(lo / np.where(hi > 0.0, hi, 1.0)), 1.0)
        pair_rho = float(rho[0, 1])
        infeasible = (cross > 0.0) & (pair_rho > rho_max + _CORRELATION_FEASIBILITY_SLACK)
        if np.any(infeasible):
            worst = int(np.argmax(np.where(infeasible, pair_rho - rho_max, -np.inf)))
            raise DomainError(
                f"the correlation model gives rho = {pair_rho:.4f} for stations 0 and 1, but "
                "two Bernoulli variables with cloud-free probabilities "
                f"{float(np.ravel(p1)[worst]):.4g} and {float(np.ravel(p2)[worst]):.4g} can "
                f"be correlated at most {float(np.ravel(rho_max)[worst]):.4f}. The "
                "marginals and the decorrelation length are inconsistent; change one, "
                "because clipping the correlation would substitute a model with no record."
            )
        exact = np.asarray(1.0 - (q1 * q2 + pair_rho * cross), dtype=np.float64)
    else:
        exact = None
        degradations.warn(
            "pcflos.joint-law-not-unique",
            f"{n_stations} stations: the pairwise correlations exp(-d/L) do not determine the "
            "joint probability that at least one is cloud-free, so only bounds are returned. "
            "The true value lies between `comonotone` (perfect correlation, max of the "
            "marginals) and `independent` (1 - prod(1 - p)); the exact N-station joint law is "
            "a declared gap (a Gaussian copula would be one choice, and no verified source says "
            "it is the right one).",
            where="quoss.system.pcflos.joint_cloud_free_probability",
            n_stations=n_stations,
            decorrelation_length_km=length,
            independent_max=float(np.max(independent)),
            comonotone_max=float(np.max(comonotone)),
        )

    return JointCloudFreeProbability(
        independent=np.asarray(independent, dtype=np.float64),
        comonotone=np.asarray(comonotone, dtype=np.float64),
        exact=exact,
        correlation=np.asarray(rho, dtype=np.float64),
        decorrelation_length_km=length,
    )
