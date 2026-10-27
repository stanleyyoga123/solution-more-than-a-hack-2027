"""One fixed, auditable configuration in the possession experiment sequence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ExperimentSpec:
    id: str
    parent_id: str
    title: str
    changed_component: str
    hypothesis: str
    rationale: str
    three_class_vote: bool = False
    bounded_gap_fill: bool = False
    boundary_dead: bool = False
    stationary_dead: bool = False
    control_confirmation: bool = False
    tag_evidence: bool = False
    quality_filter: bool = False
    smoothing_window_frames: int = 50
