"""Nearest-player evidence and bounded, within-half continuity."""

import numpy as np
from numpy.typing import NDArray


def nearest_label(
    values: NDArray[np.float64], teams: NDArray[np.int8], pitch: NDArray[np.float64]
) -> str:
    """Match baseline distances and slot-order ties; missing evidence is X.

    Kept local because Pipeline 05 is frozen and pipelines cannot import each other.
    """
    ball = values[-1, :2] * pitch
    players = values[:-1, :2] * pitch
    distances = np.hypot(*(players - ball).T)
    if not np.isfinite(distances).any():
        return "X"
    return ("H", "A")[int(teams[np.nanargmin(distances)])]


def infer(
    evidence: NDArray[np.str_],
    halves: tuple[tuple[int, int], ...],
    max_gap_frames: int,
) -> NDArray[np.str_]:
    """Fill entire short unknown runs only between matching observed team labels.

    Half bounds are inclusive. Outside halves is X; observed evidence is unchanged.
    No evidence from another half, or an already filled gap, supports a fill.
    """
    labels = np.full(len(evidence), "X", dtype="<U1")
    for start, end in halves:
        half = evidence[start : end + 1]
        labels[start : end + 1] = half
        observed = np.flatnonzero(half != "X")
        for left, right in zip(observed[:-1], observed[1:]):
            gap = right - left - 1
            if 0 < gap <= max_gap_frames and half[left] == half[right]:
                labels[start + left + 1 : start + right] = half[left]
    return labels
