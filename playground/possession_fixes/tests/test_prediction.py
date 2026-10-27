"""Physical control checks must isolate projected proximity from ownership."""

from dataclasses import fields, replace

import numpy as np
import pytest

from playground.fragmentation.evidence import build_evidence, classify_uncertainty
from playground.fragmentation.repair import join_uncertain_gaps
from playground.possession_fixes.prediction import predict_fixed
from playground.refinement.prediction import predict_refinement
from playground.refinement.specs import OCCLUSION
from playground.tests.fixtures import empty_tags, features


@pytest.mark.parametrize(
    "codes",
    [
        [0] * 100 + [1] * 100,
        [0] * 100 + [-1] * 30 + [0] * 100,
        [1] * 100 + [-1] * 100 + [0] * 100,
    ],
)
def test_default_reproduces_existing_r06_and_f03_prediction(codes):
    original = features(codes)
    tags = empty_tags(len(codes))
    evidence = build_evidence(original, original, tags)
    anchor = predict_refinement(original, tags, OCCLUSION)
    internal = classify_uncertainty(anchor, evidence)
    expected, _ = join_uncertain_gaps(internal, evidence, original.fps)
    expected = np.where(expected == "U", "D", expected)

    actual = predict_fixed(original, original, tags)

    np.testing.assert_array_equal(actual, expected)


def test_gate_blocks_forecast_winner_when_the_opponent_is_physically_closer():
    original = features([1] * 300)
    arrival = features([1] * 120 + [0] * 180)
    tags = empty_tags(300)

    unchecked = predict_fixed(original, arrival, tags)
    guarded = predict_fixed(original, arrival, tags, control_mode="gate")

    assert (unchecked[200:] == "H").all()
    assert (guarded == "A").all()


def test_gate_requires_physical_team_separation_as_well_as_nearness():
    original = features([1] * 300)
    original.nearest_home_distance_m[120:] = 1.5
    original.nearest_away_distance_m[120:] = 1.7
    original.nearest_code[120:] = 0
    arrival = features([1] * 120 + [0] * 180)

    guarded = predict_fixed(original, arrival, empty_tags(300), control_mode="gate")

    assert (guarded == "A").all()


def test_physical_mode_can_confirm_the_actual_opponent_of_a_forecast_winner():
    original = features([0] * 120 + [1] * 180)
    arrival = features([0] * 300)
    tags = empty_tags(300)

    gated = predict_fixed(original, arrival, tags, control_mode="gate")
    physical = predict_fixed(original, arrival, tags, control_mode="physical")

    assert (gated == "H").all()
    assert (physical[200:] == "A").all()


def test_physical_initialization_changes_only_the_unconfirmed_nearest_fallback():
    original = replace(
        features([1] * 200),
        nearest_home_distance_m=np.full(200, 5.0),
        nearest_away_distance_m=np.full(200, 3.0),
    )
    arrival = replace(
        features([0] * 200),
        nearest_home_distance_m=np.full(200, 3.0),
        nearest_away_distance_m=np.full(200, 5.0),
    )
    tags = empty_tags(200)

    forecast_fallback = predict_fixed(original, arrival, tags)
    physical_fallback = predict_fixed(
        original, arrival, tags, physical_initialization=True
    )

    assert (forecast_fallback == "H").all()
    assert (physical_fallback == "A").all()


def test_extra_dead_mask_survives_smoothing_and_both_missing_gap_repairs():
    data = features([0] * 120 + [-1] * 20 + [0] * 120)
    extra_dead = np.zeros(260, dtype=bool)
    extra_dead[125:135] = True
    original_mask = extra_dead.copy()

    labels = predict_fixed(data, data, empty_tags(260), extra_dead=extra_dead)

    assert (labels[125:135] == "D").all()
    assert labels[0] == labels[-1] == "H"
    np.testing.assert_array_equal(extra_dead, original_mask)


def test_original_boundary_cues_are_preserved_even_when_arrival_coordinates_differ():
    original = features([0] * 200)
    original.ball_x_m[90:110] = -1
    arrival = replace(original, ball_x_m=np.full(200, 20.0))

    labels = predict_fixed(original, arrival, empty_tags(200))

    assert (labels[90:110] == "D").all()


def test_inference_preserves_all_source_arrays():
    original = features([0] * 120 + [1] * 120)
    arrival = features([1] * 240)
    snapshots = {
        (name, field.name): getattr(data, field.name).copy()
        for name, data in (("original", original), ("arrival", arrival))
        for field in fields(data)
        if isinstance(getattr(data, field.name), np.ndarray)
    }

    predict_fixed(
        original,
        arrival,
        empty_tags(240),
        control_mode="physical",
        physical_initialization=True,
    )

    for (name, field_name), expected in snapshots.items():
        data = original if name == "original" else arrival
        np.testing.assert_array_equal(getattr(data, field_name), expected)
