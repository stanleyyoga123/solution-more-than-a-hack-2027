"""Combine set-piece context with observed type-compatible stationary balls."""

import logging
from math import ceil
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from playground.feature_data import FeatureData
from playground.smart_tags import SmartTag
from playground.temporal import persistent_mask

from .policy import RestartPolicy

LOGGER = logging.getLogger(__name__)
RESTART_TYPES = frozenset(
    {
        "throw-in",
        "corner kick",
        "goal kick",
        "free kick",
        "kick off (start)",
        "kick off (after goal)",
    }
)


def known_restart_tags(tags: tuple[SmartTag, ...]) -> tuple[SmartTag, ...]:
    """Ignore unknown automatic event types rather than assigning their meaning."""
    return tuple(
        tag
        for tag in tags
        if tag.code.strip().casefold() == "set pieces"
        and tag.event_type.strip().casefold() in RESTART_TYPES
    )


def clipped_tag_bounds(tag: SmartTag, frame_count: int) -> tuple[int, int]:
    """Intersect an event's half-open interval with the recording timeline."""
    return (
        max(0, min(frame_count, tag.start_frame)),
        max(0, min(frame_count, tag.end_frame)),
    )


def restart_geometry(
    features: FeatureData,
    event_type: str,
    policy: RestartPolicy = RestartPolicy(),
) -> NDArray[np.bool_]:
    """Locations compatible with a restart type, without requiring team ownership."""
    x = features.ball_x_m
    y = features.ball_y_m
    kind = event_type.strip().casefold()
    goal_line_distance = np.minimum(np.abs(x), np.abs(x - features.pitch_length))
    touchline_distance = np.minimum(np.abs(y), np.abs(y - features.pitch_width))
    if kind == "throw-in":
        geometry = touchline_distance <= policy.throw_in_touchline_distance_m
    elif kind == "corner kick":
        geometry = (
            np.hypot(goal_line_distance, touchline_distance) <= policy.corner_distance_m
        )
    elif kind == "goal kick":
        geometry = (goal_line_distance <= policy.goal_kick_goal_line_distance_m) & (
            np.abs(y - features.pitch_width / 2) <= policy.goal_kick_half_width_m
        )
    elif kind == "free kick":
        padding = policy.free_kick_pitch_padding_m
        geometry = (
            (x >= -padding)
            & (x <= features.pitch_length + padding)
            & (y >= -padding)
            & (y <= features.pitch_width + padding)
        )
    elif kind in ("kick off (start)", "kick off (after goal)"):
        geometry = (
            np.hypot(x - features.pitch_length / 2, y - features.pitch_width / 2)
            <= policy.kickoff_centre_distance_m
        )
    else:
        return np.zeros(features.frame_count, dtype=bool)
    return features.ball_valid & geometry


def stationary_restart_candidates(
    features: FeatureData,
    event_type: str,
    policy: RestartPolicy = RestartPolicy(),
) -> NDArray[np.bool_]:
    """A usable speed requires observed positions on both sides of its difference."""
    previous_observed = np.r_[False, features.ball_valid[:-1]]
    return (
        restart_geometry(features, event_type, policy)
        & previous_observed
        & np.isfinite(features.ball_speed_mps)
        & (features.ball_speed_mps <= policy.stationary_speed_mps)
    )


def boundary_restart_candidates(
    features: FeatureData,
    event_type: str,
    policy: RestartPolicy = RestartPolicy(),
) -> NDArray[np.bool_]:
    """Observed outside-pitch evidence applies only to boundary restart types."""
    kind = event_type.strip().casefold()
    if kind not in ("throw-in", "corner kick", "goal kick"):
        return np.zeros(features.frame_count, dtype=bool)
    margin = policy.boundary_margin_m
    outside = (
        (features.ball_x_m <= -margin)
        | (features.ball_x_m >= features.pitch_length + margin)
        | (features.ball_y_m <= -margin)
        | (features.ball_y_m >= features.pitch_width + margin)
    )
    return restart_geometry(features, kind, policy) & outside


def full_window_mask(tags: tuple[SmartTag, ...], frame_count: int) -> NDArray[np.bool_]:
    """Naive diagnostic: treat every known set-piece window as entirely dead."""
    result = np.zeros(frame_count, dtype=bool)
    for tag in known_restart_tags(tags):
        start, end = clipped_tag_bounds(tag, frame_count)
        result[start:end] = True
    return result


def restart_seed_mask(
    features: FeatureData,
    tags: tuple[SmartTag, ...],
    policy: RestartPolicy = RestartPolicy(),
) -> NDArray[np.bool_]:
    """Keep sustained stationary runs inside individual compatible tag windows."""
    started = perf_counter()
    restarts = known_restart_tags(tags)
    LOGGER.info(
        "Locating stationary restart evidence in %d tagged events", len(restarts)
    )
    result = np.zeros(features.frame_count, dtype=bool)
    minimum = max(1, ceil(policy.stationary_seconds * features.fps))
    candidates_by_type = {}
    for tag in restarts:
        kind = tag.event_type.strip().casefold()
        if kind not in candidates_by_type:
            candidates_by_type[kind] = stationary_restart_candidates(
                features, kind, policy
            )
        start, end = clipped_tag_bounds(tag, features.frame_count)
        result[start:end] |= persistent_mask(
            candidates_by_type[kind][start:end], minimum
        )
    LOGGER.info(
        "Found %d stationary restart-evidence frames in %.2f seconds",
        int(result.sum()),
        perf_counter() - started,
    )
    return result
