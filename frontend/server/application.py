"""Compose the local viewer and its independently indexed data sources."""

from functools import partial
from http.server import ThreadingHTTPServer
import json
import logging
import math
from pathlib import Path

from frontend.server.request_handler import RequestHandler
from frontend.server.quality_report_store import load_quality_reports
from frontend.server.tracking_store import TrackingStore
from frontend.server.video_metadata import read_video_metadata

_LOGGER = logging.getLogger(__name__)


def create_server(
    video: Path,
    pixels: Path,
    normalized: Path,
    metadata_path: Path,
    cache_dir: Path,
    port: int,
    *,
    birdseye_video: Path | None = None,
    birdseye_start_seconds: float = 0.0,
    trajectory_flags: Path | None = None,
    gap_continuity: Path | None = None,
) -> ThreadingHTTPServer:
    if not math.isfinite(birdseye_start_seconds) or birdseye_start_seconds < 0:
        raise ValueError("birdseye_start_seconds must be finite and nonnegative")
    _LOGGER.info("Loading tracking metadata: %s", metadata_path)
    metadata = json.loads(metadata_path.read_text())
    _LOGGER.info("Loading video properties: %s", video)
    source = read_video_metadata(video)
    metadata["video_width"] = source["width"]
    metadata["video_height"] = source["height"]
    metadata["video_url"] = "/video"
    metadata["default_frame"] = min(11186, metadata["frame_count"] - 1)
    metadata["birdseye"] = None
    if birdseye_video is None:
        _LOGGER.info("Bird's-eye video is unavailable; original views remain available")
    else:
        _LOGGER.info("Loading bird's-eye video properties: %s", birdseye_video)
        birdseye = read_video_metadata(birdseye_video)
        start_frame = math.floor(birdseye_start_seconds * metadata["fps"])
        metadata["birdseye"] = {
            **birdseye,
            "video_url": "/birdseye-video",
            "start_frame": start_frame,
        }
        _LOGGER.info(
            "Bird's-eye video loaded: %dx%d, %.3f FPS, %d frames; "
            "source start frame: %d",
            birdseye["width"],
            birdseye["height"],
            birdseye["fps"],
            birdseye["frame_count"],
            start_frame,
        )
    quality = load_quality_reports(trajectory_flags, gap_continuity)
    quality_body = json.dumps(quality, allow_nan=False, separators=(",", ":")).encode()
    store = TrackingStore(pixels, normalized, cache_dir, metadata["frame_count"])
    handler = partial(
        RequestHandler,
        store=store,
        metadata=metadata,
        video=video,
        birdseye_video=birdseye_video,
        quality_body=quality_body,
        web_dir=Path(__file__).parents[1] / "web",
    )
    return ThreadingHTTPServer(("127.0.0.1", port), handler)
