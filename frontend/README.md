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

- `data/tactical/BAR-ATH_tactical-001.mp4`
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

## Experiment comparison

Open the **Experiments** tab beside **Tracking Viewer**. Switching views pauses
playback and keeps the viewer's frame and controls in place. The dashboard uses
the same local server and requires no frontend build or additional service.
The existing viewer startup inputs are still required.

`GET /api/experiments` reads `experiments/runs/*.json` on every request using the
registry's schema reader. It returns only dashboard fields: run/method identity,
selected metrics, evaluation identity, reviewed numeric configuration parameters,
and selected provenance with warnings. Artifact paths, submission CSVs, input
contents and free-text notes are not served. Requests never record experiments,
regenerate reports, or modify manifests. The generated registry CSV is not used.

Record a new experiment after independently running inference and scoring:

```bash
python scripts/record_experiment.py \
  --submission output/possession-11/possession_deadball.csv \
  --metadata output/possession-11/possession_deadball.metadata.json \
  --scores output/possession-11/possession_deadball.scores.json
```

Supply the actual known dataset, scope, ground-truth fingerprint and scorer
identity when recording; see the [experiment registry guide](../experiments/README.md)
for the complete provenance arguments. Then click **Reload registry**, or refresh
the browser and reopen Experiments. There is no dashboard data file to maintain.

### Charts and comparison controls

- **Official evaluation metrics:** spellF1 (`spell_f1_mean`) and macroF1.
- **Dead ball & possession quality:** dead-ball F1 (`per_class.D.f1` in the
  original score, recorded as `dead_ball_f1`) versus spellF1. Zeroes remain
  visible; missing coordinates exclude a point.
- **Possession fragmentation:** predicted and ground-truth possession counts
  on graded frames, plus the official fragmentation segment ratio. This ratio
  is not the possession-count ratio. More than 1× indicates more segments;
  less than 1× can indicate over-persistence.

The default **All pipelines · exploratory comparison** view plots recorded runs
across pipelines together. Chart annotations use full pipeline/model names such
as `05_possession_baseline`; run fingerprints and commits remain in the table
and details. Select table rows to compare a subset, or use pipeline/search/status
filters. Clear selection to show all matching runs.

Cross-pipeline comparison does not establish matching evaluation conditions:
runs may have different or unknown datasets, ground truth or scorers. A prominent
warning keeps that limitation visible. Use the optional **Comparison view**
selector to restrict charts to a matching identified evaluation scope; unknown
identities remain available as individual inspections as well.

Click column headings to sort; missing values remain last in either direction.
Hover chart marks for values, or focus them and press Enter to open run details.
Each row provides configuration, exact metric values and provenance warnings.

### Limitations and interpretation

Public scores cover only **five minutes and 17 labelled possessions** and are
exploratory. Neither sorting nor chart position recommends a full-match model.
All chart counts refer to evaluated frames. Full-submission possession counts,
when recorded, are shown separately and never compared against public-window
ground-truth counts; current manifests do not contain those counts.

Missing metrics display as dashes, not zero. Dirty-tree warnings describe the
working tree when the experiment was recorded, not the current checkout. A
recording commit does not establish the code used for historical inference;
missing execution provenance stays explicit. Artifact association is supplied
by the caller. The dashboard does not certify reproducibility.

Configuration is restricted to reviewed numeric parameters for current pipelines;
unreviewed fields are omitted with a warning. Unknown or unsupported manifest
schemas produce a retryable loading error instead of partially plotted results.
On small screens, charts and the table scroll horizontally to retain readable
labels and metric columns. No new visualization dependency is required.

## Data & Diagnostics (Stage 1)

Generate the read-only report independently, then pass it to the viewer:

```bash
python -m src.diagnostics \
  --normalized output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --baseline output/possession_baseline.csv \
  --ground-truth data/BAR-ATH_possession_gt_public.csv \
  --output output/diagnostics.json
python -m frontend --diagnostics output/diagnostics.json
```

Supply the public baseline and ground truth on the same zero-based tactical
frame timeline as the normalized export. The report records all input paths.
The server loads the JSON at startup and serves GET/HEAD `/api/diagnostics`;
it never runs a pipeline. Restart after regenerating a report. Existing exports
are refused. Without `--diagnostics`, the tab explains how to configure a report.

The overview counts usable observation rows (valid, finite x/y), visible ball
frames, and mean visible player observations. Ball visibility uses normalized
tracking availability, not camera visibility or a possession estimate. Gap runs
include recording edges and cover the entire tactical recording without an
implicit halftime split. The histogram counts each missing run once across thirty equal-width duration bins.
Bins include their lower edge; only the final bin includes its upper edge.
The existing report’s `gap_ecdf` duration entries supply the observations;
cumulative fractions are not used by the histogram. Intervals
are half-open; seconds are recording time, not broadcast or match clock time.
The possession timeline displays the supplied public baseline. spellF1 uses the
vendored official scorer, its IoU thresholds, scored ground-truth runs and
abstention filling. Ground-truth X frames are ungraded.

Stage 2 is deferred: player–ball geometry, Smart Tagging coverage, failure-case
exploration, and viewer jump-to-frame integration are not included.

Diagnostics uses the same analysis headings, chart labels, legends and table
styles as Experiments. Counts use grouped digits; chart values retain the report's
precision. Focus a chart and use Left/Right to inspect values, or Home/End to
reach the first/last observation. Hover or tap a mark for the same persistent
readout. Charts scroll inside their containers on narrow screens. A failed load
provides a Retry loading button; missing reports explain the configuration.
