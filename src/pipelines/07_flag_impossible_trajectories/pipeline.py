"""Publish a compact report of suspicious observed trajectory samples."""

from collections import Counter, deque
from contextlib import closing
import csv
from dataclasses import asdict
import json
import logging
from math import isfinite
from pathlib import Path
from time import perf_counter

from src.utilities.export_files import staged_outputs
from src.utilities.motion_limits import MotionLimits
from src.utilities.normalized_tracking_metadata import read_normalized_metadata
from src.utilities.normalized_tracking_reader import (
    TrackingObservation,
    read_normalized_frames,
)
from src.utilities.pipeline_logging import frame_progress
from src.utilities.trajectory_flag_report import FLAG_COLUMNS

from .motion_screen import flag_motion

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    tracking: Path,
    metadata: Path,
    output_dir: Path,
    player_speed_limit: float = 12,
    player_acceleration_limit: float = 15,
    ball_speed_limit: float = 45,
) -> tuple[Path, Path]:
    """Screen normalized coordinates without filling or altering source tracking."""
    started = perf_counter()
    limits = MotionLimits(
        player_speed_limit, player_acceleration_limit, ball_speed_limit
    )
    if any(not isfinite(value) or value <= 0 for value in asdict(limits).values()):
        raise ValueError("Motion limits must be finite and positive")
    LOGGER.info("Starting 07_flag_impossible_trajectories; metadata: %s", metadata)
    info = read_normalized_metadata(metadata)
    history: dict[str, deque[TrackingObservation]] = {}
    entity_counts: Counter[str] = Counter()
    check_counts: Counter[str] = Counter()
    frame_count = row_count = flagged_count = 0
    with staged_outputs(output_dir, "tracking_trajectory_flags") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info("Reading tracking: %s; writing flags: %s", tracking, csv_path)
        with (
            staged_csv.open("w", newline="", encoding="utf-8") as destination,
            closing(read_normalized_frames(tracking, info)) as records,
            frame_progress(
                records, info.frame_count, "Screening motion", LOGGER
            ) as frames,
        ):
            writer = csv.DictWriter(destination, fieldnames=FLAG_COLUMNS)
            writer.writeheader()
            for _, observations in frames:
                frame_count += 1
                for observation in sorted(
                    observations, key=lambda item: item.entity_id
                ):
                    row_count += 1
                    if observation.entity_id not in history:
                        history[observation.entity_id] = deque(maxlen=3)
                    track = history[observation.entity_id]
                    if not observation.position_valid:
                        track.clear()
                        continue
                    if track and track[-1].frame + 1 != observation.frame:
                        track.clear()
                    track.append(observation)
                    flag = flag_motion(track, info.fps, limits)
                    if flag is None:
                        continue
                    writer.writerow(flag)
                    flagged_count += 1
                    entity_counts[observation.entity_id] += 1
                    check_counts["speed"] += int(flag["speed_flag"])
                    check_counts["acceleration"] += int(flag["acceleration_flag"])
        document = {
            "pipeline": "07_flag_impossible_trajectories",
            "inputs": {"tracking": str(tracking), "metadata": str(metadata)},
            "fps": info.fps,
            "pitch_dimensions": {
                "length": info.pitch_length,
                "width": info.pitch_width,
            },
            "units": {"position": "metres", "speed": "m/s", "acceleration": "m/s^2"},
            "thresholds": asdict(limits),
            "formulas": {
                "speed": "norm(position[t] - position[t-1]) * fps",
                "acceleration": "norm(velocity[t] - velocity[t-1]) * fps",
            },
            "frame_count": frame_count,
            "processed_rows": row_count,
            "flagged_rows": flagged_count,
            "flags_by_entity": dict(sorted(entity_counts.items())),
            "flags_by_check": {
                "speed": check_counts["speed"],
                "acceleration": check_counts["acceleration"],
            },
            "support_interval": (
                "Inclusive observed frames used by triggered checks; "
                "combined checks use their union."
            ),
            "limitations": [
                "Thresholds are heuristic screening limits, not verified error labels.",
                "Ball acceleration is not screened; planar ball coordinates "
                "can misrepresent airborne motion.",
                "Calculations reset at missing observations and nonconsecutive frames.",
                "No positions or entity identities are modified; speed_raw is unused.",
            ],
        }
        staged_metadata.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )
    LOGGER.info(
        "Completed 07_flag_impossible_trajectories: %d frames, %d rows, "
        "%d flags in %.2f seconds; outputs: %s, %s",
        frame_count,
        row_count,
        flagged_count,
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
