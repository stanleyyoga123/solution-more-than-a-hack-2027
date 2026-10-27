"""Correct normalized tracking with auditable identity links and interpolation."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .correction_policy import CorrectionPolicy
from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "tracking",
        "metadata",
        "flags",
        "flags-metadata",
        "gaps",
        "gaps-metadata",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--player-max-gap-seconds", type=float, default=3)
    parser.add_argument("--ball-max-gap-seconds", type=float, default=0.2)
    parser.add_argument("--spike-max-seconds", type=float, default=0.2)
    parser.add_argument("--context-seconds", type=float, default=0.2)
    parser.add_argument("--player-prediction-tolerance-m", type=float, default=2)
    parser.add_argument("--ball-prediction-tolerance-m", type=float, default=3)
    parser.add_argument("--uniqueness-margin-m", type=float, default=1)
    args = parser.parse_args()
    policy = CorrectionPolicy(
        args.player_max_gap_seconds,
        args.ball_max_gap_seconds,
        args.spike_max_seconds,
        args.context_seconds,
        args.player_prediction_tolerance_m,
        args.ball_prediction_tolerance_m,
        args.uniqueness_margin_m,
    )
    configure_console_logging()
    for path in run_pipeline(
        args.tracking,
        args.metadata,
        args.flags,
        args.flags_metadata,
        args.gaps,
        args.gaps_metadata,
        args.output_dir,
        policy,
    ):
        print(path)


if __name__ == "__main__":
    main()
