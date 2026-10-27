"""Stream frame-aligned normalised-pitch-to-pixel calibration."""

from collections.abc import Iterator
import csv
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

MATRIX_COLUMNS = tuple(f"h{row}{column}" for row in range(3) for column in range(3))


def read_homographies(
    path: Path,
) -> Iterator[tuple[int, NDArray[np.float64] | None, float]]:
    """Yield the provided transforms; valid=0 means calibration is unavailable."""
    with path.open(newline="", encoding="utf-8") as source:
        reader = csv.DictReader(source)
        for row in reader:
            frame = int(row["frame"])
            error = float(row["reprojection_error"])
            if row["valid"] == "0":
                yield frame, None, error
                continue
            matrix = np.array(
                [float(row[column]) for column in MATRIX_COLUMNS]
            ).reshape(3, 3)
            yield frame, matrix, error
