"""Apply the chosen temporal hypothesis to a fixed set of arrival evidence."""

import numpy as np
from numpy.typing import NDArray

from playground.control import confirm_control, control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.tag_features import TagFeatures
from playground.temporal import bridge_missing_codes, majority_labels

from .control import tolerant_confirm_control
from .control_policy import ControlPolicy
from .gap_bridge import bridge_occluded_possession
from .specs import RefinementSpec
from .stoppages import persistent_boundary_dead_mask


def predict_refinement(
    features: FeatureData,
    tags: TagFeatures,
    spec: RefinementSpec,
    domain_policy: DomainPolicy = DomainPolicy(),
    control_policy: ControlPolicy = ControlPolicy(),
) -> NDArray[np.str_]:
    if not spec.tolerant_control and not spec.boundary_latch:
        labels = predict(features, tags, spec, domain_policy)
    else:
        codes = bridge_missing_codes(
            features.nearest_code,
            round(domain_policy.missing_bridge_seconds * features.fps),
        )
        if spec.boundary_latch:
            dead = persistent_boundary_dead_mask(
                features, domain_policy, control_policy
            )
        else:
            dead = boundary_dead_mask(features, features.ball_valid, domain_policy)
        dead |= stationary_dead_mask(features, tags, features.ball_valid, domain_policy)
        candidates = control_candidates(
            features.nearest_home_distance_m,
            features.nearest_away_distance_m,
            features.ball_speed_mps,
            domain_policy,
        )
        if spec.tolerant_control:
            codes = tolerant_confirm_control(
                codes, candidates, dead, features.fps, domain_policy, control_policy
            )
        else:
            codes = confirm_control(
                codes, candidates, dead, features.fps, domain_policy
            )
        labels = majority_labels(codes, spec.smoothing_window_frames, True)
        labels[dead] = "D"
    if spec.occlusion_bridge:
        labels = bridge_occluded_possession(
            labels, features, tags, control_policy, domain_policy
        )
    return labels
