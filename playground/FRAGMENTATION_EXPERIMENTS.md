# Possession fragmentation experiment results

## Outcome

The fixed batch produced a **small public-window spellF1 increase from 0.533333
to 0.545455** (+0.012121, or 1.21 percentage points). The simplest candidate
with that score is **f03**, which joins short uncertain gaps bounded by the same
team when there is no confirmed opposing control or explicit dead-ball cue.
MacroF1 moved from 0.702218 to 0.702514 (+0.000296).

This does **not** establish a broad fragmentation improvement. Only two graded
frames changed, both at the start of the public evaluation window. Split and
merge diagnostics on that window did not improve. The current viewer default,
`output/prediction.csv`, remains the previous r06 prediction; f03 is retained
as a candidate for inspection rather than silently promoted.

## Why the score moved

The full-recording algorithm joined 14 uncertain gaps, changing 1,813 frames.
Only one repair intersects the public window: the inferred A interval spanning
frames [11085, 11187). The public labels start at frame 11185, so only frames
11185 and 11186 are scored. Both changed from D to the correct A label.
This was produced by the general, predeclared rule, not a frame-specific fix.

The first graded true A possession is [11185, 11351). Its prediction changed
from [11187, 11460) to [11185, 11460). Temporal IoU therefore rose from
164/275 = **0.59636** to 166/275 = **0.60364**. That crosses the scorer's 0.6
threshold, adding one match at one of its five thresholds. Matches at 0.3,
0.4, 0.5, and 0.7 did not change. The predicted end remains 109 frames late.

This explains why correcting just two frames changes spellF1 noticeably.
It is an observed score improvement with very limited evidence of generality.
No settings or inference code changed after these scores were read.

## What each repair achieved

| Component | Full-recording action | Public-window outcome |
| --- | --- | --- |
| Explicit uncertainty | Reclassified 78,312 D frames internally as U; exported them as D | Exact identity with r06 |
| Same-team joining | Joined 14 gaps; changed 1,813 frames | Corrected two frames, no new frame errors; spellF1 +0.012121 |
| Unsupported opponent islands | No eligible repairs | No prediction or score change |
| Different-team uncertain gaps | No eligible repairs | No prediction or score change |
| Direct boundary refinement | Moved 16 boundaries; changed 339 frames | All changes outside graded window; no score change |

The independent boundary-only and island-only branches also did not improve
public scores. f04/f05 equal f03 across the full recording. f06 ties f03 on
public scores but additionally changes unlabelled boundaries; the score gives
no basis for preferring that extra complexity.

Across the entire recording, H/A run count fell from 412 to 398 after joining.
Those counts include ungraded pre/post-match and halftime portions and are not
verified true possessions. Within the public window, the count remains 16
predicted versus 17 true possessions, with one split true spell and two merged
predicted spells under the positive-overlap diagnostic. Fewer full-recording
runs alone do not show that the joins were correct.

Strict origin-and-destination boundary matching within one second remained
at four matches with a conditional mean absolute error of 0.46 seconds.
Missed boundaries remained 16; spurious boundaries fell from 16 to 15. The
conditional timing average excludes unmatched boundaries and is not a complete
measure of boundary quality.

## Reproducibility and validation

- Ran all nine variants twice over 199,319 frames, in approximately 25.5 seconds
  per batch, under `playground/artifacts/fragmentation_001` and `fragmentation_002`.
- All nine submissions, official score JSONs, edit audits, internal intervals,
  and boundary diagnostics were byte-identical across runs. Source/input
  protocols and prediction hash manifests also matched.
- The original baseline matched an independent step 05 invocation. f01 matched
  the previous `refinement_002/r06_occlusion_bridge/possession.csv` exactly;
  f02's uncertainty representation exported exactly the same prediction.
- Every prediction and its hash existed before any possession-ground-truth read.
  The existing step 06 scorer performed evaluation without modification.
- **284 tests passed**, including 51 fragmentation tests. Black formatting and
  whitespace checks passed. Independent correctness and style reviews found no
  required fixes; the correctness review also exercised 2,000 deterministic
  boundary scenarios.
- This reuses the same 7,500 public frames (11185–18684), containing 17 true
  possessions. It is exploratory analysis, not a fresh holdout assessment.

Code and commands are in [fragmentation/README.md](fragmentation/README.md).
Fixed hypotheses and parent comparisons are in `fragmentation/specs.py`;
all thresholds live in the policy files. No threshold sweep or possession-label
training was performed. The runner writes audit records for every accepted
repair and preserves input data and existing outputs.

To inspect the simplest improved-score candidate in the existing frontend:

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/fragmentation_002/f03_join_uncertain_gaps/possession.csv
```

The public result supports keeping f03 as a hypothesis to test on independent,
permitted labelled data. It does not support claiming the remaining fragmentation
problem is solved or promoting the full-match edits as reliable corrections.

## Complete experiment record

The following report comes from the second run. Changes and corrected/introduced
errors are relative to each named parent. The table's delta compares spellF1
with r06. Every branch was specified before scoring, including ineffective ones.

All predictions were frozen before step 06 scoring. f00/f01 are references, f02 is an identity control, and later variants change one component from their named parent. Unresolved internal U exports as D.

| Experiment | Parent | spellF1 | Δ r06 | macroF1 | Spells | Splits | Merges |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| f00_original_baseline | none | 0.325581 | -0.207752 | 0.620733 | 26 | 5 | 3 |
| f01_occlusion_reference | f00_original_baseline | 0.533333 | +0.000000 | 0.702218 | 16 | 1 | 2 |
| f02_explicit_uncertainty | f01_occlusion_reference | 0.533333 | +0.000000 | 0.702218 | 16 | 1 | 2 |
| f03_join_uncertain_gaps | f02_explicit_uncertainty | 0.545455 | +0.012121 | 0.702514 | 16 | 1 | 2 |
| f04_remove_unsupported_islands | f03_join_uncertain_gaps | 0.545455 | +0.012121 | 0.702514 | 16 | 1 | 2 |
| f05_resolve_turnover_gaps | f04_remove_unsupported_islands | 0.545455 | +0.012121 | 0.702514 | 16 | 1 | 2 |
| f06_refine_turnover_boundaries | f05_resolve_turnover_gaps | 0.545455 | +0.012121 | 0.702514 | 16 | 1 | 2 |
| f07_boundary_only | f02_explicit_uncertainty | 0.533333 | +0.000000 | 0.702218 | 16 | 1 | 2 |
| f08_islands_only | f02_explicit_uncertainty | 0.533333 | +0.000000 | 0.702218 | 16 | 1 | 2 |

Splits count true possessions overlapping more than one same-team prediction. Merges count predictions overlapping more than one same-team true possession. Any positive overlap counts; these are structural diagnostics, not independently adjudicated error causes.

## f00_original_baseline: Original step 05

**Parent:** none. **Change:** reference.

**Hypothesis:** Reproduce the original baseline independently.

**Method:** Compare predictions with a separate step 05 invocation.

**Result:** spellF1 0.325581 (+0.000000 versus parent), macroF1 0.620733 (+0.000000). Changed 0 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 26 predictions versus 17 true possessions; 5 split true spells, 3 merged predicted spells. Matched 2 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.160 s. Missed 18 boundaries and produced 27 spurious boundaries.

## f01_occlusion_reference: Previous best r06

**Parent:** f00_original_baseline. **Change:** reference_anchor.

**Hypothesis:** Reproduce the existing interception and occlusion predictor.

**Method:** This is a reference anchor, not a one-component ablation of step 05.

**Result:** spellF1 0.533333 (+0.207752 versus parent), macroF1 0.702218 (+0.081485). Changed 34,653 full-match labels and 1,039 graded labels. Corrected 585 parent errors and introduced 159 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 16 spurious boundaries.

## f02_explicit_uncertainty: Separate unsupported D from observed stoppage cues

**Parent:** f01_occlusion_reference. **Change:** internal_representation.

**Hypothesis:** Track ambiguous labels without changing the submitted prediction.

**Method:** Internally mark D without a physical stoppage cue as U. Export unresolved U as D, so this control must match r06 exactly. U is a hypothesis, not proof that play is live.

**Result:** spellF1 0.533333 (+0.000000 versus parent), macroF1 0.702218 (+0.000000). Changed 0 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 16 spurious boundaries.

## f03_join_uncertain_gaps: Join same-team possessions across uncertain gaps

**Parent:** f02_explicit_uncertainty. **Change:** same_team_gap_repair.

**Hypothesis:** Intermittent tracking need not interrupt continuing possession.

**Method:** Join U intervals up to eight seconds bounded by the same team, unless there is an explicit stoppage cue or sustained opposing control. A broad restart window alone does not forbid the repair.

**Result:** spellF1 0.545455 (+0.012121 versus parent), macroF1 0.702514 (+0.000296). Changed 1,813 full-match labels and 2 graded labels. Corrected 2 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 15 spurious boundaries.

## f04_remove_unsupported_islands: Remove unsupported brief opponent possessions

**Parent:** f03_join_uncertain_gaps. **Change:** opponent_island_repair.

**Hypothesis:** Weak opponent labels can split a single possession.

**Method:** Replace opponent islands up to two seconds only with positive control evidence for the surrounding team on both sides and no confirmed island-team control or explicit stoppage cue.

**Result:** spellF1 0.545455 (+0.000000 versus parent), macroF1 0.702514 (+0.000000). Changed 0 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 15 spurious boundaries.

## f05_resolve_turnover_gaps: Resolve uncertainty between different controlling teams

**Parent:** f04_remove_unsupported_islands. **Change:** different_team_gap_repair.

**Hypothesis:** A loose-ball interval can contain one turnover without a stoppage.

**Method:** Resolve U gaps up to eight seconds only with confirmed flanking control and no explicit stoppage cue. Choose a single boundary minimizing contradictory observed control; record the ambiguous timing range.

**Result:** spellF1 0.545455 (+0.000000 versus parent), macroF1 0.702514 (+0.000000). Changed 0 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 15 spurious boundaries.

## f06_refine_turnover_boundaries: Refine direct turnover timing

**Parent:** f05_resolve_turnover_gaps. **Change:** boundary_timing.

**Hypothesis:** Control evidence can correct boundaries shifted by smoothing.

**Method:** Move direct H/A boundaries at most two seconds within adjacent spells, only when observed two-team control strictly improves the assignment. Preserve stoppages, unresolved uncertainty, and neighboring spells.

**Result:** spellF1 0.545455 (+0.000000 versus parent), macroF1 0.702514 (+0.000000). Changed 339 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 15 spurious boundaries.

## f07_boundary_only: Refine turnover timing without merging spells

**Parent:** f02_explicit_uncertainty. **Change:** boundary_timing.

**Hypothesis:** Boundary timing may improve independently of fragmentation repair.

**Method:** Move direct H/A boundaries at most two seconds within adjacent spells, only when observed two-team control strictly improves the assignment. Preserve stoppages, unresolved uncertainty, and neighboring spells.

**Result:** spellF1 0.533333 (+0.000000 versus parent), macroF1 0.702218 (+0.000000). Changed 339 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 16 spurious boundaries.

## f08_islands_only: Remove unsupported islands without gap filling

**Parent:** f02_explicit_uncertainty. **Change:** opponent_island_repair.

**Hypothesis:** Brief opponent interruptions may be independent of missing-data gaps.

**Method:** Replace opponent islands up to two seconds only with positive control evidence for the surrounding team on both sides and no confirmed island-team control or explicit stoppage cue.

**Result:** spellF1 0.533333 (+0.000000 versus parent), macroF1 0.702218 (+0.000000). Changed 0 full-match labels and 0 graded labels. Corrected 0 parent errors and introduced 0 errors.

**Intervals:** 16 predictions versus 17 true possessions; 1 split true spells, 2 merged predicted spells. Matched 4 boundaries within 1 s with matching origin and destination; conditional mean absolute timing error 0.460 s. Missed 16 boundaries and produced 16 spurious boundaries.

## Limits

This reuses the public five-minute correctness window, not a new holdout. Thresholds are fixed engineering hypotheses and no tuning or fitting uses possession labels. Full-match changes are unverified. Uncertainty is not evidence of live play, and physical dead-ball cues can also be wrong. Boundary timing is conditional on matched boundaries and must be read with missed/spurious counts. The runner does not promote a candidate or overwrite the viewer input.
