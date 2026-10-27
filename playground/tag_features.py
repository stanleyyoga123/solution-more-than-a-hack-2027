"""Rasterized weak evidence from automatic tactical annotations."""

from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray


@dataclass(frozen=True)
class TagFeatures:
    home_phase_votes: NDArray[np.int16]
    away_phase_votes: NDArray[np.int16]
    restart_mask: NDArray[np.bool_]
