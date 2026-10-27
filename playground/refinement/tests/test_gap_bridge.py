"""Restrict label continuity to bounded same-team ball occlusions."""

from dataclasses import replace

import numpy as np

from playground.refinement.gap_bridge import bridge_occluded_possession
from playground.tests.fixtures import empty_tags, features


def test_occlusion_bridge_fills_same_team_gap_without_changing_input():
    data = features([0] + [-1] * 30 + [0])
    labels = np.array(["H"] + ["D"] * 30 + ["H"])
    result = bridge_occluded_possession(labels, data, empty_tags(32))
    assert np.all(result == "H")
    assert np.all(labels[1:-1] == "D")


def test_occlusion_bridge_preserves_restart_or_visible_ball_stoppage():
    data = features([0] + [-1] * 30 + [0])
    labels = np.array(["H"] + ["D"] * 30 + ["H"])
    tags = empty_tags(32)
    tags.restart_mask[10] = True
    assert np.array_equal(bridge_occluded_possession(labels, data, tags), labels)
    visible = data.ball_valid.copy()
    visible[10] = True
    data = replace(data, ball_valid=visible)
    assert np.array_equal(
        bridge_occluded_possession(labels, data, empty_tags(32)), labels
    )


def test_occlusion_bridge_preserves_long_unbounded_and_opposed_team_runs():
    for labels in (
        ["D"] * 4 + ["H"],
        ["H"] + ["D"] * 4,
        ["H"] + ["D"] * 4 + ["A"],
        ["H"] + ["D"] * 81 + ["H"],
    ):
        values = np.array(labels)
        data = features([-1] * len(labels))
        assert np.array_equal(
            bridge_occluded_possession(values, data, empty_tags(len(labels))), values
        )
