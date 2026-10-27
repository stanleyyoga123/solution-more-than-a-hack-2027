# Sparse YOLO ball recovery

This experiment asks whether a pretrained detector can recover ball observations
that the supplied automatic tracker missed. It uses the original tactical video,
the original tracking's missingness mask, and inverse homography. Possession
labels are never read by this package.

The fixed initial configuration uses YOLO11n's COCO sports-ball class (32),
full-frame inference at image size 1280, confidence 0.25, and four CPU threads.
It samples missing-ball frames every 25 frames (one second at the source FPS),
plus 200 evenly spaced observed-ball controls across the recording. The controls
are selected by source visibility rather than possession labels.

## Run

The weights used by the experiment are the official
[Ultralytics YOLO11n weights](https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt).
Pass an existing local file; inference does not intentionally download weights.

```bash
.venv/bin/python -m playground.vision \
  --video data/tactical/BAR-ATH_tactical-002.mp4 \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --weights playground/artifacts/models/yolo11n.pt \
  --output-dir playground/artifacts/my_vision_run
```

The video is decoded sequentially; images are retrieved and inferred only at
selected frames. `--max-samples 4` performs a source-selected runtime pilot.
`--sample-stride`, `--max-control-frames`, and `--image-size` are recorded in the
output policy. Use a fresh output directory for every run.

## Association and outputs

Each detection's box centre is projected from image pixels into normalized pitch
coordinates, then converted to metres. Candidates more than two metres outside
the pitch are rejected. The best eligible candidate must beat the next eligible
candidate by at least 0.1 confidence.

Recovery requires a physically compatible detection pair within 1.2 seconds,
with speed at most 45 m/s. Nearby original ball anchors constrain proposals;
immediate joins have a strict speed check. Pair support is checked again after
anchor filtering so rejected detections cannot support a remaining singleton.
Separate supported pairs are also checked for conflicting consecutive recovered
observations. Both observations at an excessive-speed join are rejected, then
pair support is recomputed so the rejection cannot leave unsupported singletons.
Linear interpolation is allowed only between accepted detections when every
source ball observation inside the interval is missing. Original observed
positions are always preserved.

- `recovered_ball.csv`: source frame, pitch metres, detector/interpolation source,
  and detector confidence. Confidence is a detector score, not calibrated
  coordinate or possession accuracy.
- `detections.csv`: every raw proposal and selection/association decision,
  including samples with no detection.
- `recovery.metadata.json`: effective policy, model checksum, sampling counts,
  accepted/rejected counts, runtime, and observed-control diagnostics.

The control report includes raw top-confidence projection errors before motion
association and errors after the pitch/ambiguity candidate selection. Errors
compare with automatic source tracking, which can itself be wrong.

Cached detector evidence can be reassociated without decoding or inference:

```bash
.venv/bin/python -m playground.vision.reassociate \
  --detection-run playground/artifacts/my_vision_run \
  --output-dir playground/artifacts/my_reassociated_run
```

This is also how the original full detector run is retained while applying a
tested pair-support bug fix. The new metadata records its source detection run
and association source hashes. The expensive detector output remains fixed.

## Limits and tests

Generic COCO detection may struggle with a ball only a few pixels wide. Sparse
sampling misses short contacts. Inverse homography assumes the pitch plane, so
an airborne ball can be projected to an incorrect field location. Recovery
coverage alone is therefore insufficient evidence of better possession scoring;
the parent experiment harness evaluates the resulting predictions with step 06.

```bash
.venv/bin/python -m pytest playground/vision/tests -q
.venv/bin/python -m black --check playground/vision
```
