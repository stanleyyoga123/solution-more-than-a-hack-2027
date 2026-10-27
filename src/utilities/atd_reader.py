"""Stream the supplied ATD format one frame at a time."""

from collections.abc import Iterator
from pathlib import Path

import numpy as np
from numpy.typing import NDArray


def read_tracking(path: Path) -> Iterator[tuple[int, NDArray[np.float64]]]:
    """Yield zero-based frame indices and player-plus-ball x,y,s arrays."""
    with path.open(encoding="utf-8") as source:
        for line in source:
            frame_id, players, ball = line.strip().split(":")
            triplets = [item.split(",") for item in players.split(";") + [ball]]
            yield int(frame_id) - 1, np.array(triplets, dtype=np.float64)
