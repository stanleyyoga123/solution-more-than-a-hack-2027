"""Replace uniquely bracketed brief speed spikes using reliable source context."""

from collections import defaultdict
import csv
from math import floor
from pathlib import Path

import numpy as np

from src.utilities.motion_limits import MotionLimits

from .correction_audit import CorrectionAudit, PositionChange
from .correction_policy import CorrectionPolicy
from .motion import evaluate_bridge
from .tracking_data import TrackingData


def repair_spikes(
    data: TrackingData,
    flags: Path,
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    audit: CorrectionAudit,
) -> None:
    intervals = policy.context_intervals(fps)
    maximum = floor(policy.spike_max_seconds * fps + 1e-8)
    by_entity: dict[str, list[dict[str, str]]] = defaultdict(list)
    with flags.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            by_entity[row["entity_id"]].append(row)
    for slot, entity in enumerate(data.entities):
        positions = data.original[: data.frame_count, slot]
        candidates = set()
        for row in by_entity[entity.entity_id]:
            if row["speed_flag"] != "True":
                continue
            boundary = int(
                np.searchsorted(data.frames[: data.frame_count], int(row["end_frame"]))
            )
            for start in range(
                max(1, boundary - maximum), min(boundary + 1, data.frame_count - 1)
            ):
                for length in range(1, maximum + 1):
                    end = start + length - 1
                    if end + 1 >= data.frame_count:
                        continue
                    incoming = (
                        np.linalg.norm(positions[start] - positions[start - 1]) * fps
                    )
                    outgoing = np.linalg.norm(positions[end + 1] - positions[end]) * fps
                    if incoming > limits.speed_limit(
                        entity.entity_type
                    ) and outgoing > limits.speed_limit(entity.entity_type):
                        candidates.add((start, end))
        supported = []
        attempted = set()
        for start, end in sorted(candidates):
            attempted.add((start, end))
            left = data.context(slot, start - 1, intervals, "left")
            right = data.context(slot, end + 1, intervals, "right")
            reason = ""
            if not np.isfinite(positions[start : end + 1]).all():
                reason = "missing_candidate_position"
            elif np.any(np.diff(data.frames[start - 1 : end + 2]) != 1):
                reason = "nonconsecutive_frames"
            assessment = evaluate_bridge(
                left, right, end - start + 1, fps, entity.entity_type, limits, policy
            )
            if reason or not assessment.accepted:
                audit.record(
                    "repair",
                    "rejected",
                    reason or assessment.reason,
                    entity_id=entity.entity_id,
                    start_frame=int(data.frames[start]),
                    end_frame=int(data.frames[end]),
                    forward_error_m=assessment.forward_error_m,
                    backward_error_m=assessment.backward_error_m,
                    affected_rows=0,
                )
                continue
            supported.append((start, end, assessment))
        groups = []
        for candidate in supported:
            if groups and candidate[0] <= max(item[1] for item in groups[-1]):
                groups[-1].append(candidate)
            else:
                groups.append([candidate])
        for group in groups:
            minimum = min(end - start for start, end, _ in group)
            shortest = [item for item in group if item[1] - item[0] == minimum]
            chosen = shortest[0] if len(shortest) == 1 else None
            for start, end, assessment in group:
                accepted = (
                    chosen is not None and start == chosen[0] and end == chosen[1]
                )
                row = audit.record(
                    "repair",
                    "accepted" if accepted else "rejected",
                    "isolated_spike" if accepted else "ambiguous_spike_interval",
                    entity_id=entity.entity_id,
                    start_frame=int(data.frames[start]),
                    end_frame=int(data.frames[end]),
                    forward_error_m=assessment.forward_error_m,
                    backward_error_m=assessment.backward_error_m,
                    affected_rows=end - start + 1 if accepted else 0,
                )
                if accepted:
                    data.working[start : end + 1, slot] = assessment.positions
                    for offset, position in enumerate(
                        assessment.positions, start=start
                    ):
                        audit.changes[offset, slot] = PositionChange(
                            position.copy(), "repaired", row["correction_id"]
                        )
        for flag in by_entity[entity.entity_id]:
            start_frame, end_frame = int(flag["start_frame"]), int(flag["end_frame"])
            if any(
                int(data.frames[start]) <= end_frame
                and int(data.frames[end]) >= start_frame
                for start, end in attempted
            ):
                continue
            audit.record(
                "repair",
                "rejected",
                (
                    "acceleration_only"
                    if flag["speed_flag"] != "True"
                    else "no_supported_isolated_spike"
                ),
                entity_id=entity.entity_id,
                start_frame=start_frame,
                end_frame=end_frame,
                affected_rows=0,
            )
