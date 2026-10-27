"""Interpolate supported identity bridges while retaining unresolved source gaps."""

import csv
from pathlib import Path

import numpy as np

from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .correction_audit import CorrectionAudit, PositionChange
from .correction_policy import CorrectionPolicy
from .linking import endpoint_context
from .motion import evaluate_bridge
from .track_segment import TrackSegment
from .tracking_data import TrackingData


def read_gap_evidence(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as source:
        return list(csv.DictReader(source))


def source_gap_details(row: dict[str, str]) -> dict:
    return {
        "source_gap_status": row["status"],
        "source_gap_reason": row["reason"],
        "source_gap_start_frame": row["start_frame"],
        "source_gap_end_frame": row["end_frame"],
    }


def impute_gaps(
    data: TrackingData,
    segments: list[TrackSegment],
    links: list[tuple[int, int]],
    identities: dict[int, str],
    evidence: list[dict[str, str]],
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
    audit: CorrectionAudit,
) -> None:
    by_bounds = {
        (row["entity_id"], int(row["start_frame"]), int(row["end_frame"])): row
        for row in evidence
    }
    bridges = list(links)
    ball_segments = [segment for segment in segments if segment.entity_type == "ball"]
    bridges.extend(
        (left.number, right.number)
        for left, right in zip(ball_segments, ball_segments[1:])
    )
    visited = set()
    for left_number, right_number in sorted(bridges):
        left, right = segments[left_number], segments[right_number]
        missing_frames = right.start_frame - left.end_frame - 1
        if missing_frames == 0:
            continue
        start, end = left.end_frame + 1, right.start_frame - 1
        source_key = (left.entity_id, start, end)
        source = by_bounds.get(source_key)
        details = dict(
            entity_id=left.entity_id,
            other_entity_id=right.entity_id,
            segment_id=left.segment_id,
            other_segment_id=right.segment_id,
            corrected_entity_id=identities[left.number],
            start_frame=start,
            end_frame=end,
            affected_rows=0,
        )
        if source is not None:
            visited.add(source_key)
            details.update(source_gap_details(source))
        reason = ""
        if missing_frames / fps > policy.max_gap_seconds(left.entity_type) + 1e-8:
            reason = "long_gap"
        elif right.start - left.end - 1 != missing_frames:
            reason = "nonconsecutive_frames"
        elif (
            np.isfinite(data.original[left.end + 1 : right.start, left.slot])
            .all(axis=1)
            .any()
        ):
            reason = "source_slot_occupied"
        before = endpoint_context(data, left, "left", fps, limits, policy, flags, audit)
        after = endpoint_context(
            data, right, "right", fps, limits, policy, flags, audit
        )
        assessment = evaluate_bridge(
            before, after, missing_frames, fps, left.entity_type, limits, policy
        )
        if reason or not assessment.accepted:
            audit.record(
                "imputation",
                "rejected",
                reason or assessment.reason,
                forward_error_m=assessment.forward_error_m,
                backward_error_m=assessment.backward_error_m,
                **details,
            )
            continue
        details["affected_rows"] = missing_frames
        row = audit.record(
            "imputation",
            "accepted",
            "motion_consistent",
            forward_error_m=assessment.forward_error_m,
            backward_error_m=assessment.backward_error_m,
            **details,
        )
        for index, position in enumerate(assessment.positions, start=left.end + 1):
            audit.changes[index, left.slot] = PositionChange(
                position.copy(),
                "imputed",
                row["correction_id"],
                identities[left.number],
            )
            data.working[index, left.slot] = position
    for source in evidence:
        key = (
            source["entity_id"],
            int(source["start_frame"]),
            int(source["end_frame"]),
        )
        if key in visited:
            continue
        entity_type = source["entity_type"]
        if not source["left_frame"] or not source["right_frame"]:
            reason = "unbounded_gap"
        elif float(source["gap_seconds"]) > policy.max_gap_seconds(entity_type) + 1e-8:
            reason = "long_gap"
        else:
            reason = "unresolved_identity_or_motion"
        audit.record(
            "imputation",
            "rejected",
            reason,
            entity_id=source["entity_id"],
            start_frame=int(source["start_frame"]),
            end_frame=int(source["end_frame"]),
            affected_rows=0,
            **source_gap_details(source),
        )
