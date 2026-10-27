"""Controlled behavior for the predeclared possession experiment changes."""

from dataclasses import asdict, replace
import importlib

import numpy as np

from playground.control import confirm_control, control_candidates
from playground.dead_ball import boundary_dead_mask, stationary_dead_mask
from playground.experiments import EXPERIMENTS
from playground.prediction import predict
from playground.prediction_policy import DomainPolicy
from playground.temporal import bridge_missing_codes, majority_labels

from .fixtures import empty_tags, features


def test_each_iteration_changes_only_its_declared_prediction_component() -> None:
    informational = {
        "id",
        "parent_id",
        "title",
        "changed_component",
        "hypothesis",
        "rationale",
    }
    for parent, child in zip(EXPERIMENTS, EXPERIMENTS[1:]):
        before, after = asdict(parent), asdict(child)
        changes = [
            name
            for name in before
            if name not in informational and before[name] != after[name]
        ]
        assert child.parent_id == parent.id
        assert changes == [child.changed_component]


def test_baseline_prediction_matches_step05_including_edge_windows() -> None:
    codes = [0] * 30 + [-1] * 120 + [1] * 30 + [0, 1] * 40
    data = features(codes)
    baseline = importlib.import_module("src.pipelines.05_possession_baseline.pipeline")

    result = predict(data, empty_tags(data.frame_count), EXPERIMENTS[0])

    np.testing.assert_array_equal(result, baseline.smooth(data.nearest_code, 50))
    assert result[90] == "D"


def test_three_class_vote_preserves_missing_majority_and_home_wins_team_tie() -> None:
    codes = np.array([0, -1, -1, -1, 1], dtype=np.int8)

    original = majority_labels(codes, window=2, three_class=False)
    three_class = majority_labels(codes, window=2, three_class=True)

    assert original[2] == "H"
    assert three_class[2] == "D"


def test_missing_bridge_requires_short_same_team_bounded_interval() -> None:
    codes = np.array([-1, 0, -1, -1, 0, 1, -1, 0, 1, -1, -1, -1, 1, -1], dtype=np.int8)

    result = bridge_missing_codes(codes, maximum_frames=2)

    assert result.tolist() == [-1, 0, 0, 0, 0, 1, -1, 0, 1, -1, -1, -1, 1, -1]
    assert codes[2] == -1


def test_boundary_dead_requires_observed_sustained_margin_outside_pitch() -> None:
    data = features([0] * 8)
    data = replace(
        data,
        ball_x_m=np.array([-0.1, -0.3, 20, -0.3, -0.3, 20, 100.3, 20]),
        ball_valid=np.array([True] * 6 + [False, True]),
    )

    result = boundary_dead_mask(data, data.ball_valid, DomainPolicy())

    assert result.tolist() == [False, False, False, True, True, False, False, False]


def test_stationarity_alone_does_not_mark_play_dead() -> None:
    data = features([0] * 30)
    data = replace(
        data,
        ball_speed_mps=np.zeros(30),
        ball_displacement_1s_m=np.zeros(30),
    )

    without_context = stationary_dead_mask(
        data, empty_tags(30), data.ball_valid, DomainPolicy()
    )
    tags = replace(empty_tags(30), restart_mask=np.ones(30, dtype=bool))
    with_context = stationary_dead_mask(data, tags, data.ball_valid, DomainPolicy())

    assert not without_context.any()
    assert not with_context[:10].any()
    assert with_context[10:].all()


def test_stationary_detector_requires_continuous_ball_after_missing_frame() -> None:
    data = features([0] * 25)
    valid = np.ones(25, dtype=bool)
    valid[12] = False
    data = replace(
        data,
        ball_valid=valid,
        ball_speed_mps=np.zeros(25),
        ball_displacement_1s_m=np.zeros(25),
        median_player_speed_mps=np.zeros(25),
    )

    result = stationary_dead_mask(data, empty_tags(25), valid, DomainPolicy())

    assert not result.any()


def test_control_candidates_require_nearness_advantage_and_plausible_ball_speed() -> (
    None
):
    result = control_candidates(
        np.array([0.5, 1, 4, 1, np.inf]),
        np.array([4, 1.1, 0.5, 4, np.inf]),
        np.array([2, 2, 2, 20, np.nan]),
        DomainPolicy(),
    )

    assert result.tolist() == [0, -1, 1, -1, -1]


def test_control_retains_team_through_loose_ball_and_backdates_confirmed_switch() -> (
    None
):
    observed = np.array([0] * 4 + [1] * 3 + [0] * 2 + [1] * 5, dtype=np.int8)
    candidates = np.array([0] * 4 + [-1] * 3 + [0] * 2 + [1] * 5, dtype=np.int8)

    result = confirm_control(
        observed, candidates, np.zeros(14, dtype=bool), 10, DomainPolicy()
    )

    assert result.tolist() == [0] * 9 + [1] * 5


def test_control_requires_consecutive_opponent_confirmation() -> None:
    observed = np.array([0] * 4 + [1] * 6, dtype=np.int8)
    candidates = np.array([0] * 4 + [1, 1, -1, 1, 1, 1], dtype=np.int8)

    result = confirm_control(
        observed, candidates, np.zeros(10, dtype=bool), 10, DomainPolicy()
    )

    assert result.tolist() == [0] * 10


def test_dead_ball_clears_incumbent_and_long_missing_observations_expire() -> None:
    observed = np.array([0, 0] + [-1] * 23 + [1], dtype=np.int8)
    candidates = np.array([0, 0] + [-1] * 23 + [1], dtype=np.int8)

    expired = confirm_control(
        observed, candidates, np.zeros(26, dtype=bool), 10, DomainPolicy()
    )
    dead = np.zeros(26, dtype=bool)
    dead[4] = True
    reset = confirm_control(observed, candidates, dead, 10, DomainPolicy())

    assert expired[:22].tolist() == [0] * 22
    assert expired[22:25].tolist() == [-1] * 3
    assert expired[25] == 1
    assert reset[4:25].tolist() == [-1] * 21
    assert reset[25] == 1


def test_phase_votes_cannot_override_unambiguous_geometric_control() -> None:
    data = features([0] * 30)
    tags = replace(empty_tags(30), away_phase_votes=np.full(30, 3, dtype=np.int16))
    spec = replace(EXPERIMENTS[6], smoothing_window_frames=0)

    result = predict(data, tags, spec)

    assert result.tolist() == ["H"] * 30


def test_phase_votes_support_missing_control_after_temporal_confirmation() -> None:
    data = features([-1] * 12)
    tags = replace(empty_tags(12), away_phase_votes=np.ones(12, dtype=np.int16))
    spec = replace(EXPERIMENTS[6], smoothing_window_frames=0)

    result = predict(data, tags, spec)

    assert result.tolist() == ["A"] * 12


def test_quality_filter_uses_clean_geometry_without_mutating_raw_features() -> None:
    data = features([0] * 20)
    data = replace(
        data,
        quality_nearest_code=np.ones(20, dtype=np.int8),
        quality_home_distance_m=np.full(20, 4.0),
        quality_away_distance_m=np.full(20, 0.5),
    )
    spec = replace(EXPERIMENTS[7], smoothing_window_frames=0)

    result = predict(data, empty_tags(20), spec)

    assert result.tolist() == ["A"] * 20
    assert data.nearest_code.tolist() == [0] * 20
