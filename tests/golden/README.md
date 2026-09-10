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

### Channel and QKD (stage 2.2–2.3)

These are gaps in the *sources*, not just in the data files, and they are the
reason [ADR 0009](../../docs/adr/0009-citation-policy.md) exists. The rule there
is that a citation is a document somebody opened; what follows is what could not
be opened, written down so nobody has to rediscover it.

- **Andrews & Phillips, *Laser Beam Propagation through Random Media* (2nd ed.,
  SPIE PM152, 2005): no equation numbers.** The canonical turbulence reference is
  paywalled, has no accessible full text, and no secondary source citing its
  equations by number was located. The previous codebase cites it by number
  repeatedly (Eq. 12.46, 12.15, 12.12, 9.46–9.47); **none of those was
  verifiable**, so none is inherited. ITU-R P.1621-2 and P.1622 are used instead:
  free, numbered, and tabulated.
- **Gamma-gamma shape parameters α and β.** The source is Al-Habash, Andrews &
  Phillips, *Opt. Eng.* 40(8):1554 (2001), paywalled and unverified. The relation
  `σ²_I = (1+1/α)(1+1/β) − 1` is **not verified against a source**.
- **Beckmann/Hoyt pointing model with non-zero boresight** (a systematic aim
  offset rather than zero-mean jitter): no verified source. `channel/pointing.py`
  therefore models **zero-mean jitter only**, and says so: a *known* boresight
  offset can go through `pointing_transmittance` as a deterministic
  displacement, which is exact, but the fading *distribution* under a boresight
  offset is absent rather than approximated.
- **Farid & Hranilovic 2007 is openable, at the authors' copy.** The version of
  record (*J. Lightwave Technol.* 25(7):1702, via IEEE or Optica) is paywalled,
  but the authors host the accepted manuscript at
  `ece.mcmaster.ca/~hranilovic/publications/articles/07/jlt06IEEEFinal.pdf`, and
  that is where equations (7)-(11) and Table I were read. Recorded because
  ADR 0009 requires knowing *which* copy a citation was checked against: if that
  URL rots, the citations in `channel/pointing.py` become unverified again, and
  the honest response would be to say so rather than to keep them.
- **Table I of Farid & Hranilovic is not reproducible.** It prints the NMSE
  between their exact equation (8) and their closed form (9) at six values of
  `W/a`, but states neither the averaging range over the displacement nor the
  normalisation. No plausible convention reproduces the printed values —
  attempts land 100 to 1000 times lower — and the last two entries (0.159e-3 and
  0.153e-3) barely differ, which looks like a floor in their own computation
  rather than a trend. What `tests/channel/test_pointing.py` asserts instead is
  the *claim* the table supports: the error shrinks monotonically as `W/a` grows,
  measured against equation (8) integrated numerically (46 % at `W/a` = 2 down
  to 0.2 % at 12).
- **The pointing model's own validity condition fails for the reference
  system's largest telescope**, and that is reported rather than smoothed over.
  Farid & Hranilovic state "good agreement when `w_z/a > 6`"; a 2.3 m telescope
  at 600 km — the configuration Ntanos et al. report their best link budget for
  — gives `W/a = 3.4`. `equivalent_beam_radius_m` records a WARNING there.
  Measured against their exact integral, the closed form is still within 0.36 %
  over the displacements a 0.75 µrad jitter produces, and only diverges beyond
  about two beam radii of offset (8 %) — reached with probability ~1e-17 at that
  jitter. So the warning carries the condition *and* the measurement, because
  "outside the published range" and "wrong" are different claims.
- **`A_0 = erf(v)²` is itself an approximation**, and QuOSS does not use it.
  Farid & Hranilovic's zero-offset coefficient is a Gaussian-form fit chosen so
  that the pointing dependence collapses into one exponential; the exact value is
  `1 − exp(−2a²/W²)`, which is what `beam.geometric_transmittance` returns and
  what their own equation (8) integrates to. The two differ by −4.2e-4 (0.0018 dB)
  at the reference geometry and by −3.6e-3 at the 2.3 m station.
- **Sky radiance at 785 nm and 810 nm.** ITU-R P.1621-2 Table 1 tabulates 530,
  850, 965, 1060 and 1500 nm. Interpolating between them and presenting the
  result as a published value would be inventing a V2.
- **Typical SPAD detector parameters.** No free authoritative table was located.
  What is used instead are values that *are* published and verified: Ntanos et
  al. 2021 §4.1 (SNSPD: η 85 %, 300 cps, 50 ps jitter, 30 ns dead time) and Lim
  et al. 2014 §Evaluation (InGaAs: η 10 %, p_dc 6e-7, p_ap 4e-2). Closing this
  properly means reading the Excelitas and ID Quantique datasheets, which are
  public, and transcribing them with their revision.
- **Bufton wind coefficients disagree between sources.** ITU-R P.1621-2 Eq. (5)
  gives `v_rms = sqrt(v_g² + 33.11·v_g + 360.31)`; the form usually attributed to
  A&P uses 30.69 and 348.91. Both yield ≈21 m/s but from a different `v_g`
  (2.3 vs 2.8 m/s). ITU is chosen because it can be opened; the other is recorded
  so the discrepancy is not rediscovered from scratch.
- **Ntanos et al. 2021 as an end-to-end V2, with its caveat.** It is the best
  candidate for full reproduction (declared parameters, numbered equations,
  published result), which is exactly why what does not add up must be written
  down: its Table 1 is **not reproducible** from the paper's own disclosed
  parameters (internally inconsistent by ~5.5×), and its `q = 2/5` is
  inconsistent with its own Eq. A1 given the stated 4:1:16 intensity ratio
  (2/21 is what follows). What *does* reproduce are the inter-station ratios
  (published 1 : 0.28 : 0.084). Tests therefore assert the **shape and the
  ratios**, not the absolute figure, and say so at the assertion.

  **Third thing that does not add up, found while writing `channel/beam.py`:**
  its Eq. (5) prints the transmitter gain as `G_t = (8/w_0)²`. The product
  `G_t·G_r·L_fsl` of its Eqs. (3) and (5) *is* the geometric coupling, and with
  `G_t = 8/w_0²` — the standard optical-antenna form — that product reproduces
  the Gaussian truncation integral `1 − exp(−D_r²/2W²)` in its small-aperture
  limit to the last digit. As printed it is **8× larger, i.e. 9.03 dB
  optimistic**, and at the paper's own largest station (2.3 m at 600 km) it
  returns a transmittance of **1.36** — more light collected than transmitted.
  QuOSS uses the energy-conserving form;
  `tests/channel/test_beam.py::TestPublishedGainProduct` asserts both the
  identity and the factor of 8, so neither reading can be adopted by accident.
- **No V3 oracle for the beam geometry.** `channel/beam.py` is closed against
  V2 (Ntanos et al. Eqs. (3)-(6), ITU-R P.1622 Eqs. (11a)/(11b)) and V1
  invariants only. A frozen table from an independent FSO link-budget tool would
  be worth having, and none was located that states its beam-waist convention —
  which is the one thing that would have to match for the comparison to mean
  anything (see the next entry).
- **The beam-waist convention is a choice, not a citation.** Identifying the
  Gaussian `1/e²` waist radius with the transmitter's aperture *radius*
  (`w_t = D_T/2`) is what Ntanos et al. Eq. (6) implies, and it is what QuOSS
  uses — but it means the transmitting aperture clips 13.5 % of its own beam
  (`1 − exp(−2)`), a flat **0.63 dB** that `beam.py` does not apply and
  `link_budget.py` will. Optimum-truncation conventions (`w_t = D_T/2.2` and
  similar) differ by tens of percent in on-axis intensity, so any external
  comparison has to declare which one it uses.
- **Turbulence-induced beam spreading is not modelled**, on the source's own
  authority rather than by omission: ITU-R P.1622 §4.4 states it "is typically
  very small with respect to divergence and does not account for an appreciable
  loss of signal in either the Earth-to-space or space-to-Earth directions".
  Recorded here because "the beam radius is the vacuum-diffraction one" is a
  modelling decision that would otherwise look like a forgotten term.
- **P.1622's own two tilt coefficients disagree by 1.485× and it does not say
  why.** Eq. (10) gives the angle-of-arrival variance as
  `2.914·μ·D_R^(−1/3)/sin θ`; squaring the 2.08 of Eq. (11b) gives
  `4.326·μ·D_T^(−1/3)/sin θ` — the same shape, a different constant. The
  plausible explanation (Eq. (10) is a plane wave filling the aperture, Eq. (11b)
  a narrow beam leaving it) is **not stated in the recommendation**, so both are
  transcribed as printed and neither is used to "correct" the other.
- **SatQuMA as an independent V3 oracle for finite-key** (github.com/cnqo-qcomms/SatQuMA,
  **MIT licence**, pure Python, implements Lim et al. 2014 with its own numbered
  equations in arXiv:2109.01686). Not yet frozen into `data/`. It fails condition
  1 of “when a V3 oracle need not be frozen” — it is not a core dependency — so
  it belongs in `data/` with a manifest, generated by hand via the `reference`
  group. Note that SatQuMA uses **Chernoff** bounds (Yin et al., *Sci. Rep.*
  10:14312 (2020), Eqs. 2.9a/2.9b) where Lim et al. use **Hoeffding**: comparing
  without knowing which convention each side uses is chasing a ghost.

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
