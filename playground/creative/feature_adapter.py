"""Recompute possession evidence after changing only the ball observations."""

from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy

from .raw_tracks import RawTracks


def _motion(
    ball: NDArray[np.float64], fps: float
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    valid = np.isfinite(ball).all(axis=1)
    speed = np.full(len(ball), np.nan)
    pairs = valid[:-1] & valid[1:]
    speed[1:] = np.where(
        pairs, np.linalg.norm(np.diff(ball, axis=0), axis=1) * fps, np.nan
    )
    lag = max(1, round(fps))
    displacement = np.full(len(ball), np.nan)
    if len(ball) > lag:
        missing = np.r_[0, np.cumsum(~valid)]
        index = np.arange(lag, len(ball))
        continuous = missing[index + 1] == missing[index - lag]
        displacement[index] = np.where(
            continuous, np.linalg.norm(ball[index] - ball[index - lag], axis=1), np.nan
        )
    return speed, displacement


def rebuild_ball_features(
    base: FeatureData,
    raw: RawTracks,
    ball: NDArray[np.float64],
    policy: DomainPolicy = DomainPolicy(),
) -> FeatureData:
    """Keep player coordinates fixed and derive all ball-dependent inputs again."""
    count = len(ball)
    home = raw.team_codes == 0
    home_distance = np.full(count, np.inf)
    away_distance = np.full(count, np.inf)
    quality_home = np.full(count, np.inf)
    quality_away = np.full(count, np.inf)
    code = np.full(count, -1, dtype=np.int8)
    quality_code = np.full(count, -1, dtype=np.int8)
    nearest_speed = np.full(count, np.nan)
    ball_speed, displacement = _motion(ball, raw.fps)
    for start in range(0, count, 5000):
        stop = min(count, start + 5000)
        players = raw.positions[start:stop, :-1]
        distance = np.linalg.norm(players - ball[start:stop, None, :], axis=2)
        distance = np.where(np.isfinite(distance), distance, np.inf)
        home_distance[start:stop] = distance[:, home].min(axis=1)
        away_distance[start:stop] = distance[:, ~home].min(axis=1)
        nearest = distance.argmin(axis=1)
        located = np.isfinite(distance.min(axis=1))
        code[start:stop] = np.where(located, raw.team_codes[nearest], -1)

        previous = np.full_like(players, np.nan)
        if start:
            previous[0] = raw.positions[start - 1, :-1]
        previous[1:] = players[:-1]
        speed = np.linalg.norm(players - previous, axis=2) * raw.fps
        rows = np.arange(stop - start)
        closest_speed = speed[rows, nearest]
        nearest_speed[start:stop] = np.where(
            located & (closest_speed <= policy.player_speed_limit_mps),
            closest_speed,
            np.nan,
        )
        quality = np.where(speed > policy.player_speed_limit_mps, np.inf, distance)
        quality[ball_speed[start:stop] > policy.ball_speed_limit_mps] = np.inf
        quality_home[start:stop] = quality[:, home].min(axis=1)
        quality_away[start:stop] = quality[:, ~home].min(axis=1)
        nearest = quality.argmin(axis=1)
        quality_code[start:stop] = np.where(
            np.isfinite(quality.min(axis=1)), raw.team_codes[nearest], -1
        )
    return replace(
        base,
        ball_x_m=ball[:, 0].copy(),
        ball_y_m=ball[:, 1].copy(),
        ball_valid=np.isfinite(ball).all(axis=1),
        ball_speed_mps=ball_speed,
        ball_displacement_1s_m=displacement,
        nearest_home_distance_m=home_distance,
        nearest_away_distance_m=away_distance,
        nearest_code=code,
        quality_home_distance_m=quality_home,
        quality_away_distance_m=quality_away,
        quality_nearest_code=quality_code,
        nearest_player_speed_mps=nearest_speed,
    )
