"""Shared trajectory flag CSV contract and inclusive interval lookup."""

from bisect import bisect_left
from collections import defaultdict
import csv
from pathlib import Path

FLAG_COLUMNS = (
    "entity_id",
    "entity_type",
    "team_id",
    "start_frame",
    "end_frame",
    "speed_mps",
    "acceleration_mps2",
    "speed_flag",
    "acceleration_flag",
)


class TrajectoryFlagIndex:
    """Merge report intervals for fast per-entity overlap queries."""

    def __init__(self, intervals: dict[str, list[tuple[int, int]]]):
        self._intervals = {}
        self._ends = {}
        for entity_id, entity_intervals in intervals.items():
            merged: list[tuple[int, int]] = []
            for start, end in sorted(entity_intervals):
                if merged and start <= merged[-1][1] + 1:
                    merged[-1] = (merged[-1][0], max(merged[-1][1], end))
                else:
                    merged.append((start, end))
            self._intervals[entity_id] = merged
            self._ends[entity_id] = [end for _, end in merged]

    def overlaps(self, entity_id: str, start: int, end: int) -> bool:
        intervals = self._intervals.get(entity_id, [])
        index = bisect_left(self._ends.get(entity_id, []), start)
        return index < len(intervals) and intervals[index][0] <= end


def read_trajectory_flags(path: Path) -> TrajectoryFlagIndex:
    intervals: dict[str, list[tuple[int, int]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            intervals[row["entity_id"]].append(
                (int(row["start_frame"]), int(row["end_frame"]))
            )
    return TrajectoryFlagIndex(intervals)
