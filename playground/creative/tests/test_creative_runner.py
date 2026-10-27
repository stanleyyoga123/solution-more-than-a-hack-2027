"""Creative branches must score frozen predictions and publish reproducibly."""

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from playground.creative.runner import run_creative_experiments
from playground.creative.specs import CREATIVE_EXPERIMENTS

from .fixtures import experiment_inputs

ROOT = Path(__file__).resolve().parents[3]


def test_creative_runner_freezes_all_predictions_before_official_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = experiment_inputs(tmp_path / "inputs")
    truth = inputs[-1]
    original_read_csv = pd.read_csv
    ground_truth_reads = []

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            staged_runs = list(tmp_path.glob(".run-*/run"))
            assert len(staged_runs) == 1
            for spec in CREATIVE_EXPERIMENTS:
                assert (staged_runs[0] / spec.id / "possession.csv").is_file()
            ground_truth_reads.append(path)
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

    report = run_creative_experiments(*inputs, tmp_path / "run")

    assert ground_truth_reads
    assert report == tmp_path / "run" / "REPORT.md"
    summary = json.loads((report.parent / "summary.json").read_text())
    assert summary["baseline_exact_match"] is True
    assert summary["control_reference_exact_match"] is True
    assert len(summary["experiments"]) == 8
    for row in summary["experiments"]:
        folder = report.parent / row["experiment_id"]
        score = json.loads((folder / "possession.scores.json").read_text())
        assert row["spell_f1"] == score["spell_f1_mean"]
        assert row["macro_f1"] == score["macro_f1"]
        assert f"## {row['experiment_id']}:" in report.read_text()
    collective = json.loads(
        (report.parent / "c06_collective_ball_estimate/diagnostics.json").read_text()
    )
    assert collective["status"] == "fitted"
    assert collective["holdout_all_geometry"]["frames"] > 100
    vision = json.loads(
        (report.parent / "c07_yolo_ball_recovery/diagnostics.json").read_text()
    )
    assert vision["filled_frames"] == 0
    assert not list(tmp_path.glob(".run-*"))


def test_creative_predictions_are_independent_of_possession_ground_truth(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, vision, truth = experiment_inputs(tmp_path / "inputs")
    alternative = tmp_path / "alternative.csv"
    table = pd.read_csv(truth)
    table["label"] = ["H"] * 500 + ["A"] * 250 + ["D"] * 250
    table.to_csv(alternative, index=False)

    first = run_creative_experiments(
        tracking, metadata, tags, vision, truth, tmp_path / "first"
    )
    second = run_creative_experiments(
        tracking, metadata, tags, vision, alternative, tmp_path / "second"
    )

    for spec in CREATIVE_EXPERIMENTS:
        relative = Path(spec.id) / "possession.csv"
        assert (first.parent / relative).read_bytes() == (
            second.parent / relative
        ).read_bytes()
    original = json.loads((first.parent / "summary.json").read_text())
    changed = json.loads((second.parent / "summary.json").read_text())
    assert (
        original["experiments"][0]["macro_f1"] != changed["experiments"][0]["macro_f1"]
    )


def test_creative_runner_preserves_existing_runs_and_cleans_failed_publication(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, vision, truth = experiment_inputs(tmp_path / "inputs")
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous run")

    with pytest.raises(FileExistsError):
        run_creative_experiments(tracking, metadata, tags, vision, truth, existing)

    assert sentinel.read_text() == "previous run"
    with pytest.raises(FileNotFoundError):
        run_creative_experiments(
            tracking,
            metadata,
            tags,
            vision,
            tmp_path / "absent_truth.csv",
            tmp_path / "failed",
        )
    assert not (tmp_path / "failed").exists()
    assert not list(tmp_path.glob(".failed-*"))


def test_creative_cli_generates_all_official_reports_without_model_downloads(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, vision, truth = experiment_inputs(tmp_path / "inputs")
    destination = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playground.creative",
            "--tracking",
            str(tracking),
            "--metadata",
            str(metadata),
            "--tags",
            str(tags),
            "--vision-recovery",
            str(vision),
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
    assert "Every creative prediction frozen; scoring with step 06" in result.stderr
    assert len(list(destination.glob("c*/possession.scores.json"))) == 8
