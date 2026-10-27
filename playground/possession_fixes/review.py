"""Post-inference diagnostic comparisons for explicitly selected review intervals."""

import numpy as np
from numpy.typing import NDArray


def review_intervals(
    truth: NDArray[np.str_],
    predicted: NDArray[np.str_],
    anchor: NDArray[np.str_],
    intervals: tuple[tuple[int, int], ...],
    fps: float,
) -> list[dict]:
    results = []
    for start, end in intervals:
        target = truth[start:end]
        actual = predicted[start:end]
        previous = anchor[start:end]
        graded = target != "X"
        corrected = graded & (previous != target) & (actual == target)
        introduced = graded & (previous == target) & (actual != target)
        results.append(
            {
                "start_frame": start,
                "end_frame_exclusive": end,
                "start_seconds": start / fps,
                "end_seconds": end / fps,
                "graded_frames": int(graded.sum()),
                "wrong_frames": int((graded & (actual != target)).sum()),
                "anchor_wrong_frames": int((graded & (previous != target)).sum()),
                "corrected_anchor_errors": int(corrected.sum()),
                "introduced_anchor_errors": int(introduced.sum()),
                "predicted_counts": {
                    label: int((actual == label).sum()) for label in ("H", "A", "D")
                },
            }
        )
    return results
