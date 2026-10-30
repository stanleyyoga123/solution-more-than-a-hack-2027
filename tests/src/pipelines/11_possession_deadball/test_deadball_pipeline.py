"""Pipeline 11 timeline labels, sidecar, CLI and export safety."""

import csv
from dataclasses import replace
from importlib import import_module
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

from tests.fixtures.possession_control import write_tracking
from tests.fixtures.possession_deadball import PACKAGE, PossessionPolicy

pipeline = import_module(PACKAGE + ".pipeline")
ROOT = Path(__file__).resolve().parents[4]
METADATA = ROOT / "tests/resources/possession_control/metadata.xml"
TAGS = "<file><ALL_INSTANCES></ALL_INSTANCES></file>"

# 100 frames at 10 FPS: first half 0..49 kicks off at 0, second half 60..99 at 70.
POLICY = replace(
    PossessionPolicy(),
    activity_window_seconds=1,
    minimum_stoppage_seconds=2,
    graded_halves=((0, 49), (60, 99)),
    kickoff_frames=(0, 70),
)


def inputs(directory: Path) -> tuple[Path, Path, Path]:
    """Both players run, walk through frames 20..44, then run again; ball by home."""
    step = np.full(100, 0.3)
    step[20:45] = 0.05
    distance = np.cumsum(step)
    positions = np.zeros((100, 3, 2))
    positions[:, 0] = np.c_[distance, np.full(100, 20.0)]
    positions[:, 1] = np.c_[distance + 40, np.full(100, 40.0)]
    positions[:, 2] = np.c_[distance + 0.5, np.full(100, 20.0)]
    tracking, _ = write_tracking(directory, positions)
    tags = directory / "tags.xml"
    tags.write_text(TAGS)
    return tracking, METADATA, tags


def read_labels(path: Path) -> list[str]:
    with path.open(newline="") as source:
        return [row["label"] for row in csv.DictReader(source)]


def test_labels_follow_halves_kickoffs_and_stoppage(tmp_path: Path) -> None:
    submission, sidecar = pipeline.run_pipeline(
        *inputs(tmp_path), tmp_path / "out", POLICY
    )

    labels = read_labels(submission)
    description = json.loads(sidecar.read_text())

    assert labels[:10] == ["H"] * 10
    assert labels[28:42] == ["D"] * 14
    assert labels[46:50] == ["H"] * 4
    assert labels[50:60] == ["X"] * 10
    assert labels[60:70] == ["D"] * 10
    assert labels[75:] == ["H"] * 25
    assert description["label_counts"] == {
        label: labels.count(label) for label in "HADX"
    }
    assert description["inputs"]["smart_tagging"].endswith("tags.xml")
    assert submission.name == "possession_deadball.csv"
    assert sidecar.name == "possession_deadball.metadata.json"


def test_predictions_are_deterministic(tmp_path: Path) -> None:
    arguments = inputs(tmp_path)
    first, _ = pipeline.run_pipeline(*arguments, tmp_path / "first", POLICY)
    second, _ = pipeline.run_pipeline(*arguments, tmp_path / "second", POLICY)

    assert first.read_bytes() == second.read_bytes()


def test_pipeline_refuses_existing_output_and_preserves_both_files(
    tmp_path: Path,
) -> None:
    arguments = inputs(tmp_path)
    outputs = pipeline.run_pipeline(*arguments, tmp_path / "out", POLICY)
    before = [path.read_bytes() for path in outputs]

    with pytest.raises(FileExistsError):
        pipeline.run_pipeline(*arguments, tmp_path / "out", POLICY)

    assert [path.read_bytes() for path in outputs] == before


def test_cli_prints_only_published_paths(tmp_path: Path) -> None:
    tracking, metadata, tags = inputs(tmp_path)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            PACKAGE,
            "--tracking",
            str(tracking),
            "--metadata",
            str(metadata),
            "--smart-tagging",
            str(tags),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [
        str(tmp_path / "out/possession_deadball.csv"),
        str(tmp_path / "out/possession_deadball.metadata.json"),
    ]
    assert "Completed 11_possession_deadball" in result.stderr
