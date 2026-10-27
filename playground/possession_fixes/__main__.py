"""Compare physical-control and collective-stoppage hypotheses."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .runner import run_fix_experiments


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
        "--output-dir",
        type=Path,
        default=Path("playground/artifacts/possession_fixes_001"),
    )
    parser.add_argument(
        "--review-range",
        type=int,
        nargs=2,
        action="append",
        default=[],
        metavar=("START_FRAME", "END_FRAME_EXCLUSIVE"),
        help="Evaluation-only interval; repeat to review multiple errors",
    )
    args = parser.parse_args()
    configure_console_logging()
    print(
        run_fix_experiments(
            args.tracking,
            args.metadata,
            args.tags,
            args.ground_truth,
            args.output_dir,
            tuple(tuple(pair) for pair in args.review_range),
        )
    )


if __name__ == "__main__":
    main()
