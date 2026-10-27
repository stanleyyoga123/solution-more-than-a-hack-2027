"""Uncertainty representation must not fabricate physical or team evidence."""

from dataclasses import replace

import numpy as np

from playground.fragmentation.evidence import build_evidence, classify_uncertainty
from playground.tests.fixtures import empty_tags, features


def test_observed_sustained_control_excludes_missing_and_unknown_motion():
    original = features([0] * 5 + [-1] * 3 + [1] * 5)
    original.ball_speed_mps[2] = np.nan
    arrival = features([0] * 8 + [1] * 5)
    evidence = build_evidence(original, arrival, empty_tags(13))

    assert evidence.control_codes.tolist() == [0, 0, -1, 0, 0, -1, -1, -1] + [1] * 5
    assert evidence.confirmed_control.tolist() == [-1] * 8 + [1] * 5
    assert evidence.home_support.sum() == 0
    assert evidence.away_support.sum() == 5
    assert not evidence.dead.any()


def test_confirmation_requires_one_continuous_run_and_backdates_support():
    original = features([0] * 3 + [-1] + [0] * 4 + [1] * 4)
    evidence = build_evidence(original, original, empty_tags(12))

    assert evidence.confirmed_control.tolist() == [-1] * 4 + [0] * 4 + [1] * 4


def test_physical_dead_mask_uses_original_geometry_and_disables_control():
    original = features([0] * 20)
    original = replace(original, ball_x_m=np.full(20, -1.0))
    arrival = replace(features([0] * 20), ball_x_m=np.full(20, 40.0))
    evidence = build_evidence(original, arrival, empty_tags(20))

    assert evidence.dead.all()
    assert (evidence.control_codes == -1).all()
    assert (evidence.confirmed_control == -1).all()


def test_classification_round_trips_to_anchor_and_preserves_live_and_x():
    data = features([0] * 8)
    data.ball_x_m[3:5] = -1
    evidence = build_evidence(data, data, empty_tags(8))
    labels = np.array(list("HDDDDAXD"))
    before = labels.copy()
    internal = classify_uncertainty(labels, evidence)

    assert internal.tolist() == list("HUUDDAXU")
    exported = np.where(internal == "U", "D", internal)
    np.testing.assert_array_equal(exported, before)
    np.testing.assert_array_equal(labels, before)


def test_invalid_speed_and_geometry_do_not_supply_control():
    original = features([0] * 8)
    original.ball_speed_mps[:4] = [-1, 13, np.inf, np.nan]
    original.ball_x_m[4] = np.nan
    original.ball_y_m[5] = np.inf
    evidence = build_evidence(original, original, empty_tags(8))

    assert evidence.control_codes.tolist() == [-1] * 6 + [0, 0]
    assert not evidence.home_support.any()
