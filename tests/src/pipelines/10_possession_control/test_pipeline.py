"""Standalone pipeline 10 reference parity, CLI and export safety."""

import csv
from importlib import import_module
import json
import logging
from pathlib import Path
import subprocess
import sys

import pytest

PACKAGE = "src.pipelines.10_possession_control"
pipeline = import_module(PACKAGE + ".pipeline")
ROOT = Path(__file__).resolve().parents[4]
RESOURCES = ROOT / "tests/resources/possession_control"


def input_paths() -> tuple[Path, Path]:
    return RESOURCES / "tracking.txt", RESOURCES / "metadata.xml"


def read_submission(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))


def test_pipeline_reproduces_isolated_control_confirmation_labels(
    tmp_path: Path,
) -> None:
    submission, sidecar = pipeline.run_pipeline(*input_paths(), tmp_path)
    intervals = json.loads((RESOURCES / "expected_intervals.json").read_text())
    expected = []
    for start, end, label in intervals:
        assert start == len(expected)
        expected.extend([label] * (end - start))

    rows = read_submission(submission)
    description = json.loads(sidecar.read_text())

    assert [int(row["frame"]) for row in rows] == list(range(100))
    assert [row["label"] for row in rows] == expected
    assert submission.name == "submission.csv"
    assert sidecar.name == "submission.metadata.json"
    assert description["frame_count"] == description["processed_tracking_frames"] == 100
    assert description["label_counts"] == {
        label: expected.count(label) for label in "HAD"
    }
    assert description["teams"] == {"H": "Home", "A": "Away"}
    assert description["fps"] == 10
    assert description["inputs"] == {
        name: str(path.resolve())
        for name, path in zip(("tracking", "metadata"), input_paths(), strict=True)
    }


def test_predictions_are_deterministic(tmp_path: Path) -> None:
    first, _ = pipeline.run_pipeline(*input_paths(), tmp_path / "first")
    second, _ = pipeline.run_pipeline(*input_paths(), tmp_path / "second")

    assert first.read_bytes() == second.read_bytes()


def test_pipeline_refuses_existing_output_and_preserves_both_files(
    tmp_path: Path,
) -> None:
    outputs = pipeline.run_pipeline(*input_paths(), tmp_path)
    before = [path.read_bytes() for path in outputs]

    with pytest.raises(FileExistsError):
        pipeline.run_pipeline(*input_paths(), tmp_path)

    assert [path.read_bytes() for path in outputs] == before


def test_failed_publication_removes_partial_output_pair(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    export_files = import_module("src.utilities.export_files")
    real_link = export_files.os.link

    def reject_metadata_link(source: Path, destination: Path) -> None:
        if str(destination).endswith(".metadata.json"):
            raise OSError("publication unavailable")
        real_link(source, destination)

    monkeypatch.setattr(export_files.os, "link", reject_metadata_link)

    with pytest.raises(OSError, match="publication unavailable"):
        pipeline.run_pipeline(*input_paths(), tmp_path)

    assert list(tmp_path.iterdir()) == []
    assert "Completed 10_possession_control" not in caplog.text


def test_cli_prints_only_published_paths(tmp_path: Path) -> None:
    arguments = [sys.executable, "-m", PACKAGE]
    for flag, path in zip(("--tracking", "--metadata"), input_paths(), strict=True):
        arguments.extend((flag, str(path)))
    arguments.extend(("--output-dir", str(tmp_path)))

    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, text=True, check=True
    )

    assert result.stdout.splitlines() == [
        str(tmp_path / "submission.csv"),
        str(tmp_path / "submission.metadata.json"),
    ]
    assert "Completed 10_possession_control" in result.stderr
