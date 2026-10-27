"""Stream one frame of normalized observations at a time."""

from collections.abc import Iterator
import csv
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path


@dataclass(frozen=True)
class Observation:
    entity_id: str
    entity_type: str
    team_id: str
    pos_x: float
    pos_y: float


def read_frames(
    path: Path, start: int, stop: int
) -> Iterator[tuple[int, list[Observation]]]:
    """Select [start, stop) from the frame-major CSV, keeping one frame in memory."""
    with path.open(newline="", encoding="utf-8") as source:
        rows = csv.DictReader(source)
        for frame, group in groupby(rows, key=lambda row: int(row["frame"])):
            if frame < start:
                continue
            if frame >= stop:
                break
            observations = [
                Observation(
                    entity_id=row["entity_id"],
                    entity_type=row["entity_type"],
                    team_id=row["team_id"],
                    pos_x=float(row["pos_x"]) if row["pos_x"] else float("nan"),
                    pos_y=float(row["pos_y"]) if row["pos_y"] else float("nan"),
                )
                for row in group
            ]
            yield frame, observations
