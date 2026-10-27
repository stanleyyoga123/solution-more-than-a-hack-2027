"""Global three-state possession inference with fixed transition penalties."""

import numpy as np
from numpy.typing import NDArray

from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.feature_data import FeatureData
from playground.prediction_policy import DomainPolicy
from playground.tag_features import TagFeatures

from .policy import CreativePolicy


def viterbi_possession(
    features: FeatureData,
    tags: TagFeatures,
    policy: CreativePolicy = CreativePolicy(),
) -> NDArray[np.str_]:
    """Decode all states jointly; missing-ball bins supply neutral evidence.

    Distances determine relative team support while explicit stoppage evidence
    supports D. A distant observed ball increases uncertainty, not certainty that
    play has stopped. The model is fixed and has no learned possession labels.
    """
    count = features.frame_count
    observed = features.ball_valid
    distances = np.column_stack(
        (features.nearest_home_distance_m, features.nearest_away_distance_m)
    )
    finite_team = np.isfinite(distances)
    nearest_distance = np.where(finite_team, distances, np.inf).min(axis=1)
    available = observed & finite_team.any(axis=1)
    logits = np.zeros((count, 3))
    strength = np.exp(
        -nearest_distance[available] / policy.uncertainty_distance_scale_m
    )
    relative_distance = np.minimum(
        distances[available] - nearest_distance[available, None], 1e3
    )
    logits[available, :2] = (
        -relative_distance / policy.distance_evidence_scale_m * strength[:, None]
    )
    logits[available, 2] = policy.dead_logit_without_cue * strength
    domains = DomainPolicy()
    dead = boundary_dead_mask(features, observed, domains)
    dead |= stationary_dead_mask(features, tags, observed, domains)
    logits[dead] = (
        policy.live_logit_under_dead_cue,
        policy.live_logit_under_dead_cue,
        policy.dead_logit_under_dead_cue,
    )
    logits -= logits.max(axis=1, keepdims=True)
    negative_log_probability = (
        np.log(np.exp(logits).sum(axis=1, keepdims=True)) - logits
    )
    bin_size = max(1, round(features.fps / policy.decoding_hz))
    starts = np.arange(0, count, bin_size)
    cumulative = np.vstack(
        (np.zeros((1, 3)), np.cumsum(negative_log_probability, axis=0))
    )
    ends = np.minimum(starts + bin_size, count)
    emissions = (cumulative[ends] - cumulative[starts]) / (ends - starts)[:, None]
    transition = np.array(
        [
            [0, policy.team_transition_cost, policy.dead_transition_cost],
            [policy.team_transition_cost, 0, policy.dead_transition_cost],
            [policy.dead_transition_cost, policy.dead_transition_cost, 0],
        ],
        dtype=float,
    )
    backpointer = np.zeros((len(starts), 3), dtype=np.int8)
    costs = emissions[0].copy()
    for index in range(1, len(starts)):
        incoming = costs[:, None] + transition
        previous = np.argmin(incoming, axis=0)
        backpointer[index] = previous
        costs = emissions[index] + incoming[previous, np.arange(3)]
    states = np.empty(len(starts), dtype=np.int8)
    states[-1] = int(np.argmin(costs))
    for index in range(len(starts) - 1, 0, -1):
        states[index - 1] = backpointer[index, states[index]]
    return np.array(["H", "A", "D"])[np.repeat(states, bin_size)[:count]]
