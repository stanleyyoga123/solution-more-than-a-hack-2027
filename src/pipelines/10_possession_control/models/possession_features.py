"""Compact tracking evidence used by standalone control confirmation."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import TrackingMetadata


@dataclass(frozen=True)
class PossessionFeatures:
    """Distances use metres; missing motion is NaN and missing distance is infinity."""

    metadata: TrackingMetadata
    ball_speed_mps: NDArray[np.float64]
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
