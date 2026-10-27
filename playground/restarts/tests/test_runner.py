"""Check prediction isolation, official scoring and safe restart-batch exports."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from playground.creative.tests.fixtures import experiment_inputs
from playground.restarts.runner import run_restart_experiments
from playground.restarts.specs import RESTART_EXPERIMENTS

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def restart_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Add a genuine stationary-then-moving free kick to the synthetic recording."""
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    records = tracking.read_text().splitlines()
    for frame in range(205, 241):
        prefix, _ = records[frame].rsplit(":", 1)
        x = 50.0 if frame < 220 else 50.0 + 0.3 * (frame - 219)
        records[frame] = f"{prefix}:{x / 100},0.5,999"
    tracking.write_text("\n".join(records) + "\n")
    root = ET.Element("file")
    instances = ET.SubElement(root, "ALL_INSTANCES")
    instance = ET.SubElement(instances, "instance")
    for name, value in (
        ("ID", "synthetic-free-kick"),
        ("start", "20"),
        ("end", "24"),
        ("code", "SET PIECES"),
    ):
        ET.SubElement(instance, name).text = value
    for group, value in (("Team", "Home"), ("Type", "Free Kick")):
        label = ET.SubElement(instance, "label")
        ET.SubElement(label, "group").text = group
        ET.SubElement(label, "text").text = value
    ET.ElementTree(root).write(tags)
    return tracking, metadata, tags, truth


def test_restart_runner_freezes_all_submissions_before_official_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    restart_inputs: tuple[Path, Path, Path, Path],
) -> None:
    tracking, metadata, tags, truth = restart_inputs
    inputs_before = {path: path.read_bytes() for path in restart_inputs}
    original_read_csv = pd.read_csv
    truth_reads = []

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            references = list(
                tmp_path.rglob(f"{RESTART_EXPERIMENTS[0].id}/possession.csv")
            )
            assert len(references) == 1
            run = references[0].parent.parent
            for spec in RESTART_EXPERIMENTS:
                assert (run / spec.id / "possession.csv").is_file()
            truth_reads.append(path)
        return original_read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)

    report = run_restart_experiments(tracking, metadata, tags, truth, tmp_path / "run")

    assert truth_reads
    assert report == tmp_path / "run" / "REPORT.md"
    summary = json.loads((report.parent / "summary.json").read_text())
    assert summary["baseline_exact_match"] is True
    assert summary["occlusion_reference_exact_match"] is True
    assert len(summary["experiments"]) == len(RESTART_EXPERIMENTS)
    report_text = report.read_text()
    anchor = report.parent / RESTART_EXPERIMENTS[1].id / "possession.csv"
    changed_variants = []
    for row in summary["experiments"]:
        directory = report.parent / row["experiment_id"]
        score = json.loads((directory / "possession.scores.json").read_text())
        assert row["spell_f1"] == score["spell_f1_mean"]
        assert row["macro_f1"] == score["macro_f1"]
        submission = original_read_csv(directory / "possession.csv")
        assert submission["frame"].tolist() == list(range(1000))
        assert set(submission["label"]) <= {"H", "A", "D"}
        assert row["experiment_id"] in report_text
        if row["experiment_id"] not in {
            RESTART_EXPERIMENTS[0].id,
            RESTART_EXPERIMENTS[1].id,
        }:
            changed_variants.append(
                (directory / "possession.csv").read_bytes() != anchor.read_bytes()
            )
    assert any(changed_variants)
    assert {path: path.read_bytes() for path in restart_inputs} == inputs_before


def test_restart_predictions_are_independent_of_possession_ground_truth(
    tmp_path: Path, restart_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = restart_inputs
    alternative = tmp_path / "alternative.csv"
    labels = pd.read_csv(truth)
    labels["label"] = ["H"] * 500 + ["A"] * 250 + ["D"] * 250
    labels.to_csv(alternative, index=False)

    first = run_restart_experiments(tracking, metadata, tags, truth, tmp_path / "first")
    second = run_restart_experiments(
        tracking, metadata, tags, alternative, tmp_path / "second"
    )

    for spec in RESTART_EXPERIMENTS:
        relative = Path(spec.id) / "possession.csv"
        assert (first.parent / relative).read_bytes() == (
            second.parent / relative
        ).read_bytes()
    original = json.loads((first.parent / "summary.json").read_text())
    changed = json.loads((second.parent / "summary.json").read_text())
    assert (
        original["experiments"][0]["macro_f1"] != changed["experiments"][0]["macro_f1"]
    )


def test_restart_runner_preserves_existing_runs_and_cleans_failed_exports(
    tmp_path: Path, restart_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = restart_inputs
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous run")
    before = set(tmp_path.iterdir())

    with pytest.raises(FileExistsError):
        run_restart_experiments(tracking, metadata, tags, truth, existing)

    assert sentinel.read_text() == "previous run"
    failed = tmp_path / "failed"
    with pytest.raises(FileNotFoundError):
        run_restart_experiments(
            tracking, metadata, tags, tmp_path / "absent_truth.csv", failed
        )
    assert not failed.exists()
    assert set(tmp_path.iterdir()) == before


def test_restart_cli_publishes_reports_and_logs_input_and_output_paths(
    tmp_path: Path, restart_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = restart_inputs
    destination = tmp_path / "cli"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "playground.restarts",
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
    assert str(tags) in result.stderr
    assert str(destination) in result.stderr
    assert "step 06" in result.stderr
    frozen = json.loads((destination / "frozen_predictions.json").read_text())
    for spec in RESTART_EXPERIMENTS:
        directory = destination / spec.id
        assert (directory / "possession.scores.json").is_file()
        assert (
            frozen[spec.id]
            == hashlib.sha256((directory / "possession.csv").read_bytes()).hexdigest()
        )
