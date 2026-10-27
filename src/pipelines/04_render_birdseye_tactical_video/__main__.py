"""Render a selected tactical-video interval from a bird's-eye perspective."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--video", type=Path, required=True, help="Original tactical video"
    )
    parser.add_argument(
        "--homography", type=Path, required=True, help="Frame-aligned homography CSV"
    )
    parser.add_argument(
        "--metadata", type=Path, required=True, help="Original ATD XML metadata"
    )
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--start-seconds", type=float, default=0.0)
    parser.add_argument("--duration-seconds", type=float)
    args = parser.parse_args()
    configure_console_logging()
    output = run_pipeline(
        args.video,
        args.homography,
        args.metadata,
        args.output_dir,
        args.start_seconds,
        args.duration_seconds,
    )
    print(output)


if __name__ == "__main__":
    main()
