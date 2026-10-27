"""Causal robust motion must reject outliers and respect observation gaps."""

from dataclasses import replace

import numpy as np

from playground.creative.tests.fixtures import make_raw_tracks
from playground.refinement.motion import (
    causal_median_velocity,
    robust_interception_distances,
)


def test_velocity_uses_only_past_samples_and_rejects_one_frame_outlier() -> None:
    positions = np.column_stack(
        (np.array([0, 1, 2, 102, 4, 5, 6], dtype=float), np.zeros(7))
    )
    velocity = causal_median_velocity(positions, 10, 0.5, 12)
    assert velocity[3, 0] == 10
    assert velocity[4, 0] == 10
    changed_future = positions.copy()
    changed_future[4:] += 500
    np.testing.assert_array_equal(
        causal_median_velocity(changed_future, 10, 0.5, 12)[:4], velocity[:4]
    )


def test_velocity_discards_history_across_missing_observations() -> None:
    positions = np.array(
        [[0, 0], [0.2, 0], [0.4, 0], [np.nan, np.nan], [20, 0], [20.4, 0]]
    )
    velocity = causal_median_velocity(positions, 10, 0.5, 12)
    np.testing.assert_array_equal(velocity[3:5], 0)
    np.testing.assert_allclose(velocity[5], [4, 0])


def test_velocity_defaults_to_zero_without_plausible_differences() -> None:
    positions = np.array([[0, 0], [100, 0], [200, 0]], dtype=float)
    np.testing.assert_array_equal(causal_median_velocity(positions, 10, 0.2, 12), 0)


def test_one_missing_player_does_not_reset_another_players_motion() -> None:
    count = 6
    positions = np.zeros((count, 2, 2))
    positions[:, :, 0] = np.arange(count)[:, None] * 0.2
    positions[3, 0] = np.nan
    positions[4:, 0, 0] = [20, 20.4]
    velocity = causal_median_velocity(positions, 10, 0.5, 12)
    np.testing.assert_array_equal(velocity[4, 0], 0)
    np.testing.assert_allclose(velocity[5, 0], [4, 0])
    np.testing.assert_allclose(velocity[1:, 1, 0], 2)
    np.testing.assert_array_equal(velocity[1:, 1, 1], 0)


def test_robust_race_prefers_a_farther_player_moving_toward_ball() -> None:
    players = np.array([[[20, 20], [21.5, 20]], [[20.5, 20], [21, 20]]], dtype=float)
    ball = np.array([[22, 20], [22, 20]], dtype=float)
    raw = make_raw_tracks(ball, players=players)
    stopped = raw.positions.copy()
    stopped[0, :-1] = stopped[1, :-1]
    home, away, moving = robust_interception_distances(raw, ball)
    _, _, stationary = robust_interception_distances(
        replace(raw, positions=stopped), ball
    )
    assert moving[1] == 0
    assert stationary[1] == 1
    assert home[1] < away[1]


def test_robust_race_keeps_missing_ball_and_player_unavailable() -> None:
    ball = np.array([[22, 20], [np.nan, np.nan]], dtype=float)
    players = np.array(
        [[[np.nan, np.nan], [21, 20]], [[20, 20], [21, 20]]], dtype=float
    )
    raw = make_raw_tracks(ball, players=players)
    home, away, codes = robust_interception_distances(raw, ball)
    assert np.isinf(home[0]) and np.isfinite(away[0])
    assert codes[0] == 1
    assert np.isinf(home[1]) and np.isinf(away[1])
    assert codes[1] == -1
    np.testing.assert_array_equal(raw.positions[:, -1], ball)


def test_robust_motion_is_continuous_across_processing_chunks() -> None:
    count = 5005
    time = np.arange(count) / 10
    ball = np.column_stack((time * 2, np.zeros(count)))
    players = np.stack((ball - [2, 0], ball + [3, 0]), axis=1)
    raw = make_raw_tracks(ball, players=players)
    home, away, codes = robust_interception_distances(raw, ball)
    np.testing.assert_allclose(home[4997:5004], home[4997], atol=1e-10)
    np.testing.assert_allclose(away[4997:5004], away[4997], atol=1e-10)
    np.testing.assert_array_equal(codes[4997:5004], 0)
