"""Physical hypotheses fixed before scoring the refinement experiments."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RefinementPolicy:
    velocity_window_seconds: float = 0.2
    player_speed_limit_mps: float = 12
    ball_speed_limit_mps: float = 45
    interception_player_speed_mps: float = 7
    interception_lead_seconds: float = 0.3
    interception_velocity_fraction: float = 0.5
    reachability_step_seconds: float = 0.1
    reachability_horizon_seconds: float = 2
    reaction_seconds: float = 0.2
    acceleration_mps2: float = 3
    control_radius_m: float = 1
