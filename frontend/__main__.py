"""Run the browser viewer from the repository root with python -m frontend."""

import argparse
import logging
from pathlib import Path

from frontend.server.application import create_server
from src.utilities.pipeline_logging import configure_console_logging


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare camera and pitch tracking.")
    parser.add_argument(
        "--video", type=Path, default=Path("data/tactical/BAR-ATH_tactical-002.mp4")
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
    parser.add_argument("--cache-dir", type=Path, default=Path("output/frontend"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    configure_console_logging()
    with create_server(
        args.video,
        args.pixels,
        args.normalized,
        args.metadata,
        args.cache_dir,
        args.port,
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
