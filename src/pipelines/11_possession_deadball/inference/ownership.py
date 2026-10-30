"""Hold team ownership until the opposing team shows sustained control."""

from math import ceil

import numpy as np
from numpy.typing import NDArray

from ..configuration.policy import PossessionPolicy
from ..models.possession_features import PossessionFeatures


class Ownership:
    def __init__(self, policy: PossessionPolicy) -> None:
        self._policy = policy

    def candidates(self, features: PossessionFeatures) -> NDArray[np.int8]:
        """Require a nearby team, a distance advantage and plausible ball speed."""
        home_distance = features.nearest_home_distance_m
        away_distance = features.nearest_away_distance_m
        speed = features.ball_speed_mps
        result = np.full(features.frame_count, -1, dtype=np.int8)
        plausible_speed = ~np.isfinite(speed) | (
            speed <= self._policy.control_ball_speed_mps
        )
        result[self._controls(home_distance, away_distance) & plausible_speed] = 0
        result[self._controls(away_distance, home_distance) & plausible_speed] = 1
        return result

    def _controls(
        self, own_distance: NDArray[np.float64], opposing_distance: NDArray[np.float64]
    ) -> NDArray[np.bool_]:
        """Mark frames where a team is close enough and clearly nearer than the other."""
        return (
            np.isfinite(own_distance)
            & (own_distance <= self._policy.control_distance_m)
            & (own_distance + self._policy.control_advantage_m <= opposing_distance)
        )

    def predict(self, features: PossessionFeatures) -> NDArray[np.str_]:
        """Backdate confirmed switches; a lost ball never ends ownership."""
        candidates = self.candidates(features)
        result = np.full(features.frame_count, -1, dtype=np.int8)
        confirmation = max(
            1, ceil(self._policy.control_confirmation_seconds * features.fps)
        )
        incumbent = pending = -1
        pending_start = pending_count = 0
        for frame, observation in enumerate(features.nearest_code):
            candidate = int(candidates[frame])
            if incumbent < 0 and observation >= 0:
                incumbent = int(observation)
            if candidate >= 0 and candidate != incumbent:
                if candidate == pending:
                    pending_count += 1
                else:
                    pending = candidate
                    pending_start = frame
                    pending_count = 1
                if pending_count >= confirmation:
                    incumbent = candidate
                    result[pending_start : frame + 1] = incumbent
                    pending = -1
                    pending_count = 0
            else:
                pending = -1
                pending_count = 0
            result[frame] = incumbent
        labels = np.full(features.frame_count, "D", dtype="<U1")
        labels[result == 0] = "H"
        labels[result == 1] = "A"
        return labels
