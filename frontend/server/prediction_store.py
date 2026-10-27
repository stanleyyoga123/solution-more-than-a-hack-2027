"""Load submission labels as compact, inclusive frame intervals for playback."""

import csv
import logging
from pathlib import Path
from time import perf_counter
from typing import TypedDict

_LOGGER = logging.getLogger(__name__)


class PredictionSegment(TypedDict):
    start_frame: int
    end_frame: int
    label: str


class PredictionPayload(TypedDict):
    available: bool
    filename: str | None
    row_count: int
    segments: list[PredictionSegment]
    counts: dict[str, int]


def empty_predictions() -> PredictionPayload:
    """Represent an unconfigured prediction file without disabling playback."""
    return {
        "available": False,
        "filename": None,
        "row_count": 0,
        "segments": [],
        "counts": {label: 0 for label in ("H", "A", "D", "X")},
    }


def load_predictions(path: Path | None) -> PredictionPayload:
    """Compact consecutive labels without filling unprovided source frames.

    Inputs follow the submission's sorted zero-based ``frame,label`` format.
    Segment endpoints are inclusive, preserving X as an explicit abstention.
    """
    if path is None:
        _LOGGER.info("Prediction CSV is unavailable; prediction review is disabled")
        return empty_predictions()

    started = perf_counter()
    _LOGGER.info("Loading possession predictions: %s", path)
    payload = empty_predictions()
    payload["available"] = True
    payload["filename"] = path.name
    segments = payload["segments"]
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            frame = int(row["frame"])
            label = row["label"]
            payload["row_count"] += 1
            payload["counts"][label] += 1
            if (
                segments
                and segments[-1]["label"] == label
                and segments[-1]["end_frame"] + 1 == frame
            ):
                segments[-1]["end_frame"] = frame
            else:
                segments.append(
                    {"start_frame": frame, "end_frame": frame, "label": label}
                )
    _LOGGER.info(
        "Loaded %d prediction rows into %d intervals in %.2f seconds: %s",
        payload["row_count"],
        len(segments),
        perf_counter() - started,
        path,
    )
    return payload
