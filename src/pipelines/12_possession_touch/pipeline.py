"""Compose and run ownership inference with dead-ball detection."""

from datetime import datetime, timezone
import logging
from pathlib import Path
from time import perf_counter

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import read_metadata
from src.utilities.export_files import staged_outputs

from .configuration.policy import PossessionPolicy
from .evidence.set_piece_tags import read_set_piece_windows
from .evidence.tracking_loader import TrackingEvidenceLoader
from .export.submission import write_submission
from .inference.dead_ball import DeadBallDetector
from .inference.ownership import Ownership
from .models.possession_features import PossessionFeatures

LOGGER = logging.getLogger(__name__)


def label_timeline(
    features: PossessionFeatures,
    policy: PossessionPolicy,
    ownership: Ownership,
    stopped: NDArray[np.bool_],
) -> NDArray[np.str_]:
    """X outside the graded halves, D before each kick-off, then owner or D."""
    labels = np.full(features.frame_count, "X", dtype="<U1")
    for (first, last), kickoff in zip(
        policy.graded_halves, policy.kickoff_frames, strict=True
    ):
        labels[first:kickoff] = "D"
        owner = ownership.predict(features.between(kickoff, last + 1))
        labels[kickoff : last + 1] = np.where(stopped[kickoff : last + 1], "D", owner)
    return labels


def run_pipeline(
    tracking: Path,
    metadata: Path,
    smart_tagging: Path,
    output_dir: Path,
    policy: PossessionPolicy = PossessionPolicy(),
) -> tuple[Path, Path]:
    """Publish one full-timeline submission and metadata pair."""
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    loader = TrackingEvidenceLoader()
    ownership = Ownership(policy)
    LOGGER.info("Starting 12_possession_touch; loading metadata: %s", metadata)
    with staged_outputs(output_dir, "possession_touch") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        info = read_metadata(metadata)
        features = loader.load(tracking, info)
        LOGGER.info("Reading set-piece tags: %s", smart_tagging)
        windows = read_set_piece_windows(smart_tagging, info.fps)
        LOGGER.info("Detecting stoppages and following team touches")
        stopped = DeadBallDetector(policy, windows).detect(features)
        labels = label_timeline(features, policy, ownership, stopped)
        LOGGER.info("Writing submission: %s; metadata: %s", csv_path, metadata_path)
        write_submission(
            staged_csv,
            staged_metadata,
            labels,
            features,
            policy,
            {
                "tracking": str(tracking.resolve()),
                "metadata": str(metadata.resolve()),
                "smart_tagging": str(smart_tagging.resolve()),
            },
            started_at,
            perf_counter() - started,
        )
    LOGGER.info(
        "Completed 12_possession_touch: %d tracking frames, %d output rows "
        "in %.2f seconds; outputs: %s, %s",
        features.processed_tracking_frames,
        features.frame_count,
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
