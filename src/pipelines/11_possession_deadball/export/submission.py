"""Write a possession submission and reproducibility metadata."""

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
        "method": "ownership_with_dead_ball_detection",
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
        "label_counts": {label: int(np.sum(labels == label)) for label in "HADX"},
        "frame_convention": "Zero-based source-video frame; source ATD ID minus one",
        "limitations": (
            "Offline backdated control confirmation, restarted at each kick-off. "
            "D comes from slow player movement, a ball beyond the lines and "
            "automatic set-piece tags, so slow live play can be marked D and a "
            "moving dead ball can be missed. Nearest-player proximity is a "
            "possession proxy. Frames outside the published halves are X."
        ),
    }
    metadata_path.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
