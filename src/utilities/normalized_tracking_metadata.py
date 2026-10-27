"""Timing and pitch dimensions needed to assess normalized tracking."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class NormalizedTrackingMetadata:
    fps: float
    frame_count: int
    pitch_length: float
    pitch_width: float


def read_normalized_metadata(path: Path) -> NormalizedTrackingMetadata:
    document = json.loads(path.read_text(encoding="utf-8"))
    return NormalizedTrackingMetadata(
        fps=document["fps"],
        frame_count=document["frame_count"],
        pitch_length=document["pitch_dimensions"]["length"],
        pitch_width=document["pitch_dimensions"]["width"],
    )
