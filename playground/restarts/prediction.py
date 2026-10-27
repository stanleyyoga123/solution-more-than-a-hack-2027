"""Inject inferred dead-ball intervals into the existing possession decoder."""

import numpy as np
from numpy.typing import NDArray

from playground.control import confirm_control, control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.refinement.gap_bridge import bridge_occluded_possession
from playground.tag_features import TagFeatures
from playground.temporal import bridge_missing_codes, majority_labels


def integrate_restart_dead(
    features: FeatureData,
    tags: TagFeatures,
    mask: NDArray[np.bool_],
    domain_policy: DomainPolicy = DomainPolicy(),
) -> NDArray[np.str_]:
    """Use arrival-equivalent team evidence while keeping confirmed D explicit."""
    dead = boundary_dead_mask(features, features.ball_valid, domain_policy)
    dead |= stationary_dead_mask(features, tags, features.ball_valid, domain_policy)
    dead |= mask
    codes = bridge_missing_codes(
        features.nearest_code,
        round(domain_policy.missing_bridge_seconds * features.fps),
    )
    candidates = control_candidates(
        features.nearest_home_distance_m,
        features.nearest_away_distance_m,
        features.ball_speed_mps,
        domain_policy,
    )
    controlled = confirm_control(codes, candidates, dead, features.fps, domain_policy)
    labels = majority_labels(controlled, 50, True)
    labels[dead] = "D"
    labels = bridge_occluded_possession(labels, features, tags)
    labels[dead] = "D"
    return labels
