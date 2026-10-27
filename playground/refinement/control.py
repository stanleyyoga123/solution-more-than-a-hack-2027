"""Confirm control while tolerating brief interruptions in opposing evidence."""

from math import ceil, floor

import numpy as np
from numpy.typing import NDArray

from playground.prediction_policy import DomainPolicy

from .control_policy import ControlPolicy


def tolerant_confirm_control(
    observed_codes: NDArray[np.int8],
    candidates: NDArray[np.int8],
    dead_mask: NDArray[np.bool_],
    fps: float,
    domain_policy: DomainPolicy = DomainPolicy(),
    policy: ControlPolicy = ControlPolicy(),
) -> NDArray[np.int8]:
    """Accumulate opposing evidence across short uncertain interruptions.

    Only opposing candidate frames count towards confirmation. An incumbent
    candidate, a long uncertain interruption, or an expired pending window clears
    that evidence. Confirmed switches are backdated to the first pending frame.
    Initialization, missing-observation expiry and explicit stoppages follow the
    earlier control method.
    """
    result = np.full(len(observed_codes), -1, dtype=np.int8)
    confirmation = max(1, ceil(domain_policy.control_confirmation_seconds * fps))
    maximum_missing = max(0, round(domain_policy.missing_bridge_seconds * fps))
    maximum_uncertain = max(0, floor(policy.uncertain_interruption_seconds * fps))
    maximum_window = max(1, floor(policy.pending_window_seconds * fps))
    incumbent = pending = -1
    pending_start = pending_count = uncertain_count = missing_count = 0
    for frame, observation in enumerate(observed_codes):
        if dead_mask[frame]:
            incumbent = pending = -1
            pending_count = uncertain_count = missing_count = 0
            continue

        candidate = int(candidates[frame])
        if observation >= 0 or candidate >= 0:
            missing_count = 0
        else:
            missing_count += 1
            if missing_count > maximum_missing:
                incumbent = -1
        if incumbent < 0 and observation >= 0:
            incumbent = int(observation)

        if pending >= 0 and frame - pending_start + 1 > maximum_window:
            pending = -1
            pending_count = uncertain_count = 0

        if candidate >= 0 and candidate != incumbent:
            if candidate == pending:
                pending_count += 1
            else:
                pending = candidate
                pending_start = frame
                pending_count = 1
            uncertain_count = 0
            if pending_count >= confirmation:
                incumbent = candidate
                result[pending_start : frame + 1] = incumbent
                pending = -1
                pending_count = 0
        elif candidate < 0 and pending >= 0:
            uncertain_count += 1
            if uncertain_count > maximum_uncertain:
                pending = -1
                pending_count = uncertain_count = 0
        else:
            pending = -1
            pending_count = uncertain_count = 0
        result[frame] = incumbent
    return result
