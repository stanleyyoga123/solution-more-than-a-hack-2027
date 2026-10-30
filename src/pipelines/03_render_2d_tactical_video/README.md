# 03 — Render a top-down tactical video

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

After exporting normalized tracking with [step 02](../02_normalize_2d/README.md),
render the full recording from 0 seconds:

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
from importlib import import_module
from pathlib import Path

render_video = import_module("src.pipelines.03_render_2d_tactical_video").run_pipeline
video_path = render_video(
    tracking=Path("output/tracking_normalized_2d.csv"),
    metadata=Path("output/tracking_normalized_2d.metadata.json"),
    output_dir=Path("output"),
    start_seconds=0,
)
```
