# 08 — Assess continuity across null positions

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.

Step 08 reads normalized tracking and the matching step 07 reports. It imports
no code from step 07 and does not run it automatically. Supply reports from the
same tracking export; input format and correspondence are assumed valid.

```bash
python -m src.pipelines.08_assess_identity_continuity \
  --tracking output/tracking_normalized_2d.csv \
  --metadata output/tracking_normalized_2d.metadata.json \
  --flags output/tracking_trajectory_flags.csv \
  --flags-metadata output/tracking_trajectory_flags.metadata.json \
  --max-gap-seconds 2 \
  --context-seconds 0.2 \
  --player-prediction-tolerance 2 \
  --ball-prediction-tolerance 3 \
  --output-dir output
```

Each maximal run with either position coordinate missing becomes one report row,
including leading/trailing gaps and completely unobserved slots. Same-slot
continuity is assessed for players; ball results describe motion continuity.
Neither slot activity nor real-world identity is inferred from nulls alone.

For a bounded gap, endpoint distance is measured in metres. Required average
speed uses the actual time between the two observed endpoints, not just the
missing-frame duration. Endpoint velocities use continuous observed context:
`ceil(context_seconds × FPS)` intervals ending at the left endpoint and starting
at the right endpoint. Forward/backward errors compare constant-velocity
predictions across the entire endpoint interval with the opposite endpoint.

Classification uses the following precedence:

| Condition | Status | Reason |
| --- | --- | --- |
| Either endpoint is absent | `uncertain` | `unbounded_gap` |
| Any step 07 support interval overlaps an endpoint or its velocity context | `uncertain` | `flagged_context` |
| Required average speed exceeds the entity's step 07 speed limit | `implausible` | `excessive_required_speed` |
| Missing-frame duration exceeds the maximum gap duration | `uncertain` | `long_gap` |
| Continuous context is insufficient on either side | `uncertain` | `insufficient_context` |
| Either prediction error exceeds the entity's tolerance | `uncertain` | `motion_disagreement` |
| All checks pass | `plausible` | `motion_consistent` |

Flag overlap includes interval boundaries. Default prediction tolerances are
2 metres for players and 3 metres for the ball. A two-second gap limit at 25 FPS
allows at most 50 missing frames; observed endpoints are 51 frame intervals
apart for a gap of that length. The limit is conservative: the audited tactical
player gaps are all longer than two seconds, so none qualify as plausible under
the defaults. A motion-consistent gap is a candidate for subsequent review or
imputation testing, not a verified identity or an instruction to fill it.

Outputs are `tracking_gap_continuity.csv` and
`tracking_gap_continuity.metadata.json`. CSV rows are ordered by gap start frame
and entity ID:

| Columns | Meaning |
| --- | --- |
| `entity_id`, `entity_type`, `team_id` | Original tracking-slot identifiers. |
| `start_frame`, `end_frame` | Inclusive bounds of the missing run. |
| `missing_frames`, `gap_seconds` | Run length and its duration at source FPS. |
| `left_frame`, `right_frame` | Observed endpoint frames; blank when absent. |
| `endpoint_distance_m`, `required_speed_mps` | Endpoint displacement and minimum required average speed. |
| `forward_error_m`, `backward_error_m` | Constant-velocity prediction errors; blank without sufficient context. |
| `status`, `reason` | Assessment and the first applicable reason above. |

Metadata records source reports, effective settings and classification counts.

The pipeline streams tracking with bounded per-entity context and retains only
compact diagnostic records as needed. Reports follow the shared publication and
progress conventions: no overwrites, no partial final pair on failure, stderr
logs and stdout output paths. Positive finite configuration values are required.
It does not fill positions or change IDs. Restart the
[tracking viewer](../../../frontend/README.md#review-tracking-quality) to load
new reports; default report paths are detected independently.

## Python API

```python
from importlib import import_module
from pathlib import Path

assess_continuity = import_module(
    "src.pipelines.08_assess_identity_continuity"
).run_pipeline
gap_csv, gap_metadata = assess_continuity(
    Path("output/tracking_normalized_2d.csv"),
    Path("output/tracking_normalized_2d.metadata.json"),
    Path("output/tracking_trajectory_flags.csv"),
    Path("output/tracking_trajectory_flags.metadata.json"),
    Path("output"),
)
```
