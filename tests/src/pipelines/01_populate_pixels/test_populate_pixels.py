"""Check the numbered tracking export using valid synthetic EPTS data."""

import csv
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
RESOURCES = ROOT / "tests" / "resources" / "pipeline"
CORE_COLUMNS = {
    "frame",
    "entity_id",
    "entity_type",
    "team_id",
    "pos_x",
    "pos_y",
    "speed_raw",
    "position_valid",
}
populate_pixels = importlib.import_module(
    "src.pipelines.01_populate_pixels"
).run_pipeline


def read_rows(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    keyed = {(int(row["frame"]), row["entity_id"]): row for row in rows}
    assert len(keyed) == len(rows), "Each frame/entity pair must occur once"
    return keyed


def test_populate_pixels_exports_perspective_missing_positions_and_invalid_calibration(
    tmp_path: Path,
) -> None:
    output, metadata = populate_pixels(
        tracking=RESOURCES / "tracking.txt",
        metadata=RESOURCES / "metadata.xml",
        homography=RESOURCES / "homography.csv",
        output_dir=tmp_path,
    )
    rows = read_rows(output)

    assert output.name == "tracking_pixels.csv"
    assert metadata.name == "tracking_pixels.metadata.json"
    assert len(rows) == 9
    assert set(rows[0, "player_7"]) == CORE_COLUMNS | {
        "homography_valid",
        "reprojection_error",
    }
    assert rows[0, "player_7"]["team_id"] == "home"
    assert rows[0, "player_42"]["team_id"] == "away"
    assert rows[0, "ball"]["team_id"] == ""
    assert rows[0, "ball"]["entity_type"] == "ball"
    assert rows[0, "player_7"]["homography_valid"] == "True"
    assert rows[0, "player_7"]["position_valid"] == "True"
    assert float(rows[0, "player_7"]["pos_x"]) == pytest.approx(15 / 1.05)
    assert float(rows[0, "player_7"]["pos_y"]) == pytest.approx(20 / 1.05)
    assert float(rows[0, "ball"]["pos_x"]) == pytest.approx(63 / 1.25)
    assert float(rows[0, "ball"]["pos_y"]) == pytest.approx(44 / 1.25)
    for entity in ("player_7", "player_42", "ball"):
        assert rows[1, entity]["pos_x"] == rows[1, entity]["pos_y"] == ""
        assert rows[1, entity]["position_valid"] == "False"
        assert rows[1, entity]["homography_valid"] == "False"
        assert rows[1, entity]["reprojection_error"] == ""
    assert float(rows[1, "ball"]["speed_raw"]) == 6
    assert float(rows[1, "player_42"]["speed_raw"]) == 5
    assert float(rows[2, "player_7"]["pos_x"]) == pytest.approx(110)
    assert float(rows[2, "player_7"]["pos_y"]) == pytest.approx(-10)
    assert rows[2, "player_42"]["position_valid"] == "False"
    assert rows[2, "player_42"]["pos_x"] == rows[2, "player_42"]["pos_y"] == ""
    assert float(rows[2, "player_42"]["speed_raw"]) == 8


def test_populate_pixels_cli_runs_with_only_src_and_describes_export(
    tmp_path: Path,
) -> None:
    project = tmp_path / "isolated_project"
    shutil.copytree(
        ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipelines.01_populate_pixels",
            "--tracking",
            str(RESOURCES / "tracking.txt"),
            "--metadata",
            str(RESOURCES / "metadata.xml"),
            "--homography",
            str(RESOURCES / "homography.csv"),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        "output/tracking_pixels.csv",
        "output/tracking_pixels.metadata.json",
    ]
    assert str(RESOURCES / "metadata.xml") in result.stderr
    assert str(RESOURCES / "tracking.txt") in result.stderr
    assert str(RESOURCES / "homography.csv") in result.stderr
    assert "Completed 01_populate_pixels: 3 frames, 9 rows in " in result.stderr
    assert "output/tracking_pixels.csv" in result.stderr
    assert "output/tracking_pixels.metadata.json" in result.stderr
    assert "\r" not in result.stderr
    output = project / "output"
    metadata = json.loads((output / "tracking_pixels.metadata.json").read_text())
    assert metadata["fps"] == 25
    assert metadata["pitch_dimensions"] == {
        "length": 100,
        "width": 60,
        "unit": "metres",
    }
    assert metadata["coordinate_space"] == "video_pixels"
    assert metadata["position_unit"] == "pixels"
    assert metadata["speed_unit"] == "kph"
    assert metadata["frame_count"] == 3
    assert metadata["row_count"] == 9
    assert metadata["player_slot_count"] == 2
    assert metadata["entity_count_per_frame"] == 3
    assert metadata["teams"] == {"home": "Home", "away": "Away"}
    assert set(read_rows(output / "tracking_pixels.csv")) == {
        (frame, entity)
        for frame in range(3)
        for entity in ("player_7", "player_42", "ball")
    }

    failed = subprocess.run(
        result.args, cwd=project, env=environment, capture_output=True, text=True
    )
    assert failed.returncode != 0
    assert failed.stdout == ""
    assert "FileExistsError" in failed.stderr
    assert "Completed" not in failed.stderr
