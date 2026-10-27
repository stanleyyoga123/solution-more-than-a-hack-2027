# Recorded possession experiments

The first batch ran all nine predeclared variants on the full 199,319-frame
recording and scored them with step 06. The public labels cover 7,500 frames
(five minutes), with 17 possessions. All eight changes were fixed before this
batch's scores were available; no parameter sweep or score-driven retry was used.

The highest observed public spellF1 was **e05_control_confirmation**:

| Metric | Step 05 reference | e05 | Difference |
| --- | ---: | ---: | ---: |
| spellF1 | 0.325581 | 0.422857 | +0.097276 (+29.88% relative) |
| macroF1 | 0.620733 | 0.680016 | +0.059283 |
| Predicted possessions | 26 | 18 | -8 |
| Dead-ball recall | 21.38% | 34.85% | +13.48 percentage points |

This is the best result **within the fixed batch on the public window**. It is
not a validated full-match improvement or an automatic production recommendation.
The final experiment is deliberately retained even though it scores worse.

## What the changes taught us

- **Counting D votes helped.** e01 increased both headline metrics. It corrected
  195 parent errors and introduced 129 on labelled frames, showing a real tradeoff
  rather than uniformly better predictions. These D inputs still represent
  missing nearest-team evidence; they are not reliable stoppage observations.
- **Short same-team bridging had little effect here.** e02 changed two labelled
  frames, both correctly, without changing spellF1. It changed 33 frames overall.
- **Boundary evidence helped dead-ball recognition.** e03 changed 99 labelled
  frames, correcting 98 existing errors and introducing no new ones. Dead recall
  rose to 41.32%. The spellF1 gain was small, so frame-level benefits did not
  translate proportionately into better possession intervals.
- **Stationarity had no measured public-window effect.** e04 changed 2,625 frames
  elsewhere in the recording but none in the labelled interval. This experiment
  cannot establish whether those changes are useful.
- **Control confirmation improved possession intervals.** e05 reduced predicted
  possessions from 25 to 18 and increased spellF1 by 0.051429 versus its parent.
  MacroF1 fell slightly versus e04 (0.000719), and dead-ball recall declined. The
  interval gain comes with a frame-level tradeoff; it is not an improvement in
  every metric.
- **Our phase-tag fusion regressed.** e06 corrected 453 parent errors but
  introduced 919, reducing both headline scores. It produced only 12 possessions.
  A plausible failure mechanism is treating broad phase evidence as sufficient
  confirmation and retaining the wrong team too long. This is an interpretation
  of this implementation, not proof that automatic tagging is generally useless.
- **Motion filtering had no measured public-window effect.** e07 changed 207
  unlabelled frames. This window does not test its usefulness adequately.
- **Removing the final vote regressed in this chain.** e08 increased predicted
  possessions from 12 to 33 and lowered both scores. This supports retaining
  smoothing for this particular stateful/tag-fusion configuration, not a universal
  claim that all stateful decoders need the same smoothing window.

## Reproduction and limitations

Run the command in [README.md](README.md) with a new output directory. The initial
batch is in `artifacts/run_001/`; frame-level outputs are intentionally ignored by
Git. The retained aggregate results below come directly from its step 06 reports.

A final run in `artifacts/run_002/` reproduced all nine submissions and all nine
official score JSON files **byte for byte**. Its protocol records input hashes,
experiment-source hashes, and the source hashes of steps 05/06 and the official
metric implementation. The second run took 19.22 seconds on the development
machine. It is a reproducibility check, not an additional model-selection round.

Verification completed:

- 24 playground tests passed, including prediction independence from ground truth,
  exact baseline parity, every rule's synthetic behavior, and output safety.
- 121 tests passed when combined with the maintained pipeline/export/logging suite.
- Black passed for all 22 playground Python files; `git diff --check` passed.
- Independent correctness and style reviews found no required fixes.

```bash
.venv/bin/python -m pytest playground/tests tests/src/pipelines \
  tests/src/utilities/test_pipeline_exports.py \
  tests/src/utilities/test_pipeline_logging.py -q
.venv/bin/python -m black --check playground
```

There is no hand annotation, identity correction, public-label training, or
frame-specific rule in these experiments. The public labels were inspected in
prior work to understand the baseline's failure modes, so this is not a blind
holdout study. Inference has no label input, and tests verify that changing ground
truth changes evaluation without changing predictions.

These experiments are cumulative. A later result is conditional on its named
parent; it does not isolate the component in every possible combination. Future
parameter selection or claims of generalization should use permitted data from
other games and keep whole possessions or contiguous segments together.


Each row changes one component relative to its named parent. The full sequence and fixed domain settings were written to `protocol.json`, and every submission was generated before any public labels were read.

The unmodified step 05 pipeline independently verifies e00 frame for frame. Every experiment is scored by the unmodified step 06 pipeline.

Evaluation covers 7,500 labelled frames of 199,319 total. These are descriptive public-window results, not evidence of full-match generalization. No experiment was silently discarded, and the highest public score is not automatically promoted to a production model.

| Experiment | Parent | Change | spellF1 | Δ parent | macroF1 | D recall | Predicted spells |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| e00_baseline | — | reference | 0.325581 | +0.000000 | 0.620733 | 21.375% | 26 |
| e01_three_class_vote | e00_baseline | three_class_vote | 0.370732 | +0.045150 | 0.656359 | 34.649% | 24 |
| e02_bounded_missing_bridge | e01_three_class_vote | bounded_gap_fill | 0.370732 | +0.000000 | 0.656562 | 34.649% | 24 |
| e03_pitch_boundary | e02_bounded_missing_bridge | boundary_dead | 0.371429 | +0.000697 | 0.680735 | 41.321% | 25 |
| e04_stationary_restart | e03_pitch_boundary | stationary_dead | 0.371429 | +0.000000 | 0.680735 | 41.321% | 25 |
| e05_control_confirmation | e04_stationary_restart | control_confirmation | 0.422857 | +0.051429 | 0.680016 | 34.854% | 18 |
| e06_automatic_phase_evidence | e05_control_confirmation | tag_evidence | 0.303448 | -0.119409 | 0.563121 | 12.049% | 12 |
| e07_motion_quality | e06_automatic_phase_evidence | quality_filter | 0.303448 | +0.000000 | 0.563121 | 12.049% | 12 |
| e08_no_final_vote | e07_motion_quality | smoothing_window_frames | 0.208000 | -0.095448 | 0.550204 | 11.981% | 33 |

## e00_baseline: Step 05 baseline reproduction

**Parent:** none; step 05 reference. **Only changed component:** reference.

**Hypothesis:** Reproduce step 05 exactly before evaluating any change.

**Method and rationale:** Use the same nearest-player team and centred +/-50-frame vote; dead-ball observations do not vote for either team.

**Result:** spellF1 0.325581 (+0.000000 versus parent, +0.000000 versus baseline); macroF1 0.620733 (+0.000000 versus parent). Dead-ball precision/recall: 65.690% / 21.375%. One-second transition F1: 0.081633.

**Prediction effect:** 0 frames changed across the recording, including 0 graded frames. On graded frames it corrects 0 parent errors and introduces 0 errors. Predicted possession spells: 26 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Reference result; exact agreement with the existing step 05 baseline.

Artifacts: `e00_baseline/possession.csv`, `e00_baseline/possession.scores.json`, and `e00_baseline/experiment.json`.

## e01_three_class_vote: Allow dead-ball observations to vote

**Parent:** e00_baseline. **Only changed component:** three_class_vote.

**Hypothesis:** Counting D votes may preserve stoppages erased by team-only voting.

**Method and rationale:** Use all three classes with deterministic H, A, D tie precedence.

**Result:** spellF1 0.370732 (+0.045150 versus parent, +0.045150 versus baseline); macroF1 0.656359 (+0.035626 versus parent). Dead-ball precision/recall: 55.386% / 34.649%. One-second transition F1: 0.250000.

**Prediction effect:** 15,692 frames changed across the recording, including 441 graded frames. On graded frames it corrects 195 parent errors and introduces 129 errors. Predicted possession spells: 24 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Possession-interval matching improves on this window without a macroF1 decrease. This remains a descriptive observation.

Artifacts: `e01_three_class_vote/possession.csv`, `e01_three_class_vote/possession.scores.json`, and `e01_three_class_vote/experiment.json`.

## e02_bounded_missing_bridge: Bridge short same-team observation gaps

**Parent:** e01_three_class_vote. **Only changed component:** bounded_gap_fill.

**Hypothesis:** A brief missing observation need not interrupt team possession.

**Method and rationale:** Bridge at most two seconds only when both observed endpoint teams agree; never extrapolate at the recording boundaries.

**Result:** spellF1 0.370732 (+0.000000 versus parent, +0.045150 versus baseline); macroF1 0.656562 (+0.000203 versus parent). Dead-ball precision/recall: 55.386% / 34.649%. One-second transition F1: 0.250000.

**Prediction effect:** 33 frames changed across the recording, including 2 graded frames. On graded frames it corrects 2 parent errors and introduces 0 errors. Predicted possession spells: 24 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** No change in possession-interval F1 on this window. Consult changed-frame counts and macroF1 before interpreting this as identical predictions.

Artifacts: `e02_bounded_missing_bridge/possession.csv`, `e02_bounded_missing_bridge/possession.scores.json`, and `e02_bounded_missing_bridge/experiment.json`.

## e03_pitch_boundary: Detect sustained out-of-pitch ball observations

**Parent:** e02_bounded_missing_bridge. **Only changed component:** boundary_dead.

**Hypothesis:** A reliably observed ball beyond the field supports a stoppage.

**Method and rationale:** Require a 0.25-metre margin outside the pitch for at least 0.2 seconds; apply the dead-ball evidence after temporal voting.

**Result:** spellF1 0.371429 (+0.000697 versus parent, +0.045847 versus baseline); macroF1 0.680735 (+0.024173 versus parent). Dead-ball precision/recall: 59.627% / 41.321%. One-second transition F1: 0.280000.

**Prediction effect:** 4,486 frames changed across the recording, including 99 graded frames. On graded frames it corrects 98 parent errors and introduces 0 errors. Predicted possession spells: 25 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Possession-interval matching improves on this window without a macroF1 decrease. This remains a descriptive observation.

Artifacts: `e03_pitch_boundary/possession.csv`, `e03_pitch_boundary/possession.scores.json`, and `e03_pitch_boundary/experiment.json`.

## e04_stationary_restart: Combine stationary-ball and stoppage context

**Parent:** e03_pitch_boundary. **Only changed component:** stationary_dead.

**Hypothesis:** Stationary balls with supporting context can expose missed stoppages.

**Method and rationale:** Require low ball displacement and speed, plus slow collective movement, a nearby boundary, or automatic restart evidence; persist for one second.

**Result:** spellF1 0.371429 (+0.000000 versus parent, +0.045847 versus baseline); macroF1 0.680735 (+0.000000 versus parent). Dead-ball precision/recall: 59.627% / 41.321%. One-second transition F1: 0.280000.

**Prediction effect:** 2,625 frames changed across the recording, including 0 graded frames. On graded frames it corrects 0 parent errors and introduces 0 errors. Predicted possession spells: 25 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** No change in possession-interval F1 on this window. Consult changed-frame counts and macroF1 before interpreting this as identical predictions.

Artifacts: `e04_stationary_restart/possession.csv`, `e04_stationary_restart/possession.scores.json`, and `e04_stationary_restart/experiment.json`.

## e05_control_confirmation: Require sustained control to switch teams

**Parent:** e04_stationary_restart. **Only changed component:** control_confirmation.

**Hypothesis:** Possession should persist through passes and contested loose balls.

**Method and rationale:** Require a close player, a distance advantage and a ball-speed bound for 0.4 seconds. Backdate confirmed switches to their first supporting frame.

**Result:** spellF1 0.422857 (+0.051429 versus parent, +0.097276 versus baseline); macroF1 0.680016 (-0.000719 versus parent). Dead-ball precision/recall: 65.725% / 34.854%. One-second transition F1: 0.232558.

**Prediction effect:** 25,256 frames changed across the recording, including 870 graded frames. On graded frames it corrects 350 parent errors and introduces 271 errors. Predicted possession spells: 18 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Possession-interval matching improves, while frame-label macroF1 declines. The component makes a temporal/frame-level tradeoff.

Artifacts: `e05_control_confirmation/possession.csv`, `e05_control_confirmation/possession.scores.json`, and `e05_control_confirmation/experiment.json`.

## e06_automatic_phase_evidence: Support uncertain control with automatic phase tags

**Parent:** e05_control_confirmation. **Only changed component:** tag_evidence.

**Hypothesis:** Automatic tactical phases may supply evidence during uncertain tracking.

**Method and rationale:** Use a strictly larger positive phase vote only where geometric control is uncertain, with the same temporal confirmation as observed control.

**Result:** spellF1 0.303448 (-0.119409 versus parent, -0.022133 versus baseline); macroF1 0.563121 (-0.116895 versus parent). Dead-ball precision/recall: 68.077% / 12.049%. One-second transition F1: 0.176471.

**Prediction effect:** 49,466 frames changed across the recording, including 1,788 graded frames. On graded frames it corrects 453 parent errors and introduces 919 errors. Predicted possession spells: 12 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Possession-interval matching regresses on this window. Retain this result as evidence of the component's limitations in this chain.

Artifacts: `e06_automatic_phase_evidence/possession.csv`, `e06_automatic_phase_evidence/possession.scores.json`, and `e06_automatic_phase_evidence/experiment.json`.

## e07_motion_quality: Exclude impossible motion from control evidence

**Parent:** e06_automatic_phase_evidence. **Only changed component:** quality_filter.

**Hypothesis:** Motion glitches should contribute less evidence for a team change.

**Method and rationale:** Exclude player steps over 12 m/s and ball steps over 45 m/s using consecutive observations; retain the other settings.

**Result:** spellF1 0.303448 (+0.000000 versus parent, -0.022133 versus baseline); macroF1 0.563121 (+0.000000 versus parent). Dead-ball precision/recall: 68.077% / 12.049%. One-second transition F1: 0.176471.

**Prediction effect:** 207 frames changed across the recording, including 0 graded frames. On graded frames it corrects 0 parent errors and introduces 0 errors. Predicted possession spells: 12 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** No change in possession-interval F1 on this window. Consult changed-frame counts and macroF1 before interpreting this as identical predictions.

Artifacts: `e07_motion_quality/possession.csv`, `e07_motion_quality/possession.scores.json`, and `e07_motion_quality/experiment.json`.

## e08_no_final_vote: Remove the final fixed-window vote

**Parent:** e07_motion_quality. **Only changed component:** smoothing_window_frames.

**Hypothesis:** Stateful confirmation may preserve boundaries without a final vote.

**Method and rationale:** Set only the final smoothing half-window from 50 frames to zero.

**Result:** spellF1 0.208000 (-0.095448 versus parent, -0.117581 versus baseline); macroF1 0.550204 (-0.012917 versus parent). Dead-ball precision/recall: 67.954% / 11.981%. One-second transition F1: 0.109091.

**Prediction effect:** 5,480 frames changed across the recording, including 371 graded frames. On graded frames it corrects 123 parent errors and introduces 247 errors. Predicted possession spells: 33 versus 17 reference spells; this count was never a target used by inference.

**Interpretation:** Possession-interval matching regresses on this window. Retain this result as evidence of the component's limitations in this chain.

Artifacts: `e08_no_final_vote/possession.csv`, `e08_no_final_vote/possession.scores.json`, and `e08_no_final_vote/experiment.json`.

## Limits and next checks

The experiments form a predeclared cumulative chain: their effects are conditional on their parent, so a later regression does not prove that a component is useless in every combination. These heuristics have no training set or claimed calibrated confidence. They use automatic tracking and tags, both of which can be wrong.

The public labels cover a small section of one match and are for correctness checks, not parameter selection. Stronger claims need evaluation on permitted labelled data from other games, with whole-match or contiguous-segment splits. More frames from the same possession are not independent validation examples.

Rules: https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md
Possession definition: https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/CHALLENGE.md
