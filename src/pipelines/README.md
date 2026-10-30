# Pipeline guide

Each numbered folder owns an independently runnable pipeline and its detailed
README. See the [dependency diagrams](../../README.md#pipeline-dependencies)
for the file flow, and the [project README](../../README.md) for setup, assets,
the viewer and repository-wide checks.

## Pipeline index

| Step | Input | Output |
| --- | --- | --- |
| [`01_populate_pixels`](01_populate_pixels/README.md) | ATD text, XML, homography CSV | `tracking_pixels.csv` and metadata JSON |
| [`02_normalize_2d`](02_normalize_2d/README.md) | ATD text and XML | `tracking_normalized_2d.csv` and metadata JSON |
| [`03_render_2d_tactical_video`](03_render_2d_tactical_video/README.md) | Step 02 CSV and metadata JSON | `tactical_2d_tracking.mp4`, an animated pitch map |
| [`04_render_birdseye_tactical_video`](04_render_birdseye_tactical_video/README.md) | Original video, homography CSV, XML | `tactical_birdseye.mp4`, warped footage |
| [`05_possession_baseline`](05_possession_baseline/README.md) | ATD text and XML | `possession_baseline.csv` submission and metadata JSON |
| [`06_score_submission`](06_score_submission/README.md) | Any submission CSV and a ground-truth CSV | `<submission>.scores.json` with the official metrics |
| [`07_flag_impossible_trajectories`](07_flag_impossible_trajectories/README.md) | Normalized CSV and its metadata JSON | `tracking_trajectory_flags.csv` and metadata JSON |
| [`08_assess_identity_continuity`](08_assess_identity_continuity/README.md) | Normalized CSV, metadata, and step 07 reports | `tracking_gap_continuity.csv` and metadata JSON |
| [`09_possession_inference`](09_possession_inference/README.md) | Tactical ATD and XML | `possession_inference.csv` submission and metadata JSON |

## Running pipelines

All input paths are required arguments. `--output-dir` defaults to `output`.
Supply assets from the same recording; tactical and broadcast timelines are
independent. There is no `recording_id` column or implicit match selection.
Run the commands one by one: pipelines do not call or execute other pipelines.

CLI logs are timestamped and sent to stderr, while stdout contains only the
published output paths. Logs describe the input files, loading and writing
stages, then report processed frames, rows and elapsed seconds after publication.
Interactive terminals show a `tqdm` frame progress bar; redirected runs use
occasional progress log messages. Reusable pipeline calls use the caller's
logging configuration. Progress displays close on failure, and failed exports
do not emit a completion message.

Inputs are assumed to be valid and follow the supplied EPTS/ATD/CSV formats,
including aligned frame sequences and normalised x,y channels. Readers parse
these inputs directly, without schema layers, frame-count audits or defensive
dataset validation. Missing observations, `NaN` and homography `valid=0` are
normal data states and retain the semantics documented by each step. Native
parsing or I/O errors can surface.

## Shared tracking export format

Steps [01](01_populate_pixels/README.md) and
[02](02_normalize_2d/README.md) use the following CSV and metadata conventions.

Each CSV is ordered by frame, then by XML channel-reference slot order, followed
by the ball. Every slot is written on every frame, including missing observations.

| Column | Meaning |
| --- | --- |
| `frame` | Zero-based original recording/video frame; source ATD ID minus one. |
| `entity_id` | `player_` plus XML tracking ID, or `ball`. |
| `entity_type` | `player` or `ball`. |
| `team_id` | Source XML team ID; blank for the ball. |
| `pos_x`, `pos_y` | Original-video pixels or normalised pitch fractions, according to the export. |
| `speed_raw` | Unmodified source s value, independently of missing positions/calibration. |
| `position_valid` | `True` only when both exported coordinates are finite. |
| `homography_valid` | Pixel export only: whether the supplied transform is valid. |
| `reprojection_error` | Pixel export only: source calibration fit error, repeated for each entity. |

Missing numeric values are blank CSV cells. There is no filling, interpolation,
clamping, smoothing, derived angle or derived speed. Labels identify tracking
slots, not verified shirt numbers or persistent real-world identities. The XML
declares the s channel as `kph` in the delivered data. Metadata preserves that
declaration; the source documentation's conflicting speed claims are not
resolved here, and projecting positions does not convert the raw speed units.

Each metadata JSON records frame rate, physical pitch dimensions, position
coordinate space and units, x-right/y-down orientation, raw speed unit, source
team mapping, frame/row/slot counts, entity order, indexing and missing-value
semantics. Normalised coordinates retain their source orientation, without
flipping team attacking directions. Valid calibration is not a guarantee of
tracking accuracy or player visibility.

A full tactical export contains 199,319 frames × 47 entities = 9,367,993 rows per
CSV; each CSV is several hundred megabytes. Allow sufficient disk space.
The two exports independently read the source ATD; they do not round-trip
through each other's coordinates.

Existing destination files, including symlinks, are rejected: use a fresh output
directory for a rerun. Both artifacts are staged completely before publication;
a failed run cleans up staged files and any partially published pair. No input
or existing output is overwritten.

## Development checks

Install the formatter and tests with `uv sync --group dev --extra test`.
Format changed Python files with `python -m black <paths>` and verify them with
`python -m black --check <paths>`. Black uses 88-character lines and targets
Python 3.12. Split long strings and complicated expressions for readability even
when the formatter does not do so automatically.

Run the maintained pipeline and export/logging checks:

```bash
.venv/bin/python -m pytest tests/src/pipelines \
  tests/src/utilities/test_pipeline_exports.py \
  tests/src/utilities/test_pipeline_logging.py
```

The legacy `tests/src/utilities/test_utility.py` references a removed exploratory
module and is excluded from these checks.
