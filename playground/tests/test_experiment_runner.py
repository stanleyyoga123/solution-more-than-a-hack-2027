"""End-to-end reproducibility, frozen inference, and experiment publication."""

import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pytest

from playground.experiments import EXPERIMENTS
from playground.runner import run_experiments

from .fixtures import ROOT, write_tracking


def experiment_inputs(directory: Path) -> tuple[Path, Path, Path, Path]:
    positions = np.zeros((120, 3, 2))
    positions[:, 0] = [10, 20]
    positions[:, 1] = [30, 20]
    positions[:40, 2] = [10, 20]
    positions[40:80, 2] = [30, 20]
    positions[80:, 2] = np.nan
    tracking, metadata = write_tracking(directory, positions)
    tags = directory / "tags.xml"
    root = ET.Element("file")
    ET.SubElement(root, "ALL_INSTANCES")
    ET.ElementTree(root).write(tags)
    truth = directory / "truth.csv"
    pd.DataFrame(
        {"frame": np.arange(120), "label": ["H"] * 40 + ["A"] * 40 + ["D"] * 40}
    ).to_csv(truth, index=False)
    return tracking, metadata, tags, truth


def test_runner_freezes_every_prediction_before_reading_ground_truth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracking, metadata, tags, truth = experiment_inputs(tmp_path / "inputs")
    destination = tmp_path / "run"
    original_read_csv = pd.read_csv
    ground_truth_reads = []

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            staged_runs = list(tmp_path.glob(".run-*/run"))
            assert len(staged_runs) == 1
            for spec in EXPERIMENTS:
                assert (staged_runs[0] / spec.id / "possession.csv").is_file()
            ground_truth_reads.append(path)
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

    report = run_experiments(tracking, metadata, tags, truth, destination)

    assert ground_truth_reads
    assert report == destination / "REPORT.md"
    summary = json.loads((destination / "summary.json").read_text())
    assert summary["baseline_exact_match"] is True
    assert len(summary["experiments"]) == len(EXPERIMENTS)
    for spec, row in zip(EXPERIMENTS, summary["experiments"], strict=True):
        folder = destination / spec.id
        official_score = json.loads((folder / "possession.scores.json").read_text())
        assert row["spell_f1"] == official_score["spell_f1_mean"]
        assert row["macro_f1"] == official_score["macro_f1"]
        assert f"## {spec.id}:" in report.read_text()
    assert not list(tmp_path.glob(".run-*"))


def test_ground_truth_changes_scores_without_changing_predictions(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, truth = experiment_inputs(tmp_path / "inputs")
    alternate_truth = tmp_path / "alternate_truth.csv"
    table = pd.read_csv(truth)
    table["label"] = table["label"].map({"H": "A", "A": "D", "D": "H"})
    table.to_csv(alternate_truth, index=False)

    run_experiments(tracking, metadata, tags, truth, tmp_path / "first")
    run_experiments(tracking, metadata, tags, alternate_truth, tmp_path / "second")

    for spec in EXPERIMENTS:
        relative = Path(spec.id) / "possession.csv"
        assert (tmp_path / "first" / relative).read_bytes() == (
            tmp_path / "second" / relative
        ).read_bytes()
    first = json.loads((tmp_path / "first" / "summary.json").read_text())
    second = json.loads((tmp_path / "second" / "summary.json").read_text())
    assert first["experiments"][0]["macro_f1"] != second["experiments"][0]["macro_f1"]


def test_runner_refuses_existing_run_and_cleans_failed_staging(tmp_path: Path) -> None:
    tracking, metadata, tags, truth = experiment_inputs(tmp_path / "inputs")
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous experiment")

    with pytest.raises(FileExistsError):
        run_experiments(tracking, metadata, tags, truth, existing)

    assert sentinel.read_text() == "previous experiment"
    with pytest.raises(FileNotFoundError):
        run_experiments(
            tracking, metadata, tags, tmp_path / "absent_truth.csv", tmp_path / "failed"
        )
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed-*"))


def test_cli_runs_all_variants_and_prints_report_path(tmp_path: Path) -> None:
    tracking, metadata, tags, truth = experiment_inputs(tmp_path / "inputs")
    destination = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playground",
            "--tracking",
            str(tracking),
            "--metadata",
            str(metadata),
            "--tags",
            str(tags),
            "--ground-truth",
            str(truth),
            "--output-dir",
            str(destination),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [str(destination / "REPORT.md")]
    assert "All predictions frozen; starting step 06 evaluation" in result.stderr
    assert len(list(destination.glob("e*/possession.scores.json"))) == len(EXPERIMENTS)
