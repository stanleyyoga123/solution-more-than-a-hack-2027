"""Predeclared independent branches around the earlier control baseline."""

from dataclasses import dataclass, replace

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class CreativeSpec(ExperimentSpec):
    method: str = "baseline"


BASELINE = CreativeSpec(
    id="c00_original_baseline",
    parent_id="",
    title="Original step 05 reference",
    changed_component="reference",
    hypothesis="Reproduce the unmodified nearest-player baseline.",
    rationale="The same nearest-team codes and centred 50-frame team-only vote.",
)
CONTROL = CreativeSpec(
    id="c01_control_reference",
    parent_id="c00_original_baseline",
    title="Earlier e05 control-confirmation reference",
    changed_component="reference_anchor",
    hypothesis="Reproduce the earlier control baseline before branching.",
    rationale=(
        "This reference includes the previously declared e01-e05 components; "
        "it is an anchor, not a claim of a single new component versus c00."
    ),
    three_class_vote=True,
    bounded_gap_fill=True,
    boundary_dead=True,
    stationary_dead=True,
    control_confirmation=True,
    method="control",
)


def _branch(
    identifier: str, title: str, method: str, hypothesis: str, rationale: str
) -> CreativeSpec:
    return replace(
        CONTROL,
        id=identifier,
        parent_id=CONTROL.id,
        title=title,
        changed_component=method,
        hypothesis=hypothesis,
        rationale=rationale,
        method=method,
    )


CREATIVE_EXPERIMENTS = (
    BASELINE,
    CONTROL,
    _branch(
        "c02_causal_ball_forecast",
        "Forecast missing ball observations from past motion",
        "causal_forecast",
        "Brief ball disappearance may be reconstructed from its previous velocity.",
        "Use 0.2 seconds of continuous original context and forecast at most "
        "0.5 seconds; reject context speeds over 45 m/s. Keep the control decoder.",
    ),
    _branch(
        "c03_bidirectional_ball_bridge",
        "Reconcile past and future ball motion across gaps",
        "bidirectional_bridge",
        "Offline endpoint agreement can support more missing-ball reconstruction.",
        "Bridge original bounded gaps of at most two seconds only when both "
        "constant-velocity endpoint predictions agree within five metres and "
        "the entire linear bridge stays within the 45 m/s speed bound.",
    ),
    _branch(
        "c04_viterbi_states",
        "Replace the temporal algorithm with a three-state Viterbi decoder",
        "viterbi",
        "Global state inference can balance local evidence and transition costs.",
        "Decode five evidence bins per second with H/A/D emissions, a fixed "
        "team-transfer cost of four and live/dead transition cost of two; "
        "expand decoded bins to the source timeline without a final vote.",
    ),
    _branch(
        "c05_interception_race",
        "Replace proximity with an anticipated interception race",
        "interception",
        "The team likely to reach the moving ball may differ from the nearest team.",
        "Project the ball 0.3 seconds along observed velocity and estimate "
        "player arrival times at seven metres per second, accounting for current "
        "player motion. Keep the existing control decoder and stoppage logic.",
    ),
    _branch(
        "c06_collective_ball_estimate",
        "Estimate missing ball locations from collective team geometry",
        "collective",
        "Team shape can provide a ball-location proxy without possession labels.",
        "Fit a fixed-penalty ridge regression on clean observed balls in the "
        "first 80% of the recording. Evaluate against observed balls in the last "
        "20%; fill only missing observations with in-distribution geometry. "
        "Report spatial prediction errors separately from possession scores.",
    ),
    _branch(
        "c07_yolo_ball_recovery",
        "Recover missing ball observations from original tactical footage",
        "vision",
        "Image evidence may recover balls absent from the supplied tracker.",
        "Use a fixed pretrained sports-ball detector and geometric/temporal "
        "acceptance checks. Preserve original observations and reuse the same "
        "control decoder; detector settings and sampling are recorded separately.",
    ),
)
