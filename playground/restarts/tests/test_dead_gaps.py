"""Restrict restart-local dead-ball continuity to unsupported short live islands."""

from dataclasses import replace

import numpy as np
import pytest

from playground.restarts.dead_gaps import bridge_restart_dead_gaps
from playground.smart_tags import SmartTag
from playground.tests.fixtures import features


def restart(start: int, end: int, event_type: str = "Free Kick") -> SmartTag:
    return SmartTag("synthetic-restart", start, end, "SET PIECES", -1, event_type, "")


def test_dead_gap_bridge_fills_bounded_missing_ball_island_without_mutation():
    labels = np.array(["D"] * 10 + ["H"] * 5 + ["A"] * 5 + ["D"] * 10)
    data = features([-1] * len(labels))
    original = labels.copy()

    actual = bridge_restart_dead_gaps(labels, data, (restart(0, len(labels)),))

    assert np.all(actual == "D")
    assert np.array_equal(labels, original)


@pytest.mark.parametrize("live_evidence", ["moving_ball", "near_player"])
def test_dead_gap_bridge_preserves_supported_live_play(live_evidence: str):
    labels = np.array(["D"] * 10 + ["H"] * 10 + ["D"] * 10)
    data = features([-1] * len(labels))
    valid = data.ball_valid.copy()
    speed = data.ball_speed_mps.copy()
    home = data.nearest_home_distance_m.copy()
    valid[15] = True
    speed[15] = 3 if live_evidence == "moving_ball" else 0
    home[15] = 10 if live_evidence == "moving_ball" else 1
    data = replace(
        data, ball_valid=valid, ball_speed_mps=speed, nearest_home_distance_m=home
    )

    actual = bridge_restart_dead_gaps(labels, data, (restart(0, len(labels)),))

    assert np.array_equal(actual, labels)


@pytest.mark.parametrize(
    "label_values",
    [
        ["H"] * 5 + ["D"] * 10,
        ["D"] * 10 + ["H"] * 5,
        ["D"] + ["H"] * 21 + ["D"],
        ["D"] * 10 + ["H"] * 4 + ["X"] + ["A"] * 5 + ["D"] * 10,
    ],
    ids=["leading", "trailing", "long", "explicit_abstention"],
)
def test_dead_gap_bridge_preserves_unbounded_long_or_abstaining_intervals(
    label_values: list[str],
):
    labels = np.array(label_values)
    data = features([-1] * len(labels))

    actual = bridge_restart_dead_gaps(labels, data, (restart(0, len(labels)),))

    assert np.array_equal(actual, labels)


@pytest.mark.parametrize(
    "tags",
    [
        (),
        (restart(15, 30),),
        (restart(0, 30, "Unknown Event"),),
        (restart(0, 15), restart(15, 30)),
    ],
    ids=["no_event", "partial_window", "unknown_type", "separate_windows"],
)
def test_dead_gap_bridge_requires_one_recognized_event_covering_both_boundaries(
    tags: tuple[SmartTag, ...],
):
    labels = np.array(["D"] * 10 + ["H"] * 10 + ["D"] * 10)
    data = features([-1] * len(labels))

    actual = bridge_restart_dead_gaps(labels, data, tags)

    assert np.array_equal(actual, labels)
