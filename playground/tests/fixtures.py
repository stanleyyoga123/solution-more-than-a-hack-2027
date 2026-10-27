"""Small tracking and feature factories for possession behavior tests."""

from collections.abc import Sequence
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np
from numpy.typing import NDArray

from playground.feature_data import FeatureData
from playground.tag_features import TagFeatures
from src.utilities.epts_metadata import TrackingMetadata

ROOT = Path(__file__).resolve().parents[2]
RESOURCES = ROOT / "tests" / "resources" / "pipeline"


def metadata(frame_count: int, fps: float = 10) -> TrackingMetadata:
    return TrackingMetadata(
        fps=fps,
        pitch_length=100,
        pitch_width=60,
        speed_unit="kph",
        expected_frames=frame_count,
        slot_ids=("7", "42"),
        slot_team_ids=("home", "away"),
        team_names={"home": "Home", "away": "Away"},
    )


def features(codes: Sequence[int], fps: float = 10) -> FeatureData:
    """Default to a moving, visible ball and unambiguous nearby player control."""
    values = np.array(codes, dtype=np.int8)
    count = len(values)
    valid = values >= 0
    home = np.where(values == 0, 0.5, 4.0)
    away = np.where(values == 1, 0.5, 4.0)
    home[~valid] = np.inf
    away[~valid] = np.inf
    return FeatureData(
        metadata=metadata(count, fps),
        ball_x_m=np.where(valid, 20.0, np.nan),
        ball_y_m=np.where(valid, 20.0, np.nan),
        ball_valid=valid,
        ball_speed_mps=np.where(valid, 2.0, np.nan),
        ball_displacement_1s_m=np.where(valid, 2.0, np.nan),
        nearest_home_distance_m=home,
        nearest_away_distance_m=away,
        nearest_code=values,
        quality_home_distance_m=home.copy(),
        quality_away_distance_m=away.copy(),
        quality_nearest_code=values.copy(),
        nearest_player_speed_mps=np.where(valid, 1.0, np.nan),
        median_player_speed_mps=np.full(count, 2.0),
        visible_player_count=np.full(count, 22, dtype=np.int16),
    )


def empty_tags(frame_count: int) -> TagFeatures:
    return TagFeatures(
        home_phase_votes=np.zeros(frame_count, dtype=np.int16),
        away_phase_votes=np.zeros(frame_count, dtype=np.int16),
        restart_mask=np.zeros(frame_count, dtype=bool),
    )


def write_tracking(
    directory: Path,
    values: NDArray[np.float64],
    fps: float = 10,
    frame_indices: Sequence[int] = (),
) -> tuple[Path, Path]:
    """Write metre positions in source slot order, with unrelated raw speed 999."""
    directory.mkdir(parents=True, exist_ok=True)
    indices = list(frame_indices) if frame_indices else list(range(len(values)))
    tree = ET.parse(RESOURCES / "metadata.xml")
    tree.find("./Metadata/GlobalConfig/FrameRate").text = str(fps)
    tree.find("./DataFormatSpecifications/DataFormatSpecification").set(
        "endFrame", str(max(indices) + 1)
    )
    xml_path = directory / "metadata.xml"
    tree.write(xml_path)
    tracking = directory / "tracking.txt"
    scale = np.array([100.0, 60.0])
    with tracking.open("w") as destination:
        for frame, positions in zip(indices, values, strict=True):
            records = []
            for x, y in positions / scale:
                records.append(f"{x},{y},999")
            destination.write(f"{frame + 1}:{';'.join(records[:-1])}:{records[-1]}\n")
    return tracking, xml_path
