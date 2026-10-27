"""Predeclared changes around the existing r06 possession predictor."""

from dataclasses import dataclass, replace

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class FragmentationSpec(ExperimentSpec):
    operation: str = "reference"


BASELINE = FragmentationSpec(
    id="f00_original_baseline",
    parent_id="",
    title="Original step 05",
    changed_component="reference",
    hypothesis="Reproduce the original baseline independently.",
    rationale="Compare predictions with a separate step 05 invocation.",
)
ANCHOR = replace(
    BASELINE,
    id="f01_occlusion_reference",
    parent_id=BASELINE.id,
    title="Previous best r06",
    changed_component="reference_anchor",
    hypothesis="Reproduce the existing interception and occlusion predictor.",
    rationale="This is a reference anchor, not a one-component ablation of step 05.",
)
UNCERTAINTY = replace(
    ANCHOR,
    id="f02_explicit_uncertainty",
    parent_id=ANCHOR.id,
    title="Separate unsupported D from observed stoppage cues",
    changed_component="internal_representation",
    hypothesis="Track ambiguous labels without changing the submitted prediction.",
    rationale=(
        "Internally mark D without a physical stoppage cue as U. Export unresolved "
        "U as D, so this control must match r06 exactly. U is a hypothesis, not "
        "proof that play is live."
    ),
    operation="uncertainty",
)
JOIN = replace(
    UNCERTAINTY,
    id="f03_join_uncertain_gaps",
    parent_id=UNCERTAINTY.id,
    title="Join same-team possessions across uncertain gaps",
    changed_component="same_team_gap_repair",
    hypothesis="Intermittent tracking need not interrupt continuing possession.",
    rationale=(
        "Join U intervals up to eight seconds bounded by the same team, unless "
        "there is an explicit stoppage cue or sustained opposing control. "
        "A broad restart window alone does not forbid the repair."
    ),
    operation="join",
)
ISLANDS = replace(
    JOIN,
    id="f04_remove_unsupported_islands",
    parent_id=JOIN.id,
    title="Remove unsupported brief opponent possessions",
    changed_component="opponent_island_repair",
    hypothesis="Weak opponent labels can split a single possession.",
    rationale=(
        "Replace opponent islands up to two seconds only with positive control "
        "evidence for the surrounding team on both sides and no confirmed "
        "island-team control or explicit stoppage cue."
    ),
    operation="islands",
)
TURNOVERS = replace(
    ISLANDS,
    id="f05_resolve_turnover_gaps",
    parent_id=ISLANDS.id,
    title="Resolve uncertainty between different controlling teams",
    changed_component="different_team_gap_repair",
    hypothesis="A loose-ball interval can contain one turnover without a stoppage.",
    rationale=(
        "Resolve U gaps up to eight seconds only with confirmed flanking control "
        "and no explicit stoppage cue. Choose a single boundary minimizing "
        "contradictory observed control; record the ambiguous timing range."
    ),
    operation="turnovers",
)
BOUNDARIES = replace(
    TURNOVERS,
    id="f06_refine_turnover_boundaries",
    parent_id=TURNOVERS.id,
    title="Refine direct turnover timing",
    changed_component="boundary_timing",
    hypothesis="Control evidence can correct boundaries shifted by smoothing.",
    rationale=(
        "Move direct H/A boundaries at most two seconds within adjacent spells, "
        "only when observed two-team control strictly improves the assignment. "
        "Preserve stoppages, unresolved uncertainty, and neighboring spells."
    ),
    operation="boundaries",
)
BOUNDARIES_ONLY = replace(
    BOUNDARIES,
    id="f07_boundary_only",
    parent_id=UNCERTAINTY.id,
    title="Refine turnover timing without merging spells",
    hypothesis="Boundary timing may improve independently of fragmentation repair.",
)
ISLANDS_ONLY = replace(
    ISLANDS,
    id="f08_islands_only",
    parent_id=UNCERTAINTY.id,
    title="Remove unsupported islands without gap filling",
    hypothesis="Brief opponent interruptions may be independent of missing-data gaps.",
)

FRAGMENTATION_EXPERIMENTS = (
    BASELINE,
    ANCHOR,
    UNCERTAINTY,
    JOIN,
    ISLANDS,
    TURNOVERS,
    BOUNDARIES,
    BOUNDARIES_ONLY,
    ISLANDS_ONLY,
)
