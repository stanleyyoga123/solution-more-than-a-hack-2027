"""Read automatic SportsCode annotations without treating phases as labels."""

from dataclasses import dataclass
import logging
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from src.utilities.epts_metadata import TrackingMetadata

from .tag_features import TagFeatures

LOGGER = logging.getLogger(__name__)
ATTACKING_PHASES = frozenset(
    {
        "BUILD UP",
        "PROGRESSION",
        "LONG BALL",
        "ATTACKING TRANSITION",
        "CREATING CHANCES",
        "BALL IN FINAL THIRD",
        "BALL IN THE BOX",
        "PLAYERS IN THE BOX",
    }
)
DEFENDING_PHASES = frozenset(
    {
        "DEFENDING IN DEFENSIVE THIRD",
        "DEFENDING IN MIDDLE THIRD",
        "DEFENDING IN ATTACKING THIRD",
        "DEFENSIVE TRANSITION",
    }
)


@dataclass(frozen=True)
class SmartTag:
    """Frames use tactical origin; end_frame is exclusive for interval masks."""

    identifier: str
    start_frame: int
    end_frame: int
    code: str
    team_code: int
    event_type: str
    half: str


def read_smart_tags(path: Path, metadata: TrackingMetadata) -> tuple[SmartTag, ...]:
    """Keep unknown team tags as -1 rather than guessing their side."""
    LOGGER.info("Loading automatic tactical tags: %s", path)
    names = {
        name.strip().casefold(): index
        for index, name in enumerate(metadata.team_names.values())
    }
    root = ET.parse(path).getroot()
    tags = []
    for instance in root.findall("./ALL_INSTANCES/instance"):
        labels = {
            label.findtext("group").strip().casefold(): label.findtext("text").strip()
            for label in instance.findall("label")
        }
        tags.append(
            SmartTag(
                identifier=instance.findtext("ID"),
                start_frame=round(float(instance.findtext("start")) * metadata.fps),
                end_frame=round(float(instance.findtext("end")) * metadata.fps),
                code=instance.findtext("code").strip().upper(),
                team_code=names.get(labels.get("team", "").casefold(), -1),
                event_type=labels.get("type", ""),
                half=labels.get("half", ""),
            )
        )
    LOGGER.info("Loaded %d automatic tag intervals", len(tags))
    return tuple(tags)


def tag_features(tags: tuple[SmartTag, ...], frame_count: int) -> TagFeatures:
    """Count phase evidence; restarts are a separate, weak temporal cue."""
    votes = np.zeros((frame_count, 2), dtype=np.int16)
    restarts = np.zeros(frame_count, dtype=bool)
    for tag in tags:
        start, end = max(0, tag.start_frame), min(frame_count, tag.end_frame)
        if tag.code == "SET PIECES":
            restarts[start:end] = True
        if tag.team_code == -1:
            continue
        if tag.code in ATTACKING_PHASES:
            votes[start:end, tag.team_code] += 1
        elif tag.code in DEFENDING_PHASES:
            votes[start:end, 1 - tag.team_code] += 1
    return TagFeatures(votes[:, 0], votes[:, 1], restarts)
