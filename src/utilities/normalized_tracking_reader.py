"""Stream normalized tracking observations in physical pitch coordinates."""

from collections.abc import Iterator
import csv
from dataclasses import dataclass
from itertools import groupby
from math import isfinite
from pathlib import Path

from src.utilities.normalized_tracking_metadata import NormalizedTrackingMetadata


@dataclass(frozen=True)
class TrackingObservation:
    frame: int
    entity_id: str
    entity_type: str
    team_id: str
    x_metres: float
    y_metres: float

    @property
    def position_valid(self) -> bool:
        return isfinite(self.x_metres) and isfinite(self.y_metres)


def read_normalized_frames(
    path: Path, metadata: NormalizedTrackingMetadata
) -> Iterator[tuple[int, list[TrackingObservation]]]:
    """Retain missing slots and frame-major order without loading the full CSV."""
    with path.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        for frame, group in groupby(rows, key=lambda row: int(row["frame"])):
            observations = []
            for row in group:
                x = float(row["pos_x"]) if row["pos_x"] else float("nan")
                y = float(row["pos_y"]) if row["pos_y"] else float("nan")
                observations.append(
                    TrackingObservation(
                        frame,
                        row["entity_id"],
                        row["entity_type"],
                        row["team_id"],
                        x * metadata.pitch_length,
                        y * metadata.pitch_width,
                    )
                )
            yield frame, observations
