"""Find stoppages from slow player movement, a ball off the pitch and restart tags."""

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from ..configuration.policy import PossessionPolicy
from ..models.possession_features import PossessionFeatures


class DeadBallDetector:
    def __init__(
        self, policy: PossessionPolicy, set_piece_windows: list[tuple[int, int]]
    ) -> None:
        self._policy = policy
        self._set_piece_windows = set_piece_windows

    def detect(self, features: PossessionFeatures) -> NDArray[np.bool_]:
        """True where play is stopped. Unknown activity never starts a stoppage."""
        activity = self._activity(features)
        stopped = self._hysteresis(activity)
        stopped |= self._ball_off_pitch(features)
        slow = activity < self._policy.stoppage_exit_mps
        stopped |= self._set_piece_mask(features) & slow
        minimum = round(self._policy.minimum_stoppage_seconds * features.fps)
        return self._drop_short_runs(stopped, minimum)

    def _activity(self, features: PossessionFeatures) -> NDArray[np.float64]:
        """Mean player speed over a centred window; walking is far below running."""
        window = round(self._policy.activity_window_seconds * features.fps)
        return (
            pd.Series(features.player_speed_mps)
            .rolling(window, center=True, min_periods=max(1, window // 5))
            .mean()
            .to_numpy()
        )

    def _hysteresis(self, activity: NDArray[np.float64]) -> NDArray[np.bool_]:
        """Enter a stoppage below the entry speed; leave only above the exit speed."""
        stopped = np.zeros(len(activity), dtype=bool)
        state = False
        for frame, speed in enumerate(activity):
            if not np.isfinite(speed) or speed > self._policy.stoppage_exit_mps:
                state = False
            elif speed < self._policy.stoppage_enter_mps:
                state = True
            stopped[frame] = state
        return stopped

    def _ball_off_pitch(self, features: PossessionFeatures) -> NDArray[np.bool_]:
        """A ball held beyond the lines for most of a short window is out of play."""
        margin = self._policy.out_of_pitch_margin_m
        outside = (
            (features.ball_x_m < -margin)
            | (features.ball_x_m > features.pitch_length + margin)
            | (features.ball_y_m < -margin)
            | (features.ball_y_m > features.pitch_width + margin)
        )
        window = round(self._policy.out_of_pitch_window_seconds * features.fps)
        share = pd.Series(outside.astype(float)).rolling(
            window, center=True, min_periods=1
        )
        return share.mean().to_numpy() > 0.5

    def _set_piece_mask(self, features: PossessionFeatures) -> NDArray[np.bool_]:
        lead = round(self._policy.set_piece_lead_seconds * features.fps)
        mask = np.zeros(features.frame_count, dtype=bool)
        for start, end in self._set_piece_windows:
            mask[max(0, start - lead) : end] = True
        return mask

    @staticmethod
    def _drop_short_runs(mask: NDArray[np.bool_], minimum: int) -> NDArray[np.bool_]:
        result = mask.copy()
        edges = np.flatnonzero(np.diff(np.r_[False, mask, False].astype(np.int8)))
        for start, stop in zip(edges[::2], edges[1::2]):
            if stop - start < minimum:
                result[start:stop] = False
        return result
