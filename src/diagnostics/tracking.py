"""Load observation availability on the tactical recording timeline."""

import csv
from itertools import groupby
from src.diagnostics.geometry import nearest_distance
import logging
import math
from pathlib import Path

import numpy as np

LOGGER = logging.getLogger(__name__)


def load_tracking(
    path: Path, count: int, *, geometry: dict | None = None
) -> tuple[np.ndarray, int, int, np.ndarray]:
    """Count usable observations while retaining missing ball frames."""
    ball = np.zeros(count, dtype=bool)
    observed = usable = 0
    player_frames = np.zeros(count, dtype=int)
    with path.open(newline="") as source:
        for frame, rows in groupby(
            csv.DictReader(source), key=lambda row: int(row["frame"])
        ):
            players = []
            ball_position = None
            for row in rows:
                observed += 1
                valid = row["position_valid"] == "True" and all(
                    math.isfinite(float(row[key])) if row[key] else False
                    for key in ("pos_x", "pos_y")
                )
                usable += int(valid)
                if row["entity_type"] == "ball":
                    ball[frame] |= valid
                    if valid:
                        ball_position = (float(row["pos_x"]), float(row["pos_y"]))
                elif row["entity_type"] == "player" and valid:
                    player_frames[frame] += 1
                    if geometry is not None and geometry["truth"][frame] in "HAD":
                        players.append((float(row["pos_x"]), float(row["pos_y"])))
                if observed % 1000000 == 0:
                    LOGGER.info("Read %d tracking rows", observed)
            if geometry is not None and geometry["truth"][frame] in "HAD":
                geometry["distances"][frame] = nearest_distance(
                    ball_position, players, geometry["length"], geometry["width"]
                )
    return ball, observed, usable, player_frames
