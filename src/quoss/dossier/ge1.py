"""``docs/experiments/GE-1.md``: the field link, from architecture to what it cannot claim.

What GE-1 is
------------
Two fixed optical terminals on the ground, one kilometre apart, one sending and
one receiving, running BB84 with decoy states over a 60-second measurement
session. It is the first link of this project that somebody could actually
build, and this document is what they would read before deciding to.

What this module does, and what it refuses to do
------------------------------------------------
It asks the engine for eight runs -- one base run and seven sweeps -- and turns
what comes back into prose and tables. It evaluates no physics of its own; the
boundary and what it cost is in :mod:`quoss.dossier.base`.

Every sweep here exists to answer one decision, and the sections are ordered by
how expensive the decision is to reverse: the architecture first (it cannot be
reversed at all once the terminals are bought), then the distance, then the
lens, then the session length, which is the one an operator can change on the
day.
"""

from __future__ import annotations

from typing import Any

from quoss.core.errors import DegradationLog
from quoss.dossier.base import (
    DossierSpec,
    Limit,
    bits,
    limits_section,
    logged_codes_section,
    number,
    percent,
    share,
    table,
    times,
)
from quoss.dossier.base import run_horizontal as _run_horizontal
from quoss.dossier.base import sweep_rows as _sweep_rows
from quoss.scenario.models import AnyScenario, HorizontalScenario

__all__ = ["SPEC", "build"]

FINITE = "session.finite_bits"
"""The certified figure. The one to report."""

ASYMPTOTIC = "session.asymptotic_bits"
"""What the same session would give with an infinite block. Reported beside, never instead."""

DISTANCES_M: tuple[float, ...] = (200.0, 500.0, 1000.0, 2410.0, 5000.0)
"""The distance rows.

Five, and each is a boundary rather than a round number: 200 m is inside the
transmitter's Rayleigh range, 500 m is at its edge, 1 km is the declared link,
2410 m is just inside the weak-theory limit of this air, and 5 km is past it.
A sixth point between them would add a row and no decision.
"""

APERTURES_M: tuple[float, ...] = (0.025, 0.1)
"""The two receiving lenses: a collimator-sized one and a 10 cm one."""

WAVES: tuple[str, ...] = ("plane", "spherical")
"""The two closed forms that bracket the beam wave nobody here can compute."""

SESSIONS_S: tuple[float, ...] = (15.0, 30.0, 60.0, 120.0)
"""The declared block lengths an operator might choose."""

UNMODELLED_LOSS_DB: tuple[float, ...] = (0.0, 0.5, 1.0, 2.0)
"""Static loss added on top of the budget, to price a decibel in bits."""

AEROSOL_SCALE_HEIGHTS_M: tuple[float, ...] = (1200.0, 2000.0)
"""The two ends of the unpublished range of ADR 0009 gap 22."""


def _rows(
    scenario: AnyScenario,
    parameters: dict[str, Any],
    log: DegradationLog,
    *,
    metrics: tuple[str, ...] = (FINITE, ASYMPTOTIC),
) -> list[dict[str, Any]]:
    return _sweep_rows(scenario, parameters, metrics, degradations=log)


def _pick(rows: list[dict[str, Any]], **match: Any) -> dict[str, Any]:
    """Return the one row whose swept columns equal ``match``."""
    for row in rows:
        if all(row[key] == value for key, value in match.items()):
            return row
    raise KeyError(f"no sweep row matching {match!r}; rows: {rows!r}")


def build(scenario: AnyScenario, log: DegradationLog) -> list[str]:
    """Return the body of ``docs/experiments/GE-1.md``."""
    scenario, result = _run_horizontal(scenario, degradations=log, what="GE-1")
    budget = result.budget
    session = result.session

    distance = _rows(scenario, {"path.path_length_m": list(DISTANCES_M)}, log)
    band = _rows(
        scenario,
        {"path.path_length_m": list(DISTANCES_M), "path.wave": list(WAVES)},
        log,
    )
    lenses = _rows(
        scenario,
        {"path.receive_aperture_m": list(APERTURES_M), "path.wave": list(WAVES)},
        log,
    )
    blocks = _rows(scenario, {"session.duration_s": list(SESSIONS_S)}, log)
    extra_loss = _rows(scenario, {"path.static_loss_db": list(UNMODELLED_LOSS_DB)}, log)
    aerosol = _rows(
        scenario,
        {"path.extinction.aerosol_scale_height_m": list(AEROSOL_SCALE_HEIGHTS_M)},
        log,
    )

    lines: list[str] = []
    lines += _what_it_decides()
    lines += _architecture()
    lines += _budget_section(budget, session)
    lines += _distance_section(scenario, budget, band)
    lines += _cliff_section(distance)
    lines += _lens_section(lenses)
    lines += _block_section(session, blocks)
    lines += _price_of_a_decibel(extra_loss, aerosol)
    lines += logged_codes_section(log)
    lines += [""]
    lines += limits_section(_limits(session, extra_loss, aerosol))
    return lines


# --------------------------------------------------------------------------- #
# Sections
# --------------------------------------------------------------------------- #
def _what_it_decides() -> list[str]:
    return [
        "## What this document is for",
        "",
        "GE-1 is two fixed optical terminals on the ground, a kilometre apart, one sending and "
        "one receiving, running BB84 with decoy states. This document is what somebody reads "
        "before deciding whether to build it: what the architecture costs, what the link "
        "budget is term by term, what a bigger receiving lens buys, and what the model behind "
        "all of that is unable to say.",
        "",
        "**Every number carries its unit and the decision it changes.** A *certified* figure is "
        "one the finite-key bound of Lim et al. 2014 will stand behind for the declared "
        "session; an *asymptotic* figure is what the same link would give if the measurement "
        "ran forever. The two are printed side by side throughout and the certified one is "
        "always the one to size on. Where they differ by a lot, the difference **is** the "
        "finding, and section 4 is the extreme case of it.",
        "",
        "Two terms recur. The **block** is the stretch of data the security proof is applied "
        "to in one piece; here it is the declared session, because nothing in a stationary "
        "link's geometry fixes one "
        "([ADR 0024](../adr/0024-the-horizontal-scenario.md)). The **outage probability** is "
        "how often the link is allowed to fade below the budget; 1 % throughout, which is the "
        "figure Ntanos et al. 2021 §4.1 use.",
        "",
    ]


def _architecture() -> list[str]:
    return [
        "## 1. The architecture, and why it is not a retroreflector",
        "",
        "**Decided: two terminals, one way.** The cheaper-looking option -- one terminal with a "
        "transceiver and a corner cube at the far end, so that only one end needs power and "
        "alignment -- is not modelled here, and the reason is not effort.",
        "",
        "A retroreflected link sends the light out and back through **the same air**. The two "
        "crossings are correlated rather than independent, so the scintillation is *enhanced* "
        "instead of averaged away. Mahon et al. (Appl. Opt. 51(25):6147, 2012) measured exactly "
        "that on a 1.1 km horizontal retroreflected link over four days. That abstract settles "
        "the **sign** of the effect; the theory that would give its **magnitude** is Andrews, "
        "Phillips & Miller (Appl. Opt. 36(3):698, 1997), which is the same source this project "
        "could not open (gap 1 of the table at the end).",
        "",
        "So the decision is not *which architecture is better*, it is which one can be sized "
        "before it is bought. One can and one cannot, and that difference is larger than the "
        "cost of the second terminal. "
        "[ADR 0025](../adr/0025-two-terminals-one-way.md) records it.",
        "",
    ]


def _budget_section(budget: Any, session: Any) -> list[str]:
    total = budget.total_db
    rows = [
        [
            "Geometric",
            number(budget.geometric_db),
            share(budget.geometric_db / total) if total else "-",
            "diffraction and the transmitter's truncation. Fixed by the two apertures and the "
            "distance.",
        ],
        [
            "Atmospheric",
            number(budget.atmospheric_db),
            share(budget.atmospheric_db / total) if total else "-",
            f"{number(budget.extinction_db_per_km)} dB/km of extinction over the path, from the "
            "declared visibility.",
        ],
        [
            "Pointing fade",
            number(budget.pointing_db),
            share(budget.pointing_db / total) if total else "-",
            "the allowance for jitter at 1 % outage. Bought down with a better mount.",
        ],
        [
            "Scintillation fade",
            number(budget.scintillation_db),
            share(budget.scintillation_db / total) if total else "-",
            "the allowance for turbulence at 1 % outage. Bought down with a bigger lens, "
            "section 5.",
        ],
        [
            "Both fades, jointly",
            number(budget.fade_db),
            share(budget.fade_db / total) if total else "-",
            "the **joint** 1 % quantile, not the sum of the two above. Adding them would "
            "budget a margin nothing needs.",
        ],
        [
            "Receiver chain",
            number(budget.receiver_chain_db),
            share(budget.receiver_chain_db / total) if total else "-",
            "detector efficiency and optical loss. Fixed by the receiver bought.",
        ],
        [
            "Declared static",
            number(budget.static_db),
            share(budget.static_db / total) if total else "-",
            "anything unmodelled the scenario chose to declare. Zero here, which is a claim "
            "and not an omission.",
        ],
        [
            "**Total**",
            f"**{number(total)}**",
            "**100 %**",
            f"transmittance {number(budget.transmittance)}",
        ],
    ]
    return [
        "## 2. The budget, term by term",
        "",
        "Decibels, at the declared kilometre and the declared 1 % outage. The joint-fade row "
        "is **not** the sum of the two rows above it, and that is the one line of this table "
        "worth reading twice: summing two 1 % quantiles produces a budget that is not a 1 % "
        "budget, and on the reference downlink that mistake was worth 0.64 dB of margin nobody "
        "needed.",
        "",
        *table(["Term", "dB", "Share", "What sets it, and what changes it"], rows),
        "",
        "What the session then certifies, at 100 MHz over the declared block:",
        "",
        *table(
            ["Quantity", "Value", "Unit", "What it decides"],
            [
                [
                    "Certified secret key",
                    bits(session.finite_bits),
                    "bits",
                    "**the number to size on.**",
                ],
                [
                    "Certified rate",
                    number(session.finite_bit_s),
                    "bit/s",
                    "the same figure per second of session.",
                ],
                [
                    "Asymptotic key",
                    bits(session.asymptotic_bits),
                    "bits",
                    f"{number(session.asymptotic_bits / session.finite_bits)}x the certified "
                    "figure. Never the number to quote."
                    if session.finite_bits
                    else "the link certifies nothing; this is what an asymptotic sizing would claim.",
                ],
                ["QBER", number(session.qber), "1", "errors in the key basis."],
                [
                    "Phase error rate",
                    number(session.phase_error_rate),
                    "1",
                    "the conjugate basis. At 0.5 the single-photon term vanishes and the link "
                    "certifies nothing whatever the loss is.",
                ],
                [
                    "Noise per gate",
                    number(session.noise_counts_per_gate),
                    "counts",
                    "background, dark counts and afterpulsing together.",
                ],
                [
                    "Pulses in the block",
                    number(session.pulses),
                    "1",
                    "block size. Three orders of magnitude above the reference downlink's best "
                    "pass, so the bound is far from its small-block cliff.",
                ],
            ],
        ),
        "",
    ]


def _distance_section(
    scenario: HorizontalScenario, budget: Any, band: list[dict[str, Any]]
) -> list[str]:
    rayleigh = budget.rayleigh_range_m
    weak_limit = budget.weak_theory_path_limit_m
    wave = str(scenario.path.wave.value)
    rows = []
    for metres in DISTANCES_M:
        plane = _pick(band, **{"path.path_length_m": metres, "path.wave": "plane"})
        spherical = _pick(band, **{"path.path_length_m": metres, "path.wave": "spherical"})
        marks = []
        if metres < rayleigh:
            marks.append("inside the Rayleigh range")
        if metres > weak_limit:
            marks.append("**past the weak-theory limit**")
        rows.append(
            [
                number(metres),
                bits(plane[FINITE]),
                bits(spherical[FINITE]),
                times(max(plane[FINITE], spherical[FINITE]), min(plane[FINITE], spherical[FINITE])),
                ", ".join(marks) if marks else "-",
            ]
        )
    return [
        "## 3. Certified key against distance, with the plane-to-spherical band",
        "",
        "The two middle columns are the same link computed with each of the two closed forms "
        "available for the scintillation of a horizontal path. The scenario declares "
        f"`wave: {wave}`, so that column is the link as this project reports it; the other is "
        "the other edge of a bracket, not a second opinion.",
        "",
        "**The band between them is not an error bar, and reading it as one gives two false "
        "conclusions at once.** A shaded region around a curve means statistical uncertainty "
        "almost everywhere in the literature -- a confidence interval, a percentile, a one-sigma "
        "spread -- and this is none of those. There is no distribution behind it and no "
        "probability attached: they are **two models, each computed exactly, bracketing a third "
        "that is not implemented** (the Gaussian beam wave, gap 18). The true answer may sit "
        "anywhere between them and the shape in between is unknown, so the middle is not the "
        "most likely value and the edges are not improbable. "
        "[ADR 0017 §2](../adr/0017-publication-figures.md) states the convention and the figure "
        "carries it in its legend.",
        "",
        "**And the band is not ordered the same way at every row**, which is why it is printed "
        "as two columns rather than as a centre and a width: section 5 shows the two lenses "
        "swapping which edge is the pessimistic one.",
        "",
        *table(
            [
                "Path length (m)",
                "Plane wave, certified (bits)",
                "Spherical wave, certified (bits)",
                "Width of the band (factor)",
                "Where this row sits",
            ],
            rows,
        ),
        "",
        f"The two marks are properties of the transmitter and of the air, not of the rows: the "
        f"Rayleigh range is **{number(rayleigh)} m** (where a collimated 2.5 cm beam at 1550 nm "
        f"starts to spread appreciably) and the weak-theory limit is **{number(weak_limit)} m** "
        f"(where the plane-wave Rytov variance of this air reaches 1 Np^2). Both are carried in "
        "the result so that nothing downstream has to guess them from the shape of the data; a "
        "guessed mark looks measured ([ADR 0017 §4](../adr/0017-publication-figures.md)).",
        "",
        "Inside the Rayleigh range the band gets **narrow, for the wrong reason**. It is not "
        "that the two models agree there -- neither describes a collimated beam, and the "
        "spherical one is at its worst -- it is that the geometric term dominates, so the "
        "difference between them no longer reaches the key. A narrow band there means the "
        "answer is insensitive, not that it is known.",
        "",
    ]


def _cliff_section(distance: list[dict[str, Any]]) -> list[str]:
    far = _pick(distance, **{"path.path_length_m": DISTANCES_M[-1]})
    near = _pick(distance, **{"path.path_length_m": 1000.0})
    return [
        "## 4. The cliff, with the asymptotic figure beside it",
        "",
        f"At **{number(DISTANCES_M[-1])} m** on this air, the link certifies "
        f"**{bits(far[FINITE])} bits** and the asymptotic calculation still claims "
        f"**{bits(far[ASYMPTOTIC])} bits** over the same session "
        f"({number(far[ASYMPTOTIC] / 60.0)} bit/s).",
        "",
        "**That pair is the single most important line in this document.** An asymptotic "
        "sizing would call that distance a working link of a few kilobits per second and would "
        "be off not by a factor but by everything: the finite-key bound certifies nothing at "
        "all, because the loss has pushed the phase error rate to where the single-photon term "
        "vanishes. A study that reported only the asymptotic figure would have counted a link "
        "that does not exist.",
        "",
        f"For contrast, the declared kilometre certifies {bits(near[FINITE])} bits against "
        f"{bits(near[ASYMPTOTIC])} asymptotic -- a factor of "
        f"{times(near[ASYMPTOTIC], near[FINITE])}, large but finite. The cliff is not a gradual "
        "penalty that gets worse; it is a distance past which the certified figure is zero and "
        "the asymptotic one is not.",
        "",
        "**What this decides:** never dimension the span from an asymptotic rate, and never "
        "quote one without the certified figure on the same line.",
        "",
    ]


def _lens_section(lenses: list[dict[str, Any]]) -> list[str]:
    small, large = APERTURES_M
    rows = []
    for wave in WAVES:
        a = _pick(lenses, **{"path.receive_aperture_m": small, "path.wave": wave})
        b = _pick(lenses, **{"path.receive_aperture_m": large, "path.wave": wave})
        rows.append(
            [
                wave,
                bits(a[FINITE]),
                bits(b[FINITE]),
                times(b[FINITE], a[FINITE]),
                bits(a[ASYMPTOTIC]),
                bits(b[ASYMPTOTIC]),
                times(b[ASYMPTOTIC], a[ASYMPTOTIC]),
            ]
        )
    plane_small = _pick(lenses, **{"path.receive_aperture_m": small, "path.wave": "plane"})
    spherical_small = _pick(lenses, **{"path.receive_aperture_m": small, "path.wave": "spherical"})
    plane_large = _pick(lenses, **{"path.receive_aperture_m": large, "path.wave": "plane"})
    spherical_large = _pick(lenses, **{"path.receive_aperture_m": large, "path.wave": "spherical"})
    small_pessimist = (
        "plane" if plane_small[ASYMPTOTIC] < spherical_small[ASYMPTOTIC] else "spherical"
    )
    large_pessimist = (
        "plane" if plane_large[ASYMPTOTIC] < spherical_large[ASYMPTOTIC] else "spherical"
    )
    return [
        "## 5. What a receiving aperture buys",
        "",
        f"The largest single lever on this link. Going from a {number(1000 * small)} mm lens to "
        f"a {number(1000 * large)} mm one, at the declared kilometre, everything else held:",
        "",
        *table(
            [
                "Wave form",
                f"Certified, {number(1000 * small)} mm (bits)",
                f"Certified, {number(1000 * large)} mm (bits)",
                "Factor, certified",
                f"Asymptotic, {number(1000 * small)} mm (bits)",
                f"Asymptotic, {number(1000 * large)} mm (bits)",
                "Factor, asymptotic",
            ],
            rows,
        ),
        "",
        "**The factor is an interval and not a number**, because the two closed forms disagree "
        "about it and neither is defensible as *the* answer. Quote the interval. The two "
        "asymptotic factors are the pair this project has published before -- the lens is worth "
        "between 8.4 and 11.2 -- and the certified factors are wider, because the smaller lens "
        "loses more to the finite-key bound than to the loss.",
        "",
        f"**And the interval is not ordered the same way at the two lenses.** At "
        f"{number(1000 * small)} mm the pessimistic edge is the **{small_pessimist}** wave; at "
        f"{number(1000 * large)} mm it is the **{large_pessimist}** one. So there is no "
        "consistent 'conservative model' to pick and stay with: a sizing that chose one wave at "
        "the small lens and kept it at the large one would be using the optimistic edge without "
        "noticing. Take both.",
        "",
        "**What this decides:** the lens is the purchase to argue about, and the argument has "
        "to be made with the interval in front of it.",
        "",
    ]


def _block_section(session: Any, blocks: list[dict[str, Any]]) -> list[str]:
    declared = session.duration_s
    rows = []
    base = _pick(blocks, **{"session.duration_s": declared})
    for seconds in SESSIONS_S:
        row = _pick(blocks, **{"session.duration_s": seconds})
        rate = row[FINITE] / seconds
        rows.append(
            [
                number(seconds),
                bits(row[FINITE]),
                number(rate),
                times(rate, base[FINITE] / declared),
                bits(row[ASYMPTOTIC]),
            ]
        )
    return [
        "## 6. The declared block, which is the operator's decision and not the geometry's",
        "",
        "On a satellite downlink the block a finite-key bound is applied to is a **pass**, and "
        "nothing about that is a choice: between two passes the satellite is below the horizon "
        "and not one pulse is sent "
        "([ADR 0011](../adr/0011-the-block-is-the-pass.md)). GE-1 is stationary and nothing "
        "stops the data, so the block is whatever is declared -- and declaring 60 s is a "
        "**promise that the link was stationary and undisturbed for sixty seconds**, which is "
        "a statement about the site and the mount, not about the physics.",
        "",
        *table(
            [
                "Session (s)",
                "Certified (bits)",
                "Certified rate (bit/s)",
                f"Rate against the declared {number(declared)} s",
                "Asymptotic (bits)",
            ],
            rows,
        ),
        "",
        "The rate column is the one to read. If it were flat, the session length would be free "
        "and only the total would move; where it is not, the bound is charging for the block "
        "being short, and lengthening the session buys key at better than proportion. "
        "[ADR 0024](../adr/0024-the-horizontal-scenario.md) says who is responsible for the "
        "declared length being a legitimate one.",
        "",
    ]


def _price_of_a_decibel(extra: list[dict[str, Any]], aerosol: list[dict[str, Any]]) -> list[str]:
    baseline = _pick(extra, **{"path.static_loss_db": 0.0})
    one_db = _pick(extra, **{"path.static_loss_db": 1.0})
    rows = [
        [
            number(db),
            bits(_pick(extra, **{"path.static_loss_db": db})[FINITE]),
            percent(_pick(extra, **{"path.static_loss_db": db})[FINITE] / baseline[FINITE] - 1.0)
            if baseline[FINITE]
            else "-",
        ]
        for db in UNMODELLED_LOSS_DB
    ]
    low, high = AEROSOL_SCALE_HEIGHTS_M
    aerosol_low = _pick(aerosol, **{"path.extinction.aerosol_scale_height_m": low})
    aerosol_high = _pick(aerosol, **{"path.extinction.aerosol_scale_height_m": high})
    same = aerosol_low[FINITE] == aerosol_high[FINITE]
    return [
        "## 7. What one decibel is worth here, so that a declared gap can be priced",
        "",
        "Several of the gaps in the closing section are of the form *this term has no published "
        "number and it can only add loss*. That is unactionable until somebody knows what a "
        "decibel is worth, so here it is, measured on this link by adding declared static loss "
        "and re-running:",
        "",
        *table(["Extra loss (dB)", "Certified (bits)", "Change"], rows),
        "",
        f"**One unmodelled decibel costs {bits(baseline[FINITE] - one_db[FINITE])} bits, "
        f"{percent(one_db[FINITE] / baseline[FINITE] - 1.0) if baseline[FINITE] else '-'} of the "
        "session.** Any caveat below that can be bounded in decibels can be read through this "
        "table.",
        "",
        f"The same method prices gap 22, the unpublished aerosol scale height, and on this link "
        f"the answer is that it costs **nothing at all**: at {number(low)} m the session "
        f"certifies {bits(aerosol_low[FINITE])} bits and at {number(high)} m it certifies "
        f"{bits(aerosol_high[FINITE])}"
        + (
            " -- the same number to the bit. The reason is geometric rather than lucky: the "
            "scenario declares the visibility at the height the link runs at, so the scale "
            "height has no altitude difference to act over. **This is a property of this "
            "scenario and not of the model**, and a reader who moves this link onto a mountain "
            "while keeping a sea-level visibility figure will be exposed to the full factor of "
            "1.67 in optical depth that the gap carries."
            if same
            else ", which is a difference this scenario was expected not to have; read gap 22 "
            "before using either figure."
        ),
        "",
    ]


def _limits(
    session: Any, extra: list[dict[str, Any]], aerosol: list[dict[str, Any]]
) -> tuple[Limit, ...]:
    baseline = _pick(extra, **{"path.static_loss_db": 0.0})
    one_db = _pick(extra, **{"path.static_loss_db": 1.0})
    per_db = baseline[FINITE] - one_db[FINITE]
    low, high = AEROSOL_SCALE_HEIGHTS_M
    aerosol_delta = (
        _pick(aerosol, **{"path.extinction.aerosol_scale_height_m": high})[FINITE]
        - _pick(aerosol, **{"path.extinction.aerosol_scale_height_m": low})[FINITE]
    )
    return (
        Limit(
            gap=20,
            title="**A turbulence emulator is not a `C_n^2`.** Scintillation is phase distortion "
            "turned into amplitude *by propagation*, so a phase screen needs distance behind it. "
            "Matching the Rytov variance of a kilometre on a two-metre bench is a necessary and "
            "not a sufficient condition, and this project models no phase screens.",
            cost="Not a cost to GE-1's own figures: it bounds what **GE-0b can check about "
            "GE-1**. Measured there: a bench matching this link's Rytov variance exactly leaves "
            "its receiver seeing 2 183 times less variance and 1.42 dB less fade. See "
            "`GE-0b.md`.",
            reference="`tests/e2e/test_horizontal_scenario.py::TestTheBenchIsTheOtherFile`",
        ),
        Limit(
            gap=21,
            title="**Aperture averaging follows ITU-R P.1622's convention, not Ntanos et al.'s.** "
            "P.1622 Eq. (8) multiplies the *log-variance* by `A`; Ntanos Eq. (14) defines `A` as "
            "a ratio of scintillation *indices*. The two agree to first order for small variance "
            "and not otherwise, and no source settles which applies in the saturated regime.",
            cost="Never priced on this link, and that is the honest statement: the convention was "
            "measured on the reference **downlink**, where it moves the day by -3.29 % in the "
            "weak regime and -1.66 % saturated, and where it decides the **sign** of a published "
            "term -- the station-altitude term lands at +4 bits of 449 308 under the other "
            "convention, so the -206 bits the saturated regime reports are entirely inside this "
            "gap. GE-1 uses the same convention through "
            "`horizontal_aperture_averaging_factor`, so it inherits an unpriced error of that "
            "family.",
            reference="`tests/e2e/test_reference_scenarios.py::TestWhatTheApertureAveragingConventionCosts`",
        ),
        Limit(
            gap=22,
            title="**The aerosol scale height has no published value** (the figures in use span "
            "about 1.2 to 2 km, a factor of 1.67 in optical depth), and the visibility law "
            "carries molecular scattering at the aerosol exponent, which overstates the "
            "coefficient by 2.9 % at 10 km of visibility and 14.0 % at 50 km.",
            cost=f"**{bits(abs(aerosol_delta))} bits** on this link, from {number(low)} m to "
            f"{number(high)} m of scale height -- see section 7 for why, and for the condition "
            "under which that zero stops holding. The molecular-attribution half is inside the "
            f"declared {number(0.192)} dB/km and so inside the decibel priced above.",
            reference="`docs/adr/0023-traceable-extinction.md`, section 7 of this document",
        ),
        Limit(
            gap=23,
            title="**Molecular absorption has no number in any open source.** ITU-R P.1814 §4.1 "
            "and Kim et al. §3 both call it negligible at these wavelengths in words; neither "
            "prints a figure, and turning a line list into a specific attenuation is "
            "radiative-transfer code this project does not have.",
            cost=f"Unpriced, and bounded only by its sign: it can only **add** loss. One "
            f"decibel of it would cost {bits(per_db)} bits of the "
            f"{bits(session.finite_bits)}-bit session, from section 7. If it is negligible as "
            "both sources say in words, it is worth a fraction of that.",
            reference="section 7 of this document",
        ),
        Limit(
            gap=18,
            title="**The Gaussian beam wave is not implemented.** A real collimated beam is "
            "neither a plane wave nor a spherical one; the closed forms for it are in a source "
            "this project could not open (gap 1, Andrews & Phillips).",
            cost="The width of the plane-to-spherical band of sections 3 and 5, which is why "
            "that band is reported as two columns rather than as a margin. It is not a "
            "statistical uncertainty and must not be quoted as one.",
            reference="`docs/adr/0017-publication-figures.md` §2, sections 3 and 5 above",
        ),
    )


SPEC = DossierSpec(
    identifier="GE-1",
    subtitle="two ground terminals, one way, one kilometre",
    scenario_name="ge1_1km",
    scenario_path="scenarios/ge1_1km.yaml",
    document_path="docs/experiments/GE-1.md",
    body=build,
)
"""The GE-1 dossier."""
