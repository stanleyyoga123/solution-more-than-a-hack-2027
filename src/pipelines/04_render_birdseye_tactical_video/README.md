# 04 — Warp footage into a bird's-eye video

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

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
labels. FFmpeg must be on `PATH` with the `libx264` encoder. Encoding uses
`yuv420p`, CRF 20, the `veryfast` preset and `faststart` playback metadata.

The supplied homography maps normalized pitch positions into source-image
pixels. For each output pixel, step 04 maps its pitch position back into the
source image and samples with OpenCV's inverse-map perspective warp and linear
interpolation. Areas outside the source image are black. A frame with
`valid=0` calibration becomes a black frame; it is retained in the timeline.
There is no filling from neighbouring frames, interpolation of calibration,
smoothing, or reconstruction of unseen areas. Players and airborne objects can
appear stretched because the transform assumes a flat ground plane.

Time-range selection matches [step 03](../03_render_2d_tactical_video/README.md):
zero-based source frames, floor start,
ceil duration, and clipping at the recording end. Omit `--duration-seconds` to
render through the end; omit both time arguments to render the entire recording.
The output clip starts at time zero while representing the selected source
interval. Input decoding and rendering are streamed. Logs report loading,
selected frames, output geometry, progress, unavailable calibration count, and
completion. Existing outputs are refused, and failures leave no partial final
video. Use a fresh `--output-dir` for another render.

```python
from importlib import import_module
from pathlib import Path

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
