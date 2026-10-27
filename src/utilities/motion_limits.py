"""Physical screening thresholds shared by trajectory and gap assessments."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class MotionLimits:
    player_speed_limit_mps: float
    player_acceleration_limit_mps2: float
    ball_speed_limit_mps: float

    def speed_limit(self, entity_type: str) -> float:
        if entity_type == "ball":
            return self.ball_speed_limit_mps
        return self.player_speed_limit_mps


def read_motion_limits(path: Path) -> MotionLimits:
    document = json.loads(path.read_text(encoding="utf-8"))
    return MotionLimits(**document["thresholds"])
