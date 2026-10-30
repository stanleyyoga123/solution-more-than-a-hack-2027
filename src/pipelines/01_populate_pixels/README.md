# 01 — Populate pixel coordinates

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

```bash
python -m src.pipelines.01_populate_pixels \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --homography data/tactical/BAR-ATH_tactical_homography.csv \
  --output-dir output
```

The pixel pipeline writes `tracking_pixels.csv` and
`tracking_pixels.metadata.json`. It applies each frame's supplied homography to
normalised pitch x,y and divides by the homogeneous denominator to obtain
original-video pixel coordinates. Invalid calibration leaves both pixel
coordinates blank, with `homography_valid=False`. Undefined or nonfinite
projections also leave both coordinates blank. Finite offscreen pixel positions
are preserved. No video decoding or visibility inference is required. The
pitch-plane assumption can misplace airborne objects.

See the [shared export format](../README.md#shared-tracking-export-format) for
CSV columns, metadata fields, missing values, row order and output safety.
Processing streams one frame at a time. These exports can be loaded by the
[tracking viewer](../../../frontend/README.md).

## Python API

```python
from importlib import import_module
from pathlib import Path

populate_pixels = import_module("src.pipelines.01_populate_pixels").run_pipeline
csv_path, metadata_path = populate_pixels(
    tracking=Path("data/tactical/BAR-ATH_tactical_atd.txt"),
    metadata=Path("data/tactical/BAR-ATH_tactical_atd.xml"),
    homography=Path("data/tactical/BAR-ATH_tactical_homography.csv"),
    output_dir=Path("output"),
)
```
