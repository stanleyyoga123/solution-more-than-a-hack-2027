"""Read automatic Smart Tagging set-piece phases as video-frame intervals."""

from pathlib import Path
import xml.etree.ElementTree as ET


def read_set_piece_windows(path: Path, fps: float) -> list[tuple[int, int]]:
    """Return (start, end) frames; tags hold seconds from the first video frame."""
    root = ET.parse(path).getroot()
    return [
        (
            round(float(instance.findtext("start")) * fps),
            round(float(instance.findtext("end")) * fps),
        )
        for instance in root.iter("instance")
        if instance.findtext("code").upper() == "SET PIECES"
    ]
