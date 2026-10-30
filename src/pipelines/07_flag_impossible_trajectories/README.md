# 07 — Flag suspicious trajectories

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

Step 07 reads step 02's normalized CSV and metadata. It converts normalized
positions into metres using the supplied pitch dimensions and derives motion
using the metadata's FPS. It does not use `speed_raw` or homography.

```bash
python -m src.pipelines.07_flag_impossible_trajectories \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --player-speed-limit 12 \
  --player-acceleration-limit 15 \
  --ball-speed-limit 45 \
  --output-dir output
```

The defaults screen player speeds above 12 m/s, player accelerations above
15 m/s², and ball speeds above 45 m/s. These configurable thresholds are
heuristics, not validated accuracy or confidence estimates. Ball acceleration is
not screened because kicks and deflections can cause abrupt changes. Apparent
ball motion also inherits the limitations of ground-plane coordinates.

Speed is the Euclidean displacement between consecutive observed frames divided
by elapsed seconds. Player acceleration is the magnitude of the difference
between consecutive velocity vectors divided by elapsed seconds. Missing either
coordinate resets the history; calculations never bridge null intervals.
Equality with a threshold is not flagged. Off-pitch coordinates alone do not
trigger flags.

The pipeline writes `tracking_trajectory_flags.csv` and
`tracking_trajectory_flags.metadata.json`. The CSV contains only flagged samples,
one row per entity and ending frame, ordered by ending frame then entity ID:

| Columns | Meaning |
| --- | --- |
| `entity_id`, `entity_type`, `team_id` | Original tracking-slot identifiers. |
| `start_frame`, `end_frame` | Inclusive support interval for the triggered check(s). Speed uses two frames; acceleration uses three. |
| `speed_mps`, `acceleration_mps2` | Derived motion values; unavailable acceleration is blank, including for the ball. |
| `speed_flag`, `acceleration_flag` | Whether each value exceeds its configured threshold. |

A sample triggering both checks has one combined row covering both checks'
support. No flags produces a header-only CSV. Metadata records inputs, units,
formulas, effective thresholds and counts by entity/check. Original tracking
files are never modified.

The pipeline streams tracking with bounded per-entity context and retains only
compact diagnostic records as needed. Reports follow the shared publication and
progress conventions: no overwrites, no partial final pair on failure, stderr
logs and stdout output paths. Positive finite configuration values are required.
It does not fill positions or change IDs. Restart the
[tracking viewer](../../../frontend/README.md#review-tracking-quality) to load
new reports; default report paths are detected independently.

Its CSV and metadata feed [step 08](../08_assess_identity_continuity/README.md).

## Python API

```python
from importlib import import_module
from pathlib import Path

flag_trajectories = import_module(
    "src.pipelines.07_flag_impossible_trajectories"
).run_pipeline
flags, flags_metadata = flag_trajectories(
    Path("output/tracking_normalized_2d.csv"),
    Path("output/tracking_normalized_2d.metadata.json"),
    Path("output"),
)
```
