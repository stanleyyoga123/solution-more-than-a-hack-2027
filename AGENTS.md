# Repository Guidelines

## Project Structure & Module Organization

This repository uses a data-engineering workflow for Barcelona–Athletic match data.
Organize production code as numbered, independently runnable pipeline packages
and shared utilities:

```text
src/
├── pipelines/
│   ├── 01_populate_pixels/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   ├── 02_normalize_2d/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   ├── 03_render_2d_tactical_video/
│   │   ├── __init__.py
│   │   ├── __main__.py
│   │   └── pipeline.py
│   └── ...
└── utilities/
    ├── atd_reader.py
    ├── epts_metadata.py
    ├── export_files.py
    └── ...
```

- Name pipeline folders `NN_descriptive_step_name`, with two-digit execution-order prefixes.
- Run steps one by one from the repository root using `python -m src.pipelines.NN_descriptive_step_name`.
- Each package owns its step-specific logic. Keep `__main__.py` focused on arguments and invocation; put substantial work in focused modules inside that package.
- Pipelines must not import, call, or automatically execute other pipelines. Shared code belongs in `src/utilities/`, with descriptive modules grouped by responsibility.
- Keep helpers used by only one pipeline inside that pipeline. Do not create abstractions for hypothetical reuse.
- Local production imports must stay inside `src/`; do not depend on root-level `utilities/`, `explorations/`, or `games.py`.
- Pass input paths explicitly and write generated artifacts under `output/` by default. Preserve the distinction between tactical and broadcast timelines.

`pyproject.toml` declares dependencies and Python `>=3.12`; `.python-version`
selects Python 3.12. Recording assets live in `data/tactical/` and
`data/broadcast/`, with visual previews in `data/overlay-preview/`.

## Build, Test, and Development Commands

Run commands from the repository root:

- `uv sync --group dev --extra test`: install project, formatter, and test dependencies.
- `source .venv/bin/activate`: activate the project environment on macOS/Linux.
- `python -m src.pipelines.01_populate_pixels --help`: inspect the pixel-export arguments.
- `python -m src.pipelines.02_normalize_2d --help`: inspect the normalized-export arguments.
- `python -m src.pipelines.03_render_2d_tactical_video --help`: inspect the minimap-video arguments; requires FFmpeg with `libx264` on PATH.
- `python -m pytest tests/src/pipelines tests/src/utilities`: run the pipeline and utility checks.
- `python -m black <paths>`: format the Python files being changed.
- `python -m black --check <paths>`: verify formatting before finishing a change.

See `src/pipelines/README.md` for complete invocations. Black is the required
Python formatter; its configuration lives in `pyproject.toml`. No linter is
configured. Declare new dependencies and tooling in `pyproject.toml`.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules and functions, `PascalCase`
for classes, and `UPPER_SNAKE_CASE` for constants. Numbered pipeline folders are
the intentional exception to ordinary Python module naming. Add type hints to
interfaces, keep code modular, and pass dependencies explicitly.

Format changed Python code with Black, using the configured 88-character line
length and Python 3.12 target. Prioritize readability beyond automated formatting:
break long calls, expressions, collections, and conditions across lines; use
named intermediate values when they clarify the logic. Avoid dense one-liners,
nested ternaries, and comprehensions that hide substantial work. Split long
strings with parenthesized adjacent literals when needed. Do not bypass Black
with formatting-disable comments merely to preserve compact code.

Assume supplied input data is valid and follows the documented format. This
project-specific rule overrides shared requirements for defensive input
validation, including Pydantic solely for validation: do not add schema-validation
layers, duplicate checks, frame-count audits, or broad exception wrappers solely
to defend against malformed datasets.
Use straightforward parsing and transformation; native errors can surface.
Lightweight typed structures are sufficient when no validation is needed.

Missing observations, `NaN`, and homography `valid=0` are expected data states,
not malformed inputs. Preserve their intended semantics. Keep operational
protections against overwriting inputs or existing outputs, and clean up
incomplete exports on failure.

## Logging & Progress Reporting

Always add useful logging to pipelines and substantial loading or processing
operations. Report the step being run, input paths, loading stages, and output
destinations. On successful completion, include processed frame or row counts
and elapsed time. Report completion only after outputs have been published.

Use `tqdm` for long-running loops when a total is available. In non-interactive
environments, use simple console logging with occasional progress updates
instead of animated bars. Keep output concise: do not log every frame, row, or
entity. Missing observations are normal data and should not produce warning spam.

Put shared logging/progress helpers in `src/utilities/`. Configure console
logging at CLI entry points, not during imports or inside reusable readers.
Use Python's `logging` module with descriptive messages and severity levels;
send logs and progress to stderr so stdout remains usable for output paths.
Close progress displays on failure, preserve the original exception, and do not
emit a success message for an incomplete export.

## Testing Guidelines

Use pytest and mirror production ownership under `tests/src/pipelines/` and
`tests/src/utilities/`, with reusable setup in `tests/fixtures/` and small static
samples in `tests/resources/`. Numbered packages can be loaded with
`importlib.import_module` in tests; exercise their `python -m` entry points too.
Name tests `test_<behavior>_<condition>`. Test transformed values, missing-data
semantics, and output safety without requiring full match videos. Do not retain
tests whose only purpose is input validation that this project intentionally
omits. No coverage threshold exists.

## Commit & Pull Request Guidelines

There are no commits yet, so no established message convention exists. Use concise imperative subjects, for example `Add tactical tracking reader`. Keep changes focused. PRs should explain behavior, link relevant issues, list checks actually run, and include screenshots for overlay changes.

## Data Handling

Do not commit gated match assets or generated tracking exports. `.gitignore`
excludes `data/` and `/output/`; inspect staged paths before committing. Treat
legacy starter documentation cautiously when it references files or commands
that are absent from this repository.
