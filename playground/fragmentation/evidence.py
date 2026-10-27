"""Keep observed control and physical stoppage evidence separate from labels."""

from dataclasses import dataclass
import logging
from math import ceil

import numpy as np
from numpy.typing import NDArray

from playground.control import control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.tag_features import TagFeatures
from playground.temporal import persistent_mask

from .policy import FragmentationPolicy

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class FragmentationEvidence:
    """Binary support counts only sustained, observed team-control candidates."""

    dead: NDArray[np.bool_]
    control_codes: NDArray[np.int8]
    confirmed_control: NDArray[np.int8]
    home_support: NDArray[np.float64]
    away_support: NDArray[np.float64]


def build_evidence(
    original_features: FeatureData,
    arrival_features: FeatureData,
    tags: TagFeatures,
    policy: FragmentationPolicy = FragmentationPolicy(),
) -> FragmentationEvidence:
    """Require original observed ball geometry and speed for control evidence.

    Interception arrival equivalents provide relative team support. Physical
    stoppage detection always uses original tracking, and missing motion cannot
    provide positive control support.
    """
    domain = DomainPolicy()
    dead = boundary_dead_mask(original_features, original_features.ball_valid, domain)
    dead |= stationary_dead_mask(
        original_features, tags, original_features.ball_valid, domain
    )
    codes = control_candidates(
        arrival_features.nearest_home_distance_m,
        arrival_features.nearest_away_distance_m,
        original_features.ball_speed_mps,
        domain,
    )
    observed = (
        original_features.ball_valid
        & np.isfinite(original_features.ball_x_m)
        & np.isfinite(original_features.ball_y_m)
        & np.isfinite(original_features.ball_speed_mps)
        & (original_features.ball_speed_mps >= 0)
        & (original_features.ball_speed_mps <= domain.control_ball_speed_mps)
    )
    codes[~observed | dead] = -1
    minimum = max(1, ceil(policy.control_confirmation_seconds * original_features.fps))
    confirmed = np.full(len(codes), -1, dtype=np.int8)
    for team in (0, 1):
        confirmed[persistent_mask(codes == team, minimum)] = team
    LOGGER.info(
        "Built fragmentation evidence for %d frames: %d physical dead cues, "
        "%d observed control frames, %d sustained control frames",
        len(codes),
        int(dead.sum()),
        int((codes >= 0).sum()),
        int((confirmed >= 0).sum()),
    )
    return FragmentationEvidence(
        dead=dead,
        control_codes=codes,
        confirmed_control=confirmed,
        home_support=(confirmed == 0).astype(float),
        away_support=(confirmed == 1).astype(float),
    )


def classify_uncertainty(
    labels: NDArray[np.str_], evidence: FragmentationEvidence
) -> NDArray[np.str_]:
    """Reclassify unsupported D internally; export U as D for exact identity.

    This adds no new stoppage labels and preserves every existing live or X
    label. U identifies inference uncertainty, not a new submission class.
    """
    result = labels.copy()
    result[(labels == "D") & ~evidence.dead] = "U"
    return result
