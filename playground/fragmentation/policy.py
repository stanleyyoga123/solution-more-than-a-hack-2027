"""Fixed temporal hypotheses declared before possession scoring."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FragmentationPolicy:
    uncertain_gap_seconds: float = 8
    unsupported_island_seconds: float = 2
    anchor_context_seconds: float = 1
    boundary_search_seconds: float = 2
    control_confirmation_seconds: float = 0.4
