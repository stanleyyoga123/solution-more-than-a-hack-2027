"""Write per-experiment evidence and official restart comparison results."""

from pathlib import Path

from .specs import RestartSpec


def write_report(path: Path, summary: dict, specs: tuple[RestartSpec, ...]) -> None:
    anchor = summary["experiments"][1]
    lines = [
        "# Smart Tagging restart experiments",
        "",
        "The graph and numerical settings were fixed before this batch's scores. "
        "All submissions were frozen before step 06 read possession labels. "
        "s00 and s01 are reference anchors; subsequent branches each change one "
        "component relative to their named parent.",
        "",
        "| Experiment | Parent | spellF1 | Δ s01 | macroF1 | D precision | D recall |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or 'none'} | "
            f"{row['spell_f1']:.6f} | "
            f"{row['spell_f1'] - anchor['spell_f1']:+.6f} | "
            f"{row['macro_f1']:.6f} | {row['dead_precision']:.2%} | "
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
                f"macroF1 {row['macro_f1']:.6f} "
                f"({row['delta_macro_parent']:+.6f}). "
                f"Changed {row['changed_frames_full']:,} full-recording labels "
                f"and {row['changed_frames_graded']:,} graded labels. "
                f"Corrected {row['corrected_parent_errors']:,} parent errors and "
                f"introduced {row['introduced_parent_errors']:,} errors. "
                f"Predicted {row['predicted_spells']} possessions versus "
                f"{row['true_spells']} reference possessions.",
            ]
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "Automatic Smart Tags are event context, not verified stoppage "
            "boundaries. Missing ball observations do not prove dead play. "
            "Geometry and speed settings are fixed engineering hypotheses; "
            "no threshold sweep or possession-label training was performed.",
            "",
            "Only the public five-minute window is labelled for evaluation. "
            "Earlier results informed these hypotheses, so this is exploratory "
            "comparison rather than a fresh holdout. Full-match changes remain "
            "unverified, and no candidate is automatically deployed.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
