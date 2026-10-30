"""Generate an experimental full-match tactical possession submission."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracking", type=Path, required=True, help="Tactical ATD text"
    )
    parser.add_argument(
        "--metadata", type=Path, required=True, help="Matching EPTS XML"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--strategy", choices=["nearest-continuity"], required=True)
    parser.add_argument("--max-gap-frames", type=int, default=25)
    args = parser.parse_args()
    configure_console_logging()
    for path in run_pipeline(
        args.tracking,
        args.metadata,
        args.output_dir,
        args.strategy,
        args.max_gap_frames,
    ):
        print(path)


if __name__ == "__main__":
    main()
