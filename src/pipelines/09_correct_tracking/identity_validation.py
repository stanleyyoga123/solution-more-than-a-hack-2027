"""Controlled segment fragmentation with real same-team motion competitors."""

import numpy as np

from src.utilities.motion_limits import MotionLimits
from src.utilities.trajectory_flag_report import TrajectoryFlagIndex

from .correction_policy import CorrectionPolicy
from .link_candidate import LinkCandidate
from .linking import select_links
from .masking_validation import sampled_windows
from .motion import motion_clean, prediction_errors
from .tracking_data import TrackingData


def _visible_contexts(
    data: TrackingData,
    index: int,
    side: str,
    team_id: str,
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
) -> dict[int, np.ndarray]:
    context = policy.context_intervals(fps)
    result = {}
    first, last = (
        (index - context, index)
        if side == "left"
        else (
            index,
            index + context,
        )
    )
    for slot, entity in enumerate(data.entities):
        if entity.entity_type != "player" or entity.team_id != team_id:
            continue
        positions = data.context(slot, index, context, side)
        if len(positions) != context + 1:
            continue
        if flags.overlaps(
            entity.entity_id, int(data.frames[first]), int(data.frames[last])
        ):
            continue
        if motion_clean(positions, fps, "player", limits):
            result[slot] = positions
    return result


def evaluate_identity(
    data: TrackingData,
    fps: float,
    limits: MotionLimits,
    policy: CorrectionPolicy,
    flags: TrajectoryFlagIndex,
) -> dict:
    """Change segment IDs, retain all visible competitors, and reuse link selection."""
    summaries = []
    sizes = sorted({max(1, round(seconds * fps)) for seconds in (0.2, 1, 3)})
    for size in sizes:
        if size / fps > policy.player_max_gap_seconds:
            continue
        for block in ("early_80_percent", "late_20_percent"):
            recovered = incorrect = abstained = samples_with_competitors = 0
            for slot, left, right in sampled_windows(
                data, fps, "player", size, block, limits, policy, flags, 50
            ):
                team = data.entities[slot].team_id
                before = _visible_contexts(
                    data, left, "left", team, fps, limits, policy, flags
                )
                after = _visible_contexts(
                    data, right, "right", team, fps, limits, policy, flags
                )
                elapsed = (right - left) / fps
                candidates = []
                for old_slot, old_context in before.items():
                    for new_slot, new_context in after.items():
                        speed = (
                            np.linalg.norm(new_context[0] - old_context[-1]) / elapsed
                        )
                        if speed > limits.player_speed_limit_mps + 1e-8:
                            continue
                        forward, backward = prediction_errors(
                            old_context, new_context, elapsed, fps
                        )
                        candidates.append(
                            LinkCandidate(
                                old_slot * 2,
                                new_slot * 2 + 1,
                                forward,
                                backward,
                                max(forward, backward),
                            )
                        )
                expected = (slot * 2, slot * 2 + 1)
                if any(
                    (item.left == expected[0] or item.right == expected[1])
                    and (item.left, item.right) != expected
                    for item in candidates
                ):
                    samples_with_competitors += 1
                selected = select_links(
                    candidates,
                    policy.uniqueness_margin_m,
                    policy.player_prediction_tolerance_m,
                )
                if expected in selected:
                    recovered += 1
                elif any(a == expected[0] or b == expected[1] for a, b in selected):
                    incorrect += 1
                else:
                    abstained += 1
            summaries.append(
                {
                    "missing_frames": size,
                    "gap_seconds": size / fps,
                    "time_block": block,
                    "evaluated_windows": recovered + incorrect + abstained,
                    "windows_with_feasible_competitors": samples_with_competitors,
                    "recovered_source_pair": recovered,
                    "different_source_pair": incorrect,
                    "abstained": abstained,
                }
            )
    tied = [LinkCandidate(0, 1, 0, 0, 0), LinkCandidate(0, 2, 0, 0, 0)]
    return {
        "reference": "Artificially renamed segments of clean source-slot tracks",
        "limitation": (
            "Source-slot continuity is a controlled reference, not verified person "
            "identity. Competitors use the same team's observed endpoint contexts."
        ),
        "summaries": summaries,
        "identical_candidate_probe_rejected": not select_links(
            tied, policy.uniqueness_margin_m, policy.player_prediction_tolerance_m
        ),
    }
