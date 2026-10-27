"""Read the normalized export's timing, pitch dimensions and team colours."""

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class RenderMetadata:
    fps: float
    pitch_length: float
    pitch_width: float
    teams: dict[str, str]
    frame_count: int


def read_metadata(path: Path) -> RenderMetadata:
    """Read the documented normalized metadata without revalidating its schema."""
    document = json.loads(path.read_text(encoding="utf-8"))
    return RenderMetadata(
        fps=document["fps"],
        pitch_length=document["pitch_dimensions"]["length"],
        pitch_width=document["pitch_dimensions"]["width"],
        teams=document["teams"],
        frame_count=document["frame_count"],
    )
