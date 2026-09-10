"""Tests for `quoss.channel.beam`.

Organised by verification level, per ``tests/golden/README.md``:

- ``TestPublishedDivergence`` — **V2**. Ntanos et al. 2021 §4.1 declares a
  0.15 m transmitter at 1550 nm and states the divergence it produces, so their
  equation (6) is checked against their own prose.
- ``TestPublishedGainProduct`` — **V2**, and the one that found something: the
  product of their equations (3) and (5) is the Gaussian coupling derived in
  ``geometric_transmittance``, *exactly*, provided the transmitter gain is read
  as ``8 / w0^2``. As printed — ``(8 / w0)^2`` — it is 8x larger and returns a
  transmittance above 1 at the paper's own largest aperture.
- ``TestPublishedBeamWander`` — **V2**. ITU-R P.1622 equations (11a) and (11b)
  are the same statement in two units, and its §4.3 prose ("on the order of a
  beamwidth") is reproduced as a number.
- ``TestBeamRadiusInvariants`` / ``TestGeometricInvariants`` — **V1**. Bounds,
  monotonicity, and the far-field claim measured rather than assumed.
- ``TestTheTransmitApertureCutsBothWays`` — **V1**. The exponents that make a
  bigger uplink transmitter worse, checked by scaling, plus the table quoted in
  the module docstring.
- ``TestTheUplinkWanderWarning`` — that the model says when the geometry has
  stopped meaning what it looks like, from both sides.
- ``TestRejectsBadInput`` / ``TestModuleSurface``.

No V3: no independent implementation was located, and the gap is declared in
``tests/golden/README.md``. The absolute geometric loss is, however, indirectly
corroborated: it reproduces the "as low as 20 dB" total the paper reports for a
600 km link, which the printed gain product could not (see
``test_the_printed_form_contradicts_the_papers_own_reported_total``).
"""

from __future__ import annotations

import numpy as np
import pytest

from quoss.channel.atmosphere import integrated_cn2_m13
from quoss.channel.beam import (
    BEAM_WANDER_ANGLE_COEFFICIENT,
    BEAM_WANDER_DISPLACEMENT_COEFFICIENT,
    UPLINK_WANDER_BEAMWIDTH_LIMIT,
    beam_radius_m,
    divergence_half_angle_rad,
    geometric_transmittance,
    rayleigh_range_km,
    uplink_beam_wander_angle_rad,
    uplink_beam_wander_displacement_m,
    uplink_wander_to_divergence_ratio,
)
from quoss.core.errors import DegradationLog, DomainError, Severity
from quoss.core.units import deg_to_rad, km_to_m, transmittance_to_loss_db

# --------------------------------------------------------------------------- #
# The published system, transcribed with its citation
# --------------------------------------------------------------------------- #

NTANOS_WAVELENGTH_M = 1.55e-6
NTANOS_TRANSMIT_APERTURE_M = 0.15
NTANOS_RECEIVE_APERTURES_M = (0.75, 1.3, 2.3)
NTANOS_QUOTED_FULL_DIVERGENCE_URAD = 13.0
NTANOS_REFERENCE_RANGE_KM = 600.0
"""Ntanos et al. 2021, *Photonics* 8(12):544, §4.1 and §4.2.1.

"the wavelength of 1550 nm was selected"; "we assumed an aperture of 0.15 m for
all three transmitters that the satellites are equipped with, providing a small
beam divergence of about 13 urad"; "the OGSs of Skinakas, Helmos, and
Cholomondas are equipped with a receiver telescope aperture of 1.3 m, 2.3 m and
0.75 m, respectively"; and, from §4.2.1, "the total link loss for a 600 km link
distance can get as low as 20 dB in total. To achieve this loss performance, a
large enough telescope in the receiver is required."

The declared fixed losses that go with that last sentence, all from §4.1: SNSPD
efficiency 85 %, Bob receiver loss 2.65 dB, band-pass filter insertion loss
3 dB, polarization decoherence 0.3 dB.
"""

NTANOS_DECLARED_FIXED_LOSS_DB = (
    -10.0 * np.log10(0.85)  # detector quantum efficiency, 85 %
    + 2.65  # Bob receiver loss
    + 3.0  # band-pass filter insertion loss
    + 0.3  # polarization decoherence
)


@pytest.mark.physics
class TestPublishedDivergence:
    def test_reproduces_the_divergence_the_paper_quotes_for_its_own_transmitter(self) -> None:
        """Equation (6) against §4.1's "about 13 urad", which is the *full* angle.

        The check is worth more than it looks: it pins the half-versus-full
        convention against the source that uses both. Equation (6) returns
        6.58 urad and the prose says 13 urad, so the prose is the full angle and
        equation (6) is the half-angle. Had the two been read as the same
        quantity, every geometric loss in the module would be off by 6 dB.
        """
        half_angle = divergence_half_angle_rad(
            wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
        )
        full_angle_urad = 2.0 * half_angle * 1e6
        assert full_angle_urad == pytest.approx(NTANOS_QUOTED_FULL_DIVERGENCE_URAD, abs=0.5)
        assert half_angle * 1e6 == pytest.approx(6.578, abs=0.001)

    def test_the_divergence_is_the_far_field_angle_of_the_stated_waist(self) -> None:
        """Equation (6) is ``lambda / (pi w_t)`` with ``w_t = D_T / 2``, exactly.

        Which is what licenses ``beam_radius_m`` to propagate a Gaussian whose
        waist radius is half the aperture: the divergence and the radius have to
        come from the same beam, or the far-field radius and the near-field one
        describe different transmitters.
        """
        waist_m = 0.5 * NTANOS_TRANSMIT_APERTURE_M
        expected = NTANOS_WAVELENGTH_M / (np.pi * waist_m)
        measured = divergence_half_angle_rad(
            wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
        )
        assert measured == pytest.approx(expected, rel=1e-15)

    def test_divergence_scales_inversely_with_aperture(self) -> None:
        narrow = divergence_half_angle_rad(
            wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=1.0
        )
        wide = divergence_half_angle_rad(wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=0.1)
        assert wide / narrow == pytest.approx(10.0, rel=1e-12)


# --------------------------------------------------------------------------- #
# V2 — the published product of gains, and what it turned up
# --------------------------------------------------------------------------- #


def _printed_gain_product(*, receive_aperture_m: float, range_km: float, squared: bool) -> float:
    """Return ``G_t G_r L_fsl`` from Ntanos et al. equations (3) and (5).

    Transcribed literally so the comparison is against the paper, not against a
    rearrangement of it. ``squared=True`` is equation (5) exactly as printed,
    ``G_t = (8 / w_0)^2``; ``squared=False`` is the standard optical-antenna
    form, ``G_t = 8 / w_0^2``.
    """
    divergence = divergence_half_angle_rad(
        wavelength_m=NTANOS_WAVELENGTH_M, transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M
    )
    transmit_gain = (8.0 / divergence) ** 2 if squared else 8.0 / divergence**2
    receive_gain = (np.pi * receive_aperture_m / NTANOS_WAVELENGTH_M) ** 2
    free_space_loss = (NTANOS_WAVELENGTH_M / (4.0 * np.pi * km_to_m(range_km))) ** 2
    return float(transmit_gain * receive_gain * free_space_loss)


@pytest.mark.physics
class TestPublishedGainProduct:
    """The published product form against the Gaussian integral this module uses.

    A "gain times gain times free-space loss" product and a "fraction of a
    Gaussian inside a circle" integral look like different physics written in
    different languages. They are the same number, and showing that is what
    makes the module's formula traceable to a citable source rather than to a
    derivation nobody checked.
    """

    @pytest.mark.parametrize("receive_aperture_m", NTANOS_RECEIVE_APERTURES_M)
    def test_the_standard_gain_product_is_the_small_aperture_limit(
        self, receive_aperture_m: float
    ) -> None:
        """``G_t G_r L_fsl`` with ``G_t = 8/w0^2`` equals ``D_r^2 / (2 W^2)``.

        Algebraically it is an identity: the ``lambda^2`` of the receiver gain
        cancels the ``lambda^2`` of the free-space loss, the ``16 pi^2`` cancels
        the ``pi^2``, and what survives is ``D_r^2 / (2 (w0 z)^2)``. The residual
        4e-4 is not slack in the identity — it is the difference between the
        far-field radius ``w0 z`` the product form assumes and the exact
        ``W(z)`` that ``beam_radius_m`` returns, which is the 1.8e-4 in radius
        measured in ``TestBeamRadiusInvariants``, doubled by the square.
        """
        radius_m = float(
            beam_radius_m(
                NTANOS_REFERENCE_RANGE_KM,
                wavelength_m=NTANOS_WAVELENGTH_M,
                transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
            )
        )
        linearised = receive_aperture_m**2 / (2.0 * radius_m**2)
        product = _printed_gain_product(
            receive_aperture_m=receive_aperture_m,
            range_km=NTANOS_REFERENCE_RANGE_KM,
            squared=False,
        )
        assert product == pytest.approx(linearised, rel=1e-3)

    @pytest.mark.parametrize("receive_aperture_m", NTANOS_RECEIVE_APERTURES_M)
    def test_the_form_printed_in_equation_5_is_eight_times_larger(
        self, receive_aperture_m: float
    ) -> None:
        """``(8/w0)^2`` against ``8/w0^2``: a factor of exactly 8, so 9.03 dB.

        Asserted as exact because it is: the two differ by the factor 8 pulled
        inside or left outside the square, with no physics in between. Recording
        it here is what stops the printed form being copied in later as "the
        published version".
        """
        as_printed = _printed_gain_product(
            receive_aperture_m=receive_aperture_m,
            range_km=NTANOS_REFERENCE_RANGE_KM,
            squared=True,
        )
        standard = _printed_gain_product(
            receive_aperture_m=receive_aperture_m,
            range_km=NTANOS_REFERENCE_RANGE_KM,
            squared=False,
        )
        assert as_printed / standard == pytest.approx(8.0, rel=1e-12)
        assert 10.0 * np.log10(8.0) == pytest.approx(9.03, abs=0.005)

    def test_the_printed_form_collects_more_power_than_was_transmitted(self) -> None:
        """At the paper's own largest station, ``(8/w0)^2`` gives a transmittance of 1.36.

        This is the assertion that settles which reading was intended without
        appealing to a loss budget or to taste: a transmittance above 1 is a
        receiver collecting more light than the transmitter sent. It needs the
        paper's own numbers only — 0.15 m transmitter, 2.3 m receiver, 600 km,
        1550 nm — and no assumption from this repo.
        """
        as_printed = _printed_gain_product(
            receive_aperture_m=2.3, range_km=NTANOS_REFERENCE_RANGE_KM, squared=True
        )
        assert as_printed > 1.0
        assert as_printed == pytest.approx(1.36, abs=0.01)

        bounded = float(
            geometric_transmittance(
                NTANOS_REFERENCE_RANGE_KM,
                wavelength_m=NTANOS_WAVELENGTH_M,
                transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
                receive_aperture_m=2.3,
            )
        )
        assert bounded < 1.0

    def test_the_printed_form_contradicts_the_papers_own_reported_total(self) -> None:
        """§4.2.1 reports "as low as 20 dB" at 600 km; only one reading can produce it.

        Corroboration rather than a reproduction, and labelled as such: the
        paper does not tabulate its loss terms, so this adds up the ones it
        *does* declare (85 % detectors, 2.65 dB receiver, 3 dB filter, 0.3 dB
        polarization = 6.66 dB) and asks what the geometric term has to be for
        the total to land near 20 dB.

        With this module's formula and their largest telescope the geometric
        term is 8.07 dB, so the declared terms reach 14.7 dB and leave ~5 dB for
        absorption, scintillation and pointing — which the paper models and this
        arithmetic does not. With the printed ``(8/w0)^2`` the geometric term is
        *negative* (-1.33 dB, a gain), the total cannot exceed about 5.3 dB from
        the declared terms alone, and no plausible atmosphere closes a 15 dB gap.
        """
        geometric_db = float(
            transmittance_to_loss_db(
                geometric_transmittance(
                    NTANOS_REFERENCE_RANGE_KM,
                    wavelength_m=NTANOS_WAVELENGTH_M,
                    transmit_aperture_m=NTANOS_TRANSMIT_APERTURE_M,
                    receive_aperture_m=2.3,
                )
            )
        )
        assert geometric_db == pytest.approx(8.07, abs=0.01)

        with_this_module = geometric_db + NTANOS_DECLARED_FIXED_LOSS_DB
        assert 12.0 < with_this_module < 20.0

        printed_db = -10.0 * np.log10(
            _printed_gain_product(
                receive_aperture_m=2.3, range_km=NTANOS_REFERENCE_RANGE_KM, squared=True
            )
        )
        assert printed_db < 0.0
        assert printed_db + NTANOS_DECLARED_FIXED_LOSS_DB < 6.0


# --------------------------------------------------------------------------- #
# V2 — beam wander, ITU-R P.1622 §4.3
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestPublishedBeamWander:
    def test_the_two_printed_coefficients_differ_only_by_the_kilometre_factor(self) -> None:
        """P.1622 (11a) prints 2080 and (11b) prints 2.08, because (11a) takes L in km.

        The recommendation says so itself by writing (11b) as
        ``sigma_rc / (L x 10^3)``. Asserting it is what justifies building the
        displacement as "angle times range in metres" rather than transcribing
        2080 and hoping the caller's range is in kilometres.
        """
        ratio = BEAM_WANDER_DISPLACEMENT_COEFFICIENT / BEAM_WANDER_ANGLE_COEFFICIENT
        assert ratio == pytest.approx(km_to_m(1.0), rel=1e-12)

    def test_the_displacement_is_the_printed_equation_11a(self) -> None:
        """Reconstruct (11a) literally, with L in km and the 2080 coefficient.

        The angle-times-range construction has to give the same answer as the
        equation as printed, or the module has quietly adopted a different
        formula from the one it cites.
        """
        elevation = deg_to_rad(np.array([25.0, 55.0, 90.0]))
        aperture_m = 0.15
        range_km = 600.0
        integrated_cn2 = integrated_cn2_m13()
        printed = (
            BEAM_WANDER_DISPLACEMENT_COEFFICIENT
            * range_km
            * np.sqrt(integrated_cn2 / (aperture_m ** (1.0 / 3.0) * np.sin(elevation)))
        )
        measured = uplink_beam_wander_displacement_m(
            elevation, range_km=range_km, transmit_aperture_m=aperture_m
        )
        assert measured == pytest.approx(printed, rel=1e-12)

    def test_the_argument_of_the_square_root_is_dimensionless(self) -> None:
        """``mu`` is m^(1/3) (P.1622 (9)) and ``D_T^(1/3)`` is m^(1/3), so the ratio is a number.

        Checked numerically by the only means available to a unitless language:
        the same physical situation expressed with the length scaled, which must
        change the ratio by the cube root of the scaling and nothing else. If the
        aperture entered as ``D_T`` or ``D_T^(1/2)`` this fails, and the returned
        angle would still be a plausible few microradians.
        """
        elevation = deg_to_rad(60.0)
        small = float(uplink_beam_wander_angle_rad(elevation, transmit_aperture_m=0.1))
        large = float(uplink_beam_wander_angle_rad(elevation, transmit_aperture_m=0.8))
        assert small / large == pytest.approx(8.0 ** (1.0 / 6.0), rel=1e-12)

    def test_wander_is_on_the_order_of_a_beamwidth_as_the_recommendation_says(self) -> None:
        """P.1622 §4.3's prose, turned into the two numbers behind it.

        "Beam wander is significant in the Earth-to-space direction and can be
        on the order of a beamwidth." For the 15 cm terminal at 1550 nm under
        the nominal ITU profile: 2.56 m of r.m.s. displacement at 600 km against
        a 3.95 m beam radius, i.e. 0.65 beamwidths straight up, crossing one
        beamwidth by 20 degrees of elevation. "On the order of" is exactly
        right, which is the sort of agreement a prose claim can license — and
        the reason this is asserted as a range, not a value.
        """
        displacement_m = float(
            uplink_beam_wander_displacement_m(
                deg_to_rad(90.0), range_km=600.0, transmit_aperture_m=0.15
            )
        )
        radius_m = float(beam_radius_m(600.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15))
        assert displacement_m == pytest.approx(2.56, abs=0.01)
        assert radius_m == pytest.approx(3.95, abs=0.01)
        assert 0.1 < displacement_m / radius_m < 10.0

    def test_wander_grows_as_the_inverse_square_root_of_the_sine(self) -> None:
        """The elevation exponent, attributed rather than valued.

        Equation (11b) has ``sin(theta)^(-1/2)``, which is remarkably gentle
        next to the ``sin(theta)^(-11/6)`` of scintillation. Physically: wander
        comes from the wavefront tilt integrated once along the path, so it grows
        like the square root of the air mass, while scintillation compounds.
        """
        high = deg_to_rad(85.0)
        low = deg_to_rad(15.0)
        ratio = float(
            uplink_beam_wander_angle_rad(low, transmit_aperture_m=0.3)
            / uplink_beam_wander_angle_rad(high, transmit_aperture_m=0.3)
        )
        expected = (np.sin(high) / np.sin(low)) ** 0.5
        assert ratio == pytest.approx(float(expected), rel=1e-12)

    def test_a_better_site_wanders_less(self) -> None:
        """Wander is a power of the same integrated profile everything else uses.

        Raising the station cuts the integrated ``C_n^2`` by an order of
        magnitude (measured in ``atmosphere.integrated_cn2_m13``), and wander
        goes as its square root, so a mountain site wanders about 3.3 times less.
        """
        sea_level = float(uplink_beam_wander_angle_rad(deg_to_rad(90.0), transmit_aperture_m=0.15))
        mountain = float(
            uplink_beam_wander_angle_rad(
                deg_to_rad(90.0), transmit_aperture_m=0.15, station_height_m=2500.0
            )
        )
        profile_ratio = integrated_cn2_m13() / integrated_cn2_m13(station_height_m=2500.0)
        assert sea_level / mountain == pytest.approx(np.sqrt(profile_ratio), rel=1e-12)
        assert sea_level / mountain == pytest.approx(3.3, abs=0.1)


# --------------------------------------------------------------------------- #
# V1 — the beam radius, and the far-field claim measured
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestBeamRadiusInvariants:
    def test_the_far_field_shorthand_is_measured_not_assumed(self) -> None:
        """How wrong ``W = theta_div * z`` actually is, at three ranges.

        The shorthand is what almost every reference writes, and it is low by
        1.8e-4 relative at 600 km, 6.5e-3 at 100 km, and by ``sqrt(2)`` at the
        Rayleigh range, where the near field starts and the shorthand stops
        describing a beam at all. The exact form costs one square root, so the
        only thing the shorthand would have bought is this test not existing.
        """
        divergence = divergence_half_angle_rad(wavelength_m=1.55e-6, transmit_aperture_m=0.15)

        def relative_excess(range_km: float) -> float:
            exact = float(beam_radius_m(range_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15))
            shorthand = float(divergence * km_to_m(range_km))
            return exact / shorthand - 1.0

        assert relative_excess(600.0) == pytest.approx(1.8e-4, rel=0.05)
        assert relative_excess(100.0) == pytest.approx(6.5e-3, rel=0.05)

        at_rayleigh = rayleigh_range_km(wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        assert 1.0 + relative_excess(at_rayleigh) == pytest.approx(np.sqrt(2.0), rel=1e-12)

    def test_the_exact_radius_never_falls_below_the_far_field_line(self) -> None:
        """A hyperbola sits above its own asymptote everywhere, so this must hold.

        Worth asserting because the sign of the error is what decides whether
        the shorthand is optimistic or pessimistic about the link: the true beam
        is always *wider*, so the shorthand always overstates the collected
        power.
        """
        ranges_km = np.geomspace(1.0, 40_000.0, 60)
        exact = beam_radius_m(ranges_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        divergence = divergence_half_angle_rad(wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        assert np.all(exact >= divergence * km_to_m(ranges_km))

    def test_the_radius_never_goes_below_the_waist(self) -> None:
        ranges_km = np.geomspace(1e-6, 40_000.0, 60)
        exact = beam_radius_m(ranges_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        assert np.all(exact >= 0.5 * 0.15)
        assert np.all(np.diff(exact) > 0.0)

    def test_the_rayleigh_range_grows_as_the_square_of_the_aperture(self) -> None:
        small = rayleigh_range_km(wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        large = rayleigh_range_km(wavelength_m=1.55e-6, transmit_aperture_m=1.5)
        assert large / small == pytest.approx(100.0, rel=1e-12)

    def test_shapes_are_preserved_over_the_time_axis(self) -> None:
        """A pass is (n_samples,); a stack of passes is (n_satellites, n_samples)."""
        ranges_km = np.linspace(600.0, 2000.0, 12).reshape(3, 4)
        assert beam_radius_m(ranges_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15).shape == (
            3,
            4,
        )
        assert geometric_transmittance(
            ranges_km,
            wavelength_m=1.55e-6,
            transmit_aperture_m=0.15,
            receive_aperture_m=0.75,
        ).shape == (3, 4)


# --------------------------------------------------------------------------- #
# V1 — the geometric coupling
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestGeometricInvariants:
    def test_the_transmittance_stays_inside_zero_and_one(self) -> None:
        """The property the published product form does not have.

        Swept over four orders of magnitude in range and four in receiver size,
        including the regime where the receiver is far wider than the beam,
        which is where the linearised form passes 1.
        """
        ranges_km = np.geomspace(1.0, 40_000.0, 40)
        for receiver_m in (0.01, 0.75, 2.3, 30.0):
            values = geometric_transmittance(
                ranges_km,
                wavelength_m=1.55e-6,
                transmit_aperture_m=0.15,
                receive_aperture_m=receiver_m,
            )
            assert np.all(values > 0.0)
            assert np.all(values <= 1.0)

    def test_the_exact_form_is_always_at_or_below_its_linearisation(self) -> None:
        """``1 - exp(-x) <= x``, so the bounded form is the conservative one.

        Not a bound that was chosen: it is the first term of the exponential's
        own series, so the two agree to within the square of the argument. At
        0.75 m the gap is 0.9 % and at 2.3 m it is 8.7 %, which is why the
        difference is worth carrying rather than approximating away — a 0.4 dB
        error at the aperture that matters most.
        """
        for receiver_m, expected_gap in ((0.75, 0.0091), (1.3, 0.0274), (2.3, 0.0873)):
            radius_m = float(beam_radius_m(600.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15))
            linearised = receiver_m**2 / (2.0 * radius_m**2)
            exact = float(
                geometric_transmittance(
                    600.0,
                    wavelength_m=1.55e-6,
                    transmit_aperture_m=0.15,
                    receive_aperture_m=receiver_m,
                )
            )
            assert exact <= linearised
            assert linearised / exact - 1.0 == pytest.approx(expected_gap, rel=0.02)

    def test_more_range_and_less_aperture_always_lose_light(self) -> None:
        ranges_km = np.geomspace(100.0, 4000.0, 30)
        values = geometric_transmittance(
            ranges_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15, receive_aperture_m=0.75
        )
        assert np.all(np.diff(values) < 0.0)

        receivers = np.geomspace(0.05, 3.0, 30)
        collected = [
            float(
                geometric_transmittance(
                    600.0,
                    wavelength_m=1.55e-6,
                    transmit_aperture_m=0.15,
                    receive_aperture_m=float(d),
                )
            )
            for d in receivers
        ]
        assert np.all(np.diff(collected) > 0.0)

    def test_the_far_field_loss_is_inverse_square_in_range(self) -> None:
        """The 20 dB per decade of range that makes a LEO pass a moving target.

        With a receiver small against the beam, transmittance goes as ``1/z^2``,
        so doubling the slant range costs exactly 6 dB. Checked as the constancy
        of ``eta * z^2`` rather than at one pair of ranges, because that is the
        statement about the exponent rather than about two numbers.
        """
        ranges_km = np.array([400.0, 600.0, 1200.0, 2400.0])
        values = geometric_transmittance(
            ranges_km, wavelength_m=1.55e-6, transmit_aperture_m=0.15, receive_aperture_m=0.1
        )
        scaled = values * ranges_km**2
        assert np.all(np.abs(scaled / scaled[0] - 1.0) < 2e-3)

    def test_a_bigger_transmitter_and_a_bigger_receiver_are_interchangeable_far_out(self) -> None:
        """In the far field the coupling depends only on the product ``D_T D_r``.

        Because ``W = 2 lambda z / (pi D_T)``, the linearised transmittance is
        ``(pi D_T D_r / (2 sqrt(2) lambda z))^2``: doubling either aperture is
        the same 6 dB. Useful as a check because it is a symmetry the code does
        not implement explicitly — the two diameters enter through completely
        different expressions — so it can only hold if both are right.

        **And it is only a far-field symmetry, which this test measures rather
        than tolerates.** Trading 0.30 m of transmitter for 0.10 m of receiver
        breaks it by 5.4e-3, and that number is not slack: exactly
        ``W^2 = (theta z)^2 [1 + (z_R / z)^2]``, and the Rayleigh range grows as
        ``D_T^2``, so the 0.30 m transmitter carries sixteen times more
        near-field term than the 0.15 m one. Predicting the deviation from the
        two Rayleigh ranges is what separates "the symmetry holds where it should"
        from "the tolerance was widened until it passed".
        """
        one = float(
            geometric_transmittance(
                600.0, wavelength_m=1.55e-6, transmit_aperture_m=0.30, receive_aperture_m=0.05
            )
        )
        other = float(
            geometric_transmittance(
                600.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15, receive_aperture_m=0.10
            )
        )
        assert one == pytest.approx(other, rel=1e-2)

        def near_field_term(transmit_aperture_m: float) -> float:
            return (
                rayleigh_range_km(wavelength_m=1.55e-6, transmit_aperture_m=transmit_aperture_m)
                / 600.0
            ) ** 2

        predicted = (1.0 + near_field_term(0.15)) / (1.0 + near_field_term(0.30))
        assert one / other == pytest.approx(predicted, rel=1e-4)
        assert 1.0 - predicted == pytest.approx(5.4e-3, rel=0.02)

    def test_a_receiver_much_wider_than_the_beam_collects_everything(self) -> None:
        """Saturation, which is the physical content of the ``1 - exp`` form."""
        value = float(
            geometric_transmittance(
                10.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15, receive_aperture_m=5.0
            )
        )
        assert value == pytest.approx(1.0, abs=1e-12)


# --------------------------------------------------------------------------- #
# V1 — the aperture pulling both ways, which is the module's design claim
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheTransmitApertureCutsBothWays:
    def test_the_ratio_grows_as_aperture_to_the_five_sixths(self) -> None:
        """Divergence falls as ``D^(-1)``, wander only as ``D^(-1/6)``.

        So their ratio grows as ``D^(5/6)``, asserted here as an exponent rather
        than as a value: a factor of 10 in aperture is a factor of
        ``10^(5/6) = 6.81`` in how many beamwidths the beam strays. This is the
        claim the module docstring's table illustrates, and the reason a large
        uplink transmitter is not simply better.
        """
        log = DegradationLog()
        elevation = deg_to_rad(90.0)
        small = float(
            uplink_wander_to_divergence_ratio(
                elevation, wavelength_m=1.55e-6, transmit_aperture_m=0.1, degradations=log
            )
        )
        large = float(
            uplink_wander_to_divergence_ratio(
                elevation, wavelength_m=1.55e-6, transmit_aperture_m=1.0, degradations=log
            )
        )
        assert large / small == pytest.approx(10.0 ** (5.0 / 6.0), rel=1e-12)

    def test_the_table_in_the_module_docstring(self) -> None:
        """The three rows quoted in the docstring, so prose and code cannot drift.

        The lesson of the "219 km" in ``notes/LAST_CHANGES.md`` §14.1 is that a
        number living only in prose is a number that goes stale. These are the
        ones the module docstring prints.
        """
        log = DegradationLog()
        expected = {0.05: (19.7, 5.12, 0.26), 0.15: (6.58, 4.27, 0.65), 1.0: (0.99, 3.11, 3.15)}
        for aperture_m, (divergence_urad, wander_urad, ratio) in expected.items():
            measured_divergence = (
                divergence_half_angle_rad(wavelength_m=1.55e-6, transmit_aperture_m=aperture_m)
                * 1e6
            )
            measured_wander = (
                float(
                    uplink_beam_wander_angle_rad(deg_to_rad(90.0), transmit_aperture_m=aperture_m)
                )
                * 1e6
            )
            measured_ratio = float(
                uplink_wander_to_divergence_ratio(
                    deg_to_rad(90.0),
                    wavelength_m=1.55e-6,
                    transmit_aperture_m=aperture_m,
                    degradations=log,
                )
            )
            assert measured_divergence == pytest.approx(divergence_urad, rel=0.01)
            assert measured_wander == pytest.approx(wander_urad, rel=0.01)
            assert measured_ratio == pytest.approx(ratio, rel=0.01)

    def test_the_ratio_is_the_quotient_of_its_two_ingredients(self) -> None:
        """Asserted exactly, because it is a division and nothing else."""
        log = DegradationLog()
        elevation = deg_to_rad(np.array([30.0, 60.0, 90.0]))
        wander = uplink_beam_wander_angle_rad(elevation, transmit_aperture_m=0.15)
        divergence = divergence_half_angle_rad(wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        ratio = uplink_wander_to_divergence_ratio(
            elevation, wavelength_m=1.55e-6, transmit_aperture_m=0.15, degradations=log
        )
        assert np.array_equal(ratio, wander / divergence)

    def test_the_downlink_functions_have_nowhere_to_put_a_wander(self) -> None:
        """A quantity that must not be used in a downlink is better absent than defaulted.

        Same guard as ``uplink_log_irradiance_variance`` having nowhere to accept
        an aperture: ``geometric_transmittance`` takes no elevation and no
        turbulence at all, so a beam-wander term cannot be smuggled into a
        downlink budget through it.
        """
        import inspect

        parameters = inspect.signature(geometric_transmittance).parameters
        assert not any("wander" in name for name in parameters)
        assert not any("elevation" in name for name in parameters)
        assert not any("cn2" in name for name in parameters)


# --------------------------------------------------------------------------- #
# The model saying when the geometry has stopped meaning what it looks like
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestTheUplinkWanderWarning:
    def test_nothing_is_recorded_while_the_beam_still_holds_its_aim(
        self, degradations: DegradationLog
    ) -> None:
        uplink_wander_to_divergence_ratio(
            deg_to_rad(90.0),
            wavelength_m=1.55e-6,
            transmit_aperture_m=0.15,
            degradations=degradations,
        )
        assert len(degradations) == 0

    def test_a_warning_is_recorded_once_the_wander_exceeds_the_beam(
        self, degradations: DegradationLog
    ) -> None:
        """A metre-class uplink terminal is past the limit at every elevation.

        The point is not the number but that the caller is told: the ratio
        returned is a perfectly ordinary 3.15, and nothing about it says that a
        mean transmittance no longer describes this link.
        """
        ratio = uplink_wander_to_divergence_ratio(
            deg_to_rad(90.0),
            wavelength_m=1.55e-6,
            transmit_aperture_m=1.0,
            degradations=degradations,
        )
        assert float(ratio) > UPLINK_WANDER_BEAMWIDTH_LIMIT
        assert len(degradations) == 1
        entry = degradations.entries[0]
        assert entry.code == "beam.uplink-wander-exceeds-divergence"
        assert entry.severity is Severity.WARNING
        assert entry.where == "quoss.channel.beam.uplink_wander_to_divergence_ratio"
        assert entry.details["peak_ratio"] == pytest.approx(float(ratio))
        assert entry.details["transmit_aperture_m"] == 1.0

    def test_the_warning_fires_on_the_worst_sample_of_a_pass(
        self, degradations: DegradationLog
    ) -> None:
        """One warning for the array, keyed to its peak, not one per sample.

        A pass that crosses the limit near the horizon and clears it at
        culmination is one event to report, and the elevation-dependence is
        gentle (``sin^(-1/2)``), so the peak is the whole story.
        """
        elevation = deg_to_rad(np.linspace(10.0, 90.0, 50))
        ratio = uplink_wander_to_divergence_ratio(
            elevation,
            wavelength_m=1.55e-6,
            transmit_aperture_m=0.2,
            degradations=degradations,
        )
        assert float(np.min(ratio)) < UPLINK_WANDER_BEAMWIDTH_LIMIT < float(np.max(ratio))
        assert len(degradations) == 1
        assert degradations.entries[0].details["peak_ratio"] == pytest.approx(float(np.max(ratio)))

    def test_the_warning_is_a_warning_and_not_a_degradation(
        self, degradations: DegradationLog
    ) -> None:
        """Nothing was substituted, so ``has_degraded`` stays false.

        ``core/errors.py`` reserves DEGRADED for "a model was substituted". Here
        the caller gets exactly the ratio they asked for, in a regime where the
        *next* model they reach for will be the wrong one, which is what WARNING
        is for.
        """
        uplink_wander_to_divergence_ratio(
            deg_to_rad(90.0),
            wavelength_m=1.55e-6,
            transmit_aperture_m=1.0,
            degradations=degradations,
        )
        assert not degradations.has_degraded


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #


@pytest.mark.physics
class TestRejectsBadInput:
    def test_a_non_positive_range_is_rejected(self) -> None:
        """Zero range is rejected, not clamped: every formula divides by it."""
        with pytest.raises(DomainError, match="range_km must be strictly positive"):
            beam_radius_m(0.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15)
        with pytest.raises(DomainError, match="range_km must be strictly positive"):
            geometric_transmittance(
                np.array([600.0, -10.0]),
                wavelength_m=1.55e-6,
                transmit_aperture_m=0.15,
                receive_aperture_m=0.75,
            )
        with pytest.raises(DomainError, match="kilometres"):
            uplink_beam_wander_displacement_m(
                deg_to_rad(45.0), range_km=0.0, transmit_aperture_m=0.15
            )

    def test_a_non_finite_range_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="non-finite"):
            beam_radius_m(np.array([600.0, np.nan]), wavelength_m=1.55e-6, transmit_aperture_m=0.15)

    def test_a_non_positive_wavelength_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="wavelength_m"):
            divergence_half_angle_rad(wavelength_m=0.0, transmit_aperture_m=0.15)
        with pytest.raises(DomainError, match="wavelength_m"):
            rayleigh_range_km(wavelength_m=-1.0, transmit_aperture_m=0.15)
        with pytest.raises(DomainError, match="wavelength_m"):
            beam_radius_m(600.0, wavelength_m=float("nan"), transmit_aperture_m=0.15)

    def test_a_non_positive_aperture_is_rejected_on_both_sides(self) -> None:
        with pytest.raises(DomainError, match="transmit_aperture_m"):
            divergence_half_angle_rad(wavelength_m=1.55e-6, transmit_aperture_m=0.0)
        with pytest.raises(DomainError, match="transmit_aperture_m"):
            rayleigh_range_km(wavelength_m=1.55e-6, transmit_aperture_m=float("inf"))
        with pytest.raises(DomainError, match="receive_aperture_m"):
            geometric_transmittance(
                600.0,
                wavelength_m=1.55e-6,
                transmit_aperture_m=0.15,
                receive_aperture_m=-0.75,
            )
        with pytest.raises(DomainError, match="transmit_aperture_m"):
            uplink_beam_wander_angle_rad(deg_to_rad(45.0), transmit_aperture_m=0.0)

    def test_the_aperture_message_says_which_side_it_means(self) -> None:
        """For an uplink the transmitter is the ground terminal, which inverts intuition."""
        with pytest.raises(DomainError, match="ground terminal, not the spacecraft"):
            uplink_beam_wander_angle_rad(deg_to_rad(45.0), transmit_aperture_m=-1.0)

    def test_the_elevation_guard_fires_in_the_wander_functions(self) -> None:
        with pytest.raises(DomainError, match=r"\(0, pi/2\]"):
            uplink_beam_wander_angle_rad(0.0, transmit_aperture_m=0.15)
        with pytest.raises(DomainError, match="radians, not degrees"):
            uplink_beam_wander_angle_rad(45.0, transmit_aperture_m=0.15)
        with pytest.raises(DomainError, match="non-finite"):
            uplink_beam_wander_angle_rad(np.nan, transmit_aperture_m=0.15)

    def test_the_elevation_guard_fires_in_the_ratio_too(self, degradations: DegradationLog) -> None:
        with pytest.raises(DomainError, match=r"\(0, pi/2\]"):
            uplink_wander_to_divergence_ratio(
                0.0, wavelength_m=1.55e-6, transmit_aperture_m=0.15, degradations=degradations
            )

    def test_a_bad_station_height_is_rejected_through_the_profile(self) -> None:
        """The guard lives in ``atmosphere.integrated_cn2_m13`` and must not be bypassed."""
        with pytest.raises(DomainError, match="top of the turbulent atmosphere"):
            uplink_beam_wander_angle_rad(
                deg_to_rad(45.0), transmit_aperture_m=0.15, station_height_m=25_000.0
            )


class TestModuleSurface:
    def test_all_is_sorted_and_complete(self) -> None:
        from quoss.channel import beam

        assert beam.__all__ == sorted(beam.__all__)
        for name in beam.__all__:
            assert hasattr(beam, name)

    def test_the_module_documents_both_sources(self) -> None:
        from quoss.channel import beam

        assert beam.__doc__ is not None
        assert "P.1622" in beam.__doc__
        assert "Ntanos" in beam.__doc__

    def test_the_module_declares_what_it_leaves_out(self) -> None:
        """The omissions are load-bearing, so they are asserted like the physics.

        Three of them, each a number or a quoted decision rather than a silence:
        turbulence-induced beam spreading (P.1622 §4.4 says it is negligible),
        the 0.63 dB clipped at the transmitting aperture, and pointing error.
        """
        from quoss.channel import beam

        assert beam.__doc__ is not None
        assert "beam spreading" in beam.__doc__
        assert "0.63 dB" in beam.__doc__
        assert "pointing.py" in beam.__doc__
