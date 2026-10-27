"""Command-line entry point for the pixel export."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracking", type=Path, required=True, help="Raw ATD text file"
    )
    parser.add_argument(
        "--metadata", type=Path, required=True, help="EPTS metadata XML"
    )
    parser.add_argument(
        "--homography", type=Path, required=True, help="Per-frame homography CSV"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    args = parser.parse_args()
    configure_console_logging()
    for path in run_pipeline(
        args.tracking, args.metadata, args.homography, args.output_dir
    ):
        print(path)


if __name__ == "__main__":
    main()
