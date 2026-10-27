"""Explicit thresholds for conservative same-slot continuity screening."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GapPolicy:
    max_gap_seconds: float
    context_seconds: float
    player_prediction_tolerance: float
    ball_prediction_tolerance: float

    def prediction_tolerance(self, entity_type: str) -> float:
        if entity_type == "ball":
            return self.ball_prediction_tolerance
        return self.player_prediction_tolerance
