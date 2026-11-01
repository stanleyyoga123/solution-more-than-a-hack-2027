"""Load observation availability on the tactical recording timeline."""

import csv
import logging
import math
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)


def load_tracking(path: Path, count: int) -> tuple[np.ndarray, int, int, np.ndarray]:
    """Count usable observations while retaining missing ball frames."""
    ball = np.zeros(count, dtype=bool)
    observed = usable = 0
    player_frames = np.zeros(count, dtype=int)
    with path.open(newline="") as source:
        for row in csv.DictReader(source):
            observed += 1
            valid = row["position_valid"] == "True" and all(
                math.isfinite(float(row[key])) for key in ("pos_x", "pos_y")
            )
            usable += int(valid)
            frame = int(row["frame"])
            if row["entity_type"] == "ball":
                ball[frame] |= valid
            elif valid:
                player_frames[frame] += 1
            if observed % 1000000 == 0:
                LOGGER.info("Read %d tracking rows", observed)
    return ball, observed, usable, player_frames
