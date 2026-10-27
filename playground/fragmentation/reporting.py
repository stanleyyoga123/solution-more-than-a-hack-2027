"""Record every fixed fragmentation comparison, including negative results."""

from pathlib import Path

from .specs import FragmentationSpec


def write_report(
    path: Path, summary: dict, specs: tuple[FragmentationSpec, ...]
) -> None:
    anchor = summary["experiments"][1]
    lines = [
        "# Uncertainty and fragmentation experiments",
        "",
        "All predictions were frozen before step 06 scoring. f00/f01 are "
        "references, f02 is an identity control, and later variants change "
        "one component from their named parent. Unresolved internal U exports as D.",
        "",
        "| Experiment | Parent | spellF1 | Δ r06 | macroF1 | Spells | Splits | Merges |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or 'none'} | "
            f"{row['spell_f1']:.6f} | "
            f"{row['spell_f1'] - anchor['spell_f1']:+.6f} | "
            f"{row['macro_f1']:.6f} | {row['predicted_spells']} | "
            f"{row['split_truth_spells']} | {row['merged_prediction_spells']} |"
        )
    lines.extend(
        [
            "",
            "Splits count true possessions overlapping more than one same-team "
            "prediction. Merges count predictions overlapping more than one "
            "same-team true possession. Any positive overlap counts; these are "
            "structural diagnostics, not independently adjudicated error causes.",
        ]
    )
    for spec, row in zip(specs, summary["experiments"], strict=True):
        latency = row["mean_abs_boundary_error_s"]
        timing = "unavailable" if latency is None else f"{latency:.3f} s"
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
                f"Changed {row['changed_frames_full']:,} full-match labels and "
                f"{row['changed_frames_graded']:,} graded labels. "
                f"Corrected {row['corrected_parent_errors']} parent errors and "
                f"introduced {row['introduced_parent_errors']} errors.",
                "",
                f"**Intervals:** {row['predicted_spells']} predictions versus "
                f"{row['true_spells']} true possessions; "
                f"{row['split_truth_spells']} split true spells, "
                f"{row['merged_prediction_spells']} merged predicted spells. "
                f"Matched {row['matched_boundaries_1s']} boundaries within 1 s "
                f"with matching origin and destination; conditional mean "
                f"absolute timing error {timing}. "
                f"Missed {row['missed_boundaries_1s']} boundaries and produced "
                f"{row['spurious_boundaries_1s']} spurious boundaries.",
            ]
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "This reuses the public five-minute correctness window, not a new "
            "holdout. Thresholds are fixed engineering hypotheses and no tuning "
            "or fitting uses possession labels. Full-match changes are unverified. "
            "Uncertainty is not evidence of live play, and physical dead-ball "
            "cues can also be wrong. Boundary timing is conditional on matched "
            "boundaries and must be read with missed/spurious counts. "
            "The runner does not promote a candidate or overwrite the viewer input.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
