# Experiment registry

Record a possession experiment once, keep its provenance and official scores in
Git, and regenerate a shared comparison without a database or tracking server.
The registry reads existing outputs; it never runs inference, tunes parameters,
or evaluates a submission.

## Record an experiment

From the repository root, with the project environment active:

```bash
python scripts/record_experiment.py \
  --submission output/possession-11/possession_deadball.csv \
  --metadata output/possession-11/possession_deadball.metadata.json \
  --scores output/possession-11/possession_deadball.scores.json
```

This works with the existing outputs of Pipelines 05, 09, 10 and 11. Always
supply the matching three artifacts explicitly: Pipeline 06 does **not** embed
its submission hash, so the registry cannot prove they belong together.

When known, supply the evaluation provenance when recording, for example:

```bash
python scripts/record_experiment.py \
  --submission output/possession-11/possession_deadball.csv \
  --metadata output/possession-11/possession_deadball.metadata.json \
  --scores output/possession-11/possession_deadball.scores.json \
  --recording-id BAR-ATH_tactical \
  --dataset-id BAR-ATH-public-five-minute \
  --scope public \
  --ground-truth path/to/BAR-ATH_possession_gt_public.csv \
  --ground-truth-id BAR-ATH-public \
  --evaluator-id metrica-possession-metrics \
  --evaluator-version 3de6b60 \
  --description 'Ownership with explicit dead-ball detection'
```

Only assert `3de6b60` when that is the official scorer revision actually used.
The current source header names that revision, but it does not prove which
version produced an old score file. `--ground-truth-sha256` and
`--evaluator-sha256` accept known fingerprints when the original files are not
available. `--ground-truth` hashes the exact file supplied, without copying it.
A supplied hash must agree with a supplied ground-truth file.

`--hypothesis` and `--notes` are optional text. `--pipeline` and `--strategy`
can explicitly identify another method. `--registry` selects a separate
registry (useful for scratch experiments); `--repository` selects the checkout
whose recording-time provenance is captured. Paths supplied to the CLI are
relative to the working directory. Default registry: this repository's
`experiments/`. Use `--help` for all arguments.

Unknown provenance stays null; evaluation scope defaults to `unknown`. Future
score documents may include `dataset_id`, `scope`, `ground_truth` (`id`,
`sha256`) and `implementation` (`id`, `version`, `sha256`). Explicit CLI values
can supply or override these fields. Current Pipeline 06 emits none of them.

## Compare experiments

```bash
python scripts/compare_experiments.py
```

This regenerates [registry.csv](reports/registry.csv) from `runs/*.json` and
prints a compact table preview after successful publication. No Markdown report
is generated. The preview shows run fingerprint, pipeline, spellF1, macroF1,
D F1, evaluated possession count, fragmentation and reproducibility flags.
`dirty` means the checkout was dirty at recording; `unknown` means provenance
is incomplete. Full warnings, strategy, commits and exact metrics remain in CSV.

Rows are grouped by scope/dataset/ground-truth/evaluator identity, then ordered
by pipeline, strategy and run ID in the CSV. The terminal preview sorts all rows
by spellF1 descending, then macroF1 descending, with missing scores last and
run ID breaking remaining ties. Its Eval column identifies each evaluation group;
ordering does not establish full-match superiority. The terminal preview rounds
metrics to four decimals; the CSV retains full precision. Unknown values are
blank in CSV and dashes in the preview; recorded zeroes remain zeroes.
Unchanged manifests produce identical CSV bytes.

The CSV is published atomically. Symlink report destinations and files without
the generated report header are refused. Resolve Git report conflicts by
regenerating the CSV after combining manifests.

## What is captured

Each compact JSON manifest has `schema_version: 1` and these sections:

| Section | Contents |
| --- | --- |
| `identity` | Pipeline, strategy/version, exact recorded configuration, recording identifier, recording commit, submission hash and evaluation identity |
| `artifacts` | Paths and SHA-256 of the supplied submission, metadata and scores |
| `provenance.recording` | Current commit, dirty-tree status (including untracked files), Python/NumPy/pandas/tqdm versions and `uv.lock` hash |
| `provenance.execution` | Original Python/NumPy versions, start time and elapsed time where metadata supplies them; unknown original Git/lockfile provenance |
| `provenance.inputs` | Hashes of accessible tracking/XML inputs named by metadata, measured at recording time; missing files retain null hashes |
| `evaluation` | Dataset/scope, ground-truth identity/hash, evaluator identity/version/hash and selected official metrics |
| `prediction_statistics` | Full-submission frame count, label counts and available X count |
| `experiment` | UTC recording timestamp, description, hypothesis and notes |

Pipeline 05 uses `window_frames`; Pipeline 09 uses `parameters` plus
`halves_inclusive`; Pipelines 10/11 use the entire `policy`. Method strings map
to known pipeline names without importing or running those pipelines. Unknown
methods remain unidentified unless you supply `--pipeline`.

The registry records the parameter values present in metadata; it cannot recover
unreported implementation constants. Pipeline 05 has no source paths or runtime
versions, and none of the four stores an explicit recording ID or execution Git
SHA. Supply recording identity yourself, keeping tactical and broadcast separate.

### Metric scopes and meanings

Values are copied from Pipeline 06 without recalculation or changed definitions:

| Registry metric | Official source |
| --- | --- |
| `spell_f1_mean`, `macro_f1` | Same-named fields |
| `dead_ball_f1` | `per_class.D.f1`, not `alive_dead_f1` |
| `transition_f1` | `transitions.<tolerance in frames>.f1`; preserve each tolerance separately |
| `fragmentation` | `fragmentation` (segment ratio, not possession-count ratio) |
| `predicted_possession_count` | `n_pred_spells` |
| `ground_truth_possession_count` | `n_gt_spells` |
| `mean_possession_duration_s` | `mean_spell_duration_s` |
| `abstention_count` | `n_abstain_on_graded` |
| `graded_frame_count` | `n_graded` |

All evaluation metrics refer to **ground-truth graded frames**, even when the
input CSV spans the entire match. Temporal metrics retain the official scorer's
abstention-filling semantics. `prediction_statistics.scope: full_submission`
keeps metadata label counts separate. It includes off-play frames when present;
it is not a claim about graded full-match performance. None of the current
metadata exports supplies full-match possession count or mean duration, so those
fields remain null. An absent X count also remains null rather than becoming zero.

The public ground truth contains only **five minutes and 17 possessions**. It is
useful for checking the workflow, not tuning parameters, choosing a winner, or
establishing reliable full-match superiority. Compare only compatible evaluation
identities; unknown identities do not establish compatibility even if grouped
together. The report never selects a winning model.

## Identity, duplicates and immutability

The full fingerprint is SHA-256 of canonical JSON identity (sorted keys, fixed
serialization). Filenames use the pipeline and its first 16 fingerprint digits.
Identity includes configuration, method version, recording ID, recording-time
commit, submission hash, dataset/scope, ground-truth identity/hash and evaluator
identity/version/hash. A different ground truth or evaluator is a distinct record.

Recording timestamps, descriptions, notes, absolute paths, metadata/scores file
hashes and dirty status do not create new identities. Repeating the same identity
fails with the existing manifest path, even after the registry itself dirties the
working tree or a manifest is renamed. A filename collision also fails; existing
manifests, including symlinks, are never overwritten. There is no force flag.

An identical identity with different score bytes is refused as a duplicate too:
resolve which evaluation provenance differs instead of hiding it in another run.
Unknown ground truths/evaluators cannot distinguish evaluations reliably; provide
that provenance up front. To correct identity/provenance, record a new identified
entry and explain it in notes; do not edit an old manifest. Notes are fixed at
recording time. The CLI enforces append-only publication; Git review must enforce
that teammates do not manually rewrite or delete historical files.

A dirty tree is prominently warned about. A commit does not identify its
uncommitted code, and recording-time facts do not prove the code/environment
used for an older artifact. Original execution Git state and lockfile hashes
remain unknown. Current input fingerprints likewise do not prove those files
were unchanged since inference. Record immediately after running, retain original
artifacts locally, and inspect these limitations during review.

## Contributing through Git

1. Run inference and evaluation independently, keeping outputs under `output/`.
2. Record once with known provenance and a useful description/hypothesis.
3. Generate reports and inspect the new manifest and warnings.
4. Stage only the intended manifest, regenerated reports and any documentation.
5. Submit those changes through the team's normal Git review process.

Never commit licensed videos, raw tracking coordinates, full prediction CSVs,
frame-level arrays, or copied score transition-event arrays. The registry keeps
only selected aggregates and hashes; it does not copy input artifacts. Do not
paste sensitive data into free-text notes. Existing `data/` and `output/` ignore
rules remain unchanged. Inspect staged paths before committing.

The registry includes a real Pipeline 05 baseline run with the default 50-frame
smoothing window, scored by Pipeline 06 against the public ground truth. Its
ground-truth and evaluator fingerprints are recorded. Imported local 09/10/11
artifacts retain unknown historical evaluation provenance. Synthetic examples
remain in test fixtures only; the original demonstration manifest was moved to
ignored `output/experiment-registry-demo-archive/`.

## Checks

```bash
python -m pytest tests/src/utilities/test_experiment_tracking.py -q
python -m black --check src/utilities/experiment_tracking.py scripts \
  tests/fixtures/experiment_tracking.py tests/src/utilities/test_experiment_tracking.py
python scripts/record_experiment.py --help
python scripts/compare_experiments.py --help
```

Tests use synthetic artifacts and temporary Git repositories; licensed data is
not required.
