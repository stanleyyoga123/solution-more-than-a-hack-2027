"""Fixed numerical hypotheses for the creative experiment branches."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CreativePolicy:
    forecast_context_seconds: float = 0.2
    forecast_horizon_seconds: float = 0.5
    bridge_max_seconds: float = 2
    bridge_prediction_tolerance_m: float = 5
    ball_speed_limit_mps: float = 45
    decoding_hz: float = 5
    team_transition_cost: float = 4
    dead_transition_cost: float = 2
    distance_evidence_scale_m: float = 4
    uncertainty_distance_scale_m: float = 8
    dead_logit_without_cue: float = -3
    live_logit_under_dead_cue: float = -6
    dead_logit_under_dead_cue: float = 2
    interception_player_speed_mps: float = 7
    player_speed_limit_mps: float = 12
    interception_lead_seconds: float = 0.3
    collective_training_fraction: float = 0.8
    collective_training_stride: int = 5
    collective_ridge_penalty: float = 10
    collective_min_team_players: int = 5
    collective_max_standardized_feature: float = 4
