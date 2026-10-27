"""Input evidence contracts: source slot order, physical motion, and missingness."""

import importlib
from pathlib import Path

import numpy as np

from playground.features import load_features

from .fixtures import write_tracking


def test_nearest_codes_match_step05_with_ties_and_missing_positions(
    tmp_path: Path,
) -> None:
    positions = np.array(
        [
            [[10, 20], [30, 20], [20, 20]],
            [[np.nan, np.nan], [30, 20], [20, 20]],
            [[10, 20], [30, 20], [np.nan, np.nan]],
            [[np.nan, np.nan], [np.nan, np.nan], [20, 20]],
        ],
        dtype=float,
    )
    tracking, metadata = write_tracking(tmp_path, positions)
    baseline = importlib.import_module("src.pipelines.05_possession_baseline.pipeline")

    result = load_features(tracking, metadata)
    expected = [
        baseline.nearest_team(
            np.column_stack((frame / [100, 60], np.full(3, 999))),
            np.array([0, 1], dtype=np.int8),
            np.array([100, 60]),
        )
        for frame in positions
    ]

    assert result.nearest_code.tolist() == expected == [0, 1, -1, -1]
    np.testing.assert_allclose(result.nearest_home_distance_m[0], 10)
    assert result.visible_player_count.tolist() == [2, 1, 2, 0]
    assert result.ball_valid.tolist() == [True, True, False, True]


def test_motion_uses_metres_and_requires_continuous_observations(
    tmp_path: Path,
) -> None:
    ball_x = np.array([20, 21, 22, np.nan, 24, 25, 26, 27], dtype=float)
    positions = np.zeros((len(ball_x), 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:, 2, 0] = ball_x
    positions[:, 2, 1] = 20
    tracking, metadata = write_tracking(tmp_path, positions, fps=2)

    result = load_features(tracking, metadata)

    assert np.isnan(result.ball_speed_mps[[0, 3, 4]]).all()
    np.testing.assert_allclose(result.ball_speed_mps[[1, 2, 5, 6, 7]], 2)
    assert np.isnan(result.ball_displacement_1s_m[[0, 1, 3, 4, 5]]).all()
    np.testing.assert_allclose(result.ball_displacement_1s_m[[2, 6, 7]], 2)
    np.testing.assert_allclose(result.median_player_speed_mps[1:], 0)


def test_quality_filter_excludes_fast_player_but_keeps_newly_seen_player(
    tmp_path: Path,
) -> None:
    positions = np.array(
        [
            [[10, 20], [21, 20], [20, 20]],
            [[20, 20], [21, 20], [20, 20]],
            [[np.nan, np.nan], [21, 20], [20, 20]],
            [[20, 20], [21, 20], [20, 20]],
        ],
        dtype=float,
    )
    tracking, metadata = write_tracking(tmp_path, positions, fps=10)

    result = load_features(tracking, metadata)

    assert result.nearest_code.tolist() == [1, 0, 1, 0]
    assert result.quality_nearest_code.tolist() == [1, 1, 1, 0]
    assert np.isinf(result.quality_home_distance_m[1])
    assert np.isnan(result.nearest_player_speed_mps[1])


def test_quality_filter_excludes_fast_ball_without_changing_raw_nearest(
    tmp_path: Path,
) -> None:
    positions = np.array(
        [[[10, 20], [30, 20], [10, 20]], [[10, 20], [30, 20], [30, 20]]],
        dtype=float,
    )
    tracking, metadata = write_tracking(tmp_path, positions, fps=10)

    result = load_features(tracking, metadata)

    assert result.nearest_code.tolist() == [0, 1]
    assert result.quality_nearest_code.tolist() == [0, -1]
    np.testing.assert_allclose(result.ball_speed_mps[1], 200)


def test_motion_does_not_bridge_absent_source_frames(tmp_path: Path) -> None:
    positions = np.array(
        [[[10, 20], [30, 20], [20, 20]], [[10, 20], [30, 20], [21, 20]]],
        dtype=float,
    )
    tracking, metadata = write_tracking(
        tmp_path, positions, fps=2, frame_indices=[0, 2]
    )

    result = load_features(tracking, metadata)

    assert result.nearest_code.tolist() == [0, -1, 1]
    assert np.isnan(result.ball_speed_mps).all()
    assert np.isnan(result.ball_displacement_1s_m).all()
    assert np.isnan(result.median_player_speed_mps).all()
