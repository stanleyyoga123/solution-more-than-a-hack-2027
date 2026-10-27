"""Write branch-by-branch results for the alternative possession approaches."""

import json
from pathlib import Path

from .specs import CreativeSpec


def write_creative_report(
    path: Path,
    summary: dict,
    experiments: tuple[CreativeSpec, ...],
    diagnostics: dict[str, dict],
) -> None:
    lines = [
        "# Creative possession experiments",
        "",
        "c00 is the original step 05 baseline. c01 reproduces the earlier e05 "
        "control-confirmation reference. Every new method branches independently "
        "from c01, replacing one input-recovery or inference component. c01 is a "
        "reference anchor, not a new one-component change from c00.",
        "",
        "All configurations and predictions were fixed before reading possession "
        "labels. The collective model trains on original ball coordinates, not "
        "possession labels. All submissions use the existing step 06 scorer.",
        "",
        "| Experiment | Change | spellF1 | Δ c01 | macroF1 | D recall | "
        "Predicted possessions |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    anchor = summary["experiments"][1]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['changed_component']} | "
            f"{row['spell_f1']:.6f} | "
            f"{row['spell_f1'] - anchor['spell_f1']:+.6f} | "
            f"{row['macro_f1']:.6f} | {row['dead_recall']:.2%} | "
            f"{row['predicted_spells']} |"
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
                f"**Results:** spellF1 {row['spell_f1']:.6f}; "
                f"macroF1 {row['macro_f1']:.6f}; "
                f"{row['changed_frames_full']:,} predictions changed versus parent "
                f"({row['changed_frames_graded']:,} on graded frames). "
                f"Corrected {row['corrected_parent_errors']:,} parent errors and "
                f"introduced {row['introduced_parent_errors']:,} errors.",
                "",
                "**Independent coverage / spatial diagnostics:**",
                "",
                "```json",
                json.dumps(diagnostics[spec.id], indent=2, allow_nan=False),
                "```",
            ]
        )
    lines.extend(
        [
            "",
            "## Interpretation limits",
            "",
            "The public labels cover only five minutes of one match. Results "
            "are descriptive; no model is automatically promoted and no settings "
            "are optimized against these scores. The earlier public results were "
            "already known when choosing c01 as the reference, so this is not a "
            "blind holdout study.",
            "",
            "Spatial checks compare with the supplied automatic ball track, not "
            "verified video truth. Better reconstruction and better possession "
            "labels are different objectives. Forecasts cannot identify unobserved "
            "kicks; team shape need not determine ball location; generic sports-ball "
            "detections can be false positives and pitch projection assumes a "
            "ground-level ball. Missingness is not random, so errors on visible "
            "control frames may understate errors during actual occlusions.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
