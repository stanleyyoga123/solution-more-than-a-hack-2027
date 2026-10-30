"""Write a standalone control submission and reproducibility metadata."""

from dataclasses import asdict
import json
from pathlib import Path
import platform

import numpy as np
from numpy.typing import NDArray

from ..configuration.policy import PossessionPolicy
from ..models.possession_features import PossessionFeatures


def write_submission(
    csv_path: Path,
    metadata_path: Path,
    labels: NDArray[np.str_],
    features: PossessionFeatures,
    policy: PossessionPolicy,
    inputs: dict[str, str],
    started_at_utc: str,
    elapsed_seconds: float,
) -> None:
    with csv_path.open("w", encoding="utf-8") as destination:
        destination.write("frame,label\n")
        destination.writelines(
            f"{frame},{label}\n" for frame, label in enumerate(labels)
        )
    document = {
        "method": "standalone_control_confirmation",
        "method_version": 1,
        "policy": asdict(policy),
        "inputs": inputs,
        "execution": {
            "started_at_utc": started_at_utc,
            "elapsed_seconds": elapsed_seconds,
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
        },
        "frame_count": features.frame_count,
        "processed_tracking_frames": features.processed_tracking_frames,
        "fps": features.fps,
        "teams": dict(zip(("H", "A"), features.metadata.team_names.values())),
        "pitch_dimensions_m": [features.pitch_length, features.pitch_width],
        "label_counts": {label: int(np.sum(labels == label)) for label in "HAD"},
        "frame_convention": "Zero-based source-video frame; source ATD ID minus one",
        "limitations": (
            "Offline backdated control confirmation with no halftime reset. "
            "D means missing or expired ownership, not detected dead-ball play. "
            "Nearest-player proximity is a possession proxy. This standalone "
            "method differs from the cumulative playground e05 experiment."
        ),
    }
    metadata_path.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
