"""Collective slowdown is bounded evidence, not a missing-ball shortcut."""

from dataclasses import replace

import numpy as np
import pytest

from playground.possession_fixes.policy import FixPolicy
from playground.possession_fixes.stoppages import build_collective_stoppages
from playground.tests.fixtures import features


def remote_ball(count: int = 100):
    return replace(
        features([0] * count),
        nearest_home_distance_m=np.full(count, 3.0),
        nearest_away_distance_m=np.full(count, 5.0),
        median_player_speed_mps=np.full(count, 1.0),
        ball_speed_mps=np.full(count, 3.0),
    )


def test_seed_backdates_sustained_slowdown_with_observed_remote_ball():
    data = remote_ball(60)
    data.median_player_speed_mps[:10] = 2
    data.median_player_speed_mps[40:] = 2

    mask, audits = build_collective_stoppages(data)

    np.testing.assert_array_equal(np.flatnonzero(mask), np.arange(10, 40))
    assert audits == [
        {
            "start_frame": 10,
            "end_frame_exclusive": 40,
            "seed_start_frame": 10,
            "seed_end_frame_exclusive": 40,
            "release_reason": "collective_seed_ended",
        }
    ]


@pytest.mark.parametrize(
    "change",
    [
        "missing_ball",
        "sparse_players",
        "unknown_player_speed",
        "unknown_ball_speed",
        "fast_ball",
        "outside",
    ],
)
def test_seed_rejects_missing_sparse_unknown_fast_or_outside_evidence(change):
    data = remote_ball(30)
    if change == "missing_ball":
        data.ball_valid[:] = False
    elif change == "sparse_players":
        data.visible_player_count[:] = 7
    elif change == "unknown_player_speed":
        data.median_player_speed_mps[:] = np.nan
    elif change == "unknown_ball_speed":
        data.ball_speed_mps[:] = np.nan
    elif change == "fast_ball":
        data.ball_speed_mps[:] = 13
    else:
        data.ball_x_m[:] = -1

    mask, audits = build_collective_stoppages(data, hold=True)

    assert not mask.any()
    assert not audits


def test_slow_controlled_buildup_does_not_seed_a_stoppage():
    data = remote_ball(60)
    data.nearest_home_distance_m[:] = 1.5

    mask, audits = build_collective_stoppages(data, hold=True)

    assert not mask.any()
    assert not audits


def test_seed_requires_one_continuous_run_for_the_minimum_duration():
    data = remote_ball(39)
    data.ball_valid[19] = False

    mask, audits = build_collective_stoppages(data)

    assert not mask.any()
    assert not audits


def test_hold_retains_missing_ball_until_bounded_timeout():
    data = remote_ball(260)
    data.ball_valid[20:] = False

    mask, audits = build_collective_stoppages(data, hold=True)

    assert mask[:200].all()
    assert not mask[200:].any()
    assert audits[0]["end_frame_exclusive"] == 200
    assert audits[0]["release_reason"] == "retention_limit"


def test_one_continuous_seed_cannot_rearm_itself_after_timeout():
    data = remote_ball(500)

    mask, audits = build_collective_stoppages(data, hold=True)

    assert len(audits) == 1
    assert mask.sum() == 200
    assert not mask[200:].any()


def test_hold_releases_at_first_frame_of_confirmed_controlled_restart():
    data = remote_ball(100)
    data.nearest_home_distance_m[30:] = 0.5
    data.median_player_speed_mps[30:] = 2

    mask, audits = build_collective_stoppages(data, hold=True)

    assert mask[:30].all()
    assert not mask[30:].any()
    assert audits[0]["release_reason"] == "supported_restart_motion"
    assert audits[0]["end_frame_exclusive"] == 30


def test_brief_restart_motion_does_not_release_until_sustained_evidence():
    data = remote_ball(100)
    data.nearest_home_distance_m[30:33] = 0.5
    data.median_player_speed_mps[30:33] = 2
    data.nearest_home_distance_m[50:] = 0.5
    data.median_player_speed_mps[50:] = 2

    mask, audits = build_collective_stoppages(data, hold=True)

    assert mask[:50].all()
    assert not mask[50:].any()
    assert audits[0]["end_frame_exclusive"] == 50


def test_fast_controlled_ball_can_release_when_other_players_remain_slow():
    data = remote_ball(80)
    data.nearest_home_distance_m[30:] = 0.5
    data.ball_speed_mps[30:] = 8

    mask, audits = build_collective_stoppages(data, hold=True)

    assert mask[:30].all()
    assert not mask[30:].any()
    assert audits[0]["release_reason"] == "supported_restart_motion"


def test_sparse_collective_speed_does_not_release_a_slow_controlled_ball():
    data = remote_ball(80)
    data.nearest_home_distance_m[30:] = 0.5
    data.median_player_speed_mps[30:] = 2
    data.visible_player_count[30:] = 7

    mask, audits = build_collective_stoppages(data, hold=True)

    assert mask.all()
    assert audits[0]["release_reason"] == "recording_end"


def test_distinct_later_seed_can_initiate_a_new_stoppage():
    data = remote_ball(120)
    data.nearest_home_distance_m[30:60] = 0.5
    data.median_player_speed_mps[30:60] = 2
    data.nearest_home_distance_m[90:] = 0.5
    data.median_player_speed_mps[90:] = 2

    mask, audits = build_collective_stoppages(data, hold=True)

    assert [(a["start_frame"], a["end_frame_exclusive"]) for a in audits] == [
        (0, 30),
        (60, 90),
    ]
    assert mask.sum() == 60


def test_custom_retention_is_clipped_to_recording_and_does_not_mutate_inputs():
    data = remote_ball(80)
    before = data.ball_speed_mps.copy()
    policy = replace(FixPolicy(), collective_max_retention_seconds=3)

    mask, audits = build_collective_stoppages(data, policy, hold=True)

    assert mask.sum() == 30
    assert audits[0]["end_frame_exclusive"] == 30
    np.testing.assert_array_equal(data.ball_speed_mps, before)
