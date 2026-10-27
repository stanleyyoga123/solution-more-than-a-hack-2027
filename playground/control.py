"""Offline team-control confirmation with explicit loose-ball persistence."""

from math import ceil

import numpy as np
from numpy.typing import NDArray

from .prediction_policy import DomainPolicy


def control_candidates(
    home_distance: NDArray[np.float64],
    away_distance: NDArray[np.float64],
    ball_speed: NDArray[np.float64],
    policy: DomainPolicy,
) -> NDArray[np.int8]:
    """Require close, separated team evidence and plausible control ball speed."""
    result = np.full(len(home_distance), -1, dtype=np.int8)
    plausible_speed = ~np.isfinite(ball_speed) | (
        ball_speed <= policy.control_ball_speed_mps
    )
    home = (
        np.isfinite(home_distance)
        & (home_distance <= policy.control_distance_m)
        & (home_distance + policy.control_advantage_m <= away_distance)
        & plausible_speed
    )
    away = (
        np.isfinite(away_distance)
        & (away_distance <= policy.control_distance_m)
        & (away_distance + policy.control_advantage_m <= home_distance)
        & plausible_speed
    )
    result[home] = 0
    result[away] = 1
    return result


def confirm_control(
    observed_codes: NDArray[np.int8],
    candidates: NDArray[np.int8],
    dead_mask: NDArray[np.bool_],
    fps: float,
    policy: DomainPolicy,
) -> NDArray[np.int8]:
    """Keep the incumbent until sustained opposing evidence confirms a handover.

    At initialization, the first available team observation supplies the incumbent.
    Thereafter, confirmed switches are backdated to their first candidate frame.
    Missing observations expire after the fixed bridge duration; explicit dead-ball
    evidence clears the incumbent immediately.
    """
    result = np.full(len(observed_codes), -1, dtype=np.int8)
    confirmation = max(1, ceil(policy.control_confirmation_seconds * fps))
    maximum_missing = max(0, round(policy.missing_bridge_seconds * fps))
    incumbent = pending = -1
    pending_start = pending_count = missing_count = 0
    for frame, observation in enumerate(observed_codes):
        if dead_mask[frame]:
            incumbent = pending = -1
            pending_count = missing_count = 0
            continue
        candidate = int(candidates[frame])
        evidence_available = observation >= 0 or candidate >= 0
        if evidence_available:
            missing_count = 0
        else:
            missing_count += 1
            if missing_count > maximum_missing:
                incumbent = -1
        if incumbent < 0 and observation >= 0:
            incumbent = int(observation)
        if candidate >= 0 and candidate != incumbent:
            if candidate == pending:
                pending_count += 1
            else:
                pending = candidate
                pending_start = frame
                pending_count = 1
            if pending_count >= confirmation:
                incumbent = candidate
                result[pending_start : frame + 1] = incumbent
                pending = -1
                pending_count = 0
        else:
            pending = -1
            pending_count = 0
        result[frame] = incumbent
    return result
