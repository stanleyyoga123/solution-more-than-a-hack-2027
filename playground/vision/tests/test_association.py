"""Test physical and ambiguity gates without model inference or match footage."""

from dataclasses import replace

import numpy as np

from playground.vision.association import recover_positions, select_proposal
from playground.vision.detection import BallDetection
from playground.vision.policy import VisionPolicy
from playground.vision.inputs import sampling_mask


def detection(frame: int, x: float, y: float = 10, confidence: float = 0.8):
    return BallDetection(frame, "missing_ball", confidence, 0, 0, 1, 1, 0.5, 0.5, x, y)


def test_select_rejects_confidence_ties_and_outside_pitch_candidates():
    pitch = np.array([105, 68])
    policy = VisionPolicy()
    selected, reason = select_proposal(
        [detection(0, 10), detection(0, 20, confidence=0.75)], pitch, policy
    )
    assert selected is None
    assert reason == "ambiguous_candidates"
    selected, _ = select_proposal(
        [detection(0, 10), detection(0, 200, confidence=0.99)], pitch, policy
    )
    assert selected.x_m == 10


def test_sampling_is_deterministic_and_controls_are_observed_only():
    original = np.zeros((100, 2))
    original[10:61] = np.nan
    policy = VisionPolicy(sample_stride=25, max_control_frames=4)
    mask, controls = sampling_mask(original, policy)
    assert len(controls) == 4
    assert np.isfinite(original[list(controls)]).all()
    assert set(np.flatnonzero(mask)) - controls == {25, 50}
    limited, _ = sampling_mask(original, replace(policy, maximum_samples=2))
    assert limited.sum() == 2


def test_recovery_interpolates_only_missing_positions_between_supported_pair():
    original = np.full((25, 2), np.nan)
    original[0] = (9.5, 10)
    proposals = {5: detection(5, 10), 15: detection(15, 11)}
    recovered, _, decisions = recover_positions(proposals, original, 10, VisionPolicy())
    assert [row["frame"] for row in recovered] == list(range(5, 16))
    assert recovered[5]["x_m"] == 10.5
    assert decisions[5] == "accepted_yolo_observation"
    assert recovered[5]["source"] == "yolo_interpolation"
    assert np.array_equal(original[0], [9.5, 10])


def test_isolated_and_excessive_speed_proposals_are_rejected():
    original = np.full((30, 2), np.nan)
    recovered, _, _ = recover_positions(
        {5: detection(5, 10)}, original, 10, VisionPolicy()
    )
    assert recovered == []
    proposals = {5: detection(5, 10), 15: detection(15, 100)}
    recovered, _, _ = recover_positions(proposals, original, 10, VisionPolicy())
    assert recovered == []


def test_source_anchor_rejection_does_not_leave_unpaired_detection():
    original = np.full((30, 2), np.nan)
    original[0] = (0, 10)
    proposals = {5: detection(5, 40), 15: detection(15, 41)}
    recovered, reasons, decisions = recover_positions(
        proposals, original, 10, VisionPolicy()
    )
    assert recovered == []
    assert reasons["incompatible_source_anchor"] == 1
    assert decisions[15] == "no_pair_after_anchor_filter"


def test_recovery_never_overwrites_source_or_fills_across_observation():
    original = np.full((25, 2), np.nan)
    original[10] = (10.5, 10)
    proposals = {5: detection(5, 10), 10: detection(10, 20), 15: detection(15, 11)}
    recovered, _, _ = recover_positions(proposals, original, 10, VisionPolicy())
    assert [row["frame"] for row in recovered] == [5, 15]


def test_immediate_source_join_has_strict_speed_limit():
    original = np.full((25, 2), np.nan)
    original[4] = (0, 10)
    proposals = {5: detection(5, 6), 15: detection(15, 7)}
    recovered, reasons, _ = recover_positions(proposals, original, 10, VisionPolicy())
    assert recovered == []
    assert reasons["immediate_join_speed_violation"] == 1


def test_conflicting_adjacent_pairs_are_rejected_and_orphans_lose_support():
    original = np.full((8, 2), np.nan)
    proposals = {
        1: detection(1, 10),
        2: detection(2, 10.1),
        3: detection(3, 50),
        4: detection(4, 50.1),
    }
    policy = VisionPolicy(sample_stride=1)
    recovered, reasons, decisions = recover_positions(proposals, original, 25, policy)
    assert recovered == []
    assert reasons["adjacent_detection_speed_conflict"] == 2
    assert reasons["no_pair_after_motion_filter"] == 2
    assert decisions[2] == decisions[3] == "adjacent_detection_speed_conflict"
    assert decisions[1] == decisions[4] == "no_pair_after_motion_filter"
    reversed_proposals = dict(reversed(list(proposals.items())))
    assert recover_positions(reversed_proposals, original, 25, policy) == (
        recovered,
        reasons,
        decisions,
    )
