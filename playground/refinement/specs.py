"""A fixed graph of motion, control and missing-observation hypotheses."""

from dataclasses import dataclass, replace

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class RefinementSpec(ExperimentSpec):
    motion: str = "original"
    forecast: bool = False
    tolerant_control: bool = False
    occlusion_bridge: bool = False
    boundary_latch: bool = False


BASELINE = RefinementSpec(
    id="r00_original_baseline",
    parent_id="",
    title="Original step 05 baseline",
    changed_component="reference",
    hypothesis="Reproduce the original nearest-player submission.",
    rationale="Independent step 05 output must match this reference exactly.",
)
INTERCEPTION = RefinementSpec(
    id="r01_interception_reference",
    parent_id=BASELINE.id,
    title="Previous c05 interception reference",
    changed_component="reference_anchor",
    hypothesis="Reproduce the previous strongest possession-interval result.",
    rationale=(
        "This anchor combines earlier control rules and anticipated interception; "
        "it is not a one-component experiment relative to r00."
    ),
    three_class_vote=True,
    bounded_gap_fill=True,
    boundary_dead=True,
    stationary_dead=True,
    control_confirmation=True,
)
FORECAST = replace(
    INTERCEPTION,
    id="r02_forecast_interception",
    parent_id=INTERCEPTION.id,
    title="Add short causal forecasts to interception",
    changed_component="ball_forecast",
    hypothesis="The earlier forecasting and interception gains may complement each other.",
    rationale=(
        "Fill at most 0.5 seconds from 0.2 seconds of original continuous ball "
        "motion; recompute ball-dependent features and interception evidence."
    ),
    forecast=True,
)
ROBUST = replace(
    INTERCEPTION,
    id="r03_robust_velocity",
    parent_id=INTERCEPTION.id,
    title="Use robust causal motion estimates",
    changed_component="velocity_estimator",
    hypothesis="A trailing median can reduce noisy one-frame velocity effects.",
    rationale=(
        "Replace instantaneous ball/player velocity with a trailing 0.2-second "
        "median within the current observed run; retain the same arrival proxy."
    ),
    motion="robust",
)
REACHABLE = replace(
    ROBUST,
    id="r04_acceleration_reachability",
    parent_id=ROBUST.id,
    title="Race to the earliest reachable point on the ball trajectory",
    changed_component="arrival_model",
    hypothesis="Reaction and acceleration constraints may identify control better.",
    rationale=(
        "Use robust motion and test ball targets at 0.1-second steps through two "
        "seconds. Players react for 0.2 seconds, accelerate at 3 m/s² up to "
        "7 m/s, and control within one metre. Arrival seconds become equivalent metres."
    ),
    motion="reachability",
)
TOLERANT = replace(
    INTERCEPTION,
    id="r05_tolerant_control",
    parent_id=INTERCEPTION.id,
    title="Tolerate brief uncertainty while confirming control",
    changed_component="control_confirmation",
    hypothesis="One uncertain observation should not erase a developing handover.",
    rationale=(
        "Require the same 0.4 seconds of opposing evidence, allow at most "
        "0.12 seconds of consecutive uncertainty within a 0.8-second window, "
        "and reset on incumbent evidence or explicit dead play."
    ),
    tolerant_control=True,
)
OCCLUSION = replace(
    INTERCEPTION,
    id="r06_occlusion_bridge",
    parent_id=INTERCEPTION.id,
    title="Bridge same-team possession through pure ball occlusion",
    changed_component="occlusion_bridge",
    hypothesis="An occluded ball need not mean the match stopped.",
    rationale=(
        "Fill only D runs up to eight seconds, bounded by the same live team, "
        "with every ball observation missing and no restart or explicit dead cue."
    ),
    occlusion_bridge=True,
)
BOUNDARY = replace(
    INTERCEPTION,
    id="r07_boundary_persistence",
    parent_id=INTERCEPTION.id,
    title="Retain confirmed out-of-play evidence until a supported return",
    changed_component="boundary_state",
    hypothesis="Losing an out-of-play ball should not immediately restore possession.",
    rationale=(
        "Retain boundary-triggered D until 0.2 seconds of in-pitch movement or "
        "close team evidence; expire after 30 seconds without another boundary cue."
    ),
    boundary_latch=True,
)
FORECAST_ROBUST = replace(
    ROBUST,
    id="r08_forecast_robust",
    parent_id=FORECAST.id,
    title="Robust motion with causal ball forecasting",
    hypothesis="Robust arrival evidence may complement short reconstructed trajectories.",
    forecast=True,
)
FORECAST_TOLERANT = replace(
    TOLERANT,
    id="r09_forecast_tolerant",
    parent_id=FORECAST.id,
    title="Tolerant control with causal ball forecasting",
    hypothesis="Short forecasts and interruption-tolerant handovers may complement each other.",
    forecast=True,
)
FORECAST_BOUNDARY = replace(
    BOUNDARY,
    id="r10_forecast_boundary",
    parent_id=FORECAST.id,
    title="Boundary persistence with causal ball forecasting",
    hypothesis="An explicit restart state may separate forecast continuation from live play.",
    forecast=True,
)
FORECAST_ROBUST_TOLERANT = replace(
    TOLERANT,
    id="r11_forecast_robust_tolerant",
    parent_id=FORECAST_ROBUST.id,
    title="Tolerant control added to robust forecast interception",
    hypothesis="Combining input and control robustness may reduce fragmented possession.",
    motion="robust",
    forecast=True,
)
FORECAST_ROBUST_BOUNDARY = replace(
    BOUNDARY,
    id="r12_forecast_robust_boundary",
    parent_id=FORECAST_ROBUST.id,
    title="Boundary persistence added to robust forecast interception",
    hypothesis="Explicit out-of-play persistence may improve a more stable arrival model.",
    motion="robust",
    forecast=True,
)

REFINEMENT_EXPERIMENTS = (
    BASELINE,
    INTERCEPTION,
    FORECAST,
    ROBUST,
    REACHABLE,
    TOLERANT,
    OCCLUSION,
    BOUNDARY,
    FORECAST_ROBUST,
    FORECAST_TOLERANT,
    FORECAST_BOUNDARY,
    FORECAST_ROBUST_TOLERANT,
    FORECAST_ROBUST_BOUNDARY,
)
