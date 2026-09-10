# Reference data and what "verified" is allowed to mean

Four levels of verification. They are not interchangeable, and conflating them is
the mistake this file exists to prevent.

| Level | What it is | What it proves | Runs in CI |
|---|---|---|---|
| **V1 — invariants** | Property-based and analytic self-consistency: round trips, conservation laws, limits, symmetries. No external data. | Internal consistency. A module cannot contradict itself. | yes |
| **V2 — published values** | Numbers taken from a citable source, hand-entered with the citation next to them. | **Absolute correctness**, at the sampled points. The only level that does. | yes |
| **V3 — independent implementation** | Values generated once from an unrelated implementation (astropy/ERFA, the `sgp4` package's own verification data, GMAT, Orekit), frozen into `data/` with a manifest. | Correctness over a broad range, and the size of any modelling difference. | yes (against the frozen file) |
| **V4 — regression** | A frozen snapshot of *QuOSS's own* output. | That a refactor did not change the numbers. **Nothing about whether they are right.** | yes |

## The rule that matters

**V4 is not validation.** A frozen snapshot of our own output proves only that we
are consistently doing whatever we are doing. It is valuable — it catches
refactor damage cheaply — but a V4 test passing is never grounds for claiming a
number is correct. Anything reported as validated must trace to V2 or V3.

## SimulCTTC is not an oracle

The earlier codebase (`../SimulCTTC`) is **not** used as a reference, and no test
asserts against it. It was never validated, and reading it turned up defects that
freezing its output would have canonised — geocentric latitude returned as
geodetic, ground stations placed on a sphere (up to ~21 km out), a J3 "secular"
rate for a harmonic that has no first-order secular term, and an epoch that
silently defaulted to the wall clock.

It remains useful as a **differential check**: a script may report where old and
new disagree, because a discrepancy is a lead worth chasing in either direction.
Such a report is informational and must never gate CI.

## Layout

```
tests/golden/
├── README.md                          # this file
├── data/                              # frozen reference values, committed
│   └── frames_reference.json
└── generators/                        # scripts that produce data/, run by hand
    └── gen_frames_reference.py
```

Generators are **excluded from pytest collection** (see `addopts` in
`pyproject.toml`) because they import dependencies that the test environment
deliberately does not have.

## Rules for a reference file

1. **Committed.** CI never generates it and never reaches the network.
2. **Carries a manifest**: what produced it, which versions, and any caveat that
   affects how it should be read.
3. **Regenerated only on purpose.** A reference file that changes as a side
   effect of a dependency upgrade has stopped being a reference. If regenerating
   changes a value, that is a finding to explain before committing, not a diff to
   accept.
4. **Its generator does not import `quoss`.** An oracle that imports the code
   under test is a mirror.
5. **Inputs are written out explicitly**, not generated from a range, so that
   which cases are covered is readable and reviewable.

## When a V3 oracle need not be frozen

The rules above are about reference *files*. An oracle that runs in-process is
still V3 if it is an independent implementation, and freezing it buys nothing
when all three of these hold:

1. it is already a **core dependency**, so CI installs it anyway and stays offline;
2. it is **deterministic**, with its accuracy set by an explicit tolerance
   argument rather than by internal defaults;
3. the comparison is made **far looser than that tolerance**, so a version bump
   cannot move the result.

`tests/orbits/test_kepler.py::TestAgainstNumericalIntegration` is the case:
SciPy's `DOP853` integrating the two-body equation of motion, at `rtol=1e-13`,
compared at 1 m. What a frozen file protects against — a reference that changes
silently — does not apply. Anything that fails one of the three goes in `data/`
with a manifest, like the astropy set does.

## Tolerances

A tolerance is an argument, not a number. Each one is justified at its assertion,
and derived from a physical bound wherever possible rather than from whatever
the code currently produces. `test_frames.py::TestFrameErrorBudget` is the
pattern to copy: it does not assert a flat "close enough", it separates the
UT1 approximation from polar motion and holds each to a bound computed from the
size of the effect.

## Gaps, stated rather than filled

Reference values that would be worth having and are **not** in `data/` yet:

- **Vallado worked examples** (*Fundamentals of Astrodynamics and Applications*,
  4th ed.): GMST and site look angles are still missing. **Kepler's equation and
  COE↔RV are done** — Examples 2-1, 2-5 and 2-6, transcribed with their page
  numbers into `tests/orbits/test_kepler.py`. They live next to their citation
  rather than in `data/` because that is what a V2 value is: a number a reader
  can check against the book without running a generator.

  Transcribing them found three things worth reading before adding more: the
  book's printed inclination in Example 2-5 disagrees with its own state vector
  by 0.00087°; Examples 2-5 and 2-6 are *not* a round trip; and the argument of
  latitude `u = 145.60549°` printed on p. 116 is a **confirmed double erratum**
  in the book itself (a digit transposition `|r|: 57→67` on the same page, and
  then a printed result that does not follow even from those wrong operands).
  The correct value `u = 145.720087°` is now asserted via both `ω + ν` and the
  vector formula. See [ADR 0003](../../docs/adr/0003-orbital-elements.md)
  §“Lo que la verificación V2 encontró”. The lesson generalises: transcribe
  the *inputs* and the *outputs* separately, and assert the intermediate stages
  the book prints, because that is what localises a disagreement instead of just
  registering one.
- **SGP4 verification data**: `SGP4-VER.TLE` and `tcppver.out`, the official
  output from Vallado et al., AIAA 2006-6753. Both ship inside the `sgp4` PyPI
  package, so this arrived for free with `orbits/tle.py`, and it is **done**:
  `tests/orbits/test_tle.py::TestAgainstVallado2006VerificationData` parses
  both files directly out of the installed package and propagates
  `parse_tle`/`propagate_tle` against four satellites chosen to span distinct
  regimes — low-drag LEO, moderate-drag LEO, a high-eccentricity Molniya, and
  one that decays within the file's own test window — rather than all ~20 the
  file carries. Same pattern as the J2 DOP853 oracle below: an in-process V3
  oracle that is not frozen to a file of its own, because `sgp4` is already a
  core dependency, the comparison is deterministic, and the tolerance (1e-7 km
  position, 1e-8 km/s velocity) sits an order of magnitude above the ~7e-9 km /
  ~7e-10 km/s residual actually measured — itself consistent with
  `tcppver.out`'s own printed precision (8 decimal digits, i.e. 1e-8 km) rather
  than with any modelling difference, since both sides of the comparison run
  the same `sgp4` theory.
- **GMAT or Orekit** cross-checks for look angles, for `orbits/geometry.py`.

  For the **J2 secular rates** the gap is closed differently, and the reason is
  worth reading: `orbits/perturbations.py` carries its own in-process V3 oracle
  (DOP853 on the exact zonal force, under the three conditions above), and it
  proves more than a frozen table would. The residual against it is shown to be
  *exactly proportional to J2* — the ratio residual/J2 holds to four significant
  figures while J2 is scaled down 8x — which separates "the theory is truncated
  at first order" from "a coefficient is mistyped". A table of numbers from GMAT
  could only have bounded the disagreement, not attributed it.

  An external oracle becomes worth having again the day **second-order** (`J2²`,
  `J4`) rates are attempted. Those need mean elements, and nothing QuOSS runs
  today can produce them — see
  [ADR 0004](../../docs/adr/0004-zonal-perturbations.md).
