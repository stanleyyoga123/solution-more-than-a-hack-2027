"""Read the properties needed to align locally served video recordings."""

from pathlib import Path
from typing import TypedDict

import cv2


class VideoMetadata(TypedDict):
    width: int
    height: int
    fps: float
    frame_count: int


def read_video_metadata(path: Path) -> VideoMetadata:
    """Open a video long enough to read its dimensions and frame timing."""
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise OSError(f"Could not open video: {path}")
        return {
            "width": int(capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            "height": int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            "fps": capture.get(cv2.CAP_PROP_FPS),
            "frame_count": int(capture.get(cv2.CAP_PROP_FRAME_COUNT)),
        }
    finally:
        capture.release()
