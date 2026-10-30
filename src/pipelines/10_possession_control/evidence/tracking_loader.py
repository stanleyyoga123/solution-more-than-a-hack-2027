"""Stream raw tracking into team proximity and observed ball-speed evidence."""

from contextlib import closing
import logging
from pathlib import Path
from time import perf_counter

import numpy as np

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import TrackingMetadata
from src.utilities.pipeline_logging import frame_progress

from ..models.possession_features import PossessionFeatures

LOGGER = logging.getLogger(__name__)


class TrackingEvidenceLoader:
    def load(self, tracking: Path, metadata: TrackingMetadata) -> PossessionFeatures:
        """Preserve source timing, slot-order ties and finite off-pitch positions."""
        started = perf_counter()
        home_id = next(iter(metadata.team_names))
        home_slots = np.array([team == home_id for team in metadata.slot_team_ids])
        team_codes = np.where(home_slots, 0, 1).astype(np.int8)
        pitch = np.array([metadata.pitch_length, metadata.pitch_width])
        count = metadata.expected_frames
        home_distance = np.full(count, np.inf)
        away_distance = np.full(count, np.inf)
        nearest_code = np.full(count, -1, dtype=np.int8)
        ball_speed = np.full(count, np.nan)
        previous_ball = np.full(2, np.nan)
        previous_frame = -2
        processed = 0

        LOGGER.info("Loading possession tracking evidence: %s", tracking)
        with (
            closing(read_tracking(tracking)) as records,
            frame_progress(
                records, count, "Extracting possession evidence", LOGGER
            ) as frames,
        ):
            for frame, values in frames:
                players = values[:-1, :2] * pitch
                ball = values[-1, :2] * pitch
                consecutive = frame == previous_frame + 1
                observed = np.isfinite(ball).all() and np.isfinite(previous_ball).all()
                if consecutive and observed:
                    ball_speed[frame] = (
                        np.linalg.norm(ball - previous_ball) * metadata.fps
                    )
                distances = np.linalg.norm(players - ball, axis=1)
                located = np.isfinite(distances)
                if located.any():
                    nearest = int(np.nanargmin(distances))
                    nearest_code[frame] = team_codes[nearest]
                    if (located & home_slots).any():
                        home_distance[frame] = distances[located & home_slots].min()
                    if (located & ~home_slots).any():
                        away_distance[frame] = distances[located & ~home_slots].min()
                previous_ball = ball
                previous_frame = frame
                processed += 1

        LOGGER.info(
            "Loaded %d tracking frames in %.2f seconds",
            processed,
            perf_counter() - started,
        )
        return PossessionFeatures(
            metadata=metadata,
            ball_speed_mps=ball_speed,
            nearest_home_distance_m=home_distance,
            nearest_away_distance_m=away_distance,
            nearest_code=nearest_code,
            processed_tracking_frames=processed,
        )
