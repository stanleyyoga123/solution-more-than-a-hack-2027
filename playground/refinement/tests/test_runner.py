"""Exercise frozen predictions, official scoring, and safe batch publication."""

import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from playground.creative.tests.fixtures import experiment_inputs
from playground.refinement.runner import run_refinement_experiments
from playground.refinement.specs import REFINEMENT_EXPERIMENTS

ROOT = Path(__file__).resolve().parents[3]


def test_refinement_runner_freezes_every_submission_before_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    original_read_csv = pd.read_csv
    truth_reads = []

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            references = list(
                tmp_path.rglob(f"{REFINEMENT_EXPERIMENTS[0].id}/possession.csv")
            )
            assert len(references) == 1
            run_directory = references[0].parent.parent
            for spec in REFINEMENT_EXPERIMENTS:
                assert (run_directory / spec.id / "possession.csv").is_file()
            truth_reads.append(path)
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

    report = run_refinement_experiments(
        tracking, metadata, tags, truth, tmp_path / "run"
    )

    assert truth_reads
    assert report == tmp_path / "run" / "REPORT.md"
    summary = json.loads((report.parent / "summary.json").read_text())
    assert summary["baseline_exact_match"] is True
    assert summary["interception_reference_exact_match"] is True
    assert len(summary["experiments"]) == len(REFINEMENT_EXPERIMENTS)
    report_text = report.read_text()
    for row in summary["experiments"]:
        directory = report.parent / row["experiment_id"]
        score = json.loads((directory / "possession.scores.json").read_text())
        assert row["spell_f1"] == score["spell_f1_mean"]
        assert row["macro_f1"] == score["macro_f1"]
        submission = original_read_csv(directory / "possession.csv")
        assert submission["frame"].tolist() == list(range(1000))
        assert set(submission["label"]) <= {"H", "A", "D"}
        assert row["experiment_id"] in report_text


def test_refinement_predictions_do_not_depend_on_possession_ground_truth(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    alternative = tmp_path / "alternative.csv"
    table = pd.read_csv(truth)
    table["label"] = ["H"] * 500 + ["A"] * 250 + ["D"] * 250
    table.to_csv(alternative, index=False)

    first = run_refinement_experiments(
        tracking, metadata, tags, truth, tmp_path / "first"
    )
    second = run_refinement_experiments(
        tracking, metadata, tags, alternative, tmp_path / "second"
    )

    for spec in REFINEMENT_EXPERIMENTS:
        relative = Path(spec.id) / "possession.csv"
        assert (first.parent / relative).read_bytes() == (
            second.parent / relative
        ).read_bytes()
    original = json.loads((first.parent / "summary.json").read_text())
    changed = json.loads((second.parent / "summary.json").read_text())
    assert (
        original["experiments"][0]["macro_f1"] != changed["experiments"][0]["macro_f1"]
    )


def test_refinement_runner_preserves_existing_runs_and_cleans_failed_exports(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous run")

    with pytest.raises(FileExistsError):
        run_refinement_experiments(tracking, metadata, tags, truth, existing)

    assert sentinel.read_text() == "previous run"
    failed = tmp_path / "failed"
    with pytest.raises(FileNotFoundError):
        run_refinement_experiments(
            tracking, metadata, tags, tmp_path / "absent_truth.csv", failed
        )
    assert not failed.exists()
    assert set(tmp_path.iterdir()) == {tmp_path / "inputs", existing}


def test_refinement_cli_publishes_all_reports_and_logs_to_stderr(
    tmp_path: Path,
) -> None:
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    destination = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playground.refinement",
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
    assert str(tracking) in result.stderr
    assert str(destination) in result.stderr
    assert "step 06" in result.stderr
    for spec in REFINEMENT_EXPERIMENTS:
        assert (destination / spec.id / "possession.scores.json").is_file()
