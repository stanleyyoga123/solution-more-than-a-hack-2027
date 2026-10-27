"""Race along the ball's predicted path with bounded player acceleration."""

import logging
from math import ceil

import numpy as np
from numpy.typing import NDArray

from playground.creative.raw_tracks import RawTracks
from src.utilities.pipeline_logging import frame_progress

from .motion import MOTION_CHUNK_FRAMES, motion_chunks, team_minimum_distances
from .policy import RefinementPolicy

LOGGER = logging.getLogger(__name__)


def reachable_interception_distances(
    raw: RawTracks,
    ball_positions: NDArray[np.float64],
    policy: RefinementPolicy = RefinementPolicy(),
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int8]]:
    """Find the earliest sampled ball target a player's motion can reach.

    Forward speed is retained during reaction, then acceleration is capped at the
    running-speed limit. A ball already within the control radius has arrival zero.
    When the two-second search has no reachable target, a terminal constant-speed
    continuation supplies a finite proxy. All arrival times become equivalent
    metres so the existing possession-control decoder can consume the evidence.
    """
    count = len(ball_positions)
    home = np.full(count, np.inf)
    away = np.full(count, np.inf)
    codes = np.full(count, -1, dtype=np.int8)
    speed_limit = policy.interception_player_speed_mps
    times = np.arange(
        0,
        policy.reachability_horizon_seconds + policy.reachability_step_seconds / 2,
        policy.reachability_step_seconds,
    )
    batches = ceil(count / MOTION_CHUNK_FRAMES)
    with frame_progress(
        motion_chunks(raw, ball_positions, policy),
        batches,
        "Estimating acceleration-limited interception",
        LOGGER,
        unit="batch",
    ) as chunks:
        for start, end, players, ball, player_velocity, ball_velocity in chunks:
            arrival = np.full(players.shape[:2], np.inf)
            for elapsed in times:
                target = ball + elapsed * ball_velocity
                delta = target[:, None] - players
                distance = np.linalg.norm(delta, axis=2)
                direction = np.divide(
                    delta,
                    distance[:, :, None],
                    out=np.zeros_like(delta),
                    where=distance[:, :, None] > 0,
                )
                forward_speed = np.clip(
                    np.sum(player_velocity * direction, axis=2), 0, speed_limit
                )
                active_time = max(0, elapsed - policy.reaction_seconds)
                accelerating_time = np.minimum(
                    active_time,
                    (speed_limit - forward_speed) / policy.acceleration_mps2,
                )
                travelled = (
                    forward_speed * min(elapsed, policy.reaction_seconds)
                    + forward_speed * accelerating_time
                    + 0.5 * policy.acceleration_mps2 * accelerating_time**2
                    + speed_limit * (active_time - accelerating_time)
                )
                reached = distance <= travelled + policy.control_radius_m
                arrival[reached & ~np.isfinite(arrival)] = elapsed
            remaining = np.maximum(0, distance - travelled - policy.control_radius_m)
            fallback = times[-1] + remaining / speed_limit
            arrival = np.where(np.isfinite(arrival), arrival, fallback)
            equivalent = arrival * speed_limit
            equivalent[~np.isfinite(equivalent)] = np.inf
            home[start:end], away[start:end], codes[start:end] = team_minimum_distances(
                equivalent, raw.team_codes
            )
    return home, away, codes
