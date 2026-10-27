"""A video detector proposal and its pitch-plane projection."""

from dataclasses import dataclass


@dataclass(frozen=True)
class BallDetection:
    frame: int
    role: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    pixel_x: float
    pixel_y: float
    x_m: float
    y_m: float

    @property
    def position(self) -> tuple[float, float]:
        return self.x_m, self.y_m
