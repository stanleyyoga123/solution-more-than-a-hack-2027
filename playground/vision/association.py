"""Conservative association of sparse ball proposals without changing observations."""

from collections import Counter

import numpy as np
from numpy.typing import NDArray

from .detection import BallDetection
from .policy import VisionPolicy


def select_proposal(
    detections: list[BallDetection], pitch: NDArray[np.float64], policy: VisionPolicy
) -> tuple[BallDetection | None, str]:
    eligible = [
        item
        for item in detections
        if np.isfinite(item.position).all()
        and np.all(np.array(item.position) >= -policy.pitch_padding_m)
        and np.all(np.array(item.position) <= pitch + policy.pitch_padding_m)
    ]
    if not eligible:
        return None, "no_pitch_candidate"
    eligible.sort(key=lambda item: item.confidence, reverse=True)
    if len(eligible) > 1 and (
        eligible[0].confidence - eligible[1].confidence < policy.confidence_margin
    ):
        return None, "ambiguous_candidates"
    return eligible[0], "unambiguous_pitch_candidate"


def recover_positions(
    proposals: dict[int, BallDetection],
    original: NDArray[np.float64],
    fps: float,
    policy: VisionPolicy,
) -> tuple[list[dict], dict[str, int], dict[int, str]]:
    """Require a detection pair, physical speed and compatible nearby anchors."""
    valid = np.isfinite(original).all(axis=1)
    observed_indices = np.flatnonzero(valid)
    frames = sorted(frame for frame in proposals if not valid[frame])
    supported = set()
    maximum_intervals = round(policy.interpolation_seconds * fps)
    for left, right in zip(frames, frames[1:]):
        if right - left > maximum_intervals:
            continue
        speed = np.linalg.norm(
            np.subtract(proposals[right].position, proposals[left].position)
        ) / ((right - left) / fps)
        if speed <= policy.maximum_speed_mps:
            supported.update((left, right))
    accepted = {}
    rejected = Counter()
    decisions = {}
    for frame in frames:
        if frame not in supported:
            rejected["no_temporal_pair"] += 1
            decisions[frame] = "no_temporal_pair"
            continue
        candidate = proposals[frame]
        index = int(np.searchsorted(observed_indices, frame))
        nearby = observed_indices[max(0, index - 1) : index + 1]
        compatible = True
        failure_reason = "incompatible_source_anchor"
        for anchor in nearby:
            elapsed = abs(int(anchor) - frame) / fps
            if elapsed > policy.anchor_seconds:
                continue
            displacement = np.linalg.norm(
                np.subtract(candidate.position, original[anchor])
            )
            if abs(int(anchor) - frame) == 1 and (
                displacement * fps > policy.maximum_speed_mps + 1e-8
            ):
                compatible = False
                failure_reason = "immediate_join_speed_violation"
            if displacement > (
                policy.maximum_speed_mps * elapsed + policy.anchor_padding_m
            ):
                compatible = False
        if not compatible:
            rejected[failure_reason] += 1
            decisions[frame] = failure_reason
            continue
        accepted[frame] = candidate
        decisions[frame] = "accepted_yolo_observation"
    # Separate supported pairs can still disagree at their adjacent endpoints.
    # Neither conflicting observation has stronger physical evidence, so reject both.
    conflicting = set()
    ordered = sorted(accepted)
    for left, right in zip(ordered, ordered[1:]):
        if right - left != 1:
            continue
        speed = (
            np.linalg.norm(
                np.subtract(accepted[right].position, accepted[left].position)
            )
            * fps
        )
        if speed > policy.maximum_speed_mps + 1e-8:
            conflicting.update((left, right))
    for frame in sorted(conflicting):
        del accepted[frame]
        decisions[frame] = "adjacent_detection_speed_conflict"
        rejected["adjacent_detection_speed_conflict"] += 1
    # Rejected anchors or conflicting joins cannot support remaining singletons.
    paired_after_filters = set()
    for left, right in zip(sorted(accepted), sorted(accepted)[1:]):
        if right - left > maximum_intervals:
            continue
        distance = np.linalg.norm(
            np.subtract(accepted[right].position, accepted[left].position)
        )
        if distance / ((right - left) / fps) <= policy.maximum_speed_mps:
            paired_after_filters.update((left, right))
    for frame in sorted(set(accepted) - paired_after_filters):
        del accepted[frame]
        reason = (
            "no_pair_after_motion_filter"
            if conflicting
            else "no_pair_after_anchor_filter"
        )
        decisions[frame] = reason
        rejected[reason] += 1
    recovered = {
        frame: {
            "frame": frame,
            "x_m": item.x_m,
            "y_m": item.y_m,
            "source": "yolo_observation",
            "confidence": item.confidence,
        }
        for frame, item in accepted.items()
    }
    for left, right in zip(sorted(accepted), sorted(accepted)[1:]):
        if right - left > maximum_intervals or valid[left : right + 1].any():
            continue
        first = np.array(accepted[left].position)
        last = np.array(accepted[right].position)
        velocity = (last - first) / ((right - left) / fps)
        if np.linalg.norm(velocity) > policy.maximum_speed_mps:
            continue
        confidence = min(accepted[left].confidence, accepted[right].confidence)
        for frame in range(left + 1, right):
            position = first + (frame - left) / (right - left) * (last - first)
            recovered[frame] = {
                "frame": frame,
                "x_m": float(position[0]),
                "y_m": float(position[1]),
                "source": "yolo_interpolation",
                "confidence": confidence,
            }
    return (
        [recovered[frame] for frame in sorted(recovered)],
        dict(rejected),
        decisions,
    )
