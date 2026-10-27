"""Source ball observations and deterministic video sample selection."""

from contextlib import closing
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from src.utilities.atd_reader import read_tracking
from src.utilities.epts_metadata import TrackingMetadata

from .policy import VisionPolicy


def read_source_ball(path: Path, info: TrackingMetadata) -> NDArray[np.float64]:
    positions = np.full((info.expected_frames, 2), np.nan)
    pitch = np.array([info.pitch_length, info.pitch_width])
    with closing(read_tracking(path)) as records:
        for frame, values in records:
            positions[frame] = values[-1, :2] * pitch
    return positions


def sampling_mask(
    original: NDArray[np.float64], policy: VisionPolicy
) -> tuple[NDArray[np.bool_], set[int]]:
    valid = np.isfinite(original).all(axis=1)
    mask = ~valid & (np.arange(len(valid)) % policy.sample_stride == 0)
    observed = np.flatnonzero(valid)
    count = min(policy.max_control_frames, len(observed))
    indices = np.linspace(0, len(observed) - 1, count, dtype=int)
    controls = set(map(int, observed[indices]))
    mask[list(controls)] = True
    if policy.maximum_samples:
        selected = np.flatnonzero(mask)[policy.maximum_samples :]
        mask[selected] = False
        controls.intersection_update(np.flatnonzero(mask))
    return mask, controls
