# Refining interception-based possession

This batch builds on the earlier c05 interception race. It tests short ball
forecasts, causal robust velocities, acceleration-limited arrival times, and
alternative control/stoppage continuity rules. Each experiment changes one
component relative to its named parent; combinations are declared before scoring.
Read [the experiment write-up](../REFINEMENT_EXPERIMENTS.md) for every result and
the limitations of the strongest candidates.

Run from the repository root:

```bash
.venv/bin/python -m playground.refinement \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_refinement_run
```

Tracking, metadata and automatic tactical tags default to the original tactical
assets under `data/tactical/`. Override them with `--tracking`, `--metadata` and
`--tags`. This batch requires no detector weights or previous experiment outputs.
The public ground-truth CSV is the one used by the earlier experiment batches.
Use a fresh output directory; an existing run is never overwritten.

## Fixed experiment graph

| Variant | Parent | Single change |
| --- | --- | --- |
| r00 | None | Original step 05 reference. |
| r01 | r00 | Previous c05 reference anchor, not a one-component ablation. |
| r02 | r01 | Short causal ball forecasting. |
| r03 | r01 | Robust trailing velocity instead of one-frame differences. |
| r04 | r03 | Acceleration-limited reachability instead of a projected-point race. |
| r05 | r01 | Brief uncertainty allowed during control confirmation. |
| r06 | r01 | Same-team continuity through purely missing-ball D runs. |
| r07 | r01 | Persistence of an explicit boundary stoppage. |
| r08 | r02 | Robust velocity. |
| r09 | r02 | Tolerant control confirmation. |
| r10 | r02 | Boundary persistence. |
| r11 | r08 | Tolerant control confirmation. |
| r12 | r08 | Boundary persistence. |

The numerical hypotheses live in `policy.py`, `control_policy.py`, and the
existing `CreativePolicy`/`DomainPolicy`. There is no threshold sweep or
score-dependent branch generation. All thirteen submissions and their SHA-256
fingerprints are written before the evaluation code reads possession labels.
Both reference anchors are checked, and each submission is scored by step 06.

## Methods and limits

- **Forecasting** reuses the earlier maximum 0.5-second constant-velocity forecast
  from original ball observations. Original finite positions are preserved.
- **Robust motion** uses a trailing 0.2-second componentwise median of plausible
  velocity differences. Missing observations clear that entity's velocity
  history. Unavailable motion contributes zero velocity, as in the prior model.
- **Reachability** evaluates the predicted ball path at 0.1-second intervals
  through two seconds. Players retain forward movement during a 0.2-second
  reaction period, then accelerate at 3 m/s² up to 7 m/s. Contact within one metre
  has zero arrival time. The terminal fallback assumes a fixed last target.
  Arrival seconds are multiplied by 7 m/s to supply distance-equivalent evidence;
  these are not measured player-to-ball distances or calibrated capabilities.
- **Tolerant confirmation** keeps the earlier 0.4 seconds of required opposing
  evidence but permits up to 0.12 seconds of consecutive uncertainty within a
  0.8-second window. Incumbent evidence and explicit stoppages reset pending
  handovers. Confirmed switches are backdated to their first supporting frame.
- **Occlusion bridging** fills a D run of at most eight seconds only when the
  same live team bounds it, every ball observation is missing, and no restart or
  explicit stoppage cue overlaps. It fills labels, not ball coordinates.
- **Boundary persistence** begins only from a sustained observed out-of-pitch
  cue. It releases after 0.2 seconds of observed in-pitch movement or close-team
  arrival evidence, with a maximum 30-second retention after the last cue.

Velocity estimation is causal, but the whole pipeline remains offline because
of smoothing, gap filling and backdated confirmation. In particular, missing
observations alone cannot determine whether a real stoppage occurred.

## Outputs and checks

The run publishes `protocol.json`, `frozen_predictions.json`, `summary.csv`,
`summary.json`, and `REPORT.md`. Each variant owns its `possession.csv`, official
score JSON, configuration and inference diagnostics. Failed runs remove temporary
exports. Logs go to stderr; stdout contains the completed report path.

```bash
.venv/bin/python -m pytest playground/refinement/tests -q
.venv/bin/python -m black --check playground/refinement
```

The report preserves every result, including regressions. The same five-minute
public correctness window has already been examined in earlier batches, so these
comparisons are exploratory rather than a fresh holdout estimate of full-match
performance. No winner is automatically promoted into the production pipelines.
