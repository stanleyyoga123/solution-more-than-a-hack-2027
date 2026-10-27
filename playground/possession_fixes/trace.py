"""Export label-free evidence and the original decoder's intermediate states."""

from pathlib import Path

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from playground.control import confirm_control, control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.tag_features import TagFeatures
from playground.temporal import bridge_missing_codes, majority_labels


def write_evidence_trace(
    path: Path,
    original: FeatureData,
    arrival: FeatureData,
    tags: TagFeatures,
    seed_mask: NDArray[np.bool_],
    held_mask: NDArray[np.bool_],
) -> None:
    policy = DomainPolicy()
    candidates = control_candidates(
        arrival.nearest_home_distance_m,
        arrival.nearest_away_distance_m,
        original.ball_speed_mps,
        policy,
    )
    physical = control_candidates(
        original.nearest_home_distance_m,
        original.nearest_away_distance_m,
        original.ball_speed_mps,
        policy,
    )
    dead = boundary_dead_mask(original, original.ball_valid, policy)
    dead |= stationary_dead_mask(original, tags, original.ball_valid, policy)
    observed = bridge_missing_codes(
        arrival.nearest_code, round(policy.missing_bridge_seconds * original.fps)
    )
    controlled = confirm_control(observed, candidates, dead, original.fps, policy)
    vote = majority_labels(controlled, 50, True)
    pd.DataFrame(
        {
            "frame": np.arange(original.frame_count),
            "time_seconds": np.arange(original.frame_count) / original.fps,
            "ball_observed": original.ball_valid,
            "ball_x_m": original.ball_x_m,
            "ball_y_m": original.ball_y_m,
            "ball_speed_mps": original.ball_speed_mps,
            "ball_displacement_1s_m": original.ball_displacement_1s_m,
            "median_player_speed_mps": original.median_player_speed_mps,
            "visible_players": original.visible_player_count,
            "physical_home_distance_m": original.nearest_home_distance_m,
            "physical_away_distance_m": original.nearest_away_distance_m,
            "arrival_home_equivalent_m": arrival.nearest_home_distance_m,
            "arrival_away_equivalent_m": arrival.nearest_away_distance_m,
            "physical_nearest_code": original.nearest_code,
            "arrival_nearest_code": arrival.nearest_code,
            "arrival_candidate_code": candidates,
            "physical_candidate_code": physical,
            "original_controlled_code": controlled,
            "original_smoothed_label": vote,
            "original_dead_cue": dead,
            "restart_tag": tags.restart_mask,
            "collective_seed": seed_mask,
            "collective_held": held_mask,
        }
    ).to_csv(path, index=False)
