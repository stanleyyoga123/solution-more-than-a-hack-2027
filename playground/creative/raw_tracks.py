"""Physical positions needed by the alternative ball and interception models."""

from dataclasses import dataclass
import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import TrackingMetadata, read_metadata
from src.utilities.pipeline_logging import frame_progress

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RawTracks:
    positions: NDArray[np.float64]
    team_codes: NDArray[np.int8]
    fps: float
    pitch_length: float
    pitch_width: float
    metadata: TrackingMetadata


def load_raw_tracks(tracking: Path, metadata: Path) -> RawTracks:
    info = read_metadata(metadata)
    count = len(info.slot_ids) + 1
    positions = np.full((info.expected_frames, count, 2), np.nan)
    home = next(iter(info.team_names))
    team_codes = np.array(
        [0 if team == home else 1 for team in info.slot_team_ids], dtype=np.int8
    )
    scale = np.array([info.pitch_length, info.pitch_width])
    LOGGER.info("Loading physical trajectories for alternative models: %s", tracking)
    records = read_tracking(tracking)
    try:
        with frame_progress(
            records, info.expected_frames, "Reading physical trajectories", LOGGER
        ) as frames:
            for frame, values in frames:
                positions[frame] = values[:, :2] * scale
    finally:
        records.close()
    return RawTracks(
        positions, team_codes, info.fps, info.pitch_length, info.pitch_width, info
    )
