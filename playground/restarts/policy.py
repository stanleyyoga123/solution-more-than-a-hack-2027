"""Fixed physical and temporal hypotheses for automatic restart evidence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RestartPolicy:
    stationary_speed_mps: float = 1
    stationary_seconds: float = 0.4
    boundary_margin_m: float = 0.25
    boundary_seconds: float = 0.2
    throw_in_touchline_distance_m: float = 2
    corner_distance_m: float = 3
    goal_kick_goal_line_distance_m: float = 6
    goal_kick_half_width_m: float = 20.16
    free_kick_pitch_padding_m: float = 2
    kickoff_centre_distance_m: float = 3
    backward_seconds: float = 8
    maximum_dead_seconds: float = 20
    release_seconds: float = 0.2
    release_speed_mps: float = 2
    control_release_distance_m: float = 2
    control_release_speed_mps: float = 0.8
    maximum_ball_speed_mps: float = 45
    dead_gap_seconds: float = 2
