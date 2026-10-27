"""Reciprocal, unambiguous same-team associations between observed segments."""

from bisect import bisect_right
from collections import defaultdict

import numpy as np

from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .correction_audit import CorrectionAudit
from .correction_policy import CorrectionPolicy
from .link_candidate import LinkCandidate
from .motion import motion_clean, prediction_errors
from .track_segment import TrackSegment
from .tracking_data import TrackingData


def select_links(
    candidates: list[LinkCandidate], margin: float, tolerance: float = 2
) -> list[tuple[int, int]]:
    outgoing: dict[int, list[LinkCandidate]] = defaultdict(list)
    incoming: dict[int, list[LinkCandidate]] = defaultdict(list)
    for candidate in candidates:
        outgoing[candidate.left].append(candidate)
        incoming[candidate.right].append(candidate)
    for group in (*outgoing.values(), *incoming.values()):
        group.sort(
            key=lambda candidate: (candidate.score_m, candidate.left, candidate.right)
        )
    accepted = []
    for candidate in candidates:
        before, after = outgoing[candidate.left], incoming[candidate.right]
        if (
            before[0] != candidate
            or after[0] != candidate
            or candidate.score_m > tolerance
        ):
            continue
        outgoing_ambiguous = len(before) > 1 and (
            before[1].score_m == candidate.score_m
            or before[1].score_m - candidate.score_m < margin
        )
        incoming_ambiguous = len(after) > 1 and (
            after[1].score_m == candidate.score_m
            or after[1].score_m - candidate.score_m < margin
        )
        if outgoing_ambiguous or incoming_ambiguous:
            continue
        accepted.append((candidate.left, candidate.right))
    return accepted


def endpoint_context(
    data: TrackingData,
    segment: TrackSegment,
    side: str,
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
    audit: CorrectionAudit,
) -> np.ndarray:
    intervals = policy.context_intervals(fps)
    if segment.end - segment.start < intervals:
        return np.empty((0, 2))
    index = segment.end if side == "left" else segment.start
    start, end = (
        (index - intervals, index) if side == "left" else (index, index + intervals)
    )
    if any((frame, segment.slot) in audit.changes for frame in range(start, end + 1)):
        return np.empty((0, 2))
    context = data.context(segment.slot, index, intervals, side)
    if len(context) != intervals + 1:
        return np.empty((0, 2))
    if flags.overlaps(
        segment.entity_id, int(data.frames[start]), int(data.frames[end])
    ):
        return np.empty((0, 2))
    if not motion_clean(context, fps, segment.entity_type, limits):
        return np.empty((0, 2))
    return context


def link_segments(
    data: TrackingData,
    segments: list[TrackSegment],
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
    audit: CorrectionAudit,
) -> list[tuple[int, int]]:
    contexts = {
        (segment.number, side): endpoint_context(
            data, segment, side, fps, limits, policy, flags, audit
        )
        for segment in segments
        for side in ("left", "right")
    }
    starts = [segment.start_frame for segment in segments]
    candidates = []
    for left in segments:
        if left.entity_type != "player":
            continue
        maximum = left.end_frame + int(policy.player_max_gap_seconds * fps) + 1
        first = bisect_right(starts, left.end_frame)
        last = bisect_right(starts, maximum)
        for right in segments[first:last]:
            if left.team_id != right.team_id or right.entity_type != "player":
                continue
            details = dict(
                entity_id=left.entity_id,
                other_entity_id=right.entity_id,
                segment_id=left.segment_id,
                other_segment_id=right.segment_id,
                start_frame=left.end_frame,
                end_frame=right.start_frame,
                affected_rows=0,
            )
            before, after = (
                contexts[left.number, "left"],
                contexts[right.number, "right"],
            )
            if not len(before) or not len(after):
                audit.record(
                    "link", "rejected", "insufficient_clean_source_context", **details
                )
                continue
            elapsed = (right.start_frame - left.end_frame) / fps
            if (
                np.linalg.norm(after[0] - before[-1]) / elapsed
                > limits.player_speed_limit_mps + 1e-8
            ):
                audit.record("link", "rejected", "excessive_required_speed", **details)
                continue
            forward, backward = prediction_errors(before, after, elapsed, fps)
            candidates.append(
                LinkCandidate(
                    left.number, right.number, forward, backward, max(forward, backward)
                )
            )
    accepted = select_links(
        candidates, policy.uniqueness_margin_m, policy.player_prediction_tolerance_m
    )
    accepted_set = set(accepted)
    for candidate in candidates:
        left, right = segments[candidate.left], segments[candidate.right]
        is_accepted = (candidate.left, candidate.right) in accepted_set
        reason = (
            "unique_motion_match" if is_accepted else "ambiguous_or_nonreciprocal_match"
        )
        if candidate.score_m > policy.player_prediction_tolerance_m:
            reason = "motion_disagreement"
        audit.record(
            "link",
            "accepted" if is_accepted else "rejected",
            reason,
            entity_id=left.entity_id,
            other_entity_id=right.entity_id,
            segment_id=left.segment_id,
            other_segment_id=right.segment_id,
            start_frame=left.end_frame,
            end_frame=right.start_frame,
            forward_error_m=candidate.forward_error_m,
            backward_error_m=candidate.backward_error_m,
            score_m=candidate.score_m,
            affected_rows=0,
        )
    return accepted
