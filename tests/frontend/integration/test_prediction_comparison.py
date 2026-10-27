"""Exercise submission predictions alongside the composed video/tracking server."""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
import pytest

from frontend.server.application import create_server


@pytest.fixture
def viewer_inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    tracking = tmp_path / "tracking.csv"
    rows = [
        "frame,entity_id,entity_type,team_id,pos_x,pos_y,position_valid",
        *(f"{frame},ball,ball,,0.2,0.3,True" for frame in range(8)),
    ]
    tracking.write_text("\n".join(rows) + "\n")
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 8, "fps": 25}))
    video = tmp_path / "video.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 25, (64, 48))
    try:
        assert writer.isOpened()
        for _ in range(8):
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    finally:
        writer.release()
    return video, tracking, metadata


@contextmanager
def serve_viewer(
    inputs: tuple[Path, Path, Path], cache: Path, predictions: Path | None
) -> Iterator[int]:
    video, tracking, metadata = inputs
    with create_server(
        video,
        tracking,
        tracking,
        metadata,
        cache,
        port=0,
        predictions=predictions,
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()


def request(
    port: int,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()


def test_prediction_api_preserves_source_frames_and_is_loaded_once_at_startup(
    tmp_path: Path, viewer_inputs: tuple[Path, Path, Path]
) -> None:
    predictions = tmp_path / "prediction.csv"
    predictions.write_text("frame,label\n0,H\n1,H\n2,A\n3,D\n4,X\n6,H\n7,H\n")

    with serve_viewer(viewer_inputs, tmp_path / "cache", predictions) as port:
        status, headers, body = request(port, "/api/predictions")
        assert status == 200
        assert json.loads(body) == {
            "available": True,
            "filename": "prediction.csv",
            "row_count": 7,
            "segments": [
                {"start_frame": 0, "end_frame": 1, "label": "H"},
                {"start_frame": 2, "end_frame": 2, "label": "A"},
                {"start_frame": 3, "end_frame": 3, "label": "D"},
                {"start_frame": 4, "end_frame": 4, "label": "X"},
                {"start_frame": 6, "end_frame": 7, "label": "H"},
            ],
            "counts": {"H": 4, "A": 1, "D": 1, "X": 1},
        }
        assert int(headers["Content-Length"]) == len(body)
        head_status, head_headers, head_body = request(
            port, "/api/predictions", method="HEAD"
        )
        assert head_status == 200
        assert head_headers["Content-Length"] == headers["Content-Length"]
        assert head_body == b""

        predictions.write_text("frame,label\n0,D\n")
        assert request(port, "/api/predictions")[2] == body

        frame_status, _, frame_body = request(port, "/api/frames?start=5&count=2")
        assert frame_status == 200
        frames = json.loads(frame_body)["frames"]
        assert [frame["frame"] for frame in frames] == [5, 6]
        assert frames[0]["normalized"][0]["pos_x"] == 0.2
        assert frames[1]["pixels"][0]["entity_id"] == "ball"

        video_status, video_headers, video_body = request(
            port, "/video", headers={"Range": "bytes=0-3"}
        )
        assert video_status == 206
        assert video_body == viewer_inputs[0].read_bytes()[:4]
        assert video_headers["Content-Range"].startswith("bytes 0-3/")


def test_viewer_serves_tracking_when_no_prediction_file_is_configured(
    tmp_path: Path, viewer_inputs: tuple[Path, Path, Path]
) -> None:
    with serve_viewer(viewer_inputs, tmp_path / "cache", None) as port:
        status, _, body = request(port, "/api/predictions")
        assert status == 200
        assert json.loads(body) == {
            "available": False,
            "filename": None,
            "row_count": 0,
            "segments": [],
            "counts": {"H": 0, "A": 0, "D": 0, "X": 0},
        }
        assert request(port, "/api/metadata")[0] == 200
        assert request(port, "/api/frames?start=0&count=1")[0] == 200


def test_explicit_missing_predictions_prevent_starting_a_viewer(
    tmp_path: Path, viewer_inputs: tuple[Path, Path, Path]
) -> None:
    video, tracking, metadata = viewer_inputs
    with pytest.raises(FileNotFoundError, match="missing.csv"):
        create_server(
            video,
            tracking,
            tracking,
            metadata,
            tmp_path / "cache",
            port=0,
            predictions=tmp_path / "missing.csv",
        )
