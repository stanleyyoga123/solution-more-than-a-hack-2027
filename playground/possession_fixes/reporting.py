"""Record global scores alongside known-error diagnostics without selecting models."""

from pathlib import Path

from .specs import FixSpec


def write_report(path: Path, summary: dict, specs: tuple[FixSpec, ...]) -> None:
    anchor = summary["experiments"][2]
    lines = [
        "# Physical-control and collective-stoppage fixes",
        "",
        "Known public errors motivated this batch. All settings and comparisons "
        "were fixed before new scores; all submissions were frozen before GT "
        "was read. Review ranges never enter inference.",
        "",
        "| Experiment | Parent | spellF1 | Δ f03 | macroF1 | Spells | D recall |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or 'none'} | "
            f"{row['spell_f1']:.6f} | "
            f"{row['spell_f1'] - anchor['spell_f1']:+.6f} | "
            f"{row['macro_f1']:.6f} | {row['predicted_spells']} | "
            f"{row['dead_recall']:.2%} |"
        )
    for spec, row in zip(specs, summary["experiments"], strict=True):
        lines.extend(
            [
                "",
                f"## {spec.id}: {spec.title}",
                "",
                f"**Parent:** {spec.parent_id or 'none'}. "
                f"**Change:** {spec.changed_component}.",
                "",
                f"**Hypothesis:** {spec.hypothesis}",
                "",
                f"**Method:** {spec.rationale}",
                "",
                f"**Result:** spellF1 {row['spell_f1']:.6f} "
                f"({row['delta_spell_parent']:+.6f} versus parent), "
                f"macroF1 {row['macro_f1']:.6f}. Changed "
                f"{row['changed_frames_full']:,} full-recording labels and "
                f"{row['changed_frames_graded']:,} graded labels. Corrected "
                f"{row['corrected_parent_errors']} parent errors and introduced "
                f"{row['introduced_parent_errors']} graded errors.",
                "",
                f"**Structure:** {row['predicted_spells']} predicted versus "
                f"{row['true_spells']} true possessions, "
                f"{row['split_truth_spells']} split true spells and "
                f"{row['merged_prediction_spells']} merged predictions "
                "under positive same-team overlap diagnostics.",
            ]
        )
        for interval in row["review_ranges"]:
            lines.extend(
                [
                    "",
                    f"**Review [{interval['start_frame']}, "
                    f"{interval['end_frame_exclusive']}):** "
                    f"{interval['wrong_frames']}/{interval['graded_frames']} "
                    f"graded frames wrong (f03: {interval['anchor_wrong_frames']}). "
                    f"Corrected {interval['corrected_anchor_errors']} f03 errors; "
                    f"introduced {interval['introduced_anchor_errors']} errors.",
                ]
            )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "These are exploratory results on the repeatedly inspected public "
            "five-minute window, not an independent holdout. Physical proximity "
            "does not prove control, and collective slowdown does not prove a "
            "foul. A target-clip improvement can coincide with a worse global "
            "score. Full-match changes remain unverified. No candidate is "
            "automatically promoted and the viewer default is preserved.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
