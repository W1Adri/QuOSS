"""Validation cases for the optical channel: ITU-R P.1621-2, P.1622, and Farid & Hranilovic.

Para quien llegue nuevo: the channel is where this project most needs outside
numbers, because its formulas come from a literature that disagrees with itself
about units, conventions and even signs (``docs/adr/0009-citation-policy.md``).
The recommendations of the ITU-R are the anchor chosen there — free, numbered,
and tabulated — and this module collects every number they print that the
channel modules can recompute.

What is here, and why each one is worth a row:

- **ITU-R P.1622 Table 2**: eight log-irradiance variances ``sigma^2_lnI`` —
  the variance of the natural logarithm of received irradiance, the standard
  measure of scintillation (the twinkling a turbulent atmosphere imprints on a
  beam) — at four wavelengths and two wind speeds, under conditions the
  recommendation fully states. The strongest anchor the channel has: reproduced
  at the printed precision, and a mistyped exponent in the Rytov integral would
  miss by an order of magnitude, not by a digit.
- **ITU-R P.1621-2 §5.1.1**: the three numbers the recommendation prints about
  its own turbulence model (a 21 m/s r.m.s. wind, a top layer of about 1 km, a
  column of about 20 km). Small, but they pin the integration grid that every
  turbulence quantity is a sum over.
- **Farid & Hranilovic 2007 against Ntanos et al. 2021**: two independent
  papers publish the same pointing-fade exponent in different variables. They
  differ by 1 %, and the difference is exactly a finite-aperture term only one
  of them carries — so the case is ``COMPATIBLE`` with the term computed, not
  ``REPRODUCED`` with a loose tolerance.
- **Farid & Hranilovic Table I**, a gap: its NMSE values state neither the
  averaging range nor the normalisation, so there is no computation to compare.

Deliberately absent: anything read off ITU-R P.1621-2 Figures 1, 2 or 4 (the
absorption and scattering curves). Reading a value from a plot and calling it
published is what ADR 0009 forbids, and the zenith transmittance that would come
from them is a gap declared in ``quoss.validation.ntanos2021`` instead.
"""

from __future__ import annotations

import math
from typing import Final

from quoss.channel.atmosphere import (
    ITU_GROUND_WIND_SPEED_M_S,
    bufton_rms_wind_speed_m_s,
    itu_layer_thicknesses_m,
)
from quoss.channel.beam import divergence_half_angle_rad
from quoss.channel.pointing import beam_to_jitter_ratio, equivalent_beam_radius_m
from quoss.channel.turbulence import log_irradiance_variance
from quoss.core.errors import DegradationLog
from quoss.core.units import deg_to_rad, km_to_m, m_to_nm
from quoss.validation.base import AccountedTerm, ValidationCase

__all__ = [
    "FARID_HRANILOVIC_2007",
    "ITU_P1621_2",
    "ITU_P1622",
    "ITU_P1622_TABLE_2",
    "cases",
]

ITU_P1622: Final = (
    "ITU-R Recommendation P.1622 (04/2003), Prediction methods required for the design of "
    "Earth-space systems operating between 20 THz and 375 THz (itu.int, "
    "R-REC-P.1622-0-200304-S!!PDF-E)"
)
ITU_P1621_2: Final = (
    "ITU-R Recommendation P.1621-2 (07/2015), Propagation data required for the design of "
    "Earth-space systems operating between 20 THz and 375 THz (itu.int, "
    "R-REC-P.1621-2-201507-I!!PDF-E)"
)
FARID_HRANILOVIC_2007: Final = (
    "A. A. Farid and S. Hranilovic, Outage capacity optimization for free-space optical links "
    "with pointing errors, J. Lightwave Technol. 25(7):1702 (2007), authors' accepted manuscript "
    "at ece.mcmaster.ca; compared with A. Ntanos et al., Photonics 8(12):544 (2021)"
)

ITU_P1622_TABLE_2: Final[dict[float, dict[float, float]]] = {
    21.0: {0.532: 0.23, 0.850: 0.13, 1.064: 0.10, 1.55: 0.07},
    30.0: {0.532: 0.36, 0.850: 0.21, 1.064: 0.16, 1.55: 0.10},
}
"""ITU-R P.1622 Table 2, "Example scintillation statistics for C0 = 1.7e-14 m-2/3".

r.m.s. wind speed (m/s) -> wavelength (µm) -> ``sigma^2_lnI`` (Np^2), at "an
elevation angle of 75 degrees, earth station antenna is 5.5 m above the ground",
with the aperture below the coherence length (so no aperture averaging). The
same transcription as ``tests/channel/test_turbulence.py``, kept separately so
that this table is checked against the recommendation and not against the test.
"""

_TABLE_2_ELEVATION_DEG: Final = 75.0
_TABLE_2_STATION_HEIGHT_M: Final = 5.5

# Table 2 is printed in micrometres and the channel takes metres, so the table keys
# cross one unit boundary on the way in and a second one on the way to the case
# identifier, which is spelled in nanometres to match how the rest of the project
# names wavelengths. Only the second crossing has a helper in ``core.units``.
_M_PER_UM: Final = 1e-6

# Ntanos et al. 2021 §4.1, the pointing system both pointing sources are asked about.
_NTANOS_WAVELENGTH_M: Final = 1.55e-6
_NTANOS_TRANSMIT_APERTURE_M: Final = 0.15
_NTANOS_SMALLEST_APERTURE_M: Final = 0.75
_NTANOS_JITTER_RAD: Final = 0.75e-6
_NTANOS_RANGE_KM: Final = 600.0


def _codes(log: DegradationLog) -> tuple[str, ...]:
    """Sorted, de-duplicated degradation codes, for the case record."""
    return tuple(sorted({entry.code for entry in log}))


def _table_2_cases() -> list[ValidationCase]:
    cases: list[ValidationCase] = []
    for wind_m_s, row in ITU_P1622_TABLE_2.items():
        for wavelength_um, published in row.items():
            log = DegradationLog()
            wavelength_m = wavelength_um * _M_PER_UM
            computed = float(
                log_irradiance_variance(
                    deg_to_rad(_TABLE_2_ELEVATION_DEG),
                    wavelength_m=wavelength_m,
                    station_height_m=_TABLE_2_STATION_HEIGHT_M,
                    rms_wind_speed_m_s=wind_m_s,
                    degradations=log,
                )
            )
            nanometres = round(float(m_to_nm(wavelength_m)))
            cases.append(
                ValidationCase.evaluate(
                    identifier=f"itu-r-p1622.table2.vrms{wind_m_s:.0f}.lambda{nanometres:04d}nm",
                    source=ITU_P1622,
                    locator=(
                        f"Table 2, v_rms = {wind_m_s:.0f} m/s, λ = {wavelength_um} µm "
                        "(75° elevation, station 5.5 m, C0 = 1.7e-14 m^-2/3)"
                    ),
                    quantity="log-irradiance variance of a point receiver, downlink",
                    published=published,
                    computed=computed,
                    unit="Np^2",
                    tolerance=0.005,
                    tolerance_basis=(
                        "Half a unit in the last printed digit: the table gives two decimals, "
                        "which licenses ±0.005 Np^2 and nothing tighter."
                    ),
                    level="V2",
                    note=(
                        "Eq. (4b) integrated over the HV-5/7 profile of P.1621-2 §5.1.1 at the "
                        "conditions the table states. No aperture averaging, because the table "
                        "assumes an aperture below r0."
                    ),
                    test=(
                        "tests/channel/test_turbulence.py::TestPublishedItuTable2::"
                        "test_reproduces_the_published_variance"
                    ),
                    degradations=_codes(log),
                )
            )
    return cases


def _itu_p1621_cases() -> list[ValidationCase]:
    thicknesses_m = itu_layer_thicknesses_m()
    return [
        ValidationCase.evaluate(
            identifier="itu-r-p1621.rms-wind-for-unknown-ground-wind",
            source=ITU_P1621_2,
            locator="§5.1.1 step 1 and Eq. (5): v_g = 2.3 m/s gives v_rms = 21 m/s",
            quantity="r.m.s. wind speed along the vertical path (Bufton)",
            published=21.0,
            computed=bufton_rms_wind_speed_m_s(ITU_GROUND_WIND_SPEED_M_S),
            unit="m/s",
            tolerance=0.5,
            tolerance_basis="Printed to two significant figures, so ±0.5 m/s.",
            level="V2",
            note=(
                "Eq. (5) with the ITU coefficients (33.11, 360.31) gives 21.018 m/s. The "
                "coefficients usually attributed to Andrews & Phillips (30.69, 348.91) reach "
                "the same 21 m/s from a different ground wind; ADR 0009 gap 6."
            ),
            test=(
                "tests/channel/test_atmosphere.py::TestPublishedItuValues::"
                "test_the_recommendations_own_wind_example"
            ),
        ),
        ValidationCase.evaluate(
            identifier="itu-r-p1621.top-layer-thickness",
            source=ITU_P1621_2,
            locator="§5.1.1, after Eq. (7): 'h139 ~ 1 000 m'",
            quantity="thickness of the highest of the 139 integration layers",
            published=1000.0,
            computed=float(thicknesses_m[-1]),
            unit="m",
            tolerance=10.0,
            tolerance_basis=(
                "1 % of the printed value, from the tilde: the recommendation writes it as "
                "approximate and 1 000 m is a rounded statement of exp(6.9) = 992 m."
            ),
            level="V2",
            note="Fixes the exponential layer grid the Rytov and Fried integrals are sums over.",
            test=(
                "tests/channel/test_atmosphere.py::TestPublishedItuValues::"
                "test_the_layer_grid_reproduces_the_thickness_the_recommendation_prints"
            ),
        ),
        ValidationCase.evaluate(
            identifier="itu-r-p1621.layer-span",
            source=ITU_P1621_2,
            locator="§5.1.1, after Eq. (7): 'sum of hi ~ 20 km'",
            quantity="total height spanned by the 139 integration layers",
            published=20_000.0,
            computed=float(thicknesses_m.sum()),
            unit="m",
            tolerance=400.0,
            tolerance_basis=(
                "2 % of the printed value, from the tilde. Tight enough to fail an off-by-one "
                "grid (i = 0..138 spans 19.3 km), which is the error this number can catch."
            ),
            level="V2",
            note="Measured 20.326 km.",
            test=(
                "tests/channel/test_atmosphere.py::TestPublishedItuValues::"
                "test_the_layer_grid_reproduces_the_span_the_recommendation_prints"
            ),
        ),
    ]


def _pointing_cases() -> list[ValidationCase]:
    log = DegradationLog()
    geometry = {
        "wavelength_m": _NTANOS_WAVELENGTH_M,
        "transmit_aperture_m": _NTANOS_TRANSMIT_APERTURE_M,
        "receive_aperture_m": _NTANOS_SMALLEST_APERTURE_M,
    }
    # Ntanos et al. Eqs. (6) and (9), transcribed: w0 = 2 lambda / (pi D_t),
    # beta_p = w0^2 / (4 sigma_p^2). Written out rather than imported so the
    # published side of the comparison is the paper, not this project's beam module.
    ntanos_divergence_rad = 2.0 * _NTANOS_WAVELENGTH_M / (math.pi * _NTANOS_TRANSMIT_APERTURE_M)
    beta_p = ntanos_divergence_rad**2 / (4.0 * _NTANOS_JITTER_RAD**2)

    gamma = float(
        beam_to_jitter_ratio(
            _NTANOS_RANGE_KM, jitter_rad=_NTANOS_JITTER_RAD, degradations=log, **geometry
        )
    )
    # The finite-aperture term, computed through a different public function:
    # Farid & Hranilovic's exponent uses the *equivalent* beam radius w_zeq,
    # Ntanos et al.'s the far-field one w0 z, and gamma^2 / beta_p = (w_zeq / w0 z)^2.
    equivalent_m = float(equivalent_beam_radius_m(_NTANOS_RANGE_KM, degradations=log, **geometry))
    far_field_m = divergence_half_angle_rad(
        wavelength_m=_NTANOS_WAVELENGTH_M, transmit_aperture_m=_NTANOS_TRANSMIT_APERTURE_M
    ) * km_to_m(_NTANOS_RANGE_KM)
    aperture_residual = float(beta_p - beta_p * (equivalent_m / far_field_m) ** 2)
    tolerance = 1e-12 * beta_p

    return [
        ValidationCase.evaluate(
            identifier="farid2007.pointing-exponent-vs-ntanos-beta-p",
            source=FARID_HRANILOVIC_2007,
            locator=(
                "Farid & Hranilovic Eq. (11) (gamma^2) against Ntanos et al. Eq. (9) (beta_p), "
                "at Ntanos §4.1: 0.15 m transmitter, 0.75 m receiver, 600 km, 0.75 µrad jitter"
            ),
            quantity="pointing-fade exponent (beam-to-jitter ratio squared)",
            published=beta_p,
            computed=gamma**2,
            unit="1",
            tolerance=tolerance,
            tolerance_basis=(
                "1e-12 relative: once the aperture term is removed the two expressions are an "
                "identity, so only float rounding separates them."
            ),
            level="V2",
            note=(
                "Two papers, two variables, one exponent: 19.42 against 19.23, a 1 % "
                "difference that is 0.01 dB in the 1-in-100 pointing loss (1.030 dB against "
                "1.040 dB). The residual is not slack. Farid & Hranilovic's numerator carries "
                "the finite-aperture equivalent beam radius and Ntanos et al.'s does not, and "
                "the ratio of the two exponents equals (w_zeq / w0 z)^2 to float precision."
            ),
            test=(
                "tests/channel/test_pointing.py::TestTwoPublishedSourcesAgree::"
                "test_gamma_squared_matches_ntanos_beta_p"
            ),
            accounted=AccountedTerm(
                name="finite-aperture correction to the beam radius (w_zeq against w0 z)",
                lower=aperture_residual,
                upper=aperture_residual,
                basis=(
                    "Computed exactly through quoss.channel.pointing.equivalent_beam_radius_m, "
                    "Farid & Hranilovic Eq. (10)."
                ),
            ),
            degradations=_codes(log),
        ),
        ValidationCase.evaluate(
            identifier="farid2007.table-1-nmse",
            source=FARID_HRANILOVIC_2007,
            locator="Farid & Hranilovic Table I, NMSE between Eqs. (8) and (9), W/a = 2",
            quantity="normalised mean-square error of the closed-form pointing loss",
            published=13.0e-3,
            computed=None,
            unit="1",
            tolerance=None,
            tolerance_basis=(
                "None: the table states neither the displacement range the error is averaged "
                "over nor its normalisation, so no tolerance can be derived for a quantity "
                "that is not defined."
            ),
            level="V2",
            note=(
                "Gap. No plausible convention reproduces the printed values; attempts land "
                "100 to 1000 times lower, and the last two entries (0.159e-3, 0.153e-3) look "
                "like a numerical floor. What is asserted instead is the claim the table "
                "supports: the closed form's error falls monotonically with W/a, measured "
                "against Eq. (8) integrated numerically (tests/golden/README.md)."
            ),
            test=(
                "tests/channel/test_pointing.py::TestAgainstTheExactIntegral::"
                "test_the_error_shrinks_monotonically_as_the_table_says"
            ),
        ),
    ]


def cases() -> tuple[ValidationCase, ...]:
    """Recompute every channel case, in table order.

    Returns
    -------
    tuple of ValidationCase
        ITU-R P.1622 Table 2 (eight), ITU-R P.1621-2 (three), then the two
        pointing cases.

    Examples
    --------
    >>> [case.status.value for case in cases()][:2]
    ['reproduced', 'reproduced']
    """
    return (*_table_2_cases(), *_itu_p1621_cases(), *_pointing_cases())
