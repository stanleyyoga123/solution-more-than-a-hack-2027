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
normalize_2d = importlib.import_module("src.pipelines.02_normalize_2d").run_pipeline


def read_rows(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    keyed = {(int(row["frame"]), row["entity_id"]): row for row in rows}
    assert len(keyed) == len(rows), "Each frame/entity pair must occur once"
    return keyed


def test_normalize_2d_preserves_raw_coordinates_without_clamping_or_homography(
    tmp_path: Path,
) -> None:
    output, metadata = normalize_2d(
        tracking=RESOURCES / "tracking.txt",
        metadata=RESOURCES / "metadata.xml",
        output_dir=tmp_path,
    )
    rows = read_rows(output)

    assert output.name == "tracking_normalized_2d.csv"
    assert metadata.name == "tracking_normalized_2d.metadata.json"
    assert len(rows) == 9
    assert set(rows[0, "player_7"]) == CORE_COLUMNS
    assert float(rows[0, "player_7"]["pos_x"]) == pytest.approx(0.1)
    assert rows[0, "player_7"]["team_id"] == "home"
    assert rows[0, "player_42"]["team_id"] == "away"
    assert rows[1, "player_7"]["position_valid"] == "True"
    assert rows[1, "player_7"]["speed_raw"] == ""
    assert rows[1, "player_42"]["position_valid"] == "False"
    assert float(rows[1, "player_42"]["speed_raw"]) == 5
    assert float(rows[2, "player_7"]["pos_x"]) == pytest.approx(1.1)
    assert float(rows[2, "player_7"]["pos_y"]) == pytest.approx(-0.1)
    assert float(rows[2, "player_42"]["pos_x"]) == pytest.approx(0.2)
    assert rows[2, "player_42"]["pos_y"] == ""
    assert rows[2, "player_42"]["position_valid"] == "False"
    assert rows[2, "ball"]["pos_x"] == rows[2, "ball"]["pos_y"] == ""


def test_normalize_2d_cli_runs_with_only_src_and_describes_export(
    tmp_path: Path,
) -> None:
    project = tmp_path / "isolated_project"
    shutil.copytree(
        ROOT / "src", project / "src", ignore=shutil.ignore_patterns("__pycache__")
    )
    destination = tmp_path / "exports"
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipelines.02_normalize_2d",
            "--tracking",
            str(RESOURCES / "tracking.txt"),
            "--metadata",
            str(RESOURCES / "metadata.xml"),
            "--output-dir",
            str(destination),
        ],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == [
        str(destination / "tracking_normalized_2d.csv"),
        str(destination / "tracking_normalized_2d.metadata.json"),
    ]
    assert str(RESOURCES / "metadata.xml") in result.stderr
    assert str(RESOURCES / "tracking.txt") in result.stderr
    assert "Completed 02_normalize_2d: 3 frames, 9 rows in " in result.stderr
    assert str(destination / "tracking_normalized_2d.csv") in result.stderr
    assert str(destination / "tracking_normalized_2d.metadata.json") in result.stderr
    assert "\r" not in result.stderr
    metadata = json.loads(
        (destination / "tracking_normalized_2d.metadata.json").read_text()
    )
    assert metadata["fps"] == 25
    assert metadata["pitch_dimensions"] == {
        "length": 100,
        "width": 60,
        "unit": "metres",
    }
    assert metadata["coordinate_space"] == "normalized_pitch_2d"
    assert metadata["position_unit"] == "pitch_fraction"
    assert metadata["speed_unit"] == "kph"
    assert metadata["frame_count"] == 3
    assert metadata["row_count"] == 9
    assert metadata["player_slot_count"] == 2
    assert metadata["entity_count_per_frame"] == 3
    assert metadata["teams"] == {"home": "Home", "away": "Away"}
    assert set(read_rows(destination / "tracking_normalized_2d.csv")) == {
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
