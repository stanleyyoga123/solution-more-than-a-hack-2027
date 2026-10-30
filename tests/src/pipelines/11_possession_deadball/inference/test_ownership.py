"""Ownership keeps the incumbent until opposing control is confirmed."""

from dataclasses import replace
from importlib import import_module

import numpy as np

from tests.fixtures.possession_deadball import PACKAGE, PossessionPolicy, features

Ownership = import_module(PACKAGE + ".inference.ownership").Ownership


def predict(codes: list[int]) -> list[str]:
    return Ownership(PossessionPolicy()).predict(features(codes=codes)).tolist()


def test_ownership_survives_a_long_gap_without_evidence() -> None:
    assert predict([0, 0] + [-1] * 60 + [0]) == ["H"] * 63


def test_confirmed_handover_is_backdated_to_its_first_frame() -> None:
    assert predict([0] * 4 + [1] * 5) == ["H"] * 4 + ["A"] * 5


def test_short_opposing_run_does_not_transfer_ownership() -> None:
    assert predict([0] * 4 + [1] * 3 + [0] * 4) == ["H"] * 11


def test_frames_before_any_observation_are_dead() -> None:
    assert predict([-1, -1, 1, 1]) == ["D", "D", "A", "A"]


def test_candidates_require_distance_advantage_and_plausible_ball_speed() -> None:
    data = replace(
        features(codes=[0] * 4),
        nearest_home_distance_m=np.array([0.5, 1, 4, 1]),
        nearest_away_distance_m=np.array([4, 1.1, 0.5, 4]),
        ball_speed_mps=np.array([2, 2, 2, 20]),
    )

    result = Ownership(PossessionPolicy()).candidates(data)

    assert result.tolist() == [0, -1, 1, -1]
