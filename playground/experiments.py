"""Predeclared cumulative experiments, each changing one component."""

from dataclasses import replace

from .experiment_spec import ExperimentSpec

BASELINE = ExperimentSpec(
    id="e00_baseline",
    parent_id="",
    title="Step 05 baseline reproduction",
    changed_component="reference",
    hypothesis="Reproduce step 05 exactly before evaluating any change.",
    rationale=(
        "Use the same nearest-player team and centred +/-50-frame vote; "
        "dead-ball observations do not vote for either team."
    ),
)
THREE_CLASS = replace(
    BASELINE,
    id="e01_three_class_vote",
    parent_id=BASELINE.id,
    title="Allow dead-ball observations to vote",
    changed_component="three_class_vote",
    hypothesis="Counting D votes may preserve stoppages erased by team-only voting.",
    rationale="Use all three classes with deterministic H, A, D tie precedence.",
    three_class_vote=True,
)
MISSING_BRIDGE = replace(
    THREE_CLASS,
    id="e02_bounded_missing_bridge",
    parent_id=THREE_CLASS.id,
    title="Bridge short same-team observation gaps",
    changed_component="bounded_gap_fill",
    hypothesis="A brief missing observation need not interrupt team possession.",
    rationale=(
        "Bridge at most two seconds only when both observed endpoint teams agree; "
        "never extrapolate at the recording boundaries."
    ),
    bounded_gap_fill=True,
)
BOUNDARY = replace(
    MISSING_BRIDGE,
    id="e03_pitch_boundary",
    parent_id=MISSING_BRIDGE.id,
    title="Detect sustained out-of-pitch ball observations",
    changed_component="boundary_dead",
    hypothesis="A reliably observed ball beyond the field supports a stoppage.",
    rationale=(
        "Require a 0.25-metre margin outside the pitch for at least 0.2 seconds; "
        "apply the dead-ball evidence after temporal voting."
    ),
    boundary_dead=True,
)
STATIONARY = replace(
    BOUNDARY,
    id="e04_stationary_restart",
    parent_id=BOUNDARY.id,
    title="Combine stationary-ball and stoppage context",
    changed_component="stationary_dead",
    hypothesis="Stationary balls with supporting context can expose missed stoppages.",
    rationale=(
        "Require low ball displacement and speed, plus slow collective movement, "
        "a nearby boundary, or automatic restart evidence; persist for one second."
    ),
    stationary_dead=True,
)
CONTROL = replace(
    STATIONARY,
    id="e05_control_confirmation",
    parent_id=STATIONARY.id,
    title="Require sustained control to switch teams",
    changed_component="control_confirmation",
    hypothesis="Possession should persist through passes and contested loose balls.",
    rationale=(
        "Require a close player, a distance advantage and a ball-speed bound for "
        "0.4 seconds. Backdate confirmed switches to their first supporting frame."
    ),
    control_confirmation=True,
)
TAG_EVIDENCE = replace(
    CONTROL,
    id="e06_automatic_phase_evidence",
    parent_id=CONTROL.id,
    title="Support uncertain control with automatic phase tags",
    changed_component="tag_evidence",
    hypothesis="Automatic tactical phases may supply evidence during uncertain tracking.",
    rationale=(
        "Use a strictly larger positive phase vote only where geometric control "
        "is uncertain, with the same temporal confirmation as observed control."
    ),
    tag_evidence=True,
)
QUALITY = replace(
    TAG_EVIDENCE,
    id="e07_motion_quality",
    parent_id=TAG_EVIDENCE.id,
    title="Exclude impossible motion from control evidence",
    changed_component="quality_filter",
    hypothesis="Motion glitches should contribute less evidence for a team change.",
    rationale=(
        "Exclude player steps over 12 m/s and ball steps over 45 m/s using "
        "consecutive observations; retain the other settings."
    ),
    quality_filter=True,
)
UNSMOOTHED = replace(
    QUALITY,
    id="e08_no_final_vote",
    parent_id=QUALITY.id,
    title="Remove the final fixed-window vote",
    changed_component="smoothing_window_frames",
    hypothesis="Stateful confirmation may preserve boundaries without a final vote.",
    rationale="Set only the final smoothing half-window from 50 frames to zero.",
    smoothing_window_frames=0,
)

EXPERIMENTS = (
    BASELINE,
    THREE_CLASS,
    MISSING_BRIDGE,
    BOUNDARY,
    STATIONARY,
    CONTROL,
    TAG_EVIDENCE,
    QUALITY,
    UNSMOOTHED,
)
