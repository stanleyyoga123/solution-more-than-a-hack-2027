"""Global inference should retain supported spells and explicit stoppages."""

from dataclasses import replace

import numpy as np

from playground.creative.decoding import viterbi_possession
from playground.tests.fixtures import empty_tags, features


def test_viterbi_ignores_brief_opponent_evidence_but_keeps_a_supported_handover() -> (
    None
):
    codes = [0] * 100 + [1] * 100 + [0] * 103
    codes[50] = 1
    evidence = features(codes)

    labels = viterbi_possession(evidence, empty_tags(len(codes)))

    assert len(labels) == len(codes)
    assert labels[25] == labels[50] == labels[250] == "H"
    assert labels[150] == "A"
    assert np.count_nonzero(labels[:-1] != labels[1:]) == 2


def test_viterbi_treats_missing_observations_as_neutral_between_same_team_spells() -> (
    None
):
    evidence = features([0] * 50 + [-1] * 50 + [0] * 50)

    labels = viterbi_possession(evidence, empty_tags(evidence.frame_count))

    assert set(labels) == {"H"}


def test_viterbi_detects_sustained_explicit_out_of_pitch_evidence() -> None:
    evidence = features([0] * 250)
    ball_x = evidence.ball_x_m.copy()
    ball_x[100:140] = 101
    evidence = replace(evidence, ball_x_m=ball_x)

    labels = viterbi_possession(evidence, empty_tags(evidence.frame_count))

    assert set(labels[110:130]) == {"D"}
    assert labels[25] == labels[225] == "H"


def test_viterbi_does_not_infer_dead_ball_only_from_distant_players() -> None:
    evidence = features([0] * 100)
    evidence = replace(
        evidence,
        nearest_home_distance_m=np.full(100, 80.0),
        nearest_away_distance_m=np.full(100, 81.0),
    )

    labels = viterbi_possession(evidence, empty_tags(evidence.frame_count))

    assert "D" not in labels
