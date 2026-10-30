"""Stream raw tracking into proximity, ball position and player-activity evidence."""

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

# A faster step is an identity switch between slots, not a running player.
MAXIMUM_PLAYER_SPEED_MPS = 12


class TrackingEvidenceLoader:
    def load(self, tracking: Path, metadata: TrackingMetadata) -> PossessionFeatures:
        """Keep source timing, slot-order ties and finite off-pitch positions."""
        started = perf_counter()
        home_id = next(iter(metadata.team_names))
        home_slots = np.array([team == home_id for team in metadata.slot_team_ids])
        team_codes = np.where(home_slots, 0, 1).astype(np.int8)
        pitch = np.array([metadata.pitch_length, metadata.pitch_width])
        count = metadata.expected_frames
        ball_x = np.full(count, np.nan)
        ball_y = np.full(count, np.nan)
        ball_speed = np.full(count, np.nan)
        player_speed = np.full(count, np.nan)
        home_distance = np.full(count, np.inf)
        away_distance = np.full(count, np.inf)
        nearest_code = np.full(count, -1, dtype=np.int8)
        previous_ball = np.full(2, np.nan)
        previous_players = np.full((len(home_slots), 2), np.nan)
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
                ball_x[frame], ball_y[frame] = ball
                observed = np.isfinite(ball).all() and np.isfinite(previous_ball).all()
                if consecutive and observed:
                    ball_speed[frame] = (
                        np.linalg.norm(ball - previous_ball) * metadata.fps
                    )
                if consecutive:
                    steps = np.linalg.norm(players - previous_players, axis=1)
                    steps = steps * metadata.fps
                    steps = steps[steps <= MAXIMUM_PLAYER_SPEED_MPS]
                    if len(steps):
                        player_speed[frame] = steps.mean()
                distances = np.linalg.norm(players - ball, axis=1)
                located = np.isfinite(distances)
                if located.any():
                    nearest = int(np.nanargmin(distances))
                    nearest_code[frame] = team_codes[nearest]
                    home_distance[frame] = np.where(
                        located & home_slots, distances, np.inf
                    ).min()
                    away_distance[frame] = np.where(
                        located & ~home_slots, distances, np.inf
                    ).min()
                previous_ball = ball
                previous_players = players
                previous_frame = frame
                processed += 1

        LOGGER.info(
            "Loaded %d tracking frames in %.2f seconds",
            processed,
            perf_counter() - started,
        )
        return PossessionFeatures(
            metadata=metadata,
            ball_x_m=ball_x,
            ball_y_m=ball_y,
            ball_speed_mps=ball_speed,
            player_speed_mps=player_speed,
            nearest_home_distance_m=home_distance,
            nearest_away_distance_m=away_distance,
            nearest_code=nearest_code,
            processed_tracking_frames=processed,
        )
