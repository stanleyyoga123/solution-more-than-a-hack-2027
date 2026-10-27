"""Check the detector adapter's image-to-pitch projection with supplied boxes."""

from types import SimpleNamespace

import numpy as np

from playground.vision.detector import YoloBallDetector
from playground.vision.policy import VisionPolicy


class TensorStub:
    def __init__(self, values):
        self._values = np.array(values)

    def cpu(self):
        return self

    def numpy(self):
        return self._values


class ModelStub:
    def predict(self, image, **options):
        assert image.shape == (1080, 1920, 3)
        assert options["classes"] == [32]
        boxes = SimpleNamespace(
            xyxy=TensorStub([[490, 240, 510, 260]]), conf=TensorStub([0.8])
        )
        return [SimpleNamespace(boxes=boxes)]


def test_projection_inverts_normalized_pitch_homography_and_scales_to_metres():
    detector = YoloBallDetector(ModelStub(), VisionPolicy())
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    homography = np.diag([1000.0, 500.0, 1.0])
    result = detector.detect(image, 75, "missing_ball", homography, np.array([105, 68]))
    assert len(result) == 1
    np.testing.assert_allclose(result[0].position, [52.5, 34])
    assert result[0].pixel_x == 500
    assert result[0].pixel_y == 250
    assert result[0].frame == 75


def test_invalid_homography_preserves_pixel_proposal_without_pitch_position():
    detector = YoloBallDetector(ModelStub(), VisionPolicy())
    image = np.zeros((1080, 1920, 3), dtype=np.uint8)
    result = detector.detect(image, 75, "missing_ball", None, np.array([105, 68]))
    assert np.isnan(result[0].position).all()
    assert result[0].confidence == 0.8
