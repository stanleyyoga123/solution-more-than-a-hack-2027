"""Assess same-slot identity continuity across null tracking intervals."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--flags", type=Path, required=True)
    parser.add_argument("--flags-metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--max-gap-seconds", type=float, default=2)
    parser.add_argument("--context-seconds", type=float, default=0.2)
    parser.add_argument("--player-prediction-tolerance", type=float, default=2)
    parser.add_argument("--ball-prediction-tolerance", type=float, default=3)
    args = parser.parse_args()
    configure_console_logging()
    for path in run_pipeline(
        args.tracking,
        args.metadata,
        args.flags,
        args.flags_metadata,
        args.output_dir,
        args.max_gap_seconds,
        args.context_seconds,
        args.player_prediction_tolerance,
        args.ball_prediction_tolerance,
    ):
        print(path)


if __name__ == "__main__":
    main()
