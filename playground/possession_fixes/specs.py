"""Fixed physical-control and collective-stoppage hypotheses."""

from dataclasses import dataclass, replace

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class FixSpec(ExperimentSpec):
    control_mode: str = "arrival"
    physical_initialization: bool = False
    collective: str = "none"


BASELINE = FixSpec(
    id="p00_original_baseline",
    parent_id="",
    title="Original step 05 baseline",
    changed_component="reference",
    hypothesis="Reproduce the original baseline independently.",
    rationale="Check against a separate step 05 invocation.",
)
R06 = replace(
    BASELINE,
    id="p01_r06_reference",
    parent_id=BASELINE.id,
    title="Previous r06 reference",
    changed_component="reference_anchor",
    hypothesis="Reproduce the earlier interception and occlusion predictor.",
    rationale="Reference anchor; not a one-component change from step 05.",
)
ANCHOR = replace(
    R06,
    id="p02_f03_reference",
    parent_id=R06.id,
    title="Current f03 uncertainty-gap reference",
    changed_component="reference_anchor",
    hypothesis="Reproduce the current strongest public spellF1 candidate.",
    rationale=(
        "Run existing r06, classify uncertainty, and join supported same-team gaps."
    ),
)
GATE = replace(
    ANCHOR,
    id="p03_physical_gate",
    parent_id=ANCHOR.id,
    title="Require physical proximity for forecast-based control",
    changed_component="control_candidate_gate",
    hypothesis=(
        "Winning a projected interception race does not establish current control."
    ),
    rationale=(
        "Reject arrival-based candidates unless the selected team is within two "
        "actual metres and at least 0.5 m closer than the opponent. Keep the "
        "existing incumbent, confirmation, smoothing, and gap handling."
    ),
    control_mode="gate",
)
PHYSICAL = replace(
    ANCHOR,
    id="p04_physical_candidates",
    parent_id=ANCHOR.id,
    title="Use physical proximity for control confirmation",
    changed_component="control_candidate_geometry",
    hypothesis=(
        "Observed proximity may identify current control better than future arrival."
    ),
    rationale=(
        "Replace only control-candidate distances with original pitch distances. "
        "Keep arrival-nearest initialization and the existing speed and duration rules."
    ),
    control_mode="physical",
)
INITIALIZATION = replace(
    PHYSICAL,
    id="p05_physical_initialization",
    parent_id=PHYSICAL.id,
    title="Use physical nearest-team observations for initialization",
    changed_component="incumbent_initialization",
    hypothesis="A forecast-nearest fallback can start possession on the wrong team.",
    rationale=(
        "Feed original nearest-team codes into incumbent initialization and "
        "observation-gap handling; retain physical control confirmation."
    ),
    physical_initialization=True,
)
SEEDS = replace(
    ANCHOR,
    id="p06_collective_seeds",
    parent_id=ANCHOR.id,
    title="Detect sustained collective slowdown with an uncontrolled ball",
    changed_component="collective_stoppage_entry",
    hypothesis="Players may stop after a foul while the ball continues rolling.",
    rationale=(
        "Require two seconds of at least eight visible players with median speed "
        "at most 1.5 m/s and a visible in-pitch ball beyond two metres from every "
        "player, moving no faster than 12 m/s. Inject qualifying seed runs as D."
    ),
    collective="seeds",
)
HOLD = replace(
    SEEDS,
    id="p07_collective_hold",
    parent_id=SEEDS.id,
    title="Retain collective stoppages until supported restart motion",
    changed_component="collective_stoppage_retention",
    hypothesis="Retrieving a ball after a stoppage need not restore live possession.",
    rationale=(
        "Hold a confirmed collective seed through uncertainty, up to 20 seconds. "
        "Release on 0.4 seconds of observed physical control, in-pitch ball motion "
        "at least 2 m/s, and either renewed collective movement or ball speed "
        "at least 8 m/s. Motion above 45 m/s is not release evidence."
    ),
    collective="hold",
)
GATE_HOLD = replace(
    HOLD,
    id="p08_gate_and_hold",
    parent_id=HOLD.id,
    title="Physical control gate with collective stoppage retention",
    changed_component=GATE.changed_component,
    hypothesis=(
        "Physical ownership checks and stoppage detection may complement each other."
    ),
    rationale=GATE.rationale,
    control_mode="gate",
)
PHYSICAL_HOLD = replace(
    HOLD,
    id="p09_physical_and_hold",
    parent_id=HOLD.id,
    title="Physical control candidates with collective stoppage retention",
    changed_component=PHYSICAL.changed_component,
    hypothesis=(
        "Physical control candidates may complement collective stoppage retention."
    ),
    rationale=PHYSICAL.rationale,
    control_mode="physical",
)
INITIALIZATION_HOLD = replace(
    PHYSICAL_HOLD,
    id="p10_initialization_and_hold",
    parent_id=PHYSICAL_HOLD.id,
    title="Physical initialization and control with collective stoppages",
    changed_component=INITIALIZATION.changed_component,
    hypothesis=(
        "Physical initialization may avoid unsupported ownership after stoppages."
    ),
    rationale=INITIALIZATION.rationale,
    physical_initialization=True,
)

FIX_EXPERIMENTS = (
    BASELINE,
    R06,
    ANCHOR,
    GATE,
    PHYSICAL,
    INITIALIZATION,
    SEEDS,
    HOLD,
    GATE_HOLD,
    PHYSICAL_HOLD,
    INITIALIZATION_HOLD,
)
