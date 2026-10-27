"""Recovered-ball evidence must retain the original feature contract."""

from pathlib import Path

import numpy as np

from playground.creative.feature_adapter import rebuild_ball_features
from playground.creative.raw_tracks import load_raw_tracks
from playground.features import load_features
from playground.tests.fixtures import write_tracking


def test_rebuilding_original_ball_exactly_preserves_evidence(tmp_path: Path) -> None:
    count = 30
    positions = np.zeros((count, 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:, 2, 0] = 15 + np.arange(count) / 10
    positions[:, 2, 1] = 20
    positions[8:11, 2] = np.nan
    positions[18, 0] = [25, 20]
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)

    rebuilt = rebuild_ball_features(base, raw, raw.positions[:, -1])

    for name in (
        "ball_x_m",
        "ball_y_m",
        "ball_valid",
        "ball_speed_mps",
        "ball_displacement_1s_m",
        "nearest_home_distance_m",
        "nearest_away_distance_m",
        "nearest_code",
        "quality_home_distance_m",
        "quality_away_distance_m",
        "quality_nearest_code",
        "nearest_player_speed_mps",
    ):
        np.testing.assert_array_equal(getattr(rebuilt, name), getattr(base, name))


def test_recovered_ball_changes_control_evidence_without_mutating_inputs(
    tmp_path: Path,
) -> None:
    positions = np.array(
        [
            [[10, 20], [30, 20], [11, 20]],
            [[10, 20], [30, 20], [np.nan, np.nan]],
            [[10, 20], [30, 20], [29, 20]],
        ],
        dtype=float,
    )
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)
    recovered = raw.positions[:, -1].copy()
    recovered[1] = [29, 20]

    rebuilt = rebuild_ball_features(base, raw, recovered)

    assert base.nearest_code.tolist() == [0, -1, 1]
    assert rebuilt.nearest_code.tolist() == [0, 1, 1]
    assert rebuilt.ball_valid.tolist() == [True, True, True]
    np.testing.assert_array_equal(
        rebuilt.visible_player_count, base.visible_player_count
    )
    np.testing.assert_array_equal(
        rebuilt.median_player_speed_mps, base.median_player_speed_mps
    )
    assert np.isnan(raw.positions[1, -1]).all()
