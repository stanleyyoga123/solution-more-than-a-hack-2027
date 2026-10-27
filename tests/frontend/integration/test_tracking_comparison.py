"""Exercise the composed viewer through its public HTTP interface."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import csv
from http.client import HTTPConnection
import json
from pathlib import Path
from threading import Thread

import cv2
import numpy as np
import pytest

from frontend.server.application import create_server


def _write_tracking(path: Path, pixel_coordinates: bool) -> None:
    with path.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(
            [
                "frame",
                "entity_id",
                "entity_type",
                "team_id",
                "pos_x",
                "pos_y",
                "position_valid",
            ]
        )
        for frame in range(5):
            x = 1000 + frame if pixel_coordinates else frame / 10
            writer.writerow([frame, "player_7", "player", "home", x, 0.5, True])
            writer.writerow([frame, "ball", "ball", "", "", "", False])


@pytest.fixture
def comparison_server(tmp_path: Path) -> Iterator[int]:
    pixels = tmp_path / "pixels.csv"
    normalized = tmp_path / "normalized.csv"
    _write_tracking(pixels, pixel_coordinates=True)
    _write_tracking(normalized, pixel_coordinates=False)
    metadata = tmp_path / "metadata.json"
    metadata.write_text(json.dumps({"frame_count": 5, "fps": 25}))
    video = tmp_path / "video.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 25, (64, 48))
    try:
        assert writer.isOpened()
        for _ in range(5):
            writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    finally:
        writer.release()

    with create_server(
        video, pixels, normalized, metadata, tmp_path / "cache", port=0
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()


def _get_json(port: int, path: str) -> dict:
    with closing(HTTPConnection("127.0.0.1", port, timeout=3)) as connection:
        connection.request("GET", path)
        response = connection.getresponse()
        assert response.status == 200
        return json.loads(response.read())


def test_comparison_keeps_both_sources_on_requested_frames_during_concurrent_seeks(
    comparison_server: int,
) -> None:
    metadata = _get_json(comparison_server, "/api/metadata")
    assert metadata["video_width"] == 64
    assert metadata["video_height"] == 48
    assert metadata["video_url"] == "/video"
    assert metadata["default_frame"] == 4

    starts = [3, 1, 4, 2, 0, 1, 3, 2]
    paths = [f"/api/frames?start={start}&count=3" for start in starts]
    with ThreadPoolExecutor(max_workers=4) as executor:
        responses = list(
            executor.map(lambda path: _get_json(comparison_server, path), paths)
        )

    for start, response in zip(starts, responses, strict=True):
        frames = response["frames"]
        assert [item["frame"] for item in frames] == list(
            range(start, min(start + 3, 5))
        )
        for item in frames:
            frame = item["frame"]
            assert len(item["pixels"]) == len(item["normalized"]) == 1
            assert item["pixels"][0]["entity_id"] == "player_7"
            assert item["normalized"][0]["entity_id"] == "player_7"
            assert item["pixels"][0]["pos_x"] == 1000 + frame
            assert item["normalized"][0]["pos_x"] == frame / 10
