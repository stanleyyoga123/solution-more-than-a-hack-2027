"""Evaluate reconstruction and summarize remaining motion diagnostics."""

from collections import Counter
import logging

import numpy as np

from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .correction_audit import CorrectionAudit
from .correction_policy import CorrectionPolicy
from .identity_validation import evaluate_identity
from .masking_validation import evaluate_masking
from .track_segment import TrackSegment
from .tracking_data import TrackingData

LOGGER = logging.getLogger(__name__)


def _motion_counts(
    data: TrackingData, positions: np.ndarray, fps: float, limits: MotionLimits
) -> dict[str, int]:
    missing = speed_flags = acceleration_flags = flagged_samples = 0
    consecutive = np.diff(data.frames[: data.frame_count]) == 1
    for slot, entity in enumerate(data.entities):
        path = positions[: data.frame_count, slot]
        valid = np.isfinite(path).all(axis=1)
        missing += int((~valid).sum())
        velocity = np.diff(path, axis=0) * fps
        connected = consecutive & valid[:-1] & valid[1:]
        speed = connected & (
            np.linalg.norm(velocity, axis=1) > limits.speed_limit(entity.entity_type)
        )
        acceleration = np.zeros(len(speed), dtype=bool)
        if entity.entity_type == "player":
            acceleration[1:] = (
                connected[:-1]
                & connected[1:]
                & (
                    np.linalg.norm(np.diff(velocity, axis=0) * fps, axis=1)
                    > limits.player_acceleration_limit_mps2
                )
            )
        speed_flags += int(speed.sum())
        acceleration_flags += int(acceleration.sum())
        flagged_samples += int((speed | acceleration).sum())
    return {
        "missing_position_rows": missing,
        "speed_flagged_samples": speed_flags,
        "acceleration_flagged_samples": acceleration_flags,
        "flagged_samples": flagged_samples,
    }


def evaluate_corrections(
    data: TrackingData,
    segments: list[TrackSegment],
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
    audit: CorrectionAudit,
) -> dict:
    LOGGER.info("Evaluating masked observations against clean source tracks")
    masking = evaluate_masking(data, fps, limits, policy, flags)
    LOGGER.info("Evaluating artificial identity fragmentation and competitors")
    identity = evaluate_identity(data, fps, limits, policy, flags)
    LOGGER.info("Counting remaining missing positions and motion flags")
    changes = Counter(change.status for change in audit.changes.values())
    decisions = Counter(f"{row['operation']}:{row['status']}" for row in audit.rows)
    return {
        "method": {
            "seed": 0,
            "maximum_masking_windows_per_stratum": 200,
            "maximum_identity_windows_per_stratum": 50,
            "candidate_stride_seconds": 20,
            "time_blocks": ["early_80_percent", "late_20_percent"],
            "reference_selection": (
                "Only fully observed, contiguous windows without source motion "
                "flags are eligible references. Reconstructors receive only "
                "the context outside each hidden window."
            ),
            "limitations": [
                "Errors measure agreement with supplied tracking, not video truth.",
                "Clean-window sampling does not model every real missing interval.",
                "Errors are conditional on acceptance; rejected counts are separate.",
                "Time blocks are descriptive evaluation, not an untouched test set.",
                "Evaluation does not automatically tune thresholds or approve links.",
            ],
        },
        "masking": masking,
        "identity_fragmentation": identity,
        "diagnostics": {
            "before": _motion_counts(data, data.original, fps, limits),
            "after": _motion_counts(data, data.working, fps, limits),
            "observed_segments": len(segments),
            "changed_rows": dict(sorted(changes.items())),
            "decisions": dict(sorted(decisions.items())),
            "motion_count_scope": (
                "Per source slot, using consecutive finite positions; retained "
                "slot transitions can remain flagged after identity linking."
            ),
        },
    }
