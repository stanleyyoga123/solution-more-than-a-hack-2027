"""Official step 06 scoring and paired comparisons, isolated from inference."""

from importlib import import_module
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .experiment_spec import ExperimentSpec


def score_experiments(
    directory: Path, ground_truth: Path, experiments: tuple[ExperimentSpec, ...]
) -> dict:
    """Score already-frozen predictions; no feedback reaches a predictor."""
    score = import_module("src.pipelines.06_score_submission").run_pipeline
    truth = pd.read_csv(ground_truth)
    graded = truth["label"].ne("X").to_numpy()
    labels = truth["label"].to_numpy()
    predictions = {}
    scores = {}
    comparisons = []
    for spec in experiments:
        folder = directory / spec.id
        submission = folder / "possession.csv"
        score_path = score(submission, ground_truth, folder)
        result = json.loads(score_path.read_text(encoding="utf-8"))
        predicted = pd.read_csv(submission)["label"].to_numpy()
        parent = predictions.get(spec.parent_id, predicted)
        parent_score = scores.get(spec.parent_id, result)
        baseline_score = scores.get(experiments[0].id, result)
        changed = predicted != parent
        before_correct = parent == labels
        after_correct = predicted == labels
        comparisons.append(
            {
                "experiment_id": spec.id,
                "parent_id": spec.parent_id,
                "title": spec.title,
                "changed_component": spec.changed_component,
                "spell_f1": result["spell_f1_mean"],
                "macro_f1": result["macro_f1"],
                "delta_spell_parent": (
                    result["spell_f1_mean"] - parent_score["spell_f1_mean"]
                ),
                "delta_macro_parent": result["macro_f1"] - parent_score["macro_f1"],
                "delta_spell_baseline": (
                    result["spell_f1_mean"] - baseline_score["spell_f1_mean"]
                ),
                "delta_macro_baseline": (
                    result["macro_f1"] - baseline_score["macro_f1"]
                ),
                "dead_recall": result["per_class"]["D"]["recall"],
                "dead_precision": result["per_class"]["D"]["precision"],
                "transition_f1_1s": result["transitions"]["25"]["f1"],
                "predicted_spells": result["n_pred_spells"],
                "true_spells": result["n_gt_spells"],
                "changed_frames_full": int(changed.sum()),
                "changed_frames_graded": int((changed & graded).sum()),
                "corrected_parent_errors": int(
                    (graded & ~before_correct & after_correct).sum()
                ),
                "introduced_parent_errors": int(
                    (graded & before_correct & ~after_correct).sum()
                ),
                "label_counts_full": {
                    label: int(np.sum(predicted == label)) for label in ("H", "A", "D")
                },
            }
        )
        predictions[spec.id] = predicted
        scores[spec.id] = result
    return {
        "evaluation": {
            "ground_truth": str(ground_truth),
            "ground_truth_sha256": hashlib.sha256(
                ground_truth.read_bytes()
            ).hexdigest(),
            "total_frames": len(truth),
            "graded_frames": int(graded.sum()),
            "graded_start_frame": int(truth.loc[graded, "frame"].min()),
            "graded_end_frame": int(truth.loc[graded, "frame"].max()),
            "score_entrypoint": "src.pipelines.06_score_submission.run_pipeline",
            "interpretation": (
                "Descriptive results on the supplied public correctness check. "
                "No fitted thresholds, model training, automatic selection, or "
                "later inference changes depend on these labels or scores."
            ),
        },
        "experiments": comparisons,
    }
