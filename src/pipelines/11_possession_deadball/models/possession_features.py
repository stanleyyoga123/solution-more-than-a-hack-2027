"""Compact tracking evidence used by ownership and dead-ball detection."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import TrackingMetadata


@dataclass(frozen=True)
class PossessionFeatures:
    """Metres and seconds; missing motion is NaN and missing distance is infinity.

    `player_speed_mps` is the mean speed of the tracked players between
    consecutive frames. `nearest_code` is 0 for home, 1 for away, -1 if unknown.
    """

    metadata: TrackingMetadata
    ball_x_m: NDArray[np.float64]
    ball_y_m: NDArray[np.float64]
    ball_speed_mps: NDArray[np.float64]
    player_speed_mps: NDArray[np.float64]
    nearest_home_distance_m: NDArray[np.float64]
    nearest_away_distance_m: NDArray[np.float64]
    nearest_code: NDArray[np.int8]
    processed_tracking_frames: int

    @property
    def fps(self) -> float:
        return self.metadata.fps

    @property
    def pitch_length(self) -> float:
        return self.metadata.pitch_length

    @property
    def pitch_width(self) -> float:
        return self.metadata.pitch_width

    @property
    def frame_count(self) -> int:
        return len(self.nearest_code)

    def between(self, start: int, stop: int) -> "PossessionFeatures":
        """Features for frames start..stop-1, so ownership can restart per half."""
        window = slice(start, stop)
        return PossessionFeatures(
            metadata=self.metadata,
            ball_x_m=self.ball_x_m[window],
            ball_y_m=self.ball_y_m[window],
            ball_speed_mps=self.ball_speed_mps[window],
            player_speed_mps=self.player_speed_mps[window],
            nearest_home_distance_m=self.nearest_home_distance_m[window],
            nearest_away_distance_m=self.nearest_away_distance_m[window],
            nearest_code=self.nearest_code[window],
            processed_tracking_frames=self.processed_tracking_frames,
        )
