# Smart Tagging restart experiments

This batch tests whether restart-specific context improves possession intervals
relative to the earlier r06 interception and occlusion model. All methods are
fixed before scoring, each comparison changes one component relative to its
named parent, and failed hypotheses remain in the report.

The [recorded results](../RESTART_EXPERIMENTS.md) cover two reproducible full runs.
None of the nine new variants improved the previous best spellF1; s08 improved
frame-level macroF1 and is available for inspection in the frontend.

```bash
.venv/bin/python -m playground.restarts \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/my_restart_run
```

The original tactical tracking, XML metadata and Smart Tagging XML under
`data/tactical/` are defaults. Pass `--tracking`, `--metadata` or `--tags` to
choose other inputs from the same timeline. No existing experiment outputs,
detector weights or video inference are required. The ground truth is the public
CSV used for earlier experiments. Use a fresh output directory for every run.

## Fixed comparisons

| ID | Parent | Change |
| --- | --- | --- |
| s00 | None | Reproduce original step 05. |
| s01 | s00 | Previous r06 reference anchor, not a single-component ablation. |
| s02 | s01 | Mark entire recognized restart windows D: a coarse diagnostic. |
| s03 | s01 | Add observed stationary evidence at type-compatible locations. |
| s04 | s03 | Hold the first confirmed stoppage until observed restart motion. |
| s05 | s04 | Backtrack through up to eight seconds of compatible uncertainty. |
| s06 | s04 | Also allow observed boundary entry for boundary restart types. |
| s07 | s04 | Allow a slower restart when an observed player is nearby. |
| s08 | s04 | Inject the inferred mask into the possession state machine. |
| s09 | s06 | Add bounded backward extension to boundary-capable inference. |
| s10 | s01 | Bridge short unsupported live islands between two D intervals. |

## How event evidence is used

The XML has 59 set-piece windows: 26 throw-ins, 12 corners, 10 goal kicks,
five free kicks, and six kickoffs. Most windows span exactly 35 seconds;
kickoffs span five seconds. Their bounds are event context, not verified
dead-ball boundaries. There is no explicit foul or ball-out event class.

`policy.py` holds fixed geometry and timing hypotheses. Stationary entry
requires at least 0.4 seconds of observed ball speed no greater than 1 m/s.
Throw-ins require proximity to a touchline, corners to a corner, goal kicks to
the goal area, kickoffs to the centre, and free kicks to the pitch. Unknown
event types are ignored; an unknown team does not prevent stoppage inference.

The persistent variants use the first qualifying seed per event. Missing
observations can retain a confirmed stoppage but cannot initiate or release it.
Release requires 0.2 seconds of plausible observed in-pitch motion at least
2 m/s, with its start backdated after confirmation. The control-release variant
also accepts at least 0.8 m/s with a player within two actual metres. Release is
searched only after seed confirmation. Retention ends at the event boundary or
20 seconds after the seed, whichever comes first.

Optional backward extension crosses only missing or stationary geometry-compatible
observations and may precede the event window by a bounded amount. Optional
boundary entry requires 0.2 seconds at least 0.25 m outside the pitch, with
compatible throw-in/corner/goal-kick geometry. It does not apply to free kicks
or kickoffs. Overlapping event masks are combined by union.

The detector always receives **original coordinates and geometric distances**.
Arrival-equivalent distances are used only by the existing possession decoder.
The state-injection variant clears the incumbent at inferred stoppages, while
the other detector variants overwrite final labels with D. The s10 alternative
changes only live islands of at most two seconds bounded by D inside one event,
rejecting bridges with observed movement or nearby-player evidence.

## Outputs and verification

Every variant writes a frontend-compatible `possession.csv` (`frame,label`),
official score JSON, configuration, and inference diagnostics. Detector variants
also expose masks as `dead_intervals.csv`; its end column is explicitly
**exclusive**. Per-event diagnostics record rejected events, inferred boundaries,
entry type and release reason. CSV submission frames are zero-based video frames.

The batch writes source/input fingerprints and fixed settings in `protocol.json`,
an automatic tag inventory, all predictions and their hashes before reading
possession ground truth. It verifies step 05 and r06 references and evaluates
each submission through the existing step 06 scorer. The final directory includes
`summary.csv`, `summary.json`, and a write-up of every comparison in `REPORT.md`.
Existing outputs are preserved; failures remove temporary exports. Logs go to
stderr and the completed report path goes to stdout.

To inspect any candidate:

```bash
python -m frontend \
  --predictions playground/artifacts/my_restart_run/s04_seeded_restart_state/possession.csv
```

The runner does not overwrite `output/prediction.csv` or change a running viewer.

```bash
.venv/bin/python -m pytest playground/restarts/tests -q
.venv/bin/python -m black --check playground/restarts
```

The same five-minute public correctness window has been used in earlier work.
Prior results informed the hypotheses, so these are exploratory comparisons,
not a fresh holdout assessment. Automatic tags can be wrong, and a physically
compatible stationary ball does not prove the referee stopped play. Performance
on unlabelled portions of the match remains unknown.
