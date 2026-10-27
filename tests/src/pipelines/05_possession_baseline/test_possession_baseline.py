"""Check the nearest-player baseline on the synthetic EPTS fixture."""

import csv
import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
RESOURCES = ROOT / "tests" / "resources" / "pipeline"
possession_baseline = importlib.import_module(
    "src.pipelines.05_possession_baseline"
).run_pipeline


def read_labels(path: Path) -> list[str]:
    with path.open(newline="") as source:
        rows = list(csv.DictReader(source))
    assert [int(row["frame"]) for row in rows] == list(range(len(rows)))
    return [row["label"] for row in rows]


def test_possession_baseline_labels_nearest_team_and_missing_ball_unsmoothed(
    tmp_path: Path,
) -> None:
    # Frame 0: away is nearer in metres. Frame 1: only home is seen. Frame 2: no ball.
    submission, metadata = possession_baseline(
        tracking=RESOURCES / "tracking.txt",
        metadata=RESOURCES / "metadata.xml",
        output_dir=tmp_path,
        window=0,
    )

    assert read_labels(submission) == ["A", "H", "D"]
    description = json.loads(metadata.read_text())
    assert description["ball_located_frames"] == 2
    assert description["label_counts"] == {"H": 1, "A": 1, "D": 1}
    assert description["teams"] == {"H": "Home", "A": "Away"}


def test_possession_baseline_majority_vote_breaks_ties_for_home(
    tmp_path: Path,
) -> None:
    submission, _ = possession_baseline(
        tracking=RESOURCES / "tracking.txt",
        metadata=RESOURCES / "metadata.xml",
        output_dir=tmp_path,
        window=1,
    )

    assert read_labels(submission) == ["H", "H", "H"]


def test_possession_baseline_refuses_existing_outputs(tmp_path: Path) -> None:
    arguments = dict(
        tracking=RESOURCES / "tracking.txt",
        metadata=RESOURCES / "metadata.xml",
        output_dir=tmp_path,
    )
    possession_baseline(**arguments)

    with pytest.raises(FileExistsError):
        possession_baseline(**arguments)


def test_possession_baseline_cli_prints_output_paths(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "src.pipelines.05_possession_baseline",
            "--tracking",
            str(RESOURCES / "tracking.txt"),
            "--metadata",
            str(RESOURCES / "metadata.xml"),
            "--output-dir",
            str(tmp_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.split() == [
        str(tmp_path / "possession_baseline.csv"),
        str(tmp_path / "possession_baseline.metadata.json"),
    ]
