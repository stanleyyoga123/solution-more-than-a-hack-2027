"""Synthetic evidence and end-to-end submission checks."""

import csv
import importlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest

PACKAGE = "src.pipelines.09_possession_inference"
RESOURCES = Path(__file__).resolve().parents[4] / "tests/resources/pipeline"


@pytest.mark.parametrize(
    "evidence,limit,expected",
    [
        ("HXXH", 2, "HHHH"),
        ("HXXXH", 2, "HXXXH"),
        ("HXXA", 2, "HXXA"),
        ("XHHAX", 2, "XHHAX"),
        ("HXH", 0, "HXH"),
    ],
)
def test_continuity_only_bridges_short_matching_gaps(evidence, limit, expected):
    strategy = importlib.import_module(PACKAGE + ".strategy")
    result = strategy.infer(np.array(list(evidence)), ((0, len(evidence) - 1),), limit)
    assert "".join(result) == expected


def test_continuity_resets_between_adjacent_halves():
    strategy = importlib.import_module(PACKAGE + ".strategy")
    result = strategy.infer(np.array(list("HHXXHH")), ((1, 2), (3, 4)), 25)
    assert "".join(result) == "XHXXHX"


def test_evidence_matches_baseline():
    strategy = importlib.import_module(PACKAGE + ".strategy")
    baseline = importlib.import_module("src.pipelines.05_possession_baseline.pipeline")
    teams = np.array([0, 1], dtype=np.int8)
    pitch = np.array([100, 60])
    for ball in ([0.1, 0.2], [0.9, 0.8], [np.nan, np.nan], [0.5, 0.5]):
        values = np.array([[0.1, 0.2, 0], [0.9, 0.8, 0], [*ball, 0]])
        code = baseline.nearest_team(values, teams, pitch)
        expected = {0: "H", 1: "A", -1: "X"}[code]
        assert strategy.nearest_label(values, teams, pitch) == expected


def test_submission_is_complete_deterministic_and_safe(tmp_path):
    run = importlib.import_module(PACKAGE).run_pipeline
    tracking = tmp_path / "tracking.txt"
    # Source IDs are one-based tactical video frames, as in the shared ATD reader.
    tracking.write_text(
        "11186:0,0,0;1,1,0:0,0,0\n"
        "11187:0,0,0;1,1,0:nan,nan,0\n"
        "11188:0,0,0;1,1,0:0,0,0\n"
    )
    args = (tracking, RESOURCES / "metadata.xml")
    csv_path, sidecar = run(*args, tmp_path / "first")
    other, _ = run(*args, tmp_path / "second")
    assert csv_path.read_bytes() == other.read_bytes()
    with csv_path.open() as source:
        rows = list(csv.DictReader(source))
    assert [int(row["frame"]) for row in rows] == list(range(199319))
    labels = [row["label"] for row in rows]
    assert set(labels) <= set("HADX")
    assert labels[11185:11188] == ["H"] * 3
    assert labels[11184] == labels[11188] == labels[-1] == "X"
    document = json.loads(sidecar.read_text())
    assert document["label_counts"] == {"H": 3, "A": 0, "D": 0, "X": 199316}
    assert document["strategy"] == "nearest-continuity"
    before = csv_path.read_bytes(), sidecar.read_bytes()
    with pytest.raises(FileExistsError):
        run(*args, tmp_path / "first")
    assert before == (csv_path.read_bytes(), sidecar.read_bytes())


def test_cli_prints_published_paths(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            PACKAGE,
            "--tracking",
            str(RESOURCES / "tracking.txt"),
            "--metadata",
            str(RESOURCES / "metadata.xml"),
            "--strategy",
            "nearest-continuity",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [
        str(tmp_path / "possession_inference.csv"),
        str(tmp_path / "possession_inference.metadata.json"),
    ]


def test_published_boundaries_and_official_validation(tmp_path):
    pipeline = importlib.import_module(PACKAGE + ".pipeline")
    from src.utilities import possession_metrics as metrics

    tracking = tmp_path / "edges.txt"
    inside = {11185, 90651, 110808, 190197}
    outside = {11184, 90652, 110807, 190198}
    tracking.write_text(
        "".join(
            f"{frame + 1}:0,0,0;1,1,0:0,0,0\n" for frame in sorted(inside | outside)
        )
    )
    path, _ = pipeline.run_pipeline(
        tracking, RESOURCES / "metadata.xml", tmp_path / "out"
    )
    table = metrics.read_label_csv(path)
    assert metrics.validate_submission(table, 199319) is None
    assert all(table.iloc[frame]["label"] == "H" for frame in inside)
    assert all(table.iloc[frame]["label"] == "X" for frame in outside)
