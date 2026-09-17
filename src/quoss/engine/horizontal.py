"""One stationary link in, one result out: the horizontal half of the engine.

What this module is for, for someone arriving new
-------------------------------------------------
:mod:`quoss.engine.pipeline` runs a satellite: it propagates an orbit, finds
passes, evaluates the channel at every in-pass second, and integrates a key over
each pass and each day. None of that applies to a **bench** or to a link between
two points on the ground a kilometre apart. There is no orbit, so no pass, so no
day; the geometry does not change, so there is no time axis to integrate over;
and the turbulence is one constant instead of an integral over height.

What is left is short enough to read in one screen, and that is the point of
having it separate: a horizontal run is one loss budget, one noise budget, one
set of link conditions and one finite-key block. This module does exactly that,
calling the same physics functions a person would call by hand -- the claim
``tests/e2e/test_horizontal_scenario.py`` checks by exact float equality against
an oracle wired term by term, as ``tests/e2e/test_reference_scenarios.py`` does
for the downlink.

The block, and why it needed an ADR
-----------------------------------
``docs/adr/0011-the-block-is-the-pass.md`` decided that the block a finite-key
bound is evaluated over is a **pass**, and the argument was that the geometry
fixes it: between two passes the satellite is below the horizon and not one
pulse is sent, so a pass is not a choice anybody makes.

Here the link is stationary and nothing stops the data, so the block is whatever
the operator declares -- :attr:`~quoss.scenario.models.SessionSpec.duration_s`.
That moves the responsibility for the bound being valid from the schema to the
person writing the file, and
``docs/adr/0024-the-horizontal-scenario.md`` says what they are promising.
:func:`simulate_horizontal` records an ``INFO`` naming the declared block and
its pulse count on every run, so a result never carries the number without the
statement behind it.

What it does not do, stated rather than approximated
----------------------------------------------------
No Monte Carlo (``system/monte_carlo.py`` draws a *pass*'s fading with a
correlation time against a changing geometry; a stationary link's ensemble is a
different question and has no module yet), no cloud availability, no aggregation
over terminals, no relay. A horizontal scenario has nowhere to ask for any of
them, which is the schema making the absence visible rather than this module
silently skipping a stage.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from quoss.channel.horizontal import (
    horizontal_log_irradiance_variance,
    horizontal_loss_budget,
    plane_wave_rytov_variance,
)
from quoss.channel.link_budget import LossBudget, NoiseBudget, downlink_noise_budget
from quoss.channel.pointing import beam_to_jitter_ratio
from quoss.core.errors import DegradationLog, ScenarioError
from quoss.qkd.base import KeyRate, LinkConditions
from quoss.qkd.finite_key import FiniteKeyResult, expected_block_counts, secret_key_length
from quoss.scenario.models import HorizontalScenario
from quoss.scenario.result import (
    HorizontalBudgetResults,
    HorizontalResult,
    HorizontalSessionResults,
    Provenance,
)
from quoss.system.key_volume import SYMMETRIC_KEY_BASIS_PROBABILITY, decoy_settings_from_protocol

from .profiling import StageTimer

__all__ = ["HORIZONTAL_STAGES", "HorizontalSimulation", "simulate_horizontal"]

_WHERE = "quoss.engine.horizontal"

HORIZONTAL_STAGES: tuple[str, ...] = ("channel", "key", "result")
"""The stages a horizontal run times, in order.

Three where the downlink has seven. The four that are missing -- ``orbit``,
``geometry``, ``passes``, ``series`` -- are missing because there is no orbit,
and a stage reported as taking zero seconds would read as one that ran fast.
"""


@dataclass(frozen=True, slots=True)
class HorizontalSimulation:
    """The result plus the physics objects behind it.

    What :class:`~quoss.engine.pipeline.Simulation` is for a downlink: the way
    to reach the budgets and the finite-key terms without re-running, which is
    what the end-to-end tests compare against the hand-wired chain.

    Parameters
    ----------
    result : HorizontalResult
        The result.
    loss : LossBudget
        The loss budget as :mod:`quoss.channel.link_budget` assembled it, with
        its arrays of shape ``()``.
    noise : NoiseBudget
        The noise budget.
    conditions : LinkConditions
        What the channel delivers, as the protocol reads it.
    finite : FiniteKeyResult
        Every term of Lim et al. equation (1), so a zero can be explained.
    asymptotic : KeyRate
        The same link with an infinite block.
    """

    result: HorizontalResult
    loss: LossBudget
    noise: NoiseBudget
    conditions: LinkConditions
    finite: FiniteKeyResult
    asymptotic: KeyRate


def _require_horizontal(scenario: object) -> None:
    if not isinstance(scenario, HorizontalScenario):
        raise ScenarioError(
            "simulate_horizontal expects a quoss.scenario.models.HorizontalScenario, got "
            f"{type(scenario).__name__}. A downlink goes to quoss.engine.pipeline.simulate; "
            "quoss.engine.pipeline.run dispatches on the scenario's link field and takes either."
        )


def simulate_horizontal(
    scenario: HorizontalScenario, *, degradations: DegradationLog
) -> HorizontalSimulation:
    """Run one horizontal scenario and return the result with the objects behind it.

    The five steps, which are the four-call recipe of
    ``docs/adr/0021-horizontal-path.md`` plus the finite-key bound:

    1. **The extinction**, resolved from whichever of the two ways the scenario
       declared it (:meth:`~quoss.scenario.models.HorizontalPathSpec.extinction_db_per_km_at`).
       A declared number goes through the same call and comes back unchanged.
    2. **The loss budget**, :func:`~quoss.channel.horizontal.horizontal_loss_budget`:
       geometry, extinction, pointing and scintillation, assembled by the same
       private function the downlink's budget uses, so the two cannot add their
       terms differently.
    3. **The noise budget**, :func:`~quoss.channel.link_budget.downlink_noise_budget`.
       Its name says "downlink" and it is the right function here, because it has
       **no geometry inside it**: it takes a radiance, an aperture, a field of
       view, a filter and a gate, and none of those cares what brought the light.
       On a closed bench the radiance is zero and the background term is exactly
       zero with it.
    4. **The link conditions**, and from them the asymptotic key rate, which is
       reported beside the certified figure and never instead of it.
    5. **The block**, which is the declared session: ``pulse_rate_hz *
       duration_s`` pulses through :func:`~quoss.qkd.finite_key.expected_block_counts`
       and :func:`~quoss.qkd.finite_key.secret_key_length`, once.

    Parameters
    ----------
    scenario : HorizontalScenario
        The validated inputs.
    degradations : DegradationLog
        Receives every entry of the run, including the ``INFO`` that names the
        declared block.

    Returns
    -------
    HorizontalSimulation
        The result and the objects behind it.

    Raises
    ------
    ScenarioError
        If ``scenario`` is not a :class:`~quoss.scenario.models.HorizontalScenario`.
    DomainError
        If a physics function refuses its inputs.

    Examples
    --------
    >>> from quoss.core.errors import DegradationLog
    >>> from quoss.scenario.defaults import ge1_two_terminals
    >>> run = simulate_horizontal(ge1_two_terminals(), degradations=DegradationLog())
    >>> round(run.result.budget.total_db, 3)
    11.637
    >>> run.result.session.has_key
    True
    """
    _require_horizontal(scenario)
    timer = StageTimer()
    path = scenario.path
    transmitter = scenario.transmitter
    receiver = scenario.receiver
    protocol = scenario.protocol.to_protocol()
    security = scenario.security.to_security()

    with timer.stage("channel"):
        extinction = path.extinction_db_per_km_at(
            wavelength_m=transmitter.wavelength_m, degradations=degradations
        )
        loss = horizontal_loss_budget(
            path.path_length_m,
            wavelength_m=transmitter.wavelength_m,
            transmit_aperture_m=transmitter.aperture_m,
            receive_aperture_m=path.receive_aperture_m,
            cn2_m23=path.cn2_m23,
            extinction_db_per_km=extinction,
            wave=path.wave,
            pointing_jitter_rad=transmitter.pointing_jitter_rad,
            receiver_efficiency=receiver.chain_efficiency,
            degradations=degradations,
            outage_probability=path.outage_probability,
            static_loss_db=path.static_loss_db,
            transmit_truncation_ratio=transmitter.truncation_ratio,
            fade_combination=path.fade_combination,
            regime=path.scintillation_regime,
        )
        spec = scenario.protocol
        mean_photon_number = (
            spec.signal_probability * spec.signal_intensity
            + spec.decoy_probability * spec.decoy_intensity
        )
        noise = downlink_noise_budget(
            scenario.background.radiance_w_m2_um_sr(
                transmitter.wavelength_m, degradations=degradations
            ),
            wavelength_m=transmitter.wavelength_m,
            receive_aperture_m=path.receive_aperture_m,
            field_of_view_full_angle_rad=receiver.field_of_view_rad,
            filter_bandwidth_m=receiver.filter_bandwidth_m,
            gate_duration_s=receiver.gate_s,
            receiver_efficiency=receiver.chain_efficiency,
            dark_count_rate_cps=receiver.dark_count_rate_cps,
            degradations=degradations,
            detector_count=receiver.detector_count,
            afterpulse_probability=receiver.afterpulse_probability,
            signal_counts_per_gate=mean_photon_number * np.asarray(loss.transmittance),
        )
        conditions = LinkConditions(
            transmittance=loss.transmittance,
            noise_counts_per_gate=noise.total_per_gate,
            misalignment_error=spec.misalignment_error,
            pulse_rate_hz=transmitter.pulse_rate_hz,
            gate_duration_s=receiver.gate_s,
        )

    with timer.stage("key"):
        pulses = transmitter.pulse_rate_hz * scenario.session.duration_s
        degradations.info(
            "horizontal.block-is-the-declared-session",
            f"the finite-key block is the declared measurement session of "
            f"{scenario.session.duration_s} s, which is {pulses:.6g} pulses at "
            f"{transmitter.pulse_rate_hz:.6g} Hz. Unlike a pass (ADR 0011) nothing in the "
            "geometry fixes it: this length is a statement by whoever wrote the scenario that "
            "the link was stationary for that long, and the security parameters are per block "
            "(ADR 0024).",
            where=f"{_WHERE}.simulate_horizontal",
            session_duration_s=scenario.session.duration_s,
            pulses=float(pulses),
        )
        settings = decoy_settings_from_protocol(protocol)
        block = expected_block_counts(
            conditions,
            settings=settings,
            key_basis_probability=SYMMETRIC_KEY_BASIS_PROBABILITY,
            pulses=pulses,
        )
        finite = secret_key_length(
            block,
            settings=settings,
            security=security,
            error_correction_efficiency=protocol.error_correction_efficiency,
            degradations=degradations,
        )
        asymptotic = protocol.key_rate(conditions, degradations=degradations)

    with timer.stage("result"):
        # The two reported variances are recomputed rather than read out of the
        # budget, which does not return them. The second call uses a scratch log
        # whose entries are dropped -- and nothing is lost by that, because the
        # budget above made the identical call with the run's own log a moment
        # earlier, so every code the scratch log holds is already in
        # `degradations`. That is asserted, not assumed, by
        # tests/engine/test_horizontal.py::TestNothingIsDroppedWithTheScratchLog.
        scratch = DegradationLog()
        variance = float(
            horizontal_log_irradiance_variance(
                path.path_length_m,
                cn2_m23=path.cn2_m23,
                aperture_diameter_m=path.receive_aperture_m,
                wavelength_m=transmitter.wavelength_m,
                wave=path.wave,
                degradations=scratch,
                regime=path.scintillation_regime,
            )
        )
        gamma = float(
            beam_to_jitter_ratio(
                path.path_length_km,
                jitter_rad=transmitter.pointing_jitter_rad,
                wavelength_m=transmitter.wavelength_m,
                transmit_aperture_m=transmitter.aperture_m,
                receive_aperture_m=path.receive_aperture_m,
                degradations=scratch,
            )
        )
        rytov = float(
            plane_wave_rytov_variance(
                path.path_length_m,
                cn2_m23=path.cn2_m23,
                wavelength_m=transmitter.wavelength_m,
            )
        )
        budget = HorizontalBudgetResults(
            geometric_db=float(np.asarray(loss.geometric_db)),
            atmospheric_db=float(np.asarray(loss.atmospheric_db)),
            pointing_db=float(np.asarray(loss.pointing_db)),
            scintillation_db=float(np.asarray(loss.scintillation_db)),
            fade_db=float(np.asarray(loss.fade_db)),
            receiver_chain_db=loss.receiver_chain_db,
            static_db=loss.static_db,
            total_db=float(np.asarray(loss.total_db)),
            transmittance=float(np.asarray(loss.transmittance)),
            extinction_db_per_km=extinction,
            log_irradiance_variance_np2=variance,
            rytov_variance_np2=rytov,
            beam_to_jitter_ratio=gamma,
        )
        session = HorizontalSessionResults(
            duration_s=scenario.session.duration_s,
            pulses=float(pulses),
            finite_bits=float(np.asarray(finite.length_bits)),
            asymptotic_bits=float(np.asarray(asymptotic.secure_per_pulse)) * float(pulses),
            qber=float(np.asarray(asymptotic.qber)),
            phase_error_rate=float(np.asarray(finite.phase_error_rate)),
            noise_counts_per_gate=float(np.asarray(noise.total_per_gate)),
            correctness=security.correctness,
            secrecy=security.secrecy,
        )
        if not session.has_key:
            degradations.info(
                "horizontal.session-without-key",
                "the session certifies no key at all. That is a result and not a failure: the "
                f"asymptotic rate over the same session is {session.asymptotic_bits:.6g} bits, "
                "so a study reporting the asymptotic figure would have counted it. The phase "
                f"error rate is {session.phase_error_rate:.6g}; at 0.5 the single-photon term "
                "vanishes entirely (ADR 0011).",
                where=f"{_WHERE}.simulate_horizontal",
                asymptotic_bits=session.asymptotic_bits,
                phase_error_rate=session.phase_error_rate,
            )
        provenance = Provenance.collect(scenario, seed=None, data_versions={})

    result = HorizontalResult(
        scenario=scenario,
        provenance=provenance,
        budget=budget,
        session=session,
        warnings=degradations.to_dicts(),
        timings=timer.timings(),
    )
    return HorizontalSimulation(
        result=result,
        loss=loss,
        noise=noise,
        conditions=conditions,
        finite=finite,
        asymptotic=asymptotic,
    )
