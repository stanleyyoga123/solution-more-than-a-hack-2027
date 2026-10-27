"""Run sparse CPU video detection and publish auditable ball recovery artifacts."""

from contextlib import closing
from dataclasses import asdict, fields
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
from time import perf_counter

import cv2
import numpy as np

from src.utilities.epts_metadata import read_metadata
from src.utilities.homography_reader import read_homographies
from src.utilities.pipeline_logging import frame_progress

from .association import recover_positions, select_proposal
from .artifacts import write_rows
from .detection import BallDetection
from .detector import YoloBallDetector
from .inputs import read_source_ball, sampling_mask
from .policy import VisionPolicy

LOGGER = logging.getLogger(__name__)
OUTPUT_NAMES = ("recovered_ball.csv", "detections.csv", "recovery.metadata.json")


def _error_summary(errors: list[float]) -> dict:
    return {
        "projected_detections": len(errors),
        "median_error_m": float(np.median(errors)) if errors else None,
        "p90_error_m": float(np.quantile(errors, 0.9)) if errors else None,
        "p95_error_m": float(np.quantile(errors, 0.95)) if errors else None,
        "within_2m": sum(value <= 2 for value in errors),
        "within_5m": sum(value <= 5 for value in errors),
    }


def run_recovery(
    video: Path,
    tracking: Path,
    metadata: Path,
    homography: Path,
    weights: Path,
    output_dir: Path,
    policy: VisionPolicy = VisionPolicy(),
) -> tuple[Path, Path, Path]:
    """Recover sampled missing observations; known source ball positions survive."""
    from ultralytics import YOLO
    import torch

    started = perf_counter()
    if output_dir.exists():
        raise FileExistsError(f"{output_dir} exists; choose a new output directory")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    info = read_metadata(metadata)
    LOGGER.info("Loading source ball visibility: %s", tracking)
    original = read_source_ball(tracking, info)
    selected, controls = sampling_mask(original, policy)
    pitch = np.array([info.pitch_length, info.pitch_width])
    LOGGER.info(
        "YOLO CPU recovery: %d missing samples and %d observed controls; imgsz=%d",
        int(selected.sum()) - len(controls),
        len(controls),
        policy.image_size,
    )
    torch.set_num_threads(policy.cpu_threads)
    detector = YoloBallDetector(YOLO(str(weights)), policy)
    proposals: dict[int, BallDetection] = {}
    audit = []
    raw_errors = []
    selected_errors = []
    control_detections = 0
    sampled = 0
    last_selected = int(np.flatnonzero(selected)[-1]) if selected.any() else -1
    capture = cv2.VideoCapture(str(video))
    try:
        with (
            closing(read_homographies(homography)) as calibrations,
            frame_progress(
                calibrations,
                last_selected + 1,
                "Decoding video and recovering ball",
                LOGGER,
            ) as frames,
        ):
            for frame, matrix, _ in frames:
                if frame > last_selected:
                    break
                if not capture.grab():
                    raise OSError(f"Video decoding stopped at source frame {frame}")
                if not selected[frame]:
                    continue
                success, image = capture.retrieve()
                if not success:
                    raise OSError(f"Cannot retrieve source frame {frame}")
                role = "observed_control" if frame in controls else "missing_ball"
                detections = detector.detect(image, frame, role, matrix, pitch)
                proposal, reason = select_proposal(detections, pitch, policy)
                sampled += 1
                if proposal is not None:
                    proposals[frame] = proposal
                if role == "observed_control":
                    control_detections += bool(detections)
                    if detections:
                        raw = max(detections, key=lambda item: item.confidence)
                        if np.isfinite(raw.position).all():
                            raw_errors.append(
                                float(np.linalg.norm(raw.position - original[frame]))
                            )
                    if proposal is not None:
                        selected_errors.append(
                            float(np.linalg.norm(proposal.position - original[frame]))
                        )
                if not detections:
                    audit.append({"frame": frame, "role": role, "decision": reason})
                for detection in detections:
                    row = asdict(detection)
                    row["decision"] = (
                        reason if detection is proposal else "unselected_proposal"
                    )
                    audit.append(row)
    finally:
        capture.release()
    recovered, rejections, decisions = recover_positions(
        proposals, original, info.fps, policy
    )
    for row in audit:
        if (
            row["decision"] == "unambiguous_pitch_candidate"
            and row["role"] == "missing_ball"
        ):
            row["decision"] = decisions[int(row["frame"])]
    known_original = np.isfinite(original).all(axis=1)
    assert all(not known_original[row["frame"]] for row in recovered)
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
        document = {
            "method": "Sparse pretrained YOLO11 sports-ball recovery",
            "inputs": {
                "video": str(video),
                "tracking": str(tracking),
                "metadata": str(metadata),
                "homography": str(homography),
                "weights": str(weights),
            },
            "weights_sha256": hashlib.sha256(weights.read_bytes()).hexdigest(),
            "policy": asdict(policy),
            "fps": info.fps,
            "frame_count": info.expected_frames,
            "sampled_frames": sampled,
            "missing_ball_samples": sampled - len(controls),
            "observed_control_frames": len(controls),
            "observed_controls_with_any_detection": control_detections,
            "control_raw_top_confidence": _error_summary(raw_errors),
            "control_unambiguous_pitch_candidate": _error_summary(selected_errors),
            "missing_samples_with_pitch_proposal": sum(
                not known_original[frame] for frame in proposals
            ),
            "accepted_yolo_observations": sum(
                row["source"] == "yolo_observation" for row in recovered
            ),
            "interpolated_positions": sum(
                row["source"] == "yolo_interpolation" for row in recovered
            ),
            "recovered_positions": len(recovered),
            "rejections": rejections,
            "elapsed_seconds": perf_counter() - started,
            "limitations": [
                "COCO sports-ball detections are not a soccer-specific ball model.",
                "Pixel centres are projected onto the pitch plane; airborne balls "
                "can have inaccurate pitch coordinates.",
                "Observed-control errors compare with automatic source tracking, "
                "not manually verified video truth.",
                "Sparse sampling can miss fast contacts and brief ball visibility.",
                "No possession labels or score results enter recovery.",
            ],
        }
        (staging / OUTPUT_NAMES[2]).write_text(
            json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        if output_dir.exists():
            raise FileExistsError(f"{output_dir} was created during recovery")
        os.rename(staging, output_dir)
    paths = tuple(output_dir / name for name in OUTPUT_NAMES)
    LOGGER.info(
        "Completed YOLO recovery: %d sampled frames, %d recovered positions "
        "in %.2f seconds; outputs: %s",
        sampled,
        len(recovered),
        perf_counter() - started,
        paths,
    )
    return paths
