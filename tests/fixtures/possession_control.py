"""Small physical tracking evidence for pipeline 10 behavior checks."""

from collections.abc import Sequence
from importlib import import_module
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import TrackingMetadata

PossessionFeatures = import_module(
    "src.pipelines.10_possession_control.models.possession_features"
).PossessionFeatures


def metadata(frame_count: int, fps: float = 10) -> TrackingMetadata:
    return TrackingMetadata(
        fps=fps,
        pitch_length=100,
        pitch_width=60,
        speed_unit="kph",
        expected_frames=frame_count,
        slot_ids=("7", "42"),
        slot_team_ids=("home", "away"),
        team_names={"home": "Home", "away": "Away"},
    )


def features(codes: Sequence[int], fps: float = 10) -> PossessionFeatures:
    """Visible moving ball, with clear control evidence for observed team codes."""
    values = np.array(codes, dtype=np.int8)
    count = len(values)
    valid = values >= 0
    home_distance = np.where(values == 0, 0.5, 4.0)
    away_distance = np.where(values == 1, 0.5, 4.0)
    home_distance[~valid] = np.inf
    away_distance[~valid] = np.inf
    return PossessionFeatures(
        metadata=metadata(count, fps),
        ball_speed_mps=np.where(valid, 2.0, np.nan),
        nearest_home_distance_m=home_distance,
        nearest_away_distance_m=away_distance,
        nearest_code=values,
        processed_tracking_frames=count,
    )


def write_tracking(
    directory: Path,
    positions_m: NDArray[np.float64],
    fps: float = 10,
    frame_indices: Sequence[int] | None = None,
) -> tuple[Path, TrackingMetadata]:
    """Write normalized ATD positions, preserving source slot order and frame IDs."""
    directory.mkdir(parents=True, exist_ok=True)
    indices = list(range(len(positions_m))) if frame_indices is None else frame_indices
    tracking = directory / "tracking.txt"
    with tracking.open("w") as destination:
        for frame, positions in zip(indices, positions_m, strict=True):
            rows = []
            for x, y in positions / [100, 60]:
                rows.append(f"{x},{y},999")
            destination.write(f"{frame + 1}:{';'.join(rows[:-1])}:{rows[-1]}\n")
    return tracking, metadata(max(indices) + 1, fps)
