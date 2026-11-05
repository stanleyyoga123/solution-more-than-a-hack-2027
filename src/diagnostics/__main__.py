"""CLI for offline diagnostic generation."""

import argparse
from pathlib import Path
from src.diagnostics.report import generate_report
from src.utilities.pipeline_logging import configure_console_logging


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("normalized", "metadata", "baseline", "ground-truth"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("output/diagnostics.json"))
    parser.add_argument("--smart-tagging", type=Path)
    parser.add_argument("--event-window-seconds", type=float, default=5)
    parser.add_argument("--transition-tolerance-frames", type=int, default=25)
    args = parser.parse_args()
    configure_console_logging()
    print(
        generate_report(
            args.normalized,
            args.metadata,
            args.baseline,
            args.ground_truth,
            args.output,
            smart_tagging=args.smart_tagging,
            event_window_seconds=args.event_window_seconds,
            transition_tolerance_frames=args.transition_tolerance_frames,
        )
    )


if __name__ == "__main__":
    main()
