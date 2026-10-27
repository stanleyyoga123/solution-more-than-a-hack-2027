"""Render original tactical footage onto the supplied normalized pitch plane."""

from contextlib import closing
import logging
import os
from pathlib import Path
import shutil
import tempfile
from time import perf_counter

import cv2

from src.utilities.epts_metadata import read_metadata
from src.utilities.homography_reader import read_homographies
from src.utilities.pipeline_logging import frame_progress
from src.utilities.video_encoder import encode_video
from src.utilities.video_timing import select_frame_range

from .birdseye_renderer import BirdseyeRenderer
from .frame_reader import read_warped_frames

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    video: Path,
    homography: Path,
    metadata: Path,
    output_dir: Path,
    start_seconds: float = 0.0,
    duration_seconds: float | None = None,
) -> Path:
    """Publish a complete silent MP4 with one warped frame per selected source frame."""
    started = perf_counter()
    LOGGER.info(
        "Starting 04_render_birdseye_tactical_video; loading metadata: %s", metadata
    )
    info = read_metadata(metadata)
    output = output_dir / "tactical_birdseye.mp4"
    if os.path.lexists(output):
        raise FileExistsError(f"{output} already exists; choose a new output directory")
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise FileNotFoundError("FFmpeg must be installed and available on PATH")

    LOGGER.info("Opening source video: %s", video)
    capture = cv2.VideoCapture(str(video))
    try:
        if not capture.isOpened():
            raise OSError(f"Could not open source video: {video}")
        fps = capture.get(cv2.CAP_PROP_FPS)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        start, stop = select_frame_range(
            fps, frame_count, start_seconds, duration_seconds
        )
        renderer = BirdseyeRenderer(info.pitch_length, info.pitch_width)
        LOGGER.info(
            "Selected source frames %d..%d at %.3f FPS (%d frames)",
            start,
            stop - 1,
            fps,
            stop - start,
        )
        LOGGER.info(
            "Pitch %.2fx%.2f metres; rendering %dx%d pixels with x right and y down",
            info.pitch_length,
            info.pitch_width,
            renderer.width,
            renderer.height,
        )
        LOGGER.info("Reading frame-aligned homography: %s", homography)
        LOGGER.info("Encoding H.264 bird's-eye footage: %s", output)
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            prefix=".tactical_birdseye-", dir=output_dir
        ) as directory:
            staged = Path(directory) / "tactical_birdseye.mp4"
            with (
                closing(read_homographies(homography)) as calibrations,
                closing(
                    read_warped_frames(capture, calibrations, renderer, start, stop)
                ) as images,
                frame_progress(
                    images, stop - start, "Warping tactical footage", LOGGER
                ) as frames,
            ):
                count = encode_video(
                    frames, fps, staged, ffmpeg, renderer.width, renderer.height
                )
            os.link(staged, output)
    finally:
        capture.release()

    LOGGER.info(
        "Completed 04_render_birdseye_tactical_video: %d frames "
        "(%d without calibration, rendered black) in %.2f seconds; output: %s",
        count,
        renderer.invalid_frames,
        perf_counter() - started,
        output,
    )
    return output
