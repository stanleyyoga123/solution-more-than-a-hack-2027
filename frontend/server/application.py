"""Compose the local viewer and its independently indexed data sources."""

from functools import partial
from http.server import ThreadingHTTPServer
import json
import logging
from pathlib import Path

import cv2

from frontend.server.request_handler import RequestHandler
from frontend.server.tracking_store import TrackingStore

_LOGGER = logging.getLogger(__name__)


def create_server(
    video: Path,
    pixels: Path,
    normalized: Path,
    metadata_path: Path,
    cache_dir: Path,
    port: int,
) -> ThreadingHTTPServer:
    _LOGGER.info("Loading tracking metadata: %s", metadata_path)
    metadata = json.loads(metadata_path.read_text())
    _LOGGER.info("Loading video properties: %s", video)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise OSError(f"Could not open video: {video}")
        metadata["video_width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        metadata["video_height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    finally:
        capture.release()
    metadata["video_url"] = "/video"
    metadata["default_frame"] = min(11186, metadata["frame_count"] - 1)
    store = TrackingStore(pixels, normalized, cache_dir, metadata["frame_count"])
    handler = partial(
        RequestHandler,
        store=store,
        metadata=metadata,
        video=video,
        web_dir=Path(__file__).parents[1] / "web",
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
