"""Check progress reporting without waiting or requiring an interactive terminal."""

from contextlib import contextmanager
import importlib
import io
import logging
from pathlib import Path

import pytest

from src.utilities import export_files, pipeline_logging


def test_frame_progress_logs_occasional_counts_when_stderr_is_redirected(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(pipeline_logging.sys, "stderr", io.StringIO())
    ticks = iter([0.0, 1.0, 6.0, 7.0])
    monkeypatch.setattr(pipeline_logging, "monotonic", lambda: next(ticks))
    logger = logging.getLogger("progress-test")

    with (
        caplog.at_level(logging.INFO),
        pipeline_logging.frame_progress(
            ["first", "second", "third"], 3, "Reading frames", logger
        ) as frames,
    ):
        assert list(frames) == ["first", "second", "third"]

    assert caplog.messages == [
        "Reading frames: processing 3 frames",
        "Reading frames: 2/3 frames processed",
    ]


def test_frame_progress_closes_terminal_display_when_processing_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    terminal = io.StringIO()
    monkeypatch.setattr(terminal, "isatty", lambda: True)
    monkeypatch.setattr(pipeline_logging.sys, "stderr", terminal)
    closed = []

    @contextmanager
    def terminal_progress(items, **kwargs):
        assert kwargs["file"] is terminal
        try:
            yield iter(items)
        finally:
            closed.append(True)

    monkeypatch.setattr(pipeline_logging, "tqdm", terminal_progress)
    failure = OSError("write failed")
    with pytest.raises(OSError) as raised:
        with pipeline_logging.frame_progress(
            [1, 2], 2, "Tracking", logging.getLogger("progress-test")
        ) as frames:
            assert next(frames) == 1
            raise failure

    assert raised.value is failure
    assert closed == [True]


@pytest.mark.parametrize("step", ["01_populate_pixels", "02_normalize_2d"])
def test_pipeline_preserves_publication_error_and_omits_completion_log(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    step: str,
) -> None:
    resources = Path(__file__).resolve().parents[2] / "resources" / "pipeline"
    run_pipeline = importlib.import_module(f"src.pipelines.{step}").run_pipeline
    failure = OSError("publication failed")

    def fail_publication(source: Path, destination: Path) -> None:
        raise failure

    monkeypatch.setattr(export_files.os, "link", fail_publication)
    arguments = {
        "tracking": resources / "tracking.txt",
        "metadata": resources / "metadata.xml",
        "output_dir": tmp_path,
    }
    if step == "01_populate_pixels":
        arguments["homography"] = resources / "homography.csv"

    with caplog.at_level(logging.INFO), pytest.raises(OSError) as raised:
        run_pipeline(**arguments)

    assert raised.value is failure
    assert not any("Completed" in message for message in caplog.messages)
    assert list(tmp_path.iterdir()) == []
