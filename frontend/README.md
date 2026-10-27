# Tracking viewer

Compare the original tactical video with pixel tracking overlays against a
normalized, top-down pitch view. Both views use the same zero-based source frame.

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

Generate the two CSVs with pipelines 01 and 02 before starting the viewer.
The viewer does not run pipelines or require the video from pipeline 03.
Use `python -m frontend --help` to select different input paths or a port.
All inputs must belong to the same recording and timeline.

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

Blue and red identify the teams consistently in both views; yellow marks the
ball. Labels are tracking-slot IDs, **not verified shirt numbers**. Camera markers
outside the image are hidden. Missing positions are omitted, and finite
normalized coordinates outside the pitch are not clamped. The minimap can show
players outside the camera's view. Times refer to the source video, not the match
clock.

## Code and checks

`server/` owns local HTTP serving and indexed CSV access. `web/` contains the
browser interface and modules for playback, data access, and drawing. Match
assets remain local; the server binds to the loopback interface.

```bash
.venv/bin/python -m pytest tests/frontend -q
node --test tests/frontend/web/*.test.mjs
.venv/bin/python -m black --check frontend tests/frontend
```
