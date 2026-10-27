"""Write the organisers' nearest-player possession baseline as a submission CSV."""

from contextlib import closing
import json
import logging
from pathlib import Path
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import TrackingMetadata, read_metadata
from src.utilities.export_files import staged_outputs
from src.utilities.pipeline_logging import frame_progress

LOGGER = logging.getLogger(__name__)

HOME, AWAY, NOBODY = 0, 1, -1
LABELS = ("H", "A", "D")


def slot_teams(info: TrackingMetadata) -> NDArray[np.int8]:
    """HOME or AWAY per slot. The first team in the metadata is the home side."""
    home_id = next(iter(info.team_names))
    return np.array(
        [HOME if team == home_id else AWAY for team in info.slot_team_ids],
        dtype=np.int8,
    )


def nearest_team(
    values: NDArray[np.float64], teams: NDArray[np.int8], pitch: NDArray[np.float64]
) -> int:
    """Team of the player nearest the ball in metres, or NOBODY without an answer.

    The last row of values is the ball. Positions are scaled to metres first because
    the pitch is not square.
    """
    ball = values[-1, :2] * pitch
    players = values[:-1, :2] * pitch
    distances = np.hypot(*(players - ball).T)
    if not np.isfinite(distances).any():
        return NOBODY
    return int(teams[np.nanargmin(distances)])


def smooth(codes: NDArray[np.int8], window: int) -> NDArray[np.str_]:
    """Centred majority vote over +/- window frames; D where nobody is seen.

    Ties go to the home side, as in the organisers' starter baseline.
    """
    home_total = np.concatenate(([0], np.cumsum(codes == HOME)))
    away_total = np.concatenate(([0], np.cumsum(codes == AWAY)))
    index = np.arange(len(codes))
    low = np.maximum(0, index - window)
    high = np.minimum(len(codes), index + window + 1)
    home = home_total[high] - home_total[low]
    away = away_total[high] - away_total[low]
    labels = np.full(len(codes), "D", dtype="<U1")
    seen = (home + away) > 0
    labels[seen] = np.where(home[seen] >= away[seen], "H", "A")
    return labels


def run_pipeline(
    tracking: Path, metadata: Path, output_dir: Path, window: int = 50
) -> tuple[Path, Path]:
    """Label every source frame H, A or D and publish the CSV with a description."""
    started = perf_counter()
    LOGGER.info("Starting 05_possession_baseline; loading metadata: %s", metadata)
    info = read_metadata(metadata)
    teams = slot_teams(info)
    pitch = np.array([info.pitch_length, info.pitch_width])
    codes = np.full(info.expected_frames, NOBODY, dtype=np.int8)

    LOGGER.info("Reading tracking: %s", tracking)
    with (
        closing(read_tracking(tracking)) as records,
        frame_progress(
            records, info.expected_frames, "Finding nearest players", LOGGER
        ) as frames,
    ):
        for frame, values in frames:
            codes[frame] = nearest_team(values, teams, pitch)
    labels = smooth(codes, window)

    stem = "possession_baseline"
    with staged_outputs(output_dir, stem) as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info("Writing submission: %s", csv_path)
        with staged_csv.open("w", encoding="utf-8") as destination:
            destination.write("frame,label\n")
            destination.writelines(
                f"{frame},{label}\n" for frame, label in enumerate(labels)
            )
        home_name, away_name = info.team_names.values()
        document = {
            "method": "nearest tracked player to the ball, centred majority vote",
            "window_frames": window,
            "frame_count": len(labels),
            "ball_located_frames": int(np.sum(codes != NOBODY)),
            "label_counts": {name: int(np.sum(labels == name)) for name in LABELS},
            "teams": {"H": home_name, "A": away_name},
        }
        staged_metadata.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )
    LOGGER.info(
        "Completed 05_possession_baseline: %d frames in %.2f seconds; outputs: %s, %s",
        len(labels),
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
