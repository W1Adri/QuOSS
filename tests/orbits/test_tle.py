"""Tests for `quoss.orbits.tle`.

A TLE ("Two-Line Element set") is the format almost every real satellite orbit
is published in: two fixed-width, 69-character lines of text that a
ground-tracking pipeline fits so that SGP4 — a specific, non-negotiable analytic
theory, not a free choice of propagator — reproduces the tracked object near the
epoch. `tle.py` does not reimplement SGP4; it wraps the `sgp4` package from
PyPI and adds the checks that package skips (see its module docstring). What
these tests defend is therefore narrower than "is SGP4 correct" — that question
belongs to the `sgp4` maintainers and to AIAA 2006-6753 [1], the paper that
defines the theory — and is instead: does `parse_tle` catch what `sgp4` lets
through, and does `propagate_tle` wire the library up the way its own docstring
says it does.

Organised by verification level, per `tests/golden/README.md`:

* ``TestParseTleAcceptsAValidTle`` — V1: the happy path, including the WGS-72
  vs. WGS-84 contrast that is the whole reason `parse_tle` passes a gravity
  constant explicitly instead of taking the library's default.
* ``TestParseTleChecksum`` / ``TestParseTleRejectsMalformedInput`` /
  ``TestParseTleInitialisationErrors`` — V1, and each carries its own
  contrast: a test proving `Satrec.twoline2rv` accepts the exact input
  `parse_tle` refuses, which is the only way "we added a check `sgp4` skips" is
  a falsifiable claim rather than a comment.
* ``TestTleEpoch`` / ``TestPropagateTleAtItsOwnEpoch`` /
  ``TestPropagateTleAcceptsNegativeTimes`` /
  ``TestJdFrSplitPrecision`` / ``TestSgp4ErrorsNameTheSample`` /
  ``TestPropagateTleReusesTimeGridValidation`` /
  ``TestPropagateTleRejectsANonSatrec`` — V1, the plumbing of
  :func:`~quoss.orbits.tle.propagate_tle`.
* ``TestAgainstVallado2006VerificationData`` — V3: the official reference
  output for AIAA 2006-6753 [1], which ships free inside the `sgp4` package
  itself (see `tests/golden/README.md`).

References
----------
.. [1] Vallado, Crawford, Hujsak, Kelso, "Revisiting Spacetrack Report #3",
       AIAA 2006-6753, 2006.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest
import sgp4
from sgp4.api import SGP4_ERRORS, WGS72, WGS84, Satrec

from quoss.core.constants import WGS72_MU_KM3_S2
from quoss.core.errors import DomainError
from quoss.orbits.frames import Frame
from quoss.orbits.propagator import PropagationMethod, Trajectory
from quoss.orbits.tle import parse_tle, propagate_tle, tle_epoch_jd

# --------------------------------------------------------------------------- #
# Fixtures: one real, valid TLE, and the pieces used to break it on purpose
# --------------------------------------------------------------------------- #
ISS_TLE_LINE1 = "1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996"
ISS_TLE_LINE2 = "2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781"
"""One real ISS TLE: epoch 2020, day of year 029.91700964.

**A checksum correction, found while writing these tests, worth stating
plainly.** The TLE this task was specified against originally quoted the two
lines ending ``...9993`` and ``...212785``. Column 69 of a TLE line is not a
free digit: it is the sum of every digit in columns 1-68 of that same line,
counting ``'-'`` as 1 and everything else (letters, ``'.'``, ``'+'``, spaces) as
0, taken modulo 10 — and recomputing that sum by hand for both original lines
gives 6 and 1, not 3 and 5. Two independent checks agree this is a checksum
error and not a mistake in the check itself: this file's own
:func:`_reference_checksum` below (a second, deliberately separate
transcription of the same rule) and the `sgp4` package's own
``sgp4.io.compute_checksum`` both give the same 6 and 1.

The orbital data was never wrong — only the last character of each line was.
``Satrec.twoline2rv`` on the *original* lines returns ``satnum=25544``,
``jdsatepoch=2458877.5``, ``jdsatepochF=0.91700964...`` and ``mu=398600.8``
exactly as this task described, because :func:`sgp4.api.Satrec.twoline2rv` does
not check the checksum at all — which is precisely the gap
:func:`~quoss.orbits.tle.parse_tle` exists to close, and precisely why a test
suite for that function cannot use a fixture with a checksum error and call it
valid: `parse_tle` would (correctly) refuse it. The two module-level constants
above carry the corrected digits (``...9996`` and ``...212781``); the original,
invalid pair is not used anywhere below.
"""


def _reference_checksum(line: str) -> int:
    """Independent transcription of the TLE checksum rule.

    Column 69 of a TLE line is the checksum: sum every digit in columns 1-68,
    count ``'-'`` as 1 and everything else as 0, take the result modulo 10.
    Written a second time here rather than imported from
    :mod:`quoss.orbits.tle` or from ``sgp4.io``, so that a test built from this
    function and the module under test cannot share the same transcription bug
    — the same reasoning ``test_perturbations.py`` gives for its own
    independent copy of the Legendre polynomials.
    """
    total = 0
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return total % 10


def _corrupt_last_digit(line: str) -> str:
    """Return `line` with its checksum column changed to a different digit.

    ``(int(line[-1]) + 1) % 10`` is guaranteed to differ from the original, and
    stays a digit, so the corruption trips the checksum comparison specifically
    rather than the separate "column 69 must be a digit" check.
    """
    corrupted_digit = str((int(line[-1]) + 1) % 10)
    return line[:-1] + corrupted_digit


# A TLE that is well-formed and passes its checksum, but whose eccentricity
# SGP4 itself rejects at initialisation (`.error == 3`) once propagated through
# — one of the AIAA 2006-6753 [1] stress-test entries in the `sgp4` package's
# own ``SGP4-VER.TLE`` (there commented "try and check error code 2 but this",
# satellite number 33334), with its checksum corrected the same way the ISS
# fixture's was: the file's stress-test entries were written to trigger SGP4
# error codes, not to carry valid checksums, so line 1's checksum (9 -> 6) is
# fixed here to isolate the case this class targets from the one
# ``TestParseTleChecksum`` already covers.
ECCENTRIC_TLE_LINE1 = "1 33334U 78066F   06174.85818871  .00000620  00000-0  10000-3 0  6806"
ECCENTRIC_TLE_LINE2 = "2 33334  68.4714 236.1303 5602877 123.7484 302.5767  0.00001000 67521"

# The Minotaur upper stage that decayed 2005-11-29, one of the same file's
# entries (commented there "Sub-orbital case - Decayed 2005-11-29 (perigee =
# -51km), lost in 50 minutes"). Its checksum is already valid as shipped. Used
# below as a *real*, reproducible SGP4 failure (error code 6, "the satellite
# has decayed") rather than an injected one, since one is available.
DECAYED_TLE_LINE1 = "1 28872U 05037B   05333.02012661  .25992681  00000-0  24476-3 0  1534"
DECAYED_TLE_LINE2 = "2 28872  96.4736 157.9986 0303955 244.0492 110.6523 16.46015938 10708"


# --------------------------------------------------------------------------- #
# parse_tle: the happy path, and what it is checked against
# --------------------------------------------------------------------------- #
class TestParseTleAcceptsAValidTle:
    """The positive case, including the WGS-72 vs. WGS-84 contrast.

    **What this is:** every TLE is fitted against one specific Earth gravity
    model, WGS-72 — not WGS-84, the newer model everything else in this project
    (ground-station geodesy, GPS) uses. That is part of the SGP4 specification
    itself, not a choice `parse_tle` makes.

    **Why it is defended here:** ``sgp4.api.Satrec.twoline2rv`` happens to
    default to WGS-72 already, so passing it explicitly changes nothing about
    *this* call's output — measured below, both give ``mu == 398600.8``. The
    reason to still pass it explicitly is the same one
    :data:`quoss.orbits.perturbations.WGS72_ZONAL` exists as a distinct object
    from :data:`quoss.orbits.perturbations.EGM96_ZONAL`: relying on a library
    default to happen to match the physically correct choice is one dependency
    upgrade away from silently not matching it any more, and nothing about the
    resulting numbers would look wrong.

    **The number:** measured directly from the constant a caller would
    otherwise reach for by mistake — ``sgp4.api.WGS84`` — the two models give
    ``398600.8`` and ``398600.5`` km^3/s^2 for the *same* TLE: a difference of
    0.3 km^3/s^2, three parts in ten million of `mu`. Small, but not zero, and
    not the kind of difference a bounds check anywhere downstream would ever
    catch, because both are perfectly plausible numbers for the Earth's `mu`.
    """

    def test_satnum_and_gravity_constant_come_back_right(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        assert isinstance(satrec, Satrec)
        assert satrec.satnum == 25544
        assert satrec.mu == pytest.approx(WGS72_MU_KM3_S2)
        assert satrec.mu == pytest.approx(398_600.8)

    def test_wgs84_would_have_given_a_different_and_wrong_mu(self) -> None:
        """The contrast that justifies passing `WGS72` explicitly, measured."""
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)
        wgs84_satrec = Satrec.twoline2rv(ISS_TLE_LINE1, ISS_TLE_LINE2, WGS84)

        assert satrec.mu != wgs84_satrec.mu
        assert wgs84_satrec.mu == pytest.approx(398_600.5)

    def test_trailing_whitespace_is_tolerated(self) -> None:
        """A line read from a file often carries a trailing newline or padding.

        `parse_tle`'s own docstring says trailing whitespace is stripped before
        the 69-character length check runs; this is the test that says so
        rather than only the prose.
        """
        satrec = parse_tle(ISS_TLE_LINE1 + "  \n", ISS_TLE_LINE2 + "\n")

        assert satrec.satnum == 25544


# --------------------------------------------------------------------------- #
# The checksum: what `sgp4` skips, and what `parse_tle` catches instead
# --------------------------------------------------------------------------- #
class TestParseTleChecksum:
    """`Satrec.twoline2rv` never reads column 69 as anything but a placeholder.

    **What it is:** column 69 of each TLE line is a self-check digit — the
    ground station that produced the TLE printed the sum of its own line's
    digits (mod 10) there, so a transcription error anywhere in the preceding
    68 columns changes that sum and gets caught before the line is ever used.

    **Why it matters:** it is the only defence a TLE format has against a
    single flipped or dropped character corrupting an orbital element, and
    `sgp4.api.Satrec.twoline2rv` does not apply it — confirmed below, not
    assumed. A corrupted line does not raise, does not warn, and does not
    produce a `Satrec` with a suspicious inclination: it produces one that
    parses cleanly and describes the wrong orbit.

    **The number:** corrupting the checksum digit of :data:`ISS_TLE_LINE1`
    changes exactly one character out of 69. `Satrec.twoline2rv` accepts it
    with ``.error == 0``, the same value a genuinely sound line gets — there is
    nothing in its return value that distinguishes the two cases.
    """

    def test_a_corrupted_checksum_is_rejected(self) -> None:
        corrupted_line1 = _corrupt_last_digit(ISS_TLE_LINE1)
        assert corrupted_line1 != ISS_TLE_LINE1
        assert _reference_checksum(corrupted_line1) != int(corrupted_line1[-1])

        with pytest.raises(DomainError) as caught:
            parse_tle(corrupted_line1, ISS_TLE_LINE2)

        message = str(caught.value)
        assert "checksum" in message
        assert "twoline2rv" in message

    def test_the_trap_this_guards_against_is_real(self) -> None:
        """Contrast: raw `sgp4`, given the exact input `parse_tle` refuses.

        This is the test that makes "``Satrec.twoline2rv`` skips the checksum"
        a measured fact rather than a comment: the corrupted line is accepted,
        with no exception and no error field set, and it parses into a `Satrec`
        for the right satellite — the corruption is otherwise invisible.
        """
        corrupted_line1 = _corrupt_last_digit(ISS_TLE_LINE1)

        satrec = Satrec.twoline2rv(corrupted_line1, ISS_TLE_LINE2, WGS72)

        assert satrec.error == 0
        assert satrec.satnum == 25544


# --------------------------------------------------------------------------- #
# Structural checks: length and the line-number prefix
# --------------------------------------------------------------------------- #
class TestParseTleRejectsMalformedInput:
    """Two checks that have nothing to do with orbital mechanics.

    **What they are:** a TLE line is fixed-width, 69 characters, and its first
    field states its own line number ("1" or "2"). Neither fact is physics —
    they are file-format invariants — but a line failing either one is not a
    line `Satrec.twoline2rv` should ever be handed, because whatever it parses
    out of the wrong columns is not the field the caller thinks it is.

    **Why it matters:** swapping the two lines, or handing `parse_tle` a
    truncated line, produces a `Satrec` that still returns numbers — they are
    just numbers read from the wrong character columns, which is exactly the
    "plausible and wrong" failure mode this project treats as its worst case.
    """

    def test_a_line_that_is_too_short_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="expected 69"):
            parse_tle(ISS_TLE_LINE1[:-1], ISS_TLE_LINE2)

    def test_a_line_that_is_too_long_is_rejected(self) -> None:
        with pytest.raises(DomainError, match="expected 69"):
            parse_tle(ISS_TLE_LINE1 + "0", ISS_TLE_LINE2)

    def test_lines_given_in_the_wrong_order_are_rejected(self) -> None:
        with pytest.raises(DomainError, match=re.escape("must start with '1 '")):
            parse_tle(ISS_TLE_LINE2, ISS_TLE_LINE1)

    def test_two_copies_of_the_same_line_are_rejected(self) -> None:
        with pytest.raises(DomainError, match=re.escape("must start with '2 '")):
            parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE1)

    def test_garbage_input_is_rejected(self) -> None:
        with pytest.raises(DomainError):
            parse_tle("garbage", "more garbage")

    def test_a_non_digit_in_the_checksum_column_is_rejected(self) -> None:
        """69 characters and the right prefix are not enough if column 69 isn't a digit.

        A line built by string-editing rather than by SGP4 ground software can
        land a letter or a space in column 69 without changing the line's
        length or its ``"1 "``/``"2 "`` prefix — neither of the two checks
        above would catch it, and comparing it against the computed checksum
        (``int(printed)``) would raise ``ValueError`` instead of the intended
        ``DomainError`` if this guard were missing.
        """
        line1_with_letter_in_checksum_column = ISS_TLE_LINE1[:-1] + "X"

        with pytest.raises(DomainError, match="must be a checksum digit"):
            parse_tle(line1_with_letter_in_checksum_column, ISS_TLE_LINE2)

    def test_the_trap_this_particular_case_guards_against_is_real(self) -> None:
        """Contrast: raw `sgp4` on the same garbage, silently.

        `Satrec.twoline2rv` does not require its arguments to look like a TLE
        at all: fed two arbitrary strings, it returns an object — not an
        exception — with ``satnum == 0`` and ``.error == 2`` quietly set. A
        caller who does not know to check ``.error`` receives something that
        satisfies ``isinstance(x, Satrec)`` and describes no satellite at all.
        """
        satrec = Satrec.twoline2rv("garbage", "more garbage")

        assert satrec.error == 2
        assert satrec.satnum == 0


# --------------------------------------------------------------------------- #
# The satrec.error path: a well-formed TLE that SGP4 itself refuses
# --------------------------------------------------------------------------- #
class TestParseTleInitialisationErrors:
    """A TLE can pass every structural and checksum check and still be bad.

    **What it is:** `sgp4.api.SGP4_ERRORS` is a dictionary of six numeric codes
    the underlying Fortran-derived theory can raise at initialisation or during
    propagation — an eccentricity outside ``[0, 1)``, a negative semi-latus
    rectum, and so on. `Satrec.twoline2rv` sets ``satrec.error`` to the code
    and returns normally; it never raises. :func:`~quoss.orbits.tle.parse_tle`
    reads that field itself, once, after the call.

    **Why a dedicated fixture:** the garbage-input case above already fails
    earlier, at the length check, so it never reaches this branch at all — a
    string that is 7 characters long is never handed to `Satrec.twoline2rv`
    by `parse_tle`. Exercising the ``satrec.error != 0`` branch specifically
    needs a line that is 69 characters, starts with the right prefix, and
    passes its checksum, and is still physically invalid. :data:`ECCENTRIC_TLE_LINE1`
    is exactly that: one of the stress-test entries the `sgp4` package's own
    AIAA 2006-6753 [1] verification file carries for this purpose (commented
    there "try and check error code 2 but this"), with its checksum corrected —
    the file's stress-test entries were written to trigger `sgp4`'s internal
    error codes, not to carry valid checksums, so using it unmodified here
    would test the checksum branch instead of this one.

    **The number:** ``sgp4.api.Satrec.twoline2rv`` on this line returns
    ``.error == 3`` — "perturbed eccentricity is outside the range 0.0 to
    1.0" — silently. `parse_tle` turns that into a raised exception naming the
    same message.
    """

    def test_a_physically_invalid_but_well_formed_tle_is_rejected(self) -> None:
        with pytest.raises(DomainError, match=re.escape(SGP4_ERRORS[3])):
            parse_tle(ECCENTRIC_TLE_LINE1, ECCENTRIC_TLE_LINE2)

    def test_the_trap_this_case_guards_against_is_real(self) -> None:
        """Contrast: raw `sgp4` sets `.error` and returns normally."""
        satrec = Satrec.twoline2rv(ECCENTRIC_TLE_LINE1, ECCENTRIC_TLE_LINE2, WGS72)

        assert satrec.error == 3
        assert SGP4_ERRORS[satrec.error] == "perturbed eccentricity is outside the range 0.0 to 1.0"


# --------------------------------------------------------------------------- #
# tle_epoch_jd
# --------------------------------------------------------------------------- #
class TestTleEpoch:
    """The epoch as one float, for `TimeGrid`, which takes exactly one.

    **What it is:** `sgp4` itself stores a TLE's epoch as *two* numbers,
    ``jdsatepoch`` (an integer-valued Julian date) and ``jdsatepochF`` (the
    fraction of a day since then) — split for the same precision reason
    :func:`~quoss.orbits.tle.propagate_tle` keeps its own ``fr`` small (see
    that function's docstring). :func:`~quoss.orbits.tle.tle_epoch_jd` adds
    them back into one number, because :class:`~quoss.core.types.TimeGrid`
    takes a single ``epoch_jd`` and has nowhere to put a second float.

    **Why the test computes rather than hardcodes the expected value:** typing
    ``2458878.41700964`` into this file would make it a second, independent
    transcription of nothing — just a copy of what the addition below already
    produces, unable to catch a bug in that addition. Deriving the expected
    value from ``satrec.jdsatepoch`` and ``satrec.jdsatepochF`` directly is the
    only version of this check that could fail.
    """

    def test_the_epoch_is_the_sum_of_the_two_sgp4_fields(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)
        expected_jd = satrec.jdsatepoch + satrec.jdsatepochF

        assert tle_epoch_jd(satrec) == pytest.approx(expected_jd, rel=0.0, abs=0.0)


# --------------------------------------------------------------------------- #
# propagate_tle: shape, frame, method, and the grid it builds for itself
# --------------------------------------------------------------------------- #
class TestPropagateTleAtItsOwnEpoch:
    """The zero-elapsed-time case, and the container it must come back in.

    **Why this and not a numeric check against a reference:** at ``t_s = 0`` no
    physics happens yet, so what is being tested is entirely plumbing — did the
    right shape, frame, method and epoch reach the caller — and the V3 class at
    the bottom of this file is where the actual SGP4 numbers are checked
    against Vallado's own reference output.
    """

    def test_shape_frame_method_and_grid_epoch(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        traj = propagate_tle(satrec, np.array([0.0]))

        assert isinstance(traj, Trajectory)
        assert traj.r_km.shape == (1, 1, 3)
        assert traj.v_km_s.shape == (1, 1, 3)
        assert traj.frame is Frame.TEME
        assert traj.method is PropagationMethod.SGP4
        assert traj.grid.epoch_jd == tle_epoch_jd(satrec)
        assert np.all(np.isfinite(traj.r_km))
        assert np.all(np.isfinite(traj.v_km_s))


class TestPropagateTleAcceptsNegativeTimes:
    """A TLE's epoch usually sits in the middle of the window someone wants.

    **What it is:** a TLE is fitted to a tracking pass at whatever moment the
    ground station happened to observe the satellite, which has no reason to
    be the start of a scenario's time window — it is routinely somewhere in
    the *middle* of the pass a scenario cares about. `propagate_tle` has to run
    both backward and forward from that instant.

    **Why bit-for-bit and not "close":** the task that specified this test
    expected only agreement "to the precision of sgp4, not bit for bit" between
    a sample computed in a batch and the same sample computed alone. Measured
    instead of assumed: they are identical to the last bit. The reason is in
    the implementation, not a coincidence — `propagate_tle` computes the
    ``jd``/``fr`` split from ``grid.t_s`` with `NumPy`'s elementwise
    ``np.floor``, so the value at one array position never depends on any other
    position, and `sgp4.api.Satrec.sgp4_array` evaluates each row of its input
    independently. The tolerance is kept slightly looser than exact equality
    anyway (1 nanometre, ``1e-12`` km) so this test does not silently start
    failing the day an equivalent but differently-ordered implementation is
    substituted.
    """

    def test_the_middle_sample_matches_propagating_it_alone(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        batch = propagate_tle(satrec, np.array([-3600.0, 0.0, 3600.0]))
        alone = propagate_tle(satrec, np.array([0.0]))

        assert np.all(np.isfinite(batch.r_km))
        assert np.all(np.isfinite(batch.v_km_s))
        np.testing.assert_allclose(batch.r_km[0, 1], alone.r_km[0, 0], rtol=0.0, atol=1e-12)
        np.testing.assert_allclose(batch.v_km_s[0, 1], alone.v_km_s[0, 0], rtol=0.0, atol=1e-12)

    def test_the_two_negative_samples_are_distinct_finite_states(self) -> None:
        """Not equal to each other or to the epoch state: real motion, not a stub."""
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        traj = propagate_tle(satrec, np.array([-3600.0, -1800.0, 0.0]))

        separations_km = np.linalg.norm(np.diff(traj.r_km[0], axis=0), axis=-1)
        assert np.all(separations_km > 100.0)


# --------------------------------------------------------------------------- #
# The jd/fr split: why fr is kept small
# --------------------------------------------------------------------------- #
class TestJdFrSplitPrecision:
    """Why `propagate_tle` folds whole days back into `jd` instead of letting `fr` grow.

    **What it is:** `Satrec.sgp4_array` takes time as a *pair* of arrays, whole
    Julian date (``jd``) and day fraction (``fr``), instead of one array of
    Julian dates. `sgp4.conveniences` documents that this split exists so the
    fractional part "can, unlike the first float, be accurate down to very
    small fractions of a second" — but only if it *stays* small. Computing
    ``fr`` as ``satrec.jdsatepochF + t_s / 86400`` without ever subtracting
    whole days back out would let it grow past 1.0 after the first day and keep
    growing for as long as the propagation runs, which is exactly the "let a
    fraction grow without bound" failure the split was meant to prevent.
    `propagate_tle` instead recomputes ``whole_days = floor(jdsatepochF +
    t_s/86400)`` at every sample and keeps ``fr`` in ``[0, 1)`` throughout — see
    the function's own docstring for the three-line formula.

    **What was measured, not assumed, in writing this test:** the task that
    specified it anticipated that letting ``fr`` grow (the "naive" split below)
    might cost measurable accuracy after 30 days, and asked for the actual
    number rather than a guess. Running both splits through the *same*
    ``Satrec.sgp4_array`` call for the ISS TLE at ``t_s = 30 * 86400`` seconds
    gives **zero difference in either position or velocity, to the last bit of
    a 64-bit float** — not "small", exactly zero, checked again out to ten
    years of elapsed time during development (not asserted below, since that
    number was not produced by a test that runs, per this project's own rule
    against citing unreproduced figures). The honest reading is not "the
    normalisation was unnecessary": it is that this particular build of `sgp4`
    (a compiled C extension, ``vallado_cpp.abi3.so``) evidently does its own
    internal reduction of ``jd + fr`` in double precision regardless of how
    large ``fr`` arrives, so nothing here can be shown to depend on the
    library's own internals staying that way in a future release. Keeping
    ``fr`` small is therefore hygiene and a documented contract with `sgp4`'s
    own stated design, not a fix for an error this test could measure — and
    saying so plainly is more honest than implying the opposite.
    """

    def test_the_naive_and_folded_splits_agree_at_thirty_days(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)
        thirty_days_s = 30.0 * 86400.0

        traj = propagate_tle(satrec, np.array([thirty_days_s]))

        # The split the module's docstring warns against: fr grows past 1.0
        # instead of being folded back into jd.
        naive_fr = np.array([satrec.jdsatepochF + thirty_days_s / 86400.0])
        naive_jd = np.array([satrec.jdsatepoch])
        assert naive_fr[0] > 1.0, "the whole point of the naive split is that fr leaves [0, 1)"
        error, r_naive, v_naive = satrec.sgp4_array(naive_jd, naive_fr)
        assert error[0] == 0

        position_diff_km = float(np.linalg.norm(traj.r_km[0, 0] - r_naive[0]))
        velocity_diff_km_s = float(np.linalg.norm(traj.v_km_s[0, 0] - v_naive[0]))

        assert position_diff_km == 0.0
        assert velocity_diff_km_s == 0.0


# --------------------------------------------------------------------------- #
# SGP4 failures during propagation: named, not swallowed
# --------------------------------------------------------------------------- #
class TestSgp4ErrorsNameTheSample:
    """A batch of samples must say *which one* failed, not just that one did.

    **What it is:** ``Satrec.sgp4_array`` returns one error code per input
    sample, not one for the whole call — a satellite can be propagated
    successfully right up until the instant it decays, and the array reflects
    that per-sample rather than aborting the batch. `propagate_tle` finds the
    first non-zero entry and raises naming its position and its ``t_s``.

    **Why a real satellite instead of a stub:** the `sgp4` package's own AIAA
    2006-6753 [1] verification file carries an actual decayed object for
    exactly this purpose — :data:`DECAYED_TLE_LINE1` is the upper stage of a
    Minotaur launch, commented there "Sub-orbital case - Decayed 2005-11-29
    (perigee = -51km), lost in 50 minutes" — so no monkeypatch is needed to
    reach this branch, unlike the analogous case in
    ``test_perturbations.py``'s ``test_an_integrator_failure_becomes_a_convergence_error``,
    where no physically reachable input exists because the force model's own
    domain check catches every one first.

    **The number:** propagating this TLE from its own epoch (``t_s = 0``,
    valid) out to one hour later (``t_s = 3600``) measures error code 6 at the
    second sample, ``.error == 0`` at the first — the satellite is intact at
    its epoch and not one hour later, which is the entire meaning of the
    comment in the source file.
    """

    def test_a_decayed_satellite_names_the_failing_sample(self) -> None:
        satrec = parse_tle(DECAYED_TLE_LINE1, DECAYED_TLE_LINE2)

        with pytest.raises(DomainError) as caught:
            propagate_tle(satrec, np.array([0.0, 3600.0]))

        message = str(caught.value)
        assert SGP4_ERRORS[6] in message
        assert re.search(r"\bsample 1\b", message)
        assert "3600" in message

    def test_the_first_sample_alone_is_fine(self) -> None:
        """The contrast that shows the failure is about `t_s`, not the TLE itself."""
        satrec = parse_tle(DECAYED_TLE_LINE1, DECAYED_TLE_LINE2)

        traj = propagate_tle(satrec, np.array([0.0]))

        assert np.all(np.isfinite(traj.r_km))


# --------------------------------------------------------------------------- #
# t_s becomes a TimeGrid: its validation applies without repeating it here
# --------------------------------------------------------------------------- #
class TestPropagateTleReusesTimeGridValidation:
    """`propagate_tle` builds a `TimeGrid` from `t_s`; a bad `t_s` fails there.

    **What it is:** :func:`~quoss.orbits.tle.propagate_tle` wraps its `t_s`
    argument in ``TimeGrid(epoch_jd=tle_epoch_jd(satrec), t_s=t_s)`` rather
    than validating it by hand — so an empty array, one containing NaN, or one
    that is not strictly increasing raises exactly the `DomainError`
    :class:`~quoss.core.types.TimeGrid` already raises for the same input,
    already covered by that class's own tests.

    **Why only two smoke tests here:** re-deriving every one of `TimeGrid`'s
    invariants in this file would test `TimeGrid` a second time under a
    different name, which is the duplication `tests/golden/README.md` and this
    project's test style both avoid — what needs proving here is only that the
    validation is reached at all, not that it is correct.
    """

    def test_an_empty_t_s_is_rejected(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        with pytest.raises(DomainError):
            propagate_tle(satrec, np.array([]))

    def test_a_non_increasing_t_s_is_rejected(self) -> None:
        satrec = parse_tle(ISS_TLE_LINE1, ISS_TLE_LINE2)

        with pytest.raises(DomainError):
            propagate_tle(satrec, np.array([0.0, 100.0, 50.0]))


class TestPropagateTleRejectsANonSatrec:
    def test_a_string_is_not_a_satrec(self) -> None:
        """The contract's own example: a scenario field that forgot to call `parse_tle`."""
        with pytest.raises(DomainError, match="Satrec"):
            # `sgp4` ships no type stubs, so mypy treats `Satrec` as `Any` and
            # raises no complaint about passing a `str` here worth silencing —
            # this is a runtime check only.
            propagate_tle("not a satrec", np.array([0.0]))


# --------------------------------------------------------------------------- #
# V3 — the sgp4 package's own AIAA 2006-6753 verification data
# --------------------------------------------------------------------------- #
_SGP4_PACKAGE_DIR = Path(sgp4.__file__).parent
_TLE_FILE = _SGP4_PACKAGE_DIR / "SGP4-VER.TLE"
_TCPPVER_FILE = _SGP4_PACKAGE_DIR / "tcppver.out"
_HAS_VALLADO_DATA = _TLE_FILE.exists() and _TCPPVER_FILE.exists()


def _parse_verification_tle_pairs(path: Path) -> dict[int, tuple[str, str]]:
    """Extract every ``(line1, line2)`` pair from ``SGP4-VER.TLE``, by NORAD number.

    Deliberately a fresh, minimal reader rather than a reuse of
    ``sgp4.tests``'s own parser for the same file (viewable with
    ``python -c "import sgp4.tests, inspect; print(inspect.getsource(sgp4.tests))"``):
    that parser also extracts the three extra minute fields appended after
    column 69 (a canned start/stop/step propagation window) because the
    library's own test suite uses them to build its own time grid. This
    project's :func:`~quoss.orbits.tle.propagate_tle` takes an explicit
    ``t_s`` instead, taken directly from ``tcppver.out``'s own ``t_min``
    column, so those three extra fields are never read here.
    """
    lines = [
        line.rstrip("\n")
        for line in path.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    pairs: dict[int, tuple[str, str]] = {}
    index = 0
    while index < len(lines) - 1:
        line1, line2 = lines[index], lines[index + 1]
        if line1.startswith("1 ") and line2.startswith("2 "):
            satnum = int(line1[2:7])
            pairs[satnum] = (line1[:69], line2[:69])
            index += 2
        else:
            index += 1
    return pairs


def _parse_tcppver(path: Path) -> dict[int, np.ndarray]:
    """Extract, per satellite, the reference ``[t_min, x, y, z, vx, vy, vz]`` rows.

    Each block in ``tcppver.out`` starts with a header line reading
    ``"<satnum> xx"``. The first data row of a block (``t_min == 0``, the
    epoch) has exactly 7 whitespace-separated columns; every later row in the
    same block carries additional columns (orbital elements, a calendar
    timestamp) that this test does not need — only the first 7 columns of
    every row are read, which are always present and always in the same order.
    """
    header_pattern = re.compile(r"^\s*(\d+)\s+xx\s*$")
    blocks: dict[int, list[list[float]]] = {}
    current: int | None = None
    for line in path.read_text().splitlines():
        header_match = header_pattern.match(line)
        if header_match:
            current = int(header_match.group(1))
            blocks[current] = []
            continue
        if current is not None and line.strip():
            blocks[current].append([float(token) for token in line.split()[:7]])
    return {satnum: np.array(rows) for satnum, rows in blocks.items()}


@pytest.mark.skipif(
    not _HAS_VALLADO_DATA,
    reason=(
        "This install of the sgp4 package does not ship SGP4-VER.TLE/tcppver.out; "
        "see tests/golden/README.md, section 'Gaps, stated rather than filled'."
    ),
)
@pytest.mark.physics
@pytest.mark.reference
class TestAgainstVallado2006VerificationData:
    """The V3 oracle for this module, and it did not have to be built.

    **What it is:** AIAA 2006-6753 [1] is the paper that re-specified SGP4 in
    2006 after decades of subtly divergent implementations, and it shipped with
    an official reference: a set of test TLEs (``SGP4-VER.TLE``) and the exact
    position/velocity output of Vallado's own C++ implementation for each one
    (``tcppver.out``). Both files are installed as *data files inside the
    `sgp4` package itself* — not fetched, not generated, not committed to this
    repository's own `tests/golden/data/` — because `sgp4` already has to be a
    core dependency for `propagate_tle` to exist at all, so this data arrives
    for free the day that dependency was added. `tests/golden/README.md`
    documents the general rule this satisfies: an in-process V3 oracle need not
    be frozen to a file of its own once it is (1) already a core dependency,
    (2) deterministic, and (3) compared far looser than its own accuracy — all
    three hold here, the same way they hold for the DOP853 oracle in
    ``perturbations.py``.

    **Why the tolerance is so tight:** this is not two independent SGP4
    implementations agreeing — Vallado's C++ reference and this project's
    `Satrec.sgp4_array` call are, at the level that matters here, *the same
    theory evaluated twice*, so a modelling difference is not the thing being
    measured. What is being measured is text-file rounding: ``tcppver.out``
    prints positions to 8 decimal places (e.g. ``7022.46529266``), which is a
    resolution of 1e-8 km, or 10 micrometres — any 64-bit float rounded to that
    many digits can differ from the original by up to half that, 5e-9 km.

    **The number, measured across the four satellites below and every sample
    each one provides:** the worst position residual is 7.3e-9 km (7.3
    micrometres) and the worst velocity residual is 7.7e-10 km/s (0.77
    micrometres per second) — both consistent with print-resolution rounding,
    not with a physical or algorithmic difference. The tolerances below,
    :data:`POSITION_TOLERANCE_KM` and :data:`VELOCITY_TOLERANCE_KM_S`, are set
    an order of magnitude above each measurement: tight enough that a wrong
    gravity constant, a transposed jd/fr split, or a shape bug would fail by
    many orders of magnitude, loose enough not to be re-litigating the ASCII
    file's own printed precision.
    """

    POSITION_TOLERANCE_KM = 1e-7
    """~14x the worst measured residual, 7.3e-9 km. See the class docstring."""

    VELOCITY_TOLERANCE_KM_S = 1e-8
    """~13x the worst measured residual, 7.7e-10 km/s. See the class docstring."""

    TLE_PAIRS = _parse_verification_tle_pairs(_TLE_FILE) if _HAS_VALLADO_DATA else {}
    TCPPVER_BLOCKS = _parse_tcppver(_TCPPVER_FILE) if _HAS_VALLADO_DATA else {}

    # Four regimes out of the ~20 satellites the file carries, chosen to span
    # what a real constellation study would encounter, per each entry's own
    # comment in SGP4-VER.TLE:
    SATELLITES = (
        (5, "leo_low_drag"),  # "TEME example", the file's baseline case.
        (6251, "leo_moderate_drag"),  # "near earth normal drag equation".
        (8195, "molniya_high_eccentricity"),  # e = 0.6877146, 12h resonant.
        (28872, "decaying_high_drag"),  # decayed 2005-11-29, perigee -51 km.
    )

    @pytest.mark.parametrize(
        ("satnum", "label"), SATELLITES, ids=[label for _, label in SATELLITES]
    )
    def test_position_and_velocity_match_the_official_reference(
        self, satnum: int, label: str
    ) -> None:
        line1, line2 = self.TLE_PAIRS[satnum]
        reference = self.TCPPVER_BLOCKS[satnum]
        assert reference.shape[0] > 3, f"fixture parsing produced too few rows for {satnum}"

        satrec = parse_tle(line1, line2)
        t_s = reference[:, 0] * 60.0

        trajectory = propagate_tle(satrec, t_s)

        position_error_km = np.linalg.norm(trajectory.r_km[0] - reference[:, 1:4], axis=-1)
        velocity_error_km_s = np.linalg.norm(trajectory.v_km_s[0] - reference[:, 4:7], axis=-1)

        assert float(position_error_km.max()) < self.POSITION_TOLERANCE_KM
        assert float(velocity_error_km_s.max()) < self.VELOCITY_TOLERANCE_KM_S
