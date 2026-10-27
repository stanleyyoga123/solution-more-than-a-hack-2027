"""Assess bounded gap motion without asserting verified real-world identity."""

from math import hypot

from src.utilities.normalized_tracking_reader import TrackingObservation
from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .gap_policy import GapPolicy
from .gap_window import GapWindow

GAP_COLUMNS = (
    "entity_id",
    "entity_type",
    "team_id",
    "start_frame",
    "end_frame",
    "missing_frames",
    "gap_seconds",
    "left_frame",
    "right_frame",
    "endpoint_distance_m",
    "required_speed_mps",
    "forward_error_m",
    "backward_error_m",
    "status",
    "reason",
)
GapReport = dict[str, str | int | float | None]


def context_velocity(
    context: tuple[TrackingObservation, ...], fps: float
) -> tuple[float, float]:
    first, last = context[0], context[-1]
    duration = (last.frame - first.frame) / fps
    return (
        (last.x_metres - first.x_metres) / duration,
        (last.y_metres - first.y_metres) / duration,
    )


def assess_gap(
    gap: GapWindow,
    entity: TrackingObservation,
    fps: float,
    context_intervals: int,
    policy: GapPolicy,
    limits: MotionLimits,
    flags: TrajectoryFlagIndex,
) -> GapReport:
    """Apply the documented ordered status rules to one maximal missing run."""
    missing_frames = gap.end_frame - gap.start_frame + 1
    gap_seconds = missing_frames / fps
    left = gap.left_context[-1] if gap.left_context else None
    right = gap.right_context[0] if gap.right_context else None
    row: GapReport = {
        "entity_id": entity.entity_id,
        "entity_type": entity.entity_type,
        "team_id": entity.team_id,
        "start_frame": gap.start_frame,
        "end_frame": gap.end_frame,
        "missing_frames": missing_frames,
        "gap_seconds": gap_seconds,
        "left_frame": left.frame if left is not None else None,
        "right_frame": right.frame if right is not None else None,
        "endpoint_distance_m": None,
        "required_speed_mps": None,
        "forward_error_m": None,
        "backward_error_m": None,
        "status": "uncertain",
        "reason": "unbounded_gap",
    }
    if left is None or right is None:
        return row
    elapsed = (right.frame - left.frame) / fps
    dx = right.x_metres - left.x_metres
    dy = right.y_metres - left.y_metres
    distance = hypot(dx, dy)
    required_speed = distance / elapsed
    row["endpoint_distance_m"] = distance
    row["required_speed_mps"] = required_speed
    context_complete = (
        len(gap.left_context) == context_intervals + 1
        and len(gap.right_context) == context_intervals + 1
    )
    forward_error = backward_error = None
    if context_complete:
        left_vx, left_vy = context_velocity(gap.left_context, fps)
        right_vx, right_vy = context_velocity(gap.right_context, fps)
        forward_error = hypot(dx - left_vx * elapsed, dy - left_vy * elapsed)
        backward_error = hypot(dx - right_vx * elapsed, dy - right_vy * elapsed)
        row["forward_error_m"] = forward_error
        row["backward_error_m"] = backward_error
    flagged_context = flags.overlaps(
        entity.entity_id, left.frame - context_intervals, left.frame
    ) or flags.overlaps(entity.entity_id, right.frame, right.frame + context_intervals)
    if flagged_context:
        row["reason"] = "flagged_context"
    elif required_speed > limits.speed_limit(entity.entity_type):
        row["status"] = "implausible"
        row["reason"] = "excessive_required_speed"
    elif gap_seconds > policy.max_gap_seconds:
        row["reason"] = "long_gap"
    elif not context_complete:
        row["reason"] = "insufficient_context"
    elif forward_error > policy.prediction_tolerance(
        entity.entity_type
    ) or backward_error > policy.prediction_tolerance(entity.entity_type):
        row["reason"] = "motion_disagreement"
    else:
        row["status"] = "plausible"
        row["reason"] = "motion_consistent"
    return row
