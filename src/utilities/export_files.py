"""CSV row formatting, metadata descriptions and safe export publication."""

from collections.abc import Iterator
from contextlib import contextmanager
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from numpy.typing import NDArray

from src.utilities.epts_metadata import TrackingMetadata

BASE_COLUMNS = (
    "frame",
    "entity_id",
    "entity_type",
    "team_id",
    "pos_x",
    "pos_y",
    "speed_raw",
    "position_valid",
)


def csv_number(value: float) -> float | str:
    """Use blank CSV cells for missing numeric observations."""
    return "" if np.isnan(value) else float(value)


def frame_rows(
    frame: int,
    values: NDArray[np.float64],
    positions: NDArray[np.float64],
    metadata: TrackingMetadata,
) -> Iterator[tuple[int | str | float | bool, ...]]:
    """Retain every slot, with missing position and speed handled independently."""
    entities = [
        (f"player_{identifier}", "player", team)
        for identifier, team in zip(
            metadata.slot_ids, metadata.slot_team_ids, strict=True
        )
    ]
    entities.append(("ball", "ball", ""))
    for slot, (identifier, entity_type, team) in enumerate(entities):
        x, y = positions[slot]
        yield (
            frame,
            identifier,
            entity_type,
            team,
            csv_number(x),
            csv_number(y),
            csv_number(values[slot, 2]),
            bool(np.isfinite(positions[slot]).all()),
        )


def write_metadata(
    path: Path,
    metadata: TrackingMetadata,
    frame_count: int,
    coordinate_space: str,
    position_unit: str,
) -> None:
    """Describe stored observations and source units without derived quantities."""
    entity_count = len(metadata.slot_ids) + 1
    document = {
        "fps": metadata.fps,
        "pitch_dimensions": {
            "length": metadata.pitch_length,
            "width": metadata.pitch_width,
            "unit": "metres",
        },
        "coordinate_space": coordinate_space,
        "position_unit": position_unit,
        "orientation": {"x": "rightwards", "y": "downwards"},
        "speed_unit": metadata.speed_unit,
        "speed_note": (
            "Raw supplied s channel; not recomputed or converted with position "
            "coordinates. Source unit declaration is retained without resolving "
            "its accuracy."
        ),
        "teams": metadata.team_names,
        "frame_count": frame_count,
        "source_declared_frame_count": metadata.expected_frames,
        "row_count": frame_count * entity_count,
        "player_slot_count": len(metadata.slot_ids),
        "entity_count_per_frame": entity_count,
        "entity_ids": [f"player_{identifier}" for identifier in metadata.slot_ids]
        + ["ball"],
        "frame_convention": (
            "Zero-based video frame; source ATD frame_id = frame + 1. "
            "No cross-recording synchronisation is implied."
        ),
        "missing_values": (
            "Missing numeric observations are blank CSV cells. Every entity slot "
            "is retained; position_valid requires finite pos_x and pos_y. "
            "No filling, interpolation or clamping."
        ),
        "identity_note": (
            "Entity IDs refer to XML tracking slots, not verified shirt numbers "
            "or stable player identities."
        ),
    }
    if coordinate_space == "video_pixels":
        document["homography_note"] = (
            "Per-frame normalized-pitch-to-image transform; invalid calibration "
            "or undefined projection leaves both pixel coordinates blank. "
            "The pitch-plane assumption can misplace airborne objects. "
            "No image bounds filtering is applied."
        )
    else:
        document["normalization_note"] = (
            "Source x,y are already normalized pitch fractions, copied directly "
            "and independently of homography validity. Finite values outside "
            "0..1 are preserved."
        )
    path.write_text(
        json.dumps(document, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )


@contextmanager
def staged_outputs(
    output_dir: Path, stem: str
) -> Iterator[tuple[Path, Path, Path, Path]]:
    """Publish a complete pair and clean up partial outputs if publication fails."""
    csv_path = output_dir / f"{stem}.csv"
    metadata_path = output_dir / f"{stem}.metadata.json"
    destinations = (csv_path, metadata_path)
    for destination in destinations:
        if os.path.lexists(destination):
            raise FileExistsError(
                f"{destination} already exists; choose a new output directory"
            )
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    committed = False
    with tempfile.TemporaryDirectory(prefix=f".{stem}-", dir=output_dir) as directory:
        staged_csv = Path(directory) / csv_path.name
        staged_metadata = Path(directory) / metadata_path.name
        try:
            yield staged_csv, staged_metadata, csv_path, metadata_path
            for staged, destination in zip(
                (staged_csv, staged_metadata), destinations, strict=True
            ):
                os.link(staged, destination)
                created.append(destination)
            committed = True
        finally:
            if not committed:
                for destination in created:
                    destination.unlink()
