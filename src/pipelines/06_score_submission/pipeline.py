"""Validate a frame,label submission and score it with the official metrics."""

import json
import logging
from pathlib import Path
from time import perf_counter

from src.utilities import possession_metrics as metrics

LOGGER = logging.getLogger(__name__)


def run_pipeline(submission: Path, ground_truth: Path, output_dir: Path) -> Path:
    """Write every official metric for one submission as JSON and log the headline."""
    started = perf_counter()
    LOGGER.info("Starting 06_score_submission; ground truth: %s", ground_truth)
    truth = metrics.label_codes(metrics.read_label_csv(ground_truth))
    LOGGER.info("Reading submission: %s", submission)
    table = metrics.read_label_csv(submission)
    reason = metrics.validate_submission(table, len(truth))
    if reason:
        raise ValueError(f"{submission} is not a valid submission: {reason}")
    result = metrics.evaluate(truth, metrics.label_codes(table))

    LOGGER.info(
        "spellF1 %.4f, macroF1 %.4f, %d predicted vs %d true possessions",
        result["spell_f1_mean"],
        result["macro_f1"],
        result["n_pred_spells"],
        result["n_gt_spells"],
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{submission.stem}.scores.json"
    # The official metrics return some numpy scalars, which json cannot encode.
    document = json.dumps(result, indent=2, default=lambda value: value.item())
    # Mode "x" refuses an existing report; the JSON is complete before opening it.
    with path.open("x", encoding="utf-8") as destination:
        destination.write(document + "\n")
    LOGGER.info(
        "Completed 06_score_submission in %.2f seconds; output: %s",
        perf_counter() - started,
        path,
    )
    return path
