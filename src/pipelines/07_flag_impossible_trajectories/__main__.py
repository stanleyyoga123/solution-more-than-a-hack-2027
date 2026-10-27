"""Flag excessive player and ball motion in normalized tracking."""

import argparse
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .pipeline import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("output"))
    parser.add_argument("--player-speed-limit", type=float, default=12)
    parser.add_argument("--player-acceleration-limit", type=float, default=15)
    parser.add_argument("--ball-speed-limit", type=float, default=45)
    args = parser.parse_args()
    configure_console_logging()
    for path in run_pipeline(
        args.tracking,
        args.metadata,
        args.output_dir,
        args.player_speed_limit,
        args.player_acceleration_limit,
        args.ball_speed_limit,
    ):
        print(path)


if __name__ == "__main__":
    main()
