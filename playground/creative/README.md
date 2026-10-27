# Creative possession experiments

This second batch tries different representations and inference algorithms:
short-horizon ball forecasting, offline interpolation, global state decoding,
anticipated interception, self-supervised ball estimation, and real video-based
ball recovery. See [CREATIVE_EXPERIMENTS.md](../CREATIVE_EXPERIMENTS.md) for every
result, including unsuccessful approaches and spatial diagnostics.

The experiment graph has two reference anchors: c00 reproduces step 05, and c01
reproduces the earlier e05 control-confirmation method. Each new experiment c02–c07
branches independently from c01 and changes one recovery or inference component.
The c01 reference itself combines previously tested components and is explicitly
not presented as a one-component change from c00.

## Run video recovery

The existing project dependencies include Ultralytics, PyTorch, and OpenCV. Obtain
the official pretrained weights and keep them in ignored local storage:

```bash
mkdir -p playground/artifacts/models
curl -fL \
  https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt \
  -o playground/artifacts/models/yolo11n.pt

.venv/bin/python -m playground.vision \
  --video data/tactical/BAR-ATH_tactical-002.mp4 \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --weights playground/artifacts/models/yolo11n.pt \
  --output-dir playground/artifacts/vision_new
```

The fixed default detector runs on CPU at image size 1280, sampling missing-ball
frames every 25 frames and 200 observed-ball controls spread across the recording.
No public possession labels determine sampling, thresholds, or detector inputs.
The recorded full scan took 439.72 seconds on the development machine. This is
sparse inference across the full video, not inference on every frame.

Read [the vision guide](../vision/README.md) for proposal selection, temporal
association, cached replay, and the flat-pitch projection limitation. A cached
detection replay avoids repeating expensive inference when testing association
correctness. Newly generated recovery includes the final association logic.

## Run all creative branches

```bash
.venv/bin/python -m playground.creative \
  --vision-recovery playground/artifacts/vision_new/recovered_ball.csv \
  --ground-truth output/experiments/imputation_possession/ground_truth.csv \
  --output-dir playground/artifacts/creative_new
```

Tracking, metadata, and Smart Tagging paths default to the tactical assets above;
pass `--tracking`, `--metadata`, or `--tags` to change them. The ground-truth path
is the public file downloaded during the earlier comparison. Use a fresh output
directory for each run. Recovery requires the adjacent `recovery.metadata.json`
so its coverage, model fingerprint, policy and limitations accompany the result.

The runner records its policy and source/input fingerprints, generates every
submission, independently verifies both reference anchors, then invokes the
existing step 06 scorer. Each branch writes its configuration, submission, full
score JSON, and diagnostics. Ball-recovery branches also write their proposed
positions in pitch metres. The batch publishes `summary.csv`, `summary.json`, and
a detailed `REPORT.md` together after success; failures remove temporary outputs.

## Methods and validation

- **Causal forecasting:** extrapolate original observed velocity for at most
  0.5 seconds, never extending a chain from predicted positions. Spatial masking
  checks compare with clean supplied ball observations in the final 20% of time.
- **Bidirectional interpolation:** fill only complete short gaps whose original
  endpoint velocities agree; reject physically implausible bridges.
- **Viterbi decoding:** infer H/A/D states jointly at 5 Hz with fixed emissions
  and transition penalties. Missing observations are neutral evidence, and
  distant players alone do not imply a stoppage.
- **Interception race:** project the ball 0.3 seconds and compare team arrival
  proxies using player movement. Convert arrival times to distance-equivalent
  units for the existing control decoder; this is not a full physical simulation.
- **Collective geometry:** fit ridge regression from team centres, spreads,
  extents, and counts to observed ball coordinates. Fit only the first 80% of
  time; report spatial errors on later observed balls. Reject unsupported team
  geometry and extreme standardized inputs. No possession labels are training
  targets. This offline estimator is not claimed to be causal.
- **YOLO recovery:** detect sports balls in video, inverse-project candidates,
  require spatial/temporal consistency, and interpolate only short supported
  intervals. Original finite ball observations remain unchanged.

Ball-dependent features are recomputed after recovery while source player
coordinates remain unchanged. Coverage is reported separately from spatial
accuracy and possession scores. All coordinate references are automatic tracking,
not verified video truth; the original tracking files are preserved.

```bash
.venv/bin/python -m pytest playground/creative/tests playground/vision/tests -q
.venv/bin/python -m black --check playground/creative playground/vision
```

The public labels cover five minutes and are a correctness check, not a tuning
set. The earlier public results were known when selecting c01 as the reference,
so this is not a blind holdout study. Thresholds were fixed before this batch's
scores, and no configuration is automatically promoted to production.
