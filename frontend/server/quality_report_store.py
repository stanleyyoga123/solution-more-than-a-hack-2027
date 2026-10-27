"""Load compact trajectory episodes and gap assessments for browser review."""

from collections import Counter, defaultdict
import csv
import logging
from pathlib import Path
from time import perf_counter

_LOGGER = logging.getLogger(__name__)


def empty_quality_report() -> dict:
    """Describe unavailable reports without disabling the tracking viewer."""
    return {
        "available": {"trajectories": False, "gaps": False},
        "summary": {
            "flagged_samples": 0,
            "trajectory_episodes": 0,
            "gap_count": 0,
            "status_counts": {"plausible": 0, "implausible": 0, "uncertain": 0},
        },
        "episodes": [],
        "gaps": [],
    }


def _optional_number(
    value: str, conversion: type[int] | type[float]
) -> int | float | None:
    return conversion(value) if value else None


def _read_flag_samples(path: Path) -> dict[str, list[dict]]:
    samples: dict[str, list[dict]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            sample = {
                "entity_id": row["entity_id"],
                "entity_type": row["entity_type"],
                "team_id": row["team_id"],
                "start_frame": int(row["start_frame"]),
                "end_frame": int(row["end_frame"]),
                "speed_mps": float(row["speed_mps"]),
                "acceleration_mps2": _optional_number(row["acceleration_mps2"], float),
                "speed_flag": row["speed_flag"] == "True",
                "acceleration_flag": row["acceleration_flag"] == "True",
            }
            samples[row["entity_id"]].append(sample)
    return samples


def _episode(samples: list[dict]) -> dict:
    first = samples[0]
    speed_samples = [sample for sample in samples if sample["speed_flag"]]
    if speed_samples:
        peak = max(speed_samples, key=lambda sample: sample["speed_mps"])
    else:
        peak = max(samples, key=lambda sample: sample["acceleration_mps2"])
    accelerations = [
        sample["acceleration_mps2"]
        for sample in samples
        if sample["acceleration_mps2"] is not None
    ]
    start = min(sample["start_frame"] for sample in samples)
    return {
        "id": f"motion:{first['entity_id']}:{start}",
        "entity_id": first["entity_id"],
        "entity_type": first["entity_type"],
        "team_id": first["team_id"],
        "start_frame": start,
        "end_frame": max(sample["end_frame"] for sample in samples),
        "peak_frame": peak["end_frame"],
        "peak_speed_mps": max(sample["speed_mps"] for sample in samples),
        "peak_acceleration_mps2": max(accelerations) if accelerations else None,
        "speed_flag": bool(speed_samples),
        "acceleration_flag": any(sample["acceleration_flag"] for sample in samples),
        "sample_count": len(samples),
    }


def _read_episodes(path: Path) -> tuple[list[dict], int]:
    tracks = _read_flag_samples(path)
    episodes = []
    count = 0
    for samples in tracks.values():
        samples.sort(key=lambda sample: (sample["start_frame"], sample["end_frame"]))
        current = []
        end = -1
        for sample in samples:
            count += 1
            if current and sample["start_frame"] > end + 1:
                episodes.append(_episode(current))
                current = []
            current.append(sample)
            end = max(end, sample["end_frame"])
        if current:
            episodes.append(_episode(current))
    episodes.sort(key=lambda item: (item["start_frame"], item["entity_id"]))
    return episodes, count


def _read_gaps(path: Path) -> list[dict]:
    integer_columns = (
        "start_frame",
        "end_frame",
        "missing_frames",
        "left_frame",
        "right_frame",
    )
    decimal_columns = (
        "gap_seconds",
        "endpoint_distance_m",
        "required_speed_mps",
        "forward_error_m",
        "backward_error_m",
    )
    gaps = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            gap = dict(row)
            for column in integer_columns:
                gap[column] = _optional_number(row[column], int)
            for column in decimal_columns:
                gap[column] = _optional_number(row[column], float)
            gap["id"] = f"gap:{row['entity_id']}:{row['start_frame']}"
            gaps.append(gap)
    gaps.sort(key=lambda item: (item["start_frame"], item["entity_id"]))
    return gaps


def load_quality_reports(
    trajectory_flags: Path | None, gap_continuity: Path | None
) -> dict:
    """Read optional reports once; supplied missing paths surface as I/O errors."""
    started = perf_counter()
    report = empty_quality_report()
    if trajectory_flags is not None:
        _LOGGER.info("Loading trajectory quality report: %s", trajectory_flags)
        episodes, sample_count = _read_episodes(trajectory_flags)
        report["episodes"] = episodes
        report["available"]["trajectories"] = True
        report["summary"]["flagged_samples"] = sample_count
        report["summary"]["trajectory_episodes"] = len(episodes)
    if gap_continuity is not None:
        _LOGGER.info("Loading gap continuity report: %s", gap_continuity)
        gaps = _read_gaps(gap_continuity)
        report["gaps"] = gaps
        report["available"]["gaps"] = True
        report["summary"]["gap_count"] = len(gaps)
        statuses = Counter(gap["status"] for gap in gaps)
        report["summary"]["status_counts"] = {
            status: statuses[status]
            for status in ("plausible", "implausible", "uncertain")
        }
    _LOGGER.info(
        "Quality reports loaded: %d flagged samples, %d motion episodes, "
        "%d gaps in %.2f seconds",
        report["summary"]["flagged_samples"],
        report["summary"]["trajectory_episodes"],
        report["summary"]["gap_count"],
        perf_counter() - started,
    )
    return report
