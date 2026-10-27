"""Stream raw tactical tracking into compact, label-free possession evidence."""

from contextlib import closing
import logging
from pathlib import Path
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import read_metadata
from src.utilities.pipeline_logging import frame_progress

from .feature_data import FeatureData
from .prediction_policy import DomainPolicy

LOGGER = logging.getLogger(__name__)


def _ball_motion(
    x: NDArray[np.float64],
    y: NDArray[np.float64],
    valid: NDArray[np.bool_],
    fps: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Require continuous ball observations for every motion interval."""
    positions = np.column_stack((x, y))
    speed = np.full(len(valid), np.nan)
    connected = valid[:-1] & valid[1:]
    displacement = np.linalg.norm(np.diff(positions, axis=0), axis=1)
    speed[1:] = np.where(connected, displacement * fps, np.nan)

    lag = max(1, round(fps))
    displacement_1s = np.full(len(valid), np.nan)
    if len(valid) > lag:
        missing = np.concatenate(([0], np.cumsum(~valid)))
        indices = np.arange(lag, len(valid))
        uninterrupted = missing[indices + 1] == missing[indices - lag]
        delta = positions[indices] - positions[indices - lag]
        displacement_1s[indices] = np.where(
            uninterrupted, np.linalg.norm(delta, axis=1), np.nan
        )
    return speed, displacement_1s


def load_features(
    tracking: Path,
    metadata_path: Path,
    policy: DomainPolicy = DomainPolicy(),
) -> FeatureData:
    """Read source slots once, retaining missing observations and source timing."""
    started = perf_counter()
    LOGGER.info("Loading experiment metadata: %s", metadata_path)
    info = read_metadata(metadata_path)
    home_id = next(iter(info.team_names))
    home_slots = np.array([team == home_id for team in info.slot_team_ids])
    team_codes = np.where(home_slots, 0, 1).astype(np.int8)
    pitch = np.array([info.pitch_length, info.pitch_width])
    count = info.expected_frames

    ball_x = np.full(count, np.nan)
    ball_y = np.full(count, np.nan)
    ball_valid = np.zeros(count, dtype=bool)
    home_distance = np.full(count, np.inf)
    away_distance = np.full(count, np.inf)
    nearest_code = np.full(count, -1, dtype=np.int8)
    quality_home_distance = np.full(count, np.inf)
    quality_away_distance = np.full(count, np.inf)
    quality_nearest_code = np.full(count, -1, dtype=np.int8)
    nearest_speed = np.full(count, np.nan)
    median_speed = np.full(count, np.nan)
    visible = np.zeros(count, dtype=np.int16)
    previous_players = np.full((len(info.slot_ids), 2), np.nan)
    previous_ball = np.full(2, np.nan)
    previous_frame = -2
    processed = 0

    LOGGER.info("Reading tracking features: %s", tracking)
    with (
        closing(read_tracking(tracking)) as records,
        frame_progress(
            records, count, "Extracting possession features", LOGGER
        ) as frames,
    ):
        for frame, values in frames:
            players = values[:-1, :2] * pitch
            ball = values[-1, :2] * pitch
            player_valid = np.isfinite(players).all(axis=1)
            visible[frame] = np.count_nonzero(player_valid)
            ball_x[frame], ball_y[frame] = ball
            ball_valid[frame] = np.isfinite(ball).all()

            player_speeds = np.full(len(players), np.nan)
            quality_player_valid = player_valid.copy()
            quality_ball_valid = bool(ball_valid[frame])
            if frame == previous_frame + 1:
                movement = np.linalg.norm(players - previous_players, axis=1)
                speeds = movement * info.fps
                quality_player_valid &= ~(speeds > policy.player_speed_limit_mps)
                ball_speed = np.linalg.norm(ball - previous_ball) * info.fps
                quality_ball_valid &= not ball_speed > policy.ball_speed_limit_mps
                plausible = np.isfinite(speeds) & (
                    speeds <= policy.player_speed_limit_mps
                )
                player_speeds[plausible] = speeds[plausible]
                if plausible.any():
                    median_speed[frame] = np.median(player_speeds[plausible])

            distances = np.linalg.norm(players - ball, axis=1)
            located = np.isfinite(distances)
            if located.any():
                nearest = int(np.nanargmin(distances))
                nearest_code[frame] = team_codes[nearest]
                nearest_speed[frame] = player_speeds[nearest]
                if (located & home_slots).any():
                    home_distance[frame] = distances[located & home_slots].min()
                if (located & ~home_slots).any():
                    away_distance[frame] = distances[located & ~home_slots].min()

            quality_located = located & quality_player_valid & quality_ball_valid
            if quality_located.any():
                quality_distances = np.where(quality_located, distances, np.inf)
                nearest = int(np.argmin(quality_distances))
                quality_nearest_code[frame] = team_codes[nearest]
                if (quality_located & home_slots).any():
                    quality_home_distance[frame] = distances[
                        quality_located & home_slots
                    ].min()
                if (quality_located & ~home_slots).any():
                    quality_away_distance[frame] = distances[
                        quality_located & ~home_slots
                    ].min()
            previous_players = players
            previous_ball = ball
            previous_frame = frame
            processed += 1

    ball_speed, ball_displacement = _ball_motion(ball_x, ball_y, ball_valid, info.fps)
    LOGGER.info(
        "Loaded %d frames, %d ball observations in %.2f seconds",
        processed,
        np.count_nonzero(ball_valid),
        perf_counter() - started,
    )
    return FeatureData(
        metadata=info,
        ball_x_m=ball_x,
        ball_y_m=ball_y,
        ball_valid=ball_valid,
        ball_speed_mps=ball_speed,
        ball_displacement_1s_m=ball_displacement,
        nearest_home_distance_m=home_distance,
        nearest_away_distance_m=away_distance,
        nearest_code=nearest_code,
        quality_home_distance_m=quality_home_distance,
        quality_away_distance_m=quality_away_distance,
        quality_nearest_code=quality_nearest_code,
        nearest_player_speed_mps=nearest_speed,
        median_player_speed_mps=median_speed,
        visible_player_count=visible,
    )
