"""Predeclared missing-gap identity-quality comparisons."""

from dataclasses import dataclass, replace
from typing import Literal

from playground.experiment_spec import ExperimentSpec


@dataclass(frozen=True)
class ReacquisitionSpec(ExperimentSpec):
    eligible: Literal["none", "all", "keepers"] = "none"
    collective: bool = False


ANCHOR = ReacquisitionSpec(
    id="q00_f03_reference",
    parent_id="",
    title="Existing f03 reference",
    changed_component="reference",
    hypothesis="Reproduce the earlier uncertainty-gap candidate.",
    rationale="Existing interception, control confirmation and f03 gap repair.",
)
STOPPAGE = replace(
    ANCHOR,
    id="q01_collective_reference",
    parent_id=ANCHOR.id,
    title="Existing p07 collective-stoppage reference",
    changed_component="collective_stoppage_reference",
    hypothesis="Reproduce the strongest candidate from the preceding fixed batch.",
    rationale="Add the unchanged collective seed and retention rule from p07.",
    collective=True,
)
ALL = replace(
    ANCHOR,
    id="q02_all_player_quarantine",
    parent_id=ANCHOR.id,
    title="Quarantine impossible player reappearances",
    changed_component="reacquisition_quality",
    hypothesis=(
        "A track reappearing beyond physical reach can create false team control."
    ),
    rationale=(
        "For every player, compare a post-gap run's first point with the last "
        "trusted point using actual elapsed time. If required average speed exceeds "
        "12 m/s, exclude the entire contiguous run from inference, retain the trusted "
        "anchor, and recompute player-dependent features. Preserve source data."
    ),
    eligible="all",
)
KEEPERS = replace(
    ALL,
    id="q03_goalkeeper_quarantine",
    parent_id=ALL.id,
    title="Restrict impossible-reappearance quarantine to metadata goalkeepers",
    changed_component="quarantine_scope",
    hypothesis=(
        "A role-restricted correction may avoid excluding useful outfield tracks."
    ),
    rationale=(
        "Apply the same 12 m/s post-gap test only to slots whose XML position_type "
        "is Goalkeeper. No player identifiers or target timestamps enter the rule."
    ),
    eligible="keepers",
)
ALL_STOPPAGE = replace(
    ALL,
    id="q04_all_and_stoppage",
    parent_id=ALL.id,
    title="All-player quarantine plus collective stoppages",
    changed_component="collective_stoppage",
    hypothesis="Removing identity corruption may complement stoppage detection.",
    rationale=STOPPAGE.rationale,
    collective=True,
)
KEEPERS_STOPPAGE = replace(
    KEEPERS,
    id="q05_goalkeepers_and_stoppage",
    parent_id=KEEPERS.id,
    title="Goalkeeper quarantine plus collective stoppages",
    changed_component="collective_stoppage",
    hypothesis="Role-restricted identity correction may complement stoppage detection.",
    rationale=STOPPAGE.rationale,
    collective=True,
)

REACQUISITION_EXPERIMENTS = (
    ANCHOR,
    STOPPAGE,
    ALL,
    KEEPERS,
    ALL_STOPPAGE,
    KEEPERS_STOPPAGE,
)

# A second fixed graph follows the audit finding that an observed run can contain
# an abrupt identity jump back to a valid path. It changes segmentation, not speed.


def _with_tracklet_segmentation(spec: ReacquisitionSpec) -> ReacquisitionSpec:
    rationale = spec.rationale
    if spec.eligible != "none":
        rationale += (
            " Split observed runs at consecutive jumps above the same 12 m/s "
            "bound; apply quarantine to these physically continuous tracklets. "
            "A later reachable tracklet can restore the trusted identity."
        )
    return replace(
        spec,
        id=spec.id.replace("q0", "t0", 1),
        parent_id=spec.parent_id.replace("q0", "t0", 1),
        rationale=rationale,
    )


TRACKLET_EXPERIMENTS = tuple(
    _with_tracklet_segmentation(spec) for spec in REACQUISITION_EXPERIMENTS
)
