# Physical control and collective stoppage experiments

These experiments investigate two traced failure mechanisms: a projected
interception being mistaken for current possession, and a stoppage being missed
while the ball remains visible and moving. They preserve the existing r06 and
f03 references and evaluate general rules, without frame-specific corrections.

The [diagnosis and results](../POSSESSION_ERROR_ANALYSIS.md) record every
comparison, sampled-video findings, and the stronger p07 stoppage candidate.

```bash
.venv/bin/python -m playground.possession_fixes \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_possession_fix_run \
  --review-range 15641 15766 \
  --review-range 15889 16400
```

Run from the repository root. `--tracking`, `--metadata`, and `--tags` accept
other inputs on the same timeline; defaults are the original tactical files.
Review ranges are optional, zero-based, end-exclusive, and used only after
predictions are frozen. They never affect inference. Existing output directories
are refused, and incomplete temporary exports are removed on failure.

## Fixed comparisons

| ID | Parent | Change |
| --- | --- | --- |
| p00 | None | Independent step 05 reference. |
| p01 | p00 | Previous r06 reference anchor. |
| p02 | p01 | Current f03 reference anchor. |
| p03 | p02 | Reject arrival-based control without physical proximity and separation. |
| p04 | p02 | Use physical distances for control candidates. |
| p05 | p04 | Also use physical nearest-team observations for initialization. |
| p06 | p02 | Add collective-slowdown stoppage seeds. |
| p07 | p06 | Retain collective stoppages until supported restart motion. |
| p08 | p07 | Add the physical proximity gate. |
| p09 | p07 | Use physical control candidates. |
| p10 | p09 | Also initialize from physical nearest-team observations. |

p00–p02 are reference anchors; all subsequent branches change one component
relative to their named parent. Settings and branches are declared before
scoring, with no threshold sweep or score-dependent new variant.

## Ownership and evidence

`prediction.py` retains the existing confirmation, smoothing, and uncertainty
repairs. Its default must reproduce f03 exactly. The candidate gate requires
the forecast-winning team to be within two actual metres of the ball and at
least 0.5 m closer than its opponent. Rejection keeps uncertainty; it does not
automatically assign the other team. The physical-candidate alternative uses
original distances directly, leaving the existing speed and duration rules.

`stoppages.py` tests collective slowdown independently of possession ownership.
Entry requires two continuous seconds with at least eight visible players,
median player speed no greater than 1.5 m/s, and an observed in-pitch ball beyond
two metres from every player, moving no faster than 12 m/s. Missing observations
cannot initiate a stoppage.

The retained version holds that cue for at most 20 seconds from seed onset.
Release requires 0.4 seconds of observed physical control with ball speed at
least 2 m/s, plus either renewed collective motion or ball speed at least 8 m/s.
The physical-control detector's existing 12 m/s limit still applies. Missing
data cannot release the stoppage. Entry and release are backdated after
confirmation, making this an offline algorithm. An uninterrupted seed does not
rearm itself indefinitely after timeout.

These are fallible physical cues, not detections of a referee's decision.
Legitimate slow live play can resemble a stoppage, and close proximity need
not mean control. Added dead masks survive smoothing and both gap-repair stages.

## Outputs

The runner loads the full recording, writes every prediction and its hash, then
invokes the unchanged step 06 scorer. It records:

- `protocol.json`: fixed policy, experiment graph, source/input hashes, and
  evaluation-only review ranges.
- `evidence.csv`: original distances, arrival equivalents, ball/player motion,
  control candidates and original intermediate decoder states, plus new masks.
  Team codes are 0=home, 1=away, -1=unavailable. It contains no ground truth.
- `frozen_predictions.json`: all submission hashes before scoring.
- Per variant: frontend-compatible `possession.csv`, official scores,
  `experiment.json`, `stoppage_audit.json`, `extra_dead_intervals.csv`, and
  `review.json` with interval errors and structural diagnostics.
- `summary.csv`, `summary.json`, and `REPORT.md` with every result, including
  regressions and changes that help a target clip but harm the global score.

Edit comparisons in the main table use the named parent. Review-range errors
compare with f03. Split/merge diagnostics follow the definitions in the
[fragmentation guide](../fragmentation/README.md). Match-derived artifacts remain
Git-ignored. The runner never overwrites `output/prediction.csv` or promotes a
candidate automatically.

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/my_possession_fix_run/p03_physical_gate/possession.csv

.venv/bin/python -m pytest playground/possession_fixes/tests -q
.venv/bin/python -m black --check playground/possession_fixes
```

Known public errors and sampled footage motivated these hypotheses. This is
exploratory debugging on an already-inspected five-minute window, not an
independent holdout or proof of full-match improvement. The algorithm does not
receive manually labelled video frames, target ranges, or possession ground
truth during inference.
