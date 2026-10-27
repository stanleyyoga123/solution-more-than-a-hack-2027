"""Publish every fixed hypothesis and its paired official evaluation."""

from pathlib import Path

from .specs import RefinementSpec


def write_report(
    path: Path, summary: dict, experiments: tuple[RefinementSpec, ...]
) -> None:
    anchor = summary["experiments"][1]
    lines = [
        "# Interception refinement experiments",
        "",
        "r00 reproduces step 05; r01 reproduces the earlier c05 interception model. "
        "Each subsequent experiment changes one component relative to its named "
        "parent. All variants and predictions are frozen before scoring with step 06.",
        "",
        "| Experiment | Parent | spellF1 | Δ r01 | macroF1 | D recall |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or 'none'} | "
            f"{row['spell_f1']:.6f} | "
            f"{row['spell_f1'] - anchor['spell_f1']:+.6f} | "
            f"{row['macro_f1']:.6f} | {row['dead_recall']:.2%} |"
        )
    for spec, row in zip(experiments, summary["experiments"], strict=True):
        lines.extend(
            [
                "",
                f"## {spec.id}: {spec.title}",
                "",
                f"**Parent:** {spec.parent_id or 'none'}. "
                f"**Changed component:** {spec.changed_component}.",
                "",
                f"**Hypothesis:** {spec.hypothesis}",
                "",
                f"**Method:** {spec.rationale}",
                "",
                f"**Results:** spellF1 {row['spell_f1']:.6f} "
                f"({row['delta_spell_parent']:+.6f} against parent); "
                f"macroF1 {row['macro_f1']:.6f} "
                f"({row['delta_macro_parent']:+.6f}). "
                f"Changed {row['changed_frames_full']:,} full-recording frames, "
                f"including {row['changed_frames_graded']:,} graded frames. "
                f"Corrected {row['corrected_parent_errors']:,} parent errors and "
                f"introduced {row['introduced_parent_errors']:,} errors. "
                f"Predicted {row['predicted_spells']} possessions versus "
                f"{row['true_spells']} reference possessions.",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "These are descriptive results on the same five-minute public "
            "correctness window used earlier. Prior scores informed the choice "
            "of the reference and hypotheses, so this is not an untouched "
            "holdout. No possession labels train a model or tune a threshold "
            "within this batch, and no winner is automatically deployed.",
            "",
            "Motion and reachability settings are physical hypotheses, not "
            "calibrated player capabilities. Offline smoothing, gap bridging "
            "and confirmation backdating mean the full predictor is not a "
            "real-time system, even when its velocity estimator is causal. "
            "Missing-ball continuity can hide a true stoppage; forecast positions "
            "are estimates rather than new observations.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
