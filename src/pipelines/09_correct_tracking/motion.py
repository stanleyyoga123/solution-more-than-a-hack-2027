"""Physical bridge checks shared by repairs, interpolation, and evaluation."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

from src.utilities.motion_limits import MotionLimits

from .correction_policy import CorrectionPolicy


@dataclass(frozen=True)
class BridgeAssessment:
    reason: str
    forward_error_m: float | None = None
    backward_error_m: float | None = None
    positions: NDArray[np.float64] | None = None

    @property
    def accepted(self) -> bool:
        return self.reason == "motion_consistent"


def motion_clean(
    positions: NDArray[np.float64],
    fps: float,
    entity_type: str,
    limits: MotionLimits,
) -> bool:
    if not np.isfinite(positions).all():
        return False
    velocity = np.diff(positions, axis=0) * fps
    if np.any(
        np.linalg.norm(velocity, axis=1) > limits.speed_limit(entity_type) + 1e-8
    ):
        return False
    if entity_type == "player":
        acceleration = np.diff(velocity, axis=0) * fps
        if np.any(
            np.linalg.norm(acceleration, axis=1)
            > limits.player_acceleration_limit_mps2 + 1e-8
        ):
            return False
    return True


def prediction_errors(
    left_context: NDArray[np.float64],
    right_context: NDArray[np.float64],
    elapsed_seconds: float,
    fps: float,
) -> tuple[float, float]:
    left_velocity = (left_context[-1] - left_context[0]) * fps / (len(left_context) - 1)
    right_velocity = (
        (right_context[-1] - right_context[0]) * fps / (len(right_context) - 1)
    )
    delta = right_context[0] - left_context[-1]
    return (
        float(np.linalg.norm(delta - left_velocity * elapsed_seconds)),
        float(np.linalg.norm(delta - right_velocity * elapsed_seconds)),
    )


def evaluate_bridge(
    left_context: NDArray[np.float64],
    right_context: NDArray[np.float64],
    missing_frames: int,
    fps: float,
    entity_type: str,
    limits: MotionLimits,
    policy: CorrectionPolicy,
) -> BridgeAssessment:
    """Use only visible context; check the complete replacement including joins."""
    required = policy.context_intervals(fps) + 1
    if len(left_context) != required or len(right_context) != required:
        return BridgeAssessment("insufficient_context")
    if not motion_clean(left_context, fps, entity_type, limits) or not motion_clean(
        right_context, fps, entity_type, limits
    ):
        return BridgeAssessment("flagged_context")
    elapsed = (missing_frames + 1) / fps
    errors = prediction_errors(left_context, right_context, elapsed, fps)
    if max(errors) > policy.prediction_tolerance(entity_type):
        return BridgeAssessment("motion_disagreement", *errors)
    delta = right_context[0] - left_context[-1]
    if np.linalg.norm(delta) / elapsed > limits.speed_limit(entity_type) + 1e-8:
        return BridgeAssessment("excessive_required_speed", *errors)
    fractions = np.arange(1, missing_frames + 1, dtype=float)[:, None] / (
        missing_frames + 1
    )
    positions = left_context[-1] + fractions * delta
    path = np.concatenate((left_context, positions, right_context))
    if not motion_clean(path, fps, entity_type, limits):
        return BridgeAssessment("interpolation_motion_violation", *errors)
    return BridgeAssessment("motion_consistent", *errors, positions)
