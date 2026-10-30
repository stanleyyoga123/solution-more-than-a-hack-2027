# Experimental Possession Inference

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

## Description

Step 09 is a small experimental foundation, requiring no exports from steps 01–08.
It reads raw tactical ATD and matching EPTS XML through the shared readers.
Source ATD IDs are one-based video frames; the reader subtracts one. Do not
supply broadcast data or Smart Tagging IdFrame counters.

Run commands from the repository root with the project environment active.
The CLI requires `--tracking`, `--metadata` and `--strategy nearest-continuity`.
`--output-dir` defaults to `output/`; use a fresh directory for each inference run.

```bash
python -m src.pipelines.09_possession_inference \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --strategy nearest-continuity \
  --max-gap-frames 25 \
  --output-dir output/possession-09

python -m src.pipelines.06_score_submission \
  --submission output/possession-09/possession_inference.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output/possession-09
```

The CSV always has columns `frame,label` and 199,319 rows, frames 0–199318.
The published inclusive gameplay halves are 11185–90651 and 110808–190197
([official constants](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/games.py)).
All other frames are `X`. Each half is processed independently.

`nearest-continuity` uses the same metre-scaled nearest-player calculation and
slot-order distance ties as step 05; the first XML team is H. Its small evidence
function stays local because step 05 is frozen. Missing ball positions or no
usable player distances yield unknown evidence. A complete unknown run is filled
only when its length is at most `--max-gap-frames` (default 25, one second at
25 FPS) and both observed endpoints have the same team within the same half.
Zero disables filling. Longer, unbounded, or conflicting gaps remain `X`.
Observed H/A changes are preserved immediately; there is no majority smoothing.
This is a minimal new policy, not migration of the research E1–E4 implementations.

Outputs are `possession_inference.csv` and `possession_inference.metadata.json`.
The sidecar records strategy/version, parameters, absolute input references,
execution start/time/runtime versions, team mapping, pitch dimensions, gameplay
bounds, processed counts, filled frames and H/A/D/X occupancy. Repeated runs have
identical CSV bytes; execution timestamps and durations intentionally vary.
Existing files and symlinks are refused; failure cleans up the staged pair.
CLI logging/progress goes to stderr and published paths to stdout.

The [step 06](../06_score_submission/README.md) command above validates and
scores the CSV, writing `possession_inference.scores.json` in the same directory.
It does not consume the metadata sidecar.

There is no dead-ball evidence: D occupancy is always zero. Nearest-player
identity is only a proxy for control, and short same-team gaps can contain unseen
turnovers or stoppages. X is an abstention, not a dead-ball prediction. There is
no validated performance improvement over step 05, and no claim about private
full-match performance. Parameters must not be tuned against the public sample.
Report Pipeline 06's `n_pred_spells` as a public-scored-window count, separately
from full-match frame occupancy.

Reproduce synthetic checks without licensed assets:

```bash
python -m pytest tests/src/pipelines/09_possession_inference
python -m black --check src/pipelines/09_possession_inference \
  tests/src/pipelines/09_possession_inference
```

The local official validator is `src.utilities.possession_metrics.validate_submission`;
pass the loaded submission table and expected row count 199319. Pipeline 06
also validates before scoring. Licensed inputs and all generated artifacts stay
in ignored `data/` and `output/` directories.

## How It Works

Pipeline 09 is a deterministic **nearest-player possession classifier with short-gap continuity**. It uses the same basic player–ball proximity assumption as Pipeline 05, but preserves missing evidence as `X` and only fills certain short unknown intervals. It is an experimental foundation, **not** a demonstrated improvement over the baseline.

## Pipeline workflow

```text
Tactical ATD tracking + EPTS (Electronic Performance and Tracking Systems) metadata
                  |
                  v
Step 1: Nearest-player evidence for each gameplay frame
          H / A / X
                  |
                  v
Step 2: Short-gap continuity (default: 25 frames)
          H / A / X
                  |
                  v
Submission CSV: frame,label (199,319 frames)
```

The pipeline processes the tactical video timeline, using the published first- and second-half frame boundaries. It outputs `X` outside those halves and never bridges a gap across halftime. **It does not infer `D` (dead ball).**

## Step 1 — Nearest-player classification

For each gameplay frame, the pipeline reads the tracked ball and player coordinates, plus the players' team membership. Normalized pitch coordinates are converted into metres using the pitch dimensions in the EPTS metadata. It calculates the Euclidean distance between the ball and each tracked player:

\[
d_i = \sqrt{(x_i-x_b)^2 + (y_i-y_b)^2}
\]

The team of the nearest player with a valid distance becomes the frame's evidence label: `H` for Barcelona or `A` for Athletic Club. If no finite player–ball distance exists, the evidence label is `X` (unknown). Equal-distance ties follow tracking-slot order.

**Assumption:** The nearest player's team is a proxy for possession, not proof of controlled possession. A defender challenging the ball, a loose ball, or a deflection can make this proxy wrong.

## Step 2 — Short-gap continuity

The algorithm examines runs of `X` **within each half**. It fills an entire unknown run only if:

1. Its length is at most `max_gap_frames` (default **25 frames = 1 second** at 25 FPS).
2. Both immediately surrounding **observed** labels exist and are the **same team** (`H`/`H` or `A`/`A`).

Examples:

```text
Before: H H X X X H H     After: H H H H H H H
Before: H H X X X A A     After: H H X X X A A
```

A longer gap remains `X` even if its endpoints agree. Observed `H` and `A` labels are never changed. Previously filled gaps are not reused as new evidence. This is **gap filling, not majority-vote smoothing or temporal decoding**.

## How it differs from Pipeline 05

| Behavior | Pipeline 05 — baseline | Pipeline 09 — nearest-continuity |
|---|---|---|
| Initial team evidence | Nearest tracked player | Nearest tracked player |
| Missing usable player–ball evidence | Initially `D` | `X` (unknown) |
| Temporal treatment | Centered majority vote (default ±50 frames) | Fill only short `X` runs with matching observed endpoints |
| Suppresses isolated observed H↔A switches | Can, through smoothing | **No** — observed labels remain unchanged |
| Dead-ball predictions | Can produce `D`, though imperfectly | **Never produces `D`** |
| Halftime | No explicit reset of the vote window | Halves processed separately |

For example, Pipeline 09 leaves `H H H A H H H` unchanged, even if the isolated `A` is a proximity error. Pipeline 05's smoothing can suppress that kind of brief switch.

## Why it performed poorly

On the **public five-minute labelled window** (17 ground-truth possessions), the reported evaluation was:

| Metric | Pipeline 09 | Pipeline 05 (`baseline_smooth50`) |
|---|---:|---:|
| `spellF1` | **0.0441** | **0.3256** |
| `macroF1` | 0.4575 | 0.6207 |
| Predicted possessions | **128** | **26** |
| Dead-ball F1 | **0.0000** | **0.3225** |

Three limitations explain the direction of these results:

1. **Severe fragmentation:** Without smoothing of observed team labels, brief nearest-player changes create extra H↔A possession boundaries. Pipeline 09 predicted 128 possessions against 17 true possessions, with a mean predicted spell duration of 2.34 seconds versus 14.19 seconds in the ground truth.
2. **No dead-ball inference:** Pipeline 09 cannot emit `D`. Its public confusion matrix had zero `D` predictions. The official `spellF1` scorer fills `X` with a nearby prior label within the half, so abstaining does not independently identify stoppages.
3. **Limited gap coverage:** The default one-second bridge cannot resolve long missing-ball intervals. The earlier tracking analysis found a median gap of 10.72 seconds within the published gameplay halves. Long gaps remain `X`, and the model cannot infer genuine changes occurring within them.

These are primarily **model-design limitations**, not proof of an implementation bug. The small public window cannot establish full-match ranking performance. Pipeline 09 should therefore be treated as a reproducible inference starting point, **not a competitive replacement for Pipeline 05**.

