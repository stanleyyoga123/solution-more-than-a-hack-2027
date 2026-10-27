"""Render a normalized tracking interval as a top-down tactical MP4."""

from contextlib import closing
import logging
import math
import os
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

from src.utilities.pipeline_logging import frame_progress

from .metadata_reader import read_metadata
from .normalized_reader import read_frames
from .pitch_renderer import PitchRenderer
from .video_encoder import encode_video

LOGGER = logging.getLogger(__name__)


def _frame_range(
    fps: float,
    frame_count: int,
    start_seconds: float,
    duration_seconds: float | None,
) -> tuple[int, int]:
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError("start_seconds must be finite and nonnegative")
    if duration_seconds is not None:
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("duration_seconds must be finite and positive")
    if start_seconds >= frame_count / fps:
        raise ValueError("Requested interval contains no video frames")
    start = math.floor(start_seconds * fps)
    stop = frame_count
    if duration_seconds is not None and duration_seconds < (frame_count - start) / fps:
        stop = start + math.ceil(duration_seconds * fps)
    return start, stop


def run_pipeline(
    tracking: Path,
    metadata: Path,
    output_dir: Path,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
) -> Path:
    """Render supplied normalized observations, publishing only a completed MP4."""
    started = perf_counter()
    LOGGER.info("Starting 03_render_2d_tactical_video; loading metadata: %s", metadata)
    info = read_metadata(metadata)
    start, stop = _frame_range(
        info.fps, info.frame_count, start_seconds, duration_seconds
    )
    LOGGER.info(
        "Selected source frames %d..%d at %.3f FPS (%d frames)",
        start,
        stop - 1,
        info.fps,
        stop - start,
    )
    output = output_dir / "tactical_2d_tracking.mp4"
    if os.path.lexists(output):
        raise FileExistsError(f"{output} already exists; choose a new output directory")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("FFmpeg must be installed and available on PATH")
    output_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Loading static pitch and team legend")
    renderer = PitchRenderer(info)
    LOGGER.info("Scanning normalized tracking and selecting frames: %s", tracking)
    LOGGER.info("Encoding 1280x720 H.264 video: %s", output)
    with tempfile.TemporaryDirectory(
        prefix=".tactical_2d_tracking-", dir=output_dir
    ) as directory:
        staged = Path(directory) / "tactical_2d_tracking.mp4"
        with (
            closing(read_frames(tracking, start, stop)) as records,
            frame_progress(
                records, stop - start, "Rendering 2D tracking", LOGGER
            ) as frames,
        ):
            count = encode_video(frames, renderer, info.fps, staged, ffmpeg)
        os.link(staged, output)
    LOGGER.info(
        "Completed 03_render_2d_tactical_video: %d frames in %.2f seconds; output: %s",
        count,
        perf_counter() - started,
        output,
    )
    return output
