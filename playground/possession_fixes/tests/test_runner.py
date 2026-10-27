"""Verify frozen, reproducible fix experiments and operationally safe exports."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from playground.creative.tests.fixtures import experiment_inputs
from playground.possession_fixes.runner import run_fix_experiments
from playground.possession_fixes.specs import ANCHOR, BASELINE, FIX_EXPERIMENTS

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def fix_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    return tracking, metadata, tags, truth


def test_runner_freezes_predictions_before_truth_and_exports_official_scores(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fix_inputs: tuple[Path, Path, Path, Path],
) -> None:
    tracking, metadata, tags, truth = fix_inputs
    inputs_before = {path: path.read_bytes() for path in fix_inputs}
    read_csv = pd.read_csv
    truth_reads = []

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            references = list(tmp_path.rglob(f"{BASELINE.id}/possession.csv"))
            assert len(references) == 1
            run = references[0].parent.parent
            frozen = json.loads((run / "frozen_predictions.json").read_text())
            assert (run / "evidence.csv").is_file()
            for spec in FIX_EXPERIMENTS:
                submitted = run / spec.id / "possession.csv"
                assert submitted.is_file()
                assert (
                    frozen[spec.id]
                    == hashlib.sha256(submitted.read_bytes()).hexdigest()
                )
            truth_reads.append(path)
        return read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    ranges = ((100, 130), (700, 720))

    report = run_fix_experiments(
        tracking, metadata, tags, truth, tmp_path / "run", ranges
    )

    assert truth_reads
    assert report == tmp_path / "run" / "REPORT.md"
    summary = json.loads((report.parent / "summary.json").read_text())
    assert summary["baseline_exact_match"] is True
    assert summary["default_f03_exact_match"] is True
    assert len(summary["experiments"]) == len(FIX_EXPERIMENTS)
    report_text = report.read_text()
    for row in summary["experiments"]:
        directory = report.parent / row["experiment_id"]
        official = json.loads((directory / "possession.scores.json").read_text())
        assert row["spell_f1"] == official["spell_f1_mean"]
        assert row["macro_f1"] == official["macro_f1"]
        submission = read_csv(directory / "possession.csv")
        assert submission["frame"].tolist() == list(range(1000))
        assert set(submission["label"]) <= {"H", "A", "D"}
        assert row["experiment_id"] in report_text
        for filename in (
            "experiment.json",
            "stoppage_audit.json",
            "extra_dead_intervals.csv",
            "review.json",
        ):
            assert (directory / filename).is_file()
        reviewed = json.loads((directory / "review.json").read_text())
        assert reviewed["ranges"] == row["review_ranges"]
        assert [
            (item["start_frame"], item["end_frame_exclusive"])
            for item in reviewed["ranges"]
        ] == list(ranges)
    baseline = read_csv(report.parent / BASELINE.id / "possession.csv")
    reference = read_csv(report.parent / "step05_reference" / "possession_baseline.csv")
    assert baseline.equals(reference)
    evidence = read_csv(report.parent / "evidence.csv")
    assert evidence["frame"].tolist() == list(range(1000))
    assert {path: path.read_bytes() for path in fix_inputs} == inputs_before


def test_predictions_and_evidence_do_not_depend_on_truth_or_review_ranges(
    tmp_path: Path, fix_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = fix_inputs
    alternate_truth = tmp_path / "alternate_truth.csv"
    labels = pd.read_csv(truth)
    labels["label"] = ["H"] * 500 + ["A"] * 250 + ["D"] * 250
    labels.to_csv(alternate_truth, index=False)

    first = run_fix_experiments(
        tracking, metadata, tags, truth, tmp_path / "first", ((100, 130),)
    )
    second = run_fix_experiments(
        tracking,
        metadata,
        tags,
        alternate_truth,
        tmp_path / "second",
        ((100, 130),),
    )
    third = run_fix_experiments(
        tracking,
        metadata,
        tags,
        truth,
        tmp_path / "third",
        ((0, 10), (900, 950)),
    )

    for comparison in (second, third):
        for filename in ("evidence.csv", "frozen_predictions.json"):
            assert (first.parent / filename).read_bytes() == (
                comparison.parent / filename
            ).read_bytes()
        for spec in FIX_EXPERIMENTS:
            for filename in (
                "possession.csv",
                "stoppage_audit.json",
                "extra_dead_intervals.csv",
            ):
                relative = Path(spec.id) / filename
                assert (first.parent / relative).read_bytes() == (
                    comparison.parent / relative
                ).read_bytes()
    original = json.loads((first.parent / "summary.json").read_text())
    altered = json.loads((second.parent / "summary.json").read_text())
    other_ranges = json.loads((third.parent / "summary.json").read_text())
    assert (
        original["experiments"][0]["macro_f1"] != altered["experiments"][0]["macro_f1"]
    )
    assert (
        original["experiments"][0]["macro_f1"]
        == other_ranges["experiments"][0]["macro_f1"]
    )
    assert (
        original["experiments"][0]["review_ranges"]
        != other_ranges["experiments"][0]["review_ranges"]
    )


def test_runner_preserves_existing_outputs_and_cleans_failed_exports(
    tmp_path: Path, fix_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = fix_inputs
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous run")
    before = set(tmp_path.iterdir())

    with pytest.raises(FileExistsError):
        run_fix_experiments(tracking, metadata, tags, truth, existing)

    assert sentinel.read_text() == "previous run"
    failed = tmp_path / "failed"
    with pytest.raises(FileNotFoundError):
        run_fix_experiments(
            tracking, metadata, tags, tmp_path / "absent_truth.csv", failed
        )
    assert not failed.exists()
    assert set(tmp_path.iterdir()) == before


def test_cli_accepts_multiple_review_ranges_and_logs_loading_and_scoring(
    tmp_path: Path, fix_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = fix_inputs
    destination = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playground.possession_fixes",
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
            "--review-range",
            "100",
            "130",
            "--review-range",
            "700",
            "720",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )

    assert result.stdout.splitlines() == [str(destination / "REPORT.md")]
    for path in (tracking, metadata, tags, destination):
        assert str(path) in result.stderr
    assert "step 06" in result.stderr
    assert "Completed" in result.stderr
    protocol = json.loads((destination / "protocol.json").read_text())
    assert protocol["review_ranges"] == [[100, 130], [700, 720]]
    reviewed = json.loads((destination / ANCHOR.id / "review.json").read_text())
    assert [
        (item["start_frame"], item["end_frame_exclusive"])
        for item in reviewed["ranges"]
    ] == [(100, 130), (700, 720)]
