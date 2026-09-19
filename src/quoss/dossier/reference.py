"""``docs/experiments/reference-link.md``: the reference day, and what it does and does not certify.

What the reference link is
--------------------------
A 700 km sun-synchronous satellite over Castelldefels, one UTC day at one
second, a 0.75 m receiving telescope, and the Ntanos et al. 2021 transmitter,
receiver and protocol. It is not an experiment anybody is about to build: it is
the link every number in this project is measured on, so that two changes to
the physics can be compared on the same day.

What this document has to say that the ADRs do not
---------------------------------------------------
Three things, and the third is the one this round made mandatory.

1. **Two of the four passes certify nothing**, while the asymptotic integral
   claims hundreds of kilobits over them. That is the finding of
   ``docs/adr/0011-the-block-is-the-pass.md``, restated here for a reader who
   will not open an ADR.
2. **The elevation mask has an interior optimum**, and which optimum depends on
   the turbulence regime declared. A mask is a scheduling decision somebody
   makes, so the number has to be published with its regime attached.
3. **Which of the two Ntanos reference links is in use.** Their §4.2.1 declares
   a 20 dB best case and their §4.3.1 prints a peak key rate that requires
   24.07 dB. The two are 4.07 dB apart, both are printed, and **neither is an
   anchor here**. A document that quietly used one would be presenting a
   contested figure as a settled one.

This module computes no physics; the boundary is in
:mod:`quoss.dossier.base`.
"""

from __future__ import annotations

from typing import Any

from quoss.core.errors import DegradationLog
from quoss.core.units import rad_to_deg
from quoss.dossier.base import (
    DossierSpec,
    Limit,
    bits,
    limits_section,
    logged_codes_section,
    number,
    percent,
    signed,
    table,
    times,
)
from quoss.dossier.base import run_downlink as _run_downlink
from quoss.dossier.base import sweep_rows as _sweep_rows
from quoss.scenario.defaults import ntanos_2021
from quoss.scenario.models import AnyScenario, Scenario
from quoss.scenario.result import SimulationResult

__all__ = ["SPEC", "build"]

FINITE = "daily.finite_bits"
"""The certified key per day, summed over days."""

ASYMPTOTIC = "daily.asymptotic_bits"
"""The same day with an infinite block per pass. Reported beside, never instead."""

MASK_PARAMETER = "passes.minimum_elevation_deg"
"""The dotted scenario path the mask sweep varies."""

REGIME_PARAMETER = "channel.scintillation_regime"
"""The dotted scenario path the regime sweep varies."""

MASKS_DEG: tuple[float, ...] = (2.0, 3.0, 4.0, 4.5, 5.0, 6.0, 8.0, 10.0, 15.0, 20.0)
"""The mask angles sampled.

Ten, clustered between 3 and 8 degrees because that is where the two regimes put
their optima and a coarser grid reports the wrong angle with a straight face: at
a 2-degree spacing the saturated optimum comes back as 4.0 deg, and with the
half-degree points in the grid the sampled maximum is at 5.0 with a top flat
from 4.5 to 6. This is still a **sample and not a solve**, and the document says
so where it names the angles.
"""

REGIMES: tuple[str, ...] = ("weak", "moderate-to-strong")
"""The two scintillation regimes a downlink scenario may declare."""

STATION_APERTURES_M: tuple[float, ...] = (0.75, 1.3, 2.3)
"""The three Ntanos et al. 2021 ground stations, by the aperture that names them."""

SEA_LEVEL_M = 0.0
"""The counterfactual altitude the altitude term is measured against."""


def _pick(rows: list[dict[str, Any]], **match: Any) -> dict[str, Any]:
    for row in rows:
        if all(row[key] == value for key, value in match.items()):
            return row
    raise KeyError(f"no sweep row matching {match!r}; rows: {rows!r}")


def build(scenario: AnyScenario, log: DegradationLog) -> list[str]:
    """Return the body of ``docs/experiments/reference-link.md``."""
    scenario, result = _run_downlink(scenario, degradations=log, what="the reference link")
    masks = _sweep_rows(
        scenario,
        {MASK_PARAMETER: list(MASKS_DEG), REGIME_PARAMETER: list(REGIMES)},
        (FINITE, ASYMPTOTIC),
        degradations=log,
    )
    altitude = _sweep_rows(
        scenario,
        {"stations.0.altitude_m": [SEA_LEVEL_M, scenario.stations[0].altitude_m]},
        (FINITE,),
        degradations=log,
    )
    stations = []
    for aperture in STATION_APERTURES_M:
        station_scenario = ntanos_2021(aperture)
        declared = station_scenario.stations[0].altitude_m
        rows = _sweep_rows(
            station_scenario,
            {"stations.0.altitude_m": [SEA_LEVEL_M, declared]},
            (FINITE, ASYMPTOTIC),
            degradations=log,
        )
        stations.append((station_scenario, declared, rows))

    lines: list[str] = []
    lines += _what_it_decides(scenario)
    lines += _the_day(result)
    lines += _the_passes(result)
    lines += _the_mask(scenario, masks)
    lines += _the_stations(scenario, altitude, stations)
    lines += _which_ntanos_link()
    lines += logged_codes_section(log)
    lines += [""]
    lines += limits_section(_limits(result, altitude, stations))
    return lines


def _orbit_phrase(scenario: Scenario) -> str:
    """Describe the orbit in words, from whichever of the two ways it was declared.

    ``OrbitSpec`` carries either Keplerian elements or a TLE and never both, so
    reading ``kepler.altitude_km`` unconditionally would be a crash waiting for
    the day somebody points this dossier at a TLE-driven copy of the reference
    scenario. The branch costs two lines and removes that.
    """
    kepler = scenario.orbit.kepler
    if kepler is None:
        return "A satellite propagated from a two-line element set"
    sun_synchronous = " sun-synchronous" if kepler.sun_synchronous else ""
    return f"A {number(kepler.altitude_km)} km{sun_synchronous} satellite"


def _what_it_decides(scenario: Scenario) -> list[str]:
    station = scenario.stations[0]
    return [
        "## What this document is for",
        "",
        f"{_orbit_phrase(scenario)} over "
        f"{station.name}, one UTC day at {number(scenario.time.step_s)} s, a "
        f"{number(station.receive_aperture_m)} m receiving telescope, and the Ntanos et al. "
        "2021 transmitter, receiver and protocol. This is **not an experiment anybody is about "
        "to build**: it is the link every number in this project is measured on, so that two "
        "changes to the physics can be compared on the same day.",
        "",
        "It is in `docs/experiments/` anyway, because three of its properties are decisions "
        "somebody outside the code has to make: how many of the passes are worth scheduling, "
        "where to put the elevation mask, and which published reference link a result is being "
        "compared against.",
        "",
        "**Nothing here certifies a system.** A day of this link is a statement about a "
        "modelled orbit over a modelled sky, with cloud cover not modelled at all "
        "(`cloud_fraction: null`). Read it as the yardstick it is.",
        "",
    ]


def _the_day(result: SimulationResult) -> list[str]:
    daily = result.daily
    finite = float(daily.finite_bits.sum())
    asymptotic = float(daily.asymptotic_bits.sum())
    passes = int(daily.pass_count.sum())
    with_key = int(daily.passes_with_key.sum())
    return [
        "## 1. The day",
        "",
        *table(
            ["Quantity", "Value", "Unit", "What it decides"],
            [
                ["Certified key", bits(finite), "bits/day", "**the number to plan capacity on.**"],
                [
                    "Asymptotic key",
                    bits(asymptotic),
                    "bits/day",
                    f"{times(asymptotic, finite)}x the certified figure. An upper bound, and "
                    "loosest exactly where the link is worst.",
                ],
                [
                    "Passes above the mask",
                    str(passes),
                    "1",
                    "how many windows the geometry offers.",
                ],
                [
                    "Passes that certify a key",
                    str(with_key),
                    "1",
                    f"**{passes - with_key} of {passes} certify nothing.** Section 2.",
                ],
                [
                    "Composed secrecy",
                    number(daily.composed_secrecy),
                    "1",
                    "the day's key is the concatenation of the passes' blocks, so the failure "
                    "probabilities add (union bound). Per pass it is "
                    f"{number(result.scenario.security.secrecy)}.",
                ],
            ],
        ),
        "",
    ]


def _the_passes(result: SimulationResult) -> list[str]:
    passes = result.passes
    rows = []
    for index in range(len(passes.finite_bits)):
        finite = float(passes.finite_bits[index])
        asymptotic = float(passes.asymptotic_bits[index])
        rows.append(
            [
                str(index),
                number(float(passes.end_s[index] - passes.start_s[index])),
                number(float(rad_to_deg(float(passes.culmination_elevation_rad[index])))),
                bits(finite),
                bits(asymptotic),
                "yes" if finite > 0.0 else "**no**",
            ]
        )
    dead = [i for i in range(len(passes.finite_bits)) if float(passes.finite_bits[i]) == 0.0]
    dead_asymptotic = sum(float(passes.asymptotic_bits[i]) for i in dead)
    return [
        "## 2. The four passes, and the two that certify nothing",
        "",
        *table(
            [
                "Pass",
                "Duration (s)",
                "Culmination elevation (deg)",
                "Certified (bits)",
                "Asymptotic (bits)",
                "Certifies a key",
            ],
            rows,
        ),
        "",
        f"**{len(dead)} of the {len(rows)} passes certify exactly zero bits**, and the "
        f"asymptotic integral claims {bits(dead_asymptotic)} bits over them. That is not a "
        "failure of the run; it is the finding. A pass that is short and low delivers few "
        "detections and a high error rate, and the finite-key bound of Lim et al. 2014 has to "
        "pay for the statistical uncertainty of a small block out of the key it certifies. "
        "Below a threshold there is nothing left to pay with, and the honest answer is zero "
        "rather than a small number.",
        "",
        "**What this decides:** scheduling. Two of these windows cost ground-station time, "
        "tracking and operator attention and return nothing certifiable. A study that sized "
        "the day from the asymptotic column would have budgeted for four working passes and "
        "got two. [ADR 0011](../adr/0011-the-block-is-the-pass.md) has the argument.",
        "",
    ]


def _the_mask(scenario: Scenario, masks: list[dict[str, Any]]) -> list[str]:
    declared = scenario.passes.minimum_elevation_deg
    declared_regime = str(scenario.channel.scintillation_regime.value)
    rows = []
    optima: dict[str, tuple[float, float]] = {}
    for regime in REGIMES:
        best = max(
            (_pick(masks, **{MASK_PARAMETER: deg, REGIME_PARAMETER: regime}) for deg in MASKS_DEG),
            key=lambda row: row[FINITE],
        )
        optima[regime] = (float(best[MASK_PARAMETER]), float(best[FINITE]))
    for deg in MASKS_DEG:
        row = [number(deg)]
        for regime in REGIMES:
            entry = _pick(masks, **{MASK_PARAMETER: deg, REGIME_PARAMETER: regime})
            marker = "**" if deg == optima[regime][0] else ""
            row.append(f"{marker}{bits(entry[FINITE])}{marker}")
        row.append(
            bits(_pick(masks, **{MASK_PARAMETER: deg, REGIME_PARAMETER: REGIMES[0]})[ASYMPTOTIC])
        )
        rows.append(row)
    weak_deg, weak_bits = optima["weak"]
    strong_deg, strong_bits = optima["moderate-to-strong"]
    floor = _pick(masks, **{MASK_PARAMETER: MASKS_DEG[0], REGIME_PARAMETER: "weak"})
    return [
        "## 3. The elevation mask has an interior optimum, and it depends on the regime",
        "",
        "An **elevation mask** is the angle above the horizon below which the station does not "
        "bother tracking. The intuition is that a lower mask can only help, because it adds "
        "seconds of link. For the asymptotic key that intuition is correct and the last column "
        "below shows it: it grows monotonically as the mask drops.",
        "",
        "**For the certified key it is wrong.** Low-elevation seconds arrive through more air, "
        "so they carry more errors -- and because the whole pass is one block, those errors are "
        "charged against the key of the *entire* pass, including its good minutes. Past a "
        "point, adding seconds subtracts key.",
        "",
        *table(
            [
                "Mask (deg)",
                "Certified, `weak` (bits/day)",
                "Certified, `moderate-to-strong` (bits/day)",
                "Asymptotic, `weak` (bits/day)",
            ],
            rows,
        ),
        "",
        f"**The optimum is interior in both regimes, and it is not the same angle.** Of the "
        f"{len(MASKS_DEG)} angles sampled above, the best in `weak` is "
        f"**{number(weak_deg)} deg** ({bits(weak_bits)} bits, against {bits(floor[FINITE])} at "
        f"{number(MASKS_DEG[0])} deg) and the best in `moderate-to-strong` is "
        f"**{number(strong_deg)} deg** ({bits(strong_bits)} bits, "
        f"{percent(strong_bits / weak_bits - 1.0)} above the weak optimum). The scenario "
        f"declares `{declared_regime}` and a mask of {number(declared)} deg.",
        "",
        "**That is a sample and not a solve.** The table is ten runs, not an optimisation, so "
        "the true optimum sits somewhere inside the bracket its neighbours make and a finer "
        "grid will move the printed angle by a fraction of a degree. What the sample does "
        "establish -- and it is the part that matters -- is that the optimum is **interior**: "
        "the certified key at the lowest angle sampled is lower than at the best one, so "
        "dropping the mask to the horizon loses key.",
        "",
        "**So a mask figure is not quotable without its regime.** The regime is not a tuning "
        "knob: it says whether the weak-fluctuation theory applies at all on the path in "
        "question, and past a Rytov variance of 1 it does not "
        "([ADR 0022](../adr/0022-the-strong-regime.md)). The two columns above are two "
        "different claims about the air, and they disagree about where to point the telescope.",
        "",
        "**What this decides:** the standing instruction given to whoever schedules the station.",
        "",
    ]


def _the_stations(
    scenario: Scenario,
    altitude: list[dict[str, Any]],
    stations: list[tuple[Any, float, list[dict[str, Any]]]],
) -> list[str]:
    reference_station = scenario.stations[0]
    declared_m = reference_station.altitude_m
    at_sea = _pick(altitude, **{"stations.0.altitude_m": SEA_LEVEL_M})[FINITE]
    at_declared = _pick(altitude, **{"stations.0.altitude_m": declared_m})[FINITE]
    rows = [
        [
            f"{reference_station.name} (this scenario)",
            number(declared_m),
            number(reference_station.receive_aperture_m),
            bits(at_declared),
            bits(at_sea),
            signed(at_declared - at_sea),
            percent((at_declared - at_sea) / at_sea) if at_sea else "-",
        ]
    ]
    for station_scenario, declared, station_rows in stations:
        station = station_scenario.stations[0]
        sea = _pick(station_rows, **{"stations.0.altitude_m": SEA_LEVEL_M})[FINITE]
        real = _pick(station_rows, **{"stations.0.altitude_m": declared})[FINITE]
        rows.append(
            [
                station.name,
                number(declared),
                number(station.receive_aperture_m),
                bits(real),
                bits(sea),
                signed(real - sea),
                percent((real - sea) / sea) if sea else "-",
            ]
        )
    return [
        "## 4. The three stations, and what standing high is worth",
        "",
        "The **altitude term** is what a station's height above sea level is worth in certified "
        "bits, measured the only way it can be: the same station run at its declared altitude "
        "and at zero, everything else held. It is not a small effect for a mountain site, and "
        "it is not a simple one, which is the point of the last column.",
        "",
        "Two things fight. Starting the turbulence integral higher up removes the densest air, "
        "which lowers the variance a point receiver would see; but the same move makes the "
        "remaining turbulence *closer* to the receiver in the sense that matters for aperture "
        "averaging, which raises the fraction the telescope cannot average away. Which one wins "
        "depends on the elevation, so it depends on how a day's seconds are distributed in "
        "elevation.",
        "",
        *table(
            [
                "Station",
                "Altitude (m)",
                "Aperture (m)",
                "Certified at its altitude (bits/day)",
                "Certified at sea level (bits/day)",
                "Altitude term (bits/day)",
                "Change",
            ],
            rows,
        ),
        "",
        "**One of the four rows has the opposite sign**, and that is the finding rather than a "
        "curiosity: the highest station of the three is the one where standing high **costs** "
        "certified key. The two effects above cross over, and where they cross depends on the "
        "elevation, the aperture and how a day's seconds are distributed between them.",
        "",
        "**One caution about what the table measured**, because it is not quite the published "
        "figure it resembles. Moving a station to sea level here moves **both** things at once: "
        "the height the turbulence integral starts at *and* the station's own geodetic position, "
        "so the slant ranges change a little too. The figure this project has published before "
        "-- +457 bits for the reference station -- moves only the turbulence start. The two "
        "agree to about 7 %, which is the size of the geometric half.",
        "",
        "**Read this table with gap 21 of the closing section in front of you, because it is the "
        "column this gap lands in.** The aperture-averaging factor `A` can be defined on "
        "log-variances (ITU-R P.1622 Eq. (8), which is what this project uses) or on "
        "scintillation indices (Ntanos et al. Eq. (14)), no source settles which applies in the "
        "saturated regime, and the choice **decides the sign** of exactly this term. Measured "
        "on this reference day: the saturated altitude term is -206 bits under this project's "
        "convention and **+4 bits of 449 308 under the other one** -- which is to say the whole "
        "of it is inside the gap. The weak-regime term is larger and survives the change of "
        "convention with its sign intact (+457 against +1237 bits), so the rows above are "
        "directionally safe and their magnitudes are not.",
        "",
        "**What this decides:** whether a mountain station is worth its access road. The answer "
        "above is real and its magnitude is uncertain by the size of the term itself in the "
        "saturated regime.",
        "",
    ]


def _which_ntanos_link() -> list[str]:
    return [
        "## 5. Which of the two Ntanos reference links is being used",
        "",
        "Ntanos et al. 2021 (Photonics 8(12):544) is the source of this project's transmitter, "
        "receiver and protocol, and it prints **two** end-to-end claims about a downlink that "
        "are not consistent with each other. A document that quoted either one as *the* "
        "reference would be presenting a contested figure as a settled one, so this section "
        "exists to say that neither is used as an anchor.",
        "",
        *table(
            ["Claim", "Where", "Printed", "What this project computes", "Validation row"],
            [
                [
                    "Best-case total downlink loss",
                    "§4.2.1",
                    "20 dB",
                    "19.09 dB from their own parameters",
                    "[`ntanos2021.best-case-total-loss`](../validation.md) - **compatible**, and "
                    "on the weakest form of compatibility the table has (a term unbounded "
                    "above)",
                ],
                [
                    "Peak single-pass key rate",
                    "§4.3.1",
                    "3.33e-4 secret bits per pulse",
                    "1.053e-3, which is 3.16x theirs; landing on their figure needs 24.07 dB of "
                    "loss",
                    "[`ntanos2021.single-pass-peak-skr`](../validation.md) - **not reproduced**",
                ],
            ],
        ),
        "",
        "**The two printed claims are 4.07 dB apart from each other**, before this project is "
        "involved at all: their own §4.2.1 declares 20 dB as the best case, and their own "
        "§4.3.1 peak requires 24.07 dB under any decoy analysis that reproduces their "
        "Appendix A. Whichever of the two this project is wrong about, they cannot both be "
        "right.",
        "",
        "**So: neither is an anchor.** Both rows are in `docs/validation.md` with their "
        "tolerances and their derivations, one labelled *compatible* and one labelled *not "
        "reproduced*, and this project's numbers are traced to the ITU-R recommendations and "
        "to Lim et al. 2014 instead. If a comparison with 'the Ntanos link' is asked for, the "
        "first question is **which one**.",
        "",
    ]


def _limits(
    result: SimulationResult,
    altitude: list[dict[str, Any]],
    stations: list[tuple[Any, float, list[dict[str, Any]]]],
) -> tuple[Limit, ...]:
    declared_m = result.scenario.stations[0].altitude_m
    at_sea = _pick(altitude, **{"stations.0.altitude_m": SEA_LEVEL_M})[FINITE]
    at_declared = _pick(altitude, **{"stations.0.altitude_m": declared_m})[FINITE]
    biggest = max(
        abs(
            _pick(rows, **{"stations.0.altitude_m": declared})[FINITE]
            - _pick(rows, **{"stations.0.altitude_m": SEA_LEVEL_M})[FINITE]
        )
        for _, declared, rows in stations
    )
    return (
        Limit(
            gap=21,
            title="**Aperture averaging follows ITU-R P.1622's convention, not Ntanos et al.'s.** "
            "P.1622 Eq. (8) multiplies the log-variance by `A`; Ntanos Eq. (14) defines `A` as a "
            "ratio of scintillation indices. They agree to first order for small variance and "
            "not otherwise, and nothing settles the saturated regime.",
            cost="**-3.29 % of the day in the `weak` regime and -1.66 % saturated**, and it "
            "decides the **sign** of section 4's altitude term: the saturated term is -206 bits "
            "here and +4 bits of 449 308 under the other convention, so it lands entirely "
            f"inside the gap. On this reference station the term is {signed(at_declared - at_sea)} "
            f"bits; the largest of the three Ntanos stations' is {bits(biggest)} bits, and the "
            "same uncertainty of convention applies to all of them.",
            reference="`tests/e2e/test_reference_scenarios.py::TestWhatTheApertureAveragingConventionCosts`",
        ),
        Limit(
            gap=14,
            title="**No open source publishes a zenith atmospheric transmittance at 1550 nm**, "
            "and Ntanos et al.'s Eq. (7) raises exactly that number to the air mass -- making "
            "it the most load-bearing atmospheric quantity in their budget, and one they never "
            "state.",
            cost="This scenario declares `zenith_transmittance: 1.0`, which is 'no extinction "
            "modelled' said out loud rather than a value invented. The day above is therefore "
            "an **upper bound** on the atmospheric side. Measured elsewhere on the same day: "
            "0.230 dB of zenith extinction -- the cleanest air in the ITU's weather code table "
            "-- costs **22.7 % of the certified key**.",
            reference="`docs/adr/0023-traceable-extinction.md`, `LAST_CHANGES.md` §38",
        ),
        Limit(
            gap=22,
            title="**The aerosol scale height has no published value** and the visibility law "
            "carries molecular scattering at the aerosol exponent.",
            cost="Nothing on this day, because this scenario declares no visibility at all "
            "(see the row above). It becomes the dominant uncertainty the moment an extinction "
            "is modelled: a factor of 1.67 in optical depth, 0.230 against 0.384 dB at 23 km of "
            "visibility and 1550 nm.",
            reference="`docs/adr/0023-traceable-extinction.md`",
        ),
        Limit(
            gap=None,
            title="**Clouds are not modelled here.** `cloud_fraction` is null, so every pass "
            "above the mask is assumed to be a pass with a clear line of sight.",
            cost="Unpriced in this document, and large. The machinery exists "
            "(`system/pcflos.py`, `system/multi_ogs.py`) and is not switched on in this "
            "scenario: measured on the same day with two terminals, cloud diversity buys 2.30 "
            "times the key of Castelldefels alone, which is another way of saying a single "
            "clear-sky day is not a typical day.",
            reference="`docs/adr/0013-cloud-availability-and-station-aggregation.md`, "
            "`LAST_CHANGES.md` §29",
        ),
    )


SPEC = DossierSpec(
    identifier="reference-link",
    subtitle="the day every number in this project is measured on",
    scenario_name="reference_castelldefels",
    scenario_path="scenarios/reference_castelldefels.yaml",
    document_path="docs/experiments/reference-link.md",
    body=build,
)
"""The reference-link dossier."""
