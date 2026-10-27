"""Causal robust motion and the existing projected-point interception race."""

from collections.abc import Iterator
import logging
from math import ceil

import numpy as np
from numpy.typing import NDArray

from playground.creative.raw_tracks import RawTracks
from src.utilities.pipeline_logging import frame_progress

from .policy import RefinementPolicy

LOGGER = logging.getLogger(__name__)
MOTION_CHUNK_FRAMES = 5000
MotionChunk = tuple[
    int,
    int,
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
    NDArray[np.float64],
]


def causal_median_velocity(
    positions: NDArray[np.float64],
    fps: float,
    window_seconds: float,
    maximum_speed_mps: float,
) -> NDArray[np.float64]:
    """Median usable differences from the current continuous observation run.

    A missing position clears that entity's history. Implausible differences are
    excluded individually. No usable difference means zero velocity, retaining
    the earlier race's convention for unavailable motion.
    """
    count = len(positions)
    if not count:
        return np.zeros_like(positions)
    window = min(count, max(1, ceil(window_seconds * fps)))
    located = np.isfinite(positions).all(axis=-1)
    velocity = np.full_like(positions, np.nan, dtype=float)
    velocity[1:] = np.diff(positions, axis=0) * fps
    plausible = np.isfinite(velocity).all(axis=-1) & (
        np.linalg.norm(velocity, axis=-1) <= maximum_speed_mps
    )
    velocity[~plausible] = np.nan
    samples = np.full((window,) + positions.shape, np.nan)
    continuous = located.copy()
    for lag in range(window):
        continuous[:lag] = False
        continuous[lag:] &= located[: count - lag]
        samples[lag, lag:] = velocity[: count - lag]
        samples[lag, ~continuous] = np.nan
    supported = np.isfinite(samples).all(axis=-1).any(axis=0)
    # Supply one zero only where every sample is missing, avoiding all-NaN medians.
    samples[0, ~supported] = 0
    return np.nanmedian(samples, axis=0)


def motion_chunks(
    raw: RawTracks,
    ball_positions: NDArray[np.float64],
    policy: RefinementPolicy,
) -> Iterator[MotionChunk]:
    """Retain a trailing context at chunk boundaries without a full motion copy."""
    context = max(1, ceil(policy.velocity_window_seconds * raw.fps))
    for start in range(0, len(ball_positions), MOTION_CHUNK_FRAMES):
        end = min(start + MOTION_CHUNK_FRAMES, len(ball_positions))
        first = max(0, start - context)
        offset = start - first
        player_context = np.asarray(raw.positions[first:end, :-1], dtype=float)
        ball_context = np.asarray(ball_positions[first:end], dtype=float)
        player_velocity = causal_median_velocity(
            player_context,
            raw.fps,
            policy.velocity_window_seconds,
            policy.player_speed_limit_mps,
        )[offset:]
        ball_velocity = causal_median_velocity(
            ball_context,
            raw.fps,
            policy.velocity_window_seconds,
            policy.ball_speed_limit_mps,
        )[offset:]
        yield (
            start,
            end,
            player_context[offset:],
            ball_context[offset:],
            player_velocity,
            ball_velocity,
        )


def team_minimum_distances(
    equivalent: NDArray[np.float64], team_codes: NDArray[np.int8]
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int8]]:
    """Reduce per-player race costs, leaving unavailable teams at infinity."""
    home = equivalent[:, team_codes == 0].min(axis=1)
    away = equivalent[:, team_codes == 1].min(axis=1)
    available = np.isfinite(equivalent).any(axis=1)
    nearest = np.argmin(equivalent, axis=1)
    codes = np.where(available, team_codes[nearest], -1).astype(np.int8)
    return home, away, codes


def robust_interception_distances(
    raw: RawTracks,
    ball_positions: NDArray[np.float64],
    policy: RefinementPolicy = RefinementPolicy(),
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int8]]:
    """Change only velocity estimation in the earlier projected-target race."""
    count = len(ball_positions)
    home = np.full(count, np.inf)
    away = np.full(count, np.inf)
    codes = np.full(count, -1, dtype=np.int8)
    base_speed = policy.interception_player_speed_mps
    velocity_limit = base_speed * policy.interception_velocity_fraction
    batches = ceil(count / MOTION_CHUNK_FRAMES)
    with frame_progress(
        motion_chunks(raw, ball_positions, policy),
        batches,
        "Estimating interception from robust motion",
        LOGGER,
        unit="batch",
    ) as chunks:
        for start, end, players, ball, player_velocity, ball_velocity in chunks:
            target = ball + policy.interception_lead_seconds * ball_velocity
            delta = target[:, None] - players
            distance = np.linalg.norm(delta, axis=2)
            direction = np.divide(
                delta,
                distance[:, :, None],
                out=np.zeros_like(delta),
                where=distance[:, :, None] > 0,
            )
            approach = np.sum(player_velocity * direction, axis=2)
            effective_speed = base_speed + np.clip(
                approach, -velocity_limit, velocity_limit
            )
            equivalent = distance / effective_speed * base_speed
            equivalent[~np.isfinite(equivalent)] = np.inf
            home[start:end], away[start:end], codes[start:end] = team_minimum_distances(
                equivalent, raw.team_codes
            )
    return home, away, codes
