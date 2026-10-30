"""Control evidence preserves source timing, physical units and missingness."""

from importlib import import_module
from pathlib import Path

import numpy as np

from tests.fixtures.possession_control import write_tracking

TrackingEvidenceLoader = import_module(
    "src.pipelines.10_possession_control.evidence.tracking_loader"
).TrackingEvidenceLoader


def test_nearest_team_uses_xml_slot_order_and_retains_missing_evidence(
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

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert result.nearest_code.tolist() == [0, 1, -1, -1]
    assert result.nearest_home_distance_m[0] == 10
    assert np.isinf(result.nearest_home_distance_m[1:]).all()
    assert result.processed_tracking_frames == 4


def test_ball_speed_uses_observed_metres_and_resets_after_missing_positions(
    tmp_path: Path,
) -> None:
    positions = np.zeros((8, 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:, 2, 0] = [20, 21, 22, np.nan, 24, 25, 26, 27]
    positions[:, 2, 1] = 20
    tracking, metadata = write_tracking(tmp_path, positions, fps=2)

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert np.isnan(result.ball_speed_mps[[0, 3, 4]]).all()
    np.testing.assert_allclose(result.ball_speed_mps[[1, 2, 5, 6, 7]], 2)


def test_absent_source_frame_does_not_connect_ball_speed(tmp_path: Path) -> None:
    positions = np.array(
        [[[10, 20], [30, 20], [20, 20]], [[10, 20], [30, 20], [21, 20]]],
        dtype=float,
    )
    tracking, metadata = write_tracking(
        tmp_path, positions, fps=2, frame_indices=[0, 2]
    )

    result = TrackingEvidenceLoader().load(tracking, metadata)

    assert result.nearest_code.tolist() == [0, -1, 1]
    assert np.isnan(result.ball_speed_mps).all()
    assert result.frame_count == 3
    assert result.processed_tracking_frames == 2
