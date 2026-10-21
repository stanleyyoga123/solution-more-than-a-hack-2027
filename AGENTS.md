# Repository Guidelines

## Project Structure & Module Organization

This repository is an early Python scaffold for work with Barcelona–Athletic match data.

- `main.py`: executable entry point; currently prints a greeting.
- `pyproject.toml`: project metadata, Python requirement (`>=3.12`), and dependencies (currently empty).
- `.python-version`: selects Python 3.12.
- `data/tactical/` and `data/broadcast/`: recording-specific tracking metadata and available media.
- `data/overlay-preview/`: overlay image and video previews.

There is no application package or test suite yet. As functionality grows, place cohesive modules under `src/` and keep `main.py` focused on startup. Keep tactical and broadcast timelines distinct.

## Build, Test, and Development Commands

Run commands from the repository root:

- `python3 --version`: confirm Python 3.12 or newer.
- `python3 -m venv .venv`: create an isolated environment.
- `source .venv/bin/activate`: activate it on macOS/Linux.
- `python3 main.py`: run the current scaffold; expect `Hello from barcelona-go-go!`.

No build, lint, formatting, or test commands are configured. Declare new dependencies and tooling in `pyproject.toml` and document their commands when introduced.

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` for modules and functions, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for constants. Add type hints to new interfaces. Keep modules focused, pass dependencies explicitly, and validate external data at entry points. Prefer descriptive names such as `tracking_reader.py` over catch-all utility files. No formatter or linter is currently configured.

## Testing Guidelines

Use pytest when introducing automated tests; it is not installed as a project dependency yet. Mirror production modules under `tests/src/`, with reusable setup in `tests/fixtures/` and small static samples in `tests/resources/`. Name tests `test_<behavior>_<condition>`. Test observable results and meaningful failure cases without requiring full match videos. Document `python3 -m pytest` once configured. No coverage threshold exists.

## Commit & Pull Request Guidelines

There are no commits yet, so no established message convention exists. Use concise imperative subjects, for example `Add tactical tracking reader`. Keep changes focused. PRs should explain behavior, link relevant issues, list checks actually run, and include screenshots for overlay changes.

## Data Handling

Do not commit gated match assets. The current `.gitignore` does **not** exclude them; inspect staged paths before committing. Treat `data/README.md` cautiously: its references to `games.py`, `DATA.md`, and an evaluation runner describe files absent from this scaffold.
