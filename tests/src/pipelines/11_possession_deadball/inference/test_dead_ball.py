"""Stoppages come from walking players, a ball off the pitch and restart tags."""

from dataclasses import replace
from importlib import import_module

import numpy as np

from tests.fixtures.possession_deadball import PACKAGE, PossessionPolicy, features

DeadBallDetector = import_module(PACKAGE + ".inference.dead_ball").DeadBallDetector

# 10 FPS: a 1 s activity window and a 2 s minimum stoppage.
POLICY = replace(
    PossessionPolicy(), activity_window_seconds=1, minimum_stoppage_seconds=2
)


def detect(speed: list[float], windows: list[tuple[int, int]] | None = None):
    return DeadBallDetector(POLICY, windows or []).detect(features(np.array(speed)))


def test_sustained_walking_is_a_stoppage_and_running_is_not() -> None:
    result = detect([3.0] * 40 + [0.5] * 40 + [3.0] * 40)

    assert result[50:70].all()
    assert not result[:30].any()
    assert not result[90:].any()


def test_short_slow_dip_is_not_a_stoppage() -> None:
    result = detect([3.0] * 40 + [0.5] * 10 + [3.0] * 40)

    assert not result.any()


def test_stoppage_lasts_until_players_clearly_run_again() -> None:
    speed = [3.0] * 30 + [0.5] * 30 + [1.4] * 30 + [3.0] * 30
    result = detect(speed)

    assert result[70:80].all()
    assert not result[110:].any()


def test_slow_start_without_clear_walking_is_not_a_stoppage() -> None:
    assert not detect([1.4] * 100).any()


def test_unknown_activity_never_starts_a_stoppage() -> None:
    assert not detect([np.nan] * 100).any()


def test_ball_held_beyond_the_lines_is_a_stoppage_even_when_players_run() -> None:
    ball_x = np.full(100, 50.0)
    ball_x[30:70] = -5
    data = features(np.full(100, 3.0), ball_x=ball_x)

    result = DeadBallDetector(POLICY, []).detect(data)

    assert result[35:65].all()
    assert not result[:25].any()
    assert not result[75:].any()


def test_set_piece_tag_marks_slow_play_but_not_running_play() -> None:
    walking = detect([3.0] * 20 + [1.5] * 60 + [3.0] * 20, [(30, 60)])
    running = detect([3.0] * 100, [(30, 60)])

    assert walking[30:60].all()
    assert not running.any()
