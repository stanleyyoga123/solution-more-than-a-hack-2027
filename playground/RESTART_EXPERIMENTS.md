# Smart Tagging restart experiment results

## Outcome

Nine new variants were evaluated alongside the original step 05 and previous
r06 references, using the unchanged step 06 scorer. **None improved spellF1
over r06 (0.533333).** The default `output/prediction.csv` remains byte-identical
to r06; no new candidate was promoted.

The strongest frame-level candidate, **s08**, increased macroF1 from 0.702218
to **0.731223** (+0.029005), while spellF1 fell to **0.525714** (-0.007619).
Dead-ball precision improved from 73.46% to 77.10%, and recall from 34.85%
to 42.41%. These are useful frame-level gains, but do not meet the primary
objective of improving possession intervals.

The evaluated window has 17 true possessions. r06 predicts 16, s03 predicts
19, and s08 predicts 18. Together with lower transition F1 (0.2500 for r06
versus 0.2273 for s08), this suggests that restart cues help classify individual
frames while interval fragmentation and boundary placement remain unresolved.
Possession counts alone cannot establish whether intervals are correct.

## What the tags support

The tactical XML contains 638 automatic events, including 59 recognized
set-piece windows: 26 throw-ins, 12 corners, 10 goal kicks, five free kicks,
and six kickoffs. Non-kickoff windows last 35 seconds; kickoff windows last
five seconds. They are broad context, not ground-truth stoppage boundaries,
and there is no explicit foul or ball-out class in this file.

Treating whole windows as dead play (s02) reduced spellF1 to 0.451613 and
introduced 519 graded-frame errors while correcting 276. Requiring stationary
ball evidence at a restart-compatible location was more precise. The persistent
s04 detector found qualifying evidence in 20 of 59 events; adding boundary
entry in s06 increased this to 28 of 59. These counts measure detector coverage,
not verified detection accuracy. Most full-match changes cannot be scored
because their frames are unlabelled.

Resetting the possession state using inferred stoppages (s08) corrected another
45 graded frames relative to s04 without introducing graded-frame errors, but
left spellF1 unchanged. Backtracking and boundary entry changed predictions
outside the graded window only. The conservative dead-gap bridge (s10) made
no changes anywhere in the recording.

## Reproducibility and scope

- Runs: `playground/artifacts/restarts_001` and `restarts_002`.
- Both processed all 199,319 frames, taking approximately 26 seconds each.
- All 11 prediction CSVs and official score JSONs were byte-identical between
  runs; prediction hash manifests also matched.
- The step 05 reference was checked independently. The s01 CSV also exactly
  matched the previous `refinement_002/r06_occlusion_bridge/possession.csv`.
- Every prediction and its hash was written before possession ground truth
  was read. Each new experiment changes one component from its named parent;
  s00 and s01 are reference anchors.
- Evaluation uses the same 7,500 public frames (11185–18684) used in prior
  experiments. This is exploratory evidence, not a fresh holdout result.
- Verification: 233 tests passed across the maintained playground suites,
  pipeline tests, and export/logging tests, including 46 restart-specific tests.
  Black and whitespace checks passed. Independent correctness and style reviews
  reported no required fixes.

The code and run instructions are in [restarts/README.md](restarts/README.md).
Generated match artifacts remain ignored by Git. Each run includes masks,
per-event diagnostics, configurations, source/input hashes, scores, and a
complete generated report.

To inspect the highest-macroF1 candidate alongside the video:

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/restarts_002/s08_reset_control_state/possession.csv
```

A useful next investigation is a restart-boundary model combining ball visibility,
player motion, and video evidence, evaluated on permitted independently labelled
data. These results do not justify selecting new thresholds against this same
small public window.

## Complete experiment record

The following record is taken from the second run. Changed-frame and
corrected/introduced-error counts are relative to each experiment's named parent,
not always to r06. Table column `Δ s01` compares spellF1 with r06.

The graph and numerical settings were fixed before this batch's scores. All submissions were frozen before step 06 read possession labels. s00 and s01 are reference anchors; subsequent branches each change one component relative to their named parent.

| Experiment | Parent | spellF1 | Δ s01 | macroF1 | D precision | D recall |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| s00_original_baseline | none | 0.325581 | -0.207752 | 0.620733 | 65.69% | 21.38% |
| s01_occlusion_reference | s00_original_baseline | 0.533333 | +0.000000 | 0.702218 | 73.46% | 34.85% |
| s02_whole_restart_window | s01_occlusion_reference | 0.451613 | -0.081720 | 0.699211 | 52.82% | 53.64% |
| s03_typed_stationary_seeds | s01_occlusion_reference | 0.511111 | -0.022222 | 0.716123 | 74.48% | 38.73% |
| s04_seeded_restart_state | s03_typed_stationary_seeds | 0.525714 | -0.007619 | 0.719747 | 75.75% | 39.35% |
| s05_backtrack_supported_stop | s04_seeded_restart_state | 0.525714 | -0.007619 | 0.719747 | 75.75% | 39.35% |
| s06_boundary_entry | s04_seeded_restart_state | 0.525714 | -0.007619 | 0.719747 | 75.75% | 39.35% |
| s07_control_supported_release | s04_seeded_restart_state | 0.525714 | -0.007619 | 0.718189 | 75.56% | 38.94% |
| s08_reset_control_state | s04_seeded_restart_state | 0.525714 | -0.007619 | 0.731223 | 77.10% | 42.41% |
| s09_boundary_backtrack | s06_boundary_entry | 0.525714 | -0.007619 | 0.719747 | 75.75% | 39.35% |
| s10_restart_dead_gap_bridge | s01_occlusion_reference | 0.533333 | +0.000000 | 0.702218 | 73.46% | 34.85% |

## s00_original_baseline: Original step 05 reference

**Parent:** none. **Change:** reference.

**Hypothesis:** Reproduce the unmodified baseline.

**Method:** Checked against an independently generated step 05 submission.

**Result:** spellF1 0.325581 (+0.000000 versus parent), macroF1 0.620733 (+0.000000). Changed 0 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors. Predicted 26 possessions versus 17 reference possessions.

## s01_occlusion_reference: Previous r06 interception and occlusion reference

**Parent:** s00_original_baseline. **Change:** reference_anchor.

**Hypothesis:** Reproduce the previous strongest spellF1 result.

**Method:** This reference combines prior interception, control and occlusion rules; it is not a single-component change from s00.

**Result:** spellF1 0.533333 (+0.207752 versus parent), macroF1 0.702218 (+0.081485). Changed 34,653 full-recording labels and 1,039 graded labels. Corrected 585 parent errors and introduced 159 errors. Predicted 16 possessions versus 17 reference possessions.

## s02_whole_restart_window: Treat entire restart windows as dead ball

**Parent:** s01_occlusion_reference. **Change:** whole_window_dead.

**Hypothesis:** Test the direct-tag assumption as a deliberately coarse control.

**Method:** Set D throughout every recognized set-piece interval, without motion confirmation. This may erase live play because event windows are not verified stoppage intervals.

**Result:** spellF1 0.451613 (-0.081720 versus parent), macroF1 0.699211 (-0.003008). Changed 28,555 full-recording labels and 795 graded labels. Corrected 276 parent errors and introduced 519 errors. Predicted 14 possessions versus 17 reference possessions.

## s03_typed_stationary_seeds: Require stationary ball evidence at a plausible restart location

**Parent:** s01_occlusion_reference. **Change:** typed_stationary_dead.

**Hypothesis:** Restart type and observed stillness can support precise D frames.

**Method:** Within each known event window require 0.4 seconds of observed ball speed at most 1 m/s, gated by restart-specific geometry. Unknown teams remain usable for stoppage evidence.

**Result:** spellF1 0.511111 (-0.022222 versus parent), macroF1 0.716123 (+0.013905). Changed 563 full-recording labels and 67 graded labels. Corrected 57 parent errors and introduced 10 errors. Predicted 19 possessions versus 17 reference possessions.

## s04_seeded_restart_state: Retain the first confirmed stoppage until motion resumes

**Parent:** s03_typed_stationary_seeds. **Change:** stoppage_persistence.

**Hypothesis:** A confirmed stoppage can persist while tracking loses the ball.

**Method:** Use only the first qualifying seed per event and retain D through missing observations. End at 0.2 seconds of observed in-pitch motion between 2 and 45 m/s, backdated to that run's start, capped by the event end or 20 seconds after the seed.

**Result:** spellF1 0.525714 (+0.014603 versus parent), macroF1 0.719747 (+0.003624). Changed 257 full-recording labels and 19 graded labels. Corrected 19 parent errors and introduced 0 errors. Predicted 18 possessions versus 17 reference possessions.

## s05_backtrack_supported_stop: Extend a confirmed stoppage backward through compatible uncertainty

**Parent:** s04_seeded_restart_state. **Change:** stoppage_onset.

**Hypothesis:** The tracker may miss the beginning of a stoppage before a still ball appears.

**Method:** Extend at most eight seconds before the first confirmed seed across missing or stationary geometry-compatible observations; stop at contradictory observed play. This can precede the tag window.

**Result:** spellF1 0.525714 (+0.000000 versus parent), macroF1 0.719747 (+0.000000). Changed 38 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors. Predicted 18 possessions versus 17 reference possessions.

## s06_boundary_entry: Also accept observed out-of-pitch entry evidence

**Parent:** s04_seeded_restart_state. **Change:** stoppage_entry.

**Hypothesis:** Out-of-play geometry can seed a restart without a visible stationary ball.

**Method:** For throw-ins, corners and goal kicks, also accept 0.2 seconds outside the pitch by at least 0.25 m with compatible event geometry. Free kicks and kickoffs still require stationary evidence.

**Result:** spellF1 0.525714 (+0.000000 versus parent), macroF1 0.719747 (+0.000000). Changed 32 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors. Predicted 18 possessions versus 17 reference possessions.

## s07_control_supported_release: Recognize a slower restart near an observed player

**Parent:** s04_seeded_restart_state. **Change:** stoppage_release.

**Hypothesis:** A short controlled restart may not immediately reach 2 m/s.

**Method:** After seed confirmation, also permit sustained in-pitch motion of at least 0.8 m/s with an observed player within two actual metres. The upper plausible ball-speed bound still applies.

**Result:** spellF1 0.525714 (+0.000000 versus parent), macroF1 0.718189 (-0.001558). Changed 276 full-recording labels and 6 graded labels. Corrected 0 parent errors and introduced 6 errors. Predicted 18 possessions versus 17 reference possessions.

## s08_reset_control_state: Use inferred stoppages inside the possession state machine

**Parent:** s04_seeded_restart_state. **Change:** stoppage_integration.

**Hypothesis:** Resetting the incumbent at a stoppage may improve restart ownership.

**Method:** Inject the same inferred D mask before control confirmation instead of only overwriting final labels. Preserve explicit D through smoothing and the existing occlusion bridge.

**Result:** spellF1 0.525714 (+0.000000 versus parent), macroF1 0.731223 (+0.011476). Changed 165 full-recording labels and 45 graded labels. Corrected 45 parent errors and introduced 0 errors. Predicted 18 possessions versus 17 reference possessions.

## s09_boundary_backtrack: Backtrack confirmed stationary or boundary stoppages

**Parent:** s06_boundary_entry. **Change:** stoppage_onset.

**Hypothesis:** Additional entry evidence may complement bounded backward extension.

**Method:** Extend at most eight seconds before the first confirmed seed across missing or stationary geometry-compatible observations; stop at contradictory observed play. This can precede the tag window.

**Result:** spellF1 0.525714 (+0.000000 versus parent), macroF1 0.719747 (+0.000000). Changed 38 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors. Predicted 18 possessions versus 17 reference possessions.

## s10_restart_dead_gap_bridge: Remove short unsupported live islands within a tagged stoppage

**Parent:** s01_occlusion_reference. **Change:** dead_gap_continuity.

**Hypothesis:** Brief live labels between two D intervals may fragment one restart.

**Method:** Within a single restart window, bridge live runs up to two seconds bounded by D only if no observed ball has plausible motion at least 2 m/s or nearby player-control evidence. Preserve X and other labels.

**Result:** spellF1 0.533333 (+0.000000 versus parent), macroF1 0.702218 (+0.000000). Changed 0 full-recording labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors. Predicted 16 possessions versus 17 reference possessions.

## Limits

Automatic Smart Tags are event context, not verified stoppage boundaries. Missing ball observations do not prove dead play. Geometry and speed settings are fixed engineering hypotheses; no threshold sweep or possession-label training was performed.

Only the public five-minute window is labelled for evaluation. Earlier results informed these hypotheses, so this is exploratory comparison rather than a fresh holdout. Full-match changes remain unverified, and no candidate is automatically deployed.
