# Tracking coordinate exports

These are two independent exports of the same supplied ATD observations. Each
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
│   └── 02_normalize_2d/
│       ├── __init__.py
│       ├── __main__.py
│       └── pipeline.py
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
Run the commands one by one: neither pipeline calls or executes the other.
Both read the original ATD independently.

CLI logs are timestamped and sent to stderr, while stdout contains only the two
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

Install the formatter and tests with `uv sync --group dev --extra test`.
Format changed Python files with `python -m black <paths>` and verify them with
`python -m black --check <paths>`. Black uses 88-character lines and targets
Python 3.12. Split long strings and complicated expressions for readability even
when the formatter does not do so automatically.

Run the scoped
checks with `.venv/bin/python -m pytest tests/src/pipelines tests/src/utilities`.
