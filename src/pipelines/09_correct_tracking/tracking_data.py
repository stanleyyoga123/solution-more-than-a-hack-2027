"""Disk-backed positions and source-slot attributes for a correction run."""

from dataclasses import dataclass
import logging
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
import pandas as pd

from src.utilities.pipeline_logging import frame_progress

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Entity:
    entity_id: str
    entity_type: str
    team_id: str


class TrackingData:
    """Keep full-match arrays on disk and source CSV strings in the input file."""

    def __init__(self, directory: Path, metadata: dict):
        self._entity_ids = metadata["entity_ids"]
        self._entity_count = len(self._entity_ids)
        self._declared_frames = metadata["frame_count"]
        shape = (self._declared_frames, self._entity_count, 2)
        self.original = np.memmap(
            directory / "original.dat", mode="w+", dtype="float64", shape=shape
        )
        self.working = np.memmap(
            directory / "working.dat", mode="w+", dtype="float64", shape=shape
        )
        self.frames = np.memmap(
            directory / "frames.dat",
            mode="w+",
            dtype="int64",
            shape=(self._declared_frames,),
        )
        self.segment_numbers = np.memmap(
            directory / "segments.dat", mode="w+", dtype="int32", shape=shape[:2]
        )
        self.segment_numbers[:] = -1
        self.entities: list[Entity] = []
        self.frame_count = 0
        self.row_count = 0
        self.scale = np.array(
            [
                metadata["pitch_dimensions"]["length"],
                metadata["pitch_dimensions"]["width"],
            ]
        )

    def load(self, tracking: Path) -> None:
        LOGGER.info(
            "Loading normalized tracking into temporary disk-backed arrays: %s",
            tracking,
        )
        chunks = pd.read_csv(
            tracking,
            usecols=["frame", "entity_id", "entity_type", "team_id", "pos_x", "pos_y"],
            chunksize=self._entity_count * 5000,
            dtype={"entity_id": str, "entity_type": str, "team_id": str},
        )
        total_chunks = (self._declared_frames + 4999) // 5000
        with (
            chunks,
            frame_progress(
                chunks, total_chunks, "Loading tracking chunks", LOGGER, unit="chunk"
            ) as records,
        ):
            for chunk in records:
                if not self.entities:
                    first_frame = chunk.iloc[: self._entity_count]
                    self.entities = [
                        Entity(
                            row.entity_id,
                            row.entity_type,
                            "" if pd.isna(row.team_id) else row.team_id,
                        )
                        for row in first_frame.itertuples(index=False)
                    ]
                positions = (
                    chunk[["pos_x", "pos_y"]]
                    .to_numpy(dtype=float)
                    .reshape(-1, self._entity_count, 2)
                )
                count = len(positions)
                end = self.frame_count + count
                self.original[self.frame_count : end] = positions * self.scale
                self.frames[self.frame_count : end] = chunk["frame"].to_numpy()[
                    :: self._entity_count
                ]
                self.frame_count = end
                self.row_count += len(chunk)
        self.working[: self.frame_count] = self.original[: self.frame_count]

    def context(
        self, slot: int, index: int, intervals: int, side: str
    ) -> NDArray[np.float64]:
        start, end = (
            (index - intervals, index + 1)
            if side == "left"
            else (index, index + intervals + 1)
        )
        if start < 0 or end > self.frame_count:
            return np.empty((0, 2))
        if np.any(np.diff(self.frames[start:end]) != 1):
            return np.empty((0, 2))
        return self.original[start:end, slot]

    def close(self) -> None:
        for array in (self.original, self.working, self.frames, self.segment_numbers):
            array.flush()
            array._mmap.close()
