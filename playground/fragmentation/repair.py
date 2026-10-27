"""Bounded offline interval repairs driven only by tracking evidence."""

import logging
from math import floor

import numpy as np
from numpy.typing import NDArray

from playground.temporal import true_runs

from .evidence import FragmentationEvidence
from .policy import FragmentationPolicy

LOGGER = logging.getLogger(__name__)
type AuditRecord = dict[str, int | str | float]


def _team_code(label: str) -> int:
    return 0 if label == "H" else 1


def _adjacent_run_start(labels: NDArray[np.str_], end: int) -> int:
    start = end - 1
    while start > 0 and labels[start - 1] == labels[end - 1]:
        start -= 1
    return start


def _adjacent_run_end(labels: NDArray[np.str_], start: int) -> int:
    end = start + 1
    while end < len(labels) and labels[end] == labels[start]:
        end += 1
    return end


def _has_anchor(
    labels: NDArray[np.str_],
    evidence: FragmentationEvidence,
    start: int,
    end: int,
    context: int,
    left: bool,
) -> bool:
    if left:
        low = max(_adjacent_run_start(labels, start), start - context)
        high = start
        team = labels[start - 1]
    else:
        low = end
        high = min(_adjacent_run_end(labels, end), end + context)
        team = labels[end]
    return bool((evidence.confirmed_control[low:high] == _team_code(team)).any())


def _boundary_costs(
    evidence: FragmentationEvidence,
    left_team: str,
    low: int,
    high: int,
) -> NDArray[np.float64]:
    """Cost for boundaries low..high, assigning frames before to left team."""
    if left_team == "H":
        left_support = evidence.home_support[low:high]
        right_support = evidence.away_support[low:high]
    else:
        left_support = evidence.away_support[low:high]
        right_support = evidence.home_support[low:high]
    left_cumulative = np.r_[0, np.cumsum(left_support)]
    right_cumulative = np.r_[0, np.cumsum(right_support)]
    return right_cumulative + left_cumulative[-1] - left_cumulative


def join_uncertain_gaps(
    labels: NDArray[np.str_],
    evidence: FragmentationEvidence,
    fps: float,
    policy: FragmentationPolicy = FragmentationPolicy(),
) -> tuple[NDArray[np.str_], list[AuditRecord]]:
    """Join short same-team gaps unless dead or confirmed opponent evidence exists."""
    result = labels.copy()
    maximum = floor(policy.uncertain_gap_seconds * fps)
    audits: list[AuditRecord] = []
    for start, end in true_runs(labels == "U"):
        if start == 0 or end == len(labels) or end - start > maximum:
            continue
        team = result[start - 1]
        if team not in ("H", "A") or result[end] != team:
            continue
        opponent = 1 - _team_code(team)
        if evidence.dead[start:end].any():
            continue
        if (evidence.confirmed_control[start:end] == opponent).any():
            continue
        result[start:end] = team
        audits.append(
            {
                "operation": "join_uncertain_gap",
                "start_frame": start,
                "end_frame_exclusive": end,
                "assigned_label": str(team),
                "reason": "same_team_endpoints_without_opposing_or_dead_evidence",
            }
        )
    LOGGER.info("Joined %d same-team uncertain gaps", len(audits))
    return result, audits


def remove_unsupported_islands(
    labels: NDArray[np.str_],
    evidence: FragmentationEvidence,
    fps: float,
    policy: FragmentationPolicy = FragmentationPolicy(),
) -> tuple[NDArray[np.str_], list[AuditRecord]]:
    """Remove short opponent islands only with supported flanking control."""
    result = labels.copy()
    maximum = floor(policy.unsupported_island_seconds * fps)
    context = max(1, floor(policy.anchor_context_seconds * fps))
    audits: list[AuditRecord] = []
    for team in ("H", "A"):
        for start, end in true_runs(result == team):
            if start == 0 or end == len(result) or end - start > maximum:
                continue
            flank = result[start - 1]
            if flank not in ("H", "A") or flank == team or result[end] != flank:
                continue
            if evidence.dead[start:end].any():
                continue
            if (evidence.confirmed_control[start:end] == _team_code(team)).any():
                continue
            if not _has_anchor(result, evidence, start, end, context, left=True):
                continue
            if not _has_anchor(result, evidence, start, end, context, left=False):
                continue
            result[start:end] = flank
            audits.append(
                {
                    "operation": "remove_unsupported_island",
                    "start_frame": start,
                    "end_frame_exclusive": end,
                    "previous_label": team,
                    "assigned_label": str(flank),
                    "reason": "no_sustained_island_control_with_two_supported_flanks",
                }
            )
    LOGGER.info("Removed %d unsupported opponent islands", len(audits))
    return result, audits


def resolve_turnover_gaps(
    labels: NDArray[np.str_],
    evidence: FragmentationEvidence,
    fps: float,
    policy: FragmentationPolicy = FragmentationPolicy(),
) -> tuple[NDArray[np.str_], list[AuditRecord]]:
    """Resolve short uncertain gaps into one transition between supported teams.

    Unknown evidence is neutral. Among equal-cost boundaries, prefer the first
    supported right-team onset; without such support inside the gap, retain the
    incumbent until the right endpoint. Audits retain the full uncertainty span.
    """
    result = labels.copy()
    maximum = floor(policy.uncertain_gap_seconds * fps)
    context = max(1, floor(policy.anchor_context_seconds * fps))
    audits: list[AuditRecord] = []
    for start, end in true_runs(labels == "U"):
        if start == 0 or end == len(labels) or end - start > maximum:
            continue
        left_team, right_team = result[start - 1], result[end]
        if left_team not in ("H", "A") or right_team not in ("H", "A"):
            continue
        if left_team == right_team or evidence.dead[start:end].any():
            continue
        if not _has_anchor(result, evidence, start, end, context, left=True):
            continue
        if not _has_anchor(result, evidence, start, end, context, left=False):
            continue
        costs = _boundary_costs(evidence, left_team, start, end)
        optimal = np.flatnonzero(costs == costs.min()) + start
        right_onsets = np.flatnonzero(
            evidence.confirmed_control[start:end] == _team_code(right_team)
        )
        preferred = start + int(right_onsets[0]) if len(right_onsets) else end
        boundary = int(optimal[np.argmin(np.abs(optimal - preferred))])
        result[start:boundary] = left_team
        result[boundary:end] = right_team
        audits.append(
            {
                "operation": "resolve_turnover_gap",
                "start_frame": start,
                "end_frame_exclusive": end,
                "boundary_frame": boundary,
                "left_label": str(left_team),
                "right_label": str(right_team),
                "minimum_evidence_cost": float(costs.min()),
                "equally_supported_boundaries": len(optimal),
                "reason": "two_supported_endpoints_with_uncertain_transition_time",
            }
        )
    LOGGER.info("Resolved %d uncertain gaps between different teams", len(audits))
    return result, audits


def refine_turnover_boundaries(
    labels: NDArray[np.str_],
    evidence: FragmentationEvidence,
    fps: float,
    policy: FragmentationPolicy = FragmentationPolicy(),
) -> tuple[NDArray[np.str_], list[AuditRecord]]:
    """Move direct team transitions only for a strict observed support gain."""
    result = labels.copy()
    radius = floor(policy.boundary_search_seconds * fps)
    boundaries = np.flatnonzero(labels[1:] != labels[:-1]) + 1
    audits: list[AuditRecord] = []
    for old_boundary in boundaries:
        left_team = result[old_boundary - 1]
        right_team = result[old_boundary]
        if left_team not in ("H", "A") or right_team not in ("H", "A"):
            continue
        if left_team == right_team:
            continue
        run_start = _adjacent_run_start(result, old_boundary)
        run_end = _adjacent_run_end(result, old_boundary)
        low = max(run_start + 1, old_boundary - radius)
        high = min(run_end - 1, old_boundary + radius)
        support_low = max(run_start, low - 1)
        support_high = min(run_end, high + 1)
        if low >= high or evidence.dead[support_low:support_high].any():
            continue
        if not evidence.home_support[support_low:support_high].any():
            continue
        if not evidence.away_support[support_low:support_high].any():
            continue
        costs = _boundary_costs(evidence, left_team, low, high)
        original_cost = costs[old_boundary - low]
        minimum = costs.min()
        if minimum >= original_cost:
            continue
        optimal = np.flatnonzero(costs == minimum) + low
        boundary = int(optimal[np.argmin(np.abs(optimal - old_boundary))])
        if boundary < old_boundary:
            result[boundary:old_boundary] = right_team
        else:
            result[old_boundary:boundary] = left_team
        audits.append(
            {
                "operation": "refine_turnover_boundary",
                "previous_boundary_frame": int(old_boundary),
                "boundary_frame": boundary,
                "left_label": str(left_team),
                "right_label": str(right_team),
                "previous_evidence_cost": float(original_cost),
                "minimum_evidence_cost": float(minimum),
                "reason": "strict_sustained_observed_control_support_improvement",
            }
        )
    LOGGER.info("Refined %d direct turnover boundaries", len(audits))
    return result, audits
