"""Load tactical evidence and safely publish a competition submission pair."""

from contextlib import closing
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
from time import perf_counter

import numpy as np

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import read_metadata
from src.utilities.export_files import staged_outputs
from src.utilities.pipeline_logging import frame_progress

from .strategy import infer, nearest_label

LOGGER = logging.getLogger(__name__)
# Published tactical video coordinates (inclusive), not scoreboard or broadcast time.
# https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/games.py
FRAME_COUNT = 199319
HALVES = ((11185, 90651), (110808, 190197))


def run_pipeline(
    tracking: Path,
    metadata: Path,
    output_dir: Path,
    strategy: str = "nearest-continuity",
    max_gap_frames: int = 25,
) -> tuple[Path, Path]:
    """Write all tactical video frames, abstaining where evidence is insufficient."""
    if strategy != "nearest-continuity":
        raise ValueError(f"Unknown strategy: {strategy}")
    if max_gap_frames < 0:
        raise ValueError("max_gap_frames must be nonnegative")
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    LOGGER.info("Starting 09_possession_inference; loading metadata: %s", metadata)
    info = read_metadata(metadata)
    home_id = next(iter(info.team_names))
    teams = np.array(
        [0 if team == home_id else 1 for team in info.slot_team_ids], dtype=np.int8
    )
    pitch = np.array([info.pitch_length, info.pitch_width])
    evidence = np.full(FRAME_COUNT, "X", dtype="<U1")
    processed = 0
    # Enter before processing to reject existing outputs promptly.
    with staged_outputs(output_dir, "possession_inference") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info("Reading tactical tracking: %s", tracking)
        with (
            closing(read_tracking(tracking)) as records,
            frame_progress(
                records, info.expected_frames, "Finding nearest players", LOGGER
            ) as frames,
        ):
            for frame, values in frames:
                if any(start <= frame <= end for start, end in HALVES):
                    evidence[frame] = nearest_label(values, teams, pitch)
                processed += 1
        LOGGER.info("Applying %s with maximum gap %d frames", strategy, max_gap_frames)
        labels = infer(evidence, HALVES, max_gap_frames)
        counts = {label: int(np.sum(labels == label)) for label in "HADX"}
        LOGGER.info("Writing submission: %s; metadata: %s", csv_path, metadata_path)
        with staged_csv.open("w", encoding="utf-8") as destination:
            destination.write("frame,label\n")
            destination.writelines(
                f"{frame},{label}\n" for frame, label in enumerate(labels)
            )
        document = {
            "strategy": strategy,
            "strategy_version": 1,
            "parameters": {"max_gap_frames": max_gap_frames},
            "inputs": {
                "tracking": str(tracking.resolve()),
                "metadata": str(metadata.resolve()),
            },
            "execution": {
                "started_at_utc": started_at,
                "elapsed_seconds": perf_counter() - started,
                "python_version": platform.python_version(),
                "numpy_version": np.__version__,
            },
            "frame_count": FRAME_COUNT,
            "processed_tracking_frames": processed,
            "fps": info.fps,
            "halves_inclusive": HALVES,
            "frame_convention": "Zero-based tactical video frame; ATD source ID minus one",
            "teams": dict(zip(("H", "A"), info.team_names.values())),
            "pitch_dimensions_m": [info.pitch_length, info.pitch_width],
            "observed_team_frames": int(np.sum(evidence != "X")),
            "filled_frames": int(np.sum((evidence == "X") & (labels != "X"))),
            "label_counts": counts,
            "limitations": "Unknown evidence is X; no dead-ball inference. Experimental, not a validated improvement.",
        }
        staged_metadata.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )
    LOGGER.info(
        "Completed 09_possession_inference: %d tracking frames, %d output rows in %.2f seconds; "
        "occupancy %s; outputs: %s, %s",
        processed,
        FRAME_COUNT,
        perf_counter() - started,
        counts,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
