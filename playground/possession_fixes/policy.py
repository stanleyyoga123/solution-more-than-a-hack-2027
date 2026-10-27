"""Fixed hypotheses declared before public possession scoring."""

from dataclasses import dataclass

from playground.prediction_policy import DomainPolicy


@dataclass(frozen=True)
class FixPolicy:
    collective_min_players: int = 8
    collective_slow_speed_mps: float = DomainPolicy().stationary_player_speed_mps
    collective_seed_seconds: float = 2
    collective_max_retention_seconds: float = 20
    restart_confirmation_seconds: float = 0.4
    restart_ball_speed_mps: float = 8
