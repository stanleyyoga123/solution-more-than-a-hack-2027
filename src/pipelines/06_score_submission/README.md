# 06 — Validate and score a submission

[All pipelines](../README.md) · [Dependency diagrams](../../../README.md#pipeline-dependencies)

Run commands from the repository root with the project environment active.
Step 06 reads a `frame,label` submission CSV and a ground-truth CSV. The
submission can come from [step 05](../05_possession_baseline/README.md),
[step 09](../09_possession_inference/README.md),
[step 10](../10_possession_control/README.md),
[step 11](../11_possession_deadball/README.md), or another method. It does
not consume submission metadata or run inference automatically.

```bash
python -m src.pipelines.06_score_submission \
  --submission output/possession_baseline.csv \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --output-dir output
```

## Ground truth and interpretation

The public ground truth is `evaluation/gt/BAR-ATH_possession_gt_public.csv` in
the [organisers' repository](https://github.com/metrica-sports/more-than-a-hack-2027).
It covers five minutes and 17 possessions. Use it to check the pipeline, not
to tune parameters or infer private full-match performance. Keep submission
frames on the tactical video timeline.

The pipeline checks the competition submission format and scores it with
`src/utilities/possession_metrics.py`, an unchanged copy of the official scorer.
Validation failures raise an error before a score report is written. Headline
logs report `spellF1`, `macroF1`, and predicted versus ground-truth possession
counts. Those counts describe the scored window, whereas an inference
pipeline's metadata can describe the whole recording.

## Output

The output directory defaults to `output/`. Each run writes all returned official
metrics to `{submission_stem}.scores.json`: for example,
`possession_baseline.scores.json` or `possession_inference.scores.json`.
Existing reports are refused. Score one submission per invocation; use a fresh
output directory to score the same submission again.

Logs go to stderr and the published report path goes to stdout. The submission
CSV and ground-truth CSV are not modified.

## Checks

```bash
python -m pytest tests/src/pipelines/06_score_submission
```
