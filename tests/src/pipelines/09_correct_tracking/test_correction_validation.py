"""Reconstruction errors and identity abstention against controlled references."""

import importlib
import json
from pathlib import Path

import pytest

from tests.fixtures.tracking_corrections import correction_inputs, linear_track
from tests.fixtures.tracking_quality import Position

correct_tracking = importlib.import_module(
    "src.pipelines.09_correct_tracking"
).run_pipeline


def test_masking_reports_rejections_separately_from_accepted_reconstruction_errors(
    tmp_path: Path,
) -> None:
    track: list[Position] = []
    for frame in range(200):
        seconds = frame / 10
        # Smooth acceleration is valid motion; extrapolating it across 3s is unsafe.
        x = 0.25 * seconds**2 if seconds <= 10 else 25 + 5 * (seconds - 10)
        track.append((x, 10))
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": track})

    _, _, _, report = correct_tracking(*inputs.arguments(), tmp_path / "out")

    summaries = json.loads(report.read_text())["masking"]
    early = next(
        row
        for row in summaries
        if row["gap_seconds"] == 3 and row["time_block"] == "early_80_percent"
    )
    late = next(
        row
        for row in summaries
        if row["gap_seconds"] == 3 and row["time_block"] == "late_20_percent"
    )
    assert early["evaluated_windows"] > 0
    assert early["accepted_windows"] == 0
    assert early["rejected_windows"] == early["evaluated_windows"]
    assert early["rejection_reasons"]["motion_disagreement"] > 0
    assert early["mean_error_m"] is None
    assert early["p95_error_m"] is None
    assert late["accepted_windows"] > 0
    assert late["rejected_windows"] == 0
    assert late["mean_error_m"] == pytest.approx(0, abs=1e-10)
    for summary in summaries:
        assert summary["evaluated_windows"] == (
            summary["accepted_windows"] + summary["rejected_windows"]
        )
        assert summary["rejected_windows"] == sum(summary["rejection_reasons"].values())


def test_identity_validation_abstains_when_stationary_competitors_are_ambiguous(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(
        tmp_path / "inputs",
        {
            "player_1": linear_track(200, x_offset=10, y=10, speed_mps=0),
            "player_2": linear_track(200, x_offset=10, y=10.3, speed_mps=0),
        },
    )

    _, _, _, report = correct_tracking(*inputs.arguments(), tmp_path / "out")

    identity = json.loads(report.read_text())["identity_fragmentation"]
    assert identity["identical_candidate_probe_rejected"] is True
    for summary in identity["summaries"]:
        assert summary["evaluated_windows"] > 0
        assert (
            summary["windows_with_feasible_competitors"] == summary["evaluated_windows"]
        )
        assert summary["abstained"] == summary["evaluated_windows"]
        assert summary["recovered_source_pair"] == summary["different_source_pair"] == 0
