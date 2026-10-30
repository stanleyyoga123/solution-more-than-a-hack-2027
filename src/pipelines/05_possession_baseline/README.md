# 05 — Generate the possession baseline

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.
This pipeline reads raw tactical ATD and matching EPTS XML directly; it does
not require pixel or normalized exports.

```bash
python -m src.pipelines.05_possession_baseline \
  --tracking data/tactical/BAR-ATH_tactical_atd.txt \
  --metadata data/tactical/BAR-ATH_tactical_atd.xml \
  --window 50 \
  --output-dir output
```

## Method

Player and ball coordinates are converted to metres using the XML pitch
dimensions. Each frame's evidence is the team of the tracked player nearest
the ball. The first XML team maps to `H` and the other team to `A`; equal player
distances follow tracking-slot order. Missing ball coordinates or no usable
player distances leave the frame without team evidence.

A centred vote counts `H` and `A` evidence within ±`--window` frames (default
50). Ties go to `H`; a window with no team evidence produces `D`. Consequently,
a frame with a missing ball can still receive a team label from nearby frames.
Use `--window 0` to retain the unsmoothed nearest-player result. The vote is
clipped at recording boundaries and has no explicit halftime reset.

Distances use the metadata's 105 × 68 m pitch, rather than the organisers'
measured 105.3 × 68 m. A few frames differ from their `baseline_smooth50.csv`;
the reported public-window scores are the same. Nearest-player proximity and
missing evidence are heuristics for possession and dead balls.

## Outputs and scoring

The output directory defaults to `output/`. The pipeline writes:

- `possession_baseline.csv`: `frame,label` rows for every source frame, using
  zero-based frame numbers and `H`, `A` or `D` labels.
- `possession_baseline.metadata.json`: method, vote window, frame count,
  frames with usable team evidence, label counts and team mapping.

Existing outputs are refused; use a fresh output directory for another run.
Both artifacts are staged before publication, and failure cleans up the pair.
Logs and progress go to stderr; published output paths go to stdout.

Score the CSV with [step 06](../06_score_submission/README.md). For the
experimental strategy that preserves unknown evidence as `X` and fills only
short same-team gaps, see [step 09](../09_possession_inference/README.md).

## Checks

```bash
python -m pytest tests/src/pipelines/05_possession_baseline
```
