"""Possession changes only when the opposing team keeps the ball or passes it on."""

from dataclasses import replace
from importlib import import_module

import numpy as np

from tests.fixtures.possession_touch import PACKAGE, PossessionPolicy, features

Ownership = import_module(PACKAGE + ".inference.ownership").Ownership

# 10 FPS: touches less than 10 frames apart merge, 15 frames is a held ball and a
# pass must be completed within 30 frames. -1 is the ball in flight or out of sight.
FLIGHT = -1


def predict(codes: list[int]) -> list[str]:
    return Ownership(PossessionPolicy()).predict(features(codes=codes)).tolist()


def test_single_opposing_touch_does_not_take_possession() -> None:
    codes = [0] * 20 + [FLIGHT] * 5 + [1] * 3 + [FLIGHT] * 5 + [0] * 20

    assert predict(codes) == ["H"] * 53


def test_holding_the_ball_takes_possession_from_the_first_touch() -> None:
    assert predict([0] * 10 + [1] * 15) == ["H"] * 10 + ["A"] * 15


def test_holding_the_ball_for_less_than_the_dwell_time_is_not_enough() -> None:
    assert predict([0] * 10 + [1] * 14) == ["H"] * 24


def test_opposing_pass_completed_within_the_window_takes_possession() -> None:
    codes = [0] * 10 + [1] * 3 + [FLIGHT] * 20 + [1] * 3

    assert predict(codes) == ["H"] * 10 + ["A"] * 26


def test_opposing_second_touch_after_the_window_is_a_separate_touch() -> None:
    codes = [0] * 10 + [1] * 3 + [FLIGHT] * 40 + [1] * 3

    assert predict(codes) == ["H"] * 56


def test_touches_closer_than_the_gap_count_as_one_held_ball() -> None:
    codes = [0] * 10 + [1] * 8 + [FLIGHT] * 5 + [1] * 8

    assert predict(codes) == ["H"] * 10 + ["A"] * 21


def test_possession_is_handed_back_the_same_way() -> None:
    codes = [0] * 10 + [1] * 15 + [FLIGHT] * 5 + [0] * 15

    assert predict(codes) == ["H"] * 10 + ["A"] * 20 + ["H"] * 15


def test_ownership_survives_a_long_gap_without_touches() -> None:
    assert predict([0, 0] + [FLIGHT] * 60 + [0]) == ["H"] * 63


def test_first_toucher_owns_the_frames_before_the_first_touch() -> None:
    assert predict([FLIGHT] * 5 + [1] * 3) == ["A"] * 8


def test_half_without_any_touch_is_dead() -> None:
    assert predict([FLIGHT] * 10) == ["D"] * 10


def test_touch_requires_a_player_within_reach_of_the_ball() -> None:
    data = replace(
        features(codes=[0] * 3),
        nearest_home_distance_m=np.array([1.6, 1.5, 4.0]),
        nearest_away_distance_m=np.array([4.0, 4.0, 4.0]),
    )

    result = Ownership(PossessionPolicy()).contacts(data)

    assert [(c.first, c.last, c.team) for c in result] == [(1, 1, 0)]
