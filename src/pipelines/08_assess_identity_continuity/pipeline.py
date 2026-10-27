"""Publish conservative continuity assessments for every null tracking run."""

from collections import Counter
from contextlib import closing
import csv
from dataclasses import asdict
import json
import logging
from math import ceil, isfinite
from pathlib import Path
from time import perf_counter

from src.utilities.export_files import staged_outputs
from src.utilities.motion_limits import read_motion_limits
from src.utilities.normalized_tracking_metadata import read_normalized_metadata
from src.utilities.normalized_tracking_reader import (
    TrackingObservation,
    read_normalized_frames,
)
from src.utilities.pipeline_logging import frame_progress
from src.utilities.trajectory_flag_report import (
    read_trajectory_flags,
)

from .gap_assessment import GAP_COLUMNS, GapReport, assess_gap
from .gap_detector import GapDetector
from .gap_policy import GapPolicy

LOGGER = logging.getLogger(__name__)


def run_pipeline(
    tracking: Path,
    metadata: Path,
    flags: Path,
    flags_metadata: Path,
    output_dir: Path,
    max_gap_seconds: float = 2,
    context_seconds: float = 0.2,
    player_prediction_tolerance: float = 2,
    ball_prediction_tolerance: float = 3,
) -> tuple[Path, Path]:
    """Assess same-slot gaps while leaving their coordinates and IDs untouched."""
    started = perf_counter()
    policy = GapPolicy(
        max_gap_seconds,
        context_seconds,
        player_prediction_tolerance,
        ball_prediction_tolerance,
    )
    if any(not isfinite(value) or value <= 0 for value in asdict(policy).values()):
        raise ValueError("Gap policy values must be finite and positive")
    LOGGER.info("Starting 08_assess_identity_continuity; metadata: %s", metadata)
    info = read_normalized_metadata(metadata)
    context_intervals = ceil(context_seconds * info.fps)
    LOGGER.info("Loading trajectory flags: %s; thresholds: %s", flags, flags_metadata)
    limits = read_motion_limits(flags_metadata)
    flag_index = read_trajectory_flags(flags)
    detectors: dict[str, GapDetector] = {}
    entities: dict[str, TrackingObservation] = {}
    reports: list[GapReport] = []
    frame_count = row_count = 0
    with staged_outputs(output_dir, "tracking_gap_continuity") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        LOGGER.info(
            "Reading tracking: %s; writing gap assessments: %s", tracking, csv_path
        )
        with (
            closing(read_normalized_frames(tracking, info)) as records,
            frame_progress(
                records, info.frame_count, "Assessing gaps", LOGGER
            ) as frames,
        ):
            for _, observations in frames:
                frame_count += 1
                for observation in observations:
                    row_count += 1
                    entity_id = observation.entity_id
                    if entity_id not in detectors:
                        detectors[entity_id] = GapDetector(context_intervals)
                        entities[entity_id] = observation
                    for gap in detectors[entity_id].add(observation):
                        reports.append(
                            assess_gap(
                                gap,
                                observation,
                                info.fps,
                                context_intervals,
                                policy,
                                limits,
                                flag_index,
                            )
                        )
        for entity_id, detector in detectors.items():
            for gap in detector.finish():
                reports.append(
                    assess_gap(
                        gap,
                        entities[entity_id],
                        info.fps,
                        context_intervals,
                        policy,
                        limits,
                        flag_index,
                    )
                )
        reports.sort(key=lambda report: (report["start_frame"], report["entity_id"]))
        with staged_csv.open("w", newline="", encoding="utf-8") as destination:
            writer = csv.DictWriter(destination, fieldnames=GAP_COLUMNS)
            writer.writeheader()
            writer.writerows(reports)
        status_counts = Counter(report["status"] for report in reports)
        reason_counts = Counter(report["reason"] for report in reports)
        document = {
            "pipeline": "08_assess_identity_continuity",
            "inputs": {
                "tracking": str(tracking),
                "metadata": str(metadata),
                "flags": str(flags),
                "flags_metadata": str(flags_metadata),
            },
            "fps": info.fps,
            "policy": asdict(policy),
            "context_intervals": context_intervals,
            "speed_thresholds": {
                "player_speed_limit_mps": limits.player_speed_limit_mps,
                "ball_speed_limit_mps": limits.ball_speed_limit_mps,
            },
            "units": {"distance": "metres", "speed": "m/s", "duration": "seconds"},
            "frame_count": frame_count,
            "processed_rows": row_count,
            "gap_count": len(reports),
            "status_counts": {
                name: status_counts[name]
                for name in ("plausible", "implausible", "uncertain")
            },
            "reason_counts": dict(sorted(reason_counts.items())),
            "formulas": {
                "gap_seconds": "missing_frames / fps",
                "required_speed_mps": (
                    "endpoint_distance_m / ((right_frame - left_frame) / fps)"
                ),
                "context_velocity": (
                    "(last_position - first_position) / context_elapsed_seconds"
                ),
                "prediction_errors": (
                    "Euclidean distance between an endpoint and constant-velocity "
                    "prediction from the opposite endpoint"
                ),
            },
            "rule_precedence": [
                "unbounded_gap",
                "flagged_context",
                "excessive_required_speed",
                "long_gap",
                "insufficient_context",
                "motion_disagreement",
                "motion_consistent",
            ],
            "limitations": [
                "Plausible denotes consistent same-slot motion, not verified "
                "player identity or approval to fill positions.",
                "Long gaps can include inactivity or reassignment; "
                "no cross-slot association is performed.",
                "Ball assessments describe motion continuity, "
                "not identification or 3D ball location.",
                "No coordinates are imputed and no entity IDs are changed.",
            ],
        }
        staged_metadata.write_text(
            json.dumps(document, indent=2) + "\n", encoding="utf-8"
        )
    LOGGER.info(
        "Completed 08_assess_identity_continuity: %d frames, %d rows, "
        "%d gaps in %.2f seconds; outputs: %s, %s",
        frame_count,
        row_count,
        len(reports),
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
