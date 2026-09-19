"""``docs/experiments/GE-0b.md``: what two metres of optical bench can and cannot check.

What GE-0b is
-------------
Two metres of optical bench with a turbulence emulator in the middle, tuned so
that its plane-wave Rytov variance equals that of GE-1's kilometre of moderate
air. It is the cheap rehearsal for the field link, and the whole value of this
document is in stating precisely which of GE-1's questions it rehearses.

Why it needs a document of its own
-----------------------------------
Because the honest answer is *fewer than it looks*, and the two reasons are of
different kinds. One is outside anything this project computes -- an emulator
produces a phase screen and not a ``C_n^2``, and a screen needs propagation
distance behind it to turn phase into amplitude. The other is **inside** the
model and is large, and it is the one that would otherwise be discovered after
a purchase order: aperture averaging depends on how far away the turbulence is,
so a bench that matches the Rytov variance exactly can still leave its receiver
seeing a different world.

This module runs both scenarios -- GE-0b as given, and GE-1 from
:func:`~quoss.scenario.defaults.ge1_two_terminals` -- and puts the two results
side by side. It computes no physics; the boundary is in
:mod:`quoss.dossier.base`.
"""

from __future__ import annotations

from quoss.core.errors import DegradationLog
from quoss.dossier.base import (
    DossierSpec,
    Limit,
    bits,
    limits_section,
    logged_codes_section,
    number,
    table,
    times,
)
from quoss.dossier.base import run_horizontal as _run_horizontal
from quoss.scenario.defaults import ge1_two_terminals
from quoss.scenario.hash import scenario_hash
from quoss.scenario.models import AnyScenario, HorizontalScenario
from quoss.scenario.result import HorizontalResult

__all__ = ["SPEC", "build"]

QUESTION_FOR_THE_MANUFACTURER = (
    "What D/r_0 does the emulator reach, what Rytov number, and with how many phase screens "
    "and what relay optics between them? We need the three set independently, not a single "
    "equivalent C_n^2."
)
"""The line to paste into an email, and the reason this document exists at all.

Written out as a constant rather than inline so that ``tests/dossier`` can
assert the document contains it verbatim: a question that drifts from the one
this project can defend is worse than no question, because a vendor will answer
the one that was asked.
"""


def build(scenario: AnyScenario, log: DegradationLog) -> list[str]:
    """Return the body of ``docs/experiments/GE-0b.md``."""
    _, bench = _run_horizontal(scenario, degradations=log, what="GE-0b")
    field_scenario, field = _run_horizontal(
        ge1_two_terminals(), degradations=log, what="GE-1, which this document compares against"
    )

    lines: list[str] = []
    lines += _what_it_decides(field_scenario)
    lines += _side_by_side(bench, field)
    lines += _the_half_inside_the_model(bench, field)
    lines += _the_half_outside_the_model(bench)
    lines += _the_email(bench)
    lines += logged_codes_section(log)
    lines += [""]
    lines += limits_section(_limits(bench, field))
    return lines


def _what_it_decides(field_scenario: HorizontalScenario) -> list[str]:
    return [
        "## What this document is for",
        "",
        "GE-0b is two metres of optical bench with a turbulence emulator, tuned so that its "
        "plane-wave Rytov variance equals that of GE-1's kilometre of moderate air. This "
        "document is what somebody reads before lending the bench, buying the emulator, or "
        "planning what the bench run will be reported as having shown.",
        "",
        "**The short answer: the bench answers a real question, and it is not the question it "
        "looks like it is answering.** Two things separate it from the field link. One is "
        "outside anything this project models and can only be argued; the other is inside the "
        "model, is large, and is measured below.",
        "",
        "Both scenarios are run to produce this document. GE-1 is taken from "
        "`quoss.scenario.defaults.ge1_two_terminals`, the same versioned builder "
        "`scenarios/ge1_1km.yaml` is asserted equal to, at hash "
        f"`{scenario_hash(field_scenario)}`.",
        "",
    ]


def _side_by_side(bench: HorizontalResult, field: HorizontalResult) -> list[str]:
    b, f = bench.budget, field.budget
    bs, fs = bench.session, field.session
    rows = [
        [
            "Path length",
            number(bench.scenario.path.path_length_m),
            number(field.scenario.path.path_length_m),
            "m",
            "what the bench is standing in for.",
        ],
        [
            "C_n^2",
            number(bench.scenario.path.cn2_m23),
            number(field.scenario.path.cn2_m23),
            "m^-2/3",
            "the emulator setting that makes the two Rytov variances equal.",
        ],
        [
            "Declared wave form",
            str(bench.scenario.path.wave.value),
            str(field.scenario.path.wave.value),
            "-",
            "which closed form describes the beam over this path. Set by the distance in "
            "Rayleigh ranges, not by preference.",
        ],
        [
            "Plane-wave Rytov variance",
            number(b.rytov_variance_np2),
            number(f.rytov_variance_np2),
            "Np^2",
            "**matched, to machine precision.** This is what 'equivalent' was made to mean, "
            "and it is a reference figure for a point receiver.",
        ],
        [
            "Aperture averaging A",
            number(b.aperture_averaging),
            number(f.aperture_averaging),
            "1",
            "how much of that variance the 10 cm lens removes. **Not matched, and not close.**",
        ],
        [
            "Log-irradiance variance at the receiver",
            number(b.log_irradiance_variance_np2),
            number(f.log_irradiance_variance_np2),
            "Np^2",
            "what the detector actually sees. **Not simply the two rows above multiplied** -- "
            "see the note under this table.",
        ],
        [
            "Scintillation fade at 1 % outage",
            number(b.scintillation_db),
            number(f.scintillation_db),
            "dB",
            "the margin the receiver has to budget for turbulence.",
        ],
        [
            "Total loss",
            number(b.total_db),
            number(f.total_db),
            "dB",
            "everything. The bench is two metres long, so its geometric term is tiny.",
        ],
        [
            "Certified key, declared session",
            bits(bs.finite_bits),
            bits(fs.finite_bits),
            "bits",
            "not comparable as a figure of merit: the bench is short, not better.",
        ],
    ]
    bench_product = b.aperture_averaging * b.rytov_variance_np2
    field_product = f.aperture_averaging * f.rytov_variance_np2
    return [
        "## 1. The two links side by side",
        "",
        *table(["Quantity", "GE-0b (bench)", "GE-1 (field)", "Unit", "What it means here"], rows),
        "",
        "**One note on the arithmetic of the last three rows, because the obvious reading of "
        "them is wrong.** The Rytov row is the **plane-wave** variance, which is the reference "
        "figure the two links were tuned to match and the one the weak-theory limit is defined "
        "against. What the detector sees is `A` times the point variance **of the declared "
        f"wave**. The bench declares `{bench.scenario.path.wave.value}`, so there the two do "
        f"multiply out: {number(b.aperture_averaging)} x {number(b.rytov_variance_np2)} = "
        f"{number(bench_product)} Np^2, which is its last row. GE-1 declares "
        f"`{field.scenario.path.wave.value}`, and the same product gives "
        f"{number(field_product)} against the {number(f.log_irradiance_variance_np2)} it "
        f"actually reports -- a further factor of "
        f"{times(field_product, f.log_irradiance_variance_np2)}, which is the ratio between "
        "the plane and spherical closed forms and not an error. Anything recovering `A` by "
        "dividing one reported variance by the other is right on the bench and silently off "
        "by that factor in the field, which is why `A` is carried as a number of its own. "
        "Asserted in `tests/e2e/test_horizontal_scenario.py::TestTheHorizontalEngineAddsNothing"
        "::test_the_three_marks_the_result_carries_are_the_physics_functions_values`.",
        "",
    ]


def _the_half_inside_the_model(bench: HorizontalResult, field: HorizontalResult) -> list[str]:
    b, f = bench.budget, field.budget
    variance_ratio = times(f.log_irradiance_variance_np2, b.log_irradiance_variance_np2)
    averaging_ratio = times(f.aperture_averaging, b.aperture_averaging)
    fade_gap = f.scintillation_db - b.scintillation_db
    return [
        "## 2. The half that is inside the model, and it is large",
        "",
        "Read the Rytov and aperture-averaging rows of that table together. The **Rytov "
        "variance** is what "
        "a point detector would see, and the bench matches GE-1's to machine precision -- "
        f"{number(b.rytov_variance_np2)} against {number(f.rytov_variance_np2)} Np^2. That is "
        "the whole of what tuning `C_n^2` achieves.",
        "",
        "What reaches the key is not that. It is the **aperture-averaged** variance, and "
        "aperture averaging depends on how far away the turbulence is: a path of length `L` "
        "makes speckles of about `sqrt(lambda L)` across, and a lens averages over however many "
        "of them it covers. Two metres of path makes speckles a hundredth the size of those a "
        "kilometre makes, so the same 10 cm lens averages a hundred times more of them away.",
        "",
        f"Measured: the averaging factor is {number(b.aperture_averaging)} on the bench against "
        f"{number(f.aperture_averaging)} in the field, a factor of **{averaging_ratio}**, and "
        f"the variance that actually reaches the receiver is **{variance_ratio} times smaller "
        "on the bench**. Those two factors are not the same number, and the difference is the "
        "plane-to-spherical ratio of the note under the table, not a rounding: the bench is "
        "further ahead on averaging than it is on what the detector sees, because the two "
        f"links declare different wave forms. In the budget it comes to "
        f"{number(b.scintillation_db)} dB of scintillation fade against "
        f"{number(f.scintillation_db)} dB -- **{number(fade_gap)} dB less margin to survive**.",
        "",
        "**What this decides.** A bench tuned this way does **not** rehearse the scintillation "
        "GE-1's receiver will have to survive, for a reason that has nothing to do with phase "
        "screens and everything to do with geometry. It is still worth building: it rehearses "
        "the optics, the alignment, the detector chain, the electronics and the protocol stack "
        "end to end, and those are most of what goes wrong first. It does not rehearse the "
        "fade. If the bench run is reported as having demonstrated resilience to GE-1's "
        f"turbulence, that report is wrong by {number(fade_gap)} dB and the error is in the "
        "optimistic direction.",
        "",
    ]


def _the_half_outside_the_model(bench: HorizontalResult) -> list[str]:
    return [
        "## 3. The half that is outside the model, and can only be argued",
        "",
        f"The bench's `C_n^2` of {number(bench.scenario.path.cn2_m23)} "
        "m^-2/3 is five orders of magnitude above the strongest turbulence anybody measures "
        "outdoors. That is not a mistake: it is what `equivalent_bench_cn2_m23` returns, because "
        "the Rytov variance goes as `L^(11/6)` and two metres has to make up for a kilometre.",
        "",
        "But **an emulator does not produce a `C_n^2` over a length.** It produces a **phase "
        "screen** with a given Fried parameter `r_0`. Scintillation is phase distortion "
        "converted into amplitude *by propagation*, so a screen needs distance behind it: one "
        "screen at the start of a two-metre bench has two metres in which to develop what a "
        "kilometre of distributed air develops continuously. Laboratory practice for deep "
        "turbulence is therefore several screens with relay optics between them, so that "
        "`r_0`, the isoplanatic angle and the Rytov number can be set independently.",
        "",
        "QuOSS models Kolmogorov turbulence **given** a `C_n^2`; it does not model phase "
        "screens. So the equivalent `C_n^2` above is a **necessary and not a sufficient** "
        "condition, and this project cannot tell you how many screens make it sufficient.",
        "",
    ]


def _the_email(bench: HorizontalResult) -> list[str]:
    return [
        "## 4. The question to put to the manufacturer",
        "",
        "**Do not ask** whether the emulator reaches "
        f"`C_n^2 = {number(bench.scenario.path.cn2_m23)} m^-2/3`. A vendor can answer yes to "
        "that question with one screen, honestly, and the answer will not tell you what you "
        "need to know. Ask this instead, verbatim:",
        "",
        "> " + QUESTION_FOR_THE_MANUFACTURER,
        "",
        "And add the acceptance criterion this document supplies, which is the one the vendor "
        "cannot be expected to guess:",
        "",
        "> The receiving aperture in our field link is 10 cm at 1 km. We need the emulator "
        "> placed so that the aperture-averaged scintillation at the detector matches the "
        "> field value, not only the point-receiver Rytov variance -- see the measured factor "
        "> in section 2.",
        "",
        "**What this decides:** whether the quotation being compared is for the instrument that "
        "answers the question, or for a cheaper one that answers a different question equally "
        "well.",
        "",
    ]


def _limits(bench: HorizontalResult, field: HorizontalResult) -> tuple[Limit, ...]:
    b, f = bench.budget, field.budget
    return (
        Limit(
            gap=20,
            title="**A turbulence emulator is not a `C_n^2`.** A phase screen needs propagation "
            "distance behind it to turn phase into amplitude; this project models no screens, "
            "and takes `C_n^2` as its input.",
            cost="The whole of section 3, unpriced because it is outside the model. The half "
            "that **is** inside the model is priced in section 2: "
            f"{times(f.log_irradiance_variance_np2, b.log_irradiance_variance_np2)} times less "
            f"variance at the receiver and {number(f.scintillation_db - b.scintillation_db)} dB "
            "less fade to budget.",
            reference="`tests/e2e/test_horizontal_scenario.py::TestTheBenchIsTheOtherFile::"
            "test_matching_the_rytov_variance_does_not_match_what_the_receiver_sees`",
        ),
        Limit(
            gap=21,
            title="**Aperture averaging follows ITU-R P.1622's convention, not Ntanos et al.'s.** "
            "The two definitions of `A` differ once the variance is not small, and no source "
            "settles which applies.",
            cost="The factor of "
            f"{times(f.aperture_averaging, b.aperture_averaging)} between the two aperture "
            "averagings of section 2 is computed under one convention throughout, so the "
            "**comparison** is convention-independent in sign and not in magnitude. On the "
            "reference downlink the same choice decides the sign of a published term: the "
            "station-altitude term lands at +4 bits of 449 308 under the other convention. "
            "Never priced for a horizontal path.",
            reference="`tests/e2e/test_reference_scenarios.py::TestWhatTheApertureAveragingConventionCosts`",
        ),
        Limit(
            gap=18,
            title="**The Gaussian beam wave is not implemented.** The bench is declared "
            "`wave: plane` and the field link `wave: spherical`; neither describes a real "
            "collimated beam.",
            cost="Here the choice is easy and the gap is narrow: two metres is "
            f"{number(bench.scenario.path.path_length_m / b.rayleigh_range_m)} Rayleigh ranges "
            "of the transmitter, so the beam is genuinely collimated and the plane wave is the "
            "right idealisation. On GE-1's kilometre it is not easy, and the band there is the "
            "cost -- see `GE-1.md` sections 3 and 5.",
            reference="`docs/adr/0021-horizontal-path.md`, `GE-1.md`",
        ),
        Limit(
            gap=23,
            title="**Molecular absorption has no number in any open source.**",
            cost="Nothing measurable over two metres: the bench declares "
            f"{number(b.extinction_db_per_km)} dB/km of extinction, which is a statement about "
            "a closed enclosure rather than a missing value, and even a dusty room would be a "
            "few ten-thousandths of a decibel over this path. The gap belongs to GE-1, not to "
            "the bench.",
            reference="`GE-1.md` section 7",
        ),
    )


SPEC = DossierSpec(
    identifier="GE-0b",
    subtitle="two metres of bench, and which of GE-1's questions it answers",
    scenario_name="ge0b_bench",
    scenario_path="scenarios/ge0b_bench.yaml",
    document_path="docs/experiments/GE-0b.md",
    body=build,
)
"""The GE-0b dossier."""
