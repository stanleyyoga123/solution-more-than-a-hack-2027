"""Check boundary latching, sustained release, and finite retention."""

from dataclasses import replace

import numpy as np

from playground.refinement.control_policy import ControlPolicy
from playground.refinement.stoppages import persistent_boundary_dead_mask
from playground.tests.fixtures import features


def test_boundary_latch_persists_through_missing_ball_then_confirms_release():
    data = features([0, 0, -1, -1, 0, 0, 0], fps=10)
    x = data.ball_x_m.copy()
    x[:2] = -1
    data = replace(data, ball_x_m=x)
    mask = persistent_boundary_dead_mask(data)
    assert mask.tolist() == [True, True, True, True, True, False, False]


def test_boundary_release_needs_consecutive_observed_live_frames():
    data = features([0, 0, 0, -1, 0, 0], fps=10)
    x = data.ball_x_m.copy()
    x[:2] = -1
    data = replace(data, ball_x_m=x)
    mask = persistent_boundary_dead_mask(data)
    assert mask.tolist() == [True, True, True, True, True, False]


def test_stationary_distant_ball_inside_pitch_does_not_release_latch():
    data = features([0] * 8, fps=10)
    x = data.ball_x_m.copy()
    x[:2] = -1
    data = replace(
        data,
        ball_x_m=x,
        ball_speed_mps=np.zeros(8),
        nearest_home_distance_m=np.full(8, 5.0),
        nearest_away_distance_m=np.full(8, 5.0),
    )
    assert persistent_boundary_dead_mask(data).all()


def test_latch_expires_from_last_boundary_cue_without_extending_for_missing_ball():
    data = features([0, 0] + [-1] * 7, fps=10)
    x = data.ball_x_m.copy()
    x[:2] = -1
    data = replace(data, ball_x_m=x)
    policy = replace(ControlPolicy(), boundary_retention_seconds=0.3)
    mask = persistent_boundary_dead_mask(data, policy=policy)
    assert mask.tolist() == [True, True, True, True, True, False, False, False, False]


def test_missing_ball_or_brief_outside_observation_never_starts_latch():
    data = features([-1] * 8, fps=10)
    assert not persistent_boundary_dead_mask(data).any()
    data = features([0] * 8, fps=10)
    x = data.ball_x_m.copy()
    x[2] = -1
    data = replace(data, ball_x_m=x)
    assert not persistent_boundary_dead_mask(data).any()
