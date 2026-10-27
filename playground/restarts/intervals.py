"""Infer one bounded stoppage per tagged restart from original tracking evidence."""

import logging
from math import ceil, floor
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from playground.feature_data import FeatureData
from playground.smart_tags import SmartTag
from playground.temporal import persistent_mask, true_runs

from .evidence import (
    boundary_restart_candidates,
    clipped_tag_bounds,
    known_restart_tags,
    restart_geometry,
    stationary_restart_candidates,
)
from .policy import RestartPolicy

LOGGER = logging.getLogger(__name__)
EventDiagnostic = dict[str, str | int | bool | None]


def _release_candidates(
    features: FeatureData,
    policy: RestartPolicy,
    release_on_control: bool,
) -> NDArray[np.bool_]:
    previous_observed = np.r_[False, features.ball_valid[:-1]]
    speed = features.ball_speed_mps
    inside = (
        features.ball_valid
        & previous_observed
        & (features.ball_x_m >= 0)
        & (features.ball_x_m <= features.pitch_length)
        & (features.ball_y_m >= 0)
        & (features.ball_y_m <= features.pitch_width)
        & np.isfinite(speed)
        & (speed <= policy.maximum_ball_speed_mps)
    )
    moving = speed >= policy.release_speed_mps
    if release_on_control:
        nearest = np.minimum(
            features.nearest_home_distance_m, features.nearest_away_distance_m
        )
        moving |= (nearest <= policy.control_release_distance_m) & (
            speed >= policy.control_release_speed_mps
        )
    return inside & moving


def _extend_start(
    features: FeatureData,
    seed_start: int,
    geometry: NDArray[np.bool_],
    policy: RestartPolicy,
) -> int:
    first = max(0, seed_start - floor(policy.backward_seconds * features.fps))
    stationary = (
        geometry
        & np.isfinite(features.ball_speed_mps)
        & (features.ball_speed_mps <= policy.stationary_speed_mps)
    )
    compatible = ~features.ball_valid | stationary
    start = seed_start
    while start > first and compatible[start - 1]:
        start -= 1
    return start


def restart_dead_intervals(
    features: FeatureData,
    tags: tuple[SmartTag, ...],
    policy: RestartPolicy = RestartPolicy(),
    extend_before: bool = False,
    release_on_control: bool = False,
    include_boundary: bool = False,
) -> tuple[NDArray[np.bool_], list[EventDiagnostic]]:
    """Latch the first supported stationary restart and backdate confirmed release.

    All intervals are half-open. A tag without supported entry evidence creates no dead
    interval. Missing observations can retain a detected stoppage but cannot
    initiate or release it. Backward extension may cross the tag's start, bounded
    by the configured duration and observed live/incompatible evidence.
    Optional outside-pitch entry applies only to boundary restart types. Release
    confirmation starts after the selected entry evidence has been confirmed.
    """
    started = perf_counter()
    restarts = known_restart_tags(tags)
    LOGGER.info(
        "Inferring bounded dead-ball intervals for %d tagged restarts", len(restarts)
    )
    result = np.zeros(features.frame_count, dtype=bool)
    diagnostics = []
    minimum_seed = max(1, ceil(policy.stationary_seconds * features.fps))
    minimum_boundary = max(1, ceil(policy.boundary_seconds * features.fps))
    minimum_release = max(1, ceil(policy.release_seconds * features.fps))
    maximum_dead = max(1, floor(policy.maximum_dead_seconds * features.fps))
    release = _release_candidates(features, policy, release_on_control)
    candidates_by_type = {}
    boundary_by_type = {}
    geometry_by_type = {}
    for tag in restarts:
        start, end = clipped_tag_bounds(tag, features.frame_count)
        kind = tag.event_type.strip().casefold()
        if kind not in candidates_by_type:
            candidates_by_type[kind] = stationary_restart_candidates(
                features, kind, policy
            )
            geometry_by_type[kind] = restart_geometry(features, kind, policy)
        seed = persistent_mask(candidates_by_type[kind][start:end], minimum_seed)
        boundary_seed = np.zeros(end - start, dtype=bool)
        if include_boundary:
            if kind not in boundary_by_type:
                boundary_by_type[kind] = boundary_restart_candidates(
                    features, kind, policy
                )
            boundary_seed = persistent_mask(
                boundary_by_type[kind][start:end], minimum_boundary
            )
            seed |= boundary_seed
        diagnostic: EventDiagnostic = {
            "identifier": tag.identifier,
            "event_type": tag.event_type,
            "tag_start_frame": tag.start_frame,
            "tag_end_frame": tag.end_frame,
            "detected": False,
            "start_frame": None,
            "end_frame": None,
            "release_reason": "no_stationary_seed",
        }
        supported = np.flatnonzero(seed)
        if not len(supported):
            diagnostics.append(diagnostic)
            continue
        seed_start = start + int(supported[0])
        seed_is_boundary = bool(boundary_seed[int(supported[0])])
        confirmation = minimum_boundary if seed_is_boundary else minimum_seed
        dead_start = seed_start
        if extend_before:
            dead_start = _extend_start(
                features, seed_start, geometry_by_type[kind], policy
            )
        dead_end = min(end, seed_start + maximum_dead)
        reason = (
            "tag_window_end" if end <= seed_start + maximum_dead else "duration_limit"
        )
        release_first = min(dead_end, seed_start + confirmation)
        for release_start, release_end in true_runs(release[release_first:dead_end]):
            if release_end - release_start >= minimum_release:
                dead_end = release_first + release_start
                reason = (
                    "supported_live_motion_or_control"
                    if release_on_control
                    else "supported_live_motion"
                )
                break
        result[dead_start:dead_end] = True
        diagnostic.update(
            detected=True,
            seed_start_frame=seed_start,
            seed_type="boundary" if seed_is_boundary else "stationary",
            start_frame=dead_start,
            end_frame=dead_end,
            release_reason=reason,
        )
        diagnostics.append(diagnostic)
    LOGGER.info(
        "Detected %d restart stoppages covering %d frames in %.2f seconds",
        sum(bool(item["detected"]) for item in diagnostics),
        int(result.sum()),
        perf_counter() - started,
    )
    return result, diagnostics
