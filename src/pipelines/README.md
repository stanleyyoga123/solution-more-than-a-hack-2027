# Tracking exports and tactical video

The first two steps independently export the same supplied ATD observations.
The third renders a normalized CSV and its metadata as a top-down tactical video.
The fourth warps the original footage into a top-down pitch view using homography.
Steps 07 and 08 produce trajectory flags and same-slot gap-continuity assessments
from the normalized tracking export.
Each numbered package owns one pipeline; shared readers and export helpers live in
`src/utilities/`. Production imports stay inside `src/`.

Generated data is available in the
[Google Drive folder](https://drive.google.com/drive/folders/1BuxSs5RT_My3yr1fbt8TtAzbFK5tiay5).
Place downloaded artifacts in `output/` to reuse them. The video examples below
render from source time **0 seconds** through the end of the recording, keeping
the rendered-video timeline aligned with the original footage.

```text
src/
├── pipelines/
│   ├── 01_populate_pixels/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   ├── 02_normalize_2d/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   ├── 03_render_2d_tactical_video/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── pipeline.py
│   │   ├── metadata_reader.py
│   │   ├── normalized_reader.py
│   │   └── pitch_renderer.py
│   ├── 04_render_birdseye_tactical_video/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── pipeline.py
│   │   ├── birdseye_renderer.py
│   │   └── frame_reader.py
│   ├── 05_possession_baseline/
│   ├── 06_score_submission/
│   ├── 07_flag_impossible_trajectories/
│   ├── 08_assess_identity_continuity/
│   └── 09_correct_tracking/
└── utilities/
    ├── atd_reader.py
    ├── epts_metadata.py
    ├── export_files.py
    ├── homography_reader.py
    ├── video_encoder.py
    └── video_timing.py
```

Run from the repository root with the project's Python environment:

```bash
.venv/bin/python -m src.pipelines.01_populate_pixels \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --output-dir output

.venv/bin/python -m src.pipelines.02_normalize_2d \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --output-dir output
```

All input paths are required arguments. `--output-dir` defaults to `output`.
Supply assets from the same recording; tactical and broadcast timelines are
independent. There is no `recording_id` column or implicit match selection.
Run the commands one by one: pipelines do not call or execute other pipelines.
The first two read the original ATD independently. Step 03 takes the normalized
artifacts produced by step 02, so run step 02 before invoking step 03.
Step 04 reads original recording assets and does not require steps 01–03.

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
normal data states and retain the semantics described below. Native parsing or
I/O errors can surface.

The pixel pipeline writes `tracking_pixels.csv` and
`tracking_pixels.metadata.json`. It applies each frame's supplied homography to
normalised pitch x,y and divides by the homogeneous denominator to obtain
original-video pixel coordinates. Invalid calibration leaves both pixel
coordinates blank, with `homography_valid=False`. Undefined or nonfinite
projections also leave both coordinates blank. Finite offscreen pixel positions
are preserved. No video decoding or visibility inference is required. The
pitch-plane assumption can misplace airborne objects.

The 2D pipeline writes `tracking_normalized_2d.csv` and
`tracking_normalized_2d.metadata.json`. Raw ATD x,y are already normalised pitch
fractions, so it copies them directly. It has no dependency on homography and
retains positions from frames with invalid calibration. Finite coordinates
outside 0..1 and finite components of partially missing positions are retained.
These files are independent views of source observations, rather than an inverse
pixel-to-pitch round trip.

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

Steps 01–04 stream inputs with memory bounded by one frame. A full
tactical export contains 199,319 frames × 47 entities = 9,367,993 rows per CSV;
allow sufficient disk space. Each pipeline reads ATD separately to avoid losing
normalised observations when calibration is unavailable.

Existing destination files, including symlinks, are rejected: use a fresh output
directory for a rerun. Both artifacts are staged completely before publication;
a failed run cleans up staged files and any partially published pair. No input
or existing output is overwritten.

For Python callers, the corresponding modules expose:

```python
from pathlib import Path
from importlib import import_module

populate_pixels = import_module("src.pipelines.01_populate_pixels").run_pipeline
normalize_2d = import_module("src.pipelines.02_normalize_2d").run_pipeline

# Both functions return (csv_path, metadata_json_path).
pixel_files = populate_pixels(tracking, metadata, homography, Path("output"))
normalized_files = normalize_2d(tracking, metadata, Path("output"))
```

## Render a top-down tactical video

After exporting normalized tracking, render the full recording from 0 seconds:

```bash
.venv/bin/python -m src.pipelines.03_render_2d_tactical_video \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --output-dir output \
  --start-seconds 0
```

Step 03 writes `output/tactical_2d_tracking.mp4`. FFmpeg must be installed on
`PATH` with the `libx264` encoder. No additional Python dependencies are needed.
The output is a silent 1280×720 H.264 MP4 at the metadata's source frame rate,
using `yuv420p`, CRF 20, the `veryfast` preset and `faststart` playback metadata.
It uses normalized CSV observations directly and needs no original video,
homography, audio or ATD/XML files.

`--start-seconds` defaults to zero; omit `--duration-seconds` to render through
the end of the recording. Times refer to elapsed source recording time, not the
scoreboard clock. The start frame is `floor(start_seconds × fps)`; a requested
duration selects `ceil(duration_seconds × fps)` frames, clipped at the recording
end. Start must be finite and nonnegative, duration must be finite and positive,
and the selected interval must contain at least one frame. The on-screen header
shows the original source frame number and recording timestamp even when the
encoded clip begins later in the recording.

Input CSV columns used are `frame`, `entity_id`, `entity_type`, `team_id`, `pos_x`
and `pos_y`. Metadata supplies `fps`, `frame_count`, `pitch_dimensions` with
`length` and `width` in metres, and the ordered `teams` mapping. The reader streams
the frame-major CSV, skipping earlier frames and retaining only the selected
frame's observations in memory. It does not audit or revalidate source schemas.

The static pitch uses the physical length-to-width ratio, with white pitch
markings and goals, plus a five-metre margin. Normalized x increases rightward
and y downward. Team colours are stable in metadata order: blue, then red. Player
markers carry the numeric tracking-ID suffix; these labels are not verified
jersey numbers or persistent player identities. The ball is yellow. Missing or
nonfinite coordinates have no marker, with explicit missing-ball and empty-frame
notes. Finite off-pitch positions retain their coordinates and can appear within
the five-metre margin. Positions beyond the drawable map are clipped from view;
they are never moved onto a boundary. Marker shapes and labels also stay inside
that map, leaving the header and legend clear. No interpolation or trails are
added.

The MP4 is staged under the output directory and published only after FFmpeg
finishes successfully. Existing destinations and symlinks are refused. Failed
rendering, encoding or publication cleans up temporary output and does not emit
a completion message. Encoder stderr is included in encoding errors. Console
logging and terminal/redirected progress follow the same rules as the exports.

For Python callers:

```python
render_video = import_module("src.pipelines.03_render_2d_tactical_video").run_pipeline
video_path = render_video(
    tracking=Path("output/tracking_normalized_2d.csv"),
    metadata=Path("output/tracking_normalized_2d.metadata.json"),
    output_dir=Path("output"),
    start_seconds=0,
)
```

## Warp original footage into a bird's-eye video

Render the full recording from 0 seconds:

```bash
.venv/bin/python -m src.pipelines.04_render_birdseye_tactical_video \
  --video data/tactical/BAR-ATH_tactical-002.mp4 \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --output-dir output \
  --start-seconds 0
```

Step 04 writes `output/tactical_birdseye.mp4`. Its metadata input is the original
EPTS XML, supplying physical pitch dimensions. Frame rate and frame count come
from the original video. Use the matching tactical video and homography;
broadcast assets have a separate timeline. No tracking CSV or previous pipeline
output is required.

The silent H.264 MP4 uses the source frame rate and 12 pixels per metre. A
105 × 68 m pitch produces a 1260 × 816 image. Canvas dimensions are padded to
even values when necessary for `yuv420p`, retaining a uniform physical scale.
The video covers the full pitch rectangle, with normalized x increasing to the
right and y downward. It contains warped footage, without tracking dots or
labels. FFmpeg requirements and encoding settings match step 03.

The supplied homography maps normalized pitch positions into source-image
pixels. For each output pixel, step 04 maps its pitch position back into the
source image and samples with OpenCV's inverse-map perspective warp and linear
interpolation. Areas outside the source image are black. A frame with
`valid=0` calibration becomes a black frame; it is retained in the timeline.
There is no filling from neighbouring frames, interpolation of calibration,
smoothing, or reconstruction of unseen areas. Players and airborne objects can
appear stretched because the transform assumes a flat ground plane.

Time-range selection matches step 03: zero-based source frames, floor start,
ceil duration, and clipping at the recording end. Omit `--duration-seconds` to
render through the end; omit both time arguments to render the entire recording.
The output clip starts at time zero while representing the selected source
interval. Input decoding and rendering are streamed. Logs report loading,
selected frames, output geometry, progress, unavailable calibration count, and
completion. Existing outputs are refused, and failures leave no partial final
video. Use a fresh `--output-dir` for another render.

```python
render_birdseye = import_module(
    "src.pipelines.04_render_birdseye_tactical_video"
).run_pipeline
video_path = render_birdseye(
    video=Path("data/tactical/BAR-ATH_tactical-002.mp4"),
    homography=Path("data/tactical/BAR-ATH_tactical_homography.csv"),
    metadata=Path("data/tactical/BAR-ATH_tactical_atd.xml"),
    output_dir=Path("output"),
    start_seconds=0,
)
```

## Flag suspicious trajectories

Step 07 reads step 02's normalized CSV and metadata. It converts normalized
positions into metres using the supplied pitch dimensions and derives motion
using the metadata's FPS. It does not use `speed_raw` or homography.

```bash
python -m src.pipelines.07_flag_impossible_trajectories \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --player-speed-limit 12 \
  --player-acceleration-limit 15 \
  --ball-speed-limit 45 \
  --output-dir output
```

The defaults screen player speeds above 12 m/s, player accelerations above
15 m/s², and ball speeds above 45 m/s. These configurable thresholds are
heuristics, not validated accuracy or confidence estimates. Ball acceleration is
not screened because kicks and deflections can cause abrupt changes. Apparent
ball motion also inherits the limitations of ground-plane coordinates.

Speed is the Euclidean displacement between consecutive observed frames divided
by elapsed seconds. Player acceleration is the magnitude of the difference
between consecutive velocity vectors divided by elapsed seconds. Missing either
coordinate resets the history; calculations never bridge null intervals.
Equality with a threshold is not flagged. Off-pitch coordinates alone do not
trigger flags.

The pipeline writes `tracking_trajectory_flags.csv` and
`tracking_trajectory_flags.metadata.json`. The CSV contains only flagged samples,
one row per entity and ending frame, ordered by ending frame then entity ID:

| Columns | Meaning |
| --- | --- |
| `entity_id`, `entity_type`, `team_id` | Original tracking-slot identifiers. |
| `start_frame`, `end_frame` | Inclusive support interval for the triggered check(s). Speed uses two frames; acceleration uses three. |
| `speed_mps`, `acceleration_mps2` | Derived motion values; unavailable acceleration is blank, including for the ball. |
| `speed_flag`, `acceleration_flag` | Whether each value exceeds its configured threshold. |

A sample triggering both checks has one combined row covering both checks'
support. No flags produces a header-only CSV. Metadata records inputs, units,
formulas, effective thresholds and counts by entity/check. Original tracking
files are never modified.

## Assess continuity across null positions

Step 08 reads normalized tracking and the matching step 07 reports. It imports
no code from step 07 and does not run it automatically. Supply reports from the
same tracking export; input format and correspondence are assumed valid.

```bash
python -m src.pipelines.08_assess_identity_continuity \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --flags output/tracking_trajectory_flags.csv \
  --flags-metadata output/tracking_trajectory_flags.metadata.json \
  --max-gap-seconds 2 \
  --context-seconds 0.2 \
  --player-prediction-tolerance 2 \
  --ball-prediction-tolerance 3 \
  --output-dir output
```

Each maximal run with either position coordinate missing becomes one report row,
including leading/trailing gaps and completely unobserved slots. Same-slot
continuity is assessed for players; ball results describe motion continuity.
Neither slot activity nor real-world identity is inferred from nulls alone.

For a bounded gap, endpoint distance is measured in metres. Required average
speed uses the actual time between the two observed endpoints, not just the
missing-frame duration. Endpoint velocities use continuous observed context:
`ceil(context_seconds × FPS)` intervals ending at the left endpoint and starting
at the right endpoint. Forward/backward errors compare constant-velocity
predictions across the entire endpoint interval with the opposite endpoint.

Classification uses the following precedence:

| Condition | Status | Reason |
| --- | --- | --- |
| Either endpoint is absent | `uncertain` | `unbounded_gap` |
| Any step 07 support interval overlaps an endpoint or its velocity context | `uncertain` | `flagged_context` |
| Required average speed exceeds the entity's step 07 speed limit | `implausible` | `excessive_required_speed` |
| Missing-frame duration exceeds the maximum gap duration | `uncertain` | `long_gap` |
| Continuous context is insufficient on either side | `uncertain` | `insufficient_context` |
| Either prediction error exceeds the entity's tolerance | `uncertain` | `motion_disagreement` |
| All checks pass | `plausible` | `motion_consistent` |

Flag overlap includes interval boundaries. Default prediction tolerances are
2 metres for players and 3 metres for the ball. A two-second gap limit at 25 FPS
allows at most 50 missing frames; observed endpoints are 51 frame intervals
apart for a gap of that length. The limit is conservative: the audited tactical
player gaps are all longer than two seconds, so none qualify as plausible under
the defaults. A motion-consistent gap is a candidate for subsequent review or
imputation testing, not a verified identity or an instruction to fill it.

Outputs are `tracking_gap_continuity.csv` and
`tracking_gap_continuity.metadata.json`. CSV rows are ordered by gap start frame
and entity ID:

| Columns | Meaning |
| --- | --- |
| `entity_id`, `entity_type`, `team_id` | Original tracking-slot identifiers. |
| `start_frame`, `end_frame` | Inclusive bounds of the missing run. |
| `missing_frames`, `gap_seconds` | Run length and its duration at source FPS. |
| `left_frame`, `right_frame` | Observed endpoint frames; blank when absent. |
| `endpoint_distance_m`, `required_speed_mps` | Endpoint displacement and minimum required average speed. |
| `forward_error_m`, `backward_error_m` | Constant-velocity prediction errors; blank without sufficient context. |
| `status`, `reason` | Assessment and the first applicable reason above. |

Metadata records source reports, effective settings and classification counts.
Both pipelines stream tracking with bounded per-entity context and retain only
compact diagnostic records as needed. Reports use the existing safe publication
and progress logging conventions: no overwrites, no partial final pair on failure,
stderr logs and stdout output paths. Positive finite configuration values are
required. Neither pipeline fills positions, changes IDs or updates the frontend.

For Python callers:

```python
flag_trajectories = import_module(
    "src.pipelines.07_flag_impossible_trajectories"
).run_pipeline
assess_continuity = import_module(
    "src.pipelines.08_assess_identity_continuity"
).run_pipeline

tracking = Path("output/tracking_normalized_2d.csv")
metadata = Path("output/tracking_normalized_2d.metadata.json")
flags, flags_metadata = flag_trajectories(tracking, metadata, Path("output"))
gap_csv, gap_metadata = assess_continuity(
    tracking, metadata, flags, flags_metadata, Path("output")
)
```

## Correct tracking and impute supported gaps

Step 09 consumes the normalized export and both diagnostic reports. It does not
run earlier steps or modify their artifacts:

```bash
python -m src.pipelines.09_correct_tracking \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --flags output/tracking_trajectory_flags.csv \
  --flags-metadata output/tracking_trajectory_flags.metadata.json \
  --gaps output/tracking_gap_continuity.csv \
  --gaps-metadata output/tracking_gap_continuity.metadata.json \
  --output-dir output
```

Corrections have three stages:

1. Repair isolated spikes lasting at most 0.2 seconds only when excessive-speed
   transitions surround a uniquely supported interval. Reliable observations on
   both sides must support a linear replacement that passes speed and player
   acceleration checks. Acceleration-only flags do not trigger replacement.
2. Divide player observations into segments at missing runs and remaining
   excessive-speed transitions. Link segments only within the same team, across
   at most three seconds, with clean 0.2-second endpoint context, feasible speed,
   and forward/backward prediction errors of at most two metres. Both segments
   must prefer each other with at least a one-metre advantage over alternatives.
   An inferred identity cannot contain simultaneous observations from two slots.
3. Linearly interpolate bounded gaps within accepted identity chains only when
   the entire replacement and its joins pass motion checks. Player gaps may be
   at most three seconds; ball gaps at most 0.2 seconds, with a three-metre ball
   prediction tolerance. Ball acceleration is not constrained. Cross-slot gaps
   use the departing source slot only if it is missing throughout the interval.

Identity linking and imputation are separate decisions: accepting a link does
not guarantee that its gap can be filled. Long, unbounded, or ambiguous gaps
remain missing. The pipeline never extrapolates, clamps off-pitch coordinates,
or uses imputed positions to justify another identity link. Step 08's earlier
classifications are retained as audit evidence; its two-second cutoff is
explicitly reassessed under step 09's three-second player policy.

The outputs are:

| Artifact | Contents |
| --- | --- |
| `tracking_corrected_2d.csv` | Every source row, with corrected normalized coordinates and provenance columns. |
| `tracking_corrected_2d.metadata.json` | Source paths, effective policy, coordinate conventions, identity semantics, and correction counts. |
| `tracking_corrections.csv` | Accepted and rejected repair, link, and imputation decisions, with reasons and motion measurements. |
| `tracking_correction_validation.json` | Deterministic masking evaluation, identity-fragmentation checks, and before/after diagnostics. |

Existing columns retain their meaning: `entity_id` is the original slot,
`speed_raw` is untouched, and `pos_x`, `pos_y`, and `position_valid` describe the
resulting position. Additional columns distinguish observations from estimates:

| Columns | Meaning |
| --- | --- |
| `source_pos_x`, `source_pos_y` | Original position cells, including partial or fully missing observations. |
| `corrected_entity_id` | Deterministic inferred player-chain ID; `ball` for the ball; blank for unresolved missing rows. |
| `segment_id` | Observed segment reference. |
| `position_status` | `observed`, `repaired`, `imputed`, or `missing`. |
| `correction_id` | Audit reference for a changed position. |

Names and shirt numbers in the tactical XML are tracking-slot labels. Inferred
identities therefore describe motion continuity, not verified people. The audit
contains measurements and decisions rather than invented confidence
probabilities. The original CSV remains the source of truth for supplied values.

Validation hides clean observed windows and reconstructs them using visible
context, reporting acceptance counts and errors by entity type, duration, and
recording-time block. Controlled identity tests fragment trajectories to check
recovery and ambiguity rejection. These checks measure consistency with the
supplied tracks; they cannot establish accuracy against the footage or identity
ground truth. A successful run can leave most nulls unresolved.

Generated outputs are published together without overwriting existing files.
Temporary processing storage is cleaned up on success or failure. Logs and
progress go to stderr; the four final output paths go to stdout. The frontend
does not automatically switch to these outputs or display inferred identities.

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
