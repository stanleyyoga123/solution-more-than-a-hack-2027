"""Stream corrected positions alongside exact source values and audit references."""

from collections import Counter
import csv
import logging
from pathlib import Path

from src.utilities.pipeline_logging import frame_progress

from .correction_audit import CorrectionAudit
from .track_segment import TrackSegment
from .tracking_data import TrackingData

LOGGER = logging.getLogger(__name__)
EXTRA_COLUMNS = (
    "source_pos_x",
    "source_pos_y",
    "corrected_entity_id",
    "segment_id",
    "position_status",
    "correction_id",
)


def write_corrected_tracking(
    tracking: Path,
    destination: Path,
    data: TrackingData,
    segments: list[TrackSegment],
    identities: dict[int, str],
    audit: CorrectionAudit,
) -> dict[str, int]:
    counts = Counter()
    entity_count = len(data.entities)
    with (
        tracking.open(newline="", encoding="utf-8") as source,
        destination.open("w", newline="", encoding="utf-8") as target,
    ):
        reader = csv.DictReader(source)
        writer = csv.DictWriter(
            target, fieldnames=tuple(reader.fieldnames) + EXTRA_COLUMNS
        )
        writer.writeheader()
        # Progress counts source rows, while each row's source-slot order is retained.
        with frame_progress(
            reader, data.row_count, "Writing corrected rows", LOGGER, unit="row"
        ) as rows:
            for offset, row in enumerate(rows):
                index, slot = divmod(offset, entity_count)
                row["source_pos_x"], row["source_pos_y"] = row["pos_x"], row["pos_y"]
                segment_number = int(data.segment_numbers[index, slot])
                valid = segment_number >= 0
                row["corrected_entity_id"] = identities[segment_number] if valid else ""
                row["segment_id"] = segments[segment_number].segment_id if valid else ""
                row["position_status"] = "observed" if valid else "missing"
                row["correction_id"] = ""
                change = audit.changes.get((index, slot))
                if change is not None:
                    position = change.position / data.scale
                    row["pos_x"], row["pos_y"] = float(position[0]), float(position[1])
                    row["position_valid"] = True
                    row["position_status"] = change.status
                    row["correction_id"] = change.correction_id
                    if change.corrected_entity_id:
                        row["corrected_entity_id"] = change.corrected_entity_id
                counts[row["position_status"]] += 1
                writer.writerow(row)
    return dict(counts)


def annotate_audit_identities(
    data: TrackingData,
    segments: list[TrackSegment],
    identities: dict[int, str],
    audit: CorrectionAudit,
) -> None:
    by_id = {segment.segment_id: segment.number for segment in segments}
    slots = {entity.entity_id: slot for slot, entity in enumerate(data.entities)}
    for row in audit.rows:
        if row["status"] != "accepted":
            continue
        if row["operation"] == "repair":
            index = int(
                data.frames[: data.frame_count].searchsorted(int(row["start_frame"]))
            )
            number = int(data.segment_numbers[index, slots[row["entity_id"]]])
            row["segment_id"] = segments[number].segment_id
            row["corrected_entity_id"] = identities[number]
        elif row["segment_id"]:
            row["corrected_entity_id"] = identities[by_id[row["segment_id"]]]
