"""Dead-ball evidence from observable geometry, motion and automatic tags."""

from math import ceil

import numpy as np
from numpy.typing import NDArray

from .feature_data import FeatureData
from .prediction_policy import DomainPolicy
from .tag_features import TagFeatures
from .temporal import persistent_mask


def boundary_dead_mask(
    features: FeatureData,
    valid_ball: NDArray[np.bool_],
    policy: DomainPolicy,
) -> NDArray[np.bool_]:
    margin = policy.boundary_margin_m
    outside = (
        (features.ball_x_m <= -margin)
        | (features.ball_x_m >= features.pitch_length + margin)
        | (features.ball_y_m <= -margin)
        | (features.ball_y_m >= features.pitch_width + margin)
    )
    minimum = max(1, ceil(policy.boundary_persistence_seconds * features.fps))
    return persistent_mask(valid_ball & outside, minimum)


def stationary_dead_mask(
    features: FeatureData,
    tags: TagFeatures,
    valid_ball: NDArray[np.bool_],
    policy: DomainPolicy,
) -> NDArray[np.bool_]:
    boundary_distance = np.minimum.reduce(
        (
            np.abs(features.ball_x_m),
            np.abs(features.ball_x_m - features.pitch_length),
            np.abs(features.ball_y_m),
            np.abs(features.ball_y_m - features.pitch_width),
        )
    )
    context = (
        (features.median_player_speed_mps <= policy.stationary_player_speed_mps)
        | (boundary_distance <= policy.boundary_context_m)
        | tags.restart_mask
    )
    # A one-second displacement needs every intermediate observation to be usable.
    intervals = max(1, round(features.fps))
    invalid_total = np.r_[0, np.cumsum(~valid_ball)]
    index = np.arange(features.frame_count)
    first = np.maximum(0, index - intervals)
    continuous = (index >= intervals) & (
        invalid_total[index + 1] - invalid_total[first] == 0
    )
    stationary = (
        continuous
        & (features.ball_displacement_1s_m <= policy.stationary_displacement_m)
        & (features.ball_speed_mps <= policy.stationary_ball_speed_mps)
        & context
    )
    minimum = max(1, ceil(policy.stationary_persistence_seconds * features.fps))
    return persistent_mask(stationary, minimum)
