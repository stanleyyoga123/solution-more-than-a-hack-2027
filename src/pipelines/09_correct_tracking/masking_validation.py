"""Deterministic reconstruction checks against clean supplied observations."""

from collections import Counter
from collections.abc import Iterator

import numpy as np

from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .correction_policy import CorrectionPolicy
from .motion import evaluate_bridge, motion_clean
from .tracking_data import TrackingData


def sampled_windows(
    data: TrackingData,
    fps: float,
    entity_type: str,
    missing_frames: int,
    block: str,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
    maximum: int,
) -> Iterator[tuple[int, int, int]]:
    """Sample trusted references; the reconstruction never receives hidden cells."""
    context = policy.context_intervals(fps)
    boundary = int(data.frame_count * 0.8)
    start, stop = (
        (0, boundary)
        if block == "early_80_percent"
        else (
            boundary,
            data.frame_count,
        )
    )
    stride = max(round(20 * fps), missing_frames + 2 * context + 2)
    left_indices = range(start + context, stop - missing_frames - context - 1, stride)
    slots = [
        slot
        for slot, entity in enumerate(data.entities)
        if entity.entity_type == entity_type
    ]
    candidates = [(left, slot) for left in left_indices for slot in slots]
    order = np.random.default_rng(0).permutation(len(candidates))
    count = 0
    for number in order:
        left, slot = candidates[number]
        right = left + missing_frames + 1
        first, last = left - context, right + context
        if np.any(np.diff(data.frames[first : last + 1]) != 1):
            continue
        entity = data.entities[slot]
        if flags.overlaps(
            entity.entity_id, int(data.frames[first]), int(data.frames[last])
        ):
            continue
        truth = data.original[first : last + 1, slot]
        if not motion_clean(truth, fps, entity_type, limits):
            continue
        yield slot, left, right
        count += 1
        if count == maximum:
            return


def evaluate_masking(
    data: TrackingData,
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
) -> list[dict]:
    """Report acceptance separately from errors on accepted reconstructions."""
    summaries = []
    durations = {
        "player": (0.2, 0.5, 1.0, 2.0, 3.0),
        "ball": (0.04, 0.08, 0.12, 0.2),
    }
    context = policy.context_intervals(fps)
    for entity_type, seconds in durations.items():
        sizes = sorted({max(1, round(value * fps)) for value in seconds})
        for size in sizes:
            if size / fps > policy.max_gap_seconds(entity_type):
                continue
            for block in ("early_80_percent", "late_20_percent"):
                rejected = Counter()
                errors = []
                window_maxima = []
                evaluated = 0
                for slot, left, right in sampled_windows(
                    data, fps, entity_type, size, block, limits, policy, flags, 200
                ):
                    evaluated += 1
                    result = evaluate_bridge(
                        data.context(slot, left, context, "left"),
                        data.context(slot, right, context, "right"),
                        size,
                        fps,
                        entity_type,
                        limits,
                        policy,
                    )
                    if not result.accepted:
                        rejected[result.reason] += 1
                        continue
                    truth = data.original[left + 1 : right, slot]
                    distances = np.linalg.norm(result.positions - truth, axis=1)
                    errors.extend(distances.tolist())
                    window_maxima.append(float(distances.max()))
                summaries.append(
                    {
                        "entity_type": entity_type,
                        "missing_frames": size,
                        "gap_seconds": size / fps,
                        "time_block": block,
                        "evaluated_windows": evaluated,
                        "accepted_windows": len(window_maxima),
                        "rejected_windows": sum(rejected.values()),
                        "rejection_reasons": dict(sorted(rejected.items())),
                        "mean_error_m": float(np.mean(errors)) if errors else None,
                        "p95_error_m": (
                            float(np.quantile(errors, 0.95)) if errors else None
                        ),
                        "p95_window_max_error_m": (
                            float(np.quantile(window_maxima, 0.95))
                            if window_maxima
                            else None
                        ),
                    }
                )
    return summaries
