"""Check that restart masks alter control state and survive final continuity."""

from dataclasses import replace

import numpy as np

from playground.refinement.prediction import predict_refinement
from playground.refinement.specs import OCCLUSION
from playground.restarts.prediction import integrate_restart_dead
from playground.tests.fixtures import empty_tags, features


def test_empty_restart_mask_reproduces_the_occlusion_reference():
    data = features([0] * 90 + [-1] * 30 + [0] * 90)
    tags = empty_tags(data.frame_count)

    expected = predict_refinement(data, tags, OCCLUSION)
    actual = integrate_restart_dead(data, tags, np.zeros(data.frame_count, bool))

    assert np.array_equal(actual, expected)


def test_restart_stoppage_resets_control_before_a_new_team_observation():
    data = features([0] * 100 + [1] * 100)
    home = data.nearest_home_distance_m.copy()
    away = data.nearest_away_distance_m.copy()
    home[100:] = 4
    away[100:] = 3
    data = replace(data, nearest_home_distance_m=home, nearest_away_distance_m=away)
    tags = empty_tags(data.frame_count)
    dead = np.zeros(data.frame_count, dtype=bool)
    dead[80:100] = True

    reference = predict_refinement(data, tags, OCCLUSION)
    actual = integrate_restart_dead(data, tags, dead)

    assert reference[151] == "H"
    assert actual[151] == "A"
    assert np.all(actual[dead] == "D")


def test_restart_mask_survives_smoothing_and_same_team_occlusion_bridge():
    data = features([0] * 80 + [-1] * 40 + [0] * 80)
    tags = empty_tags(data.frame_count)
    dead = np.zeros(data.frame_count, dtype=bool)
    dead[90:110] = True
    original_codes = data.nearest_code.copy()
    original_mask = dead.copy()

    actual = integrate_restart_dead(data, tags, dead)

    assert np.all(actual[90:110] == "D")
    assert actual[0] == actual[-1] == "H"
    assert np.array_equal(data.nearest_code, original_codes)
    assert np.array_equal(dead, original_mask)
