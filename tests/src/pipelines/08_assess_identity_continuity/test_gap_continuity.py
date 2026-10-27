"""Same-slot null-gap decisions and integration with trajectory screening."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.fixtures.tracking_quality import (
    Position,
    read_rows,
    write_flags,
    write_tracking,
)

ROOT = Path(__file__).resolve().parents[4]
assess_continuity = importlib.import_module(
    "src.pipelines.08_assess_identity_continuity"
).run_pipeline


def test_continuity_reports_plausible_motion_using_actual_endpoint_elapsed_time(
    tmp_path: Path,
) -> None:
    positions: list[Position] = [(0.1 * frame, 0) for frame in range(10)]
    positions[3:5] = [None, None]
    tracking, metadata = write_tracking(tmp_path / "inputs", {"player_1": positions})
    flags, flags_metadata = write_flags(tmp_path / "flags")
    original = tracking.read_bytes()

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    rows = read_rows(report)
    assert len(rows) == 1
    row = rows[0]
    assert row["status"] == "plausible"
    assert row["reason"] == "motion_consistent"
    assert (row["start_frame"], row["end_frame"]) == ("3", "4")
    assert (row["left_frame"], row["right_frame"]) == ("2", "5")
    assert row["missing_frames"] == "2"
    assert float(row["gap_seconds"]) == pytest.approx(0.2)
    assert float(row["endpoint_distance_m"]) == pytest.approx(0.3)
    assert float(row["required_speed_mps"]) == pytest.approx(1)
    assert float(row["forward_error_m"]) == pytest.approx(0, abs=1e-12)
    assert float(row["backward_error_m"]) == pytest.approx(0, abs=1e-12)
    assert tracking.read_bytes() == original


@pytest.mark.parametrize(
    ("missing", "shift", "expected_status", "expected_reason"),
    [
        (range(3, 23), 0, "plausible", "motion_consistent"),
        (range(3, 24), 0, "uncertain", "long_gap"),
        (range(1, 3), 0, "uncertain", "insufficient_context"),
        (range(3, 5), 3, "uncertain", "motion_disagreement"),
        (range(3, 5), 4, "implausible", "excessive_required_speed"),
        (range(3, 24), 40, "implausible", "excessive_required_speed"),
    ],
    ids=[
        "duration-at-limit",
        "long-gap",
        "short-context",
        "motion-disagreement",
        "too-fast",
        "speed-before-duration",
    ],
)
def test_continuity_classifies_bounded_gaps_with_documented_precedence(
    tmp_path: Path,
    missing: range,
    shift: float,
    expected_status: str,
    expected_reason: str,
) -> None:
    positions: list[Position] = [(0.1 * frame, 0) for frame in range(27)]
    for frame in missing:
        positions[frame] = None
    for frame in range(missing.stop, len(positions)):
        positions[frame] = (0.1 * frame + shift, 0)
    tracking, metadata = write_tracking(tmp_path / "inputs", {"player_1": positions})
    flags, flags_metadata = write_flags(tmp_path / "flags")

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    row = read_rows(report)[0]
    assert row["status"] == expected_status
    assert row["reason"] == expected_reason


@pytest.mark.parametrize(
    ("interval", "expected_reason"),
    [
        (("player_1", 0, 1), "flagged_context"),
        (("player_1", 7, 8), "flagged_context"),
        (("player_1", 8, 9), "motion_consistent"),
        (("player_2", 0, 1), "motion_consistent"),
    ],
    ids=[
        "left-context-boundary",
        "right-context-boundary",
        "outside-context",
        "other-entity",
    ],
)
def test_continuity_matches_flags_by_entity_and_inclusive_context_overlap(
    tmp_path: Path,
    interval: tuple[str, int, int],
    expected_reason: str,
) -> None:
    positions: list[Position] = [(0.1 * frame, 0) for frame in range(10)]
    positions[3:5] = [None, None]
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {"player_1": positions, "player_2": [(1, 0)] * len(positions)},
    )
    flags, flags_metadata = write_flags(tmp_path / "flags", [interval])

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    assert read_rows(report)[0]["reason"] == expected_reason


def test_continuity_prefers_flagged_context_over_excessive_required_speed(
    tmp_path: Path,
) -> None:
    positions: list[Position] = [(0, 0)] * 3 + [None, None] + [(10, 0)] * 5
    tracking, metadata = write_tracking(tmp_path / "inputs", {"player_1": positions})
    flags, flags_metadata = write_flags(tmp_path / "flags", [("player_1", 5, 6)])

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    row = read_rows(report)[0]
    assert row["status"] == "uncertain"
    assert row["reason"] == "flagged_context"


def test_continuity_preserves_unbounded_and_all_null_slots_and_does_not_merge_ids(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {
            "player_2": [(0, 0), (0, 0), None, None, None, None],
            "player_1": [None, None, (0, 0), (0, 0), (0, 0), (0, 0)],
            "player_3": [None] * 6,
        },
    )
    flags, flags_metadata = write_flags(tmp_path / "flags", [("player_1", 2, 3)])

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    rows = read_rows(report)
    assert [(r["entity_id"], r["start_frame"], r["end_frame"]) for r in rows] == [
        ("player_1", "0", "1"),
        ("player_3", "0", "5"),
        ("player_2", "2", "5"),
    ]
    assert all(r["reason"] == "unbounded_gap" for r in rows)
    assert all(r["status"] == "uncertain" for r in rows)
    assert rows[0]["left_frame"] == ""
    assert rows[0]["right_frame"] == "2"
    assert rows[1]["left_frame"] == rows[1]["right_frame"] == ""
    assert rows[2]["left_frame"] == "1"
    assert rows[2]["right_frame"] == ""
    assert all(r["required_speed_mps"] == "" for r in rows)


def test_continuity_treats_partial_nulls_as_gaps_and_rounds_context_up(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {"player_1": [(0, 0), (0.1, 0), (None, 0.2), (0.3, 0), (0.4, 0), (0.5, 0)]},
        fps=7,
    )
    flags, flags_metadata = write_flags(tmp_path / "flags")

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    row = read_rows(report)[0]
    assert (row["start_frame"], row["end_frame"]) == ("2", "2")
    assert row["reason"] == "insufficient_context"


def test_continuity_does_not_build_velocity_context_across_an_earlier_gap(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs",
        {
            "player_1": [
                (0, 0),
                None,
                (0.2, 0),
                (0.3, 0),
                None,
                (0.5, 0),
                (0.6, 0),
                (0.7, 0),
            ]
        },
    )
    flags, flags_metadata = write_flags(tmp_path / "flags")

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    rows = read_rows(report)
    assert len(rows) == 2
    assert rows[1]["start_frame"] == "4"
    assert rows[1]["reason"] == "insufficient_context"


@pytest.mark.parametrize("entity", ["player_1", "ball"])
def test_continuity_uses_speed_limits_from_flag_metadata(
    tmp_path: Path,
    entity: str,
) -> None:
    positions: list[Position] = [(0.1 * frame, 0) for frame in range(8)]
    positions[3:5] = [None, None]
    tracking, metadata = write_tracking(tmp_path / "inputs", {entity: positions})
    flags, flags_metadata = write_flags(
        tmp_path / "flags", player_speed_limit=0.5, ball_speed_limit=0.5
    )

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    assert read_rows(report)[0]["reason"] == "excessive_required_speed"


@pytest.mark.parametrize(
    ("shift", "player_reason", "ball_reason"),
    [
        (2, "motion_consistent", "motion_consistent"),
        (2.5, "motion_disagreement", "motion_consistent"),
        (3, "motion_disagreement", "motion_consistent"),
        (3.1, "motion_disagreement", "motion_disagreement"),
    ],
)
def test_continuity_uses_separate_player_and_ball_prediction_tolerances(
    tmp_path: Path,
    shift: float,
    player_reason: str,
    ball_reason: str,
) -> None:
    positions: list[Position] = [(0, 0)] * 3 + [None, None] + [(shift, 0)] * 3
    tracking, metadata = write_tracking(
        tmp_path / "inputs", {"player_1": positions, "ball": positions}
    )
    flags, flags_metadata = write_flags(tmp_path / "flags")

    report, _ = assess_continuity(
        tracking, metadata, flags, flags_metadata, tmp_path / "out"
    )

    rows = {row["entity_id"]: row for row in read_rows(report)}
    assert rows["player_1"]["reason"] == player_reason
    assert rows["ball"]["reason"] == ball_reason
    assert float(rows["ball"]["forward_error_m"]) == pytest.approx(shift)


def test_quality_clis_publish_header_only_reports_and_refuse_overwrite(
    tmp_path: Path,
) -> None:
    tracking, metadata = write_tracking(
        tmp_path / "inputs", {"player_1": [(0, 0)] * 4, "ball": [(1, 1)] * 4}
    )
    flag_dir = tmp_path / "flags"
    gap_dir = tmp_path / "gaps"
    flag_command = [
        sys.executable,
        "-m",
        "src.pipelines.07_flag_impossible_trajectories",
        "--tracking",
        str(tracking),
        "--metadata",
        str(metadata),
        "--output-dir",
        str(flag_dir),
    ]
    flag_result = subprocess.run(flag_command, cwd=ROOT, capture_output=True, text=True)
    assert flag_result.returncode == 0, flag_result.stderr
    flags, flags_metadata = map(Path, flag_result.stdout.splitlines())
    command = [
        sys.executable,
        "-m",
        "src.pipelines.08_assess_identity_continuity",
        "--tracking",
        str(tracking),
        "--metadata",
        str(metadata),
        "--flags",
        str(flags),
        "--flags-metadata",
        str(flags_metadata),
        "--output-dir",
        str(gap_dir),
    ]

    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        str(gap_dir / "tracking_gap_continuity.csv"),
        str(gap_dir / "tracking_gap_continuity.metadata.json"),
    ]
    assert read_rows(flags) == []
    assert read_rows(Path(result.stdout.splitlines()[0])) == []
    assert "Completed" in flag_result.stderr
    assert "Completed" in result.stderr
    assert str(tracking) in result.stderr
    assert str(flags) in result.stderr
    assert "\r" not in result.stderr
    assert isinstance(json.loads(Path(result.stdout.splitlines()[1]).read_text()), dict)
    failed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    assert failed.returncode != 0
    assert failed.stdout == ""
    assert "Completed" not in failed.stderr
