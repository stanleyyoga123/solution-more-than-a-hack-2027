"""Protect gap and geometry measurements from artificial continuity."""

import numpy as np

from tracking_eda.tracking_diagnostics import consecutive_speed, nearest_team_distances, true_runs


def test_true_runs_keeps_separate_halves_when_missing_at_both_boundaries() -> None:
    runs = true_runs(np.ones(8, dtype=bool), [(0, 3), (5, 8)])
    assert runs[["start_frame", "stop_frame", "frames"]].values.tolist() == [[0, 3, 3], [5, 8, 3]]


def test_nearest_team_distances_returns_nan_when_ball_or_team_is_absent() -> None:
    players = np.array([[[0, 0], [np.nan, np.nan]], [[0, 0], [1, 0]]], dtype=np.float32)
    ball = np.array([[0.1, 0], [np.nan, np.nan]], dtype=np.float32)
    distance = nearest_team_distances(players, ball, np.array(["H", "A"]), ("H", "A"), (100, 60))
    assert distance[0, 0] == 10
    assert np.isnan(distance[0, 1])
    assert np.isnan(distance[1]).all()


def test_consecutive_speed_uses_metres_and_never_bridges_missing_frames() -> None:
    xy = np.array([[0, 0], [0.01, 0], [np.nan, np.nan], [0.03, 0], [0.04, 0]], dtype=np.float32)
    speed = consecutive_speed(xy, 25, (100, 60), np.array([True, True, True, True, False]))
    np.testing.assert_allclose(speed[1], 25)
    assert np.isnan(speed[[0, 2, 3, 4]]).all()
