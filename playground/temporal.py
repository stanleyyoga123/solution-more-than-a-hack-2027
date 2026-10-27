"""Temporal votes and bounded observation-gap handling for possession codes."""

from collections.abc import Iterator

import numpy as np
from numpy.typing import NDArray


def true_runs(mask: NDArray[np.bool_]) -> Iterator[tuple[int, int]]:
    """Yield half-open bounds of each maximal True run."""
    changes = np.diff(np.r_[False, mask, False].astype(np.int8))
    starts = np.flatnonzero(changes == 1)
    ends = np.flatnonzero(changes == -1)
    yield from zip(starts.tolist(), ends.tolist(), strict=True)


def persistent_mask(
    candidate: NDArray[np.bool_], minimum_frames: int
) -> NDArray[np.bool_]:
    """Retain entire supported runs in this offline detector."""
    result = np.zeros(len(candidate), dtype=bool)
    for start, end in true_runs(candidate):
        if end - start >= minimum_frames:
            result[start:end] = True
    return result


def bridge_missing_codes(
    codes: NDArray[np.int8], maximum_frames: int
) -> NDArray[np.int8]:
    """Fill only short missing runs bounded by the same observed team."""
    result = codes.copy()
    for start, end in true_runs(codes == -1):
        if start == 0 or end == len(codes) or end - start > maximum_frames:
            continue
        if codes[start - 1] == codes[end] and codes[end] >= 0:
            result[start:end] = codes[end]
    return result


def majority_labels(
    codes: NDArray[np.int8], window: int, three_class: bool
) -> NDArray[np.str_]:
    """Match step 05 team-only voting or count all H/A/D observations."""
    index = np.arange(len(codes))
    low = np.maximum(0, index - window)
    high = np.minimum(len(codes), index + window + 1)
    classes = (0, 1, -1) if three_class else (0, 1)
    totals = []
    for code in classes:
        cumulative = np.r_[0, np.cumsum(codes == code)]
        totals.append(cumulative[high] - cumulative[low])
    votes = np.stack(totals, axis=1)
    winners = np.argmax(votes, axis=1)
    labels = np.array(["H", "A", "D"])[winners]
    if not three_class:
        labels[votes.sum(axis=1) == 0] = "D"
    return labels
