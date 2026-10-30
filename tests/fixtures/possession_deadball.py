"""Small evidence arrays for pipeline 11 behavior checks."""

from collections.abc import Sequence
from importlib import import_module

import numpy as np
from numpy.typing import NDArray

from tests.fixtures.possession_control import metadata

PACKAGE = "src.pipelines.11_possession_deadball"
PossessionFeatures = import_module(
    PACKAGE + ".models.possession_features"
).PossessionFeatures
PossessionPolicy = import_module(PACKAGE + ".configuration.policy").PossessionPolicy


def features(
    player_speed: NDArray[np.float64] | None = None,
    codes: Sequence[int] | None = None,
    ball_x: NDArray[np.float64] | None = None,
    fps: float = 10,
) -> PossessionFeatures:
    """A 100 x 60 m pitch, ball at its centre unless `ball_x` moves it.

    `codes` gives the nearest team per frame (0 home, 1 away, -1 unknown), with that
    team 0.5 m from the ball and the other 4 m away. Without it nobody is located.
    """
    count = len(codes) if codes is not None else len(player_speed)
    nearest = np.full(count, -1, dtype=np.int8) if codes is None else np.array(codes)
    located = nearest >= 0
    home_distance = np.where(nearest == 0, 0.5, 4.0)
    away_distance = np.where(nearest == 1, 0.5, 4.0)
    home_distance[~located] = np.inf
    away_distance[~located] = np.inf
    return PossessionFeatures(
        metadata=metadata(count, fps),
        ball_x_m=np.full(count, 50.0) if ball_x is None else ball_x,
        ball_y_m=np.full(count, 30.0),
        ball_speed_mps=np.where(located, 2.0, np.nan),
        player_speed_mps=np.full(count, 3.0) if player_speed is None else player_speed,
        nearest_home_distance_m=home_distance,
        nearest_away_distance_m=away_distance,
        nearest_code=nearest.astype(np.int8),
        processed_tracking_frames=count,
    )
