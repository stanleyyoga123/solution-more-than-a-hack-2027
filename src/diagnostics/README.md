# Offline Data & Diagnostics

Run `python -m src.diagnostics --help`. The default output,
`output/diagnostics.json`, is automatically discovered by `python -m frontend`;
`--diagnostics` remains available for a custom report path. This package consumes existing artifacts;
it does not import or execute pipelines and does not modify the official evaluator.
See [the frontend guide](../../frontend/README.md#data--diagnostics) for a complete
regeneration command, visualizations and diagnostic definitions.

- `tracking.py`: one streaming CSV scan for Stage 1 availability and public geometry.
- `geometry.py`: nearest finite player distance in metres; exact ECDFs and medians.
- `events.py`: Smart Tagging XML phases at 25 FPS, frequency and union overlap.
- `failures.py`: public-window error/candidate intervals with overlapping categories.
- `report.py`: official Stage 1 scores, offline composition, fingerprints and publication.

Public-labelled geometry, event overlap and failure cases use only H/A/D truth.
Full-match availability and event frequency are descriptive. Reports record source
paths and SHA-256 fingerprints, generation UTC timestamp, schema version and matching
parameters. Browser responses are an allowlisted projection with source basenames;
there is no HTTP generation or mutation endpoint. Missing observations stay missing.

The same output path can be reused. Reports are written to a temporary file in
the destination directory and atomically replace the previous report only after
the complete JSON has been written. Failed runs preserve the previous report and
clean up temporary output. Input files cannot be used as output paths. Logs include input stages, periodic row progress and completion counts only
after publication. Generated data belongs under ignored `output/`; synthetic tests
need no licensed assets. Matching metadata and tactical frame timelines are assumed.

```bash
.venv/bin/python -m pytest tests/src/diagnostics tests/frontend/server/test_diagnostics.py -q
node --test tests/frontend/web/*.test.mjs
.venv/bin/python -m black --check --workers 1 src/diagnostics tests/src/diagnostics
```
