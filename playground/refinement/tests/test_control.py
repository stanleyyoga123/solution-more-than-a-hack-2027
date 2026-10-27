"""Check the evidence accumulation and reset rules of tolerant control."""

from dataclasses import replace

import numpy as np

from playground.prediction_policy import DomainPolicy
from playground.refinement.control import tolerant_confirm_control
from playground.refinement.control_policy import ControlPolicy


def test_tolerant_control_backdates_switch_across_short_uncertainty():
    observed = np.zeros(7, dtype=np.int8)
    candidates = np.array([0, 1, 1, -1, 1, 1, 0], dtype=np.int8)
    result = tolerant_confirm_control(observed, candidates, np.zeros(7, bool), 10)
    assert result.tolist() == [0, 1, 1, 1, 1, 1, 1]


def test_uncertain_frames_do_not_count_towards_confirmation():
    observed = np.zeros(7, dtype=np.int8)
    candidates = np.array([0, 1, -1, 1, -1, 1, -1], dtype=np.int8)
    result = tolerant_confirm_control(observed, candidates, np.zeros(7, bool), 10)
    assert result.tolist() == [0] * 7


def test_long_uncertainty_or_incumbent_evidence_clears_pending_control():
    observed = np.zeros(10, dtype=np.int8)
    dead = np.zeros(10, dtype=bool)
    for interrupt in (-1, 0):
        candidates = np.array([0, 1, 1, interrupt, interrupt, 1, 1, 0, 0, 0], np.int8)
        result = tolerant_confirm_control(observed, candidates, dead, 10)
        assert result.tolist() == [0] * 10


def test_pending_window_expiry_prevents_accumulating_distant_evidence():
    observed = np.zeros(10, dtype=np.int8)
    candidates = np.array([0, 1, -1, 1, -1, 1, -1, 1, 0, 0], np.int8)
    policy = replace(ControlPolicy(), pending_window_seconds=0.5)
    result = tolerant_confirm_control(
        observed, candidates, np.zeros(10, bool), 10, policy=policy
    )
    assert result.tolist() == [0] * 10


def test_missing_expiry_and_dead_cue_reset_incumbent_and_pending_control():
    observed = np.array([0, 0, 0, -1, -1, -1, 1, 1], np.int8)
    candidates = np.array([0, 1, 1, -1, -1, -1, 1, 1], np.int8)
    domain = replace(DomainPolicy(), missing_bridge_seconds=0.2)
    dead = np.zeros(8, dtype=bool)
    dead[2] = True
    result = tolerant_confirm_control(observed, candidates, dead, 10, domain)
    assert result.tolist() == [0, 0, -1, -1, -1, -1, 1, 1]


def test_missing_expiry_preserves_incumbent_only_within_bridge_duration():
    observed = np.array([0, -1, -1, -1, -1], np.int8)
    domain = replace(DomainPolicy(), missing_bridge_seconds=0.2)
    result = tolerant_confirm_control(observed, observed, np.zeros(5, bool), 10, domain)
    assert result.tolist() == [0, 0, 0, -1, -1]
