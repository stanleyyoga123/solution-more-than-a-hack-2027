# Interception refinement results

This third batch executed 13 fixed variants over all 199,319 frames: two reference
anchors and eleven single-component comparisons, including predeclared
combinations. It used the original tracking and the unmodified step 06 scorer.
The previous c05 submission and score JSON were reproduced byte-for-byte.

## Main findings

| Candidate | spellF1 | macroF1 |
| --- | ---: | ---: |
| Original step 05 | 0.325581 | 0.620733 |
| Previous c05 interception | 0.482353 | 0.690217 |
| **r06: interception + occlusion continuity** | **0.533333** | 0.702218 |
| r12: forecasting + robust motion + boundary persistence | 0.514286 | **0.708245** |

The best possession-interval result improves spellF1 by **0.050980** over the prior
best (**10.57% relative**) and by **0.207752** over step 05 (**63.81% relative**).
The highest frame-level macroF1 comes from a different candidate, r12. These
metrics measure different behavior; neither establishes full-match accuracy.

### Why occlusion continuity helped

The earlier model eventually emits D when it loses the ball for too long. The
new r06 rule bridges a D interval only when it lasts at most eight seconds, the
same team bounds it, every ball observation inside is missing, and no automatic
restart or explicit stoppage cue overlaps. It preserves the existing interception
and control algorithm and changes only the final label continuity. **It does not
fill ball coordinates.**

Across the full recording this changed 1,786 labels across 15 gaps. Only one gap,
82 frames or 3.28 seconds, lies in the labelled window: all 82 changes corrected
parent errors and none introduced errors. This concentrated gain is important:
one short interruption explains the improvement, so the public result is weaker
evidence of generalization than the headline percentage might suggest. The
other 14 bridged gaps remain unverified. Same-team endpoints can also surround a
real stoppage, particularly if automatic restart tags missed it.

### Motion and input recovery

- **r02, forecasting:** raised macroF1 from 0.690217 to 0.704386 while spellF1
  stayed effectively unchanged. Of 89 changed graded frames, 77 corrected errors
  and 12 introduced errors. The same earlier forecast policy fills 1,860 ball
  positions; no original observed coordinate is replaced.
- **r03, robust velocity:** raised spellF1 to 0.514286 and macroF1 to 0.691496.
  The trailing 0.2-second median changed 159 graded labels: 26 corrections and
  three newly wrong labels; remaining changes exchanged one wrong label for
  another. The time estimator is causal and resets across missing observations.
- **r04, acceleration reachability:** regressed to 0.422857 / 0.677273 relative
  to r03. The explicit reaction/acceleration model is more complex but its fixed
  capabilities and distance-equivalent control scale did not improve this data.
  This is not evidence that physical models in general are inferior.
- **r08, forecasting + robust velocity:** preserved r03's 0.514286 spellF1 while
  raising macroF1 to 0.706198. Relative to its forecast-only parent it changed
  106 graded frames, correcting 26 errors and introducing three.

### Control and stoppage alternatives

- **r05, tolerant confirmation:** decreased spellF1 to 0.470588 and macroF1 to
  0.689105. All 11 changed graded frames introduced errors. Allowing brief
  uncertain interruptions did not help here.
- **r07, boundary persistence:** left spellF1 unchanged and raised macroF1 to
  0.691811, correcting six graded frames with no new errors. The release test
  uses distance-equivalent arrival evidence, not literal player-to-ball distance.
- **r09, forecasting + tolerant confirmation:** reached 0.470588 / 0.703274;
  the control change again introduced 11 errors relative to its forecast parent.
- **r10, forecasting + boundary persistence:** reached 0.482353 / 0.706429;
  boundary persistence corrected ten graded errors but introduced four.
- **r11, forecasting + robust velocity + tolerant confirmation:** reached
  0.502857 / 0.704997. The final control change introduced 12 errors relative
  to r08 and reduced both scores.
- **r12, forecasting + robust velocity + boundary persistence:** reached
  0.514286 / 0.708245, the highest macroF1. Its final boundary change corrected
  ten errors and introduced four; D recall was 38.33%, versus 34.85% for r01/r06.

The graph and settings were fixed before this batch's scores; unsuccessful
methods remain in the results. No threshold sweep or score-driven generation of
additional variants was performed. Combining r06 with the robust/forecast model
has **not** been tested in this batch and no combined gain is claimed.

## Reproduction and verification

See [the run guide](refinement/README.md). All code and tests live under
`playground/refinement/`; generated artifacts stay under ignored
`playground/artifacts/`. Production pipelines and input assets are unchanged.

The first full run, `refinement_001`, took 48.45 seconds. All 187 maintained
pipeline, relevant utility, and playground tests passed, including 31 new
refinement tests. Independent correctness and style reviews found no required
fixes. Black passed for all 20 new Python files.

A second full run, `refinement_002`, took 49.49 seconds. All thirteen submission
CSVs, all thirteen official score JSONs, and the frozen prediction fingerprints
are byte-identical between runs. The interval-score candidate is
`playground/artifacts/refinement_002/r06_occlusion_bridge/possession.csv`; the
frame-score candidate is
`playground/artifacts/refinement_002/r12_forecast_robust_boundary/possession.csv`.

The following generated report preserves every variant's parent, hypothesis,
method and exact scores. The same public window was used in previous experiments;
prior results informed the reference and proposed hypotheses. This is exploratory
comparison, not an untouched holdout or proof of performance on another match.

r00 reproduces step 05; r01 reproduces the earlier c05 interception model. Each subsequent experiment changes one component relative to its named parent. All variants and predictions are frozen before scoring with step 06.

| Experiment | Parent | spellF1 | Δ r01 | macroF1 | D recall |
| --- | --- | ---: | ---: | ---: | ---: |
| r00_original_baseline | none | 0.325581 | -0.156772 | 0.620733 | 21.38% |
| r01_interception_reference | r00_original_baseline | 0.482353 | +0.000000 | 0.690217 | 34.85% |
| r02_forecast_interception | r01_interception_reference | 0.482353 | +0.000000 | 0.704386 | 37.64% |
| r03_robust_velocity | r01_interception_reference | 0.514286 | +0.031933 | 0.691496 | 34.85% |
| r04_acceleration_reachability | r03_robust_velocity | 0.422857 | -0.059496 | 0.677273 | 34.85% |
| r05_tolerant_control | r01_interception_reference | 0.470588 | -0.011765 | 0.689105 | 34.85% |
| r06_occlusion_bridge | r01_interception_reference | 0.533333 | +0.050980 | 0.702218 | 34.85% |
| r07_boundary_persistence | r01_interception_reference | 0.482353 | +0.000000 | 0.691811 | 35.26% |
| r08_forecast_robust | r02_forecast_interception | 0.514286 | +0.031933 | 0.706198 | 37.64% |
| r09_forecast_tolerant | r02_forecast_interception | 0.470588 | -0.011765 | 0.703274 | 37.64% |
| r10_forecast_boundary | r02_forecast_interception | 0.482353 | +0.000000 | 0.706429 | 38.33% |
| r11_forecast_robust_tolerant | r08_forecast_robust | 0.502857 | +0.020504 | 0.704997 | 37.64% |
| r12_forecast_robust_boundary | r08_forecast_robust | 0.514286 | +0.031933 | 0.708245 | 38.33% |

## r00_original_baseline: Original step 05 baseline

**Parent:** none. **Changed component:** reference.

**Hypothesis:** Reproduce the original nearest-player submission.

**Method:** Independent step 05 output must match this reference exactly.

**Results:** spellF1 0.325581 (+0.000000 against parent); macroF1 0.620733 (+0.000000). Changed 0 full-recording frames, including 0 graded frames. Corrected 0 parent errors and introduced 0 errors. Predicted 26 possessions versus 17 reference possessions.

## r01_interception_reference: Previous c05 interception reference

**Parent:** r00_original_baseline. **Changed component:** reference_anchor.

**Hypothesis:** Reproduce the previous strongest possession-interval result.

**Method:** This anchor combines earlier control rules and anticipated interception; it is not a one-component experiment relative to r00.

**Results:** spellF1 0.482353 (+0.156772 against parent); macroF1 0.690217 (+0.069484). Changed 34,320 full-recording frames, including 1,057 graded frames. Corrected 553 parent errors and introduced 209 errors. Predicted 17 possessions versus 17 reference possessions.

## r02_forecast_interception: Add short causal forecasts to interception

**Parent:** r01_interception_reference. **Changed component:** ball_forecast.

**Hypothesis:** The earlier forecasting and interception gains may complement each other.

**Method:** Fill at most 0.5 seconds from 0.2 seconds of original continuous ball motion; recompute ball-dependent features and interception evidence.

**Results:** spellF1 0.482353 (+0.000000 against parent); macroF1 0.704386 (+0.014169). Changed 2,687 full-recording frames, including 89 graded frames. Corrected 77 parent errors and introduced 12 errors. Predicted 17 possessions versus 17 reference possessions.

## r03_robust_velocity: Use robust causal motion estimates

**Parent:** r01_interception_reference. **Changed component:** velocity_estimator.

**Hypothesis:** A trailing median can reduce noisy one-frame velocity effects.

**Method:** Replace instantaneous ball/player velocity with a trailing 0.2-second median within the current observed run; retain the same arrival proxy.

**Results:** spellF1 0.514286 (+0.031933 against parent); macroF1 0.691496 (+0.001279). Changed 1,448 full-recording frames, including 159 graded frames. Corrected 26 parent errors and introduced 3 errors. Predicted 18 possessions versus 17 reference possessions.

## r04_acceleration_reachability: Race to the earliest reachable point on the ball trajectory

**Parent:** r03_robust_velocity. **Changed component:** arrival_model.

**Hypothesis:** Reaction and acceleration constraints may identify control better.

**Method:** Use robust motion and test ball targets at 0.1-second steps through two seconds. Players react for 0.2 seconds, accelerate at 3 m/s² up to 7 m/s, and control within one metre. Arrival seconds become equivalent metres.

**Results:** spellF1 0.422857 (-0.091429 against parent); macroF1 0.677273 (-0.014223). Changed 10,583 full-recording frames, including 377 graded frames. Corrected 25 parent errors and introduced 170 errors. Predicted 18 possessions versus 17 reference possessions.

## r05_tolerant_control: Tolerate brief uncertainty while confirming control

**Parent:** r01_interception_reference. **Changed component:** control_confirmation.

**Hypothesis:** One uncertain observation should not erase a developing handover.

**Method:** Require the same 0.4 seconds of opposing evidence, allow at most 0.12 seconds of consecutive uncertainty within a 0.8-second window, and reset on incumbent evidence or explicit dead play.

**Results:** spellF1 0.470588 (-0.011765 against parent); macroF1 0.689105 (-0.001113). Changed 224 full-recording frames, including 11 graded frames. Corrected 0 parent errors and introduced 11 errors. Predicted 17 possessions versus 17 reference possessions.

## r06_occlusion_bridge: Bridge same-team possession through pure ball occlusion

**Parent:** r01_interception_reference. **Changed component:** occlusion_bridge.

**Hypothesis:** An occluded ball need not mean the match stopped.

**Method:** Fill only D runs up to eight seconds, bounded by the same live team, with every ball observation missing and no restart or explicit dead cue.

**Results:** spellF1 0.533333 (+0.050980 against parent); macroF1 0.702218 (+0.012001). Changed 1,786 full-recording frames, including 82 graded frames. Corrected 82 parent errors and introduced 0 errors. Predicted 16 possessions versus 17 reference possessions.

## r07_boundary_persistence: Retain confirmed out-of-play evidence until a supported return

**Parent:** r01_interception_reference. **Changed component:** boundary_state.

**Hypothesis:** Losing an out-of-play ball should not immediately restore possession.

**Method:** Retain boundary-triggered D until 0.2 seconds of in-pitch movement or close team evidence; expire after 30 seconds without another boundary cue.

**Results:** spellF1 0.482353 (+0.000000 against parent); macroF1 0.691811 (+0.001594). Changed 1,719 full-recording frames, including 6 graded frames. Corrected 6 parent errors and introduced 0 errors. Predicted 17 possessions versus 17 reference possessions.

## r08_forecast_robust: Robust motion with causal ball forecasting

**Parent:** r02_forecast_interception. **Changed component:** velocity_estimator.

**Hypothesis:** Robust arrival evidence may complement short reconstructed trajectories.

**Method:** Replace instantaneous ball/player velocity with a trailing 0.2-second median within the current observed run; retain the same arrival proxy.

**Results:** spellF1 0.514286 (+0.031933 against parent); macroF1 0.706198 (+0.001811). Changed 1,444 full-recording frames, including 106 graded frames. Corrected 26 parent errors and introduced 3 errors. Predicted 18 possessions versus 17 reference possessions.

## r09_forecast_tolerant: Tolerant control with causal ball forecasting

**Parent:** r02_forecast_interception. **Changed component:** control_confirmation.

**Hypothesis:** Short forecasts and interruption-tolerant handovers may complement each other.

**Method:** Require the same 0.4 seconds of opposing evidence, allow at most 0.12 seconds of consecutive uncertainty within a 0.8-second window, and reset on incumbent evidence or explicit dead play.

**Results:** spellF1 0.470588 (-0.011765 against parent); macroF1 0.703274 (-0.001113). Changed 226 full-recording frames, including 11 graded frames. Corrected 0 parent errors and introduced 11 errors. Predicted 17 possessions versus 17 reference possessions.

## r10_forecast_boundary: Boundary persistence with causal ball forecasting

**Parent:** r02_forecast_interception. **Changed component:** boundary_state.

**Hypothesis:** An explicit restart state may separate forecast continuation from live play.

**Method:** Retain boundary-triggered D until 0.2 seconds of in-pitch movement or close team evidence; expire after 30 seconds without another boundary cue.

**Results:** spellF1 0.482353 (+0.000000 against parent); macroF1 0.706429 (+0.002042). Changed 1,849 full-recording frames, including 14 graded frames. Corrected 10 parent errors and introduced 4 errors. Predicted 17 possessions versus 17 reference possessions.

## r11_forecast_robust_tolerant: Tolerant control added to robust forecast interception

**Parent:** r08_forecast_robust. **Changed component:** control_confirmation.

**Hypothesis:** Combining input and control robustness may reduce fragmented possession.

**Method:** Require the same 0.4 seconds of opposing evidence, allow at most 0.12 seconds of consecutive uncertainty within a 0.8-second window, and reset on incumbent evidence or explicit dead play.

**Results:** spellF1 0.502857 (-0.011429 against parent); macroF1 0.704997 (-0.001201). Changed 231 full-recording frames, including 12 graded frames. Corrected 0 parent errors and introduced 12 errors. Predicted 18 possessions versus 17 reference possessions.

## r12_forecast_robust_boundary: Boundary persistence added to robust forecast interception

**Parent:** r08_forecast_robust. **Changed component:** boundary_state.

**Hypothesis:** Explicit out-of-play persistence may improve a more stable arrival model.

**Method:** Retain boundary-triggered D until 0.2 seconds of in-pitch movement or close team evidence; expire after 30 seconds without another boundary cue.

**Results:** spellF1 0.514286 (+0.000000 against parent); macroF1 0.708245 (+0.002047). Changed 1,915 full-recording frames, including 14 graded frames. Corrected 10 parent errors and introduced 4 errors. Predicted 18 possessions versus 17 reference possessions.

## Interpretation limits

These are descriptive results on the same five-minute public correctness window used earlier. Prior scores informed the choice of the reference and hypotheses, so this is not an untouched holdout. No possession labels train a model or tune a threshold within this batch, and no winner is automatically deployed.

Motion and reachability settings are physical hypotheses, not calibrated player capabilities. Offline smoothing, gap bridging and confirmation backdating mean the full predictor is not a real-time system, even when its velocity estimator is causal. Missing-ball continuity can hide a true stoppage; forecast positions are estimates rather than new observations.
