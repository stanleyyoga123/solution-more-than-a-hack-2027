"""Public step 09 invocation, reproducibility, and safe artifact publication."""

import importlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.fixtures.tracking_corrections import correction_inputs, linear_track
from tests.fixtures.tracking_quality import read_rows

ROOT = Path(__file__).resolve().parents[4]
correct_tracking = importlib.import_module(
    "src.pipelines.09_correct_tracking"
).run_pipeline


def test_correction_publishes_reproducible_data_and_validation_reports(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(
        tmp_path / "inputs", {"player_1": linear_track(200), "ball": linear_track(200)}
    )

    first = correct_tracking(*inputs.arguments(), tmp_path / "first")
    second = correct_tracking(*inputs.arguments(), tmp_path / "second")

    assert len(first) == 4
    assert all(path.is_file() for path in first + second)
    for index in (0, 2, 3):
        assert first[index].read_bytes() == second[index].read_bytes()
    metadata = json.loads(first[1].read_text())
    assert metadata["frame_count"] == 200
    assert metadata["row_count"] == 400
    validation = json.loads(first[3].read_text())
    assert validation["method"]["limitations"]
    assert {row["entity_type"] for row in validation["masking"]} == {"player", "ball"}
    assert {row["time_block"] for row in validation["masking"]} == {
        "early_80_percent",
        "late_20_percent",
    }
    for summary in validation["masking"]:
        assert summary["evaluated_windows"] > 0
        assert summary["accepted_windows"] == summary["evaluated_windows"]
        assert summary["rejected_windows"] == 0
        assert summary["mean_error_m"] == pytest.approx(0, abs=1e-10)
        assert summary["p95_error_m"] == pytest.approx(0, abs=1e-10)
    identity = validation["identity_fragmentation"]
    assert identity["identical_candidate_probe_rejected"] is True
    for summary in identity["summaries"]:
        assert summary["evaluated_windows"] > 0
        assert summary["recovered_source_pair"] == summary["evaluated_windows"]
        assert summary["different_source_pair"] == summary["abstained"] == 0
    diagnostics = validation["diagnostics"]
    assert diagnostics["before"] == diagnostics["after"]
    assert diagnostics["before"]["missing_position_rows"] == 0
    assert diagnostics["before"]["flagged_samples"] == 0
    assert diagnostics["changed_rows"] == {}
    assert len(read_rows(first[0])) == 400


def test_correction_cli_prints_only_four_artifact_paths_and_logs_progress(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": linear_track(30)})
    options = (
        "--tracking",
        "--metadata",
        "--flags",
        "--flags-metadata",
        "--gaps",
        "--gaps-metadata",
    )
    arguments = [sys.executable, "-m", "src.pipelines.09_correct_tracking"]
    for option, path in zip(options, inputs.arguments(), strict=True):
        arguments.extend((option, str(path)))
    arguments.extend(("--output-dir", str(tmp_path / "out")))

    result = subprocess.run(
        arguments, cwd=ROOT, capture_output=True, text=True, check=True
    )

    destinations = result.stdout.splitlines()
    assert len(destinations) == 4
    assert all(Path(path).is_file() for path in destinations)
    assert "09_correct_tracking" in result.stderr
    assert "Completed" in result.stderr


def test_correction_refuses_existing_artifacts_without_modifying_inputs_or_outputs(
    tmp_path: Path,
) -> None:
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": linear_track(30)})
    original = {path: path.read_bytes() for path in inputs.arguments()}
    paths = correct_tracking(*inputs.arguments(), tmp_path / "out")
    previous = {path: path.read_bytes() for path in paths}

    with pytest.raises(FileExistsError):
        correct_tracking(*inputs.arguments(), tmp_path / "out")

    assert all(path.read_bytes() == content for path, content in original.items())
    assert all(path.read_bytes() == content for path, content in previous.items())
    assert set((tmp_path / "out").iterdir()) == set(paths)


def test_correction_rolls_back_published_files_after_export_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    inputs = correction_inputs(tmp_path / "inputs", {"player_1": linear_track(30)})
    exports = importlib.import_module(
        "src.pipelines.09_correct_tracking.correction_exports"
    )
    real_link = exports.os.link
    calls = 0

    def fail_second_link(source: Path, destination: Path) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated publication failure")
        real_link(source, destination)

    monkeypatch.setattr(exports.os, "link", fail_second_link)

    with pytest.raises(OSError, match="simulated publication failure"):
        correct_tracking(*inputs.arguments(), tmp_path / "out")

    assert calls == 2
    assert not list((tmp_path / "out").iterdir())
