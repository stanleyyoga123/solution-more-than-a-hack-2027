"""Check bounded stoppage entry, persistence and backdated restart release."""

from dataclasses import replace

import numpy as np
import pytest

from playground.restarts.intervals import restart_dead_intervals
from playground.restarts.policy import RestartPolicy
from playground.smart_tags import SmartTag
from playground.tests.fixtures import features


def restart(start: int = 0, end: int = 40, identifier: str = "1"):
    return SmartTag(identifier, start, end, "SET PIECES", -1, "Free Kick", "1st Half")


def test_first_stationary_seed_persists_through_missing_ball_and_backdates_release():
    data = features([0] * 6 + [-1] * 4 + [0] * 10)
    speed = data.ball_speed_mps.copy()
    speed[:6] = 0
    data = replace(data, ball_speed_mps=speed)
    mask, events = restart_dead_intervals(data, (restart(end=20),))
    # Frame 10 has no observed predecessor, so live confirmation starts at 11.
    assert np.flatnonzero(mask).tolist() == list(range(1, 11))
    assert events[0]["start_frame"] == 1
    assert events[0]["end_frame"] == 11
    assert events[0]["release_reason"] == "supported_live_motion"


def test_released_event_does_not_start_a_second_stoppage_later_in_its_window():
    data = features([0] * 30)
    speed = np.zeros(30)
    speed[8:10] = 3
    data = replace(data, ball_speed_mps=speed)
    mask, _ = restart_dead_intervals(data, (restart(end=30),))
    assert np.flatnonzero(mask).tolist() == list(range(1, 8))
    assert not mask[10:].any()


def test_brief_or_impossible_ball_motion_cannot_release_a_stoppage():
    data = features([0] * 30)
    speed = np.zeros(30)
    speed[8] = 3
    speed[12:15] = 80
    data = replace(data, ball_speed_mps=speed)
    mask, events = restart_dead_intervals(data, (restart(end=30),))
    assert mask[1:].all()
    assert events[0]["release_reason"] == "tag_window_end"


def test_control_release_requires_close_original_distance_and_movement():
    data = replace(features([0] * 20), ball_speed_mps=np.full(20, 0.9))
    base, _ = restart_dead_intervals(data, (restart(end=20),))
    control, events = restart_dead_intervals(
        data, (restart(end=20),), release_on_control=True
    )
    assert base[1:].all()
    assert np.flatnonzero(control).tolist() == [1, 2, 3, 4]
    assert events[0]["end_frame"] == 5
    distant = replace(data, nearest_home_distance_m=np.full(20, 5.0))
    far_control, _ = restart_dead_intervals(
        distant, (restart(end=20),), release_on_control=True
    )
    assert far_control[1:].all()


def test_backward_extension_crosses_tag_start_but_stops_at_observed_live_play():
    data = features([0] * 3 + [-1] * 5 + [0] * 12)
    speed = data.ball_speed_mps.copy()
    speed[8:] = 0
    data = replace(data, ball_speed_mps=speed)
    plain, _ = restart_dead_intervals(data, (restart(start=9, end=20),))
    extended, events = restart_dead_intervals(
        data, (restart(start=9, end=20),), extend_before=True
    )
    assert np.flatnonzero(plain).tolist() == list(range(9, 20))
    assert np.flatnonzero(extended).tolist() == list(range(3, 20))
    assert events[0]["start_frame"] == 3


def test_backward_extension_has_a_fixed_duration_limit():
    data = features([-1] * 30 + [0] * 20)
    speed = data.ball_speed_mps.copy()
    speed[30:] = 0
    data = replace(data, ball_speed_mps=speed)
    policy = replace(RestartPolicy(), backward_seconds=0.5)
    mask, events = restart_dead_intervals(
        data, (restart(start=31, end=50),), policy, extend_before=True
    )
    assert events[0]["start_frame"] == 26
    assert not mask[:26].any()


def test_dead_duration_cap_is_measured_from_seed_and_missing_ball_cannot_extend_it():
    data = features([0] * 6 + [-1] * 34)
    speed = data.ball_speed_mps.copy()
    speed[:6] = 0
    data = replace(data, ball_speed_mps=speed)
    policy = replace(RestartPolicy(), maximum_dead_seconds=1)
    mask, events = restart_dead_intervals(data, (restart(),), policy)
    assert np.flatnonzero(mask).tolist() == list(range(1, 11))
    assert events[0]["release_reason"] == "duration_limit"


def test_event_without_observed_seed_creates_only_an_undetected_diagnostic():
    data = features([-1] * 40)
    mask, events = restart_dead_intervals(data, (restart(),))
    assert not mask.any()
    assert events[0]["detected"] is False
    assert events[0]["start_frame"] is None
    assert events[0]["end_frame"] is None
    assert events[0]["release_reason"] == "no_stationary_seed"


def test_intervals_leave_original_feature_arrays_unchanged():
    data = replace(features([0] * 40), ball_speed_mps=np.zeros(40))
    x_before = data.ball_x_m.copy()
    speed_before = data.ball_speed_mps.copy()
    restart_dead_intervals(
        data, (restart(),), extend_before=True, release_on_control=True
    )
    assert np.array_equal(data.ball_x_m, x_before)
    assert np.array_equal(data.ball_speed_mps, speed_before)


def test_boundary_entry_does_not_require_stationary_ball_and_uses_short_confirmation():
    data = features([0] * 20)
    x = data.ball_x_m.copy()
    y = data.ball_y_m.copy()
    x[:] = 50
    y[:2] = -1
    speed = np.full(20, 3.0)
    data = replace(data, ball_x_m=x, ball_y_m=y, ball_speed_mps=speed)
    tag = replace(restart(end=20), event_type="Throw-in")
    stationary_only, _ = restart_dead_intervals(data, (tag,))
    mask, events = restart_dead_intervals(data, (tag,), include_boundary=True)
    assert not stationary_only.any()
    assert np.flatnonzero(mask).tolist() == [0, 1]
    assert events[0]["seed_type"] == "boundary"
    assert events[0]["end_frame"] == 2


@pytest.mark.parametrize("kind", ["Free Kick", "Kick Off (Start)", "Unknown"])
def test_outside_observation_does_not_start_non_boundary_restart(kind):
    data = features([0] * 20)
    x = np.full(20, -1.0)
    data = replace(data, ball_x_m=x)
    tag = replace(restart(end=20), event_type=kind)
    mask, _ = restart_dead_intervals(data, (tag,), include_boundary=True)
    assert not mask.any()


def test_boundary_seed_needs_persistent_type_compatible_outside_observations():
    data = features([0] * 20)
    y = data.ball_y_m.copy()
    y[2] = -1
    data = replace(data, ball_y_m=y)
    tag = replace(restart(end=20), event_type="Throw-in")
    assert not restart_dead_intervals(data, (tag,), include_boundary=True)[0].any()
    # A persistent ball past the goal line is not a throw-in location.
    x = np.full(20, -1.0)
    data = replace(data, ball_x_m=x, ball_y_m=np.full(20, 30.0))
    assert not restart_dead_intervals(data, (tag,), include_boundary=True)[0].any()
