"""Test collective slowdown while an observed ball has no nearby controller."""

import logging
from math import ceil, floor

import numpy as np
from numpy.typing import NDArray

from playground.control import control_candidates
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.temporal import persistent_mask, true_runs

from .policy import FixPolicy

LOGGER = logging.getLogger(__name__)
type StoppageAudit = dict[str, int | str]


def build_collective_stoppages(
    original: FeatureData,
    policy: FixPolicy = FixPolicy(),
    hold: bool = False,
) -> tuple[NDArray[np.bool_], list[StoppageAudit]]:
    """Infer possible stoppages from sustained slow players and a remote ball.

    This is a hypothesis about collective activity, not evidence of a referee's
    decision. Missing ball observations cannot seed or release a stoppage. With
    retention enabled, each distinct qualifying seed run can initiate at most
    one bounded interval, even if the run outlasts the retention timeout.
    """
    domain = DomainPolicy()
    observed_inside = (
        original.ball_valid
        & np.isfinite(original.ball_x_m)
        & np.isfinite(original.ball_y_m)
        & (original.ball_x_m >= 0)
        & (original.ball_x_m <= original.pitch_length)
        & (original.ball_y_m >= 0)
        & (original.ball_y_m <= original.pitch_width)
    )
    enough_players = original.visible_player_count >= policy.collective_min_players
    collective_slow = (
        enough_players
        & np.isfinite(original.median_player_speed_mps)
        & (original.median_player_speed_mps <= policy.collective_slow_speed_mps)
    )
    nearest = np.minimum(
        original.nearest_home_distance_m, original.nearest_away_distance_m
    )
    plausible_motion = (
        np.isfinite(original.ball_speed_mps)
        & (original.ball_speed_mps >= 0)
        & (original.ball_speed_mps <= domain.control_ball_speed_mps)
    )
    candidate = (
        observed_inside
        & collective_slow
        & plausible_motion
        & np.isfinite(nearest)
        & (nearest > domain.control_distance_m)
    )
    minimum = max(1, ceil(policy.collective_seed_seconds * original.fps))
    seeds = persistent_mask(candidate, minimum)
    intervals = list(true_runs(seeds))
    if not hold:
        audits = [
            {
                "start_frame": start,
                "end_frame_exclusive": end,
                "seed_start_frame": start,
                "seed_end_frame_exclusive": end,
                "release_reason": "collective_seed_ended",
            }
            for start, end in intervals
        ]
        LOGGER.info(
            "Found %d collective slowdown seed intervals covering %d frames",
            len(audits),
            int(seeds.sum()),
        )
        return seeds, audits

    physical_control = control_candidates(
        original.nearest_home_distance_m,
        original.nearest_away_distance_m,
        original.ball_speed_mps,
        domain,
    )
    collective_active = (
        enough_players
        & np.isfinite(original.median_player_speed_mps)
        & (original.median_player_speed_mps > policy.collective_slow_speed_mps)
    )
    restart_motion = (
        observed_inside
        & (physical_control >= 0)
        & np.isfinite(original.ball_speed_mps)
        & (original.ball_speed_mps >= 2)
        & (original.ball_speed_mps <= domain.ball_speed_limit_mps)
        & (
            collective_active
            | (original.ball_speed_mps >= policy.restart_ball_speed_mps)
        )
    )
    confirmation = max(1, ceil(policy.restart_confirmation_seconds * original.fps))
    retention = max(1, floor(policy.collective_max_retention_seconds * original.fps))
    result = np.zeros(original.frame_count, dtype=bool)
    audits: list[StoppageAudit] = []
    covered_until = 0
    for start, seed_end in intervals:
        if start < covered_until:
            continue
        end = min(original.frame_count, start + retention)
        reason = "recording_end" if end == original.frame_count else "retention_limit"
        search_start = start + minimum
        for release_start, release_end in true_runs(restart_motion[search_start:end]):
            if release_end - release_start >= confirmation:
                end = search_start + release_start
                reason = "supported_restart_motion"
                break
        result[start:end] = True
        covered_until = end
        audits.append(
            {
                "start_frame": start,
                "end_frame_exclusive": end,
                "seed_start_frame": start,
                "seed_end_frame_exclusive": seed_end,
                "release_reason": reason,
            }
        )
    LOGGER.info(
        "Retained %d collective slowdown intervals covering %d frames",
        len(audits),
        int(result.sum()),
    )
    return result, audits
