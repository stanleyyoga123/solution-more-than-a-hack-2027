"""Separate anticipated arrival from observed physical ball control."""

from dataclasses import replace
import logging
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from playground.control import confirm_control, control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.fragmentation.evidence import build_evidence, classify_uncertainty
from playground.fragmentation.repair import join_uncertain_gaps
from playground.prediction_policy import DomainPolicy
from playground.refinement.gap_bridge import bridge_occluded_possession
from playground.tag_features import TagFeatures
from playground.temporal import bridge_missing_codes, majority_labels

LOGGER = logging.getLogger(__name__)


def predict_fixed(
    original: FeatureData,
    arrival: FeatureData,
    tags: TagFeatures,
    *,
    control_mode: Literal["arrival", "gate", "physical"] = "arrival",
    physical_initialization: bool = False,
    extra_dead: NDArray[np.bool_] | None = None,
    policy: DomainPolicy = DomainPolicy(),
) -> NDArray[np.str_]:
    """Preserve r06 plus f03 by default; isolate each physical-control change.

    The gate rejects a forecast winner without nearby, separated physical
    control. It never substitutes the opposing team. Physical mode instead
    derives candidates directly from measured player-to-ball distances.
    Physical initialization changes the nearest-team fallback used only when
    the control decoder has no incumbent; it leaves confirmation unchanged.
    """
    observed = (
        original.nearest_code if physical_initialization else arrival.nearest_code
    )
    codes = bridge_missing_codes(
        observed, round(policy.missing_bridge_seconds * original.fps)
    )
    dead = boundary_dead_mask(original, original.ball_valid, policy)
    dead |= stationary_dead_mask(original, tags, original.ball_valid, policy)
    if extra_dead is not None:
        dead |= extra_dead

    control_features = original if control_mode == "physical" else arrival
    candidates = control_candidates(
        control_features.nearest_home_distance_m,
        control_features.nearest_away_distance_m,
        original.ball_speed_mps,
        policy,
    )
    if control_mode == "gate":
        home_control = (
            original.ball_valid
            & (original.nearest_home_distance_m <= policy.control_distance_m)
            & (
                original.nearest_home_distance_m + policy.control_advantage_m
                <= original.nearest_away_distance_m
            )
        )
        away_control = (
            original.ball_valid
            & (original.nearest_away_distance_m <= policy.control_distance_m)
            & (
                original.nearest_away_distance_m + policy.control_advantage_m
                <= original.nearest_home_distance_m
            )
        )
        rejected = ((candidates == 0) & ~home_control) | (
            (candidates == 1) & ~away_control
        )
        candidates[rejected] = -1
        LOGGER.info(
            "Rejected %d physically unsupported arrival candidates", rejected.sum()
        )

    controlled = confirm_control(codes, candidates, dead, original.fps, policy)
    labels = majority_labels(controlled, 50, True)
    labels[dead] = "D"
    labels = bridge_occluded_possession(labels, original, tags, domain_policy=policy)
    labels[dead] = "D"

    evidence = build_evidence(original, arrival, tags)
    evidence = replace(evidence, dead=evidence.dead | dead)
    internal = classify_uncertainty(labels, evidence)
    repaired, _ = join_uncertain_gaps(internal, evidence, original.fps)
    result = np.where(repaired == "U", "D", repaired)
    result[dead] = "D"
    return result
