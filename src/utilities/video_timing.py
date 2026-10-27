"""Select source frame intervals consistently across video-rendering pipelines."""

import math


def select_frame_range(
    fps: float,
    frame_count: int,
    start_seconds: float,
    duration_seconds: float | None,
) -> tuple[int, int]:
    """Return an inclusive start and exclusive stop for an elapsed-time request."""
    if not math.isfinite(start_seconds) or start_seconds < 0:
        raise ValueError("start_seconds must be finite and nonnegative")
    if duration_seconds is not None:
        if not math.isfinite(duration_seconds) or duration_seconds <= 0:
            raise ValueError("duration_seconds must be finite and positive")
    if start_seconds >= frame_count / fps:
        raise ValueError("Requested interval contains no video frames")
    start = math.floor(start_seconds * fps)
    stop = frame_count
    if duration_seconds is not None and duration_seconds < (frame_count - start) / fps:
        stop = start + math.ceil(duration_seconds * fps)
    return start, stop
