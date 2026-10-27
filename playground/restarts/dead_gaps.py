"""Event-local continuity of existing dead-ball predictions."""

from math import floor

import numpy as np
from numpy.typing import NDArray

from playground.feature_data import FeatureData
from playground.smart_tags import SmartTag
from playground.temporal import true_runs

from .evidence import known_restart_tags
from .policy import RestartPolicy


def bridge_restart_dead_gaps(
    labels: NDArray[np.str_],
    features: FeatureData,
    tags: tuple[SmartTag, ...],
    policy: RestartPolicy = RestartPolicy(),
) -> NDArray[np.str_]:
    """Bridge only observed-model live islands bounded by D within one event.

    Missing tracking supplies no positive live-play evidence. That uncertainty
    permits bridging here, but an automatic restart tag can itself be wrong.
    """
    result = labels.copy()
    maximum_frames = floor(policy.dead_gap_seconds * features.fps)
    near_player = (
        np.minimum(features.nearest_home_distance_m, features.nearest_away_distance_m)
        <= policy.control_release_distance_m
    )
    plausible_speed = np.isfinite(features.ball_speed_mps) & (
        features.ball_speed_mps <= policy.maximum_ball_speed_mps
    )
    moving = plausible_speed & (features.ball_speed_mps >= policy.release_speed_mps)
    live_evidence = features.ball_valid & (moving | near_player)
    windows = [
        (max(0, tag.start_frame), min(len(labels), tag.end_frame))
        for tag in known_restart_tags(tags)
    ]
    for start, end in true_runs(np.isin(labels, ("H", "A"))):
        if start == 0 or end == len(labels) or end - start > maximum_frames:
            continue
        if labels[start - 1] != "D" or labels[end] != "D":
            continue
        if live_evidence[start:end].any():
            continue
        if not any(left <= start - 1 and end < right for left, right in windows):
            continue
        result[start:end] = "D"
    return result
