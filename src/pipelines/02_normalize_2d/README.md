# 02 — Export normalized pitch coordinates

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

```bash
python -m src.pipelines.02_normalize_2d \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --output-dir output
```

The 2D pipeline writes `tracking_normalized_2d.csv` and
`tracking_normalized_2d.metadata.json`. Raw ATD x,y are already normalised pitch
fractions, so it copies them directly. It has no dependency on homography and
retains positions from frames with invalid calibration. Finite coordinates
outside 0..1 and finite components of partially missing positions are retained.
These files are independent views of source observations, rather than an inverse
pixel-to-pitch round trip.

See the [shared export format](../README.md#shared-tracking-export-format) for
CSV columns, metadata fields, missing values, row order and output safety.
Processing streams one frame at a time. These exports can be loaded by the
[tracking viewer](../../../frontend/README.md).

The CSV and metadata feed steps [03](../03_render_2d_tactical_video/README.md),
[07](../07_flag_impossible_trajectories/README.md) and
[08](../08_assess_identity_continuity/README.md).

## Python API

```python
from importlib import import_module
from pathlib import Path

normalize_2d = import_module("src.pipelines.02_normalize_2d").run_pipeline
csv_path, metadata_path = normalize_2d(
    tracking=Path("data/tactical/BAR-ATH_tactical_atd.txt"),
    metadata=Path("data/tactical/BAR-ATH_tactical_atd.xml"),
    output_dir=Path("output"),
)
```
