"""Standalone control geometry, handover confirmation and missing-data expiry."""

from dataclasses import replace
from importlib import import_module

import numpy as np

from tests.fixtures.possession_control import features

PACKAGE = "src.pipelines.10_possession_control"
PossessionPolicy = import_module(PACKAGE + ".configuration.policy").PossessionPolicy
ControlConfirmation = import_module(
    PACKAGE + ".inference.control_confirmation"
).ControlConfirmation


def test_candidates_require_close_separated_control_and_allow_unknown_ball_speed() -> (
    None
):
    data = replace(
        features([0] * 6),
        nearest_home_distance_m=np.array([0.5, 1, 4, 1, np.inf, 0.5]),
        nearest_away_distance_m=np.array([4, 1.1, 0.5, 4, np.inf, 4]),
        ball_speed_mps=np.array([2, 2, 2, 20, np.nan, np.nan]),
    )

    result = ControlConfirmation(PossessionPolicy()).candidates(data)

    assert result.tolist() == [0, -1, 1, -1, -1, 0]


def test_control_keeps_incumbent_until_confirmation_and_backdates_handover() -> None:
    codes = [0] * 4 + [1] * 3 + [0] * 2 + [1] * 5
    data = features(codes)
    home = data.nearest_home_distance_m.copy()
    away = data.nearest_away_distance_m.copy()
    home[4:7] = away[4:7] = 4
    data = replace(data, nearest_home_distance_m=home, nearest_away_distance_m=away)

    result = ControlConfirmation(PossessionPolicy()).predict(data)

    assert result.tolist() == ["H"] * 9 + ["A"] * 5


def test_control_resets_pending_handover_on_interrupted_evidence() -> None:
    data = features([0] * 4 + [1] * 6)
    home = data.nearest_home_distance_m.copy()
    away = data.nearest_away_distance_m.copy()
    home[6] = away[6] = 4
    data = replace(data, nearest_home_distance_m=home, nearest_away_distance_m=away)

    result = ControlConfirmation(PossessionPolicy()).predict(data)

    assert result.tolist() == ["H"] * 10


def test_control_retains_missing_evidence_only_until_timeout_then_initializes_new_team() -> (
    None
):
    data = features([0, 0] + [-1] * 23 + [1])

    result = ControlConfirmation(PossessionPolicy()).predict(data)

    assert result.tolist() == ["H"] * 22 + ["D"] * 3 + ["A"]


def test_unresolved_leading_gap_stays_dead_and_confirmed_short_possession_is_retained() -> (
    None
):
    data = features([-1, -1] + [0] * 4 + [1] * 4)

    result = ControlConfirmation(PossessionPolicy()).predict(data)

    assert result.tolist() == ["D"] * 2 + ["H"] * 4 + ["A"] * 4


def test_control_can_initialize_from_nearest_team_without_a_close_candidate() -> None:
    data = replace(
        features([1, 0, 0]),
        nearest_home_distance_m=np.full(3, 10.0),
        nearest_away_distance_m=np.full(3, 8.0),
    )

    result = ControlConfirmation(PossessionPolicy()).predict(data)

    assert result.tolist() == ["A", "A", "A"]
    assert data.nearest_code.tolist() == [1, 0, 0]
