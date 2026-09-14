"""The fade inputs of the reference link, at exactly the samples its passes list.

`tests/system/reference.py` wires the reference link up to a
:class:`~quoss.qkd.base.LinkConditions`, which is all `key_volume.py` needs.
The two modules of this file's stage need three more things per in-pass sample
that the conditions object does not carry: the fade allowance the budget put
into the transmittance (to take it back out), the log-irradiance variance, and
the beam-to-jitter ratio. They come from the same budget call with the same
parameters, so a number quoted by `correlated_fading.py` or `monte_carlo.py`
traces to the same link as every number of §26-27 of `notes/LAST_CHANGES.md`.

A plain module with memoised builders, for the reason `reference.py` gives.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from quoss.channel.detector import (
    NTANOS_FILTER_INSERTION_LOSS_DB,
    NTANOS_RECEIVER_LOSS_DB,
    NTANOS_SNSPD_EFFICIENCY,
    receiver_efficiency,
)
from quoss.channel.link_budget import (
    NTANOS_POINTING_JITTER_RAD,
    NTANOS_TRANSMIT_APERTURE_M,
    downlink_loss_budget,
)
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.channel.turbulence import downlink_log_irradiance_variance
from quoss.core.errors import DegradationLog
from quoss.core.rng import RandomSource
from quoss.core.types import FloatArray
from quoss.system.correlated_fading import FadingParameters
from quoss.system.monte_carlo import (
    MonteCarloKeyVolume,
    MonteCarloOptions,
    monte_carlo_pass_key_volume,
)

from .reference import (
    RECEIVE_APERTURE_M,
    WAVELENGTH_M,
    Link,
    link,
    reference_protocol,
    reference_security,
)

REFERENCE_SEED = 20_260_913
"""The seed every Monte Carlo number quoted in the stage's prose was drawn with."""

REFERENCE_FADING = FadingParameters(
    scintillation_correlation_time_s=2e-3, pointing_correlation_time_s=20e-3
)
"""The physical order-of-magnitude estimate: milliseconds and tens of milliseconds.

Not a published value — see `correlated_fading.py`'s module docstring for why
there is none — but the pair the docstrings' headline numbers are drawn at.
"""


@dataclass(frozen=True)
class FadingInputs:
    """What `monte_carlo_pass_key_volume` needs beyond the conditions, per sample."""

    fade_db: FloatArray
    log_irradiance_variance_np2: FloatArray
    beam_to_jitter_ratio: FloatArray
    elevation_rad: FloatArray
    azimuth_rad: FloatArray
    range_km: FloatArray
    t_s: FloatArray


@lru_cache(maxsize=8)
def fading_inputs(mask_deg: float = 10.0) -> FadingInputs:
    """Return the fade allowance, sigma^2 and gamma at the reference samples of one mask."""
    return fading_inputs_of(link(mask_deg))


def fading_inputs_of(target: Link) -> FadingInputs:
    """Return the fade inputs at the samples of any wired link, through the reference budget."""
    samples, angles = target.samples, target.angles
    rows = (samples.satellite_index, samples.sample_index)
    elevation = np.asarray(angles.elevation_rad)[rows]
    azimuth = np.asarray(angles.azimuth_rad)[rows]
    slant_range = np.asarray(angles.range_km)[rows]
    log = DegradationLog()
    chain = receiver_efficiency(
        NTANOS_SNSPD_EFFICIENCY,
        optical_loss_db=NTANOS_FILTER_INSERTION_LOSS_DB + NTANOS_RECEIVER_LOSS_DB,
    )
    loss = downlink_loss_budget(
        elevation,
        range_km=slant_range,
        wavelength_m=WAVELENGTH_M,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=RECEIVE_APERTURE_M,
        zenith_transmittance=1.0,
        pointing_jitter_rad=NTANOS_POINTING_JITTER_RAD,
        receiver_efficiency=chain,
        degradations=log,
    )
    variance = downlink_log_irradiance_variance(
        elevation,
        aperture_diameter_m=RECEIVE_APERTURE_M,
        wavelength_m=WAVELENGTH_M,
        degradations=log,
    )
    gamma = beam_to_jitter_ratio(
        slant_range,
        jitter_rad=NTANOS_POINTING_JITTER_RAD,
        wavelength_m=WAVELENGTH_M,
        transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
        receive_aperture_m=RECEIVE_APERTURE_M,
        degradations=log,
    )
    return FadingInputs(
        fade_db=np.asarray(loss.fade_db, dtype=np.float64),
        log_irradiance_variance_np2=np.asarray(variance, dtype=np.float64),
        beam_to_jitter_ratio=np.asarray(gamma, dtype=np.float64),
        elevation_rad=elevation,
        azimuth_rad=azimuth,
        range_km=slant_range,
        t_s=np.asarray(target.grid.t_s)[samples.sample_index],
    )


def run_monte_carlo(
    target: Link,
    *,
    fading: FadingParameters = REFERENCE_FADING,
    realisations: int = 200,
    sample_counts: bool = True,
    seed: int = REFERENCE_SEED,
    quantiles: tuple[float, ...] = (0.05, 0.5, 0.95),
    chunk_elements: int = 2_000_000,
    degradations: DegradationLog | None = None,
    inputs: FadingInputs | None = None,
) -> MonteCarloKeyVolume:
    """Run the ensemble on a wired link with the reference protocol and security."""
    fade = inputs if inputs is not None else fading_inputs()
    return monte_carlo_pass_key_volume(
        target.conditions,
        samples=target.samples,
        nominal_fade_db=fade.fade_db,
        log_irradiance_variance_np2=fade.log_irradiance_variance_np2,
        beam_to_jitter_ratio=fade.beam_to_jitter_ratio,
        protocol=reference_protocol(),
        security=reference_security(),
        fading=fading,
        options=MonteCarloOptions(
            realisations=realisations,
            sample_counts=sample_counts,
            quantiles=quantiles,
            chunk_elements=chunk_elements,
        ),
        random_source=RandomSource.from_seed(seed),
        degradations=degradations if degradations is not None else DegradationLog(),
    )
