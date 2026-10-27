"""Draw a cached pitch and frame-specific tracking markers with OpenCV."""

import math

import cv2
import numpy as np
from numpy.typing import NDArray

from .metadata_reader import RenderMetadata
from .normalized_reader import Observation

WIDTH = 1280
HEIGHT = 720
_HEADER_HEIGHT = 90
_FOOTER_HEIGHT = 45
_MARGIN_METRES = 5.0
_TEAM_COLORS = ((255, 150, 50), (80, 80, 240))  # BGR: blue, red
_BALL_COLOR = (0, 235, 255)
_WHITE = (245, 245, 245)


def _text(
    image: NDArray[np.uint8], text: str, position: tuple[int, int], scale: float = 0.6
) -> None:
    shadow_position = (position[0] + 1, position[1] + 1)
    cv2.putText(
        image,
        text,
        shadow_position,
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        (0, 0, 0),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        image, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale, _WHITE, 1, cv2.LINE_AA
    )


def _timestamp(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    whole_seconds, fraction = divmod(remaining, 1000)
    return f"{hours:02d}:{minutes:02d}:{whole_seconds:02d}.{fraction:03d}"


class PitchRenderer:
    """Keep static geometry cached while rendering independent tracking frames."""

    def __init__(self, metadata: RenderMetadata) -> None:
        self._metadata = metadata
        map_height = HEIGHT - _HEADER_HEIGHT - _FOOTER_HEIGHT
        self._scale = min(
            WIDTH / (metadata.pitch_length + 2 * _MARGIN_METRES),
            map_height / (metadata.pitch_width + 2 * _MARGIN_METRES),
        )
        self._left = (WIDTH - metadata.pitch_length * self._scale) / 2
        self._top = (
            _HEADER_HEIGHT + (map_height - metadata.pitch_width * self._scale) / 2
        )
        self._teams = {
            identifier: _TEAM_COLORS[index % len(_TEAM_COLORS)]
            for index, identifier in enumerate(metadata.teams)
        }
        self._background = self._draw_background()

    def _metres_to_pixel(self, x: float, y: float) -> tuple[int, int]:
        return round(self._left + x * self._scale), round(self._top + y * self._scale)

    def position_to_pixel(self, pos_x: float, pos_y: float) -> tuple[int, int]:
        """Map supplied pitch fractions to pixels without clipping or clamping."""
        return self._metres_to_pixel(
            pos_x * self._metadata.pitch_length, pos_y * self._metadata.pitch_width
        )

    def _draw_background(self) -> NDArray[np.uint8]:
        image = np.full((HEIGHT, WIDTH, 3), (35, 70, 35), dtype=np.uint8)
        length, width = self._metadata.pitch_length, self._metadata.pitch_width
        cv2.rectangle(
            image,
            self._metres_to_pixel(0, 0),
            self._metres_to_pixel(length, width),
            (55, 125, 55),
            -1,
        )
        cv2.rectangle(
            image,
            self._metres_to_pixel(0, 0),
            self._metres_to_pixel(length, width),
            _WHITE,
            2,
            cv2.LINE_AA,
        )
        cv2.line(
            image,
            self._metres_to_pixel(length / 2, 0),
            self._metres_to_pixel(length / 2, width),
            _WHITE,
            2,
            cv2.LINE_AA,
        )
        cv2.circle(
            image,
            self._metres_to_pixel(length / 2, width / 2),
            round(9.15 * self._scale),
            _WHITE,
            2,
            cv2.LINE_AA,
        )
        cv2.circle(
            image,
            self._metres_to_pixel(length / 2, width / 2),
            3,
            _WHITE,
            -1,
            cv2.LINE_AA,
        )
        for side in (0, 1):
            for depth, box_width in ((16.5, 40.32), (5.5, 18.32)):
                x = 0 if side == 0 else length - depth
                cv2.rectangle(
                    image,
                    self._metres_to_pixel(x, (width - box_width) / 2),
                    self._metres_to_pixel(x + depth, (width + box_width) / 2),
                    _WHITE,
                    2,
                    cv2.LINE_AA,
                )
            penalty_x = 11 if side == 0 else length - 11
            cv2.circle(
                image,
                self._metres_to_pixel(penalty_x, width / 2),
                3,
                _WHITE,
                -1,
                cv2.LINE_AA,
            )
            goal_x = -2 if side == 0 else length
            cv2.rectangle(
                image,
                self._metres_to_pixel(goal_x, (width - 7.32) / 2),
                self._metres_to_pixel(goal_x + 2, (width + 7.32) / 2),
                _WHITE,
                2,
                cv2.LINE_AA,
            )
        image[:_HEADER_HEIGHT] = (25, 35, 25)
        image[HEIGHT - _FOOTER_HEIGHT :] = (25, 35, 25)
        legend_x = 28
        for identifier, name in self._metadata.teams.items():
            cv2.circle(
                image, (legend_x, 66), 7, self._teams[identifier], -1, cv2.LINE_AA
            )
            _text(image, name, (legend_x + 15, 72), 0.6)
            text_width = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0][0]
            legend_x += text_width + 65
        cv2.circle(image, (legend_x, 66), 6, _BALL_COLOR, -1, cv2.LINE_AA)
        _text(image, "Ball", (legend_x + 15, 72), 0.6)
        _text(image, "Labels: tracking IDs | x right, y down", (28, HEIGHT - 17), 0.55)
        return image

    def render(self, frame: int, observations: list[Observation]) -> NDArray[np.uint8]:
        """Return one BGR 720p image; unavailable observations produce no marker."""
        image = self._background.copy()
        map_left, map_top = self._metres_to_pixel(-_MARGIN_METRES, -_MARGIN_METRES)
        map_right, map_bottom = self._metres_to_pixel(
            self._metadata.pitch_length + _MARGIN_METRES,
            self._metadata.pitch_width + _MARGIN_METRES,
        )
        map_image = image[map_top:map_bottom, map_left:map_right]
        ball_tracked = False
        available = 0
        for observation in observations:
            if not math.isfinite(observation.pos_x) or not math.isfinite(
                observation.pos_y
            ):
                continue
            available += 1
            is_ball = observation.entity_type == "ball"
            if is_ball:
                ball_tracked = True
            x, y = self.position_to_pixel(observation.pos_x, observation.pos_y)
            if not (map_left <= x < map_right and map_top <= y < map_bottom):
                continue
            color = _BALL_COLOR if is_ball else self._teams[observation.team_id]
            location = (x - map_left, y - map_top)
            cv2.circle(map_image, location, 8, (0, 0, 0), -1, cv2.LINE_AA)
            cv2.circle(map_image, location, 6, color, -1, cv2.LINE_AA)
            if not is_ball:
                label_location = (location[0] + 10, location[1] - 9)
                _text(
                    map_image,
                    observation.entity_id.removeprefix("player_"),
                    label_location,
                    0.55,
                )
        _text(
            image,
            f"Frame {frame} | Recording time {_timestamp(frame / self._metadata.fps)}",
            (28, 32),
            0.75,
        )
        if not ball_tracked:
            _text(image, "Ball not tracked", (1010, 72), 0.55)
        if available == 0:
            _text(image, "No tracking observations", (475, HEIGHT // 2), 0.7)
        return image
