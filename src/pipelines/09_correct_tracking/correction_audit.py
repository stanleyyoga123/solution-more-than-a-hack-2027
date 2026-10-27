"""Decision provenance and sparse coordinate changes for step 09."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray

AUDIT_COLUMNS = (
    "correction_id",
    "operation",
    "status",
    "reason",
    "entity_id",
    "other_entity_id",
    "segment_id",
    "other_segment_id",
    "corrected_entity_id",
    "start_frame",
    "end_frame",
    "forward_error_m",
    "backward_error_m",
    "score_m",
    "source_gap_status",
    "source_gap_reason",
    "source_gap_start_frame",
    "source_gap_end_frame",
    "affected_rows",
)


@dataclass(frozen=True)
class PositionChange:
    position: NDArray[np.float64]
    status: str
    correction_id: str
    corrected_entity_id: str = ""


class CorrectionAudit:
    def __init__(self):
        self.rows: list[dict] = []
        self.changes: dict[tuple[int, int], PositionChange] = {}

    def record(self, operation: str, status: str, reason: str, **details) -> dict:
        row = {column: "" for column in AUDIT_COLUMNS}
        row.update(details)
        row.update(
            correction_id=f"correction_{len(self.rows) + 1:06d}",
            operation=operation,
            status=status,
            reason=reason,
        )
        self.rows.append(row)
        return row
