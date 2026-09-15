"""Tests for `quoss.channel.extinction`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestPublishedKimTables`` — **V2**: the 32 cells of Kim et al. 2001 Tables 2
  and 4, both laws, both of their wavelengths, against a tolerance derived from
  the printed precision.
- ``TestTheItuVisibilityCodeIsTheSameLaw`` — **between sources**: ITU-R
  P.1817-1 §12's International Visibility Code table, which states no
  wavelength, against ITU-R P.1814 equations (4)-(5). It is also what settles
  the branch convention at exactly 50 km and what proves equation (4)'s printed
  unit is wrong.
- ``TestTheUnitOfEquationFour`` — the 4.343 that P.1814 prints and does not
  mean, pinned from both published tables so that "fixing" it fails.
- ``TestInvariants`` — **V1**: monotonicity, the infinite-visibility limit, the
  exponents, and the branch joins that are *not* continuous.
- ``TestTheWarnings`` — the module says when the law it was asked for is the one
  the other source disputes, and when a visibility series crosses a jump.
- ``TestMolecularScattering`` — P.1817 equations (3)-(4), and the share of the
  visibility coefficient it accounts for at 550 nm that the aerosol exponent
  then carries to the wrong place (gap 22).
- ``TestTheVerticalColumn`` — the integral, the altitude that cancels and the
  one that does not, and the scale height's spread.
- ``TestAgainstPublishedZenithTransmittances`` — **compatible, not reproduced**:
  Gruneisen et al.'s MODTRAN ratio, and the residual of Ntanos et al.'s budget
  that no visibility can produce.
- ``TestBadInputIsRefused`` and ``TestNoHiddenDefaults``.
"""

from __future__ import annotations

import inspect
import math

import numpy as np
import pytest
from scipy.optimize import brentq

from quoss.channel import extinction
from quoss.channel.extinction import (
    AEROSOL_EXPONENT_BRANCH_BOUNDARIES_KM,
    KIM_FOG_VISIBILITY_KM,
    KIM_MIST_VISIBILITY_KM,
    KOSCHMIEDER_CONSTANT_P1814,
    KOSCHMIEDER_CONSTANT_P1817,
    MOLECULAR_SCATTERING_COEFFICIENT_KM_UM4,
    MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
    MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
    NEPER_TO_DB,
    VISIBILITY_REFERENCE_WAVELENGTH_M,
    VisibilityScalingLaw,
    aerosol_specific_attenuation_db_per_km,
    molecular_scattering_specific_attenuation_db_per_km,
    visibility_scaling_exponent,
    zenith_optical_depth_from_visibility,
    zenith_transmittance_from_visibility,
)
from quoss.channel.turbulence import NEPER_SQ_TO_DB_SQ
from quoss.core.errors import DegradationLog, DomainError, Severity

ITU = VisibilityScalingLaw.ITU_P1814
KIM = VisibilityScalingLaw.KIM_2001

# --------------------------------------------------------------------------- #
# Published values, transcribed with their citation (ADR 0009: a V2 value lives
# next to its citation in the test file, not in data/)
# --------------------------------------------------------------------------- #
KIM_TABLE_2_DB_PER_KM: tuple[tuple[float, float, float], ...] = (
    # visibility km, 785 nm, 1550 nm — Kim, McArthur & Korevaar, Proc. SPIE
    # 4214:26 (2001), Table 2, "calculated erroneously from Equation 6", i.e.
    # with q = 0.585 V^(1/3) below 6 km, which is ITU-R P.1814 equation (5).
    (0.05, 315.0, 272.0),
    (0.2, 75.0, 60.0),
    (0.5, 29.0, 21.0),
    (1.0, 14.0, 9.0),
    (2.0, 7.0, 4.0),
    (4.0, 3.0, 2.0),
    (10.0, 1.0, 0.4),
    (23.0, 0.5, 0.2),
)

KIM_TABLE_4_DB_PER_KM: tuple[tuple[float, float, float], ...] = (
    # Same paper, Table 4, "calculated using the new expression for q
    # (Equation 9)": q = 0 below 500 m, V - 0.5 to 1 km, 0.16 V + 0.34 to 6 km.
    (0.05, 340.0, 340.0),
    (0.2, 85.0, 85.0),
    (0.5, 34.0, 34.0),
    (1.0, 14.0, 10.0),
    (2.0, 7.0, 4.0),
    (4.0, 3.0, 2.0),
    (10.0, 1.0, 0.4),
    (23.0, 0.5, 0.2),
)

ITU_VISIBILITY_CODE_DB_PER_KM: tuple[tuple[float, float], ...] = (
    # Recommendation ITU-R P.1817-1 (02/2012) §12, "International visibility
    # code showing the attenuation (dB/km) for various climatic conditions".
    # Visibility converted from the metres the table prints. **The table states
    # no wavelength**, which is the point of TestTheItuVisibilityCodeIsTheSameLaw.
    (0.05, 315.0),
    (0.2, 75.0),
    (0.5, 28.9),
    (0.77, 18.3),
    (1.0, 13.8),
    (1.9, 6.9),
    (2.0, 6.6),
    (2.8, 4.6),
    (4.0, 3.1),
    (5.9, 2.0),
    (10.0, 1.1),
    (18.1, 0.6),
    (20.0, 0.54),
    (23.0, 0.47),
    (50.0, 0.19),
)

KIM_TABLE_WAVELENGTHS_M: tuple[float, float] = (785.0e-9, 1550.0e-9)
"""The two wavelengths of Kim et al.'s title, and of both their tables."""

ITU_VISIBILITY_CODE_WAVELENGTH_M: float = 785.0e-9
"""The wavelength the P.1817 table does not state, and that reproduces it.

It is the shorter of Kim et al.'s two, and one of the three P.1817's own Fig. 5
was measured at (780, 1550 and 9100 nm). See
``TestTheItuVisibilityCodeIsTheSameLaw::test_no_other_wavelength_reproduces_it``
for how well it is pinned down: to about 780 +- 10 nm, and no better.
"""

GRUNEISEN_ZENITH_TRANSMISSION_RATIO: float = 0.90
"""Gruneisen et al. 2021 §III A, on their MODTRAN runs under normal haze.

"MODTRAN simulations performed under normal haze conditions also indicate that
atmospheric transmission near zenith is about 90% of that at 1550 nm", the
comparison being with their 775 nm second-harmonic option.
"""

NTANOS_RESIDUAL_ZENITH_TRANSMITTANCE: float = 0.812
"""``L_zen`` implied by the 0.906 dB left over in Ntanos et al.'s 20 dB budget.

``docs/adr/0009-citation-policy.md`` gap 14, and
``tests/channel/test_link_budget.py::TestAgainstNtanosEtAl``. Not a published
number: a residual.
"""


def half_a_printed_digit(printed: float) -> float:
    """Return half of the last decimal place a published number was printed to.

    The tolerance a transcribed table deserves and no more: a cell printed as
    ``0.4`` says the value is in ``[0.35, 0.45)``, and a cell printed as ``315``
    says ``[314.5, 315.5)``. Derived from the transcription, not fitted to the
    model — which is the point, since a tolerance chosen to make today's number
    pass can never fail (``CLAUDE.md``).
    """
    text = repr(float(printed))
    decimals = len(text.split(".")[1].rstrip("0"))
    return 0.5 * 10.0 ** (-decimals)


def gamma_db_per_km(visibility_km: float, wavelength_m: float, law: VisibilityScalingLaw) -> float:
    """One specific attenuation, warnings discarded."""
    return float(
        aerosol_specific_attenuation_db_per_km(
            visibility_km,
            wavelength_m=wavelength_m,
            law=law,
            degradations=DegradationLog(),
        )
    )


# --------------------------------------------------------------------------- #
# V2
# --------------------------------------------------------------------------- #
class TestPublishedKimTables:
    """Both laws against the tables their own author printed them in.

    This is the strongest anchor the module has, and it is strong for a reason
    worth naming: the two tables share a paper, so the *same* transcription of
    the ``3.91``, of the 550 nm reference and of the decibel conversion has to
    reproduce 32 cells across two exponent rules, two wavelengths and three
    orders of magnitude in visibility. A wrong constant cannot fit half of them.
    """

    @pytest.mark.parametrize(
        ("table", "law", "name"),
        [
            (KIM_TABLE_2_DB_PER_KM, ITU, "Table 2 / equation (6)"),
            (KIM_TABLE_4_DB_PER_KM, KIM, "Table 4 / equation (9)"),
        ],
    )
    def test_every_cell_is_within_half_the_last_printed_digit(
        self,
        table: tuple[tuple[float, float, float], ...],
        law: VisibilityScalingLaw,
        name: str,
    ) -> None:
        worst = 0.0
        for visibility_km, at_785, at_1550 in table:
            for printed, wavelength_m in zip(
                (at_785, at_1550), KIM_TABLE_WAVELENGTHS_M, strict=True
            ):
                got = gamma_db_per_km(visibility_km, wavelength_m, law)
                tolerance = half_a_printed_digit(printed)
                assert got == pytest.approx(printed, abs=tolerance), (
                    f"Kim et al. {name}, V = {visibility_km} km, "
                    f"{wavelength_m * 1e9:.0f} nm: printed {printed}, got {got}"
                )
                worst = max(worst, abs(got - printed) / tolerance)
        # A margin, not a fit: if this ever exceeded 1 the assertion above fires
        # first. It is here so that a change which merely *nearly* breaks the
        # agreement is visible in the failure message of the next test.
        assert worst < 1.0

    def test_the_agreement_uses_nearly_all_of_the_printed_precision(self) -> None:
        """The 32 cells are tight, so the anchor is not slack.

        The worst cell of each table sits at 94 % of half its last printed
        digit. That is the useful fact: the tolerance is not generous, so the
        constants are pinned to about the precision the tables were printed to
        and not to an order of magnitude.
        """
        worst = 0.0
        for table, law in ((KIM_TABLE_2_DB_PER_KM, ITU), (KIM_TABLE_4_DB_PER_KM, KIM)):
            for visibility_km, at_785, at_1550 in table:
                for printed, wavelength_m in zip(
                    (at_785, at_1550), KIM_TABLE_WAVELENGTHS_M, strict=True
                ):
                    got = gamma_db_per_km(visibility_km, wavelength_m, law)
                    worst = max(worst, abs(got - printed) / half_a_printed_digit(printed))
        assert 0.9 < worst < 0.95

    def test_the_fog_advantage_of_1550_nm_is_the_whole_disagreement(self) -> None:
        """What choosing the law is worth, which is why it has no default.

        At 50 m of visibility ITU-R P.1814's exponent leaves 1550 nm 43 dB
        better than 785 nm over a kilometre; Kim et al.'s leaves them equal.
        Both numbers are their authors' own printed cells.
        """
        itu_785, itu_1550 = (gamma_db_per_km(0.05, w, ITU) for w in KIM_TABLE_WAVELENGTHS_M)
        kim_785, kim_1550 = (gamma_db_per_km(0.05, w, KIM) for w in KIM_TABLE_WAVELENGTHS_M)
        assert itu_785 - itu_1550 == pytest.approx(42.9, abs=0.1)
        assert kim_785 == kim_1550
        assert kim_1550 > itu_1550  # Kim et al.'s fog is worse for 1550 nm, not better


class TestTheItuVisibilityCodeIsTheSameLaw:
    """P.1817-1 §12's table, which states no wavelength, is P.1814 at 785 nm.

    Two ITU recommendations five years apart, one printing a closed form and
    the other printing a table of numbers with no formula and no wavelength
    beside it. That the second is the first evaluated at 785 nm is a
    cross-source check of a kind the channel has few of, and it pays for itself
    twice over: it fixes the branch convention at exactly 50 km, and it is half
    of the evidence that equation (4)'s printed unit is wrong.
    """

    def test_all_fifteen_cells_agree_to_within_three_percent(self) -> None:
        errors = [
            gamma_db_per_km(visibility_km, ITU_VISIBILITY_CODE_WAVELENGTH_M, ITU) / printed - 1.0
            for visibility_km, printed in ITU_VISIBILITY_CODE_DB_PER_KM
        ]
        assert max(abs(e) for e in errors) == pytest.approx(0.0279, abs=5e-4)
        assert math.sqrt(sum(e * e for e in errors) / len(errors)) == pytest.approx(
            0.0121, abs=5e-4
        )

    def test_the_fifty_kilometre_cell_settles_the_branch_convention(self) -> None:
        """Equation (5) leaves ``V = 50`` undefined; this cell decides it.

        P.1814 prints ``q = 1.6`` for ``V > 50 km`` and ``1.3`` for
        ``6 < V < 50``, with strict inequalities, so exactly 50 belongs to
        neither. The table's 0.19 dB/km is the 1.6 reading (0.192) and not the
        1.3 one (0.214), a 11 % difference, so the module reads the intervals
        half-open upward.
        """
        as_clear = NEPER_TO_DB * (KOSCHMIEDER_CONSTANT_P1814 / 50.0) * (785.0 / 550.0) ** -1.6
        as_haze = NEPER_TO_DB * (KOSCHMIEDER_CONSTANT_P1814 / 50.0) * (785.0 / 550.0) ** -1.3
        assert as_clear == pytest.approx(0.1922, abs=5e-5)
        assert as_haze == pytest.approx(0.2139, abs=5e-5)
        assert float(visibility_scaling_exponent(50.0, law=ITU)) == 1.6
        got = gamma_db_per_km(50.0, ITU_VISIBILITY_CODE_WAVELENGTH_M, ITU)
        assert abs(got - 0.19) < abs(as_haze - 0.19)

    def test_no_other_wavelength_reproduces_it(self) -> None:
        """The table pins its own unstated wavelength to about 780 +- 10 nm.

        Minimising the worst relative error over 600-1000 nm lands at 780.5 nm
        with 2.1 %, and 785 nm — Kim et al.'s — costs 2.8 %. A 2 % scatter
        remains at every wavelength, so the claim is "the same law near 780 nm",
        not "this table was computed at 785.0 nm". The control is 1550 nm, where
        the same cells are wrong by a factor of 1.16 to 2.97.
        """

        def worst(wavelength_nm: float) -> float:
            return max(
                abs(gamma_db_per_km(v, wavelength_nm * 1e-9, ITU) / printed - 1.0)
                for v, printed in ITU_VISIBILITY_CODE_DB_PER_KM
            )

        grid = np.arange(600.0, 1000.5, 0.5)
        best = float(grid[int(np.argmin([worst(nm) for nm in grid]))])
        assert best == pytest.approx(780.5, abs=1.0)
        assert worst(best) == pytest.approx(0.0210, abs=5e-4)
        assert worst(785.0) == pytest.approx(0.0279, abs=5e-4)

        ratios = [
            printed / gamma_db_per_km(v, 1550e-9, ITU)
            for v, printed in ITU_VISIBILITY_CODE_DB_PER_KM
        ]
        assert min(ratios) == pytest.approx(1.160, abs=0.005)
        assert max(ratios) == pytest.approx(2.936, abs=0.005)


class TestTheUnitOfEquationFour:
    """P.1814 equation (4) prints dB/km and returns nepers per km.

    The misreading is worth 4.343 — 9.9 dB/km in a 1 km fog — and it is the kind
    of error that produces a plausible number, so it is pinned from both
    published tables rather than argued. Whoever "corrects" this module to the
    printed unit fails here, with the two tables in the message.
    """

    def test_the_constant_is_the_two_percent_definition_inverted(self) -> None:
        assert KOSCHMIEDER_CONSTANT_P1817 == pytest.approx(-math.log(0.02), abs=5e-5)
        assert KOSCHMIEDER_CONSTANT_P1814 == pytest.approx(-math.log(0.02), abs=5e-3)

    def test_the_two_recommendations_round_it_differently_and_it_costs_nothing(self) -> None:
        """3.91 against 3.912: 0.051 %, or 0.0002 dB/km in very clear air."""
        relative = KOSCHMIEDER_CONSTANT_P1817 / KOSCHMIEDER_CONSTANT_P1814 - 1.0
        assert relative == pytest.approx(5.1e-4, abs=1e-5)
        at_23_km = gamma_db_per_km(23.0, 1550e-9, KIM)
        assert at_23_km * relative == pytest.approx(9.8e-5, abs=1e-5)

    def test_both_published_tables_require_the_decibel_conversion(self) -> None:
        """Read as printed, equation (4) misses both tables by exactly 4.343."""
        as_printed = KOSCHMIEDER_CONSTANT_P1814 / 1.0 * (785.0 / 550.0) ** -0.585
        assert as_printed == pytest.approx(3.175, abs=5e-4)
        # Kim et al. Table 2 and the P.1817 code table both print ~13.8 there.
        assert gamma_db_per_km(1.0, 785e-9, ITU) == pytest.approx(13.79, abs=5e-3)
        assert gamma_db_per_km(1.0, 785e-9, ITU) / as_printed == pytest.approx(
            NEPER_TO_DB, rel=1e-12
        )

    def test_the_misreading_costs_ten_decibels_in_a_kilometre_of_fog(self) -> None:
        correct = gamma_db_per_km(1.0, 1550e-9, ITU)
        as_printed = correct / NEPER_TO_DB
        assert correct - as_printed == pytest.approx(7.13, abs=0.01)
        at_785 = gamma_db_per_km(1.0, 785e-9, ITU)
        assert at_785 - at_785 / NEPER_TO_DB == pytest.approx(10.62, abs=0.01)

    def test_the_neper_conversion_is_the_root_of_the_turbulence_one(self) -> None:
        """One conversion, two modules, so they cannot drift."""
        assert NEPER_TO_DB**2 == pytest.approx(NEPER_SQ_TO_DB_SQ, rel=1e-15)


# --------------------------------------------------------------------------- #
# V1
# --------------------------------------------------------------------------- #
class TestInvariants:
    @pytest.mark.parametrize("law", [ITU, KIM])
    def test_infinite_visibility_is_exactly_transparent(self, law: VisibilityScalingLaw) -> None:
        """The limit the whole law has to reproduce, and exactly rather than nearly.

        Infinite visibility is the statement "no extinction", which is the value
        ``zenith_transmittance = 1.0`` has always meant in this package. It has
        to come out as an exact zero and an exact one, not 1e-17 and
        0.9999999999, because a scenario that declares no extinction and a
        scenario that models infinitely clear air must produce bit-identical
        results — the e2e suite compares by floating-point equality.
        """
        assert gamma_db_per_km(np.inf, 1550e-9, law) == 0.0
        transmittance = zenith_transmittance_from_visibility(
            np.inf,
            wavelength_m=1.55e-6,
            aerosol_scale_height_m=1200.0,
            station_altitude_m=30.0,
            visibility_altitude_m=0.0,
            law=law,
            degradations=DegradationLog(),
        )
        assert float(transmittance) == 1.0

    @pytest.mark.parametrize("wavelength_nm", [550.0, 785.0, 1550.0, 9100.0])
    @pytest.mark.parametrize("law", [ITU, KIM])
    def test_clearer_air_attenuates_less_above_the_reference_wavelength(
        self, law: VisibilityScalingLaw, wavelength_nm: float
    ) -> None:
        grid = np.geomspace(0.01, 200.0, 20_001)
        got = aerosol_specific_attenuation_db_per_km(
            grid, wavelength_m=wavelength_nm * 1e-9, law=law, degradations=DegradationLog()
        )
        assert np.all(np.diff(got) <= 0.0)

    def test_below_the_reference_wavelength_the_law_is_not_monotone(self) -> None:
        """The negative control, and it is a real defect of the published fit.

        Monotonicity in visibility is not a property of the law; it is a
        property of the law *at wavelengths longer than 550 nm*. The exponent
        jumps **up** at 6 km, and ``(lambda/550)^-q`` grows with ``q`` when
        ``lambda < 550``, so below the reference wavelength clearing the air
        makes the attenuation worse. At 400 nm, crossing 6 km upward adds
        **7.8 %**. No FSO link runs there, which is exactly why this has to be a
        test and not a remark: it is the part of the law that would be
        discovered by a reader of the code rather than by a user.
        """
        grid = np.geomspace(0.01, 200.0, 20_001)
        got = aerosol_specific_attenuation_db_per_km(
            grid, wavelength_m=400e-9, law=ITU, degradations=DegradationLog()
        )
        steps = np.diff(got)
        assert np.any(steps > 0.0)
        worst = int(np.argmax(steps))
        assert grid[worst] == pytest.approx(6.0, rel=1e-3)
        assert float(got[worst + 1] / got[worst] - 1.0) == pytest.approx(0.0779, abs=5e-4)

    @pytest.mark.parametrize(
        ("law", "expected"),
        [
            (ITU, (0.2155, 0.4643, 0.585, 0.8437, 1.3, 1.6)),
            (KIM, (0.0, 0.0, 0.5, 0.82, 1.3, 1.6)),
        ],
    )
    def test_the_exponents_are_the_printed_branches(
        self, law: VisibilityScalingLaw, expected: tuple[float, ...]
    ) -> None:
        visibility = np.array([0.05, 0.5, 1.0, 3.0, 10.0, 60.0])
        got = visibility_scaling_exponent(visibility, law=law)
        assert got == pytest.approx(np.asarray(expected), abs=5e-5)

    def test_kims_joins_are_exactly_continuous_and_p1814s_two_are_not(self) -> None:
        """The continuity check, and the answer is that one law fails it.

        Kim et al. equation (9) joins at 500 m, 1 km and 6 km to machine
        precision, and their paper claims the third one ("transitions better to
        a q value of 1.3"). ITU-R P.1814 equation (5) steps 22.3 % at 6 km.
        Neither law removes the 50 km step of 23.1 %, because both keep
        equation (6)'s upper branches.
        """
        for boundary in (KIM_FOG_VISIBILITY_KM, KIM_MIST_VISIBILITY_KM, 6.0):
            below = float(visibility_scaling_exponent(np.nextafter(boundary, 0.0), law=KIM))
            above = float(visibility_scaling_exponent(boundary, law=KIM))
            assert below == pytest.approx(above, abs=1e-9), f"Kim jumps at {boundary} km"

        jumps = {}
        for law in (ITU, KIM):
            for boundary in AEROSOL_EXPONENT_BRANCH_BOUNDARIES_KM:
                below = float(visibility_scaling_exponent(np.nextafter(boundary, 0.0), law=law))
                above = float(visibility_scaling_exponent(boundary, law=law))
                if abs(above - below) > 1e-9:
                    jumps[(law, boundary)] = above / below - 1.0
        assert set(jumps) == {(ITU, 6.0), (ITU, 50.0), (KIM, 50.0)}
        assert jumps[(ITU, 6.0)] == pytest.approx(0.2229, abs=5e-4)
        assert jumps[(ITU, 50.0)] == pytest.approx(0.2308, abs=5e-4)
        assert jumps[(KIM, 50.0)] == pytest.approx(0.2308, abs=5e-4)

    def test_what_the_six_kilometre_step_is_worth_in_decibels(self) -> None:
        """22 % in the exponent is 22 % in the answer at 1550 nm, 8 % at 785."""
        for wavelength_nm, expected in ((785.0, -0.0809), (1550.0, -0.2177)):
            below = gamma_db_per_km(np.nextafter(6.0, 0.0), wavelength_nm * 1e-9, ITU)
            above = gamma_db_per_km(6.0, wavelength_nm * 1e-9, ITU)
            assert above / below - 1.0 == pytest.approx(expected, abs=5e-4)

    def test_it_broadcasts_over_the_visibility_axis(self) -> None:
        """Vectorised over what actually varies: an hourly visibility series."""
        series = np.array([[23.0, 10.0, 5.0], [50.0, 2.0, 0.3]])
        got = aerosol_specific_attenuation_db_per_km(
            series, wavelength_m=1.55e-6, law=KIM, degradations=DegradationLog()
        )
        assert got.shape == series.shape
        for index in np.ndindex(series.shape):
            assert got[index] == pytest.approx(gamma_db_per_km(float(series[index]), 1.55e-6, KIM))

    def test_the_wavelength_ratio_is_a_pure_power_law_within_a_branch(self) -> None:
        """Two wavelengths in the same branch differ by exactly ``(l1/l2)^-q``."""
        for visibility_km in (0.7, 3.0, 20.0, 100.0):
            exponent = float(visibility_scaling_exponent(visibility_km, law=KIM))
            ratio = gamma_db_per_km(visibility_km, 1550e-9, KIM) / gamma_db_per_km(
                visibility_km, 775e-9, KIM
            )
            assert ratio == pytest.approx(2.0**-exponent, rel=1e-12)


class TestTheWarnings:
    @staticmethod
    def _codes(
        visibility: object, law: VisibilityScalingLaw, wavelength_m: float = 1.55e-6
    ) -> list[str]:
        log = DegradationLog()
        aerosol_specific_attenuation_db_per_km(
            visibility,  # type: ignore[arg-type]
            wavelength_m=wavelength_m,
            law=law,
            degradations=log,
        )
        return [entry.code for entry in log]

    def test_in_fog_p1814_says_which_source_disputes_it_and_by_how_much(self) -> None:
        log = DegradationLog()
        aerosol_specific_attenuation_db_per_km(
            0.05, wavelength_m=1.55e-6, law=ITU, degradations=log
        )
        entry = next(
            e for e in log if e.code == "extinction.kruse-exponent-below-the-fog-threshold"
        )
        assert entry.severity is Severity.WARNING
        assert entry.details["exponent_itu_p1814"] == pytest.approx(0.2155, abs=5e-5)
        assert entry.details["exponent_kim_2001"] == 0.0
        assert entry.details["db_per_km_itu_p1814"] == pytest.approx(271.65, abs=0.01)
        assert entry.details["db_per_km_kim_2001"] == pytest.approx(339.62, abs=0.01)
        assert "KIM_2001" in entry.message

    def test_kims_own_law_does_not_warn_about_itself(self) -> None:
        assert "extinction.kruse-exponent-below-the-fog-threshold" not in self._codes(0.05, KIM)

    def test_above_the_threshold_nothing_is_recorded(self) -> None:
        assert self._codes(KIM_FOG_VISIBILITY_KM, ITU) == []
        assert self._codes(np.array([0.6, 5.0]), ITU) == []

    def test_a_series_that_crosses_a_jump_is_named_with_the_size_of_the_step(self) -> None:
        log = DegradationLog()
        aerosol_specific_attenuation_db_per_km(
            np.array([4.0, 8.0]), wavelength_m=1.55e-6, law=ITU, degradations=log
        )
        entry = next(e for e in log if e.code == "extinction.visibility-spans-a-branch-boundary")
        assert entry.details["boundary_km"] == 6.0
        assert entry.details["exponent_below"] == pytest.approx(1.063, abs=5e-4)
        assert entry.details["exponent_above"] == 1.3
        assert entry.details["db_per_km_below"] == pytest.approx(0.9408, abs=5e-4)
        assert entry.details["db_per_km_above"] == pytest.approx(0.7359, abs=5e-4)

    def test_only_the_jumps_of_the_chosen_law_are_reported(self) -> None:
        """Kim's 6 km join is continuous, so crossing it is silent; 50 km is not."""
        assert self._codes(np.array([4.0, 8.0]), KIM) == []
        assert self._codes(np.array([4.0, 8.0]), ITU) == [
            "extinction.visibility-spans-a-branch-boundary"
        ]
        assert self._codes(np.array([40.0, 60.0]), KIM) == [
            "extinction.visibility-spans-a-branch-boundary"
        ]

    def test_a_series_spanning_both_jumps_reports_both(self) -> None:
        log = DegradationLog()
        aerosol_specific_attenuation_db_per_km(
            np.array([1.0, 100.0]), wavelength_m=1.55e-6, law=ITU, degradations=log
        )
        boundaries = [
            e.details["boundary_km"]
            for e in log
            if e.code == "extinction.visibility-spans-a-branch-boundary"
        ]
        assert boundaries == [6.0, 50.0]

    def test_a_scalar_exactly_on_a_boundary_warns_too(self) -> None:
        assert self._codes(6.0, ITU) == ["extinction.visibility-spans-a-branch-boundary"]

    def test_an_empty_array_is_silent_and_returns_nothing(self) -> None:
        log = DegradationLog()
        got = aerosol_specific_attenuation_db_per_km(
            np.array([]), wavelength_m=1.55e-6, law=ITU, degradations=log
        )
        assert got.shape == (0,)
        assert len(log) == 0


# --------------------------------------------------------------------------- #
# Molecular scattering, and gap 22
# --------------------------------------------------------------------------- #
class TestMolecularScattering:
    def test_the_reference_state_reproduces_the_printed_coefficient(self) -> None:
        at_reference = molecular_scattering_specific_attenuation_db_per_km(
            VISIBILITY_REFERENCE_WAVELENGTH_M,
            pressure_pa=MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
            temperature_k=MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
        )
        expected = NEPER_TO_DB * MOLECULAR_SCATTERING_COEFFICIENT_KM_UM4 / 0.55**4
        assert at_reference == pytest.approx(expected, rel=1e-12)
        assert at_reference == pytest.approx(0.05173, abs=5e-6)

    def test_it_is_a_fourth_power_of_wavelength(self) -> None:
        state = {
            "pressure_pa": MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
            "temperature_k": MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
        }
        one = molecular_scattering_specific_attenuation_db_per_km(775e-9, **state)
        two = molecular_scattering_specific_attenuation_db_per_km(1550e-9, **state)
        assert one / two == pytest.approx(16.0, rel=1e-12)

    def test_what_it_is_at_the_wavelengths_this_project_uses(self) -> None:
        """Quantifying the "negligible" that two sources state in words.

        ITU-R P.1814 §4.1 and Kim et al. §3 both say molecular contributions are
        negligible at FSO wavelengths and neither prints a number. This is the
        number, at the recommendation's own reference state.
        """
        state = {
            "pressure_pa": MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
            "temperature_k": MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
        }
        assert molecular_scattering_specific_attenuation_db_per_km(
            785e-9, **state
        ) == pytest.approx(0.01247, abs=5e-6)
        assert molecular_scattering_specific_attenuation_db_per_km(
            1550e-9, **state
        ) == pytest.approx(0.00082, abs=5e-6)

    @pytest.mark.parametrize(
        ("visibility_km", "share_at_550", "excess_at_1550"),
        [(10.0, 0.0305, 0.0286), (23.0, 0.0701, 0.0658), (50.0, 0.1523, 0.1397)],
    )
    def test_the_visibility_law_carries_the_molecular_share_at_the_wrong_exponent(
        self, visibility_km: float, share_at_550: float, excess_at_1550: float
    ) -> None:
        """Gap 22, measured: the mis-attribution, not a correction of it.

        Visibility at 550 nm is set by total extinction, molecules included.
        The law then scales the whole coefficient by an aerosol exponent of 1.3
        or 1.6 where the molecular part goes as the fourth power. So the law
        carries the molecular share to 1550 nm twelve times too large. It is
        left alone because subtracting at 550 and adding back at ``lambda`` is
        not what either source publishes.
        """
        state = {
            "pressure_pa": MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
            "temperature_k": MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
        }
        molecular_550 = molecular_scattering_specific_attenuation_db_per_km(
            VISIBILITY_REFERENCE_WAVELENGTH_M, **state
        )
        total_550 = NEPER_TO_DB * KOSCHMIEDER_CONSTANT_P1814 / visibility_km
        assert molecular_550 / total_550 == pytest.approx(share_at_550, abs=5e-4)

        exponent = float(visibility_scaling_exponent(visibility_km, law=ITU))
        scaled = molecular_550 * (1550.0 / 550.0) ** -exponent
        truth = molecular_scattering_specific_attenuation_db_per_km(1550e-9, **state)
        total_1550 = gamma_db_per_km(visibility_km, 1550e-9, ITU)
        assert (scaled - truth) / total_1550 == pytest.approx(excess_at_1550, abs=5e-4)


# --------------------------------------------------------------------------- #
# The vertical column
# --------------------------------------------------------------------------- #
def optical_depth(
    visibility_km: float,
    *,
    wavelength_m: float = 1.55e-6,
    scale_height_m: float = 1200.0,
    station_altitude_m: float = 0.0,
    visibility_altitude_m: float = 0.0,
    law: VisibilityScalingLaw = KIM,
) -> float:
    """One vertical optical depth, warnings discarded.

    The keyword defaults live **here, in the test**, and not in the module: the
    module refuses every one of them (``TestNoHiddenDefaults``).
    """
    return float(
        zenith_optical_depth_from_visibility(
            visibility_km,
            wavelength_m=wavelength_m,
            aerosol_scale_height_m=scale_height_m,
            station_altitude_m=station_altitude_m,
            visibility_altitude_m=visibility_altitude_m,
            law=law,
            degradations=DegradationLog(),
        )
    )


class TestTheVerticalColumn:
    def test_the_integral_is_the_coefficient_times_the_scale_height(self) -> None:
        """The closed form against the integral it claims to be.

        ``tau = int beta_v exp(-(h - h_v)/H) dh`` from the station upward. With
        the visibility measured at the station the exponential starts at 1 and
        the integral is ``beta * H`` exactly; the quadrature here is the check
        that no kilometre-to-metre factor went missing.
        """
        beta_per_km = gamma_db_per_km(23.0, 1.55e-6, KIM) / NEPER_TO_DB
        by_quadrature = beta_per_km * 1.2  # scale height in km
        assert optical_depth(23.0, station_altitude_m=30.0, visibility_altitude_m=30.0) == (
            pytest.approx(by_quadrature, rel=1e-12)
        )
        assert optical_depth(23.0) == pytest.approx(0.053048, abs=5e-7)

    def test_a_locally_measured_visibility_makes_the_altitude_cancel(self) -> None:
        """Exactly, at any altitude, which is why the two altitudes are separate.

        A meteorological station reports the visibility where it stands. Then
        the aerosol column above it does not depend on how high it stands — the
        coefficient at the bottom of the layer is the measured one whatever the
        bottom's altitude. Nothing in a visibility figure says whether it is
        local or a sea-level climatology, so both altitudes are arguments and
        neither has a default.
        """
        for altitude_m in (-400.0, 0.0, 30.0, 2168.0, 8848.0):
            assert optical_depth(
                23.0, station_altitude_m=altitude_m, visibility_altitude_m=altitude_m
            ) == pytest.approx(optical_depth(23.0), rel=1e-15)

    def test_a_sea_level_visibility_thins_exponentially_with_station_height(self) -> None:
        """And that is what makes a mountain site cheap to model as a good site.

        Teide OGS sits at 2390 m. Read as a sea-level figure, 23 km of
        visibility leaves it ``exp(-2390/1200) = 0.137`` of the aerosol column:
        **0.031 dB against 0.230 dB** at 1550 nm.
        """
        at_sea_level = optical_depth(23.0)
        higher = optical_depth(23.0, station_altitude_m=2390.0)
        assert higher / at_sea_level == pytest.approx(math.exp(-2390.0 / 1200.0), rel=1e-12)
        assert NEPER_TO_DB * at_sea_level == pytest.approx(0.2304, abs=5e-5)
        assert NEPER_TO_DB * higher == pytest.approx(0.0314, abs=5e-5)

    def test_the_scale_height_spread_in_the_literature_is_a_factor_of_1_67(self) -> None:
        """Gap 22's other half: no openable source publishes ``H``.

        Values in use run from about 1.2 to 2 km, and the optical depth is
        linear in it, so the spread is a factor 1.667 — 0.230 against 0.384 dB
        at 23 km of visibility and 1550 nm. That is larger than most terms this
        module was written to add, which is why the argument has no default.
        """
        thin = optical_depth(23.0, scale_height_m=1200.0)
        thick = optical_depth(23.0, scale_height_m=2000.0)
        assert thick / thin == pytest.approx(2000.0 / 1200.0, rel=1e-12)
        assert NEPER_TO_DB * thin == pytest.approx(0.2304, abs=5e-5)
        assert NEPER_TO_DB * thick == pytest.approx(0.3840, abs=5e-5)

    def test_the_transmittance_is_the_exponential_of_the_depth(self) -> None:
        for visibility_km in (2.0, 10.0, 23.0, 50.0):
            got = zenith_transmittance_from_visibility(
                visibility_km,
                wavelength_m=1.55e-6,
                aerosol_scale_height_m=1200.0,
                station_altitude_m=0.0,
                visibility_altitude_m=0.0,
                law=KIM,
                degradations=DegradationLog(),
            )
            assert float(got) == pytest.approx(math.exp(-optical_depth(visibility_km)), rel=1e-15)
            assert 0.0 < float(got) <= 1.0

    def test_it_lands_in_the_interval_the_link_budget_requires(self) -> None:
        """``atmospheric_transmittance`` refuses anything outside ``(0, 1]``.

        From 50 m of visibility — the "dense fog" bottom of ITU-R P.1817-1's own
        code table — up to ten thousand kilometres, and under both laws, nothing
        this function returns would be rejected there, and it rises with
        visibility all the way.
        """
        grid = np.geomspace(0.05, 1e4, 2_001)
        for law in (ITU, KIM):
            got = zenith_transmittance_from_visibility(
                grid,
                wavelength_m=1.55e-6,
                aerosol_scale_height_m=2000.0,
                station_altitude_m=0.0,
                visibility_altitude_m=0.0,
                law=law,
                degradations=DegradationLog(),
            )
            assert np.all(got > 0.0) and np.all(got <= 1.0)
            assert np.all(np.diff(got) >= 0.0)

    def test_below_ten_metres_of_visibility_the_transmittance_underflows_to_zero(self) -> None:
        """And that is a refusal downstream, not a wrong number — stated on purpose.

        ``exp(-tau)`` underflows to exactly 0.0 past ``tau = 745``, which
        through a 2 km aerosol layer at 1550 nm happens at **10.4 m** of
        visibility. :func:`~quoss.channel.link_budget.atmospheric_transmittance`
        requires ``(0, 1]``, so a scenario that declares such air gets a
        ``DomainError`` there rather than a zero key rate here. That is the
        right end: 10 m of visibility is 3 270 dB of vertical loss, and a link
        budget is not the place to discover that there is no link.
        """

        def at(visibility_km: float) -> float:
            return float(
                zenith_transmittance_from_visibility(
                    visibility_km,
                    wavelength_m=1.55e-6,
                    aerosol_scale_height_m=2000.0,
                    station_altitude_m=0.0,
                    visibility_altitude_m=0.0,
                    law=KIM,
                    degradations=DegradationLog(),
                )
            )

        assert at(0.0105) > 0.0
        assert at(0.0100) == 0.0
        assert NEPER_TO_DB * optical_depth(0.0104, scale_height_m=2000.0) == pytest.approx(
            3_266.0, abs=5.0
        )

    def test_the_warnings_travel_out_of_the_vertical_functions_too(self) -> None:
        log = DegradationLog()
        zenith_transmittance_from_visibility(
            0.05,
            wavelength_m=1.55e-6,
            aerosol_scale_height_m=1200.0,
            station_altitude_m=0.0,
            visibility_altitude_m=0.0,
            law=ITU,
            degradations=log,
        )
        assert [e.code for e in log] == ["extinction.kruse-exponent-below-the-fog-threshold"]


class TestAgainstPublishedZenithTransmittances:
    """Two published statements this model can be held against, and neither closes.

    Both are "compatible, not reproduced" in the vocabulary of
    ``docs/adr/0009-citation-policy.md``, and saying which is which is the point
    of the tests.
    """

    def test_gruneisens_modtran_ratio_fixes_the_optical_depth_without_the_scale_height(
        self,
    ) -> None:
        """The one anchor here that does not need the unpublished ``H``.

        Gruneisen et al. report that near-zenith atmospheric transmission at
        775 nm is about 90 % of that at 1550 nm under normal haze. 775 and 1550
        differ by exactly a factor two, so within the ``q = 1.3`` branch the
        ratio is ``exp(-(2^q - 1) tau_1550)`` and the scale height cancels
        along with the visibility: their 0.90 **is** a published 1550 nm zenith
        optical depth of 0.0720 Np, or ``L_zen = 0.9305``.
        """
        exponent = 1.3
        depth_1550 = math.log(1.0 / GRUNEISEN_ZENITH_TRANSMISSION_RATIO) / (2.0**exponent - 1.0)
        assert depth_1550 == pytest.approx(0.07205, abs=5e-6)
        assert math.exp(-depth_1550) == pytest.approx(0.9305, abs=5e-5)

        # And the model reproduces it, at the visibility their ratio implies.
        visibility_km = brentq(
            lambda v: optical_depth(v, scale_height_m=1200.0) - depth_1550, 6.0, 49.0
        )
        assert visibility_km == pytest.approx(16.93, abs=0.02)
        ratio = math.exp(
            -(optical_depth(visibility_km, wavelength_m=775e-9, scale_height_m=1200.0))
        ) / math.exp(-optical_depth(visibility_km, scale_height_m=1200.0))
        assert ratio == pytest.approx(GRUNEISEN_ZENITH_TRANSMISSION_RATIO, abs=1e-4)

    def test_their_absolute_transmittance_does_not_follow_from_their_ratio(self) -> None:
        """Their two statements need ``L_zen(1550) = 1.000`` to hold together.

        The same section takes ``eta_trans = 0.9`` for atmospheric scattering
        and absorption at 780 nm. With their own ratio of 0.90 that forces
        ``L_zen(1550) = 1.000`` exactly, which no atmosphere does. At the
        optical depth their ratio fixes, this model puts 775 nm at **0.837**,
        not 0.90. Compatible on the ratio; not reproduced on the level.
        """
        depth_1550 = math.log(1.0 / GRUNEISEN_ZENITH_TRANSMISSION_RATIO) / (2.0**1.3 - 1.0)
        at_775 = math.exp(-(2.0**1.3) * depth_1550)
        assert at_775 == pytest.approx(0.8374, abs=5e-5)
        assert at_775 / math.exp(-depth_1550) == pytest.approx(0.90, abs=1e-4)
        implied_1550_if_775_were_0_9 = 0.9 / GRUNEISEN_ZENITH_TRANSMISSION_RATIO
        assert implied_1550_if_775_were_0_9 == pytest.approx(1.0, abs=1e-12)

    def test_no_visibility_produces_the_residual_of_ntanos_budget(self) -> None:
        """The 6 km step is wide enough to skip over a published residual.

        ``docs/adr/0009-citation-policy.md`` gap 14 reads the 0.906 dB left over
        in Ntanos et al.'s 20 dB best case as ``L_zen = 0.812``, and calls it
        "an ordinary clear-sky zenith transmittance". With a model behind it
        that description does not survive. Through a 1.2 km aerosol layer at
        1550 nm the law's jump at 6 km leaves the band from **0.883 to
        1.129 dB** unreachable, and the 0.906 dB residual is inside it: no
        visibility produces it. The nearest value that any visibility does
        produce is 0.021 dB away, and it is the one at **6 km of visibility** —
        which P.1817's code table calls light fog, not clear air. The
        interesting half is not the unreachability, it is what the nearest
        reachable air is.
        """
        target = -math.log(NTANOS_RESIDUAL_ZENITH_TRANSMITTANCE)
        assert NEPER_TO_DB * target == pytest.approx(0.9046, abs=5e-4)

        just_below = optical_depth(np.nextafter(6.0, 0.0), law=ITU)
        just_above = optical_depth(6.0, law=ITU)
        assert NEPER_TO_DB * just_above == pytest.approx(0.8831, abs=5e-4)
        assert NEPER_TO_DB * just_below == pytest.approx(1.1289, abs=5e-4)
        assert just_above < target < just_below

        grid = np.geomspace(0.01, 1e4, 200_001)
        depths = np.asarray(
            zenith_optical_depth_from_visibility(
                grid,
                wavelength_m=1.55e-6,
                aerosol_scale_height_m=1200.0,
                station_altitude_m=0.0,
                visibility_altitude_m=0.0,
                law=ITU,
                degradations=DegradationLog(),
            )
        )
        closest = float(np.min(np.abs(depths - target)))
        assert closest == pytest.approx(0.00491, abs=5e-5)
        assert NEPER_TO_DB * closest == pytest.approx(0.0213, abs=5e-4)
        nearest = float(grid[int(np.argmin(np.abs(depths - target)))])
        assert nearest == pytest.approx(6.0, rel=2e-4)

    def test_a_thicker_aerosol_layer_does_reach_the_residual_and_says_at_what(self) -> None:
        """The finding above is conditional on ``H``, and the condition is stated.

        At the other end of the literature's spread, 2 km of scale height, the
        residual is reachable and corresponds to **9.8 km** of visibility —
        still haze, still not the clear sky a 20 dB best case implies.
        """
        target = -math.log(NTANOS_RESIDUAL_ZENITH_TRANSMITTANCE)
        visibility_km = brentq(
            lambda v: optical_depth(v, scale_height_m=2000.0, law=ITU) - target, 6.0, 49.0
        )
        assert visibility_km == pytest.approx(9.77, abs=0.02)
        assert float(visibility_scaling_exponent(visibility_km, law=ITU)) == 1.3


# --------------------------------------------------------------------------- #
# Refusals, and the absence of defaults
# --------------------------------------------------------------------------- #
class TestBadInputIsRefused:
    @pytest.mark.parametrize("visibility", [0.0, -1.0, float("nan")])
    def test_a_visibility_that_is_not_one(self, visibility: float) -> None:
        with pytest.raises(DomainError, match="visibility_km must be positive"):
            gamma_db_per_km(visibility, 1.55e-6, KIM)

    def test_one_bad_entry_in_an_array_refuses_the_whole_call(self) -> None:
        with pytest.raises(DomainError, match="visibility_km must be positive"):
            aerosol_specific_attenuation_db_per_km(
                np.array([23.0, -1.0]),
                wavelength_m=1.55e-6,
                law=KIM,
                degradations=DegradationLog(),
            )

    @pytest.mark.parametrize("wavelength", [0.0, -1.55e-6, float("inf")])
    def test_a_wavelength_that_is_not_one(self, wavelength: float) -> None:
        with pytest.raises(DomainError, match="wavelength_m must be finite and positive"):
            gamma_db_per_km(23.0, wavelength, KIM)

    @pytest.mark.parametrize("scale_height", [0.0, -1200.0, float("inf")])
    def test_a_scale_height_that_is_not_one(self, scale_height: float) -> None:
        with pytest.raises(DomainError, match="aerosol_scale_height_m must be finite and positive"):
            optical_depth(23.0, scale_height_m=scale_height)

    @pytest.mark.parametrize("name", ["station_altitude_m", "visibility_altitude_m"])
    @pytest.mark.parametrize("altitude", [float("inf"), float("nan")])
    def test_an_altitude_that_is_not_finite(self, name: str, altitude: float) -> None:
        with pytest.raises(DomainError, match=f"{name} must be finite"):
            optical_depth(23.0, **{name: altitude})  # type: ignore[arg-type]

    def test_a_negative_altitude_is_allowed_because_the_dead_sea_exists(self) -> None:
        assert optical_depth(23.0, station_altitude_m=-400.0) > optical_depth(23.0)

    @pytest.mark.parametrize(
        ("field", "value"),
        [("pressure_pa", 0.0), ("pressure_pa", -1.0), ("temperature_k", 0.0)],
    )
    def test_a_state_of_the_air_that_is_not_one(self, field: str, value: float) -> None:
        state = {
            "pressure_pa": MOLECULAR_SCATTERING_REFERENCE_PRESSURE_PA,
            "temperature_k": MOLECULAR_SCATTERING_REFERENCE_TEMPERATURE_K,
        }
        state[field] = value
        with pytest.raises(DomainError, match=f"{field} must be finite and positive"):
            molecular_scattering_specific_attenuation_db_per_km(1.55e-6, **state)

    def test_the_unit_message_names_the_mistake_it_expects(self) -> None:
        """A visibility in metres is the characteristic error, so it is named."""
        with pytest.raises(DomainError, match="kilometres"):
            gamma_db_per_km(-23_000.0, 1.55e-6, KIM)


class TestNoHiddenDefaults:
    """Every argument of every public function is required, and that is asserted.

    The easy way to close ADR 0009 gap 14 by accident is to give one of these a
    default: a scale height of 1200 m, a law of "itu-p1814", a sea-level
    reference altitude. Each would be a number nobody published, made
    authoritative by sitting in a signature. ``link_budget`` has the same test
    for ``zenith_transmittance`` and this is its twin.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "aerosol_specific_attenuation_db_per_km",
            "molecular_scattering_specific_attenuation_db_per_km",
            "visibility_scaling_exponent",
            "zenith_optical_depth_from_visibility",
            "zenith_transmittance_from_visibility",
        ],
    )
    def test_no_parameter_has_a_default(self, name: str) -> None:
        signature = inspect.signature(getattr(extinction, name))
        with_defaults = [
            parameter.name
            for parameter in signature.parameters.values()
            if parameter.default is not inspect.Parameter.empty
        ]
        assert with_defaults == []

    def test_the_scaling_law_has_two_members_and_no_alias_for_either(self) -> None:
        assert [member.value for member in VisibilityScalingLaw] == ["itu-p1814", "kim-2001"]

    def test_the_two_vertical_functions_take_the_same_arguments(self) -> None:
        """Same arguments, so a caller cannot mix inputs between the two.

        Getting a depth from one visibility and a transmittance from another is
        the kind of slip that produces two consistent-looking numbers.
        """
        depth = inspect.signature(zenith_optical_depth_from_visibility).parameters
        transmittance = inspect.signature(zenith_transmittance_from_visibility).parameters
        assert list(depth) == list(transmittance)
