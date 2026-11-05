"""Hand possession to the opposing team only when it keeps the ball or passes it on."""

from dataclasses import dataclass, replace

import numpy as np
from numpy.typing import NDArray

from ..configuration.policy import PossessionPolicy
from ..models.possession_features import PossessionFeatures

LABELS = ("H", "A")


@dataclass(frozen=True)
class Contact:
    """One team's player staying within reach of the ball, in frames and inclusive."""

    first: int
    last: int
    team: int


class Ownership:
    def __init__(self, policy: PossessionPolicy) -> None:
        self._policy = policy

    def contacts(self, features: PossessionFeatures) -> list[Contact]:
        """Merge touches by the same team that are less than the gap apart."""
        nearest = np.minimum(
            features.nearest_home_distance_m, features.nearest_away_distance_m
        )
        touching = (features.nearest_code >= 0) & (
            nearest <= self._policy.touch_distance_m
        )
        gap = round(self._policy.touch_gap_seconds * features.fps)
        contacts: list[Contact] = []
        for frame in np.flatnonzero(touching):
            team = int(features.nearest_code[frame])
            previous = contacts[-1] if contacts else None
            if previous and previous.team == team and frame - previous.last <= gap:
                contacts[-1] = replace(previous, last=int(frame))
            else:
                contacts.append(Contact(int(frame), int(frame), team))
        return contacts

    def predict(self, features: PossessionFeatures) -> NDArray[np.str_]:
        """Owner per frame. The first toucher owns the half until a team takes over.

        A change is dated to the first frame of the contact that takes possession.
        Frames without any contact in the half are D.
        """
        labels = np.full(features.frame_count, "D", dtype="<U1")
        contacts = self.contacts(features)
        if not contacts:
            return labels
        owner, start = contacts[0].team, 0
        for index, contact in enumerate(contacts):
            if contact.team == owner or not self._takes_possession(
                contacts, index, features.fps
            ):
                continue
            labels[start : contact.first] = LABELS[owner]
            owner, start = contact.team, contact.first
        labels[start:] = LABELS[owner]
        return labels

    def _takes_possession(
        self, contacts: list[Contact], index: int, fps: float
    ) -> bool:
        """The opposing team must hold the ball long enough or touch it again soon."""
        contact = contacts[index]
        dwell = contact.last - contact.first + 1
        if dwell >= round(self._policy.control_dwell_seconds * fps):
            return True
        if index + 1 == len(contacts):
            return False
        following = contacts[index + 1]
        window = round(self._policy.pass_window_seconds * fps)
        return (
            following.team == contact.team and following.first - contact.last <= window
        )
