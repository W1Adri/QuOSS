r"""Fading that lasts: the two link fades as processes in time, not as marginal draws.

What a fade is, for a reader who has not met the word
-----------------------------------------------------
The power a ground telescope collects from a satellite is not steady. Two
things shake it. The air the beam crosses is full of moving lenses, so the
irradiance at the telescope flickers — that is **scintillation**, the twinkling
of a star, and :mod:`quoss.channel.turbulence` says how strong it is. And the
satellite terminal never aims exactly at the telescope: what is left after its
control loop has done its best is a residual angular error that wanders, so the
telescope sits now nearer the middle of the beam, now nearer its edge — that is
**pointing jitter**, and :mod:`quoss.channel.pointing` says what it costs. A
**fade** is a stretch of time in which either of those has pushed the collected
power below what the link was designed for.

:mod:`quoss.channel.link_budget` handles both fades as **marginal
distributions**: it asks what fraction of the time the link is worse than some
level, and answers with one number per sample, the level exceeded 99 % of the
time. That is the right question for a static budget and the wrong one for a
block of counts, because it says nothing about *how long* a fade lasts once it
starts. A link that is 1 % faded in a thousand independent microsecond flickers
and a link that is 1 % faded in a single ten-second dropout have the same
marginal and completely different consequences: the first is invisible to a
post-processing block that pools a whole pass, the second takes a tenth of the
pass's detections with it. The marginal cannot tell them apart. This module can,
and it is the point of novelty ``notes/ROADMAP.md`` names for the stage.

The model: a Gaussian process in the domain where the fade is Gaussian
----------------------------------------------------------------------
Both fades are Gaussian once written in the right variable, and both variables
are the ones the channel modules already use, so nothing here introduces a
distribution the rest of the project has not verified.

**Scintillation.** :func:`~quoss.channel.link_budget.scintillation_fade_db`
reads Ntanos et al.'s equation (18) as a distribution: the fade in decibels is
Gaussian with mean ``4.343 sigma^2 / 2`` and standard deviation ``4.343 sigma``.
Undo the decibels and that is the statement that the **log-irradiance**
``chi = ln(I / <I>)`` is ``N(-sigma^2 / 2, sigma^2)``, with ``sigma^2`` the
log-irradiance variance :func:`~quoss.channel.turbulence.downlink_log_irradiance_variance`
returns in Np^2. The mean of ``-sigma^2 / 2`` is what makes ``E[exp(chi)] = 1``:
the irradiance fluctuates *around* its mean, it does not gain or lose power on
average. This module keeps that normalisation exactly, so that a realisation's
relative factor ``exp(chi)`` averages to one and the mean transmittance of the
budget is the mean transmittance of the ensemble.

**Pointing.** :mod:`quoss.channel.pointing` derives the fading law from two
independent zero-mean Gaussian jitter components, one per axis, each of standard
deviation ``sigma_s``. The relative factor is ``exp(-2 r^2 / w_zeq^2)`` with
``r`` the radial offset, and with ``gamma = w_zeq / (2 sigma_s)`` that reads::

    F_p = exp(-(x_1^2 + x_2^2) / (2 gamma^2)),    x_1, x_2 ~ N(0, 1)

which is the only form used here. Its consequences are the ones ``pointing.py``
publishes and this module tests against as an oracle: ``P(F_p < x) = x^(gamma^2)``
and ``E[F_p] = gamma^2 / (gamma^2 + 1)``. Note the second: the pointing factor
does **not** average to one. A shaking terminal loses power on average, and the
loss is the one :func:`~quoss.channel.pointing.mean_pointing_transmittance`
prices; :attr:`FadeRealisations.mean_pointing_factor` carries it so that a
caller knows what the ensemble fluctuates around.

**Time.** Each Gaussian driver — one for scintillation, two for pointing — is an
**Ornstein-Uhlenbeck process**: the simplest stationary Gaussian process with
memory. "Stationary" means its statistics do not drift; "with memory" means that
its value now is correlated with its value a moment ago, and the correlation
decays as ``exp(-|dt| / tau)``. The one parameter ``tau`` is the **correlation
time**: how long the process takes to forget where it was, to a factor ``1/e``.
A fade of correlation time ``tau`` lasts, loosely, about ``tau``; the marginal
distribution says nothing about ``tau`` at all.

Sampled on a grid the process is an AR(1) recursion — "autoregressive of order
one", the value is a fraction of the previous value plus fresh noise — and the
discretisation used here is **exact**, not Euler::

    phi_i = exp(-(t_i - t_{i-1}) / tau)
    x_i   = phi_i x_{i-1} + sqrt(1 - phi_i^2) eps_i,    eps_i ~ N(0, 1)

Exact means that the samples have precisely the ``exp(-|dt| / tau)``
autocovariance of the continuous process for *any* spacing, so the grid may be
non-uniform and as coarse as the caller likes without the process changing
character. :func:`ar1_coefficients` returns the ``phi_i``, and the first one is
zero: the first sample has no predecessor and is drawn from the stationary law.

Why the correlation time is a parameter and not a model
-------------------------------------------------------
Because no source this project has opened publishes it at the precision a
model would claim. What the literature offers is an order of magnitude through
**Taylor's frozen-turbulence hypothesis**: the turbulent pattern is carried
rigidly across the line of sight, so a correlation width ``l`` in space becomes
a correlation time ``tau = l / v`` for a transverse speed ``v``. For a ground
telescope looking at a fixed star ``v`` is the wind. For a LEO downlink it is
not: the line of sight slews through the turbulent layer at the satellite's
angular rate, and :func:`slew_transverse_speed_m_s` measures that on the
reference pass at tens of metres per second against a 2.3 m/s ground wind. The
scintillation correlation time comes out at milliseconds and the pointing one
at tens of milliseconds, and both are estimates that ADR 0009 forbids dressing
as published values. So :class:`FadingParameters` takes both as arguments, the
two helpers give the derivation for whoever wants to choose them from a
geometry, and the width ``l`` is a declared gap rather than a guessed number.

The finding this module has to state honestly: on the project's grid,
correlation barely moves the key
-----------------------------------------------------------------------
The project integrates passes on a 1 s grid, and a millisecond correlation time
means a thousand independent fades inside every sample. Two things follow, and
both are measured in ``tests/system/test_correlated_fading.py`` and
``tests/system/test_monte_carlo.py``.

First, **the quantity that belongs in the counts model is the dwell-averaged
factor**, not an instantaneous draw. A sample that speaks for one second of
pulses has its detections set by the *average* of the fade over that second,
and the average of a thousand independent fades has a thousandth of their
variance. Feeding the counts model one full-variance draw per sample would
overstate the block's fluctuation by that factor — plausible numbers, wrong by
three orders of magnitude. :func:`dwell_averaged_variance_reduction` gives the
exact reduction for an Ornstein-Uhlenbeck driver averaged over a window ``T``::

    w(T / tau) = 2 (tau / T)^2 (T / tau - 1 + exp(-T / tau))

which is 1 for ``T << tau`` (the average *is* the instantaneous value) and
``2 tau / T`` for ``T >> tau`` (the window holds ``T / (2 tau)`` independent
pieces). :func:`sample_fade_factors` applies it when handed a ``dwell_s``, and
does so by sampling the **integral** of the process over each window exactly
alongside its endpoint — the pair is jointly Gaussian with a closed-form
covariance — so that consecutive windows keep the correlation they really have
instead of the correlation their endpoints have. The nonlinearity of the two
factors is then handled by a mean-preserving shrink toward the marginal mean,
which is exact in both limits and first-order in ``sigma^2`` and ``1 / gamma^2``
between them; the size of that approximation is measured against a brute-force
fine-grid average in ``TestTheDwellAverage``.

Second, **the spread of a pass's key is set by how many independent fades the
pass holds**, so on a 1 s grid it is small until ``tau`` reaches the grid step.
The measurement is in ``monte_carlo.py``'s docstring, where the key is; the
short version is that for the reference link the P5-P95 band of the key from
fading is 0.11 % of the median at a 1 ms correlation time and crosses one per
cent only between 10 and 100 ms — two orders of magnitude above the physical
estimate — while the Poisson scatter of the counts alone puts a 9 % band on the
same pass. A study that reported P5/P95 from independent per-sample draws would
report a fading spread ten to twenty times wider than the one that is there.

What correlated fading *does* change
------------------------------------
Two things, and neither is visible to a marginal model.

- **The variance of the block counts**, hence the low quantiles of the
  finite-key result, by the factor the dwell reduction and the cross-sample
  correlation together give. An i.i.d. per-sample model is wrong in the
  direction of too much spread on a coarse grid and too little on a fine one.
- **Fade-duration statistics** — how long the link stays below a threshold once
  it drops there, and how many such episodes a pass holds. These govern gating,
  synchronisation and burst errors, and an i.i.d. model gets them wrong by
  exactly the ratio of the grid step to the correlation time.
  :func:`fade_duration_statistics` reports them on any realisation, and the
  number of down-crossings per step is checked against the exact bivariate
  normal probability ``P(x_{i-1} >= c, x_i < c)`` in
  ``TestFadeDurations``. Continuous-time crossing rates are deliberately not
  offered: an Ornstein-Uhlenbeck path is nowhere differentiable, so Rice's
  formula diverges for it, and the honest quantity is the discrete one at a
  stated step.

What is deliberately not in here
--------------------------------
**No counts, no key.** This module produces relative transmittance factors of
shape ``(realisations, n)`` and nothing else; multiplying them into a link and
pooling a block is ``monte_carlo.py``. **No reset at pass boundaries**: the
process runs over whatever ``t_s`` it is handed, and a caller that wants
independent passes hands it one pass at a time, which is what ``monte_carlo.py``
does and why. **No non-Gaussian turbulence**: the log-normal is the
weak-fluctuation model the channel already commits to, and the warning
:mod:`quoss.channel.turbulence` records at ``sigma^2 > 1`` applies unchanged to
anything sampled from it here. **No spectrum**: an Ornstein-Uhlenbeck process
has a Lorentzian power spectrum, which is the one-parameter shape; a measured
scintillation spectrum with a ``-8/3`` tail is a different, two-parameter
process, and a source for its parameters on a LEO downlink is a gap, not a
default.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``tau``                                 correlation time of a driver (s)
``phi_i``                               AR(1) coefficient of step ``i``
``x``                                   a unit-variance Ornstein-Uhlenbeck driver
``sigma^2``                             log-irradiance variance (Np^2)
``gamma``                               beam radius in units of jitter
``F_s``, ``F_p``                        scintillation and pointing factors
``m``                                   ``E[F_p] = gamma^2 / (gamma^2 + 1)``
``T``                                   dwell of a sample (s)
``w``                                   variance reduction of a dwell average
``l``, ``v``                            correlation width (m), transverse speed (m/s)
======================================  ====================================

References
----------
A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
equation (18): the log-normal scintillation fade whose normalisation is kept
here. A. A. Farid and S. Hranilovic, *J. Lightwave Technol.* **25**(7):1702,
2007, equations (9)-(11): the two-axis Gaussian jitter the pointing factor is
built from. Both opened, per ``docs/adr/0009-citation-policy.md``. The
frozen-turbulence hypothesis is G. I. Taylor's (1938) and that paper was **not**
opened for this project; only the one-line kinematic statement ``tau = l / v``
is used, and it is derived in :func:`taylor_correlation_time_s` rather than
cited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import numpy as np

from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import BoolArray, FloatArray, IntArray, frozen_view

__all__ = [
    "FadeDurationStatistics",
    "FadeRealisations",
    "FadingParameters",
    "ar1_coefficients",
    "dwell_averaged_variance_reduction",
    "fade_duration_statistics",
    "line_of_sight_angular_rate_rad_s",
    "sample_fade_factors",
    "slew_transverse_speed_m_s",
    "taylor_correlation_time_s",
]

_SERIES_SWITCH: Final[float] = 1e-3
"""Below this ``T / tau`` the dwell reduction is evaluated by series, not by ``expm1``.

``2 (expm1(-u) + u) / u^2`` cancels two ``O(u)`` terms to leave an ``O(u^2)``
one, and at ``u = 1e-3`` the cancellation costs about three of the sixteen
digits, which is harmless; at ``u = 1e-8`` it costs eight and the reduction
would come back at the percent level for a window a hundred-millionth of the
correlation time. The five-term series is exact to ``u^5 / 2520``, below
``1e-16`` at the switch, so the two branches agree to machine precision there
and the choice of switch is not a tuning.
"""

_INDEPENDENT_SAMPLES_COEFFICIENT: Final[float] = 1e-6
"""AR(1) coefficient below which consecutive samples are independent for any purpose.

``exp(-14)``: a grid step of fourteen correlation times. Used only to decide
whether to *say* that instantaneous factors on a grid carry no correlation at
all, which is the situation a caller who forgot ``dwell_s`` is in.
"""


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def _validated_correlation_time_s(name: str, value: float) -> float:
    """Return a correlation time, rejecting anything that is not a positive duration."""
    tau = float(value)
    if not np.isfinite(tau) or tau <= 0.0:
        raise DomainError(
            f"{name} must be finite and strictly positive, got {tau}. It is a duration in "
            "seconds, so a 5 millisecond correlation time is 0.005 and not 5. Zero is excluded "
            "rather than read as 'no correlation': the AR(1) coefficient exp(-dt / tau) is then "
            "0 / 0 for a zero step, and a process with no memory at all is not a limit this "
            "module needs -- pass a tau far below the grid step and the coefficients are zero "
            "to machine precision."
        )
    return tau


def _validated_axis(name: str, value: FloatArray) -> FloatArray:
    """Return a 1-D, finite, non-decreasing time axis."""
    axis = np.asarray(value, dtype=np.float64)
    if axis.ndim != 1:
        raise DomainError(
            f"{name} must be 1-D, got shape {axis.shape}. A fade process runs along one time "
            "axis; the realisation axis is created by this module, not passed in."
        )
    if not np.all(np.isfinite(axis)):
        raise DomainError(f"{name} contains non-finite values.")
    if axis.size > 1 and np.any(np.diff(axis) < 0.0):
        raise DomainError(
            f"{name} must be non-decreasing: the AR(1) recursion carries memory forward, so a "
            "step backwards in time would correlate a sample with one that has not happened yet. "
            "Two samples at the same instant are allowed and are perfectly correlated."
        )
    return axis


def _validated_generator(rng: np.random.Generator) -> np.random.Generator:
    """Return the generator, refusing the legacy global API and bare seeds."""
    if not isinstance(rng, np.random.Generator):
        raise DomainError(
            f"rng must be a numpy.random.Generator, got {type(rng).__name__}. Randomness in this "
            "project is injected through quoss.core.rng.RandomSource so that every ensemble "
            "reproduces from a recorded seed; a bare integer or the legacy np.random module "
            "would make the spread of the result depend on what ran before it."
        )
    return rng


def _validated_realisations(realisations: int) -> int:
    """Return the realisation count as a positive integer."""
    count = int(realisations)
    if count < 1:
        raise DomainError(
            f"realisations must be at least 1, got {count}. One realisation is a single sample "
            "path; zero is no ensemble at all."
        )
    return count


# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class FadingParameters:
    """The two correlation times, which are the only knobs this module has.

    A **parameter object rather than two defaults**, for the reason the module
    docstring gives: no source opened for this project publishes either number
    at the precision a default would claim, and the estimate from Taylor's
    hypothesis is an order of magnitude. A caller states both, and the result
    carries them.

    Attributes
    ----------
    scintillation_correlation_time_s : float
        ``tau`` of the log-irradiance driver, seconds, strictly positive.
        Physically milliseconds for a LEO downlink: the line of sight slews
        through the turbulent layer at tens of metres per second and the
        irradiance pattern is correlated over centimetres.
    pointing_correlation_time_s : float
        ``tau`` of each jitter axis, seconds, strictly positive. Physically tens
        of milliseconds: the residual of a tracking loop lives at the loop's
        bandwidth, which is tens of hertz.

    Raises
    ------
    DomainError
        If either time is not finite and strictly positive.

    Examples
    --------
    >>> FadingParameters(scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=0.02)
    FadingParameters(scintillation_correlation_time_s=0.002, pointing_correlation_time_s=0.02)
    >>> FadingParameters(scintillation_correlation_time_s=0.0, pointing_correlation_time_s=0.02)
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: scintillation_correlation_time_s must be finite and strictly positive, got 0.0. ...
    """

    scintillation_correlation_time_s: float
    pointing_correlation_time_s: float

    def __post_init__(self) -> None:
        """Validate both durations."""
        object.__setattr__(
            self,
            "scintillation_correlation_time_s",
            _validated_correlation_time_s(
                "scintillation_correlation_time_s", self.scintillation_correlation_time_s
            ),
        )
        object.__setattr__(
            self,
            "pointing_correlation_time_s",
            _validated_correlation_time_s(
                "pointing_correlation_time_s", self.pointing_correlation_time_s
            ),
        )


# --------------------------------------------------------------------------- #
# The process
# --------------------------------------------------------------------------- #
def ar1_coefficients(t_s: FloatArray, *, correlation_time_s: float) -> FloatArray:
    r"""Return the exact AR(1) coefficient of every step of a time axis.

    What it computes
    ----------------
    ``phi_i = exp(-(t_i - t_{i-1}) / tau)`` for ``i >= 1`` and ``phi_0 = 0``.
    In the recursion ``x_i = phi_i x_{i-1} + sqrt(1 - phi_i^2) eps_i`` the
    coefficient is *how much of the previous value survives*: 1 is perfect
    memory, 0 is none. The zero at the front is the statement that the first
    sample has nothing to remember and is drawn from the stationary
    distribution.

    Why the exponential of the step, and not a constant
    ---------------------------------------------------
    A constant coefficient is the textbook AR(1) on a uniform grid. This
    project's grids are allowed to be non-uniform (:class:`~quoss.core.types.TimeGrid`
    says so) and a pass's samples are handed over with their dwell times rather
    than their spacing, so the coefficient has to be a function of each step.
    Written this way the discretisation is exact for an Ornstein-Uhlenbeck
    process — the sampled values have exactly the ``exp(-|dt| / tau)``
    autocovariance of the continuous one — for any spacing at all, which is what
    lets ``tests/system/test_correlated_fading.py::TestTheProcess`` check the
    lag-``k`` autocorrelation against ``exp(-k dt / tau)`` to within its
    estimator's own standard error.

    Parameters
    ----------
    t_s : FloatArray
        Sample instants, seconds, 1-D and non-decreasing.
    correlation_time_s : float
        ``tau``, seconds, strictly positive.

    Returns
    -------
    FloatArray
        Coefficients in ``[0, 1]``, shaped like ``t_s``; the first is ``0``.

    Raises
    ------
    DomainError
        If ``t_s`` is not a 1-D non-decreasing finite axis, or ``tau`` is not
        finite and positive.

    Examples
    --------
    A 1 s grid with a 1 ms correlation time forgets everything between samples
    (``exp(-1000)`` underflows to exactly zero); the same grid with a 10 s
    correlation time keeps 90 %:

    >>> import numpy as np
    >>> grid = np.arange(4.0)
    >>> ar1_coefficients(grid, correlation_time_s=0.001)
    array([0., 0., 0., 0.])
    >>> np.round(ar1_coefficients(grid, correlation_time_s=10.0), 4)
    array([0.    , 0.9048, 0.9048, 0.9048])

    On a non-uniform axis each step carries its own coefficient:

    >>> np.round(ar1_coefficients(np.array([0.0, 1.0, 3.0, 3.5]), correlation_time_s=1.0), 4)
    array([0.    , 0.3679, 0.1353, 0.6065])
    """
    axis = _validated_axis("t_s", t_s)
    tau = _validated_correlation_time_s("correlation_time_s", correlation_time_s)
    coefficients = np.zeros(axis.shape, dtype=np.float64)
    if axis.size > 1:
        coefficients[1:] = np.exp(-np.diff(axis) / tau)
    return coefficients


def dwell_averaged_variance_reduction(
    dwell_s: FloatArray | float, *, correlation_time_s: float
) -> FloatArray:
    r"""Return the variance of a unit-variance OU driver averaged over a window.

    What it computes, and where it comes from
    -----------------------------------------
    For a stationary process ``x`` with autocovariance ``exp(-|dt| / tau)``,
    the average over a window of length ``T`` has variance

    .. math::

        w(u) = \frac{2}{u^2}\,(u - 1 + e^{-u}), \qquad u = T / \tau,

    which is the double integral of the autocovariance over the window,
    divided by ``T^2``. Three lines: ``Var(mean) = (1/T^2) \int_0^T \int_0^T
    e^{-|t-s|/\tau} \,ds\,dt``, the inner integral is ``\tau (2 - e^{-t/\tau}
    - e^{-(T-t)/\tau})``, and the outer one gives the closed form. The two
    limits say what it means: ``w -> 1`` as ``T << tau`` (averaging over a
    window shorter than the memory changes nothing) and ``w -> 2 tau / T`` as
    ``T >> tau`` (the window holds ``T / (2 tau)`` independent pieces, and the
    factor two is because an exponential correlation counts as a piece of
    length ``2 tau`` under a double integral).

    Why it is the quantity that belongs in a counts model
    ----------------------------------------------------
    A sample of a pass speaks for its dwell time of pulses, and the detections
    those pulses produce are set by the *time average* of the transmittance
    over the dwell, because the counts model is linear in the transmittance to
    ``eta mu``, which on the reference link is below ``5e-4``. Feeding it an
    instantaneous draw instead overstates each sample's fluctuation by ``1/w``:
    for a 1 s dwell and a 1 ms correlation time that is a factor of **500** in
    variance, which is the difference between a P5 that is real and one that is
    an artefact of the grid.

    Parameters
    ----------
    dwell_s : FloatArray or float
        Window length ``T``, seconds, non-negative. Zero means no averaging and
        returns 1. Any shape.
    correlation_time_s : float
        ``tau``, seconds, strictly positive.

    Returns
    -------
    FloatArray
        ``w`` in ``(0, 1]``, shaped like ``dwell_s``.

    Raises
    ------
    DomainError
        If any dwell is negative or non-finite, or ``tau`` is not finite and
        positive.

    Examples
    --------
    >>> import numpy as np
    >>> np.round(
    ...     dwell_averaged_variance_reduction(
    ...         np.array([0.0, 0.001, 1.0, 1000.0]), correlation_time_s=1.0
    ...     ),
    ...     6,
    ... )
    array([1.      , 0.999667, 0.735759, 0.001998])

    The ``T >> tau`` limit: one second of a millisecond process holds five
    hundred independent pieces.

    >>> float(np.round(1.0 / dwell_averaged_variance_reduction(1.0, correlation_time_s=1e-3), 1))
    500.5
    """
    window = np.asarray(dwell_s, dtype=np.float64)
    if not np.all(np.isfinite(window)) or np.any(window < 0.0):
        raise DomainError(
            "dwell_s must be finite and non-negative: it is the length of the window a sample "
            "speaks for, in seconds. Zero is allowed and means no averaging. Got range "
            f"[{float(np.min(window)) if window.size else float('nan')}, "
            f"{float(np.max(window)) if window.size else float('nan')}]."
        )
    tau = _validated_correlation_time_s("correlation_time_s", correlation_time_s)
    u = window / tau
    # The closed form cancels two O(u) terms into an O(u^2) one, so below the
    # switch a five-term series is used instead; see _SERIES_SWITCH.
    safe = np.where(u > _SERIES_SWITCH, u, 1.0)
    closed = 2.0 * (np.expm1(-safe) + safe) / safe**2
    series = 1.0 - u / 3.0 + u**2 / 12.0 - u**3 / 60.0 + u**4 / 360.0
    reduction: FloatArray = np.where(u > _SERIES_SWITCH, closed, series)
    return reduction


def _dwell_mean_coefficient(u: FloatArray) -> FloatArray:
    """Return ``(1 - exp(-u)) / u``: the covariance of a window's mean with its endpoints.

    ``Cov(mean over [0, T], x(0)) = (1/T) int_0^T e^{-t/tau} dt = (tau/T)(1 -
    e^{-T/tau})``, and by stationarity the covariance with ``x(T)`` is the same.
    Series below the switch for the same reason as the reduction.
    """
    safe = np.where(u > _SERIES_SWITCH, u, 1.0)
    closed = -np.expm1(-safe) / safe
    series = 1.0 - u / 2.0 + u**2 / 6.0 - u**3 / 24.0
    coefficient: FloatArray = np.where(u > _SERIES_SWITCH, closed, series)
    return coefficient


def _instantaneous_driver(
    rng: np.random.Generator, *, realisations: int, t_s: FloatArray, correlation_time_s: float
) -> FloatArray:
    """Return ``(realisations, n)`` samples of a unit-variance OU process at ``t_s``.

    The exact recursion of :func:`ar1_coefficients`, vectorised over
    realisations and looped over time, because the coefficient may differ at
    every step. All noise is drawn in one call so that the stream consumed is a
    function of ``(realisations, n)`` alone.
    """
    phi = ar1_coefficients(t_s, correlation_time_s=correlation_time_s)
    n = phi.size
    noise = rng.standard_normal((n, realisations))
    innovation = np.sqrt(1.0 - phi**2)
    paths = np.empty((n, realisations), dtype=np.float64)
    previous = np.zeros(realisations, dtype=np.float64)
    for i in range(n):
        previous = phi[i] * previous + innovation[i] * noise[i]
        paths[i] = previous
    return np.ascontiguousarray(paths.T)


def _dwell_averaged_driver(
    rng: np.random.Generator,
    *,
    realisations: int,
    t_s: FloatArray,
    dwell_s: FloatArray,
    correlation_time_s: float,
) -> tuple[FloatArray, FloatArray]:
    r"""Return the standardised window means of an OU driver and their raw variances.

    Sample ``i`` owns the window ``[t_i - T_i/2, t_i + T_i/2]``. The recursion
    carries the process value at the end of the previous window, bridges the
    gap to the start of this one (zero inside a pass, hours between passes)
    with an ordinary AR(1) step, and then draws the window's endpoint and its
    time average **jointly**. Conditional on the value ``x_s`` at the window
    start, with ``phi = e^{-u}``, ``c = (1 - phi) / u`` and ``v = w(u)``::

        x_end | x_s  ~  N(phi x_s, 1 - phi^2)
        mean  | x_s  ~  N(c x_s,   v - c^2),   Cov(mean, x_end | x_s) = c (1 - phi)

    which is realised with two independent standard normals as
    ``x_end = phi x_s + sqrt(1 - phi^2) e_1`` and
    ``mean = c x_s + c sqrt((1 - phi)/(1 + phi)) e_1 + r e_2`` with
    ``r^2 = v - 2 c^2 / (1 + phi)``. The three covariances are the integrals of
    ``e^{-|t-s|/tau}`` over the window, and ``r^2`` is non-negative for every
    ``u`` (it is ``u / 6`` as ``u -> 0`` and ``2 / u`` as ``u -> inf``); the
    ``maximum`` guards only the rounding of the ``u -> 0`` cancellation.

    Returns the means divided by ``sqrt(v)``, so that they have unit variance
    and the correlation structure of the true window means, plus ``v`` itself.
    """
    tau = correlation_time_s
    n = t_s.size
    u = dwell_s / tau
    phi = np.exp(-u)
    c = _dwell_mean_coefficient(u)
    v = dwell_averaged_variance_reduction(dwell_s, correlation_time_s=tau)
    residual = np.sqrt(np.maximum(v - 2.0 * c**2 / (1.0 + phi), 0.0))
    end_innovation = np.sqrt(1.0 - phi**2)
    shared = c * np.sqrt((1.0 - phi) / (1.0 + phi))

    lower = t_s - 0.5 * dwell_s
    upper = t_s + 0.5 * dwell_s
    gap = np.zeros(n, dtype=np.float64)
    if n > 1:
        gap[1:] = np.maximum(lower[1:] - upper[:-1], 0.0)
    gap_phi = np.exp(-gap / tau)
    gap_phi[0] = 0.0
    gap_innovation = np.sqrt(1.0 - gap_phi**2)

    noise = rng.standard_normal((3, n, realisations))
    means = np.empty((n, realisations), dtype=np.float64)
    state = np.zeros(realisations, dtype=np.float64)
    for i in range(n):
        start = gap_phi[i] * state + gap_innovation[i] * noise[0, i]
        means[i] = c[i] * start + shared[i] * noise[1, i] + residual[i] * noise[2, i]
        state = phi[i] * start + end_innovation[i] * noise[1, i]
    standardised = np.ascontiguousarray(means.T) / np.sqrt(v)
    return standardised, v


# --------------------------------------------------------------------------- #
# Realisations
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False, slots=True)
class FadeRealisations:
    """An ensemble of fade factors along one time axis, with its components.

    Attributes
    ----------
    t_s : FloatArray
        The sample instants, shape ``(n,)``.
    factor : FloatArray
        Relative transmittance factor, shape ``(realisations, n)``: the product
        of :attr:`scintillation` and :attr:`pointing`. Multiply the fade-free
        transmittance by it. Non-negative; its expectation is
        :attr:`mean_pointing_factor`, **not** one.
    scintillation : FloatArray
        The scintillation factor alone, shape ``(realisations, n)``, of
        expectation exactly 1.
    pointing : FloatArray
        The pointing factor alone, shape ``(realisations, n)``, in ``[0, 1]``,
        of expectation :attr:`mean_pointing_factor`.
    mean_pointing_factor : FloatArray
        ``gamma^2 / (gamma^2 + 1)`` per sample, shape ``(n,)``. What the
        pointing factor averages to, so that a caller knows the ensemble's mean
        transmittance without estimating it.
    scintillation_variance_reduction, pointing_variance_reduction : FloatArray
        The ``w`` applied to each component per sample, shape ``(n,)``; all
        ones when the factors are instantaneous. Carried because the size of
        the dwell reduction is the single number that says whether correlation
        matters on this grid.
    parameters : FadingParameters
        The correlation times these were drawn with.

    Raises
    ------
    DomainError
        If the shapes disagree, if any factor is negative or non-finite, or if
        a pointing factor exceeds one.
    """

    t_s: FloatArray
    factor: FloatArray
    scintillation: FloatArray
    pointing: FloatArray
    mean_pointing_factor: FloatArray
    scintillation_variance_reduction: FloatArray
    pointing_variance_reduction: FloatArray
    parameters: FadingParameters

    def __post_init__(self) -> None:
        """Validate the shape contract and the ranges, then freeze."""
        if not isinstance(self.parameters, FadingParameters):
            raise DomainError(
                f"parameters must be a FadingParameters, got {type(self.parameters).__name__}."
            )
        axis = np.asarray(self.t_s, dtype=np.float64)
        if axis.ndim != 1:
            raise DomainError(f"t_s must be 1-D, got shape {axis.shape}.")
        n = axis.size
        object.__setattr__(self, "t_s", frozen_view(axis))
        for name in ("factor", "scintillation", "pointing"):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.ndim != 2 or value.shape[1] != n:
                raise DomainError(
                    f"{name} must have shape (realisations, {n}), got {value.shape}. The second "
                    "axis is the time axis of t_s; the first is the ensemble."
                )
            if not np.all(np.isfinite(value)) or np.any(value < 0.0):
                raise DomainError(
                    f"{name} must be finite and non-negative: it multiplies a transmittance, and "
                    "a negative transmittance is not a deep fade but a sign error."
                )
            object.__setattr__(self, name, frozen_view(value))
        if (
            self.factor.shape != self.scintillation.shape
            or self.factor.shape != self.pointing.shape
        ):
            raise DomainError(
                f"factor {self.factor.shape}, scintillation {self.scintillation.shape} and "
                f"pointing {self.pointing.shape} must share one shape."
            )
        if np.any(self.pointing > 1.0):
            raise DomainError(
                "pointing must not exceed 1: it is the relative factor of quoss.channel.pointing, "
                "normalised so that perfect aim keeps everything, and a value above one means an "
                "absolute coupling was multiplied in."
            )
        for name in (
            "mean_pointing_factor",
            "scintillation_variance_reduction",
            "pointing_variance_reduction",
        ):
            value = np.asarray(getattr(self, name), dtype=np.float64)
            if value.shape != (n,):
                raise DomainError(f"{name} must have shape ({n},), got {value.shape}.")
            if not np.all(np.isfinite(value)) or np.any(value <= 0.0) or np.any(value > 1.0):
                raise DomainError(f"{name} must lie in (0, 1], got a value outside it.")
            object.__setattr__(self, name, frozen_view(value))

    @property
    def realisations(self) -> int:
        """Number of sample paths."""
        return int(self.factor.shape[0])

    @property
    def n(self) -> int:
        """Number of samples along the time axis."""
        return int(self.factor.shape[1])

    @property
    def shape(self) -> tuple[int, int]:
        """``(realisations, n)``."""
        return (self.realisations, self.n)

    def __repr__(self) -> str:
        return (
            f"FadeRealisations(shape={self.shape}, "
            f"factor=[{float(self.factor.min()):.4f}, {float(self.factor.max()):.4f}], "
            f"{self.parameters!r})"
        )


def sample_fade_factors(
    t_s: FloatArray,
    *,
    realisations: int,
    log_irradiance_variance_np2: FloatArray | float,
    beam_to_jitter_ratio: FloatArray | float,
    parameters: FadingParameters,
    rng: np.random.Generator,
    degradations: DegradationLog,
    dwell_s: FloatArray | None = None,
) -> FadeRealisations:
    r"""Draw an ensemble of correlated fade factors along a time axis.

    What it returns
    ---------------
    ``realisations`` sample paths of the relative transmittance factor
    ``F = F_s F_p`` at every instant of ``t_s``, with the scintillation and
    pointing parts separately, built exactly as the module docstring derives:
    three independent unit-variance Ornstein-Uhlenbeck drivers — one for the
    log-irradiance at the scintillation correlation time, two for the jitter
    axes at the pointing one — pushed through::

        F_s = exp(sigma x - sigma^2 / 2)                 E[F_s] = 1
        F_p = exp(-(x_1^2 + x_2^2) / (2 gamma^2))        E[F_p] = gamma^2 / (gamma^2 + 1)

    With ``dwell_s`` omitted these are **instantaneous** factors: their
    marginals are exactly the channel's — the log-normal of
    :func:`~quoss.channel.link_budget.scintillation_fade_db` and the power law
    ``x^(gamma^2)`` of :mod:`quoss.channel.pointing` — and their
    autocorrelation is exactly ``exp(-|dt| / tau)`` in the Gaussian domain.
    This is the form for fade-duration statistics and for any grid fine
    against ``tau``.

    With ``dwell_s`` given, sample ``i`` is the **average of the factor over
    the window** ``[t_i - T_i/2, t_i + T_i/2]``, which is the quantity a
    counts model must be fed on a grid coarse against ``tau``: the Gaussian
    drivers are sampled as exact window means (jointly with their endpoints, so
    that neighbouring windows keep their true correlation), the nonlinearity is
    evaluated on the standardised mean, and the result is shrunk toward the
    marginal mean by ``sqrt(w)`` with ``w`` the
    :func:`dwell_averaged_variance_reduction` of the driver — at ``tau`` for
    scintillation and at ``tau / 2`` for pointing, because the pointing factor
    depends on the *square* of its drivers and ``E[x_t^2 x_s^2] - 1 =
    2 exp(-2|t-s|/tau)``. That construction has exactly the right mean at
    every ``T / tau``, is exact in both limits, and reproduces the variance
    and the cross-window covariance of the true average to first order in
    ``sigma^2`` and ``1 / gamma^2`` in between; ``TestTheDwellAverage``
    measures the residual against a brute-force fine-grid average.

    Why the dwell average is the right thing to hand a counts model
    --------------------------------------------------------------
    Because the counts are linear in the transmittance. A gate clicks with
    probability ``1 - exp(-(eta mu + noise))``, and with ``eta mu`` below
    ``5e-4`` on the reference link the curvature is below ``3e-4`` of the
    value, so the detections a sample's pulses produce are its pulse count
    times the *time-averaged* transmittance to that precision. An instantaneous
    draw per sample would instead say that all of a second's pulses saw one
    fade, and on a 1 s grid with a 1 ms correlation time that overstates the
    sample's fluctuation five hundredfold.

    Parameters
    ----------
    t_s : FloatArray
        Sample instants, seconds, 1-D and non-decreasing. Hand over **one
        pass**, or one contiguous stretch: the process is never reset inside
        this function, and a caller who wants independent passes calls it once
        per pass — which is what ``monte_carlo.py`` does, because the hours
        between passes are more than ``exp(-gap / tau)`` can survive for any
        physical ``tau``.
    realisations : int
        Number of sample paths, at least 1.
    log_irradiance_variance_np2 : FloatArray or float
        ``sigma^2`` per sample, Np^2, non-negative, shape ``(n,)`` or scalar.
        From :func:`~quoss.channel.turbulence.downlink_log_irradiance_variance`.
    beam_to_jitter_ratio : FloatArray or float
        ``gamma`` per sample, strictly positive, shape ``(n,)`` or scalar. From
        :func:`~quoss.channel.pointing.beam_to_jitter_ratio`.
    parameters : FadingParameters
        The two correlation times.
    rng : numpy.random.Generator
        The injected generator. The stream consumed is a function of the
        shapes alone, so an ensemble reproduces from its seed whatever else
        the caller did with other generators.
    degradations : DegradationLog
        Receives a warning if instantaneous factors are requested on a grid
        whose every step exceeds fourteen correlation times — the case in which
        the returned samples are independent draws and would overstate a
        block's fluctuation if multiplied into per-sample counts.
    dwell_s : FloatArray, optional
        Window each sample speaks for, seconds, non-negative, shape ``(n,)``.
        Omit for instantaneous factors.

    Returns
    -------
    FadeRealisations
        The ensemble, shape ``(realisations, n)``, with its components.

    Raises
    ------
    DomainError
        If any argument fails its own guard, or the per-sample arrays do not
        broadcast to ``t_s``.

    Examples
    --------
    Instantaneous factors on a millisecond grid, with the reference link's
    ``sigma^2`` at 20 degrees and its ``gamma``:

    >>> import numpy as np
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.core.rng import RandomSource
    >>> rng = RandomSource.from_seed(7).generator
    >>> parameters = FadingParameters(
    ...     scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=0.02
    ... )
    >>> fades = sample_fade_factors(
    ...     np.arange(0.0, 1.0, 1e-3),
    ...     realisations=4,
    ...     log_irradiance_variance_np2=0.01528,
    ...     beam_to_jitter_ratio=4.407,
    ...     parameters=parameters,
    ...     rng=rng,
    ...     degradations=DegradationLog(),
    ... )
    >>> fades.shape
    (4, 1000)
    >>> np.round(fades.mean_pointing_factor[0], 4)
    np.float64(0.951)

    The pointing factor decorrelates ten times more slowly than the
    scintillation one, and both correlate between neighbouring milliseconds:

    >>> def lag_one(paths):
    ...     centred = paths - paths.mean()
    ...     return float((centred[:, 1:] * centred[:, :-1]).mean() / centred.var())
    >>> lag_one(fades.scintillation) > 0.5, lag_one(fades.pointing) > 0.9
    (True, True)

    The same link on the project's 1 s grid, with dwell averaging: every sample
    is the mean of hundreds of fades, so the factors barely move.

    >>> averaged = sample_fade_factors(
    ...     np.arange(5.0),
    ...     realisations=4,
    ...     log_irradiance_variance_np2=0.01528,
    ...     beam_to_jitter_ratio=4.407,
    ...     parameters=parameters,
    ...     rng=rng,
    ...     degradations=DegradationLog(),
    ...     dwell_s=np.ones(5),
    ... )
    >>> np.round(averaged.scintillation_variance_reduction[0], 4)
    np.float64(0.004)
    >>> bool(np.all(np.abs(averaged.factor - averaged.mean_pointing_factor) < 0.05))
    True
    """
    axis = _validated_axis("t_s", t_s)
    n = axis.size
    count = _validated_realisations(realisations)
    if not isinstance(parameters, FadingParameters):
        raise DomainError(
            f"parameters must be a FadingParameters, got {type(parameters).__name__}."
        )
    generator = _validated_generator(rng)

    variance = np.asarray(log_irradiance_variance_np2, dtype=np.float64)
    if not np.all(np.isfinite(variance)) or np.any(variance < 0.0):
        raise DomainError(
            "log_irradiance_variance_np2 must be finite and non-negative. It is sigma^2 of the "
            "log-irradiance in Np^2 from quoss.channel.turbulence, not a scintillation index and "
            "not a decibel figure."
        )
    gamma = np.asarray(beam_to_jitter_ratio, dtype=np.float64)
    if not np.all(np.isfinite(gamma)) or np.any(gamma <= 0.0):
        raise DomainError(
            "beam_to_jitter_ratio must be finite and strictly positive. It is gamma from "
            "quoss.channel.pointing.beam_to_jitter_ratio, a beam radius in units of jitter."
        )
    try:
        variance = np.broadcast_to(variance, (n,)).astype(np.float64)
        gamma = np.broadcast_to(gamma, (n,)).astype(np.float64)
    except ValueError as exc:
        raise DomainError(
            f"log_irradiance_variance_np2 {variance.shape} and beam_to_jitter_ratio "
            f"{gamma.shape} must broadcast to the ({n},) shape of t_s: one value per sample, or "
            "one for all of them."
        ) from exc

    tau_s = parameters.scintillation_correlation_time_s
    tau_p = parameters.pointing_correlation_time_s
    if dwell_s is None:
        z_s = _instantaneous_driver(
            generator, realisations=count, t_s=axis, correlation_time_s=tau_s
        )
        z_p1 = _instantaneous_driver(
            generator, realisations=count, t_s=axis, correlation_time_s=tau_p
        )
        z_p2 = _instantaneous_driver(
            generator, realisations=count, t_s=axis, correlation_time_s=tau_p
        )
        w_s = np.ones(n, dtype=np.float64)
        w_p = np.ones(n, dtype=np.float64)
        if n > 1:
            longest_memory = max(
                float(ar1_coefficients(axis, correlation_time_s=tau_s)[1:].max()),
                float(ar1_coefficients(axis, correlation_time_s=tau_p)[1:].max()),
            )
            if longest_memory < _INDEPENDENT_SAMPLES_COEFFICIENT:
                degradations.warn(
                    "correlated_fading.samples-independent",
                    "instantaneous fade factors were requested on a grid whose every step is "
                    "more than fourteen correlation times long (largest AR(1) coefficient "
                    f"{longest_memory:.1e}), so the samples are independent draws and carry no "
                    "temporal correlation at all. That is correct for a marginal, and wrong if "
                    "these factors multiply per-sample counts: each sample's pulses would all "
                    "see one fade, overstating the block's fluctuation by the ratio of the "
                    "dwell to twice the correlation time. Pass dwell_s to get the dwell-averaged "
                    "factor a counts model needs.",
                    where="quoss.system.correlated_fading.sample_fade_factors",
                    largest_coefficient=longest_memory,
                    scintillation_correlation_time_s=tau_s,
                    pointing_correlation_time_s=tau_p,
                )
    else:
        window = np.asarray(dwell_s, dtype=np.float64)
        if window.shape != (n,):
            raise DomainError(
                f"dwell_s must have shape ({n},) like t_s, got {window.shape}: one window per "
                "sample."
            )
        if not np.all(np.isfinite(window)) or np.any(window < 0.0):
            raise DomainError("dwell_s must be finite and non-negative, in seconds.")
        z_s, w_s = _dwell_averaged_driver(
            generator, realisations=count, t_s=axis, dwell_s=window, correlation_time_s=tau_s
        )
        z_p1, _ = _dwell_averaged_driver(
            generator, realisations=count, t_s=axis, dwell_s=window, correlation_time_s=tau_p
        )
        z_p2, _ = _dwell_averaged_driver(
            generator, realisations=count, t_s=axis, dwell_s=window, correlation_time_s=tau_p
        )
        # The pointing factor is a function of the squared drivers, whose
        # autocovariance is 2 exp(-2|dt|/tau): the factor decorrelates at tau/2.
        w_p = dwell_averaged_variance_reduction(window, correlation_time_s=0.5 * tau_p)

    sigma = np.sqrt(variance)
    scintillation_instant = np.exp(sigma * z_s - 0.5 * variance)
    scintillation = 1.0 + (scintillation_instant - 1.0) * np.sqrt(w_s)

    mean_pointing = gamma**2 / (gamma**2 + 1.0)
    pointing_instant = np.exp(-(z_p1**2 + z_p2**2) / (2.0 * gamma**2))
    pointing = mean_pointing + (pointing_instant - mean_pointing) * np.sqrt(w_p)

    return FadeRealisations(
        t_s=axis,
        factor=scintillation * pointing,
        scintillation=scintillation,
        pointing=pointing,
        mean_pointing_factor=mean_pointing,
        scintillation_variance_reduction=w_s,
        pointing_variance_reduction=w_p,
        parameters=parameters,
    )


# --------------------------------------------------------------------------- #
# Fade durations
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, eq=False, slots=True)
class FadeDurationStatistics:
    """How long, how often and what fraction of the time a factor sits below a threshold.

    One value of each per realisation, because the spread *between*
    realisations is part of the answer: a pass with two long fades and a pass
    with none are both draws from the same process.

    Attributes
    ----------
    threshold : float
        The level a fade is counted below.
    count : IntArray
        Number of fades — maximal runs of consecutive samples below the
        threshold — per realisation, shape ``(realisations,)``. A run that is
        already in progress at the first sample counts as one.
    mean_duration_s : FloatArray
        Mean length of those runs, seconds, per realisation. ``nan`` where the
        count is zero: "no fade happened" has no mean duration, and reporting
        zero would be a plausible number for a fade that did not exist.
    time_fraction : FloatArray
        Fraction of the axis spent below the threshold, per realisation. Its
        expectation is the marginal outage probability, which is what ties
        these statistics to the channel's own: for the pointing factor it is
        ``threshold^(gamma^2)`` and ``TestFadeDurations`` checks it against
        :func:`~quoss.channel.pointing.pointing_outage_probability`.
    steps : int
        Number of steps in the axis, ``n - 1``. The count is a count of
        down-crossings *at this step*, and the docstring of
        :func:`fade_duration_statistics` says why no step-free rate exists.
    total_time_s : float
        Length of the axis as the sum of the per-sample spacings, seconds.
    """

    threshold: float
    count: IntArray
    mean_duration_s: FloatArray
    time_fraction: FloatArray
    steps: int
    total_time_s: float

    @property
    def count_per_step(self) -> FloatArray:
        """Down-crossings per grid step, ``count / steps``; zero for a one-sample axis."""
        if self.steps == 0:
            return np.zeros(self.count.shape, dtype=np.float64)
        rate: FloatArray = self.count / float(self.steps)
        return rate


def fade_duration_statistics(
    factor: FloatArray, t_s: FloatArray, *, threshold: float
) -> FadeDurationStatistics:
    r"""Return the duration, count and time fraction of fades below a threshold.

    What it computes
    ----------------
    A **fade** here is a maximal run of consecutive samples at which
    ``factor < threshold``. Its duration is the time from the first sample of
    the run to the first sample after it — the forward spacing of every sample
    in the run summed, the last sample of the axis taking the spacing before
    it — so on a uniform grid a run of ``k`` samples lasts ``k dt``. The count
    is the number of runs, the time fraction is the summed forward spacing of
    all samples below the threshold over the axis length.

    Why it is a discrete count at a stated step, and not a rate
    -----------------------------------------------------------
    For a differentiable stationary Gaussian process Rice's formula gives the
    expected number of up-crossings of a level per unit time in closed form,
    and one would test against it. An Ornstein-Uhlenbeck path is not
    differentiable — its increments over ``dt`` are of size ``sqrt(dt)``, not
    ``dt`` — so the continuous-time crossing rate is **infinite**: refine the
    grid and the count keeps growing, because a path near the threshold crosses
    it arbitrarily many times in any interval. The quantity that exists is the
    expected number of down-crossings *per grid step*, which for a Gaussian
    driver at level ``c`` is the exact bivariate-normal probability
    ``P(x_{i-1} >= c, x_i < c) = Phi(c) - Phi_2(c, c; phi)`` with
    ``phi = exp(-dt / tau)``, and that is what ``TestFadeDurations`` checks
    :attr:`FadeDurationStatistics.count_per_step` against. The step is
    therefore reported alongside the count; a count without its step is a
    number nothing can be compared with.

    This is also the one place the difference between correlated and i.i.d.
    sampling is not a matter of degree. Independent draws at outage ``p`` give
    ``p (1 - p)`` fades per step of mean length ``1 / (1 - p)`` steps whatever
    the grid; the correlated process gives fades whose length in steps grows
    as ``tau / dt``. Refine a 1 s grid to 1 ms under an i.i.d. model and the
    fades stay one sample long — a millisecond instead of a second — while
    under the correlated one they keep their physical length.

    Parameters
    ----------
    factor : FloatArray
        Fade factors of shape ``(realisations, n)``; a 1-D array is one
        realisation.
    t_s : FloatArray
        The axis the factors are on, shape ``(n,)``, non-decreasing.
    threshold : float
        The level, strictly positive and finite.

    Returns
    -------
    FadeDurationStatistics
        Per-realisation statistics.

    Raises
    ------
    DomainError
        If the shapes disagree, the axis is not a valid one, or the threshold
        is not positive and finite.

    Examples
    --------
    Two realisations on a 1 s grid, one with two short fades and one with a
    single long one:

    >>> import numpy as np
    >>> factor = np.array(
    ...     [
    ...         [1.0, 0.2, 1.0, 1.0, 0.3, 0.1, 1.0, 1.0],
    ...         [1.0, 1.0, 0.1, 0.1, 0.1, 0.1, 0.1, 1.0],
    ...     ]
    ... )
    >>> stats = fade_duration_statistics(factor, np.arange(8.0), threshold=0.5)
    >>> stats.count
    array([2, 1])
    >>> stats.mean_duration_s
    array([1.5, 5. ])
    >>> stats.time_fraction
    array([0.375, 0.625])

    Both realisations spend a comparable fraction of the time faded; only the
    duration statistics tell them apart, which is the point of the function.
    """
    level = float(threshold)
    if not np.isfinite(level) or level <= 0.0:
        raise DomainError(
            f"threshold must be finite and strictly positive, got {level}. It is a relative "
            "transmittance factor, so a 3 dB fade threshold is 0.5."
        )
    axis = _validated_axis("t_s", t_s)
    paths = np.asarray(factor, dtype=np.float64)
    if paths.ndim == 1:
        paths = paths[np.newaxis, :]
    if paths.ndim != 2 or paths.shape[1] != axis.size:
        raise DomainError(
            f"factor must have shape (realisations, {axis.size}) to match t_s, got {paths.shape}."
        )
    if not np.all(np.isfinite(paths)):
        raise DomainError("factor contains non-finite values.")

    n = axis.size
    spacing = np.zeros(n, dtype=np.float64)
    if n > 1:
        spacing[:-1] = np.diff(axis)
        spacing[-1] = spacing[-2]
    total = float(spacing.sum())

    below: BoolArray = paths < level
    starts = below.copy()
    starts[:, 1:] &= ~below[:, :-1]
    count = starts.sum(axis=1).astype(np.int64)
    faded_time = (below * spacing).sum(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        mean_duration = np.where(count > 0, faded_time / np.where(count > 0, count, 1), np.nan)
        fraction = faded_time / total if total > 0.0 else np.zeros(count.shape)
    return FadeDurationStatistics(
        threshold=level,
        count=count,
        mean_duration_s=np.asarray(mean_duration, dtype=np.float64),
        time_fraction=np.asarray(fraction, dtype=np.float64),
        steps=n - 1,
        total_time_s=total,
    )


# --------------------------------------------------------------------------- #
# Choosing a correlation time
# --------------------------------------------------------------------------- #
def taylor_correlation_time_s(
    correlation_width_m: FloatArray | float, transverse_speed_m_s: FloatArray | float
) -> FloatArray:
    r"""Return ``l / v``: the time a frozen pattern of width ``l`` takes to pass at speed ``v``.

    The derivation, which is the whole content
    ------------------------------------------
    Taylor's frozen-turbulence hypothesis says that over the time a pattern
    takes to cross the line of sight it does not evolve, it is only carried:
    the irradiance at a fixed point at time ``t + dt`` is the irradiance that
    was a distance ``v dt`` upstream at time ``t``. A spatial correlation of
    width ``l`` therefore becomes a temporal correlation of width ``l / v``,
    and nothing else enters. That is one line of kinematics; the hypothesis is
    named for G. I. Taylor (1938), a paper not opened for this project, and
    what is used here does not depend on anything in it beyond the sentence
    above.

    Why this is a helper and not a model
    ------------------------------------
    Because both inputs are order-of-magnitude quantities on a LEO downlink.
    The width ``l`` of the irradiance pattern at the ground is set by the
    Fresnel scale of the dominant turbulent layer, ``sqrt(lambda h)``, which is
    centimetres — and no source opened for this project publishes it for a
    slant path at the precision that would make it a default. The speed ``v``
    is the slew of the line of sight through the layer,
    :func:`slew_transverse_speed_m_s`, plus the wind. Measured on the reference
    pass in ``TestChoosingACorrelationTime``, the slew term at the turbulence
    scale height is tens of metres per second at culmination, an order of
    magnitude above the 2.3 m/s ground wind of ITU-R P.1621, and with a Fresnel
    width the correlation time lands at milliseconds. That is the estimate
    :class:`FadingParameters` asks the caller to own.

    Parameters
    ----------
    correlation_width_m : FloatArray or float
        ``l``, metres, strictly positive.
    transverse_speed_m_s : FloatArray or float
        ``v``, m/s, strictly positive.

    Returns
    -------
    FloatArray
        ``l / v`` in seconds, broadcast over the inputs.

    Raises
    ------
    DomainError
        If either input is not finite and strictly positive.

    Examples
    --------
    A five-centimetre pattern carried at twenty metres per second:

    >>> float(taylor_correlation_time_s(0.05, 20.0))
    0.0025
    """
    width = np.asarray(correlation_width_m, dtype=np.float64)
    speed = np.asarray(transverse_speed_m_s, dtype=np.float64)
    if not np.all(np.isfinite(width)) or np.any(width <= 0.0):
        raise DomainError(
            "correlation_width_m must be finite and strictly positive, in metres: a pattern of "
            "no width has no correlation time."
        )
    if not np.all(np.isfinite(speed)) or np.any(speed <= 0.0):
        raise DomainError(
            "transverse_speed_m_s must be finite and strictly positive, in m/s: a pattern that "
            "does not move has an infinite correlation time, which is not a fade but a bias."
        )
    time: FloatArray = width / speed
    return time


def line_of_sight_angular_rate_rad_s(
    elevation_rad: FloatArray, azimuth_rad: FloatArray, t_s: FloatArray
) -> FloatArray:
    r"""Return the angular speed of the line of sight across the sky, rad/s.

    ``sqrt(el_dot^2 + (az_dot cos el)^2)``: the elevation rate and the azimuth
    rate projected onto the local sky, which is the speed at which the beam's
    footprint sweeps sideways at any height along the path. The two rates are
    central differences on the grid (:func:`numpy.gradient`, second order on
    a non-uniform axis), with the azimuth unwrapped first so that a pass
    through north does not register a ``2 pi`` jump as a slew.

    Not part of :class:`~quoss.orbits.geometry.LookAngles`, which carries the
    *range* rate for Doppler and no angular rate; and a finite difference is
    the honest tool here because the grid step against which the rate is
    wanted is the grid step the pass was sampled on.

    Parameters
    ----------
    elevation_rad, azimuth_rad : FloatArray
        Look angles along the axis, radians, shape ``(n,)`` with ``n >= 2``.
    t_s : FloatArray
        The axis, seconds, strictly increasing.

    Returns
    -------
    FloatArray
        Angular rate, rad/s, shape ``(n,)``.

    Raises
    ------
    DomainError
        If the shapes disagree, the axis has fewer than two samples or is not
        strictly increasing.

    Examples
    --------
    A satellite crossing the zenith at 1 degree per second in elevation alone:

    >>> import numpy as np
    >>> from quoss.core.units import deg_to_rad
    >>> t = np.arange(5.0)
    >>> rate = line_of_sight_angular_rate_rad_s(deg_to_rad(80.0 + t), np.zeros(5), t)
    >>> np.round(rate / deg_to_rad(1.0), 6)
    array([1., 1., 1., 1., 1.])
    """
    axis = _validated_axis("t_s", t_s)
    elevation = np.asarray(elevation_rad, dtype=np.float64)
    azimuth = np.asarray(azimuth_rad, dtype=np.float64)
    if elevation.shape != axis.shape or azimuth.shape != axis.shape:
        raise DomainError(
            f"elevation_rad {elevation.shape} and azimuth_rad {azimuth.shape} must have the "
            f"shape of t_s, {axis.shape}."
        )
    if axis.size < 2 or np.any(np.diff(axis) <= 0.0):
        raise DomainError(
            "t_s must hold at least two strictly increasing instants: a rate is a difference "
            "between samples."
        )
    elevation_rate = np.gradient(elevation, axis)
    azimuth_rate = np.gradient(np.unwrap(azimuth), axis)
    rate: FloatArray = np.sqrt(elevation_rate**2 + (azimuth_rate * np.cos(elevation)) ** 2)
    return rate


def slew_transverse_speed_m_s(
    elevation_rad: FloatArray | float,
    *,
    angular_rate_rad_s: FloatArray | float,
    layer_height_m: float,
) -> FloatArray:
    r"""Return how fast the line of sight moves sideways through a layer at a height.

    ``v = omega h / sin(theta)``: the slant distance from the telescope to a
    layer at height ``h`` seen at elevation ``theta`` is ``h / sin(theta)``,
    and a line of sight turning at ``omega`` moves sideways at that distance
    times ``omega``. At the zenith and 700 km this is the satellite's own
    ground speed scaled by ``h / 700 km``; at low elevation the slant distance
    grows and so does the sweep.

    Which height to use is the caller's choice and the point of the argument:
    :func:`~quoss.channel.turbulence.turbulence_scale_height_m` gives the
    ``C_n^2``-weighted height of the ITU profile, which is where most of the
    scintillation is produced and is the natural single number.

    Parameters
    ----------
    elevation_rad : FloatArray or float
        Elevation, radians, in ``(0, pi/2]``.
    angular_rate_rad_s : FloatArray or float
        ``omega`` from :func:`line_of_sight_angular_rate_rad_s`, rad/s,
        non-negative.
    layer_height_m : float
        ``h``, metres, strictly positive.

    Returns
    -------
    FloatArray
        Transverse speed, m/s, broadcast over the inputs.

    Raises
    ------
    DomainError
        If the elevation is outside ``(0, pi/2]``, the rate is negative, or the
        height is not finite and positive.

    Examples
    --------
    A 700 km satellite at the zenith turns at about 0.0107 rad/s; through a
    layer 7.7 km up that is 82 m/s, far above any wind:

    >>> float(
    ...     np.round(
    ...         slew_transverse_speed_m_s(
    ...             np.pi / 2, angular_rate_rad_s=0.0107, layer_height_m=7700.0
    ...         ),
    ...         1,
    ...     )
    ... )
    82.4
    """
    elevation = np.asarray(elevation_rad, dtype=np.float64)
    if (
        not np.all(np.isfinite(elevation))
        or np.any(elevation <= 0.0)
        or np.any(elevation > 0.5 * np.pi)
    ):
        raise DomainError(
            "elevation_rad must lie in (0, pi/2]: at or below the horizon the slant distance to "
            "any layer is undefined. Radians, so 20 degrees is 0.349."
        )
    rate = np.asarray(angular_rate_rad_s, dtype=np.float64)
    if not np.all(np.isfinite(rate)) or np.any(rate < 0.0):
        raise DomainError("angular_rate_rad_s must be finite and non-negative.")
    height = float(layer_height_m)
    if not np.isfinite(height) or height <= 0.0:
        raise DomainError(
            f"layer_height_m must be finite and strictly positive, got {height}. Metres: the "
            "ITU turbulence scale height is thousands, not a few."
        )
    speed: FloatArray = rate * height / np.sin(elevation)
    return speed
