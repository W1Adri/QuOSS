"""Background light: the counts that arrive when nothing was sent.

What this module is for
-----------------------
A single-photon detector cannot tell a signal photon from a photon of scattered
sunlight, and it cannot tell either from a thermal click of its own. Everything
it reports is a count. The rest of :mod:`quoss.channel` answers "what fraction
of the transmitted photons arrive"; this module answers the other half — **how
many counts arrive that are not signal** — for the part of that noise which
comes from the sky rather than from the detector.

The sky is not a small term. A ground telescope pointed at a satellite is also
pointed at several hundred cubic kilometres of illuminated air, and that air
scatters sunlight into the aperture along the whole line of sight. Measured with
the receiver Ntanos et al. 2021 §4.1 declare (100 urad field of view, 0.2 nm
filter, 2.3 m telescope) the background is **7.6e3 counts per second** on a
clear moonless night and **3.4e9 counts per second** under ITU-R's tabulated
bright sunshine at 850 nm — six orders of magnitude, from the same telescope,
for the same signal. That is why the published QKD downlink budgets of this
literature are nighttime budgets, and why saying so is part of the model rather
than a caveat.

Three quantities, in this order
------------------------------
1. **Radiance** ``H`` — how bright the sky is, per unit area, per unit solid
   angle, per unit wavelength. It comes from a table, not from a formula, and
   the tables are the weakest link in this module (see the gaps below).
2. **Background power** ``P_back`` — what the receiver actually collects, which
   is ``H`` multiplied by the three things the receiver can choose: its solid
   angle, its area, and its filter width.
3. **Counts per gate** — the power divided by the energy of one photon, times
   how long the detector is listening.

The two published equations are the same equation
-------------------------------------------------
ITU-R P.1621-2 equation (1) writes::

    P_back = pi theta_r^2 A_r dlambda H / 4      (theta_r in rad)

and Ntanos et al. 2021 equation (19) writes::

    P_back = H_rad Omega_FOV A_r dlambda         (Omega_FOV in sr)

These are one equation, because ``pi theta^2 / 4`` **is** the solid angle of a
cone of full angle ``theta``. Writing them side by side is worth the space
because of what the pair implies: the two sources give the receiver's field of
view **in different units under the same name**, and Ntanos et al. then declare
their own value as "a narrow FOV of 100 urad" — an angle. Feeding 100 urad to a
formula that wants steradians overestimates the background by a factor of
1.3e4, which is 41 dB, and produces a number that still looks like a count rate.

So this module takes the **angle**, in the ITU convention, and takes it as the
**full cone angle**. That convention is in the parameter name
(``field_of_view_full_angle_rad``) rather than in a comment, because reading it
as a half-angle is a clean factor of four — **6.02 dB** — and neither source
states which it means.

Why the exact solid angle and not ``pi theta^2 / 4``
----------------------------------------------------
:func:`receiver_solid_angle_sr` returns ``2 pi (1 - cos(theta / 2))``, the exact
solid angle of a cone, of which the ITU form is the small-angle limit. For any
real instrument the choice is invisible: at 100 urad the two agree to
**6.1e-9 relative**, twelve digits past anything measurable. The reason to
prefer the exact one is the same as in :mod:`quoss.channel.beam`, where the
truncation integral is preferred to the published gain product — the
approximation has no ceiling. It reads 1 % high at 39.6 deg of full angle, 5.3 %
at 90 deg, and at 360 deg it returns **31.0 sr for a whole sphere that has
4 pi = 12.6**. A formula that can report two and a half spheres of sky is
not one to leave in the path of a parameter sweep.

**The trap this module is shaped to avoid: a mean is not a probability**
------------------------------------------------------------------------
Ntanos et al. equation (20) reads::

    P_noise = t_gate * cps_background

and calls the result "the probability of the detector firing due to a background
noise photon". It is not a probability; it is the **expected number** of
background counts in the gate, which is a probability only while it is much
smaller than one. Background arrivals are Poisson, so the probability that at
least one lands in the gate is ``1 - exp(-mu)``.

Where the difference bites is not an exotic corner. With ITU-R's own tabulated
bright-sunshine radiance at 850 nm (122.3 W/m^2/um/sr, the nearest tabulated
wavelength to the 780-810 nm band this project cares about), Ntanos et al.'s own
receiver and their own 1 ns gate, equation (20) returns a "probability" of
**3.42**. The correct answer is 0.967. Even their smallest telescope reaches
0.363 against a true 0.305, and their middle one, 1.3 m, returns 1.09 — above
unity, from published parameters, with no step that looks wrong.

:func:`background_counts_per_gate` therefore returns ``mu`` and is documented as
a mean; :func:`background_click_probability` returns ``1 - exp(-mu)`` and warns
above :data:`LINEAR_CLICK_PROBABILITY_LIMIT`, which is not a taste threshold:
0.0984 is where the linear reading overshoots by 5 %, and 0.1 (where it
overshoots by 5.08 %) is that root rounded to one digit.

Temporal gating: the one lever that costs almost nothing
--------------------------------------------------------
Everything else in a link budget is fixed by the hardware. The gate width is a
free parameter, and it is the cheapest decibels in the channel, because the two
terms scale differently:

- **Background scales linearly** with the gate. Halve the gate, halve the noise.
  So do the detector's dark counts, which is why narrowing the gate is not
  robbed by them (:mod:`quoss.channel.detector` owns that term, and it obeys the
  same proportionality).
- **Signal does not.** The signal photons all arrive at nearly the same time —
  spread only by the detector's timing jitter and the sync — so a gate several
  jitters wide keeps essentially all of them. Only when the gate approaches the
  jitter does narrowing start to cost signal, and then it costs it as an ``erf``
  (:func:`gate_signal_fraction`).

With the 50 ps jitter Ntanos et al. declare, going from their 1 ns gate to 100 ps
cuts the background by **10.0 dB** and the signal by **0.08 dB**. If the figure
of merit is the shot-noise-limited ``S / sqrt(B)``, the optimum is a gate of
**2.80 jitter standard deviations** (1.19 FWHM, i.e. 59.5 ps here), which beats
the 1 ns gate by 5.36 dB — 12.26 dB of background removed for 0.77 dB of signal.
See :func:`gate_width_maximising_snr_s` for what that figure of merit does and
does not claim: the QKD key rate is a different objective and it lives in
:mod:`quoss.qkd`, and the statement that survives any objective is the monotone
one — the background-to-signal *ratio* falls all the way down.

The sources disagree at night, and it is measured rather than averaged
----------------------------------------------------------------------
ITU-R P.1621-2 §3.1 states that "a reasonable value of H during night-time
operations is (1-2) 10^-6 W/m^2/um/sr for most frequencies of interest". Ntanos
et al. put the moonless clear night at 1.5e-5 at 1550 nm. Those are the same
quantity, from two openable sources, a **factor of ten** apart, and both are
exposed here as named constants rather than reconciled into one default
(:data:`ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR`,
:data:`NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR`), the same treatment as the
Bufton wind coefficients in :mod:`quoss.channel.atmosphere`.

What the disagreement costs is a function of the telescope, which is the part
worth knowing before picking one: against the 300 cps dark-count rate the same
paper declares for its detectors, the two values differ by **1.24x** in total
noise at 0.75 m — the sky is below the detector either way — and by **2.83x** at
2.3 m, where the sky has taken over. A big telescope collects background in
proportion to its area and signal in proportion to its area, so it does not lose
signal-to-noise by growing; what it loses is the licence to ignore which of the
two published night values is right.

By daylight the two sources agree, which is worth recording for the same reason:
ITU-R's 1500 nm column gives 6.00 (normal sunshine) and 4.44 (overcast), and
Ntanos et al.'s clear-sky daylight bracket at 1550 nm is 0.1 to 6. The ITU
bright-sunshine value, 13.01, sits 2.2x above that bracket.

What is deliberately not in here
--------------------------------
**Interpolated radiance dressed as a published value.** ITU-R P.1621-2 Table 1
tabulates 530, 850, 965, 1060 and 1500 nm. This project's wavelengths of
interest include 785 and 810 nm, which are not in it, and that is declared gap 4
of ``docs/adr/0009-citation-policy.md``.
:func:`tabulated_sky_radiance_w_m2_um_sr` refuses anything off the grid;
:func:`interpolated_sky_radiance_w_m2_um_sr` will interpolate and records a
**DEGRADED** entry when it does, carrying the alternative rule's answer with it.
The honest size of that gap is measured in
``tests/channel/test_background.py::TestTheInterpolationGap``: the two defensible
rules differ by 0.48 dB at 785 nm, and — the part that matters — a leave-one-out
test *on the table's own points* is worse than that, 16 % to 27 % for the rule
this module uses (2 % to 32 % for the alternative), because the table straddles
the 940 nm water-vapour band and no smooth rule can cross it.
An interpolated radiance is a number with about a decibel of unquantified error
in it, which is fine to use and not fine to call published.

**Any dependence on where the telescope is pointed.** ITU-R Table 1 is *zenith*
radiance (their Figure 3 says so), and neither source gives an elevation
dependence, a sun-angle dependence, or an azimuth dependence — Ntanos et al.
hold ``H`` constant across a whole pass and say so. All three effects are real
and large: on a plane-parallel atmosphere the scattering path at 20 deg
elevation is 2.92 times longer than at zenith, so if the daytime radiance simply
followed the air mass it would be 4.66 dB brighter there. **That scaling is not
applied here.** ``H`` is an argument, it can be an array over the time axis if a
caller has a model for it, and this module does not invent one.

**Uplink background.** Table 1 is titled "Radiance, H, of the sky **and Earth**"
and prints only the three sky columns; the Earth columns the title promises are
not in the recommendation, although its §3.1 explicitly notes that "spacecraft
pointed at the Earth will also encounter noise from sunlight reflected from the
Earth's surface". So a satellite receiver looking down at a sunlit Earth has no
published radiance in either source, and there is none here. Ntanos et al.
consider the downlink only.

**Moonlight as a function of phase or angular separation.** The only published
handle is a bracket — 1.5e-5 moonless to 1.5e-3 full moon at 1550 nm, a factor
of 100 — and a bracket is what is exposed. A model that turned "full moon 43 deg
away, 2 days past full" into a radiance would need a lunar irradiance model
(ROLO or equivalent) that no free verified source supplied.

**Stars, planets, city lights, aurora, airglow.** P.1621-2 §3.1 lists them and
tabulates none. A ground station near a city has a night sky brighter than any
number here.

**Everything downstream of the aperture.** The filter's insertion loss, the
receiver's optical loss, and the detector's quantum efficiency all attenuate
background exactly as they attenuate signal, so they cancel in every ratio and
belong where they are applied once — :mod:`quoss.channel.detector` and
:mod:`quoss.channel.link_budget`. The counts this module returns are counts
*incident on the aperture*, which is what makes them comparable to the signal
counts computed the same way. Applying the chain here and again there is the
same double-counting mistake :mod:`quoss.channel.pointing` exists to prevent.

**Dark counts, afterpulsing, dead time.** :mod:`quoss.channel.detector`.

**A radiance that varies over the pass.** The array axis is there — ``H`` may be
an array — but nothing here generates the time series.

======================================  ====================================
Symbol                                  Meaning
======================================  ====================================
``H``                                   sky radiance (W/m^2/um/sr)
``theta_r``                             receiver field of view, full angle (rad)
``Omega``                               receiver solid angle (sr)
``A_r``                                 receiver collecting area (m^2)
``dlambda``                             optical filter bandwidth (um in the
                                        sources, m in this API)
``P_back``                              background power at the aperture (W)
``cps``                                 background photon rate (counts/s)
``t_gate``                              detection gate width (s)
``mu``                                  expected background counts per gate
``sigma_t``                             timing jitter standard deviation (s)
======================================  ====================================

References
----------
Recommendation ITU-R P.1621-2, *Propagation data required for the design of
Earth-space systems operating between 20 THz and 375 THz*, 07/2015, §3.1:
Table 1 (sky radiance at five wavelengths), Figure 3 (the spectrum those five
points sample), equation (1) (background power), and the night-time value in the
paragraph above Figure 3.

A. Ntanos et al., "LEO Satellites Constellation-to-Ground QKD Links: Greek
Quantum Communication Infrastructure Paradigm", *Photonics* **8**(12):544, 2021,
§3.7 (equations (19) and (20)), §4.1 (the receiver and detector parameters) and
§4.2.2 (the daylight and nighttime radiance values, and the 10 kcps full-moon
claim discussed in ``tests/channel/test_background.py``).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

import numpy as np
from scipy.special import erf

from quoss.channel._validation import (
    MICROMETRES_PER_METRE,
    validated_duration_s,
    validated_positive_length_m,
    validated_wavelength_m,
)
from quoss.core.constants import PLANCK_J_S, SPEED_OF_LIGHT_M_S
from quoss.core.errors import DegradationLog, DomainError
from quoss.core.types import FloatArray

__all__ = [
    "GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS",
    "ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR",
    "ITU_SKY_RADIANCE_WAVELENGTHS_M",
    "ITU_SKY_RADIANCE_W_M2_UM_SR",
    "LINEAR_CLICK_PROBABILITY_LIMIT",
    "NTANOS_DAYLIGHT_RADIANCE_RANGE_W_M2_UM_SR",
    "NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR",
    "NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR",
    "NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR",
    "SkyCondition",
    "background_click_probability",
    "background_counts_per_gate",
    "background_photon_rate_cps",
    "background_power_w",
    "gate_signal_fraction",
    "gate_width_maximising_snr_s",
    "interpolated_sky_radiance_w_m2_um_sr",
    "receiver_solid_angle_sr",
    "tabulated_sky_radiance_w_m2_um_sr",
]


class SkyCondition(StrEnum):
    """The three illumination conditions ITU-R P.1621-2 Table 1 tabulates.

    A :class:`~enum.StrEnum` for the same reason as
    :class:`quoss.orbits.frames.Frame`: a scenario file writes plain text, and
    the physics layer should compare against a member rather than against a
    string it hopes is spelled right.

    There is no ``NIGHT`` member, and that is the point of the class. Table 1
    has three columns; the night-time value is a sentence of prose in the same
    section, it is not wavelength-resolved, and the two openable sources
    disagree about it by a factor of ten. Giving it a fourth member would put a
    number of a completely different pedigree behind the same lookup. The night
    values are module constants instead, one per source, each carrying which
    source it came from — :data:`ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR` and
    :data:`NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR`.

    Attributes
    ----------
    BRIGHT_SUNSHINE
        Table 1, column "Bright sunshine". The worst tabulated case.
    NORMAL_SUNSHINE
        Table 1, column "Normal sunshine".
    OVERCAST
        Table 1, column "Overcast". Note that it is the *dimmest* of the three
        — cloud reduces the radiance reaching the receiver in this table — while
        being the condition in which no optical link works at all. The two facts
        are not in conflict: this table is about noise, and cloud attenuation is
        a different term (``system/pcflos.py`` decides whether the link exists).
    """

    BRIGHT_SUNSHINE = "bright_sunshine"
    NORMAL_SUNSHINE = "normal_sunshine"
    OVERCAST = "overcast"


ITU_SKY_RADIANCE_WAVELENGTHS_M: Final[tuple[float, float, float, float, float]] = (
    0.530e-6,
    0.850e-6,
    0.965e-6,
    1.06e-6,
    1.50e-6,
)
"""The five wavelengths of ITU-R P.1621-2 Table 1, m.

Printed there as frequencies with their wavelengths alongside — 566.0, 352.9,
310.9, 283.0 and 200.0 THz — and transcribed here from the wavelength column.

Sorted ascending, which :func:`interpolated_sky_radiance_w_m2_um_sr` relies on
and a test asserts, because :func:`numpy.interp` gives silently wrong answers on
an unsorted grid rather than raising.
"""

ITU_SKY_RADIANCE_W_M2_UM_SR: Final[
    Mapping[SkyCondition, tuple[float, float, float, float, float]]
] = MappingProxyType(
    {
        SkyCondition.BRIGHT_SUNSHINE: (303.4, 122.3, 64.62, 54.45, 13.01),
        SkyCondition.NORMAL_SUNSHINE: (101.6, 42.58, 25.12, 25.32, 6.00),
        SkyCondition.OVERCAST: (71.75, 30.3, 18.63, 17.99, 4.44),
    }
)
"""ITU-R P.1621-2 Table 1, transcribed. W/m^2/um/sr, aligned with
:data:`ITU_SKY_RADIANCE_WAVELENGTHS_M`.

A **V2 reference value living next to its citation**, per ADR 0009: fifteen
numbers a reader can check against a free document without running anything.
Read off the rendered page rather than the extracted text layer, because the
text layer of this recommendation drops symbols (it turns equation (1) into
``2r Ar H / 4``).

Two features of the table worth knowing before interpolating in it:

- The normal-sunshine column is **not monotone**: 25.12 at 965 nm and 25.32 at
  1060 nm. Any smooth decreasing fit is wrong about one of them.
- The spectrum steepens sharply after 850 nm — the local log-log slope is -1.92
  between 530 and 850 nm and -5.03 between 850 and 965 nm — because the 940 nm
  water-vapour band sits between the two. The five points sample a curve with
  structure they do not resolve, which is exactly why
  :func:`interpolated_sky_radiance_w_m2_um_sr` records a degradation.

A :class:`~types.MappingProxyType` so that a caller cannot mutate a published
table in place and have every later result silently use the new value.
"""

ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR: Final[tuple[float, float]] = (1.0e-6, 2.0e-6)
"""Night-time sky radiance, ITU-R P.1621-2 §3.1. W/m^2/um/sr.

Verbatim: "A reasonable value of H during night-time operations is
(1-2) 10^-6 W/m^2/um/sr for most frequencies of interest." Prose, not a table:
it carries no wavelength resolution and no moon phase.

**A factor of ten below** :data:`NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR`,
which is the other openable source for the same quantity. Neither is chosen as a
default here; see the module docstring for what the disagreement costs (1.24x in
total noise at 0.75 m, 2.83x at 2.3 m, against a 300 cps dark-count rate).
"""

NTANOS_MOONLESS_NIGHT_RADIANCE_W_M2_UM_SR: Final[float] = 1.5e-5
"""Moonless clear night at 1550 nm, Ntanos et al. 2021 §4.2.2. W/m^2/um/sr.

The bottom of the published nighttime bracket. Ten times
:data:`ITU_NIGHT_SKY_RADIANCE_RANGE_W_M2_UM_SR`; see there.
"""

NTANOS_FULL_MOON_RADIANCE_W_M2_UM_SR: Final[float] = 1.5e-3
"""Full moon, clear night, at 1550 nm, Ntanos et al. 2021 §4.2.2. W/m^2/um/sr.

The top of the published nighttime bracket, a factor of 100 above the moonless
value. The paper adds a checkable consequence — "even in the case of full moon,
the background radiance corresponds to 10 kcps in the photon counter at most" —
and that sentence is **not reproducible** from the parameters the same paper
declares without choosing which of its three telescopes it means: equation (19)
gives 8.1 kcps at 0.75 m, 24.4 kcps at 1.3 m and 76.4 kcps at 2.3 m. See
``tests/channel/test_background.py::TestTheFullMoonClaim``.
"""

NTANOS_STUDY_NIGHT_RADIANCE_W_M2_UM_SR: Final[float] = 1.5e-4
"""The single nighttime value Ntanos et al. 2021 §4.2.2 use for their results.

W/m^2/um/sr, at 1550 nm: "The nighttime solar radiance was set to an average
value of 1.5 x 10^-4 (watt/sr m^2 um) and was kept constant for the needs of the
numerical study." The geometric mean of their own moonless-to-full-moon bracket,
and the value to use when reproducing any figure of that paper.
"""

NTANOS_DAYLIGHT_RADIANCE_RANGE_W_M2_UM_SR: Final[tuple[float, float]] = (0.1, 6.0)
"""Clear-sky daylight radiance at 1550 nm, Ntanos et al. 2021 §4.2.2.
W/m^2/um/sr.

"Typical values for H_rad (watt/sr m^2 um) at 1550 nm for clear sky daylight
conditions may vary between 0.1 and 6". Consistent with ITU-R P.1621-2 Table 1
at the neighbouring 1500 nm, where normal sunshine is 6.00 and overcast 4.44 —
two independent sources landing on the same magnitude, which is not something
this module can say about the night.

The paper's conclusion from these numbers is the one that shapes every published
budget in this literature: "the noise levels even for low solar radiance values
are over the acceptable threshold, and therefore, no QKD link can be
established", so they model nighttime only.
"""

LINEAR_CLICK_PROBABILITY_LIMIT: Final[float] = 0.1
"""Counts per gate above which the linear reading of equation (20) misleads.

Not a taste threshold. Reading ``mu`` as a probability overestimates
``1 - exp(-mu)`` by a factor ``mu / (1 - exp(-mu))``, which reaches 5 % at
``mu = 0.0984``; this is that root rounded to one digit, where the overshoot is
5.08 %. At ``mu = 1`` it is 58 %, and above 1 the linear reading is not a
probability at all.

It doubles as a physical marker, which is why the warning is worth recording
rather than silently correcting: 0.1 background counts per gate is a receiver
collecting one noise photon every ten gates, and no QKD protocol produces a key
there. A result whose ``warnings[]`` carries this code is describing a link that
does not work, not a link whose formula was slightly off.
"""

GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS: Final[float] = 2.799970553756
"""Gate width, in timing-jitter standard deviations, that maximises ``S/sqrt(B)``.

The signal kept by a gate of half-width ``x`` in units of ``sqrt(2) sigma`` is
``erf(x)``; the background (and the dark counts) collected is proportional to
``x``. Maximising ``erf(x) / sqrt(x)`` gives the stationarity condition::

    (4 / sqrt(pi)) x exp(-x^2) = erf(x)

whose root is ``x* = 0.98993908``, so the gate — which is ``2 sqrt(2) sigma x``
wide — is ``2 sqrt(2) x* = 2.79997 sigma``, or 1.18904 FWHM.

**It is not 2.8.** The root is 2.799970553756, which differs from 2.8 in the
fifth decimal; the resemblance is a coincidence of decimal notation and there is
no identity behind it. It is written out here so that nobody "simplifies" it
into one, and ``tests/channel/test_background.py`` re-derives it with a root
finder rather than trusting this constant.

Read :func:`gate_width_maximising_snr_s` before using it: ``S/sqrt(B)`` is the
figure of merit of a shot-noise-limited measurement, not of a QKD protocol.
"""

_FWHM_PER_SIGMA: Final[float] = 2.0 * np.sqrt(2.0 * np.log(2.0))
"""``2 sqrt(2 ln 2) = 2.3548``, the FWHM of a Gaussian in units of its sigma.

Detector datasheets and the reference paper quote timing jitter as a FWHM, so
the conversion happens once, here, at the point where a jitter enters a formula
that needs a standard deviation.
"""


def _validated_radiance(radiance_w_m2_um_sr: FloatArray | float) -> FloatArray:
    """Return the sky radiance as an array, rejecting negatives and non-finites."""
    radiance = np.asarray(radiance_w_m2_um_sr, dtype=np.float64)
    if not np.all(np.isfinite(radiance)):
        raise DomainError("sky_radiance_w_m2_um_sr contains non-finite values.")
    if np.any(radiance < 0.0):
        raise DomainError(
            "sky_radiance_w_m2_um_sr must be non-negative, got a minimum of "
            f"{float(np.min(radiance))}. Zero is accepted — it is the no-background limit and "
            "is exact — but a negative radiance is not a dark sky, it is a sign error. The "
            "unit is W/m^2/um/sr, per micrometre and not per nanometre: a value read off a "
            "W/m^2/nm/sr spectrum is 1000 times too small."
        )
    return radiance


def _validated_field_of_view_rad(field_of_view_full_angle_rad: float) -> float:
    """Return the full-angle field of view, rejecting anything outside ``(0, 2 pi]``."""
    field_of_view = float(field_of_view_full_angle_rad)
    if not np.isfinite(field_of_view) or field_of_view <= 0.0:
        raise DomainError(
            "field_of_view_full_angle_rad must be finite and positive, got "
            f"{field_of_view}. The unit is radians, so a 100 microradian field of view is "
            "1e-4, not 100."
        )
    if field_of_view > 2.0 * np.pi:
        raise DomainError(
            "field_of_view_full_angle_rad must be at most 2 pi (a full sphere), got "
            f"{field_of_view}. This is the full cone angle, not the half-angle and not a "
            "solid angle in steradians: ITU-R P.1621-2 equation (1) writes the solid angle "
            "as pi theta^2 / 4, which is the small-angle solid angle of a cone of half-angle "
            "theta / 2. Passing a solid angle here overestimates the background by about "
            "4 / (pi theta) — a factor of 1.3e4 at the 100 microradian field of view of "
            "Ntanos et al. 2021 §4.1."
        )
    return field_of_view


def _validated_rate_cps(photon_rate_cps: FloatArray | float) -> FloatArray:
    """Return a background count rate as an array, rejecting negatives."""
    rate = np.asarray(photon_rate_cps, dtype=np.float64)
    if not np.all(np.isfinite(rate)):
        raise DomainError("photon_rate_cps contains non-finite values.")
    if np.any(rate < 0.0):
        raise DomainError(
            f"photon_rate_cps must be non-negative, got a minimum of {float(np.min(rate))}. "
            "The unit is counts per second at the aperture, which is what "
            "background_photon_rate_cps returns."
        )
    return rate


def _tabulated_index(wavelength_m: float) -> int | None:
    """Return the index of an exactly tabulated wavelength, or ``None``.

    Compared with a relative tolerance of 1e-9 rather than ``==`` because
    ``0.53e-6`` and ``530e-9`` are the same wavelength written two ways and
    differ in the last bit; and *not* with a loose tolerance, because 1500 nm
    and 1550 nm are 3 % apart and only one of them is in the table.
    """
    for index, tabulated in enumerate(ITU_SKY_RADIANCE_WAVELENGTHS_M):
        if abs(wavelength_m - tabulated) <= 1e-9 * tabulated:
            return index
    return None


def tabulated_sky_radiance_w_m2_um_sr(wavelength_m: float, *, condition: SkyCondition) -> float:
    """Return the published sky radiance, refusing any wavelength not in the table.

    A lookup, not a model: the value comes from ITU-R P.1621-2 Table 1 and this
    function's only job is to make it impossible to get a number out of that
    table at a wavelength the table does not contain.

    That refusal is the whole point, so it is worth defending. The table has
    five entries; the wavelengths this project cares most about (785 and 810 nm,
    where silicon detectors and the published free-space BB84 experiments live)
    are between the first two. Interpolating and returning the result would
    produce a number indistinguishable from a published one — same units, same
    magnitude, same call site — and gap 4 of ``docs/adr/0009-citation-policy.md``
    exists because that number would then be cited as ITU-R's. Anything
    off-grid therefore raises, and names
    :func:`interpolated_sky_radiance_w_m2_um_sr` as the way to say "I know, and
    I want the interpolation anyway".

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m. Must equal one of
        :data:`ITU_SKY_RADIANCE_WAVELENGTHS_M` to a relative tolerance of 1e-9.
    condition
        Which of the three tabulated illumination conditions.

    Returns
    -------
    float
        Sky radiance, W/m^2/um/sr.

    Raises
    ------
    DomainError
        If the wavelength is not finite and positive, or is not one of the five
        tabulated values.

    Examples
    --------
    The 850 nm column, which brackets the 780-810 nm band from above:

    >>> tabulated_sky_radiance_w_m2_um_sr(850e-09, condition=SkyCondition.BRIGHT_SUNSHINE)
    122.3
    >>> tabulated_sky_radiance_w_m2_um_sr(850e-09, condition=SkyCondition.OVERCAST)
    30.3

    1550 nm — the wavelength of the reference paper — is **not** in the table;
    1500 nm is, and the two are 50 nm apart:

    >>> tabulated_sky_radiance_w_m2_um_sr(  # doctest: +ELLIPSIS
    ...     1.55e-06, condition=SkyCondition.NORMAL_SUNSHINE
    ... )
    Traceback (most recent call last):
        ...
    quoss.core.errors.DomainError: wavelength_m = 1.55e-06 m (1550.0 nm) is not one of the five wavelengths of ITU-R P.1621-2 Table 1: 530.0, 850.0, 965.0, 1060.0, 1500.0 nm. ...
    """
    wavelength = validated_wavelength_m(wavelength_m)
    index = _tabulated_index(wavelength)
    if index is None:
        grid_nm = ", ".join(f"{value * 1e9:.1f}" for value in ITU_SKY_RADIANCE_WAVELENGTHS_M)
        raise DomainError(
            f"wavelength_m = {wavelength} m ({wavelength * 1e9} nm) is not one of the five "
            f"wavelengths of ITU-R P.1621-2 Table 1: {grid_nm} nm. This function only returns "
            "published values. For an interpolated one, which is not a published value and is "
            "recorded as a degradation, call "
            "quoss.channel.background.interpolated_sky_radiance_w_m2_um_sr."
        )
    return ITU_SKY_RADIANCE_W_M2_UM_SR[condition][index]


def interpolated_sky_radiance_w_m2_um_sr(
    wavelength_m: float,
    *,
    condition: SkyCondition,
    degradations: DegradationLog,
) -> float:
    """Return a sky radiance interpolated within Table 1, and say so in the log.

    Interpolation is in **log-log space**: a power law through the two
    tabulated points that bracket the wavelength, i.e. exact if the spectrum is
    a power law over the bracket. On the 530-850 nm bracket, the one that
    matters for the 780-810 nm band, the table's own slope there is
    ``H ~ lambda^-1.92``.

    Why log-log rather than linear in ``lambda``, and why the answer is
    reported as a degradation either way:

    - It cannot return a negative or zero radiance, which linear interpolation
      can once anyone extends the grid or extrapolates. That is the reason for
      the choice, and it is a robustness reason, not an accuracy one.
    - Linear interpolation would give a *higher* answer over the whole
      530-850 nm bracket — 159.1 against 142.5 at 785 nm for bright sunshine,
      0.48 dB apart — and it is not knowable from this table which is closer.
      That is why the degradation record carries both numbers.
    - The measured accuracy is **worse than that spread**. Predicting one of
      the table's own interior points from its two neighbours misses by 16 % to
      27 % with this rule, and by 2 % to 32 % with the linear one, because the
      940 nm water-vapour band sits inside the grid and the normal-sunshine
      column is not even monotone across it. So the honest uncertainty on an
      interpolated value is of order a decibel, unquantifiable from the table
      alone, and — for the rule used here — larger at every interior point than
      the difference between the candidate rules.

    Extrapolation is refused rather than clamped. :func:`numpy.interp` returns
    the end value outside the grid **without complaint**, which is the exact
    shape of silent degradation this project forbids: asking for 400 nm — where
    the true radiance is higher than at any tabulated point, since the solar
    spectrum peaks near 500 nm — would return the 530 nm value and look fine.

    Parameters
    ----------
    wavelength_m
        Optical wavelength, m. Must lie within the tabulated range,
        530 to 1500 nm inclusive.
    condition
        Which of the three tabulated illumination conditions.
    degradations
        Log that receives a ``DEGRADED`` record whenever the returned value is
        genuinely interpolated. Nothing is recorded when the wavelength is one
        of the five tabulated ones, because then the value **is** published and
        this function returns exactly what
        :func:`tabulated_sky_radiance_w_m2_um_sr` returns.

    Returns
    -------
    float
        Sky radiance, W/m^2/um/sr. Published if the wavelength is on the grid,
        interpolated otherwise.

    Raises
    ------
    DomainError
        If the wavelength is not finite and positive, or lies outside the
        tabulated range.

    Examples
    --------
    785 nm, the wavelength of the free-space BB84 literature, under bright
    sunshine. The value is returned, and the log says it is not ITU-R's:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> value = interpolated_sky_radiance_w_m2_um_sr(
    ...     785e-09, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=log
    ... )
    >>> round(value, 3)
    142.522
    >>> log.entries[0].code
    'background.sky-radiance-interpolated'
    >>> round(log.entries[0].details["linear_alternative_w_m2_um_sr"], 3)
    159.086
    >>> round(log.entries[0].details["rule_spread_db"], 3)
    0.478

    A tabulated wavelength is passed straight through, and records nothing:

    >>> clean = DegradationLog()
    >>> interpolated_sky_radiance_w_m2_um_sr(
    ...     850e-09, condition=SkyCondition.BRIGHT_SUNSHINE, degradations=clean
    ... )
    122.3
    >>> len(clean)
    0
    """
    wavelength = validated_wavelength_m(wavelength_m)
    index = _tabulated_index(wavelength)
    if index is not None:
        return ITU_SKY_RADIANCE_W_M2_UM_SR[condition][index]

    grid = np.asarray(ITU_SKY_RADIANCE_WAVELENGTHS_M, dtype=np.float64)
    if wavelength < grid[0] or wavelength > grid[-1]:
        raise DomainError(
            f"wavelength_m = {wavelength} m ({wavelength * 1e9} nm) is outside the range "
            f"ITU-R P.1621-2 Table 1 covers, {grid[0] * 1e9} to {grid[-1] * 1e9} nm. "
            "Extrapolating is refused rather than clamped to the end value: below 530 nm the "
            "sky is brighter than any tabulated point, because the solar spectrum peaks near "
            "500 nm, so the clamped answer would be wrong in the unsafe direction and would "
            "look like a table lookup. Table 1 is the whole of the published data; see gap 4 "
            "of docs/adr/0009-citation-policy.md."
        )

    values = np.asarray(ITU_SKY_RADIANCE_W_M2_UM_SR[condition], dtype=np.float64)
    power_law = float(np.exp(np.interp(np.log(wavelength), np.log(grid), np.log(values))))
    linear = float(np.interp(wavelength, grid, values))
    spread_db = float(10.0 * np.log10(max(power_law, linear) / min(power_law, linear)))
    lower = int(np.searchsorted(grid, wavelength) - 1)
    degradations.degrade(
        "background.sky-radiance-interpolated",
        f"Sky radiance at {wavelength * 1e9:.1f} nm is interpolated between the "
        f"{grid[lower] * 1e9:.1f} and {grid[lower + 1] * 1e9:.1f} nm entries of ITU-R "
        f"P.1621-2 Table 1, not read from it: {power_law:.4g} W/m^2/um/sr by the power-law "
        f"rule against {linear:.4g} by the linear one, {spread_db:.2f} dB apart. Predicting a "
        "tabulated point from its neighbours misses by 16 % to 27 % (the 940 nm water-vapour "
        "band is inside the grid), so treat this as a value with about a decibel of "
        "unquantified error, and do not report it as published. Gap 4 of "
        "docs/adr/0009-citation-policy.md.",
        where="quoss.channel.background.interpolated_sky_radiance_w_m2_um_sr",
        wavelength_nm=wavelength * 1e9,
        condition=str(condition),
        power_law_w_m2_um_sr=power_law,
        linear_alternative_w_m2_um_sr=linear,
        rule_spread_db=spread_db,
        bracket_nm=(float(grid[lower]) * 1e9, float(grid[lower + 1]) * 1e9),
    )
    return power_law


def receiver_solid_angle_sr(field_of_view_full_angle_rad: float) -> float:
    """Return the solid angle a receiver of this field of view sees, sr.

    The exact solid angle of a right circular cone of **full** angle ``theta``::

        Omega = 2 pi (1 - cos(theta / 2))

    ITU-R P.1621-2 equation (1) uses the small-angle form ``pi theta^2 / 4``
    instead, and the two agree to 6.1e-9 relative at a 100 microradian field of
    view — so for any real telescope this choice changes nothing, and the reason
    to make it is the same one :func:`quoss.channel.beam.geometric_transmittance`
    gives for preferring the truncation integral to the published gain product:
    the approximation has no ceiling. It is 1 % high at 39.6 deg of full angle,
    5.3 % at 90 deg, and at 360 deg it reports 31.0 sr of sky where a whole
    sphere has 4 pi = 12.57.

    **Full angle, not half angle.** A field of view quoted as "100 urad" is
    taken here to be the full cone, which is what makes ``pi theta^2 / 4`` the
    ITU form rather than ``pi theta^2``. Reading it the other way is a factor of
    four, 6.02 dB of background, and neither source states which it means — so
    the convention is in the parameter's name and asserted by a test rather than
    left to a comment.

    Parameters
    ----------
    field_of_view_full_angle_rad
        Full cone angle of the receiver's field of view, radians, in ``(0, 2 pi]``.

    Returns
    -------
    float
        Solid angle, sr.

    Raises
    ------
    DomainError
        If the angle is not finite and positive, or exceeds ``2 pi``.

    Examples
    --------
    The 100 microradian field of view of Ntanos et al. §4.1, and the ITU
    small-angle form it agrees with:

    >>> import numpy as np
    >>> omega = receiver_solid_angle_sr(100e-06)
    >>> f"{omega:.4e}"
    '7.8540e-09'
    >>> f"{np.pi * 100e-06**2 / 4:.4e}"
    '7.8540e-09'

    The whole sky above the horizon is 2 pi steradians, which the exact form
    gets right and the small-angle form overshoots by 5 %:

    >>> round(receiver_solid_angle_sr(np.pi), 6)
    6.283185
    >>> round(float(np.pi * np.pi**2 / 4), 6)
    7.751569
    """
    field_of_view = _validated_field_of_view_rad(field_of_view_full_angle_rad)
    return float(2.0 * np.pi * (1.0 - np.cos(0.5 * field_of_view)))


def background_power_w(
    sky_radiance_w_m2_um_sr: FloatArray | float,
    *,
    field_of_view_full_angle_rad: float,
    receive_aperture_m: float,
    filter_bandwidth_m: float,
) -> FloatArray:
    """Return the background optical power reaching the aperture, W.

    ITU-R P.1621-2 equation (1), which is Ntanos et al. 2021 equation (19)::

        P_back = H * Omega * A_r * dlambda

    Four factors, and three of them are choices the receiver's designer makes.
    That is the useful reading of this equation: the sky's brightness ``H`` is
    given, and everything else is an aperture, a field of view and a filter. The
    filter is the cheapest of the three — halving ``dlambda`` halves the noise
    and costs nothing but insertion loss — which is why the reference receiver
    uses a 0.2 nm passband, about 25 GHz, on a source that needs far less.

    The area is ``pi D^2 / 4``, the full geometric area of the aperture. A
    central obstruction (a Cassegrain secondary) reduces it, and reduces the
    collected signal by the identical factor, so it cancels in every
    signal-to-background ratio and is deliberately not modelled here.

    **Units.** ``H`` is per **micrometre**, as both sources print it, while
    ``filter_bandwidth_m`` is in metres, as ADR 0001 requires of every optical
    length in this package. The one conversion between them happens here, via
    :data:`quoss.channel._validation.MICROMETRES_PER_METRE`. Mixing the two
    conventions in one signature is deliberate: a transcribed table keeps the
    unit it was published in, so that a reader comparing 122.3 against ITU-R's
    page sees the same number, and the unit is in the argument's name so the
    mixture cannot be silent.

    Parameters
    ----------
    sky_radiance_w_m2_um_sr
        Sky radiance, W/m^2/um/sr, non-negative. Any shape — this is the one
        input that can legitimately vary over a pass, as the sun moves and the
        line of sight sweeps across the sky, so it is the array-valued argument
        even though no model here generates that series.
    field_of_view_full_angle_rad
        Full cone angle of the receiver's field of view, rad. See
        :func:`receiver_solid_angle_sr` for the convention and what getting it
        wrong costs.
    receive_aperture_m
        Diameter of the receiving aperture, m. The same telescope the signal
        terms use.
    filter_bandwidth_m
        Optical passband of the receiver, m. A 0.2 nm filter is ``0.2e-9``.

    Returns
    -------
    FloatArray
        Background power at the aperture, W, shaped like the radiance.

    Raises
    ------
    DomainError
        If the radiance is negative or non-finite, or the field of view,
        aperture or bandwidth fails its own guard.

    Examples
    --------
    The reference receiver of Ntanos et al. §4.1 — 100 urad, 0.2 nm — on the
    2.3 m telescope, under the nighttime radiance their results use:

    >>> power = background_power_w(
    ...     1.5e-04,
    ...     field_of_view_full_angle_rad=100e-06,
    ...     receive_aperture_m=2.3,
    ...     filter_bandwidth_m=0.2e-09,
    ... )
    >>> f"{float(power):.4e}"
    '9.7894e-16'

    A femtowatt is not a small amount of light for a photon counter. The same
    sky under ITU-R's tabulated bright sunshine at 850 nm is six orders of
    magnitude brighter:

    >>> daylight = background_power_w(
    ...     tabulated_sky_radiance_w_m2_um_sr(850e-09, condition=SkyCondition.BRIGHT_SUNSHINE),
    ...     field_of_view_full_angle_rad=100e-06,
    ...     receive_aperture_m=2.3,
    ...     filter_bandwidth_m=0.2e-09,
    ... )
    >>> f"{float(daylight):.4e}"
    '7.9816e-10'

    Vectorised over the time axis, for a caller who has a radiance series:

    >>> import numpy as np
    >>> over_a_pass = background_power_w(
    ...     np.array([1.5e-05, 1.5e-04, 1.5e-03]),
    ...     field_of_view_full_angle_rad=100e-06,
    ...     receive_aperture_m=0.75,
    ...     filter_bandwidth_m=0.2e-09,
    ... )
    >>> over_a_pass.shape
    (3,)
    """
    radiance = _validated_radiance(sky_radiance_w_m2_um_sr)
    solid_angle_sr = receiver_solid_angle_sr(field_of_view_full_angle_rad)
    diameter_m = validated_positive_length_m(
        "receive_aperture_m",
        receive_aperture_m,
        hint="The unit is metres, and it is the same telescope that collects the signal: a "
        "0.75 m aperture entered as 75 collects 10 000 times too much background.",
    )
    bandwidth_m = validated_positive_length_m(
        "filter_bandwidth_m",
        filter_bandwidth_m,
        hint="The unit is metres, so a 0.2 nm passband is 0.2e-9. Entered in nanometres it "
        "would inflate the background by 1e9.",
    )
    area_m2 = 0.25 * np.pi * diameter_m * diameter_m
    bandwidth_um = bandwidth_m * MICROMETRES_PER_METRE
    power_w: FloatArray = radiance * solid_angle_sr * area_m2 * bandwidth_um
    return power_w


def background_photon_rate_cps(power_w: FloatArray | float, *, wavelength_m: float) -> FloatArray:
    """Return the background photon arrival rate, counts per second.

    The first half of Ntanos et al. 2021 equation (20): a power divided by the
    energy of one photon at the signal wavelength::

        cps = P_back / (h f) = P_back lambda / (h c)

    Two things about that division are worth stating rather than assuming.

    **Why the signal wavelength and not a mean over the passband.** The
    background power in the numerator was already restricted to the filter's
    0.2 nm, so every photon in it is within 0.013 % of the signal wavelength.
    Using the centre wavelength is exact to that.

    **What it is not.** This is a rate of photons *incident on the aperture*,
    not a rate of clicks. Quantum efficiency, optical losses and the filter's
    insertion loss all multiply it, and they multiply the signal by the same
    factors, which is why they are applied once in
    :mod:`quoss.channel.link_budget` rather than here — see the module docstring
    on double counting.

    Parameters
    ----------
    power_w
        Background power at the aperture, W, non-negative. Any shape.
    wavelength_m
        Optical wavelength, m.

    Returns
    -------
    FloatArray
        Photon rate, counts per second, shaped like ``power_w``.

    Raises
    ------
    DomainError
        If the power is negative or non-finite, or the wavelength is not finite
        and positive.

    Examples
    --------
    The femtowatt of the previous example is 7.6 kilocounts per second — three
    thousand times the dark-count rate of a good detector:

    >>> rate = background_photon_rate_cps(9.789413805835627e-16, wavelength_m=1.55e-06)
    >>> round(float(rate), 1)
    7638.6

    One photon per second at 1550 nm is 128 zeptowatts, which is the scale that
    makes the rest of this module's numbers legible:

    >>> round(float(background_photon_rate_cps(1.281578e-19, wavelength_m=1.55e-06)), 6)
    1.0
    """
    power = np.asarray(power_w, dtype=np.float64)
    if not np.all(np.isfinite(power)):
        raise DomainError("power_w contains non-finite values.")
    if np.any(power < 0.0):
        raise DomainError(
            f"power_w must be non-negative, got a minimum of {float(np.min(power))}. The unit "
            "is watts, which is what background_power_w returns; a background of a "
            "femtowatt is 1e-15, not 1e-15 mW."
        )
    wavelength = validated_wavelength_m(wavelength_m)
    photon_energy_j = PLANCK_J_S * SPEED_OF_LIGHT_M_S / wavelength
    rate_cps: FloatArray = power / photon_energy_j
    return rate_cps


def background_counts_per_gate(
    photon_rate_cps: FloatArray | float, *, gate_duration_s: float
) -> FloatArray:
    """Return the expected number of background counts in one detection gate.

    Ntanos et al. 2021 equation (20), exactly as printed::

        mu = t_gate * cps_background

    **This is a mean, not a probability**, and the source calls it "the
    probability of the detector firing due to a background noise photon". The
    two agree while ``mu`` is small and diverge without any warning sign
    otherwise: the same paper's parameters under ITU-R's tabulated bright
    sunshine at 850 nm give ``mu = 3.42`` on their largest telescope and 1.09 on
    their middle one. A probability of 3.42 is not a rounding problem, and
    nothing upstream of it looks wrong.

    So this function returns the mean and is named for it;
    :func:`background_click_probability` is where a probability comes from. Use
    this one when the mean is what is wanted — it is the Poisson parameter, so
    it is what goes into a QBER computed from expected counts, and it is what
    adds linearly across independent noise sources (sky background plus dark
    counts plus stray light) before any of them becomes a probability.

    Parameters
    ----------
    photon_rate_cps
        Background photon rate at the aperture, counts per second,
        non-negative. Any shape.
    gate_duration_s
        Width of the detection gate, s, strictly positive.

    Returns
    -------
    FloatArray
        Expected counts per gate, dimensionless and unbounded above, shaped
        like ``photon_rate_cps``.

    Raises
    ------
    DomainError
        If the rate is negative or non-finite, or the gate is not finite and
        positive.

    Examples
    --------
    The reference nighttime link: 7.6 kcps in a 1 ns gate is eight counts per
    million gates, which is the regime the published budgets live in:

    >>> mu = background_counts_per_gate(7638.6, gate_duration_s=1e-09)
    >>> f"{float(mu):.4e}"
    '7.6386e-06'

    And the same receiver in daylight, where the source's own reading of this
    number as a probability breaks:

    >>> daylight = background_counts_per_gate(3.415341e09, gate_duration_s=1e-09)
    >>> round(float(daylight), 3)
    3.415
    """
    rate = _validated_rate_cps(photon_rate_cps)
    gate_s = validated_duration_s("gate_duration_s", gate_duration_s)
    counts: FloatArray = rate * gate_s
    return counts


def background_click_probability(
    photon_rate_cps: FloatArray | float,
    *,
    gate_duration_s: float,
    degradations: DegradationLog,
) -> FloatArray:
    """Return the probability that a background photon lands in one gate.

    Background arrivals are a Poisson process — independent photons from an
    incoherent source — so with a mean of ``mu`` per gate, the probability that
    the gate contains at least one is::

        p = 1 - exp(-mu),        mu = cps * t_gate

    This is the corrected form of Ntanos et al. 2021 equation (20), whose linear
    reading is its ``mu << 1`` limit. Where the two differ:

    ====== ============ ============ ==========
    ``mu``  ``1-e^-mu``  linear        overshoot
    ====== ============ ============ ==========
    0.001   0.001000     0.001         0.05 %
    0.01    0.009950     0.01          0.50 %
    0.1     0.095163     0.1           5.08 %
    1.0     0.632121     1.0          58 %
    3.42    0.967135     3.42         253 %
    ====== ============ ============ ==========

    A WARNING — not a degradation, because nothing was substituted — is
    recorded above :data:`LINEAR_CLICK_PROBABILITY_LIMIT`, carrying both
    numbers. It is not about this function's answer, which is right at any ``mu`` —
    it is about the operating point: a tenth of a background count per gate is a
    link nobody can distil a key from, so a result whose ``warnings[]`` holds
    this code is describing a curve computed in a regime the published formula
    it came from does not survive.

    Saturation cuts the other way too, and is the reason the exponential form
    matters beyond honesty: as the sky brightens, ``p`` approaches 1 rather than
    growing, so a daylight QBER computed from this never exceeds the 50 % of a
    coin flip. Computed from the linear form it can exceed 100 %.

    Parameters
    ----------
    photon_rate_cps
        Background photon rate at the aperture, counts per second,
        non-negative. Any shape.
    gate_duration_s
        Width of the detection gate, s, strictly positive.
    degradations
        Log that receives a warning where the source's linear form would
        mislead by more than 5 %.

    Returns
    -------
    FloatArray
        Probability in ``[0, 1)``, shaped like ``photon_rate_cps``.

    Raises
    ------
    DomainError
        If the rate is negative or non-finite, or the gate is not finite and
        positive.

    Examples
    --------
    At night the distinction is irrelevant, and nothing is recorded:

    >>> from quoss.core.errors import DegradationLog
    >>> log = DegradationLog()
    >>> p = background_click_probability(7638.6, gate_duration_s=1e-09, degradations=log)
    >>> f"{float(p):.4e}"
    '7.6386e-06'
    >>> len(log)
    0

    In daylight it is the difference between a probability and a nonsense, and
    the warning names the operating point:

    >>> day = background_click_probability(3.415341e09, gate_duration_s=1e-09, degradations=log)
    >>> round(float(day), 6)
    0.967135
    >>> log.entries[0].code
    'background.counts-per-gate-not-small'
    >>> round(log.entries[0].details["counts_per_gate"], 3)
    3.415

    Narrowing the gate to 100 ps is enough to bring the same daylight case back
    inside the linear regime, which is the module docstring's point about gating
    made arithmetically:

    >>> quiet = DegradationLog()
    >>> narrow = background_click_probability(
    ...     3.415341e09, gate_duration_s=100e-12, degradations=quiet
    ... )
    >>> round(float(narrow), 4)
    0.2893
    >>> len(quiet)
    1
    """
    counts = background_counts_per_gate(photon_rate_cps, gate_duration_s=gate_duration_s)
    worst = float(np.max(counts))
    if worst > LINEAR_CLICK_PROBABILITY_LIMIT:
        probability_at_worst = float(-np.expm1(-worst))
        degradations.warn(
            "background.counts-per-gate-not-small",
            f"The receiver collects {worst:.4g} background counts per gate, above the "
            f"{LINEAR_CLICK_PROBABILITY_LIMIT} where the linear form of Ntanos et al. 2021 "
            f"equation (20) starts to mislead: it reads that as a probability of {worst:.4g} "
            f"where the Poisson value is {probability_at_worst:.4g}, "
            f"{100.0 * (worst / probability_at_worst - 1.0):.0f} % lower. The value returned "
            "here is the Poisson one and is correct; the warning is about the operating point, "
            "which is a link too noisy for any key rate. Narrow the gate or the optical filter, "
            "or model this pass as daylight-interrupted the way the source does.",
            where="quoss.channel.background.background_click_probability",
            counts_per_gate=worst,
            linear_form_value=worst,
            poisson_probability=probability_at_worst,
            gate_duration_s=float(gate_duration_s),
        )
    # -expm1(-mu) rather than 1 - exp(-mu): at the nighttime mu of 7.6e-06 the naive form
    # cancels the leading digits of two numbers that differ in the sixth decimal, and loses
    # about ten bits doing it. expm1 is the identical function evaluated stably.
    probability: FloatArray = -np.expm1(-counts)
    return probability


def gate_signal_fraction(
    gate_duration_s: FloatArray | float, *, timing_jitter_fwhm_s: float
) -> FloatArray:
    """Return the fraction of the signal a gate of this width keeps.

    The lever this function exists to price: background scales **linearly** with
    the gate width, and signal does not. Signal photons arrive at a known time,
    smeared only by the detector's timing jitter, so a gate several jitters wide
    keeps all of them while a gate ten times wider collects ten times the noise
    for nothing.

    The derivation, which is two lines. Take the arrival time relative to the
    gate centre as Gaussian with standard deviation ``sigma``, the usual model
    for detector jitter, and the gate as ``[-T/2, +T/2]``. Then::

        fraction = P(|t| < T / 2) = erf( T / (2 sqrt(2) sigma) )

    with ``sigma = FWHM / (2 sqrt(2 ln 2)) = FWHM / 2.3548``, since datasheets
    and the reference paper quote the jitter as a full width at half maximum.
    **Passing a standard deviation here as if it were a FWHM understates the
    kept signal**: at the 59.5 ps optimal gate for a 50 ps FWHM, reading 50 ps
    as a sigma gives 0.4487 instead of 0.8385, a 2.7 dB error in the wrong
    direction.

    Measured with the 50 ps jitter Ntanos et al. §4.1 declare, against the 1 ns
    gate they use:

    ========== ================ ================
    Gate        Signal kept      Background
    ========== ================ ================
    1000 ps     1.000000          0 dB
    100 ps      0.981468        -10.00 dB
    59.45 ps    0.838469        -12.26 dB
    50 ps       0.760968        -13.01 dB
    25 ps       0.443941        -16.02 dB
    ========== ================ ================

    A 1 ns gate on a 50 ps detector is throwing away 10 dB of signal-to-noise to
    keep 0.08 dB of signal, and the reference paper's own text names the
    remedy — "short detector gate time opening at Bob station" — without
    quantifying it. This is the quantification, and it is a V1 derivation from
    the Gaussian jitter model rather than anything published.

    What this model leaves out, in the direction that matters: the gate is
    assumed **centred** on the signal. A synchronisation offset shifts it, and
    the kept fraction becomes a difference of two error functions — cheap to add
    and deliberately absent, because the offset is a system-level quantity (a
    clock model, a range-rate correction) and not a property of the channel. The
    jitter here is the detector's alone; a real budget adds the source's pulse
    width and the sync jitter in quadrature.

    Parameters
    ----------
    gate_duration_s
        Width of the detection gate, s, strictly positive. Any shape — this is
        the array argument because sweeping the gate is the natural use.
    timing_jitter_fwhm_s
        Detector timing jitter, **full width at half maximum**, s, strictly
        positive.

    Returns
    -------
    FloatArray
        Fraction of the signal inside the gate, in ``(0, 1)``, shaped like
        ``gate_duration_s``.

    Raises
    ------
    DomainError
        If the gate or the jitter is not finite and positive.

    Examples
    --------
    The declared 1 ns gate on the declared 50 ps detector keeps everything, so
    all of its width is noise:

    >>> round(float(gate_signal_fraction(1e-09, timing_jitter_fwhm_s=50e-12)), 9)
    1.0

    Ten times narrower costs 0.08 dB of signal for 10 dB of background:

    >>> from quoss.core.units import transmittance_to_loss_db
    >>> kept = gate_signal_fraction(100e-12, timing_jitter_fwhm_s=50e-12)
    >>> round(float(kept), 6)
    0.981468
    >>> round(float(transmittance_to_loss_db(kept)), 4)
    0.0812

    Narrower than the jitter itself, the erf turns over and the cost becomes
    real:

    >>> import numpy as np
    >>> sweep = gate_signal_fraction(
    ...     np.array([50e-12, 25e-12, 10e-12]), timing_jitter_fwhm_s=50e-12
    ... )
    >>> np.round(sweep, 4)
    array([0.761 , 0.4439, 0.1862])
    """
    gate_s = np.asarray(gate_duration_s, dtype=np.float64)
    if not np.all(np.isfinite(gate_s)):
        raise DomainError("gate_duration_s contains non-finite values.")
    if np.any(gate_s <= 0.0):
        raise DomainError(
            "gate_duration_s must be finite and positive, got a minimum of "
            f"{float(np.min(gate_s))}. The unit is seconds: a 1 nanosecond gate is 1e-9."
        )
    jitter_s = validated_duration_s("timing_jitter_fwhm_s", timing_jitter_fwhm_s)
    sigma_s = jitter_s / _FWHM_PER_SIGMA
    fraction: FloatArray = erf(gate_s / (2.0 * np.sqrt(2.0) * sigma_s))
    return fraction


def gate_width_maximising_snr_s(timing_jitter_fwhm_s: float) -> float:
    """Return the gate width that maximises ``S / sqrt(B)``, s.

    A gate of width ``T`` keeps ``erf(x)`` of the signal and collects a
    background proportional to ``T``, where ``x = T / (2 sqrt(2) sigma)``. If
    the figure of merit is the shot-noise-limited ratio ``S / sqrt(B)``, the
    objective is ``erf(x) / sqrt(x)``, which has an interior maximum: too wide
    lets in noise, too narrow throws away signal. Setting the derivative to
    zero::

        (4 / sqrt(pi)) x exp(-x^2) = erf(x)     ->     x* = 0.98993908

    so the optimum gate is ``2 sqrt(2) x* = 2.79997`` jitter standard
    deviations, i.e. :data:`GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS`, or 1.18904
    FWHM. Being a fixed multiple of the jitter is the useful part: the optimum
    knows nothing about how bright the sky is, because both terms scale with the
    gate the same way whatever the background level, and dark counts — which
    also scale linearly with the gate — do not move it either.

    **What this objective claims, and what it does not.** ``S / sqrt(B)`` is the
    figure of merit of a measurement whose noise is the shot noise of its own
    background. A QKD protocol is not that: its objective is a secret-key rate,
    which trades a QBER against a raw count rate through a protocol-dependent
    and finite-key-dependent function, and it belongs to :mod:`quoss.qkd`. Two
    statements survive the change of objective and are the ones to rely on:

    - The background-to-signal **ratio** ``x / erf(x)`` is monotone increasing,
      so narrowing the gate always improves the QBER. There is no interior
      optimum for that objective at all — the limit is how much raw rate the
      protocol can afford to lose.
    - Any objective that rewards signal and penalises the square root of noise
      lands on this width, and it is not a delicate optimum: measured over the
      merit function, every gate between 1.5 and 5 sigma is within **0.55 dB**
      of the best (0.16 dB between 2 and 4 sigma). So this is a number to design
      around, not to hit exactly — and the 1 ns gate of the reference paper,
      which is 47 sigma, is 5.36 dB off it.

    Measured with the reference detector's 50 ps FWHM: the optimum is 59.5 ps,
    which against the paper's own 1 ns gate is 12.26 dB less background for
    0.77 dB less signal — a 5.36 dB improvement in ``S / sqrt(B)``.

    Parameters
    ----------
    timing_jitter_fwhm_s
        Detector timing jitter, full width at half maximum, s, strictly
        positive.

    Returns
    -------
    float
        Gate width, s.

    Raises
    ------
    DomainError
        If the jitter is not finite and positive.

    Examples
    --------
    >>> gate_s = gate_width_maximising_snr_s(50e-12)
    >>> round(gate_s * 1e12, 3)
    59.452
    >>> round(float(gate_signal_fraction(gate_s, timing_jitter_fwhm_s=50e-12)), 6)
    0.838482

    A slower detector wants a proportionally wider gate, and nothing else about
    the link enters:

    >>> round(gate_width_maximising_snr_s(500e-12) * 1e12, 2)
    594.52
    """
    jitter_s = validated_duration_s("timing_jitter_fwhm_s", timing_jitter_fwhm_s)
    return float(GATE_MAXIMISING_SNR_IN_JITTER_SIGMAS * jitter_s / _FWHM_PER_SIGMA)
