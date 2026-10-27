"""Carry explicit out-of-play evidence through subsequent tracking uncertainty."""

from math import ceil, floor

import numpy as np
from numpy.typing import NDArray

from playground.dead_ball import boundary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy

from .control_policy import ControlPolicy


def persistent_boundary_dead_mask(
    features: FeatureData,
    domain_policy: DomainPolicy = DomainPolicy(),
    policy: ControlPolicy = ControlPolicy(),
) -> NDArray[np.bool_]:
    """Latch boundary stoppages until sustained live evidence or fixed expiry.

    Missing balls never initiate a stoppage. Release requires an observed ball
    inside the pitch with movement or nearby team evidence for the configured
    duration; the release takes effect on its confirmation frame. The timeout is
    measured from the last explicit boundary cue and is never extended by a
    missing observation.
    """
    cues = boundary_dead_mask(features, features.ball_valid, domain_policy)
    inside = (
        features.ball_valid
        & (features.ball_x_m >= 0)
        & (features.ball_x_m <= features.pitch_length)
        & (features.ball_y_m >= 0)
        & (features.ball_y_m <= features.pitch_width)
    )
    nearest = np.minimum(
        features.nearest_home_distance_m, features.nearest_away_distance_m
    )
    live = inside & (
        (features.ball_speed_mps >= policy.boundary_release_speed_mps)
        | (nearest <= policy.boundary_release_distance_m)
    )
    release_frames = max(1, ceil(policy.boundary_release_seconds * features.fps))
    retention_frames = max(0, floor(policy.boundary_retention_seconds * features.fps))
    result = np.zeros(features.frame_count, dtype=bool)
    last_cue = -1
    release_count = 0
    active = False
    for frame in range(features.frame_count):
        if cues[frame]:
            active = True
            last_cue = frame
            release_count = 0
        elif active:
            if frame - last_cue > retention_frames:
                active = False
                release_count = 0
            else:
                release_count = release_count + 1 if live[frame] else 0
                if release_count >= release_frames:
                    active = False
                    release_count = 0
        result[frame] = active
    return result
