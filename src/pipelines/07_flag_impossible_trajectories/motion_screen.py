"""Calculate motion checks within uninterrupted observed track segments."""

from collections import deque
from math import hypot

from src.utilities.normalized_tracking_reader import TrackingObservation
from src.utilities.motion_limits import MotionLimits


def flag_motion(
    history: deque[TrackingObservation], fps: float, limits: MotionLimits
) -> dict[str, str | int | float | bool | None] | None:
    """Flag strictly excessive speed or player acceleration at the latest frame."""
    if len(history) < 2:
        return None
    previous, current = history[-2], history[-1]
    vx = (current.x_metres - previous.x_metres) * fps
    vy = (current.y_metres - previous.y_metres) * fps
    speed = hypot(vx, vy)
    speed_flag = speed > limits.speed_limit(current.entity_type)
    acceleration = None
    acceleration_flag = False
    if current.entity_type == "player" and len(history) == 3:
        earlier = history[0]
        previous_vx = (previous.x_metres - earlier.x_metres) * fps
        previous_vy = (previous.y_metres - earlier.y_metres) * fps
        acceleration = hypot(vx - previous_vx, vy - previous_vy) * fps
        acceleration_flag = acceleration > limits.player_acceleration_limit_mps2
    if not speed_flag and not acceleration_flag:
        return None
    start_frame = history[0].frame if acceleration_flag else previous.frame
    return {
        "entity_id": current.entity_id,
        "entity_type": current.entity_type,
        "team_id": current.team_id,
        "start_frame": start_frame,
        "end_frame": current.frame,
        "speed_mps": speed,
        "acceleration_mps2": acceleration,
        "speed_flag": speed_flag,
        "acceleration_flag": acceleration_flag,
    }
