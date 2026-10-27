"""A missing interval with bounded observed context on either side."""

from dataclasses import dataclass

from src.utilities.normalized_tracking_reader import TrackingObservation


@dataclass(frozen=True)
class GapWindow:
    start_frame: int
    end_frame: int
    left_context: tuple[TrackingObservation, ...]
    right_context: tuple[TrackingObservation, ...]
