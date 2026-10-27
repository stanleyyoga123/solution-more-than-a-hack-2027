"""Report the post-gap quarantine comparisons without hiding regressions."""

from pathlib import Path

from .specs import ReacquisitionSpec


def write_report(
    path: Path, summary: dict, specs: tuple[ReacquisitionSpec, ...]
) -> None:
    lines = [
        "# Post-gap player reacquisition experiments",
        "",
        "These hypotheses follow a traced identity discontinuity. No player ID, "
        "target frame, or possession label enters inference. All six predictions "
        "were frozen before new scores; this remains exploratory "
        "public-window debugging.",
        "",
        "| Experiment | Parent | spellF1 | macroF1 | Spells | D recall |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or 'none'} | "
            f"{row['spell_f1']:.6f} | {row['macro_f1']:.6f} | "
            f"{row['predicted_spells']} | {row['dead_recall']:.2%} |"
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
                f"{row['changed_frames_full']} full-recording and "
                f"{row['changed_frames_graded']} graded labels. Corrected "
                f"{row['corrected_parent_errors']} parent errors; introduced "
                f"{row['introduced_parent_errors']} errors.",
            ]
        )
        for interval in row["review_ranges"]:
            lines.extend(
                [
                    "",
                    f"**Review [{interval['start_frame']}, "
                    f"{interval['end_frame_exclusive']}):** "
                    f"{interval['wrong_frames']}/{interval['graded_frames']} graded "
                    f"frames wrong (f03: {interval['anchor_wrong_frames']}).",
                ]
            )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            "The entire selected segment is quarantined after an impossible "
            "reappearance: an observed run by default, or a physically continuous "
            "tracklet with splitting enabled. A wrong old anchor can discard "
            "a valid new segment, "
            "and real identity swaps with physically plausible displacement remain "
            "undetected. No coordinates or team identities are imputed or overwritten. "
            "Collective stoppage rules remain hypotheses. The same public window "
            "motivated and evaluates this debugging work; full-match reliability "
            "requires independent evidence. No candidate is automatically promoted.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
