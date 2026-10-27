"""Filtered player coordinates must update every dependent possession feature."""

from dataclasses import fields, replace
from pathlib import Path

import numpy as np

from playground.creative.raw_tracks import load_raw_tracks
from playground.features import load_features
from playground.reacquisition.features import rebuild_player_features
from playground.tests.fixtures import write_tracking


def test_noop_rebuild_matches_all_loaded_features_including_motion_and_missingness(
    tmp_path: Path,
):
    count = 35
    positions = np.zeros((count, 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:, -1, 0] = 15 + np.arange(count) / 10
    positions[:, -1, 1] = 20
    positions[8:11, -1] = np.nan
    positions[18, 0] = [25, 20]
    positions[24:28, 1] = np.nan
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)

    rebuilt = rebuild_player_features(base, raw)

    for field in fields(base):
        expected = getattr(base, field.name)
        if isinstance(expected, np.ndarray):
            np.testing.assert_array_equal(getattr(rebuilt, field.name), expected)
    assert rebuilt.metadata == base.metadata


def test_filtered_nearest_player_changes_control_distances_and_visible_counts(
    tmp_path: Path,
):
    positions = np.tile([[10.0, 20.0], [30.0, 20.0], [11.0, 20.0]], (5, 1, 1))
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)
    filtered_positions = raw.positions.copy()
    filtered_positions[2:, 0] = np.nan
    filtered = replace(raw, positions=filtered_positions)

    rebuilt = rebuild_player_features(base, filtered)

    assert base.nearest_code.tolist() == [0] * 5
    assert rebuilt.nearest_code.tolist() == [0, 0, 1, 1, 1]
    assert np.isinf(rebuilt.nearest_home_distance_m[2:]).all()
    assert rebuilt.nearest_away_distance_m.tolist() == [19] * 5
    assert rebuilt.quality_nearest_code.tolist() == [0, 0, 1, 1, 1]
    assert rebuilt.visible_player_count.tolist() == [2, 2, 1, 1, 1]
    np.testing.assert_array_equal(raw.positions, positions)
    for name in (
        "ball_x_m",
        "ball_y_m",
        "ball_valid",
        "ball_speed_mps",
        "ball_displacement_1s_m",
    ):
        assert getattr(rebuilt, name) is getattr(base, name)


def test_all_missing_players_produce_unknown_control_and_motion(tmp_path: Path):
    positions = np.tile([[10.0, 20.0], [30.0, 20.0], [11.0, 20.0]], (5, 1, 1))
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)
    filtered_positions = raw.positions.copy()
    filtered_positions[2:, :-1] = np.nan

    rebuilt = rebuild_player_features(base, replace(raw, positions=filtered_positions))

    assert (rebuilt.nearest_code[2:] == -1).all()
    assert (rebuilt.quality_nearest_code[2:] == -1).all()
    assert np.isinf(rebuilt.nearest_home_distance_m[2:]).all()
    assert np.isinf(rebuilt.nearest_away_distance_m[2:]).all()
    assert np.isnan(rebuilt.median_player_speed_mps[2:]).all()
    assert np.isnan(rebuilt.nearest_player_speed_mps[2:]).all()
    assert (rebuilt.visible_player_count[2:] == 0).all()


def test_filtered_median_and_nearest_speed_use_only_remaining_plausible_players(
    tmp_path: Path,
):
    count = 8
    positions = np.zeros((count, 3, 2))
    positions[:, 0] = np.column_stack((10 + np.arange(count) / 10, np.full(count, 20)))
    positions[:, 1] = np.column_stack((30 + np.arange(count) / 2, np.full(count, 20)))
    positions[:, -1] = [11, 20]
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)
    filtered_positions = raw.positions.copy()
    filtered_positions[:, 0] = np.nan

    rebuilt = rebuild_player_features(base, replace(raw, positions=filtered_positions))

    np.testing.assert_allclose(base.median_player_speed_mps[1:], 3)
    np.testing.assert_allclose(rebuilt.median_player_speed_mps[1:], 5)
    np.testing.assert_allclose(rebuilt.nearest_player_speed_mps[1:], 5)
    assert np.isnan(rebuilt.median_player_speed_mps[0])


def test_chunk_boundary_uses_the_previous_frame_for_player_speed(tmp_path: Path):
    count = 5003
    positions = np.zeros((count, 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:, -1] = [11, 20]
    positions[4999:, 0, 0] += np.arange(count - 4999) / 10
    tracking, metadata = write_tracking(tmp_path, positions)
    base = load_features(tracking, metadata)
    raw = load_raw_tracks(tracking, metadata)

    rebuilt = rebuild_player_features(base, raw)

    np.testing.assert_array_equal(
        rebuilt.median_player_speed_mps, base.median_player_speed_mps
    )
    np.testing.assert_array_equal(
        rebuilt.nearest_player_speed_mps, base.nearest_player_speed_mps
    )
