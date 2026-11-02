"""Run the browser viewer from the repository root with python -m frontend."""

import argparse
import logging
from pathlib import Path

from frontend.server.application import create_server
from src.utilities.pipeline_logging import configure_console_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare camera and pitch tracking.")
    parser.add_argument(
        "--video", type=Path, default=Path("data/tactical/BAR-ATH_tactical-001.mp4")
    )
    parser.add_argument(
        "--pixels", type=Path, default=Path("output/tracking_pixels.csv")
    )
    parser.add_argument(
        "--normalized", type=Path, default=Path("output/tracking_normalized_2d.csv")
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("output/tracking_normalized_2d.metadata.json"),
    )
    parser.add_argument(
        "--birdseye-video",
        type=Path,
        help="Warped footage; defaults to output/tactical_birdseye.mp4 when present",
    )
    parser.add_argument(
        "--birdseye-start-seconds",
        type=float,
        default=0.0,
        help="Source start time used to render a trimmed bird's-eye clip",
    )
    parser.add_argument("--cache-dir", type=Path, default=Path("output/frontend"))
    parser.add_argument(
        "--trajectory-flags",
        type=Path,
        help="Step 07 CSV; defaults to output/tracking_trajectory_flags.csv when present",
    )
    parser.add_argument(
        "--gap-continuity",
        type=Path,
        help="Step 08 CSV; defaults to output/tracking_gap_continuity.csv when present",
    )
    parser.add_argument(
        "--diagnostics",
        type=Path,
        help="Offline diagnostic JSON; defaults to output/diagnostics.json when present",
    )
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    configure_console_logging()
    birdseye_video = args.birdseye_video
    if birdseye_video is None:
        default_birdseye = Path("output/tactical_birdseye.mp4")
        if default_birdseye.is_file():
            birdseye_video = default_birdseye
    trajectory_flags = args.trajectory_flags
    if trajectory_flags is None:
        default_flags = Path("output/tracking_trajectory_flags.csv")
        if default_flags.is_file():
            trajectory_flags = default_flags
    gap_continuity = args.gap_continuity
    if gap_continuity is None:
        default_gaps = Path("output/tracking_gap_continuity.csv")
        if default_gaps.is_file():
            gap_continuity = default_gaps
    diagnostics = args.diagnostics
    if diagnostics is None:
        default_diagnostics = Path("output/diagnostics.json")
        if default_diagnostics.is_file():
            diagnostics = default_diagnostics
    with create_server(
        args.video,
        args.pixels,
        args.normalized,
        args.metadata,
        args.cache_dir,
        args.port,
        birdseye_video=birdseye_video,
        birdseye_start_seconds=args.birdseye_start_seconds,
        trajectory_flags=trajectory_flags,
        gap_continuity=gap_continuity,
        diagnostics=diagnostics,
    ) as server:
        logging.getLogger(__name__).info(
            "Tracking viewer ready: http://127.0.0.1:%d", server.server_port
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.getLogger(__name__).info("Stopping tracking viewer")


if __name__ == "__main__":
    main()
