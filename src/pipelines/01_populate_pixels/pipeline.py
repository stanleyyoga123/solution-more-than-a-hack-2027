"""Export per-frame tracking positions projected into original-video pixels."""

import csv
from contextlib import closing
import logging
from pathlib import Path
from time import perf_counter

import numpy as np

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import read_metadata
from src.utilities.export_files import (
    BASE_COLUMNS,
    csv_number,
    frame_rows,
    staged_outputs,
    write_metadata,
)
from src.utilities.pipeline_logging import frame_progress

from .homography_reader import read_homographies

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    tracking: Path, metadata: Path, homography: Path, output_dir: Path
) -> tuple[Path, Path]:
    """Project positions and retain every slot, including unavailable calibration."""
    started = perf_counter()
    LOGGER.info("Starting 01_populate_pixels; loading metadata: %s", metadata)
    info = read_metadata(metadata)
    LOGGER.info(
        "Metadata loaded: %d player slots, %d declared frames, %.3f FPS",
        len(info.slot_ids),
        info.expected_frames,
        info.fps,
    )
    LOGGER.info("Reading tracking: %s", tracking)
    LOGGER.info("Reading homography: %s", homography)
    with staged_outputs(output_dir, "tracking_pixels") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info("Writing pixel export: %s", csv_path)
        frame_count = 0
        calibrations = read_homographies(homography)
        try:
            with staged_csv.open("w", newline="", encoding="utf-8") as destination:
                writer = csv.writer(destination)
                writer.writerow(
                    (*BASE_COLUMNS, "homography_valid", "reprojection_error")
                )
                with (
                    closing(read_tracking(tracking)) as records,
                    frame_progress(
                        records, info.expected_frames, "Projecting tracking", LOGGER
                    ) as frames,
                ):
                    for frame, values in frames:
                        _, matrix, error = next(calibrations)
                        pixels = np.full((len(values), 2), np.nan)
                        if matrix is not None:
                            observed = np.isfinite(values[:, :2]).all(axis=1)
                            points = values[observed, :2]
                            homogeneous = (
                                np.column_stack((points, np.ones(len(points))))
                                @ matrix.T
                            )
                            with np.errstate(
                                divide="ignore", invalid="ignore", over="ignore"
                            ):
                                projected = homogeneous[:, :2] / homogeneous[:, 2, None]
                            projected[~np.isfinite(projected).all(axis=1)] = np.nan
                            pixels[observed] = projected
                        writer.writerows(
                            (*row, matrix is not None, csv_number(error))
                            for row in frame_rows(frame, values, pixels, info)
                        )
                        frame_count += 1
        finally:
            calibrations.close()
        LOGGER.info("Writing metadata: %s", metadata_path)
        write_metadata(staged_metadata, info, frame_count, "video_pixels", "pixels")
    LOGGER.info(
        "Completed 01_populate_pixels: %d frames, %d rows in %.2f seconds; "
        "outputs: %s, %s",
        frame_count,
        frame_count * (len(info.slot_ids) + 1),
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
