"""Fixed temporal hypotheses for the possession refinement experiments."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ControlPolicy:
    uncertain_interruption_seconds: float = 0.12
    pending_window_seconds: float = 0.8
    occlusion_bridge_seconds: float = 8
    boundary_release_seconds: float = 0.2
    boundary_release_speed_mps: float = 2
    boundary_release_distance_m: float = 2
    boundary_retention_seconds: float = 30
