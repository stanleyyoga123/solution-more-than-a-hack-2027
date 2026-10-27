"""Explicit physical and ambiguity limits for conservative tracking correction."""

from dataclasses import dataclass
from math import ceil


@dataclass(frozen=True)
class CorrectionPolicy:
    player_max_gap_seconds: float = 3
    ball_max_gap_seconds: float = 0.2
    spike_max_seconds: float = 0.2
    context_seconds: float = 0.2
    player_prediction_tolerance_m: float = 2
    ball_prediction_tolerance_m: float = 3
    uniqueness_margin_m: float = 1

    def context_intervals(self, fps: float) -> int:
        return max(1, ceil(self.context_seconds * fps))

    def max_gap_seconds(self, entity_type: str) -> float:
        if entity_type == "ball":
            return self.ball_max_gap_seconds
        return self.player_max_gap_seconds

    def prediction_tolerance(self, entity_type: str) -> float:
        if entity_type == "ball":
            return self.ball_prediction_tolerance_m
        return self.player_prediction_tolerance_m
