"""Exercise real quarantine integration, frozen predictions and safe publication."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

import pandas as pd
import pytest

from playground.creative.tests.fixtures import experiment_inputs
from playground.reacquisition.runner import run_reacquisition_experiments
from playground.reacquisition.specs import (
    REACQUISITION_EXPERIMENTS,
    TRACKLET_EXPERIMENTS,
)

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def reacquisition_inputs(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    """Add one unreachable goalkeeper run followed by a physically plausible return."""
    tracking, metadata, tags, _, truth = experiment_inputs(tmp_path / "inputs")
    tree = ET.parse(metadata)
    player = tree.find("./Metadata/Players/Player")
    parameters = ET.SubElement(player, "ProviderPlayerParameters")
    parameter = ET.SubElement(parameters, "ProviderParameter")
    ET.SubElement(parameter, "Name").text = "position_type"
    ET.SubElement(parameter, "Value").text = "Goalkeeper"
    tree.write(metadata)
    lines = tracking.read_text().splitlines()
    for frame in range(200, 220):
        number, serialized_players, ball = lines[frame].split(":")
        players = serialized_players.split(";")
        if frame < 205 or frame >= 215:
            players[0] = "nan,nan,999"
        else:
            x, y, speed = players[0].split(",")
            players[0] = f"{float(x) + 0.5},{y},{speed}"
        lines[frame] = f"{number}:{';'.join(players)}:{ball}"
    tracking.write_text("\n".join(lines) + "\n")
    return tracking, metadata, tags, truth


@pytest.mark.parametrize("split_discontinuities", [False, True])
def test_runner_freezes_predictions_before_truth_and_scores_quarantined_tracks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    reacquisition_inputs: tuple[Path, Path, Path, Path],
    split_discontinuities: bool,
) -> None:
    tracking, metadata, tags, truth = reacquisition_inputs
    before = {path: path.read_bytes() for path in reacquisition_inputs}
    read_csv = pd.read_csv
    truth_reads = []
    specs = TRACKLET_EXPERIMENTS if split_discontinuities else REACQUISITION_EXPERIMENTS

    def guarded_read_csv(path, *args, **kwargs):
        if Path(path) == truth:
            references = list(tmp_path.rglob(f"{specs[0].id}/possession.csv"))
            assert len(references) == 1
            run = references[0].parent.parent
            frozen = json.loads((run / "frozen_predictions.json").read_text())
            for spec in specs:
                submitted = run / spec.id / "possession.csv"
                assert submitted.is_file()
                assert (
                    frozen[spec.id]
                    == hashlib.sha256(submitted.read_bytes()).hexdigest()
                )
            truth_reads.append(path)
        return read_csv(path, *args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", guarded_read_csv)
    ranges = ((190, 230), (700, 720))

    report = run_reacquisition_experiments(
        tracking,
        metadata,
        tags,
        truth,
        tmp_path / "run",
        ranges,
        split_discontinuities=split_discontinuities,
    )

    assert truth_reads
    assert report == tmp_path / "run" / "REPORT.md"
    summary = json.loads((report.parent / "summary.json").read_text())
    assert [row["experiment_id"] for row in summary["experiments"]] == [
        spec.id for spec in specs
    ]
    protocol = json.loads((report.parent / "protocol.json").read_text())
    assert protocol["split_discontinuities"] is split_discontinuities
    assert {path: path.read_bytes() for path in reacquisition_inputs} == before
    report_text = report.read_text()
    for spec, row in zip(specs, summary["experiments"], strict=True):
        folder = report.parent / spec.id
        score = json.loads((folder / "possession.scores.json").read_text())
        assert row["experiment_id"] == spec.id
        assert row["spell_f1"] == score["spell_f1_mean"]
        assert row["macro_f1"] == score["macro_f1"]
        submitted = read_csv(folder / "possession.csv")
        assert submitted["frame"].tolist() == list(range(1000))
        assert set(submitted["label"]) <= {"H", "A", "D"}
        assert spec.id in report_text
        for filename in (
            "experiment.json",
            "quarantine_audit.json",
            "stoppage_audit.json",
            "review.json",
        ):
            assert (folder / filename).is_file()
        reviewed = json.loads((folder / "review.json").read_text())
        assert reviewed["ranges"] == row["review_ranges"]
        assert [
            (item["start_frame"], item["end_frame_exclusive"])
            for item in reviewed["ranges"]
        ] == list(ranges)
        audit = json.loads((folder / "quarantine_audit.json").read_text())
        if spec.eligible == "none":
            assert audit["event_count"] == 0
        else:
            assert audit["event_count"] == 1
            assert audit["events"][0]["slot_id"] == "1"
            assert audit["events"][0]["start_frame"] == 205
            assert audit["events"][0]["end_frame_exclusive"] == 215


@pytest.mark.parametrize("split_discontinuities", [False, True])
def test_predictions_and_quarantine_do_not_depend_on_truth_or_review_ranges(
    tmp_path: Path,
    reacquisition_inputs: tuple[Path, Path, Path, Path],
    split_discontinuities: bool,
) -> None:
    tracking, metadata, tags, truth = reacquisition_inputs
    alternate_truth = tmp_path / "alternate_truth.csv"
    labels = pd.read_csv(truth)
    labels["label"] = ["H"] * 500 + ["A"] * 250 + ["D"] * 250
    labels.to_csv(alternate_truth, index=False)
    specs = TRACKLET_EXPERIMENTS if split_discontinuities else REACQUISITION_EXPERIMENTS

    first = run_reacquisition_experiments(
        tracking,
        metadata,
        tags,
        truth,
        tmp_path / "first",
        ((190, 230),),
        split_discontinuities=split_discontinuities,
    )
    second = run_reacquisition_experiments(
        tracking,
        metadata,
        tags,
        alternate_truth,
        tmp_path / "second",
        ((190, 230),),
        split_discontinuities=split_discontinuities,
    )
    third = run_reacquisition_experiments(
        tracking,
        metadata,
        tags,
        truth,
        tmp_path / "third",
        ((0, 10), (900, 950)),
        split_discontinuities=split_discontinuities,
    )

    for comparison in (second, third):
        assert (first.parent / "frozen_predictions.json").read_bytes() == (
            comparison.parent / "frozen_predictions.json"
        ).read_bytes()
        for spec in specs:
            for filename in (
                "possession.csv",
                "quarantine_audit.json",
                "stoppage_audit.json",
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
    tmp_path: Path, reacquisition_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = reacquisition_inputs
    existing = tmp_path / "existing"
    existing.mkdir()
    sentinel = existing / "keep.txt"
    sentinel.write_text("previous run")
    before = set(tmp_path.iterdir())

    with pytest.raises(FileExistsError):
        run_reacquisition_experiments(tracking, metadata, tags, truth, existing)

    assert sentinel.read_text() == "previous run"
    failed = tmp_path / "failed"
    with pytest.raises(FileNotFoundError):
        run_reacquisition_experiments(
            tracking, metadata, tags, tmp_path / "absent_truth.csv", failed
        )
    assert not failed.exists()
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("split_discontinuities", [False, True])
def test_cli_accepts_repeated_review_ranges_and_logs_loading_and_scoring(
    tmp_path: Path,
    reacquisition_inputs: tuple[Path, Path, Path, Path],
    split_discontinuities: bool,
) -> None:
    tracking, metadata, tags, truth = reacquisition_inputs
    destination = tmp_path / "cli"

    command = [
        sys.executable,
        "-m",
        "playground.reacquisition",
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
        "190",
        "230",
        "--review-range",
        "700",
        "720",
    ]
    if split_discontinuities:
        command.append("--split-discontinuities")

    result = subprocess.run(
        command,
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
    assert protocol["review_ranges"] == [[190, 230], [700, 720]]
    assert protocol["split_discontinuities"] is split_discontinuities
    specs = TRACKLET_EXPERIMENTS if split_discontinuities else REACQUISITION_EXPERIMENTS
    assert [item["id"] for item in protocol["experiments"]] == [
        spec.id for spec in specs
    ]
    reviewed = json.loads((destination / specs[0].id / "review.json").read_text())
    assert [
        (item["start_frame"], item["end_frame_exclusive"])
        for item in reviewed["ranges"]
    ] == [(190, 230), (700, 720)]


def test_tracklet_mode_restores_reachable_return_within_a_contiguous_run(
    tmp_path: Path, reacquisition_inputs: tuple[Path, Path, Path, Path]
) -> None:
    tracking, metadata, tags, truth = reacquisition_inputs
    lines = tracking.read_text().splitlines()
    for frame in range(210, 215):
        number, serialized_players, ball = lines[frame].split(":")
        players = serialized_players.split(";")
        x, y, speed = players[0].split(",")
        players[0] = f"{float(x) - 0.5},{y},{speed}"
        lines[frame] = f"{number}:{';'.join(players)}:{ball}"
    tracking.write_text("\n".join(lines) + "\n")
    before = {path: path.read_bytes() for path in reacquisition_inputs}

    original = run_reacquisition_experiments(
        tracking, metadata, tags, truth, tmp_path / "original"
    )
    tracklets = run_reacquisition_experiments(
        tracking,
        metadata,
        tags,
        truth,
        tmp_path / "tracklets",
        split_discontinuities=True,
    )

    for index in (2, 3, 4, 5):
        old_id = REACQUISITION_EXPERIMENTS[index].id
        new_id = TRACKLET_EXPERIMENTS[index].id
        old_audit = json.loads(
            (original.parent / old_id / "quarantine_audit.json").read_text()
        )
        new_audit = json.loads(
            (tracklets.parent / new_id / "quarantine_audit.json").read_text()
        )
        assert old_audit["event_count"] == new_audit["event_count"] == 1
        assert old_audit["events"][0]["start_frame"] == 205
        assert new_audit["events"][0]["start_frame"] == 205
        assert old_audit["events"][0]["end_frame_exclusive"] == 215
        assert new_audit["events"][0]["end_frame_exclusive"] == 210
    assert {path: path.read_bytes() for path in reacquisition_inputs} == before
