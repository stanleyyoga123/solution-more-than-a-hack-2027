"""Apply a supplied YOLO model to sports balls and project its proposals."""

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from .detection import BallDetection
from .policy import VisionPolicy

if TYPE_CHECKING:
    from ultralytics import YOLO


class YoloBallDetector:
    def __init__(self, model: "YOLO", policy: VisionPolicy) -> None:
        self._model = model
        self._policy = policy

    def detect(
        self,
        image: NDArray[np.uint8],
        frame: int,
        role: str,
        homography: NDArray[np.float64] | None,
        pitch: NDArray[np.float64],
    ) -> list[BallDetection]:
        results = self._model.predict(
            image,
            classes=[32],
            imgsz=self._policy.image_size,
            conf=self._policy.confidence,
            iou=0.5,
            max_det=20,
            device="cpu",
            verbose=False,
            save=False,
        )
        inverse = np.linalg.inv(homography) if homography is not None else None
        boxes = results[0].boxes
        detections = []
        for box, confidence in zip(
            boxes.xyxy.cpu().numpy(), boxes.conf.cpu().numpy(), strict=True
        ):
            x1, y1, x2, y2 = map(float, box)
            pixel_x, pixel_y = (x1 + x2) / 2, (y1 + y2) / 2
            position = np.full(2, np.nan)
            if inverse is not None:
                projected = inverse @ np.array([pixel_x, pixel_y, 1])
                if abs(projected[2]) > 1e-12:
                    position = projected[:2] / projected[2] * pitch
            detections.append(
                BallDetection(
                    frame,
                    role,
                    float(confidence),
                    x1,
                    y1,
                    x2,
                    y2,
                    pixel_x,
                    pixel_y,
                    float(position[0]),
                    float(position[1]),
                )
            )
        return detections
