"""Recover sparse missing-ball observations with a pretrained YOLO model."""

import argparse
import os
from pathlib import Path

from src.utilities.pipeline_logging import configure_console_logging

from .policy import VisionPolicy
from .recovery import run_recovery


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--tracking", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--homography", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-stride", type=int, default=25)
    parser.add_argument("--max-control-frames", type=int, default=200)
    parser.add_argument("--image-size", type=int, default=1280)
    parser.add_argument("--max-samples", type=int, default=0)
    args = parser.parse_args()
    os.environ.setdefault("YOLO_CONFIG_DIR", "playground/artifacts/ultralytics")
    configure_console_logging()
    policy = VisionPolicy(
        sample_stride=args.sample_stride,
        max_control_frames=args.max_control_frames,
        image_size=args.image_size,
        maximum_samples=args.max_samples,
    )
    for path in run_recovery(
        args.video,
        args.tracking,
        args.metadata,
        args.homography,
        args.weights,
        args.output_dir,
        policy,
    ):
        print(path)


if __name__ == "__main__":
    main()
