"""Offline possession continuity across short, entirely unobserved ball gaps."""

from math import floor

import numpy as np
from numpy.typing import NDArray

from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.tag_features import TagFeatures
from playground.temporal import true_runs

from .control_policy import ControlPolicy


def bridge_occluded_possession(
    labels: NDArray[np.str_],
    features: FeatureData,
    tags: TagFeatures,
    policy: ControlPolicy = ControlPolicy(),
    domain_policy: DomainPolicy = DomainPolicy(),
) -> NDArray[np.str_]:
    """Fill bounded D runs only when all ball observations are missing.

    Both endpoints must support the same live team, and no restart tag or
    explicit geometry/motion stoppage cue may overlap the interval. This is a
    label-continuity hypothesis; it does not impute ball coordinates.
    """
    result = labels.copy()
    maximum_frames = floor(policy.occlusion_bridge_seconds * features.fps)
    dead = boundary_dead_mask(features, features.ball_valid, domain_policy)
    dead |= stationary_dead_mask(features, tags, features.ball_valid, domain_policy)
    for start, end in true_runs(labels == "D"):
        if start == 0 or end == len(labels) or end - start > maximum_frames:
            continue
        team = labels[start - 1]
        if team not in ("H", "A") or labels[end] != team:
            continue
        if features.ball_valid[start:end].any():
            continue
        if tags.restart_mask[start:end].any() or dead[start:end].any():
            continue
        result[start:end] = team
    return result
