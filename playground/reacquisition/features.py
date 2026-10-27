"""Rebuild player-dependent possession evidence after observation quarantine."""

from dataclasses import replace
import logging

import numpy as np

from playground.creative.feature_adapter import rebuild_ball_features
from playground.creative.raw_tracks import RawTracks
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy

LOGGER = logging.getLogger(__name__)


def rebuild_player_features(base: FeatureData, filtered: RawTracks) -> FeatureData:
    """Recompute geometric and motion evidence while retaining original ball data."""
    rebuilt = rebuild_ball_features(base, filtered, filtered.positions[:, -1])
    count = len(filtered.positions)
    visible = np.zeros(count, dtype=np.int16)
    median_speed = np.full(count, np.nan)
    limit = DomainPolicy().player_speed_limit_mps
    for start in range(0, count, 5000):
        end = min(count, start + 5000)
        players = filtered.positions[start:end, :-1]
        visible[start:end] = np.isfinite(players).all(axis=2).sum(axis=1)
        previous = np.full_like(players, np.nan)
        if start:
            previous[0] = filtered.positions[start - 1, :-1]
        previous[1:] = players[:-1]
        speed = np.linalg.norm(players - previous, axis=2) * filtered.fps
        plausible = np.isfinite(speed) & (speed <= limit)
        rows = plausible.any(axis=1)
        chunk_median = np.full(end - start, np.nan)
        chunk_median[rows] = np.nanmedian(
            np.where(plausible[rows], speed[rows], np.nan), axis=1
        )
        median_speed[start:end] = chunk_median
    LOGGER.info(
        "Rebuilt player evidence for %d frames from quarantined observations", count
    )
    return replace(
        rebuilt,
        ball_x_m=base.ball_x_m,
        ball_y_m=base.ball_y_m,
        ball_valid=base.ball_valid,
        ball_speed_mps=base.ball_speed_mps,
        ball_displacement_1s_m=base.ball_displacement_1s_m,
        median_player_speed_mps=median_speed,
        visible_player_count=visible,
    )
