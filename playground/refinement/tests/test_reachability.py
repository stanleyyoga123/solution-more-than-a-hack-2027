"""Reachability has physical units and cannot invent evidence for missing tracks."""

from dataclasses import replace

import numpy as np
import pytest

from playground.creative.tests.fixtures import make_raw_tracks
from playground.refinement.policy import RefinementPolicy
from playground.refinement.reachability import reachable_interception_distances


def test_stationary_ball_arrival_matches_accelerating_closed_form() -> None:
    ball = np.array([[5, 20]], dtype=float)
    players = np.array([[[0, 20], [30, 20]]], dtype=float)
    raw = make_raw_tracks(ball, players=players)
    home, _, codes = reachable_interception_distances(raw, ball)
    # Travel 4m after 0.2s reaction: sqrt(2*4/3)+0.2 = 1.833s, sampled at 1.9s.
    assert home[0] == pytest.approx(1.9 * 7)
    assert codes[0] == 0


def test_ball_already_within_control_radius_has_zero_arrival() -> None:
    ball = np.array([[10, 20]], dtype=float)
    players = np.array([[[10.5, 20], [13, 20]]], dtype=float)
    home, away, codes = reachable_interception_distances(
        make_raw_tracks(ball, players=players), ball
    )
    assert home[0] == 0
    assert away[0] > 0
    assert codes[0] == 0


def test_forward_velocity_is_capped_at_the_running_speed() -> None:
    ball = np.array([[10, 20], [10, 20]], dtype=float)
    players = np.array([[[-1, 20], [30, 20]], [[0, 20], [30, 20]]], dtype=float)
    raw = make_raw_tracks(ball, players=players)
    capped, _, _ = reachable_interception_distances(raw, ball)
    at_limit = raw.positions.copy()
    at_limit[0, 0, 0] = -0.7
    limit, _, _ = reachable_interception_distances(
        replace(raw, positions=at_limit), ball
    )
    assert capped[1] == pytest.approx(limit[1])
    # 9m beyond the 1m radius at 7m/s takes 1.286s, rounded up to 1.3s.
    assert capped[1] == pytest.approx(1.3 * 7)


def test_unreached_terminal_target_adds_remaining_distance_at_speed_limit() -> None:
    ball = np.array([[100, 20]], dtype=float)
    players = np.array([[[0, 20], [50, 20]]], dtype=float)
    home, _, _ = reachable_interception_distances(
        make_raw_tracks(ball, players=players), ball
    )
    travelled = 0.5 * 3 * (2 - 0.2) ** 2
    expected = (2 + (100 - travelled - 1) / 7) * 7
    assert home[0] == pytest.approx(expected)


def test_acceleration_stops_increasing_speed_at_the_running_limit() -> None:
    ball = np.array([[100, 20]], dtype=float)
    players = np.array([[[0, 20], [50, 20]]], dtype=float)
    policy = RefinementPolicy(reachability_horizon_seconds=4)
    home, _, _ = reachable_interception_distances(
        make_raw_tracks(ball, players=players), ball, policy
    )
    accelerating = 7 / 3
    cruising = 4 - 0.2 - accelerating
    travelled = 0.5 * 3 * accelerating**2 + 7 * cruising
    expected = (4 + (100 - travelled - 1) / 7) * 7
    assert home[0] == pytest.approx(expected)


def test_reachability_reacts_to_ball_motion_and_preserves_missing_positions() -> None:
    ball = np.array([[20, 20], [21, 20], [np.nan, np.nan]], dtype=float)
    players = np.broadcast_to(
        np.array([[18, 20], [24, 20]], dtype=float), (3, 2, 2)
    ).copy()
    raw = make_raw_tracks(ball, players=players)
    home, away, projected = reachable_interception_distances(raw, ball)
    stationary_policy = RefinementPolicy(ball_speed_limit_mps=0)
    _, _, unprojected = reachable_interception_distances(raw, ball, stationary_policy)
    assert projected[1] == 1
    assert unprojected[1] == 0
    assert away[1] < home[1]
    assert projected[2] == -1
    assert np.isinf(home[2]) and np.isinf(away[2])
    np.testing.assert_array_equal(raw.positions[:, -1], ball)
