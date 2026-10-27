"""Anticipated player arrival times expressed as control-equivalent metres."""

import numpy as np
from numpy.typing import NDArray

from .policy import CreativePolicy
from .raw_tracks import RawTracks


def interception_distances(
    raw: RawTracks,
    ball_positions: NDArray[np.float64],
    policy: CreativePolicy = CreativePolicy(),
) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.int8]]:
    """Race to a projected ball, retaining the existing decoder's distance scale.

    Current player velocity contributes its component towards the target, bounded
    to half the assumed running speed in either direction. Arrival time times the
    base running speed is a distance equivalent, not a measured player distance.
    """
    count = len(ball_positions)
    home = np.full(count, np.inf)
    away = np.full(count, np.inf)
    codes = np.full(count, -1, dtype=np.int8)
    base_speed = policy.interception_player_speed_mps
    for start in range(0, count, 5000):
        end = min(start + 5000, count)
        players = np.asarray(raw.positions[start:end, :-1], dtype=float)
        ball = np.asarray(ball_positions[start:end], dtype=float)
        player_velocity = np.zeros_like(players)
        ball_velocity = np.zeros_like(ball)
        if start:
            player_velocity[0] = (players[0] - raw.positions[start - 1, :-1]) * raw.fps
            ball_velocity[0] = (ball[0] - ball_positions[start - 1]) * raw.fps
        player_velocity[1:] = np.diff(players, axis=0) * raw.fps
        ball_velocity[1:] = np.diff(ball, axis=0) * raw.fps
        player_speed = np.linalg.norm(player_velocity, axis=2)
        ball_speed = np.linalg.norm(ball_velocity, axis=1)
        player_velocity[
            ~np.isfinite(player_velocity).all(axis=2)
            | (player_speed > policy.player_speed_limit_mps)
        ] = 0
        ball_velocity[
            ~np.isfinite(ball_velocity).all(axis=1)
            | (ball_speed > policy.ball_speed_limit_mps)
        ] = 0
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
            approach, -base_speed / 2, base_speed / 2
        )
        equivalent = distance / effective_speed * base_speed
        equivalent[~np.isfinite(equivalent)] = np.inf
        home[start:end] = equivalent[:, raw.team_codes == 0].min(axis=1)
        away[start:end] = equivalent[:, raw.team_codes == 1].min(axis=1)
        available = np.isfinite(equivalent).any(axis=1)
        nearest = np.argmin(equivalent, axis=1)
        codes[start:end] = np.where(available, raw.team_codes[nearest], -1)
    return home, away, codes
