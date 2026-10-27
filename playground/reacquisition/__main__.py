"""Test physically impossible player reappearances after missing observations."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging
from .runner import run_reacquisition_experiments


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tracking", type=Path, default=Path("data/tactical/BAR-ATH_tactical_atd.txt")
    )
    parser.add_argument(
        "--metadata", type=Path, default=Path("data/tactical/BAR-ATH_tactical_atd.xml")
    )
    parser.add_argument(
        "--tags",
        type=Path,
        default=Path("data/tactical/BAR-ATH_tactical_smart_tagging.xml"),
    )
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument(
        "--split-discontinuities",
        action="store_true",
        help="Quarantine physical tracklets split at impossible consecutive jumps",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("playground/artifacts/reacquisition_001"),
    )
    parser.add_argument(
        "--review-range",
        type=int,
        nargs=2,
        action="append",
        default=[],
        metavar=("START_FRAME", "END_FRAME_EXCLUSIVE"),
    )
    args = parser.parse_args()
    configure_console_logging()
    print(
        run_reacquisition_experiments(
            args.tracking,
            args.metadata,
            args.tags,
            args.ground_truth,
            args.output_dir,
            tuple(tuple(pair) for pair in args.review_range),
            args.split_discontinuities,
        )
    )


if __name__ == "__main__":
    main()
