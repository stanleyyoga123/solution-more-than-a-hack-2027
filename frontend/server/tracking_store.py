"""Read bounded frame windows from independent pixel and pitch exports."""

import csv
import io
import math
from pathlib import Path
from typing import TypedDict

from frontend.server.csv_index import load_frame_offsets


class Observation(TypedDict):
    entity_id: str
    entity_type: str
    team_id: str
    pos_x: float
    pos_y: float


class TrackingStore:
    """Own only frame indexes; open a separate CSV handle for each request."""

    def __init__(
        self,
        pixels: Path,
        normalized: Path,
        cache_dir: Path,
        frame_count: int,
    ):
        self._pixels = pixels
        self._normalized = normalized
        self._pixel_columns, self._pixel_offsets = load_frame_offsets(
            pixels, cache_dir, frame_count
        )
        self._normalized_columns, self._normalized_offsets = load_frame_offsets(
            normalized, cache_dir, frame_count
        )

    def read_frames(self, start: int, count: int) -> list[dict]:
        pixels = _read_positions(
            self._pixels, self._pixel_columns, self._pixel_offsets, start, count
        )
        normalized = _read_positions(
            self._normalized,
            self._normalized_columns,
            self._normalized_offsets,
            start,
            count,
        )
        return [
            {
                "frame": frame,
                "pixels": pixels[frame],
                "normalized": normalized[frame],
            }
            for frame in range(start, start + count)
        ]


def _read_positions(
    path: Path, columns: list[str], offsets: list[int], start: int, count: int
) -> dict[int, list[Observation]]:
    positions: dict[int, list[Observation]] = {
        frame: [] for frame in range(start, start + count)
    }
    with path.open("rb") as stream:
        stream.seek(offsets[start])
        contents = stream.read(offsets[start + count] - offsets[start])
    rows = csv.DictReader(io.StringIO(contents.decode("utf-8")), fieldnames=columns)
    for row in rows:
        if row["position_valid"] != "True":
            continue
        x = float(row["pos_x"])
        y = float(row["pos_y"])
        if not math.isfinite(x) or not math.isfinite(y):
            continue
        positions[int(row["frame"])].append(
            {
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "team_id": row["team_id"],
                "pos_x": x,
                "pos_y": y,
            }
        )
    return positions
