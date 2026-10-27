"""Verify submission loading and the viewer's optional prediction endpoint."""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
import sys
from threading import Thread
from types import SimpleNamespace

import pytest

from frontend import __main__ as frontend_cli
from frontend.server.application import create_server
from frontend.server.prediction_store import empty_predictions, load_predictions


def test_load_predictions_compresses_consecutive_frames_and_preserves_gaps(
    tmp_path: Path,
) -> None:
    path = tmp_path / "submission.csv"
    source = "frame,label\n0,H\n1,H\n3,H\n4,A\n5,A\n6,D\n7,X\n8,X\n"
    path.write_text(source)

    result = load_predictions(path)

    assert result == {
        "available": True,
        "filename": "submission.csv",
        "row_count": 8,
        "segments": [
            {"start_frame": 0, "end_frame": 1, "label": "H"},
            {"start_frame": 3, "end_frame": 3, "label": "H"},
            {"start_frame": 4, "end_frame": 5, "label": "A"},
            {"start_frame": 6, "end_frame": 6, "label": "D"},
            {"start_frame": 7, "end_frame": 8, "label": "X"},
        ],
        "counts": {"H": 3, "A": 2, "D": 1, "X": 2},
    }
    assert path.read_text() == source


def test_load_predictions_distinguishes_unconfigured_and_empty_files(
    tmp_path: Path,
) -> None:
    path = tmp_path / "empty.csv"
    path.write_text("frame,label\n")

    unavailable = load_predictions(None)
    configured = load_predictions(path)

    assert unavailable == empty_predictions()
    assert unavailable["available"] is False
    assert unavailable["filename"] is None
    assert configured["available"] is True
    assert configured["filename"] == "empty.csv"
    assert configured["row_count"] == 0
    assert configured["segments"] == []


def test_load_predictions_reports_an_explicit_missing_path(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_predictions(tmp_path / "missing.csv")


@pytest.fixture(params=[False, True], ids=["unconfigured", "configured"])
def prediction_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request: pytest.FixtureRequest
) -> Iterator[tuple[int, Path | None]]:
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_id,entity_type,team_id,pos_x,pos_y,position_valid\n"
        "0,ball,ball,,0.2,0.3,True\n"
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 9, "fps": 25}))
    video = tmp_path / "video.mp4"
    video.write_bytes(b"test video bytes")
    monkeypatch.setattr(
        "frontend.server.application.read_video_metadata",
        lambda path: {"width": 64, "height": 48},
    )
    prediction_path = None
    if request.param:
        prediction_path = tmp_path / "prediction.csv"
        prediction_path.write_text("frame,label\n0,H\n1,H\n4,X\n")
    with create_server(
        video,
        tracking,
        tracking,
        metadata,
        tmp_path / "cache",
        0,
        predictions=prediction_path,
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port, prediction_path
        finally:
            server.shutdown()
            thread.join()


def test_prediction_endpoint_serves_startup_snapshot_for_get_and_head(
    prediction_server: tuple[int, Path | None],
) -> None:
    port, path = prediction_server
    expected = load_predictions(path)
    if path is not None:
        # Replacing a file while reviewing must not change only part of the timeline.
        path.write_text("frame,label\n0,A\n")
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request("GET", "/api/predictions")
        response = connection.getresponse()
        assert response.status == 200
        body = response.read()
        assert json.loads(body) == expected
        assert response.getheader("Cache-Control") == "no-store"
        assert int(response.getheader("Content-Length")) == len(body)

        connection.request("HEAD", "/api/predictions")
        head = connection.getresponse()
        assert head.status == 200
        assert int(head.getheader("Content-Length")) == len(body)
        assert head.read() == b""


@pytest.mark.parametrize("selection", ["absent", "default", "explicit"])
def test_cli_selects_optional_default_or_explicit_prediction_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, selection: str
) -> None:
    monkeypatch.chdir(tmp_path)
    arguments = ["frontend"]
    expected = None
    if selection != "absent":
        default = Path("output/prediction.csv")
        default.parent.mkdir()
        default.write_text("frame,label\n0,H\n")
        expected = default
    if selection == "explicit":
        expected = Path("another.csv")
        expected.write_text("frame,label\n0,A\n")
        arguments.extend(["--predictions", str(expected)])
    selected = []

    @contextmanager
    def capture_server(*args, **kwargs):
        selected.append(kwargs["predictions"])
        yield SimpleNamespace(server_port=8765, serve_forever=lambda: None)

    monkeypatch.setattr(frontend_cli, "create_server", capture_server)
    monkeypatch.setattr(sys, "argv", arguments)

    frontend_cli.main()

    assert selected == [expected]
