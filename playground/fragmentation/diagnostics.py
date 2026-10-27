"""Evaluation-only split, merge and boundary diagnostics."""

import numpy as np
from numpy.typing import NDArray

from src.utilities import possession_metrics as metrics


def fragmentation_diagnostics(
    truth: NDArray[np.str_], predicted: NDArray[np.str_], fps: float
) -> dict:
    """Count positive same-team overlaps within labelled runs, never across X.

    Split/merge counts describe overlap topology, not adjudicated error causes.
    Even a one-frame overlap counts; no threshold is fitted to public labels.
    """
    gt = metrics.label_codes(truth)
    pred = metrics.label_codes(predicted)
    runs = metrics.valid_runs(gt)
    pred = metrics.fill_abstentions(pred, runs)
    gt_spells = metrics.possession_spells(gt, runs)
    pred_spells = metrics.possession_spells(pred, runs)
    overlaps = metrics.spell_overlaps(gt_spells, pred_spells)
    gt_degree = np.zeros(len(gt_spells), dtype=int)
    pred_degree = np.zeros(len(pred_spells), dtype=int)
    for _, gt_index, pred_index in overlaps:
        gt_degree[gt_index] += 1
        pred_degree[pred_index] += 1

    matched = []
    missed = []
    spurious = []
    # Match each labelled run separately, including short synthetic X gaps.
    for run in runs:
        pairs, missing, extra = metrics.match_transitions(
            metrics.transitions(gt, [run]),
            metrics.transitions(pred, [run]),
            round(fps),
            typed="pair",
        )
        matched.extend(pairs)
        missed.extend(missing)
        spurious.extend(extra)
    offsets = np.array([p[0] - g[0] for g, p in matched], dtype=float) / fps
    return {
        "split_truth_spells": int((gt_degree > 1).sum()),
        "extra_same_team_fragments": int(np.maximum(gt_degree - 1, 0).sum()),
        "merged_prediction_spells": int((pred_degree > 1).sum()),
        "extra_truth_spells_merged": int(np.maximum(pred_degree - 1, 0).sum()),
        "uncovered_truth_spells": int((gt_degree == 0).sum()),
        "nonoverlapping_prediction_spells": int((pred_degree == 0).sum()),
        "matched_boundaries_1s": len(matched),
        "missed_boundaries_1s": len(missed),
        "spurious_boundaries_1s": len(spurious),
        "mean_abs_boundary_error_s": (
            float(np.abs(offsets).mean()) if len(offsets) else None
        ),
        "mean_signed_boundary_error_s": (
            float(offsets.mean()) if len(offsets) else None
        ),
        "boundary_matching": "Same origin and destination, one-to-one within 1s",
        "overlap_definition": "Any positive same-team overlap within graded runs",
    }
