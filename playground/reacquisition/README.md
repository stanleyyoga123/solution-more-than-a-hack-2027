# Impossible player reacquisition experiments

The possession-error investigation found an apparent identity discontinuity:
a goalkeeper slot disappeared, then reappeared near the opposing goalkeeper
at a location it could not reach within the elapsed time. This batch tests
a general inference-time exclusion rule, preserving the original tracking.

The [diagnosis and results](../POSSESSION_ERROR_ANALYSIS.md) explain why these
rules fix the inspected turnover but remain unsuitable as a general replacement
for the strongest spellF1 candidate.

```bash
.venv/bin/python -m playground.reacquisition \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_reacquisition_run \
  --review-range 15641 15766 \
  --review-range 15889 16400
```

Tracking, metadata, and Smart Tagging XML default to the original tactical
recording. Override them with `--tracking`, `--metadata`, and `--tags` using
the same timeline. Review ranges are optional, end-exclusive diagnostics and
never enter inference. Use a fresh output directory.

## Rule and comparisons

For each eligible player, the first continuous observed run is trusted.
After a missing interval, calculate the distance from the last trusted sample
to the first reacquired sample, divided by actual elapsed time. If the required
average speed exceeds the existing **12 m/s** bound, exclude the entire new
continuous run from possession evidence. Rejected samples never advance the
trusted anchor. A later plausible run can establish a new anchor.

This tests gaps only; consecutive-frame jumps are a different failure mode.
The rule contains no target frame numbers, player IDs, possession labels, or
manually annotated video input. It neither imputes coordinates nor changes
team identities. Goalkeeper eligibility comes from XML `position_type` values,
resolved by player ID into the actual tracking-slot order.

The follow-up `--split-discontinuities` mode also splits observed runs at
consecutive jumps exceeding the same speed bound. It quarantines these
physically continuous segments separately, allowing a later reachable segment
to restore the trusted path. This addresses the audit finding that an otherwise
continuous observed run can contain an identity jump back to the correct player.
No new speed threshold is introduced. This mode uses experiment IDs t00–t05
with the same parent comparisons as q00–q05 below.

```bash
.venv/bin/python -m playground.reacquisition \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_tracklet_run \
  --split-discontinuities \
  --review-range 15641 15766 \
  --review-range 15889 16400
```

| ID | Parent | Change |
| --- | --- | --- |
| q00 | None | Existing f03 reference. |
| q01 | q00 | Existing p07 collective-stoppage rule. |
| q02 | q00 | Apply post-gap quarantine to all players. |
| q03 | q02 | Restrict quarantine to metadata-labelled goalkeepers. |
| q04 | q02 | Add the unchanged collective-stoppage rule. |
| q05 | q03 | Add the unchanged collective-stoppage rule. |

Every new comparison changes one component relative to its named parent. The
quarantine threshold is inherited from the existing domain policy, with no
parameter sweep. All player-dependent evidence is rebuilt after exclusion:
physical and arrival distances, nearest-team codes, quality distances/codes,
nearest-player speed, collective median speed, and visible-player count.
Original ball observations and their motion features remain unchanged.

## Artifacts and verification

Each run writes a fixed protocol with input/source hashes, all six predictions
and their hashes before scoring, and the unchanged step 06 scores. Every variant
also has `quarantine_audit.json`, `stoppage_audit.json`, `experiment.json`, and
`review.json`. The quarantine audit records each excluded slot/run, trusted
anchor, displacement, elapsed time, and required speed. Ends are exclusive.

`summary.csv`, `summary.json`, and `REPORT.md` preserve all comparisons and
regressions. Source assets and previous output directories are preserved;
failures clean temporary exports. Match-derived artifacts are Git-ignored.
No candidate is automatically promoted or copied over the viewer default.

```bash
.venv/bin/python -m frontend \
  --predictions playground/artifacts/my_reacquisition_run/q05_goalkeepers_and_stoppage/possession.csv

.venv/bin/python -m pytest playground/reacquisition/tests -q
.venv/bin/python -m black --check playground/reacquisition
```

An incorrect trusted anchor can cause valid subsequent observations to be
discarded. Physically plausible identity swaps remain undetected, and an
entire long continuous run can be excluded after one bad reappearance.
These limitations must be evaluated alongside gains in the inspected clips.
This investigation is exploratory debugging on already-known public errors,
not an independent holdout result. See the
[preceding control/stoppage batch](../possession_fixes/README.md).
