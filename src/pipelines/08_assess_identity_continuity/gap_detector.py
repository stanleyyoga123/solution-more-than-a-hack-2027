"""Detect every null run while retaining only finite endpoint context."""

from collections import deque

from src.utilities.normalized_tracking_reader import TrackingObservation

from .gap_window import GapWindow


class GapDetector:
    """Incrementally collect one slot's gaps and short endpoint windows."""

    def __init__(self, context_intervals: int):
        self._context_intervals = context_intervals
        self._history: deque[TrackingObservation] = deque(maxlen=context_intervals + 1)
        self._gap_start: int | None = None
        self._gap_end = 0
        self._left_context: tuple[TrackingObservation, ...] = ()
        self._pending: GapWindow | None = None

    def add(self, observation: TrackingObservation) -> list[GapWindow]:
        completed = []
        if not observation.position_valid:
            if self._pending is not None:
                completed.append(self._pending)
                self._pending = None
            if self._gap_start is None:
                self._gap_start = observation.frame
                self._left_context = tuple(self._history)
            self._gap_end = observation.frame
            self._history.clear()
            return completed

        if self._gap_start is not None:
            self._pending = GapWindow(
                self._gap_start, self._gap_end, self._left_context, ()
            )
            self._gap_start = None
        self._history.append(observation)
        if self._pending is not None:
            gap = self._pending
            self._pending = GapWindow(
                gap.start_frame,
                gap.end_frame,
                gap.left_context,
                gap.right_context + (observation,),
            )
            if len(self._pending.right_context) == self._context_intervals + 1:
                completed.append(self._pending)
                self._pending = None
        return completed

    def finish(self) -> list[GapWindow]:
        """Flush short right contexts and trailing or entirely missing tracks."""
        completed = []
        if self._pending is not None:
            completed.append(self._pending)
            self._pending = None
        if self._gap_start is not None:
            completed.append(
                GapWindow(self._gap_start, self._gap_end, self._left_context, ())
            )
            self._gap_start = None
        return completed
