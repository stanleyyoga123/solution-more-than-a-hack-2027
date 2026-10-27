"""Physical and temporal settings fixed before public-score evaluation."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DomainPolicy:
    missing_bridge_seconds: float = 2
    boundary_margin_m: float = 0.25
    boundary_persistence_seconds: float = 0.2
    stationary_displacement_m: float = 0.5
    stationary_ball_speed_mps: float = 0.8
    stationary_player_speed_mps: float = 1.5
    boundary_context_m: float = 2
    stationary_persistence_seconds: float = 1
    control_distance_m: float = 2
    control_advantage_m: float = 0.5
    control_ball_speed_mps: float = 12
    control_confirmation_seconds: float = 0.4
    player_speed_limit_mps: float = 12
    ball_speed_limit_mps: float = 45
