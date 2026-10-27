"""Verify observable split, merge and timing diagnostics on tiny timelines."""

import numpy as np
import pytest

from playground.fragmentation.diagnostics import fragmentation_diagnostics


def test_diagnostics_counts_false_dead_ball_split_as_extra_fragment() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHHHHH")), np.array(list("HHDDHH")), 2
    )

    assert result["split_truth_spells"] == 1
    assert result["extra_same_team_fragments"] == 1
    assert result["merged_prediction_spells"] == 0
    assert result["spurious_boundaries_1s"] == 2
    assert result["missed_boundaries_1s"] == 0


def test_diagnostics_counts_bridge_across_true_stoppage_as_merge() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHDDHH")), np.array(list("HHHHHH")), 2
    )

    assert result["merged_prediction_spells"] == 1
    assert result["extra_truth_spells_merged"] == 1
    assert result["split_truth_spells"] == 0
    assert result["missed_boundaries_1s"] == 2
    assert result["spurious_boundaries_1s"] == 0


def test_diagnostics_reports_delayed_boundary_in_seconds() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHHHAAAA")), np.array(list("HHHHHHAA")), 4
    )

    assert result["matched_boundaries_1s"] == 1
    assert result["missed_boundaries_1s"] == 0
    assert result["spurious_boundaries_1s"] == 0
    assert result["mean_abs_boundary_error_s"] == pytest.approx(0.5)
    assert result["mean_signed_boundary_error_s"] == pytest.approx(0.5)


def test_diagnostics_requires_both_origin_and_destination_for_boundary_match() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHAAAA")), np.array(list("DDAAAA")), 4
    )

    assert result["matched_boundaries_1s"] == 0
    assert result["missed_boundaries_1s"] == 1
    assert result["spurious_boundaries_1s"] == 1
    assert result["mean_abs_boundary_error_s"] is None
    assert result["mean_signed_boundary_error_s"] is None


def test_diagnostics_never_matches_boundaries_or_merges_spells_across_ungraded_gap() -> (
    None
):
    result = fragmentation_diagnostics(
        np.array(list("HAAXHHH")), np.array(list("HHHXHAA")), 10
    )

    assert result["matched_boundaries_1s"] == 0
    assert result["missed_boundaries_1s"] == 1
    assert result["spurious_boundaries_1s"] == 1
    assert result["merged_prediction_spells"] == 0
    assert result["extra_truth_spells_merged"] == 0


def test_diagnostics_counts_even_one_frame_same_team_overlap() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHHH")), np.array(list("HAAH")), 2
    )

    assert result["split_truth_spells"] == 1
    assert result["extra_same_team_fragments"] == 1
    assert result["nonoverlapping_prediction_spells"] == 1


def test_diagnostics_uses_official_abstention_filling_inside_labelled_run() -> None:
    result = fragmentation_diagnostics(
        np.array(list("HHHH")), np.array(list("HXXH")), 2
    )

    assert result["split_truth_spells"] == 0
    assert result["extra_same_team_fragments"] == 0
    assert result["uncovered_truth_spells"] == 0
    assert result["spurious_boundaries_1s"] == 0


def test_diagnostics_returns_empty_counts_when_no_frames_are_graded() -> None:
    result = fragmentation_diagnostics(
        np.array(list("XXXX")), np.array(list("HADA")), 2
    )

    for field in (
        "split_truth_spells",
        "extra_same_team_fragments",
        "merged_prediction_spells",
        "extra_truth_spells_merged",
        "uncovered_truth_spells",
        "nonoverlapping_prediction_spells",
        "matched_boundaries_1s",
        "missed_boundaries_1s",
        "spurious_boundaries_1s",
    ):
        assert result[field] == 0
    assert result["mean_abs_boundary_error_s"] is None
    assert result["mean_signed_boundary_error_s"] is None
