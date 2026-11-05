"""Generate a possession submission from team touches and dead-ball detection."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracking", type=Path, required=True, help="Raw tactical ATD text"
    )
    parser.add_argument(
        "--metadata", type=Path, required=True, help="Matching EPTS XML"
    )
    parser.add_argument(
        "--smart-tagging",
        type=Path,
        required=True,
        help="Tactical Smart Tagging SportsCode XML",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    configure_console_logging()
    paths = run_pipeline(
        args.tracking, args.metadata, args.smart_tagging, args.output_dir
    )
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
