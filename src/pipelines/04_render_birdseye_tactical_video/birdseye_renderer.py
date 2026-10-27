"""Project source footage onto a fixed-scale, x-right/y-down pitch canvas."""

import math

import cv2
import numpy as np
from numpy.typing import NDArray

PIXELS_PER_METRE = 12


class BirdseyeRenderer:
    """Keep pitch scale uniform and pad the canvas to even H.264 dimensions."""

    def __init__(self, pitch_length: float, pitch_width: float):
        length_pixels = pitch_length * PIXELS_PER_METRE
        width_pixels = pitch_width * PIXELS_PER_METRE
        self._width = math.ceil(length_pixels / 2) * 2
        self._height = math.ceil(width_pixels / 2) * 2
        self._output_to_pitch = np.diag([1 / length_pixels, 1 / width_pixels, 1.0])
        self._invalid_frames = 0

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def invalid_frames(self) -> int:
        return self._invalid_frames

    def render(
        self,
        image: NDArray[np.uint8],
        matrix: NDArray[np.float64] | None,
    ) -> NDArray[np.uint8]:
        """Return black for missing calibration and unseen source-image regions."""
        if matrix is None:
            self._invalid_frames += 1
            return np.zeros((self._height, self._width, 3), dtype=np.uint8)

        # The supplied H maps normalized pitch positions to source-video pixels.
        # OpenCV samples each output pixel through this destination-to-source map.
        output_to_source = matrix @ self._output_to_pitch
        return cv2.warpPerspective(
            image,
            output_to_source,
            (self._width, self._height),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )
