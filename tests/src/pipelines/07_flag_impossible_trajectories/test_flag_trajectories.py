"""Public behavior of the normalized-trajectory screening pipeline."""

import importlib
import json
import os
from pathlib import Path

import pytest

from tests.fixtures.tracking_quality import read_rows, write_tracking

flag_trajectories = importlib.import_module(
    "src.pipelines.07_flag_impossible_trajectories"
).run_pipeline


def test_flagging_keeps_constant_motion_and_off_pitch_positions_unflagged(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {
            "player_1": [(-2, 0), (-1, 0), (0, 0), (1, 0)],
            "ball": [(0, 0), (10, 0), (20, 0), (30, 0)],
        },
        fps=2,
    )
    original = tracking.read_bytes()

    report, description = flag_trajectories(tracking, metadata, tmp_path / "out")

    assert read_rows(report) == []
    assert tracking.read_bytes() == original
    assert report.name == "tracking_trajectory_flags.csv"
    assert json.loads(description.read_text())["thresholds"] == {
        "player_speed_limit_mps": 12,
        "player_acceleration_limit_mps2": 15,
        "ball_speed_limit_mps": 45,
    }


def test_flagging_scales_both_pitch_axes_and_uses_strict_speed_limit(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {"player_1": [(0, 0), (3, 4)], "player_2": [(0, 0), (0, 6)]},
        fps=2,
    )

    report, _ = flag_trajectories(
        tracking, metadata, tmp_path / "out", player_speed_limit=10
    )

    rows = read_rows(report)
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "player_2"
    assert float(rows[0]["speed_mps"]) == pytest.approx(12)
    assert (rows[0]["start_frame"], rows[0]["end_frame"]) == ("0", "1")
    assert rows[0]["speed_flag"] == "True"
    assert rows[0]["acceleration_flag"] == "False"
    assert rows[0]["acceleration_mps2"] == ""


def test_flagging_combines_speed_and_acceleration_with_full_support_interval(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs", {"player_1": [(0, 0), (0.25, 0), (1, 0)]}, fps=2
    )
    boundary_report, _ = flag_trajectories(
        tracking, metadata, tmp_path / "boundary", player_acceleration_limit=2
    )

    report, _ = flag_trajectories(
        tracking,
        metadata,
        tmp_path / "out",
        player_speed_limit=1,
        player_acceleration_limit=1.9,
    )

    warning_report, _ = flag_trajectories(
        tracking,
        metadata,
        tmp_path / "warning",
        player_acceleration_limit=1.9,
    )

    assert read_rows(boundary_report) == []
    warning = read_rows(warning_report)[0]
    assert warning["speed_flag"] == "False"
    assert warning["acceleration_flag"] == "True"
    rows = read_rows(report)
    assert len(rows) == 1
    assert (rows[0]["start_frame"], rows[0]["end_frame"]) == ("0", "2")
    assert float(rows[0]["speed_mps"]) == pytest.approx(1.5)
    assert float(rows[0]["acceleration_mps2"]) == pytest.approx(2)
    assert rows[0]["speed_flag"] == rows[0]["acceleration_flag"] == "True"


def test_flagging_checks_ball_speed_without_acceleration_warning(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs", {"ball": [(0, 0), (20, 0), (20, 0), (66, 0)]}, fps=1
    )

    report, _ = flag_trajectories(tracking, metadata, tmp_path / "out")

    rows = read_rows(report)
    assert len(rows) == 1
    assert rows[0]["end_frame"] == "3"
    assert float(rows[0]["speed_mps"]) == pytest.approx(46)
    assert rows[0]["acceleration_mps2"] == ""
    assert rows[0]["acceleration_flag"] == "False"


def test_flagging_resets_motion_after_partial_null_coordinates(tmp_path: Path) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {"player_1": [(0, 0), (1, 0), (None, 2), (100, 0), (101, 0)]},
        fps=1,
    )

    report, _ = flag_trajectories(tracking, metadata, tmp_path / "out")

    assert read_rows(report) == []


def test_flagging_refuses_existing_report_without_overwriting_it(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(tmp_path / "inputs", {"ball": [(0, 0)]})
    report, description = flag_trajectories(tracking, metadata, tmp_path / "out")
    original = (report.read_bytes(), description.read_bytes())

    with pytest.raises(FileExistsError):
        flag_trajectories(tracking, metadata, tmp_path / "out")

    assert (report.read_bytes(), description.read_bytes()) == original


def test_flagging_removes_partial_publication_when_metadata_link_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tracking, metadata = write_tracking(tmp_path / "inputs", {"ball": [(0, 0)]})
    original_link = os.link

    def fail_metadata_link(source: Path, destination: Path) -> None:
        if str(destination).endswith(".metadata.json"):
            raise OSError("simulated publication failure")
        original_link(source, destination)

    monkeypatch.setattr(os, "link", fail_metadata_link)

    with pytest.raises(OSError, match="simulated publication failure"):
        flag_trajectories(tracking, metadata, tmp_path / "out")

    assert list((tmp_path / "out").iterdir()) == []
