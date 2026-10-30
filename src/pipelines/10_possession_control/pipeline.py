"""Compose and run standalone team-control confirmation."""

from datetime import datetime, timezone
import logging
from pathlib import Path
from time import perf_counter

from src.utilities.epts_metadata import read_metadata
from src.utilities.export_files import staged_outputs

from .configuration.policy import PossessionPolicy
from .evidence.tracking_loader import TrackingEvidenceLoader
from .export.submission import write_submission
from .inference.control_confirmation import ControlConfirmation

LOGGER = logging.getLogger(__name__)


def run_pipeline(tracking: Path, metadata: Path, output_dir: Path) -> tuple[Path, Path]:
    """Publish one full-timeline control submission and metadata pair."""
    started = perf_counter()
    started_at = datetime.now(timezone.utc).isoformat()
    policy = PossessionPolicy()
    loader = TrackingEvidenceLoader()
    control = ControlConfirmation(policy)
    LOGGER.info("Starting 10_possession_control; loading metadata: %s", metadata)
    with staged_outputs(output_dir, "submission") as paths:
        staged_csv, staged_metadata, csv_path, metadata_path = paths
        info = read_metadata(metadata)
        features = loader.load(tracking, info)
        LOGGER.info("Confirming sustained team control")
        labels = control.predict(features)
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
            },
            started_at,
            perf_counter() - started,
        )
    LOGGER.info(
        "Completed 10_possession_control: %d tracking frames, %d output rows "
        "in %.2f seconds; outputs: %s, %s",
        features.processed_tracking_frames,
        features.frame_count,
        perf_counter() - started,
        csv_path,
        metadata_path,
    )
    return csv_path, metadata_path
