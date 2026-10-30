"""Fixed proximity and timing settings for standalone control confirmation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PossessionPolicy:
    control_missing_timeout_seconds: float = 2
    control_distance_m: float = 2
    control_advantage_m: float = 0.5
    control_ball_speed_mps: float = 12
    control_confirmation_seconds: float = 0.4
