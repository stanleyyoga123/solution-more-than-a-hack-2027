# Possession fragmentation experiments

This batch tests whether uncertain tracking can be resolved without inventing
stoppages or erasing genuine short possessions. It starts from the existing r06
interception and occlusion predictor. Each new comparison changes one component
relative to its named parent; there is no threshold sweep.

The [recorded results](../FRAGMENTATION_EXPERIMENTS.md) cover two reproducible
runs. The simplest candidate raises public spellF1 to 0.545455, but the gain
comes from two corrected frames and does not demonstrate broad improvement.

```bash
.venv/bin/python -m playground.fragmentation \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_fragmentation_run
```

Run from the repository root. Original tactical tracking, metadata, and automatic
Smart Tagging XML are defaults; `--tracking`, `--metadata`, and `--tags` override
them. These inputs must use the same timeline. Choose a fresh output directory;
the runner preserves existing outputs and cleans failed temporary exports.

## Fixed comparisons

| ID | Parent | Change |
| --- | --- | --- |
| f00 | None | Original step 05 reference, independently checked. |
| f01 | f00 | Previous r06 anchor, not a one-component ablation. |
| f02 | f01 | Record uncertain D internally as U; exported labels must be identical. |
| f03 | f02 | Join short uncertain gaps bounded by the same team. |
| f04 | f03 | Remove unsupported brief opponent islands. |
| f05 | f04 | Resolve uncertain gaps bounded by different teams. |
| f06 | f05 | Refine the timing of direct team turnovers. |
| f07 | f02 | Test boundary refinement independently of merging. |
| f08 | f02 | Test opponent-island removal independently of gap filling. |

## Evidence and decisions

`evidence.py` separates existing physical stoppage cues from uncertain labels.
Observed boundary and stationary-ball cues use original pitch coordinates. Team
control uses arrival-equivalent distances, requires an observed ball and finite
plausible motion, and must persist for 0.4 seconds to provide confirmed support.
Missing data contributes no positive team evidence.

An r06 D frame without a physical stoppage cue becomes internal U. This is an
inference hypothesis, not proof of live play. Unsupported U that survives repairs
exports as D, preserving the standard `frame,label` submission format. H, A, and
X labels are preserved by this representation step.

`repair.py` implements four offline operations:

- **Same-team gaps:** join U runs up to eight seconds only when the endpoints
  agree and no confirmed opposing control or explicit dead cue exists. Ball
  observations may be intermittent. A broad restart tag alone is not a veto;
  it still supplies context to the existing stationary-ball detector.
- **Opponent islands:** remove a live run up to two seconds only when the same
  opposing team surrounds it, both flanks have confirmed control within one
  second, and the island has neither its own confirmed control nor a dead cue.
- **Different-team gaps:** require confirmed control on both flanks of a U gap
  up to eight seconds. Choose one transition minimizing contradictory sustained
  control evidence inside the gap. Missing frames are neutral. Equal-cost choices
  prefer the first supported right-team onset; absent that, the incumbent extends
  to the right endpoint. The audit records the uncertainty span and number of
  equally supported boundaries, so inferred timing is not presented as observed.
- **Boundary timing:** move an existing direct H/A boundary at most two seconds
  only if the assignment strictly improves agreement with sustained control.
  Both teams need evidence; adjacent spells retain at least one frame. Ties
  favor the closest boundary, and equal-cost alternatives do not move a boundary.

Explicit dead cues and X gaps block repairs. Algorithms do not cross unresolved
U or D to refine a direct turnover. No model treats every short possession as
an error or sets a target number of possessions.

## Evaluation and artifacts

All nine prediction files and their hashes are written before the runner reads
possession ground truth. Step 06 remains the scorer. The batch records:

- `protocol.json`: fixed settings, experiment graph, source and input hashes.
- `frozen_predictions.json`: hashes of the submissions before evaluation.
- Per variant: frontend-compatible `possession.csv`, official scores,
  `experiment.json`, `audit.json`, `internal_intervals.csv`, and
  `boundary_diagnostics.json`.
- `summary.csv`, `summary.json`, and `REPORT.md`: every comparison and outcome.

Audit edits are relative to the named parent; inspect ancestor audits to follow
cumulative changes. Internal interval ends are exclusive; video frame numbers
are zero-based. U appears only in diagnostics, never in submitted predictions.

Alongside spellF1 and macroF1, diagnostics count true spells overlapped by multiple
same-team predictions (splits) and predictions overlapped by multiple same-team
true spells (merges). Any positive overlap counts, including one frame. These
measure structure and are not independent proof of the cause of an error.

Boundary diagnostics match both the originating and destination label within
one second, separately inside each graded run. Timing error is conditional on
matched boundaries and must be read alongside missed and spurious counts. These
strict diagnostics complement the official scorer's destination-only transition
matching; they do not replace or modify the official score.

To view a candidate:

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/my_fragmentation_run/f06_refine_turnover_boundaries/possession.csv
```

The runner does not overwrite `output/prediction.csv` or automatically promote
a result. Match-derived outputs under `playground/artifacts/` remain Git-ignored.

```bash
.venv/bin/python -m pytest playground/fragmentation/tests -q
.venv/bin/python -m black --check playground/fragmentation
```

The public five-minute correctness window has been inspected in earlier work;
these are exploratory comparisons, not a fresh holdout. There is no training or
parameter fitting on its labels. Full-match edits remain unverified, and fewer
predicted spells alone do not establish improvement.
