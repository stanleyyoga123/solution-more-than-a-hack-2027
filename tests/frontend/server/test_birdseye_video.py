"""Check optional rendered footage and its source-frame alignment over HTTP."""

from collections.abc import Iterator
from contextlib import closing, contextmanager
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
import pytest

from frontend.server.application import create_server


def _write_video(path: Path, size: tuple[int, int], frames: int) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 25, size)
    assert writer.isOpened()
    try:
        width, height = size
        for _ in range(frames):
            writer.write(np.zeros((height, width, 3), dtype=np.uint8))
    finally:
        writer.release()


@pytest.fixture
def recording_assets(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    video = tmp_path / "source.avi"
    birdseye = tmp_path / "birdseye.avi"
    _write_video(video, (64, 48), 20)
    _write_video(birdseye, (80, 48), 3)
    tracking = tmp_path / "tracking.csv"
    tracking.write_text(
        "frame,entity_id,entity_type,team_id,pos_x,pos_y,position_valid\n"
        + "".join(f"{frame},ball,ball,,0.2,0.3,True\n" for frame in range(20))
    )
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 20, "fps": 25}))
    return video, tracking, metadata, birdseye


@contextmanager
def _serve(server: ThreadingHTTPServer) -> Iterator[int]:
    with server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()


def _request(
    port: int, path: str, method: str = "GET", headers: dict | None = None
) -> tuple[int, dict, bytes]:
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()


def test_birdseye_clip_reports_source_offset_and_serves_selected_file(
    recording_assets: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    video, tracking, metadata, birdseye = recording_assets
    server = create_server(
        video,
        tracking,
        tracking,
        metadata,
        tmp_path / "cache",
        port=0,
        birdseye_video=birdseye,
        birdseye_start_seconds=0.31,
    )
    with _serve(server) as port:
        status, _, body = _request(port, "/api/metadata")
        assert status == 200
        info = json.loads(body)
        assert info["birdseye"] == {
            "video_url": "/birdseye-video",
            "width": 80,
            "height": 48,
            "fps": 25,
            "frame_count": 3,
            "start_frame": 7,
        }
        assert info["video_width"] == 64
        assert info["frame_count"] == 20

        status, headers, body = _request(
            port, "/birdseye-video", headers={"Range": "bytes=0-31"}
        )
        assert status == 206
        assert body == birdseye.read_bytes()[:32]
        assert headers["Content-Range"] == f"bytes 0-31/{birdseye.stat().st_size}"

        status, headers, body = _request(
            port, "/birdseye-video", method="HEAD", headers={"Range": "bytes=0-31"}
        )
        assert status == 206
        assert headers["Content-Length"] == "32"
        assert body == b""


def test_viewer_remains_available_without_rendered_footage(
    recording_assets: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    video, tracking, metadata, _ = recording_assets
    server = create_server(video, tracking, tracking, metadata, tmp_path / "cache", 0)
    with _serve(server) as port:
        status, _, body = _request(port, "/api/metadata")
        assert status == 200
        assert json.loads(body)["birdseye"] is None
        assert _request(port, "/birdseye-video")[0] == 404
        assert _request(port, "/api/frames?start=0&count=1")[0] == 200


def test_explicit_missing_birdseye_video_fails_with_its_path(
    recording_assets: tuple[Path, Path, Path, Path], tmp_path: Path
) -> None:
    video, tracking, metadata, _ = recording_assets
    missing = tmp_path / "missing.mp4"
    with pytest.raises(OSError, match="missing.mp4"):
        create_server(
            video,
            tracking,
            tracking,
            metadata,
            tmp_path / "cache",
            0,
            birdseye_video=missing,
        )


@pytest.mark.parametrize("start_seconds", [-1, float("nan")])
def test_birdseye_source_offset_rejects_invalid_user_time(
    recording_assets: tuple[Path, Path, Path, Path],
    tmp_path: Path,
    start_seconds: float,
) -> None:
    video, tracking, metadata, birdseye = recording_assets
    with pytest.raises(ValueError, match="finite and nonnegative"):
        create_server(
            video,
            tracking,
            tracking,
            metadata,
            tmp_path / "cache",
            0,
            birdseye_video=birdseye,
            birdseye_start_seconds=start_seconds,
        )
