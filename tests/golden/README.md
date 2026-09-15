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

**A literal is a golden across machines, and it needs a bound of its own.**
Floating point is deterministic within a platform, not across them: IEEE 754
requires correct rounding of `+ - * / sqrt` and not of `exp`, `log`, `pow` or
`erf`. So four rules, all measured in
`tests/e2e/test_reference_scenarios.py` (module docstring):

1. **Route against route, in one process:** `==`. The same call returns the
   same doubles.
2. **A hand-written literal against a computation that passes through an
   elementary function:** a tolerance derived from the number of such calls,
   the cancellations upstream, the sensitivity of the result and the length of
   any sum — never `==`, and never a round `rel=1e-9`. On the reference day
   that is 8.15e-13 relative; the second machine that found the problem was 9
   ULP away.
3. **An integer that is `floor` of such a computation:** `==` only with a test
   showing the unfloored value is further from an integer than the derived
   error (0.039 bits against 6e-7 on the reference day).
4. **A doctest:** print at most twelve significant digits of anything that went
   through an elementary function. `10 ** 4.5` lies 0.29 ULP from the double one
   machine returns, so a library within 0.71 ULP may print a different
   seventeenth digit.

CI runs the suite on macOS arm64 and on numpy 2.0 as well, because a golden
verified on one machine is a photograph of that machine.

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

  **Now measured, which is what makes the gap actionable**
  (`tests/channel/test_background.py::TestTheInterpolationGap`): the two
  defensible rules — a power law in log-log, and linear in λ — differ by
  **0.48 dB at 785 nm**, and the real accuracy is *worse than that spread*.
  Leave-one-out on the table's own interior points misses by **16 % to 27 %**
  with the rule in use (2 % to 32 % with the linear one), because the 940 nm
  water-vapour band falls inside the grid and the normal-sunshine column is not
  even monotone across it (25.12 at 965 nm, 25.32 at 1060 nm). The table has **no
  interior point between 530 and 850 nm**, so the error *at* 785 nm cannot be
  measured with it at all, only bounded by analogy — and the test says so rather
  than quoting the smaller number. `channel/background.py` therefore splits the
  two: `tabulated_sky_radiance_w_m2_um_sr` refuses anything off the grid, and
  `interpolated_sky_radiance_w_m2_um_sr` records a `DEGRADED` carrying the other
  rule's answer.
- **Earth radiance: Table 1 promises it in its title and prints none.** The title
  reads "Radiance, H (W/m²/µm/sr), of the sky **and Earth** for several
  frequencies" and only the three sky columns are there, though §3.1 does note
  that "spacecraft pointed at the Earth will also encounter noise from sunlight
  reflected from the Earth's surface". So there is **no uplink background** in
  `channel/background.py`: neither source publishes a radiance for a sunlit
  Earth, and Ntanos et al. model the downlink only.
- **The two sources disagree by a factor of ten about the night sky.** ITU-R
  P.1621-2 §3.1 gives "(1-2)·10⁻⁶ W/m²/µm/sr for most frequencies of interest";
  Ntanos et al. §4.2.2 give 1.5e-5 at 1550 nm for a moonless clear night. Same
  treatment as the Bufton coefficients — both exposed as named constants, neither
  a default — plus a measurement of what the conflict costs: against the 300 cps
  dark-count rate of the same paper's detectors, 1.24× in total noise on a 0.75 m
  telescope and **2.83×** on a 2.3 m one. It needs resolving only for the large
  telescope, which is the one that carries their best budget.
- **Ntanos et al.'s "10 kcps at most" under a full moon is not reproducible.**
  Their own equation (19) with their own parameters gives 8.1 kcps at 0.75 m,
  24.4 kcps at 1.3 m and **76.4 kcps at 2.3 m**, and the sentence does not say
  which telescope; "at most" argues for the largest, which misses by 7.6×.
  Applying the loss chain the same section declares (3 dB filter insertion,
  2.65 dB receiver, 85 % efficiency) brings the 2.3 m station to 17.7 kcps, still
  1.8× above. Asserted as three candidate answers in `TestTheFullMoonClaim`
  rather than reproduced.
- **No published angular dependence of the sky radiance.** Table 1 is *zenith*
  radiance (its Figure 3 says so), and neither source gives an elevation, azimuth
  or sun-angle dependence — Ntanos et al. hold `H` constant across a whole pass
  and say so. The size of what that ignores: at 20° elevation the scattering path
  is 2.92 air masses, i.e. **4.66 dB** if the radiance simply followed the air
  mass. That scaling is *not* applied, and `TestModuleSurface` asserts the
  absence — no function in the module accepts an elevation — because a plausible
  air-mass correction would look exactly like physics.
- **The field-of-view convention is ambiguous in both sources**, in two
  independent ways, and both are priced: they give the FOV **in different units
  under the same name** (an angle in ITU-R equation (1), steradians in Ntanos et
  al. equation (19)), which is **41.05 dB** if the angle is handed to the
  steradian form; and neither says whether the angle is full or half, which is
  **6.02 dB**. ITU-R's own arithmetic settles it — `π θ²/4` is the small-angle
  solid angle of a cone of half-angle `θ/2`, so their `θ_r` is the full angle —
  and that is the convention QuOSS uses, spelled out in the parameter's name.
- **Typical SPAD detector parameters.** No free authoritative table was located.
  What is used instead are values that *are* published and verified: Ntanos et
  al. 2021 §4.1 (SNSPD: η 85 %, 300 cps, 50 ps jitter, 30 ns dead time, and "no
  after-pulsing effect") and Lim et al. 2014 §Evaluation (InGaAs: η 10 %,
  p_dc 6e-7, p_ap 4e-2). Closing this properly means reading the Excelitas and
  ID Quantique datasheets, which are public, and transcribing them with their
  revision.

  **Now measured, which is what makes the gap actionable.** These are not
  "typical values with a spread", they are **two instruments** 10 dB apart in
  efficiency and infinitely apart in afterpulsing, and the difference decides a
  design conclusion rather than a digit: narrowing the detection gate from 1 ns
  to 100 ps removes **10 dB** of noise with the nanowire and **0.22 dB** with
  the InGaAs diode, because afterpulses scale with the click rate and not with
  the gate. So `channel/background.py`'s "narrow the gate" is conditional, and
  the condition is which detector is in the receiver
  (`tests/channel/test_detector.py::TestGatingCannotTouchAfterpulsing`).

  **A sub-gap of units, inside it.** The two sources publish the dark count in
  different conventions — a rate (300 cps) and a probability per gate (6e-7) —
  and **Lim et al. state no gate width anywhere in the paper**, so the
  conversion cannot be done from their numbers. Read at Ntanos et al.'s 1 ns
  gate their value implies 600 cps, twice the nanowire; at 10 ns, 60 cps, half
  of it. And Ntanos et al.'s two detectors at 300 cps in their own 1 ns gate
  give **exactly** the 6e-7 per gate that Lim et al. publish per detector: a
  coincidence, asserted as one, so that nobody reads it as two independent
  sources agreeing.
- **Whether an afterpulse can itself afterpulse, and whether the dead time
  extends.** Two *model* gaps rather than value gaps, and neither source states
  either. Both are priced and both are derived thresholds rather than chosen
  ones: the one-afterpulse-per-click form of Lim et al. and the cascading
  geometric sum differ by `1/(1 - p_ap²)`, which is 0.16 % at the published
  4e-2 and 5 % at `p_ap = sqrt(1/21) = 0.2182`; the paralysable and
  non-paralysable dead-time laws differ by 5 % at `R·τ = 0.3554` (11.8 Mcps at
  30 ns) and their ceilings are `1/τ` = 33.3 Mcps and `1/(e·τ)` = 12.3 Mcps.
  The second has a consequence beyond accuracy: the paralysable law is **not
  invertible** past its maximum — 16.3 and 59.4 Mcps both report 10 Mcps — so
  `incident_count_rate_cps` exists for the non-paralysable model only, and the
  ambiguity is a missing function instead of a silent choice.
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

  **And one of its claims that does reproduce**, recorded because this list is
  otherwise a list of the ones that do not: its §4.2 argues that link
  attenuation keeps its detectors out of dead-time saturation. With its own
  100 MHz, 30 ns, µ = 0.5 and best-case 20 dB loss, 500 kcps enter a detector
  whose ceiling is 33.3 Mcps, for a loss of 1.5 % — true with two orders of
  magnitude of margin
  (`tests/channel/test_detector.py::TestAgainstNtanosEtAl::test_their_dead_time_claim_reproduces`).
- **Three published expressions that are first-order truncations of the same
  rule**, and the rule that replaces them: **means add, and the exponential
  happens once, at the end**. Lim et al.'s `D_k = 1 - (1 - 2 p_dc) exp(-η k)`
  (the two-detector dark-count union to first order), Lim et al.'s
  `R_k = D_k (1 + p_ap)` (a probability multiplied by a count factor), and
  Ntanos et al.'s `Y_0 = P_dc + P_noise` (a union computed as a sum). All three
  are excellent at their own operating points — 7e-12, 0.16 % and 1.2e-6
  respectively — and all three return something above 1 inside this project's
  daylight sweeps: 1.93, 1.006 and 3.42. `TestTheThreeLinearisations` asserts
  each departure, and `TestScalingLaws` asserts that the module's own form
  saturates at exactly 1 instead.
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
  (`1 − exp(−2)`), which `beam.py` does not apply and `link_budget.py` does.
  Optimum-truncation conventions (`w_t = D_T/2.2` and similar) differ by tens of
  percent in on-axis intensity, so any external comparison has to declare which
  one it uses.

  **This entry used to say the term was a flat 0.63 dB. It is 3.35 dB, and the
  correction is worth reading rather than just applying.** 0.63 dB is
  `1 − exp(−2)`, the light the rim blocks; it answers "how much never leaves"
  and it is not what the model gets wrong. On axis in the far field the
  *amplitude* integrates and the intensity is its square, so losing the tail of
  the amplitude integral costs twice while the power normalisation recovers it
  once. With `α = a/w_t`, what the untruncated far field overstates per unit
  **launched** power is

      η_trunc(α) = [1 − exp(−α²)]² / [1 − exp(−2α²)]

  which is 0.4621 at `α = 1`: **3.352 dB**. Three numbers exist and each has its
  own reference power — 0.632 dB against the laser, 3.352 dB against what left
  the aperture, 3.984 dB against the laser for both effects together — and they
  are one identity, not three measurements. `link_budget.py` applies the middle
  one, because a link budget's transmit power is the power out of the telescope.
  `TestTheTransmitterClipsItsOwnBeam` asserts the closed form against the
  diffraction integral evaluated by quadrature, and asserts all three numbers so
  that the other two cannot be adopted by accident.

  **What the correction changed downstream:** Ntanos et al.'s "as low as 20 dB"
  went from a 4.259 dB residual — which would have needed a vertical extinction
  of `L_zen = 0.375` at 1550 nm, an order of magnitude more than anything
  credible — to **0.906 dB**, i.e. `L_zen = 0.812`, ~~an ordinary clear-sky
  value~~. The missing decibels were in the transmitter, not in the atmosphere.
  That is a consistency and not a reproduction: the paper states no extinction
  and no truncation, and a residual landing in a plausible range is not evidence
  that it is the thing it resembles.

  **And "ordinary clear-sky" did not survive getting a model behind it
  (2026-09-15, [ADR 0023](../../docs/adr/0023-traceable-extinction.md)).**
  Through a 1.2 km aerosol layer at 1550 nm, `L_zen = 0.812` is **6 km of
  visibility** — *light fog* in ITU-R P.1817-1's own weather code — and in fact
  **no visibility produces it at all**: the published law's 22.3 % step at 6 km
  leaves the band from 0.883 to 1.129 dB unreachable, and 0.906 dB is inside it.
  At the other end of the literature's spread for the scale height, 2 km, it is
  reachable and means 9.8 km of visibility. Still compatible; no longer clear
  sky. This is the second time this entry has had to be corrected by a
  measurement, which is the argument for measuring.

### Extinction (stage 1.1)

- **Aerosol scattering has a model; molecular absorption still has no number.**
  `channel/extinction.py` implements ITU-R P.1814 Eq. (4), visibility to specific
  attenuation, verified against **32 published cells** (Kim et al. 2001 Tables 2
  and 4, both laws, both wavelengths) to within half of the last printed digit.
  What remains open is gap 23 of ADR 0009: two openable sources say molecular
  absorption is "negligible" at FSO wavelengths **in words**, ITU-R P.1621-2
  Figs. 1 and 2 are plots, and HITRAN answers but a line list is not a specific
  attenuation — turning one into the other is an LBLRTM/MODTRAN-class radiative
  transfer calculation this project does not have.
- **The aerosol scale height is a site parameter with no published value**
  (gap 22). 1.2 to 2 km is a factor 1.67 in optical depth: **0.230 against
  0.384 dB** at 23 km of visibility and 1550 nm. Hence no default.
- **A frozen MODTRAN table would be the V3 oracle this term lacks.** MODTRAN is
  paid software, so what enters instead is the one published *ratio* from
  somebody else's runs: Gruneisen et al. 2021 §III A report near-zenith
  transmission at 775 nm as "about 90 %" of that at 1550 nm under normal haze.
  Because 775 and 1550 differ by exactly a factor two, that ratio fixes the
  1550 nm zenith optical depth at **0.0720 Np** (`L_zen = 0.9305`) *without*
  needing the unpublished scale height, and the model reproduces it at 16.9 km of
  visibility. Their absolute `η_trans = 0.9` at 780 nm does **not** follow from
  it — the two statements together require `L_zen(1550) = 1.000` — so this is
  compatible on the ratio and not reproduced on the level.
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
- **Lim et al. 2014's evaluation channel model is internally inconsistent, and
  their smallest block size does not reproduce.** Their printed bit-error
  probability is `e_k = p_dc + e_mis [1 - exp(-eta_ch k)] + p_ap D_k / 2`, with
  `eta_ch` — the fibre alone — in the misalignment term, while the detection
  rate beside it carries `eta_sys = eta_ch eta_Bob`, ten times smaller. Read
  The misalignment term then contributes 3.9 points of QBER at zero loss (4.8 at
  100 km) on a system specified at 0.5 %, against 0.48 points under the
  consistent reading — a factor 8.07 that is the missing `1/eta_Bob`. Crossing that reading with whether `e_k`
  counts errors per gate or per detection gives four models whose block-size
  ratios at 100 km are **1.79**, 2.73, 1.46 and 1.47; the paper states "about
  1.75" for its own Fig. 1, so the physically consistent reading is the one
  implemented and the choice rests on their number rather than on taste.

  What still does not reproduce: their statement that a block of 1e4 reaches
  135 km. Under that reading a 1e4 block certifies no key at any distance, and
  the disagreement is exactly one decade — our 1e5 curve is their 1e4 curve.
  `tests/qkd/test_finite_key.py` asserts the **disagreement**, so that removing
  it forces this paragraph to be rewritten. See
  [ADR 0009](../../docs/adr/0009-citation-policy.md) gap 16 and
  [ADR 0010](../../docs/adr/0010-decoy-and-finite-key.md).
- **The horizontal path (`channel/horizontal.py`) has one primary source and one
  secondary one.** ITU-R P.1814 gives the plane-wave variance and a table of six
  fade depths, reproduced to their two decimals; nothing else about turbulence.
  The spherical wave and aperture averaging come from Kaushal & Kaddoum,
  arXiv:1506.04836, a survey quoting Churnside 1991 and Andrews 1992, which were
  not opened. The plane-wave averaging factor is cross-checked against ITU-R
  P.1622 equations (6)–(7) laid along a horizontal path (0.67 %, inside the 4.5 %
  its two-figure coefficient allows); the spherical one has no second source.
  ADR 0009 gap 17.
- **No Gaussian beam wave, no retroreflector, no horizontal beam wander.** The
  first is in Andrews & Phillips; the third is printed by Kaushal & Kaddoum
  without an equation number. The second was researched on 2026-09-15 and stays
  open for a reason worth writing down: the **sign** of the double-pass effect
  is settled and is the unhelpful one — a monostatic retro-reflector link is
  *more* scintillated than the one-way path, not less, because the outgoing and
  returning beams cross correlated air (Mahon et al., *Appl. Opt.* 51(25):6147
  (2012), measured on a 1.1 km horizontal link; abstract only, the record is
  paywalled) — while the **theory** is Andrews, Phillips & Miller, *Appl. Opt.*
  36(3):698 (1997), which is gap 1 under another title. ADR 0009 gaps 18 and 19,
  and [ADR 0021](../../docs/adr/0021-horizontal-path.md).
- **The moderate-to-strong scintillation model has three open sources and no
  open primary.** Ntanos et al. 2021 equation (12), Gruneisen et al. 2021
  equations (A8)/(A9) and Kaushal & Kaddoum equation (17) all print it; all three
  cite Andrews & Phillips (gap 1). The one V2 anchor is Gruneisen et al.'s
  printed maximum scintillation index of 1.24, reproduced as **1.2432** in
  `tests/channel/test_turbulence.py`. Kaushal & Kaddoum's copy carries one
  exponent wrong, and the same test says how the other two were preferred
  without a third opinion. ADR 0009 gaps 20 and 21, and
  [ADR 0022](../../docs/adr/0022-the-strong-regime.md).
- **SatQuMA as an independent V3 oracle for finite-key** (github.com/cnqo-qcomms/SatQuMA,
  **MIT licence**, pure Python, implements Lim et al. 2014 with its own numbered
  equations in arXiv:2109.01686). Not yet frozen into `data/`. It fails condition
  1 of “when a V3 oracle need not be frozen” — it is not a core dependency — so
  it belongs in `data/` with a manifest, generated by hand via the `reference`
  group. Note that SatQuMA uses **Chernoff** bounds (Yin et al., *Sci. Rep.*
  10:14312 (2020), Eqs. 2.9a/2.9b) where Lim et al. use **Hoeffding**: comparing
  without knowing which convention each side uses is chasing a ghost.

  Now actionable, and with a sharper target than when this was written:
  `qkd/finite_key.py` exists, implements Eqs. (1)-(5) of Lim et al., and already
  carries a cross-source V3 of its own — with `mu_3 = 0` and a block large enough
  for the Hoeffding term to vanish, its Eq. (3) reproduces Ma et al. 2005
  Eq. (34) as implemented in `qkd/bb84.py`, and the residual falls exactly like
  `1/sqrt(N)` (4.33e-04 at 1e16 pulses, 4.33e-08 at 1e24). What SatQuMA would add
  is the part that check cannot reach: the finite-size terms themselves.

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
