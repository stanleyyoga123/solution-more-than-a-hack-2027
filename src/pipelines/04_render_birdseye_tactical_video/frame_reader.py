"""Decode one source interval and apply its aligned per-frame calibration."""

from collections.abc import Iterator
from itertools import islice

import cv2
import numpy as np
from numpy.typing import NDArray

from .birdseye_renderer import BirdseyeRenderer


def read_warped_frames(
    capture: cv2.VideoCapture,
    calibrations: Iterator[tuple[int, NDArray[np.float64] | None, float]],
    renderer: BirdseyeRenderer,
    start: int,
    stop: int,
) -> Iterator[NDArray[np.uint8]]:
    """Seek once, then decode sequentially; input calibration rows are frame-aligned."""
    if not capture.set(cv2.CAP_PROP_POS_FRAMES, start):
        raise OSError(f"Could not seek source video to frame {start}")
    for frame, matrix, _ in islice(calibrations, start, stop):
        success, image = capture.read()
        if not success:
            raise OSError(f"Could not decode source video frame {frame}")
        yield renderer.render(image, matrix)
