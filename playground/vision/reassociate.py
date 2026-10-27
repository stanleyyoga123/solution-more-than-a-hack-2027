"""Replay motion association from cached detector evidence without video inference."""

import argparse
from collections import defaultdict
import csv
from dataclasses import fields
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
from time import perf_counter

import numpy as np

from src.utilities.epts_metadata import read_metadata
from src.utilities.pipeline_logging import configure_console_logging

from .artifacts import write_rows
from .association import recover_positions, select_proposal
from .detection import BallDetection
from .inputs import read_source_ball
from .policy import VisionPolicy
from .recovery import OUTPUT_NAMES

LOGGER = logging.getLogger(__name__)


def reassociate(detection_run: Path, output_dir: Path) -> tuple[Path, Path, Path]:
    """Keep cached raw detections fixed and recompute physical association only."""
    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} exists; choose a fresh directory")
    LOGGER.info(
        "Starting cached YOLO association; cached run: %s; output: %s",
        detection_run,
        output_dir,
    )
    LOGGER.info("Loading cached recovery metadata: %s", detection_run / OUTPUT_NAMES[2])
    document = json.loads((detection_run / OUTPUT_NAMES[2]).read_text())
    policy = VisionPolicy(**document["policy"])
    LOGGER.info("Loading source tracking metadata: %s", document["inputs"]["metadata"])
    info = read_metadata(Path(document["inputs"]["metadata"]))
    LOGGER.info(
        "Loading original ball observations: %s", document["inputs"]["tracking"]
    )
    original = read_source_ball(Path(document["inputs"]["tracking"]), info)
    pitch = np.array([info.pitch_length, info.pitch_width])
    LOGGER.info(
        "Loading cached detector proposals: %s", detection_run / OUTPUT_NAMES[1]
    )
    with (detection_run / OUTPUT_NAMES[1]).open(newline="") as source:
        audit = list(csv.DictReader(source))
    LOGGER.info(
        "Loaded %d detector audit rows; applying physical association", len(audit)
    )
    by_frame = defaultdict(list)
    for row in audit:
        if not row["confidence"]:
            continue
        values = {field.name: row[field.name] for field in fields(BallDetection)}
        values["frame"] = int(values["frame"])
        for key in values.keys() - {"frame", "role"}:
            values[key] = float(values[key])
        by_frame[values["frame"]].append(BallDetection(**values))
    proposals = {}
    for frame, detections in by_frame.items():
        proposal, _ = select_proposal(detections, pitch, policy)
        if proposal is not None:
            proposals[frame] = proposal
    recovered, rejections, decisions = recover_positions(
        proposals, original, info.fps, policy
    )
    for row in audit:
        if row["role"] != "missing_ball" or not row["confidence"]:
            continue
        frame = int(row["frame"])
        proposal = proposals.get(frame)
        if proposal is not None and (
            float(row["confidence"]) == proposal.confidence
            and float(row["pixel_x"]) == proposal.pixel_x
            and float(row["pixel_y"]) == proposal.pixel_y
        ):
            row["decision"] = decisions[frame]
    document.update(
        source_detection_run=str(detection_run),
        association_source_sha256={
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(__file__).parent.glob("*.py"))
        },
        accepted_yolo_observations=sum(
            row["source"] == "yolo_observation" for row in recovered
        ),
        interpolated_positions=sum(
            row["source"] == "yolo_interpolation" for row in recovered
        ),
        recovered_positions=len(recovered),
        rejections=rejections,
        reassociation_seconds=perf_counter() - started,
    )
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=output_dir.parent
    ) as temporary:
        staging = Path(temporary) / "run"
        staging.mkdir()
        write_rows(
            staging / OUTPUT_NAMES[0],
            ("frame", "x_m", "y_m", "source", "confidence"),
            recovered,
        )
        write_rows(
            staging / OUTPUT_NAMES[1],
            tuple(field.name for field in fields(BallDetection)) + ("decision",),
            audit,
        )
        (staging / OUTPUT_NAMES[2]).write_text(
            json.dumps(document, indent=2, allow_nan=False) + "\n"
        )
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during association")
        os.rename(staging, output_dir)
    LOGGER.info(
        "Reassociated cached video evidence: %d recovered positions in %.2f seconds",
        len(recovered),
        perf_counter() - started,
    )
    return tuple(output_dir / name for name in OUTPUT_NAMES)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--detection-run", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    configure_console_logging()
    for path in reassociate(args.detection_run, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
