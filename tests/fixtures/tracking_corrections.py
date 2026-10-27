"""Small tracking recordings and real diagnostic inputs for step 09 tests."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import csv
import importlib
import json
from math import isfinite
from pathlib import Path

from tests.fixtures.tracking_quality import Position, read_rows, write_tracking


@dataclass(frozen=True)
class CorrectionInputs:
    tracking: Path
    metadata: Path
    flags: Path
    flags_metadata: Path
    gaps: Path
    gaps_metadata: Path

    def arguments(self) -> tuple[Path, ...]:
        return (
            self.tracking,
            self.metadata,
            self.flags,
            self.flags_metadata,
            self.gaps,
            self.gaps_metadata,
        )


def correction_inputs(
    directory: Path,
    tracks: Mapping[str, Sequence[Position]],
    fps: float = 10,
    teams: Mapping[str, str] | None = None,
) -> CorrectionInputs:
    """Generate source exports plus genuine step 07/08 reports from tiny tracks."""
    tracking, metadata = write_tracking(directory / "source", tracks, fps)
    rows = read_rows(tracking)
    for row in rows:
        if teams:
            row["team_id"] = teams.get(row["entity_id"], row["team_id"])
        row["position_valid"] = str(
            all(row[key] and isfinite(float(row[key])) for key in ("pos_x", "pos_y"))
        )
    with tracking.open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    document = json.loads(metadata.read_text())
    document.update(
        {
            "entity_count_per_frame": len(tracks),
            "player_slot_count": sum(entity != "ball" for entity in tracks),
            "speed_unit": "kph",
            "orientation": {"x": "rightwards", "y": "downwards"},
        }
    )
    metadata.write_text(json.dumps(document))
    screen = importlib.import_module(
        "src.pipelines.07_flag_impossible_trajectories"
    ).run_pipeline
    assess = importlib.import_module(
        "src.pipelines.08_assess_identity_continuity"
    ).run_pipeline
    flags, flags_metadata = screen(tracking, metadata, directory / "flags")
    gaps, gaps_metadata = assess(
        tracking, metadata, flags, flags_metadata, directory / "gaps"
    )
    return CorrectionInputs(
        tracking, metadata, flags, flags_metadata, gaps, gaps_metadata
    )


def linear_track(
    frame_count: int,
    *,
    start: int = 0,
    end: int | None = None,
    x_offset: float = 0,
    y: float = 10,
    speed_mps: float = 1,
    fps: float = 10,
) -> list[Position]:
    """One observable straight-line track in metres, missing outside its extent."""
    stop = frame_count if end is None else end
    positions: list[Position] = [None] * frame_count
    for frame in range(start, stop):
        positions[frame] = (x_offset + speed_mps * frame / fps, y)
    return positions


def indexed_rows(path: Path) -> dict[tuple[int, str], dict[str, str]]:
    return {(int(row["frame"]), row["entity_id"]): row for row in read_rows(path)}
