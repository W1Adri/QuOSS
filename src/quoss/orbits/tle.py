"""TLE parsing and SGP4 propagation.

A TLE ("Two-Line Element set") is how orbits are published in practice: two
69-character lines of text, fitted by a ground-tracking pipeline so that a
specific analytic theory — SGP4 — reproduces the tracked object closely near the
epoch. This module is the boundary between that world and this project's: it
parses the two lines and propagates them, using the ``sgp4`` package from PyPI
rather than reimplementing the theory, per ``notes/ROADMAP.md`` 2.1.5.

Why this does not go through :func:`~quoss.orbits.propagator.propagate`
-------------------------------------------------------------------------
:func:`~quoss.orbits.propagator.propagate` takes
:class:`~quoss.orbits.kepler.ClassicalElements` and a model to run on them.
SGP4 is not such a model: it does not accept osculating elements and does not
produce them as an intermediate step available to a caller. Handed a TLE's own
mean elements (Brouwer theory with the Kozai correction, referred to WGS-72),
it returns a **state vector in TEME** directly — the short-period terms that
:mod:`quoss.orbits.kepler` cannot yet undo (``docs/adr/0003-orbital-elements.md``
on Brouwer-Lyddane; ``docs/adr/0006-osculating-vs-mean-elements.md`` on why
mixing mean and osculating elements costs kilometres) are folded in *inside*
SGP4, not exposed. So there is no `ClassicalElements` this module could
correctly build from a TLE, and it does not try: :func:`propagate_tle` takes a
parsed record and elapsed seconds, and returns a
:class:`~quoss.orbits.propagator.Trajectory` directly, the same output type
:func:`~quoss.orbits.propagator.propagate` produces, so
:mod:`quoss.orbits.geometry` downstream does not care which module a trajectory
came from.

Two things ``sgp4`` gets wrong by omission, verified rather than assumed
--------------------------------------------------------------------------
``sgp4.api.Satrec.twoline2rv`` is the library's own parser, and this module
calls it — but it skips two checks a caller would reasonably assume it makes,
confirmed against the installed package before writing this docstring:

1. **It does not verify the TLE checksum.** Column 69 of each line is a digit:
   the sum of every digit in columns 1-68, counting ``'-'`` as 1 and any other
   character as 0, modulo 10. Corrupting the last character of a valid ISS line
   (``...0  9996`` -> ``...0  9990``) and calling ``twoline2rv`` on the result
   is accepted without complaint — the corrupted line parses exactly as if it
   were sound.
2. **Malformed input does not raise.** ``Satrec.twoline2rv("garbage", "more
   garbage")`` returns a record with ``satnum=0`` and ``error=2`` set — and
   ``.error`` is a field nobody reads unless they know to ask for it. Left
   unchecked, a caller gets a `Satrec` that looks like an object and is not one.

Both are exactly the failure mode ``README.md`` calls "degrading in silence",
now sitting in a third-party dependency instead of this project's own code. So
:func:`parse_tle` does three things ``twoline2rv`` does not: validates line
length and prefix, recomputes and compares the checksum, and checks
``satrec.error`` after the call — all three raising
:class:`~quoss.core.errors.DomainError` rather than returning a record that
looks fine and is not.

WGS-72, explicitly, never WGS-84
---------------------------------
A TLE's mean elements are fitted **against WGS-72** — that is part of the SGP4
specification, not a modelling choice available to whoever reads the TLE later.
``Satrec.twoline2rv(line1, line2)`` already defaults to WGS-72 (confirmed:
``mu == 398600.8`` km^3/s^2 either way, against ``398600.5`` for WGS-84), but
:func:`parse_tle` passes ``sgp4.api.WGS72`` explicitly anyway, for the same
reason :data:`quoss.orbits.perturbations.WGS72_ZONAL` exists as a distinct
object from :data:`quoss.orbits.perturbations.EGM96_ZONAL`: three different
Earth models with three different radii and mu's is a mistake that stays quiet
until the numbers are compared, and :data:`quoss.core.constants.WGS72_MU_KM3_S2`
already carries the note "not the WGS-84 value" for exactly this reason.

The epoch is not a parameter
-----------------------------
:func:`~quoss.orbits.propagator.propagate` takes a
:class:`~quoss.core.types.TimeGrid` supplied by the caller, because
``ClassicalElements`` carry no epoch of their own. A parsed TLE is different:
its epoch (``satrec.jdsatepoch + satrec.jdsatepochF``) is fixed the moment it is
parsed, and letting a caller hand :func:`propagate_tle` a `TimeGrid` with some
other ``epoch_jd`` would build a :class:`~quoss.orbits.propagator.Trajectory`
that misreports what instant its elements are from — the same kind of
irrepresentable state ``docs/adr/0002-frames-and-time-scales.md`` closes for a
frame that rotates. So :func:`propagate_tle` takes elapsed seconds, ``t_s``,
and builds the ``TimeGrid`` itself from the record's own epoch; there is no
other epoch it could mean.

Splitting Julian date into (whole, fraction) to keep precision
------------------------------------------------------------------
``Satrec.sgp4_array`` wants time as a pair of arrays, ``jd`` and ``fr`` — whole
Julian date and day fraction — rather than one array of Julian dates, and that
split exists for precision: ``sgp4.conveniences`` documents that the fractional
part "can, unlike the first float, be accurate down to very small fractions of
a second" *because* it stays small. Computing ``fr`` as
``satrec.jdsatepochF + t_s / 86400`` without folding whole days back into ``jd``
would let ``fr`` grow past 1.0 for anything more than a day out, defeating the
reason the split exists. Instead, for every sample::

    whole_days = floor(satrec.jdsatepochF + t_s / 86400)
    jd = satrec.jdsatepoch + whole_days
    fr = satrec.jdsatepochF + t_s / 86400 - whole_days

so ``fr`` stays in ``[0, 1)`` no matter how many days ``t_s`` reaches.

Verification
------------
The ``sgp4`` package ships, inside its own installed directory, the official
AIAA 2006-6753 verification data (Vallado, Crawford, Hujsak, Kelso,
"Revisiting Spacetrack Report #3", 2006): ``SGP4-VER.TLE`` and ``tcppver.out``,
the reference C++ implementation's output for a spread of regimes (near-circular
LEO, high-drag decay, Molniya-class high eccentricity). See
``tests/orbits/test_tle.py`` for the V3 comparison and
``tests/golden/README.md`` for why data bundled with a core dependency does not
need freezing to a file of its own — the same argument already made there for
the DOP853 oracle in :mod:`quoss.orbits.perturbations`.

References
----------
.. [1] Vallado, Crawford, Hujsak, Kelso, "Revisiting Spacetrack Report #3",
       AIAA 2006-6753, 2006. The SGP4 specification and its official
       verification data.
.. [2] ``docs/adr/0007-tle-and-sgp4-propagation.md`` — the decisions taken here.
"""

from __future__ import annotations

import numpy as np
from sgp4.api import SGP4_ERRORS, WGS72, Satrec

from quoss.core.errors import DomainError
from quoss.core.types import FloatArray, TimeGrid
from quoss.orbits.frames import Frame
from quoss.orbits.propagator import PropagationMethod, Trajectory

__all__ = [
    "parse_tle",
    "propagate_tle",
    "tle_epoch_jd",
]

_TLE_LINE_LENGTH = 69


def _tle_checksum(line: str) -> int:
    """Compute the Vallado TLE checksum: digits sum mod 10, '-' counts as 1.

    Parameters
    ----------
    line : str
        A TLE line, at least 68 characters (the checksum column itself, 69, is
        not part of the sum).

    Returns
    -------
    int
        The checksum, 0-9.
    """
    total = 0
    for char in line[:68]:
        if char.isdigit():
            total += int(char)
        elif char == "-":
            total += 1
    return total % 10


def _validate_tle_line(line: str, line_number: int, expected_prefix: str) -> None:
    """Check length, prefix and checksum of one TLE line.

    Parameters
    ----------
    line : str
        The line as given by the caller, with trailing whitespace stripped
        before this is called.
    line_number : int
        1 or 2, for the error message.
    expected_prefix : str
        ``"1 "`` or ``"2 "``.

    Raises
    ------
    DomainError
        If the length is wrong, the line does not start with its expected
        line-number field, or the printed checksum does not match the one
        computed from columns 1-68. ``Satrec.twoline2rv`` checks none of this —
        see the module docstring for the corrupted-line and garbage-input cases
        that motivate checking it here instead.
    """
    if len(line) != _TLE_LINE_LENGTH:
        raise DomainError(
            f"TLE line {line_number} is {len(line)} characters, expected "
            f"{_TLE_LINE_LENGTH}: {line!r}."
        )
    if not line.startswith(expected_prefix):
        raise DomainError(
            f"TLE line {line_number} must start with {expected_prefix!r}, got "
            f"{line[:2]!r}: {line!r}."
        )
    printed = line[68]
    if not printed.isdigit():
        raise DomainError(
            f"TLE line {line_number} column 69 must be a checksum digit, got {printed!r}: {line!r}."
        )
    computed = _tle_checksum(line)
    if int(printed) != computed:
        raise DomainError(
            f"TLE line {line_number} fails its checksum: column 69 prints "
            f"{printed}, but the digits in columns 1-68 sum to {computed} mod 10. "
            f"sgp4.api.Satrec.twoline2rv does not check this, so a corrupted line "
            f"would otherwise parse without complaint."
        )


def parse_tle(line1: str, line2: str) -> Satrec:
    """Parse two TLE lines into an ``sgp4`` record, checking what ``sgp4`` skips.

    Parameters
    ----------
    line1, line2 : str
        The two 69-character TLE lines, in order. Trailing whitespace (a
        trailing newline from a file read, for instance) is stripped before
        validation; internal spacing is fixed-column and must match the TLE
        format exactly.

    Returns
    -------
    Satrec
        The ``sgp4`` record, initialised against WGS-72 (see the module
        docstring for why that is explicit rather than left to the library
        default). Pass this to :func:`propagate_tle`.

    Raises
    ------
    DomainError
        If either line is not 69 characters, does not start with its line
        number, fails its checksum, or if ``sgp4`` itself reports an
        initialisation error (``satrec.error != 0`` — the garbage-input case in
        the module docstring, where ``twoline2rv`` sets this and does not
        raise).

    Examples
    --------
    >>> line1 = "1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996"
    >>> line2 = "2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781"
    >>> sat = parse_tle(line1, line2)
    >>> sat.satnum
    25544
    >>> sat.mu
    398600.8
    """
    stripped1 = line1.rstrip()
    stripped2 = line2.rstrip()
    _validate_tle_line(stripped1, 1, "1 ")
    _validate_tle_line(stripped2, 2, "2 ")

    satrec = Satrec.twoline2rv(stripped1, stripped2, WGS72)
    if satrec.error:
        message = SGP4_ERRORS.get(satrec.error, f"error code {satrec.error}")
        raise DomainError(
            f"sgp4 could not initialise from this TLE: {message}. Both lines pass "
            f"their checksum, so the fields themselves are what SGP4 rejects."
        )
    return satrec


def tle_epoch_jd(satrec: Satrec) -> float:
    """Return the TLE's epoch as a single Julian date (UTC).

    Parameters
    ----------
    satrec : Satrec
        A record from :func:`parse_tle`.

    Returns
    -------
    float
        ``satrec.jdsatepoch + satrec.jdsatepochF``. Split in two by ``sgp4``
        itself for precision (see the module docstring); summed here because
        this value is only ever used as ``TimeGrid.epoch_jd``, which takes one
        float, not the pair.
    """
    return float(satrec.jdsatepoch + satrec.jdsatepochF)


def propagate_tle(satrec: Satrec, t_s: FloatArray) -> Trajectory:
    """Propagate a parsed TLE with SGP4, at seconds elapsed from its own epoch.

    Parameters
    ----------
    satrec : Satrec
        A record from :func:`parse_tle`.
    t_s : FloatArray
        Elapsed seconds from the TLE's epoch. May be negative (before the
        epoch), need not include zero, and need not be uniformly spaced — the
        same freedom :class:`~quoss.core.types.TimeGrid` grants everywhere
        else, since a TLE's epoch typically falls in the middle of the window
        someone actually wants.

    Returns
    -------
    Trajectory
        Positions and velocities of shape ``(1, n, 3)`` in
        :attr:`~quoss.orbits.frames.Frame.TEME`, with
        :attr:`~quoss.orbits.propagator.PropagationMethod.SGP4` as the method
        and a :class:`~quoss.core.types.TimeGrid` whose ``epoch_jd`` is
        :func:`tle_epoch_jd` — never a grid the caller supplied, since the TLE's
        epoch is the only one these elements could be from (see the module
        docstring).

    Raises
    ------
    DomainError
        If ``satrec`` is not a `Satrec`, if ``t_s`` fails the same checks
        :class:`~quoss.core.types.TimeGrid` applies everywhere (not 1-D, empty,
        non-finite, or not strictly increasing), or if SGP4 fails at some
        sample — named by its index, its ``t_s`` value, and the message from
        ``sgp4.api.SGP4_ERRORS``.

    Examples
    --------
    >>> line1 = "1 25544U 98067A   20029.91700964  .00001177  00000-0  29466-4 0  9996"
    >>> line2 = "2 25544  51.6446  29.6162 0004826 145.9021 214.2494 15.49332174212781"
    >>> sat = parse_tle(line1, line2)
    >>> traj = propagate_tle(sat, np.array([0.0, 60.0, 120.0]))
    >>> traj.r_km.shape
    (1, 3, 3)
    >>> traj.frame is Frame.TEME
    True
    """
    if not isinstance(satrec, Satrec):
        raise DomainError(
            f"propagate_tle expects a Satrec from parse_tle, got {type(satrec).__name__}."
        )

    grid = TimeGrid(epoch_jd=tle_epoch_jd(satrec), t_s=np.asarray(t_s, dtype=np.float64))

    elapsed_days = grid.t_s / 86400.0
    whole_days = np.floor(satrec.jdsatepochF + elapsed_days)
    jd = satrec.jdsatepoch + whole_days
    fr = satrec.jdsatepochF + elapsed_days - whole_days

    error, r_km, v_km_s = satrec.sgp4_array(jd, fr)
    bad = np.flatnonzero(error)
    if bad.size:
        first = int(bad[0])
        code = int(error[first])
        message = SGP4_ERRORS.get(code, f"error code {code}")
        raise DomainError(
            f"SGP4 failed at sample {first} of {grid.n} (t_s={grid.t_s[first]!r}): {message}."
        )

    return Trajectory(
        r_km=r_km.reshape(1, grid.n, 3),
        v_km_s=v_km_s.reshape(1, grid.n, 3),
        grid=grid,
        frame=Frame.TEME,
        method=PropagationMethod.SGP4,
    )
