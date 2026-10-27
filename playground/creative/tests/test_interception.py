"""Interception evidence must account for motion without inventing missing balls."""

from dataclasses import replace

import numpy as np

from playground.creative.interception import interception_distances
from playground.creative.policy import CreativePolicy

from .fixtures import make_raw_tracks


def test_interception_prefers_a_farther_player_approaching_the_ball() -> None:
    players = np.array([[[20, 20], [21.5, 20]], [[20.5, 20], [21, 20]]], dtype=float)
    ball = np.array([[22, 20], [22, 20]], dtype=float)
    raw = make_raw_tracks(ball, players=players)
    stopped = raw.positions.copy()
    stopped[0, :-1] = stopped[1, :-1]

    moving_home, moving_away, moving_codes = interception_distances(raw, ball)
    _, _, stopped_codes = interception_distances(replace(raw, positions=stopped), ball)

    assert stopped_codes[1] == 1
    assert moving_codes[1] == 0
    assert moving_home[1] < moving_away[1]


def test_interception_projects_the_ball_and_preserves_missingness() -> None:
    players = np.broadcast_to(
        np.array([[20, 20], [24, 20]], dtype=float), (3, 2, 2)
    ).copy()
    ball = np.array([[21, 20], [22, 20], [np.nan, np.nan]], dtype=float)
    raw = make_raw_tracks(ball, players=players)

    _, _, projected = interception_distances(raw, ball)
    home, away, unprojected = interception_distances(
        raw, ball, CreativePolicy(interception_lead_seconds=0)
    )

    assert projected[1] == 1
    assert unprojected[1] == 0
    assert projected[2] == unprojected[2] == -1
    assert np.isinf(home[2]) and np.isinf(away[2])
    np.testing.assert_array_equal(raw.positions[:, -1], ball)
