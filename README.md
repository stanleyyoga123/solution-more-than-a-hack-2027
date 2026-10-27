# Barcelona Go Go

Python pipelines and a local browser viewer for exploring Barcelona–Athletic
football tracking data. Convert the supplied ATD observations into video-pixel
and normalized pitch coordinates, render tactical videos, and compare three
views on one source timeline:

- **Camera view:** original footage with team-colored tracking dots and IDs.
- **Pitch view:** a top-down map drawn from normalized tracking positions.
- **Bird's-eye footage:** the original video warped onto the pitch plane, with
  an optional tracking overlay.

![Frontend showing the camera overlay, normalized pitch map, and labeled bird's-eye footage](docs/images/frontend.jpg)

## Generated data

The generated data is available in this
[Google Drive folder](https://drive.google.com/drive/folders/1BuxSs5RT_My3yr1fbt8TtAzbFK5tiay5).
Place downloaded tracking CSVs, metadata JSONs, and rendered videos under
`output/`, keeping the filenames listed in the pipeline table below. You can
reuse these artifacts instead of running the corresponding generation steps.
The original recording is still needed for the frontend's camera view.

## Setup

Requirements:

- Python 3.12 or newer and `uv`.
- FFmpeg with the `libx264` encoder for video pipelines 03 and 04.
- A browser supporting `requestVideoFrameCallback`, such as a current Chrome.
- Node.js only if you want to run the browser-module tests. The frontend needs
  no npm installation or build step.

Run commands from the repository root:

```bash
uv sync --group dev --extra test
source .venv/bin/activate
```

Place the recording assets under `data/`. The tactical examples below expect:

```text
data/tactical/
├── BAR-ATH_tactical-002.mp4
├── BAR-ATH_tactical_atd.txt
├── BAR-ATH_tactical_atd.xml
└── BAR-ATH_tactical_homography.csv
```

Obtain the match assets separately through the dataset provider. Match assets
and generated outputs are excluded from Git. Keep tactical and broadcast inputs
on their own timelines; their frame numbers are not interchangeable.

## Quick start

### 1. Export tracking coordinates

Create the pixel coordinates used by the camera overlay:

```bash
python -m src.pipelines.01_populate_pixels \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --output-dir output
```

Create the normalized coordinates used by the pitch map and bird's-eye overlay:

```bash
python -m src.pipelines.02_normalize_2d \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --output-dir output
```

Each step writes a CSV and a companion `.metadata.json` file. Generate these
once, then reuse them in the viewer. The full tactical CSVs are several hundred
megabytes each. Existing outputs are protected from overwriting; choose a new
`--output-dir` for another export.

### 2. Render the bird's-eye footage (optional)

```bash
python -m src.pipelines.04_render_birdseye_tactical_video \
  --video data/tactical/BAR-ATH_tactical-002.mp4 \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --start-seconds 0 \
  --output-dir output
```

This renders the full recording to `output/tactical_birdseye.mp4`. It preserves
the source frame rate and uses 12 pixels per metre: 1260 × 816 for the supplied
105 × 68 m pitch. Areas outside the camera image are black. Frames without valid
calibration remain in the video as black frames.

The warp assumes a flat pitch, so players' bodies and airborne objects can appear
stretched. Tracking dots indicate ground positions. The video has no audio.

### 3. Open the frontend

```bash
python -m frontend --port 8766
```

Open [http://127.0.0.1:8766](http://127.0.0.1:8766). The server binds only to the
local machine. Stop it with `Ctrl+C`. Without `--port`, the default is 8765.

The viewer automatically loads `output/tactical_birdseye.mp4` when present.
The camera and pitch views work without it. Its first launch builds cached CSV
indexes under `output/frontend/`; subsequent launches reuse unchanged indexes.
Tracking is fetched in small chunks rather than loading entire CSVs in the browser.

Controls include:

- Shared play/pause, speed, timeline seeking, and frame-number entry.
- Previous/next frame buttons; Space to play/pause and arrow keys to step when
  focus is outside an input or button.
- A shortcut to the approximate first kickoff: frame 11186, or 447.44 seconds.
- Independent camera, pitch, and bird's-eye label toggles.
- Separate camera and bird's-eye overlay toggles. Hiding labels keeps dots visible;
  hiding an overlay removes both dots and labels from that view.

See the [frontend guide](frontend/README.md) for custom paths and playback details.

## Pipelines

Run numbered steps individually with `python -m src.pipelines.<step>`.
They do not import or execute each other; shared code lives in `src/utilities/`.

| Step | Input | Output under the selected directory |
| --- | --- | --- |
| `01_populate_pixels` | ATD text, XML, homography CSV | `tracking_pixels.csv` and metadata JSON |
| `02_normalize_2d` | ATD text and XML | `tracking_normalized_2d.csv` and metadata JSON |
| `03_render_2d_tactical_video` | Normalized CSV and its metadata JSON | `tactical_2d_tracking.mp4` — animated tracking map |
| `04_render_birdseye_tactical_video` | Original video, homography CSV, XML | `tactical_birdseye.mp4` — warped footage |

Step 03 consumes step 02's exported files. Step 04 works directly from the
original recording assets and needs no previous pipeline output. The frontend
draws its pitch map directly from tracking data, so step 03 is optional.

To export the first ten seconds as a tracking-map video:

```bash
python -m src.pipelines.03_render_2d_tactical_video \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --start-seconds 0 \
  --duration-seconds 10 \
  --output-dir output/minimap_preview
```

Both video pipelines accept `--start-seconds` and `--duration-seconds`. Omit the
duration to render through the recording's end. Times refer to the source video,
not the scoreboard clock. The start frame is rounded down, the duration in frames
is rounded up, and the selection is clipped at the end of the recording.

For a short bird's-eye clip starting at source time zero:

```bash
python -m src.pipelines.04_render_birdseye_tactical_video \
  --video data/tactical/BAR-ATH_tactical-002.mp4 \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --start-seconds 0 \
  --duration-seconds 10 \
  --output-dir output/birdseye_clip

python -m frontend --port 8766 \
  --birdseye-video output/birdseye_clip/tactical_birdseye.mp4 \
  --birdseye-start-seconds 0
```

Supply the original render's start time so the clip aligns with the source
timeline. Outside that interval, the viewer hides the footage and its overlay.

Each CLI provides `--help`. Logs and progress go to stderr; completed output
paths go to stdout. Video files are published only after successful encoding.
See the [pipeline guide](src/pipelines/README.md) for the schema, Python APIs,
coordinate conventions, and output-safety details.

## Data conventions

- `frame` is the zero-based source-video frame.
- `entity_id` identifies a tracking slot, not a verified shirt number or player
  identity. `entity_type` distinguishes players from the ball.
- Pixel positions use the original image's coordinate system. Normalized pitch
  positions use fractions, with x increasing rightward and y downward.
- Missing numeric observations remain blank in CSVs. Missing positions are
  omitted from the visualizations; finite off-pitch positions are not clamped.
- `speed_raw` preserves the supplied speed channel. No facing angles or
  per-player confidence scores are inferred.
- Homography reprojection error describes calibration quality, not confidence
  in an individual player's position.

## Repository structure

```text
src/
├── pipelines/       # Numbered command-line pipeline packages
└── utilities/       # Shared readers, encoding, timing, logging, and exports
frontend/
├── server/          # Local HTTP server and indexed CSV access
└── web/             # Browser playback, rendering, and controls
eda/                 # Exploration notebooks
tests/               # Pipeline, utility, and frontend checks
data/                # Local recording assets (ignored)
output/              # Generated exports, videos, and indexes (ignored)
```

## Development checks

Black is the Python formatter. Format changed Python files with
`python -m black <paths>` and check them with `python -m black --check <paths>`.

Run the maintained pipeline and frontend checks:

```bash
python -m pytest tests/src/pipelines \
  tests/src/utilities/test_pipeline_exports.py \
  tests/src/utilities/test_pipeline_logging.py \
  tests/frontend -q

node --test tests/frontend/web/*.test.mjs
```

Some legacy tests still reference removed exploratory modules, so the full
`python -m pytest` collection is not currently supported. The scoped commands
above cover the current pipelines and viewer. Video tests require FFmpeg; HTTP
tests need permission to bind local ports.
