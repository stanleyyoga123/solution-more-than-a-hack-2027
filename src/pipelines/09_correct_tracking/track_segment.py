"""Observed segment boundaries and deterministic inferred identity assignment."""

from dataclasses import dataclass

import numpy as np

from src.utilities.motion_limits import MotionLimits

from .tracking_data import TrackingData


@dataclass(frozen=True)
class TrackSegment:
    number: int
    slot: int
    start: int
    end: int
    start_frame: int
    end_frame: int
    entity_id: str
    entity_type: str
    team_id: str

    @property
    def segment_id(self) -> str:
        return f"segment_{self.number + 1:06d}"


def build_segments(
    data: TrackingData, fps: float, limits: MotionLimits
) -> list[TrackSegment]:
    boundaries = []
    for slot, entity in enumerate(data.entities):
        positions = data.working[: data.frame_count, slot]
        valid = np.isfinite(positions).all(axis=1)
        speed = np.linalg.norm(np.diff(positions, axis=0), axis=1) * fps
        connected = (
            valid[:-1]
            & valid[1:]
            & (np.diff(data.frames[: data.frame_count]) == 1)
            & (speed <= limits.speed_limit(entity.entity_type) + 1e-8)
        )
        starts = np.flatnonzero(valid & np.r_[True, ~connected])
        ends = np.flatnonzero(valid & np.r_[~connected, True])
        for start, end in zip(starts, ends, strict=True):
            boundaries.append((int(start), slot, int(end)))
    segments = []
    for number, (start, slot, end) in enumerate(sorted(boundaries)):
        entity = data.entities[slot]
        segment = TrackSegment(
            number,
            slot,
            start,
            end,
            int(data.frames[start]),
            int(data.frames[end]),
            entity.entity_id,
            entity.entity_type,
            entity.team_id,
        )
        data.segment_numbers[start : end + 1, slot] = number
        segments.append(segment)
    return segments


def assign_identities(
    segments: list[TrackSegment], links: list[tuple[int, int]]
) -> dict[int, str]:
    predecessor = {right: left for left, right in links}
    identities = {}
    next_id = 1
    for segment in segments:
        if segment.entity_type == "ball":
            identities[segment.number] = "ball"
        elif segment.number in predecessor:
            identities[segment.number] = identities[predecessor[segment.number]]
        else:
            identities[segment.number] = f"track_{next_id:06d}"
            next_id += 1
    return identities
