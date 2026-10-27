"""Small normalized tracking exports for motion-quality pipeline tests."""

from collections.abc import Mapping, Sequence
import csv
import json
from pathlib import Path

Position = tuple[float | None, float | None] | None

TRACKING_COLUMNS = (
    "frame",
    "entity_id",
    "entity_type",
    "team_id",
    "pos_x",
    "pos_y",
    "speed_raw",
    "position_valid",
)
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


def write_tracking(
    directory: Path,
    tracks: Mapping[str, Sequence[Position]],
    fps: float = 10,
) -> tuple[Path, Path]:
    """Accept metre positions and write the documented normalized export format."""
    directory.mkdir(parents=True, exist_ok=True)
    tracking = directory / "tracking.csv"
    metadata = directory / "tracking.metadata.json"
    frame_count = len(next(iter(tracks.values())))
    with tracking.open("w", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(TRACKING_COLUMNS)
        for frame in range(frame_count):
            for entity, positions in tracks.items():
                position = positions[frame]
                x, y = position if position is not None else (None, None)
                writer.writerow(
                    (
                        frame,
                        entity,
                        "ball" if entity == "ball" else "player",
                        "" if entity == "ball" else "home",
                        "" if x is None else x / 100,
                        "" if y is None else y / 50,
                        999,
                        x is not None and y is not None,
                    )
                )
    document = {
        "fps": fps,
        "frame_count": frame_count,
        "row_count": frame_count * len(tracks),
        "pitch_dimensions": {"length": 100, "width": 50, "unit": "metres"},
        "entity_ids": list(tracks),
        "teams": {"home": "Home", "away": "Away"},
        "coordinate_space": "normalized_pitch_2d",
        "position_unit": "pitch_fraction",
    }
    metadata.write_text(json.dumps(document))
    return tracking, metadata


def write_flags(
    directory: Path,
    intervals: Sequence[tuple[str, int, int]] = (),
    player_speed_limit: float = 12,
    ball_speed_limit: float = 45,
) -> tuple[Path, Path]:
    """Write valid step 07 artifacts to isolate step 08's assessment behavior."""
    directory.mkdir(parents=True, exist_ok=True)
    flags = directory / "tracking_trajectory_flags.csv"
    metadata = directory / "tracking_trajectory_flags.metadata.json"
    with flags.open("w", newline="") as destination:
        writer = csv.writer(destination)
        writer.writerow(FLAG_COLUMNS)
        for entity, start, end in intervals:
            writer.writerow(
                (
                    entity,
                    "ball" if entity == "ball" else "player",
                    "" if entity == "ball" else "home",
                    start,
                    end,
                    20,
                    "",
                    True,
                    False,
                )
            )
    metadata.write_text(
        json.dumps(
            {
                "thresholds": {
                    "player_speed_limit_mps": player_speed_limit,
                    "player_acceleration_limit_mps2": 15,
                    "ball_speed_limit_mps": ball_speed_limit,
                }
            }
        )
    )
    return flags, metadata


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as source:
        return list(csv.DictReader(source))
