"""Require sustained opposing control before transferring team ownership."""

from math import ceil

import numpy as np
from numpy.typing import NDArray

from ..configuration.policy import PossessionPolicy
from ..models.possession_features import PossessionFeatures


class ControlConfirmation:
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
        home = (
            np.isfinite(home_distance)
            & (home_distance <= self._policy.control_distance_m)
            & (home_distance + self._policy.control_advantage_m <= away_distance)
            & plausible_speed
        )
        away = (
            np.isfinite(away_distance)
            & (away_distance <= self._policy.control_distance_m)
            & (away_distance + self._policy.control_advantage_m <= home_distance)
            & plausible_speed
        )
        result[home] = 0
        result[away] = 1
        return result

    def predict(self, features: PossessionFeatures) -> NDArray[np.str_]:
        """Backdate confirmed switches and expire ownership after missing evidence."""
        candidates = self.candidates(features)
        result = np.full(features.frame_count, -1, dtype=np.int8)
        confirmation = max(
            1, ceil(self._policy.control_confirmation_seconds * features.fps)
        )
        maximum_missing = max(
            0, round(self._policy.control_missing_timeout_seconds * features.fps)
        )
        incumbent = pending = -1
        pending_start = pending_count = missing_count = 0
        for frame, observation in enumerate(features.nearest_code):
            candidate = int(candidates[frame])
            evidence_available = observation >= 0 or candidate >= 0
            if evidence_available:
                missing_count = 0
            else:
                missing_count += 1
                if missing_count > maximum_missing:
                    incumbent = -1
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
