"""Apply one predeclared experiment without access to evaluation labels."""

import numpy as np
from numpy.typing import NDArray

from .control import confirm_control, control_candidates
from .dead_ball import boundary_dead_mask, stationary_dead_mask
from .experiment_spec import ExperimentSpec
from .feature_data import FeatureData
from .prediction_policy import DomainPolicy
from .tag_features import TagFeatures
from .temporal import bridge_missing_codes, majority_labels


def predict(
    features: FeatureData,
    tags: TagFeatures,
    spec: ExperimentSpec,
    policy: DomainPolicy = DomainPolicy(),
) -> NDArray[np.str_]:
    """Return one H/A/D label per source frame using tracking and automatic tags."""
    if spec.quality_filter:
        codes = features.quality_nearest_code.copy()
        home_distance = features.quality_home_distance_m
        away_distance = features.quality_away_distance_m
    else:
        codes = features.nearest_code.copy()
        home_distance = features.nearest_home_distance_m
        away_distance = features.nearest_away_distance_m
    valid_ball = features.ball_valid.copy()
    if spec.quality_filter:
        valid_ball &= ~(
            np.isfinite(features.ball_speed_mps)
            & (features.ball_speed_mps > policy.ball_speed_limit_mps)
        )
    if spec.bounded_gap_fill:
        codes = bridge_missing_codes(
            codes, round(policy.missing_bridge_seconds * features.fps)
        )
    dead_mask = np.zeros(features.frame_count, dtype=bool)
    if spec.boundary_dead:
        dead_mask |= boundary_dead_mask(features, valid_ball, policy)
    if spec.stationary_dead:
        dead_mask |= stationary_dead_mask(features, tags, valid_ball, policy)
    if spec.control_confirmation:
        candidates = control_candidates(
            home_distance, away_distance, features.ball_speed_mps, policy
        )
        if spec.tag_evidence:
            uncertain = candidates < 0
            home_vote = tags.home_phase_votes > tags.away_phase_votes
            away_vote = tags.away_phase_votes > tags.home_phase_votes
            candidates[uncertain & home_vote] = 0
            candidates[uncertain & away_vote] = 1
        codes = confirm_control(codes, candidates, dead_mask, features.fps, policy)
    labels = majority_labels(codes, spec.smoothing_window_frames, spec.three_class_vote)
    labels[dead_mask] = "D"
    return labels
