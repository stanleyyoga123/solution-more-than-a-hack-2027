# 10 — Standalone control confirmation

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Step 10 implements the control-confirmation rule introduced by playground e05
as a standalone method. It reads raw nearest-team evidence and confirms sustained
changes in ownership. The cumulative playground e05 submission also includes
other experiments; its recorded scores do not describe this standalone method.

## Run and score

From the repository root, with the project environment active:

```bash
python -m src.pipelines.10_possession_control \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --output-dir output/possession-10
```

Both input paths are required and must belong to the same tactical recording.
The output directory defaults to `output/`. Each invocation writes:

- `submission.csv`: `frame,label`, one row for every metadata-declared
  frame, with zero-based source-video frames and `H`, `A` or `D` labels.
- `submission.metadata.json`: method/version, complete policy, input
  paths, execution time and runtime versions, FPS, team mapping, pitch dimensions,
  processed-frame count, output-frame count and label counts.

The [official submission contract](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/SUBMISSION.md)
requires all 199,319 tactical-video frames (`0` through `199318`) for BAR–ATH,
including frames before kickoff, during halftime and after the final whistle.
Do not trim the CSV to the gameplay halves or the public scoring window. The
scorer ignores frames whose ground-truth label is `X`; predictions do not need
to be masked there. Upload the CSV as the possession file; the JSON is a local
reproduction sidecar. The pipeline uses the requested name `submission.csv`;
the organisers ask for a team-named copy when uploading the final entry.

Existing outputs and symlinks are refused. Use a fresh directory for each rerun.
Both files are staged before publication; failure removes incomplete exports.
Logs and progress use stderr, and published output paths use stdout.

Score the submission separately with [step 06](../06_score_submission/README.md):

```bash
python -m src.pipelines.06_score_submission \
  --submission output/possession-10/submission.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output/possession-10
```

This writes `submission.scores.json`.

## Method

The data flow is **raw tracking → observed proximity and ball speed → control
confirmation → H/A/D labels**.

### Observed evidence

Coordinates are scaled into metres with the EPTS pitch dimensions. For every
frame, the nearest tracked player's team supplies raw team evidence. The first
XML team maps to `H` and the other to `A`; equal-distance ties follow XML
tracking-slot order. Missing ball coordinates or unavailable player distances
produce missing evidence. Finite off-pitch coordinates are retained.

Ball speed is derived only between consecutive source frames with complete
observed ball coordinates. Missing observations or missing frame intervals
interrupt this measurement; unavailable speed remains NaN. The source speed
channel is not used.

### Control candidates and ownership

`ControlConfirmation` evaluates each team's distance to the ball. A candidate
needs all of the following:

- A tracked player within two metres of the ball.
- At least a 0.5 m advantage over the nearest opposing player.
- Ball speed at most 12 m/s when speed is available. Unknown speed does not veto
  otherwise valid proximity evidence.

The first available raw nearest-team observation initializes ownership. After
that, an opposing candidate must persist for 0.4 seconds to transfer possession.
A confirmed transfer is backdated to its first supporting frame. Interrupted or
incumbent-team evidence resets pending confirmation.

When neither raw nearest-team evidence nor a control candidate is available,
current ownership can persist for up to two seconds. It expires after that
limit. Candidate-free frames with usable nearest-team evidence do not expire
ownership, so the model can retain the incumbent through contested play.

The final code maps directly to `H`, `A` or `D`. **D means ownership is missing
or has expired; it is not a detected dead ball.** Initialization, sustained
transfer and timeout behavior are the control rule itself. There is no separate
label-smoothing, gap-prefill or stoppage-detection stage.

## Policy and timing

All fixed values live in `configuration/policy.py`:

| Setting | Default |
| --- | ---: |
| `control_missing_timeout_seconds` | 2 seconds |
| `control_distance_m` | 2 metres |
| `control_advantage_m` | 0.5 metres |
| `control_ball_speed_mps` | 12 m/s |
| `control_confirmation_seconds` | 0.4 seconds |

The metadata-declared recording length and FPS determine the output timeline.
Confirmation uses `ceil(seconds × FPS)` frames and the missing-evidence timeout
uses `round(seconds × FPS)`. The pipeline applies no special halftime restriction
or reset. Backdating makes the output an offline inference result.

Nearest-player proximity remains a possession proxy, and missing ownership
cannot establish whether play stopped. These limitations should be considered
when interpreting the H/A/D submission and its scores.

## Code organization

```text
10_possession_control/
├── __main__.py                  # CLI arguments and logging
├── pipeline.py                  # Dependency construction and execution
├── configuration/
│   └── policy.py                # Control-distance and timing settings
├── models/
│   └── possession_features.py   # Typed frame evidence
├── evidence/
│   └── tracking_loader.py       # ATD-to-metre proximity and ball speed
├── inference/
│   └── control_confirmation.py  # Candidate selection and ownership state
└── export/
    └── submission.py            # Submission/sidecar serialization
```

The pipeline constructs `TrackingEvidenceLoader` and `ControlConfirmation`
explicitly. The control class receives its concrete policy through its
constructor, and the loader receives paths and metadata through `load()`.
Feature-specific code stays inside this package. Production imports use only
this package and shared `src/utilities/` code.

## Python API and checks

```python
from importlib import import_module
from pathlib import Path

run_pipeline = import_module("src.pipelines.10_possession_control").run_pipeline
csv_path, metadata_path = run_pipeline(
    tracking=Path("data/tactical/BAR-ATH_tactical_atd.txt"),
    metadata=Path("data/tactical/BAR-ATH_tactical_atd.xml"),
    output_dir=Path("output/possession-10"),
)
```

```bash
python -m src.pipelines.10_possession_control --help
python -m pytest tests/src/pipelines/10_possession_control
python -m black --check src/pipelines/10_possession_control \
  tests/src/pipelines/10_possession_control
```
