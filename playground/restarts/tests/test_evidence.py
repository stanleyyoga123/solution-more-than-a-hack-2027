"""Check restart geometry and stationary support without possession labels."""

from dataclasses import replace

import numpy as np
import pytest

from playground.restarts.evidence import full_window_mask, restart_seed_mask
from playground.smart_tags import SmartTag
from playground.tests.fixtures import features


def restart(kind: str, start: int = 0, end: int = 20, code: str = "SET PIECES"):
    return SmartTag("1", start, end, code, -1, kind, "1st Half")


@pytest.mark.parametrize(
    ("kind", "location"),
    [
        ("Throw-in", (50, 1)),
        ("Corner Kick", (1, 1)),
        ("Goal Kick", (3, 30)),
        ("Free Kick", (50, 20)),
        ("Kick Off (Start)", (50, 30)),
        ("Kick Off (After Goal)", (50, 30)),
    ],
)
def test_stationary_restart_needs_type_compatible_location(kind, location):
    data = features([0] * 20)
    data = replace(
        data,
        ball_x_m=np.full(20, location[0], dtype=float),
        ball_y_m=np.full(20, location[1], dtype=float),
        ball_speed_mps=np.zeros(20),
    )
    mask = restart_seed_mask(data, (restart(kind),))
    assert not mask[0]
    assert mask[1:].all()


@pytest.mark.parametrize(
    "kind", ["Throw-in", "Corner Kick", "Goal Kick", "Kick Off (Start)"]
)
def test_stationary_ball_away_from_restart_geometry_does_not_seed(kind):
    data = replace(features([0] * 20), ball_speed_mps=np.zeros(20))
    assert not restart_seed_mask(data, (restart(kind),)).any()


def test_seed_requires_continuity_and_does_not_join_short_runs_across_dropout():
    data = features([0, 0, 0, -1, 0, 0, 0, 0, 0])
    data = replace(data, ball_speed_mps=np.zeros(9))
    mask = restart_seed_mask(data, (restart("Free Kick", end=9),))
    assert mask.tolist() == [False] * 5 + [True] * 4


def test_short_tag_and_moving_ball_supply_no_stationary_seed():
    data = replace(features([0] * 20), ball_speed_mps=np.zeros(20))
    assert not restart_seed_mask(data, (restart("Free Kick", start=2, end=5),)).any()
    assert not restart_seed_mask(features([0] * 20), (restart("Free Kick"),)).any()


def test_unknown_events_and_non_restart_codes_are_ignored_case_insensitively():
    data = replace(features([0] * 20), ball_speed_mps=np.zeros(20))
    ignored = (restart("Foul"), restart("Free Kick", code="PROGRESSION"))
    assert not restart_seed_mask(data, ignored).any()
    assert not full_window_mask(ignored, 20).any()
    assert restart_seed_mask(data, (restart(" free kick ", code=" set pieces "),)).any()


def test_full_windows_are_half_open_clipped_and_preserve_input_tags():
    tags = (
        restart("Free Kick", -10, 2),
        restart("Throw-in", 18, 30),
        restart("Goal Kick", -20, -2),
        restart("Corner Kick", 30, 40),
    )
    before = tuple(tags)
    mask = full_window_mask(tags, 20)
    assert np.flatnonzero(mask).tolist() == [0, 1, 18, 19]
    assert tags == before
