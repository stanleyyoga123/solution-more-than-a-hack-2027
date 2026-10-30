# Tracking viewer

Compare the original tactical video with pixel tracking overlays, a normalized
pitch map, and the warped bird's-eye footage from pipeline 04. The original video
controls the shared source timeline.

From the repository root, with the project environment installed:

```bash
source .venv/bin/activate
python -m frontend
```

Open **http://127.0.0.1:8765**. Stop the server with `Ctrl+C`.
No npm installation or frontend build is needed.
If that port is already in use, run `python -m frontend --port 8766` and open
**http://127.0.0.1:8766** instead.

The defaults use:

- `data/tactical/BAR-ATH_tactical-002.mp4`
- `output/tracking_pixels.csv`
- `output/tracking_normalized_2d.csv`
- `output/tracking_normalized_2d.metadata.json`
- `output/tactical_birdseye.mp4`, when present
- `output/tracking_trajectory_flags.csv`, when present
- `output/tracking_gap_continuity.csv`, when present

Generate the two CSVs with [pipeline 01](../src/pipelines/01_populate_pixels/README.md)
and [pipeline 02](../src/pipelines/02_normalize_2d/README.md) before starting the viewer.
The viewer does not run pipelines or require the video from pipeline 03.
Render the bird's-eye footage with
[pipeline 04](../src/pipelines/04_render_birdseye_tactical_video/README.md) before
starting the viewer to enable the third view. If its default file is absent, the camera and pitch map
still work and the third card explains that the footage is unavailable.
Use `python -m frontend --help` to select different input paths or a port.
All inputs must belong to the same recording and timeline.

For a different bird's-eye file, pass `--birdseye-video`. For a trimmed render,
also supply the same `--start-seconds` value used for pipeline 04 as
`--birdseye-start-seconds`. For example, the five-second preview from source time
10:00 starts at source frame 15000:

```bash
python -m frontend \
  --birdseye-video output/birdseye_preview/tactical_birdseye.mp4 \
  --birdseye-start-seconds 600
```

The offset defaults to zero for full-recording renders. It is rounded down to
the source frame boundary, matching pipeline 04. Outside a trimmed clip's time
range, the third card shows an unavailable message instead of a stale image.
An explicitly supplied missing video path is a startup error.

The first launch indexes the CSVs for fast frame access and logs loading progress.
Indexes are cached under `output/frontend/`; later launches reuse them while
the source paths, sizes, and modification times remain unchanged. The browser
requests small frame ranges instead of downloading entire CSVs.

## Controls

- Play/pause and choose playback speed.
- Scrub the shared timeline or enter a frame number.
- Step backward or forward one frame while paused.
- Jump to the approximate first kickoff, frame 11186 (447.44 seconds at 25 FPS).
- Toggle camera labels and pitch labels independently, or hide the camera overlay.
- Toggle bird's-eye labels independently, or hide its entire tracking overlay.
  Turning labels off keeps the dots visible.

Playback, speed, seeking, and frame stepping also control the bird's-eye footage.
It follows the source video, realigning during playback and seeking to the
selected frame when paused. A status message covers the footage while loading
or seeking. It has no independent playback controls or audio.

Blue and red identify the teams consistently in both views; yellow marks the
ball. Labels are tracking-slot IDs, **not verified shirt numbers**. Camera markers
outside the image are hidden. Missing positions are omitted, and finite
normalized coordinates outside the pitch are not clamped. The minimap can show
players outside the camera's view. Times refer to the source video, not the match
clock.

Bird's-eye footage preserves pipeline 04's black unseen regions and stretched
player bodies: the warp assumes a flat pitch. Its optional tracking overlay uses
normalized positions and the same team colours and tracking IDs as the other
views. Positions align with the ground plane, usually at players' feet. Known
positions can appear over black areas even when those players are outside the
original camera view.

The overlay follows the displayed bird's-eye frame, including trimmed-clip
offsets. It clears during seeking, unavailable footage, or tracking loads, so
old positions are not left on a new frame. Coordinates use pipeline 04's fixed
12 pixels per metre and preserve any padding for even video dimensions. The
video file itself is unchanged; overlays are drawn only in the browser.

## Review tracking quality

Generate reports with [step 07](../src/pipelines/07_flag_impossible_trajectories/README.md)
and [step 08](../src/pipelines/08_assess_identity_continuity/README.md), then restart
the viewer. Reports are loaded once at startup; the viewer does not run these pipelines. Each default report is
optional and detected independently. Without reports, video playback and tracking
overlays continue to work and the quality panel explains what is unavailable.
An explicitly supplied missing report path is a startup error.

For reports in a different directory:

```bash
python -m frontend \
  --trajectory-flags output/review/tracking_trajectory_flags.csv \
  --gap-continuity output/review/tracking_gap_continuity.csv
```

Use reports from the same recording and frame timeline as the displayed tracking.

The **Tracking quality** panel provides:

- Counts of flagged samples, grouped motion episodes and gaps by status.
- Filters for a tracking entity, motion flags or a gap classification.
- A timeline with separate motion and gap lanes, aligned to source-video frames.
- Previous/next navigation and a paginated event list for precise selection.
- Selected-event details, including frame bounds, motion values or gap duration
  and classification reason.
- Jumps to a motion episode's peak sample or the observed frame before a gap,
  with before/after boundary controls for gaps that have those observations.
- A highlight toggle for the selected entity in the camera, pitch and bird's-eye
  overlays. Existing label and overlay toggles remain independent.

Neighboring or overlapping flagged support intervals for the same entity are
grouped into one motion episode. The sample count remains available: an episode
is a convenient review interval, not an independently verified error. A motion
episode with speed flags jumps to its highest flagged speed; an acceleration-only
episode jumps to its highest acceleration. Highlights use existing observations
only, so no marker is invented while an entity's position is missing. Bird's-eye
highlights follow that footage's displayed frame.

Gap statuses retain step 08's meaning: `plausible` indicates consistent same-slot
motion, `implausible` indicates excessive required endpoint speed, and `uncertain`
means the available evidence is insufficient. These reports do not verify player
identity, fill nulls or alter the videos and tracking files.

## Code and checks

`server/` owns local HTTP serving and indexed CSV access. `web/` contains the
browser interface and modules for playback, data access, and drawing. Match
assets remain local; the server binds to the loopback interface.

```bash
.venv/bin/python -m pytest tests/frontend -q
node --test tests/frontend/web/*.test.mjs
.venv/bin/python -m black --check frontend tests/frontend
```
