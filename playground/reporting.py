"""Readable records of every predeclared experiment, including regressions."""

from pathlib import Path

from .experiment_spec import ExperimentSpec


def write_report(
    path: Path, summary: dict, experiments: tuple[ExperimentSpec, ...]
) -> None:
    evaluation = summary["evaluation"]
    lines = [
        "# Possession baseline experiments",
        "",
        "Each row changes one component relative to its named parent. The full "
        "sequence and fixed domain settings were written to `protocol.json`, "
        "and every submission was generated before any public labels were read.",
        "",
        "The unmodified step 05 pipeline independently verifies e00 frame for "
        "frame. Every experiment is scored by the unmodified step 06 pipeline.",
        "",
        f"Evaluation covers {evaluation['graded_frames']:,} labelled frames of "
        f"{evaluation['total_frames']:,} total. These are descriptive public-window "
        "results, not evidence of full-match generalization. No experiment was "
        "silently discarded, and the highest public score is not automatically "
        "promoted to a production model.",
        "",
        "| Experiment | Parent | Change | spellF1 | Δ parent | macroF1 | "
        "D recall | Predicted spells |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary["experiments"]:
        lines.append(
            f"| {row['experiment_id']} | {row['parent_id'] or '—'} | "
            f"{row['changed_component']} | {row['spell_f1']:.6f} | "
            f"{row['delta_spell_parent']:+.6f} | {row['macro_f1']:.6f} | "
            f"{row['dead_recall']:.3%} | {row['predicted_spells']} |"
        )
    for spec, row in zip(experiments, summary["experiments"], strict=True):
        lines.extend(
            [
                "",
                f"## {spec.id}: {spec.title}",
                "",
                f"**Parent:** {spec.parent_id or 'none; step 05 reference'}. "
                f"**Only changed component:** {spec.changed_component}.",
                "",
                f"**Hypothesis:** {spec.hypothesis}",
                "",
                f"**Method and rationale:** {spec.rationale}",
                "",
                f"**Result:** spellF1 {row['spell_f1']:.6f} "
                f"({row['delta_spell_parent']:+.6f} versus parent, "
                f"{row['delta_spell_baseline']:+.6f} versus baseline); "
                f"macroF1 {row['macro_f1']:.6f} "
                f"({row['delta_macro_parent']:+.6f} versus parent). "
                f"Dead-ball precision/recall: {row['dead_precision']:.3%} / "
                f"{row['dead_recall']:.3%}. One-second transition F1: "
                f"{row['transition_f1_1s']:.6f}.",
                "",
                f"**Prediction effect:** {row['changed_frames_full']:,} frames "
                f"changed across the recording, including "
                f"{row['changed_frames_graded']:,} graded frames. On graded frames "
                f"it corrects {row['corrected_parent_errors']:,} parent errors and "
                f"introduces {row['introduced_parent_errors']:,} errors. Predicted "
                f"possession spells: {row['predicted_spells']} versus "
                f"{row['true_spells']} reference spells; this count was never a "
                "target used by inference.",
                "",
                f"**Interpretation:** {_interpretation(row)}",
                "",
                f"Artifacts: `{spec.id}/possession.csv`, "
                f"`{spec.id}/possession.scores.json`, and "
                f"`{spec.id}/experiment.json`.",
            ]
        )
    lines.extend(
        [
            "",
            "## Limits and next checks",
            "",
            "The experiments form a predeclared cumulative chain: their effects "
            "are conditional on their parent, so a later regression does not "
            "prove that a component is useless in every combination. These "
            "heuristics have no training set or claimed calibrated confidence. "
            "They use automatic tracking and tags, both of which can be wrong.",
            "",
            "The public labels cover a small section of one match and are for "
            "correctness checks, not parameter selection. Stronger claims need "
            "evaluation on permitted labelled data from other games, with "
            "whole-match or contiguous-segment splits. More frames from the same "
            "possession are not independent validation examples.",
            "",
            "Rules: https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md",
            "Possession definition: https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/CHALLENGE.md",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _interpretation(row: dict) -> str:
    if not row["parent_id"]:
        return "Reference result; exact agreement with the existing step 05 baseline."
    spell, macro = row["delta_spell_parent"], row["delta_macro_parent"]
    if spell > 0 and macro >= 0:
        return (
            "Possession-interval matching improves on this window without a "
            "macroF1 decrease. This remains a descriptive observation."
        )
    if spell > 0:
        return (
            "Possession-interval matching improves, while frame-label macroF1 "
            "declines. The component makes a temporal/frame-level tradeoff."
        )
    if spell < 0:
        return (
            "Possession-interval matching regresses on this window. Retain this "
            "result as evidence of the component's limitations in this chain."
        )
    return (
        "No change in possession-interval F1 on this window. Consult changed-frame "
        "counts and macroF1 before interpreting this as identical predictions."
    )
