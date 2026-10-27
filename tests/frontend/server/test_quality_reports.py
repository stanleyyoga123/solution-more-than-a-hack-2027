"""Quality review report aggregation and its optional HTTP/CLI integration."""

from contextlib import closing
import csv
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread
from unittest.mock import MagicMock

import pytest

from frontend.__main__ import main
from frontend.server.application import create_server
from frontend.server.quality_report_store import load_quality_reports

FLAG_COLUMNS = (
    "entity_id",
    "entity_type",
    "team_id",
    "start_frame",
    "end_frame",
    "speed_mps",
    "acceleration_mps2",
    "speed_flag",
    "acceleration_flag",
)
GAP_COLUMNS = (
    "entity_id",
    "entity_type",
    "team_id",
    "start_frame",
    "end_frame",
    "missing_frames",
    "gap_seconds",
    "left_frame",
    "right_frame",
    "endpoint_distance_m",
    "required_speed_mps",
    "forward_error_m",
    "backward_error_m",
    "status",
    "reason",
)


def write_report(path: Path, columns: tuple[str, ...], rows: list[tuple]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as destination:
        writer = csv.writer(destination)
        writer.writerow(columns)
        writer.writerows(rows)
    return path


def test_quality_report_groups_support_intervals_and_preserves_entity_peaks(
    tmp_path: Path,
) -> None:
    flags = write_report(
        tmp_path / "flags.csv",
        FLAG_COLUMNS,
        [
            ("player_1", "player", "home", 8, 10, 13, 5, True, False),
            ("player_2", "player", "away", 8, 10, 14, "", True, False),
            ("ball", "ball", "", 9, 10, 50, "", True, False),
            ("player_1", "player", "home", 9, 11, 15, 20, True, True),
            ("player_1", "player", "home", 12, 13, 8, 30, False, True),
            ("player_1", "player", "home", 15, 17, 3, 40, False, True),
            ("player_1", "player", "home", 16, 18, 4, 50, False, True),
        ],
    )

    result = load_quality_reports(flags, None)

    assert result["available"] == {"trajectories": True, "gaps": False}
    assert result["summary"]["flagged_samples"] == 7
    assert result["summary"]["trajectory_episodes"] == 4
    assert [episode["id"] for episode in result["episodes"]] == [
        "motion:player_1:8",
        "motion:player_2:8",
        "motion:ball:9",
        "motion:player_1:15",
    ]
    first = result["episodes"][0]
    assert (first["start_frame"], first["end_frame"]) == (8, 13)
    assert first["sample_count"] == 3
    assert first["peak_frame"] == 11
    assert first["peak_speed_mps"] == 15
    assert first["peak_acceleration_mps2"] == 30
    assert first["speed_flag"] is True
    assert first["acceleration_flag"] is True
    assert result["episodes"][2]["peak_acceleration_mps2"] is None
    assert result["episodes"][3]["peak_frame"] == 18


def test_quality_report_retains_gap_status_and_nullable_metrics(tmp_path: Path) -> None:
    gaps = write_report(
        tmp_path / "gaps.csv",
        GAP_COLUMNS,
        [
            (
                "player_2",
                "player",
                "home",
                10,
                19,
                10,
                0.4,
                9,
                20,
                1.2,
                2.7,
                0.5,
                0.4,
                "plausible",
                "motion_consistent",
            ),
            (
                "ball",
                "ball",
                "",
                0,
                4,
                5,
                0.2,
                "",
                5,
                "",
                "",
                "",
                "",
                "uncertain",
                "unbounded_gap",
            ),
            (
                "player_1",
                "player",
                "away",
                30,
                34,
                5,
                0.2,
                29,
                35,
                20,
                83.3,
                "",
                "",
                "implausible",
                "excessive_required_speed",
            ),
        ],
    )

    result = load_quality_reports(None, gaps)

    assert result["available"] == {"trajectories": False, "gaps": True}
    assert result["summary"]["gap_count"] == 3
    assert result["summary"]["status_counts"] == {
        "plausible": 1,
        "implausible": 1,
        "uncertain": 1,
    }
    first = result["gaps"][0]
    assert first["id"] == "gap:ball:0"
    assert first["start_frame"] == 0
    assert first["gap_seconds"] == 0.2
    assert first["left_frame"] is None
    assert first["right_frame"] == 5
    assert first["required_speed_mps"] is None
    json.dumps(result, allow_nan=False)


def test_quality_report_exposes_unavailable_and_header_only_reports(
    tmp_path: Path,
) -> None:
    empty = load_quality_reports(None, None)
    assert empty["available"] == {"trajectories": False, "gaps": False}
    assert empty["episodes"] == empty["gaps"] == []
    flags = write_report(tmp_path / "flags.csv", FLAG_COLUMNS, [])
    gaps = write_report(tmp_path / "gaps.csv", GAP_COLUMNS, [])

    result = load_quality_reports(flags, gaps)

    assert result["available"] == {"trajectories": True, "gaps": True}
    assert result["summary"] == empty["summary"]


def test_quality_report_surfaces_explicit_missing_input(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_quality_reports(tmp_path / "missing.csv", None)


def test_quality_route_serves_startup_snapshot_and_head_without_affecting_frames(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_id,entity_type,team_id,pos_x,pos_y,position_valid\n"
        "0,ball,ball,,0.2,0.3,True\n"
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 1, "fps": 25}))
    video = tmp_path / "video.mp4"
    video.write_bytes(b"0123456789")
    flags = write_report(
        tmp_path / "flags.csv",
        FLAG_COLUMNS,
        [("ball", "ball", "", 0, 1, 50, "", True, False)],
    )
    monkeypatch.setattr(
        "frontend.server.application.read_video_metadata",
        lambda _: {"width": 100, "height": 50},
    )
    with create_server(
        video,
        tracking,
        tracking,
        metadata,
        tmp_path / "cache",
        0,
        trajectory_flags=flags,
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        flags.unlink()
        try:
            with closing(HTTPConnection("127.0.0.1", server.server_port)) as connection:
                connection.request("GET", "/api/quality")
                response = connection.getresponse()
                assert response.status == 200
                body = response.read()
                assert json.loads(body)["summary"]["flagged_samples"] == 1
                connection.request("HEAD", "/api/quality")
                response = connection.getresponse()
                assert response.status == 200
                assert int(response.getheader("Content-Length")) == len(body)
                assert response.read() == b""
                connection.request("GET", "/api/frames?start=0&count=1")
                response = connection.getresponse()
                assert response.status == 200
                assert json.loads(response.read())["frames"][0]["frame"] == 0
        finally:
            server.shutdown()
            thread.join()


@pytest.mark.parametrize("custom_flags", [False, True])
def test_quality_cli_detects_reports_independently_and_preserves_explicit_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, custom_flags: bool
) -> None:
    monkeypatch.chdir(tmp_path)
    output = tmp_path / "output"
    output.mkdir()
    default_gaps = output / "tracking_gap_continuity.csv"
    default_gaps.touch()
    args = ["frontend"]
    if custom_flags:
        args += ["--trajectory-flags", "custom.csv"]
    monkeypatch.setattr("sys.argv", args)
    server = MagicMock()
    server.__enter__.return_value = server
    server.serve_forever.side_effect = KeyboardInterrupt
    create = MagicMock(return_value=server)
    monkeypatch.setattr("frontend.__main__.create_server", create)

    main()

    assert create.call_args.kwargs["gap_continuity"] == Path(
        "output/tracking_gap_continuity.csv"
    )
    assert create.call_args.kwargs["trajectory_flags"] == (
        Path("custom.csv") if custom_flags else None
    )
