"""Command-line entry point for submission validation and scoring."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--submission", type=Path, required=True, help="frame,label CSV to score"
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        required=True,
        help="frame,label ground truth, e.g. the organisers' public 5-minute file",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    configure_console_logging()
    print(run_pipeline(args.submission, args.ground_truth, args.output_dir))


if __name__ == "__main__":
    main()
