# Tracking exports and tactical video

The first two steps independently export the same supplied ATD observations.
The third renders a normalized CSV and its metadata as a top-down tactical video.
Each
numbered package owns one pipeline; shared readers and export helpers live in
`src/utilities/`. Production imports stay inside `src/`.

```text
src/
├── pipelines/
│   ├── 01_populate_pixels/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   ├── pipeline.py
│   │   └── homography_reader.py
│   ├── 02_normalize_2d/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   └── 03_render_2d_tactical_video/
│       ├── __init__.py
│       ├── __main__.py
│       ├── pipeline.py
│       ├── metadata_reader.py
│       ├── normalized_reader.py
│       ├── pitch_renderer.py
│       └── video_encoder.py
└── utilities/
    ├── atd_reader.py
    ├── epts_metadata.py
    └── export_files.py
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

Inputs and CSV rows are streamed with memory bounded by one frame. A full
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

After exporting normalized tracking, render video time 10:00–10:10 with:

```bash
.venv/bin/python -m src.pipelines.03_render_2d_tactical_video \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --output-dir output \
  --start-seconds 600 \
  --duration-seconds 10
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
    start_seconds=600,
    duration_seconds=10,
)
```

Install the formatter and tests with `uv sync --group dev --extra test`.
Format changed Python files with `python -m black <paths>` and verify them with
`python -m black --check <paths>`. Black uses 88-character lines and targets
Python 3.12. Split long strings and complicated expressions for readability even
when the formatter does not do so automatically.

Run the scoped
checks with `.venv/bin/python -m pytest tests/src/pipelines tests/src/utilities`.
