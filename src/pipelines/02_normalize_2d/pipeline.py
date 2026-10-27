"""Export the supplied normalised 2D pitch observations independently of calibration."""

import csv
from contextlib import closing
import logging
from pathlib import Path
from time import perf_counter

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import read_metadata
from src.utilities.export_files import (
    BASE_COLUMNS,
    frame_rows,
    staged_outputs,
    write_metadata,
)
from src.utilities.pipeline_logging import frame_progress

LOGGER = logging.getLogger(__name__)


def run_pipeline(tracking: Path, metadata: Path, output_dir: Path) -> tuple[Path, Path]:
    """Stream ATD to normalized positions, preserving every slot and missing value."""
    started = perf_counter()
    LOGGER.info("Starting 02_normalize_2d; loading metadata: %s", metadata)
    info = read_metadata(metadata)
    LOGGER.info(
        "Metadata loaded: %d player slots, %d declared frames, %.3f FPS",
        len(info.slot_ids),
        info.expected_frames,
        info.fps,
    )
    LOGGER.info("Reading tracking: %s", tracking)
    with staged_outputs(output_dir, "tracking_normalized_2d") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info("Writing normalized export: %s", csv_path)
        frame_count = 0
        with staged_csv.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.writer(destination)
            writer.writerow(BASE_COLUMNS)
            with (
                closing(read_tracking(tracking)) as records,
                frame_progress(
                    records,
                    info.expected_frames,
                    "Exporting normalized tracking",
                    LOGGER,
                ) as frames,
            ):
                for frame, values in frames:
                    writer.writerows(frame_rows(frame, values, values[:, :2], info))
                    frame_count += 1
        LOGGER.info("Writing metadata: %s", metadata_path)
        write_metadata(
            staged_metadata, info, frame_count, "normalized_pitch_2d", "pitch_fraction"
        )
    LOGGER.info(
        "Completed 02_normalize_2d: %d frames, %d rows in %.2f seconds; "
        "outputs: %s, %s",
        frame_count,
        frame_count * (len(info.slot_ids) + 1),
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
