# Creative experiment results

Eight scored variants were executed across the full 199,319-frame recording:
two reference anchors and six independently attributable alternatives. All new
methods and settings were fixed before the batch's public possession scores.
The original step 05 and earlier e05 references were reproduced exactly.

The strongest public ranking result came from **anticipated interception**:

| Reference | spellF1 | macroF1 |
| --- | ---: | ---: |
| Original step 05 | 0.325581 | 0.620733 |
| Earlier e05 control method | 0.422857 | 0.680016 |
| c05 interception race | **0.482353** | **0.690217** |

The spellF1 gain is +0.156772 against step 05 (**48.15% relative**) and +0.059496
against the earlier control method (**14.07% relative**). The public ranking uses
spellF1; causal forecasting had the highest macroF1 in this batch at 0.694318.
These are descriptive results on five minutes, not verified full-match gains.

## Interpretation of every new method

### c02: Causal ball forecasting

Forecasting up to 0.5 seconds from original past velocity filled **1,860 ball
positions** across 184 gap starts. It changed 89 graded predictions, correcting
77 parent errors and introducing 12. spellF1 rose to **0.434286** and macroF1 to
**0.694318**. This supports short motion extrapolation as a useful hypothesis in
this window, without implying that long disappearances can be forecast safely.

On 100 clean masked windows per duration in the final 20% of the recording,
mean error was 0.21 m at 0.2 seconds and 0.65 m at 0.48 seconds; corresponding
95th-percentile point errors were 0.76 m and 2.61 m. Those source-track checks
exclude problematic reference windows and do not reproduce all real occlusions.

### c03: Bidirectional ball interpolation

Only **9 positions across 5 actual gaps** passed the fixed two-second limit,
endpoint prediction agreement and speed checks. No possession predictions changed
relative to the control reference. On masked data, two-second bridges accepted
only 17 of 100 candidate windows, with mean error 0.35 m among accepted cases.
Low conditional error does not compensate for low coverage on the actual gaps.

### c04: Global Viterbi state decoding

Replacing the decoder raised spellF1 to **0.444444**, but macroF1 fell to
**0.564542**. It produced 10 possession spells and recognized only 6.67% of dead
frames. The fixed model often retained a live team through uncertain intervals;
its interval-level improvement comes with a substantial stoppage/frame-label
tradeoff. It is not the strongest overall candidate from this batch.

### c05: Anticipated interception race

Instead of taking the nearest player, this model projects the ball 0.3 seconds
and estimates which team reaches that target first, accounting for current
player movement. Arrival-time proxies are converted to distance-equivalent
control evidence; the control decoder and stoppage rules remain the same.

It changed 227 graded predictions, corrected 140 parent errors and introduced 41.
spellF1 rose to **0.482353**, macroF1 to **0.690217**. It predicted 17 possessions;
matching the reference count alone is not proof of correct intervals and was
never a target used by inference. This is the best public spellF1 within the
fixed batch, not a model automatically selected for deployment.

### c06: Self-supervised ball estimation from team shape

Ridge regression learned ball location from team centres, spreads, extents, and
counts using **16,558 observed training frames** in the first 80% of the timeline.
It filled **53,271 missing ball positions** after geometry and distribution gates.
It read no possession labels.

Coverage increased substantially, but accepted late-period spatial estimates had
**21.15 m mean error** and **36.84 m p95 error** against the supplied automatic ball
track. Possession scores regressed to **0.375000 spellF1 / 0.547125 macroF1**.
Team shape is too ambiguous for this simple model to supply precise ball locations;
this experiment illustrates why filling more nulls is not an accuracy objective.

### c07: Actual YOLO video recovery

YOLO11n was run on **3,638 actual video frames** using CPU, image size 1280 and the
COCO sports-ball class: 3,438 missing-ball samples at one-second spacing across
the full recording, plus 200 evenly distributed observed-ball controls. Inference
and sequential decoding took **439.72 seconds**. This was not a simulated detector
or a scan restricted to the public scoring window.

There were 239 missing-frame pitch proposals. Temporal pairing and original-anchor
gates accepted **162 direct detections**, supporting **3,000 interpolated positions**
for **3,162 total recovered positions**. The 3,125 newly finite adjacent joins had
maximum speed 25.90 m/s, below the fixed 45 m/s gate. These are consistency checks,
not guarantees that detections represent the match ball.

Detector quality remained limited. Of 200 observed controls, 112 had any detection;
54 survived the pitch/ambiguity proposal gates. Only 28 selected candidates were
within 2 m of the source ball. Selected-candidate median error was 1.98 m, but
p90 error was **38.72 m**. The large disagreement could include detector mistakes,
projection error and errors in the source track; no manual ground truth was used.

Recovered coordinates changed 1,693 possession predictions elsewhere in the
recording, but none in the public labelled window. Scores therefore stayed at
**0.422857 / 0.680016**. This does not establish whether the unlabelled changes help.
A soccer-specific small-ball detector, higher-resolution crops, and stronger
association would be separate future experiments, not claimed results here.

## Execution record

- `vision_pilot_1280`: a four-frame runtime smoke test on the first source-selected
  missing frames, before controls or possession scoring. Zero detections; not an
  accuracy benchmark or a score-selection trial.
- `vision_001`: full 3,638-frame inference with raw detection audit retained.
- `vision_002`: 4.31-second replay of cached detections after an association
  correctness fix: rejected anchor candidates must not leave unsupported partners.
  This fixed a synthetic edge case, used the same numerical policy, and did not
  change real-run recovery counts. New direct runs include the fixed logic.
- `creative_001`: all eight frozen submissions scored with the unmodified step 06
  pipeline, with exact step 05 and earlier e05 reference checks. Runtime 26.23 s.
- `vision_003`: final cached replay after independent review exposed an adjacent
  synthetic-join edge case at one-frame sampling. Conflicting endpoints are now
  rejected before pair support is recomputed. The default run's recovery CSV is
  byte-identical to `vision_002`; replay took 4.56 s.
- `creative_002`: full rerun using `vision_003`, taking 26.72 s. All eight
  submission CSVs and all eight official score JSONs are byte-identical to
  `creative_001`. This is the final reproducibility run.

Validation: **156 tests passed**, covering the maintained pipelines, export and
logging utilities, and all playground experiments. Black passed for all 56
playground Python files. Independent correctness and style reviews are complete;
the required motion-association and loading-log fixes were re-reviewed.

The evaluated window contains 7,500 frames, from 11,185 through 18,684 inclusive.
The final best-scoring submission is
`playground/artifacts/creative_002/c05_interception_race/possession.csv`.

All artifacts live under ignored `playground/artifacts/`. Reproduction commands
and code organization are in [creative/README.md](creative/README.md). The complete
per-branch diagnostics follow, including forecasts' acceptance rates and the
collective model's held-out errors.

c00 is the original step 05 baseline. c01 reproduces the earlier e05 control-confirmation reference. Every new method branches independently from c01, replacing one input-recovery or inference component. c01 is a reference anchor, not a new one-component change from c00.

All configurations and predictions were fixed before reading possession labels. The collective model trains on original ball coordinates, not possession labels. All submissions use the existing step 06 scorer.

| Experiment | Change | spellF1 | Δ c01 | macroF1 | D recall | Predicted possessions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| c00_original_baseline | reference | 0.325581 | -0.097276 | 0.620733 | 21.38% | 26 |
| c01_control_reference | reference_anchor | 0.422857 | +0.000000 | 0.680016 | 34.85% | 18 |
| c02_causal_ball_forecast | causal_forecast | 0.434286 | +0.011429 | 0.694318 | 37.64% | 18 |
| c03_bidirectional_ball_bridge | bidirectional_bridge | 0.422857 | +0.000000 | 0.680016 | 34.85% | 18 |
| c04_viterbi_states | viterbi | 0.444444 | +0.021587 | 0.564542 | 6.67% | 10 |
| c05_interception_race | interception | 0.482353 | +0.059496 | 0.690217 | 34.85% | 17 |
| c06_collective_ball_estimate | collective | 0.375000 | -0.047857 | 0.547125 | 6.67% | 15 |
| c07_yolo_ball_recovery | vision | 0.422857 | +0.000000 | 0.680016 | 34.85% | 18 |

## c00_original_baseline: Original step 05 reference

**Parent:** none. **Changed component:** reference.

**Hypothesis:** Reproduce the unmodified nearest-player baseline.

**Method:** The same nearest-team codes and centred 50-frame team-only vote.

**Results:** spellF1 0.325581; macroF1 0.620733; 0 predictions changed versus parent (0 on graded frames). Corrected 0 parent errors and introduced 0 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "baseline",
  "original_observations": true
}
```

## c01_control_reference: Earlier e05 control-confirmation reference

**Parent:** c00_original_baseline. **Changed component:** reference_anchor.

**Hypothesis:** Reproduce the earlier control baseline before branching.

**Method:** This reference includes the previously declared e01-e05 components; it is an anchor, not a claim of a single new component versus c00.

**Results:** spellF1 0.422857; macroF1 0.680016; 35,209 predictions changed versus parent (974 on graded frames). Corrected 471 parent errors and introduced 226 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "control",
  "original_observations": true
}
```

## c02_causal_ball_forecast: Forecast missing ball observations from past motion

**Parent:** c01_control_reference. **Changed component:** causal_forecast.

**Hypothesis:** Brief ball disappearance may be reconstructed from its previous velocity.

**Method:** Use 0.2 seconds of continuous original context and forecast at most 0.5 seconds; reject context speeds over 45 m/s. Keep the control decoder.

**Results:** spellF1 0.434286; macroF1 0.694318; 3,156 predictions changed versus parent (89 on graded frames). Corrected 77 parent errors and introduced 12 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "causal_constant_velocity",
  "filled_frames": 1860,
  "supported_gap_starts": 184,
  "future_observations_used": false,
  "synthetic_context_used": false,
  "masked_spatial_validation": [
    {
      "missing_frames": 5,
      "gap_seconds": 0.2,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 100,
      "rejected_windows": 0,
      "mean_error_m": 0.20505986441261667,
      "p95_error_m": 0.7581707878455882,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    },
    {
      "missing_frames": 12,
      "gap_seconds": 0.48,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 100,
      "rejected_windows": 0,
      "mean_error_m": 0.650537326094793,
      "p95_error_m": 2.6109041978203353,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    }
  ],
  "source_observations_preserved": true
}
```

## c03_bidirectional_ball_bridge: Reconcile past and future ball motion across gaps

**Parent:** c01_control_reference. **Changed component:** bidirectional_bridge.

**Hypothesis:** Offline endpoint agreement can support more missing-ball reconstruction.

**Method:** Bridge original bounded gaps of at most two seconds only when both constant-velocity endpoint predictions agree within five metres and the entire linear bridge stays within the 45 m/s speed bound.

**Results:** spellF1 0.422857; macroF1 0.680016; 0 predictions changed versus parent (0 on graded frames). Corrected 0 parent errors and introduced 0 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "bidirectional_constant_velocity_screened_linear_bridge",
  "filled_frames": 9,
  "accepted_gaps": 5,
  "future_observations_used": true,
  "synthetic_context_used": false,
  "masked_spatial_validation": [
    {
      "missing_frames": 5,
      "gap_seconds": 0.2,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 100,
      "rejected_windows": 0,
      "mean_error_m": 0.05385277523792155,
      "p95_error_m": 0.18430210529305768,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    },
    {
      "missing_frames": 12,
      "gap_seconds": 0.48,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 92,
      "rejected_windows": 8,
      "mean_error_m": 0.17393922496543934,
      "p95_error_m": 0.5567179744549777,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    },
    {
      "missing_frames": 25,
      "gap_seconds": 1.0,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 49,
      "rejected_windows": 51,
      "mean_error_m": 0.20878719579827545,
      "p95_error_m": 0.6845395715827938,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    },
    {
      "missing_frames": 50,
      "gap_seconds": 2.0,
      "time_block": "last_20_percent",
      "evaluated_windows": 100,
      "accepted_windows": 17,
      "rejected_windows": 83,
      "mean_error_m": 0.35149760707588684,
      "p95_error_m": 0.9506334448194418,
      "reference": "Clean supplied ball positions, not verified video truth; errors are conditional on accepted reconstruction."
    }
  ],
  "source_observations_preserved": true
}
```

## c04_viterbi_states: Replace the temporal algorithm with a three-state Viterbi decoder

**Parent:** c01_control_reference. **Changed component:** viterbi.

**Hypothesis:** Global state inference can balance local evidence and transition costs.

**Method:** Decode five evidence bins per second with H/A/D emissions, a fixed team-transfer cost of four and live/dead transition cost of two; expand decoded bins to the source timeline without a final vote.

**Results:** spellF1 0.444444; macroF1 0.564542; 84,775 predictions changed versus parent (1,550 on graded frames). Corrected 525 parent errors and introduced 735 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "global_viterbi_three_states",
  "decoding_hz": 5,
  "trained_on_possession_labels": false
}
```

## c05_interception_race: Replace proximity with an anticipated interception race

**Parent:** c01_control_reference. **Changed component:** interception.

**Hypothesis:** The team likely to reach the moving ball may differ from the nearest team.

**Method:** Project the ball 0.3 seconds along observed velocity and estimate player arrival times at seven metres per second, accounting for current player motion. Keep the existing control decoder and stoppage logic.

**Results:** spellF1 0.482353; macroF1 0.690217; 8,231 predictions changed versus parent (227 on graded frames). Corrected 140 parent errors and introduced 41 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "anticipated_interception_race",
  "nearest_team_changes": 13717
}
```

## c06_collective_ball_estimate: Estimate missing ball locations from collective team geometry

**Parent:** c01_control_reference. **Changed component:** collective.

**Hypothesis:** Team shape can provide a ball-location proxy without possession labels.

**Method:** Fit a fixed-penalty ridge regression on clean observed balls in the first 80% of the recording. Evaluate against observed balls in the last 20%; fill only missing observations with in-distribution geometry. Report spatial prediction errors separately from possession scores.

**Results:** spellF1 0.375000; macroF1 0.547125; 50,771 predictions changed versus parent (1,063 on graded frames). Corrected 278 parent errors and introduced 653 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "collective_ridge_ball_location",
  "status": "fitted",
  "training_frames": 16558,
  "training_end_frame_exclusive": 159455,
  "filled_frames": 53271,
  "missing_rejected_ood_or_geometry": 25372,
  "missing_rejected_outside_pitch": 7188,
  "holdout_all_geometry": {
    "frames": 14050,
    "mean_error_m": 21.071629312052796,
    "median_error_m": 21.1072836586182,
    "p95_error_m": 37.22874301504015
  },
  "holdout_accepted_geometry": {
    "frames": 13388,
    "mean_error_m": 21.15483558899296,
    "median_error_m": 21.379216813993594,
    "p95_error_m": 36.84406243223525
  },
  "target_semantics": "Original observed ball coordinates, not possession labels or verified video truth",
  "causal": false,
  "limitation": "Collective geometry can be consistent with multiple ball locations; estimates are not calibrated observations.",
  "source_observations_preserved": true
}
```

## c07_yolo_ball_recovery: Recover missing ball observations from original tactical footage

**Parent:** c01_control_reference. **Changed component:** vision.

**Hypothesis:** Image evidence may recover balls absent from the supplied tracker.

**Method:** Use a fixed pretrained sports-ball detector and geometric/temporal acceptance checks. Preserve original observations and reuse the same control decoder; detector settings and sampling are recorded separately.

**Results:** spellF1 0.422857; macroF1 0.680016; 1,693 predictions changed versus parent (0 on graded frames). Corrected 0 parent errors and introduced 0 errors.

**Independent coverage / spatial diagnostics:**

```json
{
  "method": "Sparse pretrained YOLO11 sports-ball recovery",
  "inputs": {
    "video": "data/tactical/BAR-ATH_tactical-002.mp4",
    "tracking": "data/tactical/BAR-ATH_tactical_atd.txt",
    "metadata": "data/tactical/BAR-ATH_tactical_atd.xml",
    "homography": "data/tactical/BAR-ATH_tactical_homography.csv",
    "weights": "playground/artifacts/models/yolo11n.pt"
  },
  "weights_sha256": "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1",
  "policy": {
    "sample_stride": 25,
    "max_control_frames": 200,
    "image_size": 1280,
    "confidence": 0.25,
    "confidence_margin": 0.1,
    "pitch_padding_m": 2,
    "maximum_speed_mps": 45,
    "anchor_seconds": 1,
    "anchor_padding_m": 2,
    "interpolation_seconds": 1.2,
    "maximum_samples": 0,
    "cpu_threads": 4
  },
  "fps": 25.0,
  "frame_count": 199319,
  "sampled_frames": 3638,
  "missing_ball_samples": 3438,
  "observed_control_frames": 200,
  "observed_controls_with_any_detection": 112,
  "control_raw_top_confidence": {
    "projected_detections": 112,
    "median_error_m": 23.08483075178082,
    "p90_error_m": 61.28597857044501,
    "p95_error_m": 66.72241031331164,
    "within_2m": 27,
    "within_5m": 30
  },
  "control_unambiguous_pitch_candidate": {
    "projected_detections": 54,
    "median_error_m": 1.9770723892911701,
    "p90_error_m": 38.717867543149254,
    "p95_error_m": 46.18908372926302,
    "within_2m": 28,
    "within_5m": 30
  },
  "missing_samples_with_pitch_proposal": 239,
  "accepted_yolo_observations": 162,
  "interpolated_positions": 3000,
  "recovered_positions": 3162,
  "rejections": {
    "no_temporal_pair": 77
  },
  "elapsed_seconds": 439.7146070000017,
  "limitations": [
    "COCO sports-ball detections are not a soccer-specific ball model.",
    "Pixel centres are projected onto the pitch plane; airborne balls can have inaccurate pitch coordinates.",
    "Observed-control errors compare with automatic source tracking, not manually verified video truth.",
    "Sparse sampling can miss fast contacts and brief ball visibility.",
    "No possession labels or score results enter recovery."
  ],
  "source_detection_run": "playground/artifacts/vision_001",
  "association_source_sha256": {
    "__init__.py": "5b670d259a5f56792c19b46ff1c284bb918a7de8a0b86477321b6f688e9c2d4e",
    "__main__.py": "cfce742cb6da5b630337704c7815015f839c27f197af78a62dff926791673be7",
    "artifacts.py": "c9d176f56ed6160400d69a87fedbf6a117bdab248206303993e170a44887a76c",
    "association.py": "3de7148eaf4528413c3b56249fb9ce79f4896686d03af79bc81b52d4e0794080",
    "detection.py": "2711ea29d9172f6bb991393ddc3414bdfd49bc7334d3c7c6ba6cfddf32a59a1b",
    "detector.py": "5c220f90b68200acc2b5e1ea42c2975eb271df7b783ae1de66c332099dc3214a",
    "inputs.py": "e9a73c1c9ef03f5e393c7df011e68a84a1e0d00d7bc06f4eda9c5cb59a2426b9",
    "policy.py": "723369e5e911eb833025e3ac8352666f500af21b3f635bc50d91561c68920a1a",
    "reassociate.py": "ce188eeae99d81769ca3cad82bcc5e846b42e05448a2f2a066b9e4baec8af526",
    "recovery.py": "d92eaaaecc33ca7179078e90ffdfdef80ff97bb26b882090415b310426ffa3d6"
  },
  "reassociation_seconds": 4.545256083001732,
  "filled_frames": 3162,
  "source_observations_preserved": true
}
```

## Interpretation limits

The public labels cover only five minutes of one match. Results are descriptive; no model is automatically promoted and no settings are optimized against these scores. The earlier public results were already known when choosing c01 as the reference, so this is not a blind holdout study.

Spatial checks compare with the supplied automatic ball track, not verified video truth. Better reconstruction and better possession labels are different objectives. Forecasts cannot identify unobserved kicks; team shape need not determine ball location; generic sports-ball detections can be false positives and pitch projection assumes a ground-level ball. Missingness is not random, so errors on visible control frames may understate errors during actual occlusions.
