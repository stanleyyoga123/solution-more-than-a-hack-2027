"""Run fixed uncertainty and possession-boundary experiments."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .runner import run_fragmentation_experiments


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
        default=Path("playground/artifacts/fragmentation_001"),
    )
    args = parser.parse_args()
    configure_console_logging()
    print(
        run_fragmentation_experiments(
            args.tracking, args.metadata, args.tags, args.ground_truth, args.output_dir
        )
    )


if __name__ == "__main__":
    main()
