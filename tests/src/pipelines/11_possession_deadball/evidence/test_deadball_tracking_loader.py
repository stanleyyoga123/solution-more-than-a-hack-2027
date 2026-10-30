"""Evidence keeps metres, source timing and missing observations."""

from importlib import import_module
from pathlib import Path

import numpy as np

from tests.fixtures.possession_control import write_tracking
from tests.fixtures.possession_deadball import PACKAGE

TrackingEvidenceLoader = import_module(
    PACKAGE + ".evidence.tracking_loader"
).TrackingEvidenceLoader
read_set_piece_windows = import_module(
    PACKAGE + ".evidence.set_piece_tags"
).read_set_piece_windows


def test_player_speed_is_mean_step_in_metres_per_second(tmp_path: Path) -> None:
    positions = np.zeros((4, 3, 2))
    positions[:, 0, 0] = [10, 11, 12, 13]
    positions[:, 1, 0] = [30, 30, 30, 30]
    positions[:, 2] = [20, 20]
    tracking, metadata = write_tracking(tmp_path, positions, fps=2)

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert np.isnan(result.player_speed_mps[0])
    np.testing.assert_allclose(result.player_speed_mps[1:], 1)


def test_identity_switch_jump_is_not_counted_as_running(tmp_path: Path) -> None:
    positions = np.zeros((3, 3, 2))
    positions[:, 0, 0] = [10, 11, 60]
    positions[:, 1, 0] = [30, 31, 32]
    positions[:, 2] = [20, 20]
    tracking, metadata = write_tracking(tmp_path, positions, fps=1)

    result = TrackingEvidenceLoader().load(tracking, metadata)

    np.testing.assert_allclose(result.player_speed_mps[1:], [1, 1])


def test_absent_source_frame_leaves_speeds_unknown(tmp_path: Path) -> None:
    positions = np.array(
        [[[10, 20], [30, 20], [20, 20]], [[11, 20], [31, 20], [21, 20]]], dtype=float
    )
    tracking, metadata = write_tracking(
        tmp_path, positions, fps=2, frame_indices=[0, 2]
    )

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert np.isnan(result.player_speed_mps).all()
    assert np.isnan(result.ball_speed_mps).all()
    assert result.ball_x_m[2] == 21


def test_ball_position_is_scaled_to_metres_and_off_pitch_is_kept(
    tmp_path: Path,
) -> None:
    positions = np.zeros((2, 3, 2))
    positions[:, 2] = [[-5, 70], [20, 20]]
    tracking, metadata = write_tracking(tmp_path, positions)

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert result.ball_x_m.tolist() == [-5, 20]
    assert result.ball_y_m.tolist() == [70, 20]


def test_set_piece_windows_keep_only_set_pieces_as_frames(tmp_path: Path) -> None:
    path = tmp_path / "tags.xml"
    path.write_text(
        "<file><ALL_INSTANCES>"
        "<instance><start>2</start><end>4.5</end><code>SET PIECES</code></instance>"
        "<instance><start>9</start><end>10</end><code>BUILD UP</code></instance>"
        "</ALL_INSTANCES></file>"
    )

    assert read_set_piece_windows(path, 10) == [(20, 45)]
