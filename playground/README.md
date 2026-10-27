# Possession experiment playground

This folder contains a reproducible comparison against step 05's nearest-player
baseline. Each experiment changes **one component relative to its named parent**.
Every submission is evaluated by the existing step 06 scorer.

The [creative experiment guide](creative/README.md) extends this work with ball
forecasting, Viterbi decoding, interception races, self-supervised estimation, and
actual YOLO video recovery. Its [separate write-up](CREATIVE_EXPERIMENTS.md) records
all results and detector limitations.

The [interception refinement guide](refinement/README.md) adds a third fixed batch:
forecast combinations, robust velocities, acceleration-based arrival estimates,
and alternative control and stoppage continuity rules.
Its [write-up](REFINEMENT_EXPERIMENTS.md) records the full comparison and the
trade-off between interval and frame-level scores.

The fixed experiment sequence and domain settings are declared before scoring.
Inference sees tracking and automatic tactical tags, never possession labels.
The runner creates every prediction file before reading the public ground truth.
The original e00–e08 batch has no parameter search, model fitting, or automatic
winner promotion. The separate creative batch includes self-supervised regression
on observed ball coordinates, described in its guide.

## Run the complete batch

Run from the repository root, using the existing project environment:

```bash
.venv/bin/python -m playground \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --tags data/tactical/BAR-ATH_tactical_smart_tagging.xml \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_run
```

Use a fresh output directory for each run. The ground-truth path above is the
public file downloaded for the earlier imputation comparison. If absent, obtain
`evaluation/gt/BAR-ATH_possession_gt_public.csv` from the
[organisers' repository](https://github.com/metrica-sports/more-than-a-hack-2027)
and pass its local path explicitly. No download is performed automatically.

The three tracking/tag input paths have the defaults shown above; `--ground-truth`
is required. The batch processes the full recording in about 20 seconds on the
development machine, with roughly 17 MB of compact feature arrays. Actual runtime
depends on the machine and storage. Logs go to stderr; stdout contains the report
path after successful publication.

## Experiments

| ID | Only change from the preceding experiment |
| --- | --- |
| e00 | Exact step 05 baseline reproduction, checked independently frame for frame. |
| e01 | Include the baseline's `D` observations in the majority vote. |
| e02 | Bridge short missing-observation runs bounded by the same team. |
| e03 | Add sustained out-of-pitch ball evidence for stoppages. |
| e04 | Add stationary-ball evidence combined with movement/boundary/restart context. |
| e05 | Require sustained control evidence before transferring possession. |
| e06 | Supplement uncertain control with automatic tactical-phase team evidence. |
| e07 | Exclude impossible player/ball motion from geometric evidence. |
| e08 | Remove the final fixed-window smoothing vote. |

These are cumulative comparisons, not isolated comparisons of every feature
against e00. All settings live in `prediction_policy.py`; the experiment graph,
hypotheses, and rationales live in `experiments.py`. Fixed distances and durations
are engineering hypotheses, not calibrated physical truths or fitted values.

No possession labels or per-frame constants from the provided game's answer key
enter a predictor. Automatic tagging is used as imperfect evidence: defensive
phase team tags support the opponent; `N/A` and unrecognized codes provide no team
vote. Restart intervals are contextual cues, not direct dead-ball labels.

## Results and artifacts

Read [EXPERIMENTS.md](EXPERIMENTS.md) for the recorded results and write-up of every
experiment. Each generated run also contains:

- `protocol.json`: fixed experiment graph, settings, input/source fingerprints.
- `step05_reference/`: independently generated step 05 baseline.
- One directory per experiment containing `possession.csv`, `experiment.json`,
  and the official `possession.scores.json`.
- `summary.csv` and `summary.json`: scores, parent/baseline deltas, dead-ball
  diagnostics, changed-frame counts, and errors introduced/corrected.
- `REPORT.md`: a generated write-up for every variant, including regressions.

Match-derived outputs under `artifacts/` are ignored by Git. Code, synthetic
tests, and aggregate write-ups remain versionable. Runs refuse existing output
directories; failed runs clean up their temporary files.

## Code organization and checks

- `features.py`, `feature_data.py`: tracking-derived distances, motion and quality.
- `smart_tags.py`, `tag_features.py`: automatic phase and restart evidence.
- `temporal.py`, `control.py`, `dead_ball.py`, `prediction.py`: prediction rules.
- `experiment_spec.py`, `experiments.py`, `prediction_policy.py`: fixed protocol.
- `runner.py`, `evaluation.py`, `reporting.py`: execution, step 06 scoring, reports.
- `tests/`: synthetic behavior and end-to-end harness tests.

This research folder is the user-requested exception to the production `src/`
layout. The orchestration layer calls the public step 05/06 interfaces; prediction
modules do not call pipeline steps. No production pipeline is modified.

```bash
.venv/bin/python -m pytest playground/tests -q
.venv/bin/python -m black --check playground
```

## Interpretation

Public-window improvements are descriptive, not verified full-match gains.
The public five minutes contain only 17 possessions. The organisers reserve them
for correctness checks, not training or tuning; manually labelling this match
for training or validation is also disallowed. Further parameter selection needs
permitted data from other games. See the
[competition rules](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md)
and [possession definition](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/CHALLENGE.md).
