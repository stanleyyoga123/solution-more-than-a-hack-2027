"""Compact frame-level inputs shared by the possession experiments."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import TrackingMetadata


@dataclass(frozen=True)
class FeatureData:
    """Tracking evidence only; no possession labels enter this structure.

    Distances are in metres and speeds in metres per second. Unavailable
    distances are infinite; unavailable motion observations are NaN.
    """

    metadata: TrackingMetadata
    ball_x_m: NDArray[np.float64]
    ball_y_m: NDArray[np.float64]
    ball_valid: NDArray[np.bool_]
    ball_speed_mps: NDArray[np.float64]
    ball_displacement_1s_m: NDArray[np.float64]
    nearest_home_distance_m: NDArray[np.float64]
    nearest_away_distance_m: NDArray[np.float64]
    nearest_code: NDArray[np.int8]
    quality_home_distance_m: NDArray[np.float64]
    quality_away_distance_m: NDArray[np.float64]
    quality_nearest_code: NDArray[np.int8]
    nearest_player_speed_mps: NDArray[np.float64]
    median_player_speed_mps: NDArray[np.float64]
    visible_player_count: NDArray[np.int16]

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
